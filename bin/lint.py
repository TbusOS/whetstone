#!/usr/bin/env python3
"""whetstone lint — index-hygiene checks on a skill library.

The skill SELECTION menu = every skill's (name + description), always in the agent's
context. That is where noise lives: vague / overlapping / collision-prone descriptions
make the model pick the wrong skill or miss the right one. Skill bodies are lazy-loaded
and don't count. This linter checks the menu, not the bodies.

Checks (per skill):
  E  description missing / too short        -> model has nothing to match on
  I  description very long                  -> menu token cost
  W  description over 1024 chars             -> over the Agent Skills limit (spec/skill-package.md)
  W  description is not valid YAML           -> a strict runtime may drop it (plain value with ': ')
  W  no trigger markers (触发词 / TRIGGER)   -> weak match signal
  W  in a family but no boundary line        -> risks colliding with peers
Pairwise:
  W   name near-collision                    -> e.g. foo-review vs foo-review-framework
  W  trigger-set overlap above threshold     -> two skills compete for the same prompts
Downgraded to INFO (acknowledged, not noise):
  - companion suffix (-audit/-validator/...) whose description references the base
    (e.g. gated-dual-clone-audit audits gated-dual-clone) — intentional, not a clash
  - high trigger overlap where each description names the other (mutually disambiguated)
Menu size (the whole library at once):
  W  menu over budget                        -> the runtime keeps every name but drops
                                                descriptions to fit; a skill without its
                                                description is picked by name alone
  I  menu size, the fair share per description, which descriptions to trim first
With --listing (the menu a runtime actually sent; adapters/menu/<runtime>.py prints it):
  W  skills shown as name only               -> their triggers never reached the model
  W  menu shows a different description      -> e.g. over a runtime's own cap it showed the
                                                body's first heading instead
  I  skill missing from the snapshot         -> installed after it, or not picked up

Why a budget and not a per-skill limit: descriptions are fine one by one and still do not
fit together. Measured on one library (2026-09-29, Claude Code): 76 session-start menus
stayed at 24,536-26,880 chars while entries grew from 69 to 111, so the entries that
carried a description stayed at 46-56 and 35 of 65 skills were names only. Of 197 user
messages that used a skill's trigger words, 26% loaded it when its description was in
the menu and 1% when only its name was. The budget is a runtime property, so it is a flag
(--menu-budget, default 25000 = that measurement); Claude Code documents it as about 1%
of the context window, and it moves with the model: the same library got a 25,123-char
menu in an Opus session and a 7,978-char one in a Haiku 4.5 session, where every one of
its skills was a bare name. Check with the model you actually run.

Skills marked disable-model-invocation: true are left out of the size: only the user can
invoke them and their description is not in context (Claude Code docs; confirmed on a
live menu, where such skills had no entry at all).

Runtime-neutral: --src is any skills dir (default WHETSTONE_SKILLS_DIR or ~/.claude/skills).
stdlib only. Exit 1 if any ERROR (or any WARNING with --strict).

  bin/lint.py [--src DIR] [--json] [--strict] [--no-symlinks]
              [--menu-budget N] [--menu-reserve N] [--listing FILE|-]
"""
import os
import sys
import re
import json
import argparse

# --- tunables (kept explicit so the contract is auditable) -----------------
MIN_DESC = 40           # below this = effectively missing -> ERROR
LONG_DESC = 700         # above this = INFO (menu cost, not an error)
SPEC_DESC_MAX = 1024    # Agent Skills limit (spec/skill-package.md) -> WARN. Claude Code's own
                        # cap is 1,536; one skill over it was shown with its body's first
                        # heading instead of its description (2026-09-29, one case)
MENU_BUDGET = 25000     # chars for the whole menu; see the module docstring for where it comes from
MENU_TRIM_SHOWN = 8     # how many trim candidates the text report lists (JSON has all)
ROUTER_MARK = "<!-- whetstone:router -->"   # written by `index.py --router` (spec/routing.md)
OVERLAP_WARN = 0.40     # trigger-set Jaccard >= this between two skills -> WARN
FAMILY_T = 0.12         # trigger Jaccard >= this means "same family" (boundary line expected)
SEP = re.compile(r"[/、,，;；:：。.\s|·]+")
TRIGGER_MARK = re.compile(r"触发词|TRIGGER", re.I)
BOUNDARY_MARK = re.compile(r"DO NOT|不重复|同族|不触发|不适用|use .+-", re.I)
# suffixes that denote an intentional companion skill (evaluator/checker of, or deliberate
# sidekick to, the base), e.g. gated-dual-clone-audit audits gated-dual-clone,
# whetstone-curator curates across whetstone libraries. NOT a collision if the longer
# skill's description references the base. Distinguishes good companions from accidental
# prefix clashes (design-review-framework had "framework" — not a companion suffix).
COMPANION_SUFFIX = {"audit", "validator", "review", "critic", "evaluator",
                    "lint", "test", "check", "verify", "checker", "curator"}


_DQ_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r", "0": "\0",
               " ": " ", "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "v": "\v"}


def _close_quote(text, q):
    """Index of the closing quote in a YAML flow scalar body, or None if still open.
    Double quotes escape with a backslash; single quotes escape by doubling."""
    i = 0
    while i < len(text):
        c = text[i]
        if q == '"' and c == "\\":
            i += 2
            continue
        if c == q:
            if q == "'" and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            return i
        i += 1
    return None


def _fold(raw):
    """YAML line folding for flow scalars: a line break becomes a space, an empty
    line becomes a newline, and the indentation of continuation lines is dropped."""
    out, pending_nl = [], 0
    for n, ln in enumerate(raw.split("\n")):
        s = ln.strip() if n else ln.rstrip()
        if not s and n:
            pending_nl += 1
            continue
        if n:
            out.append("\n" * pending_nl if pending_nl else " ")
        pending_nl = 0
        out.append(s)
    return "".join(out)


def _unescape_dq(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in _DQ_ESCAPES:
                out.append(_DQ_ESCAPES[nxt])
                i += 2
                continue
            if nxt in "xuU":
                width = {"x": 2, "u": 4, "U": 8}[nxt]
                try:
                    out.append(chr(int(s[i + 2:i + 2 + width], 16)))
                    i += 2 + width
                    continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return "".join(out)


def parse_frontmatter(path, problems=None):
    """Return the YAML frontmatter as a dict of top-level string values.

    Reads the scalar forms skill files actually use: block scalars (> and |), quoted
    strings that run over several lines — even when a continuation line starts at
    column 0, which is legal inside quotes — and plain multi-line strings. A value
    that is not valid YAML is still read, and a note goes into `problems` (key ->
    reason), because a runtime that parses strictly may drop it (2026-09-29: an
    earlier version of this parser read only the first line of a quoted
    description and took its second line for a new key)."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    fm = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = lines[1:i]
            break
    if fm is None:
        return {}
    out, i = {}, 0
    while i < len(fm):
        ln = fm[i]
        if ":" not in ln or ln.startswith((" ", "\t", "#")):
            i += 1
            continue
        k, v = ln.split(":", 1)
        k, v = k.strip(), v.strip()
        if v in (">", "|", ">-", "|-", ">+", "|+"):
            blk, j = [], i + 1
            while j < len(fm) and (fm[j].startswith((" ", "\t")) or fm[j].strip() == ""):
                blk.append(fm[j].strip())
                j += 1
            joiner = "\n" if v.startswith("|") else " "
            out[k] = joiner.join(x for x in blk if x)
            i = j
            continue
        if v[:1] in ('"', "'"):
            q, body, j = v[0], v[1:], i + 1
            end = _close_quote(body, q)
            while end is None and j < len(fm):
                body += "\n" + fm[j]
                j += 1
                end = _close_quote(body, q)
            if end is None:
                if problems is not None:
                    problems[k] = f"the {q}-quoted value is never closed"
                out[k] = _fold(body)
                i = j
                continue
            raw = _fold(body[:end])
            out[k] = _unescape_dq(raw) if q == '"' else raw.replace("''", "'")
            i = j
            continue
        # plain scalar: indented lines that follow continue it
        parts, j = [v], i + 1
        while v and j < len(fm) and fm[j].startswith((" ", "\t")) and fm[j].strip():
            parts.append(fm[j].strip())
            j += 1
        val = " ".join(parts)
        if problems is not None and val:
            if ": " in val or val.endswith(":"):
                problems[k] = "an unquoted value contains ': ' — YAML reads that as a new key; quote the value"
            elif " #" in val:
                problems[k] = "an unquoted value contains ' #' — YAML cuts the rest off as a comment; quote the value"
        out[k] = val
        i = j
    return out


def load_skills(src, include_symlinks=True):
    skills = []
    for name in sorted(os.listdir(src)):
        d = os.path.join(src, name)
        sk = os.path.join(d, "SKILL.md")
        if not os.path.isfile(sk):
            continue
        is_link = os.path.islink(d)
        if is_link and not include_symlinks:
            continue
        problems = {}
        fm = parse_frontmatter(sk, problems)
        try:
            is_router = ROUTER_MARK in open(sk, encoding="utf-8", errors="replace").read()
        except OSError:
            is_router = False
        desc = fm.get("description", "") or ""
        extra = fm.get("when_to_use", "") or ""   # Claude Code shows it with the description
        skills.append({
            "dir": name,
            "name": fm.get("name", name) or name,
            "desc": desc,
            "menu_desc": desc + (" " + extra if extra else ""),
            "yaml_problem": problems.get("description") or problems.get("when_to_use"),
            # disable-model-invocation: true = only the user can invoke it, and its
            # description is not in the model's context (Claude Code docs), so it takes
            # no menu space
            "hidden": str(fm.get("disable-model-invocation", "")).strip().lower() in ("true", "yes", "on"),
            "router": is_router,
            "path": sk,
            "symlink": is_link,
        })
    return skills


# --- menu size --------------------------------------------------------------

def menu_entry_len(name, desc):
    """Chars one skill costs in the menu: '- name: desc' plus the line break, or
    '- name' when the description was dropped (matches Claude Code's listing text)."""
    return len(name) + 5 + len(desc) if desc else len(name) + 3


def parse_listing(text):
    """Parse a menu as a runtime sent it: one '- name: description' or '- name' per
    entry. A description that contains a line break (YAML '\\n' in a double-quoted
    value) continues on lines that do not start with '- '. Returns {name: desc|None}."""
    entries, cur = {}, None
    for ln in text.splitlines():
        if ln.startswith("- "):
            body = ln[2:]
            cut = body.find(": ")
            if cut > 0:
                cur = body[:cut]
                entries[cur] = body[cut + 2:]
            else:
                cur = body.strip()
                entries[cur] = None
        elif cur is not None and entries.get(cur) is not None:
            entries[cur] += "\n" + ln
    return entries


def _norm(s):
    return " ".join((s or "").split())


def router_check(skills):
    """The generated router must list every skill beside it; one that is missing can only
    be found through the menu, which is the thing the router is there to get around."""
    issues = []
    for r in (s for s in skills if s.get("router")):
        root = os.path.dirname(r["path"])
        texts = []
        for f in [r["path"]] + sorted(os.path.join(root, "families", x)
                                      for x in (os.listdir(os.path.join(root, "families"))
                                                if os.path.isdir(os.path.join(root, "families")) else [])
                                      if x.endswith(".md")):
            try:
                texts.append(open(f, encoding="utf-8").read())
            except OSError:
                pass
        listed = set(re.findall(r"^- \*\*([^*]+)\*\*", "\n".join(texts), re.M))
        missing = sorted(s["name"] for s in skills if not s.get("router") and s["name"] not in listed)
        if missing:
            issues.append(("W", r["name"], f"the router is out of date: {len(missing)} skill(s) are not in its "
                           f"catalog ({', '.join(missing)}) — regenerate with `whetstone index --router`"))
    return issues


def menu_check(skills, budget, reserve=None, listing=None):
    """Whole-library check: does the menu fit? Returns (issues, report)."""
    issues = []
    hidden = [s for s in skills if s.get("hidden")]
    skills = [s for s in skills if not s.get("hidden")]
    n = len(skills)
    full = sum(menu_entry_len(s["name"], s["menu_desc"]) for s in skills)
    overhead = sum(len(s["name"]) + 5 for s in skills)   # '- name: ' + line break, per entry
    rep = {"entries": n, "chars": full, "budget": budget, "hidden": [s["name"] for s in hidden]}

    snap = foreign = None
    if listing is not None:
        snap = parse_listing(listing)
        ours = {s["name"] for s in skills + hidden} | {s["dir"] for s in skills + hidden}
        foreign = {k: v for k, v in snap.items() if k not in ours}
        reserve, rep["reserve_source"] = sum(menu_entry_len(k, v) for k, v in foreign.items()), "listing"
    elif reserve is None:
        reserve, rep["reserve_source"] = 0, "not counted"
    else:
        rep["reserve_source"] = "--menu-reserve"
    rep["reserve"] = reserve
    over = full + reserve - budget
    rep["over"] = over

    # Fair share: what each description may use if every entry keeps one. Trimming every
    # description above it down to it always fits — the ones below it leave slack — so
    # the only case trimming cannot fix is a share too small to say anything.
    room = budget - reserve - overhead
    fair = room // n if n and room > 0 else 0
    heavy = sorted((s for s in skills if len(s["menu_desc"]) > fair),
                   key=lambda s: (-len(s["menu_desc"]), s["name"]))
    savings = sum(len(s["menu_desc"]) - fair for s in heavy)
    rep.update(fair_share=fair, savings=savings,
               trim=[{"name": s["name"], "chars": len(s["menu_desc"]),
                      "over_fair_share": len(s["menu_desc"]) - fair} for s in heavy])

    if over > 0:
        if fair == 0:
            msg = (f"menu needs ~{full + reserve} chars, budget is {budget}: the names alone plus "
                   f"{reserve} chars from outside this library already fill it — retire or merge skills")
        else:
            msg = (f"menu needs ~{full + reserve} chars, budget is {budget} (over by {over}). The runtime "
                   f"keeps every name but drops descriptions to fit (Claude Code: least-used skills "
                   f"first), and a skill without its description is picked by name alone. Fair share "
                   f"≈ {fair} chars per description; {len(heavy)} are above it, trimming them to it "
                   f"saves {savings}")
            if fair < MIN_DESC:
                msg += (f" — but a {fair}-char share is below the {MIN_DESC} a description needs to be "
                        f"matched on: retire or merge skills instead")
        issues.append(("W", "(menu)", msg))

    if snap is not None:
        name_only, differ, missing = [], [], []
        for s in skills:
            key = s["name"] if s["name"] in snap else (s["dir"] if s["dir"] in snap else None)
            if key is None:
                missing.append(s["name"])
                continue
            shown = snap[key]
            if shown is None:
                name_only.append(s["name"])
            elif _norm(shown) != _norm(s["menu_desc"]):
                differ.append(s["name"])
                issues.append(("W", s["name"], f"the menu shows a different description ({len(shown)} chars) "
                               f"than SKILL.md ({len(s['menu_desc'])} chars) — over a runtime's own cap, or a "
                               f"frontmatter the runtime parsed differently; the triggers in SKILL.md are not "
                               f"what the model saw"))
        for s in skills:
            if s.get("router") and s["name"] in name_only:
                issues.append(("W", s["name"], "the router itself is shown as name only — keep its one line in the "
                               "always-loaded rules file, which the menu budget does not touch (spec/routing.md §4 ③)"))
        if name_only:
            issues.append(("W", "(menu)", f"{len(name_only)} of {n} skills are shown as name only in the "
                           f"menu snapshot — their triggers never reached the model: {', '.join(name_only)}"))
        for m in missing:
            issues.append(("I", m, "not in the menu snapshot (installed after it, or the runtime did not pick it up)"))
        for h in hidden:
            if h["name"] in snap or h["dir"] in snap:
                issues.append(("W", h["name"], "marked disable-model-invocation, yet it is in the menu snapshot — the "
                               "runtime did not hide it (snapshot taken before the change, or the runtime ignores the flag)"))
        rep["snapshot"] = {"entries": len(snap), "chars": len(listing.rstrip("\n")), "foreign_entries": len(foreign),
                           "name_only": name_only, "different": differ, "missing": missing}
    return issues, rep


def trigger_tokens(desc):
    """Tokens from the trigger span (after 触发词/TRIGGER, up to a boundary marker)."""
    m = TRIGGER_MARK.search(desc)
    if not m:
        return set()
    span = desc[m.end():]
    b = BOUNDARY_MARK.search(span)
    if b:
        span = span[:b.start()]
    toks = {t.strip().lower() for t in SEP.split(span)}
    return {t for t in toks if len(t) >= 2 and not t.isdigit()}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def name_collision(a, b):
    """True if one kebab name's segments are a prefix of the other's."""
    sa, sb = a.split("-"), b.split("-")
    if sa == sb:
        return False
    short, long = (sa, sb) if len(sa) < len(sb) else (sb, sa)
    return long[:len(short)] == short


def lint(skills):
    issues = []  # (severity, skill_or_pair, message)

    def add(sev, who, msg):
        issues.append((sev, who, msg))

    trig = {s["name"]: trigger_tokens(s["desc"]) for s in skills}
    by_name = {s["name"]: s for s in skills}

    # family membership: who shares triggers with whom
    family = {s["name"]: [] for s in skills}
    names = [s["name"] for s in skills]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            jac = jaccard(trig[a], trig[b])
            if jac >= FAMILY_T:
                family[a].append((b, jac))
                family[b].append((a, jac))
            if jac >= OVERLAP_WARN:
                mutual = (re.search(r"\b" + re.escape(b) + r"\b", by_name[a]["desc"])
                          and re.search(r"\b" + re.escape(a) + r"\b", by_name[b]["desc"]))
                if mutual:
                    add("I", f"{a} ◂▸ {b}", f"trigger overlap (Jaccard={jac:.2f}) but each description names the other — disambiguated, ok")
                else:
                    add("W", f"{a} ~ {b}", f"trigger sets overlap (Jaccard={jac:.2f}) — they compete for the same prompts; add a boundary line naming the other")
            if name_collision(a, b):
                sa, sb = a.split("-"), b.split("-")
                short, long = (a, b) if len(sa) < len(sb) else (b, a)
                extra = long.split("-")[len(short.split("-")):]
                companion = (extra and all(s in COMPANION_SUFFIX for s in extra)
                             and re.search(r"\b" + re.escape(short) + r"\b", by_name[long]["desc"]))
                if companion:
                    add("I", f"{short} ◂ {long}", f"intentional companion (-{'-'.join(extra)}): {long} is a deliberate companion of {short} and references it — ok")
                else:
                    add("W", f"{a} ~ {b}", "name near-collision (segment prefix) — model can pick the wrong one. Companion suffixes (-audit/-validator) that reference the base are fine; else rename")

    for s in skills:
        nm = s["name"]
        tag = " [symlink]" if s["symlink"] else ""
        d = s["desc"]
        if s.get("yaml_problem"):
            add("W", nm + tag, f"frontmatter is not valid YAML: {s['yaml_problem']} — a runtime that parses strictly may drop the description")
        if len(d) < MIN_DESC:
            add("E", nm + tag, f"description missing/too short ({len(d)} chars) — nothing for the model to match on")
            continue
        if len(d) > SPEC_DESC_MAX:
            add("W", nm + tag, f"description is {len(d)} chars, over the Agent Skills limit of {SPEC_DESC_MAX} "
                "(spec/skill-package.md) — a runtime may cut or replace it (Claude Code showed one over its own "
                "1,536 cap with the body's first heading instead)")
        elif len(d) > LONG_DESC:
            add("I", nm + tag, f"description long ({len(d)} chars) — ok if it's all triggers/boundaries, else trim")
        if not TRIGGER_MARK.search(d):
            add("W", nm + tag, "no trigger markers (触发词 / TRIGGER ...) — weak match signal")
        if family[nm] and not BOUNDARY_MARK.search(d):
            peers = ", ".join(p for p, _ in sorted(family[nm], key=lambda x: -x[1])[:3])
            add("W", nm + tag, f"shares triggers with [{peers}] but has no boundary line (DO NOT TRIGGER / 不重复 / 同族)")
    return issues


def print_menu(m):
    src = {"listing": "measured from --listing", "--menu-reserve": "--menu-reserve",
           "not counted": "not counted — pass --listing or --menu-reserve"}[m["reserve_source"]]
    print("MENU  (every skill's name + description: paid by every session, before any skill is used)")
    hid = f" (+{len(m['hidden'])} hidden from the model: disable-model-invocation)" if m.get("hidden") else ""
    print(f"  this library  {m['entries']} entries, {m['chars']:,} chars{hid}")
    print(f"  outside it    {m['reserve']:,} chars ({src})")
    print(f"  budget        {m['budget']:,} chars (--menu-budget)")
    if m["over"] > 0:
        print(f"  over by       {m['over']:,} chars")
    else:
        print(f"  headroom      {-m['over']:,} chars")
    print(f"  fair share    ≈{m['fair_share']:,} chars per description")
    if m["over"] > 0 and m["trim"]:
        top = m["trim"][:MENU_TRIM_SHOWN]
        print(f"  trim first    ({len(m['trim'])} above the fair share, largest first; saves {m['savings']:,} in all)")
        for t in top:
            print(f"                {t['name']}  {t['chars']:,}  (+{t['over_fair_share']:,})")
        if len(m["trim"]) > len(top):
            print(f"                … {len(m['trim']) - len(top)} more in --json")
    snap = m.get("snapshot")
    if snap:
        print(f"  snapshot      {snap['entries']} entries, {snap['chars']:,} chars; "
              f"{len(snap['name_only'])} of this library's {m['entries']} shown as name only, "
              f"{len(snap['different'])} with a different description")
    print()


def main():
    ap = argparse.ArgumentParser(description="whetstone lint — skill index hygiene")
    ap.add_argument("--src", default=os.environ.get("WHETSTONE_SKILLS_DIR",
                    os.path.expanduser("~/.claude/skills")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--no-symlinks", action="store_true", help="skip symlinked skills")
    ap.add_argument("--menu-budget", type=int, default=MENU_BUDGET,
                    help=f"chars the runtime spends on the whole menu (default {MENU_BUDGET})")
    ap.add_argument("--menu-reserve", type=int, default=None,
                    help="chars taken by menu entries outside this library (built-in / plugin skills)")
    ap.add_argument("--listing", metavar="FILE",
                    help="the menu a runtime actually sent ('-' = stdin); "
                         "adapters/menu/claude-code.py prints Claude Code's latest")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"src not found: {args.src}", file=sys.stderr)
        return 2
    listing = None
    if args.listing:
        try:
            listing = sys.stdin.read() if args.listing == "-" else open(args.listing, encoding="utf-8").read()
        except OSError as e:
            print(f"cannot read --listing: {e}", file=sys.stderr)
            return 2
        if not parse_listing(listing):
            print("--listing has no '- name' entries — not a skill menu", file=sys.stderr)
            return 2
    skills = load_skills(args.src, include_symlinks=not args.no_symlinks)
    if not skills:
        print(f"no skills (no */SKILL.md) under {args.src}", file=sys.stderr)
        return 2
    issues = lint(skills) + router_check(skills)
    m_issues, menu = menu_check(skills, args.menu_budget, args.menu_reserve, listing)
    issues += m_issues
    E = [x for x in issues if x[0] == "E"]
    W = [x for x in issues if x[0] == "W"]
    I = [x for x in issues if x[0] == "I"]

    if args.json:
        print(json.dumps({
            "src": args.src, "skills": len(skills),
            "errors": [{"who": w, "msg": m} for _, w, m in E],
            "warnings": [{"who": w, "msg": m} for _, w, m in W],
            "infos": [{"who": w, "msg": m} for _, w, m in I],
            "menu": menu,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"whetstone lint — {args.src}  ({len(skills)} skills in menu)\n")
        for label, group in (("ERROR", E), ("WARN", W), ("INFO", I)):
            if not group:
                continue
            print(f"{label} ({len(group)})")
            for _, who, msg in group:
                print(f"  {who}: {msg}")
            print()
        print_menu(menu)
        print(f"summary: {len(E)} error(s), {len(W)} warning(s), {len(I)} info across {len(skills)} skills")

    if E:
        return 1
    if W and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

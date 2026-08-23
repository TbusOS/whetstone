#!/usr/bin/env python3
"""whetstone lint — index-hygiene checks on a skill library.

The skill SELECTION menu = every skill's (name + description), always in the agent's
context. That is where noise lives: vague / overlapping / collision-prone descriptions
make the model pick the wrong skill or miss the right one. Skill bodies are lazy-loaded
and don't count. This linter checks the menu, not the bodies.

Checks (per skill):
  E  description missing / too short        -> model has nothing to match on
  I  description very long                  -> menu token cost
  W  no trigger markers (触发词 / TRIGGER)   -> weak match signal
  W  in a family but no boundary line        -> risks colliding with peers
Pairwise:
  W   name near-collision                    -> e.g. foo-review vs foo-review-framework
  W  trigger-set overlap above threshold     -> two skills compete for the same prompts
Downgraded to INFO (acknowledged, not noise):
  - companion suffix (-audit/-validator/...) whose description references the base
    (e.g. gated-dual-clone-audit audits gated-dual-clone) — intentional, not a clash
  - high trigger overlap where each description names the other (mutually disambiguated)

Runtime-neutral: --src is any skills dir (default WHETSTONE_SKILLS_DIR or ~/.claude/skills).
stdlib only. Exit 1 if any ERROR (or any WARNING with --strict).

  bin/lint.py [--src DIR] [--json] [--strict] [--no-symlinks]
"""
import os
import sys
import re
import json
import argparse

# --- tunables (kept explicit so the contract is auditable) -----------------
MIN_DESC = 40           # below this = effectively missing -> ERROR
LONG_DESC = 700         # above this = INFO (menu cost, not an error)
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


def parse_frontmatter(path):
    """Return the YAML frontmatter as a dict. Folded/literal block scalars
    (description: > / |) are joined into one string."""
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
        if ":" in ln and not ln.startswith((" ", "\t")):
            k, v = ln.split(":", 1)
            k, v = k.strip(), v.strip()
            if v in (">", "|", ">-", "|-", ">+", "|+"):
                blk, j = [], i + 1
                while j < len(fm) and (fm[j].startswith((" ", "\t")) or fm[j].strip() == ""):
                    blk.append(fm[j].strip())
                    j += 1
                out[k] = " ".join(x for x in blk if x)
                i = j
                continue
            out[k] = v.strip('"').strip("'")
        i += 1
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
        fm = parse_frontmatter(sk)
        skills.append({
            "dir": name,
            "name": fm.get("name", name),
            "desc": fm.get("description", "") or "",
            "symlink": is_link,
        })
    return skills


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
        if len(d) < MIN_DESC:
            add("E", nm + tag, f"description missing/too short ({len(d)} chars) — nothing for the model to match on")
            continue
        if len(d) > LONG_DESC:
            add("I", nm + tag, f"description long ({len(d)} chars) — ok if it's all triggers/boundaries, else trim")
        if not TRIGGER_MARK.search(d):
            add("W", nm + tag, "no trigger markers (触发词 / TRIGGER ...) — weak match signal")
        if family[nm] and not BOUNDARY_MARK.search(d):
            peers = ", ".join(p for p, _ in sorted(family[nm], key=lambda x: -x[1])[:3])
            add("W", nm + tag, f"shares triggers with [{peers}] but has no boundary line (DO NOT TRIGGER / 不重复 / 同族)")
    return issues


def main():
    ap = argparse.ArgumentParser(description="whetstone lint — skill index hygiene")
    ap.add_argument("--src", default=os.environ.get("WHETSTONE_SKILLS_DIR",
                    os.path.expanduser("~/.claude/skills")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--no-symlinks", action="store_true", help="skip symlinked skills")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"src not found: {args.src}", file=sys.stderr)
        return 2
    skills = load_skills(args.src, include_symlinks=not args.no_symlinks)
    if not skills:
        print(f"no skills (no */SKILL.md) under {args.src}", file=sys.stderr)
        return 2
    issues = lint(skills)
    E = [x for x in issues if x[0] == "E"]
    W = [x for x in issues if x[0] == "W"]
    I = [x for x in issues if x[0] == "I"]

    if args.json:
        print(json.dumps({
            "src": args.src, "skills": len(skills),
            "errors": [{"who": w, "msg": m} for _, w, m in E],
            "warnings": [{"who": w, "msg": m} for _, w, m in W],
            "infos": [{"who": w, "msg": m} for _, w, m in I],
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
        print(f"summary: {len(E)} error(s), {len(W)} warning(s), {len(I)} info across {len(skills)} skills")

    if E:
        return 1
    if W and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""whetstone index — generate a human-readable INDEX.md catalog of a skill library.

Groups skills into families (so a growing library stays navigable) and prints one
line per skill: its capability summary (the description up to the trigger list).
Family edges come from three signals: shared trigger tokens, name near-collision,
and cross-references (one description naming another skill).

Runtime-neutral. stdlib only. Reuses the parser/heuristics from lint.py.

  bin/index.py [--src DIR] [--out FILE]      # default: print to stdout

--router writes a skill instead (spec/routing.md, trigger ③): one short menu entry whose
body is the catalog of the whole library, so a session can find an entry it cannot see
in the menu — descriptions get dropped once the menu is over budget, and a library that
keeps growing always ends up there. Skills scoped to project dirs (skill-scopes.tsv) are
not in the global dir, so they are listed from --scopes with where they live.

  bin/index.py --router --src DIR [--src DIR ...] [--scopes FILE] --out DIR/SKILL.md
               [--name experience-router] [--split-entries 150] [--split-chars 20000]

Over either split limit the catalog becomes two levels: SKILL.md lists the families and
their members' names, and families/<n>.md next to it holds the full lines.
"""
import os
import sys
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint  # noqa: E402  (sibling module: parse_frontmatter / trigger_tokens / jaccard / name_collision / load_skills / FAMILY_T)

# segments too generic to name a family after (keep meaningful ones like "design")
GENERIC_SEG = {"workflow", "tool", "dev", "to", "md", "pdf", "markdown", "the", "for", "of"}
SUMMARY_CUT = re.compile(r"触发词|TRIGGER|DO NOT|。|\. ", re.I)
SUMMARY_MAX = 110
# A name mention preceded by one of these is a BOUNDARY ref ("not X / use X instead /
# 不重复 X") — i.e. "I am distinct from X", the opposite of a family relationship — so it
# must NOT create a family edge. Without this, the boundary lines we add for hygiene would
# ironically glue distinct skills together (e.g. sdk-code-review's "不重复 design-review"
# pulled it into the design family).
BOUNDARY_CUE = re.compile(r"(不重复|不是|不同|而非|区别|反向|无关|见|use|not|instead|DO NOT)", re.I)
# English function words are not a shared topic. Without this, two English descriptions
# were joined only because both trigger spans said "when the user ... for ... or ..."
# (2026-09-29: it chained 27 skills — page styles, stock tools, a kernel style guide —
# into one "design" family).
EDGE_STOP = {"the", "a", "an", "for", "or", "and", "to", "of", "in", "on", "at", "by", "with",
             "from", "as", "is", "are", "be", "it", "this", "that", "when", "user", "users",
             "use", "says", "say", "like", "wants", "asks", "spec", "e.g.", "eg", "etc"}
# A family bigger than this is split by the name words its members share (-design,
# -gate, kernel-, ...): cross-references to a few hub skills otherwise glue everything.
FAMILY_MAX = 12


def family_ref(desc, name):
    """True only if `desc` cites `name` as a genuine family link (e.g. 'evaluator for X'),
    not as a boundary ('not X' / 'use X instead' / '不重复 X')."""
    for m in re.finditer(r"\b" + re.escape(name) + r"\b", desc):
        if not BOUNDARY_CUE.search(desc[max(0, m.start() - 30):m.start()]):
            return True
    return False


def summary(desc):
    """First clause of a description: the capability line before triggers/boundaries,
    capped so the catalog stays scannable."""
    m = SUMMARY_CUT.search(desc)
    s = desc[:m.start()] if m else desc
    s = s.strip().rstrip("—-·,， ")
    if not s:
        s = desc[:SUMMARY_MAX]
    if len(s) > SUMMARY_MAX:
        s = s[:SUMMARY_MAX].rstrip() + "…"
    return s


def build_families(skills):
    names = [s["name"] for s in skills]
    by_name = {s["name"]: s for s in skills}
    trig = {n: lint.trigger_tokens(by_name[n]["desc"]) - EDGE_STOP for n in names}

    # union-find over family edges
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            edge = (lint.jaccard(trig[a], trig[b]) >= lint.FAMILY_T
                    or lint.name_collision(a, b)
                    or family_ref(by_name[a]["desc"], b)
                    or family_ref(by_name[b]["desc"], a))
            if edge:
                union(a, b)

    groups = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    return split_big(groups), by_name


def split_big(groups):
    """Split families over FAMILY_MAX by shared name words, largest word first; members
    that share no word with another member become single entries."""
    out = {}
    for key, members in groups.items():
        if len(members) <= FAMILY_MAX:
            out[key] = members
            continue
        left = sorted(members)
        while left:
            from collections import Counter
            segs = Counter(sg for m in left for sg in set(m.split("-"))
                           if sg not in GENERIC_SEG and len(sg) >= 2)
            best = [(c, sg) for sg, c in segs.items() if c >= 2]
            if not best:
                break
            c, sg = max(best, key=lambda x: (x[0], x[1]))
            sub = [m for m in left if sg in m.split("-")]
            out[f"{key}/{sg}"] = sub
            left = [m for m in left if m not in sub]
        for m in left:
            out[f"{key}/{m}"] = [m]
    return out


def family_label(members):
    """Most common non-generic name segment shared by >=2 members, else 'misc'."""
    from collections import Counter
    segs = Counter()
    for m in members:
        for s in set(m.split("-")):
            if s not in GENERIC_SEG and len(s) >= 2:
                segs[s] += 1
    for seg, c in segs.most_common():
        if c >= 2:
            return seg
    return None


def render(skills):
    groups, by_name = build_families(skills)
    fams = [m for m in groups.values() if len(m) >= 2]
    singles = [m[0] for m in groups.values() if len(m) == 1]
    fams.sort(key=lambda m: (-len(m), sorted(m)[0]))

    out = []
    out.append("# Skill 库索引")
    out.append("")
    out.append(f"> 自动生成(`whetstone index`)。{len(skills)} 个 skill · {len(fams)} 个族 · {len(singles)} 个独立。")
    out.append("> 索引 = selection menu 的导航。新增/改 description 后重跑;配合 `whetstone lint` 查重叠/撞车。")
    out.append("")
    for members in fams:
        lab = family_label(members)
        head = f"{lab} 族" if lab else f"{sorted(members)[0]} 等"
        out.append(f"## {head} ({len(members)})")
        out.append("")
        for n in sorted(members):
            s = by_name[n]
            tag = " `[symlink]`" if s["symlink"] else ""
            out.append(f"- **{n}**{tag} — {summary(s['desc'])}")
        out.append("")
    if singles:
        out.append(f"## 独立 ({len(singles)})")
        out.append("")
        for n in sorted(singles):
            s = by_name[n]
            tag = " `[symlink]`" if s["symlink"] else ""
            out.append(f"- **{n}**{tag} — {summary(s['desc'])}")
        out.append("")
    return "\n".join(out)


# --- router ---------------------------------------------------------------------

ROUTER_MARK = "<!-- whetstone:router -->"   # lint recognises the generated router by this line
ROUTER_NAME = "experience-router"
ROUTER_DESC = ("本机经验库总目录(自动生成,{n} 个 skill)。做专业领域的任务、或遇到不熟的专有名词 / 报错 / "
               "器件 / 流程时,先跑 whetstone find <要做的事> 或查这里,查到按名字调用;菜单里多半只剩名字,"
               "别凭菜单判断有没有。触发词:有没有经验 / 之前怎么做的 / 以前踩过 / 查经验。")
TRIG_MAX_TERMS = 6
TRIG_MAX_CHARS = 60


LEAD_INS = [re.compile(x, re.I) for x in (
    r"^TRIGGER\s*(?:when)?\s*[:：]?\s*", r"^when the user (?:says|mentions|asks)\s*[:：]?\s*",
    r"^when\s*[:：]\s*", r"^on (?:requests|phrases) like\s*", r"^当用户(?:提到|说起|说|问|要)?\s*")]


def trigger_terms(desc):
    """The trigger phrases of a description, in the order written, deduplicated, capped.
    Lead-ins like "when the user says '...'" or "当用户提到 ..." are cut off the first term."""
    m = lint.TRIGGER_MARK.search(desc)
    if not m:
        return []
    span = desc[m.end():]
    b = lint.BOUNDARY_MARK.search(span)
    if b:
        span = span[:b.start()]
    out, seen, size = [], set(), 0
    for t in re.split(r"[/、,，;；。\n|]+", span):
        t = t.strip()
        for lead in LEAD_INS:
            t = lead.sub("", t)
        t = t.strip(" :：\"'“”「」*()（）").rstrip(".").strip()
        if len(t) < 2 or t.lower() in seen or t.isdigit():
            continue
        if len(out) >= TRIG_MAX_TERMS or size + len(t) > TRIG_MAX_CHARS:
            break
        seen.add(t.lower()); out.append(t); size += len(t)
    return out


def read_scopes(path, home=None):
    """{skill: [dir, ...]} from a skill-scopes.tsv (same format deploy.sh reads)."""
    home = home or os.path.expanduser("~")
    out = {}
    if not path or not os.path.isfile(path):
        return out
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\r\n")
        if not ln.strip() or ln.startswith("#"):
            continue
        f = [x for x in ln.split("\t") if x]
        if len(f) < 2:
            continue
        dirs = [home if d == "~" else (os.path.join(home, d[2:]) if d.startswith("~/") else d) for d in f[1:]]
        out.setdefault(f[0], []).extend(dirs)
    return out


def load_many(srcs):
    """Skills from several dirs; the first dir that has a name wins."""
    seen, out = set(), []
    for src in srcs:
        for sk in lint.load_skills(src, include_symlinks=True):
            if sk["name"] in seen:
                continue
            seen.add(sk["name"])
            sk["path"] = os.path.realpath(os.path.join(src, sk["dir"], "SKILL.md"))
            out.append(sk)
    return out


def router_line(sk, scopes):
    """One skill, one line — a description with a line break in it (YAML "\\n") must not
    push the rest of the entry onto a line of its own."""
    flat = " ".join(sk["desc"].split())
    parts = [f"- **{sk['name']}** — {summary(flat)}"]
    terms = trigger_terms(flat)
    if terms:
        parts.append("触发词:" + " / ".join(terms))
    if sk.get("hidden"):
        parts.append("只能由使用者用 /" + sk["name"] + " 调用")
    if sk["name"] in scopes:
        parts.append("只在 " + "、".join(f"`{d}`" for d in scopes[sk["name"]])
                     + f" 下自动出现;在别处要用,直接读 `{sk['path']}`")
    return " · ".join(parts)


def render_router(skills, scopes, name, split_entries, split_chars):
    """Returns {relative path: text}. One file, or SKILL.md + families/*.md when over a limit."""
    skills = [s for s in skills if s["name"] != name]
    groups, by_name = build_families(skills)
    fams = sorted((m for m in groups.values() if len(m) >= 2), key=lambda m: (-len(m), sorted(m)[0]))
    singles = sorted(m[0] for m in groups.values() if len(m) == 1)
    sections = []
    for members in fams:
        lab = family_label(members)
        sections.append((f"{lab} 族" if lab else f"{sorted(members)[0]} 等", sorted(members)))
    if singles:
        sections.append(("独立", singles))
    lines = {n: router_line(by_name[n], scopes) for n in by_name}
    desc = ROUTER_DESC.format(n=len(skills))
    head = ["---", f"name: {name}", 'description: "' + desc.replace('"', '\\"') + '"', "---", "", ROUTER_MARK,
            f"# 经验总目录({len(skills)} 个 skill · {len(sections)} 组)", "",
            "> 自动生成(`whetstone index --router`),**别手改**:改了会在下次生成时被覆盖。",
            "> 用法:① 先跑 `whetstone find \"<要做的事>\"`:按名字 / 描述 / 正文 / 以前引出过它的原话打分,"
            "够不上门槛会直说没有,这时别硬套;② 或按下面的关键词找。",
            "> 找到后按名字调用(Claude Code 用 Skill 工具,菜单里只剩名字的也能调;其他 agent 直接读它的 SKILL.md)。",
            "> 标了「只在某目录下自动出现」的,在别处要用就直接读它的 SKILL.md。", ""]
    flat = list(head)
    for title, members in sections:
        flat += [f"## {title}({len(members)})", ""] + [lines[n] for n in members] + [""]
    flat_text = "\n".join(flat)
    if len(skills) <= split_entries and len(flat_text) <= split_chars:
        return {"SKILL.md": flat_text}
    files, top = {}, list(head)
    top.append("> 目录较大,分成了两层:下面每组列出成员名字,完整的一行说明在该组的分目录文件里(用读文件的方式打开)。")
    top.append("")
    for i, (title, members) in enumerate(sections, 1):
        rel = f"families/{i:02d}.md"
        top += [f"## {title}({len(members)}) → `{rel}`", "", "、".join(members), ""]
        files[rel] = "\n".join([f"# {title}({len(members)})", "", "> 自动生成,别手改。", ""] + [lines[n] for n in members]) + "\n"
    files["SKILL.md"] = "\n".join(top)
    return files


def main_router(args):
    srcs = args.src or [os.environ.get("WHETSTONE_SKILLS_DIR", os.path.expanduser("~/.claude/skills"))]
    for d in srcs:
        if not os.path.isdir(d):
            print(f"src not found: {d}", file=sys.stderr)
            return 2
    if not args.out:
        print("--router needs --out <dir>/SKILL.md", file=sys.stderr)
        return 2
    skills = load_many(srcs)
    scopes = read_scopes(args.scopes)
    missing = sorted(set(scopes) - {s["name"] for s in skills})
    if missing:
        print(f"scoped skill(s) not found in any --src: {', '.join(missing)}", file=sys.stderr)
        return 2
    files = render_router(skills, scopes, args.name, args.split_entries, args.split_chars)
    root = os.path.dirname(os.path.abspath(args.out))
    old_fam = os.path.join(root, "families")
    if os.path.isdir(old_fam):             # a previous two-level catalog: drop only our own files
        for f in os.listdir(old_fam):
            if f.endswith(".md"):
                os.remove(os.path.join(old_fam, f))
    for rel, text in files.items():
        dst = args.out if rel == "SKILL.md" else os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
    n = len([s for s in skills if s["name"] != args.name])
    print(f"whetstone index --router: {n} skills, {len(files)} file(s) -> {root}", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(description="whetstone index — generate INDEX.md catalog")
    ap.add_argument("--src", action="append", default=None,
                    help="skills dir (repeatable with --router; default WHETSTONE_SKILLS_DIR or ~/.claude/skills)")
    ap.add_argument("--out", default=None, help="write to FILE (default: stdout)")
    ap.add_argument("--router", action="store_true", help="write the routing skill instead of INDEX.md")
    ap.add_argument("--scopes", default=None, help="skill-scopes.tsv, so scoped skills are listed too")
    ap.add_argument("--name", default=ROUTER_NAME)
    ap.add_argument("--split-entries", type=int, default=150)
    ap.add_argument("--split-chars", type=int, default=20000)
    args = ap.parse_args()
    if args.router:
        return main_router(args)
    args.src = (args.src or [os.environ.get("WHETSTONE_SKILLS_DIR", os.path.expanduser("~/.claude/skills"))])[0]

    if not os.path.isdir(args.src):
        print(f"src not found: {args.src}", file=sys.stderr)
        return 2
    skills = lint.load_skills(args.src, include_symlinks=True)
    if not skills:
        print(f"no skills under {args.src}", file=sys.stderr)
        return 2
    text = render(skills)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"whetstone index: {len(skills)} skills -> {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

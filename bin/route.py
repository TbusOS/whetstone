#!/usr/bin/env python3
"""whetstone route — experience routing from session events (spec/routing.md).

Runtime-neutral: everything here reads the event lines below and nothing else. Each
agent runtime gets an adapter that turns its own session records into these lines
(Claude Code: adapters/menu/claude-code.py --export-events). The learning and the
scoring therefore work the same whichever agent produced the sessions.

Event lines (JSON, one per line; every line has v, runtime, session, ts; src optional):
  {"kind":"session","cwd":"/abs"}                       first line of a session
  {"kind":"user","text":"...","cwd":"/abs"}             a message the user typed
  {"kind":"file","path":"/abs","op":"read|edit|write|search"}
  {"kind":"load","skill":"name","via":"tool|user|read|shell","use":true|false}
  {"kind":"menu","full":true,"described":[...],"names_only":[...]}   listing at start
  {"kind":"menu","full":false,"added":[...]}            names added mid-session
  {"kind":"find","query":"..."}                         the agent ran `whetstone find`

  route.py usage --events FILE [--days 60] [--ignore-dir DIR ...]
  route.py learn --events FILE [--out F]        messages that led to each skill
  route.py find <query> [--src D] [--json]      which skills fit
  route.py replay --events FILE [--sweep]       score find on past sessions, in time order
  route.py elsewhere --events FILE --project D  skills whose use sits in another project

usage prints one row per skill x project: skill, project, sessions, last used, weight.
- Only loads with "use": true count. The adapter decides, because runtimes differ: in
  Claude Code the Skill tool is how an entry gets used and a Read of its SKILL.md is
  mostly someone editing it; in Codex and pi reading SKILL.md is the only way to use one.
- One session counts once per skill x project. A long session that loads a skill five
  times is one piece of evidence, not five (measured 2026-09-29: the top 5 sessions held
  73% of all messages; one session held all 9 repeated loads).
- "Project" = the project the session was working in when it loaded the skill: the last
  file it touched before, climbed to the first dir with a project marker (.git, .repo,
  AGENTS.md, CLAUDE.md, GEMINI.md, or a runtime's dot-dir), never home itself nor above
  it (home has ~/.claude and would swallow every unmarked dir); the dir itself when no
  marker is found; the start dir if it touched no file. Runtime state dirs (~/.claude, ~/.codex, /tmp, ...)
  and skills' own dirs (a SKILL.md above, before any project marker) are skipped: reading a session log,
  a temp file or a skill's own files is not working in a project. Measured 2026-09-29:
  without the skip, 20 of 43 loads were attributed to ~/.claude/projects or /tmp, both of
  which have a .git.
- weight = sum over sessions of 0.5 ** (age in days / 30) at the session's last load.
stdlib only.
"""
import argparse
import json
import math
import os
import random
import re
import sys
import time
from datetime import datetime

HALF_LIFE_DAYS = 30.0
# find: field weights and BM25 constants are the textbook starting values (k1 1.2,
# b 0.75); name and description count more than the body because they were written
# to say what the skill is for. MIN_COVER and TOP are starting values to be set by
# `route replay`, not measured ones.
FIELD_WEIGHTS = {"name": 3.0, "desc": 2.0, "body": 1.0, "learned": 2.0}
K1, B = 1.2, 0.75
MIN_COVER = 0.3
TOP = 3
LEARN_CHARS = 400
ELSEWHERE_MIN, ELSEWHERE_SHARE = 3, 2 / 3
CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af"
TOKEN = re.compile(f"[{CJK}]+|[a-z0-9]+")
STOP = set("""a an and are as at be but by can do for from has have how i if in into is it its
me my no not of on or our so that the their them then there these they this to use used
using was we were what when where which who why will with you your""".split())
# Chinese function words, as the character pairs the tokenizer makes of them, plus the
# particles that end up alone. Without them "帮我看下这个问题" matches every skill that
# says 这个 and 问题.
STOP |= set("""这个 那个 一下 看下 看看 帮我 帮忙 问题 怎么 什么 如何 为什 为什么 可以 需要 我们 你们
他们 一个 没有 现在 然后 还是 就是 是不 不是 这样 那样 因为 所以 如果 但是 已经 应该 能不 不能 一些
有没 我想 想要 请问 麻烦 一直 时候 之后 之前 这里 那里 哪里 这些 那些 里面 还有 以及 或者 进行 当前
目前 继续 好的 我要 你看 看一 一看 的 了 是 吗 吧 呢 啊 和 在 也 都 就 要 把 被 让""".split())
USER_SKILL_DIRS = (".claude/skills", ".agents/skills", ".codex/skills", ".config/opencode/skills",
                   ".pi/agent/skills", ".gemini/skills", ".cursor/skills")
PROJECT_SKILL_SUBDIRS = (".claude/skills", ".agents/skills", ".codex/skills", ".opencode/skills",
                         ".pi/skills", ".gemini/skills", ".cursor/skills")
PROJECT_MARKERS = (".git", ".repo", "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".claude", ".codex", ".cursor",
                   ".opencode", ".pi", ".agents")
RUNTIME_DIRS = ("~/.claude", "~/.codex", "~/.config/opencode", "~/.local/share/opencode", "~/.pi",
                "~/.gemini", "~/.cursor", "/tmp", "/var/tmp")
UNKNOWN = "(unknown)"


def parse_ts(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_events(path):
    """Event dicts from a file ('-' = stdin), skipping lines that are not JSON objects."""
    fh = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
    try:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict) and ev.get("session") and ev.get("kind"):
                yield ev
    finally:
        if fh is not sys.stdin:
            fh.close()


class Places:
    """Where a path belongs: its project root, or nowhere (runtime dir / skill library)."""

    def __init__(self, home=None, ignore=()):
        self.home = os.path.realpath(home or os.path.expanduser("~"))
        dirs = [d.replace("~", self.home, 1) if d.startswith("~") else d for d in RUNTIME_DIRS]
        dirs += list(ignore)
        tmp = os.environ.get("TMPDIR")
        if tmp:
            dirs.append(tmp)
        self.ignored = [os.path.realpath(d) for d in dirs]
        self._root, self._lib = {}, {}

    def is_ignored(self, path):
        p = os.path.realpath(path)
        return any(p == d or p.startswith(d.rstrip("/") + "/") for d in self.ignored)

    def in_skill_library(self, path):
        """True inside a skill's own dir: the nearest dir above with a SKILL.md comes before
        any project marker. A repo whose root is itself a skill (SKILL.md next to .git)
        is a project, or working on it would never count as working anywhere."""
        d = os.path.normpath(path if os.path.isdir(path) else os.path.dirname(path))
        if d not in self._lib:
            cur, hit = d, False
            while os.path.realpath(cur) != self.home:
                if any(os.path.exists(os.path.join(cur, m)) for m in PROJECT_MARKERS):
                    break
                if os.path.isfile(os.path.join(cur, "SKILL.md")):
                    hit = True
                    break
                parent = os.path.dirname(cur)
                if parent == cur:
                    break
                cur = parent
            self._lib[d] = hit
        return self._lib[d]

    def project_root(self, d):
        d = os.path.normpath(d)
        if d not in self._root:
            cur, found = d, None
            while os.path.realpath(cur) != self.home:
                if any(os.path.exists(os.path.join(cur, m)) for m in PROJECT_MARKERS):
                    found = cur
                    break
                parent = os.path.dirname(cur)
                if parent == cur:
                    break
                cur = parent
            self._root[d] = found or d
        return self._root[d]

    def work_dir(self, path):
        """The dir a touched path says the session is working in, or None to skip it."""
        if not path or self.is_ignored(path) or self.in_skill_library(path):
            return None
        return path if os.path.isdir(path) else os.path.dirname(path)


def walk_loads(events, places):
    """Every load with use=true, as a dict: session, ts, start (the session line's ts),
    skill, via, project (attributed as described above), text (the last message the
    user typed in that session before it, or None) and menu (what the model saw of the
    skill at the time: "described", "name-only", "absent", or "unknown" when the
    session has no menu line)."""
    st = {}
    for ev in events:
        s, k = ev["session"], ev["kind"]
        x = st.get(s)
        if x is None:
            x = st[s] = {"cwd": None, "last": None, "text": None, "desc": set(), "names": set(),
                         "menu": False, "start": ev.get("ts")}
        if k == "session":
            x["cwd"], x["start"] = ev.get("cwd"), ev.get("ts")
            x["last"] = None
        elif k == "file":
            w = places.work_dir(ev.get("path"))
            if w:
                x["last"] = w
        elif k == "user" and isinstance(ev.get("text"), str):
            x["text"] = ev["text"]
        elif k == "menu":
            if ev.get("full"):
                x["desc"], x["names"], x["menu"] = set(ev.get("described") or ()), set(ev.get("names_only") or ()), True
            else:
                x["desc"] |= set(ev.get("added") or ())
        elif k == "load" and ev.get("use") is True and ev.get("skill"):
            where = x["last"]
            if not where:
                c = x["cwd"]
                where = c if c and not places.is_ignored(c) else None
            sk = ev["skill"]
            menu = ("unknown" if not x["menu"] else "described" if sk in x["desc"]
                    else "name-only" if sk in x["names"] else "absent")
            yield {"session": s, "ts": ev.get("ts"), "start": x["start"], "skill": sk, "via": ev.get("via"),
                   "project": places.project_root(where) if where else UNKNOWN, "text": x["text"], "menu": menu}


def usage_table(events, days, now=None, places=None):
    now = now or time.time()
    places = places or Places()
    since = now - days * 86400
    latest = {}                                   # (skill, project, session) -> last load time
    for ld in walk_loads(events, places):
        skill, where, s = ld["skill"], ld["project"], ld["session"]
        t = parse_ts(ld["ts"])
        if t is None or t < since:
            continue
        key = (skill, where, s)
        latest[key] = max(latest.get(key, 0.0), t)
    rows = {}
    for (skill, where, s), t in latest.items():
        r = rows.setdefault((skill, where), {"sessions": 0, "last": 0.0, "w": 0.0})
        r["sessions"] += 1
        r["last"] = max(r["last"], t)
        r["w"] += 0.5 ** (max(0.0, now - t) / 86400 / HALF_LIFE_DAYS)
    out = [(skill, where, r["sessions"], datetime.fromtimestamp(r["last"]).strftime("%Y-%m-%d"), round(r["w"], 3))
           for (skill, where), r in rows.items()]
    out.sort(key=lambda x: (x[1], -x[4], x[0]))
    return out


def cmd_usage(a):
    places = Places(ignore=a.ignore_dir or ())
    rows = usage_table(read_events(a.events), a.days, places=places)
    for r in rows:
        print("\t".join(str(x) for x in r))
    print(f"route usage: {len(rows)} skill x project row(s), last {a.days} days", file=sys.stderr)
    return 0


def elsewhere(events, places, project, days, min_sessions=ELSEWHERE_MIN, share=ELSEWHERE_SHARE):
    """Skills that belong to another project, as seen from `project`: used in at least
    min_sessions sessions, at least `share` of them in one other project, none in this
    one. [(skill, that project, sessions there, sessions in all)].
    A skill with little or no use is never listed: not being used while its description
    was invisible says nothing (spec/routing.md 4.3). The thresholds were fixed before
    looking at any output."""
    project = places.project_root(project)
    by = {}
    for skill, where, sessions, _, _ in usage_table(events, days, places=places):
        if where != UNKNOWN:
            by.setdefault(skill, {})[where] = sessions
    out = []
    for skill, projs in by.items():
        total = sum(projs.values())
        if projs.get(project, 0) or total < min_sessions:
            continue
        top, n = max(projs.items(), key=lambda kv: (kv[1], kv[0]))
        if n / total >= share:
            out.append((skill, top, n, total))
    return sorted(out)


def cmd_elsewhere(a):
    rows = elsewhere(read_events(a.events), Places(ignore=a.ignore_dir or ()), a.project, a.days)
    for r in rows:
        print("\t".join(str(x) for x in r))
    print(f"route elsewhere: {len(rows)} skill(s) belong to another project (last {a.days} days)", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- learn

def learn_pairs(events, places):
    """(skill, the message that led to it) for the first use of each skill in each session.
    The first use only: the message before a second load in the same session is about
    something else by then. A skill the user started by typing /name is left out: the
    user picked it, so the message before it says nothing about how they describe it."""
    seen, out = set(), []
    for ld in walk_loads(events, places):
        if ld["via"] == "user" or not ld["text"]:
            continue
        key = (ld["session"], ld["skill"])
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(ld, text=" ".join(ld["text"].split())[:LEARN_CHARS]))
    return out


def read_learned(path):
    """{skill: [text, ...]} from a file written by `route learn`; {} when there is none."""
    got = {}
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return got
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and isinstance(r.get("skill"), str) and isinstance(r.get("text"), str):
                got.setdefault(r["skill"], []).append(r["text"])
    return got


def cmd_learn(a):
    pairs = learn_pairs(read_events(a.events), Places(ignore=a.ignore_dir or ()))
    out = a.out or default_learned()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps({k: p[k] for k in ("skill", "text", "ts", "session", "project")},
                                ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    print(f"route learn: {len(pairs)} message(s) for {len({p['skill'] for p in pairs})} skill(s) -> {out}",
          file=sys.stderr)
    return 0


# ---------------------------------------------------------------- find

def default_learned():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "whetstone", "route-learned.jsonl")


def tokens(text):
    """Lower-case words of 2+ ASCII letters/digits (a plural s dropped), and pairs of
    adjacent CJK characters (a lone CJK character stays as it is). Chinese has no spaces,
    so single characters match nearly everything and whole runs match almost nothing;
    pairs are the usual middle (sqlite here has no trigram tokenizer either)."""
    out = []
    for m in TOKEN.finditer((text or "").lower()):
        w = m.group(0)
        if w[0].isascii():
            if len(w) < 2 or w in STOP:
                continue
            if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                w = w[:-1]
            out.append(w)
        elif len(w) == 1:
            if w not in STOP:
                out.append(w)
        else:
            out.extend(p for p in (w[i:i + 2] for i in range(len(w) - 1)) if p not in STOP)
    return out


def default_dirs(cwd=None, home=None):
    """Skill dirs the runtimes load from: the project ones from cwd up (nearest first,
    home excluded), then the user ones. Only dirs that exist."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    cur, dirs = os.path.realpath(cwd or os.getcwd()), []
    while cur != home and cur.startswith(home.rstrip("/") + "/"):
        dirs += [os.path.join(cur, sub) for sub in PROJECT_SKILL_SUBDIRS]
        cur = os.path.dirname(cur)
    dirs += [os.path.join(home, d) for d in USER_SKILL_DIRS]
    return [d for d in dirs if os.path.isdir(d)]


def load_library(dirs):
    """Skills an agent may pick, first dir wins on a name clash (project before user).
    Left out: the routing skill itself, and skills only the user may start
    (disable-model-invocation), since the user chose to keep those out of the model's way."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import lint
    seen_name, seen_path, docs = set(), set(), []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for sk in lint.load_skills(d):
            real = os.path.realpath(sk["path"])
            if sk["router"] or sk["hidden"] or sk["name"] in seen_name or real in seen_path:
                continue
            seen_name.add(sk["name"])
            seen_path.add(real)
            try:
                text = open(sk["path"], encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            body = text.split("\n---", 2)[-1] if text.startswith("---") else text
            docs.append({"name": sk["name"], "path": sk["path"], "desc": sk["menu_desc"], "body": body})
    return docs


class Index:
    """BM25F over the fields of FIELD_WEIGHTS (Robertson & Zaragoza 2009, simplified:
    one k1, one b, per-field length normalisation)."""

    def __init__(self, docs, learned=None):
        learned = learned or {}
        self.docs = docs
        self.tf, self.len = [], []
        for d in docs:
            fields = {"name": tokens(d["name"].replace("-", " ")), "desc": tokens(d["desc"]),
                      "body": tokens(d["body"]), "learned": tokens(" ".join(learned.get(d["name"], ())))}
            self.tf.append({f: _count(t) for f, t in fields.items()})
            self.len.append({f: len(t) for f, t in fields.items()})
        n = max(1, len(docs))
        self.avg = {f: (sum(L[f] for L in self.len) / n) or 1.0 for f in FIELD_WEIGHTS}
        self.df = {}
        for tf in self.tf:
            for t in set().union(*tf.values()):
                self.df[t] = self.df.get(t, 0) + 1

    def idf(self, t):
        N, df = len(self.docs), self.df.get(t, 0)
        return math.log(1 + (N - df + 0.5) / (df + 0.5))

    def rank(self, query, boost=None):
        """[(score, cover, matched terms, doc)] best first, for every doc with score > 0.
        cover = the share of the query's weight (idf) that the doc matches. A query word
        no skill contains weighs as much as the average known word: leaving it out made
        "hello world weather" a 100% match for the one skill that says hello."""
        allq = list(dict.fromkeys(tokens(query)))
        q = [t for t in allq if t in self.df]
        known = sum(self.idf(t) for t in q)
        total = (known + (len(allq) - len(q)) * known / len(q)) if q else 1.0
        out = []
        for i, d in enumerate(self.docs):
            score, hit = 0.0, []
            for t in q:
                tf = sum(w * self.tf[i][f].get(t, 0) / (1 - B + B * self.len[i][f] / self.avg[f])
                         for f, w in FIELD_WEIGHTS.items())
                if tf > 0:
                    score += self.idf(t) * tf * (K1 + 1) / (K1 + tf)
                    hit.append(t)
            if score > 0:
                out.append((score * (boost or {}).get(d["name"], 1.0), sum(self.idf(t) for t in hit) / total, hit, d))
        out.sort(key=lambda r: (-r[0], r[3]["name"]))
        return out


def _count(toks):
    c = {}
    for t in toks:
        c[t] = c.get(t, 0) + 1
    return c


def project_boost(pairs, project):
    """{skill: multiplier} from how many sessions used each skill in this project:
    1 + n / (n + 2), so 1 session x1.33, 2 x1.5, never above x2. Only reorders what the
    text already matched: on its own, "what this dir used lately" predicted 2 of 23
    next uses (2026-09-29). Fixed before the first replay, not fitted to it."""
    n = {}
    for p in pairs:
        if p.get("project") == project:
            n.setdefault(p["skill"], set()).add(p.get("session"))
    return {k: 1 + len(v) / (len(v) + 2) for k, v in n.items()}


def shown(ranked, top, min_cover):
    """What find prints: the best `top`, only those covering at least min_cover."""
    return [r for r in ranked[:top] if r[1] >= min_cover]


def cmd_find(a):
    query = " ".join(a.query).strip()
    if not query:
        print("usage: whetstone find <what you are about to do>", file=sys.stderr)
        return 2
    dirs = a.src or default_dirs()
    docs = load_library(dirs)
    if not docs:
        print(f"find: no skills under {', '.join(dirs) or '(no skill dir found)'}", file=sys.stderr)
        return 2
    learned = {} if a.no_learned else read_learned(a.learned or default_learned())
    ranked = Index(docs, learned).rank(query)
    hits = shown(ranked, a.top, a.min_cover)
    if a.json:
        print(json.dumps([{"name": r[3]["name"], "path": r[3]["path"], "score": round(r[0], 3),
                           "cover": round(r[1], 3), "matched": r[2]} for r in hits], ensure_ascii=False))
        return 0
    home = os.path.expanduser("~")
    for i, (score, cover, hit, d) in enumerate(hits, 1):
        where = d["path"].replace(home, "~", 1)
        print(f"{i}. {d['name']}  (covers {cover:.0%}: {' '.join(hit[:6])})  {where}")
        desc = " ".join(d["desc"].split())
        print(f"   {desc[:120]}{'…' if len(desc) > 120 else ''}")
    if not hits:
        best = f"best: {ranked[0][3]['name']} covers {ranked[0][1]:.0%}" if ranked else "nothing matched"
        print(f"no skill fits well enough ({best}, needs {a.min_cover:.0%}); go ahead without one")
    print(f"find: {len(docs)} skills searched", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- replay

def replay(events, docs, places, top=3, min_cover=MIN_COVER, seed=0):
    """Score find against what agents actually loaded, in time order.
    Each case = the first use of a skill in a session and the message typed before it.
    Variants, all over the same skill texts:
      text     name + description + body
      learned  + messages learned from sessions that started before this one
      random   a shuffled ranking                       (must score below text)
      leaky    + messages learned from all sessions, this one included
                                                         (must score above learned)
    The last two check the scorer itself: if a ranking that cannot know anything wins,
    or one that saw the answer does not, the numbers mean nothing."""
    names = {d["name"] for d in docs}
    pairs = learn_pairs(events, places)
    cases = [p for p in pairs if p["skill"] in names]
    gone = len(pairs) - len(cases)
    rng = random.Random(seed)
    text_index = Index(docs)
    res = []
    for c in cases:
        start = parse_ts(c["start"]) or 0.0
        before, every, earlier = {}, {}, []
        for p in pairs:
            every.setdefault(p["skill"], []).append(p["text"])
            if (parse_ts(p["start"]) or 0.0) < start:
                before.setdefault(p["skill"], []).append(p["text"])
                earlier.append(p)
        boost = project_boost(earlier, c["project"]) if c["project"] != UNKNOWN else {}
        order = [d["name"] for d in docs]
        rng.shuffle(order)
        row = {"case": c, "random": order.index(c["skill"]) + 1}
        learned_index = Index(docs, before)
        for v, idx, bst in (("text", text_index, None), ("learned", learned_index, None),
                            ("project", learned_index, boost), ("leaky", Index(docs, every), None)):
            ranked = idx.rank(c["text"], bst)
            pos = next((i for i, r in enumerate(ranked, 1) if r[3]["name"] == c["skill"]), None)
            sh = [r[3]["name"] for r in shown(ranked, top, min_cover)]
            row[v] = pos
            row[v + "_shown"] = "right" if c["skill"] in sh else "wrong" if sh else "none"
        res.append(row)
    return res, gone, len(pairs)


def quiet_messages(events):
    """Typed messages after which the session used no skill before the next message.
    Not all of them needed none (the model may not have known one existed), so the share
    of them find answers is an upper bound on how often it answers when it should not."""
    pending, out = {}, []
    for ev in events:
        s, k = ev["session"], ev["kind"]
        if k == "user" and isinstance(ev.get("text"), str):
            if pending.get(s):
                out.append(pending[s])
            pending[s] = ev["text"]
        elif k == "load" and ev.get("use") is True:
            pending[s] = None
    out += [t for t in pending.values() if t]
    return [" ".join(t.split())[:LEARN_CHARS] for t in out]


def sweep(res_text_ranked, quiet_best, top, cuts):
    """Rows (cut, right, wrong, none, quiet shown) for each min_cover cut."""
    rows = []
    for cut in cuts:
        right = wrong = none = 0
        for skill, ranked in res_text_ranked:
            sh = [r[3]["name"] for r in shown(ranked, top, cut)]
            if skill in sh:
                right += 1
            elif sh:
                wrong += 1
            else:
                none += 1
        rows.append((cut, right, wrong, none, sum(1 for b in quiet_best if b >= cut)))
    return rows


def _better(a, b):
    """1 if rank a beats rank b, -1 if worse, 0 if the same; None = not found (worst)."""
    a = a if a is not None else 10 ** 9
    b = b if b is not None else 10 ** 9
    return (a < b) - (a > b)


def verdict(wins, losses, win_projects):
    if losses > wins:
        return "worse"
    if ((wins >= 5 and losses == 0) or (wins >= 7 and losses <= 1)) and win_projects >= 2:
        return "keep"
    return "insufficient evidence"


def cmd_replay(a):
    docs = load_library(a.src or default_dirs())
    events = list(read_events(a.events))
    res, gone, total = replay(events, docs, Places(ignore=a.ignore_dir or ()), a.top, a.min_cover)
    n = len(res)
    print(f"route replay: {n} case(s) from {total} first use(s) with a typed message before them; "
          f"{gone} left out (skill no longer in the library); {len(docs)} skills")
    if not n:
        return 0

    def hit(v, k):
        return sum(1 for r in res if r[v] is not None and r[v] <= k)

    print(f"{'variant':<9}{'top1':>6}{'top' + str(a.top):>6}   shown: right / wrong / none")
    for v in ("random", "text", "learned", "project", "leaky"):
        tail = ""
        if v != "random":
            c = {s: sum(1 for r in res if r[v + "_shown"] == s) for s in ("right", "wrong", "none")}
            tail = f"   {c['right']:>5} / {c['wrong']:>5} / {c['none']:>4}"
        print(f"{v:<9}{hit(v, 1):>6}{hit(v, a.top):>6}{tail}")
    rnd, txt, lrn, lky = (hit(v, a.top) for v in ("random", "text", "learned", "leaky"))
    ok_r, ok_l = rnd < txt, lky > lrn
    print(f"scorer check: random {rnd} < text {txt} {'ok' if ok_r else 'FAILED'}; "
          f"leaky {lky} > learned {lrn} {'ok' if ok_l else 'FAILED'}")
    for new_v, old_v in (("learned", "text"), ("project", "learned")):
        cmp = [(_better(r[new_v], r[old_v]), r["case"]["project"]) for r in res]
        wins, losses = sum(1 for c, _ in cmp if c > 0), sum(1 for c, _ in cmp if c < 0)
        wp = len({p for c, p in cmp if c > 0})
        print(f"{new_v} vs {old_v}, case by case: {wins} better, {losses} worse, {n - wins - losses} same; "
              f"better ones from {wp} project(s) -> {verdict(wins, losses, wp)}")
    for m in ("described", "name-only", "absent", "unknown"):
        sub = [r for r in res if r["case"]["menu"] == m]
        if sub:
            print(f"  menu {m:<10} n={len(sub):<3} text top{a.top} "
                  f"{sum(1 for r in sub if r['text'] is not None and r['text'] <= a.top)}"
                  f"  learned top{a.top} {sum(1 for r in sub if r['learned'] is not None and r['learned'] <= a.top)}")
    if a.sweep:
        idx = Index(docs)
        quiet = quiet_messages(events)
        qbest = [(idx.rank(t) or [(0, 0.0)])[0][1] for t in quiet]
        ranked = [(r["case"]["skill"], idx.rank(r["case"]["text"])) for r in res]
        print(f"min-cover sweep (text variant; {len(quiet)} quiet messages = typed, no skill used before the next):")
        print(f"  {'cut':>5}  {'right':>5} {'wrong':>5} {'none':>5}   quiet shown")
        for cut, right, wrong, none, qs in sweep(ranked, qbest, a.top, [x / 20 for x in range(2, 13)]):
            print(f"  {cut:>5.2f}  {right:>5} {wrong:>5} {none:>5}   {qs:>5} ({qs / max(1, len(quiet)):.0%})")
    if a.cases:
        for r in res:
            c = r["case"]
            print(f"  {c['ts'][:10]} {c['skill']:<28} text={r['text']} learned={r['learned']} project={r['project']} "
                  f"menu={c['menu']:<9} {c['text'][:60]!r}")
    return 0 if ok_r and ok_l else 1


def main():
    ap = argparse.ArgumentParser(description="whetstone route — routing from session events")
    sub = ap.add_subparsers(dest="cmd")
    u = sub.add_parser("usage", help="skill x project table")
    u.add_argument("--events", required=True, help="event lines ('-' = stdin)")
    u.add_argument("--days", type=int, default=60)
    u.add_argument("--ignore-dir", action="append", help="another dir that is not a project")
    l = sub.add_parser("learn", help="messages that led to each skill -> the file find reads")
    l.add_argument("--events", required=True)
    l.add_argument("--out", help=f"default {default_learned()}")
    l.add_argument("--ignore-dir", action="append")
    f = sub.add_parser("find", help="which skills fit this task")
    f.add_argument("query", nargs="*")
    f.add_argument("--src", action="append", help="skill dir (repeatable; default: the dirs runtimes load)")
    f.add_argument("--learned", help=f"default {default_learned()}")
    f.add_argument("--no-learned", action="store_true")
    f.add_argument("--top", type=int, default=TOP)
    f.add_argument("--min-cover", type=float, default=MIN_COVER)
    f.add_argument("--json", action="store_true")
    w = sub.add_parser("elsewhere", help="skills whose use sits in another project")
    w.add_argument("--events", required=True)
    w.add_argument("--project", default=os.getcwd())
    w.add_argument("--days", type=int, default=60)
    w.add_argument("--ignore-dir", action="append")
    r = sub.add_parser("replay", help="score find against past sessions, in time order")
    r.add_argument("--events", required=True)
    r.add_argument("--src", action="append")
    r.add_argument("--top", type=int, default=TOP)
    r.add_argument("--min-cover", type=float, default=MIN_COVER)
    r.add_argument("--ignore-dir", action="append")
    r.add_argument("--cases", action="store_true", help="also list every case")
    r.add_argument("--sweep", action="store_true", help="also try min-cover cuts, with quiet messages")
    a = ap.parse_args()
    cmds = {"usage": cmd_usage, "learn": cmd_learn, "find": cmd_find, "replay": cmd_replay,
            "elsewhere": cmd_elsewhere}
    if a.cmd in cmds:
        return cmds[a.cmd](a)
    ap.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

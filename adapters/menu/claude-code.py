#!/usr/bin/env python3
"""Print the skill menu Claude Code last sent to the model, for `whetstone lint --listing`.

Why read it instead of computing it: the runtime decides which descriptions fit and
which skills are shown as a bare name, and that rule is not documented in full
("least-used first"). lint can estimate the size of a library; only the menu the
runtime actually sent says which skills lost their descriptions.

Where it is: Claude Code writes each session to ~/.claude/projects/<project>/<id>.jsonl.
The menu is a record {"type": "attachment", "attachment": {"type": "skill_listing",
"isInitial": true, "content": "- name: description\\n- name\\n..."}} at session start.
Records with isInitial false are deltas (skills added mid-session) and are skipped,
because they list only the new skills.

  claude-code.py [--projects DIR] [--scan N] [--session ID] [--events]
    --projects   default ~/.claude/projects
    --scan       how many of the newest session files to look through (default 40)
    --session    only that session (id or its first characters)
    --export-events  instead of the menu, print every session's events in the runtime-
                 neutral format bin/route.py reads (spec/routing.md); --days limits it to
                 sessions written in the last N days (default 60)
    --events     instead of the menu, list one session's skill events in time order
                 (default: $CLAUDE_CODE_SESSION_ID, which Claude Code sets for the
                 commands it runs, i.e. this session; without it, the session written
                 to most recently — with several sessions open that may be another one)

The menu goes to stdout; where it came from goes to stderr. Exit 2 if none is found.

--events answers "which skills, by name?" for the terse lines the UI prints. Two kinds
of event look alike there and are not the same:
  menu    the runtime (re)sent a skill's name + description — at session start, or
          mid-session when a SKILL.md was installed or edited ("N skill available").
          The body is NOT in context yet.
  loaded  the body entered the context: a Skill tool call, a Read of a SKILL.md, or
          the replay of already-loaded skills after the conversation was compacted.
--export-events turns Claude Code's own records into the neutral event lines of
spec/routing.md, so the learning and scoring in bin/ never read a Claude Code format:
  session  first record that has a cwd            {"kind":"session","cwd":...}
  user     a message the user typed (also typed mid-turn); not tool results, system
           reminders, command output or compaction summaries      {"kind":"user","text":...}
  file     Read / Edit / Write / MultiEdit / NotebookEdit / Grep / Glob with a path
                                                   {"kind":"file","path":...,"op":...}
  load     a Skill tool call ("via":"tool", "use":true), a skill the user started by
           typing /name ("via":"user", "use":true; only names on this session's menu,
           the rest are built-in commands), or a Read of a SKILL.md ("via":"read",
           "use":false: in Claude Code the Skill tool is how an entry gets used, and a
           Read of its SKILL.md is almost always someone editing it)
  menu     the skill listing: full at session start ("described" / "names_only"),
           or the names added mid-session ("added")
  find     the agent ran `whetstone find` through Bash     {"kind":"find","query":...}
           (the query it wrote, which is what find should be scored on once there are
           enough of them; until then replay has to use the user's own messages)
Every line also has v, runtime, session, ts, and src (<session file>:<line>) so a
surprising number can be traced back to the record it came from.
stdlib only.
"""
import argparse
import time
import glob
import json
import os
import re
import shlex
import sys
from datetime import datetime


def _names(att):
    names = att.get("names")
    if isinstance(names, list) and names:
        return [str(n) for n in names]
    out = []
    for ln in (att.get("content") or "").splitlines():
        if ln.startswith("- "):
            body = ln[2:]
            cut = body.find(": ")
            out.append(body[:cut] if cut > 0 else body.strip())
    return out


def _local(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return ts or "?"


def session_files(projects, session=None):
    files = glob.glob(os.path.join(projects, "*", "*.jsonl"))
    if session:
        files = [f for f in files if os.path.basename(f).startswith(session)]
    return files


def session_events(path):
    """Skill events of one session file, in file order: (ts, kind, detail, names)."""
    ev = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"skill_listing"' not in line and '"invoked_skills"' not in line \
                    and '"Skill"' not in line and "SKILL.md" not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            ts = rec.get("timestamp") or ""
            att = rec.get("attachment")
            if isinstance(att, dict) and att.get("type") == "skill_listing":
                names = _names(att)
                if att.get("isInitial"):
                    ev.append((ts, "menu", f"full menu, {len(names)} entries", []))
                else:
                    ev.append((ts, "menu", f"+{len(names)} (installed or edited)", names))
            elif isinstance(att, dict) and att.get("type") == "invoked_skills":
                names = [x.get("name") for x in att.get("skills") or [] if isinstance(x, dict) and x.get("name")]
                ev.append((ts, "loaded", "replayed after compaction", names))
            msg = rec.get("message")
            if rec.get("type") == "assistant" and isinstance(msg, dict) and isinstance(msg.get("content"), list):
                for b in msg["content"]:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") or {}
                    if b.get("name") == "Skill" and inp.get("skill"):
                        ev.append((ts, "loaded", "Skill tool", [str(inp["skill"])]))
                    elif b.get("name") == "Read" and str(inp.get("file_path", "")).endswith("/SKILL.md"):
                        ev.append((ts, "loaded", "read SKILL.md", [os.path.basename(os.path.dirname(inp["file_path"]))]))
    return ev


def print_events(projects, session):
    session = session or os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    files = session_files(projects, session)
    if not files:
        print(f"no session file{' for ' + session if session else ''} under {projects}", file=sys.stderr)
        return 2
    f = max(files, key=os.path.getmtime)
    ev = session_events(f)
    print(f"session {os.path.basename(f)[:-6]}: {len(ev)} skill event(s)", file=sys.stderr)
    for ts, kind, detail, names in ev:
        shown = ", ".join(names) if len(names) <= 8 else ", ".join(names[:8]) + f", … ({len(names)})"
        print(f"{_local(ts)}  {kind:<6}  {detail}" + (f": {shown}" if names else ""))
    loaded = sorted({n for _, k, _, ns in ev if k == "loaded" for n in ns})
    print(f"loaded in this session: {', '.join(loaded) if loaded else 'none'}")
    return 0


FILE_OPS = {"Read": ("file_path", "read"), "Edit": ("file_path", "edit"), "Write": ("file_path", "write"),
            "MultiEdit": ("file_path", "edit"), "NotebookEdit": ("notebook_path", "edit"),
            "Grep": ("path", "search"), "Glob": ("path", "search")}
NOT_TYPED = ("<", "Caveat:", "This session is being continued", "[Request interrupted")
COMMAND = re.compile(r"<command-name>/?([^<\s]+)</command-name>")
FIND_CALL = re.compile(r"(?:\bwhetstone|route\.py)\s+find\s+([^|;&\n]*)")
FIND_VALUED = ("--src", "--top", "--min-cover", "--learned")


def _find_query(command):
    """The query of a `whetstone find ...` inside a shell command, or None."""
    m = FIND_CALL.search(command or "")
    if not m:
        return None
    try:
        words = shlex.split(m.group(1))
    except ValueError:
        words = m.group(1).split()
    out, skip = [], False
    for w in words:
        if skip:
            skip = False
        elif w in FIND_VALUED:
            skip = True
        elif not w.startswith("--") and not w.startswith("2>"):
            out.append(w)
    return " ".join(out) or None


def _typed(text):
    """True for text the user typed, false for what the runtime injects in their name."""
    return isinstance(text, str) and text.strip() != "" and not text.lstrip().startswith(NOT_TYPED)


def _listing(att):
    described, names_only = [], []
    for ln in (att.get("content") or "").splitlines():
        if ln.startswith("- "):
            body = ln[2:]
            cut = body.find(": ")
            (described if cut > 0 else names_only).append(body[:cut] if cut > 0 else body.strip())
    return described, names_only


def export_events(path):
    """Neutral event dicts for one Claude Code session file, in file order."""
    sid = os.path.basename(path)[:-6]
    cwd, started, on_menu = None, False, set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for no, line in enumerate(fh, 1):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            base = {"v": 1, "runtime": "claude-code", "session": sid, "src": f"{path}:{no}"}
            ts = rec.get("timestamp") or ""
            if isinstance(rec.get("cwd"), str):
                cwd = rec["cwd"]
                if not started:
                    started = True
                    yield dict(base, ts=ts, kind="session", cwd=cwd)
            if not started:
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
            if rec.get("type") == "user" and not rec.get("isMeta") and not rec.get("isCompactSummary"):
                c = msg.get("content")
                texts = [c] if isinstance(c, str) else [b.get("text") for b in c or []
                                                        if isinstance(b, dict) and b.get("type") == "text"]
                for t in texts:
                    if _typed(t):
                        yield dict(base, ts=ts, kind="user", text=t, cwd=cwd)
                    m = COMMAND.search(t or "")
                    if m and m.group(1) in on_menu:
                        yield dict(base, ts=ts, kind="load", skill=m.group(1), via="user", use=True)
            att = rec.get("attachment")
            if isinstance(att, dict):
                if att.get("type") == "queued_command" and att.get("commandMode") == "prompt" and _typed(att.get("prompt")):
                    yield dict(base, ts=ts, kind="user", text=att["prompt"], cwd=cwd)
                elif att.get("type") == "skill_listing":
                    if att.get("isInitial"):
                        d, n = _listing(att)
                        on_menu.update(d + n)
                        yield dict(base, ts=ts, kind="menu", full=True, described=d, names_only=n)
                    else:
                        on_menu.update(_names(att))
                        yield dict(base, ts=ts, kind="menu", full=False, added=_names(att))
            if rec.get("type") == "assistant" and isinstance(msg.get("content"), list):
                for b in msg["content"]:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") or {}
                    name = b.get("name")
                    if name == "Skill" and inp.get("skill"):
                        yield dict(base, ts=ts, kind="load", skill=str(inp["skill"]), via="tool", use=True)
                    elif name == "Bash" and _find_query(inp.get("command")):
                        yield dict(base, ts=ts, kind="find", query=_find_query(inp["command"]))
                    elif name in FILE_OPS and isinstance(inp.get(FILE_OPS[name][0]), str):
                        p = inp[FILE_OPS[name][0]]
                        if not os.path.isabs(p) and cwd:
                            p = os.path.join(cwd, p)
                        if name == "Read" and p.endswith("/SKILL.md"):
                            yield dict(base, ts=ts, kind="load", skill=os.path.basename(os.path.dirname(p)),
                                       via="read", use=False)
                        yield dict(base, ts=ts, kind="file", path=os.path.normpath(p), op=FILE_OPS[name][1])


def latest_menu(projects, scan, session=None):
    files = session_files(projects, session)
    files.sort(key=os.path.getmtime, reverse=True)
    best = None
    for f in files[:scan]:
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"skill_listing"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                att = rec.get("attachment")
                if not isinstance(att, dict) or att.get("type") != "skill_listing" \
                        or not att.get("isInitial") or not isinstance(att.get("content"), str):
                    continue
                ts = rec.get("timestamp") or ""
                if best is None or ts > best[0]:
                    best = (ts, f, att)
    return best


def main():
    ap = argparse.ArgumentParser(description="print Claude Code's latest skill menu")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--scan", type=int, default=40)
    ap.add_argument("--session")
    ap.add_argument("--events", action="store_true", help="list one session's skill events instead")
    ap.add_argument("--export-events", action="store_true", help="print neutral session events instead")
    ap.add_argument("--days", type=int, default=60)
    a = ap.parse_args()
    if not os.path.isdir(a.projects):
        print(f"no such directory: {a.projects}", file=sys.stderr)
        return 2
    if a.events:
        return print_events(a.projects, a.session)
    if a.export_events:
        since = time.time() - a.days * 86400
        files = sorted(f for f in session_files(a.projects, a.session) if os.path.getmtime(f) >= since)
        n = 0
        for f in files:
            for ev in export_events(f):
                print(json.dumps(ev, ensure_ascii=False))
                n += 1
        print(f"exported {n} event(s) from {len(files)} session file(s) (last {a.days} days)", file=sys.stderr)
        return 0
    best = latest_menu(a.projects, a.scan, a.session)
    if best is None:
        print(f"no skill menu (skill_listing, isInitial) in the newest {a.scan} session file(s) "
              f"under {a.projects}", file=sys.stderr)
        return 2
    ts, f, att = best
    print(f"menu from {os.path.basename(f)} at {ts}: {att.get('skillCount', '?')} entries, "
          f"{len(att['content'])} chars", file=sys.stderr)
    sys.stdout.write(att["content"])
    if not att["content"].endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

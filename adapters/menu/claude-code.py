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
stdlib only.
"""
import argparse
import glob
import json
import os
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
    a = ap.parse_args()
    if not os.path.isdir(a.projects):
        print(f"no such directory: {a.projects}", file=sys.stderr)
        return 2
    if a.events:
        return print_events(a.projects, a.session)
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

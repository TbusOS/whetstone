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

  claude-code.py [--projects DIR] [--scan N] [--session ID]
    --projects   default ~/.claude/projects
    --scan       how many of the newest session files to look through (default 40)
    --session    only that session (id or its first characters)

The menu goes to stdout; where it came from goes to stderr. Exit 2 if none is found.
stdlib only.
"""
import argparse
import glob
import json
import os
import sys


def latest_menu(projects, scan, session=None):
    files = glob.glob(os.path.join(projects, "*", "*.jsonl"))
    if session:
        files = [f for f in files if os.path.basename(f).startswith(session)]
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
    a = ap.parse_args()
    if not os.path.isdir(a.projects):
        print(f"no such directory: {a.projects}", file=sys.stderr)
        return 2
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

#!/usr/bin/env python3
"""Turn "these skills belong to another project" into Claude Code's own menu lever.

The lever: skillOverrides in <dir>/.claude/settings.local.json. "name-only" keeps a
skill on the menu by name, still callable, but drops its description, so the menu budget
goes to the descriptions this project uses (spec/routing.md 4.1). It is not hiding: a
skill hidden from the model is one nobody remembers exists, which the user ruled out.

  claude-code.py --project DIR [--events FILE|-] [--days 60] [--write]

Where Claude Code reads that file (2.1.284, measured 2026-09-30 with 4 sessions and a
control): the git top-level when the session starts inside a git repo, subdirs included;
otherwise only the dir the session starts in, not its parents. So the file goes to the
git top-level of --project, or to --project itself when it is not in a git repo, and the
output says which sessions will see it.

Which skills: bin/route.py elsewhere (runtime-neutral). Without --events, this machine's
Claude Code sessions are read through adapters/menu/claude-code.py --export-events.
Without --write it only prints what it would set. With --write it merges:
- other keys in the file are kept as they are;
- a skill that already has an entry keeps it (the /skills screen writes this file too,
  and the user's own choice wins over a suggestion);
- the file is replaced in one step (temp file + rename), never half-written.
A file that is not a JSON object is left alone (exit 2).
stdlib only.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def _route():
    spec = importlib.util.spec_from_file_location(
        "route", os.environ.get("ROUTE_UNDER_TEST") or os.path.join(REPO, "bin", "route.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def events_lines(path, days):
    if path == "-":
        return sys.stdin.read().splitlines()
    if path:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    exporter = os.environ.get("ADAPTER_UNDER_TEST") or os.path.join(REPO, "adapters", "menu", "claude-code.py")
    out = subprocess.run([sys.executable, exporter, "--export-events", "--days", str(days)],
                         capture_output=True, text=True, check=False)
    return out.stdout.splitlines()


def settings_dir(d, home=None):
    """(dir whose .claude/settings.local.json Claude Code reads, in a git repo?)
    The search for .git stops at home, like every other upward search here: a stray
    .git above a project (or above a test dir) must not receive the file."""
    home = os.path.realpath(home or os.path.expanduser("~"))
    cur = os.path.abspath(d)
    while os.path.realpath(cur) != home:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur, True
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(d), False


def plan(settings, names):
    """(new settings dict, [(skill, what happens)]) — merge, never override the user."""
    new = dict(settings)
    cur = dict(settings.get("skillOverrides") or {})
    notes = []
    for n in names:
        if n in cur:
            notes.append((n, f"kept your setting: {cur[n]}"))
        else:
            cur[n] = "name-only"
            notes.append((n, "name-only"))
    if cur:
        new["skillOverrides"] = cur
    return new, notes


def main():
    ap = argparse.ArgumentParser(description="suggest / write skillOverrides for one project")
    ap.add_argument("--project", required=True)
    ap.add_argument("--events", help="neutral event lines ('-' = stdin); default: this machine's sessions")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    R = _route()
    places = R.Places()
    root = places.project_root(os.path.abspath(a.project))
    evs = []
    for line in events_lines(a.events, a.days):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("session") and ev.get("kind"):
            evs.append(ev)
    rows = R.elsewhere(evs, places, root, a.days)
    sdir, in_git = settings_dir(root)
    path = os.path.join(sdir, ".claude", "settings.local.json")
    settings = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                settings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"{path}: not readable as JSON ({e}); left alone", file=sys.stderr)
            return 2
        if not isinstance(settings, dict):
            print(f"{path}: not a JSON object; left alone", file=sys.stderr)
            return 2
    new, notes = plan(settings, [r[0] for r in rows])
    print(f"project {root}: {len(rows)} skill(s) used mostly elsewhere, none here (last {a.days} days)")
    why = {r[0]: r for r in rows}
    for n, what in notes:
        _, top, k, total = why[n]
        print(f"  {n:<32} {what:<28} {k} of {total} sessions in {top}")
    changed = new != settings
    if not changed:
        print("nothing to change")
        return 0
    print(f"read by sessions started in {sdir}" + (" or below (git repo)" if in_git
          else " itself only: not a git repo, sessions started in a subdir will not see it"))
    if not a.write:
        print(f"would merge into {path} (run again with --write):")
        print(json.dumps({"skillOverrides": new["skillOverrides"]}, ensure_ascii=False, indent=2))
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".whetstone-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(new, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    print(f"merged into {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

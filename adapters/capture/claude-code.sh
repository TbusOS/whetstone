#!/usr/bin/env bash
# Cangjie capture hook (OPTIONAL) — lightweight session journaler.
#
# The skill works WITHOUT this (run /distill manually). Wire it only if you want
# auto-capture. Heavy lifting is in /distill; this records pointers only
# (cwd, git HEAD, transcript path) so raw material is never lost.
#
#   Enable : add to settings.json hooks.Stop -> { "command": "bash <abs path>/capture.sh" }
#   Clean  : bash capture.sh --clean
#
# No /tmp, no secrets, no diff content — pointers only. Paths are SCRIPT_DIR-relative,
# so it works wherever the skill dir is installed.

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JOURNAL="$SKILL_DIR/journal/sessions.jsonl"

if [ "${1:-}" = "--clean" ]; then
  : > "$JOURNAL" 2>/dev/null && echo "cangjie: journal cleaned ($JOURNAL)" || echo "cangjie: nothing to clean"
  exit 0
fi

mkdir -p "$SKILL_DIR/journal"
PAYLOAD="$(cat 2>/dev/null || true)"   # Claude Code hook JSON on stdin (may be empty)

field() {
  local key="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$PAYLOAD" | jq -r --arg k "$key" '.[$k] // empty' 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$PAYLOAD" | python3 -c "import sys,json
try:
    print(json.load(sys.stdin).get('$key',''))
except Exception:
    pass" 2>/dev/null
  fi
}

CWD="$(field cwd)";              [ -n "$CWD" ] || CWD="$PWD"
TRANSCRIPT="$(field transcript_path)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

HEAD=""; CHANGED=""
if git -C "$CWD" rev-parse --git-dir >/dev/null 2>&1; then
  HEAD="$(git -C "$CWD" rev-parse --short HEAD 2>/dev/null)"
  CHANGED="$(git -C "$CWD" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
fi

printf '{"ts":"%s","cwd":"%s","head":"%s","changed":"%s","transcript":"%s"}\n' \
  "$TS" "$CWD" "$HEAD" "$CHANGED" "$TRANSCRIPT" >> "$JOURNAL"
exit 0

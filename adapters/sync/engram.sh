#!/usr/bin/env bash
# whetstone -> engram sync adapter (OPTIONAL sink).
#
#   adapters/sync/engram.sh <skill> [--src <skills-dir>] [--scope <scope>] [--dry-run] [--force]
#
# Pushes one skill package into engram as a `type: agent` memory, per the mapping in
# adapters/sync/engram.md. engram then serves recall / supersede on its side (its dedup is
# post-hoc heuristic only and memory confidence decay is unimplemented as of 2026-08 — see
# engram.md; pre-admission dedup/quality stays whetstone's job). Optional sink: whetstone
# works fine WITHOUT engram; this is additive.
#
# Contract verified against engram `memory add` (cli/engram/commands/memory.py):
#   engram memory add --type agent --name <n> --description <d> --scope <s>
#                     --source whetstone:<skill> --tags whetstone --body -
#   (SKILL.md piped on stdin via --body -). No secrets cross the boundary — SKILL.md only.
#
# --dry-run prints the exact command WITHOUT running it (works even if engram is absent).
# Without --dry-run, a missing `engram` on PATH is a clear, non-cryptic error (exit 3).

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC="${WHETSTONE_SKILLS_DIR:-$HOME/.claude/skills}"
SKILL=""; SCOPE="user"; DRY=0; FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --src)     SRC="$2"; shift 2;;
    --scope)   SCOPE="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    --force)   FORCE=1; shift;;
    -*)        echo "unknown arg: $1" >&2; exit 2;;
    *)         SKILL="$1"; shift;;
  esac
done

[ -n "$SKILL" ] || { echo "usage: engram.sh <skill> [--src D] [--scope S] [--dry-run] [--force]" >&2; exit 2; }
SDIR="$SRC/$SKILL"
SKILL_MD="$SDIR/SKILL.md"
[ -f "$SKILL_MD" ] || { echo "no SKILL.md at $SKILL_MD" >&2; exit 1; }

# Parse name + description from frontmatter (python3 if present, awk fallback).
read_meta() {
  local key="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$SKILL_MD" "$key" <<'PY'
import sys
path, key = sys.argv[1], sys.argv[2]
inside = False; val = ""
for line in open(path, encoding="utf-8"):
    s = line.rstrip("\n")
    if s.strip() == "---":
        if inside: break
        inside = True; continue
    if inside and s.lstrip().startswith(key + ":"):
        val = s.split(":", 1)[1].strip().strip('"').strip("'")
        break
print(val)
PY
  else
    awk -v k="$key" '
      /^---[[:space:]]*$/ { n++; next }
      n==1 && $0 ~ "^[[:space:]]*"k":" { sub("^[[:space:]]*"k":[[:space:]]*",""); gsub(/^["'\'']|["'\'']$/,""); print; exit }
    ' "$SKILL_MD"
  fi
}

NAME="$(read_meta name)";        [ -n "$NAME" ] || NAME="$SKILL"
DESC="$(read_meta description)"; [ -n "$DESC" ] || DESC="whetstone skill: $SKILL"
# engram caps description at ~150 chars (SPEC §4) — trim defensively, codepoint-safe
# (cut -c counts bytes in C locale and would split a multibyte char).
if command -v python3 >/dev/null 2>&1; then
  DESC="$(printf '%s' "$DESC" | python3 -c 'import sys; print(sys.stdin.read().strip()[:150])')"
else
  DESC="$(printf '%s' "$DESC" | cut -c1-150)"
fi
SOURCE="whetstone:$SKILL"

set -- engram memory add --type agent --scope "$SCOPE" \
       --name "$NAME" --description "$DESC" \
       --source "$SOURCE" --tags whetstone --body -
[ "$FORCE" -eq 1 ] && set -- "$@" --force

if [ "$DRY" -eq 1 ]; then
  echo "DRY-RUN — would run (SKILL.md piped on stdin, $(wc -c < "$SKILL_MD" | tr -d ' ') bytes):"
  printf '  '; printf '%q ' "$@"; echo
  echo "  < $SKILL_MD"
  exit 0
fi

if ! command -v engram >/dev/null 2>&1; then
  cat >&2 <<EOF
engram not found on PATH. Sync is optional — whetstone runs without it.
To enable: install engram (https://github.com/TbusOS/engram) so \`engram\` is on PATH,
then re-run. Use --dry-run to preview the exact command without engram installed.
EOF
  exit 3
fi

"$@" < "$SKILL_MD"

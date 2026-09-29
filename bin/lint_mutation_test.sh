#!/usr/bin/env bash
# Mutation battery for the menu-size half of `whetstone lint` and for
# adapters/menu/claude-code.py. Removes one piece of logic at a time and requires
# bin/lint_selftest.sh to go RED. A check whose removal changes nothing is not being
# tested, and a green suite over it reports a safety that is not there.
#
# Each mutation is a way these checks could go wrong without anyone noticing: a menu
# size that is off by a few chars per entry, a snapshot that never reports the
# skills shown as name only, a parser that reads the first line of a description.
# The mutated copy lives in a scratch dir; bin/lint.py itself is never edited.
#
#   bash bin/lint_mutation_test.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
S="$(mktemp -d "$REPO_DIR/.lint-mutation.XXXXXX")"
trap 'rm -rf "$S"' EXIT
caught=0; missed=0; skipped=0

# mut <label> <file: lint|adapter> <old> <new>
mut() {
  local label="$1" which="$2" src dst
  if [ "$which" = adapter ]; then src="$REPO_DIR/adapters/menu/claude-code.py"; else src="$SCRIPT_DIR/lint.py"; fi
  rm -rf "$S/m"; mkdir -p "$S/m"
  dst="$S/m/$(basename "$src")"
  if ! python3 - "$src" "$dst" "$3" "$4" <<'EOF'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src, encoding="utf-8").read()
if s.count(old) != 1:
    sys.exit(1)
open(dst, "w", encoding="utf-8").write(s.replace(old, new))
EOF
  then
    echo "  --  MUTATION DID NOT APPLY: $label"; skipped=$((skipped+1)); return
  fi
  local envs=()
  if [ "$which" = adapter ]; then envs=(ADAPTER_UNDER_TEST="$dst"); else envs=(LINT_UNDER_TEST="$dst"); fi
  if env "${envs[@]}" timeout 180 bash "$SCRIPT_DIR/lint_selftest.sh" >/dev/null 2>&1; then
    echo "  MISS  $label"; missed=$((missed+1))
  else
    echo "  ok    $label"; caught=$((caught+1))
  fi
}

echo "whetstone lint mutation battery"

mut "parser: a quoted value ends at its first line" lint \
  'while end is None and j < len(fm):' 'while False:'
mut "parser: continuation lines of a plain value are dropped" lint \
  'while v and j < len(fm) and fm[j].startswith((" ", "\t")) and fm[j].strip():' 'while False:'
mut "parser: double-quote escapes are left as written" lint \
  "out[k] = _unescape_dq(raw) if q == '\"' else raw.replace(\"''\", \"'\")" "out[k] = raw"
mut "parser: an unquoted ': ' is not reported" lint \
  'if ": " in val or val.endswith(":"):' 'if False:'
mut "length: the Agent Skills limit becomes >= instead of >" lint \
  'if len(d) > SPEC_DESC_MAX:' 'if len(d) >= SPEC_DESC_MAX:'
mut "length: the over-limit warning is gone" lint \
  'add("W", nm + tag, f"description is {len(d)} chars, over the Agent Skills limit' \
  'add("I", nm + tag, f"description is {len(d)} chars, over the Agent Skills limit'
mut "menu: an entry costs 2 chars less than it does" lint \
  'return len(name) + 5 + len(desc) if desc else len(name) + 3' \
  'return len(name) + 3 + len(desc) if desc else len(name) + 3'
mut "menu: the over-budget warning never fires" lint \
  '    if over > 0:
        if fair == 0:' '    if over > 10 ** 9:
        if fair == 0:'
mut "menu: the reserve is ignored" lint \
  'over = full + reserve - budget' 'over = full - budget'
mut "menu: the fair share ignores the separator" lint \
  'overhead = sum(len(s["name"]) + 5 for s in skills)' 'overhead = sum(len(s["name"]) + 3 for s in skills)'
mut "menu: the trim list is not sorted largest first" lint \
  'key=lambda s: (-len(s["menu_desc"]), s["name"]))' 'key=lambda s: s["name"])'
mut "menu: a share too small to use is not called out" lint \
  'if fair < MIN_DESC:' 'if False:'
mut "listing: foreign entries are not measured" lint \
  'reserve, rep["reserve_source"] = sum(menu_entry_len(k, v) for k, v in foreign.items()), "listing"' \
  'reserve, rep["reserve_source"] = 0, "listing"'
mut "listing: a wrapped description loses its second line" lint \
  'elif cur is not None and entries.get(cur) is not None:' 'elif False:'
mut "listing: name-only skills are not reported" lint \
  '            if shown is None:
                name_only.append(s["name"])' '            if False:
                name_only.append(s["name"])'
mut "listing: a different description is not reported" lint \
  'elif _norm(shown) != _norm(s["menu_desc"]):' 'elif False:'
mut "listing: stdin is not read" lint \
  'sys.stdin.read() if args.listing == "-" else' '"" if args.listing == "-" else'
mut "hidden: manual-only skills are counted in the menu" lint \
  'skills = [s for s in skills if not s.get("hidden")]' 'pass'
mut "hidden: the flag is never read" lint \
  '"hidden": str(fm.get("disable-model-invocation", "")).strip().lower() in ("true", "yes", "on"),' '"hidden": False,'
mut "hidden: a manual-only skill in the snapshot is not reported" lint \
  'if h["name"] in snap or h["dir"] in snap:' 'if False:'
mut "hidden: a manual-only skill in the snapshot is taken for a foreign entry" lint \
  'ours = {s["name"] for s in skills + hidden} | {s["dir"] for s in skills + hidden}' \
  'ours = {s["name"] for s in skills} | {s["dir"] for s in skills}'
mut "adapter: deltas are taken for the full menu" adapter \
  'or not att.get("isInitial") or' 'or'
mut "adapter: the first menu found wins, not the newest" adapter \
  'if best is None or ts > best[0]:' 'if best is None:'
mut "adapter: --session is ignored" adapter \
  'files = [f for f in files if os.path.basename(f).startswith(session)]' 'pass'

mut "events: a delta shows no names" adapter \
  'ev.append((ts, "menu", f"+{len(names)} (installed or edited)", names))' \
  'ev.append((ts, "menu", f"+{len(names)} (installed or edited)", []))'
mut "events: any file read under a skill counts as a load" adapter \
  'str(inp.get("file_path", "")).endswith("/SKILL.md")' '"/skills/" in str(inp.get("file_path", ""))'
mut "events: replays after compaction are dropped" adapter \
  'ev.append((ts, "loaded", "replayed after compaction", names))' 'pass'
mut "events: CLAUDE_CODE_SESSION_ID is ignored" adapter \
  'session = session or os.environ.get("CLAUDE_CODE_SESSION_ID") or None' 'pass'
mut "events: menu entries are counted as loaded" adapter \
  'loaded = sorted({n for _, k, _, ns in ev if k == "loaded" for n in ns})' \
  'loaded = sorted({n for _, k, _, ns in ev for n in ns})'

echo
echo "mutations caught: $caught   missed: $missed   did-not-apply: $skipped"
# a mutation that fails to apply is neither caught nor missed — it silently proves
# nothing, so it fails the run rather than passing quietly
bash "$SCRIPT_DIR/lint_selftest.sh" 2>&1 | tail -1
[ "$missed" -eq 0 ] && [ "$skipped" -eq 0 ]

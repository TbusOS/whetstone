#!/usr/bin/env bash
# Mutation battery for bin/route.py and the event export of adapters/menu/claude-code.py.
# Removes one piece of logic at a time and requires bin/route_selftest.sh to go RED.
# A rule whose removal changes nothing is not being tested.
#
# Each mutation is a way the usage table could go wrong without an error: a load put
# on the wrong project, one long session counted five times, a SKILL.md edit counted
# as a use, a tool result taken for something the user typed.
# The mutated copy lives in a scratch dir; the real files are never edited.
#
#   bash bin/route_mutation_test.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
S="$(mktemp -d "$REPO_DIR/.route-mutation.XXXXXX")"
trap 'rm -rf "$S"' EXIT
caught=0; missed=0; skipped=0

# mut <label> <file: route|adapter> <old> <new>
mut() {
  local label="$1" which="$2" src dst
  case "$which" in
    adapter) src="$REPO_DIR/adapters/menu/claude-code.py";;
    levers)  src="$REPO_DIR/adapters/levers/claude-code.py";;
    *)       src="$SCRIPT_DIR/route.py";;
  esac
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
  case "$which" in
    adapter) envs=(ADAPTER_UNDER_TEST="$dst");;
    levers)  envs=(LEVERS_UNDER_TEST="$dst");;
    *)       cp "$SCRIPT_DIR/lint.py" "$S/m/lint.py"; envs=(ROUTE_UNDER_TEST="$dst");;   # route imports its sibling lint
  esac
  if env "${envs[@]}" timeout 180 bash "$SCRIPT_DIR/route_selftest.sh" >/dev/null 2>&1; then
    echo "  MISS  $label"; missed=$((missed+1))
  else
    echo "  ok    $label"; caught=$((caught+1))
  fi
}

echo "whetstone route mutation battery"

mut "usage: only a tool call counts, not any adapter's use" route \
  'elif k == "load" and ev.get("use") is True and ev.get("skill"):' \
  'elif k == "load" and ev.get("via") == "tool" and ev.get("skill"):'
mut "usage: a load that is not a use counts" route \
  'elif k == "load" and ev.get("use") is True and ev.get("skill"):' \
  'elif k == "load" and ev.get("skill"):'
mut "usage: every load counts, not once per session" route \
  'key = (skill, where, s)' 'key = (skill, where, s, t)'
mut "usage: runtime dirs are not skipped" route \
  'if not path or self.is_ignored(path) or self.in_skill_library(path):' \
  'if not path or self.in_skill_library(path):'
mut "usage: skills' own dirs are not skipped" route \
  'if not path or self.is_ignored(path) or self.in_skill_library(path):' \
  'if not path or self.is_ignored(path):'
mut "usage: the project search climbs into home" route \
  'cur, found = d, None
            while os.path.realpath(cur) != self.home:' \
  'cur, found = d, None
            while True:'
mut "usage: a repo that is itself a skill counts as a skill dir" route \
  '                if any(os.path.exists(os.path.join(cur, m)) for m in PROJECT_MARKERS):
                    break
                if os.path.isfile(os.path.join(cur, "SKILL.md")):' \
  '                if os.path.isfile(os.path.join(cur, "SKILL.md")):'
mut "usage: no fallback to the start dir" route \
  'where = c if c and not places.is_ignored(c) else None' 'where = None'
mut "usage: a start dir inside a runtime dir is kept" route \
  'where = c if c and not places.is_ignored(c) else None' 'where = c if c else None'
mut "usage: the first file wins instead of the last" route \
  '            if w:
                x["last"] = w' \
  '            if w and not x["last"]:
                x["last"] = w'
mut "usage: --days is ignored" route \
  'if t is None or t < since:' 'if t is None:'
mut "usage: half-life of 7 days instead of 30" route \
  'HALF_LIFE_DAYS = 30.0' 'HALF_LIFE_DAYS = 7.0'
mut "usage: TMPDIR is not a runtime dir" route \
  '        if tmp:
            dirs.append(tmp)' \
  '        if False:
            dirs.append(tmp)'
mut "usage: --ignore-dir is dropped" route \
  'dirs += list(ignore)' 'dirs += []'

mut "usage: the menu state is misread" route \
  'else "name-only" if sk in x["names"]' 'else "described" if sk in x["names"]'

mut "find: CJK runs become single characters" route \
  'out.extend(p for p in (w[i:i + 2] for i in range(len(w) - 1)) if p not in STOP)' \
  'out.extend(ch for ch in w if ch not in STOP)'
mut "find: Chinese function words are kept" route \
  'for i in range(len(w) - 1)) if p not in STOP)' 'for i in range(len(w) - 1)))'
mut "find: the plural s is kept" route \
  'if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):' 'if False:'
mut "find: words no skill has do not count in the cover" route \
  'total = (known + (len(allq) - len(q)) * known / len(q)) if q else 1.0' 'total = known or 1.0'
mut "find: only-by-hand skills are offered" route \
  'if sk["router"] or sk["hidden"] or sk["name"] in seen_name' 'if sk["router"] or sk["name"] in seen_name'
mut "find: the routing skill offers itself" route \
  'if sk["router"] or sk["hidden"] or sk["name"] in seen_name' 'if sk["hidden"] or sk["name"] in seen_name'
mut "find: a name clash keeps both" route \
  'or sk["name"] in seen_name or real in seen_path' 'or real in seen_path'
mut "find: a missing skill dir crashes" route \
  '        if not os.path.isdir(d):
            continue' \
  '        if False:
            continue'
mut "find: the body is not searched" route \
  '"body": tokens(d["body"])' '"body": []'
mut "find: learned messages are ignored" route \
  '"learned": tokens(" ".join(learned.get(d["name"], ())))' '"learned": []'
mut "find: the threshold is ignored" route \
  'return [r for r in ranked[:top] if r[1] >= min_cover]' 'return ranked[:top]'
mut "find: a boost does nothing" route \
  'out.append((score * (boost or {}).get(d["name"], 1.0),' 'out.append((score,'
mut "find: project skill dirs are not looked for" route \
  'while cur != home and cur.startswith(home.rstrip("/") + "/"):' 'while False:'
mut "learn: every load is a pair, not the first per session" route \
  '        if key in seen:
            continue' \
  '        if False:
            continue'
mut "learn: the user's own /name pick is learned" route \
  'if ld["via"] == "user" or not ld["text"]:' 'if not ld["text"]:'
mut "learn: long messages are kept whole" route \
  'text=" ".join(ld["text"].split())[:LEARN_CHARS])' 'text=" ".join(ld["text"].split()))'
mut "replay: a session learns from itself" route \
  'if (parse_ts(p["start"]) or 0.0) < start:' 'if (parse_ts(p["start"]) or 0.0) <= start:'
mut "replay: a use does not end a quiet message" route \
  '        elif k == "load" and ev.get("use") is True:
            pending[s] = None' \
  '        elif k == "load" and ev.get("use") is True:
            pass'
mut "verdict: one project is enough" route \
  'and win_projects >= 2:' 'and win_projects >= 1:'
mut "verdict: 4-0 keeps" route \
  '(wins >= 5 and losses == 0)' '(wins >= 4 and losses == 0)'
mut "verdict: 6-1 keeps" route \
  '(wins >= 7 and losses <= 1)' '(wins >= 6 and losses <= 1)'

mut "elsewhere: a skill used here is listed" route \
  'if projs.get(project, 0) or total < min_sessions:' 'if total < min_sessions:'
mut "elsewhere: two sessions are enough" route \
  'ELSEWHERE_MIN, ELSEWHERE_SHARE = 3, 2 / 3' 'ELSEWHERE_MIN, ELSEWHERE_SHARE = 2, 2 / 3'
mut "elsewhere: use spread thin is listed" route \
  'if n / total >= share:' 'if True:'
mut "levers: the user's own entry is overwritten" levers \
  '        if n in cur:
            notes.append' \
  '        if False:
            notes.append'
mut "levers: the file goes where --project points, not the git top level" levers \
  'if os.path.exists(os.path.join(cur, ".git")):' 'if False:'
mut "levers: the search for .git climbs past home" levers \
  '    while os.path.realpath(cur) != home:
        if os.path.exists(os.path.join(cur, ".git")):' \
  '    while True:
        if os.path.exists(os.path.join(cur, ".git")):'
mut "levers: it writes without --write" levers \
  '    if not a.write:' '    if False:'
mut "levers: a JSON array is overwritten" levers \
  '        if not isinstance(settings, dict):' '        if False:'
mut "levers: other keys are dropped" levers \
  '    new = dict(settings)' '    new = {}'

mut "export: reading a SKILL.md is a use" adapter \
  'via="read", use=False)' 'via="read", use=True)'
mut "export: a built-in /command is a load" adapter \
  'if m and m.group(1) in on_menu:' 'if m:'
mut "export: injected text is taken as typed" adapter \
  'return isinstance(text, str) and text.strip() != "" and not text.lstrip().startswith(NOT_TYPED)' \
  'return isinstance(text, str) and text.strip() != ""'
mut "export: meta records are taken as typed" adapter \
  'if rec.get("type") == "user" and not rec.get("isMeta") and not rec.get("isCompactSummary"):' \
  'if rec.get("type") == "user" and not rec.get("isCompactSummary"):'
mut "export: compaction summaries are taken as typed" adapter \
  'if rec.get("type") == "user" and not rec.get("isMeta") and not rec.get("isCompactSummary"):' \
  'if rec.get("type") == "user" and not rec.get("isMeta"):'
mut "export: queued prompts are dropped" adapter \
  'att.get("commandMode") == "prompt"' 'att.get("commandMode") == "never"'
mut "export: relative paths are left relative" adapter \
  'if not os.path.isabs(p) and cwd:' 'if False:'
mut "export: src line numbers start at 0" adapter \
  'enumerate(fh, 1)' 'enumerate(fh)'
mut "export: names-only entries are listed as described" adapter \
  '(described if cut > 0 else names_only).append' 'described.append'
mut "export: find calls are not recorded" adapter \
  'elif name == "Bash" and _find_query(inp.get("command")):' 'elif False:'
mut "export: find options are taken as the query" adapter \
  '        elif w in FIND_VALUED:
            skip = True' \
  '        elif False:
            skip = True'
mut "export: the session line comes from any record" adapter \
  '            if not started:
                continue' \
  '            if False:
                continue'

echo
echo "mutations caught: $caught   missed: $missed   did-not-apply: $skipped"
bash "$SCRIPT_DIR/route_selftest.sh" 2>&1 | tail -1
[ "$missed" -eq 0 ] && [ "$skipped" -eq 0 ]

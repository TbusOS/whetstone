#!/usr/bin/env bash
# Selftest for `whetstone decision`. Runs against an isolated log under
# .decision-selftest/ — never the real journal.
#
# The one behaviour worth testing hardest is the counting rule: `stats` must count
# DISTINCT SOURCES, not lines. If it counted lines, one session could push any tag
# over the threshold by itself, and the threshold would mean nothing — the same back
# door §7 closed for 复现记录 by keying on platform/project.
#
#   bash bin/decision_selftest.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
unset CDPATH
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGE="$REPO_DIR/.decision-selftest"
D="$SCRIPT_DIR/decision.py"
LOG="$STAGE/review-decisions.jsonl"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT
rm -rf "$STAGE"; mkdir -p "$STAGE"

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok  - $1"; }
bad() { fail=$((fail+1)); echo "  FAIL- $1"; }

dec() { python3 "$D" --file "$LOG" "$@"; }
addok() { dec add "$@" >/dev/null 2>&1; }

echo "whetstone decision selftest"
echo
echo "[add] required fields and their refusals"

if addok --subject "s" --verdict accept --reason "r"; then ok "a minimal record is accepted"
else bad "a minimal record was refused"; fi
if [ "$(wc -l < "$LOG")" -eq 1 ]; then ok "exactly one line written"; else bad "wrote $(wc -l < "$LOG") lines"; fi
if python3 -c "import json,sys;json.loads(open(sys.argv[1],encoding='utf-8').readline())" "$LOG" 2>/dev/null
  then ok "the line is valid JSON"; else bad "the line is not valid JSON"; fi

if addok --subject "s" --verdict maybe --reason "r"; then bad "an unknown verdict was accepted"
else ok "an unknown verdict is refused"; fi
if addok --subject "s" --verdict accept --reason "r" --kind wharever; then bad "an unknown kind was accepted"
else ok "an unknown kind is refused"; fi
if addok --subject "s" --verdict accept --reason "r" --date 最近; then bad "a relative date was accepted"
else ok "a relative date is refused (§7: only an absolute date can be compared later)"; fi
if addok --subject "s" --verdict accept --reason "   "; then bad "a blank reason was accepted"
else ok "a blank reason is refused"; fi
if [ "$(wc -l < "$LOG")" -eq 1 ]; then ok "no refused call left a partial line behind"
else bad "a refused call still wrote: $(wc -l < "$LOG") lines"; fi

echo
echo "[add] optional fields"
rm -f "$LOG"
addok --subject "s" --verdict amend --reason "r" --layer L1 --final-layer L2 --tag layer-wrong --source c0ffee
if python3 - "$LOG" <<'PY'
import json,sys
r=json.loads(open(sys.argv[1],encoding="utf-8").readline())
assert r["layer"]=="L1" and r["final_layer"]=="L2" and r["tag"]=="layer-wrong"
assert "skill" not in r and "conf" not in r, "empty optionals must be omitted, not stored blank"
PY
then ok "given optionals stored, empty ones omitted"; else bad "optional-field handling is wrong"; fi

rm -f "$LOG"
out="$(dec add --subject "s" --verdict reject --reason "r" --tag brand-new-bucket 2>&1)"
case "$out" in *"not in the vocabulary yet"*) ok "an unknown tag is reported, not accepted silently";;
                                           *) bad "an unknown tag was accepted silently";; esac
if grep -q '"tag": *"brand-new-bucket"' "$LOG"; then ok "and it is written through as typed, not rejected or rewritten"
else bad "an unknown tag was not stored as typed"; fi

echo
echo "[stats] counts distinct sources, not lines"
rm -f "$LOG"
for i in 1 2 3 4 5; do
  addok --subject "entry $i" --verdict reject --reason "same session, same complaint" \
        --tag not-general --source SESSION-A
done
if dec stats | grep -qE '^ +1 +not-general$'; then ok "five lines from one source count as 1"
else bad "one source counted more than once: $(dec stats | grep not-general)"; fi
if dec stats | grep -q "reached the threshold"; then bad "one source crossed the threshold on its own"
else ok "one source cannot reach the threshold alone"; fi

addok --subject "e" --verdict reject --reason "r" --tag not-general --source SESSION-B
if dec stats | grep -q "reached the threshold"; then bad "two sources already flagged"
else ok "two distinct sources is still below the threshold"; fi
addok --subject "e" --verdict reject --reason "r" --tag not-general --source SESSION-C
if dec stats | grep -q "reached the threshold"; then ok "three distinct sources reaches the threshold"
else bad "three distinct sources did not reach the threshold"; fi
if dec stats | grep -q "prompt to look, not a finding"; then ok "the flag is stated as a prompt, not a verdict"
else bad "the flag reads like a finding"; fi

rm -f "$LOG"
for i in 1 2 3 4 5; do
  addok --subject "entry $i" --verdict reject --reason "no source given" --tag not-general
done
if dec stats | grep -qE '^ +1 +not-general$'; then ok "five sourceless records count as 1, not 5"
else bad "sourceless records inflate the count: $(dec stats | grep not-general)"; fi
if dec stats | grep -q "count as one between them"; then ok "the sourceless collapse is stated, not hidden"
else bad "sourceless records are collapsed without saying so"; fi

echo
echo "[robustness] a corrupt line is reported, never silently dropped"
printf 'this is not json\n' >> "$LOG"
if dec stats 2>&1 | grep -q "not valid JSON"; then ok "corrupt line reported"; else bad "corrupt line swallowed"; fi
if dec stats >/dev/null 2>&1; then ok "a corrupt line does not crash stats"; else bad "stats crashed"; fi
printf '["a","list","not","an","object"]\n' >> "$LOG"
if dec stats 2>&1 | grep -q "not valid JSON"; then ok "a JSON non-object is rejected too"
else bad "a JSON array was treated as a record"; fi

echo
echo "[list] shows what the reviewer changed"
rm -f "$LOG"
addok --subject "某条方法" --verdict amend --reason "单平台,先放 L3" --layer L2 --final-layer L3
if dec list | grep -q "L2→L3"; then ok "a layer move is visible in list"; else bad "layer move not shown"; fi

echo
echo "[vocabulary] a new tag is met with what already exists"
rm -f "$LOG"
out="$(dec add --subject s --verdict reject --reason r --tag priority-mistake --source S1 2>&1)"
case "$out" in *"not in the vocabulary yet"*) ok "a brand-new tag triggers the listing";;
                                           *) bad "a brand-new tag showed no vocabulary";; esac
case "$out" in *"layer-wrong"*) ok "the listing names existing tags";;
                             *) bad "the listing is empty";; esac
out="$(dec add --subject s --verdict reject --reason r --tag priority-mistake --source S2 2>&1)"
case "$out" in *"not in the vocabulary"*) bad "the listing repeats for a tag already in use";;
                                       *) ok "a tag already in use does not re-trigger it";; esac
out="$(dec add --subject s --verdict reject --reason r --tag layer-wrong --source S2 2>&1)"
case "$out" in *"not in the vocabulary"*) bad "a documented tag triggered the listing";;
                                       *) ok "a documented tag does not trigger it";; esac
# ordering is the whole point of showing it: the spelling already in use must be
# reachable at a glance, or the writer invents a third one
out="$(dec add --subject s --verdict reject --reason r --tag priority-wrongly --source S3 2>&1)"
first="$(printf '%s\n' "$out" | grep -A 1 'not in the vocabulary' | tail -1)"
case "$first" in *priority-mistake*) ok "the most similar existing tag is listed first";;
                                  *) bad "most-similar tag was not first: $first";; esac

echo
echo "[alias] folds counts without touching a stored line"
rm -f "$LOG"
for i in 1 2; do addok --subject "e$i" --verdict reject --reason r --tag priority-mistake --source "S$i"; done
addok --subject e3 --verdict reject --reason r --tag priority-wrong --source S3
before="$(cat "$LOG")"
if dec stats | grep -q "reached the threshold"; then bad "split spellings already crossed the threshold"
else ok "two spellings of one meaning stay below the threshold (the failure being fixed)"; fi
dec alias --from priority-mistake --to priority-wrong --reason "同一件事" >/dev/null 2>&1
if [ "$(grep -v '"kind": *"alias"' "$LOG")" = "$before" ]; then ok "every pre-existing line is byte-identical after the alias"
else bad "the alias rewrote stored lines"; fi
if dec stats | grep -qE '^ +3 +priority-wrong'; then ok "the fold merges the counts"
else bad "the fold did not merge: $(dec stats | grep priority)"; fi
if dec stats | grep -q "reached the threshold"; then ok "the merged tag now crosses the threshold"
else bad "the merged tag did not cross the threshold"; fi
if dec stats | grep -q "folded by alias"; then ok "the fold is printed, never applied silently"
else bad "counts were merged without saying so"; fi
if dec stats | grep -q "alias rule(s)"; then ok "alias rules are counted apart from decisions"
else bad "alias rules were counted as decisions"; fi
if dec stats | grep -qE '^by verdict: reject 3$'; then ok "an alias record carries no verdict into the tally"
else bad "verdict tally polluted: $(dec stats | grep '^by verdict')"; fi
if dec list -n 10 | grep -q "\[alias\]"; then ok "list renders an alias record"; else bad "list hides aliases"; fi

echo
echo "[alias] chains, loops and cancelling"
dec alias --from 排序判断错 --to priority-mistake --reason "中文写法" >/dev/null 2>&1
if dec aliases | grep -q "resolves to priority-wrong"; then ok "a chain a→b→c resolves to c"
else bad "chain not resolved: $(dec aliases | tail -1)"; fi
if dec alias --from priority-wrong --to priority-mistake --reason r >/dev/null 2>&1
  then bad "a loop-closing alias was accepted"; else ok "a loop-closing alias is refused at write time"; fi
if dec alias --from a --to b >/dev/null 2>&1; then bad "an alias without a reason was accepted"
else ok "an alias without a reason is refused"; fi
if dec alias --from priority-mistake --to priority-mistake --reason "分开" >/dev/null 2>&1
  then ok "a self-alias cancels an existing fold"; else bad "cancelling failed"; fi
if dec aliases | grep -q "^  priority-mistake  ->"; then bad "the cancelled fold is still in effect"
else ok "after cancelling, the tag stands on its own"; fi
if dec alias --from never-aliased --to never-aliased --reason r >/dev/null 2>&1
  then bad "cancelling a non-existent alias was accepted"; else ok "cancelling nothing is refused"; fi

echo
echo "[alias] a loop already in the file must not hang or fold"
rm -f "$LOG"
addok --subject e --verdict reject --reason r --tag aa --source S1
printf '%s\n' '{"date":"2026-09-04","kind":"alias","from":"aa","to":"bb","reason":"x"}' >> "$LOG"
printf '%s\n' '{"date":"2026-09-04","kind":"alias","from":"bb","to":"aa","reason":"x"}' >> "$LOG"
if timeout 10 python3 "$D" --file "$LOG" stats >/dev/null 2>&1; then ok "a hand-written loop does not hang stats"
else bad "stats hung or crashed on an alias loop"; fi
if dec stats | grep -q "alias loop"; then ok "the loop is reported"; else bad "the loop is silent"; fi
if dec stats | grep -qE '^ +1 +aa'; then ok "a looping tag is left unfolded, counts split (safe direction)"
else bad "a looping tag was folded anyway"; fi

echo
echo "[aliases] says so when there are none"
rm -f "$LOG"
if dec aliases | grep -q "no aliases in effect"; then ok "an empty alias set explains itself"
else bad "empty alias set output is unhelpful"; fi

echo
echo "[empty] an empty log says so instead of pretending"
rm -f "$LOG"
if dec stats | grep -q "expected state"; then ok "empty log explains itself"; else bad "empty log output is unhelpful"; fi

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1

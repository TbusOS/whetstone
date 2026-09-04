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

out="$(dec add --subject "s" --verdict reject --reason "r" --tag brand-new-bucket 2>&1)"
case "$out" in *"new tag"*) ok "an unknown tag is written through AND reported";;
                         *) bad "an unknown tag was accepted silently";; esac

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
echo "[empty] an empty log says so instead of pretending"
rm -f "$LOG"
if dec stats | grep -q "expected state"; then ok "empty log explains itself"; else bad "empty log output is unhelpful"; fi

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1

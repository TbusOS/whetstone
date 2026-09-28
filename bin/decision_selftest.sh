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

# ---------------------------------------------------------------------------------
# use-time conflicts (spec/use-time-conflicts.md). The failures worth fencing off are
# the silent ones: a group relaxed on a point estimate, a miss that resets nothing, a
# relaxation granted on guesses or with no exam behind it — and above all the AI
# agreeing with the human in hindsight, which is why a call is recorded in two steps.
# ---------------------------------------------------------------------------------
# step 1 with every AI field filled in; extra args override / extend
rep() { dec report --subject s --reason why --entry sk/e --ai-type stale --ai-evidence seen \
            --ai-action update --ai-certainty high "$@"; }
repok() { rep "$@" >/dev/null 2>&1; }
lastid() { python3 - "$LOG" <<'PY'
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
print([r for r in recs if r.get("kind") == "conflict-report"][-1]["conflict_id"])
PY
}
res() { dec resolve --reason r "$@"; }
resok() { res "$@" >/dev/null 2>&1; }
nlines() { wc -l < "$LOG" | tr -d ' '; }
# bulk fixture: report + answer pairs written straight to the log with valid
# fingerprints — stats is what is under test, and 45 x 2 CLI calls per case would
# make the mutation battery crawl.
# gen <n> <ai_type> <ai_evidence> <verdict|pending> [final_type] [prefix] [certainty] [source]
gen() {
  PYTHONDONTWRITEBYTECODE=1 python3 - "$SCRIPT_DIR" "$LOG" "$@" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import decision as d
a = sys.argv[2:] + [""] * 8
log, n, t, ev, v = a[0], int(a[1]), a[2], a[3], a[4]
final, pre, cert, src = a[5], a[6] or "G", a[7] or "high", a[8]
start = 0
if os.path.isfile(log):
    start = sum(1 for l in open(log, encoding="utf-8") if '"conflict-report"' in l)
with open(log, "a", encoding="utf-8") as f:
    for i in range(n):
        cid = f"C-20260928-{start + i + 1:03d}"
        r = {"date": "2026-09-28", "kind": "conflict-report", "conflict_id": cid,
             "reported_at": "2026-09-28T10:00:00", "entry": f"sk/{pre}{i}",
             "ai_type": t, "ai_evidence": ev, "ai_action": "update", "ai_certainty": cert,
             "subject": "s", "ai_reason": "r", "blocking": False, "safety": False,
             "source": src or f"{pre}{i}"}
        r["fingerprint"] = d.fingerprint(r)
        f.write(json.dumps(r) + "\n")
        if v != "pending":
            ans = {"date": "2026-09-28", "kind": "conflict-resolve", "conflict_id": cid,
                   "resolved_at": "2026-09-28T10:05:00", "verdict": v, "reason": "r"}
            if final:
                ans["final_type"] = final
            f.write(json.dumps(ans) + "\n")
PY
}
examrec() { dec exam --result "$1" --reason r >/dev/null 2>&1; }
row() { dec stats | grep -E "^  $1 × $2 +[0-9]"; }   # one group's line in stats

echo
echo "[conflict] step 1: the AI's call goes on file first, and is never rewritten"
rm -f "$LOG"
out="$(rep 2>&1)"
case "$out" in *"reported C-"*"fingerprint "*) ok "report prints the id and a fingerprint for the card";;
                                            *) bad "report did not print id + fingerprint: $out";; esac
if PYTHONDONTWRITEBYTECODE=1 python3 - "$SCRIPT_DIR" "$LOG" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import decision as d
r = json.loads(open(sys.argv[2], encoding="utf-8").readline())
assert r["kind"] == "conflict-report" and r["reported_at"] and "verdict" not in r, r
assert r["fingerprint"] == d.fingerprint(r), "stored fingerprint does not match the call"
PY
then ok "the report carries the call, a timestamp and a matching fingerprint, and no verdict"
else bad "the report line is malformed"; fi
repok --entry sk/f
if [ "$(lastid)" = "C-$(date +%Y%m%d)-02" ]; then ok "ids are numbered per day without being typed"
else bad "second id is $(lastid)"; fi
n0="$(nlines)"
if repok --conflict-id "$(lastid)"; then bad "a second report under a used id was accepted"
else ok "a used id is refused: a call once written is not rewritten"; fi
if repok --entry ""; then bad "a report without --entry was accepted"; else ok "a report without --entry is refused"; fi
if repok --ai-type obsolete; then bad "an unknown --ai-type was accepted"; else ok "an unknown --ai-type is refused"; fi
if dec report --subject s --reason why --entry sk/e --ai-type stale --ai-action update \
     --ai-certainty high >/dev/null 2>&1
  then bad "a report without --ai-evidence was accepted"
  else ok "a report missing part of the AI's call is refused (nothing to score)"; fi
if repok --reason " "; then bad "a report without a reason was accepted"
else ok "a report without the AI's reason is refused"; fi
if repok --conflict-id C-2026-1; then bad "a malformed conflict id was accepted"
else ok "a malformed conflict id is refused"; fi
if [ "$(nlines)" = "$n0" ]; then ok "refused reports left no partial line"
else bad "a refused report wrote something: $(nlines) lines, expected $n0"; fi

echo
echo "[conflict] step 2: the answer needs a report before it"
rm -f "$LOG"; repok; id="$(lastid)"; n0="$(nlines)"
if resok --conflict-id C-20990101-01 --verdict accept; then bad "an answer with no report was accepted"
else ok "an answer with no report on file is refused"; fi
if resok --conflict-id "$id" --verdict accept --final-type scope; then bad "accept with a changed type was accepted"
else ok "accept with a changed type is refused (that is amend)"; fi
if resok --conflict-id "$id" --verdict accept --final-type none; then bad "accept with final-type none was accepted"
else ok "final-type none with a non-reject verdict is refused"; fi
if resok --conflict-id "$id" --verdict accept --reason " "; then bad "an answer without a reason was accepted"
else ok "an answer without a reason is refused"; fi
if [ "$(nlines)" = "$n0" ]; then ok "refused answers left no partial line"
else bad "a refused answer wrote something"; fi
if resok --conflict-id "$id" --verdict amend --final-type scope; then ok "amend with a changed type is accepted"
else bad "amend with a changed type was refused"; fi
out="$(res --conflict-id "$id" --verdict accept --final-type stale 2>&1)"
case "$out" in *"not stored"*) ok "a final-type equal to the AI's is reported as not stored";;
                            *) bad "no note for final-type == ai-type";; esac
case "$out" in *"overrides the earlier answer"*) ok "a second answer says it overrides the first";;
                                              *) bad "a second answer overrode silently";; esac
if tail -1 "$LOG" | grep -q '"final_type"'; then bad "a same-type final-type was stored"
else ok "and the same-type final-type is not stored"; fi
rm -f "$LOG"; repok; id="$(lastid)"
if resok --conflict-id "$id" --verdict reject --final-type none; then ok "reject with final-type none is accepted"
else bad "reject with final-type none was refused"; fi

echo
echo "[conflict] no one-line path, and a miss carries no AI call"
rm -f "$LOG"
out="$(dec add --kind conflict --subject s --verdict accept --reason r 2>&1)"
case "$out" in *"decision report"*) ok "add --kind conflict is refused and points to report / resolve";;
                                 *) bad "the one-line conflict path is open: $out";; esac
if [ ! -s "$LOG" ]; then ok "and nothing was written"; else bad "the refused one-line conflict wrote a line"; fi
if dec miss --entry sk/m --final-type wrong --verdict accept --subject s --reason r --ai-type stale >/dev/null 2>&1
  then bad "a miss carrying an AI call was accepted"; else ok "a miss cannot carry an AI call"; fi
if dec miss --entry sk/m --final-type none --verdict reject --subject s --reason r >/dev/null 2>&1
  then bad "a miss typed 'none' was accepted"; else ok "a miss typed 'none' is refused"; fi
if dec miss --entry sk/m --final-type wrong --verdict accept --subject s --reason r >/dev/null 2>&1
  then ok "a well-formed miss is accepted"; else bad "a well-formed miss was refused"; fi

echo
echo "[conflict stats] exact lower bound, never the point estimate"
if PYTHONDONTWRITEBYTECODE=1 python3 - "$SCRIPT_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import decision as d
for (k, n), v in {(10, 10): 0.794, (18, 20): 0.755, (22, 22): 0.901, (45, 45): 0.950}.items():
    got = d.lower_bound(k, n)
    assert abs(got - v) < 0.001, (k, n, got)
assert d.lower_bound(0, 5) == 0.0 and d.lower_bound(3, 0) == 0.0
PY
then ok "lower_bound matches the four reference values in the spec"
else bad "lower_bound drifted from the reference values"; fi

rm -f "$LOG"; gen 22 stale seen accept
if row stale seen | grep -q "gate above"; then ok "no exam sitting: even 22/22 stays on full confirmation"
else bad "a group was relaxed with no exam behind it: $(row stale seen)"; fi
examrec pass
if row stale seen | grep -q "summary"; then ok "after a passed exam, 22/22 seen reaches summary"
else bad "22/22 seen with a passed exam did not reach summary: $(row stale seen)"; fi
examrec fail
if row stale seen | grep -q "gate above"; then ok "a later failed exam sends every group back to full"
else bad "a failed exam did not revoke the tier: $(row stale seen)"; fi

rm -f "$LOG"; examrec pass; gen 21 stale seen accept
if row stale seen | grep -qE ' full$'; then ok "21/21 stays full (bound 0.896 < 0.90)"
else bad "21/21 was relaxed: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 18 stale seen accept; gen 2 stale seen amend scope B
if row stale seen | grep -qE ' full$'; then ok "18/20 stays full — the point estimate 0.90 is not enough"
else bad "18/20 was relaxed on its point estimate: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 45 stale seen accept
if row stale seen | grep -q "batch"; then ok "45/45 reaches batch"; else bad "45/45 did not reach batch: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 44 stale seen accept
if row stale seen | grep -q "summary"; then ok "44/44 is summary, not yet batch"
else bad "44/44 tier wrong: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 45 stale inferred accept
if row stale inferred | grep -q "nothing seen"; then ok "an inferred group never relaxes, even at 45/45"
else bad "an inferred group was relaxed: $(row stale inferred)"; fi

echo
echo "[conflict stats] the guess-share gate"
rm -f "$LOG"; examrec pass; gen 22 stale seen accept; gen 10 wrong inferred accept "" I
if dec stats | grep -q "rest on inference"; then ok "31% inferred raises the warning"
else bad "31% inferred raised no warning"; fi
if row stale seen | grep -q "gate above"; then ok "and no group is relaxed while it holds"
else bad "a group was relaxed above the guess share: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 22 stale seen accept; gen 9 wrong inferred accept "" I
if dec stats | grep -q "rest on inference"; then bad "29% inferred raised the warning"
else ok "29% inferred stays below the gate"; fi
if row stale seen | grep -q "summary"; then ok "and the seen group relaxes normally"
else bad "the seen group did not relax below the gate: $(row stale seen)"; fi

echo
echo "[conflict stats] a miss resets its type; false alarms, defers and pending stay out"
rm -f "$LOG"; examrec pass; gen 22 stale seen accept
dec miss --entry sk/m --final-type stale --verdict accept --subject s --reason r --source M1 >/dev/null 2>&1
if row stale seen | grep -q "after the last miss" && row stale seen | grep -qE ' full '; then
  ok "a miss of type stale sends stale × seen back to full"
else bad "a miss did not reset its group: $(row stale seen)"; fi
gen 22 stale seen accept "" A
if row stale seen | grep -q "summary"; then ok "22 agreeing reports after the miss earn summary back"
else bad "reports after the miss were not counted: $(row stale seen)"; fi
dec miss --entry sk/m2 --final-type scope --verdict accept --subject s --reason r --source M2 >/dev/null 2>&1
if row stale seen | grep -q "summary"; then ok "a miss of another type leaves stale × seen alone"
else bad "a scope miss reset the stale group: $(row stale seen)"; fi
if dec stats | grep -q "found by you, not reported"; then ok "misses are summarised as a share"
else bad "misses are not summarised"; fi

rm -f "$LOG"; examrec pass; gen 22 stale seen accept; gen 1 stale seen reject none F
if row stale seen | grep -q "summary"; then ok "a false alarm is not counted as a wrong type"
else bad "a false alarm dragged the group down: $(row stale seen)"; fi
if row stale seen | grep -qE ' 1  summary'; then ok "and it shows in the false-alarm column"
else bad "false alarm not shown: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 21 stale seen accept; gen 1 stale seen defer "" D
if row stale seen | grep -qE ' full$'; then ok "a deferred answer is not counted as judged"
else bad "a deferred answer was counted: $(row stale seen)"; fi
rm -f "$LOG"; examrec pass; gen 22 stale seen accept; gen 1 stale seen pending "" P
if row stale seen | grep -q "summary"; then ok "a report awaiting its answer is not scored"
else bad "a pending report was scored: $(row stale seen)"; fi
if dec stats | grep -q "awaiting your answer (not scored yet): C-"; then ok "and it is listed as awaiting an answer"
else bad "pending reports are not listed"; fi

echo
echo "[conflict stats] hindsight: re-reports and edited lines are not scored"
rm -f "$LOG"
repok --entry sk/h --source SAME --ai-type stale
repok --entry sk/h --source SAME --ai-type scope
resok --conflict-id "$(lastid)" --verdict accept
if dec stats | grep -q "reported more than once within one source"; then ok "a re-report of one entry in one source is flagged"
else bad "a re-report went unflagged"; fi
if row stale seen | grep -qE ' +1 +0 '; then ok "the FIRST call is scored, against the latest answer (stale vs scope: wrong)"
else bad "the re-report's later call was scored: $(dec stats | grep ' × seen')"; fi
if dec stats | grep -qE '^  scope × seen'; then bad "the second call got a group of its own"
else ok "the second call is not scored at all"; fi

rm -f "$LOG"; repok --entry sk/t --source T1; id="$(lastid)"; resok --conflict-id "$id" --verdict accept
python3 - "$LOG" <<'PY'
import json, sys
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().splitlines()
r = json.loads(lines[0]); r["ai_type"] = "scope"          # rewrite the call in place
lines[0] = json.dumps(r)
open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
if dec stats | grep -q "no longer matches its fingerprint"; then ok "a report edited after it was written is caught"
else bad "an edited report went unnoticed"; fi
if dec stats | grep -qE '^  scope × seen'; then bad "the edited report was scored"
else ok "and it is not scored"; fi

rm -f "$LOG"
printf '%s\n' '{"date":"2026-09-28","kind":"conflict-resolve","conflict_id":"C-20260928-01","verdict":"accept","reason":"r"}' >> "$LOG"
repok --conflict-id C-20260928-01
if dec stats | grep -q "has no report before it"; then ok "an answer written before its report is ignored and flagged"
else bad "an answer before its report was accepted"; fi
if dec stats | grep -q "awaiting your answer"; then ok "so that report still awaits its answer"
else bad "an out-of-order answer resolved the report"; fi

rm -f "$LOG"
for i in 1 2 3 4 5; do repok --source SAME; done
if dec stats | grep -q "reported more than once within one source"; then ok "one entry reported five times in one source counts once"
else bad "same entry + source was counted more than once"; fi

echo
echo "[conflict stats] entries for review, rule prompts, calibration, safety"
rm -f "$LOG"
repok --entry sk/twice --source X1; resok --conflict-id "$(lastid)" --verdict accept
if dec stats | grep -q "mark for review"; then bad "one source marked an entry for review"
else ok "one source does not mark an entry for review"; fi
repok --entry sk/twice --source X2; resok --conflict-id "$(lastid)" --verdict accept
if dec stats | grep -q "sk/twice  (2 sources)"; then ok "two distinct sources mark it for review"
else bad "two distinct sources did not mark the entry"; fi

rm -f "$LOG"; gen 3 stale seen amend scope P "" SAMESRC
if dec stats | grep -q "you call it scope"; then bad "one source raised a rule prompt"
else ok "three entries from one source do not raise a rule prompt"; fi
rm -f "$LOG"; gen 3 stale seen amend scope P
if dec stats | grep -q "you call it scope: 3 distinct sources"; then ok "three distinct sources raise the rule prompt"
else bad "three distinct sources raised no rule prompt"; fi

rm -f "$LOG"; gen 3 stale seen accept "" H high; gen 2 stale seen amend scope H2 high
gen 5 stale seen accept "" L low
if dec stats | grep -q "does no better than 'low'"; then ok "high doing worse than low is called out"
else bad "a useless certainty went unmentioned"; fi
rm -f "$LOG"; gen 5 stale seen accept "" H high; gen 3 stale seen accept "" L low; gen 2 stale seen amend scope L2 low
if dec stats | grep -q "does no better than 'low'"; then bad "a working certainty was called useless"
else ok "high doing better than low raises nothing"; fi

rm -f "$LOG"; gen 1 stale seen accept
if dec stats | grep -q "Safety entries"; then bad "the safety note shows with no safety record"
else ok "no safety note without a safety record"; fi
repok --entry sk/s --source S9 --safety
if dec stats | grep -q "Safety entries"; then ok "a safety report brings the always-in-full note"
else bad "a safety report brought no note"; fi

echo
echo "[exam] and AI reports are events, not decisions"
rm -f "$LOG"
if dec exam --result maybe --reason r >/dev/null 2>&1; then bad "an exam result other than pass/fail was accepted"
else ok "an exam result other than pass/fail is refused"; fi
if dec exam --result pass --reason " " >/dev/null 2>&1; then bad "an exam without a reason was accepted"
else ok "an exam without a reason is refused"; fi
addok --subject s --verdict accept --reason r
examrec pass
repok
if dec stats | grep -qE '^by verdict: accept 1$' && dec stats | grep -q "exam sitting" \
   && dec stats | grep -q "AI conflict report"; then
  ok "exam sittings and AI reports are counted apart from decisions"
else bad "the tally was polluted: $(dec stats | grep '^by verdict')"; fi

rm -f "$LOG"
repok --entry sk/l; resok --conflict-id "$(lastid)" --verdict amend --final-type scope
dec miss --entry sk/gone --final-type wrong --verdict accept --subject s --reason r >/dev/null 2>&1
if dec list | grep -q "\[report\]  C-.* · [0-9a-f]\{6\}" && dec list | grep -q "→ scope" \
   && dec list | grep -q "MISSED"; then
  ok "list shows the report with its fingerprint, the answer and the miss"
else bad "list hides the report, the answer or the miss"; fi

echo
echo "[empty] an empty log says so instead of pretending"
rm -f "$LOG"
if dec stats | grep -q "expected state"; then ok "empty log explains itself"; else bad "empty log output is unhelpful"; fi

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1

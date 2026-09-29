#!/usr/bin/env bash
# Mutation battery for `whetstone decision`. Removes one piece of logic at a time
# and requires the selftest to go RED. A check whose removal changes nothing is not
# being tested, and a green suite over such a check reports a safety that is not
# there.
#
# Every entry below is a way this tool could fail SILENTLY — folding counts without
# saying so, counting lines instead of sources, spinning forever on an alias loop.
# Those are the failures nobody would notice from the output alone, which is exactly
# why each needs a test standing in its way.
#
#   bash bin/decision_mutation_test.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
S="$(mktemp -d "$SCRIPT_DIR/../.decision-mutation.XXXXXX")"
trap 'cp "$S/decision.orig.py" bin/decision.py 2>/dev/null; rm -rf "$S"' EXIT
cp bin/decision.py "$S/decision.orig.py"
caught=0; missed=0; skipped=0

mut() { # $1 = label, $2 = python source that mutates bin/decision.py
  if ! python3 -c "$2"; then
    echo "  --  MUTATION DID NOT APPLY: $1"; skipped=$((skipped+1))
    cp "$S/decision.orig.py" bin/decision.py; return
  fi
  # a mutation may remove a loop guard, so the suite must be able to time out
  if timeout 180 bash bin/decision_selftest.sh >/dev/null 2>&1; then
    echo "  MISS  $1"; missed=$((missed+1))
  else
    echo "  ok    $1"; caught=$((caught+1))
  fi
  cp "$S/decision.orig.py" bin/decision.py
}

R='import io,sys;p="bin/decision.py";s=io.open(p,encoding="utf-8").read()'
W='io.open(p,"w",encoding="utf-8").write(s)'

mut "stats: count lines instead of distinct sources" \
"$R
o='            by_tag_sources.setdefault(canon, set()).add(r.get(\"source\") or \"__no-source__\")'
assert o in s; s=s.replace(o,'            by_tag_sources.setdefault(canon, []).append(1)',1)
$W"

mut "stats: stop folding aliases (every spelling counts alone)" \
"$R
o='            canon, cyc = canonical(tag, amap)'
assert o in s; s=s.replace(o,'            canon, cyc = tag, False',1)
$W"

mut "stats: fold the counts but do not print the fold" \
"$R
o='    if folded:\n'
i=s.index(o); j=s.index('    if looped:', i)
s=s[:i]+s[j:]
$W"

mut "stats: count alias rules as decisions" \
"$R
o='            n_alias += 1\n            continue'
assert o in s; s=s.replace(o,'            n_alias += 1',1)
$W"

mut "canonical: drop the cycle guard (alias loops spin forever)" \
"$R
o='        if cur in seen:\n            return tag, True\n'
assert o in s; s=s.replace(o,'',1)
$W"

mut "alias: allow a loop-closing alias to be written" \
"$R
o='        if cyc:\n            print(f\"refused:'
i=s.index(o); j=s.index('return 2', i)+len('return 2')+1
s=s[:i]+s[j:]
$W"

mut "add: stop showing the vocabulary when a new tag appears" \
"$R
o='            show_vocabulary(args.tag, prior)'
assert o in s; s=s.replace(o,'            pass',1)
$W"

mut "alias_map: ignore the self-alias cancel" \
"$R
o='        if f == t:\n            m.pop(f, None)\n        else:\n            m[f] = t'
assert o in s; s=s.replace(o,'        m[f] = t',1)
$W"

# --- use-time conflicts: every way a group could be relaxed that it should not be,
# --- and every way the AI could end up agreeing with the human in hindsight ---------

mut "conflict: relax on the point estimate instead of the exact lower bound" \
"$R
o='        lb = lower_bound(k, len(basis))'
assert o in s; s=s.replace(o,'        lb = k / len(basis) if basis else 0.0',1)
$W"

mut "conflict: a miss no longer resets its type" \
"$R
o='        cut = last_miss.get(typ, -1)'
assert o in s; s=s.replace(o,'        cut = -1',1)
$W"

mut "conflict: let inferred / unseen groups relax too" \
"$R
o='        if ev != \"seen\":\n            tier = \"full (nothing seen to show)\"\n        elif not relax_ok:'
assert o in s; s=s.replace(o,'        if not relax_ok:',1)
$W"

mut "conflict: warn about the guess share but relax anyway" \
"$R
o='        relax_ok = False\n        print(f\"  ! {share'
assert o in s; s=s.replace(o,'        print(f\"  ! {share',1)
$W"

mut "conflict: count a false alarm as a wrong type" \
"$R
o='        return x[\"verdict\"] is not None and x[\"verdict\"] != \"defer\" and x[\"final\"] != \"none\"'
assert o in s; s=s.replace(o,'        return x[\"verdict\"] is not None and x[\"verdict\"] != \"defer\"',1)
$W"

mut "conflict: count a deferred answer as judged" \
"$R
o='        return x[\"verdict\"] is not None and x[\"verdict\"] != \"defer\" and x[\"final\"] != \"none\"'
assert o in s; s=s.replace(o,'        return x[\"verdict\"] is not None and x[\"final\"] != \"none\"',1)
$W"

mut "conflict: score a report that is still awaiting its answer" \
"$R
o='        return x[\"verdict\"] is not None and x[\"verdict\"] != \"defer\" and x[\"final\"] != \"none\"'
assert o in s; s=s.replace(o,'        return x[\"verdict\"] != \"defer\" and x[\"final\"] != \"none\"',1)
$W"

mut "conflict: mark an entry for review one source too late" \
"$R
o='if len(s) >= ENTRY_REVIEW_MIN)'
assert o in s; s=s.replace(o,'if len(s) > ENTRY_REVIEW_MIN)',1)
$W"

mut "conflict: rule prompts count lines, not distinct sources" \
"$R
o='set()).add(\n                x[\"key\"][1])'
assert o in s; s=s.replace(o,'[]).append(1)',1)
$W"

mut "conflict: never voice the calibration warning" \
"$R
o='and hi[1] / hi[0] <= lo[1] / lo[0]):'
assert o in s; s=s.replace(o,'and False):',1)
$W"

mut "hindsight: score the LAST report of an entry instead of the first" \
"$R
o='        first_i, first = g[0]'
assert o in s; s=s.replace(o,'        first_i, first = g[-1]',1)
$W"

mut "hindsight: score every report on its own (no one-per-entry-and-source)" \
"$R
o='        key = (r.get(\"entry\", \"?\"), r.get(\"source\") or \"__no-source__\")\n        groups.setdefault(key, []).append((i, r))'
assert o in s; s=s.replace(o,'        key = (r.get(\"entry\", \"?\"), r.get(\"conflict_id\"))\n        groups.setdefault(key, []).append((i, r))',1)
$W"

mut "hindsight: stop checking fingerprints (an edited call is scored)" \
"$R
o='        if r.get(\"fingerprint\") != fingerprint(r):'
assert o in s; s=s.replace(o,'        if False:',1)
$W"

mut "hindsight: accept an answer written before its report" \
"$R
o='        if cid not in report_pos or i < report_pos[cid]:'
assert o in s; s=s.replace(o,'        if cid not in report_pos:',1)
$W"

mut "hindsight: resolve writes an answer with no report on file" \
"$R
o='    if rep is None:\n'
assert o in s; s=s.replace(o,'    rep = rep or {}\n    if False:\n',1)
$W"

mut "hindsight: let a second report reuse an id (a call rewritten)" \
"$R
o='    if any(r.get(\"kind\") == \"conflict-report\" and r.get(\"conflict_id\") == cid for r in recs):'
assert o in s; s=s.replace(o,'    if False:',1)
$W"

mut "hindsight: reopen the one-line add --kind conflict path" \
"$R
o='    if args.kind == \"conflict\":\n        # the one-line form'
i=s.index(o); j=s.index('return 2', i)+len('return 2')+1
s=s[:i]+s[j:]
$W"

mut "model: basis counts every model's reports, not just the current one" \
"$R
o='        basis = [x for x in g if x[\"model\"] == current and x[\"pos\"] > cut and judged(x)]'
assert o in s; s=s.replace(o,'        basis = [x for x in g if x[\"pos\"] > cut and judged(x)]',1)
$W"

mut "model: the current model is the earliest report, not the latest" \
"$R
o='latest[-1].get(\"model\")'
assert o in s; s=s.replace(o,'latest[0].get(\"model\")',1)
$W"

mut "model: the fingerprint leaves the model out (a report can be relabelled)" \
"$R
o='+ ([\"model\"] if \"model\" in rec else [])'
assert o in s; s=s.replace(o,'',1)
$W"

mut "resolve: accept a changed type under verdict accept" \
"$R
o='    if final and final != \"none\" and verdict == \"accept\":'
assert o in s; s=s.replace(o,'    if False:',1)
$W"

mut "resolve: store a final-type identical to the AI's" \
"$R
o='    if args.final_type and not same:'
assert o in s; s=s.replace(o,'    if args.final_type:',1)
$W"

mut "stats: count AI reports as decisions" \
"$R
o='            events[r[\"kind\"]] = events.get(r[\"kind\"], 0) + 1\n            continue'
assert o in s; s=s.replace(o,'            events[r[\"kind\"]] = events.get(r[\"kind\"], 0) + 1',1)
$W"

cp "$S/decision.orig.py" bin/decision.py
echo
echo "mutations caught: $caught   missed: $missed   did-not-apply: $skipped"
# a mutation that fails to apply is neither caught nor missed — it silently proves
# nothing, so it fails the run rather than passing quietly
bash bin/decision_selftest.sh 2>&1 | tail -1
[ "$missed" -eq 0 ] && [ "$skipped" -eq 0 ]

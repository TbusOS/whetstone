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

cp "$S/decision.orig.py" bin/decision.py
echo
echo "mutations caught: $caught   missed: $missed   did-not-apply: $skipped"
# a mutation that fails to apply is neither caught nor missed — it silently proves
# nothing, so it fails the run rather than passing quietly
bash bin/decision_selftest.sh 2>&1 | tail -1
[ "$missed" -eq 0 ] && [ "$skipped" -eq 0 ]

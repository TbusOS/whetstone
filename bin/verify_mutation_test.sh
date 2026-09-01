#!/usr/bin/env bash
# Mutation battery for `whetstone verify`. Deletes one piece of checking logic at a
# time and requires the selftest to go RED. A check whose removal changes nothing is
# not actually being tested — and a green suite over such a check is worse than no
# suite, because it reports safety that is not there.
#
# This is how the two reviews' findings are kept fixed: each entry below is a real
# bypass or false positive somebody found, and the mutation restores the old broken
# behaviour to prove a test now stands in its way.
#
#   bash bin/verify_mutation_test.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
S="$(mktemp -d "$SCRIPT_DIR/../.verify-mutation.XXXXXX")"
trap 'cp "$S/verify.orig.py" bin/verify.py 2>/dev/null; rm -rf "$S"' EXIT
cp bin/verify.py "$S/verify.orig.py"
caught=0; missed=0

mut() { # $1 = label, $2 = python source that mutates bin/verify.py
  if ! python3 -c "$2"; then echo "  --  mutation would not apply: $1"; cp "$S/verify.orig.py" bin/verify.py; return; fi
  if bash bin/verify_selftest.sh >/dev/null 2>&1; then
    echo "  MISS  $1"; missed=$((missed+1))
  else
    echo "  ok    $1"; caught=$((caught+1))
  fi
  cp "$S/verify.orig.py" bin/verify.py
}

R='import io,sys;p="bin/verify.py";s=io.open(p,encoding="utf-8").read()'
W='io.open(p,"w",encoding="utf-8").write(s)'

mut "cap_for: drop the L1/L2 single-platform cap" \
"$R
o='    if layer in (\"L1\", \"L2\") and distinct < 2:\n'
i=s.index(o); j=s.index('\n', s.index('return 0', i))+1
s=s[:i]+s[j:]
$W"

mut "cap_for: drop 'verified once -> med'" \
"$R
o='    if verified:\n'
i=s.index(o); j=s.index('\n', s.index('return 1', i))+1
s=s[:i]+s[j:]
$W"

mut "V19/V09b: stop skipping blockquotes" \
"$R
o='        if t.lstrip().startswith(\">\"):\n            continue\n'
assert o in s; s=s.replace(o,'',1)
$W"

mut "strip_fences: stop tracking fences" \
"$R
o='        if t.lstrip().startswith(\"\`\`\`\"):\n            fence = not fence\n'
assert o in s; s=s.replace(o,'        if False:\n            fence = not fence\n',1)
$W"

mut "SKILL.md tables: hardcode the layer to L3" \
"$R
o='        r[\"layer\"] = r[\"layer\"] or layer_of_section(text, r[\"line\"]) or \"L2\"'
assert o in s; s=s.replace(o,'        r[\"layer\"] = \"L3\"',1)
$W"

mut "repro_key: revert to the shallow normalisation" \
"$R
i=s.index('    norm = re.sub('); j=s.index('\n', i)+1
s=s[:i]+'    norm = head\n'+s[j:]
$W"

mut "parse_blocks: stop treating --- as a boundary" \
"$R
o=' or re.fullmatch(r\"\\\\s*([-*_=])\\\\1{2,}\\\\s*\", t)'
assert o in s; s=s.replace(o,'',1)
$W"

mut "layer_of_section: match a bare L3 anywhere in the heading" \
"$R
o='r\"[(（]\\\\s*L([1-4])\\\\s*[)）]\\\\s*\$\", t.strip()'
assert o in s; s=s.replace(o,'r\"\\\\bL([1-4])\\\\b\", t',1)
$W"

mut "is_table_head: require a leading pipe again" \
"$R
o='    return (\"|\" in lines[i]'
assert o in s; s=s.replace(o,'    return (lines[i].strip().startswith(\"|\")',1)
$W"

mut "TESTED_OK: drop the 未 lookbehind" \
"$R
o='(?<!未)实测'
assert o in s; s=s.replace(o,'实测',1)
$W"

mut "V20: search the raw body instead of the unfenced prose" \
"$R
o='            m = re.search(r\"涉及事实[^\\\\n]*\", prose)'
assert o in s; s=s.replace(o,'            m = re.search(r\"涉及事实[^\\\\n]*\", body)',1)
$W"

mut "FIELD_LINE: narrow the prefix back to -/*" \
"$R
o='r\"^\\\\s*>?\\\\s*(?:[-*+]|\\\\d+[.)])?\\\\s*\\\\**\\\\s*\"'
assert o in s; s=s.replace(o,'r\"^\\\\s*[-*]?\\\\s*\\\\**\\\\s*\"',1)
$W"

cp "$S/verify.orig.py" bin/verify.py
echo
echo "mutations caught: $caught   missed: $missed"
bash bin/verify_selftest.sh 2>&1 | tail -1
[ "$missed" -eq 0 ]

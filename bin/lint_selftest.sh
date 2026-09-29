#!/usr/bin/env bash
# Selftest for bin/lint.py (the menu-size checks, the frontmatter parser they depend
# on) and adapters/menu/claude-code.py. Every check is exercised in both directions:
# the case it must flag, and the nearest case it must leave alone.
#
# Why the parser is tested first: the menu size is only as right as the descriptions
# it adds up. The earlier parser read one line of a quoted description, so a
# 1,693-char description counted as 1,462 and its second line became a bogus key.
#
#   bash bin/lint_selftest.sh
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
unset CDPATH WHETSTONE_SKILLS_DIR
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGE="$REPO_DIR/.lint-selftest"
LINT="${LINT_UNDER_TEST:-$SCRIPT_DIR/lint.py}"
ADAPTER="${ADAPTER_UNDER_TEST:-$REPO_DIR/adapters/menu/claude-code.py}"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT
rm -rf "$STAGE"; mkdir -p "$STAGE"

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok  - $1"; }
bad() { fail=$((fail+1)); echo "  FAIL- $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

# skill <lib> <dir> <frontmatter body lines...>   (name: <dir> is added first)
skill() {
  local lib="$1" d="$2"; shift 2
  mkdir -p "$lib/$d"
  { echo "---"; echo "name: $d"; printf '%s\n' "$@"; echo "---"; echo; echo "# $d heading"; } > "$lib/$d/SKILL.md"
}
rep() { python3 -c "import sys; print(sys.argv[1] * int(sys.argv[2]), end='')" "$1" "$2"; }
# jq-free JSON probe: jget <file> <python expression over d>
jget() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print($2)" "$1"; }

echo "whetstone lint selftest"

# ---------------------------------------------------------------- parser
echo
echo "[parse] the scalar forms skill files use"
# compared in Python, so the expected strings are written once and exactly
python3 - "$(dirname "$LINT")" "$STAGE/parse" > "$STAGE/parse.out" <<'EOF'
import os, sys
sys.path.insert(0, sys.argv[1]); import lint
root = sys.argv[2]
def case(label, fm_lines, want_desc=None, want_keys=None):
    d = os.path.join(root, str(len(os.listdir(root)) if os.path.isdir(root) else 0))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: t\n" + "\n".join(fm_lines) + "\n---\n\n# heading\n")
    got = lint.parse_frontmatter(os.path.join(d, "SKILL.md"))
    good = (want_desc is None or got.get("description") == want_desc) and \
           (want_keys is None or sorted(got) == sorted(want_keys))
    print(("ok  - " if good else "FAIL- ") + label + ("" if good else f"  got {got!r}"))
os.makedirs(root, exist_ok=True)
case("a quoted value continues past a column-0 line",
     ['description: "first line of it,', '**second** line: at column 0, legal inside quotes"', 'metadata:', '  type: x'],
     "first line of it, **second** line: at column 0, legal inside quotes")
case("...and that line does not become a new key",
     ['description: "first line,', '**second**: x"', 'metadata:', '  type: x'],
     want_keys=["name", "description", "metadata"])
case('double quotes: \\" is a quote, \\\\ a backslash, \\n a line break',
     [r'description: "say \"hi\", a \\ and\nbreak"'], 'say "hi", a \\ and\nbreak')
case("single quotes: a doubled quote is one quote", ["description: 'it''s single'"], "it's single")
case("a folded block joins lines with spaces", ["description: >", "  one", "  two", "x: y"], "one two")
case("a literal block keeps the line break", ["description: |", "  one", "  two"], "one\ntwo")
case("a plain value continues on indented lines",
     ["description: plain start", "  and its continuation", "metadata:", "  type: y"],
     "plain start and its continuation")
case("a nested block after a value is not glued onto it",
     ["description: short one", "metadata:", "  type: z"], "short one", ["name", "description", "metadata"])
case("an empty line inside quotes is a line break", ['description: "para one', '', '  para two"'], "para one\npara two")
EOF
while IFS= read -r line; do
  echo "  $line"
  case "$line" in "ok  - "*) pass=$((pass+1));; *) fail=$((fail+1));; esac
done < "$STAGE/parse.out"
[ -s "$STAGE/parse.out" ] || bad "the parser checks did not run"

echo
echo "[yaml] a description a strict runtime may drop"
Y="$STAGE/yaml"
long="$(rep 'word ' 10)"
skill "$Y" plain-colon "description: does X: then Y. 触发词: x, y. $long"
skill "$Y" quoted-colon "description: \"does X: then Y. 触发词: x, y. $long\""
skill "$Y" plain-hash "description: does X #not a comment in intent. 触发词 x y. $long"
skill "$Y" never-closed "description: \"opens and never closes. 触发词: x. $long"
python3 "$LINT" --src "$Y" > "$STAGE/y.txt" 2>&1
check "an unquoted ': ' is flagged" 'grep -q "plain-colon.*not valid YAML.*: " "$STAGE/y.txt"'
check "the same text quoted is not" '! grep -q "quoted-colon.*not valid YAML" "$STAGE/y.txt"'
check "an unquoted \" #\" is flagged" 'grep -q "plain-hash.*not valid YAML.*#" "$STAGE/y.txt"'
check "a quote that never closes is flagged" 'grep -q "never-closed.*not valid YAML.*never closed" "$STAGE/y.txt"'

# ---------------------------------------------------------------- length
echo
echo "[length] the Agent Skills limit on one description"
L="$STAGE/len"
mk() { python3 -c "import sys; p='触发词: a. '; print(p + 'x' * (int(sys.argv[1]) - len(p)), end='')" "$1"; }
d1024="$(mk 1024)"
d1025="$(mk 1025)"
skill "$L" at-limit "description: \"$d1024\""
skill "$L" over-limit "description: \"$d1025\""
python3 "$LINT" --src "$L" > "$STAGE/l.txt" 2>&1
check "1025 chars is over the limit" 'grep -q "over-limit.*1025 chars, over the Agent Skills limit of 1024" "$STAGE/l.txt"'
python3 "$LINT" --src "$L" --json > "$STAGE/l.json" 2>/dev/null
check "…as a warning, not a note" '[ "$(jget "$STAGE/l.json" "[w[\"who\"] for w in d[\"warnings\"] if \"Agent Skills limit\" in w[\"msg\"]]")" = "['"'"'over-limit'"'"']" ]'
check "1024 chars is not (only the 'long' note)" '! grep -q "at-limit.*Agent Skills limit" "$STAGE/l.txt" && grep -q "at-limit.*description long (1024" "$STAGE/l.txt"'

# ---------------------------------------------------------------- menu size
echo
echo "[menu] does the whole library fit"
M="$STAGE/menu"
skill "$M" alpha "description: \"alpha does one thing. 触发词: alpha, first. $(rep a 60)\""
skill "$M" beta  "description: \"beta does another.\\nIts second line. 触发词: beta, second. $(rep b 120)\""
# gamma is the longest, so name order and length order differ
skill "$M" gamma "description: \"gamma is the longest. 触发词: gamma, third words. $(rep g 300)\""
# the menu text a runtime would build from this library, built here independently
python3 - "$(dirname "$LINT")" "$M" > "$STAGE/full.txt" <<'EOF'
import sys; sys.path.insert(0, sys.argv[1]); import lint
sk = lint.load_skills(sys.argv[2])
print("\n".join(f"- {s['name']}: {s['menu_desc']}" for s in sk))
EOF
FULL=$(python3 -c "import sys; print(len(open(sys.argv[1], encoding='utf-8').read()))" "$STAGE/full.txt")
python3 "$LINT" --src "$M" --json > "$STAGE/m0.json"
check "menu size = the length of the menu text it stands for ($FULL)" '[ "$(jget "$STAGE/m0.json" "d[\"menu\"][\"chars\"]")" = "$FULL" ]'
check "under the default budget: no over-budget warning" '! grep -q "menu needs" "$STAGE/m0.json"'
python3 "$LINT" --src "$M" > "$STAGE/m0.txt"
check "…and the report shows headroom" 'grep -q "headroom" "$STAGE/m0.txt"'

B=$((FULL - 50))
python3 "$LINT" --src "$M" --menu-budget "$B" --json > "$STAGE/m1.json"; rc=$?
check "over the budget: warned, with the overshoot (50)" 'grep -q "over by 50)" "$STAGE/m1.json"'
check "a warning alone keeps exit 0" '[ "$rc" = 0 ]'
python3 "$LINT" --src "$M" --menu-budget "$B" --strict >/dev/null 2>&1; rc=$?
check "…and --strict turns it into exit 1" '[ "$rc" = 1 ]'

python3 "$LINT" --src "$M" --menu-budget "$((FULL + 10))" --json > "$STAGE/m2.json"
python3 "$LINT" --src "$M" --menu-budget "$((FULL + 10))" --menu-reserve 20 --json > "$STAGE/m3.json"
check "10 chars of headroom: fits" '! grep -q "menu needs" "$STAGE/m2.json"'
check "…and 20 chars from outside the library push it over" 'grep -q "over by 10)" "$STAGE/m3.json"'

# fair share and the trim order, from the definition, not from the code
# at budget 100 every description is above the share, so the order has 3 items to get wrong
python3 "$LINT" --src "$M" --menu-budget 100 --json > "$STAGE/m6.json"
python3 - "$(dirname "$LINT")" "$M" "$STAGE/m1.json" "$B" "$STAGE/m6.json" 100 > "$STAGE/fair.txt" <<'EOF'
import json, sys; sys.path.insert(0, sys.argv[1]); import lint
sk = lint.load_skills(sys.argv[2]); bad = []
for jf, B in ((sys.argv[3], int(sys.argv[4])), (sys.argv[5], int(sys.argv[6]))):
    d = json.load(open(jf))
    fair = (B - sum(len(s["name"]) + 5 for s in sk)) // len(sk)
    order = [s["name"] for s in sorted(sk, key=lambda s: -len(s["menu_desc"])) if len(s["menu_desc"]) > fair]
    got = [t["name"] for t in d["menu"]["trim"]]
    if d["menu"]["fair_share"] != fair or got != order:
        bad.append(f"budget {B}: fair {d['menu']['fair_share']} want {fair}; order {got} want {order}")
    if B == 100 and len(order) < 3:
        bad.append("fixture: budget 100 should put all 3 above the share")
print("ok" if not bad else "; ".join(bad))
EOF
check "fair share and trim order match their definition" '[ "$(cat "$STAGE/fair.txt")" = ok ]'
check "a usable fair share: no 'retire or merge'" '! grep -q "retire or merge" "$STAGE/m1.json"'
python3 "$LINT" --src "$M" --menu-budget 100 --json > "$STAGE/m4.json"
check "a share below 40 chars says retire or merge" 'grep -q "below the 40 a description needs" "$STAGE/m4.json" && [ "$(jget "$STAGE/m4.json" "0 < d[\"menu\"][\"fair_share\"] < 40")" = True ]'
python3 "$LINT" --src "$M" --menu-budget 100 --menu-reserve 100 --json > "$STAGE/m5.json"
check "reserve alone fills the budget: says retire or merge" 'grep -q "already fill it" "$STAGE/m5.json"'

# ---------------------------------------------------------------- listing
echo
echo "[listing] compare with the menu a runtime actually sent"
python3 - "$(dirname "$LINT")" "$M" > "$STAGE/snap.txt" <<'EOF'
import sys; sys.path.insert(0, sys.argv[1]); import lint
sk = {s["name"]: s for s in lint.load_skills(sys.argv[2])}
print("- alpha")                                       # name only
assert "\n" in sk["beta"]["menu_desc"]
print(f"- beta: {sk['beta']['menu_desc']}")            # its line break splits the entry
print("- plug:tool")                                   # foreign, colon in the name
print("- plug:other: a foreign description")          # foreign, with a description
EOF
python3 "$LINT" --src "$M" --listing "$STAGE/snap.txt" --json > "$STAGE/s1.json"
check "a name-only skill is listed" 'grep -q "shown as name only in the menu snapshot.*: alpha\"" "$STAGE/s1.json"'
check "a described skill is not, even when its text wraps" '[ "$(jget "$STAGE/s1.json" "d[\"menu\"][\"snapshot\"][\"name_only\"]")" = "['"'"'alpha'"'"']" ] && [ "$(jget "$STAGE/s1.json" "d[\"menu\"][\"snapshot\"][\"different\"]")" = "[]" ]'
check "a skill absent from the snapshot is noted" 'grep -q "\"gamma\"" "$STAGE/s1.json" && [ "$(jget "$STAGE/s1.json" "d[\"menu\"][\"snapshot\"][\"missing\"]")" = "['"'"'gamma'"'"']" ]'
want=$(python3 -c "print(len('plug:tool') + 3 + len('plug:other') + 5 + len('a foreign description'))")
check "entries outside the library are measured as the reserve ($want)" '[ "$(jget "$STAGE/s1.json" "d[\"menu\"][\"reserve\"]")" = "$want" ] && [ "$(jget "$STAGE/s1.json" "d[\"menu\"][\"reserve_source\"]")" = listing ]'
sed 's/^- beta: .*/- beta: something else entirely/' "$STAGE/snap.txt" | grep -v '^[^-]' > "$STAGE/snap2.txt"
python3 "$LINT" --src "$M" --listing "$STAGE/snap2.txt" --json > "$STAGE/s2.json"
check "a different description in the menu is flagged" '[ "$(jget "$STAGE/s2.json" "d[\"menu\"][\"snapshot\"][\"different\"]")" = "['"'"'beta'"'"']" ] && grep -q "menu shows a different description" "$STAGE/s2.json"'
python3 "$LINT" --src "$M" --listing - --json < "$STAGE/snap.txt" > "$STAGE/s3.json"
check "--listing - reads stdin, same result" '[ "$(jget "$STAGE/s3.json" "d[\"menu\"]")" = "$(jget "$STAGE/s1.json" "d[\"menu\"]")" ]'
printf 'not a menu\n' > "$STAGE/junk.txt"
python3 "$LINT" --src "$M" --listing "$STAGE/junk.txt" >/dev/null 2>&1; rc=$?
check "a file with no entries is refused (exit 2)" '[ "$rc" = 2 ]'
python3 "$LINT" --src "$M" --listing "$STAGE/nope.txt" >/dev/null 2>&1; rc=$?
check "an unreadable listing is refused (exit 2)" '[ "$rc" = 2 ]'

# ---------------------------------------------------------------- adapter
echo
echo "[adapter] adapters/menu/claude-code.py picks the latest full menu"
A="$STAGE/projects"; mkdir -p "$A/p1" "$A/p2"
python3 - "$A" <<'EOF'
import json, os, sys
A = sys.argv[1]
def rec(ts, initial, content):
    return json.dumps({"type": "attachment", "timestamp": ts,
                       "attachment": {"type": "skill_listing", "isInitial": initial,
                                      "skillCount": content.count("- "), "content": content}})
with open(os.path.join(A, "p1", "older-session.jsonl"), "w") as f:
    f.write(rec("2026-01-01T00:00:00Z", True, "- old: old menu") + "\n")
with open(os.path.join(A, "p2", "newer-session.jsonl"), "w") as f:
    f.write('{"broken json\n')
    f.write('{"type":"attachment","attachment":{"type":"skill_listing"}}\n')
    f.write(rec("2026-01-02T00:00:00Z", True, "- new: new menu\n- bare") + "\n")
    f.write(rec("2026-01-03T00:00:00Z", False, "- delta: added mid-session") + "\n")
# the file with the older menu gets the newer mtime, so it is scanned first:
# the menu's own timestamp must decide, not the order files are read in
import time
t = time.time()
os.utime(os.path.join(A, "p2", "newer-session.jsonl"), (t - 100, t - 100))
os.utime(os.path.join(A, "p1", "older-session.jsonl"), (t, t))
EOF
out="$(python3 "$ADAPTER" --projects "$A" 2>/dev/null)"; rc=$?
check "newest full menu wins; a newer delta and broken lines are skipped" '[ "$rc" = 0 ] && [ "$out" = "$(printf -- "- new: new menu\n- bare")" ]'
out="$(python3 "$ADAPTER" --projects "$A" --session older 2>/dev/null)"
check "--session narrows to one session" '[ "$out" = "- old: old menu" ]'
python3 "$ADAPTER" --projects "$A" --session nosuch >/dev/null 2>&1; rc=$?
check "no menu found: exit 2" '[ "$rc" = 2 ]'
python3 "$ADAPTER" --projects "$A" | python3 "$LINT" --src "$M" --listing - --json > "$STAGE/pipe.json" 2>/dev/null
check "adapter | lint --listing - works end to end" '[ "$(jget "$STAGE/pipe.json" "d[\"menu\"][\"snapshot\"][\"entries\"]")" = 2 ]'

# ---------------------------------------------------------------- the old checks
echo
echo "[existing] checks that were there before still fire"
O="$STAGE/old"
skill "$O" empty 'description: ""'
skill "$O" fine "description: \"fine skill does a thing. 触发词: fine, thing.\""
python3 "$LINT" --src "$O" > "$STAGE/o.txt" 2>&1; rc=$?
check "an empty description is an ERROR, exit 1" '[ "$rc" = 1 ] && grep -q "empty: description missing" "$STAGE/o.txt"'
check "a fine skill raises nothing" '! grep -q "^  fine" "$STAGE/o.txt"'
python3 "$LINT" --src "$O" --json > "$STAGE/o.json" 2>/dev/null
check "--json carries the menu report" '[ "$(jget "$STAGE/o.json" "d[\"menu\"][\"budget\"]")" = 25000 ]'

echo
echo "lint selftest: $pass passed, $fail failed"
[ "$fail" = 0 ]

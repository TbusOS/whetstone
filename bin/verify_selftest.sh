#!/usr/bin/env bash
# Selftest for `whetstone verify`. Builds generic fixture packages under
# .verify-selftest/ and asserts, for every check, BOTH directions:
#   - a defective fixture makes that code fire
#   - a conforming fixture does NOT make it fire
# A checker that only ever fires is as useless as one that never does; only the
# pair proves the check is looking at the thing it claims to look at.
# The final [coverage] block enforces this by reading `verify.py --explain` and
# failing if any published code lacks either direction — so this comment cannot
# drift away from the truth the way a hand-maintained claim would.
# Fixtures are 100% generic (soc-x / proj-a) — no real platform values.
# Exit 0 = all pass.
#
#   bash bin/verify_selftest.sh

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
unset CDPATH
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGE="$REPO_DIR/.verify-selftest"
VERIFY="$SCRIPT_DIR/verify.py"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT
rm -rf "$STAGE"; mkdir -p "$STAGE"

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok  - $1"; }
bad() { fail=$((fail+1)); echo "  FAIL- $1"; }

# codes emitted for a package, space separated
codes() {
  python3 "$VERIFY" "$1" --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(" ".join(sorted({i["code"] for p in d["packages"] for i in p["items"]})))'
}
has()  { case " $(codes "$1") " in *" $2 "*) return 0;; *) return 1;; esac; }

fires()     { if has "$1" "$2"; then ok "$2 fires — $3"; else bad "$2 did NOT fire — $3"; fi; }
not_fires() { if has "$1" "$2"; then bad "$2 false-positive — $3"; else ok "$2 quiet — $3"; fi; }

# ---------------------------------------------------------------- fixtures ---
# A clean, fully conforming package. Everything else is a mutation of this.
mkclean() {
  local d="$1" ; rm -rf "$d"; mkdir -p "$d/params"
  cat > "$d/SKILL.md" <<'EOF'
---
name: demo-skill
description: "Demo package used by the verify selftest. 触发词:demo / selftest。与 demo-skill-audit 同族,不重复它。"
---

# Demo Skill

## 原理与约束 (L1)

- 一次性写入的存储写坏就回不去,所以写之前必须先把原始内容存下来。

## 设计与流程 (L2)

- 先读回再比对,不从上层现象反推底层状态。

## 坑 (L2)

见 `pitfalls.md`。

## 平台参数 (L3)

> 具体值见 `params/soc-x.md`。
- 已支持平台:soc-x

## 溯源

- 来源:commit 1a2b3c4d
- 提炼日期:2026-09-02
- 复现记录:
  - soc-x · 2026-08-01 · commit 1a2b3c4d
  - proj-a · 2026-09-01 · commit 5e6f7a8b
- 验证方式:bash scripts/check.sh · 实测:通过 2026-09-01
- 置信度:high
EOF
  cat > "$d/pitfalls.md" <<'EOF'
# pitfalls.md — L2 坑库(append-only)

## 从上层状态反推底层状态会看错

- 症状:上层字段显示未生效,底层其实已经生效。
- 真因:中间层缓存了一份过期副本。
- 修法:直接读底层,不看中间层。
- 涉及事实:见 `params/soc-x.md`
- 溯源:
  - 来源:commit 1a2b3c4d · 日期:2026-08-01
  - 复现记录:
    - soc-x · 2026-08-01 · commit 1a2b3c4d
    - proj-a · 2026-09-01 · commit 5e6f7a8b
  - 验证方式:bash scripts/check.sh · 实测:通过 2026-09-01
  - 置信度:high
EOF
  cat > "$d/params/soc-x.md" <<'EOF'
# params/soc-x.md — L3 平台专属参数与事实

## 参数
| 参数 | 值 | 来源 · 日期 | 验证方式 · 实测 | 复现记录 | 置信度 |
|---|---|---|---|---|---|
| 存储起始位置 | `SLOT_A` | commit 1a2b3c4d · 2026-08-01 | 读回比对 · 实测:通过 2026-09-01 | 2026-08-01 · commit 1a2b3c4d; 2026-09-01 · commit 5e6f7a8b | high |

## 替代记录
- 2026-09-01 原 SLOT_0 → 改为 SLOT_A,因命名统一(commit 5e6f7a8b)
EOF
}

echo "whetstone verify selftest"
echo
echo "[base] clean fixture must be silent"
CLEAN="$STAGE/demo-skill"; mkclean "$CLEAN"
out="$(python3 "$VERIFY" "$CLEAN" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ]; then ok "clean package exits 0"; else bad "clean package exits $rc (expected 0)"; fi
if echo "$out" | grep -q "0 error(s), 0 warning(s)"; then
  ok "clean package: 0 error, 0 warn"
else
  bad "clean package not silent: $(echo "$out" | tail -2 | tr '\n' ' ')"
fi

# helper: copy clean, apply a mutation via a shell snippet, return dir
mut() { local n="$1"; local d="$STAGE/$n"; mkclean "$d"; echo "$d"; }

echo
echo "[V01/V02] structure"
d=$(mut m01); rm "$d/SKILL.md";                                   fires "$d" V01 "no SKILL.md"
d=$(mut m02); sed -i.bak 's/^name: demo-skill/name: Demo_Skill/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V02 "name not kebab-case"
not_fires "$CLEAN" V02 "clean name is kebab-case"
d=$(mut m02b); sed -i.bak 's/^name: demo-skill/name: other-name/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V02b "frontmatter name != dir name"

echo
echo "[V03/V04/V05] pointers, platforms, self-containment"
d=$(mut m03); sed -i.bak 's#params/soc-x.md#params/soc-z.md#' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V03 "pointer to missing params file"
not_fires "$CLEAN" V03 "clean pointers resolve"
d=$(mut m04); cp "$d/params/soc-x.md" "$d/params/soc-y.md";       fires "$d" V04 "params file not in 已支持平台"
d=$(mut m05); echo "x" > "$d/params/soc-x.md.bak";                fires "$d" V05 "editor/build leftover shipped in package"
d=$(mut m05j); touch "$d/.DS_Store";                              fires "$d" V05 "OS junk shipped in package"
d=$(mut m05s); mkdir -p "$d/scripts"; echo "#!/bin/sh" > "$d/scripts/check.sh"; echo "x" > "$d/notes.txt"
                                                              not_fires "$d" V05 "scripts and plain data files are fine (framework demands executable checks)"
d=$(mut m05b); printf '\n[out](../elsewhere/x.md)\n' >> "$d/SKILL.md"
                                                                  fires "$d" V05b "link points outside the package"

echo
echo "[V06/V07/V08/V09] provenance fields"
d=$(mut m06); python3 - "$d" <<'PY'
import sys,re,io
p=sys.argv[1]+"/SKILL.md"; s=open(p).read()
s=re.sub(r"- 复现记录:\n(  - .*\n)+","",s)
open(p,"w").write(s)
PY
                                                                  fires "$d" V06 "复现记录 field removed"
not_fires "$CLEAN" V06 "clean has all five fields"
d=$(mut m06b); sed -i.bak '/^- 验证方式:/d' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V06b "验证方式 field absent"
not_fires "$CLEAN" V06b "clean declares 验证方式"
d=$(mut m07); sed -i.bak 's/^- 提炼日期:2026-09-02/- 提炼日期:最近/' "$d/SKILL.md"
              sed -i.bak 's/^- 来源:commit 1a2b3c4d/- 来源:近期会话/' "$d/SKILL.md"
              sed -i.bak 's/ · 实测:通过 2026-09-01/ · 未实测/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V07 "relative date instead of YYYY-MM-DD"
not_fires "$CLEAN" V07 "clean uses absolute dates"
d=$(mut m08); sed -i.bak 's/^- 来源:commit 1a2b3c4d/- 来源:前面说过的那次/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V08 "untraceable source"
not_fires "$CLEAN" V08 "clean source is traceable"
d=$(mut m09); sed -i.bak 's/^- 置信度:high/- 置信度:很高/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V09 "confidence value not high/med/low"
d=$(mut m09b); printf '\n- 某条切面(置信 high):做法 A。\n' >> "$d/SKILL.md"
                                                                  fires "$d" V09b "inline 置信 high with no provenance record"
not_fires "$CLEAN" V09b "clean makes no bare confidence claim"

echo
echo "[V10/V11/V12] mechanical confidence table"
d=$(mut m10); sed -i.bak 's/ · 实测:通过 2026-09-01/ · 未实测/g' "$d/params/soc-x.md"; rm -f "$d/params"/*.bak
                                                                  fires "$d" V10 "L3 high but never tested"
not_fires "$CLEAN" V10 "clean high is earned (tested + 2 platforms)"
d=$(mut m11); sed -i.bak 's/^- 置信度:high/- 置信度:low/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V11 "human downgrade reported as INFO"
if python3 "$VERIFY" "$d" >/dev/null 2>&1; then ok "V11 downgrade does not fail the run (人审可下调)"
else bad "V11 downgrade wrongly turned into a failure"; fi
d=$(mut m12); python3 - "$d" <<'PY'
import sys,re
p=sys.argv[1]+"/pitfalls.md"; s=open(p).read()
s=s.replace("    - proj-a · 2026-09-01 · commit 5e6f7a8b\n","")   # single platform L2, still 'verified'
open(p,"w").write(s)
PY
                                                                  fires "$d" V12 "single-platform L2 may not be high even when tested"
not_fires "$CLEAN" V12 "clean L2 has two distinct platforms"

echo
echo "[V14/V16/V17] reproduction records"
d=$(mut m14); python3 - "$d" <<'PY'
import sys,re
p=sys.argv[1]+"/SKILL.md"; s=open(p).read()
s=re.sub(r"- 复现记录:\n(  - .*\n)+","- 复现记录:2 次\n",s)
open(p,"w").write(s)
PY
                                                                  fires "$d" V14 "复现记录 written as a bare count"
not_fires "$CLEAN" V14 "clean 复现记录 is a list"
d=$(mut m16); sed -i.bak 's/  - proj-a · 2026-09-01/  - soc-x · 2026-09-01/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V16 "same platform twice = gaming the gate"
not_fires "$CLEAN" V16 "clean keys are distinct"
d=$(mut m17); sed -i.bak 's/  - proj-a · 2026-09-01/  - SOC_X · 2026-09-01/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V17 "same key spelled differently"

echo
echo "[V19/V20/V21/V22] layering discipline"
d=$(mut m19); sed -i.bak 's/^- 先读回再比对.*/- 先读回再比对,地址是 0x1A40。/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V19 "concrete value in SKILL.md body"
not_fires "$CLEAN" V19 "clean body carries no concrete values"
d=$(mut m19x); sed -i.bak 's/^- 先读回再比对.*/- 先读回再比对,地址是 0x1A40。<!-- l3-ok: 举例说明格式 -->/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                              not_fires "$d" V19 "l3-ok exemption honoured"
d=$(mut m20); sed -i.bak '/^- 涉及事实:/d' "$d/pitfalls.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V20 "pitfall not split into L2+L3"
d=$(mut m20n); sed -i.bak 's#^- 涉及事实:.*#- 涉及事实:无(纯方法层)#' "$d/pitfalls.md"; rm -f "$d"/*.bak
                                                              not_fires "$d" V20 "explicit 无(纯方法层) accepted"
not_fires "$CLEAN" V20 "clean pitfall points at params/"
d=$(mut m21); sed -i.bak 's#| `SLOT_A` |#| `SLOT_A` 之所以选这个位置,是因为早期版本把另一个位置占掉了,所以只能退到这里来,后面也没有再改回去 |#' "$d/params/soc-x.md"; rm -f "$d/params"/*.bak
                                                                  fires "$d" V21 "why-prose inside a params cell"
d=$(mut m22); sed -i.bak '/^## 替代记录/,$d' "$d/params/soc-x.md"; rm -f "$d/params"/*.bak
                                                                  fires "$d" V22 "params without 替代记录 section"
not_fires "$CLEAN" V22 "clean params has 替代记录"

echo
echo "[V23/V24] runtime neutrality"
d=$(mut m23); printf '\n装到 ~/.claude/skills/ 下面。\n' >> "$d/SKILL.md"
                                                                  fires "$d" V23 "runtime-specific install path"
d=$(mut m23b); printf '\n在 Claude Code 里跑这一步。\n' >> "$d/SKILL.md"
                                                                  fires "$d" V23b "binds to a single runtime"
d=$(mut m23x); printf '\n在 Claude Code 里跑这一步。<!-- runtime-ok: 举例 -->\n' >> "$d/SKILL.md"
                                                              not_fires "$d" V23b "runtime-ok exemption honoured"
d=$(mut m24); printf '\n参见 /home/someone/work/notes.md。\n' >> "$d/SKILL.md"
                                                                  fires "$d" V24 "absolute user path"
not_fires "$CLEAN" V24 "clean uses relative paths"

echo
echo "[V06c/V07b/V08b/V13b/V15/V18/V20b/V20c] checks the first pass left untested"
d=$(mut m06c); rm -f "$d/pitfalls.md" "$d/params/soc-x.md"
              python3 - "$d" <<'PY'
import sys,re
p=sys.argv[1]+"/SKILL.md"; s=open(p).read()
open(p,"w").write(s[:s.index("## 溯源")])          # a package with no provenance anywhere
PY
                                                                  fires "$d" V06c "package carries no provenance at all"
not_fires "$CLEAN" V06c "clean package has provenance"
d=$(mut m07b); sed -i.bak 's/^- 来源:commit 1a2b3c4d/- 来源:commit 1a2b3c4d(最近那次调试)/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V07b "relative time word beside a valid absolute date"
not_fires "$CLEAN" V07b "clean date fields carry no relative words"
d=$(mut m08b); sed -i.bak 's/^- 来源:commit 1a2b3c4d/- 来源:一份调试笔记/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V08b "source without a commit or session marker"
not_fires "$CLEAN" V08b "clean source names a commit"
d=$(mut m13b); sed -i.bak 's# · 实测:通过 2026-09-01##' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V13b "验证方式 states no test result either way"
not_fires "$CLEAN" V13b "clean states 实测:通过 explicitly"
d=$(mut m15); sed -i.bak 's#  - proj-a · 2026-09-01 · commit 5e6f7a8b#  - proj-a 2026-09-01 commit 5e6f7a8b#' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V15 "reproduction line without the · separator"
not_fires "$CLEAN" V15 "clean reproduction lines are separated"
fires "$CLEAN" V18 "two distinct platforms reported as promotable (INFO)"
not_fires "$STAGE/m12" V18 "single-platform entry is not reported promotable"
d=$(mut m20b); sed -i.bak 's#^- 涉及事实:.*#- 涉及事实:见上文那一段#' "$d/pitfalls.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V20b "涉及事实 neither points at params/ nor declares 无"
not_fires "$CLEAN" V20b "clean 涉及事实 points at params/"
d=$(mut m20c); sed -i.bak 's#params/soc-x.md#params/soc-z.md#' "$d/pitfalls.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V20c "涉及事实 points at a missing params file"
not_fires "$CLEAN" V20c "clean 涉及事实 target exists"

echo
echo "[V06d/V06e/V09c] per-entry provenance and confidence spelling"
d=$(mut m06d); python3 - "$d" <<'PY'
import sys
p=sys.argv[1]+"/pitfalls.md"; s=open(p).read()
open(p,"w").write(s[:s.index("- 溯源:")])        # a pitfall entry with no provenance
PY
                                                                  fires "$d" V06d "pitfall entry carries no provenance"
not_fires "$CLEAN" V06d "clean pitfall entry carries provenance"
d=$(mut m06e); python3 - "$d" <<'PY'
import sys,re
p=sys.argv[1]+"/params/soc-x.md"; s=open(p).read()
s=s.replace(" 复现记录 | 置信度 |"," |").replace("|---|---|---|---|---|---|","|---|---|---|---|")
s=re.sub(r"\| 2026-08-01 · commit 1a2b3c4d; 2026-09-01 · commit 5e6f7a8b \| high \|","|",s)
open(p,"w").write(s)
PY
                                                                  fires "$d" V06e "params fact table without a 置信度 column"
not_fires "$CLEAN" V06e "clean params table has a 置信度 column"
d=$(mut m09c); sed -i.bak 's/^- 置信度:high/- 置信度:medium/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V09c "置信度 spelled medium"
not_fires "$CLEAN" V09c "clean spells it med/high/low"

echo
echo "[bypass] the ways the audit found to slip past the promotion gate"
d=$(mut b1); sed -i.bak 's#  - proj-a · 2026-09-01 · commit 5e6f7a8b#  - soc-x 2026-09-01 commit 5e6f7a8b#' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V15 "dropping the separator must not buy a second platform"
if python3 "$VERIFY" "$d" >/dev/null 2>&1; then
  bad "separator-less reproduction line still exits 0 — the gate is bypassable"
else ok "separator-less reproduction line fails the run"; fi
d=$(mut b2); sed -i.bak 's#| 2026-08-01 · commit 1a2b3c4d; 2026-09-01 · commit 5e6f7a8b |#| 2026-08-01 · commit 1a2b3c4d; 2026-08-01 · commit 1a2b3c4d |#' "$d/params/soc-x.md"; rm -f "$d/params"/*.bak
                                                                  fires "$d" V16 "two identical L3 lines are one event, not two"
d=$(mut b3); mkdir -p "$d/scripts"; printf '#!/bin/sh\ncd /home/someone/work && cp x ~/.claude/skills/\n' > "$d/scripts/check.sh"
                                                                  fires "$d" V24 "absolute user path inside scripts/ is still a violation"
if has "$d" V23; then ok "V23 fires — runtime path inside scripts/"; else bad "V23 missed a runtime path inside scripts/"; fi
d=$(mut b4); sed -i.bak 's/^- 提炼日期:2026-09-02/- 提炼日期:最近那次/' "$d/SKILL.md"; rm -f "$d"/*.bak
                                                                  fires "$d" V07 "a tested-on date elsewhere must not rescue a relative 提炼日期"

echo
echo "[quiet] checks that had only a positive test"
not_fires "$CLEAN" V01  "clean has SKILL.md with name+description"
not_fires "$CLEAN" V02b "clean frontmatter name matches its directory"
not_fires "$CLEAN" V04  "clean lists every params platform"
not_fires "$CLEAN" V05  "clean ships no build/OS junk"
not_fires "$CLEAN" V05b "clean links stay inside the package"
not_fires "$CLEAN" V09  "clean confidence value parses"
not_fires "$CLEAN" V11  "clean confidence is not a downgrade"
not_fires "$CLEAN" V17  "clean platform keys are spelled one way"
not_fires "$CLEAN" V21  "clean params cells hold values, not prose"
not_fires "$CLEAN" V23  "clean has no runtime-specific install path"
not_fires "$CLEAN" V23b "clean binds to no single runtime"

echo
echo "[cli] exit codes and output modes"
python3 "$VERIFY" "$STAGE/m22" >/dev/null 2>&1
[ $? -eq 0 ] && ok "warn-only package exits 0 without --strict" || bad "warn-only package should exit 0"
python3 "$VERIFY" "$STAGE/m22" --strict >/dev/null 2>&1
[ $? -eq 1 ] && ok "warn-only package exits 1 with --strict" || bad "--strict should exit 1 on warnings"
python3 "$VERIFY" "$STAGE/m01" >/dev/null 2>&1
[ $? -eq 1 ] && ok "error package exits 1" || bad "error package should exit 1"
python3 "$VERIFY" --explain >/dev/null 2>&1
[ $? -eq 0 ] && ok "--explain exits 0" || bad "--explain should exit 0"
python3 "$VERIFY" >/dev/null 2>&1
[ $? -eq 2 ] && ok "no target exits 2" || bad "no target should exit 2"
python3 "$VERIFY" --src "$STAGE/nope" >/dev/null 2>&1
[ $? -eq 2 ] && ok "missing --src exits 2" || bad "missing --src should exit 2"
if python3 "$VERIFY" "$CLEAN" --json 2>/dev/null | python3 -c 'import json,sys;json.load(sys.stdin)'; then
  ok "--json emits valid JSON"
else bad "--json output is not valid JSON"; fi
n=$(python3 "$VERIFY" --src "$STAGE" --json 2>/dev/null | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["packages"]))')
[ "${n:-0}" -gt 10 ] && ok "--src walks a whole library ($n packages)" || bad "--src found only ${n:-0} packages"

echo
echo "[coverage] every published check code must have BOTH directions"
python3 - "$0" "$VERIFY" > "$STAGE/coverage.txt" <<'PY'
import re, subprocess, sys
script = open(sys.argv[1], encoding="utf-8").read()
explain = subprocess.run([sys.executable, sys.argv[2], "--explain"],
                         capture_output=True, text=True).stdout
published = set(re.findall(r"^\s+(V[0-9a-z]+)\s", explain, re.M))
pos, neg = set(), set()
for kind, code in re.findall(r"(?:^|\s)(not_fires|fires)\s+\"[^\"]+\"\s+(V[0-9a-z]+)", script, re.M):
    (neg if kind == "not_fires" else pos).add(code)
for c in sorted(published - pos):
    print(f"BAD|{c} has no positive test (nothing proves it can fire)")
for c in sorted(published - neg):
    print(f"BAD|{c} has no negative test (nothing proves it can stay quiet)")
for c in sorted((pos | neg) - published):
    print(f"BAD|{c} is asserted here but is not a real check code — the assertion is vacuous")
print(f"OK|{len(published)} codes published, {len(pos & published)} with a positive test, "
      f"{len(neg & published)} with a negative test")
PY
# read from a file, not a pipe: a pipeline puts the loop in a subshell and the
# fail counter increments there are lost — the coverage failures would print but
# not affect the exit code
while IFS= read -r line; do
  case "$line" in
    BAD\|*) bad "coverage: ${line#BAD|}" ;;
    OK\|*)  ok  "coverage: ${line#OK|}" ;;
  esac
done < "$STAGE/coverage.txt"

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1

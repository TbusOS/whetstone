#!/usr/bin/env bash
# Selftest for whetstone-autoupdate. Runs the real scripts against isolated
# fixtures under the repo (.autoupdate-selftest): fake HOME + fake remote/clone
# git repos. Never touches the live ~/.claude, ~/.config, or any real repo.
# Covers the review-pinned failure paths: merge-only behind commits, repos files
# without trailing newline, quoted paths, trailing-slash dedup, skipped-repo
# reporting, broken skill symlinks, bad settings.json (no fake success), flat
# legacy hook entries, takeover refusal, join-mode uninstall preservation.
# Exit 0 = all pass.
#
#   bash autoupdate/selftest.sh

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
# 环境隔离:这些覆盖开关若从外部带进来,脚本会写到真配置(评审 M6)
unset WSUP_HOME WSUP_REPOS GIT_DIR GIT_WORK_TREE CDPATH
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGE="$REPO_DIR/.autoupdate-selftest"
CHECK="$SCRIPT_DIR/hooks/check-update.sh"
DOUP="$SCRIPT_DIR/bin/do-update.sh"
INSTALL="$SCRIPT_DIR/install.sh"

FAKEHOME="$STAGE/home"          # own-mode / do-update 用
FAKEHOME2="$STAGE/home2"        # join-mode 用
FAKEHOME3="$STAGE/home3"        # takeover 用
FAKEHOME4="$STAGE/home4"        # 坏 JSON 用
CONF="$FAKEHOME/.config/whetstone-autoupdate"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok  - $1"; }
bad() { fail=$((fail+1)); echo "  FAIL- $1"; }

G() { git -c user.name=selftest -c user.email=selftest@local "$@"; }

# ---- fixtures ------------------------------------------------------------
rm -rf "$STAGE"
mkdir -p "$FAKEHOME/.claude/skills" "$FAKEHOME/.config" \
         "$FAKEHOME2/.claude" "$FAKEHOME2/.config" \
         "$FAKEHOME3/.claude" "$FAKEHOME3/.config" \
         "$FAKEHOME4/.claude" "$FAKEHOME4/.config"

G init -q --bare -b main "$STAGE/remote.git"
G clone -q "$STAGE/remote.git" "$STAGE/seed" 2>/dev/null
echo one > "$STAGE/seed/f.txt"
G -C "$STAGE/seed" add f.txt && G -C "$STAGE/seed" commit -qm "c1: first"
G -C "$STAGE/seed" push -q origin main
G clone -q "$STAGE/remote.git" "$STAGE/watched" 2>/dev/null
echo two >> "$STAGE/seed/f.txt"
G -C "$STAGE/seed" commit -qam "c2: second"
G -C "$STAGE/seed" push -q origin main

mkdir -p "$CONF/cache"
printf '%s\n' "$STAGE/watched" > "$CONF/repos"

# ---- 1) check-update --report:落后 1 -------------------------------------
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "watched: 落后 1 个提交" && ok "report shows behind=1" || bad "report: $out"
echo "$out" | grep -q "c2: second" && ok "report lists commit title" || bad "report missing title"

# ---- 2) hook 模式:落后时注入 JSON + 注入防护文案 ---------------------------
out="$(HOME="$FAKEHOME" bash "$CHECK" --event SessionStart)"
echo "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1 \
  && ok "hook mode emits additionalContext JSON" || bad "hook JSON: $out"
echo "$out" | grep -q "do-update.sh" && ok "hook context carries do-update path" || bad "no do-update path"
echo "$out" | grep -q "仅供展示" && ok "hook context carries injection caution" || bad "no injection caution"

# ---- 3) union 读取 + 尾斜杠去重 ---------------------------------------------
G clone -q "$STAGE/remote.git" "$STAGE/watched2" 2>/dev/null
mkdir -p "$FAKEHOME/.config/sky-skills-autoupdate"
printf '%s\n%s\n' "$STAGE/watched2" "$STAGE/watched/" > "$FAKEHOME/.config/sky-skills-autoupdate/repos"
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "watched2:" && ok "union-read sees sibling-config repo" || bad "union-read: $out"
n="$(echo "$out" | grep -c '^watched:')"
[ "$n" = "1" ] && ok "trailing-slash duplicate deduped" || bad "watched listed $n times"

# ---- 4) repos 文件缺末尾换行:不丢仓、不粘行 --------------------------------
printf '%s' "$STAGE/watched" > "$CONF/repos"       # 无换行结尾
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "^watched:" && echo "$out" | grep -q "^watched2:" \
  && ok "no-trailing-newline repos still fully read" || bad "newline handling: $out"
printf '%s\n' "$STAGE/watched" > "$CONF/repos"     # 恢复

# ---- 5) 含引号/空格的路径不被吞 ---------------------------------------------
mkdir -p "$STAGE/q dir"
G clone -q "$STAGE/remote.git" "$STAGE/q dir/it's repo" 2>/dev/null
printf '%s\n' "$STAGE/q dir/it's repo" >> "$CONF/repos"
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -Fq "it's repo:" && ok "path with quote+space survives" || bad "quoted path lost: $out"
printf '%s\n' "$STAGE/watched" > "$CONF/repos"     # 恢复

# ---- 6) 跳过的仓在 report 里显式出现 ----------------------------------------
printf '%s\n' "$STAGE/gone-missing" >> "$CONF/repos"
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "gone-missing: 跳过" && ok "missing repo reported as skipped" || bad "skip not reported: $out"
printf '%s\n' "$STAGE/watched" > "$CONF/repos"     # 恢复

# ---- 7) do-update:dirty 跳过 ------------------------------------------------
echo local-change >> "$STAGE/watched/f.txt"
out="$(HOME="$FAKEHOME" bash "$DOUP")"
echo "$out" | grep -q "本地有未提交改动" && ok "do-update skips dirty repo" || bad "dirty skip: $out"
G -C "$STAGE/watched" checkout -q -- f.txt

# ---- 8) behind 全是 merge 提交:不炸、不静默、后续仓照常处理 ------------------
G -C "$STAGE/watched" pull -q --ff-only          # 先拉平,让 merge 提交成为唯一 delta
tree="$(G -C "$STAGE/seed" rev-parse 'HEAD^{tree}')"
old="$(G -C "$STAGE/seed" rev-parse HEAD~1)"
m="$(G -C "$STAGE/seed" commit-tree "$tree" -p "$(G -C "$STAGE/seed" rev-parse HEAD)" -p "$old" -m "merge: only")"
G -C "$STAGE/seed" update-ref refs/heads/main "$m"
G -C "$STAGE/seed" push -q origin main
printf '%s\n%s\n' "$STAGE/watched" "$STAGE/watched2" > "$CONF/repos"
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "watched: 落后 1 个提交" && ok "merge-only behind detected (no crash)" || bad "merge-only: $out"
echo "$out" | grep -q "均为 merge 提交" && ok "merge-only gets placeholder title" || bad "no placeholder: $out"
echo "$out" | grep -q "watched2:" && ok "loop survives past merge-only repo" || bad "later repos dropped"

# ---- 9) do-update:拉更新 + 新 skill symlink + 断链提示 + 重启提示 ------------
mkdir -p "$STAGE/seed/skills/newskill" "$STAGE/seed/skills/brokenskill" "$STAGE/seed/commands"
printf -- "---\nname: newskill\ndescription: selftest fixture\n---\n" > "$STAGE/seed/skills/newskill/SKILL.md"
printf -- "---\nname: brokenskill\ndescription: selftest fixture\n---\n" > "$STAGE/seed/skills/brokenskill/SKILL.md"
echo x > "$STAGE/seed/commands/foo.md"
G -C "$STAGE/seed" add -A && G -C "$STAGE/seed" commit -qm "c3: add skills + command"
G -C "$STAGE/seed" push -q origin main
ln -s /nonexistent/target "$FAKEHOME/.claude/skills/brokenskill"   # 预置断链
out="$(HOME="$FAKEHOME" bash "$DOUP")"
echo "$out" | grep -q "【watched】已更新" && ok "do-update pulls behind repo" || bad "pull: $out"
[ "$(G -C "$STAGE/watched" rev-list --count 'HEAD..@{u}')" = "0" ] && ok "watched now up to date" || bad "still behind"
[ -L "$FAKEHOME/.claude/skills/newskill" ] && ok "new skill symlinked into fake ~/.claude/skills" || bad "no symlink"
echo "$out" | grep -q "断链 symlink" && ok "broken symlink reported, not silently skipped" || bad "broken link silent: $out"
echo "$out" | grep -q "请重启" && ok "restart hint on SKILL.md/commands change" || bad "no restart hint: $out"

# ---- 10) hook 模式:全部最新时静默 -------------------------------------------
HOME="$FAKEHOME" bash "$DOUP" >/dev/null
out="$(HOME="$FAKEHOME" bash "$CHECK" --event SessionStart)"
[ -z "$out" ] && ok "hook mode silent when up to date" || bad "not silent: $out"

# ---- 11) install own 模式 + 幂等 + fragment 路径替换 --------------------------
rm -rf "$FAKEHOME/.config/sky-skills-autoupdate"   # 清掉兄弟配置,逼出 own 模式
out="$(HOME="$FAKEHOME" bash "$INSTALL" install)"
echo "$out" | grep -q "own 模式" && ok "install picks own mode (no sibling)" || bad "mode: $out"
SJ="$FAKEHOME/.claude/settings.json"
n="$(jq '[.hooks.SessionStart[]?.hooks[]?.command | select(test("autoupdate/hooks/session-start"))] | length' "$SJ")"
[ "$n" = "1" ] && ok "SessionStart hook merged" || bad "SessionStart entries = $n"
HOME="$FAKEHOME" bash "$INSTALL" install >/dev/null
n="$(jq '[.hooks.SessionStart[]?.hooks[]?.command | select(test("autoupdate/hooks/session-start"))] | length' "$SJ")"
[ "$n" = "1" ] && ok "install is idempotent (still 1 entry)" || bad "after rerun entries = $n"
c="$(grep -c "BEGIN: whetstone-autoupdate" "$FAKEHOME/.claude/CLAUDE.md")"
[ "$c" = "1" ] && ok "CLAUDE.md fragment inserted once" || bad "fragment count = $c"
grep -qF "$REPO_DIR/cli/whetstone autoupdate check" "$FAKEHOME/.claude/CLAUDE.md" \
  && ok "fragment {{CLONE}} substituted with real path" || bad "fragment placeholder not substituted"
grep -qxF "$REPO_DIR" "$CONF/repos" && ok "repos seeded with this clone" || bad "clone not in repos"

# ---- 12) 坏 JSON:不假报成功、不留临时文件、不改原文件 -------------------------
printf 'not json' > "$FAKEHOME4/.claude/settings.json"
out="$(HOME="$FAKEHOME4" bash "$INSTALL" install)"; rc=$?
echo "$out" | grep -q "部分失败" && [ "$rc" != "0" ] \
  && ok "bad JSON → reported failure, nonzero exit" || bad "fake success on bad JSON (rc=$rc): $out"
[ "$(cat "$FAKEHOME4/.claude/settings.json")" = "not json" ] && ok "bad JSON file left untouched" || bad "bad JSON file modified"
find "$FAKEHOME4/.claude" -name ".wsup.*" | grep -q . && bad "temp .wsup.* left behind" || ok "no temp files left behind"

# ---- 13) install join 模式 ----------------------------------------------------
mkdir -p "$FAKEHOME2/.config/sky-skills-autoupdate"
printf '# sibling\n/some/other/repo\n' > "$FAKEHOME2/.config/sky-skills-autoupdate/repos"
jq -n '{hooks:{SessionStart:[{hooks:[{type:"command",command:"bash \"/x/other/autoupdate/hooks/session-start.sh\""}]}]}}' \
  > "$FAKEHOME2/.claude/settings.json"
out="$(HOME="$FAKEHOME2" bash "$INSTALL" install)"
echo "$out" | grep -q "join 模式" && ok "install picks join mode (sibling hook present)" || bad "join: $out"
grep -qxF "$REPO_DIR" "$FAKEHOME2/.config/sky-skills-autoupdate/repos" \
  && ok "clone registered into sibling repos" || bad "clone not registered"
grep -qF "$REPO_DIR/autoupdate" "$FAKEHOME2/.claude/settings.json" \
  && bad "join mode must not add own hook" || ok "join mode adds no second hook"

# ---- 14) 有兄弟 hook 但无它的 repos:拒绝静默接管;--takeover 才接管(含扁平旧格式) ----
jq -n '{hooks:{SessionStart:[{type:"command",command:"bash \"/x/other/autoupdate/hooks/session-start.sh\""}]}}' \
  > "$FAKEHOME3/.claude/settings.json"     # 扁平旧格式的兄弟 entry
out="$(HOME="$FAKEHOME3" bash "$INSTALL" install)"; rc=$?
[ "$rc" = "4" ] && echo "$out" | grep -q "takeover" \
  && ok "foreign hook w/o repos → refuses, asks for --takeover" || bad "no refusal (rc=$rc): $out"
grep -qF "/x/other/autoupdate" "$FAKEHOME3/.claude/settings.json" \
  && ok "foreign hook untouched on refusal" || bad "foreign hook clobbered on refusal"
out="$(HOME="$FAKEHOME3" bash "$INSTALL" install --takeover)"
echo "$out" | grep -q "takeover" && ok "--takeover proceeds" || bad "takeover: $out"
grep -qF "/x/other/autoupdate" "$FAKEHOME3/.claude/settings.json" \
  && bad "flat foreign entry not stripped on takeover" || ok "takeover strips flat foreign entry too"
n="$(jq '[.hooks.SessionStart[]?.hooks[]?.command | select(test("autoupdate/hooks/session-start"))] | length' "$FAKEHOME3/.claude/settings.json")"
[ "$n" = "1" ] && ok "takeover leaves exactly one hook" || bad "takeover entries = $n"

# ---- 15) uninstall(own):hook / fragment / repos 全摘 -------------------------
HOME="$FAKEHOME" bash "$INSTALL" uninstall >/dev/null
n="$(jq '[.hooks.SessionStart[]?.hooks[]?.command | select(test("autoupdate/hooks/session-start"))] | length' "$SJ")"
[ "$n" = "0" ] && ok "uninstall removes hook" || bad "hook still there ($n)"
grep -q "BEGIN: whetstone-autoupdate" "$FAKEHOME/.claude/CLAUDE.md" \
  && bad "fragment still in CLAUDE.md" || ok "uninstall removes CLAUDE.md fragment"
grep -qxF "$REPO_DIR" "$CONF/repos" && bad "clone still in repos" || ok "uninstall removes clone from repos"

# ---- 16) uninstall(join):不误伤兄弟工具 --------------------------------------
before_md5="$(md5 -q "$FAKEHOME2/.claude/settings.json" 2>/dev/null || md5sum "$FAKEHOME2/.claude/settings.json" | cut -d' ' -f1)"
HOME="$FAKEHOME2" bash "$INSTALL" uninstall >/dev/null
after_md5="$(md5 -q "$FAKEHOME2/.claude/settings.json" 2>/dev/null || md5sum "$FAKEHOME2/.claude/settings.json" | cut -d' ' -f1)"
[ "$before_md5" = "$after_md5" ] && ok "join uninstall leaves sibling settings.json untouched" || bad "sibling settings changed"
grep -qF "/some/other/repo" "$FAKEHOME2/.config/sky-skills-autoupdate/repos" \
  && ok "sibling's own repos entries preserved" || bad "sibling repos entry lost"
grep -qxF "$REPO_DIR" "$FAKEHOME2/.config/sky-skills-autoupdate/repos" \
  && bad "our clone still in sibling repos" || ok "our clone removed from sibling repos"

echo
echo "passed $pass, failed $fail"
[ "$fail" = "0" ]

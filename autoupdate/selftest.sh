#!/usr/bin/env bash
# Selftest for whetstone-autoupdate. Runs the real scripts against isolated
# fixtures under the repo (.autoupdate-selftest): fake HOME + fake remote/clone
# git repos. Never touches the live ~/.claude, ~/.config, or any real repo.
# Exercises: check-update report/hook/silent, union-read of sibling repos
# configs, do-update pull + dirty-skip + new-skill symlink + restart hint,
# install own/join mode + idempotency, uninstall. Exit 0 = all pass.
#
#   bash autoupdate/selftest.sh

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGE="$REPO_DIR/.autoupdate-selftest"
CHECK="$SCRIPT_DIR/hooks/check-update.sh"
DOUP="$SCRIPT_DIR/bin/do-update.sh"
INSTALL="$SCRIPT_DIR/install.sh"

FAKEHOME="$STAGE/home"          # own-mode / do-update 用
FAKEHOME2="$STAGE/home2"        # join-mode 用
CONF="$FAKEHOME/.config/whetstone-autoupdate"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok  - $1"; }
bad() { fail=$((fail+1)); echo "  FAIL- $1"; }

G() { git -c user.name=selftest -c user.email=selftest@local "$@"; }

# ---- fixtures ------------------------------------------------------------
rm -rf "$STAGE"
mkdir -p "$FAKEHOME/.claude/skills" "$FAKEHOME/.config" "$FAKEHOME2/.claude" "$FAKEHOME2/.config"

G init -q --bare -b main "$STAGE/remote.git"
G clone -q "$STAGE/remote.git" "$STAGE/seed" 2>/dev/null
echo one > "$STAGE/seed/f.txt"
G -C "$STAGE/seed" add f.txt && G -C "$STAGE/seed" commit -qm "c1: first"
G -C "$STAGE/seed" push -q origin main
G clone -q "$STAGE/remote.git" "$STAGE/watched" 2>/dev/null
# 远端再进一个提交,让 watched 落后 1
echo two >> "$STAGE/seed/f.txt"
G -C "$STAGE/seed" commit -qam "c2: second"
G -C "$STAGE/seed" push -q origin main

mkdir -p "$CONF/cache"
printf '%s\n' "$STAGE/watched" > "$CONF/repos"

# ---- 1) check-update --report:落后 1 -------------------------------------
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "watched: 落后 1 个提交" && ok "report shows behind=1" || bad "report: $out"
echo "$out" | grep -q "c2: second" && ok "report lists commit title" || bad "report missing title"

# ---- 2) hook 模式:落后时注入 JSON ----------------------------------------
out="$(HOME="$FAKEHOME" bash "$CHECK" --event SessionStart)"
echo "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1 \
  && ok "hook mode emits additionalContext JSON" || bad "hook JSON: $out"
echo "$out" | grep -q "do-update.sh" && ok "hook context carries do-update path" || bad "no do-update path"

# ---- 3) union 读取:仓只登记在兄弟工具的 repos 里也能被看到 ----------------
G clone -q "$STAGE/remote.git" "$STAGE/watched2" 2>/dev/null
mkdir -p "$FAKEHOME/.config/sky-skills-autoupdate"
printf '%s\n' "$STAGE/watched2" > "$FAKEHOME/.config/sky-skills-autoupdate/repos"
out="$(HOME="$FAKEHOME" bash "$CHECK" --report)"
echo "$out" | grep -q "watched2:" && ok "union-read sees sibling-config repo" || bad "union-read: $out"

# ---- 4) do-update:dirty 跳过 ----------------------------------------------
echo local-change >> "$STAGE/watched/f.txt"
out="$(HOME="$FAKEHOME" bash "$DOUP")"
echo "$out" | grep -q "本地有未提交改动" && ok "do-update skips dirty repo" || bad "dirty skip: $out"
G -C "$STAGE/watched" checkout -q -- f.txt

# ---- 5) do-update:拉更新 + 新 skill symlink + 重启提示 ---------------------
mkdir -p "$STAGE/seed/skills/newskill" "$STAGE/seed/commands"
printf -- "---\nname: newskill\ndescription: selftest fixture\n---\n" > "$STAGE/seed/skills/newskill/SKILL.md"
echo x > "$STAGE/seed/commands/foo.md"
G -C "$STAGE/seed" add -A && G -C "$STAGE/seed" commit -qm "c3: add skill + command"
G -C "$STAGE/seed" push -q origin main
out="$(HOME="$FAKEHOME" bash "$DOUP")"
echo "$out" | grep -q "【watched】已更新" && ok "do-update pulls behind repo" || bad "pull: $out"
[ "$(G -C "$STAGE/watched" rev-list --count 'HEAD..@{u}')" = "0" ] && ok "watched now up to date" || bad "still behind"
[ -L "$FAKEHOME/.claude/skills/newskill" ] && ok "new skill symlinked into fake ~/.claude/skills" || bad "no symlink"
echo "$out" | grep -q "请重启" && ok "restart hint on SKILL.md/commands change" || bad "no restart hint: $out"

# ---- 6) hook 模式:全部最新时静默 ------------------------------------------
HOME="$FAKEHOME" bash "$DOUP" >/dev/null   # watched2 也拉平
out="$(HOME="$FAKEHOME" bash "$CHECK" --event SessionStart)"
[ -z "$out" ] && ok "hook mode silent when up to date" || bad "not silent: $out"

# ---- 7) install own 模式 + 幂等 --------------------------------------------
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
grep -qxF "$REPO_DIR" "$CONF/repos" && ok "repos seeded with this clone" || bad "clone not in repos"

# ---- 8) install join 模式 ---------------------------------------------------
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

# ---- 9) uninstall -----------------------------------------------------------
out="$(HOME="$FAKEHOME" bash "$INSTALL" uninstall)"
n="$(jq '[.hooks.SessionStart[]?.hooks[]?.command | select(test("autoupdate/hooks/session-start"))] | length' "$SJ")"
[ "$n" = "0" ] && ok "uninstall removes hook" || bad "hook still there ($n)"
grep -q "BEGIN: whetstone-autoupdate" "$FAKEHOME/.claude/CLAUDE.md" \
  && bad "fragment still in CLAUDE.md" || ok "uninstall removes CLAUDE.md fragment"
grep -qxF "$REPO_DIR" "$CONF/repos" && bad "clone still in repos" || ok "uninstall removes clone from repos"

echo
echo "passed $pass, failed $fail"
[ "$fail" = "0" ]

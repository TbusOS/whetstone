#!/usr/bin/env bash
# install.sh — 装/升级/卸载 whetstone 自动更新提示器(多 CLI:Claude Code / Codex / Gemini CLI)。
#
#   install   (默认) 见下面的两种模式;播种 repos
#   upgrade   同 install,但保留已有 repos 配置
#   uninstall 反向移除(本工具的 hook、CLAUDE.md 段;并把本 clone 从各 repos 配置里摘掉)
#   --dry-run 只打印将做什么,不动文件(可与上面任意子命令组合)
#
# 两种安装模式(自动判断):
#   join 模式  本机已有兼容的 autoupdate hook(如 sky-skills-autoupdate)且其 repos 配置存在
#              → 只把本 clone 登记进已有配置,不再挂第二套 hook(避免双重 fetch / 双重提示)。
#   own 模式   本机没有兼容 hook → 完整安装:hook 接进各 CLI 配置 + CLAUDE.md 规则段 + 播种 repos。
#
# 兼容协议:凡把被监控仓列表放 ~/.config/<name>-autoupdate/repos、hook 入口叫
# autoupdate/hooks/{session-start,prompt-submit,before-agent}.sh 的工具互认。
# check-update / do-update 读所有这类 repos 文件的 union,所以谁的 hook 活着都能看到全部仓。
#
# 幂等:重复跑不重复接入(按 hook 脚本路径精确剔除旧 entry)。改配置前自动备份 .bak。
# 不锁 PATH:可分发工具,用使用者环境的 git/jq。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"        # <clone>/autoupdate
CLONE="$(cd "$SCRIPT_DIR/.." && pwd)"              # <clone>
CONF_DIR="${WSUP_HOME:-$HOME/.config/whetstone-autoupdate}"
REPOS="${WSUP_REPOS:-$CONF_DIR/repos}"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
FRAGMENT="$SCRIPT_DIR/claude-md-fragment.md"
MARK_BEGIN="<!-- BEGIN: whetstone-autoupdate v1 -->"
MARK_END="<!-- END: whetstone-autoupdate v1 -->"

SS_CMD="bash \"$SCRIPT_DIR/hooks/session-start.sh\""
UPS_CMD="bash \"$SCRIPT_DIR/hooks/prompt-submit.sh\""
BA_CMD="bash \"$SCRIPT_DIR/hooks/before-agent.sh\""
# 兼容 autoupdate hook 的通用路径特征(merge 时按它做接管式剔除)
STRIP_RE="autoupdate/hooks/(session-start|prompt-submit|before-agent)"

CMD="install"; DRY=0
for a in "$@"; do
  case "$a" in
    install|upgrade|uninstall) CMD="$a" ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "缺少依赖: $1" >&2; exit 3; }; }
need git

backup()      { [ -f "$1" ] || return 0; if [ "$DRY" = 1 ]; then say "  [dry-run] cp $1 $1.bak"; else cp "$1" "$1.bak"; fi; }
ensure_json() { [ -f "$1" ] && return 0; if [ "$DRY" = 1 ]; then say "  [dry-run] 新建 $1 = {}"; else mkdir -p "$(dirname "$1")"; printf '{}' > "$1"; fi; }

# ---- 兼容工具探测 --------------------------------------------------------

CLI_CONFS="$HOME/.claude/settings.json
$HOME/.codex/hooks.json
$HOME/.gemini/settings.json"

# 本机是否已有「不属于本 clone」的兼容 autoupdate hook
has_foreign_hook() {
  local f
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    grep -E "$STRIP_RE" "$f" 2>/dev/null | grep -vF "$SCRIPT_DIR" | grep -q . && return 0
  done <<< "$CLI_CONFS"
  return 1
}

# 列出本机其他兼容工具的 repos 配置文件(不含自己的)
foreign_repos_files() {
  local f
  for f in "$HOME/.config/"*-autoupdate/repos; do
    [ -f "$f" ] || continue
    [ "$f" = "$REPOS" ] && continue
    printf '%s\n' "$f"
  done
}

# repos 文件里是否已有某仓(忽略注释/空白)
repos_has() {   # <file> <path>
  local line repo
  while IFS= read -r line; do
    repo="${line%%#*}"; repo="$(printf '%s' "$repo" | xargs 2>/dev/null)"
    [ "$repo" = "$2" ] && return 0
  done < "$1"
  return 1
}

# ---- hook merge(jq,接管式幂等) -----------------------------------------

merge_one_hook() {   # <file> <event> <command>
  local file="$1" ev="$2" cmd="$3"
  if [ "$DRY" = 1 ]; then say "  [dry-run] $file ← hooks.$ev += $cmd"; return; fi
  ensure_json "$file"
  local tmp; tmp="$(mktemp "${file%/*}/.wsup.XXXXXX")"
  jq --arg ev "$ev" --arg cmd "$cmd" --arg re "$STRIP_RE" '
    .hooks = (.hooks // {})
    | .hooks[$ev] = ((((.hooks[$ev]) // [])
        | map(select((.hooks // []) | map(.command) | any(test($re)) | not)))
        + [{hooks:[{type:"command", command:$cmd}]}])
  ' "$file" > "$tmp" && mv "$tmp" "$file"
}

unmerge_hooks() {    # <file> <event...>  只摘「属于本 clone」的 entry,不动兄弟工具的
  local file="$1"; shift
  [ -f "$file" ] || return 0
  command -v jq >/dev/null 2>&1 || { say "  (缺 jq,跳过 $file 的 hook 摘除)"; return 0; }
  backup "$file"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 从 $file 摘掉本工具 hook"; return; fi
  for ev in "$@"; do
    local tmp; tmp="$(mktemp "${file%/*}/.wsup.XXXXXX")"
    jq --arg ev "$ev" --arg p "$SCRIPT_DIR" '
      if (.hooks[$ev]?) then .hooks[$ev] = ((.hooks[$ev]) | map(select((.hooks // []) | map(.command) | any(contains($p)) | not))) else . end
    ' "$file" > "$tmp" && mv "$tmp" "$file"
  done
}

install_claude() { local f="$HOME/.claude/settings.json"; say "  [Claude Code] $f"; backup "$f"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" UserPromptSubmit "$UPS_CMD"; }
install_codex()  { local f="$HOME/.codex/hooks.json";    say "  [Codex] $f";       backup "$f"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" UserPromptSubmit "$UPS_CMD"; }
install_gemini() { local f="$HOME/.gemini/settings.json"; say "  [Gemini CLI] $f";  backup "$f"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" BeforeAgent "$BA_CMD"; }

write_claude_md() {
  backup "$CLAUDE_MD"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 在 ~/.claude/CLAUDE.md 插/更新规则段"; return; fi
  touch "$CLAUDE_MD"
  awk -v b="$MARK_BEGIN" -v e="$MARK_END" '$0==b{skip=1} skip&&$0==e{skip=0; next} !skip' "$CLAUDE_MD" > "$CLAUDE_MD.tmp" && mv "$CLAUDE_MD.tmp" "$CLAUDE_MD"
  printf '\n' >> "$CLAUDE_MD"; cat "$FRAGMENT" >> "$CLAUDE_MD"
}
remove_claude_md() {
  [ -f "$CLAUDE_MD" ] || return 0; backup "$CLAUDE_MD"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 从 CLAUDE.md 删规则段"; return; fi
  awk -v b="$MARK_BEGIN" -v e="$MARK_END" '$0==b{skip=1} skip&&$0==e{skip=0; next} !skip' "$CLAUDE_MD" > "$CLAUDE_MD.tmp" && mv "$CLAUDE_MD.tmp" "$CLAUDE_MD"
}

seed_repos() {
  if [ -f "$REPOS" ]; then
    if repos_has "$REPOS" "$CLONE"; then say "  repos 已存在且含本 clone,保留: $REPOS"
    else
      if [ "$DRY" = 1 ]; then say "  [dry-run] $REPOS += $CLONE"; else printf '%s\n' "$CLONE" >> "$REPOS"; fi
      say "  repos 已存在,补登记本 clone: $REPOS"
    fi
    return
  fi
  if [ "$DRY" = 1 ]; then say "  [dry-run] 播种 $REPOS(写入 $CLONE + 探测到的 skill 仓)"; return; fi
  mkdir -p "$CONF_DIR/cache"; cp "$SCRIPT_DIR/repos.txt.template" "$REPOS"
  {
    echo "$CLONE"
    for s in "$HOME"/.claude/skills/*; do
      [ -L "$s" ] || continue
      tgt="$(readlink -f "$s" 2>/dev/null)" || continue
      git -C "$tgt" rev-parse --show-toplevel 2>/dev/null || true
    done
  } | sort -u >> "$REPOS"
}

# 把本 clone 登记进(或摘出)兄弟工具的 repos 配置
join_foreign() {
  local f joined=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if repos_has "$f" "$CLONE"; then
      say "  已登记,跳过: $f"
    else
      if [ "$DRY" = 1 ]; then say "  [dry-run] $f += $CLONE"; else printf '%s\n' "$CLONE" >> "$f"; fi
      say "  登记本 clone → $f"
    fi
    joined=1
  done <<< "$(foreign_repos_files)"
  return $((1 - joined))
}
leave_all_repos() {
  local f
  { printf '%s\n' "$REPOS"; foreign_repos_files; } | while IFS= read -r f; do
    [ -f "$f" ] || continue
    grep -qxF "$CLONE" "$f" || continue
    if [ "$DRY" = 1 ]; then say "  [dry-run] 从 $f 摘掉 $CLONE"; else
      backup "$f"
      grep -vxF "$CLONE" "$f" > "$f.tmp"; mv "$f.tmp" "$f"
    fi
    say "  已从 $f 摘掉本 clone"
  done
}

case "$CMD" in
  install|upgrade)
    say "== whetstone-autoupdate $CMD =="
    say "clone: $CLONE"
    [ "$DRY" = 1 ] || chmod +x "$SCRIPT_DIR/hooks/"*.sh "$SCRIPT_DIR/bin/"*.sh
    if has_foreign_hook && [ -n "$(foreign_repos_files)" ]; then
      say "-- join 模式:本机已有兼容的 autoupdate hook,只登记本 clone,不再挂第二套 hook --"
      join_foreign
      say ""
      say "✓ 完成(join)。已有 hook 下个会话就会开始监控本仓。"
      say "  手动检查: $CLONE/cli/whetstone autoupdate check"
      exit 0
    fi
    need jq
    say "-- own 模式:完整安装 --"
    detected=0
    if [ -d "$HOME/.claude" ]; then install_claude; write_claude_md; detected=$((detected+1)); fi
    if [ -d "$HOME/.codex" ];  then install_codex;  detected=$((detected+1)); fi
    if [ -d "$HOME/.gemini" ]; then install_gemini; detected=$((detected+1)); fi
    if [ "$detected" = 0 ]; then
      say "⚠ 没探测到 ~/.claude、~/.codex、~/.gemini —— 没有可接入的 CLI。装好任一 CLI 后重跑本脚本。"
    fi
    seed_repos
    say ""
    say "✓ 完成,接入了 $detected 个 CLI。重启对应 CLI 让 hook 生效。"
    say "  手动检查: $CLONE/cli/whetstone autoupdate check"
    say "  通用脚本: bash $SCRIPT_DIR/hooks/check-update.sh --report"
    say "  配置(可加多仓): $REPOS"
    ;;
  uninstall)
    say "== whetstone-autoupdate uninstall =="
    unmerge_hooks "$HOME/.claude/settings.json" SessionStart UserPromptSubmit
    unmerge_hooks "$HOME/.codex/hooks.json"     SessionStart UserPromptSubmit
    unmerge_hooks "$HOME/.gemini/settings.json" SessionStart BeforeAgent
    remove_claude_md
    leave_all_repos
    say "  (本工具的配置目录保留: $CONF_DIR,如需一并删 rm -rf $CONF_DIR)"
    say "✓ 已卸载。重启对应 CLI 生效。"
    ;;
esac

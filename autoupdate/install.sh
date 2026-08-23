#!/usr/bin/env bash
# install.sh — 装/升级/卸载 whetstone 自动更新提示器(多 CLI:Claude Code / Codex / Gemini CLI)。
#
#   install    (默认) 见下面的模式说明;播种 repos
#   upgrade    同 install(两者都保留已有 repos 配置,是同义词,留两个名字只为语义清晰)
#   uninstall  反向移除(本工具的 hook、CLAUDE.md 段;并把本 clone 从各 repos 配置里摘掉)
#   --dry-run  只打印将做什么,不动文件(可与上面任意子命令组合)
#   --takeover 本机有兼容 hook 但没有它的 repos 配置(半残安装)时,明确授权接管
#              (接管 = 用本工具的 hook 替掉它的;不加此参数遇到这种情况会停下来问你)
#
# 安装模式(自动判断):
#   join 模式  本机已有兼容的 autoupdate hook(如 sky-skills-autoupdate)且其 repos 配置存在
#              → 只把本 clone 登记进已有配置,不再挂第二套 hook(避免双重 fetch / 双重提示)。
#   own 模式   本机没有兼容 hook → 完整安装:hook 接进各 CLI 配置 + CLAUDE.md 规则段 + 播种 repos。
#
# 兼容协议:凡把被监控仓列表放 ~/.config/<name>-autoupdate/repos、hook 入口叫
# autoupdate/hooks/{session-start,prompt-submit,before-agent}.sh 的工具互认。
#
# 幂等:重复跑不重复接入。merge 用「autoupdate hook 通用路径特征」做接管式剔除(own 模式
# 下本来就没有别家 hook,剔除的只是本工具旧 entry);uninstall 只摘含本 clone 路径的 entry,
# 不动别家的。改配置前备份 .bak(只备第一次,保住最初状态)。
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
# 兼容 autoupdate hook 的通用路径特征(merge 的接管式剔除用)
STRIP_RE="autoupdate/hooks/(session-start|prompt-submit|before-agent)"

CMD="install"; DRY=0; TAKEOVER=0; FAILED=0
for a in "$@"; do
  case "$a" in
    install|upgrade|uninstall) CMD="$a" ;;
    --dry-run)  DRY=1 ;;
    --takeover) TAKEOVER=1 ;;
    -h|--help)  sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "缺少依赖: $1" >&2; exit 3; }; }
need git

# 写目标若是 symlink(dotfiles 管理常见),解引用到真实文件再写,别把 symlink 换成普通文件
real_target() { if [ -L "$1" ]; then readlink -f "$1" 2>/dev/null || printf '%s' "$1"; else printf '%s' "$1"; fi; }
backup()      { [ -f "$1" ] || return 0; [ -f "$1.bak" ] && return 0
                if [ "$DRY" = 1 ]; then say "  [dry-run] cp $1 $1.bak"; else cp "$1" "$1.bak"; fi; }
ensure_json() { [ -f "$1" ] && return 0; if [ "$DRY" = 1 ]; then say "  [dry-run] 新建 $1 = {}"; else mkdir -p "$(dirname "$1")"; printf '{}' > "$1"; fi; }
# 追加一行前保证文件以换行结尾(缺末行换行会把两行粘成一行、或让 read 丢行)
append_line() { # <file> <line>
  if [ "$DRY" = 1 ]; then say "  [dry-run] $1 += $2"; return; fi
  [ -s "$1" ] && [ -n "$(tail -c1 "$1" 2>/dev/null)" ] && printf '\n' >> "$1"
  printf '%s\n' "$2" >> "$1"
}

# ---- 兼容工具探测 --------------------------------------------------------

CLI_CONFS="$HOME/.claude/settings.json
$HOME/.codex/hooks.json
$HOME/.gemini/settings.json"

# 列出配置文件里全部 hook command(jq 递归取,兼容压缩 JSON 与扁平旧格式;无 jq 退化为行 grep)
hook_commands() { # <file>
  if command -v jq >/dev/null 2>&1; then
    jq -r '[.. | .command? // empty] | .[]' "$1" 2>/dev/null
  else
    cat "$1" 2>/dev/null
  fi
}

# 本机是否已有「不属于本 clone」的兼容 autoupdate hook
has_foreign_hook() {
  local f
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    hook_commands "$f" | grep -E "$STRIP_RE" | grep -vF "$SCRIPT_DIR" | grep -q . && return 0
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

# repos 文件里是否已有某仓(忽略注释/空白;|| [ -n ] 兜住缺末行换行的最后一行)
repos_has() {   # <file> <path>
  local line repo
  while IFS= read -r line || [ -n "$line" ]; do
    repo="${line%%#*}"
    repo="${repo#"${repo%%[![:space:]]*}"}"; repo="${repo%"${repo##*[![:space:]]}"}"
    [ "${repo%/}" = "${2%/}" ] && return 0
  done < "$1"
  return 1
}

# ---- hook merge(jq,接管式幂等;失败绝不假报成功) -------------------------

merge_one_hook() {   # <file> <event> <command>
  local file ev="$2" cmd="$3" tmp
  file="$(real_target "$1")"
  if [ "$DRY" = 1 ]; then say "  [dry-run] $file ← hooks.$ev += $cmd"; return; fi
  ensure_json "$file"
  if ! jq -e . "$file" >/dev/null 2>&1; then
    say "  ! $file 不是合法 JSON,已跳过(未改动)"; FAILED=1; return
  fi
  tmp="$(mktemp "${file%/*}/.wsup.XXXXXX")" || { say "  ! 无法创建临时文件($file)"; FAILED=1; return; }
  # 剔除条件同时看嵌套 entry({hooks:[{command}]})和扁平旧格式({command}),null 免疫
  if jq --arg ev "$ev" --arg cmd "$cmd" --arg re "$STRIP_RE" '
       .hooks = (.hooks // {})
       | .hooks[$ev] = ((((.hooks[$ev]) // [])
           | map(select(
               ((((.hooks // []) | map(.command? // "")) + [(.command? // "")])
                | any(test($re))) | not)))
           + [{hooks:[{type:"command", command:$cmd}]}])
     ' "$file" > "$tmp" 2>/dev/null; then
    mv "$tmp" "$file"
  else
    rm -f "$tmp"; say "  ! jq 处理 $file 失败,未改动"; FAILED=1
  fi
}

unmerge_hooks() {    # <file> <event...>  只摘「属于本 clone」的 entry,不动兄弟工具的
  local file; file="$(real_target "$1")"; shift
  [ -f "$file" ] || return 0
  grep -qF "$SCRIPT_DIR" "$file" 2>/dev/null || return 0   # 没装过就别动它(也别留 .bak)
  command -v jq >/dev/null 2>&1 || { say "  ! 缺 jq,无法从 $file 摘 hook(请手动删含 $SCRIPT_DIR 的 entry)"; FAILED=1; return 0; }
  backup "$file"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 从 $file 摘掉本工具 hook"; return; fi
  local ev tmp
  for ev in "$@"; do
    tmp="$(mktemp "${file%/*}/.wsup.XXXXXX")" || { FAILED=1; continue; }
    if jq --arg ev "$ev" --arg p "$SCRIPT_DIR" '
         if (.hooks[$ev]?) then
           .hooks[$ev] = ((.hooks[$ev]) | map(select(
             ((((.hooks // []) | map(.command? // "")) + [(.command? // "")])
              | any(contains($p))) | not)))
         else . end
       ' "$file" > "$tmp" 2>/dev/null; then
      mv "$tmp" "$file"
    else
      rm -f "$tmp"; say "  ! jq 处理 $file 失败,未改动"; FAILED=1
    fi
  done
}

install_claude() { local f="$HOME/.claude/settings.json"; say "  [Claude Code] $f"; backup "$(real_target "$f")"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" UserPromptSubmit "$UPS_CMD"; }
install_codex()  { local f="$HOME/.codex/hooks.json";    say "  [Codex] $f";       backup "$(real_target "$f")"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" UserPromptSubmit "$UPS_CMD"; }
install_gemini() { local f="$HOME/.gemini/settings.json"; say "  [Gemini CLI] $f";  backup "$(real_target "$f")"
  merge_one_hook "$f" SessionStart "$SS_CMD"; merge_one_hook "$f" BeforeAgent "$BA_CMD"; }

write_claude_md() {
  local md; md="$(real_target "$CLAUDE_MD")"
  backup "$md"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 在 ~/.claude/CLAUDE.md 插/更新规则段"; return; fi
  touch "$md"
  awk -v b="$MARK_BEGIN" -v e="$MARK_END" '$0==b{skip=1} skip&&$0==e{skip=0; next} !skip' "$md" > "$md.tmp" && mv "$md.tmp" "$md"
  [ -s "$md" ] && [ -n "$(tail -c1 "$md")" ] && printf '\n' >> "$md"
  printf '\n' >> "$md"
  sed "s|{{CLONE}}|$CLONE|g" "$FRAGMENT" >> "$md"
}
remove_claude_md() {
  local md; md="$(real_target "$CLAUDE_MD")"
  [ -f "$md" ] || return 0
  grep -qF "$MARK_BEGIN" "$md" 2>/dev/null || return 0   # 没插过就别动它
  backup "$md"
  if [ "$DRY" = 1 ]; then say "  [dry-run] 从 CLAUDE.md 删规则段"; return; fi
  awk -v b="$MARK_BEGIN" -v e="$MARK_END" '$0==b{skip=1} skip&&$0==e{skip=0; next} !skip' "$md" > "$md.tmp" && mv "$md.tmp" "$md"
}

seed_repos() {
  if [ -f "$REPOS" ]; then
    if repos_has "$REPOS" "$CLONE"; then say "  repos 已存在且含本 clone,保留: $REPOS"
    else append_line "$REPOS" "$CLONE"; say "  repos 已存在,补登记本 clone: $REPOS"; fi
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

# 把本 clone 登记进兄弟工具的 repos 配置(join 模式);打印实际生效的配置路径
join_foreign() {
  local f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if repos_has "$f" "$CLONE"; then
      say "  已登记,跳过: $f"
    else
      append_line "$f" "$CLONE"
      say "  登记本 clone → $f"
    fi
    say "  (这是实际生效的监控配置——join 模式下想加别的仓,加进这个文件)"
  done <<< "$(foreign_repos_files)"
}
leave_all_repos() {
  local f
  { printf '%s\n' "$REPOS"; foreign_repos_files; } | while IFS= read -r f; do
    [ -f "$f" ] || continue
    grep -qF "$CLONE" "$f" || continue
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
    if has_foreign_hook; then
      if [ -n "$(foreign_repos_files)" ]; then
        say "-- join 模式:本机已有兼容的 autoupdate hook,只登记本 clone,不再挂第二套 hook --"
        join_foreign
        say ""
        say "✓ 完成(join)。已有 hook 下个会话就会开始监控本仓。"
        say "  手动检查: $CLONE/cli/whetstone autoupdate check"
        exit 0
      elif [ "$TAKEOVER" = 0 ]; then
        say "⚠ 发现别家 autoupdate hook,但找不到它的 repos 配置(~/.config/*-autoupdate/repos)。"
        say "  为避免静默替换掉它,本次不安装。二选一:"
        say "  - 修好那套工具(重跑它的 install)后再跑本脚本 → 走 join 模式;"
        say "  - 确认要用本工具接管:重跑并加 --takeover(会用本工具的 hook 替掉它的)。"
        exit 4
      else
        say "-- takeover:按 --takeover 授权,用本工具的 hook 替换已有的兼容 hook --"
      fi
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
    if [ "$FAILED" = 1 ]; then
      say "✗ 部分失败(见上面的 ! 行)——未成功的文件保持原样,修复后重跑即可。"
      exit 5
    fi
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
    if [ "$FAILED" = 1 ]; then say "✗ 部分失败(见上面的 ! 行)。"; exit 5; fi
    say "✓ 已卸载。重启对应 CLI 生效。"
    ;;
esac

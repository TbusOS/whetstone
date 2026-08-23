#!/usr/bin/env bash
# check-update.sh — whetstone 自动更新检测器(只读)。
#
# 对被监控 repos 列表里的每个 git 仓:节流 fetch + 比对本地与远端(@{u}),落后就报告。
# repos 列表取「union」:本工具自己的配置 + 本机其他兼容 autoupdate 的配置
# (~/.config/*-autoupdate/repos,如 sky-skills-autoupdate)——不管本机活着的是
# 哪家的 hook,手动检查都能看到全部被监控仓。
#
# 两种模式:
#   (默认 hook 模式) 落后时输出 {"hookSpecificOutput":{...,"additionalContext":...}},
#                    让 agent 主动提示用户;无更新则静默(不打扰)。
#   --report         人类可读地打印各仓状态(给 `whetstone autoupdate check` 手动用)。
#
# 绝不改仓库:只 fetch + 比对。实际更新由 bin/do-update.sh 在用户确认后执行。
# 不锁 PATH:这是可分发工具,要用使用者环境里的 git/jq。
# timeout 可选(macOS 默认没有):有就限 5 秒,没有就裸跑 fetch。

set -uo pipefail

CONF_DIR="${WSUP_HOME:-$HOME/.config/whetstone-autoupdate}"
REPOS_FILE="${WSUP_REPOS:-$CONF_DIR/repos}"
CACHE_DIR="$CONF_DIR/cache"

# do-update.sh 的真实路径(脚本自身在 clone/autoupdate/hooks/,更新器在 ../bin/),
# 任何 CLI 看到提示都能照这个绝对路径跑。
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
DO_UPDATE="$(cd "$SELF_DIR/../bin" 2>/dev/null && pwd)/do-update.sh"

EVENT="UserPromptSubmit"
MODE="hook"
THROTTLE=1800   # 秒;hook 入口会按事件覆盖

while [ $# -gt 0 ]; do
  case "$1" in
    --event)    EVENT="$2"; shift 2 ;;
    --throttle) THROTTLE="$2"; shift 2 ;;
    --report)   MODE="report"; shift ;;
    *)          shift ;;
  esac
done

# union 收集被监控仓:自己的 repos + 兄弟工具的 repos,去行内注释/空白,去重保序
collect_repos() {
  {
    [ -f "$REPOS_FILE" ] && cat "$REPOS_FILE"
    for f in "$HOME/.config/"*-autoupdate/repos; do
      [ -f "$f" ] || continue
      [ "$f" = "$REPOS_FILE" ] && continue
      cat "$f"
    done
  } 2>/dev/null | while IFS= read -r line; do
      repo="${line%%#*}"
      repo="$(printf '%s' "$repo" | xargs 2>/dev/null)"
      [ -n "$repo" ] && printf '%s\n' "$repo"
    done | awk '!seen[$0]++'
}

fetch_repo() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 5 git -C "$1" fetch --quiet 2>/dev/null
  else
    git -C "$1" fetch --quiet 2>/dev/null
  fi
}

repos="$(collect_repos)"
if [ -z "$repos" ]; then
  [ "$MODE" = "report" ] && echo "没有被监控的仓库(先跑 autoupdate/install.sh;配置:$REPOS_FILE)"
  exit 0
fi
mkdir -p "$CACHE_DIR" 2>/dev/null || true

emit_hook=""
emit_report=""

while IFS= read -r repo; do
  [ -d "$repo/.git" ] || continue
  name="$(basename "$repo")"

  # 节流 fetch(report 模式总是刷新)
  hash="$(printf '%s' "$repo" | cksum | cut -d' ' -f1)"
  stamp="$CACHE_DIR/$hash.lastfetch"
  now="$(date +%s 2>/dev/null || echo 0)"
  last=0; [ -f "$stamp" ] && last="$(cat "$stamp" 2>/dev/null || echo 0)"
  if [ "$MODE" = "report" ] || [ $((now - last)) -ge "$THROTTLE" ]; then
    if fetch_repo "$repo"; then
      printf '%s' "$now" > "$stamp" 2>/dev/null || true
    fi
  fi

  # 需要有 upstream 才比对
  git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1 || continue
  behind="$(git -C "$repo" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)"
  case "$behind" in ''|*[!0-9]*) behind=0 ;; esac

  if [ "$behind" -gt 0 ]; then
    titles="$(git -C "$repo" log --no-merges --format='· %s' 'HEAD..@{u}' 2>/dev/null | head -8)"
    shown="$(printf '%s\n' "$titles" | grep -c '·' || echo 0)"
    more=$((behind - shown))
    [ "$more" -gt 0 ] && titles="$titles
· …及另 $more 条"
    emit_hook="${emit_hook}【${name}】远端领先 ${behind} 个提交：
${titles}
"
    emit_report="${emit_report}${name}: 落后 ${behind} 个提交
${titles}

"
  else
    emit_report="${emit_report}${name}: 已是最新

"
  fi
done <<< "$repos"

if [ "$MODE" = "report" ]; then
  printf '%s' "${emit_report:-(repos 列表为空：$REPOS_FILE)}"
  exit 0
fi

# hook 模式：只有有更新才注入提示
[ -z "$emit_hook" ] && exit 0

ctx="检测到被监控仓库远端有更新(whetstone-autoupdate）：
${emit_hook}
请先简洁告诉用户更新了哪些内容，再问是否现在更新。用户确认后运行：
  bash \"$DO_UPDATE\"
(它做 git pull --ff-only + 给新 skill 补 symlink；若涉及 hook / SKILL.md / commands 变更，提醒用户重启当前 CLI。)"

if command -v jq >/dev/null 2>&1; then
  jq -n --arg ev "$EVENT" --arg ctx "$ctx" \
    '{hookSpecificOutput:{hookEventName:$ev, additionalContext:$ctx}}'
fi
exit 0

#!/usr/bin/env bash
# do-update.sh — 用户确认后执行更新(会改仓库)。
#
# 对被监控列表(union:自己的 repos + 本机其他 *-autoupdate 的 repos;注意 union 是
# whetstone 脚本的行为,兄弟工具的脚本只读它自己的配置)里每个落后的仓:
#   1) 工作树不干净 → 跳过(不强 pull,避免冲突)
#   2) git pull --ff-only(只快进;分叉/网络失败分别如实报告,不混淆)
#   3) 给 clone/skills/ 下的新 skill 目录在 ~/.claude/skills/ 补 symlink
#      (whetstone 这类「SKILL.md 在仓库根、整仓即一个 skill」的布局无需此步)
#   4) 报告拉到的提交;涉及 hook / SKILL.md / commands 变更则提示重启 CLI
#
# 不锁 PATH:可分发工具,用使用者环境的 git。fetch 防阻塞同 check-update.sh。

set -uo pipefail

CONF_DIR="${WSUP_HOME:-$HOME/.config/whetstone-autoupdate}"
REPOS_FILE="${WSUP_REPOS:-$CONF_DIR/repos}"
SKILLS_DIR="$HOME/.claude/skills"   # 新 skill 补 symlink 仅对 Claude Code 有意义

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }

collect_repos() {
  {
    [ -f "$REPOS_FILE" ] && awk 1 "$REPOS_FILE"
    for f in "$HOME/.config/"*-autoupdate/repos; do
      [ -f "$f" ] || continue
      [ "$f" = "$REPOS_FILE" ] && continue
      awk 1 "$f"
    done
  } 2>/dev/null | while IFS= read -r line; do
      repo="$(trim "${line%%#*}")"
      repo="${repo%/}"
      [ -n "$repo" ] && printf '%s\n' "$repo"
    done | awk '!seen[$0]++'
}

fetch_repo() {
  local -a g=(git -C "$1" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=8 fetch --quiet)
  if command -v timeout >/dev/null 2>&1; then
    timeout 8 "${g[@]}" </dev/null 2>/dev/null
  else
    GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -oBatchMode=yes -oConnectTimeout=5' \
      "${g[@]}" </dev/null 2>/dev/null
  fi
}

repos="$(collect_repos)"
[ -n "$repos" ] || { echo "没有被监控的仓库(先跑 autoupdate/install.sh;配置:$REPOS_FILE)"; exit 1; }

restart_needed=0

while IFS= read -r repo; do
  [ -d "$repo/.git" ] || { echo "跳过(不存在或非 git 仓)：$repo"; continue; }
  name="$(basename "$repo")"

  if [ -n "$(git -C "$repo" status --porcelain 2>/dev/null)" ]; then
    echo "【${name}】本地有未提交改动，已跳过——请先处理：cd \"$repo\" && git status"
    continue
  fi

  git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1 \
    || { echo "【${name}】没有 upstream，跳过"; continue; }

  # 先 fetch 拿最新远端状态;失败要记住——之后 pull 失败时报网络而不是误报分叉
  fetch_ok=1
  fetch_repo "$repo" || fetch_ok=0
  behind="$(git -C "$repo" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)"
  case "$behind" in ''|*[!0-9]*) behind=0 ;; esac
  if [ "$behind" -eq 0 ]; then
    if [ "$fetch_ok" -eq 1 ]; then echo "【${name}】已是最新"
    else echo "【${name}】fetch 失败(网络?),按上次已知远端状态无更新"; fi
    continue
  fi

  before="$(git -C "$repo" rev-parse HEAD)"
  if git -C "$repo" pull --ff-only --quiet 2>/dev/null; then
    echo "【${name}】已更新 ${behind} 个提交："
    git -C "$repo" log --no-merges --format='  · %s' "${before}..HEAD" 2>/dev/null | cut -c1-160 | head -20

    # 给新 skill 补 symlink(仅当本机装了 Claude Code,~/.claude 存在)
    if [ -d "$repo/skills" ] && [ -d "$HOME/.claude" ]; then
      for d in "$repo"/skills/*/; do
        [ -d "$d" ] || continue
        sn="$(basename "$d")"
        p="$SKILLS_DIR/$sn"
        if [ ! -e "$p" ] && [ ! -L "$p" ]; then
          mkdir -p "$SKILLS_DIR"
          if ln -s "${d%/}" "$p" 2>/dev/null; then
            echo "  + 新 skill 已链接：$sn"
            restart_needed=1
          else
            echo "  ! 链接失败：$sn → $p(请手动处理)"
          fi
        elif [ -L "$p" ] && [ ! -e "$p" ]; then
          echo "  ! 跳过 ${sn}(断链 symlink):${p} 请手动清理后重跑"
        fi
      done
    fi

    # 改了 hook / SKILL.md / commands → 需重启才完全生效
    # ((^|/) 兼容 whetstone 这类 SKILL.md 在仓库根的布局)
    if git -C "$repo" diff --name-only "${before}..HEAD" 2>/dev/null \
         | grep -qE "autoupdate/hooks/|(^|/)SKILL\.md$|(^|/)commands/"; then
      restart_needed=1
    fi
  else
    if [ "$fetch_ok" -eq 0 ]; then
      echo "【${name}】fetch 失败(网络不通?),本次跳过——恢复后重跑即可"
    else
      ahead="$(git -C "$repo" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
      case "$ahead" in ''|*[!0-9]*) ahead=0 ;; esac
      if [ "$ahead" -gt 0 ]; then
        echo "【${name}】本地与远端分叉(本地领先 $ahead 个提交)——请手动处理："
      else
        echo "【${name}】git pull --ff-only 失败——请手动处理："
      fi
      echo "         cd \"$repo\" && git status && git log --oneline -5"
    fi
  fi
done <<< "$repos"

if [ "$restart_needed" -eq 1 ]; then
  printf '\n⚠ 涉及新 skill 或 hook / SKILL.md / commands 变更，请重启对应 CLI 让其完全生效。\n'
fi
echo "完成。"

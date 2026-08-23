# whetstone-autoupdate

让你的 AI CLI 在 whetstone(或任何被监控仓)远端有更新时**主动提示你**,确认后**自动更新**——
不用每次自己想起来 `git pull`。支持 **Claude Code / Codex / Gemini CLI**。
与 sky-skills-autoupdate 同源同协议,两者装在同一台机器上不会互相打架(见「共存」)。

## 原理

这些 CLI 都不后台轮询,所以"自动提示"挂在它们的生命周期 hook 上。三家的 hook 机制
高度一致(都用 `hookSpecificOutput.additionalContext` 注入文本),所以核心是一份 **CLI 无关**的 shell:

- 会话期 hook(**SessionStart** 开会话;做事中:Claude/Codex 用 **UserPromptSubmit**、
  Gemini 用 **BeforeAgent**,节流 30 分钟)跑 `hooks/check-update.sh`:节流 `git fetch`
  + 比对本地与远端,**落后就注入提示**(远端领先几个提交、更新了什么),AI 就主动转告你、问要不要更新。
  **只读,绝不偷偷改仓库。**
- 你确认后,AI 跑 `bin/do-update.sh`:`git pull --ff-only` + 给 `skills/` 布局的仓补新 skill
  的 symlink,并报告更新了什么。whetstone 本身是「整仓即一个 skill」(SKILL.md 在仓库根,
  symlink 安装),pull 完文件即刻最新;只有 hook / SKILL.md / commands 变更要重启 CLI。

## 安装

```bash
cd <你的 whetstone clone>
bash autoupdate/install.sh            # 先看一眼:加 --dry-run
```

安装器自动二选一:

| 模式 | 触发条件 | 做什么 |
|---|---|---|
| **join** | 本机已有兼容的 autoupdate hook(如 sky-skills-autoupdate) | 只把本 clone 登记进已有的 repos 配置——不挂第二套 hook,避免双重 fetch / 双重提示 |
| **own** | 本机没有兼容 hook | 完整安装:探测已装的 CLI,把 hook 接进各自配置(jq 幂等 merge,先备份 `.bak`);往 `~/.claude/CLAUDE.md` 插行为规则段;播种 `~/.config/whetstone-autoupdate/repos` |

own 模式接入的配置:

| CLI | 配置文件 | 事件 |
|---|---|---|
| Claude Code | `~/.claude/settings.json` | SessionStart + UserPromptSubmit |
| Codex | `~/.codex/hooks.json` | SessionStart + UserPromptSubmit |
| Gemini CLI | `~/.gemini/settings.json` | SessionStart + BeforeAgent |

装完**重启对应 CLI** 生效。升级 / 卸载:`bash autoupdate/install.sh upgrade` / `uninstall`
(uninstall 会把本 clone 从所有 repos 配置里摘掉,包括 join 进去的)。

## 共存协议(与 sky-skills-autoupdate 等同族工具)

约定:被监控仓列表放 `~/.config/<name>-autoupdate/repos`(一行一个仓库根),hook 入口叫
`autoupdate/hooks/{session-start,prompt-submit,before-agent}.sh`。满足这两条的工具互认:

- `check-update.sh` / `do-update.sh` 读**所有** `~/.config/*-autoupdate/repos` 的 union——
  不管本机活着的是哪家的 hook,检测和更新都覆盖全部被监控仓。
- 安装时探测到别家 hook 就走 join 模式,全机永远只有一套 hook 在跑。

## 用法

- 自动:开会话或做事中,远端有更新时 AI 主动问你。
- 手动:`whetstone autoupdate check`(查状态)/ `whetstone autoupdate update`(更新);
  或直接跑 `bash autoupdate/hooks/check-update.sh --report` / `bash autoupdate/bin/do-update.sh`。
- 配多仓:编辑 `~/.config/whetstone-autoupdate/repos`,一行一个仓库根。
- 自测:`whetstone autoupdate selftest`(隔离夹具,不碰真配置、不碰真仓库)。

## 边界

- 离线 / 网络慢:fetch 失败即静默,不卡你(有 `timeout` 用 `timeout 5`;macOS 默认没有
  timeout,则裸跑 fetch——这是与 sky-skills 版的一个行为差异,那边没 timeout 会静默不 fetch)。
- 本地仓有改动或与远端分叉:do-update 跳过并提示,绝不强行 merge。
- 只跟当前分支的 upstream(`@{u}`),只快进(`--ff-only`)。
- **适用范围**:配置在用户级,所以本机这个用户**任何目录**开对应 CLI 都生效(与 cwd 无关);
  新 hook 需重启一次该 CLI 加载。

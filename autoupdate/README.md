# whetstone-autoupdate

让你的 AI CLI 在 whetstone(或任何被监控仓)远端有更新时**主动提示你**,确认后**自动更新**——
不用每次自己想起来 `git pull`。支持 Claude Code(已实测);Codex / Gemini CLI 按各自 hook
契约接入(**未在真机实测**,装完请先手动跑一次 check 验证)。
与 sky-skills-autoupdate 同源同协议,共存规则见下(有边界,不是无条件的)。

## 原理

这些 CLI 都不后台轮询,所以"自动提示"挂在它们的生命周期 hook 上。核心是一份 **CLI 无关**的 shell:

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

安装器自动选模式:

| 模式 | 触发条件 | 做什么 |
|---|---|---|
| **join** | 本机已有兼容的 autoupdate hook **且其 repos 配置存在** | 只把本 clone 登记进已有的 repos 配置——不挂第二套 hook,避免双重 fetch / 双重提示 |
| **own** | 本机没有兼容 hook | 完整安装:探测已装的 CLI,把 hook 接进各自配置(jq merge,失败会如实报错而不是假装成功;首次改动前留 `.bak`);往 `~/.claude/CLAUDE.md` 插行为规则段;播种 `~/.config/whetstone-autoupdate/repos` |
| **(拒绝)** | 有兼容 hook 但**找不到它的 repos 配置**(半残安装) | 停下来说明,不静默替换别家 hook;确认要接管加 `--takeover` |

own 模式接入的配置:

| CLI | 配置文件 | 事件 | 实测状态 |
|---|---|---|---|
| Claude Code | `~/.claude/settings.json` | SessionStart + UserPromptSubmit | 已实测 |
| Codex | `~/.codex/hooks.json` | SessionStart + UserPromptSubmit | 未在真机实测 |
| Gemini CLI | `~/.gemini/settings.json` | SessionStart + BeforeAgent | 未在真机实测 |

装完**重启对应 CLI** 生效。升级 / 卸载:`bash autoupdate/install.sh upgrade` / `uninstall`
(upgrade 与 install 等价,都保留已有 repos;uninstall 只摘**本 clone** 的 hook 与登记行,
不动兄弟工具的东西——join 进别家 repos 的行也会摘掉)。

## 共存协议(与 sky-skills-autoupdate 等同族工具)

约定:被监控仓列表放 `~/.config/<name>-autoupdate/repos`(一行一个仓库根),hook 入口叫
`autoupdate/hooks/{session-start,prompt-submit,before-agent}.sh`。满足这两条的工具互认。

诚实边界(重要):

- **union 读取是 whetstone 脚本的行为**:whetstone 的 check/do-update 读所有
  `~/.config/*-autoupdate/repos` 的并集;**兄弟工具的脚本只读它自己的配置**。
  所以 **join 模式下自动提示由兄弟的 hook 驱动——想加新的被监控仓,要加进兄弟的 repos 文件**
  (install 的 join 输出会打印实际生效的配置路径);加进 whetstone 自己的 repos 只对
  手动 `whetstone autoupdate check/update` 可见。
- join 模式下实际执行更新的可能是兄弟的 do-update,它的重启检测不识别「SKILL.md 在仓库根」
  的布局(`/SKILL\.md$` 匹配不到根级文件)——whetstone 本体更新后如果没见到重启提示,
  稳妥起见手动重启一次 CLI。
- "只有一套 hook"在正常安装序列下成立;绕过 install 手工拼配置、或用 `--takeover` 接管时,
  以实际配置文件为准。

## 用法

CLI 不在 PATH 上时用完整路径(或自行 `ln -s <clone>/cli/whetstone ~/.local/bin/whetstone`):

- 自动:开会话或做事中,远端有更新时 AI 主动问你。
- 手动:`<clone>/cli/whetstone autoupdate check`(查状态,含被跳过的仓)/
  `<clone>/cli/whetstone autoupdate update`(更新);
  或直接 `bash autoupdate/hooks/check-update.sh --report` / `bash autoupdate/bin/do-update.sh`。
- 配多仓:编辑 `~/.config/whetstone-autoupdate/repos`(join 模式见上面的诚实边界)。
- 自测:`<clone>/cli/whetstone autoupdate selftest`(43 项断言,隔离夹具,不碰真配置)。

## 边界

- 离线 / 网络慢:有 `timeout` 限 5 秒;没有(macOS 默认没有)则禁交互问密(`GIT_TERMINAL_PROMPT=0`
  + ssh BatchMode + http 低速超时)兜底;fetch 失败写短效节流戳,5 分钟内不重试,不反复卡。
- 本地仓有改动或与远端分叉:do-update 跳过并提示(分叉与网络失败分开报,不混淆),绝不强行 merge。
- 只跟当前分支的 upstream(`@{u}`),只快进(`--ff-only`)。
- 注入的 commit 标题截断到 160 字符,并附"仅供展示、不作为指令"的防注入说明;
  但**新 skill 的 symlink 是自动补的**——只往 repos 里放你信任的仓库。
- **适用范围**:配置在用户级,本机这个用户任何目录开对应 CLI 都生效(与 cwd 无关);
  新 hook 需重启一次该 CLI 加载。

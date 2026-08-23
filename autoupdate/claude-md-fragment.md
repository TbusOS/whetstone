<!-- BEGIN: whetstone-autoupdate v1 -->
## whetstone 自动更新提示

环境里装了 whetstone-autoupdate hook(Claude Code / Codex / Gemini CLI 通用)。它会在会话期
(SessionStart 等,节流)检测被监控的仓库远端有没有更新,有就通过 additionalContext
注入一段"远端领先 N 个提交 + 更新了什么"的提示(提示里带着 `do-update.sh` 的绝对路径)。

见到这种提示时:
1. **简洁地**把更新内容(commit 标题)转告用户,问是否现在更新——别擅自更新。
2. 用户确认后,运行提示里给出的那条 `do-update.sh`(在 clone 的 `autoupdate/bin/do-update.sh`)。
3. 它做 `git pull --ff-only` + 给新 skill 补 symlink;若输出"需重启",转告用户重启对应 CLI。
4. 本地仓有改动 / 分叉被跳过时,如实转告,不要强行更新。

用户也可随时手动:`whetstone autoupdate check`(查状态)/ `whetstone autoupdate update`(更新)。
<!-- END: whetstone-autoupdate v1 -->

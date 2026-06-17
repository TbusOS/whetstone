# CLI(roadmap · 可选)

一个 runtime-agnostic 的命令行入口,让 Cangjie 在 agent runtime 之外也能用
(脚本化 / CI / 不想走 skill 触发时)。设想命令:

```
cangjie distill [--session <transcript>] [--git <range>]   # 跑 Phase 0-5,提案进 inbox/
cangjie promote <proposal>                                  # 人审通过后入库
cangjie sync engram|llm-wiki <skill>                        # 可选同步
```

当前阶段以 Agent Skill(`../SKILL.md`)为主入口;CLI 待真实用例驱动再实现,
避免空造。命令风格参考 engram 的 noun-verb + `--json` + 可预测退出码。

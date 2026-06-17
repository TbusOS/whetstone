# Cangjie · 仓颉

> 把开发经验蒸馏成可移植的 Agent Skill。
> Distill engineering work into portable, runtime-neutral Agent Skills.

Cangjie 是一个**蒸馏工具**,不是单个 skill。做完一个功能后,它挖掘会话
(transcript + git diff + 踩坑),按作用域拆成 4 层,产出一个**自包含、跨 runtime 的 skill 包**——
你或别人(用 Claude Code / Codex / Cursor / 任何 skills-compatible runtime)把它拖进 skills 目录,
立刻具备这套能力。**越用,你的本地 skill 库越大、越准;换平台只换 L3 参数表,L1/L2 一起复用。**

## 三层边界

```
层1 · Cangjie 蒸馏器(本仓库,runtime 中立)
   extraction-framework(L1-L4 方法) · distiller 流程
   + adapters/capture/<runtime>   ← runtime 专属只隔离在这薄一层
   + adapters/sync/{engram,llm-wiki}  ← 可选下游,装了才用
        │ 产出
层2 · 可移植 skill 包(★给别人的交付物,见 spec/skill-package.md)
   SKILL.md(L1/L2) + params/<platform>.md(L3) + pitfalls.md
   纯 markdown · runtime 中立 · 自包含
        │ 可选
层3 · 下游 sink:engram(同步进记忆库) / llm-wiki(发成人看的页)
```

## 它产出什么(给别人的东西)

一个 skill 包目录,符合 Agent Skills 标准、runtime 中立、自包含。规范见
[`spec/skill-package.md`](spec/skill-package.md)。别人拖进自己 runtime 的 skills 目录就能用。

## 用法

1. 做完功能 → 触发蒸馏(把本仓库作为 Agent Skill 装进你的 runtime,说「蒸馏这次」/ `/distill`)。
2. 审提案(两道人审关:挖得对吗 / 入不入库)→ 入库。
3. (可选)自动采集 / 同步 engram / 发布 llm-wiki。

为什么必须人审:LLM 自评 skill 质量准确率仅约 46%(SkillLens),自动覆盖会让库越用越乱。

## 安装(任何 runtime)

Cangjie 自身就是一个 Agent Skill(`SKILL.md`)+ 参考资料。把整个目录放进你 runtime 的 skills 目录:

| Runtime | 放哪 |
|---|---|
| Claude Code | `~/.claude/skills/cangjie/` |
| Codex / Cursor / 其他 | 对应的 skills / rules 目录 |

- **零运行时依赖**:不装 engram、不装 darwin 也能跑。
- **自动采集(可选)**:见 [`adapters/capture/README.md`](adapters/capture/README.md)——runtime 专属只在这一层。

## 可选搭档(装了才用)

| 搭档 | 作用 | 文档 |
|---|---|---|
| engram | 把产出的 skill 包同步进本地记忆库(去重 / 衰减 / 召回) | [`adapters/sync/engram.md`](adapters/sync/engram.md) |
| llm-wiki | 把知识发成人看的 wiki 页 | [`adapters/sync/llm-wiki.md`](adapters/sync/llm-wiki.md) |
| darwin-skill(第三方) | 给单个 skill 打分 / 进化 | 见其仓库 |

## 目录

```
SKILL.md                          蒸馏器入口(Agent Skill,Phase 0-5)
references/extraction-framework.md  L1-L4 分层 schema(灵魂)
spec/skill-package.md             ★ 可移植 skill 包格式规范(交付物)
templates/                        产物骨架(skill-template / params-template)
commands/                         /distill · /promote(Claude Code 便捷别名)
adapters/capture/                 per-runtime 采集(claude-code.sh + 各 runtime 说明)
adapters/sync/                    可选下游(engram / llm-wiki)
cli/                              可选 runtime-agnostic CLI(roadmap)
inbox/                            提案暂存(运行时,不入库)
journal/                          原材料(运行时,不入库)
```

## 致谢 / 灵感

- 蒸馏流程架构借鉴 `nuwa-skill`、独立评判 + 棘轮纪律借鉴 `darwin-skill`(均为第三方开源)。
- 理论依据:EvolveR(轨迹蒸馏为策略)、AgentFactory(技能库生命周期)、
  MemoryBank(遗忘曲线)、SkillLens(skill 质量评估)。

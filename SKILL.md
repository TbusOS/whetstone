---
name: cangjie
description: "Distill a finished dev session into proposals for a self-growing local skill library. Mines the transcript + git diff + pitfalls, decomposes what was learned into 4 layers (L1 principle / L2 method+pitfall / L3 platform-params / L4 state) via references/extraction-framework.md, reconciles against existing skills (dedup / supersede / conflict), and writes a human-reviewed proposal into inbox/. Self-contained, zero runtime dependency. Trigger words: 蒸馏这次 / distill this session / 把这次经验做成 skill / 开发完记录经验 / capture what I learned. Use after finishing a feature or bugfix to capture the reusable part."
---

# Cangjie · 仓颉 — Distiller 提炼流程 (Session → Skill)

> 配套 `references/extraction-framework.md`(L1-L4 分层 schema)。本文件管「怎么从一坨会话里把 schema 套出来」。
> **Runtime 中立 + 零运行时依赖**:本文件是 Cangjie 蒸馏器的 Agent Skill 入口,任何 skills-compatible runtime(Claude Code / Codex / Cursor …)都能调。产物是可移植 skill 包(见 `spec/skill-package.md`)。engram(同步)/ llm-wiki(发布)/ darwin-skill(打分)均为**可选** sink,装不装都能跑。

把一次**已经发生**的开发会话(transcript + git diff + 踩坑),
按 extraction-framework 拆成 L1-L4,对账已有 skill 库,产出**提案**交人审,
人点头后才进库。

**和 nuwa 的根本区别:nuwa 去网上调研一个人;本流程是「会话事后挖掘」——素材已经在那,挖出信号、分层、对账、入库。**

---

## 核心原则(贯穿全程)

1. **挖掘,不创造** —— 只提炼会话里真实发生的工程学习,不脑补、不把 AI 自己的元对话当知识。
2. **diff 说 WHAT,transcript 说 WHY + 什么失败了** —— 最终 diff 抹掉了试错过程,坑和决策只在 transcript 里,两个都要挖。
3. **对账库存是命门** —— 大多数会话对应的 skill 已经存在,提炼的真正难点不是"写新的",是"和已有的合并/去重/替代",这也是库漂移的发生地。
4. **提案,不直写** —— 产物是对库的 diff,落 inbox 暂存;**人审 gate 后**才进正式库(SkillLens:LLM 判 skill 质量仅 46% 准,不许自动覆盖)。

---

## Phase 0 · 圈定范围

```
1. 确认要提炼哪次任务(刚做完的 feature)
2. 锁定素材:
   - 会话 transcript(哪段)
   - git 范围(commit 区间 / diff)
   - 踩坑 journal 条目(若 capture hook 攒了)
3. 判定领域:这次是关于什么?(安全启动 / 某驱动 bringup / SDK 迁移 …)
   → Phase 3 对账要用领域定位到对应 skill
4. 信号量筛(阈值):
   - 改了实质东西 / 踩了非平凡的坑 / 做了设计决策 → 继续
   - 纯 typo、纯机械改、零学习 → 不提炼,只往 journal 追加一行,结束
```

**🔴 失败分支:** 一次会话跨多个领域(同时碰了安全启动 + 一个驱动)→ Phase 1 起按领域分流,各自独立走完后续,**不混在一个提案里**。

---

## Phase 1 · 多角度挖掘(对同一会话做多镜头扫描)

不是 nuwa 的并行网搜,是对**同一份会话**用 4 个镜头各扫一遍,捞"学习时刻"。
长会话 → 4 个并行子 agent 各管一个镜头;短会话 → 主 agent 一遍过,4 镜头当 checklist。

| 镜头 | 挖什么 | 证据 |
|---|---|---|
| A · 改了什么 | git diff/commit:最终能跑的方案、动了哪些文件/配置 | commit hash |
| B · 踩了什么坑 | transcript 里的失败、回滚、走不通、"原来是…":症状 + 真因 + 怎么修的 | transcript 行 |
| C · 做了什么决策 + 为什么 | 设计选择、取舍、否决了哪些备选方案、为什么这么定 | transcript 行 |
| D · 发现了什么事实 | 具体值/地址/版本事实、"文档写的 X 实际是 Y" | transcript 行 / 实测 log |

**硬要求:** 每条学习时刻必须带证据指针(commit hash / transcript 定位),**禁止"会话前面说过"这种不可追溯的引用**。此刻**不去重**,先全捞。

---

## Phase 2 · 套框架分层

对 Phase 1 捞出的每条学习时刻,跑 `extraction-framework.md`:

```
for 每条学习时刻:
   1. 跑 §2 路由测试 → L1 / L2 / L3 / L4
   2. 如果是「坑」→ 跑 §4 拆:拆成 L2 教训 + L3 事实(不拆 = 不合格)
   3. 标 §7 四字段:来源 / 时间 / 置信度 / 复现次数
   4. L1/L2 拿不准 → §3 不对称:往低放
```

产出:一组分了层的**候选片段**(还没碰库)。

---

## Phase 2.5 · 🔴 CHECKPOINT:给用户看分层结果

```
暂停,展示:
  - 挖到 N 条学习时刻
  - 分层结果(L1:x 条 / L2:y 条 / L3:z 条 / L4:w 条)
  - 每个「坑」拆成的 L2+L3 两片
等用户确认"挖得对、分得对"再进 Phase 3
```

意义:挖掘和分层是主观最重的两步,在这里拦比 Phase 5 返工便宜(对标 nuwa Phase 1.5/2.5)。

---

## Phase 3 · 对账已有库(本流程最关键、最易出错的一步)

**先定 skill 归属(§12 边界逻辑):**
```
- 这领域已有 skill?(如 verified-boot 已存在)
- 用 §12:这次是 → 已有 skill 的新 L2 切面 / 已有 skill 的更新 / 全新 skill?
- L3 差异不开新 skill,只换/加参数表
```

**再对每条候选片段定动作:**

| 候选 vs 库存 | 动作 |
|---|---|
| 库里没有 | **新增** → 提案 add |
| 库里已有、一样 | **去重** → 跳过(绝不重复加,这是防膨胀的关口) |
| 库里有、但旧/错 | **替代** → 提案 supersede,§11 append+标记,**不静默覆盖**(安全/不可逆项尤其) |
| 库说 X、会话说 Y、都像对 | **冲突** → 标记交人审;按 §6 记成变体或修正 |

**L2 升级 gate(§7):** 一条教训只这次见过 → 维持 low,先泊在对应 L3 旁注,**不进 skill L2 正文**;等第 2 个平台/项目复现再升。

**🔴 失败分支:** 对账发现这次"修正"了库里一条安全相关事实(如某 OTP 地址)→ **不自动替**,强制走冲突→人审,并要求 §"硬件读字节"式的二次核实(别拿 transcript 二手记录覆盖)。

---

## Phase 4 · 质检(独立评判,不许自评)

```
对 Phase 3 的提案跑:
  - extraction-framework §8 自检清单
  - §9 反例黑名单
关键:用独立子 agent / 新上下文评判,避免"我刚写的肯定对"偏差(darwin 教训)
  独立 agent 专查:
    - 有没有带反例的东西混进 L1
    - 有没有坑没拆
    - skill 正文里有没有混进具体值
    - 有没有没去重的重复项
子 agent 不可用 → 退化干跑,提案上标 dry_run
```

---

## Phase 5 · 产出提案到 inbox + 🔴 人审 gate

```
1. 把提案写成「对库的 diff」(要 add 什么 / update 什么 / supersede 什么),
   落 inbox/ 暂存 —— 不碰正式库
2. 给人看:
   - diff 全文
   - 每条的溯源 + 置信度
   - 需要决策的:冲突项、low-confidence 项
3. 🔴 STOP:等人审
   - 批准 → /promote 把 diff 合进正式库(可选:若另装了 darwin-skill,可加跑其打分;非必须,cangjie 不依赖它)
   - 拒/改 → 回 Phase 3 调整
4. 无论入库与否,原始学习时刻都已在 journal 留底(可回溯)
```

---

## 反例黑名单(distiller 自己绝不做,对照 extraction-framework §9 + darwin dim9)

| # | 反模式 | 为什么 | 替代 |
|---|---|---|---|
| 1 | 跳过对账直接往库里加 | 重复 L1/L2 散进多个 skill = 库漂移 | Phase 3 强制对账去重 |
| 2 | 自动覆盖库里的安全事实 | 拿二手 transcript 覆盖实测真值,可能写错 | Phase 3 冲突→人审+二次核实 |
| 3 | 单次经验直接进 skill 正文 | 巧合当规律 | §7 复现 ≥2 才升 L2 |
| 4 | 同上下文自评提案 | "刚写的肯定好"偏差 | Phase 4 独立 agent |
| 5 | 只读 git diff 不读 transcript | 抹掉了坑和决策(WHY) | Phase 1 镜头 B/C 必跑 |
| 6 | 提案直写正式库 | 绕过人审 = 库不可控 | Phase 5 只写 inbox,promote 才进库 |
| 7 | 溯源写"前面说过" | 不可追溯,日后无法判过时 | 必须 commit hash / transcript 定位 |
| 8 | 把 AI 元对话/废话当工程知识 | 噪声入库 | Phase 1 只收真实工程学习 |

**触发:Phase 3、Phase 5 各对照本表一次,任一命中 → 重做该步。**

---

## 异常与边界

| 场景 | 处理 |
|---|---|
| 会话太琐碎 | Phase 0 阈值挡掉,只 journal,不提炼 |
| 跨多领域 | Phase 0 分流,各领域独立提案 |
| 领域无对应 skill | Phase 3 判定为「全新 skill」,提案建新 skill 骨架 |
| 独立评判 agent 不可用 | Phase 4 退化干跑 + 标 dry_run |
| git 范围不清 | Phase 0 问用户给 commit 区间,不猜 |

**原则:异常先告知再按规则处理,绝不静默跳过(同 darwin)。**

---

## 一句话流程

```
圈范围 → 4 镜头挖掘 → 套框架分层 → [人审①] → 对账库存(去重/替代/冲突)
       → 独立质检 → 写 inbox 提案 → [人审②] → promote 进库
```

两道人审关:① 挖得对不对、分得对不对;② 入不入库。中间全自动。

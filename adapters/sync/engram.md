# Sync 适配器 · engram(可选)

装了 [engram](https://github.com/TbusOS/engram) 才用。**不装 Whetstone 照样跑**——单机靠人审 + runtime 原生召回。

engram 是通用本地记忆系统。Whetstone 产出的 skill 包同步进去后,由它的质量机器接管,
**Whetstone 自己就不必再造一套**。但委托要按实测现状,不按文档想当然
(2026-08-24 对照 engram 代码核过):

- **召回**(Relevance Gate):已实现(BM25 + 可选向量 + RRF + rerank)。
- **supersede + archive**:已实现(consistency 六动作,只出 proposal、绝不自动改文件)。
- **去重**:只有**事后**扫描(`consistency scan`),且当前是启发式(hash + Jaccard + 反义词表),
  写入时不去重,embedding 聚类未接线(engram T-41/T-48)→ **入库前去重仍是 whetstone Phase 3 的责任,推不掉**。
- **置信度**:证据分级事件流已实现(人工确认 ±1.0 > fixture ±0.6 > LLM 自报 ±0.2);
  但 memory 资产的时间衰减公式(engram SPEC §4.8)**代码里未实现**,真衰减的只有 Session 资产 TTL。

## 映射(Whetstone → engram 资产)

| Whetstone | engram frontmatter |
|---|---|
| skill 包(SKILL.md) | 一条 memory,`type: agent`(或新增 `type: skill`) |
| L1/L2/L3/L4 层 | `extra.scope_layer: 1\|2\|3\|4`(与 engram 的 org/team/user/project scope 正交,放 extra) |
| 来源会话/commit | `source: whetstone:<session-id>` |
| 置信度 / 复现记录 / 验证方式 | 目标位是 engram 的 confidence 事件流;**当前脚本不单独传**,随 SKILL.md body 整体灌入,engram 不自动解析 |
| 平台 params | 各自一条,或挂在 skill 资产的 extra |

## 接法

用 `adapters/sync/engram.sh`(或 `whetstone sync engram <skill>`)。它按上表把一个 skill 包
推成 engram 的 `type: agent` 资产:

```bash
# 预览要跑的命令,不实际写(engram 不在 PATH 也能跑,用来核对)
whetstone sync engram git-workflow --dry-run

# 真写(需 engram 在 PATH;缺了会给清晰提示,退 3)
whetstone sync engram git-workflow
```

脚本做的事:从 `SKILL.md` frontmatter 取 `name` / `description`(codepoint 安全截到 150)→
构造 `engram memory add --type agent --scope user --name … --description … --source whetstone:<skill> --tags whetstone --body -`,
把 `SKILL.md` 内容从 stdin 灌进去。**只传 SKILL.md,不碰 secret。** 之后 engram 负责索引、去重、召回。

> 实测状态:命令构造 + `--dry-run` + 缺 engram 优雅退出**已实测**;**实际写入未在本机验证**
> (本机 engram 缺 click 跑不起来)。装好 engram 后首跑请用 `--dry-run` 核对再去掉。

engram 的 `memory add` 契约见 `engram/cli/engram/commands/memory.py`;frontmatter schema 见
`engram/cli/engram/core/frontmatter.py`(unknown 字段前向兼容,`extra.scope_layer` 安全)。
按层拆成多条资产时,可在每条挂 `extra.scope_layer: 1|2|3|4`(本脚本默认把整包同步成一条 agent 资产)。

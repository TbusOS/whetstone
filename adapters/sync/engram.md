# Sync 适配器 · engram(可选)

装了 [engram](https://github.com/TbusOS/engram) 才用。**不装 Cangjie 照样跑**——单机靠人审 + runtime 原生召回。

engram 是通用本地记忆系统,已实现去重(Consistency Engine)/ 置信衰减 / supersede+archive / 召回
(Relevance Gate)。Cangjie 产出的 skill 包同步进 engram 后,这些质量机器自动接管,
**Cangjie 自己就不必再造一套**。

## 映射(Cangjie → engram 资产)

| Cangjie | engram frontmatter |
|---|---|
| skill 包(SKILL.md) | 一条 memory,`type: agent`(或新增 `type: skill`) |
| L1/L2/L3/L4 层 | `extra.scope_layer: 1\|2\|3\|4`(与 engram 的 org/team/user/project scope 正交,放 extra) |
| 来源会话/commit | `source: cangjie:<session-id>` |
| 置信度 / 复现次数 | engram 的 `validated_count` / `confidence` 块 |
| 平台 params | 各自一条,或挂在 skill 资产的 extra |

## 接法

`/promote` 入库后,可选调 engram CLI 写入(`engram memory add --type=agent --scope=user …`)
或直接写 engram 兼容的 markdown+frontmatter 到其 `.memory/`。engram 负责索引、去重、召回。

engram 的 frontmatter schema 见 `engram/cli/engram/core/frontmatter.py`(unknown 字段前向兼容,
`extra.scope_layer` 安全)。

# Sync 适配器 · llm-wiki(可选)

装了 [llm-wiki](https://github.com/TbusOS/llm-wiki) 才用。**不装不影响 Cangjie。**

llm-wiki 是**人看的**知识库(交叉链接 markdown + Web UI)。Cangjie 产出的是**给 agent 用的** skill 包。
同一条知识可以两头都有:wiki 页给人读来龙去脉,skill 包给 agent 执行。

## 映射(Cangjie → llm-wiki 页)

| Cangjie | llm-wiki 页 |
|---|---|
| L1/L2(原理 + 设计/方法) | `wiki/concepts/<Topic>.md`(带来龙去脉的概念页) |
| L3 平台参数 | `wiki/entities/<Platform>.md` 或概念页下的参数小节 |
| 矛盾/变体 | llm-wiki 的"Known contradictions"区 |

## 接法

`/promote` 入库后,可选把知识导出到 skill 包的 `knowledge/`,再 `wiki ingest` 进某个 llm-wiki 实例。
遵循 llm-wiki 的 frontmatter schema + wikilink 约定(见 llm-wiki `skill/references/`)。

人看 wiki / agent 用 skill —— 两个不同层,不冲突。

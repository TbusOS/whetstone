# 可移植 Skill 包格式规范 (Portable Skill Package Spec)

Cangjie 的**交付物**。一个 skill 包是一个**自包含目录**,符合 Agent Skills 标准、
runtime 中立——拖进任何 skills-compatible runtime 的 skills 目录即得能力。

## 目录布局

```
<skill-name>/
  SKILL.md            # 入口:frontmatter + L1 原理 + L2 设计/SOP + 切面 + L3 指针
  pitfalls.md         # L2 坑库,append-only,每条带溯源
  params/
    <platform>.md     # L3:该平台全部参数 + 实现事实(一平台一份)
  knowledge/          # (可选) 给 engram/llm-wiki 的导出件,不影响 runtime 加载
```

## SKILL.md frontmatter(Agent Skills 标准)

```yaml
---
name: <kebab-case-name>
description: "做什么 + 何时用 + 触发词。一行,≤1024 字符,runtime 中立。"
---
```

正文按 `references/extraction-framework.md` 的分层组织:
- **L1 原理/约束** —— 换任何平台都成立的客观约束。
- **L2 设计/流程/坑** —— 可迁移的设计、SOP、诊断手法(指向 `pitfalls.md`)。
- **切面**(若覆盖多个 L2 切面,如 verified-boot 家族)。
- **L3 指针** —— "具体值见 `params/<platform>.md`",正文不写具体值。

## L3 参数文件(`params/<platform>.md`)

只放值与事实,不放"为什么"。每条带 来源 + 置信度。结构事实/设计变更带 version-bound 的 why。
事实改写用 append + 标记替代,不静默覆盖(尤其安全/不可逆项)。模板见 `templates/params-template.md`。

## 每条知识必带溯源

来源(会话/commit)· 提炼日期(绝对日期)· 置信度(high/med/low)· 复现次数(几个平台见过)。

## Runtime 中立硬规则(否则别的 runtime 拒装)

- ❌ 不写"在 Claude Code 里""Claude Code skill"等绑定单 runtime 的措辞(nuwa 曾因此被别的 agent 拒装)。
- ❌ 不写绝对用户路径(`/home/<user>/…`);引用一律仓库内相对路径。
- ❌ 不内嵌具体值进 SKILL.md 正文(降 L3)。
- ✅ 纯 markdown;自包含;复制目录即用。

## 可移植性保证

- 单元 = 这一个目录。打包(zip / git)给别人,别人拖进自己 runtime 的 skills 目录即用。
- 换平台:只新增/改 `params/<platform>.md`,SKILL.md(L1/L2)不动。
- 方法变好:改 SKILL.md 的 L2,所有平台一起受益。

## 发布脱敏(公开分享前必查)

skill 包要外发(开源 / 给外部)时,过一遍敏感词:厂商专名、内部项目代号、内部路径/IP、
个人姓名等一律脱敏或换 generic。内部自用包可保留真实平台信息。

# 可移植 Skill 包格式规范 (Portable Skill Package Spec)

Whetstone 的**交付物**。一个 skill 包是一个**自包含目录**,符合 Agent Skills 标准、
runtime 中立——拖进任何 skills-compatible runtime 的 skills 目录即得能力。

## 目录布局

```
<skill-name>/
  SKILL.md            # 入口:frontmatter + L1 原理 + L2 设计/SOP + 禁止清单 + 切面 + L3 指针
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
- **禁止清单**(§14)—— 本领域"绝不能做 X"的点名清单;纯原理型 skill 用
  `<!-- blacklist-ok: 理由 -->` 显式豁免。
- **切面**(若覆盖多个 L2 切面,如 verified-boot 家族)。
- **L3 指针** —— "具体值见 `params/<platform>.md`",正文不写具体值。

## L3 参数文件(`params/<platform>.md`)

只放值与事实,不放"为什么"。每条带 §7 溯源字段(来源/日期/复现记录/验证方式含实测结果/置信度,见下节)。结构事实/设计变更带 version-bound 的 why。
事实改写用 append + 标记替代,不静默覆盖(尤其安全/不可逆项)。模板见 `templates/params-template.md`。

## 每条知识必带溯源(extraction-framework §7)

来源(会话/commit)· 提炼日期(绝对日期)· 复现记录(列表:平台/项目 · 日期 · 指针,次数 = 行数)
· 验证方式(可执行检查,可空但空则置信度封顶 med)· 置信度(high/med/low,§7 机械表判:
实测验证通过 + 复现记录 ≥2 行才 high)。
后续会话印证一条已入库知识时,给它的复现记录 append 一行(随提案过人审)——证据跨会话累积。

## Runtime 中立硬规则(否则别的 runtime 拒装)

- ❌ 不写"在 Claude Code 里""Claude Code skill"等绑定单 runtime 的措辞(nuwa 曾因此被别的 agent 拒装)。
- ❌ 不写绝对用户路径(`/home/<user>/…`);引用一律仓库内相对路径。
- ❌ 不内嵌具体值进 SKILL.md 正文(降 L3)。
- ✅ 自包含;复制目录即用;链接不指向包外。
- ✅ 知识本体是 markdown。**`scripts/` 里的可执行检查是欢迎的、且对硬性 checklist 是必需的**
  —— 一条"做 X 时必须同时做 A/B/C"的规矩,只有散文没有能跑的检查,等于没固化。
  用 stdlib / POSIX shell,别硬编码平台名与绝对路径,换机 clone 就能跑。
- ❌ 不打包编译产物与编辑器/系统残留(`.pyc` / `.DS_Store` / 归档包)。

## 可移植性保证

- 单元 = 这一个目录。打包(zip / git)给别人,别人拖进自己 runtime 的 skills 目录即用。
- 换平台:只新增/改 `params/<platform>.md`,SKILL.md(L1/L2)不动。
- 方法变好:改 SKILL.md 的 L2,所有平台一起受益。

## 机械检查(别只靠人记)

上面**大部分**机械可判的规则由 `whetstone verify` 执行,不靠"提交前再看一眼"
(哪些没覆盖、哪些故意不判,`--explain` 末尾原样列着):

```bash
whetstone verify <skill-pkg>          # 单个包
whetstone verify --src ~/skills --strict   # 整库,warn 也算失败
whetstone verify --explain            # 每条检查是什么 + 明确不判什么
```

它查:溯源五字段齐不齐 · 置信度是否越过 §7 机械表允许的上限 · 复现记录是不是列表、
有没有同一平台重复计数 · 坑拆没拆 · 正文有没有混进具体值 · 有没有禁止清单(§14) ·
有没有 runtime 绑定措辞与绝对用户路径。

它**不查**(机械判不了,硬判只会制造假阳,留给 Phase 4 人审):L1 举不举得出反例 ·
删掉平台值后 L2 还成不成立 · 矛盾有没有被保留 · 本次印证的回写做了没有 ·
禁止清单里写的是不是真有用(V25 只查这一节在不在)。
`--explain` 会把这份边界原样打印出来。

**还有一件它整个测不了**:五字段回答的是"这条知识真不真",不是"装上这个包使用者
有没有变强"。两者不能互相预测(extraction-framework §14 末的注解列了实测数据),
所以全绿只说明证据纪律没破,不说明这个包好用。

## 发布脱敏(公开分享前必查)

skill 包要外发(开源 / 给外部)时,过一遍敏感词:厂商专名、内部项目代号、内部路径/IP、
个人姓名等一律脱敏或换 generic。内部自用包可保留真实平台信息。

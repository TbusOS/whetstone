---
name: <skill-name>   # kebab-case;不要是另一个 skill 名的段前缀(避免 foo-bar vs foo-bar-baz 撞车)
# description 契约(见 extraction-framework §13;新增后跑 whetstone lint 校验):
#   ① 能力行:一句话说做什么  ② 触发词:列具体短语,带「触发词:」或「TRIGGER when」
#   ③ 边界声明(同族必写):「DO NOT TRIGGER … use X」/「与 X 同族,不重复它」
# runtime-neutral,一行,长到说清能力+触发+边界即可(过长是菜单成本)。
description: "<能力行>。触发词:<A / B / C>。与 <同族 skill> 同族,不重复它。"
---

# <Skill 标题>

## 原理与约束 (L1)
<不变量:换任何平台都成立的客观约束。举不出反例才放这一层。>

## 设计与流程 (L2)
<可迁移的设计模式 / SOP(带步骤序) / 诊断手法。这是"你的做法",别人可能不同。>

## 坑 (L2)
<可迁移教训。详见 pitfalls.md;每条带 来源 + 日期 + 复现记录 + 验证方式 + 置信度(extraction-framework §7)。>

## 切面(可选,若本 skill 覆盖多个 L2 切面,如 verified-boot 家族)
- <切面 A:验在哪一环 / 入口在哪 → 指向其 L3>
- <切面 B:…>

## 平台参数 (L3)
> 具体值不写这里 —— 见 `params/<平台>.md`。
- 已支持平台:<列表>

## 溯源
<!-- 五字段见 extraction-framework §7;置信度按机械表判,无实测验证封顶 med -->
- 来源:<会话 / commit hash>
- 提炼日期:<绝对日期>
- 复现记录:<平台/项目 · 日期 · 指针>(一行一条,append-only;次数 = 行数)
- 验证方式:<可执行检查:命令 / 脚本 / 最小复现;可空,空则置信度封顶 med>
- 置信度:<high / med / low>(§7 机械表:实测验证通过 + 复现 ≥2 才 high)

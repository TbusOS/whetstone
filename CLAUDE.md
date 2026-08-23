# Whetstone · 磨刀石 — 项目上下文(Claude Code 打开本目录即加载)

> 这份文件是「打开 whetstone 目录就能接着开发」的载体。Claude Code 打开本目录会自动读它。
> 原始会话 transcript 不可移植(机器本地、按路径分库),所以连续性靠这份**蒸馏过的状态** ——
> 正好是 whetstone 自己的哲学:把会话蒸馏成可复用知识,而不是搬原始记录。

## 这是什么

Whetstone 是一个**蒸馏工具**(不是单个 skill):开发完一个功能,挖掘会话(transcript + git diff + 踩坑),
按作用域拆成 4 层,对账已有 skill 库,产出一个**可移植、runtime 中立的 Agent Skill 包**,人审后入库。
越用本地 skill 库越大越准;换平台只换 L3 参数表;打包给别人(任何 runtime)即得能力。

- 主入口:`SKILL.md`(distiller 流程 Phase 0–5)
- 灵魂:`references/extraction-framework.md`(L1–L4 分层 schema)
- 交付物规范:`spec/skill-package.md`(可移植 skill 包格式)
- 介绍页:`docs/index.html`(anthropic 风格,GitHub Pages 用,已过设计三闸)

## 定位决定(已定,别再推翻除非有新理由)

1. **独立仓库**,不并进 sky-skills。判据:它是「多组件工具」(方法+格式+adapter),不是单个 skill;
   先例是 llm-wiki/engram(我们自己的独立工具),不是 nuwa/darwin(花叔的第三方 skill)。
2. **Runtime 中立 + 零运行时依赖**。runtime 专属只隔离在 `adapters/capture/<runtime>`;产物是纯 markdown。
   不写「在 Claude Code 里」这类绑定措辞(否则别的 agent 拒装)。
3. **engram / llm-wiki / darwin 都是可选 sink**,装了增强,不装照跑。
   特别是:**engram 已实现去重/置信衰减/召回**,whetstone 不重造这套 —— 有 engram 就委托它,
   单机靠人审 + runtime 原生召回。
4. **L1–L4 分层**:L1 原理(任何平台成立)/ L2 方法+坑(可迁移,你的做法)/ L3 平台参数(换平台就变的值)/
   L4 状态(下次会话就变)。坑必须拆成 L2 教训 + L3 事实。详见 extraction-framework.md。
5. **作用域还决定 skill 边界**:共享 L1/L2 的领域合成一个 skill(如 verified-boot 家族),陌生的分开。

## 约定

- **命名一律小写**(`whetstone`),跟 skill name、install 路径、兄弟仓库一致;品牌展示用 `Whetstone · 磨刀石`(标题里大写)。
- **公开仓库 → push 前必做脱敏**:厂商芯片型号、内部项目代号/工单号、内部路径/IP、个人姓名 —— 一律换 generic 或删。docs/index.html 和 spec 里的安全启动例已是 generic。
- **★工具 / 产物分离(防泄露铁线)**:本仓库 = **工具**(公开);distiller 蒸出的真 skill 包 = **产物**(常带真实平台值,留内部 `~/.claude/skills/<name>/`,**永不 push 进本仓库**)。
  - 公开仓库要放 demo → **必须另写 100% generic 版**(`SoC-X` / `OTP[ADDR]` / `RSA-N`,无工单号、无能反推厂商的细节,如某厂商文档地址与实测不符这类),**严禁拷内部产物包来改**(改最易漏脱敏)。
  - 现状:`references/extraction-framework.md §5` 的 generic 安全启动例已充当 demo,通常不必再加 demo 包。
  - 反面教材 2026-06-17:第一个试点蒸出的 `verified-boot`(带某芯片真实平台值)正确地产在 `~/.claude/skills/`(内部),没进本仓库 —— 当时差点建议把它做成公开 demo,被用户挡下。
- **commit message 禁止任何 Claude / Anthropic 署名**(全局铁律)。本仓库是开源/个人工具,commit 邮箱用你的公开身份,message 格式自由。
- 脚本开头锁 PATH(`/usr/local/...`)+ `PYTHONNOUSERSITE=1`;临时文件不用 /tmp;路径用 SCRIPT_DIR 相对。
- 设计 HTML 一律走 anthropic-design skill + 发布前三闸(`~/.claude/skills/design-review/dr-cli docs/index.html`)。

## 当前状态:v1 核心完成(2026-06-17)

**核心(思考层)= 完成 + 验证:**
- `SKILL.md`(Phase 0-5)· `references/extraction-framework.md`(L1-L4,跨领域压测过)· `spec/skill-package.md` —— **2 次真实试点跑通**(蒸出 verified-boot / sdk-migration 两个内部 skill 包),还反哺出 Phase 3 的"doc + git/code 双查"规则。
- 已发布:github.com/TbusOS/whetstone(main)+ GitHub Pages **https://doc.tbusos.com/whetstone/**(源 /docs,Enforce HTTPS;含工具介绍 `index.html` + 通用 skills 介绍 `skills.html`,anthropic 风,过设计三闸)。
- templates / commands / README / 本文件齐。

**管道层 = 2026-06-18 补了一轮(按"真用得着 + 建了就实测"做,不空造):**
- `adapters/capture/claude-code.sh`:**已实测**(`adapters/capture/selftest.sh` 10/10:jq 路径 / python 回退 / 空 stdin / `--clean`)。实测时抓出真 bug:`SKILL_DIR` 原来只上跳一级 `..`,journal 会落到 `adapters/journal/` 而非 skill 根 `journal/`(`/distill` 读的那个)——已改成两级 `../..`。
- `bin/promote.sh`:**已建+实测**。机械装新 skill;撞已有 skill **拒绝静默覆盖**(L2 merge / fact supersede 是语义活,留给 agent `/promote`,或 `--force` 整包替换)。provenance 写 `journal/promoted.jsonl`。`--list/--dry-run/--force`。
- `cli/whetstone`:**已建+实测**。noun-verb 派发 pack/deploy/promote/capture/selftest/journal/sync;`distill` 诚实提示"在 agent runtime 跑"不假装。纯 bash 零依赖。
- `adapters/sync/engram.sh`:**已建,dry-run 实测**。按核实的 engram `memory add` 契约构造命令(type=agent/scope=user/source=whetstone:<skill>/body=SKILL.md via stdin,desc codepoint 安全截 150)。**实际写入未在本机验证**(本机 engram 缺 click 跑不起来)——文档已如实标注,装好 engram 首跑用 `--dry-run` 核对。
- `bin/lint.py` + `bin/index.py`(2026-06-18 加,索引卫生):**已建+实测**(对真 26-skill 菜单跑过)。lint 揪 description 缺触发词 / 触发词高重叠(Jaccard)/ 名字段前缀撞车(真抓到 design-review ↔ design-review-framework,已把后者重命名为 sdk-code-review 消除);index 生成分族 INDEX.md。配套 extraction-framework §13「description 契约」+ skill-template frontmatter。**根因**:skill 选择发生在 name+description 菜单(常驻上下文),库长大噪声从这进,正文懒加载不算。
- `/distill` `/promote`:仍是 agent 流程定义;`/promote` 的语义 merge 靠对话,`bin/promote.sh` 只机械化了"装新 skill + 撞库不覆盖"那半。
- `adapters/sync/llm-wiki`:仍是文档,未写脚本(没真需求)。
- 跨 runtime(Codex/Cursor):采集契约中立可照搬,**仍未在真实 Codex/Cursor 上实测**(本机无该 runtime)。
- **§7 证据升级(2026-08-24)**:调研(engram 内部 + ai-doc 论文 + 业界系统)确认设计的唯一结构性缺口是"质量控制全在入口,入库后无信号回流"。两个 spec 级修复,零新基础设施:① **验证方式字段**(吸收 kernel-learn"无可执行检查不准建"):每条带可执行检查位,置信度改**机械判定表**(实测验证 + 复现 ≥2 才 high,无验证封顶 med);② **复现回写**(ExpeL 式 upvote):复现次数(裸数字)改复现记录(append-only 列表),Phase 3 对账时本次印证过的旧条目在提案里 append 一行——人审不再一次性。改动:extraction-framework §7/§8/§9、SKILL.md Phase 2/3/4/5 + 黑名单 +9/+10、双模板(顺修模板漏"复现次数"字段的 bug)、spec/skill-package.md;`adapters/sync/engram.md` 修正两处对 engram 的过度声明(去重仅事后启发式、memory 置信衰减未实现——委托按实测不按文档)。
- `autoupdate/`(2026-08-24 加):多 CLI 自动更新提示器,从 sky-skills-autoupdate 移植 + 三处适配:**join/own 双模式**(本机已有兼容 hook 就只登记 repos,不挂第二套,防双重提示)、**union 读取** `~/.config/*-autoupdate/repos`(谁的 hook 活着都能看到全部被监控仓)、修两处移植 bug(macOS 无 `timeout` 时 fetch 静默失效 → 加回退;重启检测正则 `/SKILL\.md$` 匹配不到仓库根布局 → `(^|/)`)。**已建+实测**(`autoupdate/selftest.sh` 22/22,隔离夹具;本机 install 实测走 join 模式)。CLI 加 `whetstone autoupdate check|update|install|upgrade|uninstall|selftest`。

## 判断:v1 算完成,先用起来

工具本身基本到头了。**"越用越聪明"发生在长大的 skill 库里(产物),不是给工具加功能。** 管道层等真用着疼了再补对应那块:忘记蒸 → 挂 capture hook;有 engram 且想自动同步 → 写 sync;要上别的 runtime → 实测 + 修措辞。**真正该持续做的:继续蒸 skill 让库长大。**

## 待定 / 可选功能

- **skill 库跨机迁移**:推荐把自己的 skill 放**私有** repo(clone 即部署);whetstone 可加 `bin/pack.sh` + `bin/deploy.sh`(generic tar + manifest)当补充。未建,按需。

## 续上下文怎么做

打开本目录后:读本文件 → 读 `git status -sb` 看实际状态 → 需要细节再读对应文件。
**记忆 / 会话记录**:本仓 `memory/SESSION-LOG.md`(通用,0 内部数据);**完整内部记录(带真实平台值 + 会话流水)在私有仓 `whetstone-skills-private/memory/`**,不在此。
带真实平台示例的设计草稿保留在本机本地(**不在本公开仓库**),勿入公开仓库。

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
3. **engram / llm-wiki / darwin 都是可选 sink**,装了增强,不装照跑。委托 engram 按**实测现状**
   (2026-08-24 核对其代码,详见 adapters/sync/engram.md):召回 / supersede / 证据分级事件流已实现,
   可委托;**去重仅事后启发式扫描、memory 置信衰减未实现**——入库前去重与质量把关是 whetstone
   Phase 3 自己的责任,推不掉。单机靠人审 + runtime 原生召回。
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

## 当前状态:v0.2.0(核心完成 2026-06-17;verify / decision 后续加)

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
- **§7 证据升级(2026-08-24)**:调研(engram 内部 + ai-doc 论文 + 业界系统)确认设计的唯一结构性缺口是"质量控制全在入口,入库后无信号回流"。两个 spec 级修复,零新基础设施:① **验证方式字段**(吸收 kernel-learn"无可执行检查不准建"):每条带可执行检查位,置信度改**机械判定表**(实测验证 + 复现 ≥2 才 high,无验证封顶 med);② **复现回写**(ExpeL 式 upvote):复现次数(裸数字)改复现记录(append-only 列表),Phase 3 对账时本次印证过的旧条目在提案里 append 一行——人审不再一次性。改动:extraction-framework §7/§8/§9、SKILL.md Phase 2/3/4/5 + 黑名单 +9/+10、双模板、spec/skill-package.md;engram 过度声明按实测修正(CLAUDE.md 定位决定 #3 / README / engram.md / engram.sh 四处)。
- **评审加固轮(2026-08-24,3 个独立评审 agent 全查了一遍)**:§7 补齐——机械表加 L2 附加约束(单平台 L2 封顶 low,med 的"验证 1 次"条款只适用 L3)、验证方式加「实测:通过 <日期>/未实测」承载位、复现记录行唯一键 = 平台/项目(防同项目刷次数绕过升级 gate)、params 模板补齐复现/日期列、`/promote` 加回写落地步骤(也承认 curator fetch 提案)、新增 pitfalls-template。autoupdate 修 6 个必修(merge-only 提交炸算术、repos 缺末行换行丢仓、jq 失败假报成功、README 两条共存承诺改诚实、own 模式静默吞兄弟 hook→改为拒绝+--takeover、selftest 环境泄漏),selftest 22→**43 项**全过;另修 bash 坑:UTF-8 locale 下 `$var` 后紧跟全角字符会被当变量名(set -u 直接死)。
- `autoupdate/`(2026-08-24 加):多 CLI 自动更新提示器,从 sky-skills-autoupdate 移植 + 三处适配:**join/own 双模式**(本机已有兼容 hook 就只登记 repos,不挂第二套,防双重提示)、**union 读取** `~/.config/*-autoupdate/repos`(谁的 hook 活着都能看到全部被监控仓)、修两处移植 bug(macOS 无 `timeout` 时 fetch 静默失效 → 加回退;重启检测正则 `/SKILL\.md$` 匹配不到仓库根布局 → `(^|/)`)。**已建+实测**(`autoupdate/selftest.sh` 22/22,隔离夹具;本机 install 实测走 join 模式)。CLI 加 `whetstone autoupdate check|update|install|upgrade|uninstall|selftest`。
- **`whetstone verify`(0.1.0 之后加,`fca1f04`;当前版本号 `cli/whetstone` 里 `WHETSTONE_VERSION=0.2.0`)**:把 §7/§8/§9 里**机械可判**的那部分变成能跑的检查,38 个检查码。三份独立评审加固过(堵掉 4 条绕过路径 + 8 处误报)。配 `bin/verify_selftest.sh`(124 项,**每个检查码正反两个方向都测**,并有覆盖检查:`--explain` 里发布的码缺任一方向就报红)+ `bin/verify_mutation_test.sh`(14 条故意改坏,自检必须报红)。`--explain` 末尾原样列着**它不判什么**。
- **§14 产出物的禁止清单 + V25(2026-09-04,`d58e766`)**:依据 SkillLens(arXiv 2605.23899)—— 它把"明写高危动作禁止清单"列为三个与真实效用相关的特征之一。**§9 那张黑名单管的是提炼器自己,产出的包以前从没被要求带一张。** V25 是 WARN 不是 ERROR:presence 机械可判、content 不可判,出错方向是放过。同 commit 还澄清了 §4 末:**降 L3 降的是会随平台变的值,不是工具名/命令名** —— V19 实际只扫五类(hex/IP/系统绝对路径/v 版本号/带量纲的数),这点以前只存在于代码里,而 §9#1 叠 §3 读容易做出一份只剩抽象步骤的文档,那正是同一篇论文测出效果最差的写法。
- **`whetstone decision`:人审决定记录(2026-09-04,`06d7869` + `9f20417`)**:框架自进化的第一步,**只记录,不分析,不改任何规则**。动机:§7 和 §14 两次框架升级都来自外部读物 + 人拍板,工具自己的运行历史根本不存在 —— 而人审每次批/拒/改本身就是免费产生的标注,以前会话一结束全丢。`stats` 按**不同来源**去重计数(不按行数;无来源的全算一个),某标签攒够 3 个不同来源才点名,**点名 ≠ 结论**。配标签一致性两个机制:写前摆词表(相似度只用于排序)+ `alias` 读取时合并(存的行一字节不动,§11)。**没做自动"你是不是想说 X"** —— 实测任何阈值都做不了(0.72 漏掉 0.60 的真同义对,0.60 又误判 0.643 的非同义对;词序颠倒 0.455;跨语言 0.0)。46 项自检 + 8 条故意改坏的测试。规范见 `spec/review-decisions.md`。
- **变异测试的一个洞(2026-09-04,`c7ac229`)**:`mut()` 遇到锚点对不上时既不算抓到也不算漏掉,一条早已失效的变异会安静地什么都不测而整套照样绿。两套现在都单独计 `did-not-apply` 并计入失败,且给自检套了 `timeout`(去掉循环保护的变异会真的转不出来)。**验过它会红**:故意改坏一条锚点,修前 `caught:13 missed:0` 退出 0,修后 `did-not-apply:1` 退出 1。
- **★ 已知边界(2026-09 写进 §14 / `--explain` / spec / README)**:上面所有检查回答的都是「这条知识真不真、能不能追溯」,**没有一条回答「装上这个包使用者是不是变强了」**。SkillLens 实测这两件事不能互相预测(25% 的抽取器×使用者配对出现负迁移,最差领域 47%;裸看文本判优劣 46.4%;排版格式 p>0.34 无显著影响)。所以 verify 全绿只说明证据纪律没破。

## 判断:v1 算完成,先用起来

工具本身基本到头了。**"越用越聪明"发生在长大的 skill 库里(产物),不是给工具加功能。** 管道层等真用着疼了再补对应那块:忘记蒸 → 挂 capture hook;有 engram 且想自动同步 → 写 sync;要上别的 runtime → 实测 + 修措辞。**真正该持续做的:继续蒸 skill 让库长大。**

**这个判断后来被两次打破,两次都是对的**(记下来,免得下次又用"工具到头了"挡掉该做的事):
`verify` 是因为「61 条标 high 的条目,0 条说得出验证方式」这个真实疼点才写的;
`decision` 是因为「框架自己的历史根本不存在,所以每次升级只能靠外部读物」。
**判断依据不是"工具还能不能加功能",是"有没有一个反复咬人的地方"** ——
没有就继续蒸 skill,有就补那一块。

## 兄弟仓:whetstone-curator(团队侧,2026-08-24 建)

github.com/TbusOS/whetstone-curator —— 「库 → 库」经验流动,fetch(按需帮个人从队友库筛经验)
/ harvest(收割全队进 canonical 团队库)双模式,AI 筛人裁。规则全部引用本仓 extraction-framework,
依赖本仓 ≥ 89a341d(§7 证据升级)。本仓配合改动:lint.py COMPANION_SUFFIX 加 `curator`。
团队相关需求先去那边看 REQUIREMENTS/DESIGN/TASKS,别在本仓重复造。

## 待定 / 可选功能

- **skill 库跨机迁移**:推荐把自己的 skill 放**私有** repo(clone 即部署);whetstone 可加 `bin/pack.sh` + `bin/deploy.sh`(generic tar + manifest)当补充。未建,按需。

## 续上下文怎么做

打开本目录后:读本文件 → 读 `git status -sb` 看实际状态 → 需要细节再读对应文件。
**记忆 / 会话记录**:本仓 `memory/SESSION-LOG.md`(通用,0 内部数据);**完整内部记录(带真实平台值 + 会话流水)在私有仓 `whetstone-skills-private/memory/`**,不在此。
带真实平台示例的设计草稿保留在本机本地(**不在本公开仓库**),勿入公开仓库。

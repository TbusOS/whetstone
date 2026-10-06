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
- 介绍页:`docs/index.html`(GitHub Pages 用;2026-10-07 改版为自有的深色「磨刀石 + 岩层」风格,6 个页面共用 `docs/assets/site.css` + `site.js`)

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
- `docs/` 页面用自有风格(2026-10-07 user 定:不再套 anthropic-design 等现成设计 skill)。公共样式 / 中英切换在 `docs/assets/site.css`、`site.js`,页面专属样式写在各页内联 `<style>`;分享预览图 `assets/og-home.png` 由 `assets/og-home.src.html` 渲染(1200×630,2 倍)。
  页面上手写的数字(检查条数 38、demo-skill 的 verify 输出、阶段名)不会自动跟着代码变,改了 verify / SKILL.md 要回来同步。

## 当前状态:v0.2.0(核心完成 2026-06-17;verify / decision 后续加)

**核心(思考层)= 完成 + 验证:**
- `SKILL.md`(Phase 0-5)· `references/extraction-framework.md`(L1-L4,跨领域压测过)· `spec/skill-package.md` —— **2 次真实试点跑通**(蒸出 verified-boot / sdk-migration 两个内部 skill 包),还反哺出 Phase 3 的"doc + git/code 双查"规则。
- 已发布:github.com/TbusOS/whetstone(main)+ GitHub Pages **https://doc.tbusos.com/whetstone/**(源 /docs,Enforce HTTPS;含工具介绍 `index.html` + 通用 skills 介绍 `skills.html` + 验证实践记录 `why-verify.html` + `claude-md-layering.html` + 用时纠错功能页 `use-time-conflicts.html`(2026-09-29)+ 经验路由功能页 `routing.html`)。2026-10-07 六页全部改为深色自有风格(旧 anthropic.css / fonts.css 已删);原来的 SVG 图改成 HTML/CSS 画,文字能换行、手机不再超宽。
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
- **用时冲突处理(2026-09-28)**:经验入库之后的纠错通道。agent 用到库里的经验、发现和当前代码 / 实测对不上时,先分类(过期 / 范围不符 / 原本就错 / 代码又犯了经验警告过的错 / 两条经验互相矛盾)、按证据分三档(直接看到 / 推出来的 / 看不到)、主动报,**人确认了才改**。规范 `spec/use-time-conflicts.md`。**判断挪到"用的时候"是这版的关键**:入库时手里只有文本,判断对错没有依据;用的时候代码和板子就在眼前。`decision` 加了 `report` / `resolve` / `miss`,**冲突分两步记**:记录是被打分的 AI 自己写的,一行写两边的话,AI 的"自己的判断"可以照着人的答案填,一致率 100% 且看不出来。所以 AI 的判断先落记录并打印指纹(报告必须带这行),人的回答事后追加;同一编号不能重报,事后改过的行指纹对不上、不计分,同一条经验在一个来源里重报只给第一次打分。`stats` 按"类型 × 证据档"用精确二项下界(不用点估计)算判对率,给出每组该怎么问(完整 / 摘要 / 批量,**只改怎么问,不改问不问**);推断占比 >30%、该类型出现漏报,都退回完整确认。**2026-09-29 按 user 决定去掉了单独的考卷**:真实冲突记录就是考试,放宽本来就要至少 22 条真实记录全对,考卷只是重复把关;同日又补上换模型的空档:每条报告记 `--model`(算进指纹),放宽只算当前模型的记录,换模型每组从 0 开始(规范第 8 节末)。decision 自检 119 项,故意改坏 31 条。**"先问人、后记判断"这种做法工具挡不住,只能靠报告里那行指纹让人看一眼。**
- **入口脚本软链接 + autoupdate 自检外逃(2026-09-29)**:两个早就存在、给全局规则接线时才撞上的问题。
  ① `cli/whetstone` 用 `dirname "${BASH_SOURCE[0]}"` 算目录、没解开软链接,经 `~/.local/bin/whetstone` 调用时 verify / lint / decision 全部失败,只有 `--version` 正常,所以五周没人发现;改成循环解链接,`decision_selftest.sh` 加了一层 / 两层软链接两项(先对旧版跑出 2 项失败)。
  ② autoupdate 自检锁 PATH 后用的是 `/usr/bin/git` 2.25,不认 `init -b`,测试仓库没建成;后面 `git -C <普通目录> add -A / commit / push` 沿目录往上落到**真实仓,并推到了公开远端**(一笔作者 `selftest@local`、说明 "c3: add skills + command" 的误提交,内容恰好是①的修复;user 决定改写历史,已强推换成两笔正常提交)。现在三层:`GIT_CEILING_DIRECTORIES` 不许越过测试目录往上找;跑测试前逐个核对测试仓库是不是它自己的仓,不是就退出 2;结束时比对外层仓的 HEAD 和工作区。建仓改成老 git 也能用的写法。在隔离克隆 + 假远端里验过:旧脚本复现外逃、新脚本 44 项全过且不动仓、故意弄坏建仓时停在测试之前、只留第一层也挡得住。**这台机器上改前是 31 过 12 败(`ee88a1f` 上实测),上面"43 项全过"那条不适用于 git < 2.28 的机器。**
- **`deploy.sh` 防死循环(2026-09-29,从私有仓副本搬回)**:取值选项末尾是 `shift 2`,bash 在只剩一个参数时 `shift 2` 失败且一个都不移,`--gen-claudemd` 漏写值就在 `while` 里空转(私有仓注释记着曾空转 76.5 小时 CPU)。私有仓 09-03 就修了,但修在了副本上,公开仓一直没有 —— 私有仓的漂移检查只会说"上游更新了、本仓落后",照做 `--sync` 反而会把修复盖掉(那边的检查已改成按提交时间判断哪边新)。新增 `bin/deploy_selftest.sh`(`whetstone deploy-selftest`):6 个取值选项各自缺值必须 5 秒内退出 2 并点名,再验生成全局规则与装链接两个模式照常工作。先对旧版跑:7 项卡死;修后 12 项全过、0.16 秒。
- **lint 加菜单体积检查(2026-09-29)**:起因是实测"聊到相关话题 skill 会不会被加载"——技能菜单有总预算,
  超了 runtime 不删 skill、只去掉一部分描述;一台机器上 65 个 skill 有 35 个只剩名字,触发词出现时有描述的 26% 被加载、
  只剩名字的 1%。**单条描述都合格,合在一起照样装不下**,以前的 lint 只看单条。现在 `lint` 算整份菜单的长度,
  和 `--menu-budget`(默认 25000,即 76 份实测菜单)比,超了给**平均份额**和先砍哪几条(把超份额的都砍到份额,
  一定放得下;份额 < 40 字符才必须停用 / 合并);单条超 1024(Agent Skills 标准)报警告;YAML 写错报警告。
  `whetstone menu-snapshot | whetstone lint --listing -` 拿 Claude Code 实际发出的菜单对照(适配器在
  `adapters/menu/`,lint 本身不绑 runtime):哪些只剩名字、哪些显示的不是自己的描述(实测一例:描述超过 Claude Code
  自己的 1,536 上限,菜单里显示的是正文第一个标题)。**顺带修了 frontmatter 解析器**:双引号描述跨行、第二行从行首写起
  (YAML 合法)时,旧解析器只读第一行、还把第二行当成新字段 —— 一条 1,693 字符的描述只算成 1,462;现在对 64 个合法 skill
  与 PyYAML 逐个一致。自检 50 项、故意改坏 25 条(先跑出 3 条漏网,补了测试)。
  `menu-snapshot --events`:界面上只显示「N skill available」,这里按时间列出名字,并把两种事件分开 ——
  **菜单更新**(名字 + 描述重发;SKILL.md 被装上或改过就会发,正文不进上下文)和**真正加载**(Skill 工具 /
  读 SKILL.md / 压缩后重放)。不给 `--session` 时用 Claude Code 给命令设的 `CLAUDE_CODE_SESSION_ID`
  (即当前会话);没有它才退回最近写入的会话 —— 几个会话同时开着时那可能是别人的。
  同日实测(无交互会话 + `--settings '{"disableAllHooks": true}'` 不跑钩子):`disable-model-invocation: true`
  的 skill 在菜单里连名字都没有(lint 已不计它们);`<项目>/.claude/skills/` 从子目录启动也会往上找到(目录不是 git 仓也行),
  从别处启动则读到该目录文件时中途补进菜单;**预算跟着模型走** —— 同一个库 Opus 会话 25,123 字符、Haiku 4.5 会话 7,978。
- **经验路由(2026-09-30 第二版 + 一期大部分实现,`spec/routing.md`)**:菜单有预算、库一直长,平铺菜单迟早分不够。
  三层:① 常驻 —— 路由 skill(`whetstone route catalog`)、按项目让位(Claude Code `skillOverrides` 设 `name-only`,
  不是藏)、跟文件绑定的加 `paths`(09-30 实测:开局不在菜单,读到匹配文件才追加 —— 平时不占预算);
  ② 按需 —— `whetstone find "<要做的事>"`(BM25F:名字 / 描述 / 正文 / 学到的原话;中文按两个字切 + 虚词表;
  覆盖率不够门槛就直说没有,**给错比不给糟**);③ 离线学习 —— `route learn` 学「使用者怎么说 → 用了哪条」。
  **钩子 0 个、不写死目录清单、不用只许手动调用省菜单,都是 user 定的。**
  **通用性**(user 09-30 要求适配 Codex / opencode / pi 等):`bin/route.py` 只读统一会话事件(`session` / `user` /
  `file` / `load{via,use}` / `menu` / `find`),每个运行时一个适配器;`use` 由适配器判(Claude Code 读 SKILL.md
  多半是改它,Codex / pi 读 SKILL.md 就是在用)。六家对照(装库目录、菜单上限、项目级开关、会话里有没有菜单)在规范第 5.3 节。
  **改动靠回放决定**(`route replay`):按时间切、逐例比 5 胜 0 负或 7 胜 1 负且来自 ≥2 个项目才保留;
  随机排序必须输、偷看答案必须赢,否则数字作废。第一次回放(一台机器 34 例):学原话 9 胜 0 负 → 保留;
  「本项目用过就加分」3 胜 4 负 → 不用;门槛 0.3 只是起点(原话当查询太口语,适配器已开始记模型写的 `find` 查询,攒够再定)。
  修了两处归属错:主目录有 `~/.claude` 会吞掉所有无标记目录;仓根本身是 skill(`SKILL.md` 挨着 `.git`)时,
  在仓里干活全被当成读 skill。
  `whetstone route plan`(`adapters/levers/claude-code.py`)把「用得集中在别的项目」(`route elsewhere`:≥3 会话、
  ≥2/3 在另一项目、本项目 0 次,事先定)翻成 `skillOverrides: name-only`,默认只打印,`--write` 才合并、保留使用者自己的条目。
  **实测设置文件读哪一层**:git 仓里读仓根(子目录启动也读);不在 git 仓只读启动目录本身。本机数据下三个项目都是 0 条建议。
  **自检外逃第二次**:测试「不在 git 仓」时往上找 `.git` 找到了本仓,把夹具合并进本仓 `.claude/settings.local.json`
  (被全局 gitignore,git status 看不到;已删)。现在:往上找一律停在家目录、测试目录放 `.git` 挡板、末尾查测试目录外有没有文件被写
  (隔离副本里去掉前两层验过它会红)。**跑故意改坏测试时别改仓里任何文件**,否则末尾那道检查会误报。
  自检 `route_selftest.sh` 73 项、`route_mutation_test.sh` 57 条全抓。
  未做:同时链到 `~/.agents/skills`、按 Codex 规则算菜单、第二个运行时的适配器。
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

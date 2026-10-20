# Whetstone · 磨刀石

做完一个功能,whetstone 把这次会话里学到的东西提炼成一个 skill 包,装进你自己的 skill 库。
下次做同类的事,agent 会自己用上它。每一条都必须写明出处,写不出出处的进不了库。

*别的「把会话提炼成 skill」的工具只管往库里写,这个还会拒绝。*

English: [README.md](README.md)

## 一条经验从会话到下次被用上

```
会话记录 + git diff
   │ 1. 提炼:模型照 SKILL.md 的步骤做,每条写明出处
   ▼
一个 skill 包:一个目录,三个文件
   │ 2. 把关:whetstone verify 查证据,再过人审
   ▼
你自己的 skill 库(~/.claude/skills/、~/.agents/skills/ 等)
   │ 3. 再用:运行时把每个包的 name + description 放进菜单给模型看
   ▼
话题对上 → 模型读 SKILL.md 正文 → 做到那一步再读 params/<平台>.md
```

每一步由谁来做,是有意分开的:

- **第 1 步是模型做的。** 分清会话里哪句是经验、哪句是闲聊,要读懂意思,规则写不出来。
  所以提炼器是一份写给 agent 的步骤说明([`SKILL.md`](SKILL.md),Phase 0-5),不是程序。
  `whetstone distill` 只会提示你到 agent 里去跑。
- **第 2 步不信模型。** 模型会补没有的东西,也会给自己打高分。它写出来的每一条都要写明
  来自哪个提交或哪次会话,要过一道不靠模型的命令检查,还要过人审两次:
  第一次看「挖得对不对」,第二次定「进不进库」。
- **第 3 步是运行时自己的 skill 机制。** whetstone 不负责触发。它管两件事:菜单上那两行
  写得好不好(`whetstone lint`),菜单太长显示不全时还能搜到(`whetstone find`)。
- 提炼出来的包放在**你自己的**库里,不放进本仓库:包里有真实的平台值。本仓库只放工具。

## 写对的包长什么样

[`examples/good-skill/`](examples/good-skill) 是一个完整的包,领域是编的:只能写一次的存储。
`whetstone verify` 在它身上挑不出毛病。

```
examples/good-skill/
├── SKILL.md          靠什么被选中(name + description),然后是原理、
│                     做法、绝不能做的事,以及指向另外两个文件
├── pitfalls.md       踩过的坑:症状、真因、修法、涉及哪些值
└── params/soc-x.md   只在 soc-x 这个平台成立的值;换平台就加一个文件
```

**`SKILL.md`:靠这两行被选中。** 话题对上之前,运行时只把这两行给模型看。
description 写清楚这个包管什么(只能写一次的存储怎么写、怎么核对),以及哪些说法该让它出来。

<!-- excerpt: examples/good-skill/SKILL.md -->
```yaml
name: good-skill
description: "一次性写入的存储(写坏就回不去)怎么写、怎么核对:写前先存原始内容,写后直接读回底层比对。触发词:一次性写入 / 写入前备份 / 读回比对 / write-once storage。"
```

正文按知识的种类分节:原理与约束(L1)· 设计与流程(L2)· 坑(指向 `pitfalls.md`)·
禁止(绝不能做的事)· 平台参数(指向 `params/soc-x.md`)· 溯源(这些都是从哪来的)。

**`pitfalls.md`:一条坑。** 症状、真因、修法,以及涉及哪些值。后面跟着它的证据,
字段和下面那张表一样。

<!-- excerpt: examples/good-skill/pitfalls.md -->
```markdown
## 从上层状态反推底层状态会看错

- 症状:上层字段显示未生效,底层其实已经生效。
- 真因:中间层缓存了一份过期副本。
- 修法:直接读底层,不看中间层。
- 涉及事实:见 `params/soc-x.md`
```

**`params/soc-x.md`:具体值,每个值都带证据。**

<!-- excerpt: examples/good-skill/params/soc-x.md -->
| 参数 | 值 | 来源 · 日期 | 验证方式 · 实测 | 复现记录 | 置信度 |
|---|---|---|---|---|---|
| 存储起始位置 | `SLOT_A` | commit 1a2b3c4d · 2026-08-01 | 读回比对 · 实测:通过 2026-09-01 | 2026-08-01 · commit 1a2b3c4d; 2026-09-01 · commit 5e6f7a8b | high |
| 读回起始地址 | `0x1A40` | commit 1a2b3c4d · 2026-08-01 | 读回比对 · 实测:通过 2026-09-01 | 2026-08-01 · commit 1a2b3c4d | med |

| 列 | 写什么 | 第一行写的 |
|---|---|---|
| 参数 | 这个值叫什么 | 存储起始位置 |
| 值 | 具体是多少,只在这个平台成立 | `SLOT_A` |
| 来源 · 日期 | 从哪个提交得来、哪天 | commit 1a2b3c4d · 2026-08-01 |
| 验证方式 · 实测 | 怎么复查,真跑过没有 | 读回比对 · 2026-09-01 实测通过 |
| 复现记录 | 之后每核实一次记一行 | 2 行 |
| 置信度 | 由前两列按规则算出来,不能凭感觉填 | `high` |

两行的置信度不一样是有原因的。第一行实测通过、又核实过两次,所以可以写 `high`。
第二行只实测过一次,对一个值来说够得上 `med`。如果是一条**做法**,只在一个平台上见过,
测得再好也只能是 `low`:见过一次说明不了它到处都成立。完整规则见下面的
[置信度是一张表](#置信度是一张表不是感觉)。

<!-- output: whetstone verify examples/good-skill --brief -->
```console
$ whetstone verify examples/good-skill --brief

whetstone verify — examples/good-skill

INFO (2)
  i pitfalls.md:5  [V18] [从上层状态反推底层状态会看错] reproduced on 2 distinct platforms/projects — eligible to move into the SKILL.md L2 body
  i good-skill  [V08d] 2 commit hash(es) cited in 来源 / 复现记录, none checked against git

summary: 0 error(s), 0 warning(s), 2 info
```

没有错误,也没有警告。那条坑已经在两个项目上见过,可以升进 `SKILL.md` 正文(V18)。
示例里的提交号是编的,所以没去 git 里查(V08d;加上 `--repo <git 仓库>` 就会查)。

## 写错了会怎样

[`examples/demo-skill/`](examples/demo-skill) 就是同一个包故意改坏 6 处,
`diff -r examples/good-skill examples/demo-skill` 能看到每一处。这是 whetstone 里负责说「不」的部分:
置信度按一张规则表算,不看模型的感觉;只在一个平台见过的经验进不了 skill 正文;
事实只能追加并标明被替代,不能悄悄改掉。这些都不是写在文档里的一段话,是 `whetstone verify`,
不合格就返回非零退出码。

<!-- output: whetstone verify examples/demo-skill --brief -->
```console
$ whetstone verify examples/demo-skill --brief

whetstone verify — examples/demo-skill

ERROR (5)
  ✗ SKILL.md:31  [V16] [溯源] 复现记录 has two lines for the same platform/project: 'soc-x'
  ✗ SKILL.md:31  [V12] [溯源] L2 claims 置信度 high, the table allows only low — 复现记录 has 1 line(s), needs 2 (single-platform L1/L2 is capped at low — the §7 constraint outranks the table)
  ✗ pitfalls.md:5  [V14] [从上层状态反推底层状态会看错] 复现记录 is a bare count 「2 次」
  ✗ pitfalls.md:5  [V12] [从上层状态反推底层状态会看错] L2 claims 置信度 high, the table allows only low — 复现记录 has 0 line(s), needs 2 (single-platform L1/L2 is capped at low — the §7 constraint outranks the table)
  ✗ params/soc-x.md:6  [V10] [存储起始位置] L3 claims 置信度 high, the table allows only low — 验证方式 never passed a test; 复现记录 has 1 line(s), needs 2

WARN (3)
  ! SKILL.md:18  [V19] concrete value in the body (hex address/value): '0x1A40'
  ! SKILL.md  [V25] no section says what must NEVER be done in this domain
  ! params/soc-x.md  [V22] no 替代记录 section

INFO (1)
  i demo-skill  [V08d] 2 commit hash(es) cited in 来源 / 复现记录, none checked against git

summary: 5 error(s), 3 warning(s), 1 info
```

改坏 6 处,查出 8 条。5 条错误依次是:同一个平台记了两次,冒充在两个平台复现过 ·
一条做法只在一个平台见过却标了 `high` · 复现记录写成一个数字而不是一条条记录 ·
同上 · 一个平台值从没实测过却标了 `high`。3 条警告:正文里写了该放进 `params/` 的具体值 ·
没写这个领域绝不能做什么 · 没有替代记录。去掉 `--brief`,每一条下面会多一行它依据的规则。

INFO 那一条说的是有一项检查没跑。示例里的提交号是编的,加上 `--repo <git 仓库>`,
每个都会变成错误(V08c):出处指向一个谁也找不到的提交,等于没有出处。不给 `--repo` 就不查,
但会说一声没查。

上面两段输出都是真实运行的结果,自检会重跑一遍,和 README 对不上就报红;
前面摘的那几段也会逐行和原文件比对。字段名保留中文,因为你要改的文件里就是这么写的。

---

> 第一次拿它检查一个真实的库时是什么样:
> [**我标了 61 条「高置信」,没有一条说得出是怎么验证的。**](https://doc.tbusos.com/whetstone/why-verify.html)

## 为什么还要再做一个

skill 库坏掉的时候不会报错。它会慢慢装满看着有道理、没法证伪、曾经对过的建议,
而且还挂着「高置信」的标签。半年后你分不清哪些条目是真有用的,哪些只是传说,
读这些条目的模型也分不清。

所以要问的不是「agent 能不能写出一个 skill 文件」,而是**这条流程拒绝做什么**:

| whetstone 不做的事 | 为什么 |
|---|---|
| 自动写进库 | 提案先放进 `inbox/`。两道人审:**挖得对不对**,然后**进不进库**。 |
| 没有一条真跑通过的检查,就标 `high` | 没法证伪的说法挂着高置信标签,正是一条规矩悄悄过期时的样子。 |
| 把只在一个平台见过的教训升进正文 | 一次可能是巧合。要在第二个不同的平台再见到,否则留在 skill 正文之外。 |
| 同一个项目算两次 | 复现记录按平台 / 项目记,一个项目跑十次也只算一行;不然回写就成了绕过升级门槛的后门。 |
| 悄悄改掉一个事实 | 只追加,并标明被替代,安全相关和改了就回不去的值尤其如此。 |
| 自己给自己打分 | 质检在另一个上下文里做。没有引导的 LLM 评委在两个 skill 里挑更好的那个,准确率 46.4%,和掷硬币差不多([SkillLens,Microsoft](https://microsoft.github.io/SkillLens/))。自评偏差是这个设计默认会有的,不是希望能避开的。 |
| 把写在文档里当成执行了 | 上面每条规矩里能机械判断的部分,都是 `whetstone verify` 里的一项检查。 |

## 置信度是一张表,不是感觉

| 等级 | 条件 |
|---|---|
| `high` | 可执行的检查**跑通过**,**并且**在 ≥2 个不同的平台 / 项目上复现过 |
| `med` | 在 ≥2 个不同的平台 / 项目上复现过;**或者**验证通过一次,但这条路只对 L3 事实开放 |
| `low` | 其余情况 |

一条做法验证过一次,不说明它到处都成立。所以只在一个平台上见过的 L1 / L2 条目,即使检查通过,
置信度也封顶 `low`。人审可以把任何条目往下调,但**绝不能**越过条件往上调。`verify` 就是照这个
不对称实现的:超过上限是错误(ERROR),低于上限只是提示(INFO)。

## 它有意不判的东西

把本来不能机械判断的事硬做成检查,只会制造误报。下面这些留给人审,
`whetstone verify --explain` 会把这条边界完整打出来:

- 一条 L1 条目是不是真的没有例外
- 一条 L2 教训去掉所有平台专属的值之后还成不成立
- 矛盾是被如实保留了,还是被平均掉了
- 这次会话该回写的复现记录有没有回写(要看会话,只看包看不出来)
- 拿不准的时候,条目是不是往低处放了(只看得到结果,看不到当时怎么想的)
- 禁止清单里写的是真会出事的动作,还是凑数的空话(V25 只看得到这一节在不在,看不到写得好不好)

`--explain` 还写明了每项检查比它服务的规矩窄在哪。比如溯源是按声明过的记录查的,
`SKILL.md` 正文里一条完全没写溯源的裸条目,`verify` 看不见。

还有一条边界在整张清单之外:上面每项检查问的都是知识**是不是真的、能不能追溯**,
没有一项问「装上这个包,使用者是不是变强了」。这两件事不能互相预测:SkillLens 的语料里
25% 的「提取方 × 使用方」组合出现了负迁移,看文本像不像样也预测不了有没有用。
所以检查全过只说明证据纪律守住了,不说明这个 skill 好。

## 四层

只用一把尺子:**这条知识能走多远?** 完整定义见
[`references/extraction-framework.md`](references/extraction-framework.md)。

| 层 | 范围 | 放在哪 |
|---|---|---|
| **L1** 原理 | 换任何平台、任何厂商都成立;是客观约束,不是你的选择 | `SKILL.md` |
| **L2** 做法 / 坑 | 换了平台还成立,但这是**你的**做法 | `SKILL.md` · `pitfalls.md` |
| **L3** 平台事实 | 换平台就会变:地址、长度、工具名 | `params/<平台>.md` |
| **L4** 状态 | 下次会话就会变:当前用的钥、当前 HEAD、哪块板子 | 记忆,带时间戳 |

一条坑从来不只属于一层。它是一条能带走的教训(L2),**加上**一个只对一个平台成立的事实(L3)。
不拆开是硬错误:把教训和平台绑在一起,同一个坑就得踩两次。

换一个新平台,只加一个 `params/` 文件。做法改进了,只改一行 L2,每个平台都跟着受益。
这里说的「越用越好用」就是指这个不对称。

## 安装

whetstone 本身就是一个 Agent Skill(`SKILL.md`)加几份参考文档。把整个目录放进你所用运行时的
skills 目录就行:Claude Code、Codex、Cursor,或者任何读 Agent Skills 目录结构的运行时。
不绑定某一个运行时,也不用装别的东西:命令行是 bash,检查只用 Python 标准库,
产出的全是普通 markdown。

```bash
git clone https://github.com/TbusOS/whetstone.git
cd whetstone
bash bin/verify_selftest.sh                       # 40 项检查的自检
bash bin/verify_mutation_test.sh                  # 逐条删掉检查,自检必须报红
./cli/whetstone verify examples/good-skill --brief
./cli/whetstone verify examples/demo-skill --brief
```

自检对每一项检查都测**两个方向**:坏的样例必须报,好的样例必须不报。还有一道覆盖检查:
任何一个公开的检查码缺了其中一个方向,整个自检就失败,所以「每项都测了两个方向」这句话不会
慢慢变成假话。故意改坏测试会逐个删掉检查逻辑,要求自检报红:删掉一项检查什么都没变,
说明它根本没被测到,这时候自检全绿反而是在报一个不存在的安全。三次独立评审找到了四种绕过
升级门槛的办法:去掉分隔符、标题里只是提到了「L3」、平台名后面加括号、表格不以竖线开头。
现在每一种都是一条故意改坏的测试。

故意改坏的那一处也可能没改上,因为它要改的那段原文已经变了。这样的一条什么也证明不了,
以前既不算抓到也不算漏掉,于是某项检查悄悄不再被测,整套测试照样全绿。现在它单独计数,
并且会让测试失败。这一点验过:故意弄坏一条的定位原文,测试确实报红。

可选,都不是必须的:会话采集([`adapters/capture/`](adapters/capture/README.md))、
更新提示(`bash autoupdate/install.sh`)、下游同步([`adapters/sync/`](adapters/sync))。

## 使用

1. 做完一个功能 → 触发提炼(`/distill`,或者说「把这次会话提炼一下」)。
2. 审提案,两道关:**挖得对不对?** 然后 **进不进库?**
3. 对包跑 `whetstone verify`,再用 `whetstone promote` 装进你的库。

读会话记录是 agent 的活,在你的运行时里做。它前后那些确定性的步骤都是命令行:

```bash
whetstone verify <包> --strict      # 证据纪律:负责说「不」的就是它
whetstone verify <包> --repo <目录> # 另外查:出处里写的每个提交号都要在这个仓库里存在
whetstone verify --explain          # 全部 40 项检查、各自的边界、留给人判断的部分
whetstone lint --src ~/skills       # 菜单卫生:描述重叠、名字撞车、描述太含糊,
                                    # 以及整张菜单放不放得下(menu-snapshot | lint --listing -)
whetstone index --src ~/skills      # 分组目录
whetstone promote <提案>            # 装一个提案;库里已有同名的,拒绝覆盖
whetstone pack | deploy             # 把库搬到另一台机器
whetstone sync engram <skill>       # 可选:把一个 skill 推进本地的 engram 记忆库
whetstone decision add …            # 记下你对一个提案的决定和理由
whetstone decision stats            # 这些决定开始指向什么
whetstone decision alias --from … --to …   # 把同一个意思的两种写法合并
whetstone find "<你要做的事>"       # 哪些 skill 合适;没有合适的就直说没有
whetstone route events | whetstone route learn --events -   # 从过去的会话里学你是怎么问的
whetstone route replay --events <文件>      # 按时间顺序,在过去的会话上给一个路由改动打分
whetstone route plan --project <目录>       # Claude Code:让主要在别处用的 skill 让位(只打印;--write 才合并)
```

`lint` 和 `verify` 防的是两种不同的坏法。`lint` 防**找错**:库里描述互相重叠,模型就会挑错 skill。
`verify` 防**信错**:库里条目挂着没挣来的置信度,模型就会相信错的东西。

`decision` 两样都不防,它只记录。审一个提案会产生一个判断:照原样保留、往下挪一层、降级、拒绝。
每一个判断都说明了框架和你在哪里想法不一样。这些以前随会话结束就没了。它们是这个工具唯一
白来的标注,也是框架将来能靠自己的证据(而不是靠下一篇有人读到的论文)改进的唯一原料。
它目前什么都不分析:它有意不做什么,见 [`spec/review-decisions.md`](spec/review-decisions.md)。

`find` 和 `route` 防的是**够不着**:库大到一定程度,运行时给模型看的菜单就放不下了,
丢了描述的条目在相关话题出现时不再被选中(在一台机器上实测:有描述的 26%,没描述的 1%)。
路由用运行时自带的开关让菜单变短,剩下的交给一条任何 agent 都能跑的搜索命令,并且从过去的会话里学,
不用钩子。核心只读一种中立的事件格式,所以每个运行时要一个适配器:**Claude Code 的已经写好并测过;
Codex、opencode、pi、Gemini CLI 和 Cursor 是照着它们的源码设计的,还没写。**
见[路由页面](https://doc.tbusos.com/whetstone/routing.html)和 [`spec/routing.md`](spec/routing.md)。

一个标签只有在同一个意思一直用同一个字符串时才会攒起来。所以你第一次用一个新标签时,`add` 会把
已有的词表摆出来;事后 `alias` 再把两种写法合并,合并发生在读取时,存下的每一行一个字节都不改。
它不会做的是猜:在这份词表上实测,没有哪个相似度阈值能把 `priority-wrong` / `priority-mistake`(0.60)
和 `missing-feature` / `missing-split`(0.643)分开,词序颠倒或换一种语言更是直接失效。
排序错了只多看一眼,合并错了就把信号毁了。

## 目录

```
SKILL.md                            提炼器入口(Phase 0-5)
references/extraction-framework.md  L1-L4 分层规则,真正的核心
spec/skill-package.md               可移植 skill 包的格式(交付物)
spec/review-decisions.md            一条人审决定记录长什么样,以及它的边界
spec/routing.md                     经验路由:三层、中立事件格式、六个运行时
commands/                           /distill 和 /promote 两个斜杠命令的定义
bin/verify.py                       证据纪律,做成可执行的检查
bin/verify_selftest.sh              自检:每项检查两个方向都测,带覆盖检查
bin/verify_mutation_test.sh         逐条删掉检查,自检必须报红
bin/decision.py                     人审决定记录(只记录)
bin/decision_mutation_test.sh       逐条删掉 decision 的检查,自检必须报红
bin/lint.py · bin/index.py          菜单卫生,包括整张菜单放不放得下
bin/lint_selftest.sh                lint 自检,两个方向都测;lint_mutation_test.sh 逐条改坏
bin/route.py                        路由核心:find / learn / usage / replay / elsewhere(不绑定运行时)
bin/route_selftest.sh               路由自检,两个方向都测;route_mutation_test.sh 逐条改坏
bin/pack.sh · bin/deploy.sh · bin/promote.sh   搬包、装包
cli/whetstone                       不绑定运行时的命令行,纯 bash
templates/                          提炼出的 skill / params / pitfalls 的骨架
examples/good-skill/                写对的包:开头逐段讲的就是它
examples/demo-skill/                同一个包故意改坏 6 处,verify 演示用的就是它
inbox/ · journal/                   等待审核的提案;挖出来的原始材料
adapters/capture · adapters/sync    可选:会话采集、下游同步
adapters/menu                       运行时实际发出的菜单,以及把它的会话转成中立事件(Claude Code)
adapters/levers                     按路由学到的结果去设运行时自己的菜单开关(Claude Code)
autoupdate/                         可选:多个命令行工具的更新提示
docs/                               doc.tbusos.com/whetstone 上的项目页面
```

## 配套项目

| 项目 | 补上什么 |
|---|---|
| [whetstone-curator](https://github.com/TbusOS/whetstone-curator) | 团队侧:从队友的库里挑好条目,或者收进一个共享库 |
| engram | 把一个包同步进本地记忆库([说明](adapters/sync/engram.md);能做什么是对照它的代码核过的,不是照它的 README) |
| llm-wiki | 把知识发布成给人看的页面([说明](adapters/sync/llm-wiki.md);只有文档,还没有脚本) |

更多背景见项目页面:**https://doc.tbusos.com/whetstone/**

## 许可

MIT,见 [LICENSE](LICENSE)。

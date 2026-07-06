# CLAUDE.md 分层设计(可复用)

把 agent 的持久指令按「是否每轮都需要」分层,让常驻的全局 `CLAUDE.md` 保持精简、中性;
重的、领域相关的内容改成按需加载。换任意机器都能用同一套 `deploy.sh` 复现。

## 为什么要分层

- 全局 `~/.claude/CLAUDE.md` **每轮常驻**(全文进上下文)。往里堆得越多:① 吃 token、降指令遵循度;② 内容密度过高时容易触发服务端安全分类器误报(尤其含大量 dual-use 技术词时)。
- 解法:只有「无触发词、每轮都要生效」的中性规则留在全局;其余按需加载。

## 四层

| 层 | 存放 | 何时加载 | 放什么 |
|---|---|---|---|
| **全局常驻** | `base/conduct.md` → 生成 `~/.claude/CLAUDE.md` | 每轮 | 通用中性行为约束(署名规矩、诚实/查证纪律、权限、secret 处理、风格) |
| **按需 skill** | `skills/<name>/`(symlink 自数据仓) | 触发词命中才载入正文 | 领域方法 / 流程;正文平台无关 + `params/<platform>.md` 放具体值 |
| **组织共享** | `base/<org>-common.md` | 项目 `CLAUDE.md` 里 `@import` | 跨产品共享的开发约定(提交规范、脚本/编译环境、路径规矩) |
| **项目状态** | `<project>/CLAUDE.md` | cd 进该目录 | 当前任务 / 关键路径 + `@import` 组织共享层 |

**铁律:常驻行为约束不能做成 on-demand skill。** skill 要触发词才载入;像「禁某类署名」「输出风格」这种每轮都要生效、又没有触发场景的规则,做成 skill = 大多数轮次不触发 = 静默失效。这类只能留在常驻层。

## 机制:`deploy.sh` 三模式

```bash
# 1) 部署 skills:从数据仓 symlink 进 ~/.claude/skills(单一真相,改一处即生效)
bin/deploy.sh --link <data-repo>

# 2) 生成全局常驻文件:base/conduct.md → ~/.claude/CLAUDE.md(自动备份旧的)
bin/deploy.sh --gen-claudemd <data-repo>

# 3) 让某项目 CLAUDE.md 导入组织共享层(幂等,--import 传任意共享文件的绝对路径)
bin/deploy.sh --add-import <project>/CLAUDE.md --import <data-repo>/base/<org>-common.md
```

## 换新机器 runbook

```bash
# a. 拉工具仓(本仓)+ 数据仓(你的私有 skills 仓,内含 base/ 和 skills/)
git clone <this-tool-repo>
git clone <your-private-skills-data-repo>   # 含真实值就保持 private

# b. skills symlink + 生成全局常驻文件
whetstone/bin/deploy.sh --link  <data-repo>
whetstone/bin/deploy.sh --gen-claudemd <data-repo>

# c. 每个项目:建/补 <project>/CLAUDE.md(项目状态)+ 导入组织共享层
whetstone/bin/deploy.sh --add-import <project>/CLAUDE.md \
                        --import <data-repo>/base/<org>-common.md

# d. 每个项目首个 session:会弹一次「外部导入」批准框(项目目录外的 @import),点同意,以后不再弹
```

## 注意

- `@import` **启动时全量载入,不省 context**;它的价值是「单一真相 + 组织」,不是省 token。真正「不触发不载入」的是按需 skill。所以重内容留 skill,别 @import。
- 全局常驻层保持**中性、低密度**——这是控制误报的关键,不是靠机制绕过分类器。
- 数据仓若含真实值(内部路径 / 组织名 / 平台参数),**设 private**;工具仓(本仓)保持通用、可公开。
- 多根项目(代码和笔记在不同挂载点):每个根放一个 `CLAUDE.md`,薄的那个只 `@import` 主 hub 即可。

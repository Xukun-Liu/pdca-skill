---
title: pdca-skill 版本历史
version: v1.0.2
last_updated: 2026-08-19
author: huihui
---

# pdca-skill 版本历史

> 本文件记录 pdca-skill（前身 riji-skill，再前身 huihui-skill）从 2026-06-27 诞生到 2026-07-21 公开发布版的完整进化历程。
> 不是冷冰冰的变更日志,而是一份带温度的"成长档案"——记录每一次重构、每一轮对抗审查、每一个深夜踩坑后顿悟的瞬间。

---

## 一、作者寄语:为什么会有 riji-skill

riji-skill 不是一夜之间写出来的,是**耗时两个月、花费 1036 元 token 费用（后转为trae免费版开发）、每天都在打磨**才出来的沉淀。其中核心高强度开发期连续 16 天、47 个关键节点、34 轮对抗审查,但前后的思考、调研、调整从未停止。**花费 1036 元 token 费用后,开始使用 TRAE 免费版继续开发**——工具在变,打磨的节奏从未改变。

它起源于一个简单的诉求:**"我需要的是不断进化的"**。2026-06-29 那天,刘工的一句反馈让我重新理解了"进化"——不是工程测试,而是使用中持续自我改进的闭环(感知→沉淀→进化→反馈)。从那天起,huihui-skill 从一份"静态规则文档"踏上进化之路,经历了:

- **从 v1.0 到 v4.0 的规则膨胀期**(6/27-7/10):整合 Superpowers 160K 星、Karpathy 170K 星、planning-with-files 45K 星等 6+ 顶级项目经验,经历 13 轮对抗性审查迭代
- **从 v4.0 到 v1.0 公开发布的收敛期**(7/11):21 轮对抗审查 HIGH 连续 4 轮清零,才敢说"可以发布了"
- **从 huihui-skill 到 riji-skill 的蜕变期**(7/12-7/21):落地自生长四道安全锁、红队 13 攻击场景全拦截、PDCA 4 环脊柱模型

> **riji-skill 是工作方法的长期沉淀。它不是"借来的工具",而是协作宪法——7 条铁律、HARD-GATE、Memory First、触发钩子表、references/ 下的参考模块,都是过去反复踩坑后固化下来的规则。**
> —— 摘自 SKILL.md 用户画像

---

## 二、版本时间线(双线进化图谱)

### A 线:huihui-skill / riji_skill 协作宪法(SKILL.md 框架)

```
2026-06-27  v1.0       初版(从 agent.md 转换)
2026-06-28  v1.4       静态规则文档阶段
2026-06-29  v1.5       自进化引擎诞生(感知→沉淀→进化→反馈四层闭环)
                       ── 刘工反馈"我需要的是不断进化的",重新理解进化定义
2026-06-30  v1.6       顶级对标升级(Superpowers 160K + Karpathy 170K + planning 45K)
2026-06-30  v1.7       思维导图导航体系(8 处纯文本缩进导图)
2026-06-30  v1.8       渐进式披露触发保证五层防御
2026-06-30  v1.9       高星项目对标(5 条铁律精简版 + 冷记忆生命周期 + evals.json 15 用例)
                       ── 一天完成 4 版本升级的高强度开发
                       ─────── 7 天空窗期(产品方向调整 + riji MCP 主线) ───────
2026-07-06  v2.0       移除自进化引擎 §12,新增 §0.5/§3.5/§12
2026-07-06  v2.1       内嵌 find-skills 工作流
2026-07-08  v2.2       分类文件夹结构 + generate_docs.py
2026-07-08  v2.3       移除硬编码 Skill 清单,改动态搜索
2026-07-08  v2.4       内嵌 vercel-labs/skills find-skills 13.1K stars
2026-07-08  v2.5       全面升级代码规则体系(9 章 + 6 种设计模式)
2026-07-09  v2.6       融入 neat-freak sync-matrix 概念
2026-07-09  v2.7       触发钩子表全行关键词扩写(2-3→10+ 个)
2026-07-09  v2.8       融入 HTML 报告生成能力
2026-07-09  v2.9       融入 /plan 硬指令
2026-07-09  v3.0       新增文件变动声明硬性规则 §2
2026-07-09  v3.1       Bootstrap 引导式初始化 + 重构 memory 体系
2026-07-09  v3.2       版本历史外置为独立 HISTORY.md
2026-07-09  v3.3       "回溯保障"提升为第 6 条铁律(5→6 条)
2026-07-09  v3.4       find-skills 改 WebFetch/WebSearch 零依赖
2026-07-09  v3.5       新增 SUMMARY.md 根索引
                       ── 一天完成 10 版本升级
2026-07-10  v3.6       grill-me 逻辑审查修复(17 H+32 M)
2026-07-10  v3.7       新增「主 docs 目录」概念 + 散落归档机制
2026-07-10  v3.8       grill-me 第二轮审查修复(11 H+M)
2026-07-10  v3.9       命名空间隔离(_hh/_HH 后缀,65+177+26 处替换)
2026-07-10  v4.0       第一性原理拆解 + 对抗性审查 6 维度 13 轮迭代
                       ── 一天完成 5 版本升级 + 13 轮对抗审查
                       ─────── 整合期 ───────
2026-07-11  v1.0       🎯 首个公开发布稳定版(21 轮对抗审查,HIGH 连续 4 轮清零)
2026-07-11  v1.1       控制平面定位升级(SKILL.md 844→793 行,-51)
2026-07-11  v1.2       控制平面深化(SKILL.md 793→669 行,-124)
2026-07-11  v1.3       控制平面收尾(SKILL.md 669→635 行,-34,150/150 全绿)
2026-07-11  v1.4       脊柱模型 + 参考模块阶段标签(22 个 references)
2026-07-11  v1.5       校验增强 ROUT-03(检查数 15→16)
2026-07-12  v1.0.0     riji_skill v1.0.0(改名 huihui-skill → riji_skill,落地四道安全锁)
                       ─────── 9 天稳定期 ───────
2026-07-21  v1.0.0     🚀 riji-skill-public v1.0.0 公开发布版
                       PDCA 4 环脊柱模型 + 10 副 agent + 8 要素启动检查
2026-07-31  v1.0.0     吸收 i-have-adhd（MIT, Ayoub Ghriss）输出节奏规则
                        ── 评审 https://github.com/ayghri/i-have-adhd 后融合
                        ── 新增 SKILL.md §2.1：首行动作/尾行下一步/时间估计具体化/发送前自检
                        ── 按 PDCA 阶段差异化适用（/plan 不适用，/do/check/act/问答适用）
                        ── 不采用 #9 列表上限 5（与 riji-skill 长表格载体冲突）
2026-08-01  v1.0.0     新增「任务启动 Git 管理询问」（用户反馈融合）
                        ── 复杂任务开工前问 2 问（工作区状态/分支策略）+ 3 默认值（git init/WIP commit/任务 tag 默认打）
                        ── 简单任务轻量 git status 检查，脏才问，不啰嗦
                        ── 落点：SKILL.md §6 /plan 步骤3 + git_workflow §6.5 + spec_template §0.G
                        ── 6 条规则 riji-skill 已覆盖不重复（#2/#4/#5/#7/#8/#10）
2026-08-06  v1.0.1     文件扫描确认门控（security.md L2：任务外扫描先确认范围+目的+关键词）
                        ── 技能图谱自动化（--auto 每轮 /act 3.6a 自动刷新）+ 数据外置 ~/.riji-skill/data/
2026-08-11  v1.0.1     Excel 分析能力系统性升级（当时未登记，v1.0.2 补登）
                       ── excel_analysis.md v1.0.0→v1.3.0：新增 7 章 + 从 4 个外部 skill 提炼 9 项方法论；4 个配套文件交叉引用闭环
2026-08-13  v1.0.1     融合 HTML/PPT 制作（自包含方法论，内网可用）
                       ── 新增 references/do/code/html_ppt_creation.md：PPT 用 python-pptx/PptxGenJS 生成可编辑 .pptx + 六风格视觉配方；HTML 幻灯片手写单文件；HTML 网页手写 + 前端设计五原则；图表手写 SVG；内网边界明确
                       ── trigger_hooks 新增 2 触发钩子行（v1.1.4→v1.1.5）；index 47→48；README/网页说明/subagents 登记；版本不 bump 保持 v1.0.1
2026-08-19  v1.0.2     🚀 pdca-skill-public v1.0.2 公开发布版（当前版本）
                       两批能力升级（Excel v1.3.0 + HTML/PPT 模块）+ 发布瘦身（缓存/私人数据/占位外链清理）
```

### B 线:日积 riji MCP / 产品(Python 实现,独立于 SKILL.md 框架)

```
2026-07-02  v3.0→v3.1  日积集成版(合并 huihui-mcp + riji_demo,11 MCP 工具)
2026-07-02  v3.2       /riji prompt 优化(STAR 结果导向 + 同事式聊天)
2026-07-02  v4.0.0     架构澄清 + 文件结构整理(42 项检查全过)
2026-07-02  v5.0.0     产品方向调整:专注技能积淀(删除 daily,激活 skills)
                       ── 一日 11 对话大重构
                       ─────── 2 天空窗期 ───────
2026-07-04  v7.0.0     baseline 快照(四层记忆金字塔 + BM25+BGE-M3 + 73 MCP + 55 测试)
2026-07-04  v7.0→v7.3  P0/P1/P2 改进(L1 主动遗忘 + 关系图谱 + JSONL + CI/CD + 237 测试)
                       ── 一天 13 次 git 提交
2026-07-05  v7.3       14 项升级 + bat 转 Python + 工具描述优化
2026-07-05  v7.4       修复 51 个测试失败 + 代码卫生清理
2026-07-06  v7.4       前端错误诊断与修复(防御性编程 +207/-86 行)
2026-07-07  v7.4       P1/P2 收尾 + QA 16/16 PASS + 项目结构梳理
2026-07-08  v8.0.0     版本号对齐 + Dashboard 崩溃修复(v7 兼容层)
2026-07-09  v8.1       记忆管理页修复 + 重复标签页删除
2026-07-11  v9.0.0     MCP 彻底移除(决策!),分层架构,79 REST API
2026-07-12  v10.0.0    v10 融合版 + riji_skill 自生长机制(四道安全锁 + 红队 13 攻击全拦截)
```

---

## 三、关键技术突破(18 项难题攻克)

| # | 时间 | 突破 | 解决了什么难题 |
|---|---|---|---|
| 1 | 2026-06-29 | **自进化引擎四层闭环** | 从"静态规则文档"升级为"使用中持续自我改进的闭环"(感知→沉淀→进化→反馈) |
| 2 | 2026-06-30 | **顶级对标整合** | 整合 Superpowers 160K 星 + Karpathy 170K 星 + planning-with-files 45K 星经验,建立 HARD-GATE/No Placeholders/TDD-for-Skills 等执行纪律 |
| 3 | 2026-07-02 | **径向树思维导图** | 替换力导向图,BFS 分层 + 叶子数权重 + 扇区角度分配,知识可视化有清晰层级 |
| 4 | 2026-07-02 | **VSCode 三栏布局重构** | 活动栏 48px + 侧边栏 260px + 主编辑区 flex:1,支持 6 页面混合模式渲染 |
| 5 | 2026-07-02 | **Python 三引号 JS 转义踩坑修复** | 定位 `\'` 被 Python 消耗为 `'` 导致 JS SyntaxError,用 `node vm.Script` 验证语法,改为 `\\'` 修复 |
| 6 | 2026-07-04 | **四层记忆金字塔 + 混合检索** | L0 对话→L1 原子事实→L2 场景→L3 全局配置,BM25 + BGE-M3 1024 维语义匹配 |
| 7 | 2026-07-04 | **冷记忆膨胀三层防护** | 入库去重(0.90 阈值)+ 总量上限(1000 条)+ 归档真删(365 天) |
| 8 | 2026-07-04 | **记忆检索优化(RRF 融合)** | 多路检索(向量/关键词/标签/时间)+ RRF 融合(k=60)+ 综合重排四步流程 |
| 9 | 2026-07-01 | **集中式记忆架构** | 对标 Mem0 55K 星,纯文件系统实现全局+项目双层隔离,100% 向后兼容 |
| 10 | 2026-06-30 | **进化信号三分类 + Misevolution 防御** | learnings/errors/feature_requests 三信号 + 6 条核心不变量 + 灰度期 3 次对话观察 |
| 11 | 2026-07-10 | **17 轮 grill-me + 13 轮对抗审查** | 修复指令优先级矛盾/衰减信号不可观测/命名空间撞车等问题,adversarial_review.md v1.3→v2.4 |
| 12 | 2026-07-11 | **MCP 彻底移除决策** | v9 中 MCP 协议冗余,改为 REST API + CLI 架构,grep 返回 0 匹配 |
| 13 | 2026-07-12 | **riji_skill 自生长四道安全锁** | 铁律哈希锁死 + diff 确认闸门 + 改前快照 + 经验待审人审晋升,红队 13 攻击场景全拦截 |
| 14 | 2026-07-07 | **QA agent 超轮次 fallback 亲验法** | 专用 QA agent 连续两次超轮次(18/20),改用系统 Python + monkey-patch 亲验 16/16 PASS |
| 15 | 2026-07-12 | **路径漂移治本** | 12 文件约 80 处旧名引用 → 批量转相对路径,以后目录改名也不怕 |
| 16 | 2026-07-11 | **手绘呈现能力** | 撤除 HTML 报告,借鉴 hand-drawn-note-generator 设计思想 clean-room 重写,5 受众模式 + 7 关系类型 |
| 17 | 2026-07-11 | **agent-find + Exa REST 直连** | 改名 find-agent→agent-find,修复 Exa score bug,增强 key 多位置自动探测 |
| 18 | 2026-07-21 | **PDCA 4 环脊柱模型 + 10 副 agent** | /plan→/do→/check→/act 循环 + /loop 第 5 触发词 + L1/L2 任务等级 + 10 副 agent 只读调研架构 |

---

## 四、付出记录(可量化的努力证据)

### 4.1 整体投入(最核心的付出证据)

| 指标 | 数据 | 说明 |
|---|---|---|
| **总耗时** | **两个月** | 从构思到公开发布,每天都在打磨,从未停止 |
| **token 费用** | **1036 元** | 纯 AI 协作成本,每一分都花在打磨规则上 |
| **高强度开发期** | **连续 16 天** | 2026-06-27 至 2026-07-12 核心开发无中断 |
| **单日最高版本密度** | **10 版本/天** | 2026-07-09 一天完成 huihui-skill v2.6→v3.5 |
| **单日最高 git 提交** | **13 次/天** | 2026-07-04 v7.0→v7.3 阶段 |
| **单日最高对话数** | **11 对话/天** | 2026-07-02 riji MCP v3.0→v4.0 大重构 |

### 4.2 对抗审查轮数(质量打磨)

| 阶段 | 审查轮数 | 结果 |
|---|---|---|
| huihui-skill v4.0 | **13 轮** | 修复 4H+15M → 4H+15M → ... → 4H+15M,adversarial_review.md v1.3→v2.4 |
| huihui-skill v1.0 公开发布 | **21 轮** | HIGH 连续 4 轮清零才发布 |
| riji_skill 自生长机制 | **红队 13 攻击场景** | A1-E2 全拦截,PROTECTED 区哈希全程恒定 `caf390...` |
| **合计** | **34+ 轮对抗审查** | 用最严苛的标准打磨每一行规则 |

### 4.3 代码与文档规模

| 指标 | 数据 |
|---|---|
| SKILL.md 控制平面瘦身 | 3 轮 -209 行(844→793→669→635) |
| 前端防御性编程 | +207/-86 行(2026-07-06) |
| P1/P2 代码改动 | 4 files +563/-17 行(2026-07-07) |
| 命名空间隔离 | 65+177+26 = 268 处路径替换(2026-07-10) |
| 测试覆盖扩充 | 114 → 237(2026-07-04) |
| 测试失败修复 | 51 个(2026-07-05) |
| 数据库清理 | 1213 → 62 条(2026-07-05) |
| "日记→日积"改名 | 66 处(dashboard.py 6 + db.py 1 + 说明书 45 + DB 14) |
| 路径漂移治理 | 12 文件约 80 处(2026-07-12) |

### 4.4 最终交付物规模(riji-skill-public v1.0.0)

```
1  SKILL.md            协作宪法主文件
35 references          参考手册(按需加载)
11 assets              文档模板
36 evals               行为测试用例
35 scripts             自动化脚本
18 tests               代码测试
 9 protocol 模块        协议层常量
 4 server_lite 模块    本地 Web 服务
10 agents_rj           副 agent 配置
```

---

## 五、关键决策点(产品方向与架构选型)

| # | 时间 | 决策 | 理由 |
|---|---|---|---|
| 1 | 2026-06-29 | 从"静态规则文档"升级为"自进化协作框架" | 刘工反馈"我需要的是不断进化的",重新理解进化=使用中持续自我改进的闭环 |
| 2 | 2026-06-30 | TDD-for-Skills 进化铁律 | 无失败案例不加新规则,防止规则膨胀 |
| 3 | 2026-07-02 | "日记→日积"改名 | 刘工定名:"日积,工作日志,每天收获" |
| 4 | 2026-07-02 | 产品方向从"日记+技能"调整为"专注技能积淀" | 删除 daily 相关,激活 skills 表 |
| 5 | 2026-07-02 | 图谱页用力导向图→径向树思维导图 | 力导向图节点散落无层级,径向树有清晰层级 |
| 6 | 2026-07-06 | 前端修复采用防御性编程,不改后端 | `(obj && obj.field)\|\|default`,避免连锁影响 |
| 7 | 2026-07-06 | 工作区整理采用"增量式归档" | Chesterton's Fence 原则——不理解文件为何存在前不擅自移动 |
| 8 | 2026-07-07 | QA agent 失败时主理人改用系统 Python 亲验 | 专用 QA agent 连续两次超轮次(18/20)未产出 |
| 9 | 2026-07-09 | "回溯保障"提升为第 6 条铁律 | 动手改前必须确保工作区已 commit |
| 10 | 2026-07-10 | 命名空间隔离(_hh/_HH 后缀) | 避免与各大 agent 平台通用命名撞车 |
| 11 | 2026-07-11 | MCP 功能彻底移除(v9 决策) | MCP 协议冗余,REST API + CLI 架构更直接 |
| 12 | 2026-07-11 | huihui-skill v1.0 公开发布版整合 21 轮对抗审查 | HIGH 连续 4 轮清零才发布 |
| 13 | 2026-07-12 | 自生长四道安全锁强制力落代码层 | SKILL.md 文字无强制力,bash 脚本才能真拦住违规写回 |
| 14 | 2026-07-12 | 版本回滚用内置快照,不依赖 git | 环境 git 状态不可控,快照自包含更稳 |
| 15 | 2026-07-12 | 路径漂移治本用相对路径 | 替换目录名只治标,下次改名又漂移 |
| 16 | 2026-07-12 | 产品定位统一:日积(riji)= 完整产品;riji_skill = 轻量内核版 | 区分完整产品和轻量内核,便于分发 |

---

## 六、致谢与展望

### 产品理念

> **开发一个独属于自己、可以不断积累的 skill。**

riji-skill 的初心很简单——市面上的 AI 工具千千万,但都是"借来的工具":换个对话、换个平台,沉淀的经验就丢了。我想要的是**一个能跟着自己成长、越用越懂自己的协作框架**——把踩过的坑、走过的弯路、验证过的工作方式,固化成规则,让每一次对话都站在前一次的基础上。

这不是一次性项目,而是一份**会跟着我持续进化的数字资产**。两个月、1036 元、34 轮对抗审查,打磨的不是代码,是"让 AI 真正为我所用"的工作方式。

### 关键引路人

- **刘工**——2026-06-29 那句"我需要的是不断进化的",是整个自进化引擎的起点

### 对标的开源项目(站在巨人的肩膀上)

riji-skill 的诞生离不开以下开源项目的启发与对标,正是在反复研究这些项目的设计哲学后,才打磨出本框架的规则体系:

| 项目 | 启发的能力 |
|---|---|
| **Superpowers**(160K stars) | 技能触发纪律 1% 原则、HARD-GATE 硬门控、No Placeholders 铁律、Self-Review 四检查、TDD-for-Skills 元规则 |
| **Karpathy**(170K stars) | 四大行为原则 |
| **planning-with-files**(45K stars) | RAM/Disk 心智模型、2-Action Rule、3-Strike 协议、5 问测试 |
| **Hermes Agent**(106K stars) | 三层记忆、Skill 自修补、4 阶段流水线质量审核、background review 信号 |
| **Mem0**(~55K stars) | 三级隔离、集中式记忆服务器、EVERTIME 模式 |
| **anthropics/skills** | skill-creator 设计、evals 官方测试体系、灰度期可观测 |
| **vercel-labs/skills**(13.1K stars) | find-skills 动态搜索机制 |
| **cexll/myclaude** | skill-install 安全扫描 |
| **neat-freak** | sync-matrix 概念(18 个关键词触发) |
| **Letta Memory Blocks** | 冷记忆生命周期管理 |
| **Graphiti Bi-Temporal** | 冷记忆时间维度 |
| **Yuzc-001/hand-drawn-note-generator** | 手绘呈现能力的设计思想(clean-room 重写) |
| **agentmemory** | 集中式记忆服务器架构 |

> 没有这些先行者的探索,就没有 riji-skill 的今天。本框架的每一条规则,都能在这些项目中找到思想源头。

### 设计哲学沉淀

> **"框架 = 反复踩坑固化"**
>
> 7 条铁律不是凭空想出来的,是过去反复踩坑后固化下来的规则。Agent 每次加载本文件,等于加载了已验证的工作方式。
>
> **"治本不治标"**
>
> 路径漂移用相对路径治本,不用替换目录名治标。下次改名也不怕。
>
> **"Chesterton's Fence"**
>
> 不理解文件为何存在之前,不擅自删除。增量式归档,而非暴力清理。

### 未来展望

riji-skill v1.0.0 是一个新的起点,不是终点。框架已具备:
- **自进化闭环**(Learn Cycle 五阶段:scan/mine/gate/reflect/adopt)
- **自生长机制**(四道安全锁 + 红队验收)
- **对抗性审查**(6 维度迭代,确保规则质量)

它会在使用中持续进化——每一次踩坑、每一次反馈、每一次 learn_cycle,都会让它变得更好。

---

## 维护规则

> 每次版本升级在此追加一行,并同步更新 SKILL.md 头部版本号。
> 维护者:pdca-skill 框架自动维护 + 人工审核
> License: pdca-skill 非商业源码可得许可证 v1.0（非商业免费，商用须书面授权）

### 2026-08-01：SKILL.md 结构瘦身（-306 行）

- 去重：记忆双写 3 节合并、导图/判定流程块删除、§1.6/§0.56 压缩
- 下沉 5 模块：/act 细则→act_procedure.md，插入新任务→insert_new_task.md，/loop 完整规则→loop_constraints.md，条目增强格式→working_memory_rules.md §2.2，文件变动声明示例→communication_rules.md
- 索引同步：index.md 补登记 3 遗漏+2 新增→41 模块；trigger_hooks/SKILL.md PDCA 表/资源导图/README 计数 36→41 全链路对齐
- 1391→1085 行（-22%），零规则丢失

### 2026-08-06：文件扫描确认门控（v1.0.1）

- 失败案例：内网环境 AI 可能无确认扫描任务外文件（全盘/共享盘/他人目录），技能图谱功能静默扫 home 并读取 AI 工具记忆目录
- security.md 新增「文件扫描确认门控」：L0 任务内免确认 / L1 点名单文件一句话确认 / L2 任务外先确认（范围+目的+关键词）；敏感命中不引用不转述不持久化；汇报禁止连文件名；L1/L2 记录走 write_project 只记范围目的；脚本轨按扫描根判定；用户可跳过（告知风险+if-then 留痕）
- trigger_hooks.md：安全行加扫描类关键词；skill_graph 行加 L2 确认前置（v1.1.1）
- skill_graph.md：触发确认说明 + evidence_files 豁免声明（功能核心，用户确认）
- README.md：安全表格补门控描述 + 隐私声明
- skill_graph_extract.py：修复非交互模式 bug——未确认目录只记录路径不读取（原为"未确认也读"）
- 决策记录：脚本修复 ✅ / evidence 豁免 ✅ / 硬性规则（非安全不变量）✅ / 只改 public 版 ✅
- 对抗性审查 2 轮：第 1 轮 5 HIGH+9 MEDIUM（白名单绕过门控/excerpt 持久化/main 同名函数必崩/扫描根父链/版本号不同步）；第 2 轮修复验证 11/12 生效，无新 HIGH。修复：白名单豁免声明（用户确认）+ SENSITIVE_PATTERNS 敏感行摘录过滤（词边界+空格变体+sk- 裸值）、删同名占位函数与 main 重复调用、删 cwd 父链扫描根、删 --interactive 死参数、security.md 跳过边界句、skill_graph.md 扫描根清单按代码重写、README 测试数字实测对齐；新增测试 12 项全过（含 main 冒烟/excerpt 过滤/扫描根父链）

### 2026-08-06：技能图谱自动化 + 数据外置（v1.0.1）

- 触发升级：/act 每轮 3.6a 自动刷新 `--auto`（仅左轨 L0 安全级，哈希未变缓存命中零成本；taxonomy 缺失 [SKIP] exit 0；阶段失败 exit 2 不阻断 /act）；用户点名仍走全量双轨 + L2 确认
- 数据外置：缓存/输出/图谱四件套迁至 `~/.riji-skill/data/docs_rj/skill_graph/`（升级不丢图谱）；断链修复（read_riji_memory 单入口）；右轨补真 URL + 适配 roadmap 新仓库结构（真实命中 7879 节点，修复前是 fallback 假数据）
- 提取升级：结构化经验字段置信度加权（复用 memory_distill 解析器，词边界匹配）；CSV 公式注入防护（=+-@、\t、\r、全角变体）
- 质量：新增 tests/test_skill_graph_fix.py 8 测试全过；validate_skill.py / build.py / extract.py 子进程编码修复（utf-8+replace+PYTHONIOENCODING 注入），validate_skill 32/32 MUST FIX=0；全量 pytest 202 项 201 passed + 1 skipped（实测校准，无失败项）
- 对抗性审查 2 轮：第 1 轮 5 HIGH+16 MEDIUM；第 2 轮 fresh subagent 验证 5 HIGH 全部真修复、无新增 HIGH；13 LOW + 7 遗留 MEDIUM 记录到 memory「约定」区块
- 决策记录：砍增量层（80% 复杂度解决 0 成本问题）✅ / --auto 仅左轨遵守自身 L2 门控 ✅ / 保留右轨全景 ✅ / 经验标签只做加权不做采纳（distill 管采纳）✅ / 版本号与门控合并统一 v1.0.1（用户决策）✅
- 配套文档：skill_graph.md §3 双触发、act_procedure.md 3.6a 细则、SKILL.md 3.6a 行、trigger_hooks.md 双语义

### 2026-08-06：融合文章写作模块（v1.0.1）

- 新增：references/common/style/article-writing.md 入口（活人感写作，改造自外部写作技能，不留来源痕迹）+ article-writing/ 5 子模块（forum-prose/reality/fiction/formats/revision）+ scripts/check_prose.py 成稿检查脚本
- 入口带流程覆盖声明（写作任务不走 spec/task、材料澄清 ≤3 问、正文只交作品）与禁令适用范围声明（成稿禁令只约束对外文章，不约束框架文档）
- 路由：trigger_hooks.md 新增文章写作触发行（写文章/写知乎/写公众号/写博客/写小说/写故事/写人物稿/写口播稿/写演讲稿/活人感/文风/长文）
- 全链路对齐：references 41→47、common 16→22、style 1→7（index.md v1.2.0 嵌套例外条款）；README/SKILL.md/网页说明.html 计数同步；顺手修 agent 知识库计数漂移（bootstrap 11→10 / spec_design 5→3 / code_eng 8→7 / doc_proc 5→4，以 subagents_rj.md 正向配置为权威源）+ 3 文件头部引用范围标注对齐
- 决策记录：融合方案 A 整体嵌入 ✅ / 版本 v1.0.1 不 bump ✅ / 双副本 A+B 同步 ✅ / A 顺手 git init ✅ / 不留来源痕迹 ✅（memory 私有留档）

### 2026-08-06：融合收尾对抗审查修复（v1.0.1）

- 对抗性审查第 1 轮（独立 subagent，6 维度）：1 HIGH + 6 MEDIUM + 7 LOW
- HIGH 修复：index.md 计数口径修正（common 21→22、style 6→7、分类规则表 style 行 1→7，入口文件计入；总数 47 口径=除 index.md 外模块数，正确保留）
- MEDIUM 修复：速查表 memory_governance/goal_brief 引用范围列对齐 main（4 处漂移全清）；check_prose.py 抒情词表补"锋利/坚硬/柔软"3 词与 revision.md 对齐；入口流程覆盖声明补"启动前置检查（8 要素）与 memory 收尾按框架常态执行"；revision.md 脚本命令补工作目录说明
- LOW 处置：子模块阶段标签加注、触发词双命中仲裁、exit 2 双语义区分、task 计划文档描述偏差（导航行/4处→5处/33→34 脚本/3→9→12）→ 全部记录在案（本 HISTORY + task 测试结果区），留待后续版本统一处理
- 文档留痕：task/spec 补记 3 文件头部改动登记（执行期顺手修）；grep 验证命令精确化为 `human-writing|khazix`（v1.1.0 为框架版本号不计入）

### 2026-08-06：文章写作触发词补充"去AI味"（v1.0.1）

- 用户要求：去AI味（文章改写润色场景）也要触发文章写作技能
- trigger_hooks.md v1.1.2→v1.1.3：文章写作触发行关键词补"去AI味"（13 触发词），头部关键词注释同步；article-writing.md 入口关键词注释同步

### 2026-08-06：移除 MIGRATION.md（v1.0.1）

- 用户确认删除（方案 A）：MIGRATION.md 为 v1.0.0 时代遗留（老文档规整指南），已被 generate_docs.py 模板化自动生成替代，docs_rj 文档已全部打戳无老文档残留，memory 零使用记录，且自身版本已漂移（仍 v1.0.0）
- 连带清理：trigger_hooks.md v1.1.3→v1.1.4 删 MIGRATION.md 触发行 + 头部关键词清理；sync-matrix.md v1.0.0→v1.0.1 删引用行；A/B 双副本同步删除

### 2026-08-06：README 产品化重度改版（v1.0.1）

- 门面：居中海报 + shields 徽章（Non-Commercial / v1.0.1 / 跨平台 / PRs welcome）+ slogan 前半与网页说明呼应（把管理学的 PDCA，装进每一次 AI 协作）
- **两大核心定位前置**：①自己的记忆（跟人不跟工具、数据外置）②文档规整（spec/task/handoff + SUMMARY + sync-matrix）
- 结构：前后对比 → 4 卖点 → 30 秒上手 → 能力地图 → 参考手册 → 安装详解（原技术段后移保留）
- 预留 `assets/readme/` 配图位（K3 后补 hero-loop.svg 等）；A/B 双副本同步
- **配图落地（2026-08-07）**：K3 无法配图，改走 hand-drawn-report.md 手绘 SVG 路径——`assets/readme/hero-loop.svg`（记忆→PDCA→文档闭环，白板技术图 16:9，手写体+抖动路径+2 强调色）；README「长什么样」取消注释替换 ASCII 块；XML 已校验 well-formed，浏览器实测 11 处文字无溢出
- **许可证变更（用户操作，改版记录补登）**：Apache-2.0 → riji-skill 非商业源码可得许可证 v1.0（LICENSE 全文替换 + README 徽章同步）
- 对抗审查第 1 轮（独立 subagent）：6 HIGH + 6 MEDIUM + 6 LOW；HIGH/MEDIUM 全修——TOC 2 锚点断链（em dash slugger 规则）、悬空引用「快速上手」、Red Flags 16→19 条（2 处）、loop_constraints 死链、补发 exa.env.json.example、ASCII 图对齐、目录结构登记网页说明.html/exa.env.json.example/assets-readme、补回装前 2 前提、PRs 徽章去假链接、隐私声明补回"不引用/转述/持久化"承诺与豁免表述、参考手册表末加 index.md 全量入口；LOW 记录在案

### 2026-08-07：README 手绘闭环图落地（v1.0.1）

- K3 无法配图 → 走 hand-drawn-report.md SVG 路径
- 新增 `assets/readme/hero-loop.svg`：记忆→PDCA→文档 闭环手绘（白板技术图 16:9，手写体 Ma Shan Zheng + 抖动路径 + 黄/砖红 2 强调色）
- README「长什么样」取消 K3 占位注释、删除 ASCII 块，改引 SVG（width 720）；目录结构注释同步
- 验证：SVG XML well-formed；浏览器实测 11 处文字 bbox 均不溢出方框（标题 634px / 方框 224px）
- 测试排查：pytest 7 failed 全为 Windows GBK 预存在问题（learn_tidy_count×6 + handoff_tidy×1），git stash 对照 HEAD 同败，与本次无关；附带发现 `PYTHONIOENCODING=utf-8` 会让 dispatch/find_similar 子进程测试误败（正常环境全过），建议后续版本统一修子进程解码（errors='replace' + 编码注入）
- A/B 双副本同步（README + SVG hash 一致）

### 2026-08-07：许可证正式切换（Apache-2.0 → 非商业源码可得许可证 v1.0）

- 诉求：个人学习 / 研究等非商业用途免费；任何商业用途（出售、作为收费产品 / 服务实质组成部分等）须事先获得作者书面授权
- LICENSE 全文替换为「riji-skill 非商业源码可得许可证 v1.0」（署名 huihui），含非商用免费 + 商用须书面授权 + 免责 + 违约即终止授权
- 同步 5 处引用：SKILL.md frontmatter `license` 字段、README 徽章 + 许可证章节、网页说明.html hero 徽章 + footer、tests/conftest.py fixture
- A/B 双副本一致：公开仓库与本地技能副本均切换；validate_skill A/B 均 32/32 MUST FIX=0
- 范围与效力：新许可证只约束此后发布版本（已发 Apache 旧副本不追溯）；执行靠作者本人（平台版权投诉为主要手段）

### 2026-08-10：更名 riji-skill → pdca-skill（v1.0.1）

- 用户拍板品牌改名：riji-skill-public v1.0.1 → pdca-skill-public v1.0.1（7 条映射全仓库替换，89 文件 / 1010 处，git 历史不改写）
- 用户数据迁移：~/.riji-skill/data → ~/.pdca-skill/data（10430 文件 / 19.68MB，零丢失），桥接 config.json 保持已安装副本路径兼容
- HISTORY 历史正文按「历史保真」原则保留原名（仿 huihui→riji 先例）：时间线 / 版本表 / 对抗审查记录中的 riji 引用不改；仅 frontmatter title、H1、首段前身声明、维护规则块品牌行更新
- 对抗性审查 2 轮（独立 subagent）：第 1 轮 6 HIGH + 14 MEDIUM；第 2 轮 fresh 验证 HIGH 全真修复 + 无新增 HIGH（HOME 权限收窄 / 测试死参数 / 自伤风险 / 对账口径 / 数字漂移等）
- 决策记录：不删旧数据 ✅ / 数据迁移 + 桥接（不追已安装副本）✅ / 文件夹整体改名 ✅ / 一次性批量替换 + git diff 全量核验 ✅ / HISTORY 历史保真 ✅

### 2026-08-13：融合 HTML/PPT 制作（v1.0.1）

- 背景：用户反馈 riji-skill 在 HTML 制作与 PPT 制作上是短板——office_processing.md 只有 python-pptx 文件操作，SKILL.md 触发钩子表无"做网页/做PPT"路由；且目标环境是**内网离线机**（无 trae 插件、无 CDN），因此不做插件路由，改为把方法论直接沉淀为自包含模块
- 方案：自包含方法论（从已装 trae 插件提炼精华后内化，**不依赖插件**）——新增 `references/do/code/html_ppt_creation.md`：PPT 用 python-pptx（纯 Python）/PptxGenJS（Node）生成可编辑 .pptx + 六风格视觉配方；HTML 幻灯片手写单文件（16:9 舞台 + 键盘翻页 + Node 导出）；HTML 网页手写 + 前端设计五原则；图表手写 SVG / 本地 echarts；内网边界见 §四
- 登记 7 处：trigger_hooks.md（+2 触发钩子行 v1.1.4→v1.1.5）/ index.md（47→48、do 8→9、code 5→6、doc_proc 4→5）/ SKILL.md §0.5 资源索引（+2 行）/ README.md（能力地图 + 参考手册 23→24 高频模块 + 包内 47→48）/ subagents_rj.md（doc_proc_agent 知识库 + 触发词）/ 网页说明.html / HISTORY.md 本节
- 验证：validate_skill MUST FIX=0 + 残留 grep 0 + 版本号一致性
- 决策记录：自包含方法论（非路由、非整体嵌入）✅ / HTML 与 PPT 都做 ✅ / 版本不 bump 保持 v1.0.1 ✅ / 变更记录落盘 `C:\Users\86029\Desktop\PDCA-skill v1.0.2升级\` ✅

### 2026-08-11：Excel 分析能力系统性升级（v1.0.2 内容，本节 2026-08-19 补登）

- 背景：用户反馈 Excel 深度分析是短板——excel_analysis.md 停留在 v1.0.0 基础方法论，缺颜色编码/可视化/格式规范/做表前规划等工程实践
- 三阶段推进：① excel_analysis.md 核心方法论扩充（新增颜色编码速查/可视化设计原则/专业表格格式规范/做表前规划/KPI 卡片设计等 6 章 + 验收清单扩充，v1.0.0→v1.2.1）② 打通 4 个配套文件引用关系形成「分析能力 + 配套工具 + 审查保障」闭环——office_processing.md v1.1.0（交叉引用表）/ file_to_markdown.md v1.1.0（Excel 转 MD 6 场景注意事项）/ code_rules.md v1.1（第十章 Excel 代码规范）/ adversarial_review.md v1.1.0（§四数据分析专项审查 8 维度）③ 从 4 个新装 skill（industry-researcher / lark-sheets / lark-base / lark-drive）提炼 9 项方法论融入（意图→操作映射/数据源范围 3 步确认/全局 vs 局部/图表数据源精确控制/扩展图表选型/三方对照验证法/交付验收 6 项追溯/美化 5 维度/条件格式设计方法论新增章，v1.2.1→v1.3.0），剥离飞书 API 依赖纯 Python 可用
- 来源：xlsx skill + data-processing 插件 + 4 个 lark/industry skill 提炼，内网离线可用；源记录见《本次对话变更记录_20260811.md》
- 验证：5 文件版本号 header 与版本历史一致 + 无占位符 + 交叉引用路径有效 + 内网零依赖
- 本节为 2026-08-19 发布 v1.0.2 时补登（当时未写入 HISTORY）

### 2026-08-19：v1.0.2 公开发布版

- 版本 bump：v1.0.1 → v1.0.2 全链路同步 17 处——SKILL.md frontmatter + HTML 注释 / README 版本行 / 网页说明.html 3 处 / HISTORY.md frontmatter + 时间线 + 页脚 / assets 11 个模板 `skill_version` / evals.json / subagent_config_rj.json（+last_updated）/ server_lite `__init__.py`+`app.py` 健康检查+static/index.html 面板版本 / startup_tidy.py SUMMARY 生成戳 / package_skill.py 用法示例；references 模块自身版本号与「【v1.0.1 新增】」类历史标记按惯例保留
- 本版内容（相对 v1.0.1 发布包）：① Excel 分析系统性升级（见 2026-08-11 补登条目）② HTML/PPT 制作模块（见 2026-08-13 条目）③ 发布瘦身
- 发布瘦身（按可复用 SOP，开发环境复制为发布目录后剔除）：.git/（446 文件 git 历史+个人远端）/ docs_rj/（88 文件私人用户数据）/ outputs_rj/ / .playwright-mcp/ / __pycache__×4（3.10+3.11 双份）/ tests/.pytest_cache / .primary_docs_rj（私人本地路径）/ agents_rj/subagent_call_log.jsonl（运行日志）；README 顶部 img.shields.io 外链徽章换纯文本版本行；网页说明.html 占位 clone 命令（github.com/yourname）改「下载 ZIP 解压」；成品 156 文件（v1.0.1 为 155，差 1 = 新增 html_ppt_creation.md），框架本体零损失
- 决策记录：exa.env.json.example 保留（README 方式B 引用作配置模板，内容仅占位符无真实 key，用户拍板）✅ / 发布文案 = HISTORY 登记 + 独立《v1.0.2 发布介绍》✅ / 验证后打 zip ✅
- 验证：validate_skill 32/32 pass MUST FIX=0（版本同步前后各跑一轮均全绿）+ 身份残留扫描 0 命中（Xukun-Liu/huihui_9999/yourname/img.shields.io 全零；HISTORY 内 3 处 `~/.riji-skill/data` 为改名历史保真记录）

---

**版本**:v1.0.2 | **最后更新**:2026-08-19 | **作者**:huihui

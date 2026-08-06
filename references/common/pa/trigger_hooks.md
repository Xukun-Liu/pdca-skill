<!-- PDCA标签：P.route A.handoff -->
<!-- 子标签场景：路由判断、关键词触发、reference 索引 -->
<!-- 关键词清单：报错/写代码/写spec/跳过规则/对抗审查/项目结构/设计模式/API/数据库/Git/回滚/memory/沟通/安全/测试/部署/性能/浏览器/Office/转Markdown/Excel分析/装skill/同步整理/验收交接/bootstrap/多项目/git备份/上下文压缩/learn/规整文档/升级文档/migrate docs/regularize -->
<!-- 引用范围：main + bootstrap_agent -->

# 触发钩子表（从 SKILL.md §0 外迁）

> 阶段标签：P · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.1 | 外迁时间：2026-07-15 12:00 | 更新：2026-08-06（安全行加扫描关键词 / skill_graph 行加 L2 确认前置）| PDCA 标签：P.route A.handoff
> 本文件是 riji-skill 的关键词→reference 映射总表，从 SKILL.md §0 外迁而来，作为路由层 reference 平级管理。
> 触发逻辑不变：遇到关键词→读对应 reference→再动手。报错信号不自动读 debugging.md，先询问用户意图（见文末"报错询问机制"节）。

---

## 🔴 References 触发钩子表【硬性】（遇到这些情况，先读文件再动手）

> **🌐 联网搜索统一规则（v1.0.0 新增）**：凡是需要"搜网上的东西"的场景（找 skill / 找 agent / 找工具 / 找 MCP server / 查开源项目 / 查技术方案 / 查文档 / 查仓库等），**统一先走 [references/plan/route/agent_find.md](../../plan/route/agent_find.md) 的四层降级链**：① Exa REST 直连（环境变量 `EXA_API_KEY` 或 `exa.env.json`）→ ② Exa MCP → ③ WebFetch（URL 抓取）→ ④ WebSearch。**能用 Exa 就用 Exa，不行再 WebFetch，再不行 WebSearch**。其他 reference 里写 WebSearch/WebFetch 的地方，都按此规则前置走 agent_find.md。

| 当你遇到/准备做... | 📖 必须立即读... | 🚀 自动触发... |
|---------------------|-----------------|----------------|
| 报错/出错/不对/不行/坏了/崩了/异常/不好使/修不好/不work/不符合预期/error/failed | references/common/dc/debugging.md（完整读四步调试+3-Strike） | - |
| 准备写代码/改代码/改文件/写个/帮我写/实现/开发/coding/加功能/新增功能/改功能/修bug/重构/优化代码 | references/do/code/code_rules.md（至少读四原则+HARD-GATE+No Placeholders） | - |
| 准备写spec/写task/写文档/写需求/做需求/需求分析/写方案/出方案/写设计/做设计/规划 | references/common/pda/document_specs.md | **自动调用 `generate_docs.py` 生成文档目录结构；生成的 spec/task 文档顶部按 hand-drawn-report.md 内联手绘 SVG 速览图（默认带图）** |
| 想跳过规则/太简单/不用确认/不确定/该不该继续/感觉不对/是不是偏了/是不是有问题/检查代码/检查逻辑/review一下/复盘 | references/check/red_flags.md（先翻理性化反驳表） | - |
| 审一下/挑刺/grill/对抗审查/审查方案/审spec/审代码/找漏洞/挑毛病/adversarial | references/common/pc/adversarial_review.md（第一性原理拆解+对抗性审查流程） | **复杂任务自动启动独立 subagent 做对抗性审查** |
| 文件放哪/目录怎么组织/放哪个目录/结构怎么弄/项目结构/代码放哪/模块怎么分/文件夹怎么建/准备设计项目结构/模块划分/架构设计/分层设计/代码组织 | references/plan/design/project_structure.md | - |
| 设计模式/用工厂/用策略/依赖注入/观察者/模板方法/适配器/代码架构/怎么设计代码/怎么组织代码 | references/plan/design/design_patterns.md | - |
| API/接口/RESTful/endpoint/路由/写接口/设计接口/API设计/HTTP接口/后端接口 | references/do/code/code_rules.md（第六章） | - |
| 数据库/建表/SQL/Schema/数据模型/表结构/字段/索引/数据存储/ER图 | references/do/code/code_rules.md（第七章） | - |
| Git/提交/commit/分支/branch/push/PR/merge/合并/打tag/发版 | references/do/code/git_workflow.md | - |
| commit message 规范/Conventional Commits/WIP commit/commit 关联 task/校验 commit/commit 格式 | references/do/code/git_workflow.md §2.4-§2.9 | **硬性：建议跑 `scripts/commit_lint.py lint` 预校验 + `scripts/commit_lint_install.py install` 装 hook 自动拦截** |
| 回滚/回溯/恢复/还原/改坏了/撤销/undo/rollback/revert/回到之前/紧急回滚/代码改错了 | references/do/code/git_workflow.md §6（回溯保障） | **硬性：动手改前必须先 commit 确保工作区干净** |
| memory/记忆/存盘/检查点/5问/reboot/忘了/想不起来/上次聊了什么/进度在哪/接上/上次说到哪 | references/common/pa/working_memory_rules.md | - |
| 记忆归档/记忆降级/记忆升格/记忆删除/记忆重评/记忆治理/容量超限/记忆隔离/记忆回滚 | references/common/pa/memory_governance.md | 方案 3-R 治理工具专用触发词，避开"archive"裸词（与任务归档区分） |
| 怎么沟通/怎么问/怎么汇报/怎么确认/要不要确认/该不该问/怎么说/怎么跟你说 | references/common/dc/communication_rules.md | - |
| 安全/删文件/删除/装依赖/install/pip/npm/碰个人目录/敏感信息/密钥/密码/token/环境变量/扫描文件/搜索文件/找文件/遍历目录/共享盘/涉密/内网 | references/do/danger/security.md（安全边界 + 文件扫描确认门控 L0/L1/L2） | - |
| 测试/写测试/跑测试/测试用例/单测/单元测试/集成测试/test/tdd/mock | references/do/code/code_rules.md（第五章测试策略） | - |
| 部署/发布/上线/CI/CD/持续集成/pipeline/docker/k8s | references/plan/route/skill_management.md | **自动执行 agent-find 搜索部署相关 skill（Exa REST → Exa MCP → WebFetch → WebSearch 四层降级）** |
| 性能优化/性能/瓶颈/慢/卡顿/profiling/内存泄漏/延迟 | references/common/dc/debugging.md（四步调试法定位瓶颈） | - |
| 浏览器操控/浏览器自动化/Agent浏览/网页操作/自动填表/AI网页抓取/让AI操作浏览器/RPA | references/do/code/browser_automation.md | **含选型对比（MCP / 非 MCP 方案并列）与落地步骤；若需更专业方案，自动执行 agent-find 搜外部 skill** |
| 金融/PDF/Word/Excel/图片/视频/音频/Office/自动化/爬虫/数据分析/专业领域/专用工具/转PDF/转Word/转Excel/转Markdown/Excel分析 | **优先执行 agent-find 全网搜外部 skill**（见 references/plan/route/agent_find.md） | **四层降级：①Exa REST 直连→②Exa MCP→③WebFetch→④WebSearch；搜到候选后走 skill_management.md 安全扫描+安装流程；若搜不到合适 skill，再降级用本地 reference 兜底** |
| 处理PDF/Word/PPT/Excel文件（读/写/改/转/合并/拆分/提取表格/做PPT/Excel公式/Office文档操作/文档转换） | references/do/code/office_processing.md（PDF·Word·PPT·Excel 读·写·改·转·合并·提取全流程，纯本地工具，内网可用） | **兜底用：agent-find 搜不到合适外部 skill 时，用本模块本地纯 Python 方案；内网可用，零外部依赖** |
| 转Markdown/转md/文件转markdown/PDF转md/Word转md/PPT转md/Excel转md/HTML转md/文档转markdown/提取成markdown | references/do/code/file_to_markdown.md（PDF·Word·PPT·Excel·HTML→MD，纯Python离线可用，某工具 一行转） | **兜底用：agent-find 搜不到合适外部 skill 时，用本模块本地 某工具 方案；首选 某工具 一行命令，精细控制换专用库** |
| 分析数据/Excel数据分析/数据清洗/透视表/统计分析/图表可视化/同比环比/做看板/从表里找规律/数据分析方法论 | references/common/pd/excel_analysis.md（清洗·透视·统计·图表·预测 方法论，纯本地，内网可用） | **兜底用：agent-find 搜不到合适外部 skill 时，用本模块本地方法论；动手前先读第一节"想清楚3问"；与 office_processing.md 分工：它管"读写Excel文件"，本模块管"怎么分析出结论"** |
| 安装skill/装skill/下载skill/找一个skill/有没有skill/skill推荐/技能/插件/扩展 | references/plan/route/skill_security.md | **自动执行 SkillAudit 安全扫描** |
| 同步一下/整理文档/整理一下/更新记忆/梳理一下/收尾/这个阶段做完了/新人能直接上手/检查规范/审计规则/规范体检/交接/里程碑/sync/neat/tidy/版本号一致/一致性检查/清理/打扫/对一下 | references/common/da/sync-matrix.md（按矩阵逐项核对版本号+引用+文件一致性） | **自动执行全局版本号一致性检查** |
| 规整文档/升级文档到 v1.0.0/migrate docs/按新版本规整/按新标准整理/regularize | [MIGRATION.md](../../MIGRATION.md)（按步骤整理项目 docs_rj/ 文档内容） | **扫描 docs_rj/ → 预览老文档 → HARD-GATE 确认 → 备份到 docs_rj/migration_backup_{时间戳}_{序号}/ → 按 §3 整理 → 验证 → 汇报 → 写 memory**<br>　仲裁规则：用户裸说"整理一下/整理文档"→ 上一行（sync-matrix 只核对版本号）；用户说"规整/升级/migrate/按新版本整理"→ 本行（MIGRATION.md 改内容）<br>　识别信号优先级：①无 frontmatter ②无 skill_version ③skill_version < v1.0.0 ④version 注释不一致 ⑤内容特征（无 §0 设计层等）<br>　整理范围：仅 docs_rj/{spec,task,handoff,memory}/*.md + SUMMARY_RJ.md；禁止触碰 skill 包自带 assets/ |
| 验收/验收一下/审核/看一下做得对不对/看一下进度报告/交接/给你接手/handoff/存档/总结/总结一下/汇报/进度/汇总/梳理一下做了什么/产出报告/报告/让我看看总结/确认一下做得对不对/计划/方案/规划一下/出方案/做规划/盘点/能力清单 | references/common/da/hand-drawn-report.md（按内容关系类型生成手绘 SVG） | **报告/计划/盘点类输出默认在对话内附手绘 SVG 速览图，若生成 md 则 md 顶部同时内联同款 SVG（带图、单文件自包含）；交接时额外刷新 {主docs}/SUMMARY_RJ.md（见 summary_view.md）** |
| 交接/收尾/给你接手/handoff/存档/交接工作 | references/common/da/sync-matrix.md → **自动调用 `python scripts/handoff_tidy.py --task {任务名}`** | **硬性：交接时必跑 handoff_tidy**<br>　管线：守卫+归档+刷新+漂移+外部记忆清理+平台记忆融入技能记忆+强制#3→#4同步+五问预跑+sync-matrix核对<br>　效果：自动整理文档+对齐记忆+强制走技能记忆（禁止用平台记忆替代）+融入平台记忆并删除原件 |
| 定验收标准/写验收/写验收条件/DoD/验收严格点/怎么算做完/acceptance/给定当那么/GivenWhenThen | references/common/pc/acceptance_criteria.md（DoD+Given/When/Then+4道质量闘门） | **定义"做完了"的硬标准——写 spec 验收小节前先读；与 adversarial_review.md(找茬执行)+red_flags.md(偏离报警) 配合成严格验收闭环** |
| /plan /设计 /方案 /从头开始 /新项目 /帮我规划 /一步一步来 /规划一下 /想清楚再做 /需求分析 /做需求 /出方案 | 按 SKILL.md §6 /plan 完整 7 步流程执行（步骤1 P.bootstrap 读状态→步骤2 P.route 三层挑选+报错询问→步骤3 需求澄清→步骤4 P.design 第一性原理拆解→步骤4a P.reuse 外部资源搜索【自动调用 agent_find 搜索外部资源】→步骤5 brainstorming+HARD-GATE→步骤6 writing-plans+HARD-GATE+Self-Review+对抗审查） | **PDCA /plan 触发词：默认用户零背景，疯狂追问确认，步骤4a 自动搜索外部资源，步骤5/6 各一次 HARD-GATE，确认好再进入 /do** |
| 首次使用/初始化/文件不存在/memory不存在/memory_main.md不存在/项目结构缺失/第一次用/新项目/bootstrap/没装过/还没初始化 | references/plan/bootstrap/bootstrap.md（逐文件引导创建） | **自动检测缺失目录，报告后逐个确认创建，不静默创建** |
| 多项目/切换项目/多个项目/项目切换/换项目/同时搞几个 | references/plan/bootstrap/multi_project.md | - |
| git备份/清理/瘦身/释放空间/git太大/仓库太大/.git太大/磁盘满了/备份堆积/清理分支/清理reflog/大文件历史/git体检/仓库体检 | references/common/da/git_backup_cleanup.md（5阶段：体检/备份/清理/维护/生命周期，纯Python标准库） | **体检纯只读（L1）+ 备份自动commit（L2）+ 清理fresh clone+HARD-GATE确认（L3）；startup_tidy/handoff_tidy 自动跑体检钩子** |
| 上下文压缩/对话超10轮/单轮超200行/读了超10个文件/感觉忘了/凭印象回答/连续3次没引文件/compact/compression/记不清了/忘了刚才 | references/plan/bootstrap/compaction_recovery.md 压缩恢复协议（检测信号表+7步恢复流程） | **自动执行7步恢复流程（停→读SUMMARY→读MEMORY→重读铁律→五问→告知用户→继续）** |
| learn/学习一下/自进化/自我优化/扫一下skill/skill体检/优化框架/找可优化点/learn_cycle/learn_tidy | references/act/learn/learn_cycle.md（learn 6阶段流程+判断标准+adopt规范） | **自动调用 `python scripts/learn_tidy.py scan --dry-run`；agent 读 learn_cycle.md + adversarial_review.md 提建议；HARD-GATE 确认后 adopt** |
| prompt优化/减法原则/规则层扫描/绝对规则/过程指令/重复规则/硬性密度/结果优先/OpenAI原则/GPT-5.6/prompt_guidance/prompt_metrics | references/act/learn/prompt_optimization.md（OpenAI 12原则+减法审查清单+阈值解读） | **learn_cycle reflect 阶段自动读；agent 拿 scan_report.json 的 prompt_metrics 做语义审查提建议** |
| /plan 阶段输出 triage / 定方向后自动循环 | references/plan/route/loop_triage.md | **/plan 阶段自动加载，输出 High Priority / Watch / Noise 三段式** |
| L2 /do 执行前 / 自动循环进入执行 | references/do/danger/loop_constraints.md + references/do/danger/security.md | **/do 阶段自动加载，确保路径/合并/改动/预算/失败约束生效** |
| /check 验证阶段 | references/check/loop_verifier.md + references/check/red_flags.md | **/check 阶段自动加载，verifier 默认 REJECT until proven otherwise** |
| /act 归档阶段 / 生成任务状态 | references/common/pda/document_specs.md + references/common/pa/summary_view.md + references/act/persist/act_procedure.md | **/act 阶段自动加载，生成 TASK_STATE.md 并更新 memory** |
| /loop（"自动循环""跑循环""开始循环""loop模式""自动模式"） | references/do/danger/loop_constraints.md + references/check/loop_verifier.md | **检查前置条件（/plan 已确认 + loop_admission level≥L2 + git 仓库）→ 询问模式（auto/semi）→ 启动 /do→/check 循环** |
| master_graph/技能图谱/能力画像/skill graph/我看我有什么技能/我未掌握什么/差距分析/技能雷达/我还有什么没学/推荐我学什么 | references/act/learn/skill_graph.md（三阶段流水线+双轨提取+三格式渲染） | **先确认后触发（用户点名全量）：本功能扫描 `~`/APPDATA 等任务外目录（属 security.md L2 门控），必须先向用户确认范围+目的，确认后才自动调用 `python scripts/skill_graph_build.py --source all`；白名单 8 个 AI 工具固定记忆目录豁免确认（用户启用功能即授权，见 skill_graph.md §4），关键词发现扫描仍须确认；输出 `~/.riji-skill/data/docs_rj/skill_graph/` skill_graph.md + .csv + .svg + manifest.json**。**每轮 /act 3.6a 自动刷新仅左轨（`--auto`，L0 安全级免确认，哈希未变缓存命中跳过，taxonomy 缺失 [SKIP] exit 0，阶段失败 exit 2 不阻断）** |
| 市场调研/market research/竞品调研/竞品对比/feature 对比/4 维度调研 | assets/market_research_template.md（9段+6项质检对齐 某开源项目 market-research.md） | **/plan 步骤4a.5 自动加载，覆盖 feature/UX/complaints/technical 4 维度** |
| 副 agent 调度/召唤副 agent/多 agent/并行调研/专业分工/顾问团/复杂任务深度调研 | references/common/pda/subagents_rj.md（9 副 agent 角色配置 + 调度规则 + 权限白名单） | **可跑 `python scripts/launch_subagent_rj.py suggest --task "任务描述"` 获取调度建议；主 agent 按建议用 Task 工具启动副 agent（subagent_type=general_purpose_task）做只读调研；详见 SKILL.md §0.56** |
| 执行中插需求/打断/插入新任务/挂起/暂停任务/恢复原任务/paused | references/do/comm/insert_new_task.md（4步打断流程/挂起/恢复/边界case） | **在范围内当子任务追加，超范围走 4 步打断流程；/loop 自动模式下立即熔断 escalate** |

> ❌ 禁止以"我记得规则"为借口跳过读文件。RAM（上下文）是易失的，细节必须从硬盘重读。触发信号出现不读对应reference = Red Flag偏离。

---

## 🛡️ 读取失败降级【硬性】

若某个 reference 读取失败/文件缺失/内容被截断，**禁止凭记忆顶替**。按此顺序降级：
1. 若 SKILL.md 中有该主题的简述则参考（注意：多数 reference 主题在 SKILL.md 无完整兜底，仅有一句话提及）
2. 明确告知用户"XX规则文件读取异常，无法获取详细规则"
3. 走澄清菜单问用户"该规则文件读取失败，是手动提供规则内容、暂停任务、还是用通用能力顶上？"，不擅自假设规则内容

---

## 报错询问机制【硬性】

当用户描述含报错信号（报错/不行/失败/异常/error/failed 等）时，**不自动读 debugging.md**，先询问用户意图：

**询问菜单**：
> 检测到报错信号（关键词：报错/不行/失败/异常/error/failed）
> 你想：
> 1. 走系统调试（读 debugging.md 四步调试法 + 3-Strike 协议）
> 2. 只是提及报错，按原任务继续
> 3. 其他：你说我调整
>
> 选哪个？

**设计理由**："我报错了"和"我要修报错"是两件事——前者可能只是背景描述，后者才是明确调试需求。直接读 debugging.md 可能误判场景，先问意图更安全。

**适用场景**：
- /do 触发后描述含报错信号 → 询问
- /plan 步骤2 路由判断时描述含报错信号 → 询问
- 隐式触发命中 debugging 关键词 → 询问

**用户选 ①** → 读 debugging.md，按四步调试法走
**用户选 ②** → 跳过 debugging，按原任务继续
**用户选 ③** → 按用户指示调整

---

## 与 PDCA 四触发词的关系

本表是**隐式触发**（用户描述命中关键词→自动路由到对应 reference）。

PDCA 四触发词（`/plan` `/do` `/check` `/act`）是**显式触发**（用户主动喊触发词→走对应阶段流程）。

两者并存：
- 用户喊 `/do` → 显式入口，按 PDCA /do 流程走，其中用三层挑选读取 D 标签 reference
- 用户未喊触发词但描述含关键词 → 隐式触发，按本表路由
- 显式触发优先级高于隐式触发（用户喊了触发词就按触发词走，不被关键词打断）

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-07-21 | 初版：从 SKILL.md §0 外迁；新增报错询问机制+PDCA 关系节 |
| v1.1.1 | 2026-08-06 | 安全行加扫描类关键词（扫描文件/搜索文件/找文件/遍历目录/共享盘/涉密/内网）；skill_graph 行加 L2 确认前置（扫 home 属任务外，须先确认）+ v1.0.2 --auto 3.6a 自动刷新双语义（仅左轨 L0 免确认 / 点名全量 L2 确认，输出路径外置 ~/.riji-skill/data/） |

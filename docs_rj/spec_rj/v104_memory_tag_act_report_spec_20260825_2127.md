---
title: v104_memory_tag_act_report - 需求规格说明
version: v1.0.0
skill_version: v1.0.4
date_created: 2026-08-25 21:27
last_updated: 2026-08-25 21:27
owner: 用户（发起+验收）
tags: [v1.0.4, memory_tag, act_interactive, leader_report]
derived_from: spec_main_rj.md §3（项目目标：记忆/PDCA/docs 三位一体闭环）
---

# spec：v104_memory_tag_act_report

> 版本：v1.0.0 | 更新：2026-08-25 21:27
> 任务：pdca-skill v1.0.3 → v1.0.4 三痛点体系化改造（记忆文件夹制+标签体系 / act 互动复盘 / 领导汇报 reference）

---

## 0. 设计层：本质拆解（第一性原理）

### 本质目标
用户要的不是"加功能"，是三个结果：①记忆**找得到**（按标签+按时间检索，不再在大文件里翻）②复盘**有互动**（用户的判断沉淀进记忆，不是 AI 单方面流水账）③汇报**有模板**（对上汇报有结构有数据，不裸写）。

### 不可压缩约束
- C1（架构）：纯 markdown + Python 脚本零系统依赖——不能引入向量库/数据库（Letta/Mem0 方案只能借鉴思想不能搬实现）
- C2（数据链）：memory_distill.py / learn_tidy.py 等下游脚本依赖 memory_main.md 条目格式解析——索引化必须同步适配下游，否则 distill/learn 闭环静默死亡（对抗审查 H1）
- C3（兼容）：外置数据目录 `~/.pdca-skill/data/` 跨 skill 版本共享——新旧版本混写需 schema_version 防撕裂（对抗审查 M3）
- C4（回滚）：迁移涉及用户全部历史记忆（118 条）——必须先备份、对账校验、失败回滚
- C5（Windows）：PowerShell 管道中文损坏 + 沙箱拦截 tempfile.mkstemp 的历史教训（项目记忆已载）——脚本写文件用 open() 直写 + 强制 UTF-8

### 从约束推导的最优解
两层标签设计（6 主分类文件夹 + 自由标签）是 C1 约束下的最优：Mem0 式向量标签库违反 C1；纯文件名前缀（对抗审查 H2 备选）治标不治本（用户明确要"文件夹制"）；文件夹制 + 下游 rglob 适配在 C1-C5 全约束内。

---

## 0.1 方案对比

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| A：最小改动 | 只加标签文件夹，memory_main 不动，act 加一段文字，新建汇报 reference | 改动小（2-3 文件） | 痛点1 治标不治本；标签乱根源不除 |
| **B'：三痛点体系化改造（推荐，含对抗审查 4 HIGH 修复）** | 6 主分类文件夹+索引化+write_project 改造+迁移+下游 7 处适配+act 互动步骤+leader_report 三表联动 | 三痛点治本；闭环完整；对抗审查已过一轮 | 改动面大（约 15 文件）；需 50 轮测试兜底 |
| C：B' + 检索自动化 | B' 基础上加按标签检索脚本 | 检索最强 | 超出本次痛点范围，工程量+40% |

**我推荐方案B'**：三个痛点全治本，C 的检索脚本留 v1.0.5。用户已多轮确认（文件夹结构/互动形式/汇报场景/迁移策略/测试轮数全部拍板）。

---

## 0.A 外部资源搜索清单【P.reuse】

### 搜索关键词
agent memory / memory layer / tag taxonomy（脱敏：不含项目名）

### 内部复用（步骤4a.1）
- 找到：`scripts/memory_shadow_write.py` write_project 双写机制（L287-291 已有 tags/experience_tags 参数体系）→ 在其上扩展 memory_class 参数，不另起炉灶
- 找到：`scripts/migrate_user_data.py` 迁移脚本骨架（文件锁/迁移标记/回滚窗口模式）→ 迁移脚本复用此模式

### GitHub/Gitee 开源项目（步骤4a.3 + WebSearch）
| 候选 | 仓库URL | Stars | License | 复用方式 | 是否采用 | 理由 |
|------|---------|-------|---------|----------|----------|------|
| Letta (MemGPT) | github.com/letta-ai/letta | ~23k | Apache-2.0 | 参考架构（分层记忆思想） | 思想采用 | 纯 markdown 环境不能搬实现 |
| Mem0 | github.com/mem0ai/mem0 | ~59k | Apache-2.0 | 参考架构（scope+自动标签） | 思想采用 | 同上 |
| opencode-agent-memory | github.com/joshuadavidthomas/opencode-agent-memory | - | MIT | 参考架构（block+journal append-only） | 思想采用 | journal 模式=现有 write_project，验证方向 |
| awesome-agentic-memory | github.com/Anandesh-Sharma/awesome-agentic-memory | - | - | 仅学习（taxonomy 综述） | 是 | CoALA/Tulving 分类学依据 |
| reflect pattern（Claude Diary/claude-mem） | 见 awesome 列表 | - | - | 参考架构（session-end 追问复盘） | 思想采用 | act 互动的业界标准做法佐证 |

### 搜索降级记录
- [x] 网络可用：是（WebSearch 5 条结果）
- [x] GitHub API：find_similar.py 0 条（关键词过窄）→ 降级 WebSearch 成功
- [x] Gitee：0 条 → 跳过
- [x] Exa：未配置 → 直接 WebSearch

### 复用结论
- **采用**：内部 write_project 扩展（不新建写入通道）；migrate_user_data.py 迁移模式复用；Letta/Mem0 的"分层+自动标签"思想
- **不采用**：向量库/graph memory（违反 C1 纯 markdown 约束）
- **对 brainstorming 的建议**：围绕 B' 方案展开，标签体系单点常量设计（借鉴 Mem0 的标签收敛思想）

### BRD 视角对比表
| 候选产品 | Stars/用户量 | 核心功能 | 优点 | 缺点 | 可借鉴点 | 不做的代价 |
|---------|-------------|---------|------|------|----------|-----------|
| Letta | ~23k | 分层记忆 OS 式管理 | 分层清晰、自管理 | 需 Python 服务+DB | 分层思想 | 记忆继续扁平混乱，找历史经验靠翻 |
| Mem0 | ~59k | 自动记忆提取+scope | 自动化程度高 | 云依赖/复杂 | 标签自动收敛 | 标签继续"无"或自由泛滥 |
| 手工 AGENTS.md 约定 | 普遍 | 纯 markdown 手工约定 | 零依赖 | 无结构无治理 | 已是现状 | 现状痛点本身 |

**市场调研质检**：4 维度覆盖——feature（3 框架功能对比）✓；design-UX（分层/scope/journal 三种设计模式）✓；user expectations（LongMemEval 基准、plain filesystem 74% 佐证轻量路线可行）✓；technical implementation（hybrid vector+graph+KV 技术栈对比）✓。

---

## 0.2 少写代码 / 复用优先评估

| 评估项 | 方案A | 方案B' | 方案C |
|--------|-------|--------|-------|
| 优先复用现有代码？ | 是（改动最小） | **是**（write_project 扩展参数而非重写；migrate 模式复用） | 部分 |
| 引入非必要新依赖？ | 否 | **否**（纯 Python 标准库） | 否 |
| 为未来预写代码（YAGNI）？ | 否 | **否**（检索脚本不做留 v1.0.5；标签单点常量服务于用户明确的"后续会增加"，不算 YAGNI） | 是（检索超出本次范围） |
| 新增代码量最少？ | 是 | 否（+memory_tags.py ~60行、+migrate_memory_v104.py ~200行、改造 ~150行） | 否 |
| 因"少写"省略安全/校验？ | 否 | **否**（对账校验+备份+schema_version 三道保险） | 否 |

**评估结论**：B' 复用优先最优——所有新代码都有明确痛点对应，无投机性代码。

---

### 0.G Git 管理约定

| 项 | 回答 | 执行约定 |
|----|------|----------|
| Q1 工作区状态 | commit（2 个遗留文档改动属上次 v103_sync 收尾产出） | /do 开始前先 commit 存档 |
| Q2 分支策略 | **新建 feature 分支** | `git checkout -b feature/v1.0.4-memory-tag-act-report` |
| D1 git init | 已 init（master 跟踪 gitee/main） | 不适用 |
| D2 WIP commit | 允许（默认） | 每 task 子项存一次档 |
| D3 任务 tag | 打（默认） | start + verified 两个 tag |

---

## 1. PRD 层：业务背景与目标

### §1.X 任务分型与富规格
- **目标类型**：**执行型**（能写出验收命令：迁移对账数字、validate 通过数、测试轮数）
- **富规格引用路径**：
  - 测试套件：`tests/`（pytest，含 test_memory_distill.py 等现有 18 个测试文件）
  - 验收脚本：`scripts/validate_skill.py`（基线 32/32 PASS）
  - 对抗审查报告：`docs_rj/check_rj/v104_memory_tag_act_report_adversarial_20260825.md`（4H/7M/4L 清单，本 spec 的修复依据）

### §1.0 业务背景与痛点
- **背景**：用户使用 pdca-skill v1.0.3 过程中发现三大痛点，要求升级 v1.0.4
- **痛点**：①记忆混乱——118 条记忆堆在 memory_main.md 单一大文件（实证：3 个脏数据段 `## data`/`## 86029`/`## 6a866d23...`），标签大量为"无"，无法按标签/时间检索；②/act 零互动——纯脚本流水线，用户判断从不沉淀；③无汇报 reference——49 个模块没有"给领导汇报"方法论，汇报裸写

### §1.1 业务价值
- **价值评级**：高
- **理由**：记忆是 pdca-skill 三定位（记忆/PDCA/docs）的根基，痛点1 直接治根基；痛点2/3 补齐闭环最后两块（复盘互动+对上汇报）
- **AI 提示**：无保留意见

### §1.2 不做的代价 / 机会成本
- **不做的代价**：记忆继续无序增长（现 118 条，月增 ~30 条，一年后 400+ 条大文件不可用）；用户经验持续流失（每次对话的判断不沉淀）；汇报场景继续无支撑
- **替代方案**：无更省做法（方案A 治标不治本已被否）

### §1.3 成功指标（可验证）
- **指标**：①write_project 带 memory_class 落对应文件夹，非法值兜底 workflow；②迁移前后条目对账 118=118；③distill/learn 在新结构下正常（≥1 条经验可提取、count 不为 0）；④leader_report 触发词命中；⑤50 轮全流程测试通过；⑥validate_skill.py 32/32（不低于基线）
- **验证方法**：见 §5 AC 表（每条给具体命令）

### §1.4 干系人
- **发起人**：用户（本人）
- **使用者**：用户 + 各环境 AI agent（TRAE/opencode 等）
- **验收人**：用户（亲验 + 50 轮测试报告）

---

## 2. PRD 层：定义与术语

- **主分类（memory_class）**：决定记忆文件落哪个文件夹的固定分类，共 6 个 + 兜底：tech_solution（技术方案）/ pitfall（踩坑教训）/ workflow（流程规范）/ tool_usage（工具使用）/ decision（管理决策）/ status（状态进度），未覆盖类型兜底落 workflow
- **自由标签（tags/experience_tags）**：第 2 层标签，写在文件内，保持现有机制不变
- **两层标签设计**：主分类（文件夹级，保秩序）+ 自由标签（文件级，保灵活）
- **主分类优先级**：一条记忆符合多分类时的归类顺序：status > decision > pitfall > tech_solution > tool_usage > workflow
- **索引化**：memory_main.md 从"全文聚合"瘦身为"每条一行（时间|标签|重要性|is_lesson|一句话摘要|正文文件相对链接）"
- **互动复盘**：/act 步骤 1.5，AI 动态生成 2-3 个针对本次任务的问题，用户回答并入同一次 write_project 落盘
- **schema_version**：数据目录结构版本标记文件，防旧版 skill 混写新结构

---

## 3. PRD 层：范围

- **包含**：
  - P1 标签体系：`scripts/memory_tags.py` 单点常量（MEMORY_TAGS 列表 + 优先级常量 + 校验函数）
  - P1 存储结构：项目侧 `docs_rj/memory_rj/{主分类}/{YYYYMM}/` 两层文件夹；全局侧 memory_main.md 索引化（行内嵌 is_lesson/标签元数据）
  - P1 write_project 改造：新增 memory_class 参数（CLI + 函数签名），非法值 warning+落 workflow；写入路径路由到标签文件夹
  - P1 存量迁移：`scripts/migrate_memory_v104.py`（双备份→解析 3 种异构格式→按映射表归档→对账校验→写 schema_version→脏数据段归并）
  - P1 下游适配 7 处：memory_distill.py（rglob 正文）/ learn_tidy.py（rglob）/ loop_admission.py（glob→rglob）/ handoff_tidy.py（listdir→rglob）/ archive_tidy.py（同）/ act_procedure.md（Glob 加 `**`）/ memory_shadow_write.py 治理族（容量统计改数文件数、条目定位改正文文件内）
  - P2 act 互动复盘：SKILL.md §6 /act 节 + act_procedure.md 新增步骤 1.5（动态 2-3 问 / 并入同次 write_project / 可跳过 SKIPPED / /loop auto 自动 SKIPPED 留痕）
  - P2 leader_report.md：新建 `references/common/da/leader_report.md`（PDCA 标签 A.handoff；结构：一句话结论→进展→数据成果→风险问题→下一步计划→需要的支持；数据源映射表：memory/TASK_STATE/task.md）
  - P2 触发联动三表：trigger_hooks.md（表格+头部注释+版本历史 v1.1.8）/ SKILL.md（资源索引+仲裁规则一行）/ references/index.md（49→50 模块）
  - P2 仲裁规则：给领导/向上汇报→leader_report；验收报告/手绘图→hand-drawn-report；做PPT→html_ppt_creation
  - P1 测试：50 轮全流程模拟（四阶段×多脚本类型）+ 现有 pytest 回归
  - P1 版本收尾：HISTORY.md v1.0.4 条目、SKILL.md 版本号、memory_governance.md/working_memory_rules.md 格式规范同步
- **不包含**：
  - 按标签检索脚本（留 v1.0.5，方案C 内容）
  - server_lite 前端适配（保持现状跳过）
  - 全局侧文件夹制（memory_main.md 索引化即全局侧方案，正文不迁全局）
  - 8-9 个主分类扩展（用户明确"后续可能会增加"，本次单点常量留扩展口，不预建）

---

## 4. PRD 层：功能需求

### 4.1 memory_tags.py 标签单点常量

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-001 | 定义 MEMORY_TAGS=[tech_solution,pitfall,workflow,tool_usage,decision,status]、TAG_PRIORITY、validate_memory_class() 函数；非法值返回 workflow+warning | P1 | 对抗审查 L3/L4 |

- **输入**：字符串 memory_class（可选值见 MEMORY_TAGS）
- **处理**：validate_memory_class(v) → v in MEMORY_TAGS 则返回 v，否则返回 'workflow' 并打 warning（沿用 memory_shadow_write L320-332 现有 warning+默认值模式）
- **输出**：合法主分类字符串
- **边界**：None/空串/大小写不一（Tech_Solution→tech_solution 归一化）/中文输入 → 全部落 workflow+warning
- **错误处理**：无异常抛出，永远返回合法值（写通道不可断）

### 4.2 write_project 改造（memory_class 参数）

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-002 | write_project 函数签名+CLI 增加 memory_class 可选参数；正文落 `{memory_rj}/{memory_class}/{YYYYMM}/{task}_memory_*.md`；全局 upsert 行含元数据 | P1 | 痛点1 |

- **输入**：write_project(task, content, memory_class=None, tags=None, ...)
- **处理**：①memory_class 缺省时由内容关键词启发式推断（含"踩坑/报错/失败"→pitfall；含"方案/架构/实现"→tech_solution；含"完成/进度/状态"→status；含"决策/拍板"→decision；含"工具/命令"→tool_usage；其余 workflow），推断结果打印给 agent 确认可读；②路径路由 `{YYYYMM}` 从时间戳提取；③全局索引行格式：`- {时间} | {主分类} | 重要性{级} | is_lesson={bool} | {一句话摘要≤40字} | [正文]({相对路径})`
- **输出**：正文文件（标签文件夹内）+ memory_main.md 索引行
- **边界**：同 task 多次写入（append 语义不变，同文件夹追加）；跨月写入各落当月文件夹（沿用现有跨午夜规则）
- **错误处理**：标签文件夹创建失败 → 降级落 memory_rj 根目录+告警（不丢数据）

### 4.3 存量迁移脚本

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-003 | migrate_memory_v104.py：备份→解析→归档→对账→schema_version，全流程幂等可重跑 | P1 | 痛点1+M1/M3 |

- **输入**：`~/.pdca-skill/data/` 下 memory_main.md（118 条）+ docs_rj/memory_rj/ 扁平文件
- **处理**（五步，对应 M1 修复）：
  1. **双备份**：memory_main.md → memory_main.md.bak_v103；memory_rj/ → memory_rj_backup_v103/（整目录复制）
  2. **解析 3 种异构格式**：`### 记忆条目` 完整式（115条）/ `- **时间**|...` 一行摘要式（3条）/ 同 task 多条目（全保留，如 02_Riji技能推文 6 条）
  3. **归类映射**：完整式按【任务/做了什么/学到了什么】内容关键词推断主分类（启发式同 REQ-002）+ 存量自由标签映射表（sandbox_workaround→pitfall、sync_release→workflow、adopted_lesson→workflow、bugfix→pitfall、cross-machine→workflow、regression→pitfall、architecture→tech_solution）；推断不出的落 workflow；一行摘要式按摘要关键词推断；脏数据段（## data/## 86029/## 6a86*）条目归并到其正文里写的真实项目名分段，无真实项目可归的落 memory/orphan/
  4. **对账校验**：迁移前 memory_main.md 条目总数 == 迁移后（6 标签文件夹 + orphan）正文文件条目总和；不等→打印差异明细→exit 2（判失败）
  5. **写 schema_version**：`~/.pdca-skill/data/.schema_version` 内容 `{"version": "v1.0.4", "structure": "tag_folder_monthly", "migrated_at": "{时间戳}"}`
- **输出**：新结构文件树 + 迁移报告（stdout JSON：总数/各类计数/孤儿数/耗时）
- **边界**：memory_rj 里已有子目录（.skill_graph_cache）→ 只迁 `*_memory_*.md` 文件模式，跳过目录；重跑幂等（检测 .schema_version 已存在且 structure 相同 → 跳过已迁条目）
- **错误处理**：任一步异常 → 打印失败步骤+已备份位置 → exit 2，不删任何原文件（备份兜底回滚=直接用 .bak_v103 覆盖）

### 4.4 下游 7 处适配

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-004 | 7 处扁平假设改深层扫描（对抗审查 H1/H2/M4 清单逐项） | P1 | 对抗审查 |

适配清单（唯一维护源，task T2 逐项对应）：

| 文件 | 位置 | 改动 |
|------|------|------|
| scripts/memory_distill.py | L36-130 解析入口 | memory_main 分段解析 → rglob('**/*_memory_*.md') 正文解析（### 记忆条目 格式不变，解析逻辑复用） |
| scripts/learn_tidy.py | L13 harvest | 同上 rglob |
| scripts/loop_admission.py | L238-252 | mem_dir.glob → mem_dir.rglob |
| scripts/handoff_tidy.py | L498-505 | os.listdir → Path.rglob('*_memory_*.md') |
| scripts/archive_tidy.py | L84/L308 | 同上 rglob |
| references/act/persist/act_procedure.md | L20-21 | Glob 模式 `memory_rj/*_memory_*.md` → `memory_rj/**/*_memory_*.md` |
| scripts/memory_shadow_write.py | L616-618/L736-756/L873-916 治理族 | 容量统计：数标签文件夹文件数；_find_entry：正文文件内定位；_FLAG_STATUS_RE：解析正文文件（正文格式不变，正则不动，改输入源） |

### 4.5 act 互动复盘

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-005 | /act 步骤 1.5：动态生成 2-3 问 → 回答并入同次 write_project → 记忆含「互动复盘」段 | P1 | 痛点2+M2 |

- **输入**：本次任务的 spec/task/memory 上下文
- **处理**：①AI 按任务内容动态生成 2-3 个问题（生成规则：至少 1 问教训/风险（"这次哪里最容易再犯？"）+ 1 问决策依据（"为什么选这个方案不选那个？"）+ 0-1 问下一步（"下次遇到类似情况第一步做什么？"）；用 AskUserQuestion 呈现）；②用户回答 → 拼进 content 的 `【互动复盘】` 段（Q/A 格式）→ **同一次** write_project 落盘（时序：1.5 问在步骤 1 写盘之前完成，避免双写两个文件）；③跳过语义：用户说"跳过/不用" → SKIPPED 留痕（TASK_STATE 记"用户跳过互动复盘"），不 BLOCKED；/loop auto 无人值守 → 不弹问题自动 SKIPPED+留痕
- **输出**：记忆文件含【互动复盘】段（或留痕跳过）
- **边界**：用户只答部分问题 → 只落已答部分；ADD 用户长任务 → 问题不超过 3 个（硬上限）
- **错误处理**：AskUserQuestion 工具异常 → 降级文字提问，用户不答则 SKIPPED

### 4.6 leader_report.md + 三表联动

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-006 | 新建汇报 reference + 触发钩子 + 仲裁规则三处联动 | P1 | 痛点3+H4 |

- **输入**：触发词"给领导汇报/向上汇报/出汇报文档/给老板汇报"
- **处理**：①leader_report.md 内容含：汇报文档六段结构模板（一句话结论→进展→数据成果→风险问题→下一步计划→需要的支持）+ 数据源映射表（进展←TASK_STATE/数据成果←memory 索引行/风险←task.md 阻塞项+spec §9）+ 三级领导适配（直属领导重细节/大领导重结论/跨部门重背景）+ 生成流程（拉数据→填模板→hand-drawn-report 手绘速览图置于文档顶部）；②trigger_hooks.md 加行（关键词精确集，不用裸"汇报"）+ 头部注释 + 版本历史 v1.1.8；③SKILL.md 仲裁规则加一行 + 资源索引加一行
- **输出**：50 个 reference 模块的完整体系
- **边界**："汇报"单独出现 → 仲裁表：给领导/向上→leader_report；验收/手绘→hand-drawn-report；做PPT→html_ppt_creation；无上下文 → 澄清菜单
- **错误处理**：数据源缺失（如无 TASK_STATE）→ 模板对应段标注"暂无数据"不编造

---

## 5. Spec 层：验收标准（素颜章节）

| ID | 验收标准 | 测试方法 | 基线数字 |
|----|----------|----------|---------|
| AC-001 | write_project 带 memory_class=pitfall 调用后，`memory_rj/pitfall/{YYYYMM}/` 下存在正文文件，memory_main.md 出现含元数据索引行 | 跑 `python scripts/memory_shadow_write.py`（CLI 传参）后 ls 检查 + grep 索引行 | 新文件 1 个/索引行 1 行 |
| AC-002 | memory_class 传非法值"xyz"，落 workflow 文件夹且 stderr 出现 warning | 同 AC-001 传非法值 | warning 1 条/文件落 workflow |
| AC-003 | 6 标签字符串仅定义于 memory_tags.py（其他脚本 import 引用，不重复定义） | `grep -rn "tech_solution" scripts/` 逐文件核对：定义只在 memory_tags.py，他处为 import/引用 | 定义点 1 处 |
| AC-004 | 迁移前后条目对账：118 条 = 6 标签文件夹正文条目总和 + orphan | 跑 migrate_memory_v104.py，看输出 JSON total 字段 | 118=118 |
| AC-005 | 双备份存在：memory_main.md.bak_v103 + memory_rj_backup_v103/ | ls 检查 | 2 处备份 |
| AC-006 | .schema_version 写入；write_project 启动检测版本不匹配输出告警 | cat .schema_version；模拟旧标记跑 write_project 看告警 | 标记 1 个/告警 1 条 |
| AC-007 | distill 新结构下能提取经验：跑 memory_distill.py 输出 ≥1 条（存量有 is_lesson=true 条目如 v103_t3） | `python scripts/memory_distill.py distill --project {名} --output-dir docs_rj/learn_rj` | ≥1 条 |
| AC-008 | learn_tidy count 正常：total_entries > 0（不复发 global_total=0） | `python scripts/learn_tidy.py count --threshold 20` | >0 |
| AC-009 | loop_admission 检测到新结构近期记忆（记忆项不扣分） | 跑 loop_admission.py 看记忆检测项 | 不因记忆缺失扣分 |
| AC-010 | /act 步骤 1.5 规则存在于 SKILL.md + act_procedure.md（互动复盘/动态问题/SKIPPED 语义） | grep "互动复盘" 两文件 | 2 文件命中 |
| AC-011 | leader_report.md 存在且三表联动：trigger_hooks 表+头部注释+版本历史、SKILL.md 索引+仲裁、index.md 50 模块 | ls + grep 逐表核对 | 4 文件命中 |
| AC-012 | 现有 pytest 回归全绿（18 个测试文件） | `python -m pytest tests/ -q` | 全 PASS/skipped 合法 |
| AC-013 | validate_skill.py 不低于基线 | `python scripts/validate_skill.py` | 32/32 PASS/MUST FIX=0 |
| AC-014 | 50 轮全流程测试通过（覆盖 /plan /do /check /act 四阶段 × 混合脚本类型：技术修复/写作/发布/巡检），每轮产出记忆含主分类+互动复盘段（/act 轮） | 测试脚本+人工记录，报告落 docs_rj/check_rj/ | 50/50 通过 |
| AC-015 | 反向验证：迁移脚本对账故意制造差异（删 1 条正文）→ 脚本 exit 2 报差异 | 删测试副本 1 条文件重跑 | exit 2/差异检出 |

> **AC 映射 task**：AC-001~003→T1；AC-004~006/015→T3；AC-007~009/012→T2；AC-010→T5a；AC-011→T5b；AC-013~014→T6。
>
> **完成条件双指标**：①结果指标：50 轮测试通过 + validate 32/32 + 对账 118=118；②约束指标：迁移零数据丢失（对账相等）+ 回滚零使用（备份在但未动用）。

---

## 6. Spec 层：正例与反例

### 正例
- write_project(task="fix_bug", content="...踩坑：mkstemp 被沙箱拦截...", memory_class="pitfall") → 落 `memory_rj/pitfall/202608/fix_bug_memory_20260825_2130.md` + 索引行 `- 2026-08-25 21:30 | pitfall | 重要性high | is_lesson=true | mkstemp沙箱拦截 workaround | [正文](...)`
- 用户说"给领导汇报" → 仲裁路由 leader_report.md → 生成六段结构文档 + 手绘速览图

### 反例
- memory_class="发布"（中文非法值）→ ❌ 建第 7 个文件夹 → ✅ warning+落 workflow
- 迁移后直接删 memory_main.md.bak_v103 → ❌ 丢回滚能力 → ✅ 保留 7 天回滚窗口（对齐现有 .migrated 机制）
- /act 步骤 1 先写盘再问互动问题 → ❌ 双写两个记忆文件 → ✅ 先问后写同次落盘

---

## 7. Spec 层：技术方案与代码结构

- **文件结构**（新增 5 + 修改 10）：
```
pdca-skill/
├── scripts/
│   ├── memory_tags.py            ★新增（~60行）
│   ├── migrate_memory_v104.py    ★新增（~200行）
│   ├── memory_shadow_write.py    修改（memory_class 参数+路径路由+治理族适配）
│   ├── memory_distill.py         修改（rglob）
│   ├── learn_tidy.py             修改（rglob）
│   ├── loop_admission.py         修改（rglob）
│   ├── handoff_tidy.py           修改（rglob）
│   └── archive_tidy.py           修改（rglob）
├── references/
│   ├── common/da/leader_report.md ★新增
│   ├── common/pa/trigger_hooks.md 修改（钩子行+注释+版本 v1.1.8）
│   ├── common/pa/working_memory_rules.md 修改（两层标签格式规范）
│   ├── common/pa/memory_governance.md 修改（容量统计新口径）
│   ├── act/persist/act_procedure.md 修改（步骤1.5+Glob **）
│   └── index.md                   修改（50 模块）
├── SKILL.md                       修改（/act 1.5+仲裁+索引+版本号）
├── HISTORY.md                     修改（v1.0.4 条目）
└── tests/
    ├── test_memory_tags.py        ★新增
    └── test_migrate_memory_v104.py ★新增
```
- **依赖**：Python 3.8+ 标准库（pathlib/json/re/datetime/shutil），零新依赖

### 7.1 副 agent 使用计划
| 副 agent | 用途 |
|----------|------|
| code_eng_agent_pdca | T2 下游适配后代码审查（只读） |
| learn_opt_agent_pdca | 50 轮测试结果分析（只读） |

---

## 8. Spec 层：依赖关系

- **TECH-001**: Python 3.8+（现有环境已满足）
- **TECH-002**: 外置数据目录 `~/.pdca-skill/data/` 可写（现有，迁移在其内操作）
- 无外部系统依赖

---

## 9. Spec 层：风险与降级

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 迁移中途异常 | 中 | 高 | 双备份先行+失败不删原件+exit 2 停止；回滚=覆盖 .bak_v103 |
| 沙箱拦截 tempfile.mkstemp（历史教训） | 高 | 中 | 迁移/write 脚本全部 open() 直写，禁用 mkstemp；沿用 UTF-8 强制 |
| 旧版 skill 环境混写（M3） | 中 | 高 | .schema_version 检测+告警拒写 |
| 下游适配遗漏（16 脚本引用 memory_main） | 中 | 高 | T2 按对抗审查清单逐项+grep 全量二次扫描；AC-012 回归兜底 |
| 启发式归类误判（20-30% 混合条目） | 高 | 低 | 误判不丢数据（只影响文件夹位置）+ 索引行可查；50 轮测试观察误判率，>30% 时升级人工规则 |
| 50 轮测试 token 消耗大 | 确定 | 中 | 用户已明确"不省 token 不赶时间"；分批跑（每批 10 轮）防上下文溢出 |

---

## 10. Clarifications（澄清增量记录）

| 时间 | 澄清问题 | 回答 | 影响 spec 哪节 | 关键变量 | 未验证假设 | 是否重跑 Self-Review |
|------|----------|------|---------------|---------|-----------|---------------------|
| 2026-08-25 20:50 | 标签体系怎么定？ | 用户：调研 GitHub/Gitee 开源项目 | §0.A/§2 | 调研结论=两层设计 | 无 | 是 |
| 2026-08-25 20:52 | 文件夹结构？ | 标签文件夹+按月子目录 | §3/§4.2 | 无 | 无 | 是 |
| 2026-08-25 20:52 | act 互动形式？ | 动态追问，按任务生成问题 | §4.5 | 无 | 无 | 是 |
| 2026-08-25 20:52 | 汇报场景？ | 结构化汇报文档 | §4.6 | 无 | 无 | 是 |
| 2026-08-25 21:05 | 方案B确认？ | 用户：对抗性审核下方案 | §0.1（触发对抗审查） | 审查发现 4H | 无 | 是 |
| 2026-08-25 21:10 | 修复后确认？ | 用户：讲改后效果 | 效果呈现（场景对比） | 无 | 无 | 否 |
| 2026-08-25 21:15 | 6 标签能覆盖全部记忆？ | 抽样验证：2-3 成混合型按主导归+兜底 | §2/§6 | 误判率待 50 轮实测 | 启发式误判率 <30%（/do T6 验证） | 是 |
| 2026-08-25 21:20 | 新增主分类？ | 用户：没想好，后续可能会增加 | §3（不包含：单点常量留口） | 未来标签数 | 无 | 否 |
| 2026-08-25 21:25 | 测试轮数？ | 50 轮全流程 | §5 AC-014 | 无 | 无 | 否 |

### 10.1 问诊收口摘要
- **已确认事实**：两层标签设计/标签文件夹+按月子目录/动态追问/结构化汇报/全量迁移/feature 分支/50 轮测试/效果认可（三场景对比）/对抗审查 4 HIGH 修复设计回填
- **未验证假设**：①启发式归类误判率 <30%（50 轮测试验证）②memory_distill rglob 改造后解析成功率 100%（T2 单测验证）③118 条对账精确相等（T3 实跑验证）
- **关键变量**：①误判率（超标则升级人工归类规则）②旧版环境是否存在混写场景（影响 schema_version 检测优先级）

---

## Self-Review 自检清单

| # | 检查项 | 通过？ |
|---|--------|--------|
| 1 | 占位符扫描：无 TBD/TODO/适当/类似 | ✓ |
| 2 | 内部一致性：主分类/两层标签/优先级前后一致 | ✓ |
| 3 | 范围：无用户未要求的功能（检索脚本明确排除） | ✓ |
| 4 | 歧义：SKIPPED 语义/跳过/降级均有明确定义 | ✓ |
| 5 | 方案对比：3 方案+明确推荐 B'+理由 | ✓ |
| 6 | 验收标准：15 条全可验证+基线数字 | ✓ |
| 7 | No Placeholders：无伪代码（实现细节到参数/路径级） | ✓ |
| 8 | 错误处理：每 REQ 有边界+错误处理 | ✓ |
| 9 | BRD 对齐：§1.0-1.4 全填+可验证指标 | ✓ |
| 10 | 基线不可退：118=118/32/32/50/50 | ✓ |
| 11 | 命令实测：generate_docs.py 已实测（21:27 成功）；其余命令在 task 标注 /do 实测 | ✓ |
| 12 | 进度记录：task.md 有进度状态+阻塞项 | ✓ |
| 13 | 连败换项：task.md 总览注明 | ✓ |
| 14 | 反向验证：AC-015 标注（对账故意制造差异） | ✓ |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-08-25 21:27 | 初版（含对抗审查 4H/7M/4L 修复设计回填） |

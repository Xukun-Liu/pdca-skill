<!-- PDCA标签：P.bootstrap A.persist -->
<!-- 子标签场景：文档汇总视图 -->
<!-- 关键词清单：SUMMARY/根索引/漂移检查/文档汇总/根索引刷新 -->
<!-- 引用范围：main + bootstrap_agent + sync_agent -->

# 汇总视图规范（Summary View）
> 阶段标签：P · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 更新：2026-07-29

> 📖 **什么时候读这个文件**：
> - 不确定 SUMMARY_RJ.md 该写什么/怎么写时
> - 不确定什么时候触发 SUMMARY 更新时
> - 跑漂移检查（链接有效性核对）时
> 🔴 **不要在这时候读**：
> - 已在按三触发正常维护 SUMMARY 时

---

## 一、SUMMARY_RJ.md 是什么

`{主docs}/SUMMARY_RJ.md` 是项目全部文档的**根索引**——用 markdown 链接把 memory + spec + task + handoff 互连成知识图谱。核心思想：

- **只做导航，不做内容**：SUMMARY 只放"链接 + 一句话描述"，内容仍在原文件（导航/内容分离）
- **每个 section 有 leading paragraph**：≤250 字符概述本 section 涵盖哪些文档
- **漂移检查**：grep 提取所有链接 → ls 确认文件存在

> **与 spec_main_rj.md 的职责区分**：SUMMARY_RJ.md 只做导航（链接列表），spec_main_rj.md 做项目总 spec（目标/PRD/技术栈/宪法/任务/ADR/状态，最新置顶）。两者同级，互不重复。详见 [docs_rj/spec_main_rj.md](../docs_rj/spec_main_rj.md)。

## 二、文件位置

`{workspace}/{主docs}/SUMMARY_RJ.md`

> 与 {主docs}/ 同级（扁平5类结构），是主 docs 目录下唯一的根索引文件。
> 主 docs 路径见 `.primary_docs_rj` 标记，默认 `./docs_rj/`（详见 [document_specs.md](../pda/document_specs.md)「多 docs 目录处理」）；全局记忆路径固定在 skill 包 `memory/`。

## 三、生成/更新时机【硬性】（三个触发点）

| # | 触发时机 | 动作 | 由谁触发 |
|---|---------|------|---------|
| 1 | **启动检查时** | 读 SUMMARY_RJ.md 建立全局认知；若不存在则创建（见下方「创建流程」） | SKILL.md §1 启动检查 |
| 2 | **对话结束（记忆写入落盘）时** | 刷新 SUMMARY（更新 last_updated + 新增/变更文档条目） | working_memory_rules.md §2 记忆写入流程 |
| 3 | **交接时** | 生成交接文档后，同步刷新 SUMMARY，确保接手方一眼看全 | sync-matrix.md §五 任务交接 |

**创建流程**（触发1中 SUMMARY 不存在时）：
1. 复制 `assets/summary_template.md` 到 `{主docs}/SUMMARY_RJ.md`
2. 填 frontmatter：title=项目名、version=当前 SKILL.md 版本号、last_updated=当前时间、total_docs=0（待填）、require-rule-mention=true
3. 逐 section 扫描主 docs 目录，把存在的文档填入对应 section（链接 + 一句话描述）
4. 无文档的 section 保留标题 + leading paragraph，正文写"暂无"
5. 填完跑漂移检查（见§五），同步 total_docs
6. 不静默创建——告知你"SUMMARY_RJ.md 不存在，已用模板创建并扫描填充，请确认"

**禁止**：
- ❌ 跳过任一触发点（三触发都是硬性）
- ❌ SUMMARY 里复制原文件内容（违背导航/内容分离）
- ❌ 链接指向不存在的文件（漂移）

> 🚀 **自动化（R4）**：漂移检查已纳入 `scripts/startup_tidy.py` 的 `run()` 末尾，每次启动整理自动执行（见 `drift_check()`），无需手动触发。SUMMARY 刷新（`SummaryRefresher.refresh()`）也在同一步骤内完成。

## 四、SUMMARY_RJ.md 模板结构

见 `assets/summary_template.md`。支持两种实现模式（v1.1.0 新增模式 B）：

### 模式 A：逐文件列出（原 v1.0.0 模式）

1. **Frontmatter**：title / version / last_updated / total_docs / require-rule-mention
2. **leading paragraph**：≤250 字符概述本文件作用
3. **🧠 Memory 文档** section：列出 `memory/memory_main.md`（全局聚合）+ 所有 `{项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md`
4. **📋 Spec 文档** section：列出所有 {主docs}/spec_rj/{任务名}_spec_*.md
5. **✅ Task 文档** section：列出所有 {主docs}/task_rj/{任务名}_task_*.md
6. **🤝 Handoff 文档** section：列出所有 {主docs}/handoff_rj/{任务名}_handoff_*.md
7. **🔗 漂移检查清单** section：grep 命令模板

### 模式 B：INDEX 二级索引（v1.1.0 新增，推荐大项目用）

当项目文件数超过 20 时，逐文件列出会导致 SUMMARY 膨胀难维护。此时可用 INDEX 二级索引模式：

1. **Frontmatter**：同模式 A
2. **leading paragraph**：≤250 字符概述本文件作用
3. **📂 类目全量索引** section：列出 5 个子目录的 INDEX.md 链接（memory_rj/INDEX.md、spec_rj/INDEX.md、task_rj/INDEX.md、handoff_rj/INDEX.md、archive_rj/INDEX.md），每个 INDEX.md 内部再逐文件列出 + 状态标注（active/superseded/archived）
4. **当前活跃任务** section：列出所有 status≠archived 的任务（任务名 + 状态 + TASK_STATE 链接）
5. **文档索引** section：项目当前状态描述 + Bootstrap 填充情况

**模式 B 优势**：①SUMMARY 只维护 INDEX 链接（不维护文件列表），减少漂移；②每个 INDEX.md 内部维护自己类目的文件列表 + 状态，职责单一；③handoff_tidy.py 自动维护 5 个 INDEX.md，SUMMARY 自动维护"当前活跃任务"section。
**模式 B 劣势**：多一层跳转（SUMMARY → INDEX → 文件），不适合小项目。
**选择标准**：文件数 ≤20 用模式 A，>20 用模式 B。riji-skill-public v1.0 目前 40 文件，用模式 B。

每个 section 顶部必须有 leading paragraph（≤250 字符）。

**模板占位符处理**：模板中的 `{项目名}`/`{版本号}`/`{日期}` 等占位符用实际值替换。无对应文档的 section 不删除，保留标题 + leading paragraph + 正文写"暂无"。

**250 字符校验方法**：leading paragraph 写完后，用字符计数确认≤250 字符（中文1字=1字符）。超250 则精简——删修饰词、留核心信息（"本 section 列出所有 spec 文档，按任务名分组"而非"本 section 用于列出和归档项目中所有的需求规格文档，方便快速查找"）。目测标准：不超过2行（终端宽度80字符时）。

## 五、漂移检查（替代 lat check）

**触发时机**：每次更新 SUMMARY 后必跑（三个触发点都跑）。

**检查步骤**：

1. **提取所有链接**：grep `]\(` SUMMARY_RJ.md，提取所有 `[显示名](路径)` 中的路径
2. **逐个确认存在**：对每个路径 ls 确认文件存在
3. **发现漂移处置**：
   - 文件不存在 → 从 SUMMARY 删除该条目，或修复路径
   - 文件存在但未在 SUMMARY 列出 → 补充条目
4. **更新 frontmatter**：total_docs 字段同步实际条目数

**降级**：若 grep/ls 不可用（Windows PowerShell 限制），用 Read 工具逐个确认。

**跨行链接降级**：markdown 链接可能跨行（`[显示名]\n(路径)`），grep `]\(` 单行匹配会漏。降级处理：①优先用多行匹配（grep -P `]\(\s*` 或 ripgrep -U）；②若工具不支持多行，用 Read 工具读 SUMMARY_RJ.md 全文，人工扫链接；③跨行链接统一改为单行（SUMMARY 维护时强制链接写在一行内）。

> 🚀 **自动化（R4）**：漂移检查（`drift_check()`）已纳入 `scripts/startup_tidy.py` 的 `run()` 末尾自动执行——每次启动整理会刷新 SUMMARY 并跑漂移检查，输出 `TidyReport.drift` 与 `drift_missing`。手动跑仅作补充。

## 六、require-rule-mention 机制

SUMMARY frontmatter 加 `require-rule-mention: true`，含义：SUMMARY 中列出的每个文档，须被 SKILL.md 或 references/ 中至少一条规则引用（说明何时读它）。

**检查方法**：对 SUMMARY 列出的每个文档路径，grep 该文件名在 SKILL.md + references/ 中的引用。若某文档无任何规则引用，提示你"该文档游离于规则体系外，是否补规则或归档"。

**豁免范围**：以下文档类型豁免 require-rule-mention 检查（它们是任务产出物，不需要被规则引用）：
- `{主docs}/spec_rj/{任务名}_*.md`——spec 是任务级产出，由 document_specs.md 规则统一覆盖，不需要逐个引用
- `{主docs}/task_rj/{任务名}_*.md`——task 是任务级产出，同上
- `{主docs}/handoff_rj/{任务名}_*.md`——handoff 是任务级产出，同上
- `docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md`——项目记忆由 working_memory_rules.md 统一覆盖

**需检查的文档**：`memory/memory_main.md`、`SUMMARY_RJ.md` 本身、references/ 下的文件——这些必须被规则引用，否则游离于体系外。

## 七、反模式

| 反模式 | 正确做法 |
|--------|----------|
| SUMMARY 里复制原文件内容 | 只放链接 + 一句话描述 |
| 链接指向不存在的文件 | 跑漂移检查，修复或删除 |
| 只在启动时更新，结束/交接不更新 | 三触发都更新（硬性） |
| section 无 leading paragraph | 每个 section 顶部写 ≤250 字符概述 |
| total_docs 与实际条目数不一致 | 更新后同步 frontmatter |

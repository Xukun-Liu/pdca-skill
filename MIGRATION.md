---
title: riji-skill 文档规整指南
skill_version: v1.0.1
last_updated: 2026-07-30 10:00
---

<!-- PDCA标签：A.tidy -->
<!-- 子标签场景：版本规整/老文档整理/migration -->
<!-- 关键词清单：规整文档/升级文档/按新版本规整/migrate docs/regularize/按新标准整理 -->
<!-- 引用范围：main + sync_agent -->

# 文档规整指南（v1.0.0）

> 版本：v1.0.0 | 更新：2026-07-30 10:00
>
> 适用范围：项目 `docs_rj/` 下的 spec / task / handoff / memory / SUMMARY_RJ.md
>
> 禁止触碰：skill 包自带 `assets/` 模板（仅引用，不改写）、`scripts/`、`references/`、`protocol/` 等框架自身文件
>
> 触发方式：用户喊"规整文档 / 升级文档 / 按新版本规整 / migrate docs / regularize"时，AI 读取本文件后按 §4 流程执行

---

## §1 当前版本标准（v1.0.0）

### 1.1 字段标准唯一来源

为避免与模板漂移，本文件不手写"当前 frontmatter 应该有什么字段"，统一以 `assets/` 模板为唯一来源：

| 文档类型 | 唯一来源模板 |
|----------|------------|
| spec | [assets/spec_template.md](assets/spec_template.md) frontmatter |
| task | [assets/task_template.md](assets/task_template.md) frontmatter |
| handoff | [assets/handoff_template.md](assets/handoff_template.md) frontmatter |
| memory | [assets/memory_template.md](assets/memory_template.md) frontmatter |
| spec_main | [assets/spec_main_template.md](assets/spec_main_template.md) frontmatter |
| SUMMARY | [assets/summary_template.md](assets/summary_template.md) frontmatter |

**读取规则**：整理时 AI 先读对应模板 frontmatter，以模板字段为准。

### 1.2 一致性硬规则

- frontmatter `version` 字段 与 正文 `> 版本：vX.X.X` 注释必须一致，统一为 v1.0.0
- frontmatter `skill_version` 字段记录"按哪个 riji-skill 版本生成的"，新文档生成时自动带 v1.0.0，老文档规整后补 v1.0.0
- `skill_version` 与 SKILL.md 头部 HTML 注释 `<!-- Skill 版本：v1.0.0 -->` 必须一致

---

## §2 老文档识别方法

按以下优先级（从高到低）判定每个文档是否需要规整：

| 优先级 | 信号 | 判定 | 处置 |
|--------|------|------|------|
| 1 | frontmatter 完全缺失 | v1.0 早期 | 触发"补全 frontmatter"步骤 |
| 2 | frontmatter 无 `skill_version` 字段 | 老版本，未打戳 | 需规整，补 skill_version |
| 3 | frontmatter `skill_version` < v1.0.0 | 已打戳但版本旧 | 需规整，更新 skill_version |
| 4 | 正文 `> 版本：` 注释与 frontmatter `version` 不一致 | 内部漂移 | 需规整，统一版本号 |
| 5 | 内容特征：无 §0 设计层 / 无 GWT 验收标准 / 无进度状态字段 | 老版本内容 | 需规整，按 §3 处置结构差异 |

**识别流程**：逐文件按优先级 1→5 检查，命中任一即标记为"需规整"。

---

## §3 整理步骤（按文档类型）

### 3.1 spec 整理

**字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `title` | 有 | 有 | 保留原值 |
| `version` | 有 | v1.0.0 | 更新为 v1.0.0 |
| `skill_version` | 无 | v1.0.0 | 补：v1.0.0 |
| `date_created` | 有 | 有 | 保留原值 |
| `last_updated` | 有 | 有 | 更新为当前整理时间 |
| `owner` | 有 | 有 | 保留原值 |
| `tags` | 无 | [] | 补：[]（空数组，由用户后续填） |
| `derived_from` | 无 | spec_main_rj.md §X | 补：`spec_main_rj.md §X`（X 由用户确认；无 spec_main 时填 `[待补]`） |

**结构差异处置**：

- 缺 §0 设计层（第一性原理拆解）：标记 `<!-- §0 设计层：本任务为简单任务，跳过 -->`，**不自动补空段**（避免猜测内容）
- 缺 §10 Clarifications：不补（用户澄清记录，不可猜测）
- 用户自定义章节：**保留原样**，仅规整 frontmatter + 标准章节

**废弃字段处置**：v1.0 → v1.0.0 仅新增字段不删除字段，无废弃字段需处理。

### 3.2 task 整理

**字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `title` | 有 | 有 | 保留原值 |
| `version` | 有 | v1.0.0 | 更新为 v1.0.0 |
| `skill_version` | 无 | v1.0.0 | 补：v1.0.0 |
| `date_created` | 有 | 有 | 保留原值 |
| `last_updated` | 有 | 有 | 更新为当前整理时间 |
| `spec_ref` | 无 | spec_rj/{task}_spec_{date}.md | 补：按文件名推导（同名 spec 文件路径） |

**结构差异处置**：

- 缺 REQ-038 进度状态：在总览补"进度状态：未开始/进行中/已完成/阻塞"（按内容推断，无法推断填"未开始"）
- 缺 REQ-039 阻塞项：补"阻塞项：无"
- 缺 REQ-040 开工回执：**保留原样，不补**（避免猜测用户意图）
- 缺 REQ-041 项目纪律：补"项目纪律：无"

### 3.3 handoff 整理

**字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `title` | 有 | 有 | 保留原值 |
| `version` | 有 | v1.0.0 | 更新为 v1.0.0 |
| `skill_version` | 无 | v1.0.0 | 补：v1.0.0 |
| `date_created` | 有 | 有 | 保留原值 |
| `last_updated` | 有 | 有 | 更新为当前整理时间 |
| `handoff_from` | 无 | [交接人] | 补：`[待补]` |
| `handoff_to` | 无 | [接手人] | 补：`[待补]` |
| `status` | 无 | [进行中/暂停/完成] | 补：按内容推断，无法推断填"进行中" |

**结构差异处置**：无结构差异（handoff 结构稳定）。

### 3.4 memory 整理

> ⚠️ memory 文件**无 YAML frontmatter**，用 markdown 加粗字段存储元数据。`write_project` / `memory_shadow_write` 写入格式：
> ```
> ### 记忆条目 · {task}（{timestamp}）
> **意图**：{intent}
> **上下文**：{context}
> **工具**：...
> **反馈**：...
> **结果**：...
> **标签**：...
> ```
> 整理时按相同格式处理，不引入 YAML frontmatter。

**元数据字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `**标签**` | 有 | 有 | 保留原值 |
| `**结果**` | 有 | 有 | 保留原值 |
| `**skill_version**` | 无 | v1.0.0 | 在 `**标签**` 与正文之间补 `**skill_version**: v1.0.0` |

**整理规则**：

- 已有 memory 文件：在 `**标签**` 行后插入 `**skill_version**: v1.0.0`
- 无 `**标签**` 行（极简格式）：在 `### 记忆条目` 标题行后插入 `**skill_version**: v1.0.0`
- 已含 `**skill_version**` 且 = v1.0.0：跳过（幂等）
- 已含 `**skill_version**` 但 < v1.0.0：更新为 v1.0.0
- 关键决策/阶段记录/用户自定义章节：保留原样，不补

### 3.5 SUMMARY 整理

**字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `title` | 有 | 有 | 保留原值 |
| `version` | 有 | v1.0.0 | 更新为 v1.0.0 |
| `skill_version` | 无 | v1.0.0 | 补：v1.0.0 |
| `last_updated` | 有 | 有 | 更新为当前整理时间 |
| `total_docs` | 无 | N | 补：自动统计 docs_rj/ 下 .md 文件数 |

**结构差异处置**：保留用户手写内容（导航链接、分类、备注），仅刷 frontmatter。

### 3.6 spec_main 整理

**字段映射表**：

| 字段 | v1.0 | v1.0.0 必填 | 缺失处置 |
|------|------|------------|----------|
| `title` | 有 | 有 | 保留原值 |
| `version` | 有 | v1.0.0 | 更新为 v1.0.0 |
| `skill_version` | 无 | v1.0.0 | 补：v1.0.0 |
| `date_created` | 有 | 有 | 保留原值 |
| `last_updated` | 有 | 有 | 更新为当前整理时间 |
| `owner` | 有 | 有 | 保留原值 |
| `tags` | 有 | 有 | 保留原值 |
| `derived_from` | 有 | 有 | 保留原值（顶层模板为 null） |
| `based_on` | 有 | 有 | 保留原值（顶层模板为 null） |

**结构差异处置**：保留用户手写内容，仅刷 frontmatter。

### 3.7 不参与规整的模板

以下 6 个模板加了 `skill_version` 字段但**不参与自动规整**（非 docs_rj/ 下的用户文档，而是 skill 包框架文件）：

| 模板 | 原因 |
|------|------|
| `memory_bootstrap_template.md` | 全局 memory_main.md 模板，非项目 docs_rj/ 文件 |
| `skill_graph_template.md` | skill_graph.md 渲染模板，非用户文档 |
| `market_research_template.md` | 市场调研报告模板，非核心文档类型 |
| `daily_log_template.md` | 归档日志模板，非核心文档类型 |
| `archive_template.md` | 归档任务袋模板，非核心文档类型 |
| `index_template.md` | 类目 INDEX.md 模板，非核心文档类型 |

这些模板加 `skill_version` 仅用于"模板自身版本标记"，AI 整理 docs_rj/ 时跳过。

```
1. 扫描
   ├─ 遍历 docs_rj/{spec_rj,task_rj,handoff_rj,memory_rj}/*.md + docs_rj/SUMMARY_RJ.md
   └─ 排除：TASK_STATE_*.md / .spec_main_version_cache / 隐藏文件 / archive_rj/
       / INDEX.md / DEPENDENCY_MAP.md（状态文件，不规整）

2. 识别（按 §2 优先级 1→5 逐文件判定）
   └─ 标记每个文档为"需规整"或"已对齐"

3. 预览（HARD-GATE 确认点）
   ├─ 列出"老文档清单 + 每个要改什么 + 备份路径"
   ├─ 上限 20 个，超出分页提示"剩余 N 个，是否继续？"
   └─ 用户三选一：全部改 / 只改某类（如只改 spec）/ 取消

4. 备份（用户确认后）
   ├─ 备份目录：docs_rj/migration_backup_{时间戳}_{序号}/
   │   （序号防同时间戳覆盖，如 migration_backup_20260730_1000_1/）
   ├─ 目录不存在则创建
   └─ 整理前逐文件备份（不整批打包，便于单文件回滚）

5. 整理（按 §3 逐文件逐字段）
   ├─ 每文件整理前已备份
   ├─ **frontmatter 改动前先检测 `---` 边界**：缺失 `---` 的文件跳过 + 告警 + 记录到失败清单
   ├─ 按字段映射表补/改 frontmatter（文本替换，不引入 YAML 解析依赖）
   ├─ 按结构差异处置规则处理正文
   ├─ 用户自定义章节一律保留原样
   ├─ **遇到"需用户确认"字段时停下批量询问**：列出所有需确认的字段和候选值，用户确认后继续
   ├─ **文档被其他进程锁定时**：跳过该文件 + 告警 + 记录到失败清单，不阻断其余文件

6. 验证
   ├─ grep `TBD|TODO|适当处理|类似XX` 占位符扫描（`[待补]` 为合法豁免，不计入）
   ├─ python scripts/startup_tidy.py --dry-run 漂移检查
   └─ 逐文件 frontmatter 字段比对（对照 §3 映射表）

7. 回滚（如整理失败 = 整理时抛异常 或 验证步骤 grep 非零匹配）
   ├─ 整理失败时立即停（不继续后续文件）
   ├─ 从备份目录逐文件整文件覆盖还原（备份是整理前完整快照）
   ├─ 删除半整理版本（如有）
   └─ 告警用户"整理失败，已回滚到整理前状态，请检查 X 文件"

8. 汇报
   ├─ 列出改了哪些文件 + 每个改了什么（补了哪些字段/改了什么结构）
   ├─ 验证结果（占位符扫描/漂移检查/frontmatter 比对）
   └─ 备份目录路径

9. 写 memory（Memory First 硬规则）
   ├─ 经 write_project 写 memory_rj/migration_memory_{时间戳}.md
   ├─ 记录：整理时间 / 范围 / N 个文件 / 备份路径 / 验证结果
   └─ 自动 upsert 全局 memory_main.md
```

### 边界 case 处置

| 场景 | 处置 |
|------|------|
| 空 docs_rj/（新项目刚 bootstrap） | 扫描后报告"无老文档，跳过规整" |
| 100+ 老文档 | 预览分页，每页 20 个，超出提示"剩余 N 个，是否继续？" |
| 同一文档被多次整理（用户喊两次"规整文档"） | 读 skill_version 戳，已是 v1.0.0 → 跳过，仅记录 no-op |
| 跨语言文档（中文 spec + 英文 task） | 规则一样（字段名是英文，与语言无关） |
| 用户自定义章节 | 保留原样，仅规整 frontmatter + 标准章节 |
| 状态文件（TASK_STATE_*.md / .spec_main_version_cache） | 排除，不规整 |

### 安全性

- **范围限定**：仅 `{项目根}/docs_rj/{spec_rj,task_rj,handoff_rj,memory_rj}/*.md` + `docs_rj/SUMMARY_RJ.md`
- **禁止触碰**：skill 包自带 `assets/` 模板 / `scripts/` / `references/` / `protocol/` 等框架自身文件
- **备份目录不存在则创建**，加序号防覆盖：`migration_backup_{时间戳}_{序号}/`
- **整理失败**：立即停 + 回滚该文件 + 告警用户（不继续后续文件）
- **memory_rj 不可写**：告警用户，不静默跳过 memory 写入

---

## §5 每次版本升级时的维护（8 步）

skill 版本升级（如 v1.0.0 → v1.2.0）时，按以下 8 步维护本文件：

| 步骤 | 动作 | 责任 |
|------|------|------|
| 1 | 更新 MIGRATION.md frontmatter `skill_version` | 与 SKILL.md 头部 HTML 注释一致 |
| 2 | 检查全部 12 个 `assets/*_template.md` frontmatter 是否有字段变更（§1 引用的 6 核心模板 + §3.7 列出的 6 非核心模板） | 如有变更，§1 引用关系不变（仍指向模板），但 §3 字段映射表要补新字段。**全部 12 模板的 `skill_version` 戳必须同步更新**（含 §3.7 不参与规整的 6 个，避免版本号残留） |
| 3 | 更新 §2 识别方法 | 如新版本引入新字段，补"无 {新字段}"作为识别信号 |
| 4 | 更新 §3 字段映射表 | 如新增字段需补到老文档，加映射行 |
| 5 | 更新 §3 结构差异处置 | 如新版本引入新结构，补处置规则 |
| 6 | 死引用检查 | grep 附录引用的文件路径是否仍存在（sync-matrix.md / trigger_hooks.md / bootstrap.md / project_structure.md / startup_tidy.py / learn_tidy.py）；如 references/ 目录重构，同步更新附录路径 |
| 7 | skill 包根目录变更检查 | 扫根目录文件删/增，特别盯 §1 启动检查依赖的标记文件（`.primary_docs_rj` 等）；如删除 §1 依赖的标记文件，先确认 SKILL.md / references 是否同步更新引用 |
| 8 | 在 HISTORY.md 追加版本行 | 记录版本号 + 变更说明 + 指向本文件的维护动作 |

**单一来源原则**：本文件 §5 是"版本升级时如何维护 MIGRATION.md"的唯一来源；`sync-matrix.md` 第一章只引用本文件，不重复步骤。

---

## §6 版本收敛策略

- **§3 整理步骤按版本累积**：v2.0 时如 §3 膨胀 > 500 行，旧版本步骤在本文件内折叠到 `## 历史整理步骤（v1.x）` 段（skill 包内归档，不放项目 docs_rj/）
- **MIGRATION.md 自身永远是当前 skill 版本**：skill 删了重装即更新（用户痛点：skill 包永远干净最新）
- **被整理文档打 skill_version 戳后**：下次规整时读该戳判定是否需要再规整，避免重复整理
- **version 与 skill_version 区分**：`version` = 文档自身内容修订版（v1.0.0 → v1.1.1 → v1.2.0），`skill_version` = 生成它的 riji-skill 版本，二者可不同

---

## 附录：与现有机制的关系

| 现有机制 | 与本文件关系 |
|----------|------------|
| [sync-matrix.md](references/common/da/sync-matrix.md) | sync-matrix 核对"版本号一致性"（只读不改）；本文件"规整文档内容"（改内容）。互补不冲突 |
| [trigger_hooks.md](references/common/pa/trigger_hooks.md) | 新增触发词路由到本文件，与现有"整理文档"（路由到 sync-matrix）区分 |
| [bootstrap.md](references/plan/bootstrap/bootstrap.md) | bootstrap 处理"完全缺失"（首次使用）；本文件处理"已存在但版本旧"（版本规整） |
| [project_structure.md](references/plan/design/project_structure.md) | project_structure 标 `legacy` 不规整内容；本文件规整内容（archive_rj 下的 legacy 文件不规整） |
| [startup_tidy.py](scripts/startup_tidy.py) | startup_tidy 整理散落文档（物理位置）；本文件整理文档内容（frontmatter/结构） |
| [learn_tidy.py](scripts/learn_tidy.py) `migrate_memory_entries` | learn_tidy 迁移 memory 条目格式；本文件迁移全量文档 frontmatter + 结构（范围更大） |

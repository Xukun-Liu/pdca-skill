---
version: v1.1.0
skill_version: v1.1.0
---

<!-- PDCA标签：A.tidy -->
<!-- 子标签场景：类目索引模板 -->
<!-- 关键词清单：INDEX/类目索引/最新文件/active/superseded -->

# {category_name}/ 类目索引模板

> 本模板是 INDEX.md 的"骨架示例"。实际 INDEX.md 由 `scripts/handoff_tidy.py`
> 在 /act 阶段自动生成（`_refresh_category_indexes` 方法），**禁止手工编辑**。
> 模板用途：①规范字段格式 ②给文档管理工具参考结构 ③人工对照检查。

## 一、生成时机

- **触发**：`/act` 阶段 handoff_tidy.py 跑 step 4.7
- **频率**：每次 /act 都刷新（幂等覆盖，时间戳更新）
- **目录范围**：`memory_rj/` / `spec_rj/` / `task_rj/` / `handoff_rj/` / `archive_rj/`
- **执行顺序**：`_refresh_category_indexes` 先跑（生成 INDEX.md），`_annotate_summary_recency` 后跑（SUMMARY 标注 + 插入 INDEX 入口块）
  - 原因：`_annotate_summary_recency` 内部调 `_ensure_index_entries_in_summary` 检查 INDEX.md 存在性，必须先有 INDEX.md 才能插入入口块
  - 全新项目第一次 /act 也能正确工作（INDEX.md 从无到有）
- **跨项目使用**：脚本路径基于 `resolve_primary_docs()` 解析（4 级优先级：显式参数 > marker > memory > 约定查找），不依赖 skill 包路径，用户在自己项目跑 /act 也能正确生成 INDEX.md

## 二、INDEX.md 标准格式

```markdown
# {subdir}/ 类目索引

> 自动生成，请勿手工编辑。由 handoff_tidy.py /act 时刷新。
> 最后刷新：2026-07-23 14:30

| 状态 | 文件 | 任务前缀 | 最后更新 |
|------|------|----------|----------|
| 🟢 active | [remove_resume_add_knowledge_spec_20260723_1430.md](./spec_rj/remove_resume_add_knowledge_spec_20260723_1430.md) | remove_resume_add_knowledge | 2026-07-23 14:30 |
| 🟢 active | [server_lite_v2_spec_20260722_2345.md](./spec_rj/server_lite_v2_spec_20260722_2345.md) | server_lite_v2 | 2026-07-22 23:45 |
| 🟢 active | [spec_main_rj.md](./spec_rj/spec_main_rj.md) | - | 无时间戳 |
| 🟡 superseded | [fifty_real_scenarios_tests_spec_20260722_1430.md](./spec_rj/fifty_real_scenarios_tests_spec_20260722_1430.md) | fifty_real_scenarios_tests | 2026-07-22 14:30 |

## 状态说明
- 🟢 active: 当前最新版本，应优先查看
- 🟡 superseded: 同任务有更新版本或任务已结束，仅供参考
- ⚪ archived: 已归档至 archive_rj/（本索引不列）
```

## 三、状态判定规则（实现见 tidy_common._classify_file_status）

### 1. 分组规则

| 文件类型 | 分组 key | 状态 |
|----------|---------|------|
| `spec_main_rj.md` / `SUMMARY_RJ.md` | `SPECIAL:{filename}` | active（永远） |
| `TASK_STATE_*.md` | `TASK_STATE:{filename}` | active（永远） |
| `{task}_{type}_{ts}.md`（匹配正则，type 含 archive） | `TASK:{task_prefix}_{type}` | 组内按时间戳判定（archive_rj：folder 标 archived，file 标 legacy） |
| 其余孤儿文件 | `ORPHAN:{filename}` | active（保守，不误判） |

### 2. 同任务组内状态判定

- **有时间戳文件**：按时间戳降序，最新 → active，其余 → superseded
- **无时间戳文件**（如 `{task}_memory.md`）：保守标 active，不与有时间戳的同组文件互斥
- **示例**：
  - `server_lite_v2_spec_20260722_2345.md`（仅此一个有时间戳）→ active
  - `server_lite_v2_spec_20260725_0900.md`（如有更新版本）→ active，前一个变 superseded

### 3. 文件名正则

```
^([a-z0-9_]+?)_(spec|task|memory|handoff|archive)_(\d{8}_\d{4}|memory)\.md$
```

| 字段 | 含义 | 示例 |
|------|------|------|
| group 1 | task 前缀 | `server_lite_v2` |
| group 2 | 文件类型 | `spec` / `task` / `memory` / `handoff` / `archive` |
| group 3 | 时间戳或 `memory` | `20260722_2345` 或 `memory` |

### 4. 时间戳格式化

`YYYYMMDD_HHMM` → `YYYY-MM-DD HH:MM`

例：`20260722_2345` → `2026-07-22 23:45`

## 四、与 SUMMARY_RJ.md 时效标注的关系

| 维度 | SUMMARY_RJ.md | INDEX.md |
|------|---------------|----------|
| 范围 | 全局根索引（5 类目） | 单类目局部 |
| 标注 | `最新·{ts}` / `历史·{ts}` 内联 | `🟢 active` / `🟡 superseded` / `⚪ archived` 列 |
| 视角 | 跨类目导航 | 同类目全貌 |
| 生成 | `_annotate_summary_recency` | `_refresh_category_indexes` |
| 导航链接 | 含 INDEX 入口块（5 个类目 INDEX.md 链接） | 无回链（单向导航） |

两者互补：SUMMARY 看"哪个最新 + 跳到 INDEX"，INDEX 看"同类目还有谁 + 状态"。

## 五、排序规则

INDEX.md 表格按以下规则排序：

1. active 在前，superseded 在后
2. 同状态内按时间戳降序（最新优先）
3. 无时间戳文件排在同状态末尾

## 六、降级与异常

| 场景 | 处理 |
|------|------|
| 类目目录不存在 | 跳过，不报错 |
| 类目目录为空 | 跳过，不生成 INDEX |
| 文件名不匹配正则 | 标 ORPHAN，状态 active（保守） |
| dry-run 模式 | 不写文件，仅打印 `[dry-run] 将创建/更新 INDEX.md: ...` |
| 写入失败 | 记录 error，继续处理下一类目（不阻断） |

## 七、版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-23 | 初始版本，对应 handoff_tidy.py step 4.7 |
| v1.1 | 2026-07-23 | 加 archive_rj 类目（⚪ archived 状态）；SUMMARY 加 INDEX 入口块（方案 A 单向导航）；修复执行顺序 bug（先 _refresh_category_indexes 再 _annotate_summary_recency，确保全新项目第一次 /act 也能插入入口块）；验证跨项目使用（脚本不依赖 skill 包路径） |

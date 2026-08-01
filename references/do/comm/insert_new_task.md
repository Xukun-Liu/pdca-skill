<!-- PDCA标签：D.comm -->
<!-- 子标签场景：/do 执行中插入新任务处置（打断/挂起/恢复） -->
<!-- 关键词清单：插入新任务/打断/新需求/挂起/暂停/恢复任务/paused/TASK_STATE/插队/回到原任务 -->
<!-- 引用范围：main -->

# 执行中插入新任务处置（自 SKILL.md §6 /do 第10项下沉，唯一维护源）

> 版本：v1.0.0 | 创建：2026-08-01
> 阶段标签：D.comm

> 📖 **什么时候读这个文件**：/do 执行中用户插入新需求，且判定**不在当前任务范围内**时必读（4 步打断流程）。
> 🔴 **不要在这时候读**：新需求在范围内（直接当子任务追加即可，无需读本文件）。

---

## 触发判定（agent 判断新需求是否超当前任务范围）

- 复杂任务（有 `spec_rj/{task}_spec_*.md`）→ 按 spec "范围/功能"节判定
- 简单任务（无 spec）→ 按 `TASK_STATE.md` 的 Goal 字段 + memory 中记录的任务定义判定 + memory 留痕判定依据
- 模糊 → 按 1% 原则（有 1% 可能性在范围内 → 当子任务处理）

## 在范围内 → 当子任务处理

追加到当前 task.md 末尾，**继续完成当前进行中的 task 项后做新项**（符合铁律7；不打断；若当前项卡住触发 3-Strike，先 escalate 用户决定，不自动跳到新项）。

## 不在范围内 → 4 步打断流程

### 步骤1：原任务挂起

- `TASK_STATE_{原任务id}.md` 的 `status` 改为 `paused`，frontmatter 加 `paused_reason: "用户插入新任务 {新任务名}"`
- `task_rj/{原任务}_task_*.md` frontmatter 结束（第二个 `---`）后、第一个 `##` 段落前插入暂停行（避免破坏 YAML frontmatter）：`> ⏸ 暂停于 {YYYY-MM-DD HH:MM}，因插入新任务 {新任务名}，当前进度：第 N 个 `##` 段落已完成，第 N+1 个 `##` 段落进行中`（计数基准：task.md frontmatter 后的 `##` 段落数，不含 frontmatter）
- 经 `write_project(task=原任务名, content="挂起原因+新任务名+进度")` 写 memory（挂起记录落原任务 memory 文件，避免下次 /plan 读原任务时断链）

### 步骤2：新任务 HARD-GATE（含 spec/task 选择）

- agent 先按 §4 任务分级判定复杂/简单，呈现判定 + 理由
- 用户**确认/推翻**判定（用户跳过 → 默认简单任务 + TASK_STATE 留痕"用户跳过复杂/简单判定"）
- 复杂任务 → 走 §5 阶段1 完整 spec/task 流程（调 generate_docs.py 建文档目录）
- 简单任务 → 走最低流程（memory 留痕 + 一句话方案 HARD-GATE 确认后直接做）

### 步骤3：执行新任务

- 复杂任务走完整 PDCA（/do→/check→/act）
- 简单任务走最低流程（确认→做→验证→memory）
- 新任务执行中触发熔断（如 3-Strike）→ 按现有熔断流程 escalate 用户，原任务保持 paused

### 步骤4：回到原任务

- 新任务完成后问用户："回到原任务 {原任务名} 吗？（暂停于第 N 个 `##` 段落）"
- 用户选"回" → `TASK_STATE` status 改 `pending`（恢复正常执行态；handoff_tidy.py 一致性保障会自动清除 paused_reason，无需 agent 手工删除）+ memory 留痕"恢复原任务" + 读回原 task.md 定位到暂停行记录的"第 N+1 个 `##` 段落进行中"继续（按 `##` 段落数定位，不依赖编号）
- 用户选"不回" → 按用户选择处置（继续暂停 / 标记 abandoned / 稍后回）
- **跨会话降级**：若 task.md 已被 handoff_tidy 归档到 `archive_rj/`，恢复机制为：①从 `archive_rj/{task}_{ts}/` 复制 task.md 到 `task_rj/`（不删除归档原件，保留历史）②重建 `TASK_STATE` status=pending ③刷新 SUMMARY_RJ.md 链接（避免断链）④memory 留痕"跨会话恢复原任务"

## /loop 自动模式特殊处理

/loop 自动模式下检测到用户插入新任务 → 立即触发熔断 escalate（与现有 stop-check 一致）→ 退出循环 → 走上述 4 步打断流程；/loop 半自动模式按常规流程处理。

## 边界 case 处理

- 多个新需求 → 按提出顺序排队，每个走完整 4 步
- 原任务已 paused → paused_reason 改为"叠加插入新任务 X（原 paused 原因：Y）"
- 嵌套打断 → **禁止嵌套**（最多一层），新任务执行中再插入 → 走"在范围内→追加子任务"或 escalate 用户

## 与现有规则关系

本流程是铁律7（逐项核对）的前置保障——保证插入新任务时不跳过原 task 项；与 /loop stop-check 互补（本流程覆盖普通 /do 模式，stop-check 覆盖 /loop 自动模式）；与对话恢复协议互补（本流程是同对话打断，对话恢复协议是跨对话恢复）；复用 compaction_recovery.md 的"关键清单外置"机制（写 memory + 更新 TASK_STATE + commit）。

**配套代码**：`scripts/handoff_tidy.py` 已支持 `paused` status 保留 + `paused_reason` 字段续传（`_read_existing_paused_reason` + `_write_task_state` frontmatter/body 双写）。

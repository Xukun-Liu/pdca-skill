# v103_t3 Apply Cross-Machine 5 Fix — SUMMARY

**任务**：跨机 5 修复落地 v1.0.3（from 他机 2026-08-21 memory_distill 在 v1.0.1 上的蒸馏）+ 对抗性审查 H1 缓解 + 总回归通过

**日期**：2026-08-23
**模式**：/plan → /do（5 fix + 1 chore + 总回归 8 AC）→ /act（本 SUMMARY + 记忆 + 验收）

---

## 1. 5 修复（diff 仍 valid → 一提交一修复）

| # | 脚本 | 修复点 | Commit | Refs |
|---|------|--------|--------|------|
| 1 | memory_shadow_write.py | CLI 强制 UTF-8 stdin 防 PS 中文损坏 | a654197 | v103_t3 |
| 2 | handoff_tidy.py | 禁 cwd 基名作 project_name 防污染 | 5bd0d09 | v103_t3 |
| 3 | memory_distill.py | 跳过 archived/demoted 条目 | 46181d1 | v103_t3 |
| 4 | validate_skill.py | 加 opencode skills 搜索根（兜底） | 6a3a37d | v103_t3 |
| 5 | learn_tidy.py | scan 改全段扫描修 global_total=0 误报 | 7d4a606 | v103_t3 |

外加 1 chore：`5610895 chore(v103t3): 同步 .primary_docs_rj 路径标签为当前开发机`

---

## 2. 对抗性审查（/plan 阶段 6 维 4 级）

| 等级 | 数量 | 状态 |
|------|------|------|
| HIGH | 1（H1：spec 描述 < 真实代码结构） | ✅ H1 缓解：spec/task 加占位说明 + 强制 Read 真实代码后再 patch |
| MEDIUM | 0 | — |
| LOW | 2 | 文档细节，T007 收口 |
| CRITICAL | 0 | — |

H1 是最危险项：spec 占位符（如"接 §X.Y"）vs 真实代码结构可能漂移，多版本叠加后极易误 patch。**缓解不可省**。

---

## 3. T006 总回归 — 8 AC 全部 PASS

| AC | 验证项 | 结果 |
|----|--------|------|
| AC-001 | 中文 stdin 写入 memory_main.md 完整保留 | PASS |
| AC-002 | handoff_tidy --task 正确生成 project_name（不取 cwd） | PASS |
| AC-003 | memory_distill 过滤 archived/demoted 条目 | PASS |
| AC-004 | validate_skill 32/32 PASS（brainstorming/writing-plans 临时 .bak） | PASS（opencode fallback 生效） |
| AC-005 | learn_tidy scan global_total=39 > 0（修复前为 0） | PASS |
| AC-006 | validate_skill 综合 32/32 PASS / FAIL=0 / MUST FIX=0 | PASS |
| AC-007 | git log -n 5 含 5 v103t3 fix commits | PASS |
| AC-008 | T000_backup.sha256 5/5 校验通过 | PASS |

---

## 4. 关键文件

- Spec: `docs_rj/spec_rj/v103_t3_apply_cross_machine_5fix_spec_20260823_2302.md`
- Task: `docs_rj/task_rj/v103_t3_apply_cross_machine_5fix_task_20260823_2302.md`
- Backup: `_sync_tmp/scripts/` + `T000_backup.sha256`（5/5）
- Scan report: `docs_rj/learn_rj/20260823-231938/scan_report.json`
- Memory: `docs_rj/memory_rj/v103_t3_apply_cross_machine_5fix_memory_*.md`（双写 project+global）

---

## 5. 经验沉淀

1. **跨机修复移植 ≠ 直接 apply**：版本差要先 diff 再 patch，他机 v1.0.1 vs 本机 v1.0.3 有结构性差异（如 memory_distill 已支持 archived/demoted 而 v1.0.1 还没有 → 移植前要 re-check 真实状态）。
2. **H1（spec 占位 vs 真实代码结构漂移）最危险**：补占位说明 + 强制 Read 真实代码后再 patch 是不可省的缓解。
3. **AC 验证必须反向**：造真实输入看输出，不能只看代码读懂就当 PASS。T005 AC-005 初次 global_total=0 是误报（primary_docs 路径传错缺 /docs_rj 后缀），get_docs_rj_path() 后正解为 39。
4. **PowerShell 习惯 ≠ bash**：`head` 不存在（用 `Select-String -Pattern`），`&&` 不存在（用 `;`），`<` 不支持重定向到外部命令 stdin（用 Python `subprocess` 或 `--content`）。
5. **一提交一修复**保持 git history 可读、可 cherry-pick、可独立 revert。

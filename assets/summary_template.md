---
title: 文档汇总视图
version: v1.1.0
skill_version: v1.1.0
last_updated: YYYY-MM-DD HH:MM
total_docs: 0
require-rule-mention: true
---

# 📚 文档汇总视图（SUMMARY）

本文件汇总项目全部文档（memory+spec+task+handoff+changelog），用 markdown 链接互连成知识图谱。纯 markdown 实现，零系统依赖。自动生成/更新：启动检查时 + 对话结束归档时 + 交接时（三触发硬性）。

## 🧠 Memory 文档

项目记忆体系——全局 `memory/memory_main.md`（skill 包内，按 `## {项目名}` 分段）+ 项目 `docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md`（写入即落盘 + 自动 upsert 全局），无独立归档步骤。

- [memory/memory_main.md](../memory/memory_main.md) — 全局聚合记忆主文件（按项目分段，启动必读）
- [docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md](memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md) — 项目级任务记忆（写入即落盘）

## 📋 Spec 文档

需求规格——每个任务一个 spec.md，看完能写代码不用猜，含 2-3 方案对比，通过 Self-Review。

- [{主docs}/spec_rj/{任务名}_spec_YYYYMMDD_HHMM.md]({主docs}/spec_rj/{任务名}_spec_YYYYMMDD_HHMM.md) — {任务名} 需求规格（一句话描述）

## ✅ Task 文档

任务清单——每个任务一个 task.md，每条含"怎么做+怎么验证"，Verification 通过才打勾。

- [{主docs}/task_rj/{任务名}_task_YYYYMMDD_HHMM.md]({主docs}/task_rj/{任务名}_task_YYYYMMDD_HHMM.md) — {任务名} 任务清单（一句话描述）

## 🤝 Handoff 文档

交接文档——当前状态、已完成、待办、阻塞项，30 秒接手。

- [{主docs}/handoff_rj/{任务名}_handoff_YYYYMMDD_HHMM.md]({主docs}/handoff_rj/{任务名}_handoff_YYYYMMDD_HHMM.md) — {任务名} 交接文档（一句话描述）

## 🔗 漂移检查清单

每次更新 SUMMARY 后必跑（三触发都跑）。用 grep + ls 做漂移检查。

```bash
# 1. 提取所有链接路径
grep -oP '\]\(\K[^)]+' {主docs}/SUMMARY_RJ.md

# 2. 逐个 ls 确认存在（示例）
ls ../memory/memory_main.md
ls {主docs}/memory_rj/{任务名}_memory_2026-07-09.md

# 3. 同步 total_docs
# 数 SUMMARY 中条目数，更新 frontmatter total_docs 字段
```

若 grep/ls 不可用（Windows PowerShell），用 Read 工具逐个确认文件存在。

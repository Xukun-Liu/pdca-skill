---
version: v1.0.0
skill_version: v1.0.2
---

# 归档任务袋 · {task}_{ts}

> 版本：v1.0.0 | 更新：{date}
> 结构：`archive_rj/{task}_{YYYYMMDD_HHMM}/`（任务启动时间戳从原文件名提取）

## 任务袋结构

```
archive_rj/{task}_{ts}/
├── spec.md       ← 归档规格（由 _build_archive_doc 生成，含元数据头部+原始内容）
├── task.md       ← 归档任务清单
├── handoff.md    ← 归档交接文档
└── memory.md     ← 归档记忆（可选，若有任务专属 memory）
```

## 背景
任务 `{task}` 已完成并通过验收（status=completed + Sign-off），归档至 archive_rj。
任务启动时间戳：{ts}（从原文件名提取，不依赖 mtime，避免 touch/checkout 漂移）

## 归档元数据
- 任务名：{task}
- 任务启动时间：{ts}
- 归档时间：{date}
- 归档原因：完成 / 过时 / 合并 / 暂停
- 来源路径：docs_rj/{type}_rj/{task}_{type}_{ts}.md

## 关键结论 / 可复用产出
（后续任务可直接复用的要点、决策、接口、坑）

## 关联
- 相关 spec：
- 相关 task：
- 相关 handoff：
- 相关 memory：

---
> 本任务袋由 pdca-skill archive_tidy.py 自动归档（D1 方案：按任务子文件夹聚合）。

---
title: YYYY-MM-DD - 归档日志
version: v1.1.0
skill_version: v1.1.0
date_created: YYYY-MM-DD HH:MM
last_updated: YYYY-MM-DD HH:MM
---

# YYYY-MM-DD（归档）

> 版本：v1.1.0 | 更新：YYYY-MM-DD HH:MM
> 本文件为历史命名的归档日志模板（保留历史命名）。新模型中项目记忆写入即落盘到 `{项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md` 并经 `write_project` 自动 upsert 全局 `memory/memory_main.md`，无独立归档步骤、无 SESSION_END 收尾标记。

## 工作记录

- [YYYY-MM-DD HH:MM] 做了什么
- [YYYY-MM-DD HH:MM] 做了什么

---

## 格式说明

- 文件名即日期，一天一个文件
- 归档时创建，如已存在则 append
- 每条记录格式：`- [YYYY-MM-DD HH:MM] {做了什么}`（完整时间戳，因归档可能跨天）
- 以对话为一组，组间空行分隔

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | YYYY-MM-DD HH:MM | 初版（改为归档模板） |

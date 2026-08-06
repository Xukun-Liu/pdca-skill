---
title: 项目级长期记忆
version: v1.0.0
skill_version: v1.0.1
date_created: YYYY-MM-DD HH:MM
last_updated: YYYY-MM-DD HH:MM
---

# memory/memory_main.md（全局聚合记忆 · skill 包内）

> 按 `## {项目名}` 分段聚合各项目记忆（主次跟进）。项目级记忆在 `{项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md`，写入即落盘并经 `write_project` 自动 upsert 本文件。
> ⚠️ 仅供参考，以你当前指令为准

## {项目名}

### 关键决策

- [YYYY-MM-DD][任务名] 决策内容

### 约定

- 版本号升级规则：主版本号（破坏性变更）、次版本号（向后兼容的新增/重构）
- 主 docs 路径：./docs_rj/（默认；全局记忆路径固定在 skill 包 memory/，无需在此记录主 docs 路径）

### 对抗性审查记录（长期保留）

- [YYYY-MM-DD HH:MM] [{任务名}] 对抗性审查 LOW：[LOW 问题描述]
- [YYYY-MM-DD HH:MM] [{任务名}] 对抗性审查状态：已用正常轮次=X，安全轮次数=Y

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | YYYY-MM-DD HH:MM | 初版（Bootstrap 创建） |

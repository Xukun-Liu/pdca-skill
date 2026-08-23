---
title: pdca-skill global memory
version: v1.0.0
skill_version: v1.0.3
date_created: 2026-08-23
last_updated: 2026-08-23
owner: 86029
tags: [pdca-skill, memory, skeleton]
---

# memory_main（空骨架）

> 此文件为 `scripts/package_skill.py` 白名单要求的最小骨架（`_SKELETON_WHITELIST = {"memory/memory_main.md", "docs_rj/SUMMARY_RJ.md", "docs_rj/spec_rj/spec_main_rj.md"}`），避免发布包被打包排除。
>
> 实际全局记忆由使用者首次启动后由 Bootstrap 自动填充：
> - Bootstrap 阶段读取项目 + 跨项目知识
> - 写入路径：本机 `~/.pdca-skill/data/memory/memory_main.md`（用户数据外置，不进 git）
> - 写入时机：每次 /act 阶段 learn_tidy + handoff_tidy
>
> 本骨架仅作为发布包占位，仓库内保持空内容。

<!-- PDCA标签：P.bootstrap -->
<!-- 子标签场景：多项目切换 -->
<!-- 关键词清单：多项目/切换项目/多个项目/项目切换/换项目/同时搞几个 -->
<!-- 引用范围：main + bootstrap_agent -->

# 多项目管理（Multi-Project）
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 最近更新：2026-07-21（首次登记版本号引用块，SCR-10 修复） | PDCA 标签：P.bootstrap
> 对应 SKILL.md 章节：§3.5 多项目管理

> 本文件从 SKILL.md §3.5 下沉而来，作为按需加载的详细规范。
> 你同时推进多个项目，需明确记忆文件归属与切换规则。

## 记忆文件层级

| 文件 | 路径 | 用途 |
|------|------|------|
| 全局记忆 | `memory/memory_main.md`（skill 包内） | 跨项目经验、个人偏好、项目清单 |
| 项目记忆 | `{项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md` | 本项目专用记录（写入即落盘 + 自动 upsert 全局 memory_main） |
| 任务记忆 | `{项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md` | 本任务状态 |

## 切换项目规则【硬性】

1. **切换项目 = 新对话**：必须重新读全局 memory + 新项目的 memory
2. **跨项目引用**：需明确说明"这个经验来自 XX 项目"，避免混淆
3. **全局 vs 项目**：全局 memory 记"所有项目通用"的规则，项目 memory 记"只适合本项目"的经验

## 目录结构规范

每个项目保持一致结构：

```
{workspace}/
├── .agent/
│   ├── skills/           # 项目级 skills（可选）
│   └── SOUL.md          # 项目专用 AI 性格（可选）
├── docs_rj/
│   ├── memory_rj/         # 项目记忆（{任务名}_memory_YYYYMMDD_HHMM.md，建在主 docs 内）
│   └── ...                # 任务文档（扁平5类：spec_rj/task_rj/handoff_rj/archive_rj）
├── src/                 # 源代码
└── outputs_rj/             # 输出文件
```

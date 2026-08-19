---
version: v1.0.0
skill_version: v1.0.2
---

# skill_graph.md 输出模板

> ⚠️ 本文件是渲染模板的骨架参考，实际渲染由 `scripts/skill_graph_render.py` 的 `render_markdown()` 函数完成。
> 此文件用于文档化输出结构，不直接被脚本读取。

---

## 模板结构

```
# {{user_name}}的技能图谱

> ⚠️ 自动生成于 {{generated_at}}，请勿手动修改。重新生成请运行 `python scripts/skill_graph_build.py`

## 概览
- 全集技能数：{{total_skills}}
- 已掌握：{{mastered_count}} ({{mastered_percent}})
- 未掌握：{{not_mastered_count}} ({{not_mastered_percent}})
- 额外掌握：{{extra_mastered_count}}
- 掌握率：{{mastery_rate}}
- 数据源：{{sources_scanned}}
- 全集源：{{taxonomy_sources}}

## 技能图谱（SVG 交互图）
**颜色说明**：绿色=已掌握，灰色=未掌握，橙色=额外掌握，橙边=推荐补的高优先级。
```svg
{{svg_content}}
```

<details>
<summary>ASCII 树状图（降级视图）</summary>
```
{{ascii_tree}}
```
</details>

## 已掌握技能（{{mastered_count}} 个）
| 技能 | 分类 | 置信度 | 证据数 | 来源工具 | 首次出现 | 最近出现 |
|------|------|--------|--------|----------|----------|----------|
| {{name}} | {{category}} | {{confidence}} | {{evidence_count}} | {{source_tools}} | {{first_seen}} | {{last_seen}} |

## 额外掌握技能（{{extra_mastered_count}} 个，不在全集内）
| 技能 | 分类 | 置信度 | 证据数 | 来源工具 |
|------|------|--------|--------|----------|

## 未掌握技能（{{not_mastered_count}} 个）
### 高优先级（{{high_count}} 个）
| 技能 | 分类 | 全集来源 | 学习链接 |
|------|------|----------|----------|

### 中优先级（{{medium_count}} 个）
### 低优先级（{{low_count}} 个）

## 分类汇总
| 分类 | 技能数 | 平均置信度 |
|------|--------|------------|

## 生成元数据
- 生成时间：{{generated_at}}
- 左轨已掌握技能：{{raw_skills_count}}
- 右轨全集技能：{{taxonomy_skills_count}}
- 记忆数据源：{{sources_scanned}}
- 全集数据源：{{taxonomy_sources}}
- 同步校验：见 `docs_master_graph/manifest.json`
```

---

## CSV 模板（13 列）

```
skill_name,category,status,confidence,evidence_count,source_tools,evidence_files,first_seen,last_seen,reason,roadmap_ref,priority,learning_link
{{name}},{{category}},{{status}},{{confidence}},{{evidence_count}},{{source_tools}};,{{evidence_refs}};,{{first_seen}},{{last_seen}},{{reason}},{{roadmap_ref}},{{priority}},{{learning_link}}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| skill_name | string | 技能名 |
| category | string | 分类 |
| status | enum | mastered / not_mastered / extra_mastered |
| confidence | float | 置信度 0-1 |
| evidence_count | int | 证据数 |
| source_tools | string | 来源工具（分号分隔） |
| evidence_files | string | 证据文件引用（分号分隔） |
| first_seen | string | 首次出现时间 |
| last_seen | string | 最近出现时间 |
| reason | string | 未掌握原因（仅 not_mastered） |
| roadmap_ref | string | 全集来源（仅 not_mastered） |
| priority | enum | high / medium / low（仅 not_mastered） |
| learning_link | string | 学习链接（仅 not_mastered） |

---

## SVG 模板（径向树布局）

```
1200×800 画布
中心：用户节点（深蓝 r=30）
中圈：分类节点（黄色 r=22，环绕中心）
外圈：技能节点（已掌握 r=8 绿 / 未掌握 r=5 灰 / 额外 r=7 橙）
连线：已掌握实线 / 未掌握虚线
右下：图例
右上：生成时间戳
```

---

## Manifest 模板

```json
{
  "generated_at": "{{ISO timestamp}}",
  "files": {
    "markdown": {"path": "...", "sha256": "..."},
    "csv": {"path": "...", "sha256": "..."},
    "svg": {"path": "...", "sha256": "..."}
  },
  "summary": {...},
  "sync_check": "all three files generated from same skills_clustered.json"
}
```

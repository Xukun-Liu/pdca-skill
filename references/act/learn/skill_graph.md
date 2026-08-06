<!-- PDCA标签：A.learn -->
<!-- 子标签场景：技能图谱、能力画像、掌握度分析、差距分析、未掌握推荐 -->
<!-- 关键词清单：技能图谱/能力画像/skill graph/我看我有什么技能/掌握什么/未掌握什么/差距分析/技能雷达/skill_graph -->
<!-- 引用范围：main + learn_opt_agent -->

# skill_graph 子流程：用户技能图谱生成

> 阶段标签：A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 新增：2026-07-17 | PDCA 标签：A.learn
> 对应脚本：[scripts/skill_graph_build.py](../scripts/skill_graph_build.py)
> 参考来源：GitHub 调研（19 次查询 0 完全匹配，填补赛道空白）

---

## §1 核心定位

**做什么**：从用户的多源记忆中自动提取已掌握技能，对比多源技能全集，生成"已掌握/未掌握/额外掌握"三段式技能图谱。

**不做什么**：
- ❌ 不做 AI agent 自身的技能画像（仅做用户画像）
- ❌ 不做已加载 skill 清单的依赖图谱（仅从记忆挖掘）
- ❌ 不做实时更新（手动触发刷新）

**核心价值**：
- 用户和 AI 都能一眼看到能力地图
- 明确"应该掌握但还没掌握"的技能（学习方向）
- 识别用户独有技能（不在标准全集内的特长）

---

## §2 三阶段流水线

| 阶段 | 脚本 | 输入 | 输出 | LLM |
|------|------|------|------|-----|
| 1 提取 | skill_graph_extract.py | 多源记忆 + 4源全集 | skills_raw.json + master_taxonomy.json | 否（规则） |
| 2 归纳 | skill_graph_cluster.py | 阶段1输出 | skills_clustered.json | 可选（当前规则降级） |
| 3 渲染 | skill_graph_render.py | 阶段2输出 | skill_graph.md + .csv + .svg + manifest.json | 否（模板） |

**总入口**：`python scripts/skill_graph_build.py`（自动串联三阶段 + 缓存）

---

## §3 触发时机

### 自动触发关键词

用户说以下话时触发：
- "技能图谱" / "能力画像" / "skill graph"
- "我看我有什么技能" / "我掌握什么"
- "我未掌握什么" / "差距分析" / "技能雷达"
- "我还有什么没学" / "推荐我学什么"

### 手动触发

```
python scripts/skill_graph_build.py
python scripts/skill_graph_build.py --source all --user-name "你的名字"
python scripts/skill_graph_build.py --no-cache  # 强制重算
python scripts/skill_graph_build.py --skip-taxonomy  # 仅左轨（调试）
```

---

## §4 双轨数据源

> 🔴 **触发前确认【硬性·v1.0.1】**：本功能扫描 `~`/`%APPDATA%`/`%LOCALAPPDATA%`/Library Application Support 等**任务外目录**（属 security.md「文件扫描确认门控」L2 级）。触发前必须先向用户确认范围+目的，确认后才运行。非交互模式（无 TTY）下不读取新发现工具的记忆文件（只记录路径，见 skill_graph_extract.py）。

### 左轨（记忆挖掘 · 已掌握）

**白名单 8 AI 工具**（固定路径扫描）：
- Trae: `~/.trae-cn/memory/`
- Claude Code: `~/.claude/`
- Cursor: `~/.cursor/`
- OpenClaw: `~/.openclaw/`
- Windsurf: `~/.codeium/` 或 `~/.windsurf/`
- Cline: `~/.cline/`
- Continue: `~/.continue/`
- GitHub Copilot: `~/.github-copilot/`

**关键词发现**（6 扫描根 + 8 关键词）：
- 扫描根：`~` `~/.config/` `~/.local/share/` `~/.appdata/` 或 `~/Library/Application Support/` `%APPDATA%`/`%LOCALAPPDATA%` 项目目录链
- 关键词：`memory` `agent` `skill` `remember` `assistant` `ai` `conversation` `session`
- 新工具发现后交互式询问用户是否纳入

### 右轨（多源全集 · 应掌握）

| 源 | 类型 | 覆盖内容 |
|----|------|----------|
| roadmap.sh | git clone | 开发者角色技能树（237k★） |
| engineer_competency | git clone | 工程能力矩阵 + 软技能 |
| GitHub Topics | API | 实际工具框架排名 |
| SO Survey | 硬编码 | 年度热门技能（无公开 API） |

**降级策略**：任一源拉取失败自动降级到硬编码列表，不阻断流程。

---

## §5 三格式输出

| 格式 | 路径 | 受众 | 说明 |
|------|------|------|------|
| Markdown + SVG | `memory/skill_graph.md` | 人看（Trae 预览器） | 单文件自包含，零依赖 |
| CSV | `docs_master_graph/skill_graph.csv` | Excel/程序 | UTF-8 BOM，13 列 |
| SVG | `docs_master_graph/skill_graph.svg` | 浏览器/分享 | 1200×800，支持缩放 |
| Manifest | `docs_master_graph/manifest.json` | 同步校验 | 三文件 SHA256 |

### SVG 颜色方案（色盲友好）

| 颜色 | 含义 | 节点大小 |
|------|------|----------|
| 深绿 `#16a34a` | 已掌握 | 大圆 r=8 |
| 灰色 `#9ca3af` | 未掌握 | 小圆 r=5 |
| 橙色 `#ea580c` | 额外掌握（不在全集） | 中圆 r=7 |
| 灰+橙边 `#f59e0b` | 推荐补的高优先级未掌握 | r=6 |

### CSV 字段（13 列）

`skill_name, category, status, confidence, evidence_count, source_tools, evidence_files, first_seen, last_seen, reason, roadmap_ref, priority, learning_link`

> **evidence_files 豁免声明【v1.0.1】**：`evidence_files` 字段含具体文件路径（file/line/timestamp），是本功能「证据可追溯」验收标准（AC8）的核心，属功能设计豁免——不受 security.md 门控「不记录路径」约束。用户已确认豁免（2026-08-06）。

---

## §6 缓存机制

- 对每个输入记忆文件算 SHA256
- 文件未变 → 跳过全部阶段
- `--no-cache` 强制重算
- 缓存 manifest：`docs_rj/memory_rj/.skill_graph_cache/cache_manifest.json`

---

## §7 降级模式

| 场景 | 降级方案 |
|------|----------|
| LLM 服务不可用 | 阶段2 降级到规则分类（按 category_hint 聚合） |
| git clone 超时 | 右轨降级到硬编码技能列表 |
| GitHub API 限流 | 降级到硬编码列表 |
| SVG 渲染失败 | 降级到 ASCII 树状图 |
| 某扫描根不存在 | 跳过 + 告警，不阻断 |

---

## §8 验收标准（14 条）

| AC | 标准 | 验证方式 |
|----|------|----------|
| AC1 | 输出稳定性 | 同输入跑2次 diff < 5% |
| AC2 | SVG 可读性 | Trae 预览器正常显示 |
| AC3 | 无占位符 | grep TBD/TODO = 0 |
| AC4 | 多源覆盖 | sources_scanned ≥ riji + 1 AI 工具 |
| AC5 | 缓存生效 | 第二次跑跳过全部阶段 |
| AC6 | 分类数量 | 3 ≤ N ≤ 7 |
| AC7 | 零外部依赖 | 仅 Python 标准库 |
| AC8 | 证据可追溯 | 每条技能含 file/line/timestamp |
| AC9 | 新工具可扩展 | discovered_tools 字段存在 |
| AC10 | 扫描覆盖面 | 至少命中 1 个工具 |
| AC11 | CSV 格式有效 | UTF-8 BOM + Excel 无乱码 |
| AC12 | 独立 SVG 可打开 | 浏览器无 XML 错误 |
| AC13 | 三格式同步 | manifest.json hash 校验 |
| AC14 | 差距分析完整 | mastered + not_mastered + extra_mastered |

---

## §9 常见问题

**Q: roadmap.sh git clone 超时怎么办？**
A: 自动降级到硬编码列表，不阻断。网络好时重跑 `--no-cache` 补全。

**Q: 发现新 AI 工具怎么纳入？**
A: 关键词发现机制会自动扫到，交互模式停下问用户。非交互模式记录到 `discovered_tools` 字段。

**Q: LLM 调用怎么接入？**
A: 阶段2 的 `cluster_with_llm()` 函数签名已留，填入 LLM 服务调用即可。当前用规则降级。

**Q: 技能图谱多久刷新一次？**
A: 手动触发，无自动刷新。建议学习新技能后跑一次。

---

## §10 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-17 | 初版：三阶段流水线 + 双轨提取 + 三格式渲染 |

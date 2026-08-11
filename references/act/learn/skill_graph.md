<!-- PDCA标签：A.learn -->
<!-- 子标签场景：技能图谱、能力画像、掌握度分析、差距分析、未掌握推荐 -->
<!-- 关键词清单：技能图谱/能力画像/skill graph/我看我有什么技能/掌握什么/未掌握什么/差距分析/技能雷达/skill_graph -->
<!-- 引用范围：main + learn_opt_agent -->

# skill_graph 子流程：用户技能图谱生成

> 阶段标签：A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.1 | 新增：2026-07-17 | PDCA 标签：A.learn
> 对应脚本：[scripts/skill_graph_build.py](../scripts/skill_graph_build.py)
> 参考来源：GitHub 调研（19 次查询 0 完全匹配，填补赛道空白）

---

## §1 核心定位

**做什么**：从用户的多源记忆中自动提取已掌握技能，对比多源技能全集，生成"已掌握/未掌握/额外掌握"三段式技能图谱。

**不做什么**：
- ❌ 不做 AI agent 自身的技能画像（仅做用户画像）
- ❌ 不做已加载 skill 清单的依赖图谱（仅从记忆挖掘）
- ❌ 不做实时更新（/act 每轮自动刷新 + 手动触发；非实时 watch）

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

### 自动触发（每轮 /act · v1.0.1）

- 每轮 /act 步骤 3.6a 自动跑 `python scripts/skill_graph_build.py --auto`（无需用户点名）
- `--auto` 语义：仅左轨 pdca（记忆已积累，安全 L0 级，不触发 L2 扫描确认）；记忆哈希未变 → 缓存命中直接跳过（零成本）；哈希变化 → 自动重算三阶段并更新 `~/.pdca-skill/data/docs_rj/skill_graph/` 四件套（实际路径由 `user_data_path.get_docs_rj_path()` 动态解析：PDCA_DATA_DIR > config.json > 默认）
- taxonomy 缓存缺失时 `[SKIP]` 提示 + exit 0，记录 memory"skill_graph SKIP（taxonomy 缺失）"，由手动全量补
- 退出码：0=成功/跳过；2=阶段失败（auto 模式下告警并记录 memory"skill_graph 自动刷新失败"，**不阻断** /act，继续后续步骤）
- 失败语义：手动全量 exit 1 阻断；auto 失败降级不阻断（详见 act_procedure.md 步骤 3.6a）

### 用户点名触发

用户说以下话时触发：
- "技能图谱" / "能力画像" / "skill graph"
- "我看我有什么技能" / "我掌握什么"
- "我未掌握什么" / "差距分析" / "技能雷达"
- "我还有什么没学" / "推荐我学什么"

用户点名 = 全量双轨（含右轨），触发前仍须 L2 确认范围+目的（见 §4）。

### 手动触发

```
python scripts/skill_graph_build.py  # 全量（双轨）
python scripts/skill_graph_build.py --source all --user-name "你的名字"
python scripts/skill_graph_build.py --auto   # 仅左轨自动刷新（/act 3.6a 用）
python scripts/skill_graph_build.py --no-cache  # 强制重算
python scripts/skill_graph_build.py --skip-taxonomy  # 跳过右轨全集拉取（调试用；注意：默认 source=all 仍会扫描 AI 工具记忆，仅 --auto 是真正仅左轨）
```

---

## §4 双轨数据源

> 🔴 **触发前确认【硬性·v1.0.1】**：本功能扫描 `~`/`%APPDATA%`/`%LOCALAPPDATA%`/Library Application Support 等**任务外目录**（属 security.md「文件扫描确认门控」L2 级）。触发前必须先向用户确认范围+目的，确认后才运行。非交互模式（无 TTY）下不读取新发现工具的记忆文件（只记录路径，见 skill_graph_extract.py）。
>
> **白名单目录豁免声明【v1.0.1·用户确认】**：下方「白名单 8 AI 工具」固定目录是本功能「读 AI 工具记忆生成技能图谱」的核心功能路径——用户**启用技能图谱功能即视为授权**读取这些目录（与 evidence_files 豁免同思路），不重复走 L2 确认。豁免范围仅限这 8 个固定目录；其余任务外扫描仍须确认。配套约束（v1.0.1 落地）：①敏感行摘录不入库——excerpt 命中密码/token/密钥等敏感模式时替换为 `[sensitive line omitted]`；②读取范围为工具目录内记忆类文件（`.md/.json/.jsonl/.txt`，深 3 层，黑名单目录剪枝）——不主动越界读取用户其他目录。

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

**关键词发现**（扫描根 + 8 关键词）：
- 扫描根（最多 7 个，按代码 `_get_scan_roots()` 实测）：`~` `~/.config/` `~/.local/share/` `%APPDATA%` `%LOCALAPPDATA%`（Windows）`~/Library/Application Support`（macOS 存在时）`cwd`（当前工作目录；v1.0.1 起**不含**父目录链，与 L0「父目录链不算任务范围」对齐）
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

| 格式 | 路径（v1.0.1 起外置用户数据目录） | 受众 | 说明 |
|------|------|------|------|
| Markdown + SVG | `~/.pdca-skill/data/docs_rj/skill_graph/skill_graph.md` | 人看（Trae 预览器） | 单文件自包含，零依赖 |
| CSV | `~/.pdca-skill/data/docs_rj/skill_graph/skill_graph.csv` | Excel/程序 | UTF-8 BOM，13 列 |
| SVG | `~/.pdca-skill/data/docs_rj/skill_graph/skill_graph.svg` | 浏览器/分享 | 1200×800，支持缩放 |
| Manifest | `~/.pdca-skill/data/docs_rj/skill_graph/manifest.json` | 同步校验 | 三文件 SHA256 |

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
>
> **discovered_tools 路径声明【v1.0.1】**：关键词发现的工具路径会进入缓存 JSON（skills_raw.json）并在 `--discover-only` 时输出到 stdout，同样属功能设计（AC9 要求 discovered_tools 字段存在）。此声明针对**脚本文件输出**；AI 对话中向用户汇报时仍遵守 security.md「汇报不报具体文件名」规则。

---

## §6 缓存机制

- 对每个输入记忆文件算 SHA256
- **缓存仅对自动模式（--auto）生效**：输入未变 → 缓存命中跳过全部阶段（零成本）；变化 → 重算
- **全量模式（用户点名/手动）不用缓存**：始终完整重算三阶段（要最新数据），跑完更新缓存供后续 --auto 用
- `--no-cache` 强制重算（auto 模式用）
- 仅完整三阶段跑完才更新缓存；`--force-stage` 部分跑不写缓存（防误命中）
- 缓存 manifest：`~/.pdca-skill/data/docs_rj/memory_rj/.skill_graph_cache/cache_manifest.json`

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
| AC4 | 多源覆盖 | sources_scanned ≥ pdca + 1 AI 工具 |
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
A: 关键词发现机制会自动扫到，交互模式停下问用户，确认纳入后才读取其记忆内容。**非交互模式（无 TTY）降级语义【v1.0.1】：只把路径记录到 `discovered_tools` 字段，不读取内容、不纳入本次提取**（防止未确认读取任务外敏感文件）；如需纳入，重跑时在交互终端确认。

**Q: LLM 调用怎么接入？**
A: 阶段2 的 `cluster_with_llm()` 函数签名已留，填入 LLM 服务调用即可。当前用规则降级。

**Q: 技能图谱多久刷新一次？**
A: 每轮 /act 自动刷新一次（--auto：记忆没变则秒过，变了才重算）+ 用户点名/手动随时全量刷新（--source all）。不需要手工记着跑。

---

## §10 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.1 | 2026-08-06 | 自动化改造：/act 每轮 3.6a 自动刷新（--auto 仅左轨 L0 安全级，哈希未变缓存命中零成本）；缓存/输出外置 `~/.pdca-skill/data/`；断链修复（read_pdca_memory 单入口）；结构化经验字段置信度加权；CSV 公式注入防护；右轨补真 URL + 适配 roadmap 新仓库结构；扫描确认门控配套（触发前确认、白名单豁免声明、非交互不读未确认目录、敏感行摘录过滤、扫描根去父链） |
| v1.0 | 2026-07-17 | 初版：三阶段流水线 + 双轨提取 + 三格式渲染 |

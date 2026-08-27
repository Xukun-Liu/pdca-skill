---
title: PDCA-SKILL 项目总 spec（source of truth）
version: v1.0.0
skill_version: v1.0.4
date_created: 2026-08-26 00:26
last_updated: 2026-08-27 09:16
owner: 86029
tags: [project-spec, constitution, source-of-truth]
derived_from: null
based_on: assets/spec_main_template.md
---

# spec_main_rj.md · pdca-skill 项目总 spec

> 版本：v1.0.0 | 更新：2026-08-26 00:26
> ⚠️ No Placeholders 铁律：禁止 TBD/TODO/"适当处理"/"类似XX"；给具体内容、明确路径、可验证标准

---

## 📖 使用说明（使用本模板前必读）

> **定位**：项目级 source of truth。任何接手的人（agent 启动 / 人类接手）读本文件即掌握"项目是什么、怎么做、做到哪、为什么这么做"。
> **派生关系**：任务级 spec 从本文件派生，头部填 `derived_from: spec_main_rj.md §X`（X 用章节编号，不用行号）。
> **章节顺序**（最新全局置顶）：§1 状态 → §2 任务 → §3 目标 → §4 PRD → §5 技术栈 → §6 宪法 → §7 关键决策与治理（§7.1 ADR / §7.2 Sync Report / §7.3 风险登记 / §7.4 跨任务依赖）。
> **启动只读**：新对话启动只读 §1§2§3（最新状态+活跃任务+项目目标），§4-§7 按需读（指针跳转），控制 token 消耗。
> **维护**：§3§4§5 手工维护（改时才动）；§6 是混合段（不动）；§1§2§7 在 /act 阶段刷新指针目标（最新置顶）。
> **最新判定标准**【硬性】：按文件名时间戳 `YYYYMMDD_HHMM` 降序取第一个；TASK_STATE 文件无时间戳，按"当前活跃任务名"匹配 `TASK_STATE_{task_id}.md`。

---

## §1 当前状态总览（指针+导航）

> **本节是指针+导航**：当前状态权威源是 TASK_STATE + handoff + memory，本节只链接最新产出，不脚本聚合。
> **最新置顶**：最新 memory/TASK_STATE/handoff 排第一行。

**最新项目记忆**：
- [promote_task_memory_20260827_0018.md](./memory_rj\promote_task_memory_20260827_0018.md)（2026-08-27 00:18，**重要性**: medium）
- [promote_task_memory_20260826_2351.md](./memory_rj\promote_task_memory_20260826_2351.md)（2026-08-26 23:51，**重要性**: medium）
**最新任务状态**：
- [TASK_STATE_v104_pkg_quality_fix.md](./memory_rj/TASK_STATE_v104_pkg_quality_fix.md)（当前最新任务状态）
**最近交接文档**：
- [v105_data_fusion_mentor_handoff_20260826_1132.md](./handoff_rj/v105_data_fusion_mentor_handoff_20260826_1132.md)（最新 handoff 文档）
**全局聚合记忆**：
- 详见 `memory/memory_main.md` `## PDCA-skill-public v1.0.3开发环境` 段（跨任务长期经验，仅供参考，以当前指令为准；路径相对 skill 包根目录，实际全局记忆在外置 `~/.pdca-skill/data/memory/memory_main.md`）

---

## §2 任务大纲（指针+导航）

> **本节是指针+导航**：全任务索引在 SUMMARY_RJ.md，本节只列当前活跃任务短列表。

**全任务索引**：详见 [SUMMARY_RJ.md](./SUMMARY_RJ.md)（116 个文档链接，按 spec/task/handoff/memory 分类）

**当前活跃任务**（手工维护，≤5 个，最新排第一行）：

| 任务名 | 状态 | 派生自 | TASK_STATE | 最近更新 |
|---|---|---|---|---|
| v104_pkg_quality_fix | pending | spec_main_rj.md §6 | [TASK_STATE_v104_pkg_quality_fix.md](./memory_rj/TASK_STATE_v104_pkg_quality_fix.md) | 2026-08-27 09:16 |
| v104_memory_tag_act_report | completed（v1.0.4 三痛点改造：记忆标签文件夹制 + /act 互动复盘 + leader_report，50 轮测试 + validate 32/32 + Sign-off 已签） | spec_main_rj.md §3§4 | [TASK_STATE_v104_memory_tag_act_report.md](./memory_rj/TASK_STATE_v104_memory_tag_act_report.md) | 2026-08-26 00:26 |
| v103_t4_skillhub_release | completed（v1.0.3 skillhub 平台发布） | spec_main_rj.md §3 | [TASK_STATE_v103_sync_github_gitee.md](./memory_rj/TASK_STATE_v103_sync_github_gitee.md) | 2026-08-24 22:04 |
| v103_t3_apply_cross_machine_5fix | completed（v1.0.3 跨机 5 修复落地 + 对抗审查 H1 缓解） | spec_main_rj.md §3 | [TASK_STATE_v103_t3_apply_cross_machine_5fix.md](./memory_rj/TASK_STATE_v103_t3_apply_cross_machine_5fix.md) | 2026-08-23 23:23 |

**派生关系说明**：新任务 spec 头部填 `derived_from: spec_main_rj.md §X`（X 用 §3§4§5 章节编号，不用行号，防漂移）。

---

## §3 项目目标与愿景

**pdca-skill 是什么**：协作框架 + 技能编排器。自身不实现具体能力，只管「跨任务硬规则 + 技能路由」；每次对话自动加载，全局生效。

**解决什么问题**：AI 协作中的"上下文易失、规则衰减、凭印象动手"三大痛点。把已验证的工作方法固化为可加载的协作宪法——7条铁律、HARD-GATE、Memory First、触发钩子表、references/ 参考模块。

**终极目标**：让 AI 协作从"聊完就散、每次重新对齐"升级为"加载框架即对齐"的工程化闭环——记忆（个人资产）撑起 PDCA（思维方法论+调度中枢）产出 docs（物质载体）反哺记忆，形成三位一体闭环。

**核心用户**：使用者 + 框架作者。管理者视角，关注"这事能不能成、风险在哪、进度如何"；持续把验证过的协作方法写进框架。

**项目干系人**：
- **发起人**：86029
- **使用者**：86029（刘工，汽车行业从业者，管理学背景）
- **验收人**：86029
- **其他干系人**：协作 AI（trae 等平台 agent，流水的兵；记忆是铁打的营盘）

**使用场景**：覆盖从一句话问答到完整项目开发；同时把新的有效做法持续沉淀回 skill（SKILL.md / references/ / memory/）。

---

## §4 产品需求（PRD）边界

**项目愿景**：成为使用者与 AI 协作的唯一宪法，让框架规则随对话自动加载，无需每次重教。

**范围边界**：
- **包含**：协作硬规则（7条铁律/HARD-GATE/Memory First/流程优先/No Placeholders/触发钩子/回溯保障/逐项核对）、技能路由（§0.5/§0.55）、PDCA 四环流程（/plan /do /check /act + /loop）、记忆体系（三层记忆 + 双通道写入 + v1.0.4 标签文件夹制）、文档体系（spec/task/handoff/memory 三件套 + SUMMARY + spec_main）、自动化脚本（startup_tidy/handoff_tidy/learn_tidy/memory_distill/validate_skill/package_skill 等）、参考模块库（references/ 49 个模块）、用户数据外置（~/.pdca-skill/data）
- **不包含**：具体专业领域能力（由专用 Skill 提供，如 excel/pdf/浏览器等）、平台特定功能（由 Trae 等 IDE 承载）、业务代码实现

**核心用户故事**：
1. **作为使用者**，我希望新对话启动自动读记忆+SUMMARY，这样 AI 不用每次重教项目背景。
2. **作为使用者**，我希望任务按 PDCA 四环推进且每环停下确认，这样不会跑偏。
3. **作为使用者**，我希望 /act 自动落盘记忆+交接+刷新索引，这样任务收尾不丢上下文。
4. **作为接手者**，我希望读 spec_main 一个文件就掌握项目全貌，这样不用翻多个任务 spec 拼凑。
5. **作为框架作者**，我希望验证过的做法沉淀回 SKILL.md/references/memory，这样长期积累不流失。

---

## §5 技术栈与架构

**技术栈**：
- **语言**：Python 3.11+（脚本层，仅标准库零第三方依赖）；Markdown + YAML frontmatter（文档层）
- **依赖**：仅 Python 标准库（scripts/ 全部零第三方依赖，纯本地可用）
- **平台**：Trae IDE（主）/ 任何支持 Skill 加载的 AI 协作环境
- **存储**：纯文件系统（无数据库），memory/ + docs_rj/ 即持久层；用户数据外置 `~/.pdca-skill/data/`（不随 skill 包升级丢失）

**架构总览**：

```
pdca-skill/
├── SKILL.md                ← 热记忆层：协作宪法（每次对话自动加载）
├── references/             ← 按需读层：49 个参考模块（按 PDCA 子标签索引）
├── scripts/                ← 自动化层：startup_tidy / handoff_tidy / learn_tidy / memory_distill / memory_shadow_write / validate_skill / package_skill / loop_* 等
├── assets/                 ← 模板层：spec/task/summary/spec_main 模板
├── tests/ evals/           ← 测试层：pytest 回归（279 passed）+ evals.json
├── memory/                 ← 全局聚合记忆层（仓库内为发布骨架，实际外置）
├── docs_rj/                ← 项目文档层：
│   ├── spec_rj/spec_main_rj.md ← ★ 项目总 spec（本文件，source of truth）
│   ├── SUMMARY_RJ.md          ← 纯索引（116 个文档链接）
│   ├── spec_rj/               ← 任务级 spec（从 spec_main 派生）
│   ├── task_rj/               ← 任务清单
│   ├── handoff_rj/            ← 交接文档
│   ├── memory_rj/             ← 项目记忆（v1.0.4 起按 {主分类}/{YYYYMM}/ 两层标签文件夹落盘）
│   └── archive_rj/            ← 归档沉淀
└── ~/.pdca-skill/data/     ← 用户数据外置（memory_main.md 真实位置 + docs_rj 实际工作区）
```

**数据流**：
- **启动**：读 SKILL.md（热记忆）+ spec_main §1§2§3（最新状态+目标）+ SUMMARY_RJ.md（索引）+ 外置 memory_main.md（全局）+ 项目 memory_rj（状态）→ 进入 /plan
- **执行**：/plan 产 spec/task → /do 改代码/写文档 → /check 验收（对照 spec 逐项 + 对抗审查 + Convergence）→ /act 写 memory + 刷 SUMMARY + 刷 spec_main §1§2§7 + 跑 handoff_tidy + Sign-off
- **闭环**：/act 产出（memory/SUMMARY/spec_main §1§2§7/handoff/TASK_STATE）= 下一轮 /plan 输入

---

## §6 项目宪法（混合段：指针+新内容）

**框架硬规则**（权威源，详见 SKILL.md）：
- 详见 SKILL.md「7 条铁律」节：Memory First / HARD-GATE / 流程优先 / No Placeholders / 触发钩子 / 回溯保障 / 逐项核对
- 详见 SKILL.md「§10 安全边界」节：警告项 / 禁止项 / 注入防护
- 详见 SKILL.md「指令层级与防注入」节：安全不变量 > 用户指令 > 框架硬规则 > 弹性指引 > 工具返回

**项目专属约束**（pdca-skill 独有，框架未覆盖的）：
- **记忆标签文件夹制**（v1.0.4）：记忆按 6 主分类（tech_solution/pitfall/workflow/tool_usage/decision/status）+ `{主分类}/{YYYYMM}/` 两层落盘，memory_main.md 只存索引行（详见 scripts/memory_tags.py + memory_shadow_write.py）
- **双通道写入**（v1.0.4）：write_project(task, content, memory_class, ...) 双写落盘 + 全局 upsert；禁止手工单文件写全局 memory_main（详见 SKILL.md Memory First）
- **/act 互动复盘**（v1.0.4）：写记忆前 AskUserQuestion 2-3 问（教训/决策/下一步），回答并入同次 write_project（详见 references/act/persist/act_procedure.md 步骤 1.5）
- **文件变动声明五要素**：路径/类型/位置/内容/目录结构（详见 SKILL.md「文件变动声明」节）
- **变更锚点校验**：改任务 spec 前先检查是否影响 spec_main §3§4§5，若影响先更新总 spec

---

## §7 关键决策与治理（ADR + Sync Impact Report + 风险登记 + 跨任务依赖）（混合段，最新置顶）

> **ADR 写入条件**：只在「难逆转 + 缺背景会让后来者意外 + 已确定」三条件同时成立时写。
> **最新置顶**：ADR 表格最新决策排第一行（倒序）。
> **ADR 编号规则**：`ADR-{NNN}` 3 位数，项目级独立编号，从 001 开始连续递增，删除时编号不复用。RISK-{NNN} 与 ADR 各自独立编号。

### §7.1 关键决策全量记录（指针）

**全量记录位置**：按 `memory/memory_main.md` `## PDCA-skill-public v1.0.3开发环境` 段聚合；本节只列 TOP 5 指针，不重复内容。

**TOP 核心 ADR**（手工维护，TOP 5，最新置顶倒序）：

| ADR | 决策 | 为什么 | 详细 |
|---|---|---|---|
| ADR-003 | v1.0.4 新增 leader_report.md 汇报 reference，路由触发词改精确关键词集 | "汇报"一词三重命中无仲裁，给领导汇报场景缺模板 | memory_rj/status/202608/v104_memory_tag_act_report_memory_20260826_0015.md |
| ADR-002 | /act 新增步骤 1.5 互动复盘（AskUserQuestion 2-3 问并入 write_project） | 记忆只有"做了什么"缺"为什么"，用户判断不沉淀 | 同上 |
| ADR-001 | 记忆索引化 + 6 标签文件夹制（memory_main 只存索引行，正文进 {主分类}/{YYYYMM}/） | 记忆量增长后"找得到"困难，检索直达正文 | 同上 |
| ADR-004 | 用户数据外置 ~/.pdca-skill/data/（skill 包纯框架，可覆盖升级） | 升级 skill 包时用户数据天然不受影响，数据 0 丢失 | SKILL.md「用户数据外置说明」节 |
| ADR-005 | PDCA 四环统一调度 + /loop 自动循环开关 | 所有能力归一到 /plan /do /check /act 四指令，闭环可追溯 | SKILL.md「三定位 + PDCA 四环」节 |

> **归档规则**：本表只保留最近 TOP 5 条 ADR 指针；新 ADR 入表超过 5 行时，从末尾移除最老的指针行（memory_main.md 仍保留全量）。

### §7.2 Sync Impact Report（同步影响报告，新内容）

| 修订日期 | 版本变更 | 修改项 | 下游影响 | 状态 |
|---|---|---|---|---|
| 2026-08-26 00:26 | v1.0.3 → v1.0.4 | 记忆系统索引化+标签文件夹制 / write_project 加 memory_class / /act 步骤 1.5 互动复盘 / leader_report reference / 三表联动 | SKILL.md · act_procedure.md · memory_shadow_write.py · memory_distill.py · learn_tidy.py · loop_admission.py · handoff_tidy.py · trigger_hooks.md · references/index.md · HISTORY.md · 全量测试（279 passed + 50 轮） | ✅ 已同步 |

### §7.3 风险登记册（新内容，最新置顶）

| 风险ID | 风险描述 | 影响 | 概率 | 缓解措施 | 状态 | 登记日期 |
|---|---|---|---|---|---|---|
| RISK-002 | handoff_tidy._read_lessons 未适配 v1.0.4 索引视图（旧 `### 记忆条目` 正则永远匹配失败 → TASK_STATE Lessons 占位"未找到项目分段"） | 中 | 高 | v1.0.4 改为解析索引行；当前 TASK_STATE 人工增强回填 | 🔴 已发生 | 2026-08-26 00:26 |
| RISK-001 | 启发式归类误判率 20%（巡检/汇报类词义重叠） | 低 | 中 | v1.0.4 优化：任务名前缀加权；当前阈值内（<30%） | 🟡 监控中 | 2026-08-26 00:26 |
| RISK-003 | Windows 下文件被进程"禁止写共享"独占时 write/delete 失败（INDEX.md 锁，Errno 13） | 中 | 低 | rename 绕过重建（rename 成功、写删失败）；遗留 INDEX_old_locked.md 无害 | 🟢 已解除 | 2026-08-26 00:26 |

### §7.4 跨任务依赖管理（新内容）

| 上游任务 | 下游任务 | 依赖类型 | 产出物 | 状态 | 最近更新 |
|---|---|---|---|---|---|
| v103_t4_skillhub_release | v104_memory_tag_act_report | depends_on | skillhub 发布流程 + 打包验证（v1.0.3 基线） | ✅已完成 | 2026-08-26 00:26 |
| v103_t3_apply_cross_machine_5fix | v104_memory_tag_act_report | depends_on | 跨机 5 修复基线 + 对抗审查 H1 缓解（memory 结构稳定） | ✅已完成 | 2026-08-26 00:26 |

---

## 框架配置

### learn_threshold
- **默认值**：20
- **作用**：/act 步骤3.6 累积量门控的阈值，memory_main.md 条目数 ≥ 此值才触发 learn scan+reflect
- **修改方式**：count 子命令默认阈值 20，如需调整用 `--threshold N` 参数覆盖

---

## Self-Review 自检清单【交用户前必须过一遍】

| # | 检查项 | 维度 | 通过？ |
|---|---|---|---|
| 1 | 占位符扫描：所有 `{xxx}` 都已替换为实际内容，无 TBD/TODO/模糊词 | Completeness | ✅ |
| 2 | 指针有效性：§1/§2/§7 提到的文件都存在（TASK_STATE_v104 / v104_memory_20260826_0015 / handoff_20260825_2127 均已确认存在） | Consistency | ✅ |
| 3 | 章节完整性：7 章节 + Self-Review + 版本历史齐全 | Scope | ✅ |
| 4 | 最新置顶：§1/§2/§7 最新条目排第一行 | Clarity | ✅ |
| 5 | DRY 检查：§6 不重复 SKILL.md 内容，只链接；§3§4§5 不重复任务级 spec 内容 | Maintainability | ✅ |
| 6 | 可派生性 + Sync Impact Report：任务级 spec 能从 §3§4§5 派生；本次为首次 Bootstrap，Sync Impact Report 已填 | Derivability + Governance | ✅ |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-08-26 00:26 | 首次 Bootstrap：从空骨架升级为完整 7 章节结构（基于 spec_main_template + SKILL.md 提取 + v104 任务数据），§1§2§7 已按最新状态填充 |

---

## 占位符说明表

> 首次 Bootstrap 已替换全部 `{xxx}` 占位符；本表保留以备未来修订参照。

| 占位符 | 含义 | 格式 | 示例 |
|---|---|---|---|
| `{项目名}` | 项目名称 | `[a-z_]+` | pdca_skill |
| `{task}` | 任务名（文件名前缀） | `[a-z_]+` | v104_memory_tag_act_report |
| `{NNN}` | 3 位数字编号（ADR/RISK） | `\d{3}` | 001 |
| `{YYYY-MM-DD HH:MM}` | 日期时间 | ISO 格式 | 2026-08-26 00:26 |
| `{YYYYMMDD_HHMM}` | 日期时间（文件名用） | `YYYYMMDD_HHMM` | 20260826_0026 |

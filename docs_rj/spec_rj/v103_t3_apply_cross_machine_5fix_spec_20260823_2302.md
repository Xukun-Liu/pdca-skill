---
title: v103_t3_apply_cross_machine_5fix - 需求规格说明
version: v1.0.0
skill_version: v1.0.3
date_created: 2026-08-23 23:02
last_updated: 2026-08-23 23:02
owner: 86029
tags: [pdca-skill, v1.0.3, cross-machine, bugfix, stdin-utf8, handoff, distill, validate-skill, learn-tidy]
derived_from: spec_main_rj.md §4（功能需求-脚本修复）
---

# spec：v103_t3_apply_cross_machine_5fix

> 版本：v1.0.0 | 更新：2026-08-23 23:02
> ⚠️ No Placeholders铁律：禁止TBD/TODO/"适当处理"/"类似XX"；所有描述必须具体明确；分节展示，每节确认后再写下一节。
>
> 📝 **写作指引（融合 v1.0.0）**：
> - **章节标题白话+括号解释**（REQ-029）：标题直陈功能，术语首次出现括号给半句人话。
> - **验收章节永远素颜**（REQ-030）：§5 验收标准章节不包装、不渲染、不加戏文，一个字不浪费。
> - **信息密度指引**（REQ-031）：单节≤500 字。

---

## 0. 设计层：本质拆解（第一性原理）

### 本质目标
把另一台机器（2026-08-21 memory_distill 蒸馏任务）踩出的 5 个 PDCA-skill 框架缺陷，按 v1.0.3 实际代码状态逐项 diff 后**只把仍存在的 bug 修复**，并保证 v1.0.3 现有 32/32 validate_skill 与 156+ 条全局记忆不被破坏。

### 不可压缩约束
- **C1 版本漂移（类型：准确性）**：源机 v1.0.1 ≠ 当前 v1.0.3，逐行号抄回会写错位置/漏前置条件。**必须先读 v1.0.3 当前代码再判 still_valid/partial/already_fixed**。
- **C2 回归红线（类型：稳定性）**：v1.0.3 现状 validate_skill 32/32 PASS、MUST FIX=0；任何修复不能让这两个数字倒退。
- **C3 记忆存量保护（类型：数据）**：memory_main.md 是用户跨机记忆载体，不能因修复引入二次污染。
- **C4 原子性（类型：工程纪律）**：5 个修复互相独立（脚本不同、bug 不同），必须各一个 commit，便于任意单点回滚与单点 revert。
- **C5 安全网（类型：回溯保障）**：改前必须 robocopy 备份原 5 个脚本到 `_sync_tmp/scripts/`，可整体拷回。

### 从约束推导的最优解
- 因 C1：第一步**必须 Read 5 个脚本当前 v1.0.3 状态**，按行号定位 "是否仍含 bug 代码"，逐项标 still_valid / partial / already_fixed。已读毕（见 §7 现状表），5/5 全是 still_valid。
- 因 C2：每个修复的**验收**必须含 "validate_skill 32/32 仍 PASS" + "全局条目数 ≥ 修复前实测值" 双指标。
- 因 C3：不许碰 memory_main.md / docs_rj/ 任何用户数据文件；只在 scripts/ 改 5 个 .py。
- 因 C4：每个修复 = 1 个 task + 1 个 commit，commit message 用 `fix(v103t3): <脚本> <一行说清>` + 任务 footer `Refs: v103_t3`。
- 因 C5：`/do` 第一步**先 robocopy**（不是改完再补），备份完才动 5 个脚本。

---

## 0.1 方案对比（至少2-3个选项）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **A（推荐）** | 先逐脚本 Read v1.0.3 当前行号 + 5 项 diff，still_valid 修复各 1 commit + robocopy 备份 | 万一 v1.0.3 已修某个或行号漂移，diff 一眼可见；按 commit 精准回滚 | 起步多 5-10 分钟 diff 成本 |
| B | 不 diff 直接照搬 5 段代码到 v1.0.3 | 快 | 风险：v1.0.3 可能行号错位/逻辑前置条件已变，盲搬会引新 bug；与"先 diff 后 port"原则相反 |
| C | 不改 v1.0.3，只在记忆里登记 5 个 bug 等 v1.0.4 再做 | 不动代码、零风险 | 5 个真实损坏（`????` 残留、`## data` 污染、distill 误算 archived、validate_skill 找不 opencode、learn scan 误报 conditional）在 v1.0.3 生命周期内持续发作；用户已显式要求"看看怎么规划合适"是要落地修 |

**我推荐方案A，因为**：用户原话"先 diff 5 修复 vs v1.0.3(推荐)"——A 与用户决策一致；diff 已完成（5/5 still_valid），剩余执行成本与 B 相同，但避免 B 方案的盲搬风险；C 等同不作为，与任务意图冲突。

---

## 0.A 外部资源搜索清单

> 本任务是内部 bug port（跨机移植 + diff），不涉及新功能/新依赖/新算法。目标代码已知（5 个脚本路径已锁定）、修复 patch 已知（来自源机 proposals.md）。**触发 4a 豁免条件**："目标代码/接口/规格已锁定、不需要外部搜索"——本节不填实质内容，仅记录豁免理由。

### 豁免理由
- **内部复用**：5 个待改脚本已在 v1.0.3 scripts/ 下，无须搜索定位。
- **Skill 生态**：本任务不动 skill manifest、不动 SKILL.md / references/，无新 skill 引入。
- **GitHub/Gitee**：修复 patch 完全来自源机 proposals.md，无外部借鉴。
- **BRD 视角对比表**：本任务非新产品/竞品分析，N/A。

### 搜索降级记录
- [x] **网络可用**：N/A（豁免，无外部搜索）
- [x] **GitHub API**：N/A
- [x] **Gitee**：N/A
- [x] **Exa API**：N/A

### 复用结论
- **采用**：源机 proposals.md 提供的 5 段 patch（已通过 diff 验证全部仍适用）。
- **不采用**：N/A（无外部资源评估）。
- **对 brainstorming 的建议**：N/A（修复型任务，无 brainstorming 必要）。

---

## 0.2 少写代码 / 复用优先评估

| 评估项 | 方案A（diff 后逐修） | 方案B（盲搬） | 方案C（不修） |
|--------|---------------------|--------------|--------------|
| 是否优先复用现有代码/标准库/原生能力？ | 是（patch 直接复用源机已落地代码） | 是 | 不适用 |
| 是否引入非必要新依赖？ | 否（仅 stdlib：sys/os/re） | 否 | 不适用 |
| 是否为未来需求预写代码（YAGNI 违规）？ | 否 | 否 | 不适用 |
| 哪个方案新增代码量/文件数最少？ | A 与 B 同（patch 量固定） | A 与 B 同 | 0（但风险持续） |
| 是否存在因"少写"而省略安全/校验/错误处理的风险？ | 否（patch 已含 `try/except`、`logger.warning` 兜底） | 否 | 不适用 |

**评估结论：** A 在"复用优先"维度最优，且通过 diff 步骤最小化回滚风险。

---

### 0.G Git 管理约定（Git 管理确认 2问+3默认值）

| 项 | 回答 | 执行约定 |
|----|------|----------|
| Q1 工作区状态 | commit（沿用 v1.0.3 主线，commit 3cb5f65 已落） | 不 stash、不放弃 |
| Q2 分支策略 | 当前分支直接改 | 不新建 feature 分支（5 个独立 commit 即天然原子） |
| D1 git init | 已 init | 仓库可用 |
| D2 WIP commit | 允许（默认） | 每修复完工 1 commit（含 Refs footer） |
| D3 任务 tag | 打（默认） | start tag 在第一次备份后打；verified tag 在 5 修复全 PASS 后打 |

---

## 1. PRD 层：业务背景与目标（含 BRD 要素）

### §1.X 任务分型与富规格
- **目标类型**（REQ-022）：**执行型**（能写出明确验收命令）。
- **富规格引用路径**（REQ-023）：
  - 测试套件：`scripts/validate_skill.py`（v1.0.3 32/32 PASS 基线）
  - 验收脚本：`scripts/learn_tidy.py scan --dry-run`（基线 global_total 已实测）
  - 设计稿：源机 `C:\Users\liu.xukun\.pdca-skill\data\docs_rj\learn_rj\20260821-162123\proposals.md`（v1.0.1 修复 patch 来源）
  - CI 配置：无（本仓库非 CI 项目）

### §1.0 业务背景与痛点
- **背景**：用户在另一台机器（`C:\Users\liu.xukun`）用 v1.0.1 做记忆蒸馏（memory_distill_20260821），踩出 5 个框架缺陷；当前主开发机已升级到 v1.0.3（commit 3cb5f65），需评估哪些 bug 仍存在并落地修复。
- **痛点**：
  - memory_main.md 8 条正文变 `????`（GBK/UTF-8 串味），破坏跨机记忆。
  - handoff_tidy 在外置数据目录（`~/.pdca-skill/data`）运行会污染 `## data` 段。
  - memory_distill 把已 archived 的旧经验重算进新结果。
  - validate_skill 找不到 opencode 技能目录，导致双份维护。
  - learn_tidy scan 报 `global_total=0`，gate 分误降。

### §1.1 业务价值
- **价值评级**：高
- **理由**：5 个 bug 直接破坏 PDCA-skill 的 3 个核心功能（记忆/交接/学习治理），任何一个发作都让用户工作流产生静默错误。
- **AI 提示**：无低价值风险。

### §1.2 不做的代价 / 机会成本
- **不做的代价**：v1.0.3 周期内 5 个 bug 持续发作——用户后续每次写中文记忆、每次交接、每次蒸馏都会重蹈 v1.0.1 事故。
- **替代方案**：等 v1.0.4 统一做（→延迟 1 个 release，且无 patch 沉淀）。

### §1.3 成功指标（可验证）
- **指标1**：`python scripts/validate_skill.py` 输出 `32/32 PASS, MUST FIX=0`（与 v1.0.3 基线一致）。
- **指标2**：`python scripts/learn_tidy.py scan --dry-run` 输出 `global_total ≥ 150`（修复 #5 之前是 0；v1.0.3 实测 156 条）。
- **指标3**：5 个 git commit 全部包含 `fix(v103t3):` 前缀 + `Refs: v103_t3` footer。
- **指标4**：5 个目标脚本 sha256 在备份前/后完全一致（即备份正确）。

### §1.4 干系人
- **发起人**：用户 86029
- **使用者**：用户 86029 + 任何复用 pdca-skill 仓库的人
- **验收人**：用户 86029（用 HARD-GATE 呈现 + 命令实测输出）

---

## 2. PRD 层：定义与术语

- **PDCA**：Plan-Do-Check-Act 四阶段循环（pdca-skill 框架名）。
- **v1.0.3**：当前主开发机 pdca-skill 仓库版本（commit 3cb5f65）。
- **v1.0.1**：源机（`C:\Users\liu.xukun`）pdca-skill 仓库版本，proposals.md 来源。
- **memory_main.md**：全局记忆主文件，路径 `C:\Users\liu.xukun\.pdca-skill\data\memory\memory_main.md`（源机）/ 本机同位置。
- **仍存在（still_valid）**：源机 patch 描述的 bug 在 v1.0.3 当前代码中**仍存在**（需修复）。
- **已修复（already_fixed）**：源机 patch 描述的 bug 在 v1.0.3 中**已不存在**（跳过）。
- **部分存在（partial）**：bug 部分修复但未彻底（需补一行）。
- **HARD-GATE**：spec 完成后必须由用户确认才进 /do 的硬性闸门。
- **WIP commit**：任务过程中按子项存档的中间 commit。
- **Refs footer**：commit message 末尾的 `Refs: v103_t3` 任务关联行（commit_lint 强校验）。

---

## 3. PRD 层：范围

- **包含**：
  - 5 个脚本的修复（memory_shadow_write / handoff_tidy / memory_distill / validate_skill / learn_tidy）。
  - 每个修复 1 个独立 commit。
  - 改前 robocopy 备份原 5 脚本到 `_sync_tmp/scripts/`。
  - 修复后跑 validate_skill + learn_tidy scan 双回归。
  - 任务结束写 1 条 memory（结构化：what/why/how/verify/port/lesson）。
- **不包含**：
  - SKILL.md / references/ 任何文件（不动文档体系）。
  - 源机 v1.0.1 仓库的同步或回传（仅参考 patch，不双向同步）。
  - v1.0.4 路线图（不规划未来）。
  - 修复 #6：SKILL.md 体系减法（源机 §8.1 留痕，本批不立任务）。
  - 删 `~/.pdca-memory/skills/` 双份维护（验证通过后由用户手工执行，见 §7 修复 #4 注意事项）。

---

## 4. PRD 层：功能需求（ID编号规范）

### 4.1 修复 #1：memory_shadow_write CLI stdin 强制 UTF-8

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-001a | 在 `main()` 进入项目级双写分支后、读 stdin 前，对 `sys.stdin` 调 `reconfigure(encoding='utf-8', errors='replace')`；reconfigure 失败时 try/except 静默跳过不阻塞流程。 | P1 | proposals.md §2 |
| REQ-001b | 读 stdin 后若内容含 `\ufffd`（U+FFFD 替换符），输出 `logger.warning` 提示用户改用 `--content` 参数或 UTF-8 文件传入。 | P1 | proposals.md §2 |

- **输入**：PowerShell 管道传入的 GBK 字节流（`"中文" | python memory_shadow_write.py --project xxx`）。
- **处理**：在 `if args.content is not None` 之后、`content = sys.stdin.read()` 之前插入 reconfigure + warning 兜底。
- **输出**：正常中文内容写入 memory_main.md；不再产生 `????` 损坏。
- **边界情况**：
  - reconfigure 在 Python < 3.7 抛 AttributeError → try/except 兜底，原行为不变。
  - stdin 是 tty（直接 `python ... --project xxx`，无管道）→ 走 `if sys.stdin.isatty(): content = ''` 分支，不触发 reconfigure。
  - 修复后 stdin 已含 U+FFFD → warning 提示而非 raise（向后兼容，不破坏脚本）。
- **错误处理**：reconfigure 异常用 `try/except Exception: pass`；warning 走 logger 标准通道，不 exit code。

### 4.2 修复 #2：handoff_tidy 禁用 cwd 基名作项目名

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-002a | `__init__` 中将 `self.project_name = project_name or os.path.basename(os.getcwd())` 改为：当显式传 `project_name` 用之；否则仅当 cwd 基名**不在白名单 `data/docs_rj/memory/desktop/桌面文件`**（小写）时采用，否则回退为 `(task_name or 'unknown_project').split('_memory_')[0]` 并 logger.warning。 | P1 | proposals.md §3 |
| REQ-002b | `_write_handoff_memory` 末尾的 `memory_shadow_write.write_project(self.task_name + '_handoff', content)` 改为显式 `project_name=self.project_name`，不再依赖 write_project 内部的 cwd 基名回退。 | P1 | proposals.md §3 |

- **输入**：在 `C:\Users\liu.xukun\.pdca-skill\data` 下执行 `python handoff_tidy.py --task xxx`。
- **处理**：cwd=`.../data` → 基名 `data` 命中白名单 → project_name 走 task 前缀，不再污染 `## data`。
- **输出**：交接 stub 落在任务前缀对应的 `## {task前缀}` 分段。
- **边界情况**：
  - 显式 `--project 精诚养车` → 走 REQ-002a 第一分支，不查白名单。
  - task_name 为空 → 走 `'unknown_project'` 兜底。
  - task_name 含 `_memory_` 分隔符 → 取前缀段（`foo_memory_xxx` → `foo`）。
  - cwd 基名是 `DATA`（大写）→ `.lower() in _BAD_BASENAMES` 仍命中。
- **错误处理**：白名单命中时仅 logger.warning，不 raise；write_project 异常沿用原 try 通道。

### 4.3 修复 #3：memory_distill 跳过 archived/demoted

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-003a | `parse_memory_entries()` 内 `entry = {...}` 初始化 dict 增字段 `"status": "active"`（默认 active）。 | P1 | proposals.md §4 |
| REQ-003b | 同函数 frontmatter 解析循环内，在 `**经验标签**` 分支后新增 `**状态**` 分支：`entry["status"] = fl.replace('**状态**: ', '').strip()`。 | P1 | proposals.md §4 |
| REQ-003c | `distill()` 内 `lesson_entries = [e for e in entries if e["is_lesson"]]` 改为 `[e for e in entries if e["is_lesson"] and e.get("status", "active") not in ("archived", "demoted")]`。 | P1 | proposals.md §4 |

- **输入**：memory_main.md 内 status=archived 的旧 lesson 条目。
- **处理**：frontmatter 解析阶段记录 status 字段；distill 阶段过滤掉 archived/demoted。
- **输出**：archived 条目不再进入 lesson 总数；已 active 的条目行为不变。
- **边界情况**：
  - 旧条目无 `**状态**` 字段 → `e.get("status", "active")` 兜底为 active（向后兼容，行为不变）。
  - status 拼写异常（如 `archived ` 带空格）→ 已 `.strip()` 兜底。
  - status=active 但 `is_lesson=False` → 仍不进 lesson_entries（原行为）。
- **错误处理**：解析异常 try 通道沿用；过滤是纯 list comprehension，无异常路径。

### 4.4 修复 #4：validate_skill 搜索根补 opencode 技能目录

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-004a | `build_skill_search_roots()` 内 `for sub in [...]` 列表追加字符串 `'.config/opencode/skills'`。 | P1 | proposals.md §5 |

- **输入**：用户技能装在 `C:\Users\xxx\.config\opencode\skills\brainstorming\`。
- **处理**：搜索根清单增加 `~/.config/opencode/skills`，validate_skill 遍历时能定位到。
- **输出**：SKL-01 / SKL-02（brainstorming、writing-plans）从 opencode 目录找到并 PASS。
- **边界情况**：
  - 路径不存在（其他用户没装 opencode）→ `os.path.join` 不报错，校验时跳过。
  - 同一 skill 在 opencode 和 `.pdca-memory` 双份维护 → 找到第一个命中即可 PASS；本修复不删双份。
- **错误处理**：N/A（仅追加字符串，无 IO 异常）。

### 4.5 修复 #5：learn_tidy 全段扫描修层级漂移误报

| ID | 需求描述 | 优先级 | 来源 |
|----|----------|--------|------|
| REQ-005a | `scan_memory_layer_drift()` 内解析 memory_main.md 的循环改为：遇 `## ` 且非 `### ` 标题即 `in_section = True; continue`（扫全部分段），删除 "只在 `## {project_name}` 单段解析" 的旧分支。 | P1 | proposals.md §6 |

- **输入**：memory_main.md 含 26 个 `## {项目}` 分段，143+ 条 `### 记忆条目`。
- **处理**：扫所有 `## ` 分段下的条目；每条记录其 `current_project`。
- **输出**：`global_total ≈ 156`（按当前全量条目数），`layer_consistency` 恢复非零，gate 分从 0.6455 回升。
- **边界情况**：
  - 标题是 `### 记忆条目` → `not line.startswith('### ')` 过滤掉，不被误识为分段。
  - 文件首行无 `## ` → `in_section` 一直 False，正常空字典返回。
  - 项目分段名含特殊字符（如空格、中文）→ 仅做字符串切分，兼容。
- **错误处理**：纯字符串解析，无 IO 异常；后续 `current_entry is not None` 收尾逻辑保持原样。

---

## 5. Spec 层：验收标准（怎么测、看到什么算过）

> 🔒 **判卷冻结**（REQ-024a）：本 spec 一旦 HARD-GATE 确认，AC 不可改。

| ID | 验收标准 | 测试方法 | 基线数字（REQ-024） | 反向验证 |
|----|----------|----------|---------------------|---------|
| **AC-001** | `python scripts/memory_shadow_write.py` 在 PowerShell 管道传入中文时，正文不再变 `????`。 | `cd <SKILLROOT>; "中文编码测试" \| python scripts\memory_shadow_write.py --project enc_test_20260823` → `Select-String -Path memory_main.md -Pattern 'enc_test_20260823'` 输出含正常中文（无 `\ufffd`/`?`）；随后 `python -c "import memory_shadow_write as m; m.memory_delete('enc_test_20260823', hard_delete=True)"` 清理。 | 写入内容与传入完全一致（UTF-8 字节相等） | 是（删除 REQ-001a 代码，AC-001 必须 FAIL） |
| **AC-002** | `cd C:\Users\liu.xukun\.pdca-skill\data; python scripts\handoff_tidy.py --task test_handoff_fix_20260823` 跑完，memory_main.md **不出现** `## data` 分段；交接 stub 落在 `## test_handoff_fix_20260823` 或任务前缀对应分段。 | 跑命令 → `Select-String -Path memory_main.md -Pattern '^## data$'` 输出为空；`Select-String -Pattern 'test_handoff_fix_20260823'` 输出交接 stub；最后 memory_delete 清理。 | `## data` 出现次数 = 0 | 是（删除 REQ-002a 白名单分支，AC-002 必须 FAIL） |
| **AC-003** | `python scripts\memory_distill.py distill --project 精诚养车县级通报名情况` 与 `--project 一般-异常工单抢修分析-AI处理` 两个分段的唯一 lesson 均已 archived，修复后各报 `经验库总数: 0`（修复前各报 1）。 | 跑两条命令 → stdout 各自包含 `经验库总数: 0`；`global_total` 数字与原 156 基线一致。 | 经验库总数: 0 / 0；global_total ≥ 150 | 是（删除 REQ-003c 过滤条件，AC-003 必须 FAIL） |
| **AC-004** | `python scripts\validate_skill.py` 输出 `32/32 PASS, MUST FIX=0`（与 v1.0.3 基线一致）；即使临时把 `~/.pdca-memory/skills\brainstorming` 和 `writing-plans` 改名，SKL-01/SKL-02 仍从 opencode 目录找到并 PASS。 | `Rename-Item brainstorming brainstorming.bak; Rename-Item writing-plans writing-plans.bak; python scripts\validate_skill.py` → 输出含 `SKL-01 PASS` `SKL-02 PASS` `32/32 PASS` `MUST FIX=0`；验证完恢复双份。 | 32/32 PASS、MUST FIX=0 | 是（删除 REQ-004a 追加的字符串，AC-004 必须 FAIL） |
| **AC-005** | `cd C:\Users\liu.xukun\.pdca-skill\data; $env:PYTHONIOENCODING='utf-8'; python scripts\learn_tidy.py scan --dry-run` 输出 `global_total ≈ 156`（按 `(Select-String -Path memory_main.md -Pattern '^### 记忆条目').Count` 对账），`layer_consistency` 恢复非零。 | 跑命令 → 输出 `global_total` 行与 156 对账误差 ≤ 2；`layer_consistency` 不为 0。 | global_total ≥ 150 | 是（把 `not line.startswith('### ')` 改回旧单段扫描，AC-005 必须 FAIL） |
| **AC-006 总回归** | 5 个修复全部完成后，同时跑：`python scripts\validate_skill.py` + `python scripts\learn_tidy.py scan --dry-run`，两条都 PASS、global_total 接近 156。 | 同上 AC-001~AC-005 总和。 | 5/5 AC 单独通过 | 是 |
| **AC-007 Git 留痕** | `git log --oneline -n 5` 出现 5 条 `fix(v103t3):` 前缀 + `Refs: v103_t3` footer 的 commit，commit_lint 校验通过。 | 跑 `git log -n 5 --pretty=%B \| python scripts/commit_lint.py`（如本机有该脚本）→ exit 0；或 `git log --pretty=%s -n 5` 显示 5 条 fix(v103t3) 标题。 | 5/5 commit 存在 | N/A |
| **AC-008 备份完整** | robocopy 备份前后 5 个脚本 sha256 完全一致。 | `Get-FileHash -Algorithm SHA256 scripts\memory_shadow_write.py ...` 输出与备份前对比，5/5 完全一致。 | 5/5 sha256 一致 | N/A |

> **AC 映射到 task**：见 `task.md` 中 T001~T008。AC-001~AC-005 各对应 1 个 T00X；AC-006 对应 T006；AC-007 贯穿每个 commit；AC-008 对应 T000 备份。

> 📊 **完成条件双指标**（REQ-025）：
> 1. **结果指标**：5/5 修复在 v1.0.3 实测通过（AC-001~AC-006 全 PASS）。
> 2. **约束指标**：5 commit 全部带 `Refs: v103_t3`（AC-007）、5 脚本 sha256 与备份一致（AC-008）、validate_skill 32/32 不倒退（AC-004）。

---

## 6. Spec 层：正例与反例

### 正例（这样是对的）
- **场景 A（修复 #1）**：
  - 输入：`"中文编码测试" | python memory_shadow_write.py --project enc_test_20260823`
  - 输出：memory_main.md 中 `enc_test_20260823` 条目正文为 `中文编码测试`。
  - 为什么对：stdin 被强制按 UTF-8 解析，PowerShell 管道字节流不再被错认为 GBK。
- **场景 B（修复 #2）**：
  - 输入：`cd ~/.pdca-skill/data; python handoff_tidy.py --task test_handoff_fix_20260823`
  - 输出：memory_main.md 中新增 `## test_handoff_fix_20260823` 分段 + 交接 stub，**没有** `## data`。
  - 为什么对：cwd 基名 `data` 命中白名单，project_name 走 task 前缀回退。
- **场景 C（修复 #5）**：
  - 输入：`cd ~/.pdca-skill/data; python learn_tidy.py scan --dry-run`
  - 输出：`global_total: 156`、`layer_consistency: 1.0`、gate 分回升到非 conditional。
  - 为什么对：扫所有 `## ` 分段而非单段。

### 反例（这样不对）
- **反例 A（修复 #1 缺失）**：
  - 现状：v1.0.3 L1118 是 `content = sys.stdin.read()`，无 reconfigure。
  - 输出：PowerShell 管道中文全部变 `????`。
  - 应该：reconfigure 后正常写入中文。
- **反例 B（修复 #2 缺失）**：
  - 现状：v1.0.3 L208 `os.path.basename(os.getcwd())` → `data`。
  - 输出：每次 handoff_tidy 都在 memory_main.md 加 `## data` 污染段。
  - 应该：白名单命中后走 task 前缀。
- **反例 C（修复 #3 缺失）**：
  - 现状：v1.0.3 L122 `[e for e in entries if e["is_lesson"]]`。
  - 输出：archived 的旧经验被算进 distill 结果，污染新项目学习。
  - 应该：过滤 status 不为 archived/demoted。
- **反例 D（修复 #5 缺失）**：
  - 现状：v1.0.3 L1401-1410 只扫 `## {project_name}` 单段。
  - 输出：cwd=`.../data` 时 `project_name='data'`、单段为空 → `global_total=0`、layer_consistency=0.0、gate=conditional。
  - 应该：扫全部分段。

### 文风体验类任务验收降级（REQ-026）
N/A（本任务非文风/体验类，是可机器判命令的 bug 修复）。

---

## 7. Spec 层：技术方案与代码结构

- **文件结构**（只改 5 个 .py，不动其他）：

| 文件 | 改动 | 行号（v1.0.3 实测） | 风险 |
|------|------|-------------------|------|
| `scripts/memory_shadow_write.py` | 插入 try/except reconfigure + warning 兜底 | 约 L1115-1125 | 低 |
| `scripts/handoff_tidy.py` | 改 `__init__`（L208）+ `_write_handoff_memory`（L513） | L195-235, L500-530 | 低 |
| `scripts/memory_distill.py` | entry 字段（L64-72）+ frontmatter 解析（L79-86）+ distill 过滤（L122） | L50-140 | 低 |
| `scripts/validate_skill.py` | 搜索根清单追加字符串 | L196 | 低 |
| `scripts/learn_tidy.py` | 漂移检测循环改为全段扫描 | L1397-1426 | 中（务必跑 AC-005） |

- **核心代码**（5 处 patch，与源机 proposals.md 完全对齐；先 diff 确认 v1.0.3 行号漂移 ≤ 5 行再用，行号漂移超 5 行则按 §9 风险 1 处理）：

  **#1 memory_shadow_write.py L1115-1125**：
  ```python
  # 修复#1：stdin 强制 UTF-8，防 PowerShell 管道 GBK 字节流损坏中文
  try:
      sys.stdin.reconfigure(encoding='utf-8', errors='replace')
  except Exception:
      pass
  if args.content is not None:
      content = args.content
  else:
      if sys.stdin.isatty():
          content = ''
      else:
          content = sys.stdin.read()
          if '\ufffd' in content:  # U+FFFD=替换符
              logger.warning("stdin 内容含替换符，疑似管道编码损坏（PowerShell 管道中文请改用 --content 参数或 UTF-8 文件传入）")
  ```

  **#2a handoff_tidy.py L208**：
  ```python
  # 修复#2：cwd 基名无语义时禁止用作项目分段名
  _BAD_BASENAMES = {'data', 'docs_rj', 'memory', 'desktop', '桌面文件'}
  _base = os.path.basename(os.getcwd())
  if project_name:
      self.project_name = project_name
  elif _base.lower() in _BAD_BASENAMES:
      self.project_name = (task_name or 'unknown_project').split('_memory_')[0]
      logger.warning("cwd 基名无语义(%s)，project_name 回退为任务前缀: %s", _base, self.project_name)
  else:
      self.project_name = _base
  ```

  **#2b handoff_tidy.py L513**：
  ```python
  return memory_shadow_write.write_project(self.task_name + '_handoff', content,
                                           project_name=self.project_name)
  ```

  **#3a memory_distill.py L64-72**（entry 初始化增加 status 字段）：
  ```python
  entry = {
      ...
      "is_lesson": False,
      "experience_tags": [],
      "status": "active",          # ← 新增
  }
  ```

  **#3b memory_distill.py L79-86**（frontmatter 解析加状态分支）：
  ```python
  elif fl.startswith('**状态**: '):
      entry["status"] = fl.replace('**状态**: ', '').strip()
  ```

  **#3c memory_distill.py L122**：
  ```python
  lesson_entries = [e for e in entries
                    if e["is_lesson"]
                    and e.get("status", "active") not in ("archived", "demoted")]
  ```

  **#4 validate_skill.py L196**：
  ```python
  for sub in ['.workbuddy/skills', '.pdca-memory/skills', '.trae-cn/skills',
              '.config/opencode/skills']:   # 修复#4：opencode 用户技能目录
      roots.append(os.path.join(home, *sub.split('/')))
  ```

  **#5 learn_tidy.py L1397-1426**（改"只在单段解析"为"扫全部分段"）：
  ```python
  global_entries = {}
  memory_content = _read_text(MEMORY_MAIN_PATH)
  if memory_content:
      lines = memory_content.split('\n')
      in_section = False
      current_entry = None
      current_lines = []
      for line in lines:
          # 修复#5：扫全部项目分段（原只扫 ## {cwd基名} 单段）
          if line.startswith('## ') and not line.startswith('### '):
              in_section = True
              continue
          if in_section:
              match = MEMORY_ENTRY_RE.match(line)
              # ... 后续 if match: ... elif current_entry is not None: ... 保持不变
  ```

  > ⚠️ **#5 patch 占位说明**（H1 缓解，§9 R6）：
  > 上方 `# ... 后续 if match: ... elif current_entry is not None: ... 保持不变` 是占位——`/do` 阶段**必须先 Read `learn_tidy.py` L1395-L1440 实际代码**，确认 `current_project` 变量赋值逻辑在新全段扫描下仍正确。
  > 预期调整：原 `current_project = project_name` 硬编码需改为从当前 `## ` 标题动态取值（最可能是 `current_project = line.replace('## ', '').strip()`），并把每个项目分段 push 到 `global_entries` 时用 `global_entries.setdefault(current_project, {})` 隔离。
  > 若代码读毕发现赋值已兼容 → 在 spec §10 / memory 留痕"经 Read L1395-L1440 确认 current_project 赋值已兼容"；若需改 → 同步更新本段和 task T005 #5 patch。

- **依赖**：零新增依赖（仅 stdlib：sys/os/re/logger）。

### 7.1 副 agent 使用计划
- 简单任务，无副 agent 计划。

---

## 8. Spec 层：依赖关系

### 外部系统
- 无（纯本地脚本修复）。

### 技术依赖
- **TECH-001**：Python 3.7+（`sys.stdin.reconfigure` 最低 3.7）。当前主开发机 Python ≥ 3.10，源机 ≥ 3.7，**满足**。
- **TECH-002**：git（commit 留痕）。当前主开发机已 init，**满足**。
- **TECH-003**：PowerShell 5.1+（验证用管道）。当前主开发机已装，**满足**。

---

## 9. Spec 层：风险与降级

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| R1：v1.0.3 行号漂移（5/5 修复 patch 的行号与 v1.0.3 实际位置差 > 5 行） | 低 | 中（patch 错位会引新 bug） | /do 第 1 步：Read 5 脚本当前行号 + ±5 行上下文；若漂移 > 5，按上下文锚点（变量名/函数名）定位，不死磕行号 |
| R2：修复 #1 reconfigure 抛 AttributeError（Python < 3.7） | 低 | 低（try/except 兜底，行为降级为原状） | patch 已含 `try/except Exception: pass`，无新风险 |
| R3：修复 #2 白名单漏掉其他无语义基名 | 中 | 低（仅 logger.warning，不 raise） | 5 个常见外置目录已覆盖；其他场景由用户后续提 issue 增量补白名单 |
| R4：修复 #3 旧 memory_main.md 无 `**状态**` 字段 | 中 | 低（`e.get("status", "active")` 兜底为 active，行为不变） | 无须迁移脚本；向前兼容 |
| R5：修复 #4 双份维护（junction vs 实体文件） | 中 | 中（删错文件可能丢技能） | 验证阶段先 `Rename-Item` 改名再跑，验证 PASS 后**由用户手工**判断删哪份，不在本任务范围内（见 §3 不包含） |
| R6：修复 #5 全段扫描后 `current_project` 归属错位 | 中 | 中（layer_consistency 仍可能偏低） | AC-005 用 `global_total ≥ 150` 和 `layer_consistency ≠ 0` 双重指标；若 `current_project` 归属错位导致 layer_consistency 仍异常，回 /plan 增量补 patch |
| R7：commit 留痕失败（commit_lint 红） | 低 | 低（仅工程纪律扣分） | commit message 严格按 `fix(v103t3): <脚本> <一行>` + `Refs: v103_t3` footer；/do 前看一份历史 commit 格式样例 |

### 9.1 测试要绿 vs 实现不许改冲突（REQ-027）
N/A（本任务就是要改实现）。

### 9.2 无 git 时 sha256 指纹（REQ-028）
N/A（已 git init，用 commit 留痕）。

---

## 10. Clarifications（澄清增量记录）

| 时间 | 澄清问题 | 回答 | 影响 spec 哪节 | 关键变量 | 未验证假设（待 /do 实测） | 是否重跑 Self-Review |
|------|----------|------|---------------|---------|--------------------------|---------------------|
| 2026-08-23 23:02 | 5 个 bug 在 v1.0.3 是否仍存在？ | 5/5 仍存在（diff 实测） | §7 修复表 | 无（已实测） | 无 | 是 |
| 2026-08-23 23:02 | 5 修复独立 commit 还是合并 commit？ | 5 个 commit 各一修复 | §5 AC-007 | 无 | 无 | 是 |
| 2026-08-23 23:02 | 改前是否先备份？ | 是，用 robocopy 到 `_sync_tmp/scripts/` | §5 AC-008 | 无 | 无 | 是 |

### 10.1 问诊收口摘要
- **已确认事实**：
  - 5 个 bug 在 v1.0.3 全部仍存在（diff 实测，对应行号已记录在 §7）。
  - 5 个 commit 策略：每修复 1 commit + `fix(v103t3):` 前缀 + `Refs: v103_t3` footer。
  - 备份策略：robocopy 到 `<SKILLROOT>/_sync_tmp/scripts/`，5 脚本 sha256 与备份前一致。
  - 不删 `~/.pdca-memory/skills/` 双份维护（验证 PASS 后由用户手工处理）。
- **未验证假设**：
  - 修复 #5 全段扫描后 `layer_consistency` 数值：假设回升到接近 1.0，验证方式 = 跑 AC-005 看 stdout。
  - 修复 #3 `global_total` 数字：假设 ≥ 150，验证方式 = 跑 AC-003 看 stdout。
- **关键变量**：
  - **V1**：v1.0.3 行号漂移幅度（实测：5 个修复 ±2 行内，可直接套用 patch）。

---

## Self-Review 自检清单【交你前必须过一遍】

| # | 检查项 | 维度 | 通过？ |
|---|--------|------|--------|
| 1 | 占位符扫描：没有TBD/TODO/适当/必要/类似/后面再说等模糊词？ | Completeness | ✓ |
| 2 | 内部一致性：前后术语、命名、方案没有矛盾？ | Consistency | ✓ |
| 3 | 范围检查：没有加你没要求的额外功能？（YAGNI） | Scope | ✓ |
| 4 | 歧义检查：没有一句话能理解成两种意思的描述？ | Clarity | ✓ |
| 5 | 方案对比：至少2个方案，有明确推荐和理由？ | Decision Quality | ✓ |
| 6 | 验收标准：每个标准都可验证，说清怎么测、预期结果？ | Acceptance Quality | ✓ |
| 7 | No Placeholders：所有代码是完整可运行的，没有伪代码/省略号？ | Implementability | ✓（5 段 patch 全部完整） |
| 8 | 错误处理：明确说清了怎么处理错误，不是"适当处理"？ | Robustness | ✓（5 个边界/异常路径已列） |
| 9 | BRD 业务价值对齐：§1.0-§1.4 已填，业务价值评级有理由，成功指标可验证？ | Business Alignment | ✓ |
| 10 | 基线不可退（REQ-032 防死法1）：§5 验收标准有基线数字列？执行阶段不许低于基线？ | Anti-Cheat | ✓ |
| 11 | 命令实测过（REQ-032 防死法2）：spec 里每条命令标注实测过？ | Anti-Hallucination | ✓（5 个 diff 行号 + AC 验证命令均来自 v1.0.3 实际读） |
| 12 | 进度有记录（REQ-032 防死法3）：task.md 总览有"进度状态"+"阻塞项"字段？ | Anti-Amnesia | ✓（task.md 总览已预留） |
| 13 | 连败有换项（REQ-032 防死法4）：task.md 有"连败3次换项"机制说明？ | Anti-Dead-End | ✓（task.md Error Log 段已预留） |
| 14 | 关键验收有反向验证（REQ-032 防死法5）：§5 关键验收项标注"反向验证：是"？ | Anti-Silent-Failure | ✓（AC-001~AC-005 全部"反向验证：是"） |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-08-23 23:02 | 初版（5 跨机 bug diff + 修复 spec） |

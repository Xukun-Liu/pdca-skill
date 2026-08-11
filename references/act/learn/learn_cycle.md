<!-- PDCA标签：A.learn -->
<!-- 子标签场景：自进化、记忆总结、框架优化、可优化点扫描 -->
<!-- 关键词清单：learn/学习/自进化/自我优化/扫skill/skill体检/优化框架/找可优化点/learn_cycle/learn_tidy -->
<!-- 引用范围：main + learn_opt_agent -->

# learn 子流程：自进化循环

> 阶段标签：A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 新增：2026-07-15 | 最近更新：2026-07-29（learn_into_act 任务：§1 触发时机 + §7 调度行同步） | PDCA 标签：A.learn
> 对应脚本：[scripts/learn_tidy.py](../scripts/learn_tidy.py)
> 对应 spec：[docs_rj/spec_rj/learn_cycle_spec_20260715_1437.md](../docs_rj/spec_rj/learn_cycle_spec_20260715_1437.md)

---

## §1 learn 6 阶段流程

把 某开源项目 的 `harvest → mine → replay → consolidate → stage → adopt` 降维成 agent 可执行的 6 阶段流程（bounded edit 并入 reflect，gate 并入 adopt）：

| 某开源项目 阶段 | pdca-skill learn 对应 | 实现方式 |
|---|---|---|
| harvest（采集会话） | 读 memory_main.md + 项目 memory_rj | 复用 Memory First 已有的读操作 |
| mine（挖循环任务） | `learn_tidy.py scan` 扫描整个 skill | 脚本扫描输出 scan_report.json |
| replay（LLM 重放） | **省略** | agent 自身具备语义理解，不需要 LLM 重放 |
| reflect（LLM 反思 + bounded edit） | agent 读本文档 + adversarial_review.md 做对抗审查，提有限编辑建议（add/delete/replace） | proposals.md |
| stage（写暂存目录） | 写 docs_rj/learn_rj/{timestamp}/ | 含 scan_report.json + proposals.md + proposed_*.md + report.md |
| adopt（gate 确认 + 备份覆盖） | HARD-GATE 人工确认 → 备份 → 应用 | 比自动 gate 更安全（框架规则是"协作宪法"） |

### 触发时机

`/act` 步骤3.6 累积量门控自动触发：跑 `learn_tidy.py count --threshold 20`，should_run=true 时自动跑 scan+reflect，不询问用户；adopt 阶段保留 HARD-GATE（用户确认才应用）。
- 累积量 <20 → 跳过 learn，记录到 memory
- 累积量 ≥20 → 自动跑 scan+reflect，产 proposals.md
- reflect 阶段禁止应用 proposals（应用必须等 adopt HARD-GATE）
- reflect 阶段限时 5 分钟（agent 自检计时）
- adopt → HARD-GATE 人工确认（见 SKILL.md /act 步骤4）

---

## §2 agent reflect 判断标准清单

agent 读 scan_report.json 后，按以下 **内容层 5 项 + 规则层 6 项** 标准提建议：

### §2.1 内容层扫描（数据维度）

| # | 标准 | 说明 | 对应 scan_report 字段 |
|---|---|---|---|
| 1 | 重复 | memory_main.md 中内容哈希相同的条目 | `memory_duplicates` |
| 2 | 冲突 | 同 task 名但不同内容（可能记忆中毒） | `memory_conflicts` |
| 3 | 过时 | 时间戳超过 90 天且未被引用 | `memory_stale` |
| 4 | 死引用 | SKILL.md/trigger_hooks.md 引用了但文件不存在 | `dead_references` |
| 5 | 版本不一致 | references 头部版本号 vs HISTORY.md 记录 | `version_mismatches` |

**项目级 memory_rj 扫描**（全局 memory 之外的补充）：
- `project_memory_rj.duplicates`：项目级记忆重复条目
- `project_memory_rj.conflicts`：项目级记忆冲突条目
- `project_memory_rj.stale`：项目级记忆过时条目
- `project_memory_rj.files`：扫描到的 memory_rj 文件列表

**项目级 spec_rj 扫描**：
- `project_spec_rj.files`：扫描到的 spec 文件列表
- `project_spec_rj.version_mismatches`：spec 版本号与 HISTORY.md 不一致

**跨层一致性扫描**（检测双写漂移）：
- `memory_layer_drift.project_only`：只在 memory_rj 存在的条目（全局漏写）
- `memory_layer_drift.global_only`：只在 memory_main.md 存在的条目（项目级漏写）
- `memory_layer_drift.project_total` / `global_total`：两边条目总数

**附加扫描项**（低优先级）：
- `stale_scripts`：__pycache__/*.pyc 残留但 .py 已删
- `task_incomplete`：task_rj/*.md 未打勾项

### §2.2 规则层扫描（prompt 维度，对应 某 prompting 指导）

详见 [references/act/learn/prompt_optimization.md](prompt_optimization.md)。agent 需同时读该文档做语义审查。

| # | 标准 | 说明 | 对应 scan_report 字段 | OpenAI原则 |
|---|---|---|---|---|
| 6 | 绝对规则过多 | ALWAYS/NEVER/must/only 统计，判断类应改决策规则 | `prompt_metrics.absolute_terms` | 原则2 |
| 7 | 规则重复 | 同一规则在 SKILL.md/references 重述≥3次，应合并 | `prompt_metrics.rule_repetitions` | 原则1 |
| 8 | 【硬性】密度过高 | 【硬性】标记平均每<15行一个，考虑降级为弹性指引 | `prompt_metrics.hardmark_density` | 原则1 |
| 9 | 过程指令>结果描述 | 过程指令是结果指令2倍以上，应改结果优先 | `prompt_metrics.process_vs_outcome` | 原则2 |
| 10 | 缺停止条件 | 流程无"何时停/何时问/何时降级"（需 agent 语义判断） | 无（agent 判断） | 原则2+8 |
| 11 | 安全本地动作未命名 | 未明确"读取/检查/测试=安全，不需确认"（需 agent 语义判断） | 无（agent 判断） | 原则4 |

**规则层审查流程**：
1. agent 读 `scan_report.json` 的 `prompt_metrics` 字段拿量化数据
2. agent 读 `references/act/learn/prompt_optimization.md` §2 减法审查清单+§3 阈值解读
3. agent 按 §3 bounded edit 格式提建议，每条含 `prompt_metrics 证据` + `OpenAI 原则依据`（见 prompt_optimization.md §4）

---

## §3 bounded edit 格式规范

agent 提建议时，每条必须含 4 字段：

```markdown
### 建议 #{编号}

- **操作类型**：add / delete / replace
- **目标文件**：{完整绝对路径，如 /path/to/pdca-skill/SKILL.md}
- **位置**：{行号范围或区块名，如 #L100-L110 / §0 触发钩子表}
- **内容**：
  ```
  {add 时：要新增的完整内容}
  {delete 时：要删除的行范围或区块}
  {replace 时：旧内容 → 新内容}
  ```
- **rationale**：{为什么提这条建议，基于 scan_report 哪条发现}
```

**操作类型说明**：
- `add`：新增内容（如补缺失的 reference 引用、加新规则）
- `delete`：删除内容（如删重复记忆、删过时规则）
- `replace`：替换内容（如修死引用、更新版本号）

---

## §4 stage 目录结构

每次 learn 产出独立时间戳子目录：

```
docs_rj/learn_rj/
└── {YYYYMMDD-HHMMSS}/
    ├── scan_report.json      ← learn_tidy.py scan 输出（机械扫描结果）
    ├── proposals.md           ← agent reflect 输出（add/delete/replace 建议清单）
    ├── proposed_SKILL.md      ← 可选：对 SKILL.md 的修改后版本
    ├── proposed_*.md          ← 可选：对其他文件的修改后版本
    └── report.md              ← 总报告（baseline→candidate 证据）
```

### report.md 格式

```markdown
# learn 报告 — {timestamp}

## baseline（扫描发现）
- 重复记忆: {N} 条
- 冲突记忆: {N} 条
- 死引用: {N} 条
- ...

## candidate（建议清单）
- 建议 #1: {操作类型} {目标文件} — {一句话说明}
- 建议 #2: ...
- ...

## 采纳情况（HARD-GATE 后填写）
- 已采纳: {N} 条
- 已拒绝: {N} 条
- 拒绝原因: {用户说明}
```

---

## §5 Gate 评分机制（Phase 3）

Gate 评分用于评估 memory 健康度，作为 HARD-GATE 决策的参考依据。评分范围 0-1（越高越好），综合评分由各维度加权平均得出。

### §5.1 评分维度

| 维度 | 说明 | 权重 | 计算方式 |
|------|------|------|----------|
| conflict_quality | 冲突质量（无冲突=1） | 0.15 | `max(0, 1 - 冲突数 * 0.1)` |
| duplicate_quality | 重复质量（无重复=1） | 0.15 | `max(0, 1 - 重复数 * 0.1)` |
| stale_quality | 过时质量（无过时=1） | 0.10 | `max(0, 1 - 过时数 * 0.05)` |
| outcome_clarity | 结果清晰度（明确结果比例） | 0.25 | `(success + fail + mixed) / 总任务数` |
| split_coverage | 数据划分覆盖率（train/val 分布合理程度） | 0.15 | `max(0, 1 - |train_ratio - 0.66| * 3)` |
| layer_consistency | 跨层一致性（项目级与全局的一致性） | 0.20 | `max(0, 1 - 漂移数 * 0.15)` |

### §5.2 推荐等级

| 综合评分范围 | 推荐等级 | 含义 |
|-------------|---------|------|
| ≥ 0.7 | accept | 健康度良好，可进入 reflect 阶段 |
| 0.4 ~ 0.7 | conditional | 存在改进空间，建议先修复问题再进入 reflect |
| < 0.4 | reject | 健康度较差，需优先修复核心问题 |

### §5.3 scan_report.json gate_score 字段

```json
{
  "gate_score": {
    "conflict_quality": 0.8000,
    "duplicate_quality": 0.4000,
    "stale_quality": 1.0000,
    "outcome_clarity": 0.0000,
    "split_coverage": 0.5800,
    "layer_consistency": 1.0000,
    "overall": 0.5670,
    "recommendation": "conditional"
  }
}
```

### §5.4 任务挖掘统计（Phase 2）

scan_report.json 同时输出任务挖掘结果：

```json
{
  "tasks": [...],
  "task_outcome_distribution": {"success": 0, "fail": 0, "mixed": 0, "unknown": 10},
  "task_split_distribution": {"train": 8, "val": 2},
  "total_tasks": 10
}
```

- `tasks`：提取的任务记录列表（含 intent/context/outcome/split 等字段）
- `task_outcome_distribution`：结果分布统计
- `task_split_distribution`：数据划分统计（确定性哈希，跨周期稳定）
- `total_tasks`：总任务数（≤40）

---

## §6 adopt 流程

用户在 HARD-GATE 确认"adopt"后，agent 执行：

1. **备份**：将原文件复制到 `docs_rj/learn_rj/{timestamp}/backup/`
2. **应用编辑**：按用户确认的建议逐条 apply（add/delete/replace）
3. **写 memory**：经 `write_project(task='learn_cycle', content=...)` 记录本次 learn 产出
4. **刷 SUMMARY**：刷新 `{主docs}/SUMMARY_RJ.md`

### 备份规范

```python
# 参考实现
import shutil
backup_dir = os.path.join(staging_dir, 'backup')
os.makedirs(backup_dir, exist_ok=True)
for live_file in affected_files:
    shutil.copy2(live_file, os.path.join(backup_dir, os.path.basename(live_file)))
# 然后才 apply 编辑
```

---

## §6 禁止项【硬性】

learn 建议禁止触及以下核心规则（HARD-GATE 时 agent 必须主动标注"核心规则保护"）：

- ❌ 禁止删除 7 条铁律
- ❌ 禁止删除 HARD-GATE 机制
- ❌ 禁止删除 Memory First 硬规则
- ❌ 禁止删除 No Placeholders 铁律
- ❌ 禁止删除安全不变量
- ❌ 禁止删除 PDCA 4 环结构

**理由**：这些是框架的"协作宪法"，是过去反复踩坑后固化下来的规则。learn 的目的是优化"实现细节"（如重复记忆、死引用、过时规则），不是推翻"核心规则"。

---

## §7 与 某开源项目 的差异说明

| 维度 | 某开源项目 | pdca-skill learn |
|---|---|---|
| 形态 | Python 训练引擎 | markdown 框架 + agent 执行 |
| replay | LLM 重放+评分 | 省略（agent 自身具备语义理解） |
| gate | 自动 held-out 验证 | 人工 HARD-GATE（更安全） |
| API 调用 | 需要（LLM 评分） | 不需要（agent 自身能力） |
| 调度 | nightly cron | /act 步骤3.6 累积量门控自动触发 |
| 作用面 | CLAUDE.md + SKILL.md | memory（memory_main.md + 项目 memory_rj） |

**降维理由**：pdca-skill 的 agent 自身就是 optimizer，不需要额外的 LLM replay 循环；框架规则是"协作宪法"，自动 gate 可能接受破坏性改动，人工 HARD-GATE 更安全。

---

## §8 Phase 5 状态机与回归保护

> Phase 5 在 §1-§7 基础上新增「状态机管理 + 回归检测 + 回滚机制 + manifest 留痕」四件套，防止 learn 闭环把规则改坏。文档对应代码：[scripts/learn_tidy.py](../scripts/learn_tidy.py) 的 `LearnState` 类 / `detect_regression` / `rollback` / `write_manifest` 函数。

### §8.1 LearnState 状态机

learn 流程的状态机管理，防止状态错乱（如未扫描就提建议、未采纳就归档）。

**状态迁移图（单向，不允许回退）**：

```
pending → scanning → proposing → adopting → archived
```

| 状态 | 含义 | 进入条件 |
|------|------|---------|
| pending | 初始状态 | LearnState(task) 构造时 |
| scanning | 扫描中 | 从 pending advance('scanning') |
| proposing | 提建议中 | 从 scanning advance('proposing') |
| adopting | 采纳中 | 从 proposing advance('adopting') |
| archived | 已归档（终态） | 从 adopting advance('archived'),**且 adopted 列表非空** |

**不变量**：
- `adopting → archived` 必须先有 `adopted` 列表（防止空归档）
- `archived` 是终态，不能再迁移
- 跳跃迁移（如 `pending → adopting`）抛 `ValueError`

### §8.2 detect_regression 回归检测

检测 memory_main.md 是否发生规则倒退（已采用的规则被删/被弱化）。

**基线维护规范**：
- 默认基线路径：`{skill_root}/memory/memory_main.md.bak_learn`
- 基线创建时机：每次 adopt 应用建议后，把当前 memory_main.md 复制为 `.bak_learn`（作为下次 learn 的基线）
- 基线不存在时：detect_regression 返回 `regression_count=0 + note='baseline not found'`，不报错

**规则类 section 扩展匹配**（Phase 5 修复）：
- 中文节：`## 硬规则` / `## 关键约定` / `## 长期经验` / `## 不可恢复上下文` / `## 工程约定`
- 英文节：`## Hard Constraints` / `## Engineering Conventions` / `## Lessons Learned` / `## Key Decisions` / `## ADR`
- 匹配多节拼接对比，不限于单一「## 硬规则」节

**判定阈值**：
- 相似度 < 0.3 → `type='deleted'`（规则在基线有但当前完全找不到相似行）
- 相似度 < 0.85 → `type='weakened'`（规则被削弱）
- 相似度 ≥ 0.85 → 不算回归（正常措辞优化）

**返回结构**：
```json
{
  "regression_count": int,
  "regressions": [{"rule_id": "rule_001", "type": "deleted|weakened",
                    "baseline_snippet": "...", "current_snippet": "...",
                    "similarity": 0.42}],
  "baseline_path": str,
  "current_path": str,
  "note": "baseline not found"  // 基线不存在时附加
}
```

### §8.3 rollback 回滚机制

当 detect_regression 检出回归，用户可决定回滚 memory_main.md 到基线版本。

**安全约束**：
- `dry_run=True`（默认）：只输出 unified_diff 预览，不动文件
- `dry_run=False`（用户显式 `--no-dry-run`）：先备份当前为 `{current}.bak_rollback_{timestamp}`，再复制 baseline → current
- 基线不存在时：返回 `{'rolled_back': False, 'error': 'baseline not found'}`

**CLI 用法**：
```bash
# 预览回滚 diff
python scripts/learn_tidy.py rollback --baseline memory/memory_main.md.bak_learn \
                                       --current memory/memory_main.md

# 实际执行回滚（需 --no-dry-run）
python scripts/learn_tidy.py rollback --baseline memory/memory_main.md.bak_learn \
                                       --current memory/memory_main.md --no-dry-run
```

### §8.4 write_manifest 留痕

把 LearnState 序列化为 manifest.json 落盘，便于跨对话追踪 learn 状态。

**双写策略**：
- `manifest_{timestamp}.json`：时间戳版，保留历史（每次新增）
- `manifest_latest.json`：覆盖式，反映最新状态

**输出目录**：默认 `docs_rj/learn_rj/{timestamp}/`，可被 `--output-dir` 覆盖。

### §8.5 3 个新子命令 + scan --phase5 flag

| 子命令 | 功能 | 关键参数 |
|--------|------|----------|
| `rollback` | 回滚 memory_main.md 到基线 | `--baseline` / `--current` / `--dry-run`（BooleanOptionalAction，用 `--no-dry-run` 实际执行） |
| `detect-regression` | 检测规则回归 | `--skill-root` / `--baseline-memory` |
| `write-manifest` | 写 LearnState manifest | `--task` / `--output-dir` / `--state` |
| `scan --phase5` | scan 时附带跑 detect_regression | `--phase5` flag |

**scan --phase5 行为**：跑 scan + detect_regression，若 regression_count>0 输出"建议运行 `rollback --baseline <baseline_path>` 回滚"提示。

### §8.6 触发时机

- **detect-regression**：每次 `/act` A.learn 闭环后跑一次，对比上次 adopt 后的基线
- **rollback**：detect-regression 输出 regression_count>0 时，由用户决定是否回滚（HARD-GATE）
- **write-manifest**：每次 LearnState 状态迁移时自动调用（learn_tidy.py 内部触发）
- **scan --phase5**：用户主动想检查回归时跑

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-15 14:55 | 初版：基于 某开源项目 v0.2.0 设计 learn 6 阶段流程 |
| v1.1 | 2026-07-29 22:30 | learn_into_act 任务：§1 触发时机从"独立询问"改为"/act 步骤3.6 累积量门控自动触发"；§7 调度行同步 |

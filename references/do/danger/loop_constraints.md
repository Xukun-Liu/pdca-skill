<!-- PDCA标签：D.danger -->
<!-- 子标签场景：/do 阶段运行时约束、路径/合并/改动/预算/失败约束 -->
<!-- 关键词清单：constraints/safety/denylist/auto-merge/L2/熔断/stagnation/no_progress -->
<!-- 引用范围：main + loop_agent -->

---
name: loop-constraints
description: >
  pdca-skill 的运行时约束。每次 L2 任务 /do 阶段开始前必须读取并强制执行。
  这些规则是底线，不可被任务目标覆盖。
pdca: D.danger
keywords: [constraints, safety, denylist, auto-merge]
---

> 版本：v1.1.0 | 更新：2026-08-01（新增「/loop 触发词完整规则」节，自 SKILL.md 下沉为唯一维护源）
> 阶段标签：D.danger

# Loop Constraints

## 路径约束
- 不允许自动编辑 `auth/`、`payments/`、`secrets/`、`credentials/`、`infrastructure/`、`migrations/`、`.env`、`.env.*`。
- 不允许自动编辑任何包含 `password`、`token`、`secret`、`key` 字样的文件。

## 合并约束
- 默认 no auto-merge。
- 仅允许文档/注释 typo、import 排序等低风险改动通过 PR，且仍需人工 review。

## 代码改动约束
- 单次 `/do` 改动文件数 ≤5，超过必须拆分或 HARD-GATE。
- 不改无关代码、不做与任务目标无关的重构。
- 必须先跑测试/校验再 mark done。

### denylist 代码检查约定

**强制代码检查**：/loop 模式下，每次改文件前必须调 `loop_guard.py check --denylist-check {path}`。

denylist 路径模式（完整列表，对齐 loop_constraints.md L15-16）：
- 路径段：`auth` / `payments` / `secret`（覆盖 secrets 单复数）/ `credentials` / `infrastructure` / `migrations` / `.env`
  - 使用路径边界匹配：`(^|/)dirname([/.]|$)`，避免误命中 `author.py`/`secretary.py`/`authentication.py`
- 字样：`password` / `token`（用词边界 `\b` 避免误命中 `password_hash.py`/`tokenize.py` 等合法文件）/ `key`（用正则 `(?:\b|[_/.])key\b` 覆盖 `private_key.pem`/`api.key` 等，排除 `keyboard`/`monkey` 误匹配）

命中任一模式 → 立即 escalate，停下问用户。

### 改动文件数代码检查约定

**强制代码检查**：/loop 模式下，每次改文件后必须调 `loop_guard.py check --changed-files-check --root .`。

阈值：>5 个文件 → 立即 escalate，停下问用户。
非 git 仓库：返回 -1 → 立即 escalate（配合 spec §4.1 前置条件 3"必须 git 仓库"）。

统计方式（对齐 `loop_guard.py count_changed_files` 实现）：
- 统计范围：`git diff --name-only`（已跟踪文件的修改/新增/删除，含 staged + unstaged）+ `git ls-files --others --exclude-standard`（未跟踪的 new files）
- 不含：`.gitignore` 排除的文件、已删除文件的 diff 落盘、仅修改权限的文件
- 注意：修改 `outputs_rj/` 等生成目录也计入总数，跨迭代累计

## 失败约束
- 同一 error_signature 连续 3 次 → escalate。
- 任意失败连续 5 次 → escalate。
- 单次任务总迭代 ≥10 次 → escalate。

## 迭代约束

> 借鉴 某开源项目 workflow engine 的 while_loop/do_while step 的 max_iterations 机制。
> 某开源项目 默认 max_iterations=10，显式拒绝 bool（因 Python `isinstance(True, int)` 为 True，`True < 1` 为 False，bool 会绕过 int 校验）。

### max_iterations 配置规则

- **默认值**：10（与现有"单次任务总迭代 ≥10 次 → escalate"一致）
- **可配置**：复杂任务可在 spec.md 里调高（如 15），简单任务可调低（如 5）
- **配置位置**：spec.md front-matter 字段 `max_iterations: 10`（整数）
- **类型严格**：
  - 必须是 int >= 1
  - **显式拒绝 bool**（`isinstance(val, bool)` → 拒绝，因 `True` 会被当作 1）
  - 拒绝字符串（如 `"10"`）、浮点数（如 `10.0`）
- **运行时再次校验**：/do 进入循环前，agent 必须显式读取 spec.md 的 max_iterations 字段并校验类型（不只靠 validate_skill.py 校验）
- **代码层校验**：[scripts/validate_skill.py](../../../scripts/validate_skill.py) 新增 SCR-08，校验 spec/task 模板的 max_iterations 字段是整数非 bool（`isinstance(val, int) and not isinstance(val, bool)`）

### 配置示例

```yaml
# spec.md front-matter
---
title: 复杂任务 - 需求规格说明
version: v1.0.0
max_iterations: 15  # 复杂任务调高（默认 10）
---
```

## 人权约束
- 用户说"停"时立即退出自动循环。
- 任何不确定必须 escalate，禁止猜测。

---

## /loop 触发词完整规则（自 SKILL.md 下沉，唯一维护源）

> SKILL.md「三定位 + PDCA 四环」节仅留核心不变量；本节为 /loop 规则的唯一权威。/do 阶段进入循环前必读。

### 前置条件（全部满足才能启动）
1. /plan 已完成且用户明确确认
2. `python scripts/loop_admission.py .` 退码=0 且 level≥L2（L1=Report-only 不改代码，不进入循环；L0 拒绝）
3. 必须是 git 仓库（`git rev-parse --is-inside-work-tree` 返回 true）——铁律6要求"动手改前必须确保工作区已 commit"，非 git 仓库无回溯保障，拒绝 /loop

### 启动流程
1. Agent 收到 /loop 指令
2. 跑 loop_admission.py 准入检查
3. 不满足前置条件 → 拒绝并告知原因
4. 满足 → 询问模式（自动 auto / 半自动 semi）
5. 用户选模式后进入循环

### 模式定义与选择规则
- **自动模式（auto）**：Agent 自动跑 /do→/check 直到完成或熔断，中间不停
- **半自动模式（semi）**：每次 /do→/check 迭代完成后停下问"继续/调整/停"（task.md 子项 ≠ 迭代号，一次迭代可能处理多个子项）
- level=L2 → 用户选 auto 或 semi；level=L1 → 拒绝 /loop（Report-only 不进循环）；level=L0 → 拒绝 /loop

### 退出条件
- 所有 task.md 项完成 → 进 /act
- 熔断触发（5 条：stagnation/no_progress/max_iter/denylist/改动数）→ 停下问用户
- 用户喊"停" → 立即退出
- /check 输出 ESCALATE → 停下问用户

### 与默认"停下问"的关系（解决 L77 vs L794 矛盾）
/loop 是显式启动开关，覆盖默认"停下问"行为。不喊 /loop 时按 PDCA 4 环默认"停下问"走。

### 无人值守执行阶段规则
- 仅对 L2 任务生效，且在 /plan 得到用户明确确认后才启动。
- 启动后 Agent 自动推进 `/do → /check → /do → /check` 循环，直到完成或触发 escalate。
- 必须停下回到人工的情况：同一 error_signature 连续 3 次（stagnation）；任意失败连续 5 次（no_progress）；单次任务总迭代 ≥10 次；触碰 denylist 路径或改动文件数 >5；用户说"停"。
- **用户喊"停"的检测**（迭代间检查，不破坏"自动模式中间不停"语义）：
  - /loop 自动模式下，每次 /do→/check 迭代结束、准备进下一轮前，Agent 短暂检查对话历史中是否出现"停"/"stop"/"pause"/"中断"关键词
  - 检测到 → 立即退出循环，跑 handoff_tidy 归档 ledger，写 TASK_STATE（loop_status=paused）
  - 不检测到 → 继续下一轮迭代（迭代内不停，符合"自动模式"定义）
  - 下次 /plan 读 TASK_STATE 后用户可再 /loop 继续（loop_iteration 续传）
  - **调用命令**：`python scripts/loop_guard.py stop-check --task-id {task_id} --text "{最近N轮对话文本}"`，退出码 1 = 检测到停止关键词，0 = 未检测到
- 不跨会话：当前对话结束，任务暂停；下次 /plan 读取最新 `TASK_STATE.md` 后由用户决定是否继续。

### Week-one L1 规则
任何新任务类型、新 pattern、新工具接入，第一周必须 L1；稳定运行 ≥1 周并通过 /check 后，才可申请升级到 L2。

### 批次间轻量 Self-Review【硬性】
L2 无人值守模式下分批执行时，每批完成后必须做轻量 Self-Review（4 项检查），不等最后才跑对抗审查：
- **触发条件**：L2 模式 + 分批执行（≥2 批）
- **4 项检查**（每批完成后）：
  1. **占位符扫描**：grep 本批产出是否有 TBD/TODO/适当处理/类似XX/伪代码
  2. **内部一致性**：本批产出与已 commit 的前批产出是否矛盾（如版本号、函数签名、文件路径）
  3. **文档同步**：本批若新增/修改了对外接口（CLI/函数签名/目录结构），是否已同步到 SKILL.md / README.md / references/
  4. **测试覆盖**：本批若新增脚本，是否加了对应测试（pytest test_xxx）
- **原因**：历史执行中曾出现对抗审查才发现 3 个 HIGH（LearnState 文档脱节/rollback argparse BUG/detect_regression 永远返回 0），前几批都没做 Self-Review，问题累积到最后才暴露
- **不等最后才对抗审查**：轻量 Self-Review 是每批的"快速体检"，对抗审查仍是最后的大审查（复杂任务/大改后必做）

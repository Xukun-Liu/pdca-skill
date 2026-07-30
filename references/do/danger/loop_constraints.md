<!-- PDCA标签：D.danger -->
<!-- 子标签场景：/do 阶段运行时约束、路径/合并/改动/预算/失败约束 -->
<!-- 关键词清单：constraints/safety/denylist/auto-merge/L2/熔断/stagnation/no_progress -->
<!-- 引用范围：main + loop_agent -->

---
name: loop-constraints
description: >
  riji-skill 的运行时约束。每次 L2 任务 /do 阶段开始前必须读取并强制执行。
  这些规则是底线，不可被任务目标覆盖。
pdca: D.danger
keywords: [constraints, safety, denylist, auto-merge]
---

> 版本：v1.1.0
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
- **代码层校验**：[scripts/validate_skill.py](../scripts/validate_skill.py) 新增 SCR-08，校验 spec/task 模板的 max_iterations 字段是整数非 bool（`isinstance(val, int) and not isinstance(val, bool)`）

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

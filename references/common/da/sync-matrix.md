<!-- PDCA标签：D.code A.tidy -->
<!-- 子标签场景：同步矩阵/一致性检查 -->
<!-- 关键词清单：同步一下/整理文档/整理一下/更新记忆/梳理一下/收尾/这个阶段做完了/新人能直接上手/检查规范/审计规则/规范体检/交接/里程碑/sync/neat/tidy/版本号一致/一致性检查/清理/打扫/对一下 -->
<!-- 引用范围：main + sync_agent -->

# 变更影响矩阵（Sync Matrix）
> 阶段标签：D · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.1 | 更新：2026-08-06（移除 MIGRATION.md 引用行）

遇到不确定"这次改动要同步哪些文件"时查这张表。**两个方向都要查**：正向（加了什么） + 反向（该从哪些文件删）。

---

## 一、Skill 版本升级

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 版本号升级（v1.0） | SKILL.md（头部版本号+变更摘要注释） | 更新版本号、日期、变更摘要（不再在 SKILL.md 内嵌版本历史表，仅保留指向 HISTORY.md 的引用链接） |
| | HISTORY.md（版本历史，唯一权威来源） | 追加新版本行（版本历史外置到此文件） |
| | evals/evals.json（version字段） | 更新版本号，补新规则测试用例 |
| | references/*.md（版本头，仅当内容有改动时） | 逐一更新 `> 版本：vX.X`（references 有独立版本号，内容没改不升版本） |
| | **git 处置【硬性·v1.0.0 新增】** | **必打 release commit + tag**：`git commit -m "chore(release): v1.0.0"` + `git tag -a release-v1.0.0 -m "..."`，详见 [git_workflow.md §2.10/§5.5](../../do/code/git_workflow.md) |
| 版本号在多个文件出现 | 全局 grep `v\d+\.\d+` 确认版本号一致（重点检查旧版本残留） | 对齐版本号 |
| spec_main_rj.md 版本升级 | docs_rj/spec_main_rj.md frontmatter version | 与 SUMMARY_RJ.md frontmatter + assets/spec_template.md derived_from 字段一致 |
| spec_main_template.md 版本升级 | assets/spec_main_template.md frontmatter version | 实例 spec_main_rj.md based_on 字段一致；如模板结构变更（章节增删），实例需同步 |
| assets/*_template.md frontmatter 新增 skill_version 字段 | 12 个模板（spec/task/handoff/memory/spec_main/summary/...） | frontmatter 加 `skill_version: v1.0.0`（新文档生成时自动带戳，老文档规整后补戳） |

---

## 二、规则文件变更

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 新增 reference 文件 | SKILL.md（触发钩子表+资源索引） | 新增触发钩子行 + 资源索引条目 |
| | 新文件本身 | 写版本头、内容 |
| 删除 reference 文件 | SKILL.md（清除死引用） | 删触发钩子表对应行 + 资源索引条目 |
| | 全局 grep 该文件名 | 清除所有引用 |
| 修改硬性规则 | SKILL.md（对应章节） | 更新规则描述 |
| | 相关 reference | 更新详细说明 |
| | evals/evals.json | 补/改测试用例 |
| 新增触发钩子 | SKILL.md（触发钩子表） | 新增一行 |
| | 对应 reference | 确保触发钩子指向的文件存在 |
| | evals/evals.json | 补测试用例 |
| 删除触发钩子 | SKILL.md（触发钩子表） | 删除对应行 |
| | evals/evals.json | 删除对应测试用例 |

---

## 二·补充：memory 体系变更

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| memory 体系结构变化 | SKILL.md（Memory First 节 + §1 启动检查） | 更新读写规则、归档机制 |
| | references/common/pa/working_memory_rules.md | 更新文件体系、存盘检查点、归档流程 |
| | references/common/pda/document_specs.md | 更新 记忆写入与全局聚合格式 |
| | assets/daily_log_template.md | 改为归档模板 |
| | assets/memory_bootstrap_template.md | 新建/更新 memory/memory_main.md 最小模板 |
| 新增 Bootstrap 机制 | SKILL.md（§1 + 触发钩子表） | 新增 Bootstrap 章节 + 触发钩子行 |
| | references/plan/bootstrap/bootstrap.md | 新建/更新 Bootstrap 规则 |
| | references/common/pa/working_memory_rules.md | 反模式表补"静默创建"条目 |

---

## 三、脚本/工具变更

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 新增脚本 | SKILL.md（资源索引） | 新增脚本说明条目 |
| | 相关 reference | 更新使用说明 |
| | tests/ | 新建测试文件 |
| 修改脚本 | tests/ 对应测试 | 更新测试用例 |
| | 相关 reference | 更新使用说明 |
| 删除脚本 | SKILL.md（清除引用） | 删除资源索引条目 |
| | tests/ | 删除对应测试 |
| | 全局 grep 脚本名 | 清除所有引用 |

---

## 四、文档体系变更

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 新增文档类型 | SKILL.md（§3 文档体系） | 更新三件套速览表 |
| | assets/ 对应模板 | 新建模板文件 |
| | scripts/generate_docs.py | 更新 DOC_TYPES 字典 |
| | evals/evals.json | 补测试用例 |
| 修改模板 | assets/ 对应模板文件 | 更新模板内容 |
| | scripts/generate_docs.py | 确认占位符兼容 |
| 删除文档类型 | SKILL.md（§3） | 清除对应条目 |
| | assets/ | 删除模板 |
| | scripts/generate_docs.py | 更新 DOC_TYPES |

---

## 五、任务完成/交接/里程碑

> 🚀 **交接时自动调用 `python scripts/handoff_tidy.py --task {任务名}`**（期3新增）：交接整理管线自动执行守卫+归档+刷新+漂移检查+外部记忆清理+强制#3→#4同步+五问预跑+sync-matrix核对。详见 [scripts/handoff_tidy.py](../scripts/handoff_tidy.py)。

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 任务完成 | memory/memory_main.md（全局聚合）「关键决策」分区 | 经 write_project 自动 upsert 关键决策+完成状态 |
| | {项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md | 写入即落盘，自动 upsert 全局 memory_main |
| | {主docs}/task_rj/{任务名}_task_YYYYMMDD_HHMM.md | 更新状态为已完成 |
| | {主docs}/handoff_rj/ | 生成交接文档 |
| 任务交接 | {主docs}/handoff_rj/ | 写当前状态、已完成、待办、阻塞项 |
| | {项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md | 记录交接时点 |
| 里程碑 | HISTORY.md（版本历史，外置） | 追加新版本行（不再更新 SKILL.md 版本历史表） |
| | memory/memory_main.md（全局聚合） | 记录里程碑事件 |
| | **git 处置【硬性·v1.0.0 新增】** | **必打 release commit + tag**：`git commit -m "chore(release): v1.0.0"` + `git tag -a release-v1.0.0 -m "..."`，详见 [git_workflow.md §2.10/§5.5](../../do/code/git_workflow.md) |
| 阶段完成 | 按本表"任务完成"执行 | 额外检查：触发钩子表是否完整、引用是否有效 |

---

## 六、死引用清理

| 检查项 | 方法 | 处置 |
|--------|------|------|
| 触发钩子表指向的文件存在吗 | 逐行检查 references/ 路径 → ls 确认 | 不存在→删钩子行或修复路径 |
| SKILL.md 里的链接有效吗 | grep 出所有 `](references/` → ls 确认 | 死链→修复或删除 |
| references/ 里互相引用有效吗 | 逐文件 grep 出链接 → ls 确认 | 死链→修复 |
| evals.json 来源字段对应规则存在吗 | 逐条检查 source 字段 → 确认规则未删除 | 规则已删→删除测试用例 |

---

## 七、版本号一致性

> 这是 pdca-skill 最容易产生不一致的痛点——多处出现版本号，改一处漏一处。

| 出现位置 | 格式示例 | 当前实际版本号 | 检查方法 |
|---------|---------|--------------|---------|
| SKILL.md 文件头 | `<!-- Skill 版本：v1.0` | （手写） | 直接读 |
| HISTORY.md（外置） | `version: v1.0` | （手写） | 直接读 |
| evals/evals.json | `"version": "v1.0"` | （手写） | grep |
| references/do/code/code_rules.md | `> 版本：v1.0` | （手写） | grep `版本：v\d` |
| references/common/dc/communication_rules.md | `> 版本：v1.0` | （手写） | grep `版本：v\d` |
| references/common/dc/debugging.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/design/design_patterns.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/pda/document_specs.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/route/agent_find.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/do/code/git_workflow.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/design/project_structure.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/check/red_flags.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/pc/adversarial_review.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/do/danger/security.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/route/skill_management.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/route/skill_security.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/route/skill_creation.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/pa/working_memory_rules.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/da/sync-matrix.md | `> 版本：v1.0` | （手写） | 直接读 |
| references/plan/bootstrap/bootstrap.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/pa/summary_view.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/common/da/hand-drawn-report.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/plan/route/usage_examples.md | `> 版本：v` | （手写） | grep `版本：v\d` |
| references/do/danger/loop_constraints.md | `> 版本：v1.0` | （手写） | grep `版本：v\d` |
| references/plan/route/loop_triage.md | `> 版本：v1.0` | （手写） | grep `版本：v\d` |
| references/check/loop_verifier.md | `> 版本：v1.0` | （手写） | grep `版本：v\d` |

**版本号升级时的一条命令检查**：
```bash
# 检查新版本号已全线更新
grep -rn "v1\.0\.0" references/ SKILL.md HISTORY.md evals/ --include="*.md" --include="*.json"

# 检查老版本号残留（仅 HISTORY.md 版本历史行和 sync-matrix 说明文本中合法，其他文件不应有）
grep -rn "v0\.9" references/ SKILL.md HISTORY.md evals/ --include="*.md" --include="*.json"
```
升级后全线替换为 `v1.0`，不再有残留旧版本号（注意：references 文件有自己的独立版本号如 v1.0/v2.1，不随 SKILL.md 版本号变，只更新内容时才升自己的版本号；HISTORY.md 的历史版本行保留旧版本号是合法的）。

**🔴 版本号升级完成后必须打 release commit + tag【硬性·v1.0.0 新增】**：
```bash
# 1. 打 release commit（详见 git_workflow.md §2.10）
git commit -m "chore(release): v1.0.0

Refs: {触发版本号升级的任务名}"

# 2. 打 release tag（详见 git_workflow.md §5.5）
git tag -a release-v1.0.0 -m "Release v1.0.0: 一句话说明本次版本变更"
```
- tag 格式固定 `release-v{X.Y.Z}`（带 `release-` 前缀避免与分支名冲突）
- commit_lint.py R10 自动校验 `chore(release):` 的 subject 格式，不合规阻断提交
- 边界情况（版本号回滚/未真正升级）处理见 git_workflow.md §2.10

---

## 七.5、commit_lint 脚本可执行性校验（v1.1 新增）

> 新增 commit message 校验脚本后，sync-matrix 增加 3 项可执行性校验。

| 校验项 | 校验方式 | 期望结果 |
|--------|---------|---------|
| commit_lint.py 可执行 | `python scripts/commit_lint.py lint "feat(test): valid" --json` | exit_code=0, passed=true |
| commit_lint_install.py 可执行 | `python scripts/commit_lint_install.py status --json` | 输出 JSON 含 is_git_repo 字段 |
| git_workflow.md §2.4-§2.9 存在 | `grep "§2.4 原子提交" references/do/code/git_workflow.md` | 命中 1 行 |

**一条命令校验**：
```bash
python scripts/commit_lint.py lint "feat(test): valid" --json | grep -q '"exit_code": 0' && echo "commit_lint OK" || echo "commit_lint FAIL"
python scripts/commit_lint_install.py status --json | grep -q "is_git_repo" && echo "install OK" || echo "install FAIL"
grep -q "§2.4 原子提交" references/do/code/git_workflow.md && echo "doc OK" || echo "doc FAIL"
```

---

## 八、汇总视图同步（SUMMARY_RJ.md）

| 变更类型 | 必须同步的文件 | 处置 |
|---------|--------------|------|
| 新增文档（spec_rj/task_rj/handoff_rj/archive_rj） | {主docs}/SUMMARY_RJ.md | 在对应 section 新增条目（链接 + 一句话描述） |
| 删除文档 | {主docs}/SUMMARY_RJ.md | 删除对应条目 |
| 文档重命名/移动 | {主docs}/SUMMARY_RJ.md | 更新链接路径 |
| 任务完成 | {主docs}/SUMMARY_RJ.md | 刷新对应条目的一句话描述（标注完成状态） |
| 任务交接 | {主docs}/SUMMARY_RJ.md | 刷新 handoff section + 更新 last_updated |
| 版本号升级 | {主docs}/SUMMARY_RJ.md（frontmatter version） | 同步版本号 |
| SUMMARY 更新后 | {主docs}/SUMMARY_RJ.md | 跑漂移检查（grep `]\(` → ls 确认 → 同步 total_docs） |

**三触发硬性**（任一触发都必须刷新 SUMMARY）：
1. 启动检查时（SUMMARY 不存在则创建）
2. 对话结束（记忆写入落盘）后刷新
3. 交接时（生成交接文档后刷新）

---

## 九、loop reference 文件索引

> 2026-07-16 新增：loop-engineering 融合引入的 3 个 reference 文件，及其 PDCA 标签、加载时机、关键词、需同步的引用源。

| reference 文件 | PDCA 标签 | 加载时机 | 关键词 | 需同步的引用源 |
|----------------|-----------|----------|--------|----------------|
| loop_constraints.md | D.danger | /do 阶段前加载 | constraints, safety, denylist | SKILL.md §6 /do 解锁声明、trigger_hooks.md L2 /do 行前 |
| loop_triage.md | P.route | /plan 阶段加载 | triage, priority, plan | SKILL.md §6 /plan 步骤、trigger_hooks.md /plan triage 行 |
| loop_verifier.md | C.verify | /check 阶段加载 | verify, check, reject | SKILL.md §6 /check 默认立场、trigger_hooks.md /check 验证行 |

**同步规则**：
- 新增/修改 loop reference 文件 → 同步检查 SKILL.md 脊柱模型索引表 + trigger_hooks.md 对应行 + 本索引表。
- 新增 loop 相关失败模式 → 同步更新 references/check/red_flags.md §4 + references/common/pc/acceptance_criteria.md L1/L2 验收标准。

---

## 使用方式

**触发时机**：任务完成、交接、里程碑、收尾、同步时，按本表逐项核对。

**执行顺序**：
1. 先做"正向"：本次改了什么 → 查表 → 改对应文件
2. 再做"反向"：全局 grep 被改/被删的关键词 → 清残留引用
3. 最后做"版本号一致性"：grep 版本号确认无残留

**不确定时**：列出来问你，不要自己假设。
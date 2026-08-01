<!-- PDCA标签：D.code -->
<!-- 子标签场景：Git 操作 -->
<!-- 关键词清单：Git/提交/commit/分支/branch/push/PR/merge/合并/打tag/发版/回滚/回溯/恢复/还原/改坏了/撤销/undo/rollback/revert/回到之前/紧急回滚/代码改错了 -->
<!-- 引用范围：main + code_eng_agent -->

# Git 工作流与代码审查
> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-10

> 📖 **什么时候读这个文件**：
> - 需要创建Git提交/分支时
> - 需要进行代码审查时
> - 需要制定分支策略时
> - 需要规范commit消息时
> 🔴 **不要在这时候读**：
> - 简单的文件修改，直接提交即可

---

## 第一章：分支策略

### 1.1 Git Flow（适合大型项目）

**分支类型**

| 分支 | 命名格式 | 用途 | 生命周期 |
|------|----------|------|----------|
| main | `main` | 生产环境代码 | 永久 |
| develop | `develop` | 开发整合分支 | 永久 |
| feature | `feature/{功能名}` | 新功能开发 | 临时 |
| release | `release/{版本号}` | 版本发布准备 | 临时 |
| hotfix | `hotfix/{版本号}` | 紧急修复 | 临时 |

**工作流程**

```
main          ────●──────●──────●──────
                  │      │      │
develop        ───┼──────┼──────┼──────●──────●──────
                  │      │      │      │      │
feature/user    ──●──────●──────┘      │      │
                  │                    │      │
feature/payment  ─────────────────────●──────┘
                                      │
release/1.0      ─────────────────────────────●──────●───┘
                                              │
hotfix/1.0.1    ──────────────────────────────●──────
```

**操作步骤**

```bash
# 创建feature分支
git checkout develop
git checkout -b feature/user-auth

# 开发完成后合并到develop
git checkout develop
git merge --no-ff feature/user-auth
git branch -d feature/user-auth

# 创建release分支
git checkout develop
git checkout -b release/1.0

# 发布到main
git checkout main
git merge --no-ff release/1.0
git tag -a v1.0 -m "Version 1.0"

# 同步回develop
git checkout develop
git merge --no-ff release/1.0
git branch -d release/1.0

# 创建hotfix分支
git checkout main
git checkout -b hotfix/1.0.1

# 修复完成后合并到main和develop
git checkout main
git merge --no-ff hotfix/1.0.1
git tag -a v1.0.1 -m "Version 1.0.1"

git checkout develop
git merge --no-ff hotfix/1.0.1
git branch -d hotfix/1.0.1
```

### 1.2 Trunk Based Development（适合小型项目/快速迭代）

**核心原则**

- 所有开发都在 `main` 分支上进行
- 频繁提交（每天多次）
- 使用短生命周期的 feature 分支
- 自动测试和持续集成

**工作流程**

```
main          ───●──●──●──●──●──●──●──●──●──●──
                  │  │  │  │  │
feature/a       ──●──┘  │  │  │
                  │     │  │  │
feature/b       ────────●──┘  │
                  │          │
feature/c       ─────────────●──┘
```

**操作步骤**

```bash
# 创建feature分支（从main）
git checkout main
git checkout -b feature/a

# 开发并频繁提交
git add .
git commit -m "feat: implement feature A part 1"
git add .
git commit -m "feat: implement feature A part 2"

# 定期同步main更新
git checkout main
git pull origin main
git checkout feature/a
git merge main

# 开发完成后合并到main
git checkout main
git merge feature/a
git branch -d feature/a
git push origin main
```

### 1.3 选择建议

| 项目类型 | 推荐策略 | 原因 |
|----------|----------|------|
| 大型企业项目 | Git Flow | 严格的版本管理，适合多版本并行开发 |
| 小型创业项目 | Trunk Based | 快速迭代，简化流程 |
| 开源项目 | Trunk Based | 社区贡献者友好，简化协作 |
| AI Agent 项目 | Trunk Based | 快速实验和迭代 |

---

## 第二章：Commit 规范

### 2.1 Conventional Commits

**格式**

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Type 分类**

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(api): add user registration endpoint` |
| `fix` | Bug修复 | `fix(database): resolve connection leak` |
| `docs` | 文档修改 | `docs(readme): update installation instructions` |
| `style` | 代码格式 | `style: format code with black` |
| `refactor` | 重构 | `refactor(service): extract helper functions` |
| `test` | 测试 | `test(api): add unit tests for login endpoint` |
| `chore` | 构建/工具 | `chore(deps): bump requests to v2.31.0` |
| `perf` | 性能优化 | `perf: optimize database query` |
| `ci` | CI/CD配置 | `ci: add GitHub Actions workflow` |
| `revert` | 回滚 | `revert: revert "feat: add new feature"` |

**Scope 建议**

| Scope | 说明 |
|-------|------|
| `api` | API层 |
| `core` | 核心逻辑 |
| `database` | 数据库相关 |
| `ui` | 用户界面 |
| `config` | 配置文件 |
| `utils` | 工具函数 |
| `tests` | 测试代码 |

### 2.2 示例

**简单提交**
```
feat(api): add user registration endpoint
```

**带body的提交**
```
feat(api): add user registration endpoint

- Implement POST /api/users endpoint
- Add email validation using marshmallow
- Password hashing with bcrypt

Closes #123
```

**带footer的提交**
```
fix(database): resolve connection leak

The connection pool was not being properly closed after requests,
causing memory leaks over time.

BREAKING CHANGE: The database connection string format has changed.
```

### 2.3 编写规则

| 规则 | 说明 |
|------|------|
| 标题不超过 50 字符 | 确保在 GitHub 上完整显示 |
| 使用祈使句 | `add` 而非 `added` 或 `adds` |
| 标题结尾不加句号 | 简洁为主 |
| body 使用 Markdown | 可以使用列表、链接等 |
| 引用 Issue | 使用 `Closes #123` 或 `Fixes #123` |

---

### 2.4 原子提交原则（Atomic Commit）【硬性】

> 每次提交只做一件事，能独立编译/运行/测试。业界黄金法则。

**规则**：
- 一个 commit = 一个逻辑变更（一个功能点 / 一个 bug 修复 / 一个重构）
- 禁止一个 commit 混杂多类型变更（如既加功能又改 bug 又改样式）
- 用 `git add -p` 分块暂存，把相关改动单独提交

**判断标准**：commit message 能用一句话说清做了什么 = 粒度合适；要写"和"连接多个变更 = 粒度太大，拆分。

**反例**：
```
fix: 修复登录问题，添加用户头像，顺便优化数据库查询
```
↑ 3 件事混在一起，回滚困难。应拆成 3 个 commit。

**正例**：
```
fix(auth): resolve token expiration check error

Refs: t07_user_auth_20260724
```

---

### 2.5 commit 关联任务名（Refs footer）【硬性】

> 框架用任务名做跨文件 key（见 SKILL.md §0.6），commit 必须关联任务名，跨对话恢复时 `git log --grep {task_name}` 可反查。

**格式**：在 commit message footer 加 `Refs: {task_name}`

**示例**：
```
feat(api): add user registration endpoint

- Implement POST /api/users endpoint
- Add email validation

Refs: t07_user_auth_20260724
```

**规则**：
- task_name 必须与 `docs_rj/spec_rj/{task}_spec_*.md` / `docs_rj/task_rj/{task}_task_*.md` 文件名前缀一致
- task_name 格式：`[a-z][a-z0-9_]*`（对齐 §0.6 任务名规范）
- 简单任务（无 spec/task 文件）可省略，但 WIP commit 必须带（见 §2.7）

---

### 2.6 框架文件单独 commit【硬性】

> spec/task/memory 文档与业务代码分开提交，避免回滚代码连带回滚文档。

**规则**：
- `docs_rj/` 下文件（spec/task/memory/handoff）单独 commit，type 用 `docs`
- 代码改动单独 commit，type 用 `feat`/`fix`/`refactor` 等
- 禁止 `git add .` 一次性提交文档+代码混合改动

**示例**：
```
# ✅ 正确：分两次提交
git add docs_rj/spec_rj/t07_user_auth_spec_20260724_1030.md
git commit -m "docs(spec): add user auth spec

Refs: t07_user_auth_20260724"

git add src/api/users.py
git commit -m "feat(api): add user registration endpoint

Refs: t07_user_auth_20260724"

# ❌ 错误：混合提交
git add .
git commit -m "feat: add user auth"
```

---

### 2.7 WIP commit 格式【硬性】

> 铁律6 要求"动手改前工作区已 commit"，复杂任务中途用 WIP commit 保障回溯点。WIP 格式必须统一，便于识别和后续清理。

**格式**：`chore(wip): {task_name} {简述}`

**示例**：
```
chore(wip): t07_user_auth_20260724 implement JWT validation halfway
```

**规则**：
- type 固定 `chore`，scope 固定 `wip`
- 必须带 task_name（对齐 §2.5）
- 简述用一句话说明做到哪一步
- WIP commit 在任务完成后建议用 `git rebase -i` 清理（见 §5.3）

---

### 2.8 /do 阶段 commit 时机【硬性】

> 铁律7 要求"逐项核对，完成一个打勾一个"。commit 时机对齐 task.md 子项粒度。

**规则**：每完成一个 task.md 子项 → commit 一次（Verification-before-Completion 之后）

**执行顺序**【硬性】：
1. 按 task.md 子项执行改动
2. 跑验证步骤，看到预期结果
3. 打勾标记完成
4. **commit**（用规范格式 + Refs footer）
5. 进下一个子项

**禁止**：
- ❌ 多个子项改动攒一起 commit（回溯断链，违反铁律6 精神）
- ❌ 子项未验证就 commit（违反 Verification-before-Completion）

---

### 2.9 自动校验（commit_lint.py）【硬性】

> 框架提供纯 Python 校验脚本 `scripts/commit_lint.py`，对齐 Conventional Commits + 框架规范。可通过 `scripts/commit_lint_install.py` 安装 git hook 自动拦截不合规提交。

**校验规则**（9 条）：

| 规则 | 严重度 | 说明 |
|------|--------|------|
| R1 type 在 VALID_TYPES | ERROR | Conventional Commits 强制 |
| R2 subject ≤50 字符 | WARNING | 业界惯例 |
| R3 subject 祈使句 | WARNING | 检测 -ed 结尾（过去式） |
| R4 subject 不加句号 | WARNING | 业界惯例 |
| R5 body 每行 ≤72 字符 | WARNING | 业界惯例 |
| R6 WIP 必须 chore(wip): | ERROR | 对齐 §2.7 |
| R7 Refs task_name 格式 | ERROR | 对齐 §0.6 |
| R8 混合改动检测 | WARNING | 对齐 §2.6 |
| R9 BREAKING CHANGE 格式 | ERROR | Conventional Commits 强制 |

**退出码**：0=通过, 1=WARNING（不阻断）, 2=ERROR（阻断提交）

**使用方式**：
```bash
# 单条校验
python scripts/commit_lint.py lint "feat(api): add endpoint

Refs: t07_user_auth_20260724"

# 从文件校验（commit-msg hook 调用）
python scripts/commit_lint.py lint-file .git/COMMIT_EDITMSG --json

# 校验最近 5 条 commit
python scripts/commit_lint.py check-last --n 5

# 安装 git hook
python scripts/commit_lint_install.py install

# 检查 hook 状态
python scripts/commit_lint_install.py status
```

---

### 2.10 release commit 规范【硬性·v1.0.0 新增】

> 版本号升级时必须打 release commit，配合 §5.5 release tag 形成可追溯发版历史。
> 触发时机：仅当 SKILL.md 头部版本号 + HISTORY.md + evals/evals.json 同步升级时（详见 [sync-matrix.md §一/§七](../../common/da/sync-matrix.md)）。

**格式**：

```
chore(release): v{X.Y.Z}

[可选 body：本次版本变更摘要]

Refs: {task_name}
```

**规则**：
- type 固定 `chore`，scope 固定 `release`
- subject 必须是版本号 `v{X.Y.Z}`（X/Y/Z 均为数字，对齐 semver 语义化版本）
- Refs footer 必填，关联触发版本号升级的任务名（对齐 §2.5）
- 一个版本号升级 = 一个 release commit（禁止批量升级合并提交，对齐 §2.4 原子提交）

**示例**：

```
chore(release): v1.0.0

- 升级 SKILL.md 头部版本号至 v1.0.0
- 同步 HISTORY.md / evals.json / 各 references 版本号
- 完成 references/ 目录 PDCA 重构

Refs: release_git_tag_sync_20260725
```

**R10 自动校验**：commit_lint.py R10 规则自动校验 `chore(release):` 的 subject 格式（必须匹配 `^v\d+\.\d+\.\d+$`），不合规阻断提交（详见 [commit_lint.py](../../../scripts/commit_lint.py)）。

**边界情况**：
- **版本号回滚**（如 v1.0.1 → v1.0.0）→ 不打新 release commit，仅在 HISTORY.md 记录回滚原因
- **版本号未真正升级**（仅文字修改/格式调整）→ 不打 release commit，用普通 `docs:` 类型即可
- **tag 已存在**（详见 §5.5 边界处理）

**与 §2.6 框架文件单独 commit 的关系**：release commit 是例外——它聚合本次版本号升级涉及的所有文件变更（SKILL.md + HISTORY.md + evals.json + references/*）成一个 commit，因为这些都是同一逻辑变更（版本号升级），符合 §2.4 原子提交"一个逻辑变更一个 commit"。

---

## 第三章：代码审查清单

### 3.1 功能正确性

- [ ] 代码是否实现了需求描述的功能
- [ ] 边界条件是否处理（空值、边界值、异常情况）
- [ ] 错误处理是否完善（异常捕获、错误日志、降级策略）
- [ ] 测试用例是否覆盖主要场景
- [ ] 是否有未处理的边缘情况

### 3.2 代码质量

- [ ] 函数/方法是否单一职责（一个函数只做一件事）
- [ ] 代码是否有重复（DRY 原则）
- [ ] 变量命名是否清晰（见名知意）
- [ ] 函数参数是否合理（参数数量、类型）
- [ ] 代码复杂度是否过高（圈复杂度）
- [ ] 是否有魔法数字或硬编码
- [ ] 是否有注释掉的代码
- [ ] 是否有TODO/FIXME标记

### 3.3 安全性

- [ ] 输入是否验证（防止注入攻击）
- [ ] 敏感数据是否保护（密码、Token、API Key）
- [ ] 是否有SQL注入风险
- [ ] 是否有XSS风险
- [ ] 是否有CSRF风险
- [ ] 权限控制是否完善
- [ ] 依赖是否有安全漏洞

### 3.4 性能

- [ ] 是否有不必要的循环或重复计算
- [ ] 是否有N+1查询问题
- [ ] 是否有内存泄漏风险
- [ ] 是否使用了合适的数据结构
- [ ] 是否有缓存策略
- [ ] 是否有并发问题

### 3.5 可维护性

- [ ] 代码是否符合项目风格规范
- [ ] 是否有足够的文档和注释
- [ ] 是否遵循项目的目录结构
- [ ] 是否有适当的日志记录
- [ ] 是否有错误处理机制
- [ ] 是否有监控指标

### 3.6 测试覆盖

- [ ] 是否有单元测试
- [ ] 是否有集成测试
- [ ] 测试是否通过
- [ ] 测试覆盖率是否达标
- [ ] 测试命名是否规范
- [ ] 是否有Mock外部依赖

---

## 第四章：代码审查流程

### 4.1 创建 Pull Request

```bash
# 推送分支到远程
git push origin feature/my-feature

# 创建 Pull Request
# 使用 gh CLI
gh pr create --title "feat: add my feature" --body "Description of changes"
```

### 4.2 审查步骤

1. **初步检查**：查看 PR 标题、描述、关联的 Issue
2. **代码浏览**：通读代码，理解整体逻辑
3. **详细审查**：逐文件、逐函数审查，使用审查清单
4. **测试验证**：运行测试，验证功能正确性
5. **反馈**：提出具体的改进建议

### 4.3 反馈规范

**正面反馈**
- ✅ 代码结构清晰
- ✅ 测试覆盖全面
- ✅ 命名规范

**改进建议**
- 💡 建议将这个函数拆分为两个函数
- 💡 可以添加单元测试覆盖这个场景
- 💡 这里可以使用策略模式简化

**需要修改**
- ❌ 这个变量命名不够清晰
- ❌ 缺少错误处理
- ❌ 存在安全风险

### 4.4 合并规则

- [ ] 至少一个人批准
- [ ] 所有测试通过
- [ ] 没有待解决的评论
- [ ] 符合项目代码风格
- [ ] 使用 Squash Merge 保持提交历史清晰

---

## 第五章：Git 最佳实践

### 5.1 提交频率

| 频率 | 场景 |
|------|------|
| 每天多次 | 日常开发，小步提交 |
| 每次功能完成 | 简单任务 |
| 每个逻辑块 | 复杂功能，按模块提交 |

### 5.2 分支管理

- 删除已合并的分支
- 定期清理本地分支
- 使用描述性的分支名称
- 分支生命周期尽量短

### 5.3 冲突解决

- 定期从主分支拉取更新
- 在本地解决冲突后再推送
- 优先使用 rebase 保持线性历史

### 5.4 标签管理

```bash
# 创建标签
git tag -a v1.0 -m "Version 1.0"

# 推送标签
git push origin v1.0

# 删除标签
git tag -d v1.0
git push origin :v1.0
```

---

### 5.5 release tag 规范【硬性·v1.0.0 新增】

> 版本号升级时配合 §2.10 release commit 打 tag，建立可追溯发版历史。
> 触发时机：与 §2.10 release commit 同步，每个 release commit 必打一个 release tag。

**tag 命名格式**：`release-v{X.Y.Z}`

- 带 `release-` 前缀，避免与分支名（如 `release/1.0`、`v1.0`）冲突
- `{X.Y.Z}` 必须与 release commit 的 subject 一致（如 commit subject 是 `v1.0.0`，tag 就是 `release-v1.0.0`）
- 使用 annotated tag（`git tag -a`），不用 lightweight tag（带 message 便于 `git show` 查看版本说明）

**操作命令**：

```bash
# 1. 先打 release commit（见 §2.10）
git commit -m "chore(release): v1.0.0

Refs: release_git_tag_sync_20260725"

# 2. 打 release tag（annotated，必带 -m message）
git tag -a release-v1.0.0 -m "Release v1.0.0: 版本号升级 + references PDCA 重构"

# 3. 推送 tag 到远程（可选，本地仓库可跳过）
git push origin release-v1.0.0
```

**查询版本**：

```bash
# 列出所有 release tag（按版本号排序）
git tag -l "release-v*" --sort=-v:refname

# 查看某版本详情（含 tag message + 关联 commit）
git show release-v1.0.0

# 反查 release commit（在 commit log 中搜索）
git log --grep "chore(release)" --oneline

# 查看当前仓库对应的最近 release 版本
git describe --tags --match "release-v*" --abbrev=0
```

**边界情况处理**：

- **tag 已存在**：
  - 优先：`git tag -d release-v1.0.0` 删除后重打（保留干净历史）
  - 备选：`git tag -f -a release-v1.0.0 -m "..."` 强制覆盖（仅在确认覆盖时使用，会丢失原 tag 信息）
  - 推送到远程时如已存在：`git push origin :release-v1.0.0` 删除远程后重推，或 `git push origin -f release-v1.0.0` 强制覆盖
- **版本号回滚**：不打新 tag，记录到 HISTORY.md；旧 tag 保留不删（避免污染 tag 历史，回滚后的版本号不重复打 tag）
- **打错 tag**：立即 `git tag -d release-v{X.Y.Z}` 删除本地 + `git push origin :release-v{X.Y.Z}` 删除远程，避免污染 tag 历史

**与 §5.4 通用标签管理的关系**：§5.4 是通用标签管理操作（创建/推送/删除）；§5.5 是 release 专用规范，命名格式（`release-v{X.Y.Z}`）和操作流程（必打 annotated tag + 必带 message）更严格。日常开发用 §5.4，版本号升级用 §5.5。

---

## 第六章：回溯保障【硬性】

> 新增。目标：保证改错了能回到改前状态，任务中断能回到稳定点，线上事故能紧急回滚。

### 6.1 代码改动前检查点（场景B）

**规则**：AI 动手改代码/文件前，必须确保当前工作区是干净的（已 commit）

**执行顺序**【硬性】：HARD-GATE 确认方案 → commit 确保工作区干净 → 记录回溯点 → 动手改。不可颠倒（先 commit 再 HARD-GATE 会导致方案被否决后多了无意义 commit；先改再 commit 会丢失回溯点）。

**检查流程**【硬性】：
1. 改动前先 `git status` 确认工作区状态
2. 如有未提交改动 → 按以下优先级处理：
   - 改动是本次任务的 → 先 commit（哪怕只是 WIP commit）
   - 改动是其他任务的/不确定来源 → `git stash` 暂存，或询问你"工作区有未提交改动（列出文件），是先 commit、stash 还是放弃？"
3. 记录当前 commit hash（`git rev-parse HEAD`）作为回溯点
4. 开始改动
5. 改动后如需回溯：`git reset --hard <回溯点hash>`

**禁止**【硬性】：
- ❌ 在未 commit 的工作区上直接改（改错了无法回溯）
- ❌ 改完再 commit 却忘了改前状态（丢失回溯点）

**只读操作边界**：以下操作不修改任何文件，不需要检查点——`grep/read/ls/git status/git diff/git log/git show/git blame`。但凡会创建/修改/删除文件的操作（write/edit/mkdir/rm/git add/git commit/git checkout <file>）都必须先过检查点。

**非 Git 项目降级**：若项目未用 Git 管理（无 .git 目录），用文件备份替代 commit 检查点：
1. 改动前把要改的文件复制一份（`cp file.md file.md.bak`）或用 zip 快照整个目录
2. 记录备份路径作为回溯点
3. 改动后如需回溯：从备份恢复
4. 询问你是否需要初始化 Git 仓库以便获得完整回溯能力

### 6.2 任务级回溯检查点（场景C）

**规则**：复杂任务在关键节点必须打 tag

| 节点 | tag 命名格式 | 示例 |
|------|-------------|------|
| 任务启动 | `task/{任务名}/start` | `task/auth/start` |
| 阶段完成 | `task/{任务名}/{阶段名}-done` | `task/auth/spec-done` |
| 验收通过 | `task/{任务名}/verified` | `task/auth/verified` |

**tag 命名约束**【硬性】：任务名只允许 `[a-z][a-z0-9_-]*` 格式（小写字母开头+小写字母/数字/下划线/连字符）。中文/空格/大写字母需先转换（如"用户认证"→`user-auth`，"Auth System"→`auth-system`）。Git tag 不允许部分特殊字符（`: ? * [ ]`等），用 `_` 或 `-` 替代。

**回溯到稳定点**：
```bash
# 任务改到一半出问题，回到阶段完成点
git reset --hard task/auth/spec-done
```

### 6.3 紧急回滚 SOP（场景D）

**决策树**：根据场景选对工具

```
出问题了
│
├─ 还没 commit？
│   └─ git checkout -- <文件>  # 丢弃工作区改动
│
├─ 已 commit 但还没 push？
│   └─ git reset --hard HEAD~1  # 回到上一个 commit
│
├─ 已 push 到远程？
│   └─ git revert <commit>      # 用新 commit 撤销（安全，不改写历史）
│
└─ 任务改到一半出问题？
    └─ git reset --hard task/{任务名}/{阶段名}-done  # 回到稳定点（见6.2）
```

**禁止**【硬性】：
- ❌ 已 push 到共享分支的 commit 用 `git reset --hard`（改写共享历史，坑队友）
- ❌ 不确认 hash 就 reset（reset 错了丢更多）
- ❌ `git push --force` 到 main/master（见 SKILL.md Git Safety Protocol）

**自己分支 vs 共享分支区分**：
- **自己分支**（本地 feature 分支，未 push 或 push 后无人拉取）：可以用 `git reset --hard` 回溯，安全
- **共享分支**（main/develop/已有人协作的 feature 分支）：禁止 `git reset --hard`，只能用 `git revert` 创建新 commit 撤销
- **判断标准**：`git branch -r --contains <commit>` 有输出说明该 commit 已在远程分支 → 视为共享，只能 revert；无输出说明只在本地 → 可以 reset

**恢复误删**：
```bash
# 误删了 commit？用 reflog 找回
git reflog
git reset --hard HEAD@{N}  # N 是 reflog 里的序号
```

### 6.4 任务收尾 commit（场景E）【硬性】

> 新增。目标：任务完成后确保工作区干净，交接/启动时无未提交改动残留。与 6.1（改前 commit）互补，形成"改前+改后"双重回溯保障。

**规则**：/act 阶段最后（步骤5），必须 git status 检测工作区，有未提交改动则 commit

**执行顺序**【硬性】：/act 步骤1-4.1 完成 → git status 检测 → 有改动则构造消息+校验+用户确认+commit → /act 完成

**执行流程**【硬性】：
1. `git status` 检测工作区
   - 无改动 → 跳过，记录"工作区干净"
   - 有改动 → 进 2
2. agent 构造 commit 消息（基于 task 名 + 改动类型）：
   - type：根据改动判断（feat/fix/docs/chore/refactor...）
   - scope：根据改动模块（api/core/docs/handoff...）
   - subject：基于 task 名 + 改动摘要（≤50字符）
   - body：列出主要改动点
   - `Refs: {task_name}` footer（对齐 SKILL.md §0.6 任务名关联）
3. 调 `python scripts/commit_lint.py lint "{消息}" --task {task_name}` 校验
   - 校验通过（exit_code=0/1）→ 进 4
   - 校验不通过（exit_code=2）→ agent 修消息 → 重校验（max 3次）→ 通过后进 4
4. HARD-GATE：呈现 commit 消息给用户确认
   - 用户确认 → `git add -u` + `git commit`（-u 只 add 已跟踪文件改动，不 add 新文件）
   - 用户改消息 → 用用户的消息重校验+commit
   - 用户说跳过 → 记录到 memory"用户跳过 /act commit"

**非 Git 项目降级**：若项目未用 Git 管理，跳过本步，告警"非 git 仓库，建议初始化"。

**与 6.1 的关系**：
- 6.1（改前 commit）= 保证改前有回溯点，改错了能回到改前状态
- 6.4（改后 commit）= 保证改后工作区干净，交接/启动无残留
- 两者互补：6.1 是"安全网"，6.4 是"收尾归档"

**禁止**【硬性】：
- ❌ /act 结束时不 commit 留下脏工作区（交接/启动会告警）
- ❌ 跳过 commit_lint 校验直接 commit（消息可能不合规）
- ❌ 不经用户确认直接 commit（违反 HARD-GATE）

### 6.5 任务启动 Git 管理询问（场景A）【硬性·复杂任务】

> 新增。目标：复杂任务启动时先问清 git 管理偏好（在哪干活、脏工作区怎么处理），避免 agent 猜分支/commit 节奏；简单任务只做轻量检查不啰嗦。与 6.1（改前 commit）、6.2（任务级 tag）、6.4（收尾 commit）配合，形成"启动问清 → 改前检查 → 节点标记 → 收尾归档"完整闭环。

**触发时机**【硬性】：/plan 步骤3 需求澄清阶段（与 BRD 5 问并行）。复杂任务必问 2 问 + 确认 3 默认值；简单任务只做轻量 git status 检查（工作区干净直接过，脏则问一句 commit/stash/放弃）。回答写入 spec §0.G，/do 期间按约定执行不再重复问。

**2 问 + 3 默认值**：

| 项 | 内容 | 处理流程 |
|----|------|----------|
| **Q1** 工作区状态 | `git status` 有未提交改动 | 问"commit / stash / 放弃"：commit=本次任务改动先存档（哪怕 WIP）；stash=其他任务或不确定来源先挪开；放弃=明确不要了。回答后按 §6.1 执行 |
| **Q2** 分支策略 | 当前分支直接改 or 新建 feature 分支 | 个人项目可当前分支直接改；协作/发布项目建议 feature 分支。回答后按 §3 分支策略执行 |
| **D1** git init | 非 git 仓库时 | 自动问一句"要初始化 git 吗"。否 → 文件备份降级（§6.1 非 Git 项目降级）+ /loop 不可用 |
| **D2** WIP commit | 默认允许 | 每完成一个 task 子项存一次档（格式见 §2.7），方便随时退回 |
| **D3** 任务 tag | 默认打 | 任务开始 `task/{任务名}/start` + 验收通过 `task/{任务名}/verified`（见 §6.2） |

**收尾 commit 不变**：/act 步骤5 收尾 commit（§6.4）仍走 HARD-GATE 确认，不受默认值影响。

**禁止**【硬性】：
- ❌ 复杂任务跳过 2 问直接动手（违反 HARD-GATE + 铁律6 精神）
- ❌ 简单任务把 2 问全问一遍（啰嗦，违反轻量原则）

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-08 | 初版，收录分支策略（Git Flow/Trunk Based）、Commit规范（Conventional Commits）、代码审查清单、代码审查流程、Git最佳实践 |
| v1.1 | 2026-07-24 | 新增 §2.4-§2.9：原子提交原则、commit 关联任务名（Refs footer）、框架文件单独 commit、WIP commit 格式、/do 阶段 commit 时机、自动校验（commit_lint.py）|
| v1.2 | 2026-07-29 | §6 新增 6.4 任务收尾 commit（场景E），与 6.1 改前 commit 互补，形成"改前+改后"双重回溯保障；对齐 SKILL.md /act 步骤5 |
| v1.3 | 2026-08-01 | §6 新增 6.5 任务启动 Git 管理询问（场景A）：复杂任务必问 2 问（工作区状态/分支策略）+ 3 默认值（git init/WIP commit/任务 tag），简单任务轻量 git status 检查；对齐 SKILL.md §6 /plan 步骤3 与 spec_template §0.G |

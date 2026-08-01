<!-- PDCA标签：A.tidy D.danger -->
<!-- 子标签场景：Git 备份清理 -->
<!-- 关键词清单：git备份/清理/瘦身/释放空间/git太大/仓库太大/.git太大/磁盘满了/备份堆积/清理分支/清理reflog/大文件历史/git体检/仓库体检 -->
<!-- 引用范围：main + code_eng_agent -->

# git 备份清理管理（git_backup_cleanup）
> 阶段标签：D · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-13

> 📖 **什么时候读这个文件**：
> - 磁盘空间被 git 仓库占满，想清理释放空间时
> - 想备份 git 仓库（含全部历史）到单个文件时
> - 想清理已合并分支/过期 reflog/大文件历史时
> - 想跑 git gc/repack 瘦身 .git 目录时
> - 想清理堆积的备份文件时
> - 不确定 git 仓库健康状态时
> 🔴 **不要在这时候读**：
> - 日常 git 操作（commit/push/pull）——走 git_workflow.md
> - 代码回滚/恢复——走 git_workflow.md §6

---

## 一、核心哲学：5阶段分层，体检先行，清理必确认

> git 清理是破坏性操作（可能丢代码历史），用户代码0基础不懂 git 底层。本模块的设计哲学：**体检纯只读（随便跑）→ 备份可回溯（跑前自动 commit）→ 清理必确认（fresh clone + HARD-GATE）→ 维护非破坏（git gc/repack）→ 生命周期防膨胀（清理旧备份）**。

5阶段对应5个子命令，从安全到危险递进：

| 阶段 | 子命令 | 风险等级 | 安全机制 | 何时用 |
|------|--------|----------|----------|--------|
| ① 体检 | `--analyze` | 无（纯只读） | 不修改任何文件 | 想看仓库健康状态 |
| ② 备份 | `--backup` | 低 | 自动 commit + verify | 改代码前/定期备份 |
| ③ 清理 | `--cleanup` | 高 | fresh clone + HARD-GATE 确认 | 仓库膨胀想释放空间 |
| ④ 维护 | `--maintain` | 中 | dry-run 预览 | 定期瘦身 .git |
| ⑤ 生命周期 | `--lifecycle` | 中 | 列清单 + 确认 | 备份文件堆积 |

---

## 二、安全门控设计【硬性】

### 2.1 三级安全边界

| 级别 | 适用阶段 | 门控要求 |
|------|----------|----------|
| L1 只读 | 体检 | 无门控，随便跑，不修改任何文件 |
| L2 预览 | 备份/维护/生命周期 | dry-run 预览 → 用户确认 → 执行 |
| L3 破坏性 | 清理 | fresh clone（副本操作）+ HARD-GATE 确认 + 原仓库不动 |

### 2.2 安全不变量（不可跳）

1. **清理必须用户确认**：`--cleanup` 执行前列出操作清单，等用户输入"确认"才执行。`--confirm` 参数可跳过交互（仅用于脚本自动化，手动使用时禁用）。
2. **清理在 fresh clone 副本上操作**：原仓库始终不动，改错可丢副本。借鉴 git-filter-repo 的安全机制。
3. **备份前自动 commit**：`--backup` 检测工作区有未提交改动 → 自动 `git add . + git commit`，确保备份完整（铁律6回溯保障）。
4. **体检失败不阻断**：集成到 startup_tidy/handoff_tidy 的体检钩子失败时仅告警，不阻断主流程（B5隔离，与现有归档错误处理一致）。

### 2.3 星级警告（借鉴 git-sizer）

体检结果按 .git 目录大小输出星级警告，让用户一眼判断严重程度：

| 星级 | 大小范围 | 含义 | 建议动作 |
|------|----------|------|----------|
| * | <100MB | 健康 | 无需操作 |
| ** | 100MB-1GB | 注意 | 定期维护（--maintain） |
| *** | 1GB-5GB | 警告 | 维护 + 清理已合并分支 |
| **** | 5GB-10GB | 严重 | 全量清理（--cleanup --all） |
| ***** | >10GB | 危险 | 立即清理 + 定位大文件历史 |

---

## 三、5阶段操作手册

### 3.1 体检（--analyze）

**用途**：看仓库健康状态，纯只读，随便跑。

**命令**：
```bash
python scripts/git_backup_tidy.py --analyze
python scripts/git_backup_tidy.py --analyze --json    # JSON 输出（供 tidy 脚本解析）
python scripts/git_backup_tidy.py --analyze --top 20  # 显示前20个大文件（默认10）
```

**输出内容**：
- .git 目录大小（字节数 + 人类可读格式 KB/MB/GB）
- .git 历史中最大的 N 个文件（文件名 + 大小 + 所在 commit）
- 分支/tag/reflog 数量统计
- 星级警告（* 到 *****）

**安全保证**：纯只读，不修改任何文件，不调用任何写操作。集成到 startup_tidy/handoff_tidy 时自动跑此阶段。

### 3.2 备份（--backup）

**用途**：备份整个仓库（含全部历史）到单个 .bundle 文件。

**命令**：
```bash
python scripts/git_backup_tidy.py --backup
python scripts/git_backup_tidy.py --backup --dry-run              # 预览不执行
python scripts/git_backup_tidy.py --backup --output-dir D:\backup # 指定备份目录
```

**流程**：
1. 检测工作区状态（git status）
2. 有未提交改动 → 自动 `git add . + git commit -m "auto backup commit {timestamp}"`
3. 构造备份文件名：`{仓库名}_backup_{YYYYMMDD_HHMM}.bundle`
4. `git bundle create {output_dir}/{filename}.bundle --all`
5. `git bundle verify {output_dir}/{filename}.bundle`（验证完整性）

**输出**：JSON `{backup_path, size, verified, commit_before}`

**安全保证**：备份前自动 commit 确保完整（铁律6）；verify 验证备份可用；dry-run 预览不执行。

### 3.3 清理（--cleanup）

**用途**：清理已合并分支/过期 reflog/大文件历史，释放空间。

**命令**：
```bash
python scripts/git_backup_tidy.py --cleanup --target branches    # 清理已合并分支
python scripts/git_backup_tidy.py --cleanup --target reflog      # 清理过期 reflog
python scripts/git_backup_tidy.py --cleanup --target large-files # 清理大文件历史
python scripts/git_backup_tidy.py --cleanup --all                # 全部清理
python scripts/git_backup_tidy.py --cleanup --all --dry-run      # 预览
```

**流程**：
1. **fresh clone**：`git clone --mirror {repo} {tmp_dir}/repo-clone`（原仓库不动）
2. dry-run → 在副本上模拟，输出将清理什么 + 预计释放多少空间
3. 非 dry-run → 列出操作清单，等用户输入"确认"（--confirm 跳过）
4. 执行清理（按 --target 分支）
5. `git gc --aggressive --prune=now`
6. 对比清理前后大小，输出报告
7. 提示：副本在 {tmp_dir}，原仓库未动；如需应用，手动 push 副本到新仓库

**输出**：JSON `{clone_path, operations, before_size, after_size, released, original_repo_untouched}`

**安全保证**：fresh clone 副本操作（原仓库始终不动）；HARD-GATE 确认（用户不确认则取消）；清理失败回滚副本。

**大文件清理注意**：用 `git filter-branch` 清理大文件历史有静默损坏风险（git 官方已弃用）。本模块默认提示用 `git-filter-repo`（若已装），未装则用 filter-branch 但强制 fresh clone + verify。

### 3.4 维护（--maintain）

**用途**：git gc + repack 瘦身 .git 目录，非破坏性。

**命令**：
```bash
python scripts/git_backup_tidy.py --maintain
python scripts/git_backup_tidy.py --maintain --dry-run
```

**流程**：
1. 记录维护前 .git 大小
2. dry-run → 打印将执行的 `git gc --aggressive --prune=now` + `git repack -A -d` 命令
3. 实际执行 → git gc + git repack
4. 记录维护后 .git 大小
5. 输出对比报告

**输出**：JSON `{before_size, after_size, released, commands_run}`

**安全保证**：git gc/repack 是 git 原生维护命令，非破坏性（只清理不可达对象+压缩 packfile）；dry-run 预览。

### 3.5 生命周期（--lifecycle）

**用途**：清理堆积的备份文件，防膨胀。

**命令**：
```bash
python scripts/git_backup_tidy.py --lifecycle
python scripts/git_backup_tidy.py --lifecycle --dry-run
python scripts/git_backup_tidy.py --lifecycle --keep 10 --days 60  # 保留10个+60天内
```

**流程**：
1. 扫描备份目录所有 *.bundle 文件
2. 按修改时间排序（新→旧）
3. 应用保留策略：保留最近 N 个（默认7）+ 最近 N 天内的（默认30），其余标记为待删除
4. dry-run → 打印将删除的文件清单 + 总大小
5. 非 dry-run → 列出清单等用户确认，确认后删除

**输出**：JSON `{total_backups, kept, deleted, released_size}`

**安全保证**：列清单 + 用户确认才删除；删除失败跳过并记录 error，继续处理其他文件。

---

## 四、与框架集成

### 4.1 集成到 startup_tidy

**位置**：`startup_tidy.py` 的 `run()` 末尾

**行为**：启动整理时自动跑 `analyze_repo()`（纯只读体检），结果写入 `TidyReport.git_health` 字段

**目的**：开始干活前看仓库状态，有问题提示用户

**失败处理**：体检失败仅告警不阻断（B5隔离），与现有归档错误处理一致

### 4.2 集成到 handoff_tidy

**位置**：`handoff_tidy.py` 的 `run()` 中

**行为**：交接整理时自动跑 `analyze_repo()`（纯只读体检），结果写入 `HandoffReport.git_health` 字段

**目的**：交接报告含仓库体检，接手方一眼看全仓库健康状况

**失败处理**：体检失败仅告警不阻断（B5隔离）

### 4.3 两处共用同一个函数

```python
# startup_tidy.py 和 handoff_tidy.py 都调用：
from git_backup_tidy import analyze_repo
report.git_health = analyze_repo(repo_path)
```

不重复造轮子（reuse first），两处都调 `analyze_repo()`，体检逻辑统一。

### 4.4 SKILL.md 触发钩子

SKILL.md §0 触发钩子表新增一行：

| 当你遇到/准备做... | 📖 必须立即读... | 🚀 自动触发... |
|---------------------|-----------------|----------------|
| git备份/清理/瘦身/释放空间/git太大/仓库太大/.git太大/磁盘满了/备份堆积/清理分支/清理reflog/大文件历史 | references/common/da/git_backup_cleanup.md | - |

---

## 五、反模式

| 反模式 | 正确做法 |
|--------|----------|
| 清理时不做 fresh clone，直接在原仓库操作 | 强制 fresh clone 副本操作，原仓库不动 |
| 清理时不等用户确认直接执行 | HARD-GATE 确认，用户输入"确认"才执行 |
| 备份时不自动 commit，工作区有未提交改动 | 自动 commit 确保备份完整（铁律6） |
| 用 filter-branch 直接清理（性能差+静默损坏风险） | 默认提示用 git-filter-repo，未装则强制 fresh clone + verify |
| 备份文件不清理，无限堆积 | 生命周期管理（默认保留7个+30天） |
| 体检失败阻断主流程 | 仅告警不阻断（B5隔离） |
| 大仓库直接跑清理不做 dry-run | 先 dry-run 预览，确认预计释放空间后再执行 |

---

## 六、典型使用场景

### 场景1：用户发现磁盘快满了，想清理

```bash
# 1. 体检看状态
python scripts/git_backup_tidy.py --analyze

# 2. 看到星级 *** 警告，先备份
python scripts/git_backup_tidy.py --backup

# 3. 预览清理
python scripts/git_backup_tidy.py --cleanup --all --dry-run

# 4. 确认清理
python scripts/git_backup_tidy.py --cleanup --all

# 5. 维护瘦身
python scripts/git_backup_tidy.py --maintain

# 6. 清理旧备份
python scripts/git_backup_tidy.py --lifecycle
```

### 场景2：定期维护（每月一次）

```bash
python scripts/git_backup_tidy.py --analyze          # 体检
python scripts/git_backup_tidy.py --maintain         # gc + repack
python scripts/git_backup_tidy.py --lifecycle        # 清理旧备份
```

### 场景3：交接前自动体检

```bash
# handoff_tidy 自动跑体检，无需手动调用
python scripts/handoff_tidy.py --task my_task
# 交接 JSON 含 git_health 字段
```

---

## 七、技术实现说明

### 7.1 纯 Python 标准库

本模块仅用 Python 标准库（os/sys/subprocess/json/argparse/datetime/shutil/pathlib/re/tempfile/time），不装任何外部依赖。git 操作通过 `subprocess` 调用 git 原生命令。

### 7.2 复用框架共享函数

- 复用 `tidy_common.py` 的共享函数（如日志、JSON 输出）
- 复用 `generate_docs.py` 的 `atomic_write`（如需写文件）

### 7.3 与现有 tidy 脚本一致

- 输出格式：JSON（供 tidy 脚本解析）+ 人类可读报告（默认）
- 错误处理：B5隔离（失败仅告警不阻断）
- dry-run：所有阶段都支持 dry-run 预览

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-13 22:13 | 初版：5阶段操作手册 + 安全门控设计 + 框架集成说明 + 反模式 + 典型场景 |

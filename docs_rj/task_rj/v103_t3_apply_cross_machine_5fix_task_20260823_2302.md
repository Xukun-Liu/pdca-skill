---
title: v103_t3_apply_cross_machine_5fix - 任务清单
version: v1.0.0
skill_version: v1.0.3
date_created: 2026-08-23 23:02
last_updated: 2026-08-23 23:02
spec_ref: spec_rj/v103_t3_apply_cross_machine_5fix_spec_20260823_2302.md
---

# task：v103_t3_apply_cross_machine_5fix

> 版本：v1.0.0 | 更新：2026-08-23 23:02
> ⚠️ No Placeholders铁律：禁止TBD/TODO/"适当处理"/"类似XX"；每个代码步骤给完整代码；每个命令给预期结果；每个task给验证步骤。

---

## 总览

- **对应 spec**：`docs_rj/spec_rj/v103_t3_apply_cross_machine_5fix_spec_20260823_2302.md`
- **最终目标**：把源机 5 个跨机 bug 在 v1.0.3 当前代码上**逐项 diff → 修仍存在的 → 5 个独立 commit 留痕**，且 v1.0.3 基线（validate_skill 32/32、global_total ≈ 156）不倒退。
- **当前阶段**：Phase 1 需求对齐（已写完 spec，待用户 HARD-GATE 确认 → 进 Phase 2 执行）
- **HARD-GATE状态**：未确认（spec/task 已写完，等用户在确认闸门处说"可以/通过"才进 /do）
- **进度状态**（REQ-038）：未开始（待 HARD-GATE 通过）
- **阻塞项**（REQ-039）：无（5 个 bug diff 已完成、5 段 patch 已知、行号 ±2 行内对齐）
- **开工回执**（REQ-040）：
  - 理解的目标 = 把源机 v1.0.1 蒸馏踩出的 5 个 bug 在 v1.0.3 上 diff + 修 + 5 commit 留痕，不破坏基线
  - 顺序 = T000（备份）→ T001（#1）→ T002（#2）→ T003（#3）→ T004（#4）→ T005（#5）→ T006（总回归）→ T007（写 memory/SUMMARY/handoff）
  - 最大风险 = 修复 #5 全段扫描后 `current_project` 归属错位（缓解：AC-005 双重指标 + 错位时回 /plan 增量补 patch）
- **项目纪律**（REQ-041）：
  - 每个 task 完成后必须跑对应 AC 验证命令，看到预期输出才打勾
  - 改动白名单仅 5 个 .py，不许碰 SKILL.md / references/ / memory_main.md
  - 每个修复 1 个 commit，commit message 严格 `fix(v103t3): <脚本> <一行说清>` + `Refs: v103_t3` footer
  - 出现连败 3 次（同一 AC 红 3 次）即停，回 /plan 重新评估

---

## Phase 1: 需求对齐

> 本阶段已在 spec.md 完成（T000~T007 的结构与字段已定），这里复述各 task 的"做什么"摘要，详细 12 字段见 Phase 2。

- [ ] **T000** robocopy 备份 5 脚本到 `_sync_tmp/scripts/`，并记录 sha256。
- [ ] **T001** 修复 #1：memory_shadow_write.py 强制 stdin UTF-8 + 替换符 warning。
- [ ] **T002** 修复 #2：handoff_tidy.py 禁用 cwd 基名（白名单 + task 前缀回退 + 显式 project_name）。
- [ ] **T003** 修复 #3：memory_distill.py entry 加 status 字段 + frontmatter 解析 + distill 过滤。
- [ ] **T004** 修复 #4：validate_skill.py 搜索根清单加 `.config/opencode/skills`。
- [ ] **T005** 修复 #5：learn_tidy.py scan_memory_layer_drift 改为全段扫描。
- [ ] **T006** 总回归：validate_skill + learn_tidy scan 双跑，5/5 AC 全 PASS。
- [ ] **T007** /act 收尾：写 1 条 memory + 更新 SUMMARY + 跑 handoff_tidy。

---

## Phase 2: 执行

> ⚠️ **每个 task 必须包含 12 字段**（REQ-033~037 + REQ-034a + 8 个核心字段）。

### T000 [备份] 用 robocopy 把 5 脚本备份到 `_sync_tmp/scripts/`

- 怎么做：
  ```powershell
  $SKILLROOT = "c:\Users\86029\Desktop\github_gitee 开源项目\PDCA-SKILL 文件夹\pdca-skill\PDCA-skill-public v1.0.2_开发环境"
  robocopy "$SKILLROOT\scripts" "$SKILLROOT\_sync_tmp\scripts" memory_shadow_write.py handoff_tidy.py memory_distill.py validate_skill.py learn_tidy.py /NFL /NDL
  Get-FileHash -Algorithm SHA256 "$SKILLROOT\scripts\memory_shadow_write.py", "$SKILLROOT\scripts\handoff_tidy.py", "$SKILLROOT\scripts\memory_distill.py", "$SKILLROOT\scripts\validate_skill.py", "$SKILLROOT\scripts\learn_tidy.py" | Format-Table -AutoSize
  Get-FileHash -Algorithm SHA256 "$SKILLROOT\_sync_tmp\scripts\memory_shadow_write.py", "$SKILLROOT\_sync_tmp\scripts\handoff_tidy.py", "$SKILLROOT\_sync_tmp\scripts\memory_distill.py", "$SKILLROOT\_sync_tmp\scripts\validate_skill.py", "$SKILLROOT\_sync_tmp\scripts\learn_tidy.py" | Format-Table -AutoSize
  ```
- 验证：
  - `robocopy` 输出 `Files Copied: 5`（或类似成功行，无失败行）。
  - 备份前后 5 个脚本 sha256 完全一致（10 行哈希两两配对相等）。
  - 用 `Test-Path "$SKILLROOT\_sync_tmp\scripts\learn_tidy.py"` 返回 True。
- 边界条件：
  - 正常路径：5 个脚本全部存在、readable → robocopy 复制 5 个文件。
  - 边界/异常：`_sync_tmp/scripts/` 不存在 → robocopy 自动创建；任一源文件缺失 → 报错，对应 sha256 校验失败，立刻停。
- 验收标准（GWT）：
  - **Given** 5 个目标脚本存在于 `$SKILLROOT\scripts\` 下
  - **When** 跑 robocopy + 双遍 Get-FileHash
  - **Then** `_sync_tmp\scripts\` 出现 5 个同名文件，且 sha256 与源 5 文件两两相等
- 不通过处理：从 `_sync_tmp/scripts/` 整体拷回 `$SKILLROOT/scripts/`（即恢复现场），回 /plan 评估是 robocopy 路径问题还是 git 工作区已脏。
- 改动白名单路径（REQ-033）：`_sync_tmp/scripts/`（新建目录 + 5 个拷贝）。
- 反向验证（REQ-034）：N/A（备份类任务，无失效安全风险）。
- 防作弊点名禁止（REQ-034a）：N/A（核对/审查类任务，无代码改动/无命令执行）。
- 死规矩带后果（REQ-035）：做「先备份才动源脚本」，否则「T001 起任意修复回滚时无安全网」。
- 依赖排序说明（REQ-036）：T000 排第一；后续 T001~T005 全部依赖此备份存在。
- 防幻觉验证（REQ-037）：robocopy 与 Get-FileHash 均为 /do 阶段实际跑的命令。

---

### T001 [修复 #1] memory_shadow_write.py stdin 强制 UTF-8

- 怎么做：
  1. Read `scripts/memory_shadow_write.py` L1108-1128，定位 `if not args.project:` 后的 `if args.content is not None:` 分支。
  2. 用 SearchReplace 把 `if args.content is not None:` 之前插入 try/except reconfigure + warning：
     ```python
     # 修复#1：stdin 强制 UTF-8，防 PowerShell 管道 GBK 字节流损坏中文
     try:
         sys.stdin.reconfigure(encoding='utf-8', errors='replace')
     except Exception:
         pass
     ```
  3. 在 `content = sys.stdin.read()` 之后加 U+FFFD 替换符检测：
     ```python
     content = sys.stdin.read()
     if '\ufffd' in content:  # U+FFFD=替换符
         logger.warning("stdin 内容含替换符，疑似管道编码损坏（PowerShell 管道中文请改用 --content 参数或 UTF-8 文件传入）")
     ```
  4. 跑 AC-001 验证命令（见下）。
  5. git add + commit：
     ```powershell
     git add scripts/memory_shadow_write.py
     git commit -m "fix(v103t3): memory_shadow_write CLI 强制 UTF-8 stdin 防 PowerShell 中文损坏" -m "在 main() 项目级双写分支入口加 sys.stdin.reconfigure(encoding='utf-8')，避免 GBK 字节流被 UTF-8 解析导致中文变 ????。" -m "Refs: v103_t3"
     ```
- 验证：
  ```powershell
  $env:PYTHONIOENCODING='utf-8'
  "中文编码测试" | python scripts\memory_shadow_write.py --project enc_test_20260823
  Select-String -Path "$env:USERPROFILE\.pdca-skill\data\memory\memory_main.md" -Pattern "enc_test_20260823" -Context 2,2
  python -c "import sys; sys.path.insert(0, 'scripts'); import memory_shadow_write as m; m.memory_delete('enc_test_20260823', hard_delete=True)"
  ```
  - `Select-String` 输出应含 `中文编码测试`（不是 `????` 或 `\ufffd`）。
  - `memory_delete` 返回成功，memory_main.md 不再有 `enc_test_20260823`。
- 边界条件：
  - 正常路径：PowerShell 管道传入中文 → reconfigure 成功 → 写入正常中文。
  - 边界/异常：Python < 3.7（reconfigure 抛 AttributeError）→ try/except 兜底，原行为不变。
  - 边界/异常：stdin 是 tty（直接 `python --project xxx`，无管道）→ 走 `isatty()` 分支返回空 content，不触发 reconfigure。
- 验收标准（GWT）：
  - **Given** PowerShell 5.1+ + Python 3.7+ + memory_main.md 写权限
  - **When** `"中文编码测试" | python memory_shadow_write.py --project enc_test_20260823`
  - **Then** memory_main.md 中出现含 `中文编码测试` 正常中文的条目（不是 `????`）
- 不通过处理：
  - 若 reconfigure 抛 AttributeError 未兜住 → 补 `except (AttributeError, Exception): pass`。
  - 若 Select-String 仍看到 `????` → 检查 logger 是不是走 stderr 没显示，重新跑命令去掉 `| Out-Null`。
  - 若 memory_delete 报 "项目不存在" → 说明 memory_main.md 写入路径不对，Read 写入的 `## ` 分段名。
- 改动白名单路径（REQ-033）：`scripts/memory_shadow_write.py`（只动 L1115-1125 这块）。
- 反向验证（REQ-034）：是——失效会让跨机中文记忆继续损坏（静默数据丢失）。
- 防作弊点名禁止（REQ-034a）：不许 `try: pass` 把 reconfigure 完全跳过；不许用 `content = ''` 抹平测试；不许改 logger.warning 抑制输出。
- 死规矩带后果（REQ-035）：做「插入 reconfigure + 替换符检测」，否则「跨机中文写入继续损坏且无 warning 提示」。
- 依赖排序说明（REQ-036）：T001 排 T000 之后；T002~T005 互不依赖，可任意顺序。
- 防幻觉验证（REQ-037）：所有命令将在 /do 阶段实际跑过（验证 + 清理）。

---

### T002 [修复 #2] handoff_tidy.py 禁用 cwd 基名 + 显式传 project_name

- 怎么做：
  1. Read `scripts/handoff_tidy.py` L200-220，定位 `__init__` 中 `self.project_name = project_name or os.path.basename(os.getcwd())`。
  2. 用 SearchReplace 替换为：
     ```python
     # 修复#2：cwd 基名无语义时（外置数据目录等）禁止用作项目分段名
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
  3. Read L505-525，定位 `_write_handoff_memory` 末尾 `return memory_shadow_write.write_project(self.task_name + '_handoff', content)`。
  4. 用 SearchReplace 替换为：
     ```python
     return memory_shadow_write.write_project(self.task_name + '_handoff', content,
                                              project_name=self.project_name)
     ```
  5. 跑 AC-002 验证命令（见下）。
  6. git add + commit：
     ```powershell
     git add scripts/handoff_tidy.py
     git commit -m "fix(v103t3): handoff_tidy 禁用 cwd 基名作项目名" -m "白名单 {data,docs_rj,memory,desktop,桌面文件} 命中时回退到 task_name 前缀，避免污染 ## data 等无语义分段。同时显式传 project_name 避免双重回退。" -m "Refs: v103_t3"
     ```
- 验证：
  ```powershell
  cd "$env:USERPROFILE\.pdca-skill\data"
  python scripts\handoff_tidy.py --task test_handoff_fix_20260823
  Select-String -Path "$env:USERPROFILE\.pdca-skill\data\memory\memory_main.md" -Pattern "^## data$"
  Select-String -Path "$env:USERPROFILE\.pdca-skill\data\memory\memory_main.md" -Pattern "test_handoff_fix_20260823"
  python -c "import sys; sys.path.insert(0, 'scripts'); import memory_shadow_write as m; m.memory_delete('test_handoff_fix_20260823_handoff', hard_delete=True)"
  ```
  - `Select-String "^## data$"` 应输出空。
  - `Select-String "test_handoff_fix_20260823"` 应输出交接 stub（`## test_handoff_fix_20260823` 分段下有 handoff 条目）。
- 边界条件：
  - 正常路径：cwd=`.../data` → 基名 `data` 命中白名单 → project_name 走 `test_handoff_fix_20260823` 前缀。
  - 边界/异常：cwd=`C:\Users\xxx\Desktop\github_gitee 开源项目\PDCA-SKILL 文件夹\...` → 基名 `PDCA-skill-public v1.0.2_开发环境` 不在白名单 → 走第三分支用 `_base`，行为不变。
  - 边界/异常：task_name 为空 → 回退到 `'unknown_project'`。
  - 边界/异常：基名是 `DATA`（大写）→ `.lower() in _BAD_BASENAMES` 仍命中。
- 验收标准（GWT）：
  - **Given** cwd 是 `~/.pdca-skill/data`、task=`test_handoff_fix_20260823`、memory_main.md 写权限
  - **When** 跑 `python handoff_tidy.py --task test_handoff_fix_20260823`
  - **Then** memory_main.md 不出现 `## data` 分段；新增 `## test_handoff_fix_20260823` 分段含交接 stub
- 不通过处理：
  - 若仍出现 `## data` → 检查 cwd 实际是什么（`Get-Location`）、白名单是否被覆盖。
  - 若交接 stub 落入 `## test_handoff_fix_20260823_handoff`（带 `_handoff` 后缀）→ 检查 `write_project` 是否接收 task_name 已含后缀的 key。
  - 若 `__init__` 报错 → 检查 `task_name` 是不是 __init__ 的入参（不一定是，可能在外部传）。
- 改动白名单路径（REQ-033）：`scripts/handoff_tidy.py`（只动 L208 + L513 两块）。
- 反向验证（REQ-034）：是——失效会让 handoff 段持续污染（隐性数据膨胀）。
- 防作弊点名禁止（REQ-034a）：不许把白名单留空；不许把 warning 改成 `print` 后删掉；不许把 `project_name=self.project_name` 改成 `project_name=None`。
- 死规矩带后果（REQ-035）：做「白名单 + 显式 project_name 双管齐下」，否则「`## data` 段持续产生 + write_project 二次回退兜不住」。
- 依赖排序说明（REQ-036）：T002 排 T001 之后（无关性，但 T000 后顺序任意），习惯性放第二位。
- 防幻觉验证（REQ-037）：所有命令 /do 实跑。

---

### T003 [修复 #3] memory_distill.py entry 加 status + frontmatter 解析 + distill 过滤

- 怎么做：
  1. Read `scripts/memory_distill.py` L55-95，定位 `parse_memory_entries()` 内 `entry = {...}` 初始化 dict 和 frontmatter 解析循环。
  2. 在 entry dict 末尾加 `"status": "active",  # ← 新增`。
  3. 在 frontmatter 循环 `elif fl.startswith('**经验标签**: '):` 分支后插入：
     ```python
     elif fl.startswith('**状态**: '):
         entry["status"] = fl.replace('**状态**: ', '').strip()
     ```
  4. Read L115-130，定位 `lesson_entries = [e for e in entries if e["is_lesson"]]`。
  5. 用 SearchReplace 替换为：
     ```python
     lesson_entries = [e for e in entries
                       if e["is_lesson"]
                       and e.get("status", "active") not in ("archived", "demoted")]
     ```
  6. 跑 AC-003 验证命令。
  7. git commit：
     ```powershell
     git add scripts/memory_distill.py
     git commit -m "fix(v103t3): memory_distill 跳过 archived/demoted 经验条目" -m "parse_memory_entries 增 status 字段，frontmatter 解析记录 **状态**，distill 阶段过滤掉非 active 状态。" -m "Refs: v103_t3"
     ```
- 验证：
  ```powershell
  $env:PYTHONIOENCODING='utf-8'
  python scripts\memory_distill.py distill --project 精诚养车县级通报名情况
  python scripts\memory_distill.py distill --project 一般-异常工单抢修分析-AI处理
  ```
  - 两条命令 stdout 各包含 `经验库总数: 0`（修复前各 1，因为唯一 lesson 已 archived）。
- 边界条件：
  - 正常路径：status=archived 的条目被过滤，不进 lesson 总数。
  - 边界/异常：旧条目无 `**状态**` 字段 → `e.get("status", "active")` 兜底为 active，行为不变。
  - 边界/异常：status 拼写异常（`archived ` 带空格）→ `.strip()` 兜底。
- 验收标准（GWT）：
  - **Given** memory_main.md 含 status=archived 的旧 lesson（精诚养车/异常工单 两个分段各 1 条）
  - **When** 跑 `python memory_distill.py distill --project <两段>`
  - **Then** 两条命令 stdout 各输出 `经验库总数: 0`
- 不通过处理：
  - 若仍报 1 → 检查 `**状态**` 字段在 memory_main.md 是否实际拼写为 `**状态**:archived`（无空格）。
  - 若 global_total 跌出 ≥ 150 范围 → 误伤了 active 条目，回退 list comprehension。
- 改动白名单路径（REQ-033）：`scripts/memory_distill.py`（3 处：entry 字段 + frontmatter + distill 过滤）。
- 反向验证（REQ-034）：是——失效会让 archived 旧经验持续污染新项目学习。
- 防作弊点名禁止（REQ-034a）：不许把过滤改成 `if e["is_lesson"]` 直接返回（去掉过滤）；不许删 `e.get` 兜底（破坏向前兼容）；不许改 archived 字符串匹配大小写。
- 死规矩带后果（REQ-035）：做「entry 字段 + frontmatter 解析 + distill 过滤三处一起」，否则「缺一处整个修复无效」。
- 依赖排序说明（REQ-036）：T003 排 T002 之后（无关性，顺序任意），放第三位。
- 防幻觉验证（REQ-037）：/do 阶段实际跑两条 distill 命令对账。

---

### T004 [修复 #4] validate_skill.py 搜索根加 `.config/opencode/skills`

- 怎么做：
  1. Read `scripts/validate_skill.py` L190-210，定位 `build_skill_search_roots()` 内的 `for sub in [...]` 列表。
  2. 用 SearchReplace 追加 `'.config/opencode/skills'`：
     ```python
     for sub in ['.workbuddy/skills', '.pdca-memory/skills', '.trae-cn/skills',
                 '.config/opencode/skills']:   # 修复#4：opencode 用户技能目录
         roots.append(os.path.join(home, *sub.split('/')))
     ```
  3. 跑 AC-004 验证命令（先临时改名双份维护）：
     ```powershell
     Rename-Item $env:USERPROFILE\.pdca-memory\skills\brainstorming brainstorming.bak
     Rename-Item $env:USERPROFILE\.pdca-memory\skills\writing-plans writing-plans.bak
     python scripts\validate_skill.py
     Rename-Item $env:USERPROFILE\.pdca-memory\skills\brainstorming.bak brainstorming
     Rename-Item $env:USERPROFILE\.pdca-memory\skills\writing-plans.bak writing-plans
     ```
  4. git commit：
     ```powershell
     git add scripts/validate_skill.py
     git commit -m "fix(v103t3): validate_skill 搜索根补 opencode 技能目录" -m "build_skill_search_roots 的 home 下搜索根清单追加 .config/opencode/skills，避免 opencode 用户装的 brainstorming/writing-plans 在双份维护改名后被漏掉。" -m "Refs: v103_t3"
     ```
- 验证：
  - `validate_skill.py` 输出含 `SKL-01 PASS` `SKL-02 PASS` `32/32 PASS` `MUST FIX=0`。
- 边界条件：
  - 正常路径：opencode 目录有 skill → 找到并 PASS。
  - 边界/异常：opencode 目录不存在 → `os.path.join` 不报错，校验跳过。
  - 边界/异常：双份维护中一份被改名 → 仍能从另一份找到，PASS。
- 验收标准（GWT）：
  - **Given** `~/.config/opencode/skills/brainstorming` 和 `writing-plans` 是 entity 目录，`~/.pdca-memory/skills/` 下同名目录已临时改名
  - **When** 跑 `python validate_skill.py`
  - **Then** 输出 `32/32 PASS, MUST FIX=0`，且 SKL-01 / SKL-02 标记 PASS
- 不通过处理：
  - 若 SKL-01/SKL-02 FAIL → 检查 `~/.config/opencode/skills/brainstorming` 是否真实存在（`Test-Path`），不存在则说明 opencode 装在别的位置。
  - 若 validate_skill 整体 FAIL 数增多 → 检查列表追加后是否有重复 root。
- 改动白名单路径（REQ-033）：`scripts/validate_skill.py`（只动 L196 那一行字符串）。
- 反向验证（REQ-034）：是——失效会让 opencode 用户持续双份维护。
- 防作弊点名禁止（REQ-034a）：不许把 list 替换为 hardcoded 单条；不许删 `.pdca-memory/skills`（破坏现有用户）。
- 死规矩带后果（REQ-035）：做「仅追加字符串，不删其他根」，否则「现有用户搜索路径会变窄」。
- 依赖排序说明（REQ-036）：T004 排 T003 之后（无关性），放第四位。
- 防幻觉验证（REQ-037）：/do 实测两条 Rename-Item + 跑 validate_skill。

---

### T005 [修复 #5] learn_tidy.py scan_memory_layer_drift 改全段扫描

- 怎么做：
  1. Read `scripts/learn_tidy.py` L1390-1430，定位 `scan_memory_layer_drift()` 内 `heading = '## %s' % project_name` 和 `if line.rstrip('\n') == heading: in_section = True` 块。
  2. 用 SearchReplace 替换为：
     ```python
     global_entries = {}
     memory_content = _read_text(MEMORY_MAIN_PATH)
     if memory_content:
         lines = memory_content.split('\n')
         in_section = False
         current_entry = None
         current_lines = []
         for line in lines:
             # 修复#5：扫全部项目分段（原只扫 ## {cwd基名} 单段，外置数据目录下恒为空→global_total=0 误报）
             if line.startswith('## ') and not line.startswith('### '):
                 in_section = True
                 continue
             if in_section:
                 match = MEMORY_ENTRY_RE.match(line)
                 # ... 后续 if match: ... elif current_entry is not None: ... 保持不变
     ```
  3. 跑 AC-005 验证：
     ```powershell
     cd "$env:USERPROFILE\.pdca-skill\data"
     $env:PYTHONIOENCODING='utf-8'
     python scripts\learn_tidy.py scan --dry-run
     (Select-String -Path "$env:USERPROFILE\.pdca-skill\data\memory\memory_main.md" -Pattern '^### 记忆条目').Count
     ```
  4. git commit：
     ```powershell
     git add scripts/learn_tidy.py
     git commit -m "fix(v103t3): learn_tidy scan 改全段扫描修 global_total=0 误报" -m "scan_memory_layer_drift 不再只看 ## {cwd基名} 单段，改为扫所有 ##  分段，恢复 global_total 与 layer_consistency 计算准确性。" -m "Refs: v103_t3"
     ```
- 验证：
  - learn_tidy.py scan --dry-run 输出 `global_total` ≈ 156（与 Select-String 计数对账误差 ≤ 2）。
  - `layer_consistency` 非零。
- 边界条件：
  - 正常路径：cwd=`.../data`、memory_main.md 含 26 个 `## ` 分段 → 扫到 156 条。
  - 边界/异常：标题是 `### 记忆条目` → `not line.startswith('### ')` 过滤掉。
  - 边界/异常：memory_main.md 第一个字符就是 `###`（无 `## `）→ in_section 一直 False，返回空 dict（行为退化但不报错）。
- 验收标准（GWT）：
  - **Given** cwd=`~/.pdca-skill/data`、memory_main.md 含 156 条 `### 记忆条目`
  - **When** 跑 `python learn_tidy.py scan --dry-run`
  - **Then** 输出 `global_total` ≥ 150、`layer_consistency` ≠ 0
- 不通过处理：
  - **H1 强制前置**（H1 缓解）：动手前先 Read `learn_tidy.py` L1395-L1440 实际代码，确认 `current_project` 赋值逻辑在新全段扫描下仍正确（最可能修改：原 `current_project = project_name` 需改为 `current_project = line.replace('## ', '').strip()` + 用 `global_entries.setdefault(current_project, {})` 隔离各项目）。如需补全 patch → 同步更新本段和 spec §7 #5 patch。
  - 若 global_total 仍为 0 → 检查 `MEMORY_ENTRY_RE` 是否匹得到 `### 记忆条目 ...`（不是 `### 记忆条目 (N)`）。
  - 若 `current_project` 归属错位导致 layer_consistency 仍异常 → 回 /plan 增量补 patch（见 §9 R6）。
  - 若 commit 后 validate_skill 突然 FAIL → 跨脚本影响，git revert 回到 T000 状态。
- 改动白名单路径（REQ-033）：`scripts/learn_tidy.py`（只动 scan_memory_layer_drift 内的循环入口判断）。
- 反向验证（REQ-034）：是——失效会让 learn scan gate 持续误报 conditional。
- 防作弊点名禁止（REQ-034a）：不许把 `not line.startswith('### ')` 删掉（会导致 `### 标题` 被误识为分段）；不许把 `in_section = True; continue` 改成 `break`（退化成原单段行为）。
- 死规矩带后果（REQ-035）：做「扫全段且 `###` 排除」，否则「`### 标题` 被吞成分段 → 当前段重置 → 条目归属错位」。
- 依赖排序说明（REQ-036）：T005 放最后（修复体量最大、风险最高），但顺序其实可任意。
- 防幻觉验证（REQ-037）：/do 实际跑 + Select-String 对账。

---

## Phase 3: 验收

### T006 [总回归] 5/5 AC 全部跑过 + 5 commit 留痕

- 怎么做：
  ```powershell
  cd "$SKILLROOT"
  $env:PYTHONIOENCODING='utf-8'
  python scripts\validate_skill.py
  cd "$env:USERPROFILE\.pdca-skill\data"
  python scripts\learn_tidy.py scan --dry-run
  git log --pretty=format:"%h %s" -n 5
  ```
- 验证：
  - validate_skill 输出 `32/32 PASS, MUST FIX=0`。
  - learn_tidy scan 输出 `global_total ≥ 150`。
  - git log 出现 5 条 `fix(v103t3):` 前缀的 commit。
- 边界条件：
  - 正常路径：5 修复都过 → 5/5 AC PASS。
  - 边界/异常：任一 AC 失败 → 回对应 T00X 修补，不要用 `git revert` 整体回滚（丢失其他修复的留痕）。
- 验收标准（GWT）：
  - **Given** T000~T005 全部完成
  - **When** 跑 validate_skill + learn_tidy scan + git log
  - **Then** validate_skill 32/32 PASS、global_total ≥ 150、git log 含 5 条 fix(v103t3) 标题
- 不通过处理：
  - 若 validate_skill FAIL 但未动 validate_skill.py → 可能是其他修复引入跨脚本副作用，逐修复二分排查。
  - 若 global_total 跌出 150 → 修复 #5 没生效，git log 看 commit 是否包含 T005 的改动。
  - 若 commit 数 ≠ 5 → git log 全列出来看哪条漏了，对应 T00X 重 commit。
- 改动白名单路径（REQ-033）：N/A（只读 + 观察）。
- 反向验证（REQ-034）：N/A（验收任务，无新写代码）。
- 防作弊点名禁止（REQ-034a）：N/A（核对/验收类任务）。
- 死规矩带后果（REQ-035）：做「不过任一 AC 都不算完成」，否则「破坏 AC-006 总回归的红线」。
- 依赖排序说明（REQ-036）：T006 排 T005 之后，依赖 T001~T005 全过。
- 防幻觉验证（REQ-037）：所有命令 /do 实跑，输出贴到 handoff。

---

### T007 [/act 收尾] 写 memory + 更新 SUMMARY + 跑 handoff_tidy

- 怎么做：
  1. 用 `scripts/memory_shadow_write.py` 写 1 条 memory：
     ```powershell
     $env:PYTHONIOENCODING='utf-8'
     $content = @"
     ## 2026-08-23 v103_t3 跨机 5 bug 修复完成

     ### what
     把源机 v1.0.1 蒸馏踩出的 5 个 bug 在 v1.0.3 上 diff + 修完，5 个独立 commit 留痕。

     ### why
     源机 proposals.md 给出 5 段 patch，但 v1.0.3 与 v1.0.1 行号/逻辑可能漂移；盲搬会引新 bug。先 diff 5/5 仍存在，再逐项修。

     ### how
     - 修复#1 memory_shadow_write: stdin 强制 UTF-8 + U+FFFD warning
     - 修复#2 handoff_tidy: cwd 基名白名单 + 显式 project_name
     - 修复#3 memory_distill: entry 加 status + frontmatter 解析 + 过滤 archived/demoted
     - 修复#4 validate_skill: 搜索根加 .config/opencode/skills
     - 修复#5 learn_tidy: scan_memory_layer_drift 改全段扫描

     ### verify
     - validate_skill 32/32 PASS、MUST FIX=0
     - learn_tidy scan global_total ≥ 150、layer_consistency ≠ 0
     - 5 commit 全部 fix(v103t3) + Refs footer

     ### port
     源机 proposals.md 适用前必须 diff 当前代码；行号漂移 > 5 行按变量/函数名锚点定位。

     ### lesson
     跨机 patch 永远先 diff，别盲搬。
     "@
     $content | python scripts\memory_shadow_write.py --project v103_t3_apply_cross_machine_5fix_memory
     ```
  2. 更新 `docs_rj/SUMMARY_RJ.md` 加一行 v103_t3 摘要（参考 v103_t2 格式）。
  3. 跑 handoff_tidy 把当前任务交接：
     ```powershell
     cd "$env:USERPROFILE\.pdca-skill\data"
     python scripts\handoff_tidy.py --task v103_t3_apply_cross_machine_5fix
     ```
- 验证：
  - memory_main.md 出现 `v103_t3_apply_cross_machine_5fix_memory` 条目（内容含上述 what/why/how/verify/port/lesson 6 段）。
  - SUMMARY_RJ.md 出现 v103_t3 行。
  - handoff_tidy 不报错。
- 边界条件：
  - 正常路径：写 memory + 更新 SUMMARY + 跑 handoff_tidy 全部成功。
  - 边界/异常：写 memory 时 stdin 中文再坏（不应该，#1 修完）→ 用 `--content` 参数 + 临时文件。
- 验收标准（GWT）：
  - **Given** T001~T006 全过
  - **When** 跑上述 3 个动作
  - **Then** memory_main.md / SUMMARY_RJ.md 各新增对应内容，且无报错
- 不通过处理：写 memory 失败用 `--content` 兜底；SUMMARY 编辑失败回退到 Read+Edit；handoff_tidy 报错看 stderr 走 #2 修复的兜底分支。
- 改动白名单路径（REQ-033）：`docs_rj/SUMMARY_RJ.md`（追加 1 行）+ `~/.pdca-skill/data/memory/memory_main.md`（通过 memory_shadow_write 追加 1 条）。
- 反向验证（REQ-034）：N/A（收尾类任务）。
- 防作弊点名禁止（REQ-034a）：不许把 memory 写成 placeholder；不许 SUMMARY 行留空字段。
- 死规矩带后果（REQ-035）：做「6 段结构化 memory + SUMMARY + handoff_tidy 三件套」，否则「任务无沉淀，跨机/跨人交接断档」。
- 依赖排序说明（REQ-036）：T007 排最后，依赖 T001~T006 全过。
- 防幻觉验证（REQ-037）：/do 实跑 + 读 memory_main.md / SUMMARY_RJ.md 确认。

---

## 验收清单（4 道闸门 + 增强 3 项）

进入 Phase 3 前，逐条核对。有任何一条不过，不算做完。

- [ ] **闸门1 规格自检**：每个 task 都包含 12 个字段？边界条件没空？验收标准写成 GWT？
- [ ] **闸门2 差别核对**：只改了 5 个声明脚本？没偷偷改 SKILL.md / references/ / memory_main.md？5 commit 全部 fix(v103t3) 前缀 + Refs footer？
- [ ] **闸门3 测试抓错**：每个 AC 验证命令实际跑过？反向验证（AC-001~AC-005）确实制造过失败证明会响？
- [ ] **闸门4 人工签收**：用户明确说"可以/通过"，并指出具体看了哪条 AC/哪行代码？
- [ ] **闸门5 暗卷抽查**（REQ-042）：2-3 条 spec 没写的抽查项，管理者自留，验收时复跑。
- [ ] **闸门6 贴命令输出**（REQ-043）：每条 AC 都贴实际命令输出（含反向验证红→绿证据），只说做完了不算。
- [ ] **闸门7 止损满轮即停**（REQ-044）：跑满 N=3 轮对抗审查即停，如实汇报卡在哪、还差什么。

---

## 待回答的关键问题（Key Questions）

| # | 问题 | 状态 | 答案 |
|---|------|------|------|
| 1 | 5 个 bug 在 v1.0.3 是否仍存在？ | closed | 5/5 仍存在（diff 实测） |
| 2 | 5 修复独立 commit 还是合并 commit？ | closed | 5 个独立 commit |
| 3 | 改前是否先备份？ | closed | 是，robocopy 到 `_sync_tmp/scripts/` |

---

## 决策记录（Decision Log）

| 决策 | 理由 | 时间 | 来源 |
|------|------|------|------|
| 先 diff 后逐修（方案 A） | 用户原话"先 diff 5 修复 vs v1.0.3(推荐)" | 2026-08-23 23:02 | AskUserQuestion |
| 5 个独立 commit | 原子性，便于单点 revert | 2026-08-23 23:02 | AskUserQuestion |
| robocopy 备份到 `_sync_tmp/scripts/` | 不上 git stash（避免和未 commit 工作区混淆） | 2026-08-23 23:02 | AskUserQuestion |
| 不删 `~/.pdca-memory/skills/` 双份维护 | junction vs 实体文件辨识有风险，由用户手工处理 | 2026-08-23 23:02 | proposals.md §5 注意事项 + spec §3 |
| 修复 #6（SKILL.md 减法）不在本批 | proposals.md §8.1 立项留痕，不混做 | 2026-08-23 23:02 | proposals.md §8.1 |

---

## 错误记录（Error Log）

> 跑满 3 次同 AC 红即停，回 /plan 重设计。

| 时间 | 错误现象 | 第几次尝试 | 怎么解决的 |
|------|----------|-----------|-----------|
| - | - | - | - |

---

## 测试结果（Test Results）

> Check 阶段逐项验证时记录。每条 AC 都要实际跑、贴实际输出。

| 测试项 | 怎么测的（具体命令/操作） | 预期结果 | 实际结果 | 通过？ |
|--------|--------------------------|----------|----------|--------|
| AC-001 | `"中文编码测试" \| python memory_shadow_write.py --project enc_test_20260823` + Select-String | 写入中文（不是 `????`） | - | - |
| AC-002 | `cd ~/.pdca-skill/data; python handoff_tidy.py --task test_handoff_fix_20260823` + `Select-String "^## data$"` | `## data` 出现 0 次 | - | - |
| AC-003 | `python memory_distill.py distill --project 精诚养车县级通报名情况` / `一般-异常工单抢修分析-AI处理` | 各报 `经验库总数: 0` | - | - |
| AC-004 | `Rename-Item` 双份 + `python validate_skill.py` | 32/32 PASS、MUST FIX=0 | - | - |
| AC-005 | `cd ~/.pdca-skill/data; python learn_tidy.py scan --dry-run` | global_total ≥ 150、layer_consistency ≠ 0 | - | - |
| AC-006 总回归 | validate_skill + learn_tidy scan + git log | 双回归通过 + 5 commit | - | - |
| AC-007 Git 留痕 | `git log -n 5 --pretty=%s` | 5 条 fix(v103t3) 标题 | - | - |
| AC-008 备份完整 | 备份前后 sha256 对比 | 5/5 一致 | - | - |

---

## 视觉/浏览器发现

N/A（CLI 脚本任务，无视觉产出）。

---

## Self-Review 自检清单【交你前必须过一遍】

| # | 检查项 | 通过？ |
|---|--------|--------|
| 1 | 占位符扫描：没有TBD/TODO/适当/必要/类似/后面再说等模糊词？ | ✓ |
| 2 | 内部一致性：前后术语、命名、方案没有矛盾？ | ✓ |
| 3 | 范围检查：没有加你没要求的额外内容？ | ✓（5 修复 + 备份 + 收尾，无 #6） |
| 4 | 歧义检查：没有一句话能理解成两种意思的描述？ | ✓ |
| 5 | 验证步骤：每个 task 都有具体的"怎么验证"+预期结果？ | ✓ |
| 6 | 边界条件：每个 task 都列出了正常路径和边界/异常路径？ | ✓ |
| 7 | 验收标准：每个 task 的验收标准都是 GWT、可测量？ | ✓ |
| 8 | No Placeholders：所有代码是完整可运行的，没有伪代码/省略号？ | ✓ |
| 9 | 12 字段齐全：每个 T00X 都含 GWT + 不通过处理 + 改动白名单 + 反向验证 + 防作弊 + 死规矩 + 依赖排序 + 防幻觉？ | ✓ |
| 10 | 闸门 1-7 检查项已预留位置？ | ✓ |

---

## 阻塞与备注

- 暂无阻塞。HARD-GATE 待用户确认后才进 /do。
- 提醒：用户原话"我在另外一台蒸馏记忆，也是针对这个skill"——本机是主开发机（v1.0.3 commit 3cb5f65），源机是 v1.0.1；diff 已在 /plan 完成，5/5 仍存在。

---

## 任务格式说明

**格式**: `- [ ] [TaskID] [P?] [Story?] Description with file path`

| 组件 | 必填？ | 说明 |
|------|--------|------|
| `- [ ]` | 是 | 复选框，标记完成状态 |
| `T00X` | 是 | 任务ID，顺序递增 |
| `[P]` | 否 | 可并行执行时添加（本任务 5 修复可并行，但 T000 必须先） |
| Description + 文件路径 | 是 | 描述必须带具体文件路径 |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-08-23 23:02 | 初版（T000~T007 + 8 AC + 12 字段全填） |

# riji-skill

> AI 协作框架——每次对话自动加载，所有场景生效。从一句话问答到完整项目开发，涉及任务管理、文档规范、代码协作、需求澄清、验收标准时自动触发。

## 先说痛点：你请的 AI 助手，为什么需要"规矩"？

你让 AI 干活，最怕三件事：**没问清就动手**（做偏了返工）、**改着改着改崩了**（还找不回上一版）、**聊着聊着它"忘了"之前定好的事**（上下文一压缩就失忆）。这些问题通常不是你没说清，而是 AI 默认"凭记忆裸奔"的毛病。

riji-skill 就是给 AI 套上的**一套协作规矩 + 一本随查手册**：把反复踩过的坑固化成硬规则，让 AI 每次动手前先确认、出错时有章法可调、记忆有地方存。

但记忆不只是防失忆——你在 AI 协作上踩过的坑、验证过的方法、做过的关键决策，是越用越厚的**个人资产**，跨项目跨工具都跟你走。riji-skill 的三层记忆系统，本质是你的"AI 协作方法论笔记本"，**经验沉淀**（验证过的方法论、踩过的坑、关键决策）+ **状态记忆**（任务进度、上下文、卡点）两个分量都有——AI 是流水的兵，记忆是铁打的营盘。

## 三个定位：记忆 → PDCA → docs（三位一体闭环）

riji-skill 不是平级三件套，而是**层级 + 闭环**——三个定位互锁，形成核心架构：

```
① 记忆（基础·个人资产·跟人不跟工具）
   ↓ 撑起（记忆是 PDCA 的输入/输出物质）
② PDCA（主干·思维方法论 + 统一调度中枢）
   ↓ 产出（/plan 产 spec/task、/act 产 memory/handoff）
③ docs（产出·物质载体·工程化管理方法）
   ↓ 反哺（docs 持久化记忆，喂下一轮 /plan）
① 记忆（/act 写 memory = 下一轮 /plan 输入）→ 闭环
```

- **记忆**：跟随你本人（不跟项目、不跟工具）的个人资产——经验沉淀（做过什么、学到什么）+ 状态记忆（做到哪、卡在哪）两个分量持续积累，越用越厚。AI 是流水的兵，记忆是铁打的营盘
- **PDCA**：既是解决问题的思维方法论，又是统一调度中枢——所有能力归一到 /plan /do /check /act 四指令
- **docs**：把 AI 协作从"聊完就散"升级为可追溯/可交接/可复用的工程化方法——spec（方案）+ task（执行清单）+ handoff（交接记录）+ memory（结构化记忆），每次协作成果都变成文件留下来。riji-skill 自身就是这套方法搭出来的活样本

## 这个技能是干嘛的（大白话版）

把 riji-skill 想成 AI 助手的**「协作宪法 + 交通指挥中心」**：

- **宪法**——规定 AI 干活时必须遵守的硬规则（先读记忆再动手、动手前必须跟你确认方案、不给半成品伪代码、报错就读调试手册……），防止"AI 凭印象乱改 → 改崩 → 上下文丢了 → 来回返工"。
- **指挥中心**——它自己**不实现**具体业务能力（不会去画界面、做表格、跑爬虫），而是内置一张"触发钩子表"：你一说什么，它就知道该去读哪份参考手册、或该去外部调度哪个专业技能。

一句话：**riji-skill 管"怎么协作得靠谱"，具体活儿交给它调来的专业模块/外部技能干。**

## 你需要知道的前提（2 条）

1. **它得跑在一个能调用大模型的 AI 助手上**（如 WorkBuddy）。框架是"规矩"，模型是"脑子"——脑子在内网要有内网版模型才能完全离线跑。
2. **框架本身零云依赖、纯本地文件**：不联网、不调外部 API。内网部署 = 把整个目录拷贝过去即可，比那些依赖云端的技能省心。
   > 补充：画图 / Excel / 爬虫等"具体活"要靠外部专业技能，那些技能各自可能有云依赖——这是技能自己的事，不传染框架。

## 一天里它怎么帮你（一个真实例子）

你说："帮我写个用户登录功能。"

- **没有框架**：AI 可能直接噼里啪啦写代码，写成啥样你不清楚，改崩了难回退。
- **有 riji-skill**，AI 会：① **先澄清**（账号密码还是手机验证码？要记住登录状态吗？）——动手前先对齐；② **读规矩**（自动读 `code_rules.md` 按统一风格写、`security.md` 防 SQL 注入）；③ **留后路**（改之前先提交检查点，真改崩了一键回退）；④ **写文档**（顺手生成 spec 方案 + task 步骤 + handoff 交接）；⑤ **记下来**（约定写进记忆，下次接着聊不"失忆"）。

你感受到的差别：它**先问清楚再干、干得有规矩、出问题能回退、事后有文档**，而不是甩给你一堆代码。

## 它是什么 / 它不是什么

| ✅ 它是 | ❌ 它不是 |
|--------|----------|
| 一套**跨任务硬规则** + 按需加载的**参考手册** | 一个把几十个技能"打包塞进自己体内"的大杂烩 |
| **技能编排器**：需要时去外部找/调专业技能 | 自带具体业务能力的"万能工具箱"（如画图、Excel） |
| 纯本地 Markdown，零云依赖，内网可直接拷贝部署 | 依赖外部 API/账号才能跑的在线服务 |

> 数量澄清：包内**内嵌 41 个参考模块**（`references/`），但**0 个独立子技能**（没有 `skills/` 子目录）。需要浏览器操控、Office、金融等专业能力时，它通过 `skill_management` / `agent_find` 两个钩子去**外部**搜索并调度对应技能——那些技能不在包里。

## 核心能力

| 能力 | 说明 |
|------|------|
| **PDCA 四环统一调度中枢** | 所有能力归一到 /plan（想清楚）/ /do（动手做）/ /check（验结果）/ /act（处理动作：交接+记忆+learn 门控自进化）四个入口指令。/loop 是 /do+/check 自动循环模式开关。/act 产出 = 下一轮 /plan 输入，形成闭环。记忆系统、副 agent 调度、文档三件套、/loop 循环、learn 自进化、handoff_tidy、触发钩子、第一性原理拆解、对抗性审查、用户数据外置、Bootstrap 初始化、Git 回溯保障、SUMMARY 根索引、Red Flags、安全处理、手绘呈现、agent-find 都通过 PDCA 触发，**用户只需记 4 个词就能调度框架全部能力** |
| **7条铁律** | Memory First（先读记忆再动手）、HARD-GATE（方案确认后才动手）、流程优先（先判断走什么流程）、No Placeholders（不给伪代码/TBD）、触发钩子（报错按报错询问机制确认用户意图再决定是否读 debugging、写代码读 code_rules）、回溯保障（改前确保工作区干净可回退）、逐项核对（执行阶段按 task.md 逐项完成验证打勾，验收阶段对照 spec.md 逐条核对） |
| **第一性原理拆解** | 复杂任务方案探索前必做三问：本质目标是什么？不可压缩的约束有哪些？从约束出发的最优解是什么？避免照搬已有方案 |
| **对抗性审查** | Self-Review 后用独立 subagent 做 6 维度批判性审查（内部一致性/逻辑完整性/可执行性/边界 case/安全性/可维护性），产出 HIGH/MEDIUM/LOW 分级报告，修复后迭代直到清零，3 轮上限防无限循环 |
| **安全 HIGH 特殊处理** | 安全漏洞（SQL 注入/权限越界/数据泄露等）触发独立处理流程：判定权三级（用户>主 agent>subagent）、优先修复+延后非安全、X/Y 双计数器（正常轮次 X≤3、安全轮次 Y≤4）、回归验证轮、链式新安全 HIGH 递增规则、Y=4 升级用户决策 |
| **文档三件套** | spec（方案）、task（执行清单）、handoff（交接记录）自动生成。把 AI 协作从"聊完就散"升级为**可追溯/可交接/可复用**的工程化方法——`generate_docs.py` 一键创建目录结构。**riji-skill 自身**（SKILL.md + 36 references + 12 模板 + 32 脚本 + SUMMARY）就是用这套方法搭出来的活样本 |
| **三层记忆系统** | 热记忆（SKILL.md+references，硬性，每次自动加载）、全局聚合记忆（`memory/memory_main.md`，skill 包内，按项目分段）、项目记忆（`{项目根}/docs_rj/memory_rj/`）；写入即落盘并自动 upsert 全局 |
| **用户数据外置（方案B）** | 用户数据（memory/docs_rj/outputs_rj/server_lite_data）外置到 `~/.riji-skill/data/`，与框架文件物理分离。**升级时解压覆盖框架文件，用户数据 0 丢失**。三级优先级路径解析（环境变量 `RIJI_DATA_DIR` > 配置文件 `~/.riji-skill/config.json` > 默认值），老用户首次启动自动迁移。`server_lite_data/` 为框架自动创建的占位目录（server_lite 当前不主动引导使用，见下文说明） |
| **命名空间隔离** | 所有运行时产物加 `_rj` 后缀（`docs_rj/`、`memory_rj/`、`_rj` 类型文件夹），避免与其他 agent 平台通用命名撞车 |
| **Bootstrap 初始化** | 首次使用检测缺失文件，逐个确认创建，引导填写主 docs 路径等配置 |
| **Git 回溯保障** | 代码改动前检查点、任务级回溯检查点、紧急回滚 SOP，确保改崩了能回到稳定状态；复杂任务启动先问 Git 管理（2 问 + 3 默认值，见 git_workflow §6.5），简单任务轻量检查 |
| **agent-find 动态搜索** | 需要第三方 agent/能力时优先用 Exa REST API 直连全网搜索（绕开 MCP/OAuth；MCP 作可选上层，都不可用才降级 WebFetch/WebSearch），零系统依赖跨平台可用，安装前安全扫描 |
| **SUMMARY_RJ.md 根索引** | 文档汇总视图一眼看全项目结构，自动更新+漂移检查，替代 CLI 工具零依赖 |
| **Red Flags 16 条** | 偏离信号自检：连续输出未确认、没过 HARD-GATE 就动手、凭记忆回答不读文件等，出现信号立即重读铁律 |
| **手绘呈现（hand-drawn-report）** | 验收/审核/汇报时内容→手绘 SVG 速记/信息图，单文件自包含；md 顶部内联同款 SVG |

## 参考手册（references/）—— 41 个按需读取模块

不全部加载到上下文，触发钩子按"你正在做什么"自动指引读取。按使用场景分 7 类：

**① 写代码 / 改代码时**
| 文件 | 用途 |
|------|------|
| [code_rules.md](references/do/code/code_rules.md) | 代码风格/结构/错误处理/测试/API/数据库/安全规范 |
| [design_patterns.md](references/plan/design/design_patterns.md) | 6 种设计模式应用指南 |
| [project_structure.md](references/plan/design/project_structure.md) | 标准项目结构/模块划分/配置管理 |
| [git_workflow.md](references/do/code/git_workflow.md) | Git 分支策略/Commit 规范/回溯保障/回滚 SOP |

**② 出错 / 调试时**
| 文件 | 用途 |
|------|------|
| [debugging.md](references/common/dc/debugging.md) | 报错时的四步调试法 |
| [red_flags.md](references/check/red_flags.md) | 16 条偏离信号 + 理性化反驳（自检"是不是偏了"） |

**③ 写文档 / 出报告时**
| 文件 | 用途 |
|------|------|
| [document_specs.md](references/common/pda/document_specs.md) | 文档命名/格式/多 docs 目录处理规范 |
| [hand-drawn-report.md](references/common/da/hand-drawn-report.md) | 手绘呈现（内容→手绘 SVG 速记/信息图） |

**④ 安全 / 合规时**
| 文件 | 用途 |
|------|------|
| [security.md](references/do/danger/security.md) | 安全边界 + 5 层指令优先级 + 注入防御 + **文件扫描确认门控**（L0 任务内免确认 / L1 点名单文件一句话确认 / L2 任务外扫描先确认：范围+目的+关键词） |
| [skill_security.md](references/plan/route/skill_security.md) | 第三方 skill 安全审计规范 |

> 🔴 **隐私声明（v1.0.1）**：框架的「技能图谱」功能（master_graph）会扫描本机 AI 工具记忆目录（`~/.claude`、`~/.cursor`、`%APPDATA%` 等）来生成能力画像。**用户点名/手动全量触发时，该扫描属任务外扫描，运行前会先向你确认**（8 个固定 AI 工具记忆目录为功能核心豁免——你启用该功能即视为授权，见 skill_graph.md §4）；扫描发现的敏感文件内容不会被引用、转述或持久化（敏感行摘录自动过滤）。**每轮 /act 自动刷新（--auto）仅读框架自身记忆（左轨 riji，L0 免确认）**，不扫上述外目录，记忆未变化时零成本跳过。其余功能均只读写框架自身目录与 `~/.riji-skill/data/`（用户数据外置），零云依赖。

**⑤ 记忆 / 交接 / 多项目时**
| 文件 | 用途 |
|------|------|
| [working_memory_rules.md](references/common/pa/working_memory_rules.md) | 记忆读写/归档/跨对话恢复规则 |
| [summary_view.md](references/common/pa/summary_view.md) | SUMMARY_RJ.md 根索引规范 + 漂移检查 |
| [sync-matrix.md](references/common/da/sync-matrix.md) | 变更影响矩阵 + 版本号一致性检查 |
| [multi_project.md](references/plan/bootstrap/multi_project.md) | 多项目切换/隔离规范 |
| [compaction_recovery.md](references/plan/bootstrap/compaction_recovery.md) | 上下文压缩恢复协议（7 步恢复流程） |

**⑥ 要找外部专业能力时（浏览器 / 搜索 / 装技能）**
| 文件 | 用途 |
|------|------|
| [browser_automation.md](references/do/code/browser_automation.md) | 浏览器操控/自动化（选型对比 + 落地步骤） |
| [agent_find.md](references/plan/route/agent_find.md) | 第三方 agent/能力 搜索/安装/验证流程 |
| [skill_management.md](references/plan/route/skill_management.md) | Skill 搜索→安装→验证→安全扫描全流程 |

**⑦ 初始化 / 审查 / 示范时**
| 文件 | 用途 |
|------|------|
| [bootstrap.md](references/plan/bootstrap/bootstrap.md) | 引导式初始化流程（首次使用） |
| [adversarial_review.md](references/common/pc/adversarial_review.md) | 第一性原理拆解 + 对抗性审查完整规则 |
| [communication_rules.md](references/common/dc/communication_rules.md) | 沟通四原则 + 文件变动声明 |
| [usage_examples.md](references/plan/route/usage_examples.md) | 3 段真实对话演示完整流程 |

## 模板文件（assets/）—— 12 个开箱即用

spec / task / handoff / memory / memory_bootstrap / daily_log / summary / archive / market_research / spec_main / skill_graph / index 十二类模板，配合 `generate_docs.py` 自动生成。

## 安装

### 方式一：复制到 skills 目录

将 `riji-skill/` 整个目录复制到你的 AI 编程助手的 skills 目录下即可。

### 用户数据外置（重要）

riji-skill 采用**用户数据外置方案**：你的记忆、文档、输出等数据放在 `~/.riji-skill/data/`（与框架文件物理分离），**不在 skill 包内**。

**为什么这样设计**：每次发布新版 skill 包，你只需解压覆盖框架文件，**用户数据 0 丢失**——再也不用担心升级覆盖丢数据。

**数据目录结构**（首次启动自动创建）：

```
~/.riji-skill/
├── config.json              # 路径配置（可选，不存在则用默认值）
└── data/
    ├── memory/              # 全局聚合记忆（memory_main.md）
    ├── docs_rj/             # 项目文档（spec/task/handoff/memory）
    │   ├── memory_rj/
    │   ├── spec_rj/
    │   ├── task_rj/
    │   └── SUMMARY_RJ.md
    ├── outputs_rj/          # 输出产物
    └── server_lite_data/    # 框架自动创建的占位目录（server_lite 数据，当前不主动引导使用）
```

**三级优先级路径解析**（从高到低）：

1. **环境变量** `RIJI_DATA_DIR`（临时覆盖，如 `set RIJI_DATA_DIR=D:\my-riji-data`）
2. **配置文件** `~/.riji-skill/config.json` 的 `data_dir` 字段（持久化自定义路径）
3. **默认值** `~/.riji-skill/data/`（推荐，零配置）

**老用户升级**：如果你之前用的是包内数据（旧版本），首次启动新版会**自动迁移**包内数据到外置目录，迁移成功后包内的旧数据目录可安全删除。迁移是原子操作（复制成功才删除源），支持并发锁（防多实例冲突），7 天回滚窗口。

**server_lite 说明**：server_lite（日积面板）是已完整实现但不主动引导使用的可选组件——功能与 AI 对话定位重叠，当前版本不再引导用户启动。代码保留供未来扩展或用户主动启用，如需使用：`python run_server.py` 启动后访问 http://127.0.0.1:5210。`server_lite_data/` 目录由框架自动创建作为占位，即使不启用 server_lite 也无负面影响。

### 首次使用

第一次对话时，框架会自动检测缺失文件并引导 Bootstrap 初始化（同时自动创建外置数据目录 `~/.riji-skill/data/`），按提示确认创建即可。

### 验证安装

完成目录复制后，建议在 `riji-skill/` 项目根目录（包含 `SKILL.md` 的目录）下运行以下命令，确认安装完整、脚本可执行。所有命令仅使用 Python 标准库，无第三方依赖（测试套件需要 pytest）。

#### 环境前置检查

| 项 | 要求 | 检查命令 |
|----|------|---------|
| Python 版本 | 3.9 及以上 | `python --version` |
| 操作系统 | Windows / macOS / Linux 均可 | — |
| 当前目录 | 必须在 `riji-skill/` 项目根 | Windows：`cd`（无参数）；macOS/Linux：`pwd` |
| pytest（仅测试验证需要） | 任意现代版本 | `python -m pytest --version` |

检查 Python 版本：

```bash
python --version
```

预期输出：

```text
Python 3.9.x  或更高版本（如 Python 3.10.x / 3.11.x / 3.12.x）
```

> Windows 用户用 `python`；macOS/Linux 用户若默认 `python` 指向 Python 2，请改用 `python3`。

#### 基础验证命令

以下 5 条命令覆盖核心脚本，在项目根执行。**成功标志：退出码 0 且汇总行显示"失败 0"**。

**① 项目结构守卫 — startup_tidy**

```bash
python scripts/startup_tidy.py --dry-run
```

预期输出（stdout 输出 JSON 报告，stderr 输出日志）：

```text
{
  "mode": "dry-run",
  "status": "ok",
  ...
}
```

- 成功标志：退出码 0；JSON 中 `status` 字段为 `"ok"`；无 `[BLOCKER]` 级别问题
- `[WARN]` 级别警告（如归档类提示）可忽略
- 若报 `[BLOCKER] SUMMARY_RJ.md 缺失`，加 `--create-summary` 参数引导创建

**② 技能验证 — validate_skill**

```bash
python scripts/validate_skill.py
```

预期输出（关键标志）：

```text
[SCR-01] ... : PASS
[SCR-02] ... : PASS
...
全部检查通过 (N/N)
```

- 成功标志：退出码 0；末尾汇总"全部检查通过"；所有 `[SCR-XX]` 项均为 `PASS`
- 检查范围：scripts/ 完整性、references/ 引用、generate_docs.py 可调用性等

**③ 全局文件验证 — validate_global_files**

```bash
python scripts/validate_global_files.py
```

预期输出（关键标志）：

```text
共 N 文件 / 验证 N / 通过 N / 失败 0
```

- 成功标志：退出码 0；汇总行 `失败 0`
- 检查范围：SKILL.md / README.md / HISTORY.md / memory/memory_main.md / protocol/*.py 等全局关键文件的存在性与格式

**④ 路由检查 — route_check**

```bash
python scripts/route_check.py
```

预期输出（关键标志）：

```text
共 N 条 / 通过 N / 失败 0
```

- 成功标志：退出码 0；汇总行 `失败 0`
- 默认检查脚本上级目录（即仓库根）；如需指定其他目录，加 `--skill-dir <路径>`
- 检查范围：触发钩子表、references 索引、`protocol/routing.py` 路由层一致性

> ⚠️ 本脚本不支持位置参数（不要写 `route_check.py .`），默认即检查仓库根目录。

**⑤ 协议对齐 — protocol_align**

```bash
python scripts/protocol_align.py
```

预期输出（关键标志）：

```text
共 N 条 / 通过 N / 失败 0
```

- 成功标志：退出码 0；汇总行 `失败 0`
- 检查范围：`protocol/` 包常量与 SKILL.md / references 的字段约定对齐

#### 测试验证

运行 pytest 测试套件（覆盖负向测试 + 协议对齐 + 扫描确认门控 + 技能图谱修复 + 交接 4 闸门，共 202 个测试用例，201 passed + 1 skipped，详见 HISTORY.md 2026-08-06）：

```bash
python -m pytest tests/ -v
```

预期输出（关键标志）：

```text
========================= test session starts =========================
platform ... -- Python 3.9.x, pytest-x.x.x, ...
rootdir: .../riji-skill, configfile: tests/pytest.ini
collected 202 items

tests/test_negative_cases.py::test_no_circular_imports PASSED                [  5%]
tests/test_negative_cases.py::test_no_personal_paths PASSED                  [ 11%]
tests/test_negative_cases.py::test_no_dead_references PASSED                 [ 17%]
tests/test_negative_cases.py::test_protocol_importable_without_errors PASSED [ 23%]
tests/test_protocol_align.py::test_extract_traceability_sources_returns_valid_dict PASSED [ 29%]
tests/test_protocol_align.py::test_extract_traceability_sources_handles_missing_docstring PASSED [ 35%]
tests/test_protocol_align.py::test_check_alignment_returns_correct_structure PASSED [ 41%]
...（参数化测试用例，共 202 项）
========================= 201 passed, 1 skipped in ~30s ==========================
```

- 成功标志：退出码 0；末尾 `201 passed, 1 skipped`；无新增 `FAILED` 字样
- 实际耗时与版本号会因环境而异，关键看 `passed` 数量与退出码

> Windows 用户也可一键运行：`tests\run_tests.cmd`（等价于 `python -m pytest tests/ -v`）。

#### 当前版本已知状态

当前版本 `validate_skill.py` 32/32 项通过（FAIL=0，MUST FIX=0），pytest 测试套件 202 项中 201 项通过 + 1 skipped，无本版本引入的已知失败项。

#### 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| `python: command not found` | Python 未安装或未加入 PATH | 安装 Python 3.9+ 并勾选 "Add to PATH"；macOS/Linux 用 `python3` |
| `ModuleNotFoundError: No module named 'pytest'` | 未安装 pytest | `python -m pip install pytest` |
| `can't open file 'scripts/xxx.py'` | 当前目录不对 | `cd` 到 `riji-skill/` 项目根再执行（须包含 `SKILL.md` 和 `scripts/`） |
| `startup_tidy` 报 `[BLOCKER] SUMMARY_RJ.md 缺失` | 项目首次使用未初始化 | `python scripts/startup_tidy.py --dry-run --create-summary` 引导创建 |
| `startup_tidy` 输出乱码或 JSON 解析失败 | Windows 控制台编码问题 | 执行 `chcp 65001` 切换为 UTF-8；或改用 PowerShell 7+ |
| `validate_skill` 报 SCR-10 缺少版本号引用块 | 部分 `references/*.md` 未补版本号标记 | 属已知待办，可忽略；或手工在文件头部补版本号引用块 |
| `validate_global_files` 全部失败 | 项目根路径检测异常或核心文件缺失 | 确认在项目根执行；重新完整复制 `riji-skill/` 目录 |
| `route_check` 报 `unrecognized arguments: .` | 误传了位置参数 | 本脚本不支持位置参数，去掉 `.`；默认检查仓库根；如需指定目录用 `--skill-dir <路径>` |
| `route_check` 报 `protocol/routing.py 不存在` | protocol/ 包缺失 | 重新完整复制 `riji-skill/protocol/` 目录 |
| pytest 报 `configfile: pytest.ini not found` | 当前目录不对 | `cd` 到项目根；`tests/pytest.ini` 会自动加载 |
| pytest 报 `No module named 'protocol'` | protocol/ 包未正确复制 | 确认 `protocol/__init__.py` 存在；重新复制 `protocol/` 目录 |
| 中文输出乱码 | Windows 控制台编码问题 | `chcp 65001` 切换 UTF-8，或改用 PowerShell；重定向到文件时用 `Out-File -Encoding utf8` |

通过以上全部验证（或仅核心命令通过 + pytest 201 项全过）后，即可确认 riji-skill 安装完整、可正常使用。下一步可参考下方"快速上手"开始第一次对话。

## 可选配置项

riji-skill **默认零配置即可运行**——所有外部搜索能力都有降级链（API 不可用时退回 WebSearch）。但配置以下任一项，对应能力会从"降级模式"升级到"完整模式"。

**配置总览**：

| # | 配置项 | 用途 | 不配的后果 | 配置难度 |
|---|--------|------|-----------|---------|
| 1 | `EXA_API_KEY` | Exa REST API 全网语义搜索（`agent-find` 钩子用） | 退回 WebSearch 兜底，精准度下降 | ⭐⭐ 简单 |
| 2 | `GITHUB_TOKEN` | `find_similar.py` 搜 GitHub 仓库（`/plan` 步骤 4a.3 用） | API 限流 60次/小时，常返回 0 条 | ⭐⭐ 简单 |
| 3 | `GITEE_TOKEN` | `find_similar.py` 搜 Gitee 仓库（`/plan` 步骤 4a.3 用） | API 限流较紧，常返回 0 条 | ⭐⭐ 简单 |
| 4 | `RIJI_DATA_DIR` | 用户数据外置路径覆盖（默认 `~/.riji-skill/data/`） | 用默认路径，无影响 | ⭐ 极简 |

> **建议**：① Exa（最常用，全网搜索）→ ② GitHub Token（搜代码仓库）→ ③ Gitee Token（国内源）→ ④ RIJI_DATA_DIR（仅自定义路径才配）。**全部可选，按需配**。
>
> **此外还有 3 项运行时配置**（非环境变量，是脚本参数/文件字段，见下方 ⑤ 运行时配置（可选）章节）：`find_similar.py` 命令行参数、server_lite 端口、`/loop` 最大迭代次数。默认值都能跑，仅调整行为时才改。

---

### ① 配置 Exa 搜索（`EXA_API_KEY`）

**用途**：`agent-find` 能力（找 skill / 找 agent / 找工具 / 找 MCP server / 查开源项目）默认优先走 **Exa REST API 直连**做全网语义搜索，精准度远高于普通搜索引擎。不配则降级走 WebSearch。

**两种配置方式（任选其一）**：

#### 方式 A：环境变量（推荐，跨平台）

1. 去 [dashboard.exa.ai](https://dashboard.exa.ai) 注册账号 → 申请 API Key（免费额度足够日常使用）
2. 复制 key（格式类似 `xxxx-xxxx-xxxx-xxxx`）
3. 设置环境变量：

| 平台 | 命令 |
|------|------|
| **Windows（永久）** | PowerShell：`[System.Environment]::SetEnvironmentVariable("EXA_API_KEY", "你的key", "User")` |
| **Windows（临时）** | CMD：`set EXA_API_KEY=你的key` |
| **macOS / Linux** | `echo 'export EXA_API_KEY="你的key"' >> ~/.bashrc && source ~/.bashrc`（zsh 用户改 `~/.zshrc`） |

4. **重开终端**后生效

#### 方式 B：`exa.env.json` 文件（项目本地）

1. 复制模板：`cp exa.env.json.example exa.env.json`
2. 编辑 `exa.env.json`，把 `YOUR_EXA_API_KEY_HERE` 换成你的 key：

```json
{
  "EXA_API_KEY": "你的真实key"
}
```

3. **确认 `.gitignore` 已包含 `exa.env.json`**（防止误提交到 git）：

```bash
# 在项目根运行，应输出 exa.env.json
grep "exa.env.json" .gitignore
```

> 脚本会自动探测多个候选位置：当前目录 / `../` / `../../` / `~/.agent/skills/riji-skill/` / `~/.workbuddy/skills/riji-skill/`，都找不到再退回环境变量。

#### 验证

```bash
# 设置后新开终端，运行（应能正常返回搜索结果 JSON）
python -c "import os; print('EXA_API_KEY 已设置' if os.environ.get('EXA_API_KEY') else '未设置')"
```

#### Exa MCP（可选上层，无需 key）

若你的客户端**已配置 Exa MCP**（OAuth 免 key），可改用 MCP 工具 `web_search_exa` / `web_fetch_exa`，省去读 key 步骤。配置：

```json
{
  "mcpServers": {
    "exa": { "url": "https://mcp.exa.ai/mcp" }
  }
}
```

首次连接时在浏览器登录一次即可使用。**与 REST API 是两套独立鉴权体系**（MCP 走 OAuth，REST 用 `x-api-key` 头），二者选其一。

#### 安全注意

- ❌ **不要提交到 git**：`exa.env.json` 必须在 `.gitignore` 中
- ❌ **不要打包进分发的 zip**：`package_skill.py` 已自动排除
- ❌ **不要复用他人 key**：每个用户申请自己的
- ✅ **定期更换**：建议 90 天到期重新生成
- ✅ **泄露处理**：立即去 [dashboard.exa.ai](https://dashboard.exa.ai) 撤销并重新生成

---

### ② 配置 GitHub Token（`GITHUB_TOKEN`）

**用途**：`/plan` 步骤 4a.3 跑 `python scripts/find_similar.py scan` 搜 GitHub 仓库时用。不配 → 限流 60次/小时（约1次/分钟），常被限返回 0 条；配了 → 5000次/小时，稳定返回真实结果。

**获取步骤**：

1. 浏览器打开 https://github.com/settings/tokens?type=beta （Fine-grained，官方推荐）
2. 点 **Generate new token** → **Generate new fine-grained token**
3. 填写：
   - **Token name**：`find-similar-riji-skill`
   - **Expiration**：90 天（到期再生成）
   - **Repository access**：选 **Public Repositories (read-only)**（只读公共仓库，最小权限）
   - **Permissions**：保持默认（搜索 API 不需要额外权限）
4. 点 **Generate token** → **立即复制**（只显示一次！格式类似 `github_pat_xxxx...`）

**设置环境变量**：

| 平台 | 命令 |
|------|------|
| **Windows（永久）** | PowerShell：`[System.Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "github_pat_xxxx", "User")` |
| **Windows（临时）** | CMD：`set GITHUB_TOKEN=github_pat_xxxx` |
| **macOS / Linux** | `echo 'export GITHUB_TOKEN="github_pat_xxxx"' >> ~/.bashrc && source ~/.bashrc` |

**验证**：

```bash
# 重开终端后运行
python scripts/find_similar.py scan --task "PDF解析" --keywords "PDF,解析" --min-stars 5
# 看到 "[find_similar] 搜索 GitHub... -> N 条结果"（N>0）即生效
```

**安全注意**：

- ❌ **不要提交到 git**：token 只存环境变量，不写进任何文件
- ✅ **最小权限**：只勾 `Public Repositories (read-only)`，不要勾 `repo` 全权限
- ✅ **定期更换**：90 天到期重新生成
- ✅ **泄露处理**：立即去 https://github.com/settings/tokens 撤销（Revoke）

---

### ③ 配置 Gitee Token（`GITEE_TOKEN`）

**用途**：`/plan` 步骤 4a.3 跑 `find_similar.py scan` 搜 Gitee 仓库（国内 skill 源）时用。不配 → 限流较紧常返回 0 条；配了 → 稳定返回结果。

**获取步骤**：

1. 浏览器打开 https://gitee.com/profile/personal_access_tokens
2. 点 **生成新令牌**
3. 填写：
   - **名称**：`find-similar-riji-skill`
   - **有效期**：90 天
   - **权限**：只勾 `projects`（仓库读取，最小权限）
4. 点 **提交** → **立即复制**（格式类似 `xxxxxxxxxxxxxxxxxxxx`）

**设置环境变量**：

| 平台 | 命令 |
|------|------|
| **Windows（永久）** | PowerShell：`[System.Environment]::SetEnvironmentVariable("GITEE_TOKEN", "gitee_xxxx", "User")` |
| **Windows（临时）** | CMD：`set GITEE_TOKEN=gitee_xxxx` |
| **macOS / Linux** | `echo 'export GITEE_TOKEN="gitee_xxxx"' >> ~/.bashrc && source ~/.bashrc` |

**验证**：

```bash
# 重开终端后运行
python scripts/find_similar.py scan --task "PDF解析" --keywords "PDF,解析" --min-stars 5
# 看到 "[find_similar] 搜索 Gitee... -> N 条结果"（N>0）即生效
```

**安全注意**：

- ❌ **不要提交到 git**：token 只存环境变量
- ✅ **最小权限**：只勾 `projects`，不要勾 `user_info` / `emails` 等
- ✅ **定期更换**：90 天到期重新生成
- ✅ **泄露处理**：立即去 https://gitee.com/profile/personal_access_tokens 撤销

---

### ④ 配置用户数据路径（`RIJI_DATA_DIR`，可选）

**用途**：覆盖默认用户数据路径 `~/.riji-skill/data/`。仅在你想把数据放到其他位置（如 D 盘、移动硬盘、网络盘）时才配。**不配 = 用默认路径，无任何影响**。

**三级优先级**（从高到低）：

1. **环境变量** `RIJI_DATA_DIR`（临时覆盖）
2. **配置文件** `~/.riji-skill/config.json` 的 `data_dir` 字段（持久化自定义路径）
3. **默认值** `~/.riji-skill/data/`（推荐，零配置）

**设置环境变量（临时覆盖）**：

| 平台 | 命令 |
|------|------|
| **Windows** | CMD：`set RIJI_DATA_DIR=D:\my-riji-data` |
| **macOS / Linux** | `export RIJI_DATA_DIR=/path/to/my-riji-data` |

**持久化配置（推荐）**：

编辑 `~/.riji-skill/config.json`（不存在则创建）：

```json
{
  "data_dir": "D:/my-riji-data"
}
```

> 路径分隔符：Windows 用 `/` 或 `\\`（不要用单个 `\`，JSON 会转义错）。

**验证**：

```bash
python -c "from scripts.user_data_path import get_user_data_dir; print(get_user_data_dir())"
# 输出你配置的路径即生效
```

**安全注意**：

- ✅ **路径权限**：确保目标路径当前用户有读写权限
- ✅ **不要指向网络盘根目录**：建议指向网络盘下的子目录（如 `Z:/riji-data/`，不要直接 `Z:/`）
- ✅ **跨平台路径**：Windows 用 `/` 或 `\\`，macOS/Linux 用 `/`

---

### ⑤ 运行时配置（可选）

以下配置不是环境变量，而是脚本命令行参数或文件内字段，**不配也能用默认值跑**，仅在你需要调整行为时改。

#### 5.1 `find_similar.py` 命令行参数

`/plan` 步骤 4a.3 跑外部资源搜索时用的脚本，配了 `GITHUB_TOKEN` / `GITEE_TOKEN` 后才会真正返回结果。

**`scan` 子命令参数**：

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `--task` | ✅ 是 | — | 任务描述（写入输出文件名，如 `PDF解析`） |
| `--keywords` | ❌ 否 | 从 `--task` 自动提取 | 搜索关键词，逗号分隔（如 `PDF,解析`） |
| `--min-stars` | ❌ 否 | `5` | 最低 star 数过滤（GitHub/Gitee） |
| `--max-age-days` | ❌ 否 | `365` | 最后更新在 N 天内才算（过滤老项目） |
| `--output` | ❌ 否 | 自动 | 输出 JSON 路径（默认 `docs_rj/spec_rj/find_similar_{task}_{时间戳}.json`） |

**示例**：

```bash
# 最简用法（--keywords 从 --task 自动提取）
python scripts/find_similar.py scan --task "PDF解析"

# 自定义关键词 + 过滤条件
python scripts/find_similar.py scan --task "PDF解析" --keywords "PDF,解析" --min-stars 10 --max-age-days 365

# 列出所有配置的搜索源（无需参数）
python scripts/find_similar.py list
```

> 不配 token 也能跑，但 GitHub/Gitee API 限流常返回 0 条；配了 token 才稳定返回真实结果。

#### 5.2 server_lite 端口（PORT=5210）

server_lite（本地看板）默认端口 **5210**，启动后访问 http://127.0.0.1:5210。

**改端口方法**（两种，任选其一）：

| 方式 | 操作 | 说明 |
|------|------|------|
| 改配置文件（推荐） | 编辑 `server_lite/config.py` 第 35 行：`PORT = 5200` | 改一次永久生效，所有启动方式都用这个端口 |
| 改入口脚本 | 编辑 `run_server.py` 第 11 行的 `5210` 数字：`app.run(host="127.0.0.1", port=app.config.get('PORT', 5200), debug=True)` | 仅影响 `python run_server.py` 启动方式；若 config.py 也改了，以 config.py 为准 |

> server_lite 当前为可选组件（不主动引导使用），不启动它就无需关心这个端口。

#### 5.3 `/loop` 最大迭代次数（`max_iterations: 10`）

`/loop` 自动循环模式默认最多迭代 10 次后熔断停下。复杂任务可调高，简单任务可调低。

**配置位置**：在任务 spec.md 文件的 front-matter（顶部 YAML 区块）：

```yaml
---
title: 复杂任务 - 需求规格说明
version: v1.0.0
max_iterations: 15  # 复杂任务调高（默认 10）
---
```

**取值规则**：
- **类型必须 int**：拒绝 bool / 字符串 / 浮点数（`"10"` / `10.0` 都不行）
- **最小值 1**：低于 1 会被拒
- **建议范围**：
  - 简单任务：5-8（快速熔断，避免瞎试）
  - 默认：10
  - 复杂任务：15-20（给足空间，但仍有限制防无限循环）

> 不写这个字段 = 用默认值 10。详见 [references/loop_constraints.md](references/loop_constraints.md)。

---

### 配置项快速排查

如果配了 token 但 `find_similar.py` 仍返回 0 条，按以下顺序排查：

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| `python -c "import os; print(os.environ.get('GITHUB_TOKEN'))"` 输出 `None` | 环境变量未生效 | 重开终端；或检查是否设成了 `Machine` 级但当前用户无权读 |
| `find_similar.py` 报 `401 Unauthorized` | token 失效或错误 | 去 GitHub/Gitee 设置页重新生成 |
| `find_similar.py` 报 `403 Forbidden` | token 权限不足 | 检查 token 权限（GitHub 选 `Public Repositories (read-only)`，Gitee 勾 `projects`） |
| `find_similar.py` 报 `Connection timeout` | 网络不通 | 检查代理/VPN；GitHub 在国内可能需要梯子 |
| Exa 搜索返回空 | key 配置错或额度用完 | 去 [dashboard.exa.ai](https://dashboard.exa.ai) 检查额度；或换 `exa.env.json` 方式重试 |
| `exa.env.json` 被误提交到 git | `.gitignore` 未配置 | `git rm --cached exa.env.json` + 确认 `.gitignore` 含 `exa.env.json` |

> **降级保证**：以上配置**全部不配**也不影响框架核心功能——所有外部搜索都有 WebSearch 兜底，所有用户数据都有默认路径。配置只是"从降级模式升级到完整模式"。

## 目录结构

```
riji-skill/
├── SKILL.md                    # 主入口文件，每次对话自动加载（含 7 铁律 / HARD-GATE / 触发钩子表）
├── README.md                   # 本文件
├── HISTORY.md                  # 版本历史
├── index.html                  # 项目落地页（介绍页）
├── run_server.py               # server_lite 启动脚本（可选组件，当前不主动引导使用）
├── .gitignore
├── .primary_docs_rj            # 主 docs 目录标记
├── assets/                     # 12 个模板文件
│   ├── spec_template.md
│   ├── spec_main_template.md
│   ├── task_template.md
│   ├── handoff_template.md
│   ├── memory_template.md
│   ├── memory_bootstrap_template.md
│   ├── daily_log_template.md
│   ├── summary_template.md
│   ├── archive_template.md
│   ├── market_research_template.md
│   ├── skill_graph_template.md
│   └── index_template.md
├── references/                 # 41 个参考手册（按需读取，见上表）
├── scripts/                    # Python 脚本（协作框架核心 + 用户数据外置 + loop 守卫，共 33 个）
│   ├── archive_tidy.py
│   ├── browser_inspect_docs.py      # 文档浏览器检视辅助
│   ├── check_skill_updates.py
│   ├── commit_lint.py               # Git commit 信息校验
│   ├── commit_lint_install.py       # commit_lint 安装脚本
│   ├── devlog_sync.py
│   ├── find_similar.py              # 外部资源搜索（/plan 步骤 4a.3 用，搜 GitHub/Gitee/国内平台）
│   ├── generate_docs.py
│   ├── generate_host_rules.py
│   ├── git_backup_tidy.py
│   ├── handoff_tidy.py
│   ├── launch_subagent_rj.py
│   ├── learn_tidy.py
│   ├── link_indexer.py
│   ├── loop_admission.py
│   ├── loop_audit.py
│   ├── loop_guard.py
│   ├── memory_distill.py            # 记忆蒸馏/精炼
│   ├── memory_shadow_write.py
│   ├── migrate_user_data.py         # 用户数据迁移（老用户升级自动迁移）
│   ├── package_skill.py             # 发布打包脚本（排除用户数据目录）
│   ├── protocol_align.py
│   ├── route_check.py
│   ├── skill_graph_build.py
│   ├── skill_graph_cluster.py
│   ├── skill_graph_extract.py
│   ├── skill_graph_render.py
│   ├── startup_tidy.py
│   ├── test_loop_admission.py
│   ├── tidy_common.py
│   ├── user_data_path.py            # 三级优先级路径解析 + 安全检测
│   ├── validate_global_files.py
│   └── validate_skill.py
├── server_lite/                # 本地 Web 界面（可选组件，已实现但不主动引导使用）
│   ├── static/                 # 前端文件（index.html/app.js/style.css）
│   ├── tests/                  # server_lite 测试套件（保留，见 server_lite/tests/README.md）
│   ├── api_settings.py         # 数据管理 API（路径查看/修改/迁移）
│   ├── api_knowledge.py
│   ├── api_skills.py
│   ├── api_docs.py
│   ├── app.py
│   └── ...
├── protocol/                   # 文件协议层（字段契约/路由/校验）
├── tests/                      # 测试套件（pytest，202 项）
├── docs_rj/                    # 项目文档（外置后实际在 ~/.riji-skill/data/docs_rj/）
├── memory/                     # 全局聚合记忆（外置后实际在 ~/.riji-skill/data/memory/）
├── outputs_rj/                 # 输出产物（外置后实际在 ~/.riji-skill/data/outputs_rj/）
├── agents_rj/                  # 副 agent 配置
└── evals/
    └── evals.json              # 典型场景测试用例集
```

> **注意**：`docs_rj/`、`memory/`、`outputs_rj/` 在打包发布时会自动排除（由 `package_skill.py` 处理），用户安装后这些目录实际位于 `~/.riji-skill/data/` 下。本地开发环境保留这些目录作为骨架和示例。

## 迭代历程

本框架历经多轮迭代打磨，主要里程碑：

| 阶段 | 核心突破 |
|------|---------|
| 基础框架 | 从 agent.md 转换→自进化引擎→references 多域拆分→思维导图导航→渐进式披露→5 条铁律→evals 测试集 |
| 架构重构 | 移除自进化引擎简化架构→agent-find 内嵌→文档体系三件套→动态搜索→代码规则扩写 9 章→sync-matrix→触发钩子全行扩写→HTML 报告→/plan 硬指令 |
| 硬规则加固 | 文件变动声明→Bootstrap 引导初始化→版本历史外置→Git 回溯保障（第 6 条铁律）→WebFetch 零依赖搜索→SUMMARY_RJ.md 根索引→Phase2 grill-me 审查修复 17H+32M→指令优先级 5 层统一→Memory First 全面修复 |
| 分发适配 | 主 docs 目录概念→散落文档归档→第二轮 grill-me 修复 11H+M→全局去个人化→命名空间隔离（_rj/_RJ 后缀+双读兼容+迁移脚本） |
| 方法论增强 | 第一性原理拆解三问 + 对抗性审查 6 维度迭代流程 + 安全 HIGH 特殊处理 + X/Y 双计数器 + 3 轮上限防无限循环 |
| 对抗审查打磨 | 21 轮独立 subagent 对抗性审查迭代，从 5H+14M 逐轮修复至 HIGH 连续 4 轮清零，最终砍掉追加轮机制（N 计数器），彻底解决"修一个引一个"的循环问题 |

### 关键质量保障

- **21 轮对抗性审查**：每轮由独立 subagent 按 6 维度审查，修复所有 HIGH 和 MEDIUM 级别问题
- **3 个典型场景用例集（evals.json）**：覆盖 handoff_tidy 触发、memory 新路径、changelog 废弃等核心机制
- **HIGH 连续 4 轮清零**：最后 4 轮审查（R18-R21）均无 HIGH 级别问题
- **砍断无限循环根因**：删除追加轮机制（N 计数器），X=3 强制停止，提供"记录到后续版本/重新拆解重审/停止"三选项，从规则层面杜绝无限审查
- **安全 HIGH 处理完备**：5 条客观清单判定、X/Y 双计数器（X≤3 正常轮、Y≤4 安全轮）、混合回滚方案、Y=4 升级路径闭环
- **边界 case 全覆盖**：上下文压缩恢复、跨对话续做、文件读取失败降级（瞬时/永久/部分失败/空文件）、LOW 写入失败降级（临时文件+合并机制）、计数器半成品修复判断

## 快速上手

1. **安装**：将 `riji-skill/` 目录放到你的 AI 编程助手 skills 目录
2. **开始对话**：框架自动加载，首次使用会引导 Bootstrap 初始化
3. **接任务**：框架自动判断任务复杂度，简单任务直接做，复杂任务走 **PDCA 四环**——/plan（想清楚）→ /do（动手做）→ /check（验结果）→ /act（处理动作：交接+记忆+learn 门控自进化）。/act 产出是下一轮 /plan 的输入，**形成闭环**。用户喊 /loop 可启动 /do+/check 自动循环模式
4. **方案确定前**：复杂任务自动做第一性原理拆解三问
5. **Self-Review 后**：大改/复杂任务自动触发对抗性审查
6. **出错时**：框架通过触发钩子表自动指引读对应 reference 文件

## 许可证

Apache-2.0

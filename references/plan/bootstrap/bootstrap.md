<!-- PDCA标签：P.bootstrap -->
<!-- 子标签场景：首次使用/文件缺失/初始化 -->
<!-- 关键词清单：首次使用/初始化/文件不存在/memory不存在/memory_main.md不存在/项目结构缺失/第一次用/新项目/bootstrap/没装过/还没初始化 -->
<!-- 引用范围：main + bootstrap_agent -->

# Bootstrap 引导式初始化
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-24

> 📦 **用户数据外置说明（v1.0.0 新增，v1.0.4 修订）**：跟人走的数据（memory/ outputs_rj/ server_lite_data/）外置到 `~/.pdca-skill/data/`，skill 包纯框架；**跟项目走的 docs_rj 建在项目根**。其中 `server_lite_data/` 为框架自动创建的占位目录（server_lite 当前不主动引导使用，该目录即使为空也无负面影响）。本流程初始化的是**项目根下的 docs_rj 结构**（从 `assets/` 模板复制到项目 `./docs_rj/`），不是包内也不是外置。外置遗留数据按**只读存档**原地保留（不迁移、不续写）。路径解析经 `scripts/user_data_path.py`（三级优先级：环境变量 > 配置文件 > 默认值）。老用户首次启动新版时 `startup_tidy.py` 自动迁移包内数据到外置目录。

> 📖 **什么时候读这个文件**：
> - 首次使用 pdca-skill 时
> - 启动检查（startup_tidy）报告项目结构缺失（docs_rj/memory_rj/ 或 docs_rj 5类 不存在）时
> - 需要创建项目级必需文件时
> - 首次使用需校准 SKILL.md 中的示例绝对路径时（§四 路径校准）
> - 首次使用需引导用户确认用户画像与 Agent 描述时（§五）
> 🔴 **不要在这时候读**：
> - 项目 docs_rj/memory_rj/ 与全局 memory/memory_main.md 已就位且正常工作时

---

## 一、触发时机

Bootstrap 在以下情况自动触发：
1. **首次使用**（启动整理报告项目根 `docs_rj/memory_rj/` 或 `docs_rj` 5类 缺失）
2. **关键文件缺失**（启动检查 §1 步骤3 发现全局/项目记忆缺失）
3. **新项目初始化**（切换项目时目标项目 memory 不存在）

触发信号见 SKILL.md §1 启动检查与触发钩子表。

> 🚦 **前置依赖（报告型守卫）**：启动整理管线（`scripts/startup_tidy.py`）以项目结构完整性为前置——检测 `docs_rj/memory_rj/` + `docs_rj` 5类 + `outputs_rj/` + `.agent/` 是否齐备，**缺失仅报告、绝不静默建**。若结构缺失，先完成本 Bootstrap 引导式创建（含 skill 包 `memory/memory_main.md` 全局聚合落点），再跑启动整理 / 记忆双写（`memory_shadow_write.write_project`），避免写到未初始化的目录。启动整理的守卫只报告清单，交互式初始化仍是首选（不静默创建）。

---

## 二、引导式创建流程【硬性·强制阻断】

### 强制阻断规则【硬性】

若项目 `docs_rj/` 8 要素任一缺失，主 agent **必须停下**走本流程：

- ❌ 不允许"先干活后补建"——这是 Red Flag（违反 Memory First + 违反 SKILL.md §0 启动前置检查）
- ❌ 用户催促不是跳过的理由（Red Flag #6）
- ❌ 跳过本流程 = 违反 SKILL.md §0 启动前置检查硬规则

**8 要素清单**（与 SKILL.md §0 启动前置检查一致）：
1. `.primary_docs_rj` 标记**有效**（项目根；read_primary_docs_marker() 非 None；空/BOM/坏路径=缺失）
2. `docs_rj/` 主目录
3. `docs_rj/spec_rj/`
4. `docs_rj/task_rj/`
5. `docs_rj/handoff_rj/`
6. `docs_rj/archive_rj/`
7. `docs_rj/memory_rj/`
8. `docs_rj/SUMMARY_RJ.md`

### 8 要素统一创建流程

**核心原则**：不静默创建。一次性展示缺失要素清单，用户确认后统一创建（不再逐个文件确认）。

**执行步骤**：

```
检测到 8 要素任一缺失
│
├─ 停下告知："检测到 docs_rj/ 不完整，缺失 N 要素：{列出缺失项}，需先初始化"
│
├─ 展示 8 要素清单 + 各要素用途：
│   1. .primary_docs_rj 标记 → 主 docs 唯一性宣告（避免多 docs 歧义）
│   2. docs_rj/ 主目录 → 所有任务文档的根
│   3. spec_rj/ → 需求规格分类
│   4. task_rj/ → 任务清单分类
│   5. handoff_rj/ → 交接文档分类
│   6. archive_rj/ → 归档分类（按任务子文件夹聚合，{task}_{ts}/）
│   7. memory_rj/ → 项目记忆分类（Memory First 落盘点）
│   8. SUMMARY_RJ.md → 根索引（跨对话恢复入口）
│
├─ 问你："按规范创建 docs_rj/ 完整结构（8 要素），可以吗？"
│
├─ 你确认 → 执行统一创建（三脚本串联）：
│   ├─ python {skill_dir}/scripts/generate_docs.py --declare-primary
│   │   → 建 .primary_docs_rj 标记 + docs_rj/ 主目录（要素 1-2）
│   ├─ python {skill_dir}/scripts/generate_docs.py --task bootstrap_init --type all
│   │   → 建 5 类子目录 + 模板（要素 3-7）
│   │   注：generate_docs.py 已修复 --assets-dir 默认值（基于脚本位置推导，无需显式传参）
│   └─ python {skill_dir}/scripts/startup_tidy.py --create-summary
│       → 建 SUMMARY_RJ.md（要素 8）
│
│   注：{skill_dir} = pdca-skill 安装目录（如 c:\Users\xxx\.agent\skills\pdca-skill）
│
├─ 你拒绝 → 停下，告知"未初始化无法保证 Memory First，建议先初始化再继续"
│
└─ 验证 8 要素全齐**且有效**（marker 用 read_primary_docs_marker() 验证，禁止 isfile）─ 继续任务
```

### Bootstrap 覆盖范围（8 要素·完整规范）

| 层级 | # | 要素 | 位置 | 创建方式 | 用途 |
|---|---|---|---|---|---|
| 必需 | 1 | `.primary_docs_rj` 标记 | 项目根 | `generate_docs.py --declare-primary` | 主 docs 唯一性宣告，避免多 docs 歧义 |
| 必需 | 2 | `docs_rj/` 主目录 | 项目根 | `mkdir` 或 `generate_docs.py --task` | 所有任务文档的根 |
| 必需 | 3 | `docs_rj/spec_rj/` | 主 docs 内 | `generate_docs.py --task` | 需求规格分类 |
| 必需 | 4 | `docs_rj/task_rj/` | 主 docs 内 | `generate_docs.py --task` | 任务清单分类 |
| 必需 | 5 | `docs_rj/handoff_rj/` | 主 docs 内 | `generate_docs.py --task` | 交接文档分类 |
| 必需 | 6 | `docs_rj/archive_rj/` | 主 docs 内 | `generate_docs.py --task` | 归档分类（按任务子文件夹聚合） |
| 必需 | 7 | `docs_rj/memory_rj/` | 主 docs 内 | `generate_docs.py --task` | 项目记忆分类（Memory First 落盘点） |
| 必需 | 8 | `docs_rj/SUMMARY_RJ.md` | 主 docs 内 | `startup_tidy.py --create-summary` | 根索引（跨对话恢复入口） |
| 全局 | - | skill 包 `memory/memory_main.md` | skill 包 `memory/` | `write_project` 自动 upsert | 全局聚合记忆（按项目分段） |

---

## 三、初始化内容

新模型**不需要** `MEMORY_RJ.md` 这类单一主索引文件。初始化落点如下：

1. **项目根 `docs_rj/memory_rj/`**：创建空目录（项目记忆经 `write_project` 按需生成 `{task}_memory_YYYYMMDD_HHMM.md`，无需模板）。
2. **skill 包 `memory/memory_main.md`**：建头（`# 主记忆（全局聚合 · 主次跟进）` + `## {项目名}` 占位分段），全局聚合经 `write_project` 自动 upsert。
3. **约定**：全局记忆路径固定在 skill 包 `memory/`，主 docs 默认 `./docs_rj`（无需在 memory 文件里记路径）。

> 注：`assets/memory_bootstrap_template.md` 保留为兼容模板，新项目引导时以"建目录 + 建 memory_main 头"为主。

---

## 四、路径校准（首次使用时）

若用户从源码复制安装，SKILL.md 中的示例路径为 `/path/to/pdca-skill/...` 形式。首次使用时建议替换为实际安装路径，便于复制打开。

---

## 五、用户画像与 Agent 描述引导确认（首次使用时）【硬性】

SKILL.md 中的「用户画像」和「对 Agent 的要求描述」两节定义了协作的基础参数。首次使用时，需引导用户确认或自定义这两项内容。**修改写入 SKILL.md 本身（热记忆层），不是 memory_main.md**——因为 Agent 行为由 SKILL.md 热记忆层决定，写 memory_main.md（弹性层）不保证生效。

### 5.1 用户画像确认流程

```
路径校准完成后
│
├─ 展示 SKILL.md 中的默认用户画像（读取 SKILL.md「用户画像」节）
│   ├─ 身份/角色
│   ├─ 与 skill 的关系
│   ├─ 技术背景
│   ├─ 沟通偏好
│   └─ 使用场景
│
├─ 问用户："以上是默认用户画像，需要修改吗？"
│   ├─ 用户说"要/改" → 逐项询问修改（一次一问，给建议答案）
│   │   ├─ "你的身份/角色是什么？"
│   │   ├─ "你与本 skill 的关系是什么？"
│   │   ├─ "你的技术背景如何？"
│   │   ├─ "你的沟通偏好是什么？"
│   │   └─ "你的使用场景是什么？"
│   └─ 用户说"不用/跳过" → 使用默认画像，跳到 5.2
│
└─ 如有修改 → 备份 SKILL.md → 编辑 SKILL.md「用户画像」节 → 告知"已更新"
```

### 5.2 Agent 描述确认流程

```
用户画像确认完成后
│
├─ 展示 SKILL.md 中的默认 Agent 描述（读取 SKILL.md「对 Agent 的要求描述」节）
│   ├─ 人格定位
│   ├─ 行为准则
│   ├─ 输出与沟通要求
│   └─ 红线（禁止）
│
├─ 问用户："以上是默认 Agent 描述，需要修改吗？"
│   ├─ 用户说"要/改" → 逐项询问修改（一次一问，给建议答案）
│   │   ├─ "你希望 Agent 的人格定位是什么？"
│   │   ├─ "你希望 Agent 遵循哪些行为准则？"
│   │   ├─ "你对 Agent 的输出与沟通有什么要求？"
│   │   └─ "你希望 Agent 遵守哪些红线（禁止行为）？"
│   └─ 用户说"不用/跳过" → 使用默认描述
│
└─ 如有修改 → 备份 SKILL.md → 编辑 SKILL.md「对 Agent 的要求描述」节 → 告知"已更新"
```

### 5.3 修改安全要求【硬性】

- **备份**：修改 SKILL.md 前必须先备份（如 `SKILL.md.bak_YYYYMMDD_HHMM`）
- **HARD-GATE**：每次修改 SKILL.md 都需用户明确确认
- **只改内容不改结构**：只修改「用户画像」和「对 Agent 的要求描述」两节的内容，不碰其他章节
- **Chesterton's Fence**：修改红线/行为准则前，先理解其存在理由（见 SKILL.md §9），不得顺手推翻
- **告知变更**：修改完成后告知用户"已更新 SKILL.md 的 XX 节，备份在 XX"

### 5.4 后续更新

非首次使用时，用户可通过对话直接说"更新我的用户画像"或"修改 Agent 描述"触发重新确认。

---

## 六、反模式

| 反模式 | 正确做法 |
|--------|----------|
| 检测到文件缺失后静默创建 | 停下告知 + 展示模板 + 等确认 |
| 一次创建所有缺失文件 | 逐个文件单独确认 |
| 创建后不告知 | 创建完成后汇总告知 "已创建 X/N 个文件" |
| 跳过必需文件不记录 | 跳过必需文件时记录到 memory（经 write_project） |
| 跳过路径校准不告知 | 首次使用必须执行 §四 路径校准，跳过时告知后果 |
| 把用户画像/Agent描述写入 memory_main.md | 写入 SKILL.md 热记忆层（§五 5.3），memory_main.md 只经 write_project 写入 |
| 修改 SKILL.md 前不备份 | 先备份（SKILL.md.bak_时间戳），再修改（铁律6 回溯保障） |



---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

### 启动前置检查【硬性】（v1.0.0 新增）

接到任何任务（含简单任务），流程判断后、动手前，必须先确认项目 `docs_rj/` 完整性。

**检查清单（8 要素）**：
1. `.primary_docs_rj` 标记**有效**（项目根；以 `read_primary_docs_marker()` 返回非 None 为准；空文件/BOM 文件/路径不存在一律视为缺失，走 bootstrap 修复）
2. `docs_rj/` 主目录存在
3. `docs_rj/spec_rj/` 存在
4. `docs_rj/task_rj/` 存在
5. `docs_rj/handoff_rj/` 存在
6. `docs_rj/archive_rj/` 存在
7. `docs_rj/memory_rj/` 存在
8. `docs_rj/SUMMARY_RJ.md` 根索引存在

**处理逻辑**：
- **8 要素全齐** → 继续任务
- **任一缺失** → 停下，走 [references/plan/bootstrap/bootstrap.md](bootstrap.md) §二 8 要素统一创建流程（不静默跳过、不先干活后补建）
- **用户催促** → 不是跳过的理由（Red Flag #6）

**为什么硬性**：
- Memory First 要求任何任务都要写 memory → memory_rj/ 缺失 = 数据丢失
- SUMMARY 缺失 = 跨对话恢复断链（§1 启动检查第2步读 SUMMARY 建立全局认知）
- .primary_docs_rj 缺失 = 主 docs 歧义（generate_docs.py 每次扫描浪费时间 + 可能选错 docs）
- spec_rj/task_rj/handoff_rj/archive_rj 缺失 = 复杂任务进入阶段1时无地方落 spec/task

**与 §5 阶段1 的关系**：§5 阶段1「自动生成文档目录」针对"复杂任务"建任务级模板文件（{任务名}_spec_*.md 等）；本节针对"任何任务"建项目级目录骨架（8 要素）。本节是 §5 阶段1 的前置——目录骨架不存在，§5 阶段1 的模板文件没地方放。

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

### Bootstrap 初始化（首次使用/文件缺失时）【硬性】

当 startup_tidy 报告项目结构缺失时，**不静默创建**，按 [references/plan/bootstrap/bootstrap.md](bootstrap.md) 引导式创建：①停下告知 ②逐个文件确认 ③创建后继续。覆盖范围：必需层（`docs_rj/memory_rj/` + `memory/memory_main.md`）+ 推荐层（`docs_rj/` 5类 + `outputs_rj/` + `.agent/`）。

### SUMMARY 缺失引导式创建【硬性】

若 `{主docs}/SUMMARY_RJ.md` 不存在：**不静默跳过**，按 [references/common/pa/summary_view.md](../../common/pa/summary_view.md) 三触发①引导式创建——读 `assets/summary_template.md` 模板 + 扫描 `docs_rj` 各子目录生成（纯 markdown，零依赖）。`scripts/startup_tidy.py` 已升级为"发现缺失即 `[BLOCKER]` 警告"（可加 `--create-summary` 确认后自动生成）；`scripts/validate_skill.py` 的 `ARC-04` 也强制校验其存在（MUST FIX）。两条防线互补，杜绝"漏建无人发现"。

### 归档检查（每次启动时）【硬性】

若 `docs_rj/memory_rj/{task}_memory_*.md` 含**未完成任务标记**，提示"检测到任务 X 记忆有未完成任务，要继续吗？"，确认后按对话恢复协议处理（见 Memory First 节）。

### paused 状态检测（每次启动时）【硬性·v1.0.0 新增】

若 `docs_rj/memory_rj/TASK_STATE_{task}.md` 的 frontmatter `status: paused`（因 §6 /do 第10项"执行中插入新任务处置"挂起），启动检查必须：
1. 读取 `paused_reason` 字段（frontmatter 优先，回退 body `## Paused Reason` 段）
2. 读取原 task.md 暂停行（`> ⏸ 暂停于...`）定位进度
3. 向用户提示："原任务 {原任务名} 因插入新任务 {新任务名} 暂停于第 N 项，要回到原任务还是继续新任务？"，按 §6 /do 第10项步骤4 处置
4. **不自动恢复**——必须用户明确选择"回"才将 status 改回 pending（handoff_tidy.py 的一致性保障会自动清除 paused_reason）

---

## §1.5 上下文压缩恢复协议（Compaction Recovery Protocol）【硬性】

> 完整检测信号表（6 项）+ 7 步恢复流程 + 与现有规则关系，已下沉至 [references/plan/bootstrap/compaction_recovery.md](compaction_recovery.md)（按需读）。

**核心不变量**：压缩后只重读规则 = 只恢复“怎么做”，没恢复“在哪、做了什么、为什么”。检测到任一致死信号 → 停 → 读 SUMMARY → 读 MEMORY → 重读铁律 → 过五问 → 告知你 → 继续（7 步不可跳）。

---

## §1.7 导师信条：8 条铁律为什么存在（八问八答）

> 阶段标签：P.bootstrap（启动重申铁律时按需读）。
> SKILL.md「🧭 你相信什么」只放一句话版；本节存完整理由与「我常会问你」提问句，用于启动重申时**说清理由**而非背规则。

| 铁律 | 为什么信它 | 我常会问你 |
|------|-----------|-----------|
| 1. Memory First | 上下文易失，记忆是铁打的营盘。不写下来，下次开口就得从头讲，越用越累。 | "这一步做完，你希望下次直接接上的，是哪件事？" |
| 2. HARD-GATE | 动手前先对齐，比做完返工便宜得多。你以为的"顺手改一下"，常藏着没对齐的假设。 | "在动手之前，我们先对齐：要达成的是这个吗？" |
| 3. 流程优先 | 先判断走哪条路，再迈步。哪怕只有 1% 可能该走流程，也值得先停下来想一秒。 | "这件事，值得走完整流程，还是快速过？" |
| 4. No Placeholders | 半成品交付比不交付更危险——它会假装已经完成。 | "这里有没有'差不多''待定'的地方，我们补齐？" |
| 5. 触发钩子 | 凭记忆动手 = 偏离。细节要从硬盘重读，不是从脑子里猜。 | "这个信号，你想让我先查原因，还是先继续原任务？" |
| 6. 回溯保障 | 改错了能回去，才敢放心改。没有回溯点的动手是赌博。 | "动手前，工作区已经存档了吗？" |
| 7. 逐项核对 | 跳过一项不报错的，往往就是最后出事的那一项。 | "我们对照清单，还差哪一项没打勾？" |
| 8. 先查再写 | 文档里写过、别人做过的，再自己编一遍就是浪费。查一次的成本，永远低于重做一次。 | "这事之前是不是定过？我先去翻文档和现成实现，可以吗？" |

> 这份信条是给双方看的，不是给你背的。哪天某条不再成立、或该加个理由，提醒我一起改。

---

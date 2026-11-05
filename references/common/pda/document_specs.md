<!-- PDCA标签：P.design D.code A.handoff -->
<!-- 子标签场景：文档规格 -->
<!-- 关键词清单：写spec/写task/写文档/写需求/做需求/需求分析/写方案/出方案/写设计/做设计/规划/文档优先/之前写过/之前定过/落盘/决策落盘 -->
<!-- 引用范围：main + spec_design_agent -->

# 文档规范
> 阶段标签：P · D · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-18

> 📖 **什么时候读这个文件**：
> - 准备写spec.md/task.md文档时
> - **动手前想先查"之前是不是定过"（文档优先）时**
> - 准备提交spec给你确认前做Self-Review时
> - 不确定No Placeholders细节时
> - 不确定主 docs 目录/多个 docs 怎么处理时
> 🔴 **不要在这时候读**：
> - 不需要写文档的简单任务
> - 纯代码执行阶段已有明确task

---

## 文档优先（Doc First）【硬性】

> 铁律8「先查再写」的文档侧。**读 > 问 > 猜**：文档里写过的，别再问一遍、更别推翻重来。

### 三条规则

1. **动手前先读**：接到任务先看 `docs_rj/` 的 spec / task / handoff / memory，以及项目根 README / ADR / 变更日志。**文档已有答案 → 直接沿用并说明"依据 XX 文档"**，不重复追问用户，不另起一套方案。
2. **决策必须落盘**：对话里定下的实质决策（选型、口径、边界、放弃的方案、用户明确说"就按这个来"）**当场写进 spec / task / memory**。只停在对话里 = 下一轮/换对话就没了，等于没做。
3. **冲突先问归属**：文档与口头说法不一致时，**不要自己选一个**。先问"以文档为准还是以刚才说的为准"，用户选定后**同步改文档**，让文档继续是唯一事实源。

### 反例（都是真实踩过的坑）

| 反例 | 后果 | 正确做法 |
|---|---|---|
| 上次 spec 已经定了方案 A，这次没读就重新设计出方案 B | 返工 + 用户要重复解释 | 先读 spec，发现 A，直接说"沿用 spec 的方案 A，因为…" |
| 用户口头说"这个字段不要了"，没写进 spec，三天后换对话又加回来 | 需求漂移、反复 | 当场改 spec，并回一句"已更新 spec：删除 XX 字段" |
| 文档写"用 MySQL"，用户口头说"用 SQLite"，直接按 SQLite 做了 | 文档失效，后续接手的人被误导 | 先问以哪个为准，选定后同步改文档 |

### 与铁律8「先查再写」的分工

- **文档侧**（本节）：先读已有 spec/task/handoff/memory，先落盘新决策。
- **实现侧**（[minimal_code_principles.md](../pd/minimal_code_principles.md)）：先查能不能不写 / 库里有没有 / 标准库与已装依赖 / 外部有没有现成 skill。

---

## 多 docs 目录处理【硬性】

### 主 docs 目录概念

一个项目**只有一个主 docs 目录**，所有 pdca-skill 任务文档（spec_rj/task_rj/handoff_rj/archive_rj）+ 项目记忆（memory_rj）都存放在这里；项目记忆在 `docs_rj/memory_rj/` 内。位置不固定，默认 `./docs_rj/`。

### 优先级路由

脚本 `generate_docs.py` 按以下优先级查找主 docs 目录：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `--docs-dir` 命令行参数 | 手动指定，最高优先 |
| 2 | `.primary_docs_rj` 标记 | 主 docs 绝对路径（首次选定后由 `--declare-primary` 写入，默认路由 `./docs_rj/`） |
| 3 | `./docs_rj/` | 默认路径，90% 场景 |
| 4 | `./.agent/documents/` | 平台适配 |
| 5 | `./src/docs/` | 框架约定（Sphinx/MkDocs） |
| 6 | 第一个找到的 docs 目录 | 兜底 |

### 首次选择流程

```
启动检查 / 创建文档时
│
├─ 读 .primary_docs_rj 标记
│   ├─ 有"主 docs 路径"且存在 → 直接用
│   └─ 无 / 不存在 → 扫描项目找所有 docs 目录
│       ├─ 找到 0 个 → 在 ./docs_rj/ 创建（Bootstrap 流程）
│       ├─ 找到 1 个 → 直接用，写入 .primary_docs_rj 标记
│       └─ 找到多个 → 列出候选让用户选，选定后写 .primary_docs_rj 标记
```

### 主 docs 唯一性宣告（R3）【硬性】

一个项目**只有一个主 docs 目录**。为避免多 docs 歧义，主 docs 路径以以下两处为准，优先级从高到低：

1. **`.primary_docs_rj` 隐藏标记**（项目根）：一行，含主 docs 绝对路径。由 `python generate_docs.py --declare-primary [PATH]` 写入。
2. 主 docs 路径默认 `./docs_rj/`；全局记忆路径固定在 skill 包 `memory/`，无需在 memory 文件里记主 docs 路径。

**宣告流程**：
```
运行 python generate_docs.py --declare-primary [PATH]
│
├─ 路径省略 → 自动检测（标记 > 优先级路由）
├─ 写 .primary_docs_rj 标记（含绝对路径，默认路由 ./docs_rj/）
└─ 全局记忆路径固定在 skill 包 memory/，无需在 memory 文件里记主 docs 路径
```

**启动歧义处理**：`scripts/startup_tidy.py` 解析主 docs 时按 R3 优先级取唯一值；若发现多个 docs 目录且标记/约定均缺失或冲突，列出候选供你选择并写回（不静默移动、不静默改写）。

**与启动整理关系**：`.primary_docs_rj` 标记也是 `startup_tidy.py` 解析主 docs 的第一优先级来源，确保每次启动整理都锚定同一主 docs。

### 散落归档

检测到 pdca-skill 任务文档散落在非主 docs 目录时：
1. **扫描识别**：运行 `python generate_docs.py --scan-docs` 输出 JSON 清单
2. **告知用户**：列出散落文档的位置和内容
3. **用户确认后归档**：运行 `python generate_docs.py --archive-scattered --primary-docs {主docs}`
4. **归档 = 移动**：文件移动到主 docs，删空目录，更新 SUMMARY_RJ.md

### 识别特征

pdca-skill 产出的任务文档有固定结构：

| 特征 | 说明 | 示例 |
|------|------|------|
| 子目录名 | 固定4种 | `spec_rj/` `task_rj/` `handoff_rj/` `archive_rj/`（记忆不在内，独立在根 `memory/`） |
| 文件名 | 时间前缀式（时间+任务名+类型，无编号前缀） | `20260710_1430_user_auth_spec.md` |

非 pdca-skill 文档（如 Sphinx API 文档、用户手册）不会被误识别。

### 冲突处理

| 情况 | 处理 |
|------|------|
| 主 docs 和散落目录有同名任务 | 主 docs 优先，跳过散落的 |
| 移动过程出错 | 降级到手动提示 |

---

## 文件用途与位置

| 文件 | 位置 | 性质 |
|------|------|------|
| spec | `{主docs}/spec_rj/YYYYMMDD_HHMM_{项目名}_spec_{任务名}.md` | 需求规格 |
| task | `{主docs}/task_rj/YYYYMMDD_HHMM_{项目名}_task_{任务名}.md` | 任务清单 + 验收标准 + 验证步骤 |
| handoff（手工） | `{主docs}/handoff_rj/YYYYMMDD_HHMM_{项目名}_handoff_{任务名}.md` | 手工创建的交接文档 |
| handoff（自动） | `{项目根}/docs_rj/memory_rj/YYYYMMDD_HHMM_{任务名}_handoff_memory.md` | handoff_tidy.py 自动生成（经 write_project 双写，自动 upsert 全局 memory_main；L1 修复·澄清设计意图） |
| memory | `{项目根}/docs_rj/memory_rj/YYYYMMDD_HHMM_{任务名}_memory.md` | 任务级极简笔记（写入即落盘 + 自动 upsert 全局 `memory/memory_main.md`） |

> 命名说明：spec/task/handoff 由 `generate_docs.py` 生成，统一时间前缀式 4 段 `YYYYMMDD_HHMM_{项目名}_{类型}_{任务名}.md`（项目名缺省取当前目录名，可用 `--project` 指定）；memory 由 `memory_shadow_write.py` 生成，沿用 `YYYYMMDD_HHMM_{任务名}_memory.md`。读取侧两种格式都兼容。

模板文件存放在 `assets/` 目录：
- `assets/spec_main_template.md`（项目级总 spec 模板，通用，其他项目复制填空即可用；实例：docs_rj/spec_main_{项目名}.md）
- `assets/spec_template_lite.md`（**v1.0.4 起默认**，≤90 行轻量版）
- `assets/task_template_lite.md`（**v1.0.4 起默认**，≤70 行轻量版）
- `assets/spec_template.md`（重型，仅 `--full` 场景）
- `assets/task_template.md`（重型，仅 `--full` 场景）
- `assets/handoff_template.md`
- `assets/memory_template.md`
- `assets/daily_log_template.md`（归档日志模板，文件名保留历史命名）

### 自动触发机制【硬性】

当准备写spec_rj/task文档时，**自动触发**文档生成脚本：

1. **触发时机**：进入阶段1（需求对齐），判断任务为复杂任务时
2. **自动执行**：调用 `scripts/generate_docs.py --task {任务名} --type all`（v1.0.4 起默认产出**轻量模板**）
3. **无需确认**：文档目录结构生成是标准流程，无需额外确认
4. **后续步骤**：脚本执行完成后，读取生成的模板文件并填充内容
5. **升级重型（门禁，v1.0.4）**：命中升级信号四条（架构级改动/跨3+文件/动已交付物/用户明说"重型"）→ 先呈现理由经 HARD-GATE 确认，再 `--full --full-reason "{理由}"`（脚本门禁：无理由或 <10 字 exit 2 拒绝、零产出）

**自动触发流程**：

```
判断任务为复杂任务
    │
    ├─ 提取任务名（小写+下划线）
    ├─ 自动调用 generate_docs.py（自动检测主 docs 目录；v1.0.4 默认在项目根 ./docs_rj 创建）
    ├─ 创建 {主docs}/ 扁平 4 类目录结构（spec_rj/task_rj/handoff_rj/archive_rj）
    ├─ 生成 4 类模板 + memory_rj 模板（项目记忆在 docs_rj/memory_rj/ 内）
    └─ 读取模板文件，开始填充内容
```

**降级方案**：如果脚本执行失败（路径错误、Python不可用、权限问题），手动创建目录结构并复制模板文件：

```bash
# {主docs} 替换为实际主 docs 路径，默认 ./docs_rj/（v1.0.4 起默认建项目根）
mkdir -p {主docs}/{spec_rj,task_rj,handoff_rj,archive_rj}
cp ~/.agent/skills/pdca-skill/assets/spec_template_lite.md {主docs}/spec_rj/YYYYMMDD_HHMM_{项目名}_spec_{任务名}.md
cp ~/.agent/skills/pdca-skill/assets/task_template_lite.md {主docs}/task_rj/YYYYMMDD_HHMM_{项目名}_task_{任务名}.md
cp ~/.agent/skills/pdca-skill/assets/handoff_template.md {主docs}/handoff_rj/YYYYMMDD_HHMM_{项目名}_handoff_{任务名}.md
# 项目记忆在 docs_rj/memory_rj/ 内，经 memory_shadow_write.write_project 双写
cp ~/.agent/skills/pdca-skill/assets/memory_template.md {项目根}/docs_rj/memory_rj/YYYYMMDD_HHMM_{任务名}_memory.md
```

> ⚠️ 脚本路径：`pdca-skill/scripts/generate_docs.py`（skill 安装目录下）

---

## No Placeholders 铁律【硬性】

spec.md和task.md里**绝对禁止**以下模糊描述：

| 禁止项 | 为什么禁止 | 必须怎么做 |
|--------|-----------|-----------|
| ❌ TBD、TODO、"后面再说"、"待补充" | 模糊=没计划=执行时会猜 | 现在就补全，补不全就不要写 |
| ❌ "适当处理错误"/"加必要的验证"/"处理边界情况" | 什么叫"适当"？执行时理解可能完全不同 | 写具体："用try-except捕获FileNotFoundError，返回友好提示'文件不存在'" |
| ❌ "写测试" | 测什么？怎么测？预期结果是什么？ | 写："写单元测试test_login_success，输入正确用户名密码，预期返回200+token" |
| ❌ "参考Task N的做法"/"类似上面" | 执行时可能跳着读，上下文丢失 | 要么重复写关键代码/步骤，要么明确引用"见Task 3的数据库连接部分，复制即可" |
| ❌ 伪代码/描述性文字说"在这里实现XX功能" | 伪代码不能直接运行，还得猜 | 给完整可运行代码 |
| ❌ 命令只写"运行XX"，不说预期结果 | 不知道跑成什么样算成功 | 写："运行python main.py，预期终端输出'Server running on port 5000'，浏览器访问http://localhost:5000看到首页" |

**简单任务可以没有完整spec，但一句话方案里不能有模糊词。**

---

## Self-Review：写完必须自检【硬性·Unit Tests for English】

> 借鉴 某开源项目 checklist 命令（Unit Tests for English 隐喻：测试需求文档本身的质量）。
> **本节为引用说明**：9 维度 Self-Review 清单的**唯一维护源**在 [assets/spec_template.md](../../../assets/spec_template.md) "Self-Review 自检清单"节，本节不重复维护，避免漂移。

写完spec.md或task.md之后、交给你之前，必须自己先检查：

- **简单任务**（一句话能说清）：过 4 项（占位符/一致性/范围/歧义）
- **复杂任务**：过 9 项（占位符/一致性/范围/歧义/方案对比/验收标准/No Placeholders/错误处理/BRD 业务价值对齐）

检查项详细清单见 [assets/spec_template.md](../../../assets/spec_template.md) Self-Review 节。

自检发现问题直接改，不用告诉你"我发现个问题改了"——改完再交。

### clarify 子流程（借鉴 某开源项目 clarify 命令）

- **触发时机**：/plan 步骤3 需求澄清 + /do 阶段发现 spec 模糊时回流触发
- **/do 回流规则**：/do 阶段发现 spec 模糊 → 停下 → 触发 clarify 子流程（增量补 spec §10 Clarifications 节）→ 继续 /do
- **每答即写回**：每个澄清回答立即 integrate 到 spec §10 Clarifications 节（含时间/问题/回答/影响 §X.Y/是否重跑 Self-Review）
- **每答重跑 Self-Review**：每答后重跑 spec Self-Review 9 维度（复杂任务）或 4 维度（简单任务），toggle 通过状态

---

## memory 约束

- **记录要素**（缺一不可）：任务一句话、关键决策和原因、当前进度、遗留待办（带时间戳）
- **写作要求**：一句话一条，只记事实和结果，不记过程流水账
- **不记的**：spec 已写的需求、task 已列的步骤、memory 里重复出现的旧事
- **检验**：写完后问自己——删掉任意一行，影响别人理解这个任务吗？不影响的就删

---

## 记忆写入与全局聚合

- **项目级记忆**：`{项目根}/docs_rj/memory_rj/YYYYMMDD_HHMM_{task}_memory.md`（任务名进文件名，带分钟级时间戳）。写入经 `memory_shadow_write.write_project(task, content)` 双写——落项目 `docs_rj/memory_rj/` + 幂等 upsert 全局 `memory/memory_main.md`。
- **全局聚合记忆**（skill 包内）：`memory/memory_main.md` 按 `## {项目名}` 分段聚合各项目记忆（主次跟进）。
- **写入即落盘**：所有项目记忆经 `write_project` 自动 upsert 全局 memory_main，无需手工同步、无独立归档步骤、无 SESSION_END 收尾标记。
- **同分钟文件名冲突处理规则**（LOW-3 新增·M4 完善边界 case）：文件名时间戳粒度为分钟，同分钟内多次 `write_project` 可能产生同名文件冲突。处理规则：① 写入前检查同名文件是否存在；② 不存在 → 正常写入；③ 已存在 → 追加序号后缀 `_N`（N 从 2 开始递增，**递增直到找到不存在的值**，上限 N≤99），格式 `{task}_memory_{YYYYMMDD}_{HHMM}_2.md`、`{task}_memory_{YYYYMMDD}_{HHMM}_3.md`，以此类推；④ N=99 仍存在 → 报错并升级用户决策（极端罕见场景）；⑤ 全局 memory_main 仍幂等 upsert（按 `## {项目名}` 段聚合，不重复）；⑥ 并发场景：`write_project` 内部按文件写入串行处理（同分钟多进程并发场景罕见，按写入顺序串行追加 `_N` 后缀）；⑦ 文件名长度校验：task 名 + 时间戳 + `_N` 后缀 ≤ 200 字符（Windows 上限 255，留余量）；⑧ 同分钟多次写入属罕见场景，**正常推荐做法是"同分钟内的多次写入合并为一次写入"**（content 一次写全）。

> 旧模型中的"当日工作记录"区块、"归档日志 `memory_rj/YYYY-MM-DD.md`"、"MEMORY_RJ.md 关键决策/约定/当日工作记录四区块"均已废弃——改为全局 `memory/memory_main.md` 按项目分段长期保留。

模板见 `assets/memory_bootstrap_template.md`.

---

## 项目总 spec

| 文档 | 作用 | 创建时机 | 完成标准 |
|------|------|----------|----------|
| `docs_rj/spec_main_rj.md` | 项目级 source of truth（目标/PRD/技术栈/宪法/任务/ADR/状态，最新置顶），任务 spec 从它派生 | 项目首次 /plan 时（本项目 2026-07-18） | 7 章节齐全（§1§2§7 最新置顶）；3 新内容+4 指针段；任务 spec 头部填 derived_from |

---

## spec 完成标准

> **档位说明（v1.0.4）**：以下标准适用于**重型模板**（`--full` 场景）；轻量模板按 `assets/spec_template_lite.md` 骨架达标即可（目标/方案对比/范围/验收标准/风险回退/澄清记录六节齐、无占位符）。

- 看完能写代码，不用再猜
- 有正例也有反例
- 有可量化的验收标准
- **必须包含2-3个方案对比表**（见communication_rules.md），明确推荐哪个。**复杂任务方案对比时，必须按 [references/common/pd/minimal_code_principles.md](../pd/minimal_code_principles.md) 评估"复用优先/最小实现"维度：是否优先复用现有代码/标准库/原生能力/已装依赖？是否引入非必要新依赖？是否违反 YAGNI？哪个方案新增代码量最小？**
- **复杂任务必须包含"本质拆解"小节**（见 [adversarial_review.md](../pc/adversarial_review.md) 第二章）：本质目标 + 不可压缩约束 + 从约束推导的最优解
- **复杂任务必须包含 BRD 要素**：spec §1.0-§1.4 五子项必填（业务背景与痛点/业务价值/不做的代价/成功指标/干系人），简单任务可只填 §1.0+§1.3
- **复杂任务必须包含 §0.A BRD 视角对比表**：类似产品对比 + 不做的代价分析，对齐 某开源项目 market-research
- **复杂任务必须包含 §10 Clarifications 节**：澄清增量记录，每答即写回 + 重跑 Self-Review
- **分节展示**，每节不超过200字，每节确认后再写下一节
- 通过Self-Review（简单任务 4 项/复杂任务 9 维度），无占位符、无矛盾、无歧义、无额外内容

---

## task 完成标准

> **档位说明（v1.0.4）**：以下标准适用于**重型模板**（`--full` 场景）；轻量模板按 `assets/task_template_lite.md` 骨架达标即可（总览含 HARD-GATE/进度状态/阻塞项 + 每任务 4 字段 + 验收闸门 4 道齐、无占位符）。

- 每条有验收标记
- 按阶段分组（阶段1需求对齐 / 阶段2执行 / 阶段3验收）
- 阻塞项单独列出
- **每个task项必须包含三个字段【硬性】**：
  1. 做什么（具体动作）
  2. 怎么做（完整代码/具体命令/操作步骤，无伪代码）
  3. **怎么验证它做完了**（具体验证步骤+预期结果）
- 做完必须实际跑验证步骤，看到预期结果了，才能标记 [x] 完成（Verification-before-Completion）
- 通过Self-Review四检查

task项示例（正确）：
```markdown
- [ ] Task 3：连接SQLite数据库
  - 怎么做：在db.py中添加以下代码：
    ```python
    import sqlite3
    def get_db():
        conn = sqlite3.connect('app.db')
        conn.row_factory = sqlite3.Row
        return conn
    ```
  - 验证：运行`python -c "from db import get_db; conn = get_db(); print('Connected OK')"`，预期输出"Connected OK"
```

task项示例（错误，违反No Placeholders）：
```markdown
- [ ] Task 3：添加数据库连接，适当处理错误
```

---

## 双向汇聚规则

Memory 分三层：热记忆（SKILL.md/references，硬性）、全局聚合记忆（`memory/memory_main.md`，skill 包内）、项目记忆（`{项目根}/docs_rj/memory_rj/{task}_memory_*.md`）。

**上行（任务经验 → 全局聚合记忆）**

| 时机 | 动作 |
|------|------|
| 每次写记忆 | 经 `memory_shadow_write.write_project(task, content)` 双写：落项目 `docs_rj/memory_rj/{task}_memory_*.md` + 幂等 upsert 全局 `memory/memory_main.md`（按 `## {项目名}` 分段，主次跟进） |
| 任务验收完成 | 将任务关键决策提炼 <=1 句话，写入项目记忆，自动 upsert 全局 memory_main「关键决策」 |

**下行（全局 → 任务）**

| 时机 | 动作 |
|------|------|
| 每次新对话启动 | 启动检查读取全局 `memory/memory_main.md`，提取相关项目经验指导本次对话 |
| 新任务启动 | 读取全局 memory_main，将相关经验写入新任务的 memory 作为参考 |

---

## 版本号规则【硬性】

所有文档都必须带版本号，头部标注 + 底部版本历史表。

### 版本号格式

```
v{主版本}.{次版本}_{日期}_{时间}
```

- **主版本**：结构调整、重大功能变更（v1.0 → v2.0）
- **次版本**：内容修订、字段补充（v1.0 → v1.1）
- **日期**：`YYYYMMDD`（如 20260708）
- **时间**：`HHMM`（精确到分钟，如 1030）

**示例**：`v1.1_20260708_1422` 表示 2026年7月8日14点22分的1.1版本

### 版本升级规则

| 版本变化 | 触发条件 | 示例 |
|----------|----------|------|
| 初版 | 文档首次创建 | v1.0_20260708_1030 |
| 次版本 +1 | 内容修订、字段补充、条目增减 | v1.0_20260708_1030 -> v1.1_20260708_1422 |
| 主版本 +1 | 结构调整、章节增删、整体重写 | v1.2_20260708_1422 -> v2.0_20260709_0915 |

### 文件头部格式

```markdown
---
title: {任务名} - 需求规格说明
version: v1.0.0
date_created: 2026-07-08 10:30
last_updated: 2026-07-08 10:30
---

> 版本：v1.0.0 | 更新：2026-07-08 14:22
```

### 文件底部格式

```markdown
## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-08 10:30 | 初版 |
| v1.1 | 2026-07-08 14:22 | 新增验收标准章节 |
```

### 版本归档规则

| 变更类型 | 归档方式 |
|----------|----------|
| 任务归档（统一规则） | 创建归档目录 `archive_rj/{task}_YYYYMMDD_HHMM/`，内放 `spec.md`/`task.md`/`handoff.md`/`memory.md`（任务启动时间戳从原文件名提取，不依赖 mtime） |
| 存量扁平文件 | 保留原位，INDEX.md 标注 `legacy` 状态，不强制迁移 |
| 最终发布 | 归档到 `releases/{任务名}/v1.0/`（保留现有机制） |

> 注：早期版本曾按"小修订/大升级"区分版本子文件夹归档（v1.0_YYYYMMDD_HHMM/），自 v1.0.0 起统一改为按任务子文件夹聚合（{task}_YYYYMMDD_HHMM/），对齐 §0.6 案件编号心智模型。

---

## SUMMARY_RJ.md 格式（文档汇总视图）

> 纯 markdown 落地。详见 [summary_view.md](../pa/summary_view.md)。

| 要素 | 规则 |
|------|------|
| 文件位置 | `{主docs}/SUMMARY_RJ.md`（主 docs 目录下唯一根索引） |
| 性质 | 根索引，只做导航不做内容（链接 + 一句话描述） |
| Frontmatter | title / version / last_updated / total_docs / require-rule-mention: true |
| Leading paragraph | 文件顶部 ≤250 字符概述；每个 section 顶部 ≤250 字符概述 |
| Section 划分 | 🧠 Memory / 📋 Spec / ✅ Task / 🤝 Handoff / 📦 Changelog / 🔗 漂移检查清单 |
| 条目格式 | `- [显示名](相对路径) — 一句话描述` |
| 链接 | 标准 markdown 链接 `[text](path)`，相对路径，可渲染可点击 |
| 生成/更新时机 | 启动检查时 + 对话结束归档时 + 交接时（三触发硬性） |
| 漂移检查 | 每次更新后跑：grep `]\(` 提取链接 → ls 确认存在 → 同步 total_docs |
| 模板 | `assets/summary_template.md` |

**禁止**：
- ❌ SUMMARY 里复制原文件内容（违背导航/内容分离）
- ❌ 链接指向不存在的文件（漂移）
- ❌ section 无 leading paragraph

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

### 用户数据外置说明【硬性·v1.0.0 新增】

> 本节说明用户数据与框架文件的物理分离机制，所有路径引用以本节为准。

**核心机制**：用户数据外置到 `~/.pdca-skill/data/`（跨平台用户目录下），skill 包纯框架。升级 skill 包（解压覆盖）时用户数据天然不受影响——数据 0 丢失。**v1.0.4：外置只放跟人走的资产（memory_main/outputs_rj/server_lite_data）；跟项目走的文档（docs_rj）建在项目根目录**。

**路径解析三级优先级**：环境变量 `PDCA_DATA_DIR` > 配置文件 `~/.pdca-skill/config.json` 的 `data_dir` 字段 > 默认值 `~/.pdca-skill/data/`。由 `scripts/user_data_path.py` 统一解析，所有脚本经此模块读写用户数据。

**外置目录结构**（`~/.pdca-skill/data/` 下）：
- `memory/memory_main.md` — 全局聚合记忆（原 skill 包内 `memory/memory_main.md`）
- `outputs_rj/` — 任务输出（loop_ledger.json 等）
- `server_lite_data/` — 框架自动创建的占位目录（server_lite 用户数据；server_lite 当前不主动引导使用，该目录即使为空也无负面影响）
- `undo/` — 治理工具操作前的备份（delete/archive/promote/demote/rethink 等）
- `quarantine/` — 隔离区（治理工具删除/隔离的条目暂存）

> **项目文档位置（v1.0.4）**：`docs_rj/` 默认建在**项目根**。外置检测到遗留（递归 `*.md >0`）按**只读存档**处理——旧数据原地保留可读、不迁移、不续写，新文档一律写项目根（防同一任务 spec/task 与 memory 撕裂两处）；搬回需手动移动 + `--declare-primary` 宣告。

**框架文件**（skill 包内，可覆盖升级）：SKILL.md / scripts/ / references/ / assets/ / agents_rj/ / tests/ / evals/ / protocol/ / server_lite/ 框架代码 + assets/ 模板。

**启动自动迁移**：老用户首次启动新版时，`startup_tidy.py` 检测包内有用户数据 + 外置为空 → 自动迁移到外置目录 + 写 `.migrated` 标记（保留 7 天回滚窗口）。迁移用跨平台文件锁（`~/.pdca-skill/.migrate.lock`）防并发竞争。

**⚠️ 锁文件说明**：`~/.pdca-skill/.migrate.lock` 残留正常（空文件，O_CREAT 复用，不依赖文件不存在），不要手工删除。

**server_lite 说明**：server_lite（日积面板）是已完整实现但不主动引导使用的可选组件——功能与 AI 对话定位重叠，当前版本不再引导用户启动。代码保留供未来扩展或用户主动启用，如需使用：`python run_server.py` 启动后访问 http://127.0.0.1:5210。数据路径管理可由 AI 对话直接改 `~/.pdca-skill/config.json` + 跑 `scripts/migrate_user_data.py` 替代。

**发布打包**：`scripts/package_skill.py --version v1.0.0` 打包时自动排除用户数据目录，发布包只含框架文件。

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

## §0.6 任务名关联 key【硬性】

> 任务名是跨文件关联的**唯一 key**。memory / spec / task / handoff 文件都按任务名前缀命名，调用 `write_project` / `generate_docs.py` / `handoff_tidy.py` 时必须传同一 task 名——否则文件散落、跨对话恢复时找不到上下文、`SUMMARY_RJ.md` 链接断链。本节定义任务名的格式规范 + 冲突处理，是 §5 阶段1「自动生成文档目录」的前置约束。

**硬规则**：

1. **任务名必须含项目标识**：每个任务启动时，任务名必须含项目标识（如 `v4_4_t07_learn_phase5`），作为 memory / spec / task / handoff 文件名前缀
2. **任务名是跨文件关联的唯一 key**：在 `write_project(task, content)` / `generate_docs.py --task {任务名}` / `handoff_tidy.py --task {任务名}` 调用时，**必须传同一 task 名**——否则文件散落，跨对话恢复时 `SUMMARY_RJ.md` 链接断链、`memory_main.md` 项目分段错位
3. **任务名格式限制**：只允许 `[a-z0-9_]+` 格式（小写字母 + 数字 + 下划线），**不允许空格 / 中文 / 特殊字符**——脚本文件名兼容性 + 跨平台一致性（Windows / macOS / Linux 文件系统都安全）
4. **任务名冲突处理**：同名任务冲突时（如同一项目内两个 `t07_fix`），新任务必须加时间戳后缀（如 `t07_fix_20260718`），保证文件名唯一不覆盖

**命名示例**：

| 场景 | 任务名 | 文件命名示例 |
|------|--------|--------------|
| 某升级第 7 任务 | `t07_learn_phase5` | `20260718_1030_t07_learn_phase5_spec.md` |
| 简单 bug 修复 | `bugfix_login_timeout_20260718` | `20260718_1400_bugfix_login_timeout_20260718_memory.md` |
| 同名冲突 | `t07_fix_20260718`（新）vs `t07_fix`（旧） | 两个独立任务，文件不覆盖 |

**与 §5 阶段1 自动生成文档目录的关系**：§5 阶段1 调用 `generate_docs.py --task {任务名}` 自动建 5 类文件夹，本节定义"任务名怎么取"——脚本按本节规则校验任务名格式，不合规直接报错拒绝执行（对齐铁律4 No Placeholders：不写"待定任务名"）。

**与 Memory First 的关系**：`write_project(task, content)` 落盘时 task 名进文件名（`YYYYMMDD_HHMM_{task}_memory.md`），task 名错 = 文件散落到错误位置 = 全局 `memory_main.md` 项目分段错位 = 下一轮 /plan 步骤1 读不到。

> 类比：案件编号——一个案子从立案到结案，所有材料（笔录 / 证据 / 判决）都按同一案件编号归档。编号一错，材料散落，下次接手翻不到。任务名就是案件编号，必须规范 + 唯一 + 全程一致。

---

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

### 阶段1：需求对齐——自动生成文档目录【硬性】

当判断任务为复杂任务（需要写spec/task）时，**自动触发**以下流程：

1. **提取任务名**：从用户需求中提取任务名（小写+下划线格式）
2. **自动生成文档结构**：调用 `scripts/generate_docs.py --task {任务名}`（默认 `--type all`），自动在 `docs_rj/` 下建 5 类常驻文件夹并生成带时间戳的模板；**项目记忆 `docs_rj/memory_rj/` 建在主 docs 内**
3. **读取模板**：打开生成的 `docs_rj/spec_rj/*_{任务名}_spec.md` / `docs_rj/task_rj/*_{任务名}_task.md` 模板文件
4. **填充内容**：按模板结构填充需求内容

生成结构（扁平）：

```
docs_rj/
├── spec_rj/      YYYYMMDD_HHMM_{任务名}_spec.md
├── task_rj/      YYYYMMDD_HHMM_{任务名}_task.md
├── handoff_rj/   YYYYMMDD_HHMM_{任务名}_handoff.md
├── memory_rj/    YYYYMMDD_HHMM_{任务名}_memory.md   ← 项目记忆，建在主 docs 内
├── archive_rj/   {task}_YYYYMMDD_HHMM/（按任务子文件夹聚合，任务启动时间戳从原文件名提取）
└── SUMMARY_RJ.md
```

> 📁 完整目录树 + 手动降级 bash + 脚本路径/任务名校验细则：见 [references/common/pda/document_specs.md](document_specs.md)「文件用途与位置 / 自动触发机制」（按需读，零系统依赖）。脚本自动检测主 docs 目录，无需手动指定路径。

**自动触发条件**：任务判断为"复杂"（一句话说不清）且需写完整三件套（spec/task/memory）。

**无需用户确认**：文档目录结构生成是标准流程，无需额外确认。

**硬规则**【硬性】：
- 阶段1未完成，禁止进入阶段2（哪怕你催）
- 每个task完成必须实际跑验证步骤，看到预期结果才能打勾（Verification-before-Completion）
- **Stop-the-line**：严重偏离spec/你明确反对/产出质量不可接受时，立即停下沟通
- 跨对话做不完就更新task.md+memory，下次接着干，不要赶进度跳步骤

---

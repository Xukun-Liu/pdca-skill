<!-- PDCA标签：A.persist A.tidy -->
<!-- 子标签场景：/act 阶段步骤细则（spec_main 刷新/ADR/风险/learn 门控/distill/前端面板） -->
<!-- 关键词清单：/act/act细则/spec_main刷新/ADR候选/风险候选/learn门控/distill/TASK_STATE/前端面板同步/收尾 -->
<!-- 引用范围：main -->

# /act 步骤细则（自 SKILL.md §6 下沉，唯一维护源）

> 版本：v1.1.0 | 创建：2026-08-01 | 更新：2026-10-28
> 阶段标签：A.persist A.tidy

> 📖 **什么时候读这个文件**：进入 /act 阶段，执行步骤 0 / 1.5 / 3 / 3.5 / 3.5a / 3.5b / 3.6 / 3.6a / 3.7 / 3.8 / 4 / 4.1 / 5 时必读。
> 🔴 **不要在这时候读**：/plan /do /check 阶段（SKILL.md §6 /act 节保留步骤总览 + 指针）。

---

## 步骤总览（自 SKILL.md §6 /act 下沉，唯一维护源）

0. **MUST FIX 清零门控【硬性·v1.0.0 新增】**：进 /act 前必须跑 `python scripts/validate_skill.py`，若存在 MUST FIX 项：
   - **禁止关闭任务**：MUST FIX 未清零时，任务状态只能 `pause`（不能 `completed`），TASK_STATE.md status=pending
   - **立即修复**：优先回 /do 修复 MUST FIX 项（同一会话内）
   - **跨会话降级**：若用户明确说"先关闭，下次修"，记录到 memory + TASK_STATE.md 留痕"MUST FIX 未清零，用户豁免"，允许 status=completed 但标注 `with_known_debt: true`
   - **原因**：历史执行中曾出现 MUST FIX 项从批次前遗留到收尾才修，技术债跨批次累积
1.5. **互动复盘【v1.0.4 硬性】**：详见下方「步骤 1.5：互动复盘」节。
1. **写项目记忆**：经 `write_project(task, content, memory_class=主分类)` 落 `docs_rj/memory_rj/{主分类}/{YYYYMM}/{task}_memory_*.md`（v1.0.4 标签文件夹结构）+ 全局 `memory/memory_main.md` 索引行（含 task/主分类/重要性/is_lesson/摘要/正文链接）；主分类 6 选 1（tech_solution/pitfall/workflow/tool_usage/decision/status，定义见 scripts/memory_tags.py 单点常量），未传时按内容推断、非法值兜底 workflow
2. **刷新 `{主docs}/SUMMARY_RJ.md`**（见 [summary_view.md](../../common/pa/summary_view.md) §三触发2）
3. **跑 `python scripts/handoff_tidy.py --task {任务名}`** 整理归档（含临时文件清理/死引用清理/漂移检查/平台记忆融入/五问预跑/loop_guard ledger 归档/**生成 `docs_rj/memory_rj/TASK_STATE_{task_id}.md`**）；**若 handoff_tidy 失败**（脚本异常/Python 缺失），至少手动 `write_project` 写 memory + 刷 SUMMARY + 手写 TASK_STATE.md，告警用户"handoff_tidy 失败，已手动落盘核心产出，下次 /act 补跑"；**手动 TASK_STATE.md 必须补一行 `learn_distill_pending: true`**（learn/distill 补跑挂起标记——下次 /act 步骤 3.6 检测到即强制补跑，防降级丢步骤【learn_gap_fix】）
3.5. **刷新 `spec_main_rj.md` §1§2§7 指针目标**【硬性】（数据源=TASK_STATE.md）：§1⑦状态总览链接（Glob 按文件名时间戳取最新，残留 `{xxx}` 占位文字必须替换为实际链接，取不到则保留+告警）、§2⑤任务大纲（最新任务置顶）、§7⑥ADR（新决策加行+TOP5 归档）；不重写 §3§4§5§6，刷新后更新 frontmatter `last_updated`。完整操作细则（Glob 规则/TOP5/降级分支）见本文件「步骤 3.5」节
3.5a. **§7.1 ADR 候选确认【硬性·REQ-009】**：handoff_tidy 报告 `adr_candidates` 逐条判定写入 §7.1（最新置顶+TOP5 归档）或明说"本次无新 ADR"（不说=偏离）；`adr_pending_agent=true` 未判定 = 偏离
3.5b. **§7.3 风险候选确认【硬性·REQ-009】**：同上判定 `risk_candidates` 写入 §7.3 或明说"本次无新风险"；§7.2/§7.4 由 handoff_tidy 自动刷新，无需 agent 干预
3.6. **learn 门控【自动触发·双条件·learn_gap_fix】**：跑 `python scripts/learn_tidy.py count --threshold 20`——门控双条件：①累积量≥阈值 ②检测到 TASK_STATE 挂起标记 `learn_distill_pending: true`（上次 /act 降级遗留；脚本自动扫描 TASK_STATE_*.md，命中时 JSON 输出 `pending_degraded_learn: true`），任一满足即 should_run=true；should_run=false 记录"learn 跳过"进步骤4；true 自动 `scan --dry-run` → reflect **仅产 proposals.md（禁应用，限 5 分钟）** → 等步骤4 adopt HARD-GATE；**补跑完成后将对应 TASK_STATE 的 learn_distill_pending 置 false（防每次 /act 重复触发）**；scan 无发现/失败（退码2）/用户喊停分别记录跳过
3.6a. **技能图谱自动刷新【自动触发·v1.0.1】**：跑 `python scripts/skill_graph_build.py --auto`（仅左轨 pdca，L0 安全级；记忆哈希未变缓存命中零成本跳过；taxonomy 缺失 [SKIP] exit 0；阶段失败 exit 2 不阻断 /act 仅记录 memory）
3.7. **读 Gate Evidence 确认闸门【硬性·handoff_gate_fix】**：不再靠 agent 自觉声明——读 TASK_STATE 的 Gate Evidence 段核对 4 闸门；证据不全时 `--mark-completed` 会被拒签（signoff_blocked，报告 blocked_gates 列出缺项）；用户强制完成需显式 `--force`，且 Sign-off 记 `forced: true` 审计标记
3.8. **前端面板同步（server_lite，可选）**：默认跳过；用户主动启用 server_lite 时提醒点「🔄 同步数据」刷新前端缓存
3.9. **整理文件夹【本次新增·命名+分类】**：归类散乱文件 + 新文件按时间前缀命名。① 归类：把工作目录散乱的版本包/发布包/参考素材归到 Johnny Decimal 顶层目录（`10-项目/20-领域/30-资源/40-归档/90-系统`，见 project_structure.md「文件夹分类」节）；② 命名：新产生的 spec/task/handoff 按 `YYYYMMDD_HHMM_{项目名}_{类型}_{任务名}.md` 时间前缀式命名（项目名缺省取当前目录名，`generate_docs.py --project` 可指定；memory 沿用 `YYYYMMDD_HHMM_{任务名}_memory.md`，见 document_specs.md 命名章节）；③ 复用 startup_tidy.py 的 PARA 下沉逻辑，不新建脚本；④ 脚本异常 → 手动归类 + 告警，不阻断 /act；⑤ 存量文件不翻改（渐进迁移）
4. **adopt HARD-GATE**（若步骤3.6 有 proposals）：呈现 proposals.md → 确认"adopt" → 备份原文件+应用编辑+write_project 写 memory；"跳过"记录跳过；"调整"重新 reflect；无 proposals 直接进步骤4.1
4.1. **distill 询问（经验采纳）**：跑 `python scripts/memory_distill.py distill --project {项目名} --output-dir docs_rj/learn_rj` → ≥1 条经验则 AskUserQuestion 展示 TOP3 问"是否采纳"（采纳/拒绝/稍后）；采纳经 write_project 写全局 `## {项目名}` 分段（importance_level=high, is_lesson=true, experience_tags 含 "adopted_lesson"）；0 条 → 输出一行可见告知「distill 完成：0 条新经验（无 is_lesson=true 条目可采纳）」再跳过，**禁止静默跳过**【learn_gap_fix】（脚本已加 NOTICE 行，agent 须复述）
5. **任务收尾 commit**【硬性·v1.0.0 新增】：/act 阶段最后，确保工作区干净（任务产出已 commit），避免交接/启动时看到未提交改动。
   - **触发条件**：/act 步骤1-4.1 全部完成后执行
   - **非 git 仓库降级**：若项目未用 git 管理（无 .git 目录），跳过本步，告警"非 git 仓库，建议初始化"
   - **执行流程**：①`git status` 检测工作区 → 无改动跳过记录"工作区干净"；有改动进 2 ②agent 构造 commit 消息（type/scope/subject/body + `Refs: {task_name}` footer，对齐 SKILL.md §0.6 任务名关联）③调 `python scripts/commit_lint.py lint "{消息}" --task {task_name}` 校验 → 不合规（exit_code=2）agent 修消息重校验（max 3次）④HARD-GATE 呈现 commit 消息给用户确认 → `git add -u` + `git commit`；用户跳过则记录到 memory"用户跳过 /act commit"
   - **与铁律6关系**：铁律6=改前 commit（回溯点），本步=改后 commit（干净状态）。两者互补，闭环回溯保障。
   - **消息规范**：遵循 Conventional Commits（见 [git_workflow.md](../../do/code/git_workflow.md) §2 + scripts/commit_lint.py R1-R10）
6. **/act 完成**：问用户"/act 完成（含 learn adopt + distill 询问 + 任务收尾 commit），产出将作为下一轮 /plan 的输入。进入下一轮 /plan 吗？"

---

## 步骤 1.5：互动复盘【硬性·v1.0.4】

写项目记忆（步骤 1）**之前**执行——先问后写，回答并入同一次 write_project 落盘（时序错了会产生两个记忆文件）。

- **问题生成规则**（动态 2-3 问，按任务内容定制）：
  1. **必问 1 问教训/风险**："这次任务哪里最容易再犯？"（或结合具体风险点，如"这次沙箱拦截的坑，下次新环境要怎么提前防？"）
  2. **必问 1 问决策依据**："为什么选这个方案不选另一个？"（引用本次实际对比过的方案）
  3. **选问 0-1 问下一步**："下次遇到类似情况，第一步做什么？"（仅当任务有明确可复用模式时问）
- **呈现方式**：AskUserQuestion 工具（选项+可自由输入）；工具异常时降级文字提问
- **回答落盘**：拼进 content 末尾的 `【互动复盘】` 段，格式：
  ```
  【互动复盘】
  Q1（教训）：这次哪里最容易再犯？
  A1：{用户回答}
  Q2（决策）：为什么选方案 B'？
  A2：{用户回答}
  ```
- **跳过语义**：用户说"跳过/不用/别问了" → SKIPPED，TASK_STATE.md 记一行"用户跳过互动复盘（{时间}）"，**不 BLOCKED**（对齐 SKILL.md §0 AskUserQuestion 跳过降级路径）；部分回答只落已答部分
- **/loop auto 无人值守**：不弹问题，自动 SKIPPED + TASK_STATE 留痕"loop_auto 无人值守，互动复盘跳过"
- **硬上限**：问题数 ≤3（ADD 用户长任务不超载）
- **三类任务问题样例**：
  - 技术任务：①"这次报错的根因，下次怎么提前识别？"②"为什么选 rglob 方案不改数据格式？"③"下个环境部署时第一步验证什么？"
  - 写作任务：①"这次的文风调整，哪条规则最容易被读者感知？"②"为什么选这个标题不选备选？"③"下一篇同题材直接复用什么？"
  - 发布任务：①"这次打包校验哪步最容易漏？"②"为什么排除这些文件入包？"③"下次发布前查什么清单？"

---

## 步骤 3.5：刷新 spec_main_rj.md §1§2§7 指针目标

（GAP2 修复，handoff_tidy 产出的 TASK_STATE.md 是数据源）

- **取最新硬性步骤【硬性】**：用 Glob 取最新文件，按文件名时间戳 `YYYYMMDD_HHMM` 降序取第一个（不用 mtime，避免 touch/checkout 漂移）；TASK_STATE 文件无时间戳，按"当前活跃任务名"匹配 `TASK_STATE_{task_id}.md`；**v1.0.4 起 memory_rj 为标签文件夹结构，Glob 模式用 `memory_rj/**/*_memory_*.md`（深层递归）**
- §1⑦当前状态总览：更新"最新项目记忆"链接（Glob `memory_rj/**/*_memory_*.md` 取最新，v1.0.4 深层递归）+ "最新任务状态"链接（取 `TASK_STATE_{当前活跃任务}.md`）+ "最近交接文档"链接（Glob `handoff_rj/*_handoff_*.md` 取最新）
- **占位文字恢复为链接【硬性·LOW-2 上轮遗留·M8 修复】**：实例中残留的模板格式占位文字（如 `{task}_memory_{YYYYMMDD_HHMM}.md`）必须替换为 Glob 取到的最新文件实际 markdown 链接（格式 `[文件名](./相对路径)`，如 `[spec_main_template_memory_20260718_1300.md](./memory_rj/spec_main_template_memory_20260718_1300.md)` 为写法示例，实际路径以 Glob 结果为准），不保留占位文字
  - **触发条件**：每次 /act 步骤 3.5 执行时，检测实例 §1/§2 链接是否为 `{xxx}` 格式占位文字，若是则替换
  - **降级方案**：若 Glob 取不到最新文件（如 memory_rj/ 为空或 Glob 失败），保留原占位文字，告警用户"§1/§2 链接未刷新，下次 /act 补刷"，不阻断 /act 流程
- §2⑤任务大纲：更新"当前活跃任务"表格（最新任务排第一行，状态从 TASK_STATE 确认）
- §7⑥ADR：若本次任务产生新关键决策（详见 spec_main_rj.md §7 ADR 写入条件），加一行 ADR-X（最新置顶，倒序）
  - **TOP 5 归档触发**：若加 ADR 后表格超过 5 行，按 [spec_main_template.md §7.1 归档规则](../../../assets/spec_main_template.md) 移除时间最老的指针行（memory_main.md 仍保留全量记录，无需手工写入）
- 不重写 §3§4§5§6（手工维护，改时才动）；刷新后更新 spec_main_rj.md frontmatter 的 `last_updated`
- **handoff_tidy 失败降级**：若步骤3 handoff_tidy 失败**且未手动补写 TASK_STATE.md**（最终无任何 TASK_STATE 产出），跳过本步骤，告警用户"spec_main_rj.md §1§2§7 指针未刷新，下次 /act 补刷"；若步骤3 已手动补写 TASK_STATE，则本步骤正常执行（基于手动 TASK_STATE 刷新 §1§2§7）

---

## 步骤 3.5a：§7.1 ADR 候选确认【硬性·REQ-009】

handoff_tidy 报告 `adr_candidates` 字段含脚本扫描 memory_rj 提取的 ADR 候选清单（≤5 条），agent 必须判定每条候选是否写入 §7.1 表格：
- 是 → 写入 §7.1 表格第一行（最新置顶）+ 触发 TOP 5 归档（>5 行移除最老）
- 否 → 明确说"本次无新 ADR"（留痕，不说=偏离）
- 报告 `adr_pending_agent=true` 时未做判定 = 偏离

---

## 步骤 3.5b：§7.3 风险候选确认【硬性·REQ-009】

handoff_tidy 报告 `risk_candidates` 字段含脚本扫描 task_rj 提取的风险候选清单（≤5 条），agent 必须判定每条候选是否写入 §7.3 表格：
- 是 → 写入 §7.3 表格第一行（最新置顶）
- 否 → 明确说"本次无新风险"（留痕，不说=偏离）

**§7.2/§7.4 自动刷新**：handoff_tidy 自动追加 §7.2 Sync Impact 行（检测 version 变更）+ §7.4 跨任务依赖行（扫 task_rj depends_on/blocks），无需 agent 干预。

---

## 步骤 3.5c：Gate Evidence 核对【硬性·handoff_gate_fix】

handoff_tidy 报告 `blocked_gates` 非空时，任务停在 pending，agent 必须**如实告知用户缺哪几扇闸门**（不口头声明完成）：
- 补证据 → 回 /check 步骤 6.5 补写 Gate Evidence 段 + 落盘 `docs_rj/check_rj/` 报告，重跑 handoff_tidy
- 用户强制完成 → 显式加 `--force`，Sign-off 记 `forced: true` 审计标记（可追溯）

---

## 步骤 3.6：learn 累积量门控【自动触发】

- 跑 `python scripts/learn_tidy.py count --threshold 20`
- should_run=false → 跳过 learn，记录到 memory"learn 跳过（累积量 N < 阈值 20）"，进步骤4
- should_run=true → 自动跑 `python scripts/learn_tidy.py scan --dry-run`（不询问）
- agent 读 scan_report.json + [references/act/learn/learn_cycle.md](../learn/learn_cycle.md) + [references/common/pc/adversarial_review.md](../../common/pc/adversarial_review.md) 做 reflect，产 proposals.md
- **reflect 阶段仅产 proposals.md，禁止应用任何 proposals（应用必须等步骤4 adopt HARD-GATE）**
- **reflect 阶段限时 5 分钟（agent 自检计时：reflect 前 record 开始时间，reflect 后 record 结束时间，差值>5 分钟则告警+跳过 adopt+记录 memory"learn reflect 超时"）**
- proposals.md 写入 `docs_rj/learn_rj/{timestamp}/`
- learn 产出路径经 `write_project` 写入 memory（回流下一轮 /plan，对应 A.learn 闭环）
- scan 无发现（scan_report.json 各字段为空）→ 跳过 adopt，记录"learn 无发现"
- scan 失败（退出码 2）→ 告警用户+跳过 learn+记录 memory"learn scan 失败"
- scan+reflect 期间用户喊"停" → 跳过 adopt，记录"learn 用户中断"到 memory

---

## 步骤 3.6a：技能图谱自动刷新【自动触发·v1.0.1】

跑 `python scripts/skill_graph_build.py --auto`：

- **--auto 约束**：强制 source=pdca（仅左轨，L0 安全级，不触发 security.md L2 扫描确认）+ skip_taxonomy（用上次 taxonomy 缓存）
- **记忆未变**（SHA256 缓存命中）→ 跳过全部阶段，零成本，直接继续
- **记忆已变** → 自动重算三阶段，更新 `~/.pdca-skill/data/docs_rj/skill_graph/` 四件套（md/csv/svg/manifest.json）
- **taxonomy 缓存缺失** → `[SKIP]` 提示 + exit 0，记录 memory"skill_graph SKIP（taxonomy 缺失）"，继续（由用户点名/手动全量补）
- **阶段失败** → auto 模式 exit 2，**不阻断** /act：记录 memory"skill_graph 自动刷新失败"后继续；手动全量模式 exit 1 阻断
- 输出路径已外置用户数据目录（`user_data_path.get_docs_rj_path()/skill_graph/`），升级 skill 不丢图谱

---

## 步骤 3.8：前端面板同步（server_lite，可选）

server_lite 当前不主动引导使用，本步骤默认跳过。若用户主动启用了 server_lite 管理台（`python run_server.py`，默认 http://127.0.0.1:5210），可提醒用户点右上角「🔄 同步数据」按钮刷新前端缓存。未启用则跳过，不阻断 /act 流程。

---

## 步骤 4.1：distill 询问（经验采纳）

/act 阶段 learn adopt 后（步骤4）或 learn 跳过后，跑 `python scripts/memory_distill.py distill --project {项目名} --output-dir docs_rj/learn_rj`：
- distill 产出≥1条经验 → 用 AskUserQuestion 展示 TOP3 经验问用户"是否采纳为长期经验？"（选项：采纳/拒绝/稍后）
- 用户采纳 → 经 `write_project` 写入 memory_main.md 对应"## {项目名}"分段（importance_level=high, is_lesson=true, experience_tags 含 "adopted_lesson"），不新建"## 经验库"段（与约束2分段规范一致）
- 用户拒绝/稍后 → 跳过，经验保留在 lessons.json 待后续采纳
- distill 产出0条 → 跳过询问，继续 /act

<!-- PDCA标签：A.persist A.tidy -->
<!-- 子标签场景：/act 阶段步骤细则（spec_main 刷新/ADR/风险/learn 门控/distill/前端面板） -->
<!-- 关键词清单：/act/act细则/spec_main刷新/ADR候选/风险候选/learn门控/distill/TASK_STATE/前端面板同步/收尾 -->
<!-- 引用范围：main -->

# /act 步骤细则（自 SKILL.md §6 下沉，唯一维护源）

> 版本：v1.0.4 | 创建：2026-08-01
> 阶段标签：A.persist A.tidy

> 📖 **什么时候读这个文件**：进入 /act 阶段，执行步骤 1.5 / 3.5 / 3.5a / 3.5b / 3.6 / 3.6a / 3.8 / 4.1 时必读。
> 🔴 **不要在这时候读**：/plan /do /check 阶段（SKILL.md §6 /act 节已含各步核心规则）。

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
- **占位文字恢复为链接【硬性·LOW-2 上轮遗留·M8 修复】**：实例中残留的模板格式占位文字（如 `{task}_memory_{YYYYMMDD_HHMM}.md`）必须替换为 Glob 取到的最新文件实际 markdown 链接（格式 `[文件名](./相对路径)`，如 `[spec_main_template_memory_20260718_1300.md](./memory_rj/spec_main_template_memory_20260718_1300.md)`），不保留占位文字
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

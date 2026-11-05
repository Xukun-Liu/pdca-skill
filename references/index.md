<!-- PDCA标签：P.route A.handoff -->
<!-- 子标签场景：references/ 导航索引、启动查找、交接结构说明 -->
<!-- 关键词清单：index/导航/索引/references目录/PDCA结构/子文件夹 -->

# references/ 目录索引

> 版本：v1.3.1 | 创建：2026-07-25 | 更新：2026-11-05（新增 chart_cookbook.md / report_pipeline.md；补登此前漏计/漏列的 multi_session.md、check_procedure.md、common/core 与 agent_factory；计数 58→61 对齐实测）| pdca-skill 参考模块导航
> 阶段标签：P.route A.handoff
>
> 本索引是 references/ 目录的导航地图。61 个参考模块按 PDCA 四环节 + common 融合区组织，看到路径即知用途。

---

## 一、目录结构概览

```
references/
├── index.md                  ← 你在这里（导航索引）
├── common/                   ← 跨 PDCA 阶段融合（30个）
│   ├── core/ (3个) 框架核心（常驻）
│   ├── agent_factory/ (1个) agent 工厂
│   ├── pa/   (4个) P+A 启动规划+归档闭环
│   ├── pc/   (2个) P+C 方案设计+验证审查
│   ├── pd/   (4个) P+D 方案设计+编码执行
│   ├── pda/  (2个) P+D+A 贯穿全流程
│   ├── dc/   (2个) D+C 执行+调试验证
│   ├── da/   (5个) D+A 执行+归档整理
│   └── style/ (7个) P+D 写作风格（特例，含 writing_style + article-writing 入口 + 5 子模块）
├── plan/                     ← P 环节：想清楚（13个）
│   ├── bootstrap/  (3个) P.bootstrap 启动恢复
│   ├── route/      (7个) P.route 路由判断
│   └── design/     (3个) P.design 方案设计
├── do/                       ← D 环节：动手做（11个）
│   ├── code/       (7个) D.code 编码
│   ├── comm/       (2个) D.comm 执行期任务流
│   └── danger/     (2个) D.danger 安全危险
├── check/                    ← C 环节：验结果（3个）
│   ├── check_procedure.md   C.verify 验收流程
│   ├── red_flags.md     C.reflexion 反思
│   └── loop_verifier.md C.verify 验证
└── act/                      ← A 环节：处理动作（4个）
    ├── learn/      (3个) A.learn 学习进化
    └── persist/    (1个) A.persist 落盘细则
```

---

## 二、分类规则

### 2.1 common/ 判定规则

文件头部 PDCA 标签**跨 2+ 母标签**（如 P+A、D+C）即进 common/，无例外。子文件夹名 = 融合的母标签字母拼接（小写）：

| 子文件夹 | 融合阶段 | 含义 | 文件数 |
|----------|----------|------|--------|
| pa/ | P+A | 启动规划 + 归档闭环 | 4 |
| `pc/` | P+C | 方案设计 + 验证审查 | 2 |
| `pd/` | P+D | 方案设计 + 编码执行 | 4 |
| `pda/` | P+D+A | 贯穿全流程 | 2 |
| `dc/` | D+C | 执行 + 调试验证 | 2 |
| `da/` | D+A | 执行 + 归档整理 | 5 |
| `style/` | P+D | 写作风格（子文件夹命名特例，按主题命名） | 7 |

> **嵌套例外条款（2026-08-06 新增）**：`style/` 下允许主题子目录（如 `style/article-writing/`），子模块文件不单独挂 PDCA 标签、不计入分类规则表，由入口文件（`style/article-writing.md`）链式加载。嵌套例外仅适用于 `style/` 主题化组织，其余子文件夹不得再嵌套。
> **聚合域例外条款（2026-08-31 新增）**：`common/da/` 兼作「交付呈现聚合域」——①汇报/交接类呈现模块（leader_report.md，仅 A.handoff）②vendored 嵌入式第三方模块（diagram-design.md 入口 + `diagram-design/` 随附子文件，PDCA 标签 D.code D.comm）按模块目录就近挂 `common/da/`，不受"单母标签进 do/"规则约束。vendored 子文件豁免版本块/孤儿/阶段标签校验（见 validate_skill.py `VENDORED_REF_PREFIXES`，禁止在该前缀放 pdca 原创文件）。

### 2.2 PDCA 单阶段归属规则

文件头部 PDCA 标签**只含 1 个母标签**时，归对应环节，再按子标签建子文件夹：

| 环节 | 子文件夹 | 子标签 | 含义 |
|------|----------|--------|------|
| `plan/` | `bootstrap/` | P.bootstrap | 启动恢复（3个） |
| `plan/` | `route/` | P.route | 路由判断（7个） |
| `plan/` | `design/` | P.design | 方案设计（3个） |
| `do/` | `code/` | D.code | 编码（7个） |
| `do/` | `comm/` | D.comm | 执行期任务流（2个） |
| `do/` | `danger/` | D.danger | 安全危险（2个） |
| `check/` | （不细分） | C.verify / C.reflexion | 验证/反思（3个） |
| `act/` | `learn/` | A.learn | 学习进化（3个） |
| `act/` | `persist/` | A.persist | 落盘细则（1个） |

> act/ 下 learn/ 按 A.learn 子标签建，persist/ 按 A.persist 子标签建。

---

## 三、快速查找指南（按任务场景）

| 你要做什么 | 该读哪个子文件夹 |
|------------|------------------|
| 启动新对话/恢复上下文 | `common/pa/`（working_memory_rules, summary_view）+ `plan/bootstrap/` |
| 路由判断该走什么流程 | `common/pa/`（trigger_hooks）+ `plan/route/` |
| 写方案/spec/task | `common/pda/`（document_specs）+ `common/pc/`（acceptance_criteria, adversarial_review）+ `plan/design/` |
| 写代码/改代码 | `do/code/`（code_rules）+ `common/pd/`（minimal_code_principles） |
| 调试报错 | `common/dc/`（debugging）+ `do/code/`（git_workflow 回滚） |
| 安全审查/危险操作 | `do/danger/`（security, loop_constraints） |
| 验收/对抗审查 | `common/pc/`（adversarial_review, acceptance_criteria）+ `check/` |
| 偏离自检/感觉不对 | `check/`（red_flags） |
| 交接/同步/整理 | `common/da/`（sync-matrix, hand-drawn-report, git_backup_cleanup） |
| 画专业图（架构图/时序图/甘特图/ER图等 39 种）/重绘 drawio·mermaid/导出 PNG·SVG | `common/da/`（diagram-design）；报告速览图仍 `common/da/`（hand-drawn-report，视觉同源） |
| 学习进化/prompt 优化 | `act/learn/` |
| 处理 Office/PDF/Excel/在文档里放图 | `do/code/`（office_processing, file_to_markdown）+ `common/pd/`（data_analysis, chart_cookbook） |
| 画数据图/选图表类型/matplotlib 中文乱码 | `common/pd/`（chart_cookbook） |
| 出一份数据报告（取数→计算→成稿→校验→分发） | `common/pd/`（report_pipeline）+ `common/da/`（leader_report）+ `common/pd/`（chart_cookbook） |
| 找/装/建外部 skill | `plan/route/`（skill_management, skill_security, skill_creation, agent_find） |
| 多项目管理 | `plan/bootstrap/`（multi_project） |
| 上下文压缩恢复 | `plan/bootstrap/`（compaction_recovery）+ `common/pa/`（working_memory_rules） |
| 副 agent 调度 | `common/pda/`（subagents_rj） |
| 检索注入/上下文过载（要塞什么、塞多少） | `common/core/`（retrieval_inject：L1 摘要 / L2 片段 / L3 全文 + 预算 + 去重 + 带源） |

---

## 四、文件归属速查表（61 个模块 × 所属子文件夹 × 引用范围）

> 计数口径：**不含** vendored 第三方包（`common/da/diagram-design/**`）与本索引自身。分布：plan 13 / do 11 / check 3 / act 4 / common 30。

> 引用范围列说明:标注该 reference 被哪些 agent 读取(`main` = 主 agent,其余为 9 个副 agent 简称)。详细反向索引见第七节。

### common/（30个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| placeholder_gate.md | common/core/ | D.comm C.verify | main + code_eng + doc_proc |
| retrieval_inject.md | common/core/ | P.route D.comm C.verify | main + code_eng |
| write_verify.md | common/core/ | D.comm C.verify A.persist | main + code_eng |
| agent_factory.md | common/agent_factory/ | P.design D.code | main + skill_mgmt |
| trigger_hooks.md | common/pa/ | P.route A.handoff | main + bootstrap |
| working_memory_rules.md | common/pa/ | P.bootstrap A.persist | main + bootstrap |
| summary_view.md | common/pa/ | P.bootstrap A.persist | main + bootstrap + sync |
| memory_governance.md | common/pa/ | P.bootstrap A.persist | main |
| acceptance_criteria.md | common/pc/ | P.design C.verify | main + spec_design |
| adversarial_review.md | common/pc/ | P.design C.adversarial | main + spec_design + learn_opt |
| minimal_code_principles.md | common/pd/ | P.design D.code | main + bootstrap |
| data_analysis.md | common/pd/ | P.design D.code | main + doc_proc |
| chart_cookbook.md | common/pd/ | P.design D.code | main + doc_proc |
| report_pipeline.md | common/pd/ | P.design D.comm | main + doc_proc |
| document_specs.md | common/pda/ | P.design D.code A.handoff | main + spec_design |
| subagents_rj.md | common/pda/ | P.route D.code A.handoff | main（元数据） |
| communication_rules.md | common/dc/ | D.comm C.verify | main + code_eng |
| debugging.md | common/dc/ | D.code C.verify | main + code_eng |
| hand-drawn-report.md | common/da/ | D.comm A.handoff | main + doc_proc + sync |
| diagram-design.md | common/da/ | D.code D.comm | main + doc_proc |
| leader_report.md | common/da/ | A.handoff | main |
| git_backup_cleanup.md | common/da/ | A.tidy D.danger | main + code_eng |
| sync-matrix.md | common/da/ | D.code A.tidy | main + sync |
| writing_style.md | common/style/ | P.design D.comm | main |
| article-writing.md | common/style/ | P.design D.comm C.verify | main |
| forum-prose.md | common/style/article-writing/ | 链式加载（入口） | main |
| reality.md | common/style/article-writing/ | 链式加载（入口） | main |
| fiction.md | common/style/article-writing/ | 链式加载（入口） | main |
| formats.md | common/style/article-writing/ | 链式加载（入口） | main |
| revision.md | common/style/article-writing/ | 链式加载（入口） | main |
| write_verify.md | common/core/ | C.verify D.code | main + code_eng |
| placeholder_gate.md | common/core/ | C.verify D.code | main + code_eng + doc_proc |
| retrieval_inject.md | common/core/ | C.verify D.comm | main + doc_proc |
| agent_factory.md | common/agent_factory/ | D.code A.persist | main + skill_mgmt（Agent 三件套模板说明，配套 `scripts/agent_factory/`） |

> 🆕 v1.1.0 `common/core/`（硬门区，3 个）：`write_verify.md`（C4 写后校验）、`placeholder_gate.md`（C1 占位符硬门）、`retrieval_inject.md`（C6 检索注入）——已登记入上表。
>
> 🆕 v1.1.0 `common/agent_factory/`：`agent.json`（元数据）/ `AGENT.md`（首行硬门 `[subagent: <name>]`，上表登记项）/ `memory/memory_agent.md`（agent 记忆骨架）+ README；配套脚本 `scripts/agent_factory/`（new_agent / register_agent / validate_agent / agent_memory，退出码 0 通过 / 1 内容问题 / 2 环境错误）。

### plan/（13个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| bootstrap.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| compaction_recovery.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| multi_project.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| usage_examples.md | plan/route/ | P.route | main + bootstrap |
| skill_management.md | plan/route/ | P.route | main + skill_mgmt |
| skill_security.md | plan/route/ | P.route | main + skill_mgmt |
| skill_creation.md | plan/route/ | P.route | main + skill_mgmt |
| agent_find.md | plan/route/ | P.route | main + skill_mgmt |
| loop_triage.md | plan/route/ | P.route | main + loop |
| design_patterns.md | plan/design/ | P.design | main + bootstrap |
| project_structure.md | plan/design/ | P.design | main + bootstrap |
| goal_brief.md | plan/design/ | P.design | main |
| plan_procedure.md | plan/route/ | P.route | main（/plan 全流程细则，SKILL.md §6 指针目标） |

### do/（11个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| browser_automation.md | do/code/ | D.code | main + browser |
| code_rules.md | do/code/ | D.code | main + code_eng |
| file_to_markdown.md | do/code/ | D.code | main + doc_proc |
| git_workflow.md | do/code/ | D.code | main + code_eng |
| html_ppt_creation.md | do/code/ | D.code | main + doc_proc |
| multi_session.md | do/code/ | D.code | main + code_eng |
| office_processing.md | do/code/ | D.code | main + doc_proc |
| security.md | do/danger/ | D.danger | main + code_eng |
| loop_constraints.md | do/danger/ | D.danger | main + loop |
| insert_new_task.md | do/comm/ | D.comm | main |
| do_procedure.md | do/comm/ | D.comm | main（/do 全流程细则，SKILL.md §6 指针目标） |

### check/（3个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| red_flags.md | check/ | C.reflexion | main + code_eng |
| loop_verifier.md | check/ | C.verify | main + loop |
| check_procedure.md | check/ | C.verify C.adversarial | main（/check 全流程细则，SKILL.md §6 指针目标） |

### act/（4个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| learn_cycle.md | act/learn/ | A.learn | main + learn_opt |
| prompt_optimization.md | act/learn/ | A.learn | main + learn_opt |
| skill_graph.md | act/learn/ | A.learn | main + learn_opt |
| act_procedure.md | act/persist/ | A.persist A.tidy | main |

---

## 五、新增 reference 文件时的归属判定

新增文件时，按以下步骤判定归属：

1. **确定 PDCA 标签**：根据文件内容判定它服务于哪些 PDCA 阶段
2. **跨 2+ 母标签？** → 进 common/ 对应融合子文件夹（如 P+A → common/pa/）
3. **只 1 个母标签？** → 进对应环节子文件夹（如 P.design → plan/design/）
4. **标注引用范围**：在文件头部第 3 行后加 `<!-- 引用范围：main + xxx_agent -->`（见第四节列说明）
5. **更新本索引**：在第四节速查表加一行（含引用范围列）+ 在第六节反向索引加一行

> 规则要点：common/ 判定无例外，跨阶段即进 common/，避免主观判断。

---

## 六、反向索引：reference → agent

> 反向查表:已知 reference 文件,查"哪些 agent 会读它"。数据源为 [subagents_rj.md](common/pda/subagents_rj.md) 第二节各副 agent 知识库。
>
> **简称对照**: `main` = 主 agent;`bootstrap` = bootstrap_agent_pdca;`skill_mgmt` = skill_mgmt_agent_pdca;`spec_design` = spec_design_agent_pdca;`code_eng` = code_eng_agent_pdca;`doc_proc` = doc_proc_agent_pdca;`loop` = loop_agent_pdca;`learn_opt` = learn_opt_agent_pdca;`sync` = sync_agent_pdca;`browser` = browser_agent_pdca。
>
> **共读文件高亮**: 标 ⭐ 的文件被 2+ 副 agent 引用,改这些文件时需注意对多 agent 的影响。

### 6.1 按 agent 分组(正向:agent → reference)

| agent | 知识库(reference 数) | 引用的 reference |
|------|----------------------|------------------|
| bootstrap_agent | 10 | plan/bootstrap/{bootstrap, compaction_recovery, multi_project}.md · common/pa/{summary_view, working_memory_rules, trigger_hooks}.md · plan/route/usage_examples.md · plan/design/{project_structure, design_patterns}.md · common/pd/minimal_code_principles.md |
| skill_mgmt_agent | 4 | plan/route/{skill_management, skill_security, skill_creation, agent_find}.md |
| spec_design_agent | 3 | common/pc/{acceptance_criteria, adversarial_review}.md · common/pda/document_specs.md |
| code_eng_agent | 8 | do/code/{code_rules, git_workflow, multi_session}.md · common/da/git_backup_cleanup.md · common/dc/{debugging, communication_rules}.md · check/red_flags.md · do/danger/security.md |
| doc_proc_agent | 8 | do/code/{office_processing, file_to_markdown, html_ppt_creation}.md · common/pd/{data_analysis, chart_cookbook, report_pipeline}.md · common/da/{hand-drawn-report, diagram-design}.md |
| loop_agent | 3 | plan/route/loop_triage.md · do/danger/loop_constraints.md · check/loop_verifier.md |
| learn_opt_agent | 4 | act/learn/{learn_cycle, prompt_optimization, skill_graph}.md · common/pc/adversarial_review.md |
| sync_agent | 3 | common/da/{sync-matrix, hand-drawn-report}.md · common/pa/summary_view.md |
| browser_agent | 1 | do/code/browser_automation.md |

### 6.2 按 reference 分组(反向:reference → agent)

| reference | 路径 | 被哪些 agent 读 |
|-----------|------|-----------------|
| bootstrap.md | plan/bootstrap/ | main + bootstrap |
| compaction_recovery.md | plan/bootstrap/ | main + bootstrap |
| multi_project.md | plan/bootstrap/ | main + bootstrap |
| usage_examples.md | plan/route/ | main + bootstrap |
| skill_management.md | plan/route/ | main + skill_mgmt |
| skill_security.md | plan/route/ | main + skill_mgmt |
| skill_creation.md | plan/route/ | main + skill_mgmt |
| agent_find.md | plan/route/ | main + skill_mgmt |
| loop_triage.md | plan/route/ | main + loop |
| design_patterns.md | plan/design/ | main + bootstrap |
| project_structure.md | plan/design/ | main + bootstrap |
| goal_brief.md | plan/design/ | main |
| trigger_hooks.md | common/pa/ | main + bootstrap |
| working_memory_rules.md | common/pa/ | main + bootstrap |
| summary_view.md ⭐ | common/pa/ | main + bootstrap + sync |
| memory_governance.md | common/pa/ | main |
| acceptance_criteria.md | common/pc/ | main + spec_design |
| adversarial_review.md ⭐ | common/pc/ | main + spec_design + learn_opt |
| minimal_code_principles.md | common/pd/ | main + bootstrap |
| data_analysis.md | common/pd/ | main + doc_proc |
| chart_cookbook.md | common/pd/ | main + doc_proc |
| report_pipeline.md | common/pd/ | main + doc_proc |
| document_specs.md | common/pda/ | main + spec_design |
| subagents_rj.md | common/pda/ | main(元数据) |
| communication_rules.md | common/dc/ | main + code_eng |
| debugging.md | common/dc/ | main + code_eng |
| hand-drawn-report.md ⭐ | common/da/ | main + doc_proc + sync |
| leader_report.md | common/da/ | main |
| diagram-design.md | common/da/ | main + doc_proc |
| git_backup_cleanup.md | common/da/ | main + code_eng |
| sync-matrix.md | common/da/ | main + sync |
| writing_style.md | common/style/ | main |
| article-writing.md | common/style/ | main |
| forum-prose.md | common/style/article-writing/ | main |
| reality.md | common/style/article-writing/ | main |
| fiction.md | common/style/article-writing/ | main |
| formats.md | common/style/article-writing/ | main |
| revision.md | common/style/article-writing/ | main |
| browser_automation.md | do/code/ | main + browser |
| code_rules.md | do/code/ | main + code_eng |
| file_to_markdown.md | do/code/ | main + doc_proc |
| git_workflow.md | do/code/ | main + code_eng |
| multi_session.md | do/code/ | main + code_eng |
| html_ppt_creation.md | do/code/ | main + doc_proc |
| office_processing.md | do/code/ | main + doc_proc |
| security.md | do/danger/ | main + code_eng |
| loop_constraints.md | do/danger/ | main + loop |
| insert_new_task.md | do/comm/ | main |
| red_flags.md | check/ | main + code_eng |
| loop_verifier.md | check/ | main + loop |
| learn_cycle.md | act/learn/ | main + learn_opt |
| prompt_optimization.md | act/learn/ | main + learn_opt |
| skill_graph.md | act/learn/ | main + learn_opt |
| act_procedure.md | act/persist/ | main |

### 6.3 统计摘要

| 指标 | 值 |
|------|-----|
| reference 总数 | 61（口径：不含 vendored 第三方包 `common/da/diagram-design/**` 与本索引自身） |
| 仅 main 读的 reference | 15（subagents_rj.md 元数据 + insert_new_task.md + act_procedure.md + plan_procedure.md + do_procedure.md + check_procedure.md + memory_governance.md + writing_style.md + goal_brief.md + article-writing 入口 + 5 子模块） |
| 被 2+ 副 agent 共读的 reference | 3（summary_view⭐、adversarial_review⭐、hand-drawn-report⭐） |
| 知识库最大的副 agent | bootstrap_agent(10 个 reference) |
| 知识库最小的副 agent | browser_agent(1 个 reference) |
| 副 agent 总数 | 9 |

---

## 七、版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-07-25 | 初版：从扁平 36 文件重构为 PDCA 四环节 + common 融合区子文件夹结构 |
| v1.1.0 | 2026-08-01 | SKILL.md 瘦身同步：登记 5 个模块（memory_governance/writing_style/goal_brief 补登记 + insert_new_task/act_procedure 新增）；目录/计数/agent 引用更新 |
| v1.2.0 | 2026-08-06 | 融合文章写作模块：41→47、common 16→22、style 1→7（article-writing 入口 + 5 子模块）；2.1 补嵌套例外条款；顺手修 agent 知识库计数漂移（bootstrap 11→10 / spec_design 5→3 / code_eng 8→7 / doc_proc 5→4，以 subagents_rj.md 正向配置为权威源） |
| v1.2.1 | 2026-08-06 | 对抗审查第 1 轮修复：common 21→22、style 6→7、分类规则表 style 行 1→7（补入口文件计数）；速查表 memory_governance/goal_brief 引用范围列对齐 main；头部版本同步 v1.2.1 |
| v1.2.2 | 2026-08-10 | data_analysis.md v1.0.0→v1.1.0 内容变更触发索引版本刷新（新增7章方法论：数据质量评估/趋势分析/结构拆解/异常识别/可视化升级/报告合成/数据合并；描述列/PDCA标签/引用范围均不变；SKILL.md §3 资源索引描述同步更新）|
| v1.2.3 | 2026-08-13 | 融合 HTML/PPT 制作：新增 html_ppt_creation.md（D.code），47→48、do 8→9、code 5→6、doc_proc_agent 4→5；速查表 + 反向索引同步 |
| v1.2.4 | 2026-08-20 | 融合建 Skill 参考：新增 skill_creation.md（P.route，方法论提炼自外部开源资产，归属见包级 NOTICE），48→49、plan 11→12、route 5→6、skill_mgmt_agent 3→4；速查表 + 正/反向索引同步 |
| v1.2.5 | 2026-08-20 | 对抗审查修复（14 HIGH）：目录树/分类表 plan·route 计数同步（11→12、5→6）、§6.2 反向索引表补 skill_creation.md 行（修正 v1.2.4"反向索引同步"未兑现）、subagents_rj/config json 权威源同步（见各文件自身版本） |
| v1.2.6 | 2026-08-25 | v1.0.4 新增 leader_report.md（common/da/，A.handoff，领导汇报六段结构），49→50、common 22→23；速查表 + 总数同步；触发钩子/仲裁规则见 trigger_hooks.md v1.1.8 与 SKILL.md |
| v1.2.7 | 2026-08-31 | 画图双轨升级：新增 diagram-design.md 入口（common/da/，D.code D.comm，嵌入式 diagram-design v2.6.7 MIT，vendored 子目录豁免校验），50→51、common 22→24（还 v1.2.6 leader_report 目录树欠账）、da 3→5、doc_proc 5→6；头部版本还旧账 v1.2.5→v1.2.7；§2.1 加聚合域例外条款 |
| v1.3.0 | 2026-10-28 | v1.1.0 索引重写：计数按实测口径统一为 58 个非 vendored 模块（plan 13 / do 10 / check 3 / act 4 / common 28），明确排除 `common/da/diagram-design/**` 与本索引自身；补登 core 三文件 + agent_factory.md；新增 plan/do/check 三个 procedure 指针文件行；资源导图模块数 49→58 |
| v1.3.1 | 2026-11-05 | 数据分析/作图/汇报线升级：新增 chart_cookbook.md（common/pd/，P.design D.code）与 report_pipeline.md（common/pd/，P.design D.comm），58→61（同时补登此前漏计/漏列的 multi_session.md、check_procedure.md、common/core 三件与 agent_factory）；do 10→11、common 28→30；§三 补 3 行场景、§6.1 doc_proc 6→8 / code_eng 7→8、§6.2 补 3 行、§6.3 与文末导图计数同步 |

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

### 📚 资源索引导图（什么情况读什么文件）

> 📌 references/ 目录已按 PDCA 四环节重构，导航索引见 [references/index.md](index.md)

```
资源索引（触发→文件）
│
├─ 🗂️ 导航
│   └─ 查找 references/ 结构 → [references/index.md](index.md)（61 个模块 × PDCA 子文件夹归属速查表）
│
├─ 📝 模板（复制用）
│   ├─ 写项目总spec → assets/spec_main_template.md（项目级 source of truth 模板·实例 docs_rj/spec_main_{项目名}.md）
│   ├─ 写spec → assets/spec_template.md
│   ├─ 写task → assets/task_template.md
│   ├─ 写市场调研报告 → assets/market_research_template.md（9 段+6 项质检·/plan 步骤4a.5 用）
│   ├─ 记归档日志 → assets/daily_log_template.md
│   └─ 记经验 → docs_rj/memory_rj/{task}_memory_YYYYMMDD_HHMM.md（经 write_project 自动 upsert 全局 memory_main）
│
├─ 📖 规则参考（按需读，什么都不确定时先翻red_flags.md）
│   ├─ 出问题/报错/修不好 → references/common/dc/debugging.md（四步调试+3-Strike+Reflexion）
│   ├─ 准备写代码 → references/do/code/code_rules.md（四原则+HARD-GATE）
│   ├─ 准备写文档/spec → references/common/pda/document_specs.md（No Placeholders+Self-Review）
│   ├─ 不确定该不该继续/感觉不对劲 → references/check/red_flags.md（偏离信号+理性化反驳表）
│   ├─ 准备审方案/挑刺/大改后审查 → references/common/pc/adversarial_review.md（第一性原理拆解+对抗性审查流程）
│   ├─ 定验收标准/写 DoD/验收严格点 → references/common/pc/acceptance_criteria.md（DoD+Given/When/Then+4道质量闸门）
│   ├─ 处理 Office 文档（PDF/Word/PPT/Excel 读写改转合并提取）→ references/do/code/office_processing.md（纯本地工具，内网可用）
│   ├─ 做 HTML 网页/落地页/前端页面 → references/do/code/html_ppt_creation.md（HTML/PPT 制作自包含方法论，手写 HTML/CSS/JS，内网可用）
│   ├─ 做 PPT/幻灯片/演示文稿 → references/do/code/html_ppt_creation.md（HTML/PPT 制作自包含方法论，python-pptx / PptxGenJS / HTML 幻灯片，内网可用）
│   ├─ 画专业图（架构图/时序图/甘特图/ER图/泳道图/桑基图/鱼骨图/看板图/类图等 39 种）/重绘 drawio·mermaid/导出 PNG·SVG → references/common/da/diagram-design.md（嵌入式 diagram-design v2.6.7 MIT：39 图型+自包含 HTML+校验脚本；报告速览图仍走 hand-drawn-report.md，视觉同源）
│   ├─ 把文件转成 Markdown（PDF/Word/PPT/Excel/HTML→MD）→ references/do/code/file_to_markdown.md（纯Python离线可用，一键转MD）
│   ├─ 做 Excel 数据分析（清洗/透视/统计/图表/预测/看板/数据质量/趋势分析/结构拆解/异常识别/报告合成/数据合并）→ references/common/pd/data_analysis.md（纯本地，内网可用）
│   ├─ 画数据图/选图表类型/matplotlib 中文乱码/Excel 活图 vs Word 插图 → references/common/pd/chart_cookbook.md（关系驱动选型 6 类 + 6 套可跑模板 + 诚实性 6 条红线）
│   ├─ 出一份数据报告（取数→计算→成稿→校验→分发）→ references/common/pd/report_pipeline.md（四段式骨架 + 对账四道 + 六类断言 + G1–G4 交付门禁）
│   ├─ memory怎么读写 → references/common/pa/working_memory_rules.md（RAM/Disk+存盘检查点+5问）
│   ├─ 记忆治理/容量超限/记忆归档降级 → references/common/pa/memory_governance.md（治理工具+容量阈值+隔离+回滚）
│   ├─ 文件放哪/目录结构 → references/plan/design/project_structure.md
│   ├─ 沟通怎么说/怎么问问题 → references/common/dc/communication_rules.md
│   ├─ 浏览器自动化/网页操作/自动填表 → references/do/code/browser_automation.md（Agent操作浏览器+RPA）
│   ├─ 安全边界/什么不能碰 → references/do/danger/security.md
│   ├─ 首次使用/文件缺失/Bootstrap初始化 → references/plan/bootstrap/bootstrap.md（引导式创建，不静默）
│   ├─ 文档汇总视图/根索引 → references/common/pa/summary_view.md（SUMMARY_RJ.md 规范+漂移检查）
│   ├─ 用户技能图谱/能力画像/掌握度分析 → references/act/learn/skill_graph.md（三段式：已掌握/未掌握/额外掌握，A.learn）
│   ├─ 版本同步矩阵/规则一致性核对 → references/common/da/sync-matrix.md（升级后核对版本号/死引用/规则一致性）
│   ├─ 给领导汇报/向上汇报/出汇报文档/周报月报/SCQA/金字塔原理/结论先行/MECE → references/common/da/leader_report.md（六段结构汇报文档：结论→进展→数据→风险→计划→求助 + SCQA 开场四问 + 金字塔四原则 + MECE 检查 + 口径三状态，v1.1.0）
│   ├─ git 备份清理 5 阶段 → references/common/da/git_backup_cleanup.md（手动备份/自动备份/历史清理/回收/校验）
│   ├─ git 工作流规范 → references/do/code/git_workflow.md（commit 规范/分支策略/标签管理/冲突处理）
│   ├─ 执行中插入新任务/打断处置 → references/do/comm/insert_new_task.md（4步打断流程/挂起/恢复/边界case）
│   ├─ 校验 commit message 格式 → scripts/commit_lint.py（纯 Python，零依赖，9 条规则）
│   ├─ 安装 commit-msg hook → scripts/commit_lint_install.py（install/uninstall/status）
│   ├─ goal_brief/任务书/防作弊/反向验证/暗卷/多agent → references/plan/design/goal_brief.md（参考项目 机制详述：六节结构/防五种死法/法与情报/明暗卷/探索型改四处）
│   ├─ 戏文/训话/写作风格/大白话 → references/common/style/writing_style.md（参考项目 写作风格：大白话规范/戏文三铁律/训话6句/标题表15个/语气句5条/画饼4条）
│   ├─ 写文章/写知乎/写公众号/写博客/写小说/写故事/写人物稿/写口播稿/写演讲稿/活人感/文风/长文 → references/common/style/article-writing.md（活人感写作入口：按任务链式加载 article-writing/ 5 子模块；写作任务不生成 spec/task，直接出稿）
│   ├─ /act 步骤细则（spec_main刷新/ADR/learn门控）→ references/act/persist/act_procedure.md（/act 阶段必读）
│   ├─ 写完文件要确认真的写进去了 → references/common/core/write_verify.md（C4 写后校验硬门：存在/非空/关键块/无BOM 四查 + write_project 回执核对）
│   ├─ 交付前扫 TBD/待补充/伪代码 → references/common/core/placeholder_gate.md（C1 占位符硬门：validate_skill.py --placeholder-check，命中退码 1）
│   ├─ 检索结果要塞进上下文/怕过载 → references/common/core/retrieval_inject.md（C6 检索注入：L1摘要/L2片段/L3全文三档 + 预算 + 去重 + 带源）
│   ├─ 升级后核对数据/文档一致性、出运行报告、看健康趋势 → scripts/data_verify.py（版本号/死引用/口径三状态）· scripts/run_report.py（做了什么/改了哪些文件/耗时）· scripts/health_report.py（体量/记忆增长/死链趋势）
│   ├─ 建 agent/写 agent/定义副 agent/agent 注册表/agent 记忆 → references/common/agent_factory/agent_factory.md（Agent 三件套模板 agent.json+AGENT.md+memory_agent.md + 使用说明；脚本 scripts/agent_factory/ 四件：new_agent/register_agent/validate_agent/agent_memory，统一退出码 0 通过 / 1 内容问题 / 2 环境错误）
│   ├─ 涉及专业领域能力 → 见 references/plan/route/skill_management.md 先搜专用 Skill
│   └─ 建skill/创建skill/新建技能/写一个skill/做一个skill/skill开发/改skill/优化skill/测试skill/skill模板 → references/plan/route/skill_creation.md（意图捕获4问/四件套结构/三级渐进加载/description写法/测试迭代循环）
│
└─ 🧪 测试验证：evals/evals.json（典型场景+预期响应+断言）
```

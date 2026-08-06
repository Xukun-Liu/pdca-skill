<!-- PDCA标签：P.route A.handoff -->
<!-- 子标签场景：references/ 导航索引、启动查找、交接结构说明 -->
<!-- 关键词清单：index/导航/索引/references目录/PDCA结构/子文件夹 -->

# references/ 目录索引

> 版本：v1.0.0 | 创建：2026-07-25 | riji-skill 参考模块导航
> 阶段标签：P.route A.handoff
>
> 本索引是 references/ 目录的导航地图。47 个参考模块按 PDCA 四环节 + common 融合区组织，看到路径即知用途。

---

## 一、目录结构概览

```
references/
├── index.md                  ← 你在这里（导航索引）
├── common/                   ← 跨 PDCA 阶段融合（21个）
│   ├── pa/   (4个) P+A 启动规划+归档闭环
│   ├── pc/   (2个) P+C 方案设计+验证审查
│   ├── pd/   (2个) P+D 方案设计+编码执行
│   ├── pda/  (2个) P+D+A 贯穿全流程
│   ├── dc/   (2个) D+C 执行+调试验证
│   ├── da/   (3个) D+A 执行+归档整理
│   └── style/ (6个) P+D 写作风格（特例，含 article-writing 入口 + 5 子模块）
├── plan/                     ← P 环节：想清楚（11个）
│   ├── bootstrap/  (3个) P.bootstrap 启动恢复
│   ├── route/      (5个) P.route 路由判断
│   └── design/     (3个) P.design 方案设计
├── do/                       ← D 环节：动手做（8个）
│   ├── code/       (5个) D.code 编码
│   ├── comm/       (1个) D.comm 执行期任务流
│   └── danger/     (2个) D.danger 安全危险
├── check/                    ← C 环节：验结果（2个）
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
| `pd/` | P+D | 方案设计 + 编码执行 | 2 |
| `pda/` | P+D+A | 贯穿全流程 | 2 |
| `dc/` | D+C | 执行 + 调试验证 | 2 |
| `da/` | D+A | 执行 + 归档整理 | 3 |
| `style/` | P+D | 写作风格（子文件夹命名特例，按主题命名） | 1 |

> **嵌套例外条款（2026-08-06 新增）**：`style/` 下允许主题子目录（如 `style/article-writing/`），子模块文件不单独挂 PDCA 标签、不计入分类规则表，由入口文件（`style/article-writing.md`）链式加载。嵌套例外仅适用于 `style/` 主题化组织，其余子文件夹不得再嵌套。

### 2.2 PDCA 单阶段归属规则

文件头部 PDCA 标签**只含 1 个母标签**时，归对应环节，再按子标签建子文件夹：

| 环节 | 子文件夹 | 子标签 | 含义 |
|------|----------|--------|------|
| `plan/` | `bootstrap/` | P.bootstrap | 启动恢复（3个） |
| `plan/` | `route/` | P.route | 路由判断（5个） |
| `plan/` | `design/` | P.design | 方案设计（3个） |
| `do/` | `code/` | D.code | 编码（5个） |
| `do/` | `comm/` | D.comm | 执行期任务流（1个） |
| `do/` | `danger/` | D.danger | 安全危险（2个） |
| `check/` | （不细分） | C.verify / C.reflexion | 验证/反思（2个） |
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
| 学习进化/prompt 优化 | `act/learn/` |
| 处理 Office/PDF/Excel | `do/code/`（office_processing, file_to_markdown）+ `common/pd/`（excel_analysis） |
| 找/装外部 skill | `plan/route/`（skill_management, skill_security, agent_find） |
| 多项目管理 | `plan/bootstrap/`（multi_project） |
| 上下文压缩恢复 | `plan/bootstrap/`（compaction_recovery）+ `common/pa/`（working_memory_rules） |
| 副 agent 调度 | `common/pda/`（subagents_rj） |

---

## 四、文件归属速查表（47 个模块 × 所属子文件夹 × 引用范围）

> 引用范围列说明:标注该 reference 被哪些 agent 读取(`main` = 主 agent,其余为 9 个副 agent 简称)。详细反向索引见第七节。

### common/（21个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| trigger_hooks.md | common/pa/ | P.route A.handoff | main + bootstrap |
| working_memory_rules.md | common/pa/ | P.bootstrap A.persist | main + bootstrap |
| summary_view.md | common/pa/ | P.bootstrap A.persist | main + bootstrap + sync |
| memory_governance.md | common/pa/ | P.bootstrap A.persist | main + bootstrap |
| acceptance_criteria.md | common/pc/ | P.design C.verify | main + spec_design |
| adversarial_review.md | common/pc/ | P.design C.adversarial | main + spec_design + learn_opt |
| minimal_code_principles.md | common/pd/ | P.design D.code | main + bootstrap |
| excel_analysis.md | common/pd/ | P.design D.code | main + doc_proc |
| document_specs.md | common/pda/ | P.design D.code A.handoff | main + spec_design |
| subagents_rj.md | common/pda/ | P.route D.code A.handoff | main（元数据） |
| communication_rules.md | common/dc/ | D.comm C.verify | main + code_eng |
| debugging.md | common/dc/ | D.code C.verify | main + code_eng |
| hand-drawn-report.md | common/da/ | D.comm A.handoff | main + doc_proc + sync |
| git_backup_cleanup.md | common/da/ | A.tidy D.danger | main + code_eng |
| sync-matrix.md | common/da/ | D.code A.tidy | main + sync |
| writing_style.md | common/style/ | P.design D.comm | main |
| article-writing.md | common/style/ | P.design D.comm C.verify | main |
| forum-prose.md | common/style/article-writing/ | 链式加载（入口） | main |
| reality.md | common/style/article-writing/ | 链式加载（入口） | main |
| fiction.md | common/style/article-writing/ | 链式加载（入口） | main |
| formats.md | common/style/article-writing/ | 链式加载（入口） | main |
| revision.md | common/style/article-writing/ | 链式加载（入口） | main |

### plan/（11个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| bootstrap.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| compaction_recovery.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| multi_project.md | plan/bootstrap/ | P.bootstrap | main + bootstrap |
| usage_examples.md | plan/route/ | P.route | main + bootstrap |
| skill_management.md | plan/route/ | P.route | main + skill_mgmt |
| skill_security.md | plan/route/ | P.route | main + skill_mgmt |
| agent_find.md | plan/route/ | P.route | main + skill_mgmt |
| loop_triage.md | plan/route/ | P.route | main + loop |
| design_patterns.md | plan/design/ | P.design | main + bootstrap |
| project_structure.md | plan/design/ | P.design | main + bootstrap |
| goal_brief.md | plan/design/ | P.design | main + spec_design + code_eng |

### do/（8个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| browser_automation.md | do/code/ | D.code | main + browser |
| code_rules.md | do/code/ | D.code | main + code_eng |
| file_to_markdown.md | do/code/ | D.code | main + doc_proc |
| git_workflow.md | do/code/ | D.code | main + code_eng |
| office_processing.md | do/code/ | D.code | main + doc_proc |
| security.md | do/danger/ | D.danger | main + code_eng |
| loop_constraints.md | do/danger/ | D.danger | main + loop |
| insert_new_task.md | do/comm/ | D.comm | main |

### check/（2个）

| 文件 | 子文件夹 | PDCA 标签 | 引用范围 |
|------|----------|-----------|----------|
| red_flags.md | check/ | C.reflexion | main + code_eng |
| loop_verifier.md | check/ | C.verify | main + loop |

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
> **简称对照**: `main` = 主 agent;`bootstrap` = bootstrap_agent_riji;`skill_mgmt` = skill_mgmt_agent_riji;`spec_design` = spec_design_agent_riji;`code_eng` = code_eng_agent_riji;`doc_proc` = doc_proc_agent_riji;`loop` = loop_agent_riji;`learn_opt` = learn_opt_agent_riji;`sync` = sync_agent_riji;`browser` = browser_agent_riji。
>
> **共读文件高亮**: 标 ⭐ 的文件被 2+ 副 agent 引用,改这些文件时需注意对多 agent 的影响。

### 6.1 按 agent 分组(正向:agent → reference)

| agent | 知识库(reference 数) | 引用的 reference |
|------|----------------------|------------------|
| bootstrap_agent | 10 | plan/bootstrap/{bootstrap, compaction_recovery, multi_project}.md · common/pa/{summary_view, working_memory_rules, trigger_hooks}.md · plan/route/usage_examples.md · plan/design/{project_structure, design_patterns}.md · common/pd/minimal_code_principles.md |
| skill_mgmt_agent | 3 | plan/route/{skill_management, skill_security, agent_find}.md |
| spec_design_agent | 3 | common/pc/{acceptance_criteria, adversarial_review}.md · common/pda/document_specs.md |
| code_eng_agent | 7 | do/code/{code_rules, git_workflow}.md · common/da/git_backup_cleanup.md · common/dc/{debugging, communication_rules}.md · check/red_flags.md · do/danger/security.md |
| doc_proc_agent | 4 | do/code/{office_processing, file_to_markdown}.md · common/pd/excel_analysis.md · common/da/hand-drawn-report.md |
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
| excel_analysis.md | common/pd/ | main + doc_proc |
| document_specs.md | common/pda/ | main + spec_design |
| subagents_rj.md | common/pda/ | main(元数据) |
| communication_rules.md | common/dc/ | main + code_eng |
| debugging.md | common/dc/ | main + code_eng |
| hand-drawn-report.md ⭐ | common/da/ | main + doc_proc + sync |
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
| reference 总数 | 47 |
| 仅 main 读的 reference | 12（subagents_rj.md 元数据 + insert_new_task.md + act_procedure.md + memory_governance.md + writing_style.md + goal_brief.md + article-writing 入口 + 5 子模块） |
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
| v1.2.0 | 2026-08-06 | 融合文章写作模块：41→47、common 16→21、style 1→6（article-writing 入口 + 5 子模块）；2.1 补嵌套例外条款；顺手修 agent 知识库计数漂移（bootstrap 11→10 / spec_design 5→3 / code_eng 8→7 / doc_proc 5→4，以 subagents_rj.md 正向配置为权威源） |

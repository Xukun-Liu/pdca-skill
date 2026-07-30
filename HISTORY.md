---
title: riji-skill 版本历史
version: v1.1.0
last_updated: 2026-07-29
---

# riji-skill 版本历史

> 本文件记录 riji-skill 所有公开发布版本变更。
> 维护规则：每次版本升级在此追加一行，并同步更新 SKILL.md 头部版本号。

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-07-21 | 首个正式公开发布版。核心能力：PDCA 四环协作流程（/plan→/do→/check→/act）、7条铁律（Memory First/HARD-GATE/流程优先/No Placeholders/触发钩子/回溯保障/逐项核对）、多副 agent 架构（主 agent + 9 副 agent + 调度辅助工具，主 agent 守宪法、副 agent 只读调研）、Loop Engineering（L0-L3 四级任务等级+熔断机制）、三层记忆体系（热/温/冷）、docs_rj 8 要素项目骨架（.primary_docs_rj + docs_rj/ + spec_rj/ + task_rj/ + handoff_rj/ + archive_rj/ + memory_rj/ + SUMMARY_RJ.md，启动前置检查硬规则强制阻断）、37 个参考手册按需加载、25 个自动化脚本（文档生成/记忆写入/整理归档/准入审计/运行时熔断/事后审计/副 agent 调度）、技能编排（agent-find 动态搜索）、自进化（Learn Cycle 五阶段 scan/mine/gate/reflect/adopt）、对抗性审查（独立 subagent 6 维度批判性审查）、手绘呈现、技能图谱。纯本地文件，零云依赖，拷贝即用。Apache-2.0 开源许可。 |
| v1.0.0 | 2026-07-25 | references/ 目录结构重构：36 个扁平 .md 文件按 PDCA 四环节 + common 融合区重构为子文件夹结构（common/pa,pc,pd,pda,dc,da + plan/bootstrap,route,design + do/code,danger + check + act/learn）。新增 references/index.md 导航索引。7 个脚本遍历逻辑改 os.walk 递归。全量验证 validate_skill 31/31 pass + pytest 78 passed。 |
| v1.0.0 | 2026-07-28 | archive_rj 归档结构重构（D1 方案）：从扁平归档（{task}_{type}_{ts}_archived.md）改为按任务子文件夹聚合（{task}_{ts}/{type}.md）。任务启动时间戳从原文件名提取（不依赖 mtime，避免 touch/checkout 漂移）。17 文件全改：archive_tidy.py（归档路径改子文件夹）、handoff_tidy.py（INDEX 识别 folder+file 两种形态）、tidy_common.py（reconcile_doc_links 扫子文件夹）、startup_tidy.py（PARA 下沉改子文件夹）、generate_docs.py（L7 硬规则补例外条款）、document_specs.md/project_structure.md/SKILL.md/bootstrap.md/adversarial_review.md（文字同步）、archive_template.md（任务袋 meta 模板）、index_template.md/spec_main_template.md（状态说明同步）。存量扁平文件保留标 legacy，不强制迁移。validate_skill 31/31 pass。 |
| v1.0.0 | 2026-07-28 | spec_main 自动刷新机制实现：tidy_common.py 新增 refresh_spec_main（§1§2§7.2§7.4 自动刷新 + §7.1/§7.3 候选提取）+ _ac_verify.py 17 AC 验收 + 对抗审查 2 轮 APPROVE。Phase 6 Convergence 修复 §7.4 残留脏数据（_refresh_section7_4 限定 frontmatter 匹配 + seen_relations 去重，防 docstring 示例误提取）。handoff_tidy bug 修复：task_name=None 时 .lower() 和 +'_handoff' 崩溃防御（对齐 _run_loop_guard_finalize 保护模式）。SKILL.md §3.5a/3.5b ADR/风险确认子步骤 + Red Flag。validate_skill 31/31 pass。 |
| v1.0.0 | 2026-07-29 | /act 阶段补步骤5「任务收尾 commit」【硬性】：/act 步骤1-4.1 完成后，git status 检测工作区，有改动则 agent 构造 Conventional Commits 消息→commit_lint.py 校验→HARD-GATE 用户确认→git add -u + commit。与铁律6（改前 commit）互补，形成"改前+改后"双重回溯保障。git_workflow.md §6 新增 6.4 场景E（v1.2）。SKILL.md /act 步骤5新增+原步骤5改步骤6。 |
| v1.1.0 | 2026-07-29 | leader 机制融合到 PDCA 流程（REQ-001~053）：SKILL.md /plan 步骤3/4/5/6 增强（三分领导的话/实测命令/假绿灯/富规格/执行型vs探索型/6条自检）；/do 增强（任务0/开工回执/顺手活/连败3次/回滚/止损/防幻觉）；/check 增强（暗卷/反向验证/验收官/贴命令输出）；§0.56 增强（全局上下文）。spec_template.md 12 项增强（目标类型/富规格/基线数字/判卷冻结/双指标/characterization/sha256/素颜/信息密度/文风体验/标题白话/防死法）。task_template.md 13 项增强（改动白名单/反向验证/防作弊/死规矩/依赖排序/防幻觉/进度状态/阻塞项/开工回执/项目纪律/暗卷/贴命令/止损）。新增 references/plan/design/goal_brief.md + references/common/style/writing_style.md。4 轮对抗审查 HIGH 清零。 |

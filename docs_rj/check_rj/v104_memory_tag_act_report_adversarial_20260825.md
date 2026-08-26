# 对抗审查报告：v104_memory_tag_act_report 方案B

> 审查时间：2026-08-25 21:05 | 审查方式：独立 fresh subagent（6 维度批判性审查）
> 审查对象：v1.0.4 升级方案B（三痛点体系化改造）
> 结论：方案方向可行，发现 **4 HIGH / 7 MEDIUM / 4 LOW**；4 HIGH 修复设计已回填 spec（v104_memory_tag_act_report_spec_20260825_2127.md），修复对应关系见文末。
> 终态复验：4 HIGH 已全部修复回填并逐项验证（含 /check Convergence 修补轮），终态 **0 HIGH**（gate2 闸门证据）

## HIGH（必须修复才能进 /do，已全部回填 spec）

- [H1] memory_main.md 索引化会直接打断 distill/learn 闭环（数据链断裂）| 证据：`scripts/memory_distill.py` L36-82/L110-130 完全依赖 memory_main.md 条目格式解析过滤 is_lesson；`learn_tidy.py` L13 harvest 同理 | 后果：distill 永远输出 0 条，/act 步骤 4.1 经验采纳静默死亡 | **修复（已回填 spec §4.4-①② + task T003）**：distill/learn 改 rglob 扫标签文件夹正文文件（正文格式不变，解析逻辑复用）

- [H2] 两层子目录与现有代码扁平假设冲突，至少 4 处失效 | 证据：①act_procedure.md L20-21 单层 Glob；②loop_admission.py L238-252 单层 glob（loop 准入扣分降级）；③handoff_tidy.py L498-505 os.listdir 单层；④archive_tidy.py L84/L308 同 | **修复（已回填 spec §4.4 全表 + task T003）**：7 处适配清单逐项改 rglob，附 grep 全量二次扫描

- [H3] 6 标签与现有双标签字段（tags/experience_tags）关系未定义，"AI 自动选标签"接口空白 | 证据：memory_shadow_write.py L287-291 已有 tags+experience_tags 双参数；act_procedure.md L99 distill 采纳写死 experience_tags 含 adopted_lesson | **修复（已回填 spec §2/§4.1/§4.2 + task T001/T002）**：memory_class 作为第三参数（归档分类，决定文件夹），与 tags/experience_tags 并存分工；非法值兜底 workflow+warning；存量自由标签映射表（sandbox_workaround→pitfall 等 7 条）写入迁移脚本

- [H4] "汇报"一词三重命中（leader_report/hand-drawn-report/html_ppt_creation），仲裁规则零覆盖 | 证据：trigger_hooks.md L49 与 L70 均含"汇报"；SKILL.md 仲裁规则 7 条不含汇报 | **修复（已回填 spec §4.6 + task T006）**：精确关键词集（给领导汇报/向上汇报/出汇报文档/给老板汇报，禁裸"汇报"）+ 仲裁规则一行 + 三表同步（trigger_hooks/SKILL.md/index.md）

## MEDIUM（应修复，已列入 task）

- [M1] 存量迁移 3 种异构格式解析规则未定义 → 已回填 spec §4.3 五步 + 对账校验（task T004）
- [M2] /act 步骤 1.5 与 /loop auto 无人值守冲突 + 双写风险 → 已回填 spec §4.5（SKIPPED 语义+同次 write_project，task T005）
- [M3] 旧版 skill 与新结构混写风险 → 已回填 .schema_version 检测（spec §4.2⑥，task T002）
- [M4] 治理工具族（容量统计/_find_entry/_FLAG_STATUS_RE）基于旧格式 → 已回填 spec §4.4⑦（task T003）
- [M5] 文档联动清单不完整（漏 working_memory_rules/memory_governance/index） → 已回填 spec §3 包含项 + task T007
- [M6] 全局侧条目项目归属 + 跨月散落 → 设计决策：全局侧不建文件夹（索引化即全局方案），正文 source of truth 在项目侧；跨月各落当月（沿用现有跨午夜语义）
- [M7] 工作量无估计 → 已回填 spec §0.1 缺点列 + 方案对比

## LOW（可选，部分采纳）

- [L1] Tulving 三分类映射牵强 → 采纳：spec 定稿删学术映射表述，改为"功能分类"
- [L2] 记忆类型与经验领域两正交维度压一个字段 → 采纳：TAG_PRIORITY 优先级规则（spec §2）
- [L3] 未来加标签无集中机制 → 采纳：memory_tags.py 单点常量（spec §4.1，用户明确"后续会增加"）
- [L4] 未覆盖类型无兜底 → 采纳：统一落 workflow 兜底规则（spec §2）

## 总体结论

方案B 方向可行（三痛点诊断准确、痛点2/3 改造成本低风险小），痛点1 的"索引化+标签文件夹"存在 4 个 HIGH，修复设计已全部回填 spec v1.0 后再走 HARD-GATE。审查通过（条件：按回填后的 B' 执行）。

## 审查过程记录

- 读完 6 个背景文件：SKILL.md（Memory First/记忆双写/§6 /act/references 索引）、memory_shadow_write.py、act_procedure.md、memory_main.md（前150行）、working_memory_rules.md、trigger_hooks.md
- 加读 3 个下游脚本验证：memory_distill.py / loop_admission.py / handoff_tidy.py（发现问题 H1/H2）
- grep 实测：16 个脚本引用 memory_main；至少 4 处代码假设 memory_rj 扁平结构

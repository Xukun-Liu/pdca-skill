<!-- PDCA标签：C.verify C.adversarial C.reflexion -->
<!-- 子标签场景：/check 验证细则（解释三步/Reflexion三问/spec逐项核对/跨产物analyze/Gate Evidence/Convergence/验收机制/loop三态） -->
<!-- 关键词清单：/check/Reflexion/3-Strike/逐项核对/跨产物一致性/Coverage Gaps/Convergence/Gate Evidence/暗卷抽查/反向验证/验收官降级/loop_verifier/APPROVE/REJECT/ESCALATE -->
<!-- 引用范围：main -->

# /check 步骤细则（自 SKILL.md §6 下沉，唯一维护源）

> 版本：v1.1.0 | 创建：2026-10-28
> 阶段标签：C.verify C.adversarial C.reflexion

> 什么时候读：进入 /check 后按需查阅（步骤5 核对前读本页；步骤6/7 读 adversarial_review.md；/loop 模式读第 9 条）。

## /check（验结果）

1. 解释三步：大图上下文→类比解释→逐块讲解（一次≤15行）
2. 问题处理三步：承认没成功→报错翻译成大白话→修好说清哪出问题
3. 3次尝试失败→升级你（3-Strike 协议，不允许第4次瞎试）
4. 修复/完成后→**Reflexion 结构化反思三问**【硬性】：
   - 我预期会怎样？实际发生了什么？
   - 为什么有差距？没遵守规则？还是规则有缺口？
   - 如果是规则缺口，具体场景是什么？（记录到 memory 时一并说明）
5. **对照 spec 逐项核对**【硬性】：按 spec.md 验收标准逐条核对，不遗漏任何一项
6. **跨产物一致性 analyze**【复杂任务必做】：在铁律7逐项核对**之后**执行（先做铁律7不可替代，再做跨产物 analyze 补充）。6 维度检测（Coverage Gaps/Duplication/Ambiguity/Constitution Alignment/Inconsistency/Underspecification）+ 4 级严重度（CRITICAL/HIGH/MEDIUM/LOW）。详见 [adversarial_review.md](../common/pc/adversarial_review.md) 第六章。
6.5. **Gate Evidence 落盘【硬性·handoff_gate_fix】**：跨产物 analyze（步骤 6）完成后、Convergence（步骤 7）之前，当场把 4 闸门证据写入 `docs_rj/memory_rj/TASK_STATE_{task_id}.md` 的 `## Gate Evidence` 段，并将审查报告落盘 `docs_rj/check_rj/{task}_adversarial_{时间戳}.md` / `{task}_consistency_{时间戳}.md`（报告结论必须含 `0 HIGH`，否则闸门 2/3 判缺证据）。段格式：
   - `- gate1_spec_verification: pass (N/N)`（N=spec AC 总数，来自步骤 5）
   - `- gate2_adversarial: pass (0 HIGH) | 证据: {相对 docs_rj 的路径}#L行号`
   - `- gate3_consistency: pass (0 HIGH) | 证据: {路径}#L行号`
   - `- gate4_user_confirm: confirm | 时间戳: {时间} | 用户原话: "{原话}"`；/loop 无人值守时写 `loop_auto | 说明: /loop 无人值守，待用户确认`
   - **原理**：证据产生时落盘、验证时只读不写——handoff_tidy 的 4 闸门判定只读校验上述段与报告文件，不靠 agent 自觉声明
7. **append-only Convergence**：若跨产物 analyze 发现 gap，**追加**到 task.md 末尾 `## Phase N: Convergence` 段（不删现有 task，不改 spec.md）。**Convergence 是修补记录+追加，不替代修补**——回 /do 修补（修改 task.md 子项打勾）同时追加 Convergence 记录修补内容。CRITICAL/HIGH 优先，constitution 违反最先。累积超过 5 个 Phase 时归档到 `archive_rj/`。详见 [adversarial_review.md](../common/pc/adversarial_review.md) §6.3。
   - **修补后独立 fresh agent 重验**【硬性·复杂任务】：Convergence 修补完成后，**必须由独立 fresh subagent 重新验证**（不让原 fixer 自证，反 sunk-cost bias）。重验 subagent 重新 dispatch，按 6 维度审查修补后的 spec/task，确认原 gap 已修复且未引入新问题。重验不通过→继续修补+再重验（max 3 cycles），达 3 cycles 仍不通过→升级用户决策。简单任务可由主 agent 自验，复杂任务必须独立 fresh subagent。
8. **/check 完成**：通过则问"进入 /act 吗？"；不通过则问"回 /do 修补还是回 /plan 重设计？"——回 /do 修补完成后，重新进入 /check 验证修补结果

**验收机制**（融合）【硬性·复杂任务】：
- **暗卷抽查**：2-3 条 spec 里没写的抽查项，管理者自留，验收时复跑（明卷=spec 公开验收命令已有；暗卷=额外抽查防偷工）
- **反向验证**：凡是"坏了没人会知道"的检查都要——故意制造一次失败证明会响，贴红→还原贴绿
- **验收官降级**：摸不到执行环境时退化为"用户亲验清单"（协作场景无外部 agent 可转贴，让用户按清单亲验）
- **贴实际命令输出**：验收时每条都要在对话里贴实际命令输出（含反向验证的红→绿证据），只说做完了不算
- **报告格式**：结构化报告（过没过/干成了什么/遗留问题/下一步），不限于5行
- 详见 [goal_brief.md](../plan/design/goal_brief.md) "验收机制"节

9. **/loop 模式下的 /check 三态输出**（仅 /loop 启动后生效）：
   - **前置**：加载 [loop_verifier.md](loop_verifier.md)（默认 REJECT 立场），按其 7 项检查清单原文执行（不改写，清单唯一维护源在该文件）
   - **输出三态之一**：**APPROVE**（7 项全过 → 回写 ledger success → 继续下个 task）；**REJECT**（有项未过 → 回写 failure + error_signature → 回 /do 修补）；**ESCALATE**（连续 REJECT ≥3 次 → 停下问用户）
   - **回写 ledger**：`python scripts/loop_guard.py check --task-id {task_id} --status {success|failure} --error {error_sig}`
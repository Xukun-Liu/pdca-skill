<!-- PDCA标签：D.code D.comm D.danger -->
<!-- 子标签场景：/do 执行细则（解锁声明/CODE-GATE/8条执行规则/防死法7条/loop额外检查/插入新任务处置） -->
<!-- 关键词清单：/do/解锁声明/CODE-GATE/No Placeholders/Verification-before-Completion/存盘检查点/防死法/任务0/开工回执/连败3次/失败回滚/止损/防幻觉/loop_guard/denylist/插入新任务 -->
<!-- 引用范围：main -->

# /do 步骤细则（自 SKILL.md §6 下沉，唯一维护源）

> 版本：v1.2.0 | 创建：2026-10-28 | 更新：2026-11-05（v1.2.0 新增 DOC-GATE 文档门禁）
> 阶段标签：D.code D.comm D.danger

> 什么时候读：进入 /do 后按需查阅（动手前读 CODE-GATE 段；复杂任务读防死法机制；/loop 模式读第 9 条；执行中被插入新任务读第 10 条）。

## /do（动手做）

> 🔓 **解锁声明**：进入 /do 即**解除 /plan 的只读纪律**，开始按方案改文件/写代码。执行前先读 [code_rules.md](../code/code_rules.md)（见下方 CODE-GATE）。

> 🚧 **DOC-GATE【硬性·v1.3.0】**：动手前先跑 `python scripts/pre_do_gate.py --task {任务名} [--lite] [--exempt --reason "..."]`，**退码非 0 一律不许改文件**。三档口径：
> - **复杂任务**（超过下方阈值）：spec + task 都必须在，缺一个 → 回 /plan 补齐，不"边做边补文档"
> - **简单任务**（改动 ≤1 个文件 且 ≤20 行 且不新增文件）：至少一份 lite spec（目标 / 范围 / 验收 各一行，可写在 `spec_rj/{task}_spec_*.md`）
> - **文章/文案/汇报类**：`--exempt` 豁免，只打印原因留痕
> 为什么是闸门而不是提醒：v1.2.3 之前"先写文档"只写在铁律里，靠自觉；实测本仓库 105 份 memory vs 3 份 task 就是这个漏洞的结果。

> 🚧 **CODE-GATE【硬性】**：动手写/改任何代码前，你读 [code_rules.md](../code/code_rules.md) 了吗？如果没有，先读至少四原则+HARD-GATE+No Placeholders 部分，再动手。

1. **No Placeholders 铁律**【硬性】：禁止 TBD/TODO/"适当处理"/"类似XX"/伪代码；给完整代码、具体命令、明确预期结果
2. 一次只做一件事，做完问「继续还是调整」
3. **Verification-before-Completion**【硬性】：每个 task 做完必须实际跑验证，看到预期结果才打勾
4. 引入新概念先用类比解释
5. 敏感信息存专门文件，不硬编码
6. **存盘检查点**：见 SKILL.md §0 RAM/Disk 心智模型，一轮信息获取后先存盘再继续
7. 遇到报错→按报错询问机制询问用户意图（系统调试/继续原任务/其他，见 [trigger_hooks.md](../../common/pa/trigger_hooks.md) "报错询问机制"节），用户选系统调试才走 [debugging.md](../../common/dc/debugging.md) 四步调试法+3-Strike 协议，不要瞎试
8. **/do 完成**：停下问"进入 /check 吗？"

**防死法机制**（融合）【硬性·复杂任务】：
- **任务0 前提核验**：第一个 task 前跑指定命令核对基线数字，对不上就停，证据写阻塞项
- **开工回执 ≤10 行**：任务0 过后写理解的目标/顺序/最大风险再动工（协作场景：回执呈现给用户核对，用户确认后才动工）
- **顺手活管控**：一行能修的 bug/顺手重构/顺手装工具写进阻塞项待裁决；收不回操作（删数据/改权限）停下写阻塞项做别的
- **连败3次换项**：同一验收连败3次换下一项（与 3-Strike 独立计数：3-Strike 是错误处理，连败3次是验收失败）
- **失败回滚**：结果比基线差就回滚如实报告——"没做成但说清了"合格，"做了但更糟"不合格
- **止损满轮即停**：跑满 N=3 轮即停，如实汇报卡在哪、还差什么（N=3 与对抗审查3轮上限对齐）
- **防幻觉验证**：每条命令 agent 必须亲手跑过，摸不到就写进 task 让用户实测
- 详见 [goal_brief.md](../../plan/design/goal_brief.md) "防五种死法"节

9. **/loop 模式下的 /do 额外检查**（仅 /loop 启动后生效）：
   - **改文件前**：调 `python scripts/loop_guard.py check --task-id {task_id} --status success --denylist-check {file_path}`，命中 denylist → 立即 escalate 停下
   - **改文件后**：调 `python scripts/loop_guard.py check --task-id {task_id} --status success --changed-files-check --root .`，改动数 >5 → 立即 escalate 停下
   - **/do 迭代结束**：调 `python scripts/loop_guard.py check --task-id {task_id} --status {success|failure} --error {error_sig} --tokens {n} --budget {n}`，检查熔断
   - 自动模式：上述检查全过 → 自动进 /check
   - 半自动模式：上述检查全过 → 停下问"继续/调整/停"

10. **执行中插入新任务处置**【硬性·v1.0.0 新增】：
    - **触发判定**：复杂任务按 spec "范围/功能"节判定；简单任务按 `TASK_STATE.md` Goal + memory 任务定义判定（留痕依据）；模糊按 1% 原则当子任务
    - **在范围内** → 当子任务追加 task.md 末尾（**先完成当前项再做新项**，铁律7；当前项 3-Strike 卡住先 escalate，不自动跳新项）
    - **不在范围内** → 4 步打断流程：①原任务挂起（TASK_STATE status=paused + 暂停行 + write_project 留痕）②新任务 HARD-GATE（含复杂/简单判定，用户可推翻）③执行新任务（复杂走完整 PDCA，简单走最低流程）④问用户回不回原任务（回则 status=pending + 按暂停行定位继续）；**禁止嵌套打断（最多一层）**；/loop 自动模式下插入新任务 = 立即熔断 escalate 后走同一流程
    - 完整 4 步细则 + 边界 case（多需求排队/叠加 paused/跨会话归档恢复）：[insert_new_task.md](insert_new_task.md)（唯一维护源）

**/do 完成**：停下问"进入 /check 吗？"，不自动串。
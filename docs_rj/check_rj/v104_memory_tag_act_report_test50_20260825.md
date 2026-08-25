# v1.0.4 50 轮全流程测试报告（T008 / AC-014）

> 测试时间：2026-08-25 22:30-22:50（首轮）+ 23:20-23:40（/check 修补轮）| 测试人：主 agent + fresh subagent（对话层）
> 对应 spec：v104_memory_tag_act_report_spec_20260825_2127.md §5 AC-014
> 结论：**50/50 通过 + 对话层 3/3 PASS，全量回归 279 passed / 1 skipped（含 BUG-B 回归测试），validate 32/32，真实数据零污染**

## 〇、/check 修补轮记录（Convergence Phase 1）

/check 复验 AC-004 时抓到 CRITICAL：迁移后索引被吃 44 行（82≠126）。根因两个 BUG，全修复：

| BUG | 位置 | 修复 | 验证 |
|-----|------|------|------|
| **BUG-B**：旧通道 upsert_global_memory 块替换边界不含索引行 → 替换时整片吃掉后随索引 | memory_shadow_write.py L354（check-fix） | 块边界加 `_is_entry_line()` 终止 | 新增回归测试 test_upsert_global_memory_does_not_eat_index_lines PASS |
| **BUG-A**：governance 测试组合运行时穿透写真实 memory_main（v1.0.3 遗留，索引化后危害放大） | tests/ 部分 fixture 隔离缺口 | conftest.py autouse fixture `_isolate_global_memory` 兜底隔离（只 patch 路径不建目录，防 mkdir 冲突） | 全量 pytest 前后真实文件 md5 一致（True）；fixes+phase1+2+3 组合复验 same=True |
| 数据重建 | memory_main.md | 删 25 个污染块 + 从 legacy_body 重建 45 行缺失索引 | 对账 legacy=126 ≤ index=127、污染块=0；正文零丢失（126 文件完好） |
| **修补3**（复验新发现）：45 行历史脏 ts 索引行（时间戳小时十位丢失，如 `22:14`→`_2:14`，不匹配 expand 正则致 distill=0） | memory_main.md 索引行 | 36 行按 URL 文件名反推规范 ts 重写 + 9 行无法反推者删后从 legacy_body 补回（9 行） | distill 恢复提取 10 条经验、learn count=115、终态对账 126≤127 PASS、0 不匹配行 |

修补后全量：279 passed（+1 BUG-B 回归）、validate 32/32、loop 100/100、真实文件零污染（pytest 前后 md5 一致）。

## 一、测试构成（机械层 + 对话层双层设计）

| 层 | 轮数/用例 | 验证内容 | 载体 |
|----|-----------|---------|------|
| 机械层 | 50 轮（parametrize） | 每轮全链路：write_project → 标签文件夹落点 → 索引行元数据 → expand_index_lines 展开 → distill 可解析 | tests/test_v104_50rounds.py（可回归） |
| 机械层附加 | 2 用例 | 误判率统计 + leader_report 六段结构断言 | 同上 |
| 对话层 | 3 项抽样（fresh subagent） | 新对话读新结构记忆（索引→正文）/ /act 互动问题生成质量 / 汇报路由 | 本报告 §三 |
| 行为层 | 1 轮真实 | 本任务会话本身（/plan→/do→/check→/act 完整走 v1.0.4 新流程） | 全程实录 |

## 二、机械层 50 轮明细

任务类型分布：技术修复 15 / 写作 10 / 发布 10 / 巡检 10 / 汇报 5（对齐 task T008 矩阵）。

每轮检查点（全过）：
- a) 正文落 `{推断主分类}/{YYYYMM}/` 深层文件夹（50/50）
- b) memory_main.md 索引行含 task/主分类/is_lesson/正文链接（50/50）
- c) 索引行展开后 parse_memory_entries 解析到该条目（50/50，H1 数据链闭环）

**推断误判率：20%（10/50）< 30% 阈值**（spec 未验证假设①成立）。误判明细（全部为跨类模糊内容，无严重错位，且误判不丢数据仅影响文件夹位置）：

| 轮次 | 类型 | 预期 | 实际 | 分析 |
|------|------|------|------|------|
| r24 | 写作 | workflow | pitfall | 内容含"踩坑经历做开场白"（词命中，边界合理） |
| r34 | 发布 | workflow | pitfall | "版本号回退事故复盘"含回退词（合理） |
| r38/r42 | 巡检 | status | tech_solution | "已补录/依赖检查"内容词弱 |
| r39/r45 | 巡检 | status | workflow | 巡检内容无特异词，兜底 |
| r43 | 巡检 | status | pitfall | "异常"命中 |
| r46-r50 | 汇报 | 互串 | - | 汇报内容 workflow/status 语义重叠 |

**全量回归**：278 passed / 1 skipped（226 既有 + 52 新增），37.3 秒。
**validate_skill**：32/32 PASS，MUST FIX=0。

## 三、对话层抽样（fresh subagent 报告全文结论）

| 验证项 | 结果 | 关键证据 |
|--------|------|---------|
| 1. 新对话 /plan 读记忆 | PASS | 索引行七段管道格式可解析；按"pitfall + is_lesson=true"过滤 30 秒定位最近踩坑（2026-08-20 沙箱拦截条目），file:/// 链接点开正文完整（33 行含 frontmatter 六段） |
| 2. /act 互动问题生成 | PASS | 针对"126 条迁移对账零差异"任务生成 3 问全部绑定任务特有要素（哪个环节最易丢条目/为什么选标签文件夹不选单文件/对账方法可复用什么），非泛泛三问 |
| 3. 汇报路由 | PASS | "给领导汇报 v1.0.4"命中 SKILL.md L359 仲裁行 → leader_report.md；六段数据源映射表可直接执行（TASK_STATE/spec AC/task 阻塞项/互动复盘段） |

subagent 补充观察（legacy_body 与 memory_rj 双目录）处置说明：检索链路走索引行链接直达正文（不依赖目录枚举），写入链路 50 轮机械测试已验证新条目落 memory_rj 深层并回写索引——**无覆盖缺口**。

## 四、AC 达成汇总（AC-013/014）

| AC | 标准 | 实测 | 结果 |
|----|------|------|------|
| AC-014 | 50/50 轮通过 | 机械层 50/50 + 对话层 3/3 + 行为层 1 轮真实 | ✅ |
| AC-013 | validate 32/32 | 32/32 PASS / MUST FIX=0 | ✅ |
| 假设① | 误判率 <30% | 20% | ✅ |

## 五、遗留与建议

1. 巡检/汇报类内容词义重叠的误判（7/10 条），可在后续版本（v1.0.5）给 status/decision 加"任务名前缀加权"（如 ops_/report_ 前缀直接路由）——本次不改（误判无害+阈值内）
2. 50 轮测试已固化为 pytest 可回归资产（tests/test_v104_50rounds.py），后续任何记忆系统改动跑一次即验证

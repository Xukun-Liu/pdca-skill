---
title: v104_memory_tag_act_report - 任务清单
version: v1.0.0
skill_version: v1.0.4
date_created: 2026-08-25 21:27
last_updated: 2026-08-25 21:27
spec_ref: spec_rj/v104_memory_tag_act_report_spec_20260825_2127.md
---

# task：v104_memory_tag_act_report

> 版本：v1.0.0 | 更新：2026-08-25 21:27
> 每个task含：做什么/怎么做/怎么验证/边界/GWT/不通过处理/白名单/反向验证/防作弊/死规矩/依赖排序/防幻觉

---

## 总览

- **对应 spec**：`docs_rj/spec_rj/v104_memory_tag_act_report_spec_20260825_2127.md`
- **最终目标**：pdca-skill v1.0.4——记忆按 6 主分类文件夹+月份落盘（找得到）、/act 互动复盘沉淀用户判断（有互动）、leader_report 汇报 reference（有模板），50 轮全流程测试通过
- **当前阶段**：阶段1（需求对齐完成，待进阶段2）
- **HARD-GATE状态**：是（方案 B' 经用户多轮确认 + 对抗审查 4 HIGH 修复回填后用户拍板）
- **进度状态**：未开始
- **阻塞项**：无
- **开工回执**：理解的目标=三痛点治本（记忆文件夹制/act互动/汇报reference）+50轮测试；顺序=T000→T001→…→T009（Git→标签常量→write_project改造→下游适配→迁移→act规则→汇报reference→文档同步→测试→收尾）；最大风险=迁移数据丢失（双备份+对账兜底）与下游适配遗漏（grep全量扫描兜底）
- **项目纪律**：feature 分支 `feature/v1.0.4-memory-tag-act-report`；每个 task 完成即 WIP commit；改动白名单外文件需先向用户说明；版本号 T007 统一升级；连败 3 次换项并上报（REQ-032 防死法4）
- **AC 映射总表**：AC-001~003→T001/T002；AC-004~006/015→T004；AC-007~009/012→T003；AC-010→T005；AC-011→T006；AC-013~014→T008

---

## Phase 1: 需求对齐

- [x] T000-P 文档骨架生成（generate_docs.py 已实测成功，2026-08-25 21:27 创建 spec/task/handoff/archive 四件）
  - 验证：ls docs_rj/{spec,task,handoff,archive}_rj/v104_memory_tag_act_report_* → 4 文件存在（已实测 ✓）
  - 防作弊点名禁止/防幻觉验证：命令已亲手跑过 ✓
  - 依赖排序说明：一切任务的前置（文档落点）

---

## Phase 2: 执行

- [ ] T000 Git 准备：commit 遗留 + 建 feature 分支 + start tag
  - 怎么做：①`git add docs_rj/SUMMARY_RJ.md docs_rj/spec_rj/spec_main_rj.md` + `git commit -m "docs(v103_sync): 收尾文档更新"`；②`git checkout -b feature/v1.0.4-memory-tag-act-report`；③`git tag task/v104_memory_tag_act_report/start`
  - 验证：`git branch --show-current` → feature/v1.0.4-memory-tag-act-report；`git status` → 工作区干净
  - 边界条件：正常=2 文件提交成功；异常=commit 冲突 → 查 git log 定位后重试 1 次，仍败则上报用户
  - 验收标准（GWT）：Given master 有 2 个未提交文档改动 When 执行三步 Then 新分支存在且工作区干净
  - 不通过处理：分支创建失败 → 回 master 排查后重来；tag 冲突 → 检查同名 tag 是否残留
  - 改动白名单路径：无文件改动（纯 git 操作）
  - 反向验证：否
  - 防作弊点名禁止：N/A（git 操作类）
  - 死规矩带后果：先 commit 再建分支，否则遗留改动会污染 feature 分支首个 commit
  - 依赖排序说明：铁律6 回溯保障前置——后续所有改动的回滚点
  - 防幻觉验证：git 命令在 /do 实测

- [ ] T001 新建 scripts/memory_tags.py 单点常量 + tests/test_memory_tags.py
  - 怎么做：创建 `scripts/memory_tags.py`，内容：`MEMORY_TAGS = ["tech_solution","pitfall","workflow","tool_usage","decision","status"]`、`TAG_PRIORITY = ["status","decision","pitfall","tech_solution","tool_usage","workflow"]`（列表序=优先级序）、`FALLBACK_TAG = "workflow"`、`validate_memory_class(v)`（None/空串→FALLBACK+warning；大小写归一 `v.strip().lower()`；命中 MEMORY_TAGS 返回原值；否则 FALLBACK+warning）、`infer_memory_class(content)`（关键词启发式：踩坑/报错/失败/异常/rollback→pitfall；方案/架构/实现/部署→tech_solution；完成/进度/状态/交接→status；决策/拍板/选择/取舍→decision；工具/命令/脚本/用法→tool_usage；默认 workflow；多命中按 TAG_PRIORITY 取最高）；创建 `tests/test_memory_tags.py`（≥8 个用例：6 合法值各 1 + 非法值/None/中文/大小写归一/多命中优先级）
  - 验证：`python -m pytest tests/test_memory_tags.py -q` → 全 PASS
  - 边界条件：正常=6 合法值原样返回；异常=None/""/"发布"/"Tech_Solution"→归一或兜底 workflow + stderr warning
  - 验收标准（GWT）：Given memory_tags.py 存在 When pytest 跑 8 用例 Then 全 PASS 且非法值全落 workflow
  - 不通过处理：单测失败 → 修函数本体（不改测试迁就实现）；修 3 次仍败 → 上报
  - 改动白名单路径：`scripts/memory_tags.py`（新增）、`tests/test_memory_tags.py`（新增）
  - 反向验证：是——非法值不落兜底会静默建错文件夹，测试含 4 个非法值用例证明会 warning
  - 防作弊点名禁止：禁 skip/todo/mock；测试必须真跑
  - 死规矩带后果：标签字符串只许在 memory_tags.py 定义，否则 AC-003 单点性破坏、未来加标签要改多处
  - 依赖排序说明：T002 write_project 和 T004 迁移脚本都 import 此模块，必须最先建
  - 防幻觉验证：pytest 在 /do 实测

- [ ] T002 write_project 改造：memory_class 参数 + 路径路由 + 索引行 + schema_version 检测
  - 怎么做：修改 `scripts/memory_shadow_write.py`：①函数签名加 `memory_class=None`，CLI 加 `--memory-class` 参数；②import memory_tags（validate_memory_class/infer_memory_class），缺省时 infer 并 print 推断结果；③正文路径 `{memory_rj}/{tag}/{YYYYMM}/`（YYYYMM 从当前时间戳取），文件夹 mkdir(parents=True, exist_ok=True)；④全局 upsert 改为索引行：`- {YYYY-MM-DD HH:MM} | {tag} | 重要性{level} | is_lesson={bool} | {摘要≤40字} | [正文]({相对路径})`（同 task 最新条目替换旧索引行，语义对齐现有"每 task 保最新"）；⑤写文件全部 open(path,'w',encoding='utf-8') 直写（禁 mkstemp，C5 约束）；⑥启动时读 `~/.pdca-skill/data/.schema_version`，缺失或 structure!=tag_folder_monthly → stderr 告警"数据结构版本不匹配，请先跑 migrate_memory_v104.py"（告警不阻断，降级写 memory_rj 根目录）
  - 验证：①`python scripts/memory_shadow_write.py --task v104_test --memory-class pitfall --content "测试：踩坑记录"`（CLI 实际参数以脚本 argparse 为准）→ `memory_rj/pitfall/202608/` 出现正文文件 + memory_main.md 出现索引行；②传 `--memory-class xyz` → 文件落 workflow + warning；③AC-001/002 命令逐条跑
  - 边界条件：正常=合法 tag 落对应文件夹；异常=非法 tag 兜底、文件夹创建失败降级根目录、锁竞争按现有 msvcrt 锁机制等待
  - 验收标准（GWT）：Given 改造完成 When 分别传合法/非法 memory_class Then pitfall 文件夹 1 文件+索引行 / workflow 文件夹 1 文件+warning
  - 不通过处理：路由错 → 检查 tag 变量传递链；索引行格式错 → 对照 spec §4.2 格式模板修
  - 改动白名单路径：`scripts/memory_shadow_write.py`（修改）
  - 反向验证：是——AC-002 非法值用例
  - 防作弊点名禁止：禁 mock 掉路径路由逻辑；必须真写文件真检查
  - 死规矩带后果：索引行必须含元数据（tag/is_lesson），否则 H1 数据链修复白做（distill 靠元数据过滤）
  - 依赖排序说明：依赖 T001 的 memory_tags 模块；先于 T003（下游适配要跑它验证）/T004（迁移后新写入走新通道）
  - 防幻觉验证：CLI 命令 /do 实测（含中文 content 验证 UTF-8）

- [ ] T003 下游 7 处适配 + pytest 回归
  - 怎么做：按 spec §4.4 适配清单逐项改：①memory_distill.py 解析入口改 `Path(memory_dir).rglob('**/*_memory_*.md')` 扫正文（### 记忆条目 解析逻辑复用）；②learn_tidy.py harvest 同改 rglob；③loop_admission.py L238-252 glob→rglob；④handoff_tidy.py L498-505 os.listdir→Path.rglob('*_memory_*.md')；⑤archive_tidy.py L84/L308 同改；⑥act_procedure.md L20-21 Glob 模式加 `**`；⑦memory_shadow_write.py 治理族（容量统计改数标签文件夹文件数 rglob；_find_entry 定位改正文文件内；_FLAG_STATUS_RE 输入源改正文）。改完跑 `grep -rn "memory_main" scripts/` 全量二次扫描，逐文件核对无"解析 memory_main 正文"残留（索引读写除外）
  - 验证：①`python -m pytest tests/ -q` → 全 PASS（AC-012）；②`python scripts/memory_distill.py distill --project PDCA-skill-public v1.0.3开发环境 --output-dir docs_rj/learn_rj` → ≥1 条经验（AC-007）；③`python scripts/learn_tidy.py count --threshold 20` → total_entries>0（AC-008）；④loop_admission 记忆检测项不扣分（AC-009）
  - 边界条件：正常=深层文件全被扫到；异常=空文件夹 rglob 返回空不报错
  - 验收标准（GWT）：Given T002 完成且 memory_rj 有深层文件 When 跑 4 条验证命令 Then pytest 全绿 + distill ≥1 + count>0 + 准入不扣分
  - 不通过处理：某脚本扫不到深层文件 → 打印 rglob 结果调试路径模式；解析失败 → 对照正文格式核对正则
  - 改动白名单路径：`scripts/memory_distill.py`、`scripts/learn_tidy.py`、`scripts/loop_admission.py`、`scripts/handoff_tidy.py`、`scripts/archive_tidy.py`、`references/act/persist/act_procedure.md`、`scripts/memory_shadow_write.py`（治理族部分）
  - 反向验证：否（回归测试兜底）
  - 防作弊点名禁止：禁改测试阈值/删测试用例迁就实现
  - 死规矩带后果：7 处必须全改，漏 1 处对应功能静默失效（H1/H2 的教训）
  - 依赖排序说明：依赖 T002（新结构文件产生后适配才有验证对象）；先于 T004（迁移后下游必须立刻可用）
  - 防幻觉验证：4 条验证命令 /do 实测

- [ ] T004 迁移脚本 + 实跑迁移 + 对账 + 反向验证
  - 怎么做：①新建 `scripts/migrate_memory_v104.py`（按 spec §4.3 五步：双备份→解析 3 异构格式→归类映射（含存量标签映射表+脏数据段归并）→对账校验→写 schema_version；open() 直写+UTF-8；幂等：.schema_version 存在且 structure 相同则跳过已迁条目）；②新建 `tests/test_migrate_memory_v104.py`（用临时目录造 3 种格式样例：完整式/一行摘要式/同 task 多条目 + 脏数据段样例，跑迁移函数断言对账相等+文件夹结构+幂等重跑）；③**实跑真数据**：`python scripts/migrate_memory_v104.py`（对 118 条真迁移）→ 输出 JSON total=118；④反向验证：复制备份到临时目录，删 1 条正文后重跑 → exit 2 + 差异明细（AC-015）
  - 验证：①单测全 PASS；②实跑 JSON `"total": 118` 且对账 `equal: true`（AC-004）；③`ls ~/.pdca-skill/data/memory/memory_main.md.bak_v103 ~/.pdca-skill/data/docs_rj/memory_rj_backup_v103` → 2 备份在（AC-005）；④`cat ~/.pdca-skill/data/.schema_version` → v1.0.4 标记（AC-006）；⑤反向验证 exit 2
  - 边界条件：正常=118=118；异常=对账不等 exit 2 停+打印差异；重跑幂等不重复迁移
  - 验收标准（GWT）：Given 真数据 118 条 When 实跑迁移 Then 对账相等+双备份+schema_version 全部就位；Given 测试副本删 1 条 When 重跑 Then exit 2 检出差异
  - 不通过处理：对账不等 → 看 JSON 差异明细定位格式解析 bug，修复后重跑（幂等保证不重复）；误判率高（>30%）→ 上报用户决策是否人工归类
  - 改动白名单路径：`scripts/migrate_memory_v104.py`（新增）、`tests/test_migrate_memory_v104.py`（新增）；实跑产生的外置数据目录变更（备份/新结构/schema_version）
  - 反向验证：是——AC-015（故意制造差异证明对账会响）
  - 防作弊点名禁止：禁跳过对账/禁用 ||true 掩盖 exit 2/禁 mock 真数据
  - 死规矩带后果：实跑前必须先确认双备份存在，否则用户 118 条记忆无回滚点（C4 约束）
  - 依赖排序说明：依赖 T002/T003（迁移后新写入+下游读取都已就绪）；真数据实跑是用户数据操作，跑前 HARD-GATE 再确认一次
  - 防幻觉验证：全部命令 /do 实测
  - ⚠️ **实跑前 HARD-GATE**：真数据迁移属不可逆操作（虽有备份），执行前向用户确认"备份就绪，开始迁移？"

- [ ] T005 act 互动复盘规则落盘（SKILL.md + act_procedure.md）
  - 怎么做：①SKILL.md §6 /act 节步骤 1 前插入步骤 1.5（内容按 spec §4.5：动态 2-3 问生成规则/并入同次 write_project/SKIPPED 语义//loop auto 自动跳过留痕/ADD 硬上限 3 问）；②act_procedure.md 加"步骤 1.5：互动复盘"细则节（含问题生成示例 3 组：技术任务/写作任务/发布任务各一组 Q 样例）；③SKILL.md 三层记忆体系表与 Memory First 节补"两层标签"一句
  - 验证：`grep -n "互动复盘" SKILL.md references/act/persist/act_procedure.md` → 2 文件命中（AC-010）；grep 确认 SKIPPED 语义与 /loop auto 留痕规则均在
  - 边界条件：正常=规则完整；异常=无（纯文档）
  - 验收标准（GWT）：Given 两文件更新 When grep 互动复盘 Then 2 文件命中且含动态生成规则+SKIPPED+loop_auto 三要素
  - 不通过处理：要素缺 → 对照 spec §4.5 逐条补
  - 改动白名单路径：`SKILL.md`、`references/act/persist/act_procedure.md`
  - 反向验证：否（T008 50 轮测试覆盖）
  - 防作弊点名禁止：N/A（文档类）
  - 死规矩带后果：1.5 必须插在步骤 1 写盘前，否则双写两个记忆文件（M2 修复失效）
  - 依赖排序说明：纯文档可与 T004 并行，但排在 T004 后（先保数据后改流程）
  - 防幻觉验证：N/A（文档类，grep 验证）

- [ ] T006 leader_report.md + 三表联动
  - 怎么做：①新建 `references/common/da/leader_report.md`（PDCA 标签头 `A.handoff`；六段模板+数据源映射表+三级领导适配+生成流程+示例 1 篇）；②trigger_hooks.md 加触发行（关键词"给领导汇报/向上汇报/出汇报文档/给老板汇报"→ leader_report.md）+ 头部关键词注释 + 版本历史 v1.1.8；③SKILL.md 多行命中仲裁规则加一行（"汇报"→上下文限定：给领导/向上→leader_report；验收/手绘→hand-drawn-report；做PPT→html_ppt_creation；无上下文→澄清菜单）+ 资源索引加一行；④references/index.md 49→50 模块加行
  - 验证：`grep -n "leader_report" references/common/pa/trigger_hooks.md SKILL.md references/index.md` → 3 文件命中 + `ls references/common/da/leader_report.md` 存在（AC-011 共 4 文件）
  - 边界条件：正常=三表联动；异常=关键词误伤（"汇报"裸词不进触发行，靠仲裁表分流）
  - 验收标准（GWT）：Given 四处更新 When ls+grep Then leader_report.md 存在且 3 表各含 1 处引用+版本历史 bump
  - 不通过处理：漏表 → 按 AC-011 四文件清单逐个补
  - 改动白名单路径：`references/common/da/leader_report.md`（新增）、`references/common/pa/trigger_hooks.md`、`SKILL.md`（索引+仲裁）、`references/index.md`
  - 反向验证：否
  - 防作弊点名禁止：N/A（文档类）
  - 死规矩带后果：关键词必须精确集（禁裸"汇报"），否则与 hand-drawn-report/html_ppt 三重命中路由未定义（H4 复发）
  - 依赖排序说明：纯文档可与 T005 并行
  - 防幻觉验证：N/A（文档类，grep 验证）

- [ ] T007 文档同步 + 版本号统一升 v1.0.4
  - 怎么做：①working_memory_rules.md §2.2 记忆条目格式加 memory_class 字段说明+两层标签设计+索引行格式（格式规范唯一维护源，必须改否则新旧规则矛盾——M5）；②memory_governance.md 容量阈值口径改"数标签文件夹文件数"；③HISTORY.md 顶部加 v1.0.4 条目（三痛点改造+对抗审查+50 轮测试摘要）；④SKILL.md 头部版本注释 v1.0.3→v1.0.4；⑤跑 `grep -rn "v1\.0\.3" SKILL.md HISTORY.md README.md` 核对无版本号残留不一致（历史记录条目里的 v1.0.3 属正常保留，只改"当前版本"标记）
  - 验证：grep 版本号核对 + `python scripts/validate_skill.py` → ≥32/32 PASS 且 MUST FIX=0（AC-013 前置检查）
  - 边界条件：正常=版本统一；异常=validate 报 MUST FIX → 当场修完再过
  - 验收标准（GWT）：Given 全部改动完成 When validate_skill Then 32/32 PASS/MUST FIX=0 且当前版本标记统一 v1.0.4
  - 不通过处理：validate 失败项 → 逐条修（MUST FIX 清零门控，/act 步骤 0 规则）
  - 改动白名单路径：`references/common/pa/working_memory_rules.md`、`references/common/pa/memory_governance.md`、`HISTORY.md`、`SKILL.md`（版本号）、`README.md`（如有版本徽章）
  - 反向验证：否
  - 防作弊点名禁止：禁为过 validate 改判卷标准（validate 脚本本身不在白名单）
  - 死规矩带后果：版本号最后统一升，否则中间 task 的 WIP commit 携带错误版本号造成 sync-matrix 漂移
  - 依赖排序说明：所有内容改动完成后收口，先于 T008（测试要在最终版上跑）
  - 防幻觉验证：validate /do 实测

- [ ] T008 50 轮全流程测试 + validate 终验
  - 怎么做：①设计测试矩阵：50 轮 = 四阶段全流程（/plan→/do→/check→/act）× 脚本类型混合（技术修复 15 轮/写作任务 10 轮/发布任务 10 轮/巡检任务 10 轮/汇报任务 5 轮——第 5 类专门验证 leader_report），每轮检查点：a) /plan 读到新结构记忆 b) /do 产记忆落正确标签文件夹 c) /check 走 hand-drawn-report d) /act 弹互动问题（模拟回答与跳过两态各覆盖）+ 记忆含【互动复盘】段 e) 汇报轮按 leader_report 六段结构产出；②分 5 批执行（每批 10 轮，防上下文溢出），每批记录通过/失败数；③失败轮分析根因修复后该轮重跑；④汇总报告落 `docs_rj/check_rj/v104_memory_tag_act_report_test50_20260825.md`（50 轮明细+通过率+误判率统计+执行时长）；⑤终验 `python scripts/validate_skill.py` → 32/32
  - 验证：测试报告显示 50/50 通过（AC-014）+ validate 32/32（AC-013）+ 启发式误判率统计 <30%（spec 未验证假设①）
  - 边界条件：正常=50/50；异常=某轮失败 → 修复后重跑该轮（不计新轮数）；误判率 ≥30% → 停下上报用户决策升级人工规则
  - 验收标准（GWT）：Given v1.0.4 全部改动完成 When 50 轮分 5 批跑完 Then 50/50 通过+报告落盘+validate 32/32
  - 不通过处理：单轮失败 → 记录现象+根因+修复，重跑该轮；3 批整体失败率>20% → 停止测试回 /plan 复审设计
  - 改动白名单路径：`docs_rj/check_rj/v104_memory_tag_act_report_test50_20260825.md`（新增报告）；测试中发现的 bug 修复回归对应白名单文件
  - 反向验证：是——互动"跳过"态专门覆盖（证明 SKIPPED 留痕不 BLOCKED）
  - 防作弊点名禁止：禁凑数（没真跑写通过）/禁跳轮/每轮要有真实产出文件证据；用户明言"不省 token 不赶时间"
  - 死规矩带后果：必须分批跑，否则上下文溢出导致后半测试凭印象填（违反防幻觉）
  - 依赖排序说明：所有功能完成后终验；50 轮是用户明确的验收标准
  - 防幻觉验证：每轮产出文件（记忆/报告）为证，报告汇总明细

---

## Phase 3: 收尾

- [ ] T009 收尾：verified tag + 汇总汇报 + 合并决策
  - 怎么做：①`git tag task/v104_memory_tag_act_report/verified`；②向用户汇报：三痛点改造效果对照（spec §1.3 指标逐条）+ 50 轮测试摘要 + 文件变更清单（五要素+目录树）；③问用户 feature 分支合并 master 与否（用户决策点）
  - 验证：git tag 存在；汇报含全部 AC 结果
  - 验收标准（GWT）：Given T008 全过 When 收尾 Then verified tag 打上+完整汇报呈现+合并决策留给用户
  - 不通过处理：N/A（收尾类）
  - 改动白名单路径：无（git 操作+汇报）
  - 反向验证：否
  - 防作弊点名禁止：N/A（收尾类）
  - 死规矩带后果：合并决策必须留给用户，否则越权（铁律2 HARD-GATE 精神）
  - 依赖排序说明：最后一步
  - 防幻觉验证：N/A（收尾类）

---

## 连败换项规则（REQ-032 防死法4）

任一 task 验证连败 3 次 → 换下一个独立 task（T005/T006 文档类优先顶上），原 task 上报用户裁决。同一验收连败禁止第 4 次瞎试。

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-08-25 21:27 | 初版（T000-T009 全量分解，含 13 字段/白名单/反向验证） |

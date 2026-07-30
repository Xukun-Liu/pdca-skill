<!-- PDCA标签：P.bootstrap A.persist -->
<!-- 子标签场景：记忆读写规则 -->
<!-- 关键词清单：memory/记忆/存盘/检查点/5问/reboot/忘了/想不起来/上次聊了什么/进度在哪/接上/上次说到哪 -->
<!-- 引用范围：main + bootstrap_agent -->

# 工作记忆规则（Working Memory Rules）
> 阶段标签：P · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 更新：2026-07-24

> 📦 **用户数据外置说明（v1.0.0 新增）**：全局聚合记忆 `memory/memory_main.md` 与项目记忆 `docs_rj/memory_rj/{task}_memory_*.md` 均位于外置目录 `~/.riji-skill/data/` 下（非 skill 包内）。经 `scripts/memory_shadow_write.py` 的 `write_project()` 双写：落外置项目记忆 + 幂等 upsert 外置全局 `memory/memory_main.md`。路径解析经 `scripts/user_data_path.py`。

> 📖 **什么时候读这个文件**：
> - 不知道memory该写什么/怎么写时
> - 忘了RAM/Disk/存盘检查点/5问测试细节时
> - 不确定什么时候该存盘/归档时
> 🔴 **不要在这时候读**：
> - 已经在按Memory First正常读写memory时

---

## 1. 心智模型：RAM vs Disk

AI 必须理解：

| 概念 | 类比 | 特性 |
|------|------|------|
| 上下文窗口（当前对话） | RAM（内存） | 易失（/clear就没了）、有限（token上限）、速度快 |
| 文件系统（memory/、docs_rj/） | 硬盘 | 持久（关机也在）、无限、跨对话保留 |

核心原则：任何重要信息——发现、决策、错误、进度——必须写入文件（"存到硬盘"）。
只在脑子里（上下文）记着 = 没存，断电（/clear、上下文压缩、新对话）就丢了。

这不是"建议"，是硬规则，优先级等同于 Memory First。

---

## 2. memory 文件体系

### 三层结构

| 层级 | 文件 | 作用 | 写入时机 | 跟进 |
|------|------|------|----------|------|
| 热记忆 | SKILL.md + references/ | 协作框架规则，自动加载 | 框架自身维护 | - |
| 全局聚合记忆 | `memory/memory_main.md`（skill 包内） | 跨项目长期经验，按 `## {项目名}` 分段聚合 | 经 `write_project` 自动 upsert | 主次跟进（项目→全局） |
| 项目记忆 | `{项目根}/docs_rj/memory_rj/{task}_memory_YYYYMMDD_HHMM.md` | 本项目按任务阶段的记忆 | 任务进行中经 `write_project` 落盘 | 自动 upsert 全局 |

> 🗂️ **全局聚合 vs 项目记忆（主次跟进）**：项目记忆是落盘点（`{项目根}/docs_rj/memory_rj/`），全局 `memory/memory_main.md` 仅经 `write_project` 幂等 upsert 产生（按 `## {项目名}` 分段插入）。**禁止手工单文件写全局 memory_main**——会破坏主次跟进一致性，产生漂移。

### 写入方式（治本，write_project）

对话中写项目记忆一律走 `scripts/memory_shadow_write.write_project(task, content)`：
- 落 `{项目根}/docs_rj/memory_rj/{task}_memory_YYYYMMDD_HHMM.md`（append-only，带分钟级时间戳，天然按时间排序）
- 幂等 upsert `memory/memory_main.md` 的 `## {项目名}` 分段（全局自动跟进）
- **同分钟文件名冲突处理规则**：见 [document_specs.md](../pda/document_specs.md)「记忆写入与全局聚合」节（LOW-3 新增，统一维护避免漂移）

**写入即落盘 + 自动全局跟进，无独立归档步骤**——无需手工剪切/移动，无需手工收尾标记。

### 治理 flag（方案 3-R，软引用归档）

记忆条目可通过 flag 标记状态（不物理移动文件），符合"无独立归档步骤"硬规则：

| 状态 | 含义 | 工具 | 说明 |
|------|------|------|------|
| active | 活跃（默认） | write_project | 正常读写 |
| archived | 已归档（软隐藏） | memory_archive | 仍在原位，agent 可按需读 |
| demoted | 已降级 | memory_demote | 全局条目标记，不删除 |

**容量阈值触发**（防膨胀，无 LLM 时只隔离不删除）：
- 单项目段 > 30 条 OR > 50K 字符 → 标记 low+unknown 为 archived
- 全局总量 > 500 条 → 跨项目按 timestamp 标记 archived
- memory_rj/ 单文件 > 500 行 → 整文件移到 archive_rj/memory_rj/（保留最近 5 条）

**HARD-GATE 矩阵**：
- memory_delete：HARD-GATE（破坏性，默认软删除）
- memory_archive：自动（可逆）
- memory_promote：自动（复用 upsert）
- memory_demote：HARD-GATE（改全局状态）
- memory_rethink：HARD-GATE（LLM 建议，不自动执行）

**备份与回滚**：5 工具每次操作前自动备份到 `{user_data_dir}/undo/{tool}_{ts}/`，保留 30 天。CLI：`python memory_shadow_write.py --rollback <timestamp>`。

### 长期经验（关键决策/约定）

直接以 `write_project` 写入全局 `memory/memory_main.md` 的对应项目分段，始终保留、不参与"当日归档"。

**文件缺失时**：走 Bootstrap 初始化（见 [bootstrap.md](../../plan/bootstrap/bootstrap.md)），不静默创建。

---

## 2.1 记忆写入路由（R5）

对话中写项目记忆一律走 `memory_shadow_write.write_project(task, content)`，按 `task` 落到项目 `docs_rj/memory_rj/{task}_memory_*.md` 并幂等 upsert 全局 `memory/memory_main.md` 的 `## {项目名}` 分段：

| 内容类型 | 落盘文件 | 全局跟进 |
|----------|----------|----------|
| 用户画像/偏好/纠正 | `{项目根}/docs_rj/memory_rj/{task}_memory_*.md`（task 取 `user_profile` 等） | upsert `memory/memory_main.md` 对应项目分段 |
| 用户反馈/评价/对抗意见 | `{项目根}/docs_rj/memory_rj/{task}_memory_*.md` | 同上 |
| 重要决策及理由/项目进度/关键发现 | `{项目根}/docs_rj/memory_rj/{task}_memory_*.md` | 同上 |
| 参考资料/外部知识/链接 | `{项目根}/docs_rj/memory_rj/{task}_memory_*.md` | 同上 |

**失败策略（A3 + B5）**：
- 项目记忆落盘（`docs_rj/memory_rj/{task}_memory_*.md`）写入**必须成功**，失败抛错**阻断**对话（数据不丢）。
- 全局 upsert（`memory/memory_main.md`）写入失败**捕获后仅告警、不阻断**对话，并隔离故障（B5），不互相覆盖独有内容。
- 两者均**追加**写入，不整文件覆写。

---

## 3. 存盘检查点（Save Checkpoint）

### 规则内容

完成一轮"信息获取类操作"（无论几次），准备动手前必须停下来，把关键发现写入文件。

什么是"信息获取类操作"：
- Web搜索（WebSearch）
- 浏览器浏览网页（WebFetch、MCP browser工具）
- 查看截图/图片
- 阅读PDF/长文档
- 读取超过100行的长文件
- 使用grep/search进行代码搜索

### 写入目标（按信息类型分流）

> 🔁 **主次跟进（A3）**：所有项目记忆写入统一经 `memory_shadow_write.write_project(task, content)`——落 `{项目根}/docs_rj/memory_rj/{task}_memory_*.md`（必须成功）+ 幂等 upsert 全局 `memory/memory_main.md`（失败仅告警）。不再直接单文件写全局 memory_main。

| 信息类型 | 写入目标（经 write_project 主次跟进） | task 命名 |
|----------|----------------------------------------|-----------|
| 项目级发现（架构、代码模式、API用法） | 写入 `{主docs}/docs_rj/task_rj/{任务名}_task_*.md` 或 findings（非记忆，不入双写） | - |
| 用户画像/偏好/纠正/最佳实践 | `docs_rj/memory_rj/{task}_memory_*.md` | `user_profile` 等 |
| 用户反馈/评价/对抗意见 | `docs_rj/memory_rj/{task}_memory_*.md` | `feedback_xxx` 等 |
| 重要决策及理由/项目进度/关键发现 | `docs_rj/memory_rj/{task}_memory_*.md` | 对应任务名 |
| 参考资料/外部知识/链接 | `docs_rj/memory_rj/{task}_memory_*.md` | `reference_xxx` 等 |
| 对话过程中的进度记录 | `docs_rj/memory_rj/{task}_memory_*.md`（写入即落盘+自动全局跟进） | 对应任务名 |

### 为什么要设存盘检查点

视觉/多模态信息在上下文里衰减极快：
- 截图看了就忘（图片不持久化在上下文）
- 网页关了就没（WebFetch结果在长对话里会被挤出）
- 搜索结果10条以上就记不清前几条说了什么

存盘检查点（一轮信息获取后即存盘）是经过45K+用户验证的最佳实践——不要等到对话末尾才"总结"，那时中间发现已经丢了。

---

## 4. 5-Question Reboot Test（重启五问）

### 何时使用

- 每次新对话启动时（启动检查最后一步）
- 每次上下文被压缩（/compact）后
- 每次觉得"我好像忘了什么"时
- 复杂任务中断后恢复时

> 上下文压缩触发时，五问作为 SKILL.md references/plan/bootstrap/compaction_recovery.md 压缩恢复协议的**步骤5**执行——先读 SUMMARY+MEMORY（步骤2-3）、重读铁律（步骤4），再过五问（步骤5）。不单独触发。

### 五个问题

| # | 问题 | 去哪里找答案 | 答不上来怎么办 |
|---|------|-------------|---------------|
| 1 | 我现在在哪？（当前阶段/任务） | `docs_rj/memory_rj/{task}_memory_*.md`、task.md | 立刻读 task.md |
| 2 | 我接下来要去哪？（下一步做什么） | task.md 的待办项 | 立刻读 task.md |
| 3 | 最终目标是什么？ | spec.md、task.md Goal部分 | 立刻读 spec.md |
| 4 | 我已经学到了什么？（踩过的坑、关键发现） | `memory/memory_main.md`（本项目分段）、findings.md、错误记录 | 立刻读 memory/memory_main.md |
| 5 | 我已经做了什么？（已完成项） | `docs_rj/memory_rj/{task}_memory_*.md`、task.md 已完成标记 | 立刻读 task.md |

如果有任何一个问题答不上来，立刻停下来读文件，不要凭感觉继续。

**文件缺失时降级**：若 `memory/memory_main.md` 或项目 `docs_rj/memory_rj/{task}_memory_*.md` 不存在，回答"首次对话，无历史记录"即可通过五问，走 Bootstrap 初始化（见 [bootstrap.md](../../plan/bootstrap/bootstrap.md)）。不凭记忆编造历史。

**「最近1-2天」定义**：读取 `docs_rj/memory_rj/{task}_memory_*.md`（按文件名时间戳定位最近1-2天的文件）；若全部不存在，走 Bootstrap。

---

## 5. 保存时机 Checklist

以下时刻必须检查是否有未保存的进度，立即写入文件：

| # | 时机 | 要保存什么 |
|---|------|-----------|
| 1 | 完成一个阶段/任务项后 | 更新task.md状态（pending→in_progress→complete）+ 经 write_project 写 docs_rj/memory_rj/{task}_memory_*.md |
| 2 | 完成一轮信息获取操作后 | 存盘检查点：把发现写入对应文件（见§3 写入目标分流表） |
| 3 | 遇到错误并尝试修复后 | 更新错误记录（Error Log），Attempt计数+1 |
| 4 | 做了重要技术/方案决策后 | 经 write_project 写入 memory/memory_main.md 本项目分段（关键决策），写明理由 |
| 5 | 测试完成后 | 更新测试结果表（Test Results） |
| 6 | 用户回答了关键问题后 | 更新Key Questions表，划掉已回答的 |
| 7 | 准备压缩上下文前（/compact） | 强制全面检查：task.md状态最新吗？memory 写了吗？决策/错误/测试都记录了吗？ |
| 8 | **对话结束/用户说再见前** | **经 write_project 写记忆**（见§2）：落 docs_rj/memory_rj/{task}_memory_*.md + 自动 upsert 全局 memory_main，无需独立归档 |
| 9 | Stop-the-line触发时 | 先保存当前状态快照（docs_rj/memory_rj/{task}_memory_*.md + task状态），再停下来沟通 |
| 10 | 查看了图片/截图/网页后 | 立即把关键信息文本化写入findings（多模态信息最易丢失） |
| 11 | 解决一个错误后 | 除了更新Error Log，还要做Reflexion反思（见debugging.md §3.5） |
| 12 | 完成一个task/阶段后 | 更新task状态+做Reflexion反思，有规则缺口才记录到 memory/memory_main.md 本项目分段 |
| 13 | **交接时** | 生成交接文档后，刷新 {主docs}/SUMMARY_RJ.md（handoff section 新增条目 + 更新 last_updated + 跑漂移检查） |

---

## 6. 视觉/多模态信息即时文本化

最容易丢失的信息类型：图片、截图、网页截图、PDF内容。

规则：
1. 查看截图/图片后，立刻用文字描述关键内容：「截图显示：页面上有一个登录按钮在右上角，表单包含邮箱和密码两个字段」
2. 浏览网页后，立刻写下核心发现（不要只存URL，URL会过期或内容会变）
3. 阅读PDF后，摘要关键结论
4. 这些文字描述写入findings.md或task.md的视觉发现区
5. 不要等——看完立刻写，过了一轮操作后大概率已经遗忘了关键细节

---

## 7. 记忆评估参数（方案A）【v1.0.0 新增】

write_project 支持以下可选参数（agent 自身 LLM 评估，不调外部 API）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `importance_level` | str | "medium" | 重要性等级（high/medium/low） |
| `is_lesson` | bool | False | 是否为可复用经验 |
| `experience_tags` | list | [] | 经验标签列表（如 ["bugfix", "architecture"]） |

### 评估时机
agent 在调用 write_project 前先做语义评估：
- 这条记忆是否为可复用经验？（is_lesson）
- 重要性等级？（importance_level）
- 属于什么领域？（experience_tags）

### 评估标准
- `importance_level=high`：关键决策/bug修复/架构变更/用户明确要求记住
- `importance_level=medium`：常规任务记录
- `importance_level=low`：日常流水账
- `is_lesson=true`：含可复用的经验/教训/模式

### 与 distill 的关系
- write_project 标记 `is_lesson=true` 的条目 → memory_distill.py 提取为 lessons.json
- /act 阶段 agent 用自身 LLM 填充 reflection 字段完成经验提炼
- 用户采纳后经 write_project 写回 memory_main.md（importance_level=high, experience_tags 含 "adopted_lesson"）

---

## 8. 反模式：什么时候你违反了工作记忆规则

| 反模式 | 正确做法 |
|--------|----------|
| "我先做完这部分再一起记" | 不行，存盘检查点是硬规则 |
| "这个我记得住" | 你记不住，token窗口有限，先存盘 |
| "对话末尾再写memory总结就行" | 末尾只写总结，中间发现已经丢了 |
| "截图看了但我没什么要写的" | 强制问自己：看到了什么关键信息？写下来 |
| "读了个文件但没发现新东西" | 如果文件超过100行，至少写一句"读了XX文件，确认了YY" |
| 上下文压缩前没检查保存状态 | 这是严重违规，压缩后丢失的信息无法恢复 |
| **"对话结束不写记忆"** | **必须写**：经 write_project 落 docs_rj/memory_rj/{task}_memory_*.md + 自动 upsert 全局 memory_main |
| **"memory/ 缺失就静默创建"** | **禁止**：走 Bootstrap 引导（见 bootstrap.md），报告后逐个确认创建 |
| **"YYYY-MM-DD.md 缺失就不写"** | 归档时如不存在则创建（用归档模板），这是正常流程不是 Bootstrap |

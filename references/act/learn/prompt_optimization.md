<!-- PDCA标签：A.learn -->
<!-- 子标签场景：prompt减法、规则层审查、OpenAI原则、GPT-5.6适配 -->
<!-- 关键词清单：prompt优化/减法原则/规则层扫描/绝对规则/过程指令/重复规则/硬性密度/结果优先/OpenAI/GPT-5.6/prompt_guidance -->
<!-- 引用范围：main + learn_opt_agent -->

# Prompt 优化参考模块（某 prompting 指导 降维）

> 版本：v1.1.0 | 新增：2026-07-15 | PDCA 标签：A.learn
> 对应脚本：[scripts/learn_tidy.py](../scripts/learn_tidy.py)（prompt_metrics 字段）
> 对应 spec：[docs_rj/spec_rj/prompt_optimization_spec_20260715_1600.md](../docs_rj/spec_rj/prompt_optimization_spec_20260715_1600.md)
> 参考来源：某 prompting 指导（developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6，2026-07）
> 阶段标签：A（旧标签，以头部 PDCA 标签为准）

---

## §1 12 条原则速查表

| # | 原则 | 一句话 | riji-skill 对应 | 判断标准 |
|---|---|---|---|---|
| 1 | 先简化（Trim） | 从已工作的 prompt 开始，一次移除一组，重跑 evals | SKILL.md 主体+references/*.md（真实数据见 §5） | 重复规则重述≥3次→考虑合并 |
| 2 | 结果优先（Outcome-first） | 描述目标而非规定每步；ALWAYS/NEVER 只用于真不变量 | L150"第一步永远是"（过程指令） | 判断类用决策规则，非绝对词 |
| 3 | 人格/协作/长度 | personality 和 collaboration style 都保持简短 | L109-114 承诺装置偏长 | 每节≤10行 |
| 4 | 自主权边界 | 审查→报告不改；改动→本地改+非破坏性验证；外部→需确认 | L116-127 指令层级（未命名安全本地动作） | 明确命名读取/检查/测试=安全 |
| 5 | 工具路由 | 只暴露任务相关工具；依赖前置检索时明确说 | trigger_hooks.md（未按任务限定暴露） | 路由表按任务过滤 |
| 6 | 程序化工具调用（PTC） | 用于 bounded workflows（过滤/聚合/去重） | **不适用**（markdown 框架无 PTC） | N/A |
| 7 | 接地/引用/检索预算 | 引用行为作为 prompt 一部分；缺证据时如何降级 | L424 文件变动声明（无检索预算） | 缺证据≠事实 no |
| 8 | 长时工作流 | 第一个工具调用前发简短前言；大里程碑后压缩 | L266-271 存盘检查点（✅已覆盖） | 里程碑压缩非每轮 |
| 9 | 推理努力 | low=延迟敏感；medium=平衡起点；high 仅当 evals 增益 | 无按任务难度调整机制 | 按任务分级调推理强度 |
| 10 | 前端/视觉 | 提供产品上下文、保留现有设计系统 | **不适用**（非前端框架） | N/A |
| 11 | 完成前检查 | 给验证工具访问；编码跑测试/lint/构建 | L667 Verification+L653 对抗审查（✅） | 改动后必跑验证 |
| 12 | prompt 结构 | Role/Personality/Goal/Success/Constraints/Tools/Output/Stop | 按主题组织（非8段式，可接受） | OpenAI 说"starting point" |

---

## §2 减法审查清单（agent reflect 用）

agent 读 scan_report.json 的 prompt_metrics 后，按以下 4 项提 add/delete/replace 建议：

### 2.1 绝对规则→决策规则

**判断标准**：ALWAYS/NEVER/must/only 用于判断类（如何时搜索、何时提问、何时迭代）而非真不变量（安全/必填字段/禁止动作）。

**示例**：
- ❌ "永远先判断流程"（过程指令+绝对词）→ ✅ "每个任务必须先确定流程"（结果描述）
- ❌ "禁止凭记忆回答"（绝对词）→ ✅ "回答前需读文件确认，除非是纯概念问答"（决策规则）

**对应 scan_report 字段**：`prompt_metrics.absolute_terms`
- `ALWAYS/永远/必须` count > 15 → 考虑减绝对规则
- `NEVER/永不/禁止` count > 10 → 考虑减绝对规则

### 2.2 过程指令→结果描述

**判断标准**：规定"第一步、先、再、然后、按这个走"的过程指令，若模型已可靠执行，可改为结果描述。

**示例**：
- ❌ "第一步永远是先判断流程，再行动"（过程）→ ✅ "每个任务的产出必须先含流程判断结论"（结果）

**对应 scan_report 字段**：`prompt_metrics.process_vs_outcome`
- `ratio > 2:1`（过程指令是结果指令的2倍以上）→ 考虑改结果优先

### 2.3 重复规则→合并

**判断标准**：同一规则在 SKILL.md/references 出现≥3次，考虑合并到主定义处+其他处用引用。

**示例**（基于真实数据）：
- "报错询问机制" 出现5次（L82/L142/L199/L217/L671）→ 合并到 L142（主定义）+其他4处用"见 trigger_hooks.md 报错询问机制节"
- "HARD-GATE确认才动手" 出现5次（L79/L204/L647/L651/L663）→ 合并到 L79（铁律主定义）+其他4处用"见铁律2"

**对应 scan_report 字段**：`prompt_metrics.rule_repetitions`
- `count ≥ 3` → 考虑合并

### 2.4 不必要示例→删除

**判断标准**：示例不改变行为（即删掉后模型仍按规则执行），可删除以节省 token。

**示例**：
- L177-185 澄清菜单示例（7行）→ 若模型已可靠执行澄清菜单格式，可删示例只保留格式规范

**对应 scan_report 字段**：无（需 agent 语义判断，脚本无法检测）

---

## §3 scan_report.json 的 prompt_metrics 字段解读

| 字段 | 阈值 | 含义 | 建议动作 |
|---|---|---|---|
| `absolute_terms.total` | > 40 | 绝对规则词总数过高 | 审查哪些可改决策规则 |
| `absolute_terms.by_term.ALWAYS.count` | > 15 | ALWAYS 类过多 | 优先减 ALWAYS/永远/必须 |
| `absolute_terms.by_term.NEVER.count` | > 10 | NEVER 类过多 | 优先减 NEVER/永不/禁止 |
| `rule_repetitions[].count` | ≥ 3 | 同一规则重述≥3次 | 合并到主定义+其他处用引用 |
| `hardmark_density.total` | > 40 | 【硬性】标记过多 | 审查哪些可降级为弹性指引 |
| `hardmark_density.density_per_lines` | < 15 | 平均每<15行一个【硬性】 | 密度过高，考虑减标记 |
| `process_vs_outcome.ratio` | > 2:1 | 过程指令是结果指令2倍以上 | 改结果优先 |

---

## §4 修复建议模板（对齐 learn_cycle.md §3）

agent 提建议时，每条按 learn_cycle.md §3 bounded edit 格式，并追加 prompt_metrics 证据：

```markdown
### 建议 #{编号}

- **操作类型**：add / delete / replace
- **目标文件**：{完整绝对路径}
- **位置**：{行号范围或区块名}
- **内容**：
  ```
  {add/delete/replace 的具体内容}
  ```
- **rationale**：{为什么提这条建议}
- **prompt_metrics 证据**：{引用 scan_report.json 的具体字段值，如 "rule_repetitions[0].count=5, locations=[L82,L142,L199,L217,L671]"}
- **OpenAI 原则依据**：{对应12条原则的编号，如 "原则1 先简化 + 原则2 结果优先"}
```

---

## §5 OpenAI 原则 vs riji-skill 真实数据对照

基于真实扫描数据（scan_report.json 20260715-160938）：

| 原则 | riji-skill 现状 | 真实数据 | 缺口 |
|---|---|---|---|
| 1 先简化 | 7764行（SKILL.md+references）+125个【硬性】 | 20条规则重述≥3次（rule_repetitions） | HIGH |
| 2 结果优先 | 262个绝对规则词 | ALWAYS类125+NEVER类75+must类7+only类55；过程指令521 vs 结果指令30（ratio=17.37:1） | HIGH |
| 3 人格/协作 | 承诺装置6行+沟通五原则21行 | 偏长 | LOW |
| 4 自主权边界 | 指令层级5层 | 未命名"安全本地动作" | LOW |
| 5 工具路由 | trigger_hooks.md | 31个 reference 全暴露 | LOW |
| 7 接地/引用 | 无检索预算 | 无"缺证据降级"规则 | MEDIUM |
| 9 推理努力 | 无分级机制 | 所有任务同一强度 | MEDIUM |

**关键发现**：
- 原则2（结果优先）缺口最大：ratio=17.37:1（过程指令是结果指令17倍），262个绝对规则词中多数是判断类而非真不变量
- 原则1（先简化）缺口次之：20条规则重述≥3次，最高频规则需合并到主定义+其他处用引用
- 【硬性】密度：125个/7764行=每62行一个，密度不算高（阈值<15行才算高），暂不作为优先修复项

---

## §6 不适用原则说明

| 原则 | 不适用理由 |
|---|---|
| 6 程序化工具调用（PTC） | riji-skill 是 markdown 框架，无程序化工具调用场景 |
| 10 前端/视觉 | riji-skill 非前端框架，无视觉/布局/设计系统 |
| 12 prompt 结构8段式 | 按主题组织也合理，OpenAI 明确说"Use this structure as a starting point"，不强制改 |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-15 16:10 | 初版：基于 某 prompting 指导 降维成 12 条原则速查表+减法审查清单+prompt_metrics 字段解读 |

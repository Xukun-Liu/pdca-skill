<!-- PDCA标签：P.design D.code -->
<!-- 子标签场景：少写代码原则 -->
<!-- 关键词清单：少写代码/复用优先/YAGNI/7级决策梯子/最小实现 -->
<!-- 引用范围：main + bootstrap_agent -->

# 少写代码 / 复用优先原则

> 阶段标签：D（旧标签，以头部 PDCA 标签为准）
>
> 版本：v1.0.0 | 更新：2026-07-25
>
> 📖 **什么时候读这个文件**：
> - 进入 `/plan` 流程做方案对比时
> - 准备写代码前想判断"能不能少写"
> - 用户要求"精简代码"/"复用优先"/"避免过度工程"时
> - 发现 AI 有过度设计、重复造轮子、提前抽象倾向时
>
> 🔴 **不要在这时候读**：
> - 用户明确要求"怎么写都行，先跑起来"时
> - 纯概念问答，不涉及具体实现方案时

---

## 核心思想

不是"代码越短越好"，而是：

> **在满足需求、守住安全与正确性底线的前提下，优先复用已有资源，避免重复造轮子。**

少写代码的真正价值不是炫技，而是减少：
- **维护面**：代码越少，未来需要读、改、测的地方越少
- **bug 面**：新代码是新 bug 的主要来源
- **token 消耗**：AI 少生成代码 = 降低调用成本
- **认知负担**：团队成员需要理解的东西越少

---

## 7 级决策梯子

AI 在动手写代码前，必须按这个顺序决策：

| 阶梯 | 问题 | 行动 |
|------|------|------|
| 1 | 这东西需要存在吗？ | 不需要 → 跳过，明确说"YAGNI" |
| **1.5** | **外部有没有现成 skill / 项目？** | **跑 `python scripts/find_similar.py scan --task "{任务}" --keywords "{关键词}"` 搜 GitHub + Gitee + Coze + 腾讯 SkillHub + skills.sh（6 源）。找到 → 评估复用方式（直接引用 / 封装适配 / 参考架构 / 仅学习）；跳过条件：用户明确说"不用搜" 或 纯 bug 修复/参数调整。详见 [§6 /plan 步骤 4a.3](../../../SKILL.md) + [agent_find.md](../../plan/route/agent_find.md)** |
| 2 | 代码库里已经有吗？ | 复用现有函数/模块/配置 |
| 3 | 标准库能做吗？ | 用标准库 |
| 4 | 原生平台特性能做吗？ | 用原生能力（如 `<input type='date'>`） |
| 5 | 已安装的依赖能做吗？ | 用已有依赖 |
| 6 | 一行代码能解决吗？ | 那就一行 |
| 7 | 最后才写 | 最小实现，刚好满足需求 |

**第 1.5 级说明【硬性·v1.0.0 新增】**：

- **为什么加这一级**：历史执行中曾出现"代码库里没有，但 GitHub 上有现成 skill 直接能用"的场景被跳过，导致重复造轮子。这一级把"外部资源搜索"从"推荐"升格为"梯子必经步骤"，与 §6 /plan 步骤 4a.3 的 `find_similar.py` 硬规则呼应。
- **执行动作**：跑 `find_similar.py scan` → 评估候选 → 写入 spec §0.A 复用资源清单 → 在步骤5 方案对比中引用本步骤结果。
- **跳过条件**：①用户明确说"不用搜"；②纯 bug 修复/参数调整（与 §6 /plan 步骤4a 跳过条件一致）。跳过时必须记录到 memory。
- **与第 2 级关系**：第 1.5 级查"代码库外"，第 2 级查"代码库内"。先外后内是为了避免"代码库内有但更糙的版本"被先用——若外部有更成熟的实现，封装适配后可能比内部复用更省维护成本。
- **网络不可用降级**：`find_similar.py` 跑不通 → 标注"网络不可用，外部搜索跳过"，进步骤2，不阻塞。

**举例**：用户要一个日期选择器。

- 普通 AI：安装 `flatpickr` → 写包装组件 → 加样式 → 讨论时区
- 应用本原则后的 AI：先问"原生 `<input type='date'>` 够不够用？" → 如果够用，直接给一行 HTML

---

## 理论依据

| 原则 | 来源 | 核心思想 |
|------|------|----------|
| **DRY**<br>Don't Repeat Yourself | Andy Hunt & Dave Thomas,《The Pragmatic Programmer》(1999) | 每项知识在系统中只应有一处权威表达 |
| **YAGNI**<br>You Aren't Gonna Need It | Ron Jeffries / Kent Beck, Extreme Programming | 不要为未来可能的需求写代码 |
| **KISS**<br>Keep It Simple, Stupid | Kelly Johnson, Lockheed Skunk Works | 设计应简单到普通人能维护 |
| **Rule of Least Power** | Tim Berners-Lee & Noah Mendelsohn, W3C TAG Finding (2006) | 选能力刚好够用的方案 |
| **Worse is Better** | Richard P. Gabriel,《The Rise of "Worse is Better"》(1989) | 简单可实现的方案胜过理论上完美的复杂方案 |
| **Choose Boring Technology** | Dan McKinley,《Choose Boring Technology》(2015) | 日常用经过验证的"无聊"技术，把创新预算留给真正值得冒险的地方 |
| **AHA**<br>Avoid Hasty Abstractions | Kent C. Dodds,《AHA Programming》(2020) | 先允许一定重复，等模式稳定后再抽象 |
| **The Wrong Abstraction** | Sandi Metz,《The Wrong Abstraction》(2016) | 错误的抽象比重复代码更贵 |

这些原则不是新东西，但 AI 编码时代需要被重新编码成**可执行的提示词规则**。

---

## 同类项目参考

### GitHub

| 项目 | 说明 | 可信度 |
|------|------|--------|
| **agent-skills** (addyosmani/agent-skills) | 24 个生产级工程技能，含 code-simplification、incremental-implementation | Addy Osmani（Google Chrome 工程负责人）维护 |
| **andrej-karpathy-skills** (forrestchang/andrej-karpathy-skills) | 单个 `CLAUDE.md`，含 Simplicity First / Surgical Changes | 个人整理，内容源自 Andrej 某专家 公开观察 |
| **awesome-cursorrules** (PatrickJS/awesome-cursorrules) | `.cursorrules` 规则合集，可挑"复用优先"类规则 | 社区维护 Awesome 列表 |
| **某开源项目** (某开源项目) | GitHub 官方规范驱动开发工具包 | **官方项目** |

### Gitee

| 项目 | 说明 | 可信度 |
|------|------|--------|
| **cursorrules-cn** (leonda/cursorrules-cn) | 中文 CursorRules 聚合站点 | Gitee 仓库，有在线站点 |
| **AI开发脚手架** (huang_yang/ai-developed-scaffolding) | Cursor/Trae/Qoder 提示词与规则模板 | 个人项目 |
| **APIJSON** (TommyLemon/APIJSON) | 腾讯开源，零代码接口与文档 ORM，强调后端少写代码 | 企业级开源 |

---

## 与 riji-skill 现有规则的衔接

- 与 `references/do/code/code_rules.md` 的 **Simplicity First** 一致：能 50 行解决的不写 200 行。
- 与 **No Placeholders** 一致：少写代码不等于写省略号或伪代码，而是给完整且最小化的实现。
- 与 **HARD-GATE** 一致：方案必须经你确认，AI 不能借"少写"之名擅自砍掉必要功能。
- 与 **Memory First** 一致：重要的"为什么不写"决策要写入项目记忆，避免每次重复争论。

---

## 红线：这些绝对不能"少写"

> ⚠️ 以下领域不允许为了"少写代码"而省略：
> - **理解问题本身**：没看懂需求就动手，写得再短也是错的
> - **输入校验**（尤其信任边界）：用户输入、外部 API、文件上传等必须校验
> - **错误处理与数据丢失保护**：异常路径、回滚、数据完整性不能省
> - **安全**：认证、授权、加密、防注入、防越权等
> - **可访问性**：面向用户界面需考虑基础 a11y
> - **用户明确要求实现的功能**：用户说要做，就不能以"少写"为由砍掉

**原则**：在这些红线上，"懒"是"高效但可靠"，不是"偷懒"。

---

## 在 `/plan` 中的应用

进入 `/plan` 流程后，在"方案对比"环节必须增加以下评估：

- [ ] **是否跑了外部资源搜索（梯子第 1.5 级）**？跑 `find_similar.py scan`，结果写入 spec §0.A；若跳过需满足跳过条件（用户说"不用搜"/纯 bug 修复）+ 记录到 memory
- [ ] 该方案是否优先复用了现有代码/标准库/原生能力/已装依赖？
- [ ] 该方案是否引入了非必要的新依赖？
- [ ] 该方案是否为未来可能的需求预写了代码（YAGNI 违规）？
- [ ] 各方案中，哪个新增代码量/文件数最少？
- [ ] 是否存在因"少写"而触碰红线的风险？

如果某个方案在"复用优先"维度明显更优，即使它在"技术新颖性"上得分较低，也应优先推荐。

---

## 正例与反例

### 正例

- **日期选择器**：优先使用原生 `<input type='date'>`，而不是安装 `flatpickr` 并封装组件。
- **修 bug**：先 grep 所有调用者，找到公共函数统一加 guard，而不是在每个调用点复制粘贴修复。
- **数据深拷贝**：优先使用 `structuredClone()`，而不是引入 `lodash` 或写递归函数。

### 反例

- 为了"少写代码"删掉用户输入校验。
- 用户说"可能以后支持多语言"，就直接写完整 i18n 框架。
- 第一次见到两处相似代码就强行抽象，导致后续不断加条件分支。

---

## 一句话总结

> **先问"能不能不写"，再问"能不能复用"，最后才写"最小且完整"的实现。**

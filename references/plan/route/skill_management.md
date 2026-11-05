<!-- PDCA标签：P.route -->
<!-- 子标签场景：Skill 搜索安装 -->
<!-- 关键词清单：部署/发布/上线/CI/CD/持续集成/pipeline/docker/k8s/金融/PDF/Word/Excel/图片/视频/音频/Office/自动化/爬虫/数据分析/专业领域/专用工具 -->
<!-- 引用范围：main + skill_mgmt_agent -->

# 技能发现与安装（Skill 管理）
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 更新：2026-08-20

> 📖 **什么时候读这个文件**：
> - 任务涉及专业领域，不确定有没有现成 Skill 时
> - 用户明确/暗示"有没有 skill 能搞定 XX""帮我找下 XX 工具"时
> - 自己通用能力不够、明显缺专业工具时（**第一步**就来看）
> - 用户点名"用 XX skill"且需要安装时

🔴 **不要在这时候读**：

- 通用任务（写代码/改文件/问答/文档）且确认无需外部 Skill 时

---

## 一、触发信号（满足任一即进入本流程）

1. 任务落在专业域（金融数据 / PDF·Word·Excel·PPT / 浏览器自动化 / 图片·视频生成 / 部署 / 测试 / 设计 …）
2. 用户说"有没有 skill 能 XX""帮我找下 XX 工具"
3. 当前通用能力搞不定，明显缺专业工具
4. 用户点名"用 XX skill"
5. 用户提供 GitHub 仓库 URL 并希望安装 skills

---

## 二、Skill 发现与安装流程

### 流程总览

```
触发信号 → agent-find 搜索（统一走 agent_find.md 四层降级：① Exa REST → ② Exa MCP → ③ WebFetch → ④ WebSearch） → 安全扫描 → 用户确认 → 安装（npx 可选，降级处理） → 验证
              │                    │                              │
              ▼                    ▼                              ▼
       [agent_find.md]      [skill_security.md]            [Step 4 验证]
```

### Step 1: 技能发现（agent-find）【统一走 agent_find.md 四层降级：① Exa REST → ② Exa MCP → ③ WebFetch → ④ WebSearch；不用 npx】

详细流程见 [agent_find.md](agent_find.md)：

1. **理解需求**：识别领域和具体任务
2. **统一走 agent_find.md 四层降级搜索**：详见 [agent_find.md](agent_find.md)——① Exa REST 直连（读 `EXA_API_KEY` 环境变量或 `exa.env.json`）→ ② Exa MCP（OAuth 免 key）→ ③ WebFetch（URL 抓取）→ ④ WebSearch。搜索词如 `best claude agent skill for X`、`mcp server for X`
3. **降级兜底**（Exa REST 与 MCP 都不可用时）：按 agent_find.md 第③④层降级——WebFetch 访问 `https://www.skills.sh/` 拿排行榜 + WebSearch 全网/`site:skills.sh <关键词>` 搜特定领域；或 WebFetch 直接访问技能页面
4. **验证质量**：检查安装数量、来源信誉、GitHub stars
5. **呈现选项**：给用户展示 top 3–5 候选（名字+用途+安装量+来源+安装命令）

> ⚠️ **搜索环节不依赖 npx**——AI 内置 WebFetch/WebSearch 工具，零系统依赖，跨平台可用。

### Step 2: 安全扫描（必选）

**CRITICAL:** 在安装任何 skill 之前，必须执行安全扫描。

详细流程见 [skill_security.md](skill_security.md)：

1. **调用 SkillAudit API**：扫描 SKILL.md 文件（用 WebFetch 调用，不依赖 npx）
2. **评估风险等级**：clean → low → moderate → high → critical
3. **决策**：
   - clean：自动安装
   - low：提醒用户后安装
   - moderate 及以上：拒绝安装

### Step 3: 安装（降级处理）【硬性】

安装环节分两档处理：

**情况A：npx 可用（有 Node.js 环境）**

| Agent | Install path |
|-------|-------------|
| Claude Code | `~/.claude/skills/{skill_name}/` |
| Codex | `~/.codex/skills/{skill_name}/` |
| Cursor | `~/.cursor/skills/{skill_name}/` |
| Other | `~/.agent/skills/{skill_name}/` |

**安装命令**：
```bash
npx skills add <owner/repo@skill> -g -y
```

**情况B：npx 不可用（无 Node.js / PowerShell 执行策略禁用 / 其他原因）**

**降级处理**——呈现安装命令让用户自己跑：

```
检测到当前环境无法自动安装 skill（原因：npx 不可用）。

请在终端手动执行以下命令安装：
  npx skills add <owner/repo@skill>

或者访问以下链接查看手动安装方式：
  https://skills.sh/<owner>/<repo>/<skill-name>

安装完成后告诉我，我来验证是否就位。
```

**禁止**【硬性】：
- ❌ npx 跑不了就放弃整个流程（搜索功能不依赖 npx，仍可用）
- ❌ 静默跳过安装（必须告知用户安装命令）
- ❌ 强制用户改系统设置来装 skill

### Step 4: 验证

```bash
ls -la ~/.agent/skills/<skill-name>
```

- 确认 `SKILL.md` 等文件就位，再向用户报成功
- 若目标目录已存在同名 skill：显式处理冲突（跳过 / 替换 / 改名），不要静默覆盖
- 若 Step 3 走的降级方案（用户自己装），等用户告知装完后再验证

---

## 三、找不到怎么办（不硬撑）

1. 如实说"没有找到匹配的 skill"
2. 用通用能力直接帮他把事办了（或问是否继续）
3. 若他常做这类事，建议自建：`npx skills init my-xyz-skill`（需 npx 可用）

---

## 四、安全与确认【硬性】

- **仅从可信源安装**（`vercel-labs`、`anthropics`、`microsoft` 等官方来源）
- **安装前必须安全扫描**：见 [skill_security.md](skill_security.md)
- **不装来路不明、要求可疑权限的 skill**

---

## 五、Skill 调用铁律【硬性】

1. **能力不足时先走本流程的搜索流程**，不要硬撑
2. **调用前先读 Skill 说明**，了解能力和限制
3. **Skill 冲突时**，以你明确指令为准
4. **Skill 调用失败**，立即回退到通用方法，不要卡住

---

## 版本历史

| 版本 | 时间       | 变更                                                       |
| ---- | ---------- | ---------------------------------------------------------- |
| v1.0.0 | 2026-07-21 | 初版：Skill 管理决策树+搜索→安装→验证流程 |
| v1.1.0 | 2026-08-20 | 对抗审查修复：安装路径表补 TRAE 列（`~/.trae-cn/skills/`）；§三自建建议改为指向 skill_creation.md 全流程（npx init 仅作可选脚手架，补齐降级路径） |

---

<!-- 自 SKILL.md 下沉（v1.1.0），本节为唯一维护源 -->

## §0.5 Skill 管理决策树（何时调用其他 Skill）

本 Skill 是协作框架，不覆盖所有专业能力。遇到专业领域任务，优先调用对应的专用 Skill。

- **完整决策树 / 搜索→安装→验证流程 / agent-find 动态搜索机制 / Skill 调用铁律**：全部下沉至 [references/plan/route/skill_management.md](skill_management.md)（按需读，零系统依赖）。
- 一句话：任务涉及专业领域 → 走 skill_management.md 的「搜索→安装→验证」；你点名“用 XX skill” → 直接加载；能力不足 → 先搜专用 Skill 再动手；要新建/改写一个 skill → 走 skill_creation.md 的「意图捕获→结构→写法→测试迭代」。

### 外部术语引入即登记或澄清【硬性·v1.0.0 新增】

当方案文档/外部资料/用户输入引入**项目内不存在的术语**时（如 "E1-E5 平台机制" 等外部代号），必须立即处置：

- **检测方式**：引入术语后，用 Glob + Grep 全项目搜索该术语，若无任何匹配 → 视为外部术语
- **处置二选一**：
  1. **登记到项目词典**：在 `docs_rj/spec_main_rj.md` 或新建 `docs_rj/glossary_rj.md` 中登记术语 + 含义 + 来源 + 引用位置
  2. **第一时间澄清**：走 §0 澄清菜单问用户"术语 X 指什么？是 Y 还是 Z？"
- **禁止行为**：禁止凭印象猜测术语含义后直接使用（违反铁律5"凭记忆动手=偏离"）
- **原因**：历史执行中曾出现引入项目里完全无记录的外部术语，导致无法执行
- **与 §0 澄清菜单关系**：本节是"术语"维度的强化，澄清菜单是"任务方向"维度的兜底，两者互补

---

## §0.55 先查 skill 原则【硬性】

> 接到任务后，**第一件事不是 brainstorming，而是查 SKILL.md §0 触发钩子表 + 翻 references/plan/route/skill_management.md 看有没有专用 skill 命中**。本节是 §0.5 Skill 管理决策树的执行时点强化——"先查后做"，避免直接用通用能力硬上专业领域任务（专业 skill 的领域知识远厚于通用能力，跳过 = 浪费专业资源 + 产出质量打折）。

**硬规则**：

1. **接到任务的第一动作是查 skill**：不是先 brainstorming，不是先写 spec，而是先扫 SKILL.md §0 触发钩子表 + 翻 references/plan/route/skill_management.md 看有没有专用 skill 命中
2. **专用 skill 优先于通用能力**：若专用 skill 存在（如 web-dev / frontend-design / pdf / agent-browser 等），**优先调用该 skill** 而非用通用能力硬上
3. **调用专用 skill 时必记 memory**：在 memory 中记录"调用了 XX skill 处理 YY 任务"（经 `write_project` 落盘），留痕便于后续追溯——这也是 §1.6 每轮声明 skill 使用的数据源
4. **专用 skill 不可用时才回退通用能力**：专用 skill 未安装 / 不匹配 / 能力不足时，才回退到通用能力，**且需明确告知用户**"专用 skill XX 不可用，使用通用能力顶上，可能效果不如专用 skill"

**与 §0.5 的关系**：§0.5 定义"何时调用其他 Skill"的决策树（完整决策树见 skill_management.md），§0.55 定义"接到任务必须先查"的执行时点（动态触发规则）。两者互补，不冲突——§0.5 是"知道有这些 skill"，§0.55 是"每次接任务都要查一遍"。

> 类比：医生接诊第一动作是翻诊断手册 + 查专科医生目录，不是凭经验直接开药。专科医生在（专用 skill）→ 转诊；不在 → 自己看（通用能力）+ 告知患者"这科没专科医生，我全科顶上"。

---

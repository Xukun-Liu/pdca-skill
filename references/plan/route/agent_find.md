<!-- PDCA标签：P.route -->
<!-- 子标签场景：动态搜索 agent -->
<!-- 关键词清单：agent-find/动态搜索/部署/搜skill -->
<!-- 引用范围：main + skill_mgmt_agent -->

# Agent Find（找 agent / 能力 / 联网搜索统一入口）
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-19

> 📖 **什么时候读这个文件**：
> - **凡是需要"搜网上的东西"的场景**——找 skill / 找 agent / 找工具 / 找 MCP server / 查开源项目 / 查技术方案 / 查文档等，都先读本文件
> - 用户问"how do I do X"且可能有现有 skill / agent
> - 用户说"find a skill for X"或"is there a skill for X"
> - 用户问"can you do X"且 X 是专业能力
> - 用户表达扩展 agent 能力的兴趣
> - 用户想搜索工具、模板或工作流
> - 用户提到希望在特定领域（设计、测试、部署等）获得帮助
> - 用户问"有没有好用的 MCP""推荐个 agent / 工具"

---

## Exa 搜索【四层优先级】

本机制搜索优先级为：**① Exa REST API 直连（首选）→ ② Exa MCP（可选上层）→ ③ WebFetch（URL 抓取）→ ④ WebSearch（兜底）**。最轻便用法是 REST 直连——无需配 MCP、无需 OAuth，直接读 `EXA_API_KEY`（环境变量或 `exa.env.json`）打搜索。

> **四层降级触发逻辑**：
> - **① Exa REST**：环境变量 `EXA_API_KEY` 或 `exa.env.json` 存在 → 走 REST 直连（语义搜索，精准度最高）
> - **② Exa MCP**：REST key 不存在但已配 Exa MCP（`https://mcp.exa.ai/mcp`，OAuth 免 key）→ 走 MCP
> - **③ WebFetch**：Exa 都不可用 → 用 WebFetch 访问已知 skill 列表站点（如 `https://www.skills.sh/`、`https://某开源仓库`）抓静态列表
> - **④ WebSearch**：WebFetch 也拿不到 → 用 WebSearch 搜 `best agent skill for {关键词}`
>
> **注意**：REST 与 MCP 是两套独立鉴权体系；REST 用 `x-api-key` 头，MCP 走 OAuth/可选 key。REST 直连更轻、更无需 UI 配置，是首选。

### ① (首选) Exa REST API 直连

**最轻便、零 UI 配置**：不依赖 MCP、不弹 OAuth 登录，直接 `POST https://api.exa.ai/search`，用 `x-api-key` 头携带 key 即可搜索。key 优先从环境变量 `EXA_API_KEY` 读取，其次从仓库根 `exa.env.json` 读取（见下方示例）。

**权威事实（REST API）**：

- 端点：`POST https://api.exa.ai/search`
- 鉴权头：`x-api-key: <你的key>`
- 请求体（JSON）关键字段：
  - `query`（必填）：搜索词
  - `numResults`：返回条数，如 `5`
  - `type`（可选）：`keyword` / `neural` / `auto`
  - `contents`（可选）：控制返回字段，如 `{"text": true}` 让结果带 `text`
- 响应（JSON）：`results` 数组，每项含 `title`、`url`、`text` 等字段；结果**已由 Exa 服务端按相关度排好序**，直接取前 N 条即可（实测响应不含 `score` 字段，勿依赖它排序）
- 免费额度：key 即 `exa.env.json` 的 `EXA_API_KEY`

**示例 A：Bash curl（从 `exa.env.json` 读取 key，绝不硬编码）**

```
# 自动探测多个候选位置读取 key（不硬编码明文）
for p in exa.env.json ../exa.env.json ../../exa.env.json \
         ~/.agent/skills/pdca-skill/exa.env.json \
         ~/.workbuddy/skills/pdca-skill/exa.env.json; do
  if [ -f "$p" ]; then KEY=$(python -c "import json;print(json.load(open('$p'))['EXA_API_KEY'])"); break; fi
done
[ -z "$KEY" ] && KEY="$EXA_API_KEY"   # 退回环境变量
[ -z "$KEY" ] && { echo "未找到 Exa key（exa.env.json 或 EXA_API_KEY 环境变量）"; exit 1; }
curl -s -X POST https://api.exa.ai/search \
  -H "x-api-key: $KEY" \
  -H "content-type: application/json" \
  -d '{"query":"best claude agent skill for X","numResults":5,"type":"auto"}'
```

> key 已自动探测多个候选位置（当前目录 / 仓库根 `../` `../../` / `~/.agent/skills/pdca-skill/` / `~/.workbuddy/skills/pdca-skill/`），都找不到再退回 `EXA_API_KEY` 环境变量。

**示例 B：Python `urllib`（标准库，环境必有，无需装 `requests`）**

```python
import json
import os
import urllib.request

def load_exa_key():
    """自动探测多个候选位置读取 key（绝不硬编码明文）。"""
    candidates = [
        "exa.env.json",                      # 当前工作目录
        "../exa.env.json",                   # 仓库根（脚本在子目录时）
        "../../exa.env.json",
        os.path.expanduser("~/.agent/skills/pdca-skill/exa.env.json"),
        os.path.expanduser("~/.workbuddy/skills/pdca-skill/exa.env.json"),
    ]
    for p in candidates:
        try:
            with open(os.path.expanduser(p)) as f:
                return json.load(f)["EXA_API_KEY"]
        except Exception:
            continue
    return os.environ.get("EXA_API_KEY")     # 最终退回环境变量

KEY = load_exa_key()
if not KEY:
    raise SystemExit("未找到 Exa key：请确认 exa.env.json 位置，或设置 EXA_API_KEY 环境变量")

body = json.dumps({
    "query": "best claude agent skill for X",
    "numResults": 5,
    "type": "auto",
}).encode()

req = urllib.request.Request(
    "https://api.exa.ai/search",
    data=body,
    headers={"x-api-key": KEY, "content-type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    data = json.load(resp)

for r in data.get("results", []):
    print(r.get("title"), "|", r.get("url"))  # 结果已按相关度排序，直接取前 N 条
```

**搜索词**：联网搜索不再限定 `site:skills.sh`，改为全网找 skill / agent / 工具 / mcp，例如 `best claude agent skill for X`、`mcp server for X`、`claude agent skill for pull request review`。

> ⚠️ **安全红线**：真实 key 只能存在于 `exa.env.json`，文档里只允许出现读取命令/变量，严禁任何明文 key。

### ② (可选上层) Exa MCP（若客户端已配）

若你的客户端**已经配置**了 Exa MCP（OAuth 免 key，无需 API Key），可改用 MCP 工具 `web_search_exa` / `web_fetch_exa`，省去读 key 步骤。这是**可选的上层**，不是必需路径——没配 MCP 时用 ① REST 直连即可。

**MCP 配置（OAuth 免 key，最简）**：

```json
{
  "mcpServers": {
    "exa": {
      "url": "https://mcp.exa.ai/mcp"
    }
  }
}
```

（可选 API Key：在配置里加 `headers: { "x-api-key": "YOUR_EXA_API_KEY" }`，用于突破免费额度限速 / 生产使用；`YOUR_EXA_API_KEY` 换成你自己申请的 key。）

MCP 暴露工具：

- `web_search_exa`：联网搜索（全网找 skill / agent / 工具 / mcp server）
- `web_fetch_exa`：把给定 URL 读成干净 markdown（用于读取候选 agent 的详情页）

> 还可用 `tools=` 查询参数启用额外工具，例如 `https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa` 可开启 `web_search_advanced_exa`（高级搜索）；`?tools=agent_tools` 可启用 agent 工具集。

> 说明：MCP 走 OAuth / 可选 key，与 ① 的 REST API（`x-api-key` 头）是两套独立鉴权体系；二者选其一即可，REST 直连更轻、更无需 UI 配置。

### ③ (兜底) WebSearch + WebFetch（REST 与 MCP 都不可用时）

当 REST 直连失败（无 `exa.env.json` / key 失效 / 网络不通）**且** MCP 也不可用时：

- 降级回 AI 内置的 `WebSearch` + `WebFetch`（沿用原有的零依赖兜底逻辑，仍跨平台可用）
- 搜索词用全网通用词（见 Step 1），不再限定 `site:skills.sh`

---

## 核心原则【硬性】

**搜索优先级：① 优先用 Exa REST API 直连（`POST https://api.exa.ai/search`，读 `exa.env.json` 的 key，绕开 MCP/OAuth）；② 若客户端已配 Exa MCP，可改用 `web_search_exa`/`web_fetch_exa` 作为可选上层；③ REST 与 MCP 都不可用时降级 WebSearch/WebFetch（AI 内置工具，零系统依赖）；安装用 npx（可选，跑不了就降级）。**

理由：Exa REST 直连最轻便（零 UI 配置、无需 OAuth 登录），命中率远高于只搜单一站点，覆盖 skill / agent / 工具 / mcp 等更广生态；MCP 作为可选上层给已配好的客户端用；AI 内置工具零系统依赖，跨平台可用；npx 在某些环境（如 Windows PowerShell 执行策略禁用）跑不了，不能让搜索功能因此瘫痪。

---

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill / agent
- Says "find a skill for X" or "is there a skill for X"
- Asks "can you do X" where X is a specialized capability
- Expresses interest in extending agent capabilities
- Wants to search for tools, templates, or workflows
- Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)
- Asks for a recommended MCP server or external tool

## What is the Skills / Agents Ecosystem?

Skills and agents are reusable capabilities for AI agents. The open agent skills ecosystem at [skills.sh](https://www.skills.sh/) hosts modular packages that extend agent capabilities with specialized knowledge, workflows, and tools. Additionally, the broader ecosystem includes **MCP servers** and community-built **agents** that can be discovered via web search.

**Browse skills at:** https://www.skills.sh/

**Installation (when npx available):**

- `npx skills add <owner/repo@skill>` - Install a skill from GitHub or other sources
- `npx skills check` - Check for skill updates
- `npx skills update` - Update all installed skills

> ⚠️ 上述 npx 命令需要 Node.js 环境。若环境不可用（如 Windows PowerShell 执行策略禁用），见下方 Step 6 降级方案。

## How to Help Users Find Agents / Skills

### Step 1: Understand What They Need

When a user asks for help with something, identify:

1. The domain (e.g., React, testing, design, deployment)
2. The specific task (e.g., writing tests, creating animations, reviewing PRs)
3. Whether this is a common enough task that a skill / agent likely exists

### Step 2: 优先 Exa REST API 直连全网搜索

**首选用 Exa REST API 直连做全网搜索**（见上方 ① 的 curl / urllib 示例，从 `exa.env.json` 读取 key 调用 `POST https://api.exa.ai/search`），搜索词不再限定 `site:skills.sh`，用更通用的全网词：

```
best claude agent skill for react performance
claude skill for pull request review
mcp server for kubernetes deployment
agent skill for generating changelog
```

用 `web_fetch_exa`（若已配 MCP）或直接 `WebFetch <候选详情页URL>` 读取候选 agent 的详情页（拿到干净 markdown）。

> 若 REST 直连不可用（无 `exa.env.json` / key 失效 / 网络不通）→ 见 Step 2b 改用已配好的 Exa MCP；若 MCP 也没配 → 见 Step 3 兜底。

### Step 2b: 可选上层——Exa MCP（web_search_exa，仅当客户端已配）

**若客户端已配置 Exa MCP**，可改用 `web_search_exa` 工具做全网搜索（OAuth 免 key，无需读 `exa.env.json`）：

```
web_search_exa "best claude agent skill for react performance"
web_search_exa "claude skill for pull request review"
web_search_exa "mcp server for kubernetes deployment"
web_search_exa "agent skill for generating changelog"
```

也可以用 `web_fetch_exa <候选详情页URL>` 直接读取候选 agent 的详情页（拿到干净 markdown）。

> 若 MCP 也未配置 / 不可用 → 见 Step 3 兜底路径。

### Step 3: 排行榜 + WebSearch 兜底（降级路径，REST 与 MCP 都不可用时）

**若 Exa REST 直连不可用，且 Exa MCP 也不可用**，用 AI 内置 WebFetch/WebSearch 兜底（沿用原有的零依赖兜底逻辑）：

1. 用 WebFetch 访问 `https://www.skills.sh/` 拿 top 技能列表
2. 用 WebSearch 搜特定领域（建议全网通用词，必要时可加 `site:skills.sh <领域关键词>` 精确限定）
3. 也可以用 WebFetch 直接访问特定技能页面：

```
WebFetch https://www.skills.sh/<owner>/<repo>/<skill-name>
```

例如：

- 用户问"怎么做 React 性能优化？" → `WebSearch "react performance agent skill"`
- 用户问"能帮我做 PR review 吗？" → `WebSearch "pull request review skill"`
- 用户问"我需要生成 changelog" → `WebSearch "changelog generator skill"`

### Step 4: Verify Quality Before Recommending

**Do not recommend a skill based solely on search results.** Always verify:

1. **Install count** — Prefer skills with 1K+ installs. Be cautious with anything under 100.
2. **Source reputation** — Official sources (`vercel-labs`, `anthropics`, `microsoft`) are more trustworthy than unknown authors.
3. **GitHub stars** — Check the source repository. A skill from a repo with <100 stars should be treated with skepticism.

### Step 5: Present Options to the User

When you find relevant skills / agents, present them to the user with:

1. The skill / agent name and what it does
2. The install count and source
3. The install command they can run
4. A link to learn more at skills.sh

Example response:

```
我找到了一个可能适合的 skill！

名称：react-best-practices
用途：React 和 Next.js 性能优化指南（来自 Vercel 工程团队）
安装量：185K
来源：vercel-labs/agent-skills

安装命令：npx skills add vercel-labs/agent-skills@react-best-practices
详情：https://skills.sh/vercel-labs/agent-skills/react-best-practices
```

### Step 6: 安装（降级处理）【硬性】

安装环节分两档处理：

**情况A：npx 可用（有 Node.js 环境）**

自动安装：

```bash
npx skills add <owner/repo@skill> -g -y
```

`-g` 全局安装，`-y` 跳过确认。

**情况B：npx 不可用（无 Node.js / PowerShell 执行策略禁用 / 其他原因）**

降级处理——**呈现安装命令让用户自己跑**：

```
检测到当前环境无法自动安装 skill（原因：npx 不可用）。

请在终端手动执行以下命令安装：
  npx skills add vercel-labs/agent-skills@react-best-practices

或者访问以下链接查看手动安装方式：
  https://skills.sh/vercel-labs/agent-skills/react-best-practices

安装完成后告诉我，我来验证是否就位。
```

**禁止**【硬性】：

- ❌ npx 跑不了就放弃整个 agent-find 流程（搜索功能不依赖 npx，仍可用）
- ❌ 静默跳过安装（必须告知用户安装命令）
- ❌ 强制用户改系统设置（如改 PowerShell 执行策略）来装 skill

### Step 7: Security Scan Before Installation

**CRITICAL:** Before installing any skill, perform a security scan using [references/plan/route/skill_security.md](skill_security.md) rules.

1. Run SkillAudit API scan
2. Check risk level
3. Only install if risk level is `clean` or `low`
4. For `moderate` or higher, refuse installation

> 注：安全扫描用 WebFetch 调用 SkillAudit API，不依赖 npx。

## Common Skill / Agent Categories

When searching, consider these common categories:

| Category | Example Queries |
| --------------- | ---------------------------------------- |
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd, mcp server |
| Documentation | docs, readme, changelog, api-docs |
| Code Quality | review, lint, refactor, best-practices |
| Design | ui, ux, design-system, accessibility |
| Productivity | workflow, automation, git, agent |
| MCP / Tools | mcp server, claude agent, external tool |

## Tips for Effective Searches

1. **首选 Exa REST API 直连全网搜**：用 ① 的 curl / urllib 调用 `POST https://api.exa.ai/search`，`best claude agent skill for react` 比 `react skill` 更精准，覆盖更广
2. **已配 MCP 时可用 `web_search_exa`**：OAuth 免 key，省去读 key 步骤（可选上层）
3. **REST 与 MCP 都不可用才退化 WebSearch**：可加 `site:skills.sh` 精确限定，但优先全网通用词
4. **Try alternative terms**: If "deploy" doesn't work, try "deployment" or "ci-cd"
5. **Check popular sources**: Many skills come from `vercel-labs/agent-skills` or `ComposioHQ/awesome-claude-skills`

## When No Skills Are Found

If no relevant skills / agents exist:

1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using your general capabilities
3. Suggest the user could create their own skill with `npx skills init`（若 npx 可用）

Example:

```
我在 skills.sh 上没找到匹配 "xyz" 的 skill。
不过我可以用通用能力直接帮你搞定这件事，要继续吗？

如果你经常做这类事，可以考虑自建 skill：
npx skills init my-xyz-skill
（需要 Node.js 环境）
```


## find_similar.py 统一搜索脚本（/plan 步骤 4a.3 执行工具）

> **版本**：v1.0.0 | **更新**：2026-07-25
>
> 本脚本是 /plan 步骤 4a.3 的执行工具，用于自动搜索 GitHub + Gitee + 国内 skill 平台，找类似 skill 或项目。GitHub + Gitee 用 API 调用（稳定，支持 token 避免限流），国内大厂平台（Coze/腾讯 SkillHub/skills.sh）API 不公开，脚本只输出搜索链接，由主 agent 后续用 WebFetch 工具抓取页面内容。

### 6 个搜索源清单

| # | 名称 | 方法 | 语言 | token 环境变量 | 说明 |
|---|------|------|------|---------------|------|
| 1 | Gitee 仓库（shishishe/skill 等） | API | zh | GITEE_TOKEN | 国内 skill 仓库，243 个技能 |
| 2 | GitHub | API | en | GITHUB_TOKEN | 通用代码仓库，海外源 |
| 3 | Coze 技能商店 | link | zh | 无 | 字节扣子生态，365+ skill，API 不公开 |
| 4 | 腾讯 SkillHub | link | zh | 无 | 腾讯汉化社区，13000+ skill，API 不公开 |
| 5 | skills.sh | link | en | 无 | Claude 官方生态 |
| 6 | 国内大厂平台 link 源 | link | zh | 无 | 脚本输出搜索链接，agent 用 WebFetch 抓 |

### 用法

```bash
# 基本用法（自动从任务描述提取关键词）
python scripts/find_similar.py scan --task "PDF 文档解析 skill"

# 指定关键词（逗号分隔）
python scripts/find_similar.py scan --task "认证模块" --keywords "JWT,认证,token"

# 简单任务用高阈值快速过滤
python scripts/find_similar.py scan --task "改个参数" --min-stars 100

# 自定义输出路径
python scripts/find_similar.py scan --task "test" --output docs_rj/spec_rj/custom_reuse.md

# 列出所有搜索源
python scripts/find_similar.py list
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| --task | 任务描述（必填） | - |
| --keywords | 搜索关键词（逗号分隔） | 从任务描述提取 |
| --output | 输出文件路径 | docs_rj/spec_rj/{task}_reuse_YYYYMMDD_HHMM.md |
| --min-stars | 最小 star 数 | 5 |
| --max-age-days | 最大更新天数 | 365 |

### token 配置（避免限流）

**GitHub token**：
- 无认证：限流 60 次/小时
- 有认证：限流 5000 次/小时
- 配置：设置环境变量 `GITHUB_TOKEN`（在 GitHub Settings → Developer settings → Personal access tokens 生成）

**Gitee token**：
- 配置：设置环境变量 `GITEE_TOKEN`（在 Gitee 个人设置 → 私人令牌 生成）

**Exa key**（可选，用于 4a.2 Skill 生态搜索）：
- 配置：设置环境变量 `EXA_API_KEY` 或创建 `exa.env.json`

### 输出格式

脚本生成 markdown 报告，包含：
1. **API 源搜索结果**（GitHub + Gitee）：表格列出名称/Stars/最后更新/语言/描述
2. **国内大厂平台**（link 源）：搜索链接 + 操作说明（agent 用 WebFetch 抓取）
3. **后续建议**：优先评估高 star + 最近更新，走 skill_management.md 安装流程

### 质量过滤 + 去重

- **质量过滤**：star ≥ min_stars + 最后更新 ≤ max_age_days
- **去重**：按 URL 去重
- **评分排序**：star 数 × 中文源加权（Gitee × 1.2），降序排序


## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-08 | 初版，基于 某开源仓库 CLI（npx skills find/add） |

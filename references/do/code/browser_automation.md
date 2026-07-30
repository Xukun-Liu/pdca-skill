<!-- PDCA标签：D.code -->
<!-- 子标签场景：浏览器自动化 -->
<!-- 关键词清单：浏览器操控/浏览器自动化/Agent浏览/网页操作/自动填表/AI网页抓取/让AI操作浏览器/RPA -->
<!-- 引用范围：main + browser_agent -->

# 浏览器操控（让 Agent 自动操作浏览器）
> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-11
> 定位：当任务需要"让 AI Agent 自动操作真实浏览器"（导航 / 填表 / 抓取 / 点击 / 登录 / 反爬绕过）时，先读本文件做选型，再落地。本文件只陈列成熟方案与取舍，**不替使用者写死技术选型**。

> 📖 **什么时候读这个文件**：
> - 用户要让 AI 自动操作网页：浏览、填表、抓取、点击、登录
> - 提到"浏览器自动化 / Agent 浏览 / 网页操作 / RPA / 让 AI 操作浏览器 / 反爬绕过"
> - 需要在 Playwright / Browser Use / Stagehand / Skyvern / MCP 方案之间选型

🔴 **不要在这时候读**：
> - 纯后端 API 调用、无需真实浏览器即可完成的数据采集
> - 静态页传统爬虫（requests / BeautifulSoup）——这类走通用参考，不在此列

---

## 一、触发信号（满足任一即进入本流程）

1. 任务目标包含"打开网站 / 填写表单 / 点击按钮 / 自动登录 / 抓取网页内容"
2. 用户明确"用 AI 操作浏览器""做个浏览器机器人""自动逛网页"
3. 现有接口 / API 拿不到数据，必须走真实浏览器渲染
4. 需要绕过前端反爬、处理动态 JS 渲染页面

---

## 二、选型对比矩阵（客观，不写死）

| 方案 | 形态 | 是否依赖 MCP | 成熟度 / 社区 | 核心特点 | 适用场景 | 注意 |
|------|------|------------|--------------|----------|----------|------|
| **Browser Use** | 纯 Python SDK（库） | 否 | 97k+ ★，类别最大 | DOM 蒸馏降 token、模型无关（OpenAI/Anthropic/Gemini/Ollama）、原生 MCP 可选 | 开发者自建 Agent 首选 | 标准云版会用输入训练模型，敏感数据来自托管 |
| **Playwright**（微软） | 代码驱动 / 测试框架 | 否（原生 MCP 可选） | Apache-2.0，免费 | 100% 确定性、支持 Chromium/Firefox/WebKit、可当 Agent 底层 | E2E 测试、大规模爬虫、确定型自动化 | UI 一变脚本易失效，需自己写决策逻辑 |
| **Stagehand** | TypeScript SDK | 否（MCP 可选） | Browserbase 团队 | act / extract / observe 三段式，AI + 传统选择器混合 | 工程师要可控性、混合确定性 | 偏前端栈 |
| **Skyvern** | 开源 + 云 | 否（MCP 可选） | 开源 + 企业级 | 无选择器、视觉推理、Route Memorization | 运维团队、动态/反爬站点、无代码仪表盘 | 复杂多步任务云信用消耗不可预测 |
| **Playwright MCP** | MCP Server | **是（必须装 MCP）** | 微软官方 `@playwright/mcp` | 让 Cursor/Claude 等 MCP 客户端一句话直控浏览器 | 已用 MCP 生态、想零 glue code | 需额外部署 MCP 运行时 |
| **Browser Use MCP** | MCP Server | **是（必须装 MCP）** | 官方提供 | 把 Browser Use 能力暴露为 MCP 工具 | 同上，偏好 Browser Use 语义 | 需装 MCP |
| **Skyvern MCP** | MCP Server | **是（必须装 MCP）** | 官方提供 | Claude/Cursor 触发 Skyvern 任务 | 已用 Skyvern 且要走 MCP | 需装 MCP |

> 说明：**是否装 MCP 由使用者按自身环境决定**，本框架不强制。下方主力示例给"纯 SDK"形态（零额外依赖、最易本地跑）；若你的环境已具备 MCP 运行时，上表 MCP 类方案同样可用，取舍见末列。

---

## 三、主力落地：Browser Use 纯 SDK 形态（非 MCP，零额外依赖）

### Step 1：安装
```bash
pip install browser-use langchain-openai
playwright install chromium
```

### Step 2：最小可运行脚本（`agent_browser.py`）
```python
import asyncio
from browser_use import Agent
from langchain_openai import ChatOpenAI

async def main():
    # BYOK：用你自己的模型（OpenAI / Anthropic / Gemini / Ollama 皆可，见下方切换）
    llm = ChatOpenAI(model="gpt-4o", api_key="YOUR_OPENAI_KEY")

    agent = Agent(
        task="打开 https://www.google.com ，在搜索框输入 'browser use' 并回车，返回第一条结果的标题",
        llm=llm,
    )
    result = await agent.run()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3：运行验证
```bash
OPENAI_API_KEY=sk-xxx python agent_browser.py
```
预期：终端打印第一条搜索结果的标题，无报错即连通成功。

### 切换模型（BYOK，均无需 MCP）
- **Anthropic**：`pip install langchain-anthropic`，`from langchain_anthropic import ChatAnthropic; llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key="...")`
- **Gemini**：`pip install langchain-google-genai`，`from langchain_google_genai import ChatGoogleGenerativeAI; llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key="...")`
- **本地 Ollama**：`from langchain_ollama import ChatOllama; llm = ChatOllama(model="qwen2.5")`

---

## 四、备选与边界

- **Playwright（纯代码）**：当任务高度确定、需 100% 可复现时优先（如回归测试、固定流程爬虫）。AI Agent 框架（Browser Use 等）可架在 Playwright 之上。
- **Stagehand**：TypeScript 栈、想要 act/extract/observe 精细控制时。
- **Skyvern**：不想写选择器、面对频繁改版的动态站点、或需要带仪表盘的托管运行时时。
- **MCP 类方案（Playwright MCP / Browser Use MCP / Skyvern MCP）**：适用于**已经部署 MCP 运行时**的环境（Cursor / Claude Desktop / 任意 MCP 客户端）。它们能省去 glue code，但前提是接受装 MCP——是否采用由使用者决定，本文件不强制。

---

## 五、安全边界

- **凭据与敏感数据**：不要把账号密码 / API Key 硬编码进脚本；优先环境变量或密钥管理器。敏感业务选自托管 / 私有部署。
- **反爬与合规**：自动访问网站需遵守目标站 robots.txt 与适用法规；高频请求做好限速与 UA 伪装，避免触发封禁或法律风险。
- **费用不可预测**：LLM 驱动的方案按 token / 步数计费，复杂多步任务消耗难以预估；重复任务优先用缓存（Skyvern 的 Route Memorization、Browser Use 的会话复用）降本。
- **人工监督**：WebVoyager 基准成功率 69%–97%（取决于任务类型），复杂 / 新颖流程仍需把"人工确认"内嵌进 pipeline（尤其是登录、支付等关键动作）。

---

## 六、引用来源

- toolradar.com — Best Computer-Use & Browser AI Agents 2026 / Best AI Browser Agents in 2026
- dev.to — Top AI Agent Frameworks for Web Automation in 2026
- 掘金 — 2026 年最新 AI 浏览器工具全面对比
- capsolver.com — Best 7 AI Agents Tools for Web Automation in 2026
（检索日：2026-07-11）

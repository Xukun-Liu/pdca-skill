<!-- PDCA标签：P.design -->
<!-- 子标签场景：项目结构 -->
<!-- 关键词清单：文件放哪/目录怎么组织/放哪个目录/结构怎么弄/项目结构/代码放哪/模块怎么分/文件夹怎么建/准备设计项目结构/模块划分/架构设计/分层设计/代码组织 -->
<!-- 引用范围：main + bootstrap_agent -->

# 项目文件结构与版本管理
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-10

### 📁 工作区目录结构导图

```
{工作目录}/
│
├─ riji-skill/              ← Skill本身
│   ├─ SKILL.md                ← 核心规则（每次自动加载）
│   ├─ references/             ← 参考手册（按需读）
│   │   ├─ debugging.md        ← 出错时读
│   │   ├─ red_flags.md        ← 不确定该不该继续时读
│   │   ├─ code_rules.md       ← 写代码前读
│   │   ├─ document_specs.md   ← 写文档前读
│   │   ├─ working_memory_rules.md ← memory读写规则
│   │   ├─ communication_rules.md  ← 沟通规则
│   │   ├─ project_structure.md    ← 本文件
│   │   ├─ security.md        ← 安全边界
│   │   ├─ skill_management.md ← 需要找/装新 Skill 时读
│   │   ├─ design_patterns.md  ← 需要设计模式时读
│   │   ├─ git_workflow.md     ← 需要Git操作时读
│   │   ├─ usage_examples.md  ← 使用示例
│   │   ├─ bootstrap.md        ← 首次使用/文件缺失时读
│   │   ├─ agent_find.md      ← 需要找/装新 agent/能力 时读
│   │   ├─ skill_security.md   ← 安装第三方 Skill 前读
│   │   ├─ summary_view.md     ← SUMMARY_RJ.md 规范
│   │   ├─ sync-matrix.md      ← 版本号一致性检查
│   │   └─ hand-drawn-report.md ← 生成手绘呈现时读
│   └─ assets/                 ← 模板文件（复制用）
│       ├─ spec_main_template.md  ← 项目级总 spec 模板（通用）
│       ├─ spec_template.md
│       ├─ task_template.md
│       ├─ memory_template.md
│       ├─ handoff_template.md
│       ├─ daily_log_template.md
│       ├─ memory_bootstrap_template.md
│       └─ summary_template.md
│
└─ docs_rj/                      ← 主文档目录（扁平5类，已标记 .primary_docs_rj）
    ├─ spec_main_rj.md           ← 项目总 spec（source of truth，2026-07-18 新增，任务 spec 从它派生）
    ├─ SUMMARY_RJ.md             ← 纯索引（63文件链接）
    ├─ spec_rj/                  ← 需求规格分类文件夹
    │   └─ {任务名}_spec_YYYYMMDD_HHMM.md
    ├─ task_rj/                  ← 任务清单分类文件夹
    │   └─ {任务名}_task_YYYYMMDD_HHMM.md
    ├─ handoff_rj/               ← 交接文档分类文件夹
    │   └─ {任务名}_handoff_YYYYMMDD_HHMM.md
    ├─ memory_rj/                ← 项目记忆分类文件夹（跨对话持久化，建在主 docs 内）
    │   └─ {任务名}_memory_YYYYMMDD_HHMM.md  ← 任务级记忆（写入即落盘 + 自动 upsert 全局 memory_main）
    └─ archive_rj/               ← 归档分类文件夹（按任务子文件夹聚合，D1 方案）
        ├─ {task}_YYYYMMDD_HHMM/  ← 任务袋（任务启动时间戳从原文件名提取，不依赖 mtime）
        │   ├─ spec.md
        │   ├─ task.md
        │   ├─ handoff.md
        │   └─ memory.md
        └─ {task}_{type}_YYYYMMDD_HHMM_archived.md  ← legacy 扁平文件（保留原位，不迁移）
```

> 📖 **什么时候读这个文件**：
> - 不确定文件放哪/目录怎么组织时
> - 准备创建新目录/新文件时
> - 需要设计项目结构/模块划分时
> 🔴 **不要在这时候读**：
> - 已有明确目录结构且只改现有文件时

---

## 项目文件框架

分为两层：工作区（正在干的）和发布区（干完的版本快照）。

```
{工作目录}/
├── AGENTS.md                          <- 全局协作规则
│
│   ┌─ 工作区（当前开发） ─────────────────────────────────┐
│   │
├── src/                               <- 当前版本源码
│   └── {任务名}/
│       ├── main.py
│       └── ...
│
├── outputs_rj/                           <- 当前版本产物（用户看这）
│   └── {任务名}/
│       ├── index.html
│       └── ...
│
├── docs_rj/                              <- 过程文档（持续更新，扁平4类）
│   ├── spec_rj/
│   ├── task_rj/
│   ├── handoff_rj/
│   └── archive_rj/
│   │
│   └──────────────────────────────────────────────────┘
│
│   ┌─ memory（运行时记忆：热/全局聚合/项目三级体系） ──────────┐
│   │
├── docs_rj/memory_rj/
│   ├── {任务名}_memory_YYYYMMDD_HHMM.md   <- 项目级记忆（写入即落盘）
│   │   （全局聚合记忆在 skill 包 memory/memory_main.md，按项目分段）
│   │
│   └──────────────────────────────────────────────────┘
│
│   ┌─ riji-skill（热记忆：协作框架本身） ─────────────────┐
│   │
├── riji-skill/
│   ├── SKILL.md                       <- 主规则文件（热记忆，每次对话加载）
│   ├── assets/                        <- 模板文件
│   │   ├── memory_template.md
│   │   ├── spec_template.md
│   │   ├── task_template.md
│   │   ├── handoff_template.md
│   │   ├── daily_log_template.md
│   │   ├── memory_bootstrap_template.md
│   │   └── summary_template.md
│   └── references/                    <- 分域详细规则（热记忆）
│       ├── communication_rules.md
│       ├── code_rules.md
│       ├── document_specs.md
│       ├── project_structure.md
│       ├── security.md
│       ├── red_flags.md
│       ├── debugging.md
│       ├── working_memory_rules.md
│       ├── skill_management.md
│       ├── design_patterns.md
│       ├── git_workflow.md
│       ├── usage_examples.md
│       ├── bootstrap.md
│       ├── agent_find.md
│       ├── skill_security.md
│       ├── summary_view.md
│       ├── sync-matrix.md
│       └── hand-drawn-report.md
│   │
│   └──────────────────────────────────────────────────┘
│
│   ┌─ 发布区（历史版本快照） ─────────────────────────────┐
│   │
└── releases/                          <- 所有完成版本
    └── {任务名}/
        ├── v1.0/
        │   ├── src/                   <- v1.0 时的源码快照
        │   ├── outputs_rj/               <- v1.0 时的产物快照
        │   └── docs_rj/                  <- v1.0 时的三件套快照
        ├── v1.1/
        │   └── ...
        └── v2.0/
            └── ...
    │
    └──────────────────────────────────────────────────┘
```

---

## 标准项目结构（Python/Flask）

```
project-root/
├── src/                    # 源代码
│   ├── __init__.py         # 包初始化
│   ├── main.py             # 主入口
│   ├── core/               # 核心逻辑（业务规则、领域模型）
│   │   ├── __init__.py
│   │   ├── entities.py     # 领域实体（User、Product、Order等）
│   │   ├── services.py     # 业务服务（UserService、PaymentService等）
│   │   └── repositories.py # 数据访问接口（抽象层）
│   ├── api/                # API层（RESTful接口）
│   │   ├── __init__.py
│   │   ├── routes.py       # 路由定义（@app.route）
│   │   ├── schemas.py      # 请求/响应Schema（marshmallow）
│   │   └── controllers.py  # 控制器逻辑（参数解析、调用Service、返回响应）
│   ├── infrastructure/     # 基础设施层（具体实现）
│   │   ├── __init__.py
│   │   ├── database.py     # 数据库连接（SQLAlchemy/SQLite）
│   │   ├── api_clients.py  # 外部API客户端（requests）
│   │   └── cache.py        # 缓存实现（Redis/内存缓存）
│   ├── utils/              # 工具函数
│   │   ├── __init__.py
│   │   ├── logger.py       # 日志配置
│   │   └── helpers.py      # 通用辅助函数（日期格式化、加密等）
│   └── config/             # 配置
│       ├── __init__.py
│       ├── settings.py     # 配置加载（环境变量→配置对象）
│       └── env.py          # 环境变量定义
├── tests/                  # 测试代码
│   ├── __init__.py
│   ├── unit/               # 单元测试：单个函数/类
│   ├── integration/        # 集成测试：模块间协作
│   ├── e2e/                # 端到端测试：完整用户流程
│   └── fixtures/           # 测试数据
├── docs/                   # 文档
│   ├── api/                # API文档（OpenAPI/Swagger）
│   ├── design/             # 设计文档（架构图、流程图）
│   └── user/               # 用户文档（使用指南）
├── scripts/                # 工具脚本
│   ├── setup.py            # 环境设置脚本
│   └── deploy.py           # 部署脚本
├── assets/                 # 静态资源（图片、模板、配置文件）
├── .env.example            # 环境变量模板
├── .gitignore              # Git忽略规则
├── requirements.txt        # Python依赖
├── pyproject.toml          # 项目配置（pytest、flake8等）
└── README.md               # 项目说明
```

---

## 模块划分规则

### 1. 按领域驱动设计划分

| 层级 | 职责 | 示例 |
|------|------|------|
| Domain（领域层） | 业务规则、领域模型 | User、Order、Payment |
| Application（应用层） | 用例编排、业务流程 | UserService、OrderService |
| Infrastructure（基础设施层） | 技术实现、外部依赖 | Database、API Client、Cache |
| Interface（接口层） | 用户交互、API暴露 | Controllers、Routes |

### 2. 依赖方向

```
Interface → Application → Domain → Infrastructure
```

- 上层依赖下层，不反向
- Domain 层不依赖任何其他层
- Infrastructure 层实现 Domain 层定义的接口

### 3. 循环依赖处理

- 通过接口层解耦：定义抽象接口，实现放在不同模块
- 使用延迟导入：在函数内部导入，避免模块加载时的循环
- 重构设计：合并或拆分模块，重新划分职责

---

## 配置管理规范

### 1. 环境变量分层

| 环境 | 文件 | 用途 |
|------|------|------|
| Development | `.env` | 本地开发配置 |
| Test | `.env.test` | 测试环境配置 |
| Production | 环境变量（不提交） | 生产环境配置 |

### 2. 配置文件优先级

1. 命令行参数
2. 环境变量
3. `.env` 文件
4. 默认配置

### 3. 敏感配置处理

- 敏感配置（数据库密码、API Key）放在环境变量中
- `.env` 文件加入 `.gitignore`
- 提供 `.env.example` 作为模板

### 4. 配置验证

```python
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    API_KEY: str = Field(..., env="API_KEY")
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

---

## 项目初始化流程

### 步骤1：创建目录结构

```bash
mkdir -p src/core src/api src/infrastructure src/utils src/config
mkdir -p tests/unit tests/integration tests/e2e tests/fixtures
mkdir -p docs/api docs/design docs/user scripts assets
```

### 步骤2：创建配置文件

```bash
touch .env.example .gitignore requirements.txt README.md
```

### 步骤3：初始化Git

```bash
git init
git add .
git commit -m "Initial commit"
```

### 步骤4：设置虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 步骤5：安装依赖

```bash
pip install flask marshmallow pytest pytest-mock python-dotenv pydantic
```

### 步骤6：初始化测试框架

```bash
pytest --init
```

### 步骤7：创建核心文件

```bash
# src/main.py
# src/__init__.py
# src/config/settings.py
# src/config/env.py
# src/core/entities.py
# src/api/routes.py
# tests/unit/test_example.py
```

---

## 规则刚性分类：Rigid vs Flexible【硬性】

所有规则必须标注刚性级别，防止要么死板要么随意：

| 分类 | 标记 | 含义 | 例子 | 跳过时怎么办 |
|------|------|------|------|-------------|
| **硬性规则** | 【硬性】（Rigid） | 必须严格遵守，不能"灵活处理" | Memory First、HARD-GATE、No Placeholders、安全禁止项、Chesterton's Fence | 需要你明确知晓后果并确认跳过（如"跳过memory读写会导致下次对话丢失上下文，确定吗？"） |
| **弹性规则** | 【弹性】（Flexible） | 原则要遵守，但具体方式可灵活调整 | 类比方式、分块大小、沟通语气细节、方案数量（2个还是3个）、分节数量 | 你说"这个不用那么正式"就可以灵活调整，不需要额外警告 |

**你可以随时调整刚性**：
- 把弹性规则变硬："以后每次都要先给我看3个方案"
- 把硬性规则临时变弹性："这次跳过设计直接改"
- 但必须明确说出来，不能默认

---

## 两个区的职责

| 区 | 放什么 | 谁更新 | 什么时候用 |
|----|--------|--------|------------|
| 工作区（src/outputs_rj/docs） | 当前正在开发/修改的版本 | AI 持续更新 | 日常干活 |
| 发布区（releases/） | 已完成版本的全部文件快照 | 版本确认完成后手动归档 | 回头看、对比、回滚 |

---

## 版本流转规则

- **日常迭代**（v1.0 -> v1.1）：工作区 src/outputs 直接改，docs_rj/ 三件套更新版本号
- **大版发布**（v1.x -> v2.0）：将当前工作区完整复制到 `releases/{任务名}/v1.0/`，然后继续在工作区开发 v2.0
- **docs 三件套**：版本号在文件内追踪，每次修订同步更新版本号
- **同名文件覆盖**：工作区 outputs_rj/ 同一文件每次生成覆盖旧版本 -> 旧版本在 releases/
- **Skill版本**：SKILL.md自身版本号在文件头部和版本历史表追踪

---

## 文件命名规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 任务文件夹 | 小写 + 下划线 | `billing_tool`、`report_q1` |
| 入口文件 | 描述性命名 | `index.html`、`main.py` |
| 版本文件夹 | v{主版本}.{次版本} | `v1.0`、`v2.1` |

禁止：中文文件名、空格、特殊符号（`-` 和 `_` 除外）

---

## 三件套对照表

| 文档 | 作用 | 创建时机 | 更新时机 | 完成标准 |
|------|------|----------|----------|----------|
| {项目根}/docs_rj/memory_rj/{任务名}_memory_YYYYMMDD_HHMM.md | 记录双方说了什么、做了什么（极简） | 任务启动时 | 每个阶段结束 | 含决策点 + 关键变更，写入即落盘 + 自动 upsert 全局 memory_main，30秒能接手 |
| spec.md | 需求规格，专业 PM 水准 | 阶段1（需求对齐）产出 | 需求变更时 | 看完能写代码不用猜，含2-3方案对比，通过Self-Review |
| task.md | 任务拆解清单 + 验收标准 + 验证步骤 | 阶段1结束后 | 每步完成时 | 每条有验证步骤+预期结果，No Placeholders，Verification通过才打勾 |

---

## Definition of Done（项目级底线）【硬性】

以下条件每次任务完成时必须全部满足，不因任务类型不同而跳过。这是屏障线，不是建议。

1. **三件套已同步**：spec / task / memory 均为最新版本，版本号已更新
2. **待办已清理**：task.md 无遗留未完成项，memory 待办已消解或归档
3. **用户已确认**：验收阶段用户明确说「可以」「通过」「没问题」
4. **产物可运行**：代码/文档可打开、可运行、无依赖缺失，每个task都过了Verification
5. **无遗留 Red Flag**：本次任务过程中触发的 Red Flag 均已在 task.md 中记录并解除
6. **经验已沉淀**：本次关键经验已提炼到全局 `memory/memory_main.md`（经 write_project 自动 upsert）
7. **Self-Review已过**：所有交付文档都过了Self-Review四检查（占位符/一致性/范围/歧义）

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-06-29 | 初版，双区架构+三件套+DoD六条 |

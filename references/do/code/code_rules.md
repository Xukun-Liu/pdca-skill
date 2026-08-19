<!-- PDCA标签：D.code -->
<!-- 子标签场景：写代码规则 -->
<!-- 关键词清单：写代码/改代码/改文件/写个/帮我写/实现/开发/coding/加功能/新增功能/改功能/修bug/重构/优化代码/API/接口/RESTful/endpoint/数据库/建表/SQL/Schema/测试/写测试/跑测试/单测/tdd/mock -->
<!-- 引用范围：main + code_eng_agent -->

# 代码规则
> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1 | 更新：2026-08-11

> 📖 **什么时候读这个文件**：
> - 准备写/改任何代码前
> - 准备做Surgical Changes时
> - 不确定代码风格、结构设计、设计模式时
> - 需要设计API接口或数据库Schema时
> 🔴 **不要在这时候读**：
> - 只是纯概念问答/讨论方案不改代码
> - 已经在按HARD-GATE确认过的方案执行

---

## 第一章：代码风格规范

### 1.1 命名规范

**Python**

| 类型 | 规则 | 正例 | 反例 |
|------|------|------|------|
| 文件 | snake_case | `user_service.py` | `UserService.py`、`userService.py` |
| 变量 | snake_case | `user_name` | `userName`、`UserName` |
| 函数 | snake_case | `get_user_info()` | `GetUserInfo()`、`getUserInfo()` |
| 类 | PascalCase | `class UserService` | `class user_service` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY = 3` | `maxRetry = 3` |
| 模块 | snake_case | `api_client` | `ApiClient` |

**JavaScript/TypeScript**

| 类型 | 规则 | 正例 | 反例 |
|------|------|------|------|
| 文件 | kebab-case | `user-service.js` | `userService.js` |
| 变量 | camelCase | `userName` | `user_name` |
| 函数 | camelCase | `getUserInfo()` | `get_user_info()` |
| 类 | PascalCase | `class UserService` | `class userService` |
| 常量 | UPPER_SNAKE_CASE | `const MAX_RETRY = 3` | `const maxRetry = 3` |

**SQL**

| 类型 | 规则 | 正例 | 反例 |
|------|------|------|------|
| 表名 | 小写复数 | `users` | `User`、`user` |
| 字段名 | 小写蛇形 | `user_name` | `UserName`、`userName` |
| 索引名 | idx_表名_字段名 | `idx_users_email` | `email_index` |

### 1.2 缩进和格式

- Python：4 空格缩进
- JavaScript/TypeScript：2 空格缩进
- HTML/CSS：2 空格缩进
- SQL：2 空格缩进
- 行尾无空格
- 文件末尾留空行

### 1.3 注释规范

- 模块级：文件顶部说明用途和作者
- 函数级：说明输入输出、副作用
- 复杂逻辑：解释为什么这么做，而不是做了什么
- 禁止注释掉的代码（删除或用TODO）
- 中文注释用全角符号（。，、：；）

```python
"""
用户服务模块
负责用户的创建、查询、更新和删除操作
"""

def get_user_by_id(user_id: int) -> User:
    """
    根据ID获取用户

    Args:
        user_id: 用户ID

    Returns:
        User对象

    Raises:
        UserNotFoundError: 用户不存在时抛出
    """
    # 使用缓存优先查询，减少数据库压力
    cache_key = f"user:{user_id}"
    cached_user = cache.get(cache_key)
    if cached_user:
        return cached_user
    ...
```

### 1.4 空行和空格

- 函数之间空 2 行
- 类之间空 2 行
- 逻辑块之间空 1 行
- 运算符两边留空格
- 逗号后留空格

### 1.5 导入排序

```python
# 标准库（按字母顺序）
import os
import sys
from typing import Optional, List

# 第三方库（按字母顺序）
import requests
from flask import Flask, jsonify
from marshmallow import Schema, fields

# 本地模块（按相对路径）
from .models import User
from .utils.logger import get_logger
from .config.settings import Config
```

---

## 第二章：代码结构设计

### 2.1 三层架构模式

```
┌─────────────────────────────────────────────┐
│              Command Layer                  │
│  (入口命令、参数解析、用户交互)               │
│  /weather-orchestrator                      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Agent Layer                    │
│  (业务逻辑、流程编排、Skill协调)             │
│  WeatherOrchestrator                       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Skill Layer                    │
│  (原子能力、具体实现、工具调用)               │
│  WeatherAPI、FormatOutput、CacheSkill       │
└─────────────────────────────────────────────┘
```

### 2.2 模块化拆分原则

- 单一职责：每个模块只做一件事
- 高内聚低耦合：模块内部紧密，模块间松耦合
- 关注点分离：UI/业务/数据分离
- 依赖方向：上层依赖下层，不反向

### 2.3 文件拆分规则

| 文件行数 | 状态 | 建议 |
|----------|------|------|
| < 200 | 正常 | 保持原样 |
| 200-500 | 关注 | 评估是否需要拆分 |
| > 500 | 必须拆分 | 按功能拆分为多个文件 |

### 2.4 索引文件模式

```python
# src/core/__init__.py
from .weather_service import WeatherService
from .cache_service import CacheService
from .user_service import UserService

__all__ = ["WeatherService", "CacheService", "UserService"]
```

### 2.5 循环依赖处理

- 避免循环导入：通过接口层解耦
- 使用延迟导入：在函数内部导入
- 重构设计：合并或拆分模块

---

## 第三章：设计模式应用

> 📖 完整的设计模式指南（含应用场景、核心结构、代码示例、优缺点对比）见 [references/plan/design/design_patterns.md](../../plan/design/design_patterns.md)。
> 
> 涵盖6种模式：工厂模式、策略模式、依赖注入、观察者模式、模板方法模式、适配器模式。
> 
> 选型速查：
> 
> | 问题 | 推荐模式 |
> |------|----------|
> | 如何创建对象？ | 工厂模式 |
> | 如何选择算法？ | 策略模式 |
> | 如何解耦依赖？ | 依赖注入 |
> | 如何通知变化？ | 观察者模式 |
> | 如何标准化流程？ | 模板方法模式 |
> | 如何兼容接口？ | 适配器模式 |

---

## 第四章：错误处理规范

### 4.1 统一错误类型

```python
class AppError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details

class ValidationError(AppError):
    def __init__(self, field, message):
        super().__init__("VALIDATION_ERROR", message, {"field": field})

class ServiceError(AppError):
    def __init__(self, service, message):
        super().__init__("SERVICE_ERROR", message, {"service": service})

class NotFoundError(AppError):
    def __init__(self, resource, resource_id):
        super().__init__(
            "NOT_FOUND",
            f"{resource} not found",
            {"resource": resource, "id": resource_id}
        )
```

### 4.2 错误日志格式

```python
import logging
import traceback

logger = logging.getLogger(__name__)

def handle_error(e):
    logger.error(
        f"[{e.code}] {e.message}",
        extra={
            "details": e.details,
            "stack": traceback.format_exc()
        }
    )
```

### 4.3 重试机制

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

class NetworkError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, NetworkError))
)
def fetch_data(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
```

### 4.4 降级策略

```python
def get_weather(city):
    try:
        return weather_api.get(city)
    except ServiceError:
        logger.warning("Weather API unavailable, using fallback")
        return get_cached_weather(city)
    except Exception as e:
        logger.error(f"Failed to get weather: {e}")
        return {"temp": None, "error": "Service unavailable"}
```

---

## 第五章：测试策略

### 5.1 测试分层

```
tests/
├── unit/           # 单元测试：单个函数/类，隔离外部依赖
│   ├── test_user_service.py
│   └── test_api_client.py
├── integration/    # 集成测试：模块间协作，真实依赖
│   └── test_user_flow.py
├── e2e/            # 端到端测试：完整用户流程
│   └── test_weather_orchestrator.py
└── fixtures/       # 测试数据
    └── test_users.json
```

### 5.2 测试命名规范

```python
def test_get_user_by_id_returns_user():
    """测试通过ID获取用户返回正确用户"""
    pass

def test_get_user_by_id_raises_not_found():
    """测试获取不存在的用户抛出异常"""
    pass

def test_user_registration_with_valid_data():
    """测试使用有效数据注册用户"""
    pass

def test_user_registration_with_invalid_email():
    """测试使用无效邮箱注册用户"""
    pass
```

### 5.3 Mock 和 Stub

```python
from unittest.mock import Mock, patch

def test_weather_agent_uses_cache():
    mock_cache = Mock()
    mock_cache.get.return_value = {"temp": 25}

    agent = WeatherAgent(cache_service=mock_cache)
    result = agent.get_weather("Beijing")

    mock_cache.get.assert_called_with("weather:Beijing")

def test_api_client_retry_on_failure():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = [
            requests.exceptions.ConnectionError,
            {"status": 200, "json": lambda: {"data": "ok"}}
        ]
        client = APIClient()
        result = client.fetch("https://api.example.com")

        assert mock_get.call_count == 2
```

### 5.4 测试覆盖率要求

| 模块类型 | 覆盖率要求 |
|----------|------------|
| 核心业务逻辑 | ≥ 80% |
| API 接口 | ≥ 70% |
| 工具函数 | ≥ 90% |

---

## 第六章：API 设计规范

### 6.1 RESTful 规范

| 操作 | HTTP 方法 | 路径 |
|------|-----------|------|
| 创建 | POST | `/api/users` |
| 列表 | GET | `/api/users` |
| 详情 | GET | `/api/users/{id}` |
| 更新 | PUT | `/api/users/{id}` |
| 部分更新 | PATCH | `/api/users/{id}` |
| 删除 | DELETE | `/api/users/{id}` |

### 6.2 查询参数规范

| 参数类型 | 示例 | 说明 |
|----------|------|------|
| 分页 | `page=1&page_size=20` | 分页查询 |
| 过滤 | `status=active&type=admin` | 按条件过滤 |
| 排序 | `sort=created_at&order=desc` | 排序 |
| 搜索 | `q=keyword` | 全文搜索 |

### 6.3 错误响应格式

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input",
        "details": {
            "field": "email",
            "reason": "Email format is invalid"
        }
    }
}
```

### 6.4 分页响应格式

```json
{
    "data": [...],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 100,
        "total_pages": 5
    }
}
```

### 6.5 HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

---

## 第七章：数据库设计规范

### 7.1 Schema 设计原则

- 命名规范：表名小写复数，字段名小写蛇形
- 主键：使用自增 ID 或 UUID
- 外键：明确引用关系，添加 ON DELETE 约束
- 索引：为查询频繁字段创建索引
- 时间戳：每张表添加 created_at 和 updated_at

### 7.2 SQLite 最佳实践

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
```

### 7.3 索引策略

| 场景 | 索引类型 | 示例 |
|------|----------|------|
| 唯一约束 | UNIQUE | `email` |
| 外键查询 | NORMAL | `user_id` |
| 状态筛选 | NORMAL | `status` |
| 组合查询 | COMPOUND | `user_id, status` |

---

## 第八章：安全性规范

### 8.1 输入验证

```python
from marshmallow import Schema, fields, validate

class UserSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    role = fields.Str(validate=validate.OneOf(['user', 'admin', 'editor']))
```

### 8.2 敏感数据保护

- 密码使用 bcrypt 或 Argon2 加密
- API Key 不要硬编码，使用环境变量
- 日志中不要打印敏感信息（密码、Token、银行卡号）
- 数据库中敏感字段加密存储

```python
import bcrypt

def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password: str, hashed_password: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)
```

### 8.3 SQL 注入防护

```python
# 正确：使用参数化查询
user_id = 123
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# 错误：字符串拼接
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 8.4 XSS 防护

```python
from flask import Flask, request
import html

app = Flask(__name__)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    # 转义用户输入
    safe_query = html.escape(query)
    return f"搜索结果: {safe_query}"
```

---

## 第九章：原有核心规则

### 9.1 代码四大行为原则【硬性】

| # | 原则 | 含义 | 反模式 |
|---|------|------|--------|
| 1 | **Think Before Coding** | 动手前先明确：要解决什么问题？输入输出是什么？怎么验证？ | 上来就敲代码，边写边想 |
| 2 | **Simplicity First** | 能50行解决的不要写200行；不要加"未来可能用得到"的功能。详见 [references/common/pd/minimal_code_principles.md](../../common/pd/minimal_code_principles.md) | 过度设计、抽象层太多 |
| 3 | **Surgical Changes** | 改bug/加功能只动必须动的地方 | "反正都打开了顺便改一下" |
| 4 | **Goal-Driven Execution** | 先定义"做完长什么样"，再开始写；每写完一块就验证 | 写了一堆代码但不知道有没有用 |

### 9.2 HARD-GATE：设计未批，绝对不动代码【硬性】

任何代码/文件/配置修改之前，必须先呈现设计/方案并得到用户确认。

### 9.3 No Placeholders 铁律【硬性】

写代码和写task/spec一样，禁止模糊描述。

### 9.4 Verification-before-Completion【硬性】

不是"我写完代码了"就算完成，必须实际运行验证步骤。

---

---

## 第十章：Excel 代码规范（openpyxl / pandas）

> 当任务涉及 Python 操作 Excel（openpyxl 写公式/格式、pandas 分析数据）时，除遵循通用规则外，还需遵守以下 Excel 专属规范。

### 10.1 openpyxl 代码规范

| 规则 | 说明 | 正例 | 反例 |
|------|------|------|------|
| **常量定义复用** | 样式常量（Fill/Border/Font）在文件顶部一次定义，全表复用 | 见下方"可复用样式助手" | 每格单独 new PatternFill |
| **公式优先** | 用 Excel 公式字符串而非 Python 计算后硬编码值 | `ws['B10'] = '=SUM(B2:B9)'` | `ws['B10'] = 5000` |
| **索引 1 基** | openpyxl 行列从 1 开始 | `row=5, col=3` = C5 | `row=0, col=0` 报错 |
| **data_only 只读不存** | `data_only=True` 读计算值，但不要 save | `load_workbook(f, data_only=True)` 仅读 | `load_workbook(f, data_only=True).save()` 丢公式 |
| **列映射核查** | 第 64 列是 BL 不是 BK | `openpyxl.utils.get_column_letter(64)` → 'BL' | 凭印象写 'BK' |
| **公式后必重算** | 写完公式后交付前必须重算验证 | 用 `formulas` 库重算（离线可用） | 交付后打开全是 0/空白 |

### 10.2 pandas 数据分析代码规范

| 规则 | 说明 | 正例 | 反例 |
|------|------|------|------|
| **inplace 慎用** | 默认不原地修改，显式赋值 | `df = df.dropna()` | `df.dropna(inplace=True)`（难追踪） |
| **链式操作圆括号** | 多步操作用小括号包起来分行 | `(df .query("...") .groupby(...) .agg(...))` | 一行几百字符 |
| **类型显式指定** | 读 Excel 时指定 dtype 防止推断错误 | `pd.read_excel(f, dtype={'id': str})` | 让 pandas 自动推断 id 变 float |
| **索引拉平** | 透视/分组后导出到 Excel 前拉平索引 | `pivot.reset_index(inplace=True)` | 多层索引直接 to_excel |
| **NaN 处理** | 运算前处理 NaN，否则结果全 NaN | `df['值'].fillna(0).sum()` | `df['值'].sum()` 含 NaN 返回 NaN |
| **抽样调试** | 大数据先抽样调试，确认逻辑后再全量跑 | `df.sample(1000).pipe(分析函数)` | 10 万行直接跑，debug 时重跑 5 分钟 |

### 10.3 Excel 代码常见陷阱

| 陷阱 | 现象 | 原因 | 修复 |
|------|------|------|------|
| **DataFrame 行号偏移** | Excel 行号比预期大 1 | DataFrame 索引 0 基，Excel 1 基 | 写公式时 `row = df_index + 2`（+1 转 1 基，+1 表头行） |
| **日期变时间戳** | Excel 里显示 45000 而非 2023-01-01 | pandas 读 Excel 日期格式丢失 | `pd.to_datetime()` 或 `read_excel(parse_dates=['日期列'])` |
| **空值公式 #DIV/0!** | 打开 Excel 整片 #DIV/0! | 公式中分母可能有空值 | `=IF(denom=0,"",num/denom)` |
| **跨表引用掉链** | 改名后公式失效 | 公式引用了其他 Sheet 名 | 用 `Sheet1!A1` 格式，改名后自动更新 |
| **大数据写入慢** | 写入 10 万行耗时 > 1 分钟 | openpyxl 逐行写入慢 | 用 `write_only=True` 或 pandas 的 `to_excel()` |

### 10.4 可复用样式助手（推荐复制到项目中）

```python
from openpyxl.styles import PatternFill, Border, Side, Font

# 一次定义，全表复用
ZEBRA_FILL_1 = PatternFill("solid", fgColor="FFFFFF")
ZEBRA_FILL_2 = PatternFill("solid", fgColor="F7F9FC")
HEADER_FILL = PatternFill("solid", fgColor="1F2937")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
KPI_FILL = PatternFill("solid", fgColor="EAF2FF")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9DEE7"),
    right=Side(style="thin", color="D9DEE7"),
    top=Side(style="thin", color="D9DEE7"),
    bottom=Side(style="thin", color="D9DEE7"),
)

def style_header(ws, row, min_col, max_col):
    """统一表头样式"""
    for c in range(min_col, max_col + 1):
        cell = ws.cell(row, c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

def style_data_area(ws, min_row, max_row, min_col, max_col):
    """数据区域斑马纹+细边框"""
    for r in range(min_row, max_row + 1):
        fill = ZEBRA_FILL_1 if (r - min_row) % 2 == 0 else ZEBRA_FILL_2
        for c in range(min_col, max_col + 1):
            cell = ws.cell(r, c)
            cell.fill = fill
            cell.border = THIN_BORDER
```

> 完整样式函数（含 KPI 高亮、合计行强调、数字格式）见 `excel_analysis.md` §十八「可复用样式助手函数」。

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-06-29 | 从 SKILL.md §8 抽出独立成文 |
| v1.1 | 2026-08-11 | 新增第十章 Excel 代码规范（openpyxl/pandas 规范、常见陷阱、样式助手） |

<!-- PDCA标签：P.design -->
<!-- 子标签场景：设计模式 -->
<!-- 关键词清单：设计模式/用工厂/用策略/依赖注入/观察者/模板方法/适配器/代码架构/怎么设计代码/怎么组织代码 -->
<!-- 引用范围：main + bootstrap_agent -->

# 设计模式应用指南
> 阶段标签：P（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 更新：2026-07-08

> 📖 **什么时候读这个文件**：
> - 需要设计复杂系统架构时
> - 需要解耦组件依赖时
> - 需要实现可扩展的功能时
> - 需要优化代码结构时
> 🔴 **不要在这时候读**：
> - 简单功能，直接写代码即可
> - 已有明确的设计方案

---

## 第一章：工厂模式（Factory Pattern）

### 1.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 创建复杂对象 | 对象创建逻辑复杂，涉及多个步骤或依赖 | Skill 对象创建 |
| 对象创建逻辑分散 | 创建逻辑分散在多处，需要集中管理 | 不同类型的工具创建 |
| 根据条件创建不同对象 | 需要根据运行时条件选择创建哪种对象 | 根据用户配置创建不同的处理器 |
| 解耦创建与使用 | 调用方不需要知道对象创建细节 | 服务发现与实例化 |

### 1.2 核心结构

```
┌──────────────────┐     create()     ┌──────────────────┐
│   Factory        │ ──────────────→  │   Product        │
│  (工厂类)         │                  │  (产品接口)       │
└──────────────────┘                  └────────┬─────────┘
                                               │
            ┌──────────────────────────────────┼──────────────────────────────────┐
            ▼                                  ▼                                  ▼
    ┌──────────────┐                   ┌──────────────┐                   ┌──────────────┐
    │ ConcreteA    │                   │ ConcreteB    │                   │ ConcreteC    │
    │ (具体产品A)   │                   │ (具体产品B)   │                   │ (具体产品C)   │
    └──────────────┘                   └──────────────┘                   └──────────────┘
```

### 1.3 代码示例（注册表模式）

```python
from typing import Dict, Type, Any

class Skill:
    def execute(self, **kwargs):
        pass

class WeatherSkill(Skill):
    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def execute(self, **kwargs):
        city = kwargs.get('city')
        return f"Weather for {city}: sunny (API key: {self.api_key})"

class SearchSkill(Skill):
    def execute(self, **kwargs):
        query = kwargs.get('query')
        return f"Search results for: {query}"

class SkillFactory:
    _registry: Dict[str, Type[Skill]] = {}

    @classmethod
    def register(cls, skill_type: str):
        def decorator(skill_class: Type[Skill]) -> Type[Skill]:
            cls._registry[skill_type] = skill_class
            return skill_class
        return decorator

    @classmethod
    def create(cls, skill_type: str, **kwargs) -> Skill:
        skill_class = cls._registry.get(skill_type)
        if not skill_class:
            raise ValueError(f"Unknown skill type: {skill_type}")
        return skill_class(**kwargs)

SkillFactory.register("weather")(WeatherSkill)
SkillFactory.register("search")(SearchSkill)
```

### 1.4 使用示例

```python
weather_skill = SkillFactory.create("weather", api_key="abc123")
result = weather_skill.execute(city="Beijing")
print(result)

search_skill = SkillFactory.create("search")
result = search_skill.execute(query="python")
print(result)
```

### 1.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 解耦对象创建与使用 | 增加了代码复杂度 |
| 集中管理创建逻辑 | 需要额外维护工厂类 |
| 易于扩展新类型 | 简单场景下显得多余 |
| 符合开闭原则 | |

---

## 第二章：策略模式（Strategy Pattern）

### 2.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 多种算法解决同一问题 | 同一个问题有多种解法，需要根据情况选择 | 不同的搜索算法 |
| 需要运行时切换算法 | 算法需要在运行时动态切换 | 根据网络状况选择不同的数据获取策略 |
| 算法复杂度不同 | 不同算法适用于不同规模的数据 | 小规模用线性搜索，大规模用二分搜索 |
| 避免大量条件判断 | 替代 if-else 或 switch-case | 根据类型选择不同的处理策略 |

### 2.2 核心结构

```
┌──────────────────┐     uses     ┌──────────────────┐
│   Context        │ ───────────→  │   Strategy       │
│  (上下文类)       │              │  (策略接口)       │
└──────────────────┘              └────────┬─────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            ▼                              ▼                              ▼
    ┌──────────────┐               ┌──────────────┐               ┌──────────────┐
    │ StrategyA    │               │ StrategyB    │               │ StrategyC    │
    │ (具体策略A)   │               │ (具体策略B)   │               │ (具体策略C)   │
    └──────────────┘               └──────────────┘               └──────────────┘
```

### 2.3 代码示例

```python
from abc import ABC, abstractmethod
from typing import List

class SearchStrategy(ABC):
    @abstractmethod
    def search(self, query: str, data: List[str]) -> List[str]:
        pass

class LinearSearch(SearchStrategy):
    def search(self, query: str, data: List[str]) -> List[str]:
        results = []
        for item in data:
            if query.lower() in item.lower():
                results.append(item)
        return results

class BinarySearch(SearchStrategy):
    def search(self, query: str, data: List[str]) -> List[str]:
        data_sorted = sorted(data)
        left, right = 0, len(data_sorted) - 1
        results = []
        while left <= right:
            mid = (left + right) // 2
            if query.lower() in data_sorted[mid].lower():
                results.append(data_sorted[mid])
                left = mid + 1
            elif query.lower() < data_sorted[mid].lower():
                right = mid - 1
            else:
                left = mid + 1
        return results

class SearchAgent:
    def __init__(self, strategy: SearchStrategy):
        self.strategy = strategy

    def execute_search(self, query: str, data: List[str]) -> List[str]:
        return self.strategy.search(query, data)

    def set_strategy(self, strategy: SearchStrategy):
        self.strategy = strategy
```

### 2.4 使用示例

```python
data = ["apple", "banana", "cherry", "date", "elderberry"]

linear_search = LinearSearch()
agent = SearchAgent(linear_search)
result = agent.execute_search("berry", data)
print(result)

binary_search = BinarySearch()
agent.set_strategy(binary_search)
result = agent.execute_search("banana", data)
print(result)
```

### 2.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 消除大量条件判断 | 增加了类的数量 |
| 符合开闭原则 | 需要额外定义策略接口 |
| 运行时动态切换 | 简单场景下显得多余 |
| 便于单元测试 | |

---

## 第三章：依赖注入（Dependency Injection）

### 3.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 解耦组件依赖 | 组件之间的依赖关系由外部注入，而非自己创建 | Service 依赖 Repository |
| 替换依赖进行测试 | 测试时可以注入 Mock 对象 | 注入 Mock 数据库 |
| 管理复杂依赖关系 | 依赖关系复杂，需要统一管理 | 多个服务之间的依赖 |
| 提高代码可测试性 | 依赖可以被替换，便于测试 | 单元测试时注入测试依赖 |

### 3.2 核心结构

```
┌──────────────────┐     injects     ┌──────────────────┐
│   Injector       │ ──────────────→  │   Service        │
│  (注入器)         │                  │  (服务类)        │
└──────────────────┘                  └────────┬─────────┘
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │   Dependency     │
                                    │  (依赖类)        │
                                    └──────────────────┘
```

### 3.3 代码示例（构造函数注入）

```python
class Database:
    def connect(self):
        return "Connected to production database"

class MockDatabase:
    def connect(self):
        return "Connected to mock database"

class UserService:
    def __init__(self, db: Database):
        self.db = db

    def get_user(self, user_id: int) -> str:
        connection = self.db.connect()
        return f"User {user_id} fetched from: {connection}"

class EmailService:
    def __init__(self, db: Database):
        self.db = db

    def send_email(self, user_id: int, message: str) -> str:
        connection = self.db.connect()
        return f"Email sent to user {user_id} using: {connection}"

class Container:
    def __init__(self, environment: str = "production"):
        self.environment = environment

    def get_database(self) -> Database:
        if self.environment == "test":
            return MockDatabase()
        return Database()

    def get_user_service(self) -> UserService:
        return UserService(self.get_database())

    def get_email_service(self) -> EmailService:
        return EmailService(self.get_database())
```

### 3.4 使用示例

```python
container = Container()
user_service = container.get_user_service()
result = user_service.get_user(123)
print(result)

test_container = Container(environment="test")
test_user_service = test_container.get_user_service()
result = test_user_service.get_user(123)
print(result)
```

### 3.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 降低耦合度 | 增加了代码复杂度 |
| 提高可测试性 | 需要额外的容器/注入器 |
| 便于替换依赖 | 学习曲线较陡 |
| 符合单一职责原则 | |

---

## 第四章：观察者模式（Observer Pattern）

### 4.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 状态变化通知多个对象 | 一个对象状态变化需要通知多个观察者 | 任务状态变化通知日志、UI、通知服务 |
| 解耦观察者和被观察者 | 观察者和被观察者之间松耦合 | 事件总线系统 |
| 事件驱动系统 | 基于事件的架构 | 消息队列、事件订阅 |
| 多模块协作 | 多个模块需要响应同一个事件 | 系统状态变更通知 |

### 4.2 核心结构

```
┌──────────────────┐     notify()     ┌──────────────────┐
│   Observable     │ ───────────────→  │   Observer       │
│  (被观察者)       │                   │  (观察者接口)     │
└──────────────────┘                   └────────┬─────────┘
     │                                           │
     │ add/remove                                │ update()
     │                                           │
     ▼                                           ▼
┌──────────────────┐                   ┌──────────────────┐
│   Subject        │                   │   ConcreteA      │
│  (具体主题)       │                   │  (具体观察者A)    │
└──────────────────┘                   └──────────────────┘
                                           │
                                           ▼
                                   ┌──────────────────┐
                                   │   ConcreteB      │
                                   │  (具体观察者B)    │
                                   └──────────────────┘
```

### 4.3 代码示例

```python
from abc import ABC, abstractmethod
from typing import List, Any

class Observer(ABC):
    @abstractmethod
    def update(self, event: str, data: Any = None):
        pass

class TaskLogger(Observer):
    def update(self, event: str, data: Any = None):
        print(f"[LOG] Task {data.get('task_id')}: {event}")

class TaskNotifier(Observer):
    def update(self, event: str, data: Any = None):
        print(f"[NOTIFY] Task {data.get('task_id')} status changed to: {event}")

class TaskUI(Observer):
    def update(self, event: str, data: Any = None):
        print(f"[UI] Updating task {data.get('task_id')} display to: {event}")

class TaskManager:
    def __init__(self):
        self._observers: List[Observer] = []
        self._status: str = "pending"

    def add_observer(self, observer: Observer):
        self._observers.append(observer)

    def remove_observer(self, observer: Observer):
        self._observers.remove(observer)

    def notify(self, event: str, data: Any = None):
        for observer in self._observers:
            observer.update(event, data)

    def update_status(self, task_id: int, status: str):
        self._status = status
        self.notify(status, {"task_id": task_id})
```

### 4.4 使用示例

```python
task_manager = TaskManager()

logger = TaskLogger()
notifier = TaskNotifier()
ui = TaskUI()

task_manager.add_observer(logger)
task_manager.add_observer(notifier)
task_manager.add_observer(ui)

task_manager.update_status(1, "in_progress")
task_manager.update_status(1, "completed")

task_manager.remove_observer(notifier)
task_manager.update_status(1, "archived")
```

### 4.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 解耦观察者和被观察者 | 观察者过多时可能影响性能 |
| 符合开闭原则 | 通知顺序不确定 |
| 支持广播通信 | 可能产生意外的副作用 |
| 便于扩展新观察者 | |

---

## 第五章：模板方法模式（Template Method Pattern）

### 5.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 多个算法有相同骨架结构 | 多个算法共享相同的步骤，但具体实现不同 | 不同的任务执行流程 |
| 需要标准化流程 | 流程固定，但某些步骤可以自定义 | 请求处理流程 |
| 代码复用 | 多个类共享相同的代码逻辑 | 数据库操作流程 |
| 控制子类扩展 | 父类控制流程，子类实现具体步骤 | 服务调用流程 |

### 5.2 核心结构

```
┌─────────────────────────────────────────────────────┐
│           AbstractClass（抽象类）                    │
│  ┌─────────────────────────────────────────────┐    │
│  │ template_method():                         │    │
│  │   step1()  ← 抽象方法                      │    │
│  │   step2()  ← 抽象方法                      │    │
│  │   step3()  ← 具体方法（可选覆盖）            │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────┘
                           │ extends
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ConcreteA      │ │  ConcreteB      │ │  ConcreteC      │
│  (具体实现A)     │ │  (具体实现B)     │ │  (具体实现C)     │
│  step1(): ...   │ │  step1(): ...   │ │  step1(): ...   │
│  step2(): ...   │ │  step2(): ...   │ │  step2(): ...   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 5.3 代码示例

```python
from abc import ABC, abstractmethod

class TaskTemplate(ABC):
    def execute(self) -> str:
        result = []
        result.append(self.prepare())
        result.append(self.run())
        result.append(self.cleanup())
        return "\n".join(result)

    @abstractmethod
    def prepare(self) -> str:
        pass

    @abstractmethod
    def run(self) -> str:
        pass

    def cleanup(self) -> str:
        return "[Template] Cleaning up resources"

class DataProcessingTask(TaskTemplate):
    def prepare(self) -> str:
        return "[DataProcessing] Loading data from database"

    def run(self) -> str:
        return "[DataProcessing] Processing 1000 records"

    def cleanup(self) -> str:
        return "[DataProcessing] Closing database connection"

class ApiCallTask(TaskTemplate):
    def prepare(self) -> str:
        return "[ApiCall] Setting up API client"

    def run(self) -> str:
        return "[ApiCall] Making HTTP request to external service"

class FileProcessingTask(TaskTemplate):
    def prepare(self) -> str:
        return "[FileProcessing] Opening input file"

    def run(self) -> str:
        return "[FileProcessing] Parsing and transforming file content"
```

### 5.4 使用示例

```python
data_task = DataProcessingTask()
print(data_task.execute())

api_task = ApiCallTask()
print(api_task.execute())

file_task = FileProcessingTask()
print(file_task.execute())
```

### 5.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 代码复用 | 增加了抽象层次 |
| 标准化流程 | 灵活性受限 |
| 符合开闭原则 | 父类和子类耦合度高 |
| 便于维护 | |

---

## 第六章：适配器模式（Adapter Pattern）

### 6.1 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 复用已有类但接口不兼容 | 已有类功能符合需求，但接口不一致 | 旧API与新API的兼容 |
| 统一不同接口的调用方式 | 多个类有类似功能但接口不同 | 统一不同数据库的操作接口 |
| 第三方库接口变更 | 第三方库升级后接口变化 | 兼容新旧版本的SDK |
| 解耦客户端与实现 | 客户端依赖统一接口，不依赖具体实现 | 插件系统 |

### 6.2 核心结构

```
┌──────────────────┐     uses     ┌──────────────────┐
│   Client         │ ───────────→  │   Target         │
│  (客户端)         │              │  (目标接口)       │
└──────────────────┘              └────────┬─────────┘
                                           │ implements
                                           ▼
                                    ┌──────────────────┐
                                    │   Adapter        │
                                    │  (适配器)         │
                                    └────────┬─────────┘
                                             │ adapts
                                             ▼
                                    ┌──────────────────┐
                                    │   Adaptee        │
                                    │  (被适配者)       │
                                    └──────────────────┘
```

### 6.3 代码示例（类适配器）

```python
class LegacyAPI:
    def fetch_data(self, params: dict) -> dict:
        return {"legacy_format": params}

class NewAPI:
    def get(self, query: str) -> dict:
        return {"new_format": query}

class APIAdapter:
    def __init__(self, api):
        self.api = api

    def request(self, **kwargs) -> dict:
        if hasattr(self.api, 'fetch_data'):
            return self.api.fetch_data(kwargs)
        elif hasattr(self.api, 'get'):
            query = kwargs.get('query', '')
            return self.api.get(query)
        else:
            raise NotImplementedError("Unsupported API type")

class DataFetcher:
    def __init__(self, adapter: APIAdapter):
        self.adapter = adapter

    def fetch(self, **kwargs) -> dict:
        return self.adapter.request(**kwargs)
```

### 6.4 使用示例

```python
legacy_api = LegacyAPI()
legacy_adapter = APIAdapter(legacy_api)
fetcher = DataFetcher(legacy_adapter)
result = fetcher.fetch(user_id=123)
print(result)

new_api = NewAPI()
new_adapter = APIAdapter(new_api)
fetcher = DataFetcher(new_adapter)
result = fetcher.fetch(query="weather")
print(result)
```

### 6.5 优点与缺点

| 优点 | 缺点 |
|------|------|
| 复用已有代码 | 增加了代码复杂度 |
| 解耦客户端与实现 | 需要额外维护适配器 |
| 符合开闭原则 | 可能隐藏了适配逻辑 |
| 便于替换实现 | |

---

## 设计模式选型指南

| 问题 | 推荐模式 |
|------|----------|
| 如何创建对象？ | 工厂模式 |
| 如何选择算法？ | 策略模式 |
| 如何解耦依赖？ | 依赖注入 |
| 如何通知变化？ | 观察者模式 |
| 如何标准化流程？ | 模板方法模式 |
| 如何兼容接口？ | 适配器模式 |

---

## 版本历史

| 版本 | 时间 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-07-08 | 初版，收录6种常用设计模式：工厂模式、策略模式、依赖注入、观察者模式、模板方法模式、适配器模式 |

# protocol/ - 协议层结构化常量

> riji-skill 协议层说明
> 借鉴业界 AI PM 协议实践，Python 版改造

## 用途

定义所有跨任务的协议常量（铁律 ID / 三态 / 角色 / 合同 / 路由 / 验证策略 / markdown 结构 / 变更影响图），作为 skill 协议层结构化的载体。

## 9 个 .py 文件

| 文件 | 用途 |
|------|------|
| `__init__.py` | barrel 文件，相对导入导出所有协议常量 |
| `constants.py` | 核心常量（铁律 ID / 三态 / 阶段 ID / 字段等级 / 字段来源） |
| `file_roles.py` | 10 个文件角色（written_by / read_by / description） |
| `field_contracts.py` | 4 个字段合同（project_memory / spec / task / handoff） |
| `stages.py` | 13 条 PDCA 阶段决策规则（7 现有 + 6 新增）+ 全局伴随能力 |
| `routing.py` | PDCA 4 环路由 + 仲裁规则 |
| `validation.py` | 5 角色验证策略 + 日志时间戳正则 + 陈旧口径检测 |
| `markdown_structure.py` | Markdown 模板章节（spec/task/handoff 实际章节）+ 复用章节 |
| `change_impact_map.py` | 8 family 变更影响图 + `get_impacted_files()` 函数 |

## 设计原则

- **纯 Python 标准库**：零第三方依赖，可直接 `import`
- **PEP 8 大写命名**：所有常量用 `UPPER_SNAKE_CASE`
- **中文注释**：对齐项目风格，docstring 说明用途
- **路径相对 skill 包根**：如 `'SKILL.md'` 不是 `'skills/riji-skill/SKILL.md'`

## 借鉴来源

- 业界 AI PM 协议实践（Python 版改造）
- riji-skill 实际目录结构
- assets/*_template.md 实际章节

## 如何使用

```python
from protocol import (
    FILE_ROLES,
    FIELD_CONTRACTS,
    STAGE_DECISION_RULES,
    ROUTE_TARGETS,
    VALIDATION_POLICY,
    MARKDOWN_TEMPLATES,
    CHANGE_IMPACT_MAP,
    get_impacted_files,
)

# 查询文件角色
print(FILE_ROLES['SKILL.md'])

# 查询变更影响
impacted = get_impacted_files(['SKILL.md'])
print(impacted)

# 查询 PDCA 路由
print(ROUTE_TARGETS['plan']['triggers'])
```

## 验证命令

```bash
cd /path/to/riji-skill
python -c "import sys; sys.path.insert(0, '.'); from protocol import FILE_ROLES; assert len(FILE_ROLES)==10; print('OK')"
```

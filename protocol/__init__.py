"""protocol - 协议层结构化常量

riji-skill 协议层任务产出。
借鉴业界 AI PM 协议实践，Python 版改造。

定义所有跨任务的协议常量：
- 铁律 ID / 三态 / 阶段 ID / 字段等级 / 字段来源（constants）
- 文件角色（file_roles）
- 字段合同（field_contracts）
- PDCA 阶段决策规则（stages）
- 路由表 + 仲裁规则（routing）
- 验证策略（validation）
- Markdown 模板章节（markdown_structure）
- 变更影响图（change_impact_map）

用法：
    from protocol import FILE_ROLES, FIELD_CONTRACTS, STAGE_DECISION_RULES
    from protocol import ROUTE_TARGETS, VALIDATION_POLICY, MARKDOWN_TEMPLATES
    from protocol import CHANGE_IMPACT_MAP, get_impacted_files

设计来源: SKILL.md §0 流程优先 + §3 文档体系, references/common/da/sync-matrix.md
"""

from .constants import (
    IRON_RULE_IDS,
    HARD_GATE_TRI_STATES,
    STAGE_IDS,
    FIELD_LEVELS,
    FIELD_SOURCES,
)
from .file_roles import FILE_ROLES
from .field_contracts import FIELD_CONTRACTS
from .stages import STAGE_DECISION_RULES, GLOBAL_COMPANION_ABILITIES
from .routing import ROUTE_TARGETS, GATE_STATES, ARBITRATION_RULES
from .validation import VALIDATION_POLICY
from .markdown_structure import COMMON_SECTIONS, MARKDOWN_TEMPLATES
from .change_impact_map import CHANGE_IMPACT_MAP, get_impacted_files

__all__ = [
    # constants
    'IRON_RULE_IDS',
    'HARD_GATE_TRI_STATES',
    'STAGE_IDS',
    'FIELD_LEVELS',
    'FIELD_SOURCES',
    # file_roles
    'FILE_ROLES',
    # field_contracts
    'FIELD_CONTRACTS',
    # stages
    'STAGE_DECISION_RULES',
    'GLOBAL_COMPANION_ABILITIES',
    # routing
    'ROUTE_TARGETS',
    'GATE_STATES',
    'ARBITRATION_RULES',
    # validation
    'VALIDATION_POLICY',
    # markdown_structure
    'COMMON_SECTIONS',
    'MARKDOWN_TEMPLATES',
    # change_impact_map
    'CHANGE_IMPACT_MAP',
    'get_impacted_files',
]

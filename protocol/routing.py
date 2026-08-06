"""routing.py - 路由表与仲裁规则

PDCA 4 环路由：触发词 / 输出 / 是否只读。
GATE_STATES = HARD_GATE_TRI_STATES（从 constants 导入别名）。
ARBITRATION_RULES：多关键词命中时的仲裁规则。
设计来源: SKILL.md §0 流程优先, references/common/pa/trigger_hooks.md
"""

from .constants import HARD_GATE_TRI_STATES

# PDCA 4 环路由
ROUTE_TARGETS = {
    'plan': {
        'triggers': [
            '/plan', '/设计', '/方案', '从头开始', '新项目',
            '帮我规划', '一步一步来', '规划一下', '想清楚再做',
            '需求分析', '做需求', '出方案'
        ],
        'output': 'spec/task/plan 文档',
        'readonly': True
    },
    'do': {
        'triggers': ['/do', '动手', '执行', '开始做', '实现', '改代码', '写代码'],
        'output': '代码改动 + 验证结果',
        'readonly': False
    },
    'check': {
        'triggers': ['/check', '验收', '检查', '对照 spec', '验证', '跑测试'],
        'output': '验收报告 + Reflexion 反思',
        'readonly': True
    },
    'act': {
        'triggers': ['/act', '收尾', '归档', '交接', '落盘', '写 memory', '刷 summary'],
        'output': 'memory + SUMMARY + handoff + learn 门控自动触发 + distill 询问',
        'readonly': False
    }
}

# 三态别名（HARD_GATE_TRI_STATES 同义）
GATE_STATES = HARD_GATE_TRI_STATES

# 多关键词命中仲裁规则
ARBITRATION_RULES = {
    '梳理一下': {
        'default_route': 'sync-matrix',
        'note': '默认走 sync-matrix（整理规范），除非明确"梳理做了什么"才走 hand-drawn-report'
    },
    '需求分析/出方案': {
        'default_route': '/plan',
        'condition': '若带 /plan 前缀或"从头开始/新项目"',
        'fallback': 'document_specs.md（方案文档顶部按 hand-drawn-report.md 带图）',
        'note': '带 /plan 前缀或"从头开始/新项目"→走 /plan；否则→document_specs.md'
    }
}

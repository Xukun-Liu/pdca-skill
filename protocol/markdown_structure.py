"""markdown_structure.py - Markdown 模板章节定义

按 assets/*_template.md 实际章节填：
- spec: 13 章节（assets/spec_template.md 实际 ## 章节列表，0.1/0.A/0.2 算 0 子节时）
- task: 12 章节（assets/task_template.md 实际 ## 章节列表，排除 Self-Review+版本历史）
- handoff: 10 章节（assets/handoff_template.md 实际 ## 章节列表）

COMMON_SECTIONS 复用 Self-Review + 版本历史。
memory 项只放指针指向 SKILL.md。
设计来源: SKILL.md §3 三件套, references/common/pda/document_specs.md
"""

# 复用章节（跨模板共用）
COMMON_SECTIONS = {
    'self_review': {
        'required': True,
        'min_dimensions': 4,
        'note': '简单任务过前 4 维度，复杂任务必过 9 维度'
    },
    'version_history': {
        'required': True,
        'min_entries': 1,
        'note': '至少 1 条版本记录'
    }
}

# Markdown 模板章节（从 assets/*_template.md 实际读取）
MARKDOWN_TEMPLATES = {
    'spec': {
        'template_file': 'assets/spec_template.md',
        'sections': [
            '0. 设计层：本质拆解（第一性原理）',
            '0.1 方案对比',
            '0.A 外部资源搜索清单',
            '0.2 少写代码 / 复用优先评估',
            '1. PRD 层：业务背景与目标',
            '2. PRD 层：定义与术语',
            '3. PRD 层：范围',
            '4. PRD 层：功能需求',
            '5. Spec 层：验收标准',
            '6. Spec 层：正例与反例',
            '7. Spec 层：技术方案与代码结构',
            '8. Spec 层：依赖关系',
            '9. Spec 层：风险与降级',
            '10. Clarifications',
            'Self-Review 自检清单',
            '版本历史'
        ],
        'min_sections': 13
    },
    'task': {
        'template_file': 'assets/task_template.md',
        'sections': [
            '总览',
            'Phase 1: 需求对齐',
            'Phase 2: 执行',
            'Phase 3: 验收',
            '验收清单（4 道闸门）',
            '待回答的关键问题（Key Questions）',
            '决策记录（Decision Log）',
            '错误记录（Error Log）',
            '测试结果（Test Results）',
            '视觉/浏览器发现',
            'Self-Review 自检清单',
            '阻塞与备注',
            '任务格式说明',
            '版本历史'
        ],
        'min_sections': 12
    },
    'handoff': {
        'template_file': 'assets/handoff_template.md',
        'sections': [
            '1. 当前状态',
            '2. 已完成工作',
            '3. 待办事项',
            '4. 关键决策',
            '5. 已知问题/风险',
            '6. 环境信息',
            '7. 联系方式',
            '8. 变更历史',
            '9. 接手须知（五问预跑）',
            '版本历史'
        ],
        'min_sections': 10
    },
    'memory': {
        'template_file': 'assets/memory_template.md',
        'sections': [
            '指针：详见 SKILL.md Memory First 章节'
        ],
        'min_sections': 1,
        'note': 'memory 项只放指针指向 SKILL.md，不在协议层重复定义'
    }
}

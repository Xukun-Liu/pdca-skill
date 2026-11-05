"""field_contracts.py - 字段合同定义

定义 7 类文档的字段合同：project_memory / spec / task / handoff / skill_main / readme / global_memory。
每个合同含 required_when + fields（每个字段含 level/source/match）。
- project_memory: 8 字段含 outcome，required_when='task_completed'
- spec: 含 background+risks+alternatives，required_when='complex_task'
- task: label 对齐模板原文"怎么做/验证/验收/状态"
- handoff: 7 章节
- skill_main: SKILL.md 4 关键章节（条铁律/Memory First/§0/§1），match=markdown_header
- readme: README.md 3 关键章节（安装/上手/能力地图，短词松匹配），match=markdown_header
- global_memory: memory_main.md 项目分段（pdca-skill），match=markdown_header
设计来源: SKILL.md §3 三件套, references/common/pda/document_specs.md
"""

FIELD_CONTRACTS = {
    'project_memory': {
        'required_when': 'task_completed',
        'fields': {
            'task': {'level': 'required', 'source': 'file'},
            'timestamp': {'level': 'required', 'source': 'file'},
            'decision': {'level': 'required', 'source': 'dialogue'},
            'changes': {'level': 'required', 'source': 'file'},
            'outcome': {'level': 'required', 'source': 'inferred'},
            'blockers': {'level': 'recommended', 'source': 'dialogue'},
            'next_step': {'level': 'recommended', 'source': 'inferred'},
            'lessons_learned': {'level': 'recommended', 'source': 'inferred'}
        }
    },
    'spec': {
        'required_when': 'complex_task',
        'fields': {
            'background': {'level': 'required', 'source': 'dialogue'},
            'goal': {'level': 'required', 'source': 'dialogue'},
            'scope': {'level': 'required', 'source': 'dialogue'},
            'risks': {'level': 'required', 'source': 'inferred'},
            'alternatives': {'level': 'required', 'source': 'inferred'},
            'acceptance': {'level': 'required', 'source': 'dialogue'},
            'derived_from': {'level': 'required', 'source': 'file'}
        }
    },
    'task': {
        'required_when': 'complex_task',
        'fields': {
            'how_to': {'level': 'required', 'source': 'inferred'},
            'verification': {'level': 'required', 'source': 'inferred'},
            'acceptance': {'level': 'required', 'source': 'dialogue'},
            'status': {'level': 'required', 'source': 'file'}
        }
    },
    'handoff': {
        'required_when': 'task_handoff',
        'fields': {
            'current_status': {'level': 'required', 'source': 'file'},
            'completed': {'level': 'required', 'source': 'file'},
            'todo': {'level': 'required', 'source': 'file'},
            'blockers': {'level': 'recommended', 'source': 'dialogue'},
            'next_handoff': {'level': 'recommended', 'source': 'inferred'},
            'changes': {'level': 'required', 'source': 'file'},
            'checklist': {'level': 'recommended', 'source': 'inferred'}
        }
    },
    'skill_main': {
        'required_when': 'global_file_validation',
        'fields': {
            '条铁律': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
            'Memory First': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
            '§0 流程优先': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
            '§1 启动检查': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
        }
    },
    'readme': {
        'required_when': 'global_file_validation',
        'fields': {
            '安装': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
            # 用短词松匹配，兼容 README 实际章节名（如「30 秒上手」「完整能力地图」）
            '上手': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
            '能力地图': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
        }
    },
    'global_memory': {
        'required_when': 'global_file_validation',
        'fields': {
            'pdca-skill': {'level': 'required', 'source': 'file', 'match': 'markdown_header'},
        }
    }
}

"""validation.py - 验证策略

5 角色规则：skill_rules / project_memory / spec / task / handoff。
每个含 required_fields + validation_rules。
log_file_pattern：时间戳正则（YYYYMMDD_HHMM，如 20260718_1432）。
global_assertions：陈旧口径检测模式（stale_patterns）。
设计来源: SKILL.md §1 启动检查, references/common/da/sync-matrix.md
"""

VALIDATION_POLICY = {
    'skill_rules': {
        'required_fields': [
            'name', 'description', 'agent_created',
            'license', 'version', 'keywords',
            'category', 'author'
        ],
        'validation_rules': [
            'frontmatter_complete',
            'no_stale_references'
        ]
    },
    'project_memory': {
        'required_fields': [
            'task', 'timestamp', 'decision',
            'changes', 'outcome'
        ],
        'validation_rules': [
            'outcome_explicit',
            'timestamp_pattern_valid',
            'no_legacy_platform_memory_path'
        ]
    },
    'spec': {
        'required_fields': [
            'background', 'goal', 'scope',
            'risks', 'alternatives', 'acceptance',
            'derived_from'
        ],
        'validation_rules': [
            'two_options_compared',
            'self_review_passed',
            'no_placeholders'
        ]
    },
    'task': {
        'required_fields': [
            'how_to', 'verification', 'acceptance', 'status'
        ],
        'validation_rules': [
            'gwt_format',
            'boundary_conditions_listed',
            'all_tasks_checked_before_check'
        ]
    },
    'handoff': {
        'required_fields': [
            'current_status', 'completed', 'todo',
            'changes', 'checklist'
        ],
        'validation_rules': [
            'five_question_prefilled',
            'version_history_present'
        ]
    },
    # 日志文件时间戳正则（如 20260718_1432）
    'log_file_pattern': r'\d{8}_\d{4}',
    # 全局断言：陈旧口径检测模式
    'global_assertions': {
        'stale_patterns': [
            'C:\\Users\\',           # 硬编码 Windows 本机路径前缀（应脱敏）
            '_skillhub_meta.json',        # 陈旧元数据文件
            '36 条场景'                    # 陈旧口径
        ]
    }
}

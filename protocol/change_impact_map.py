"""change_impact_map.py - 变更影响图

8 个 family（5 现有 + 3 新增）：
- skill_core / references / scripts / memory / docs（现有）
- handoff_protocol / learn_cycle_protocol / trigger_hooks_protocol（新增）

get_impacted_files：根据变更文件列表，返回受影响文件列表。
设计来源: SKILL.md §3 文档体系, references/common/da/sync-matrix.md
"""

CHANGE_IMPACT_MAP = {
    # === 现有 5 个 ===
    'skill_core': {
        'trigger_files': ['SKILL.md'],
        'impacted_files': [
            'references/*.md',
            'scripts/validate_skill.py',
            'HISTORY.md'
        ]
    },
    'references': {
        'trigger_files': ['references/*.md'],
        'impacted_files': [
            'SKILL.md',
            'scripts/validate_skill.py'
        ]
    },
    'scripts': {
        'trigger_files': ['scripts/*.py'],
        'impacted_files': [
            'scripts/validate_skill.py',
            'SKILL.md'
        ]
    },
    'memory': {
        'trigger_files': ['memory/memory_main.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md'
        ]
    },
    'docs': {
        'trigger_files': ['docs_rj/*.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md'
        ]
    },
    # === 新增 3 个 ===
    'handoff_protocol': {
        'trigger_files': ['scripts/handoff_tidy.py'],
        'impacted_files': [
            'assets/handoff_template.md',
            'docs_rj/memory_rj/TASK_STATE_*.md'
        ]
    },
    'learn_cycle_protocol': {
        'trigger_files': ['scripts/learn_tidy.py'],
        'impacted_files': [
            'references/act/learn/learn_cycle.md',
            'docs_rj/learn_rj/'
        ]
    },
    'trigger_hooks_protocol': {
        'trigger_files': ['references/common/pa/trigger_hooks.md'],
        'impacted_files': [
            'SKILL.md'
        ]
    },
    # === docs_rj 子目录级（新增 5 个，对应 spec REQ-004）===
    'docs_rj_spec': {
        'trigger_files': ['docs_rj/spec_rj/*.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md',
            'docs_rj/DEPENDENCY_MAP.md',
            'docs_rj/spec_rj/INDEX.md'
        ]
    },
    'docs_rj_task': {
        'trigger_files': ['docs_rj/task_rj/*.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md',
            'docs_rj/DEPENDENCY_MAP.md',
            'docs_rj/task_rj/INDEX.md'
        ]
    },
    'docs_rj_handoff': {
        'trigger_files': ['docs_rj/handoff_rj/*.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md',
            'docs_rj/DEPENDENCY_MAP.md',
            'docs_rj/handoff_rj/INDEX.md'
        ]
    },
    'docs_rj_memory': {
        'trigger_files': ['docs_rj/memory_rj/*.md'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md',
            'docs_rj/DEPENDENCY_MAP.md',
            'docs_rj/memory_rj/INDEX.md'
        ]
    },
    'docs_rj_archive': {
        'trigger_files': ['docs_rj/archive_rj/*'],
        'impacted_files': [
            'docs_rj/SUMMARY_RJ.md',
            'docs_rj/DEPENDENCY_MAP.md',
            'docs_rj/archive_rj/INDEX.md'
        ]
    }
}


def get_impacted_files(changed_files: list) -> list:
    """根据变更文件列表，返回受影响文件列表。

    基于 CHANGE_IMPACT_MAP，匹配规则：变更文件路径 endswith 或包含某 trigger_files 条目。

    Args:
        changed_files: 变更文件路径列表

    Returns:
        受影响文件路径列表（去重+排序）
    """
    impacted = set()
    for f in changed_files:
        for family, rule in CHANGE_IMPACT_MAP.items():
            if any(f.endswith(t) or t in f for t in rule['trigger_files']):
                impacted.update(rule['impacted_files'])
    return sorted(impacted)

"""file_roles.py - 文件角色定义

定义 skill 包内 10 个核心文件角色：written_by / read_by / description。
路径相对 skill 包根（如 'SKILL.md' 不是 'skills/riji-skill/SKILL.md'）。
基于实际目录结构。
设计来源: SKILL.md §3 文档体系, references/plan/design/project_structure.md
"""

FILE_ROLES = {
    'SKILL.md': {
        'role': 'main_entry',
        'written_by': ['agent', 'human'],
        'read_by': ['agent', 'human'],
        'description': '协作框架主入口，定义7条铁律+触发钩子+流程'
    },
    'HISTORY.md': {
        'role': 'version_history',
        'written_by': ['agent'],
        'read_by': ['agent', 'human'],
        'description': '版本历史变更记录，每次发版追加一条'
    },
    'README.md': {
        'role': 'project_doc',
        'written_by': ['agent', 'human'],
        'read_by': ['human'],
        'description': '项目对外说明，使用者首先阅读'
    },
    'references/*.md': {
        'role': 'reference_module',
        'written_by': ['agent'],
        'read_by': ['agent'],
        'description': '参考模块，按需加载（PDCA 母标签+子标签）'
    },
    'assets/*_template.md': {
        'role': 'template',
        'written_by': ['agent', 'human'],
        'read_by': ['agent'],
        'description': '文档模板（spec/task/handoff/summary 等）'
    },
    'scripts/*.py': {
        'role': 'script',
        'written_by': ['agent', 'human'],
        'read_by': ['agent'],
        'description': 'Python 工具脚本（handoff_tidy/learn_tidy/startup_tidy 等）'
    },
    'memory/memory_main.md': {
        'role': 'global_memory',
        'written_by': ['agent'],
        'read_by': ['agent'],
        'description': '全局聚合记忆，按 ## {项目名} 分段'
    },
    'docs_rj/SUMMARY_RJ.md': {
        'role': 'project_summary',
        'written_by': ['agent'],
        'read_by': ['agent', 'human'],
        'description': '项目汇总视图，三触发自动更新'
    },
    'docs_rj/spec_rj/*.md': {
        'role': 'spec_doc',
        'written_by': ['agent'],
        'read_by': ['agent', 'human'],
        'description': '需求规格文档（PRD+Spec 层）'
    },
    'docs_rj/task_rj/*.md': {
        'role': 'task_doc',
        'written_by': ['agent'],
        'read_by': ['agent', 'human'],
        'description': '任务清单文档（含 GWT 验收标准）'
    }
}

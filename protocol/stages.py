"""stages.py - PDCA 阶段决策规则

13 条决策规则：7 条对齐 7 条铁律 + 6 条新增。
每条规则含 stage / gate / description。

GLOBAL_COMPANION_ABILITIES：skill 字段为概念能力名，非真实已装。
如 brainstorming/writing-plans 是概念，实际靠 agent 通用能力或按需搜专用 skill。
设计来源: SKILL.md §7条铁律 + §6 PDCA, references/common/pc/acceptance_criteria.md
"""

STAGE_DECISION_RULES = {
    # === 现有 7 条（对齐 7 条铁律） ===
    'memory_first': {
        'stage': 'plan',
        'gate': 'hard',
        'description': '启动先读全局 summary+memory 与项目 memory，不可跳'
    },
    'hard_gate': {
        'stage': 'plan',
        'gate': 'hard',
        'description': '动手前先呈现方案，等明确确认词再动手'
    },
    'process_first': {
        'stage': 'plan',
        'gate': 'hard',
        'description': '先判断走什么流程再行动，1%原则'
    },
    'no_placeholders': {
        'stage': 'do',
        'gate': 'hard',
        'description': '给完整代码/命令，禁止 TBD/TODO/伪代码'
    },
    'trigger_hooks': {
        'stage': 'do',
        'gate': 'hard',
        'description': '遇到触发关键词先读对应 reference 再动手'
    },
    'rollback_safety': {
        'stage': 'do',
        'gate': 'hard',
        'description': '动手改前必须确保工作区已 commit，改错可回溯'
    },
    'item_check': {
        'stage': 'check',
        'gate': 'hard',
        'description': '执行按 task.md 逐项打勾，验收对照 spec.md 逐条核对'
    },
    # === 新增 6 条 ===
    'file_fact_priority': {
        'stage': 'plan',
        'gate': 'hard',
        'description': '文件事实优先，DONE 由文件判定非对话'
    },
    'outcome_required': {
        'stage': 'act',
        'gate': 'hard',
        'description': '项目记忆 outcome 字段必填，不可省'
    },
    'spec_two_options': {
        'stage': 'plan',
        'gate': 'hard',
        'description': 'spec 必须含 2 方案对比，明确推荐'
    },
    'task_all_checked': {
        'stage': 'check',
        'gate': 'hard',
        'description': 'task 全打勾才能进下一阶段'
    },
    'high_cleared': {
        'stage': 'check',
        'gate': 'hard',
        'description': 'HIGH 问题清零才能验收（最多 3 轮）'
    },
    'act_summary_refresh': {
        'stage': 'act',
        'gate': 'hard',
        'description': 'act 阶段必须刷新 SUMMARY_RJ.md'
    }
}

# skill 字段为概念能力名，非真实已装。
# 如 brainstorming/writing-plans 是概念，实际靠 agent 通用能力或按需搜专用 skill。
GLOBAL_COMPANION_ABILITIES = {
    'brainstorming': {
        'skill': 'brainstorming',
        'purpose': '方案探索，产出 2-3 方案对比',
        'installed': False,
        'note': '概念能力名，agent 用通用能力顶上或按需搜索专用 skill'
    },
    'writing-plans': {
        'skill': 'writing-plans',
        'purpose': '生成实施计划 md，顶部带手绘图',
        'installed': False,
        'note': '概念能力名，agent 用通用能力顶上'
    }
}

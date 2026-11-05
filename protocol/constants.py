"""constants.py - 协议层核心常量

定义跨任务协议常量：铁律 ID / 三态 / 阶段 ID / 字段等级 / 字段来源。
借鉴业界 AI PM 协议实践，Python 版改造。
所有常量纯 PEP 8 大写命名，零第三方依赖。
设计来源: SKILL.md §8条铁律, references/common/da/sync-matrix.md
"""

# 8 条铁律 ID 列表（对齐 SKILL.md §8 条铁律）
IRON_RULE_IDS = [
    'memory_first',      # 铁律1：Memory First（启动必读+每对话必写）
    'hard_gate',         # 铁律2：HARD-GATE（动手前先呈现方案等确认）
    'process_first',     # 铁律3：流程优先（1%原则，先判断走什么流程）
    'no_placeholders',   # 铁律4：No Placeholders（完整代码/命令）
    'trigger_hooks',     # 铁律5：触发钩子（遇关键词先读 reference）
    'rollback_safety',   # 铁律6：回溯保障（改前 commit）
    'item_check',        # 铁律7：逐项核对（执行按 task 打勾，验收对照 spec）
    'lookup_first',      # 铁律8：先查再写（先读已有文档 + 先查已有实现）
]

# HARD-GATE 三态（pass=通过 / retry=重试 / mark_pending=标记待处理）
HARD_GATE_TRI_STATES = {
    'pass': 'pass',                  # 通过，进入下一阶段
    'retry': 'retry',                # 重试，要求重做
    'mark_pending': 'mark_pending',  # 标记待处理（人工介入）
}

# PDCA 4 环阶段 ID
STAGE_IDS = ['plan', 'do', 'check', 'act']

# 字段等级（含 FORBIDDEN 禁用等级）
FIELD_LEVELS = {
    'required': 'required',          # 必填
    'recommended': 'recommended',    # 推荐
    'optional': 'optional',          # 可选
    'forbidden': 'forbidden',        # 禁用（如平台记忆路径、硬编码本机路径）
}

# 字段来源（文件事实优先：file > dialogue > inferred）
FIELD_SOURCES = {
    'file': 'file',          # 从文件读取（优先级最高）
    'dialogue': 'dialogue',  # 来自对话
    'inferred': 'inferred',  # 推断
}

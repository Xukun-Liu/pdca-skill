#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
learn_tidy.py — riji-skill learn 子流程扫描器（Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5）
=============================================================

用途
----
对应 spec_rj/learn_cycle_spec_20260715_1437.md 的 REQ-001~REQ-004。
从 memory 中提炼可优化点，输出结构化 JSON 报告到 docs_rj/learn_rj/{timestamp}/scan_report.json。

设计参考：某开源项目的 harvest+mine 阶段（降维成纯 Python 扫描）。
- harvest：读 memory_main.md + 项目 memory_rj 采集使用经验
- mine：扫记忆找重复/冲突/过时/跨层漂移

核心原则：memory 是 learn 的唯一数据源。
非 memory 扫描（死引用/版本不一致/代码清理/规则审查）由其他工具负责：
- startup_tidy.py：启动时完整性检查（死引用/版本一致性）
- handoff_tidy.py：交接时清理（代码清理）
- adversarial_review.md：对抗性审查（规则审查）

Phase 1 新增特性：
- 增强 memory 条目格式支持（intent/context/tools_used/feedback_signals/outcome/tags）
- 旧格式迁移脚本（migrate 子命令）
- 向后兼容：同时支持新旧格式解析

技术约束
--------
* 仅使用 Python 标准库（os/sys/json/re/datetime/hashlib/argparse）。
* 复用 tidy_common.py 的 resolve_primary_docs。
* scan 只读+写报告，不改 live 文件（安全约束）。

退出码
-------
* 0 = 成功无异常
* 1 = 扫描出错（部分步骤失败，仍输出报告含 errors[]）
* 2 = 结构缺失（memory_main.md 不存在等）

运行方式
---------
  python scripts/learn_tidy.py scan [--dry-run] [--scope all|memory]
  python scripts/learn_tidy.py migrate [--dry-run]
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_data_path  # noqa: E402  用户数据外置：提供 get_docs_rj_path() / get_memory_main_path()
try:
    from tidy_common import resolve_primary_docs
except ImportError:
    def resolve_primary_docs(primary_docs_arg=None):
        candidate = str(user_data_path.get_docs_rj_path())
        return candidate if os.path.isdir(candidate) else None

try:
    from memory_shadow_write import write_project
except ImportError:
    def write_project(task, content, project_memory_dir=None, project_name=None,
                      intent="", context="", tools_used=None, feedback_signals=None,
                      outcome="unknown", tags=None):
        pass

# ===========================================================================
# 常量
# ===========================================================================

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_MAIN_PATH = str(user_data_path.get_memory_main_path())
MEMORY_ENTRY_RE = re.compile(
    r'^###\s*记忆条目\s*·\s*(.+?)（(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})）\s*$',
    re.MULTILINE
)
STALE_DAYS = 90
MEMORY_RJ_DIR = 'memory_rj'

# ===========================================================================
# 辅助函数
# ===========================================================================

def _read_text(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ''

def _write_text(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def _backup_file(src_path, backup_dir):
    if not os.path.exists(src_path):
        return None
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, os.path.basename(src_path) + '.bak')
    shutil.copy2(src_path, backup_path)
    return backup_path


def cmd_count(args):
    """轻量统计 memory_main.md 条目数，与阈值比较输出 JSON（learn_into_act v1.0.0 新增）

    Args:
        args: argparse Namespace，含 threshold(int)/memory_path(str)

    Returns:
        int: 退出码（0=成功，2=文件不存在）

    Outputs:
        JSON 到 stdout，含 total_entries/threshold/should_run/memory_path/warning(可选)/error(可选)
    """
    # M2-4 修复：threshold 负数处理
    threshold = args.threshold
    warning_msg = None
    if threshold < 0:
        threshold = 20
        warning_msg = "threshold 负数（%d），已用默认值 20" % args.threshold

    memory_path = args.memory_path if args.memory_path else MEMORY_MAIN_PATH
    if not os.path.exists(memory_path):
        print(json.dumps({
            "total_entries": 0,
            "threshold": threshold,
            "should_run": False,
            "memory_path": memory_path,
            "error": "memory_main.md not found"
        }, ensure_ascii=False, indent=2))
        return 2

    content = _read_text(memory_path)
    entries = MEMORY_ENTRY_RE.findall(content)
    total = len(entries)
    # H4 修复：total=0 时强制 should_run=false（即使 threshold=0），避免空跑
    should_run = total >= threshold and total > 0

    result = {
        "total_entries": total,
        "threshold": threshold,
        "should_run": should_run,
        "memory_path": memory_path
    }
    # H2 修复：total=0 但文件有内容 → 告警格式不匹配
    if total == 0 and len(content) > 0:
        result["warning"] = "memory_main.md 有内容但无匹配条目，请检查 MEMORY_ENTRY_RE 格式"
    # M2-4 修复：threshold 负数告警
    if warning_msg:
        result["warning"] = warning_msg

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ===========================================================================
# 数据结构（Phase 2：TaskRecord）
# ===========================================================================

class TaskRecord:
    """任务记录（从 memory 条目提取）
    
    字段说明：
        id: 唯一标识（基于 intent 的哈希）
        intent: 用户意图摘要
        context: 上下文信息
        tools_used: 使用的工具列表
        feedback_signals: 反馈信号列表
        outcome: 结果标签（success/fail/mixed/unknown）
        tags: 标签列表
        source_entries: 来源记忆条目列表（含任务名+时间戳）
        split: train/val（确定性划分）
    """
    
    def __init__(self, intent, context="", tools_used=None, feedback_signals=None,
                 outcome="unknown", tags=None, source_entries=None):
        self.intent = intent.strip()
        self.context = context.strip()
        self.tools_used = tools_used or []
        self.feedback_signals = feedback_signals or []
        self.outcome = outcome
        self.tags = tags or []
        self.source_entries = source_entries or []
        self.split = None
        
        # 生成唯一 ID（跨周期稳定）
        # intent 非空时用 intent，否则用 task+timestamp 组合
        id_base = self.intent
        if not id_base and self.source_entries:
            first_source = self.source_entries[0]
            task_name = first_source.get('task', '')
            timestamp = first_source.get('timestamp', '')
            id_base = f"{task_name}|{timestamp}"
        if not id_base:
            id_base = "unknown_task"
        self.id = hashlib.md5(id_base.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self):
        return {
            'id': self.id,
            'intent': self.intent,
            'context': self.context,
            'tools_used': self.tools_used,
            'feedback_signals': self.feedback_signals,
            'outcome': self.outcome,
            'tags': self.tags,
            'source_entries': self.source_entries,
            'split': self.split,
        }

class GateScore:
    """Gate 评分（memory 健康度评估）
    
    各维度评分范围：0-1（越高越好）
    综合评分：加权平均
    recommendation：accept/conditional/reject
    
    维度说明：
        conflict_quality: 冲突质量（无冲突=1，冲突越多越接近0）
        duplicate_quality: 重复质量（无重复=1，重复越多越接近0）
        stale_quality: 过时质量（无过时=1，过时越多越接近0）
        outcome_clarity: 结果清晰度（明确结果比例）
        split_coverage: 数据划分覆盖率（train/val 分布合理程度）
        layer_consistency: 跨层一致性（项目级与全局的一致性）
    """
    
    def __init__(self):
        self.conflict_quality = 0.0
        self.duplicate_quality = 0.0
        self.stale_quality = 0.0
        self.outcome_clarity = 0.0
        self.split_coverage = 0.0
        self.layer_consistency = 0.0
        self.overall = 0.0
        self.recommendation = "conditional"
    
    def calculate_overall(self):
        """计算综合评分（加权平均）"""
        weights = {
            'conflict_quality': 0.15,
            'duplicate_quality': 0.15,
            'stale_quality': 0.10,
            'outcome_clarity': 0.25,
            'split_coverage': 0.15,
            'layer_consistency': 0.20,
        }
        
        total_weight = sum(weights.values())
        self.overall = sum(
            getattr(self, key) * weights[key]
            for key in weights
        ) / total_weight
        
        # 根据综合评分确定 recommendation
        if self.overall >= 0.7:
            self.recommendation = "accept"
        elif self.overall >= 0.4:
            self.recommendation = "conditional"
        else:
            self.recommendation = "reject"
    
    def to_dict(self):
        return {
            'conflict_quality': round(self.conflict_quality, 4),
            'duplicate_quality': round(self.duplicate_quality, 4),
            'stale_quality': round(self.stale_quality, 4),
            'outcome_clarity': round(self.outcome_clarity, 4),
            'split_coverage': round(self.split_coverage, 4),
            'layer_consistency': round(self.layer_consistency, 4),
            'overall': round(self.overall, 4),
            'recommendation': self.recommendation,
        }

# ===========================================================================
# 学习状态机（Phase 5：LearnState）
# ===========================================================================

class LearnState:
    """learn 流程状态机（Phase 5）

    用于追踪 learn 子流程的状态迁移，确保流程单向推进、不允许回退。
    archived 视为终态；进入 archived 前必须至少有 1 条 adopted。

    状态迁移图：
        pending → scanning → proposing → adopting → archived
        （单向，不允许回退；adopting→archived 必须先有 adopted 列表）

    字段说明：
        state: 当前状态（pending/scanning/proposing/adopting/archived）
        task: 任务名（用于追踪与 manifest 记录）
        started_at: 启动时间 ISO 格式时间戳
        proposals: 建议列表（proposing 阶段后填充）
        adopted: 已采纳建议列表（adopting 阶段后填充）
        rejected: 已拒绝建议列表
        archived_path: 归档文件路径（archived 阶段后填充）
    """

    # 合法状态集合
    VALID_STATES = {'pending', 'scanning', 'proposing', 'adopting', 'archived'}

    # 合法迁移表（key: 当前状态，value: 可迁移到的状态集合）
    TRANSITIONS = {
        'pending': {'scanning'},
        'scanning': {'proposing'},
        'proposing': {'adopting'},
        'adopting': {'archived'},
    }

    def __init__(self, task: str):
        """初始化状态机

        参数：
            task: 任务名（用于追踪与 manifest 记录）
        """
        self.state = 'pending'
        self.task = task
        self.started_at = datetime.now().isoformat()
        self.proposals = []
        self.adopted = []
        self.rejected = []
        self.archived_path = ''

    def to_dict(self) -> dict:
        """序列化为 dict（用于写 manifest JSON）"""
        return {
            'state': self.state,
            'task': self.task,
            'started_at': self.started_at,
            'proposals': self.proposals,
            'adopted': self.adopted,
            'rejected': self.rejected,
            'archived_path': self.archived_path,
        }

    def is_terminal(self) -> bool:
        """判断是否为终态（archived 视为终态）"""
        return self.state == 'archived'

    def advance(self, new_state: str) -> None:
        """状态迁移（校验合法性）

        参数：
            new_state: 要迁移到的状态

        异常：
            ValueError:
                - new_state 不在合法状态集合中
                - 当前状态到 new_state 的迁移不合法（含回退）
                - new_state=='archived' 但 adopted 列表为空
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(
                '非法状态: %s（合法状态: %s）' % (new_state, sorted(self.VALID_STATES))
            )

        if self.state == 'archived':
            raise ValueError(
                '终态不可迁移: 当前 archived，不允许迁移到 %s' % new_state
            )

        allowed = self.TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                '非法迁移: %s → %s（合法迁移: %s → %s）'
                % (self.state, new_state, self.state, sorted(allowed))
            )

        # adopting → archived 必须先有 adopted 列表
        if new_state == 'archived' and len(self.adopted) == 0:
            raise ValueError(
                '迁移到 archived 失败: adopted 列表为空（必须至少采纳 1 条建议才能归档）'
            )

        self.state = new_state

# ===========================================================================
# 解析函数（支持新旧格式）
# ===========================================================================

def _parse_memory_entries(content, file_path=''):
    """解析 memory 条目，支持新旧格式。

    参数：
        content: str - memory 文件内容
        file_path: str - 文件路径（用于定位）

    新格式（增强版）：
    ### 记忆条目 · 任务名（YYYY-MM-DD HH:MM）
    **意图**：xxx
    **上下文**：xxx
    **工具**：xxx, xxx
    **反馈**：positive/negative/mixed/none
    **结果**：success/fail/mixed/unknown
    **标签**：xxx, xxx

    内容...

    旧格式（兼容）：
    ### 记忆条目 · 任务名（YYYY-MM-DD HH:MM）
    内容...

    返回：
        List[dict]: 包含 task, timestamp, content, hash, intent, context,
                    tools_used, feedback_signals, outcome, tags, file_path, line_number 字段
    """
    entries = []
    if not content:
        return entries
    lines = content.split('\n')
    current_entry = None
    current_lines = []
    start_line = 0

    for idx, line in enumerate(lines):
        match = MEMORY_ENTRY_RE.match(line)
        if match:
            if current_entry is not None:
                body = '\n'.join(current_lines).strip()
                current_entry['content'] = body
                current_entry['hash'] = hashlib.md5(body.encode('utf-8')).hexdigest()
                entries.append(current_entry)

            current_entry = {
                'task': match.group(1).strip(),
                'timestamp': match.group(2).strip(),
                'intent': '',
                'context': '',
                'tools_used': [],
                'feedback_signals': [],
                'outcome': 'unknown',
                'tags': [],
                # T003 新增：评估参数（与 write_project eval_frontmatter 对齐）
                'importance_level': 'medium',
                'is_lesson': False,
                'experience_tags': [],
                'file_path': file_path,
                'line_number': idx + 1,
            }
            start_line = idx + 1
            current_lines = []
        elif current_entry is not None:
            # 检查是否是元数据行（新格式）
            meta_match = re.match(r'^\*\*(意图|上下文|工具|反馈|结果|标签|重要性|是否经验|经验标签|状态|归档原因|反思)\*\*[:：]\s*(.+)$', line)
            if meta_match:
                key = meta_match.group(1)
                value = meta_match.group(2).strip()
                if key == '意图':
                    current_entry['intent'] = value
                elif key == '上下文':
                    current_entry['context'] = value
                elif key == '工具':
                    current_entry['tools_used'] = [t.strip() for t in value.split(',')] if value else []
                elif key == '反馈':
                    if value == 'none':
                        current_entry['feedback_signals'] = []
                    else:
                        current_entry['feedback_signals'] = [f.strip() for f in value.split(',')] if value else []
                elif key == '结果':
                    # 提取首词（success/fail/mixed/unknown），忽略括号内的详细说明
                    # 修复 outcome 提取 bug：原逻辑保留完整 value 字符串（如
                    # "success（validate_skill 31/31 PASS）"），导致 calculate_task_distributions
                    # 严格匹配 outcome_dist 字典 key 失败，gate_score.outcome_clarity 误报 0.0
                    outcome_word = value.split('（')[0].strip().lower()
                    if outcome_word in ('success', 'fail', 'mixed', 'unknown'):
                        current_entry['outcome'] = outcome_word
                    else:
                        current_entry['outcome'] = 'unknown'
                elif key == '标签':
                    current_entry['tags'] = [t.strip() for t in value.split(',')] if value else []
                # T003 新增：评估参数解析（与 write_project eval_frontmatter 对齐）
                elif key == '重要性':
                    if value in ('high', 'medium', 'low'):
                        current_entry['importance_level'] = value
                    else:
                        current_entry['importance_level'] = 'medium'
                elif key == '是否经验':
                    current_entry['is_lesson'] = value.lower() == 'true'
                elif key == '经验标签':
                    if value and value != '无':
                        current_entry['experience_tags'] = [t.strip() for t in value.split(',')]
                    else:
                        current_entry['experience_tags'] = []
                continue

            # 普通内容行
            current_lines.append(line)

    if current_entry is not None:
        body = '\n'.join(current_lines).strip()
        current_entry['content'] = body
        current_entry['hash'] = hashlib.md5(body.encode('utf-8')).hexdigest()
        entries.append(current_entry)

    return entries

# ===========================================================================
# 任务挖掘函数（Phase 2）
# ===========================================================================

def heuristic_mine(entries, *, max_tasks=40):
    """从 memory 条目中提取 TaskRecord（任务挖掘）
    
    过滤规则：
        1. intent 不能为空且长度 >= 8（旧格式降级：使用 content 前100字符作为 intent）
        2. 优先保留有明确 outcome 的任务（success > fail > mixed > unknown）
        3. 排除重复的 intent（同一文件内）
    
    参数：
        entries: List[dict] - 解析后的 memory 条目列表
        max_tasks: int - 最大任务数（默认40）
    
    返回：
        List[TaskRecord]
    """
    tasks = []
    seen_intents = set()
    
    # 按 outcome 明确程度排序（明确的优先）
    OUTCOME_PRIORITY = {'success': 4, 'fail': 3, 'mixed': 2, 'unknown': 1}
    sorted_entries = sorted(entries, key=lambda e: OUTCOME_PRIORITY.get(e.get('outcome', 'unknown'), 1), reverse=True)
    
    for entry in sorted_entries:
        intent = entry.get('intent', '').strip()
        
        # 降级策略：如果 intent 为空，使用 content 的前100字符作为 intent
        # 这是为了兼容旧格式迁移后的条目（没有 intent 字段）
        if not intent:
            content = entry.get('content', '').strip()
            if content:
                intent = content[:100].strip()
        
        # 过滤条件 1：intent 不能为空且长度 >= 8
        if not intent or len(intent) < 8:
            continue
        
        # 过滤条件 2：排除重复的 intent
        if intent in seen_intents:
            continue
        
        # 过滤条件 3：达到最大任务数时，只保留有明确结果的任务
        if len(tasks) >= max_tasks:
            current_outcome = entry.get('outcome', 'unknown')
            if current_outcome == 'unknown':
                continue
        
        # 创建 TaskRecord
        source_entry = {
            'task': entry.get('task', ''),
            'timestamp': entry.get('timestamp', ''),
        }
        
        task = TaskRecord(
            intent=intent,
            context=entry.get('context', ''),
            tools_used=entry.get('tools_used', []),
            feedback_signals=entry.get('feedback_signals', []),
            outcome=entry.get('outcome', 'unknown'),
            tags=entry.get('tags', []),
            source_entries=[source_entry],
        )
        
        tasks.append(task)
        seen_intents.add(intent)
        
        if len(tasks) >= max_tasks:
            break
    
    return tasks

def dedup_tasks(tasks):
    """合并相同 intent 的任务记录（去重冲突解决）
    
    冲突解决策略：
        - 同 intent 不同 outcome：优先保留更明确的 outcome（success > fail > mixed > unknown）
        - 同 intent 不同 context：合并 context（取并集，去重）
        - 同 intent 不同 tools_used：合并 tools_used（去重）
        - 同 intent 不同 source_entries：合并 source_entries（去重）
    
    参数：
        tasks: List[TaskRecord]
    
    返回：
        List[TaskRecord]
    """
    OUTCOME_PRIORITY = {'success': 4, 'fail': 3, 'mixed': 2, 'unknown': 1}
    
    # 按 intent 分组
    intent_groups = {}
    for task in tasks:
        if task.intent not in intent_groups:
            intent_groups[task.intent] = []
        intent_groups[task.intent].append(task)
    
    deduped = []
    for intent, group in intent_groups.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue
        
        # 合并同 intent 的多个任务记录
        # 1. 选择最明确的 outcome
        best_task = max(group, key=lambda t: OUTCOME_PRIORITY.get(t.outcome, 1))
        
        # 2. 合并 context（取并集）
        contexts = set()
        for t in group:
            if t.context:
                contexts.add(t.context)
        merged_context = '; '.join(contexts)
        
        # 3. 合并 tools_used（去重）
        tools_set = set()
        for t in group:
            tools_set.update(t.tools_used)
        merged_tools = sorted(list(tools_set))
        
        # 4. 合并 feedback_signals（去重）
        feedback_set = set()
        for t in group:
            feedback_set.update(t.feedback_signals)
        merged_feedback = sorted(list(feedback_set))
        
        # 5. 合并 tags（去重）
        tags_set = set()
        for t in group:
            tags_set.update(t.tags)
        merged_tags = sorted(list(tags_set))
        
        # 6. 合并 source_entries（去重）
        source_set = set()
        for t in group:
            for se in t.source_entries:
                key = f"{se['task']}|{se['timestamp']}"
                source_set.add(key)
        merged_sources = []
        for key in source_set:
            task_name, ts = key.split('|', 1)
            merged_sources.append({'task': task_name, 'timestamp': ts})
        
        # 创建合并后的任务记录
        merged_task = TaskRecord(
            intent=intent,
            context=merged_context,
            tools_used=merged_tools,
            feedback_signals=merged_feedback,
            outcome=best_task.outcome,
            tags=merged_tags,
            source_entries=merged_sources,
        )
        
        deduped.append(merged_task)
    
    return deduped

def assign_splits(tasks, *, val_fraction=0.34, seed=42):
    """确定性划分 train/val（固定哈希保证跨周期稳定性）
    
    稳定性保证：
        - 相同 task.id + 相同 seed → 相同 split（跨周期稳定）
        - 新增任务不会影响已有任务的 split（增量稳定）
        - seed 可配置，允许用户调整划分比例
    
    参数：
        tasks: List[TaskRecord]
        val_fraction: float - val 集比例（默认0.34）
        seed: int - 随机种子（默认42）
    
    返回：
        List[TaskRecord]（已分配 split）
    """
    val_cut = int(round(val_fraction * 100))
    
    for t in tasks:
        bucket = int(hashlib.sha256((str(seed) + t.id).encode()).hexdigest(), 16) % 100
        t.split = "val" if bucket < val_cut else "train"
    
    # 保证 val 非空（至少2个任务时）
    real_splits = {t.split for t in tasks}
    if len(tasks) >= 2 and "val" not in real_splits:
        tasks[-1].split = "val"
    
    # 保证 train 非空
    if not any(t.split == "train" for t in tasks) and len(tasks) >= 2:
        tasks[0].split = "train"
    
    return tasks

def calculate_task_distributions(tasks):
    """计算任务分布统计
    
    返回：
        dict: {
            'task_outcome_distribution': {success: N, fail: N, mixed: N, unknown: N},
            'task_split_distribution': {train: N, val: N},
            'total_tasks': N,
        }
    """
    outcome_dist = {'success': 0, 'fail': 0, 'mixed': 0, 'unknown': 0}
    split_dist = {'train': 0, 'val': 0}
    
    for t in tasks:
        outcome = t.outcome
        if outcome in outcome_dist:
            outcome_dist[outcome] += 1
        
        split = t.split
        if split in split_dist:
            split_dist[split] += 1
    
    return {
        'task_outcome_distribution': outcome_dist,
        'task_split_distribution': split_dist,
        'total_tasks': len(tasks),
    }

def calculate_gate_score(report):
    """计算 memory 健康度评分（Gate Score）
    
    参数：
        report: dict - scan() 生成的扫描报告
    
    返回：
        GateScore 对象
    """
    score = GateScore()
    
    # 1. conflict_quality（冲突质量）
    total_conflicts = len(report.get('memory_conflicts', []))
    proj_conflicts = len(report.get('project_memory_rj', {}).get('conflicts', []))
    total = total_conflicts + proj_conflicts
    if total == 0:
        score.conflict_quality = 1.0
    else:
        score.conflict_quality = max(0.0, 1.0 - total * 0.1)
    
    # 2. duplicate_quality（重复质量）
    total_duplicates = len(report.get('memory_duplicates', []))
    proj_duplicates = len(report.get('project_memory_rj', {}).get('duplicates', []))
    total = total_duplicates + proj_duplicates
    if total == 0:
        score.duplicate_quality = 1.0
    else:
        score.duplicate_quality = max(0.0, 1.0 - total * 0.1)
    
    # 3. stale_quality（过时质量）
    total_stale = len(report.get('memory_stale', []))
    proj_stale = len(report.get('project_memory_rj', {}).get('stale', []))
    total = total_stale + proj_stale
    if total == 0:
        score.stale_quality = 1.0
    else:
        score.stale_quality = max(0.0, 1.0 - total * 0.05)
    
    # 4. outcome_clarity（结果清晰度）
    outcome_dist = report.get('task_outcome_distribution', {})
    total_tasks = outcome_dist.get('success', 0) + outcome_dist.get('fail', 0) + \
                  outcome_dist.get('mixed', 0) + outcome_dist.get('unknown', 0)
    if total_tasks == 0:
        score.outcome_clarity = 0.5
    else:
        clear_count = outcome_dist.get('success', 0) + outcome_dist.get('fail', 0) + outcome_dist.get('mixed', 0)
        score.outcome_clarity = clear_count / total_tasks
    
    # 5. split_coverage（数据划分覆盖率）
    split_dist = report.get('task_split_distribution', {})
    train_count = split_dist.get('train', 0)
    val_count = split_dist.get('val', 0)
    total = train_count + val_count
    if total == 0:
        score.split_coverage = 0.5
    else:
        train_ratio = train_count / total
        target_ratio = 0.66
        deviation = abs(train_ratio - target_ratio)
        score.split_coverage = max(0.0, 1.0 - deviation * 3)
    
    # 6. layer_consistency（跨层一致性）
    layer_drift = report.get('memory_layer_drift', {})
    project_only = len(layer_drift.get('project_only', []))
    global_only = len(layer_drift.get('global_only', []))
    total_drift = project_only + global_only
    if total_drift == 0:
        score.layer_consistency = 1.0
    else:
        score.layer_consistency = max(0.0, 1.0 - total_drift * 0.15)
    
    # 计算综合评分
    score.calculate_overall()
    
    return score

# ===========================================================================
# 反思建议生成函数（Phase 4：reflect）
# ===========================================================================

def find_latest_scan_report(primary_docs):
    """找到最新的 scan_report.json
    
    参数：
        primary_docs: str - 主 docs 目录路径
    
    返回：
        str: scan_report.json 的完整路径，未找到返回 None
    """
    learn_rj_dir = os.path.join(primary_docs, 'learn_rj')
    if not os.path.isdir(learn_rj_dir):
        return None
    
    try:
        timestamp_dirs = [d for d in os.listdir(learn_rj_dir) 
                          if os.path.isdir(os.path.join(learn_rj_dir, d))]
        if not timestamp_dirs:
            return None
        
        latest_dir = max(timestamp_dirs)
        scan_report_path = os.path.join(learn_rj_dir, latest_dir, 'scan_report.json')
        
        if os.path.exists(scan_report_path):
            return scan_report_path
        return None
    except Exception:
        return None

def generate_proposals(scan_report_path):
    """生成建议清单（机械类建议自动生成，语义类建议留占位符）
    
    参数：
        scan_report_path: str - scan_report.json 的路径
    
    返回：
        dict: {
            'proposals': [建议列表],
            'semantic_placeholders': [语义类建议占位符列表],
            'staging_dir': 暂存目录路径,
        }
    """
    try:
        with open(scan_report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        return {'proposals': [], 'semantic_placeholders': [], 'staging_dir': '', 'error': str(e)}
    
    proposals = []
    proposal_num = 1
    
    # 暂存目录路径（与 scan_report 同目录）
    staging_dir = os.path.dirname(scan_report_path)
    
    # ── 机械类建议：内容层（确定性操作）──
    
    # 1. 删除重复记忆
    duplicates = report.get('memory_duplicates', [])
    for dup in duplicates:
        proposals.append({
            'number': proposal_num,
            'action': 'delete',
            'target': 'memory',
            'location': dup.get('location', ''),
            'content': dup.get('content', '')[:200],
            'rationale': f"发现重复记忆：{dup.get('hash', '')[:8]}，保留主条目，删除重复",
        })
        proposal_num += 1
    
    # 2. 删除项目级重复记忆
    proj_duplicates = report.get('project_memory_rj', {}).get('duplicates', [])
    for dup in proj_duplicates:
        proposals.append({
            'number': proposal_num,
            'action': 'delete',
            'target': 'project_memory_rj',
            'location': dup.get('location', ''),
            'content': dup.get('content', '')[:200],
            'rationale': f"发现项目级重复记忆，保留主条目，删除重复",
        })
        proposal_num += 1
    
    # 3. 修复冲突记忆（标记冲突，需人工确认）
    conflicts = report.get('memory_conflicts', [])
    for conf in conflicts:
        proposals.append({
            'number': proposal_num,
            'action': 'review',
            'target': 'memory',
            'location': conf.get('location', ''),
            'content': f"任务: {conf.get('task', '')}, 冲突数量: {conf.get('count', 0)}",
            'rationale': f"发现冲突记忆：任务 {conf.get('task', '')} 有 {conf.get('count', 0)} 个不同版本，需人工审查确认正确版本",
        })
        proposal_num += 1
    
    # 4. 删除过时记忆（超过90天未被引用）
    stale = report.get('memory_stale', [])
    for s in stale:
        proposals.append({
            'number': proposal_num,
            'action': 'delete',
            'target': 'memory',
            'location': s.get('location', ''),
            'content': s.get('content', '')[:200],
            'rationale': f"发现过时记忆：时间戳 {s.get('timestamp', '')}，超过90天且未被引用",
        })
        proposal_num += 1
    
    # 5. 删除项目级过时记忆
    proj_stale = report.get('project_memory_rj', {}).get('stale', [])
    for s in proj_stale:
        proposals.append({
            'number': proposal_num,
            'action': 'delete',
            'target': 'project_memory_rj',
            'location': s.get('location', ''),
            'content': s.get('content', '')[:200],
            'rationale': f"发现项目级过时记忆，超过90天且未被引用",
        })
        proposal_num += 1
    
    # 6. 修复跨层漂移（全局漏写或项目级漏写）
    layer_drift = report.get('memory_layer_drift', {})
    project_only = layer_drift.get('project_only', [])
    global_only = layer_drift.get('global_only', [])
    
    if project_only:
        proposals.append({
            'number': proposal_num,
            'action': 'sync',
            'target': 'memory_main.md',
            'location': 'memory_main.md',
            'content': f"需要同步 {len(project_only)} 条项目级记忆到全局",
            'rationale': f"发现 {len(project_only)} 条记忆只存在于项目级 memory_rj，需同步到全局 memory_main.md",
        })
        proposal_num += 1
    
    if global_only:
        proposals.append({
            'number': proposal_num,
            'action': 'sync',
            'target': 'project_memory_rj',
            'location': 'project_memory_rj',
            'content': f"需要同步 {len(global_only)} 条全局记忆到项目级",
            'rationale': f"发现 {len(global_only)} 条记忆只存在于全局 memory_main.md，需同步到项目级 memory_rj",
        })
        proposal_num += 1
    
    # ── 语义类建议占位符（规则层，需 agent 填充）──
    
    semantic_placeholders = [
        {
            'number': proposal_num,
            'category': '规则层',
            'item': '绝对规则过多',
            'description': 'ALWAYS/NEVER/must/only 统计，判断类应改决策规则',
            'evidence_field': 'prompt_metrics.absolute_terms',
            'openai_principle': '原则2',
            'action': 'replace',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
        {
            'number': proposal_num + 1,
            'category': '规则层',
            'item': '规则重复',
            'description': '同一规则在 SKILL.md/references 重述≥3次，应合并',
            'evidence_field': 'prompt_metrics.rule_repetitions',
            'openai_principle': '原则1',
            'action': 'replace',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
        {
            'number': proposal_num + 2,
            'category': '规则层',
            'item': '密度过高',
            'description': '【硬性】标记平均每<15行一个，考虑降级为弹性指引',
            'evidence_field': 'prompt_metrics.hardmark_density',
            'openai_principle': '原则1',
            'action': 'replace',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
        {
            'number': proposal_num + 3,
            'category': '规则层',
            'item': '过程指令>结果描述',
            'description': '过程指令是结果指令2倍以上，应改结果优先',
            'evidence_field': 'prompt_metrics.process_vs_outcome',
            'openai_principle': '原则2',
            'action': 'replace',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
        {
            'number': proposal_num + 4,
            'category': '规则层',
            'item': '缺停止条件',
            'description': '流程无"何时停/何时问/何时降级"',
            'evidence_field': '无（agent 判断）',
            'openai_principle': '原则2+8',
            'action': 'add',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
        {
            'number': proposal_num + 5,
            'category': '规则层',
            'item': '安全本地动作未命名',
            'description': '未明确"读取/检查/测试=安全，不需确认"',
            'evidence_field': '无（agent 判断）',
            'openai_principle': '原则4',
            'action': 'add',
            'note': '【需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后填充】',
        },
    ]
    
    return {
        'proposals': proposals,
        'semantic_placeholders': semantic_placeholders,
        'staging_dir': staging_dir,
        'scan_report': report,
    }

def write_proposals_md(result):
    """将建议清单写入 proposals.md
    
    参数：
        result: dict - generate_proposals() 的返回值
    
    返回：
        str: proposals.md 的路径
    """
    staging_dir = result.get('staging_dir', '')
    if not staging_dir:
        return ''
    
    proposals = result.get('proposals', [])
    semantic_placeholders = result.get('semantic_placeholders', [])
    scan_report = result.get('scan_report', {})
    
    timestamp = scan_report.get('timestamp', '')
    
    content_lines = []
    content_lines.append(f'# learn 建议清单 — {timestamp}')
    content_lines.append('')
    content_lines.append('> PDCA 标签：A.learn')
    content_lines.append('> 生成方式：learn_tidy.py reflect（机械类自动生成 + 语义类占位符）')
    content_lines.append('')
    content_lines.append('## 扫描概览')
    content_lines.append('')
    gate_score = scan_report.get('gate_score', {})
    content_lines.append(f'- 综合评分：{gate_score.get("overall", 0.0):.4f}')
    content_lines.append(f'- 推荐等级：{gate_score.get("recommendation", "conditional")}')
    content_lines.append(f'- 总任务数：{scan_report.get("total_tasks", 0)}')
    content_lines.append('')
    
    # 机械类建议
    content_lines.append('## 一、机械类建议（自动生成，可直接执行）')
    content_lines.append('')
    if proposals:
        for p in proposals:
            content_lines.append(f'### 建议 #{p["number"]}')
            content_lines.append('')
            content_lines.append(f'- **操作类型**：{p["action"]}')
            content_lines.append(f'- **目标**：{p["target"]}')
            content_lines.append(f'- **位置**：{p["location"]}')
            content_lines.append(f'- **内容预览**：{p["content"]}')
            content_lines.append(f'- **理由**：{p["rationale"]}')
            content_lines.append('')
            content_lines.append('---')
            content_lines.append('')
    else:
        content_lines.append('暂无机械类建议。')
        content_lines.append('')
    
    # 语义类建议占位符
    content_lines.append('## 二、语义类建议（需 agent 填充）')
    content_lines.append('')
    content_lines.append('> 【注意】以下建议需 agent 读 learn_cycle.md §2.2 + prompt_optimization.md 后，')
    content_lines.append('> 根据实际情况填充具体内容。')
    content_lines.append('')
    for p in semantic_placeholders:
        content_lines.append(f'### 建议 #{p["number"]}（{p["item"]}）')
        content_lines.append('')
        content_lines.append(f'- **分类**：{p["category"]}')
        content_lines.append(f'- **操作类型**：{p["action"]}')
        content_lines.append(f'- **说明**：{p["description"]}')
        content_lines.append(f'- **证据字段**：{p["evidence_field"]}')
        content_lines.append(f'- **OpenAI 原则**：{p["openai_principle"]}')
        content_lines.append(f'- **备注**：{p["note"]}')
        content_lines.append('')
        content_lines.append('  ```')
        content_lines.append('  【待填充】具体修改内容')
        content_lines.append('  ```')
        content_lines.append('')
        content_lines.append('---')
        content_lines.append('')
    
    # 底部提示
    content_lines.append('## 下一步')
    content_lines.append('')
    content_lines.append('1. agent 读 prompt_optimization.md 后填充语义类建议')
    content_lines.append('2. HARD-GATE 确认后执行 adopt')
    content_lines.append('')
    
    proposals_path = os.path.join(staging_dir, 'proposals.md')
    _write_text(proposals_path, '\n'.join(content_lines))
    
    return proposals_path

def find_latest_proposals(primary_docs):
    """找到最新的 proposals.md
    
    参数：
        primary_docs: str - 主 docs 目录路径
    
    返回：
        str: proposals.md 的完整路径，未找到返回 None
    """
    learn_rj_dir = os.path.join(primary_docs, 'learn_rj')
    if not os.path.isdir(learn_rj_dir):
        return None
    
    try:
        timestamp_dirs = [d for d in os.listdir(learn_rj_dir) 
                          if os.path.isdir(os.path.join(learn_rj_dir, d))]
        if not timestamp_dirs:
            return None
        
        latest_dir = max(timestamp_dirs)
        proposals_path = os.path.join(learn_rj_dir, latest_dir, 'proposals.md')
        
        if os.path.exists(proposals_path):
            return proposals_path
        return None
    except Exception:
        return None

def adopt(proposals_path, dry_run=True):
    """执行 adopt（半自动模式：备份+生成操作清单，实际修改由 agent 执行）
    
    参数：
        proposals_path: str - proposals.md 的路径
        dry_run: bool - 是否预览模式
    
    返回：
        dict: {
            'backup_dir': 备份目录路径,
            'action_list': 操作清单,
            'skipped_semantic': 跳过的语义类建议数量,
            'dry_run': 是否预览模式,
            'errors': 错误列表,
        }
    """
    try:
        proposals_content = _read_text(proposals_path)
    except Exception as e:
        return {'backup_dir': '', 'action_list': [], 'skipped_semantic': 0, 
                'dry_run': dry_run, 'errors': [str(e)]}
    
    staging_dir = os.path.dirname(proposals_path)
    backup_dir = os.path.join(staging_dir, 'backup')
    
    # 创建备份目录
    if not dry_run:
        os.makedirs(backup_dir, exist_ok=True)
    
    action_list = []
    skipped_semantic = 0
    result_errors = []
    
    # 解析 proposals.md，提取机械类建议（一、机械类建议）
    lines = proposals_content.split('\n')
    in_mechanical = False
    current_proposal = None
    
    for i, line in enumerate(lines):
        if '## 一、机械类建议' in line:
            in_mechanical = True
            continue
        if in_mechanical and ('## 二、语义类建议' in line or '## 下一步' in line):
            in_mechanical = False
            continue
        if not in_mechanical:
            continue
        
        if line.startswith('### 建议 #'):
            if current_proposal:
                action_list.append(current_proposal)
            current_proposal = {'number': '', 'action': '', 'target': '', 'location': '', 'content': '', 'rationale': ''}
            current_proposal['number'] = line.replace('### 建议 #', '').strip()
        elif current_proposal and line.startswith('- **操作类型**：'):
            current_proposal['action'] = line.replace('- **操作类型**：', '').strip()
        elif current_proposal and line.startswith('- **目标**：'):
            current_proposal['target'] = line.replace('- **目标**：', '').strip()
        elif current_proposal and line.startswith('- **位置**：'):
            current_proposal['location'] = line.replace('- **位置**：', '').strip()
        elif current_proposal and line.startswith('- **内容预览**：'):
            current_proposal['content'] = line.replace('- **内容预览**：', '').strip()
        elif current_proposal and line.startswith('- **理由**：'):
            current_proposal['rationale'] = line.replace('- **理由**：', '').strip()
    
    if current_proposal:
        action_list.append(current_proposal)
    
    # 统计跳过的语义类建议
    if '## 二、语义类建议' in proposals_content:
        semantic_section = proposals_content.split('## 二、语义类建议')[1]
        skipped_semantic = semantic_section.count('### 建议 #')
    
    # 备份受影响文件（半自动：先备份，实际修改由 agent 执行）
    backed_up_files = []
    for action in action_list:
        target = action.get('target', '')
        if target == 'memory':
            files_to_backup = [MEMORY_MAIN_PATH]
        elif target == 'project_memory_rj':
            memory_rj_dir = os.path.join(os.path.dirname(staging_dir), 'memory_rj')
            if os.path.isdir(memory_rj_dir):
                files_to_backup = [os.path.join(memory_rj_dir, f) 
                                  for f in os.listdir(memory_rj_dir) if f.endswith('.md')]
            else:
                files_to_backup = []
        elif target == 'memory_main.md':
            files_to_backup = [MEMORY_MAIN_PATH]
        elif target == 'project_memory_rj':
            memory_rj_dir = os.path.join(os.path.dirname(staging_dir), 'memory_rj')
            files_to_backup = [os.path.join(memory_rj_dir, f) 
                              for f in os.listdir(memory_rj_dir) if f.endswith('.md')] if os.path.isdir(memory_rj_dir) else []
        else:
            files_to_backup = []
        
        for fpath in files_to_backup:
                if os.path.exists(fpath) and fpath not in backed_up_files:
                    backed_up_files.append(fpath)
                    if not dry_run:
                        import shutil
                        shutil.copy2(fpath, os.path.join(backup_dir, os.path.basename(fpath)))
    
    # 写 memory + 刷新 SUMMARY（PDCA 闭环）
    if not dry_run:
        try:
            # 写 learn 产出到 memory
            memory_content = f"learn adopt 执行完成\n\n操作清单:\n"
            for action in action_list:
                memory_content += f"- #{action['number']}: {action['action']} {action['target']}\n"
            memory_content += f"\n跳过语义类建议: {skipped_semantic} 条\n"
            memory_content += f"备份目录: {backup_dir}\n"
            
            write_project(
                task='learn_cycle',
                content=memory_content,
                intent="执行 learn adopt，应用建议清单",
                context=f"staging_dir={staging_dir}",
                tools_used=["learn_tidy.py adopt"],
                outcome="success",
                tags=["learn", "adopt", "memory_cleanup"],
            )
            
            # 刷新 SUMMARY_RJ.md（简化版本：重新写入包含 learn_rj 的索引）
            summary_path = os.path.join(os.path.dirname(staging_dir), 'SUMMARY_RJ.md')
            if os.path.exists(summary_path):
                summary_content = _read_text(summary_path)
                if 'learn_rj' not in summary_content:
                    summary_content += f"\n- [learn 报告](learn_rj/{os.path.basename(staging_dir)}/proposals.md)\n"
                    _write_text(summary_path, summary_content)
        except Exception as e:
            result_errors.append(f"写 memory/SUMMARY 失败: {str(e)}")
    
    return {
        'backup_dir': backup_dir,
        'action_list': action_list,
        'skipped_semantic': skipped_semantic,
        'backed_up_files': backed_up_files,
        'dry_run': dry_run,
        'errors': result_errors,
    }

# ===========================================================================
# 扫描函数
# ===========================================================================

def scan_memory_duplicates(entries):
    hash_map = {}
    for e in entries:
        h = e['hash']
        if h not in hash_map:
            hash_map[h] = []
        hash_map[h].append({
            'task': e['task'],
            'timestamp': e['timestamp'],
            'file_path': e.get('file_path', ''),
            'line_number': e.get('line_number', 0),
        })
    duplicates = []
    for h, items in hash_map.items():
        if len(items) > 1:
            duplicates.append({
                'hash': h,
                'count': len(items),
                'entries': items,
                'location': items[0].get('file_path', '') + ':' + str(items[0].get('line_number', 0)),
                'content': next((e.get('content', '')[:200] for e in entries if e['hash'] == h), ''),
            })
    return duplicates

def scan_memory_conflicts(entries):
    task_map = {}
    for e in entries:
        t = e['task']
        if t not in task_map:
            task_map[t] = []
        task_map[t].append({
            'timestamp': e['timestamp'],
            'hash': e['hash'],
            'file_path': e.get('file_path', ''),
            'line_number': e.get('line_number', 0),
        })
    conflicts = []
    for t, items in task_map.items():
        unique_hashes = set(i['hash'] for i in items)
        if len(unique_hashes) > 1:
            conflicts.append({
                'topic': t,
                'entries': items,
                'location': items[0].get('file_path', '') + ':' + str(items[0].get('line_number', 0)),
                'count': len(unique_hashes),
            })
    return conflicts

def scan_memory_stale(entries, now=None):
    if now is None:
        now = datetime.now()
    stale = []
    for e in entries:
        try:
            ts = datetime.strptime(e['timestamp'], '%Y-%m-%d %H:%M')
        except ValueError:
            continue
        age_days = (now - ts).days
        if age_days > STALE_DAYS:
            stale.append({
                'task': e['task'],
                'timestamp': e['timestamp'],
                'age_days': age_days,
                'content': e.get('content', '')[:200],
            })
    return stale

def scan_project_memory_rj(primary_docs):
    if not primary_docs:
        return {'duplicates': [], 'conflicts': [], 'stale': [], 'files': []}

    memory_rj_path = os.path.join(primary_docs, MEMORY_RJ_DIR)
    if not os.path.isdir(memory_rj_path):
        return {'duplicates': [], 'conflicts': [], 'stale': [], 'files': []}

    all_entries = []
    file_list = []

    for f in sorted(os.listdir(memory_rj_path)):
        if not f.endswith('.md'):
            continue
        file_path = os.path.join(memory_rj_path, f)
        file_list.append(f)
        content = _read_text(file_path)
        entries = _parse_memory_entries(content, file_path)
        all_entries.extend(entries)

    now = datetime.now()
    return {
        'duplicates': scan_memory_duplicates(all_entries),
        'conflicts': scan_memory_conflicts(all_entries),
        'stale': scan_memory_stale(all_entries, now),
        'files': file_list,
    }

def scan_memory_layer_drift(primary_docs, project_name=None):
    if not primary_docs:
        return {'project_only': [], 'global_only': [], 'project_total': 0, 'global_total': 0}

    memory_rj_path = os.path.join(primary_docs, MEMORY_RJ_DIR)
    if not os.path.isdir(memory_rj_path):
        return {'project_only': [], 'global_only': [], 'project_total': 0, 'global_total': 0}

    project_name = project_name or os.path.basename(os.getcwd())

    project_entries = {}
    for f in sorted(os.listdir(memory_rj_path)):
        if not f.endswith('.md'):
            continue
        file_path = os.path.join(memory_rj_path, f)
        content = _read_text(file_path)
        entries = _parse_memory_entries(content, file_path)
        for e in entries:
            key = e.get('task', '') + '|' + e.get('timestamp', '')
            project_entries[key] = {'task': e['task'], 'timestamp': e['timestamp'], 'source': 'memory_rj/' + f}

    global_entries = {}
    memory_content = _read_text(MEMORY_MAIN_PATH)
    if memory_content:
        lines = memory_content.split('\n')
        heading = '## %s' % project_name
        in_section = False
        current_entry = None
        current_lines = []
        for line in lines:
            if line.rstrip('\n') == heading:
                in_section = True
                continue
            if in_section and line.startswith('## ') and line.rstrip('\n') != heading:
                break
            if in_section:
                match = MEMORY_ENTRY_RE.match(line)
                if match:
                    if current_entry is not None:
                        key = current_entry['task'] + '|' + current_entry['timestamp']
                        global_entries[key] = {'task': current_entry['task'], 'timestamp': current_entry['timestamp'], 'source': 'memory_main.md'}
                    current_entry = {
                        'task': match.group(1).strip(),
                        'timestamp': match.group(2).strip(),
                    }
                    current_lines = []
                elif current_entry is not None:
                    current_lines.append(line)
        if current_entry is not None:
            key = current_entry['task'] + '|' + current_entry['timestamp']
            global_entries[key] = {'task': current_entry['task'], 'timestamp': current_entry['timestamp'], 'source': 'memory_main.md'}

    project_keys = set(project_entries.keys())
    global_keys = set(global_entries.keys())

    project_only = [project_entries[k] for k in project_keys - global_keys]
    global_only = [global_entries[k] for k in global_keys - project_keys]

    return {
        'project_only': project_only,
        'global_only': global_only,
        'project_total': len(project_entries),
        'global_total': len(global_entries),
    }

# ===========================================================================
# 迁移函数（Phase 1）
# ===========================================================================

def _is_old_format(content):
    """检测内容是否为旧格式（不含元数据字段）"""
    if '**意图**：' in content and '**结果**：' in content:
        return False
    return MEMORY_ENTRY_RE.search(content) is not None

def _migrate_entry_to_new_format(entry):
    """将单个条目转换为新格式"""
    lines = []
    lines.append('### 记忆条目 · %s（%s）' % (entry['task'], entry['timestamp']))
    if entry.get('intent'):
        lines.append('**意图**：%s' % entry['intent'])
    if entry.get('context'):
        lines.append('**上下文**：%s' % entry['context'])
    if entry.get('tools_used'):
        lines.append('**工具**：%s' % ', '.join(entry['tools_used']))
    if entry.get('feedback_signals'):
        lines.append('**反馈**：%s' % ', '.join(entry['feedback_signals']))
    else:
        lines.append('**反馈**：none')
    lines.append('**结果**：%s' % entry.get('outcome', 'unknown'))
    if entry.get('tags'):
        lines.append('**标签**：%s' % ', '.join(entry['tags']))
    lines.append('')
    if entry.get('content'):
        lines.append(entry['content'])
    return '\n'.join(lines)

def migrate_memory_entries(primary_docs, dry_run=True):
    """迁移旧格式 memory 条目到新格式

    参数：
        primary_docs: 主 docs 目录路径
        dry_run: True 只预览，不实际修改

    返回：
        dict: {'migrated': int, 'skipped': int, 'errors': List[str]}
    """
    result = {'migrated': 0, 'skipped': 0, 'errors': []}

    if not primary_docs:
        result['errors'].append('primary_docs 未解析，无法迁移')
        return result

    memory_rj_path = os.path.join(primary_docs, MEMORY_RJ_DIR)
    if not os.path.isdir(memory_rj_path):
        result['errors'].append('memory_rj 目录不存在: %s' % memory_rj_path)
        return result

    backup_dir = os.path.join(memory_rj_path, 'backup_migrate')

    for f in sorted(os.listdir(memory_rj_path)):
        if not f.endswith('.md'):
            continue

        file_path = os.path.join(memory_rj_path, f)
        content = _read_text(file_path)

        if not _is_old_format(content):
            result['skipped'] += 1
            continue

        entries = _parse_memory_entries(content, file_path)
        if not entries:
            result['skipped'] += 1
            continue

        new_entries = [_migrate_entry_to_new_format(e) for e in entries]
        new_content = '\n\n'.join(new_entries) + '\n'

        print('  %s: %d 条条目需要迁移' % (f, len(entries)))

        if not dry_run:
            try:
                backup_path = _backup_file(file_path, backup_dir)
                print('       → 备份到: %s' % backup_path)
                _write_text(file_path, new_content)
                result['migrated'] += 1
            except Exception as e:
                result['errors'].append('迁移文件 %s 失败: %s' % (f, str(e)))
        else:
            result['migrated'] += 1

    return result

# ===========================================================================
# 主扫描函数
# ===========================================================================

def scan_prompt_metrics(skill_root):
    """扫描 SKILL.md + references/ 统计 prompt_metrics 字段【learn_cycle 20260723-102312 建议 #3】

    对应 prompt_optimization.md §3 的 4 个字段：
    - absolute_terms: 绝对化词汇计数（ALWAYS/永远/必须/NEVER/永不/禁止）
    - rule_repetitions: 规则重复（同一规则在≥3个文件出现）
    - hardmark_density: 【硬性】标记密度
    - process_vs_outcome: 过程指令 vs 结果描述比例

    Args:
        skill_root: str - skill 根目录路径

    Returns:
        dict: prompt_metrics 字段
    """
    import re as _re

    # 收集 SKILL.md + references/*.md 内容（递归遍历子目录，key 用 POSIX 风格）
    md_files = {}
    skill_md_path = os.path.join(skill_root, 'SKILL.md')
    if os.path.isfile(skill_md_path):
        md_files['SKILL.md'] = _read_text(skill_md_path) or ''
    refs_dir = os.path.join(skill_root, 'references')
    if os.path.isdir(refs_dir):
        for root, dirs, files in os.walk(refs_dir):
            for f in sorted(files):
                if f.endswith('.md'):
                    rel = os.path.relpath(os.path.join(root, f), refs_dir)
                    rel_posix = rel.replace(os.sep, '/')
                    md_files['references/' + rel_posix] = _read_text(os.path.join(root, f)) or ''

    all_content = '\n'.join(md_files.values())
    total_lines = all_content.count('\n') + 1

    # 1. absolute_terms: 绝对化词汇计数
    absolute_terms = {
        'total': 0,
        'by_term': {
            'ALWAYS': {'count': 0, 'terms': ['ALWAYS', '永远', '必须']},
            'NEVER': {'count': 0, 'terms': ['NEVER', '永不', '禁止']},
        },
    }
    for info in absolute_terms['by_term'].values():
        for term in info['terms']:
            if term.isascii():
                info['count'] += len(_re.findall(r'\b' + _re.escape(term) + r'\b', all_content))
            else:
                info['count'] += all_content.count(term)
        absolute_terms['total'] += info['count']

    # 2. rule_repetitions: 规则重复（同一规则在≥3个文件出现）
    rule_phrases = [
        'HARD-GATE', 'Memory First', 'No Placeholders',
        '报错询问机制', '逐项核对', '回溯保障',
    ]
    rule_repetitions = []
    for phrase in rule_phrases:
        file_count = sum(1 for content in md_files.values() if phrase in content)
        if file_count >= 3:
            rule_repetitions.append({
                'phrase': phrase,
                'count': file_count,
                'files': [f for f, c in md_files.items() if phrase in c],
            })

    # 3. hardmark_density: 【硬性】标记密度
    hardmark_count = all_content.count('【硬性】') + all_content.count('【硬规则】')
    hardmark_density = {
        'total': hardmark_count,
        'total_lines': total_lines,
        'density_per_lines': round(total_lines / hardmark_count, 1) if hardmark_count > 0 else 0,
    }

    # 4. process_vs_outcome: 过程指令 vs 结果描述比例
    process_terms = ['先', '再', '然后', '步骤', '第一步', '动手前', '执行前']
    outcome_terms = ['必须含', '产出必须', '完成标志', '产出物', '结果']
    process_count = sum(all_content.count(t) for t in process_terms)
    outcome_count = sum(all_content.count(t) for t in outcome_terms)
    process_vs_outcome = {
        'process_count': process_count,
        'outcome_count': outcome_count,
        'ratio': round(process_count / outcome_count, 2) if outcome_count > 0 else 0,
    }

    return {
        'absolute_terms': absolute_terms,
        'rule_repetitions': rule_repetitions,
        'hardmark_density': hardmark_density,
        'process_vs_outcome': process_vs_outcome,
    }


def scan(scope='all', dry_run=True, memory_path=None):
    """扫描 memory 输出 JSON 报告。

    参数：
        scope: all|memory（两者等价，all 为向后兼容）
        dry_run: True 只输出报告不改任何文件
        memory_path: 自定义 memory 文件路径（测试用，默认用 MEMORY_MAIN_PATH）

    返回：
        dict: 扫描报告
    """
    actual_memory_path = memory_path if memory_path else MEMORY_MAIN_PATH
    primary_docs = resolve_primary_docs()
    report = {
        'timestamp': datetime.now().strftime('%Y%m%d-%H%M%S'),
        'scope': scope,
        'primary_docs': primary_docs,
        'errors': [],
    }

    structure_missing = False

    # ── 全局 memory_main.md 扫描 ──────────────────────────────────────
    try:
        memory_content = _read_text(actual_memory_path)
        if not memory_content:
            report['errors'].append({
                'step': 'memory_scan',
                'error': 'memory_main.md 不存在或为空: %s' % actual_memory_path,
            })
            report['memory_duplicates'] = []
            report['memory_conflicts'] = []
            report['memory_stale'] = []
            structure_missing = True
        else:
            entries = _parse_memory_entries(memory_content, actual_memory_path)
            report['memory_duplicates'] = scan_memory_duplicates(entries)
            report['memory_conflicts'] = scan_memory_conflicts(entries)
            report['memory_stale'] = scan_memory_stale(entries)
    except Exception as e:
        report['errors'].append({'step': 'memory_scan', 'error': str(e)})
        report['memory_duplicates'] = []
        report['memory_conflicts'] = []
        report['memory_stale'] = []

    # ── 项目级 memory_rj 扫描 ────────────────────────────────────────
    try:
        report['project_memory_rj'] = scan_project_memory_rj(primary_docs)
    except Exception as e:
        report['errors'].append({'step': 'project_memory_scan', 'error': str(e)})
        report['project_memory_rj'] = {'duplicates': [], 'conflicts': [], 'stale': [], 'files': []}

    # ── 跨层一致性扫描（memory_rj ↔ memory_main.md）──────────────────
    try:
        report['memory_layer_drift'] = scan_memory_layer_drift(primary_docs)
    except Exception as e:
        report['errors'].append({'step': 'memory_layer_drift_scan', 'error': str(e)})
        report['memory_layer_drift'] = {'project_only': [], 'global_only': [], 'project_total': 0, 'global_total': 0}

    # ── 任务挖掘（Phase 2：mine）─────────────────────────────────────
    try:
        # 收集所有 memory 条目（全局 + 项目级）
        all_entries = []
        
        # 从全局 memory_main.md 收集
        memory_content = _read_text(actual_memory_path)
        if memory_content:
            global_entries = _parse_memory_entries(memory_content, actual_memory_path)
            all_entries.extend(global_entries)
        
        # 从项目级 memory_rj 收集
        if primary_docs:
            memory_rj_path = os.path.join(primary_docs, MEMORY_RJ_DIR)
            if os.path.isdir(memory_rj_path):
                for f in sorted(os.listdir(memory_rj_path)):
                    if f.endswith('.md'):
                        file_path = os.path.join(memory_rj_path, f)
                        content = _read_text(file_path)
                        entries = _parse_memory_entries(content, file_path)
                        all_entries.extend(entries)
        
        # 任务挖掘流程
        raw_tasks = heuristic_mine(all_entries, max_tasks=40)
        deduped_tasks = dedup_tasks(raw_tasks)
        assigned_tasks = assign_splits(deduped_tasks, val_fraction=0.34, seed=42)
        
        # 转换为 dict 格式
        tasks_dict = [t.to_dict() for t in assigned_tasks]
        
        # 计算分布统计
        task_distributions = calculate_task_distributions(assigned_tasks)
        
        report['tasks'] = tasks_dict
        report.update(task_distributions)
        
    except Exception as e:
        report['errors'].append({'step': 'task_mine', 'error': str(e)})
        report['tasks'] = []
        report['task_outcome_distribution'] = {'success': 0, 'fail': 0, 'mixed': 0, 'unknown': 0}
        report['task_split_distribution'] = {'train': 0, 'val': 0}
        report['total_tasks'] = 0

    # ── prompt_metrics 扫描（Phase 2.5：prompt 优化指标）─────────────
    try:
        report['prompt_metrics'] = scan_prompt_metrics(SKILL_ROOT)
    except Exception as e:
        report['errors'].append({'step': 'prompt_metrics_scan', 'error': str(e)})
        report['prompt_metrics'] = {
            'absolute_terms': {'total': 0, 'by_term': {}},
            'rule_repetitions': [],
            'hardmark_density': {'total': 0, 'total_lines': 0, 'density_per_lines': 0},
            'process_vs_outcome': {'process_count': 0, 'outcome_count': 0, 'ratio': 0},
        }

    # ── Gate 评分（Phase 3：gate）─────────────────────────────────────
    try:
        gate_score = calculate_gate_score(report)
        report['gate_score'] = gate_score.to_dict()
    except Exception as e:
        report['errors'].append({'step': 'gate_score', 'error': str(e)})
        report['gate_score'] = {
            'conflict_quality': 0.0,
            'duplicate_quality': 0.0,
            'stale_quality': 0.0,
            'outcome_clarity': 0.0,
            'split_coverage': 0.0,
            'layer_consistency': 0.0,
            'overall': 0.0,
            'recommendation': 'conditional',
        }

    # ── summary 汇总 ─────────────────────────────────────────────────
    high_count = 0
    medium_count = (len(report.get('memory_duplicates', [])) +
                    len(report.get('memory_conflicts', [])))
    low_count = len(report.get('memory_stale', []))

    proj_mem = report.get('project_memory_rj', {})
    medium_count += len(proj_mem.get('duplicates', [])) + len(proj_mem.get('conflicts', []))
    low_count += len(proj_mem.get('stale', []))

    layer_drift = report.get('memory_layer_drift', {})
    high_count += len(layer_drift.get('project_only', [])) + len(layer_drift.get('global_only', []))

    # ── lessons_extracted 经验提取维度（T003）─────────────────────────
    try:
        lessons_entries = []
        lessons_mem_content = _read_text(actual_memory_path)
        if lessons_mem_content:
            lessons_entries = _parse_memory_entries(lessons_mem_content, actual_memory_path)
        report['lessons_extracted'] = {
            'total_lessons': sum(1 for e in lessons_entries if e.get('is_lesson')),
            'importance_distribution': {
                'high': sum(1 for e in lessons_entries if e.get('importance_level') == 'high'),
                'medium': sum(1 for e in lessons_entries if e.get('importance_level') == 'medium'),
                'low': sum(1 for e in lessons_entries if e.get('importance_level') == 'low'),
            },
        }
    except Exception as e:
        report['errors'].append({'step': 'lessons_extracted', 'error': str(e)})
        report['lessons_extracted'] = {
            'total_lessons': 0,
            'importance_distribution': {'high': 0, 'medium': 0, 'low': 0},
        }

    report['summary'] = {
        'total_issues': high_count + medium_count + low_count,
        'by_severity': {
            'high': high_count,
            'medium': medium_count,
            'low': low_count,
        },
        'errors_count': len(report.get('errors', [])),
    }

    # ── 写 JSON 到 learn_rj/{timestamp}/ ─────────────────────────────
    if primary_docs:
        learn_rj_dir = os.path.join(primary_docs, 'learn_rj')
    else:
        learn_rj_dir = os.path.join(SKILL_ROOT, 'learn_rj_fallback')
    ts_dir = os.path.join(learn_rj_dir, report['timestamp'])
    try:
        os.makedirs(ts_dir, exist_ok=True)
        report_path = os.path.join(ts_dir, 'scan_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        report['output_path'] = report_path
        if not primary_docs:
            report['errors'].append({
                'step': 'write_report',
                'error': 'primary_docs 未解析，报告已 fallback 写到 skill 根目录: %s' % report_path,
            })
    except Exception as e:
        report['errors'].append({'step': 'write_report', 'error': str(e)})

    report['structure_missing'] = structure_missing or (not primary_docs)

    return report

# ===========================================================================
# 决策类更新检测与规则信号扫描（T15）
# ===========================================================================

def is_decision_like_update(content):
    """检测内容是否是决策类更新。

    决策类关键词:确认/澄清/收口/细化/明确/对齐/口径/决策/拍板/定下来/达成共识/修正/纠正/调整方向。
    """
    if not content:
        return False
    decision_keywords = [
        '确认', '澄清', '收口', '细化', '明确', '对齐', '口径',
        '决策', '拍板', '定下来', '达成共识',
        '修正', '纠正', '调整方向',
    ]
    return any(kw in content for kw in decision_keywords)

def merge_into_latest(task, content, memory_dir, timestamp=None):
    """同主题同阶段合并(决策类追加 #### 补充更新 段)。

    找最近 {task}_memory_*.md,若内容是决策类,
    在最近 ### 记忆条目段后追加 #### 补充更新 子段。
    """
    import glob
    from datetime import datetime
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    pattern = os.path.join(memory_dir, '%s_memory_*.md' % task)
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return {'action': 'no_target', 'reason': 'no existing memory file for task'}

    if not is_decision_like_update(content):
        return {'action': 'skipped', 'reason': 'not decision-like update'}

    target_file = files[0]
    with open(target_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 找最近的 ### 记忆条目段
    section_marker = '### 记忆条目 · %s' % task
    if section_marker not in text:
        # 退而求其次:找 ### 任意段
        section_marker = '### '

    # 在文件末尾(或最近 ### 段后)追加 #### 补充更新
    supplement = '\n\n#### 补充更新（%s）\n\n%s\n' % (timestamp, content)
    new_text = text.rstrip() + supplement

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(new_text)

    return {
        'action': 'merged',
        'file': target_file,
        'section': '#### 补充更新（%s）' % timestamp,
    }


# ---------------------------------------------------------------------------
# memory_rethink（方案 3-R 阶段4：LLM 重评建议，HARD-GATE）
# ---------------------------------------------------------------------------

def memory_rethink(project_name=None, task_name=None, scope='stale'):
    """重评 memory 条目，给"保留/合并/删除"建议清单（HARD-GATE，不自动执行）。

    本函数只产出建议，不自动修改 memory。agent 拿到建议后需 HARD-GATE 确认
    再调 memory_delete/memory_archive/memory_demote 执行。

    Args:
        project_name: 项目名，None 则全扫
        task_name: 指定 task 名，None 则扫全部
        scope: 扫描范围
            'stale' = 超 90 天的条目（默认）
            'low'   = importance=low 的条目
            'duplicates' = 重复条目（按 hash）
            'all'   = 全部条目

    Returns:
        dict: {
            'suggestions': [
                {
                    'task': str,
                    'timestamp': str,
                    'current_importance': str,
                    'current_status': str,
                    'suggestion': 'keep'/'merge'/'archive'/'delete',
                    'reason': str,
                },
                ...
            ],
            'total_scanned': int,
            'total_suggestions': int,
        }
    """
    import memory_shadow_write
    if not os.path.isfile(memory_shadow_write.GLOBAL_MEMORY_FILE):
        return {'suggestions': [], 'total_scanned': 0, 'total_suggestions': 0}
    try:
        with open(memory_shadow_write.GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return {'suggestions': [], 'total_scanned': 0, 'total_suggestions': 0}

    suggestions = []
    total_scanned = 0
    import re as _re
    from datetime import datetime, timedelta

    # 定位分段
    heading = '## %s' % project_name if project_name else None
    seg_indices = []
    for i, ln in enumerate(lines):
        if heading:
            if ln.rstrip('\n') == heading:
                seg_indices.append(i)
        else:
            if ln.startswith('## '):
                seg_indices.append(i)

    for seg_idx in seg_indices:
        seg_end = len(lines)
        for j in range(seg_idx + 1, len(lines)):
            if lines[j].startswith('## ') and j != seg_idx:
                seg_end = j
                break
        # 扫描分段内的 ### 记忆条目
        for j in range(seg_idx + 1, seg_end):
            line = lines[j].strip()
            m = _re.match(r'^### 记忆条目 · (.+?)(?:（(\d{4}-\d{2}-\d{2} \d{2}:\d{2})）)?$', line)
            if not m:
                continue
            entry_task = m.group(1).strip()
            entry_ts = m.group(2)
            if task_name and entry_task != task_name:
                continue
            total_scanned += 1
            # 读 block
            entry_end = j + 1
            while entry_end < seg_end and not lines[entry_end].startswith('### ') and not lines[entry_end].startswith('## '):
                entry_end += 1
            block_text = ''.join(lines[j:entry_end])
            # 解析 flag + 重要性
            flag = memory_shadow_write._parse_entry_flag(block_text)
            importance_m = _re.search(r'\*\*重要性\*\*:\s*(\w+)', block_text)
            importance = importance_m.group(1) if importance_m else 'medium'

            # 按 scope 过滤
            should_suggest = False
            suggestion = 'keep'
            reason = ''
            if scope == 'stale' and entry_ts:
                try:
                    entry_date = datetime.strptime(entry_ts, '%Y-%m-%d %H:%M')
                    if datetime.now() - entry_date > timedelta(days=90):
                        should_suggest = True
                        if importance == 'high':
                            suggestion = 'keep'
                            reason = '超 90 天但 importance=high，建议保留'
                        else:
                            suggestion = 'archive'
                            reason = '超 90 天且 importance=%s，建议归档' % importance
                except ValueError:
                    pass
            elif scope == 'low' and importance == 'low':
                should_suggest = True
                if flag['status'] == 'archived':
                    suggestion = 'delete'
                    reason = 'importance=low 且已 archived，建议硬删除'
                else:
                    suggestion = 'archive'
                    reason = 'importance=low，建议归档'
            elif scope == 'all':
                should_suggest = True
                suggestion = 'keep'
                reason = '全扫模式，默认保留（请人工复核）'

            if should_suggest:
                suggestions.append({
                    'task': entry_task,
                    'timestamp': entry_ts or '',
                    'current_importance': importance,
                    'current_status': flag['status'],
                    'suggestion': suggestion,
                    'reason': reason,
                })

    return {
        'suggestions': suggestions,
        'total_scanned': total_scanned,
        'total_suggestions': len(suggestions),
    }

def scan_memory_for_rule_signals(memory_dir):
    """扫描 memory 文件,找规则信号(以后都这么干/记下来/加到 skill 里 等)。"""
    import glob
    signals = []
    rule_keywords = [
        '以后都这么干', '以后都这样', '以后这么干',
        '记下来', '加到 skill 里', '写进 skill',
        '加到规则', '加到铁律', '加到框架',
        '固化', '沉淀', '长期规则',
    ]
    if not os.path.isdir(memory_dir):
        return signals
    for fp in glob.glob(os.path.join(memory_dir, '*.md')):
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, start=1):
                    for kw in rule_keywords:
                        if kw in line:
                            signals.append({
                                'file': fp,
                                'line_no': i,
                                'line': line.strip(),
                                'keyword': kw,
                            })
                            break  # 一行只记一个关键词
        except Exception:
            continue
    return signals

# ===========================================================================
# Phase 5：回归检测与回滚（detect_regression / rollback / write_manifest）
# ===========================================================================

def _extract_hard_rules_section(text):
    """提取规则类 section 内容（Phase 5 辅助函数）

    Phase 5 修复:扩展正则匹配多种 ## 节标题,覆盖 memory_main.md 实际结构:
    - 「## 硬规则」（中文）
    - 「## Hard Constraints」（英文,来自 project_memory）
    - 「## Engineering Conventions」（英文,来自 project_memory）
    - 「## Lessons Learned」（英文,来自 project_memory）
    - 「## Key Decisions」（关键约定,常见节）
    - 「## 关键约定」（中文）

    从匹配的标题行开始,到下一个「## 」标题行结束（不含下一个标题）。
    如果没有找到任何匹配的 section,返回空字符串。

    参数：
        text: str - 文件全文内容

    返回：
        str: 规则类 section 的完整文本（含标题行,多个匹配拼接）
    """
    if not text:
        return ''
    # Phase 5 修复:扩展正则匹配多种规则类节标题
    # 中文:硬规则 / 关键约定 / 关键决策 / 长期经验 / 不可恢复上下文 / 工程约定 / 核心发现 / 核心产出
    # 英文:Hard Constraints / Engineering Conventions / Lessons Learned / Key Decisions / ADR
    pattern = r'^##\s*(?:硬规则|关键约定|关键决策|长期经验|不可恢复上下文|工程约定|核心发现|核心产出|Hard\s*Constraints|Engineering\s*Conventions|Lessons\s*Learned|Key\s*Decisions|ADR).*?(?=^##\s|\Z)'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    if matches:
        return '\n\n'.join(matches)
    return ''

def detect_regression(skill_root, baseline_memory_path=None):
    """检测 memory_main.md 是否发生规则回归（Phase 5）

    通过对比当前 memory_main.md 与基线版本的「## 硬规则」section，
    判断规则是否被削弱（weakened）或删除（deleted）。

    参数：
        skill_root: skill 根目录路径
        baseline_memory_path: 基线 memory_main.md 路径，
                              默认为 {skill_root}/memory/memory_main.md.bak_learn

    返回：
        dict: {
            'regression_count': int,
            'regressions': [{'rule_id': str, 'type': 'deleted|weakened',
                             'baseline_snippet': str, 'current_snippet': str,
                             'similarity': float}],
            'baseline_path': str,
            'current_path': str,
            'note': str  # 基线不存在时附加说明
        }
    """
    # 当前 memory_main.md 路径（用户数据外置）
    current_path = str(user_data_path.get_memory_main_path())

    # 默认基线路径（用户数据外置）
    if baseline_memory_path is None:
        baseline_memory_path = str(
            user_data_path.get_user_data_dir() / 'memory' / 'memory_main.md.bak_learn')

    # 基线不存在 → 返回空结果（note 字段说明原因）
    if not os.path.exists(baseline_memory_path):
        return {
            'regression_count': 0,
            'regressions': [],
            'baseline_path': '',
            'current_path': current_path,
            'note': 'baseline not found',
        }

    # 读基线与当前
    baseline_text = _read_text(baseline_memory_path)
    current_text = _read_text(current_path)

    # 提取「## 硬规则」section
    baseline_section = _extract_hard_rules_section(baseline_text)
    current_section = _extract_hard_rules_section(current_text)

    # 按行 split（去掉空行与首尾空白）
    baseline_lines = [ln.strip() for ln in baseline_section.split('\n') if ln.strip()]
    current_lines = [ln.strip() for ln in current_section.split('\n') if ln.strip()]

    regressions = []

    # 遍历基线每条规则，在当前版本里找最相似的行
    for idx, base_line in enumerate(baseline_lines):
        best_ratio = 0.0
        best_match = ''
        for cur_line in current_lines:
            ratio = difflib.SequenceMatcher(None, base_line, cur_line).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = cur_line

        if best_ratio < 0.3:
            # 在当前版本里找不到任何相似行 → deleted
            regressions.append({
                'rule_id': 'rule_%03d' % (idx + 1),
                'type': 'deleted',
                'baseline_snippet': base_line[:200],
                'current_snippet': '',
                'similarity': round(best_ratio, 4),
            })
        elif best_ratio < 0.85:
            # 相似度低于阈值 → weakened（规则被削弱）
            regressions.append({
                'rule_id': 'rule_%03d' % (idx + 1),
                'type': 'weakened',
                'baseline_snippet': base_line[:200],
                'current_snippet': best_match[:200],
                'similarity': round(best_ratio, 4),
            })

    return {
        'regression_count': len(regressions),
        'regressions': regressions,
        'baseline_path': baseline_memory_path,
        'current_path': current_path,
    }

def rollback(baseline_memory_path, current_memory_path, dry_run=True):
    """回滚 memory_main.md 到基线版本（Phase 5）

    参数：
        baseline_memory_path: 基线 memory_main.md 路径
        current_memory_path: 当前 memory_main.md 路径
        dry_run: True 只生成 diff 预览、不动文件；False 实际执行回滚

    返回：
        dict: {
            'rolled_back': bool,
            'backup_path': str,
            'diff_preview': str
        }
    """
    # 校验基线存在
    if not os.path.exists(baseline_memory_path):
        return {'rolled_back': False, 'error': 'baseline not found'}

    # 读基线与当前（按行保留行尾，便于 unified_diff 输出）
    baseline_lines = _read_text(baseline_memory_path).splitlines(keepends=True)
    if os.path.exists(current_memory_path):
        current_lines = _read_text(current_memory_path).splitlines(keepends=True)
    else:
        current_lines = []

    # 生成 unified diff 预览
    diff = difflib.unified_diff(
        baseline_lines,
        current_lines,
        fromfile='baseline:' + os.path.basename(baseline_memory_path),
        tofile='current:' + os.path.basename(current_memory_path),
    )
    diff_preview = ''.join(diff)

    # dry-run 模式：只返回 diff 预览，不动文件
    if dry_run:
        return {
            'rolled_back': False,
            'backup_path': '',
            'diff_preview': diff_preview,
        }

    # 实际回滚：先备份当前文件，再复制基线 → 当前
    backup_path = ''
    if os.path.exists(current_memory_path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = current_memory_path + '.bak_rollback_' + timestamp
        shutil.copy2(current_memory_path, backup_path)

    # 确保目标目录存在后复制基线 → 当前
    os.makedirs(os.path.dirname(os.path.abspath(current_memory_path)), exist_ok=True)
    shutil.copy2(baseline_memory_path, current_memory_path)

    return {
        'rolled_back': True,
        'backup_path': backup_path,
        'diff_preview': diff_preview,
    }

def write_manifest(learn_state, output_dir):
    """写 learn manifest（Phase 5）

    参数：
        learn_state: LearnState 实例
        output_dir: 输出目录路径（不存在则自动创建）

    返回：
        dict: {
            'manifest_path': str,
            'latest_path': str,
            'state': dict
        }
    """
    # 校验/创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    state_dict = learn_state.to_dict()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    manifest_path = os.path.join(output_dir, 'manifest_' + timestamp + '.json')
    latest_path = os.path.join(output_dir, 'manifest_latest.json')

    # 写时间戳版（每次新增一个）
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)

    # 覆盖写 latest 版（始终反映最新状态）
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)

    return {
        'manifest_path': manifest_path,
        'latest_path': latest_path,
        'state': state_dict,
    }

def rule_scan_and_pool(args):
    """rule 子命令入口:扫描 memory 找规则信号 + 汇总。

    用 args.command 判断(不是 args.subcmd)。
    """
    skill_dir = getattr(args, 'skill_dir', None) or os.getcwd()
    memory_dir = str(user_data_path.get_docs_rj_path() / 'memory_rj')

    signals = scan_memory_for_rule_signals(memory_dir)
    files_with_signals = set(s['file'] for s in signals)

    result = {
        'total_signals': len(signals),
        'files_with_signals': len(files_with_signals),
        'signals': signals,
    }

    # 输出汇总
    print('Rule signals scan:')
    print('  Total signals: %d' % result['total_signals'])
    print('  Files with signals: %d' % result['files_with_signals'])
    for s in signals[:10]:
        print('  - [%s:%d] %s' % (
            os.path.basename(s['file']), s['line_no'], s['line'][:60]))

    # 非 dry-run 时写报告
    if not getattr(args, 'dry_run', False) and signals:
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M')
        report_path = os.path.join(memory_dir, 'rule_scan_report_%s.md' % ts)
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('# Rule Scan Report (%s)\n\n' % ts)
                f.write('Total signals: %d\n\n' % len(signals))
                for s in signals:
                    f.write('- [%s:%d] %s\n' % (
                        os.path.basename(s['file']), s['line_no'], s['line']))
            print('Report written: %s' % report_path)
        except Exception as e:
            print('Failed to write report: %s' % e)

    return result

# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='riji-skill learn 子流程扫描器（从 memory 提炼可优化点）'
    )
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    scan_parser = subparsers.add_parser('scan', help='扫描 memory 输出 JSON 报告')
    scan_parser.add_argument('--dry-run', action='store_true', default=True,
                             help='只输出报告不改任何文件')
    scan_parser.add_argument('--scope', choices=['all', 'memory'],
                             default='all', help='限定扫描范围（默认 all；all 和 memory 等价）')
    scan_parser.add_argument('--phase5', action='store_true', default=False,
                             help='启用 Phase 5 回归检测（基线对比 + 回滚提示）')
    scan_parser.add_argument('--memory-path', default=None,
                             help='自定义 memory 文件路径（测试用，默认用 MEMORY_MAIN_PATH）')

    migrate_parser = subparsers.add_parser('migrate', help='迁移旧格式 memory 条目到新格式')
    migrate_parser.add_argument('--dry-run', action='store_true', default=False,
                                help='只预览迁移，不实际修改文件')

    reflect_parser = subparsers.add_parser('reflect', help='读取最新 scan_report.json 生成建议清单')
    reflect_parser.add_argument('--dry-run', action='store_true', default=False,
                                help='只预览建议，不写入 proposals.md')

    adopt_parser = subparsers.add_parser('adopt', help='执行 adopt（备份+生成操作清单，实际修改由 agent 执行）')
    adopt_parser.add_argument('--dry-run', action='store_true', default=False,
                              help='只预览操作，不备份不执行')

    rule_parser = subparsers.add_parser('rule', help='扫描 memory 找规则信号')
    rule_parser.add_argument('--dry-run', action='store_true', default=True,
                             help='只输出不写报告（默认开启，去掉 --dry-run 写报告）')
    rule_parser.add_argument('--skill-dir', default=None,
                             help='skill 根目录（默认当前目录）')

    # ── Phase 5 新子命令 ──────────────────────────────────────────────
    rollback_parser = subparsers.add_parser('rollback',
                                            help='回滚 memory_main.md 到基线版本（Phase 5）')
    rollback_parser.add_argument('--baseline', required=True,
                                 help='基线 memory_main.md 路径（必填）')
    rollback_parser.add_argument('--current', required=True,
                                 help='当前 memory_main.md 路径（必填）')
    # Phase 5 修复:用 BooleanOptionalAction(Python 3.9+)避免 store_true+default=True 永远 True 的 BUG
    # 用户可用 --no-dry-run 实际执行回滚
    rollback_parser.add_argument('--dry-run', action=argparse.BooleanOptionalAction, default=True,
                                 help='只生成 diff 预览、不动文件（默认开启，使用 --no-dry-run 实际执行回滚）')

    detect_regression_parser = subparsers.add_parser('detect-regression',
                                                      help='检测 memory_main.md 是否发生规则回归（Phase 5）')
    detect_regression_parser.add_argument('--skill-root', default=os.getcwd(),
                                          help='skill 根目录（默认当前目录）')
    detect_regression_parser.add_argument('--baseline-memory', default=None,
                                          help='基线 memory_main.md 路径（默认 {skill-root}/memory/memory_main.md.bak_learn）')

    write_manifest_parser = subparsers.add_parser('write-manifest',
                                                  help='写 learn manifest 到指定目录（Phase 5）')
    write_manifest_parser.add_argument('--task', required=True,
                                       help='任务名（必填，写入 LearnState.task）')
    write_manifest_parser.add_argument('--output-dir', required=True,
                                       help='输出目录路径（必填，manifest 写入此目录）')
    write_manifest_parser.add_argument('--state', default='pending',
                                       help='LearnState 初始状态 JSON 字符串（默认 "pending"）')

    # count 子命令注册（learn_into_act v1.0.0 新增）
    sub_count = subparsers.add_parser('count', help='统计 memory 条目数与阈值比较')
    sub_count.add_argument('--threshold', type=int, default=20,
                           help='触发 learn 的条目数阈值（默认 20，负数自动用默认值）')
    sub_count.add_argument('--memory-path', default=None,
                           help='自定义 memory 文件路径（测试用，默认用 MEMORY_MAIN_PATH）')
    sub_count.set_defaults(func=cmd_count)

    args = parser.parse_args()

    if args.command == 'count':
        sys.exit(cmd_count(args))

    if args.command == 'scan':
        scan_memory_path = args.memory_path if args.memory_path else None
        report = scan(scope=args.scope, dry_run=args.dry_run, memory_path=scan_memory_path)
        print('=' * 60)
        print('📋 learn_tidy.py scan 完成')
        print('=' * 60)
        print('时间戳: %s' % report['timestamp'])
        print('扫描范围: %s' % report['scope'])
        print('主 docs: %s' % report.get('primary_docs', '(未解析)'))
        print()
        s = report.get('summary', {})
        print('发现问题总数: %d' % s.get('total_issues', 0))
        print('  - high:   %d' % s.get('by_severity', {}).get('high', 0))
        print('  - medium: %d' % s.get('by_severity', {}).get('medium', 0))
        print('  - low:    %d' % s.get('by_severity', {}).get('low', 0))
        print('  - errors: %d' % s.get('errors_count', 0))
        print()
        
        # 任务挖掘统计（Phase 2）
        task_stats = report.get('task_outcome_distribution', {})
        split_stats = report.get('task_split_distribution', {})
        print('任务挖掘统计:')
        print('  - 总任务数: %d' % report.get('total_tasks', 0))
        print('  - 结果分布:')
        print('    * success: %d' % task_stats.get('success', 0))
        print('    * fail:    %d' % task_stats.get('fail', 0))
        print('    * mixed:   %d' % task_stats.get('mixed', 0))
        print('    * unknown: %d' % task_stats.get('unknown', 0))
        print('  - 数据划分:')
        print('    * train: %d' % split_stats.get('train', 0))
        print('    * val:   %d' % split_stats.get('val', 0))
        print()
        
        # Gate 评分统计（Phase 3）
        gate_score = report.get('gate_score', {})
        print('Gate 评分:')
        print('  - 综合评分: %.4f' % gate_score.get('overall', 0.0))
        print('  - 推荐: %s' % gate_score.get('recommendation', 'conditional'))
        print('  - 各维度:')
        print('    * 冲突质量: %.4f' % gate_score.get('conflict_quality', 0.0))
        print('    * 重复质量: %.4f' % gate_score.get('duplicate_quality', 0.0))
        print('    * 过时质量: %.4f' % gate_score.get('stale_quality', 0.0))
        print('    * 结果清晰: %.4f' % gate_score.get('outcome_clarity', 0.0))
        print('    * 划分覆盖: %.4f' % gate_score.get('split_coverage', 0.0))
        print('    * 跨层一致: %.4f' % gate_score.get('layer_consistency', 0.0))
        print()
        if report.get('output_path'):
            print('报告已写入: %s' % report['output_path'])

        # Phase 5：--phase5 启用回归检测
        if getattr(args, 'phase5', False):
            phase5_result = detect_regression(SKILL_ROOT)
            print()
            print('Phase 5 回归检测:')
            print('  - 回归数量: %d' % phase5_result.get('regression_count', 0))
            if phase5_result.get('baseline_path'):
                print('  - 基线: %s' % phase5_result['baseline_path'])
            else:
                print('  - 基线: 未找到（建议先备份 memory_main.md 为 .bak_learn）')
            if phase5_result.get('regression_count', 0) > 0:
                print('  ⚠️ 检测到回归，建议运行:')
                print('     python learn_tidy.py rollback --baseline %s --current %s'
                      % (phase5_result['baseline_path'], phase5_result['current_path']))

        if report.get('structure_missing'):
            sys.exit(2)
        if report.get('errors'):
            sys.exit(1)
        sys.exit(0)

    elif args.command == 'migrate':
        print('=' * 60)
        print('📋 learn_tidy.py migrate（迁移旧格式到新格式）')
        print('=' * 60)
        print('模式: %s' % ('预览模式' if args.dry_run else '执行模式'))
        print()

        primary_docs = resolve_primary_docs()
        result = migrate_memory_entries(primary_docs, dry_run=args.dry_run)

        print()
        print('迁移结果:')
        print('  - 需要迁移: %d 个文件' % result['migrated'])
        print('  - 已为新格式: %d 个文件' % result['skipped'])
        if result['errors']:
            print('  - 错误: %d 个' % len(result['errors']))
            for err in result['errors']:
                print('    * %s' % err)

        if args.dry_run:
            print()
            print('⚠️ 预览模式，未实际修改任何文件。去掉 --dry-run 执行实际迁移。')

        if result['errors']:
            sys.exit(1)
        sys.exit(0)

    elif args.command == 'reflect':
        print('=' * 60)
        print('📋 learn_tidy.py reflect（生成建议清单）')
        print('=' * 60)
        print('模式: %s' % ('预览模式' if args.dry_run else '执行模式'))
        print()

        primary_docs = resolve_primary_docs()
        scan_report_path = find_latest_scan_report(primary_docs)
        
        if not scan_report_path:
            print('❌ 未找到最新的 scan_report.json，请先运行 "python learn_tidy.py scan"')
            sys.exit(1)
        
        print(f'读取 scan_report: {scan_report_path}')
        print()
        
        result = generate_proposals(scan_report_path)
        
        if 'error' in result:
            print(f'❌ 生成建议失败: {result["error"]}')
            sys.exit(1)
        
        # 打印建议摘要
        proposals = result.get('proposals', [])
        semantic_placeholders = result.get('semantic_placeholders', [])
        
        print('机械类建议（自动生成）:')
        if proposals:
            for p in proposals:
                print(f'  #{p["number"]}: {p["action"]} {p["target"]} - {p["rationale"][:50]}...')
        else:
            print('  暂无机械类建议')
        print()
        
        print('语义类建议（需 agent 填充）:')
        for p in semantic_placeholders:
            print(f'  #{p["number"]}: {p["item"]} - {p["description"][:30]}...')
        print()
        
        # 写入 proposals.md
        if not args.dry_run:
            proposals_path = write_proposals_md(result)
            if proposals_path:
                print(f'✅ proposals.md 已写入: {proposals_path}')
            else:
                print('❌ 写入 proposals.md 失败')
                sys.exit(1)
        else:
            print('⚠️ 预览模式，未写入 proposals.md')
        
        sys.exit(0)

    elif args.command == 'adopt':
        print('=' * 60)
        print('📋 learn_tidy.py adopt（执行建议）')
        print('=' * 60)
        print('模式: %s' % ('预览模式' if args.dry_run else '执行模式'))
        print()

        primary_docs = resolve_primary_docs()
        proposals_path = find_latest_proposals(primary_docs)
        
        if not proposals_path:
            print('❌ 未找到最新的 proposals.md，请先运行 "python learn_tidy.py reflect"')
            sys.exit(1)
        
        print(f'读取 proposals: {proposals_path}')
        print()
        
        result = adopt(proposals_path, dry_run=args.dry_run)
        
        if result['errors']:
            print(f'❌ adopt 失败: {result["errors"]}')
            sys.exit(1)
        
        # 打印操作清单
        action_list = result.get('action_list', [])
        skipped_semantic = result.get('skipped_semantic', 0)
        backed_up_files = result.get('backed_up_files', [])
        
        print('操作清单（机械类建议）:')
        if action_list:
            for action in action_list:
                print(f'  #{action["number"]}: {action["action"]} {action["target"]}')
                print(f'    位置: {action["location"]}')
                print(f'    理由: {action["rationale"]}')
                print()
        else:
            print('  暂无机械类建议')
        print()
        
        if skipped_semantic > 0:
            print(f'⚠️ 跳过 {skipped_semantic} 条语义类建议（未填充具体内容）')
            print('   请 agent 读 prompt_optimization.md 后填充语义类建议')
            print()
        
        # 打印备份信息
        if not args.dry_run:
            print('备份文件:')
            for f in backed_up_files:
                print(f'  ✅ {f}')
            print()
            print(f'备份目录: {result["backup_dir"]}')
        else:
            print('⚠️ 预览模式，未执行备份')
            print('   去掉 --dry-run 执行实际备份和操作')
            print()
        
        sys.exit(0)

    elif args.command == 'rule':
        print('=' * 60)
        print('📋 learn_tidy.py rule（扫描 memory 找规则信号）')
        print('=' * 60)
        print('模式: %s' % ('预览模式（不写报告）' if args.dry_run else '执行模式（写报告）'))
        print()

        rule_scan_and_pool(args)
        sys.exit(0)

    elif args.command == 'rollback':
        print('=' * 60)
        print('📋 learn_tidy.py rollback（回滚 memory_main.md）')
        print('=' * 60)
        print('模式: %s' % ('预览模式（dry-run）' if args.dry_run else '执行模式（实际回滚）'))
        print()

        result = rollback(args.baseline, args.current, dry_run=args.dry_run)
        if result.get('error'):
            print('❌ %s' % result['error'])
            sys.exit(1)

        print('基线: %s' % args.baseline)
        print('当前: %s' % args.current)
        print('已回滚: %s' % ('是' if result.get('rolled_back') else '否'))
        if result.get('backup_path'):
            print('备份: %s' % result['backup_path'])
        if result.get('diff_preview'):
            print()
            print('Diff 预览（前 2000 字符）:')
            print(result['diff_preview'][:2000])
        sys.exit(0)

    elif args.command == 'detect-regression':
        print('=' * 60)
        print('📋 learn_tidy.py detect-regression（检测规则回归）')
        print('=' * 60)
        print()

        result = detect_regression(args.skill_root, baseline_memory_path=args.baseline_memory)
        print('回归数量: %d' % result.get('regression_count', 0))
        print('当前路径: %s' % result.get('current_path', ''))
        print('基线路径: %s' % result.get('baseline_path', '(未找到)'))
        if result.get('note'):
            print('说明: %s' % result['note'])
        if result.get('regressions'):
            print()
            print('回归详情:')
            for r in result['regressions']:
                print('  - %s [%s] similarity=%.4f' % (r['rule_id'], r['type'], r['similarity']))
                print('    baseline: %s' % r['baseline_snippet'][:80])
                print('    current:  %s' % r['current_snippet'][:80])
        print()
        print('JSON 输出:')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    elif args.command == 'write-manifest':
        print('=' * 60)
        print('📋 learn_tidy.py write-manifest（写 learn manifest）')
        print('=' * 60)
        print()

        # 创建 LearnState 实例
        learn_state = LearnState(args.task)
        # 如果 --state 传入 JSON，尝试解析并应用
        if args.state and args.state != 'pending':
            try:
                state_data = json.loads(args.state)
                if 'state' in state_data:
                    learn_state.state = state_data['state']
                if 'proposals' in state_data:
                    learn_state.proposals = state_data['proposals']
                if 'adopted' in state_data:
                    learn_state.adopted = state_data['adopted']
                if 'rejected' in state_data:
                    learn_state.rejected = state_data['rejected']
                if 'archived_path' in state_data:
                    learn_state.archived_path = state_data['archived_path']
            except json.JSONDecodeError as e:
                print('⚠️ --state JSON 解析失败: %s，使用默认 pending 状态' % str(e))

        result = write_manifest(learn_state, args.output_dir)
        print('manifest 已写入:')
        print('  - 时间戳版: %s' % result['manifest_path'])
        print('  - latest 版: %s' % result['latest_path'])
        print('状态: %s' % json.dumps(result['state'], ensure_ascii=False))
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
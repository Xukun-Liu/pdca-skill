"""
loop_admission.py — 项目 loop 准入审计工具

给定项目目录，输出 readiness score(0-100) + level(L0/L1/L2/L3) + findings + recommendations。
把 SKILL.md §6 的 6 道门从"文档约定"升级为"代码强制"。

对应 spec：docs_rj/spec_rj/loop_admission_python_spec_20260717_0943.md
版本：（T006 format_human 加 ASCII 进度条 + Findings 按 ok/warn/fail 排序）
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, NamedTuple


# ===== 常量（spec §7.1）=====

SCORE_WEIGHTS = {
    'skill_md': 8,
    'references_count': 6,
    'history_md': 3,
    'pdca_coverage': 4,
    'memory_main': 4,
    'memory_rj_recent': 4,
    'summary_rj': 4,
    'docs_trio': 5,
    'loop_tools': 8,
    'task_state': 12,
    'security': 4,
    'triage': 10,
    'verifier': 10,
    'constraints': 3,
    'trigger_hooks': 4,
    'loop_activity': 4,
    'governance_tool_scope': 2,
    'governance_stall': 2,
    'governance_escalation': 2,
    'safety_doc': 2,
}

BASE_SCORE = 5
LEVEL_THRESHOLDS = {'L1': 50, 'L2': 70, 'L3': 85}
EXIT_CODE_THRESHOLD = 50

# 等级评估文本（AuditResult.assessment 用）
ASSESSMENT_TEXTS = {
    'L0': 'L0=不可用（仅 base 分，无任何 loop 信号）',
    'L1': 'L1=report-only（只分析不改代码）',
    'L2': 'L2=assisted（/plan 确认后自动跑 /do→/check）',
    'L3': 'L3=unattended（完全无人值守）',
}


# ===== dataclass（spec §7.2）=====

@dataclass
class LoopSignals:
    """22 项 loop 准入信号，每项为 (是否命中, 证据列表)。"""
    skill_md: tuple[bool, list[str]]
    references_count: tuple[bool, list[str]]
    history_md: tuple[bool, list[str]]
    pdca_coverage: tuple[bool, list[str]]
    memory_main: tuple[bool, list[str]]
    memory_rj_recent: tuple[bool, list[str]]
    summary_rj: tuple[bool, list[str]]
    docs_trio: tuple[bool, list[str]]
    loop_tools: tuple[bool, list[str]]
    task_state: tuple[bool, list[str]]
    security: tuple[bool, list[str]]
    triage: tuple[bool, list[str]]
    verifier: tuple[bool, list[str]]
    constraints: tuple[bool, list[str]]
    trigger_hooks: tuple[bool, list[str]]
    loop_activity: tuple[bool, list[str]]
    governance_tool_scope: tuple[bool, list[str]]
    governance_stall: tuple[bool, list[str]]
    governance_escalation: tuple[bool, list[str]]
    safety_doc: tuple[bool, list[str]]
    # @deprecated 预算管理已移除，保留仅为兼容旧版 JSON 输出格式（SCORE_WEIGHTS 不含此项，不影响评分）
    skill_md_budget: tuple[bool, list[str]]


@dataclass
class Finding:
    """审计发现项。"""
    level: str  # ok / warn / fail
    message: str


@dataclass
class AuditResult:
    """审计结果。"""
    target: str
    score: int
    level: str
    assessment: str
    signals: LoopSignals
    findings: List[Finding]
    recommendations: List[str]


class ScoreResult(NamedTuple):
    """compute_score 返回值（M5 重构：替代 4 元组，兼容元组解包+支持属性访问）。

    Attributes:
        score: 0-100 整数（base + 信号累加，钳制）
        level: L0/L1/L2/L3
        assessment: 等级描述文本
        findings: 降级 warn finding 列表
    """
    score: int
    level: str
    assessment: str
    findings: List[Finding]


# ===== 22 项信号检测函数（spec §4.3 + §7.3，T002 实现）=====

def detect_skill_md(root: Path) -> tuple[bool, list[str]]:
    """检测 SKILL.md 存在 + 含'7条铁律'关键词（+8）。"""
    skill_md = root / 'SKILL.md'
    if not skill_md.exists():
        return (False, [])
    content = skill_md.read_text(encoding='utf-8', errors='ignore')
    if '7条铁律' in content or '七条铁律' in content:
        return (True, [f'{skill_md} 含"7条铁律"关键词'])
    return (False, [])


def detect_references_count(root: Path) -> tuple[bool, list[str]]:
    """检测 references/ 下 .md 文件数 ≥30（+6）。"""
    refs_dir = root / 'references'
    if not refs_dir.is_dir():
        return (False, [])
    md_files = list(refs_dir.glob('*.md'))
    count = len(md_files)
    if count >= 30:
        return (True, [f'references/ 下 {count} 个 .md 文件（≥30）'])
    return (False, [f'references/ 下仅 {count} 个 .md 文件（<30）'])


def detect_history_md(root: Path) -> tuple[bool, list[str]]:
    """检测 HISTORY.md 存在 + 含版本号条目（+3）。"""
    history = root / 'HISTORY.md'
    if not history.exists():
        return (False, [])
    content = history.read_text(encoding='utf-8', errors='ignore')
    if re.search(r'\bv\d+\.\d+', content):
        return (True, [f'{history} 含版本号条目'])
    return (False, [])


def detect_pdca_coverage(root: Path) -> tuple[bool, list[str]]:
    """检测 references/ 下 .md 文件 PDCA 标签覆盖率 ≥80%（+4）。"""
    refs_dir = root / 'references'
    if not refs_dir.is_dir():
        return (False, [])
    md_files = list(refs_dir.glob('*.md'))
    if not md_files:
        return (False, ['references/ 无 .md 文件'])
    labeled = 0
    for f in md_files:
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'(PDCA|阶段)标签：', content):
                labeled += 1
        except (OSError, UnicodeDecodeError):
            # OSError: 权限/文件系统异常；UnicodeDecodeError: 编码异常（errors='ignore' 通常已吞，此处防御性）
            pass
    coverage = labeled / len(md_files)
    if coverage >= 0.8:
        return (True, [f'PDCA 标签覆盖率 {coverage:.0%}（{labeled}/{len(md_files)}，≥80%）'])
    return (False, [f'PDCA 标签覆盖率 {coverage:.0%}（{labeled}/{len(md_files)}，<80%）'])


# ===== 辅助函数（M4 重构：抽公共模式）=====

def _detect_file_exists(path: Path, hint: str = '') -> tuple[bool, list[str]]:
    """检测单文件存在，返回 (是否, evidence)。

    Args:
        path: 文件路径
        hint: 可选描述标签（用于 evidence 文案，空则不附加）

    Returns:
        (是否存在, evidence 列表)
    """
    if path.exists():
        if hint:
            return (True, [f'{path} 存在（{hint}）'])
        return (True, [f'{path} 存在'])
    return (False, [])


def _detect_keyword_in_files(
    files: list[Path],
    hints: list[str],
    label: str,
) -> tuple[bool, list[str]]:
    """在多个文件中按关键词列表正则搜索，命中任一即返回 True。

    Args:
        files: 候选文件列表（不存在的自动跳过）
        hints: 关键词列表（拼接为正则 OR 模式，IGNORECASE 匹配）
        label: 命中标签描述（用于 evidence 文案）

    Returns:
        (是否命中, evidence 列表)
    """
    # M-2 修复：re.escape 转义每个 hint，防止未来含正则元字符的 hint 导致意外匹配/ReDoS。
    # 当前 hints 全是字面字符串，re.escape 不改变语义；前缀匹配（如 r'escalat'）转义后仍为字面 'escalat'，
    # re.search 仍能匹配 'escalate'/'escalation' 等前缀，语义不变。
    pattern = '|'.join(re.escape(h) for h in hints)
    for f in files:
        if not f.exists():
            continue
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return (True, [f'{f} 含"{match.group()}"（{label}）'])
        except (OSError, UnicodeDecodeError):
            pass
    return (False, [])


def detect_memory_main(root: Path) -> tuple[bool, list[str]]:
    """检测 memory/memory_main.md 存在（+4）。"""
    return _detect_file_exists(root / 'memory' / 'memory_main.md')


def detect_memory_rj_recent(root: Path) -> tuple[bool, list[str]]:
    """检测 docs_rj/memory_rj/ 有 *_memory_*.md 且 mtime ≥ now-7天（+4）。"""
    mem_dir = root / 'docs_rj' / 'memory_rj'
    if not mem_dir.is_dir():
        return (False, [])
    now = time.time()
    seven_days = 7 * 24 * 3600
    for f in mem_dir.glob('*_memory_*.md'):
        try:
            mtime = f.stat().st_mtime
            if now - mtime <= seven_days:
                return (True, [f'{f} mtime 近 7 天'])
        except OSError:
            pass
    return (False, [])


def detect_summary_rj(root: Path) -> tuple[bool, list[str]]:
    """检测 docs_rj/SUMMARY_RJ.md 存在（+4）。"""
    return _detect_file_exists(root / 'docs_rj' / 'SUMMARY_RJ.md')


def detect_docs_trio(root: Path) -> tuple[bool, list[str]]:
    """检测 docs_rj/spec_rj + task_rj + handoff_rj 三目录齐全（+5）。"""
    dirs = [
        root / 'docs_rj' / 'spec_rj',
        root / 'docs_rj' / 'task_rj',
        root / 'docs_rj' / 'handoff_rj',
    ]
    missing = [str(d) for d in dirs if not d.is_dir()]
    if not missing:
        return (True, ['docs_rj/ 三件套目录齐全（spec_rj+task_rj+handoff_rj）'])
    return (False, [f'缺失目录：{missing}'])


def detect_loop_tools(root: Path) -> tuple[bool, list[str]]:
    """检测 loop_guard.py + loop_audit.py 两脚本存在（+8）。"""
    scripts = [
        root / 'scripts' / 'loop_guard.py',
        root / 'scripts' / 'loop_audit.py',
    ]
    missing = [str(s) for s in scripts if not s.exists()]
    if not missing:
        return (True, ['loop 工具链齐全（loop_guard+loop_audit）'])
    return (False, [f'缺失脚本：{missing}'])


def detect_task_state(root: Path) -> tuple[bool, list[str]]:
    """检测 docs_rj/memory_rj/TASK_STATE_*.md 存在（+12，=stateFile）。"""
    mem_dir = root / 'docs_rj' / 'memory_rj'
    if not mem_dir.is_dir():
        return (False, [])
    matches = list(mem_dir.glob('TASK_STATE_*.md'))
    if matches:
        return (True, [f'TASK_STATE 文件：{[m.name for m in matches]}'])
    return (False, [])


def detect_security(root: Path) -> tuple[bool, list[str]]:
    """检测 references/do/danger/security.md 存在 + SKILL.md 含'安全不变量'（+4）。"""
    sec_md = root / 'references' / 'do' / 'danger' / 'security.md'
    skill_md = root / 'SKILL.md'
    if not sec_md.exists():
        return (False, [])
    if not skill_md.exists():
        return (False, [])
    content = skill_md.read_text(encoding='utf-8', errors='ignore')
    if '安全不变量' in content:
        return (True, [f'{sec_md} 存在 + SKILL.md 含"安全不变量"'])
    return (False, [])


def detect_triage(root: Path) -> tuple[bool, list[str]]:
    """检测 references/plan/route/loop_triage.md 存在（+10）。"""
    return _detect_file_exists(root / 'references' / 'plan' / 'route' / 'loop_triage.md')


def detect_verifier(root: Path) -> tuple[bool, list[str]]:
    """检测 references/check/loop_verifier.md 存在（+10）。"""
    return _detect_file_exists(root / 'references' / 'check' / 'loop_verifier.md')


def detect_constraints(root: Path) -> tuple[bool, list[str]]:
    """检测 references/do/danger/loop_constraints.md 存在（+3）。"""
    return _detect_file_exists(root / 'references' / 'do' / 'danger' / 'loop_constraints.md')


def detect_trigger_hooks(root: Path) -> tuple[bool, list[str]]:
    """检测 references/common/pa/trigger_hooks.md 存在（+4）。"""
    return _detect_file_exists(root / 'references' / 'common' / 'pa' / 'trigger_hooks.md')


def _detect_loop_activity_fallback(root: Path) -> tuple[bool, list[str]]:
    """降级检测：③TASK_STATE mtime 近 7 天 ④loop_audit.py 存在。"""
    mem_dir = root / 'docs_rj' / 'memory_rj'
    if mem_dir.is_dir():
        now = time.time()
        seven_days = 7 * 24 * 3600
        for f in mem_dir.glob('TASK_STATE_*.md'):
            try:
                mtime = f.stat().st_mtime
                if now - mtime <= seven_days:
                    return (True, [f'{f} mtime 近 7 天（STATE 文件活动）'])
            except OSError:
                pass
    loop_audit = root / 'scripts' / 'loop_audit.py'
    if loop_audit.exists():
        return (True, [f'{loop_audit} 存在（loop 工具活动信号）'])
    return (False, [])


def detect_loop_activity(root: Path) -> tuple[bool, list[str]]:
    """检测 loop 活动（+4）。判定顺序：①git rev-parse ②git log ③TASK_STATE mtime ④loop_audit.py。"""
    # ①先 git rev-parse 判断是否 git 仓库
    try:
        rev_result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=str(root), capture_output=True, text=True, timeout=1.5,
        )
        if rev_result.returncode != 0 or rev_result.stdout.strip() != 'true':
            # 非 git 仓库 → 降级到 ③④
            return _detect_loop_activity_fallback(root)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return _detect_loop_activity_fallback(root)
    # ②若 git 仓库再 git log -1 取最近 commit
    try:
        log_result = subprocess.run(
            ['git', 'log', '-1', '--format=%H %ci'],
            cwd=str(root), capture_output=True, text=True, timeout=1.5,
        )
        if log_result.returncode == 0 and log_result.stdout.strip():
            return (True, [f'git log: {log_result.stdout.strip()[:80]}'])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    # git log 失败 → 降级到 ③④
    return _detect_loop_activity_fallback(root)


def detect_governance_tool_scope(root: Path) -> tuple[bool, list[str]]:
    """检测 SKILL.md/security.md/loop_constraints.md 含工具范围约束关键词（+2）。"""
    files = [
        root / 'SKILL.md',
        root / 'references' / 'do' / 'danger' / 'security.md',
        root / 'references' / 'do' / 'danger' / 'loop_constraints.md',
    ]
    hints = [
        r'least-privilege', r'tool scope', r'scoped tools', r'allow-list',
        r'read-only tools', r'permission scope', r'allowed-tools',
        r'权限约束', r'禁止访问', r'敏感文件', r'安全边界',
    ]
    return _detect_keyword_in_files(files, hints, '工具范围约束')


def detect_governance_stall(root: Path) -> tuple[bool, list[str]]:
    """检测 SKILL.md/loop_constraints.md 含停滞治理关键词（+2）。

    关键词覆盖：circuit breaker / max attempts / no-progress（连字符）
    / no_progress（下划线，SKILL.md 实际用词）/ stagnation / stalled / stuck / same error。
    """
    files = [
        root / 'SKILL.md',
        root / 'references' / 'do' / 'danger' / 'loop_constraints.md',
    ]
    hints = [
        r'circuit breaker', r'max attempts',
        r'no-progress', r'no_progress', r'stagnation',
        r'stalled', r'stuck', r'same error',
    ]
    return _detect_keyword_in_files(files, hints, '停滞治理')


def detect_governance_escalation(root: Path) -> tuple[bool, list[str]]:
    """检测 SKILL.md/loop_constraints.md 含升级治理关键词（+2）。"""
    files = [
        root / 'SKILL.md',
        root / 'references' / 'do' / 'danger' / 'loop_constraints.md',
    ]
    hints = [r'escalat', r'hand-off', r'HITL', r'human review', r'needs human', r'stop and ask', r'exit code 2']
    return _detect_keyword_in_files(files, hints, '升级治理')


def detect_safety_doc(root: Path) -> tuple[bool, list[str]]:
    """检测 references/do/danger/security.md 存在（+2）。"""
    return _detect_file_exists(root / 'references' / 'do' / 'danger' / 'security.md')


# @deprecated 预算管理已移除，保留仅为兼容旧版 JSON 输出格式（SCORE_WEIGHTS 不含此项，不影响评分）
def detect_skill_md_budget(root: Path) -> tuple[bool, list[str]]:
    """检测 SKILL.md 含 budget 关键词（保留兼容，不再评分）。"""
    hints = [r'budget', r'token cap', r'kill switch', r'loop-pause-all', r'预算']
    return _detect_keyword_in_files([root / 'SKILL.md'], hints, 'budget 关键词')


# ===== 审计主函数（T003 实现）=====

def _emit_downgrade_warns(
    signals: LoopSignals,
    intended_level: str,
    score: int,
) -> list[Finding]:
    """生成降级 warn finding：按 intended_level 检查所有必需项，缺失项各报一条 warn。

    金字塔传递性（H1 修复）：L3 ⊇ L2 ⊇ L1
        - L1 必需：task_state
        - L2 必需：triage + task_state（L1 必需项的超集）
        - L3 必需：verifier + triage + task_state + loop_activity

    独立 if 链（非 elif，M3 修复）：报全所有缺失项，而非只报第一个。

    Args:
        signals: 22 项信号
        intended_level: 按分数应达到的等级（'L1'/'L2'/'L3'）
        score: 当前 score（用于 warn 文案）

    Returns:
        warn finding 列表（可能为空）
    """
    findings: list[Finding] = []

    if intended_level == 'L1':
        # L1 必需：task_state
        if not signals.task_state[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L1 阈值（{score}≥{LEVEL_THRESHOLDS["L1"]}）但缺 task_state 信号——影响降级判定',
            ))

    elif intended_level == 'L2':
        # L2 必需（金字塔 ⊇ L1）：triage + task_state
        if not signals.triage[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L2 阈值（{score}≥{LEVEL_THRESHOLDS["L2"]}）但缺 triage 信号——影响降级判定',
            ))
        if not signals.task_state[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L2 阈值（{score}≥{LEVEL_THRESHOLDS["L2"]}）但缺 task_state 信号（金字塔 L2⊇L1 必需项）——影响降级判定',
            ))

    elif intended_level == 'L3':
        # L3 必需（金字塔 ⊇ L2 ⊇ L1）：verifier + triage + task_state + loop_activity
        if not signals.verifier[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L3 阈值（{score}≥{LEVEL_THRESHOLDS["L3"]}）但缺 verifier 信号——影响降级判定',
            ))
        if not signals.triage[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L3 阈值（{score}≥{LEVEL_THRESHOLDS["L3"]}）但缺 triage 信号（金字塔 L3⊇L2 必需项）——影响降级判定',
            ))
        if not signals.task_state[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L3 阈值（{score}≥{LEVEL_THRESHOLDS["L3"]}）但缺 task_state 信号（金字塔 L3⊇L1 必需项）——影响降级判定',
            ))
        if not signals.loop_activity[0]:
            findings.append(Finding(
                'warn',
                f'分数达到 L3 阈值（{score}≥{LEVEL_THRESHOLDS["L3"]}）但缺 loop_activity 信号（非 git 仓库或无近期 commit）——影响降级判定',
            ))

    return findings


def compute_score(signals: LoopSignals) -> ScoreResult:
    """从 21 项信号计算 score + level + assessment + findings（spec §7.4）。

    金字塔传递性（H1 修复）：L3 ⊇ L2 ⊇ L1
        - L3: score≥85 + verifier + triage + task_state + loop_activity
        - L2: score≥70 + triage + task_state（金字塔 L2⊇L1 必需项）
        - L1: score≥50 + task_state
        - L0: 其他

    降级 warn finding（H2+M3 修复）：
        - 所有降级路径都生成 warn finding（不再只 L2 分支生成）
        - 独立 if 链（非 elif）：报全所有缺失项

    Args:
        signals: 22 项信号 dataclass

    Returns:
        ScoreResult(score, level, assessment, findings)
        - score: 0-100 整数（base + 信号累加，钳制）
        - level: L0/L1/L2/L3
        - assessment: 等级描述文本
        - findings: 降级 warn finding 列表（按缺失项给具体中文 warn）
    """
    score = BASE_SCORE  # 5
    for field_name, weight in SCORE_WEIGHTS.items():
        hit, _ = getattr(signals, field_name)
        if hit:
            score += weight
    score = max(0, min(100, score))

    has_real_activity = signals.loop_activity[0]

    # 金字塔判定（L2 加 task_state 必需项，L2⊇L1）
    if (score >= LEVEL_THRESHOLDS['L3']
            and signals.verifier[0]
            and signals.triage[0]
            and signals.task_state[0]
            and has_real_activity):
        level = 'L3'
        findings: list[Finding] = []
    elif (score >= LEVEL_THRESHOLDS['L2']
            and signals.triage[0]
            and signals.task_state[0]):
        level = 'L2'
        # 降级 warn：按 score 应达到的等级检查缺失项（H2+M3 修复）
        if score >= LEVEL_THRESHOLDS['L3']:
            findings = _emit_downgrade_warns(signals, 'L3', score)
        else:
            findings = []
    elif score >= LEVEL_THRESHOLDS['L1'] and signals.task_state[0]:
        level = 'L1'
        # 降级 warn：从 L3 往下逐级检查，报全所有降级 warn（H2+M3 修复，独立 if 非 elif）
        findings = []
        if score >= LEVEL_THRESHOLDS['L3']:
            findings.extend(_emit_downgrade_warns(signals, 'L3', score))
        if score >= LEVEL_THRESHOLDS['L2']:
            findings.extend(_emit_downgrade_warns(signals, 'L2', score))
    else:
        level = 'L0'
        # 降级 warn：从 L3 往下逐级检查，报全所有降级 warn（H2+M3 修复，原代码零 warn）
        findings = []
        if score >= LEVEL_THRESHOLDS['L3']:
            findings.extend(_emit_downgrade_warns(signals, 'L3', score))
        if score >= LEVEL_THRESHOLDS['L2']:
            findings.extend(_emit_downgrade_warns(signals, 'L2', score))
        if score >= LEVEL_THRESHOLDS['L1']:
            findings.extend(_emit_downgrade_warns(signals, 'L1', score))

    assessment = ASSESSMENT_TEXTS[level]
    return ScoreResult(score=score, level=level, assessment=assessment, findings=findings)


def audit_project(root: Path) -> AuditResult:
    """
    审计项目目录，返回 AuditResult（spec §7.4）。

    Args:
        root: 项目根目录路径

    Returns:
        AuditResult 对象（target/score/level/assessment/signals/findings/recommendations）

    Raises:
        FileNotFoundError: root 不存在时（T007 在 main 中捕获并退码 1）
    """
    if not root.exists():
        raise FileNotFoundError(f'项目目录不存在：{root}')

    # 调用 21 个 detect_* 函数 → 组装 LoopSignals
    signals = LoopSignals(
        skill_md=detect_skill_md(root),
        references_count=detect_references_count(root),
        history_md=detect_history_md(root),
        pdca_coverage=detect_pdca_coverage(root),
        memory_main=detect_memory_main(root),
        memory_rj_recent=detect_memory_rj_recent(root),
        summary_rj=detect_summary_rj(root),
        docs_trio=detect_docs_trio(root),
        loop_tools=detect_loop_tools(root),
        task_state=detect_task_state(root),
        security=detect_security(root),
        triage=detect_triage(root),
        verifier=detect_verifier(root),
        constraints=detect_constraints(root),
        trigger_hooks=detect_trigger_hooks(root),
        loop_activity=detect_loop_activity(root),
        governance_tool_scope=detect_governance_tool_scope(root),
        governance_stall=detect_governance_stall(root),
        governance_escalation=detect_governance_escalation(root),
        safety_doc=detect_safety_doc(root),
        skill_md_budget=detect_skill_md_budget(root),
    )

    score, level, assessment, score_findings = compute_score(signals)

    # 生成 findings：每项信号命中=ok，加上 compute_score 产生的降级 warn
    findings: list[Finding] = []
    for field_name in SCORE_WEIGHTS:
        hit, evidence = getattr(signals, field_name)
        if hit:
            msg = f'{field_name}: {evidence[0] if evidence else "命中"}'
            findings.append(Finding('ok', msg))
    findings.extend(score_findings)

    # 生成 recommendations：按 level 给改进建议
    recommendations: list[str] = []
    if level == 'L0':
        recommendations.append('创建 SKILL.md 含"7条铁律"+ references/ 目录（≥30 个 .md）+ memory/memory_main.md + docs_rj/memory_rj/TASK_STATE_*.md')
    elif level == 'L1':
        recommendations.append('加 references/plan/route/loop_triage.md（+10）+ loop 工具链（loop_guard/loop_audit，+4）→ 升级到 L2')
    elif level == 'L2':
        recommendations.append('加 references/check/loop_verifier.md（+10）+ 确保 TASK_STATE 存在 + 确保 loopActivity（git 仓库）→ 升级到 L3')
    else:  # L3
        recommendations.append('已达 L3（unattended），可进入无人值守执行阶段；持续监控 loop_guard ledger 与 TASK_STATE mtime')

    return AuditResult(
        target=str(root),
        score=score,
        level=level,
        assessment=assessment,
        signals=signals,
        findings=findings,
        recommendations=recommendations,
    )


# ===== 输出格式化（T006 完善版：ASCII 进度条 + 分节装饰）=====

def _progress_bar(score: int, width: int = 10) -> str:
    """生成 ASCII 进度条：每格=10 分，已命中 █，未命中 ░。

    示例：score=100 → '██████████'，score=59 → '█████░░░░░'，score=5 → '░░░░░░░░░░'
    """
    filled = min(width, score // 10)
    return '█' * filled + '░' * (width - filled)


def format_human(r: AuditResult) -> str:
    """人类可读格式（T006 完善版）。

    输出结构：
        1. 头部：目标项目
        2. 分数行：ASCII 进度条 + score/100 + Level + Assessment
        3. Findings 列表（按 ok/warn/fail 分组，ok 在前）
        4. Recommendations 列表
    """
    lines: list[str] = []
    # 头部
    lines.append(f'目标项目: {r.target}')
    lines.append('')
    # 分数行（ASCII 进度条 + Level + Assessment）
    bar = _progress_bar(r.score)
    lines.append(f'Score: [{bar}] {r.score}/100')
    lines.append(f'Level: {r.level}')
    lines.append(f'Assessment: {r.assessment}')
    lines.append('')
    # Findings 列表（按 level 分组：ok 在前，warn 次之，fail 最后）
    lines.append(f'Findings ({len(r.findings)} 项):')
    order = {'ok': 0, 'warn': 1, 'fail': 2}
    sorted_findings = sorted(r.findings, key=lambda f: order.get(f.level, 99))
    for i, f in enumerate(sorted_findings, 1):
        lines.append(f'  [{i}] [{f.level}] {f.message}')
    lines.append('')
    # Recommendations 列表
    lines.append(f'Recommendations ({len(r.recommendations)} 项):')
    for i, rec in enumerate(r.recommendations, 1):
        lines.append(f'  [{i}] {rec}')
    return '\n'.join(lines)


def format_json(r: AuditResult) -> str:
    """JSON 格式（T006 完善版）。

    用 asdict 把 AuditResult 递归转 dict，default=str 兜底非原生 JSON 类型（如 Path），
    ensure_ascii=False 保留中文可读性。字段顺序按 dataclass 定义顺序（target/score/level/
    assessment/signals/findings/recommendations）。
    """
    return json.dumps(asdict(r), indent=2, ensure_ascii=False, default=str)


# ===== main =====

def main() -> int:
    """
    入口函数：解析参数，调用审计，输出结果，返回退出码。

    Returns:
        0=score≥50，2=score<50，1=异常（T007 完整实现）
    """
    # 强制 UTF-8 输出（Windows 控制台默认 GBK，会导致中文乱码）
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(
        prog='loop_admission.py',
        description='项目 loop 准入审计工具：输出 readiness score + level + findings',
    )
    parser.add_argument('path', type=str, help='项目目录路径')
    parser.add_argument(
        '--json',
        action='store_true',
        dest='as_json',
        help='输出 JSON 格式（默认 human 可读）',
    )
    args = parser.parse_args()

    root = Path(args.path)
    try:
        result = audit_project(root)
    except FileNotFoundError as e:
        # 路径不存在 → 退码 1（spec §4.4）
        print(f'[错误] {e}', file=sys.stderr)
        return 1
    except (PermissionError, OSError) as e:
        # 权限不足/OS 异常 → 退码 1（T007 完整实现）
        print(f'[错误] 访问项目目录失败：{e}', file=sys.stderr)
        return 1
    except Exception as e:
        # 其他未预期异常 → 退码 1（兜底，避免 Python 默认退码 1 无提示）
        print(f'[错误] 审计过程异常：{type(e).__name__}: {e}', file=sys.stderr)
        return 1

    if args.as_json:
        print(format_json(result))
    else:
        print(format_human(result))

    # 退码约定（spec §4.4）：score<50 退码 2，score≥50 退码 0
    return 0 if result.score >= EXIT_CODE_THRESHOLD else 2


if __name__ == '__main__':
    sys.exit(main())

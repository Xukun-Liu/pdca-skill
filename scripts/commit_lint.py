#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit_lint.py — Git Commit Message 校验脚本
============================================================

用途
----
给 pdca-skill 框架新增 commit message 校验能力，对齐 Conventional Commits 1.0.0
规范 + 框架 §0.6 任务名关联规则。支持三种子命令：
  lint       — 校验单条 commit message 字符串
  lint-file  — 校验文件中的 commit message（commit-msg hook 调用）
  check-last — 校验最近 N 条 commit（手动检查历史）

技术约束
--------
* 仅使用 Python 标准库（os/sys/re/json/argparse/subprocess），无 pip 依赖。
* 兼容 Python >= 3.8。
* 输出 JSON 格式，对齐 git_backup_tidy.py 风格。
* 退出码：0=通过, 1=WARNING（不阻断）, 2=ERROR（阻断提交）。

校验规则
--------
* R1 type 必须在 VALID_TYPES 中                     [ERROR]
* R2 subject ≤50 字符                                [WARNING]
* R3 subject 用祈使句（检测 -ed 结尾，过去式）       [WARNING]
* R4 subject 结尾不加句号                            [WARNING]
* R5 body 每行 ≤72 字符                              [WARNING]
* R6 WIP commit 必须用 chore(wip): 格式              [ERROR]
* R7 Refs footer 的 task_name 格式 [a-z0-9_]+        [ERROR]
* R8 混合改动检测（docs_rj/ + src/ 同时改）          [WARNING]
* R9 BREAKING CHANGE 必须用 ! 或 footer              [ERROR]
* R10 chore(release) subject 必须 vX.Y.Z 格式        [ERROR]

================================================================================
运行方式
================================================================================
  python commit_lint.py lint "feat(api): add endpoint" [--task NAME] [--json]
  python commit_lint.py lint-file .git/COMMIT_EDITMSG [--task NAME] [--json]
  python commit_lint.py check-last [--n 5] [--json]
"""

import argparse
import json
import os
import re
import subprocess
import sys

# ===========================================================================
# 常量
# ===========================================================================

# Conventional Commits 1.0.0 + Angular 规范的 type 枚举
VALID_TYPES = {
    'feat', 'fix', 'docs', 'style', 'refactor',
    'test', 'chore', 'perf', 'ci', 'revert', 'build',
}

# 可选 scope（可扩展，未在列表中的 scope 仅告警不阻断）
VALID_SCOPES = {
    'api', 'core', 'database', 'ui', 'config', 'utils',
    'tests', 'wip', 'spec', 'memory', 'task', 'handoff',
}

MAX_SUBJECT_LEN = 50
MAX_BODY_LINE_LEN = 72

# 任务名格式（对齐 SKILL.md §0.6 + generate_docs.py TASK_NAME_RE）
TASK_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')

# commit message 头部正则：<type>(<scope>)!?: <subject>
# 参考 Conventional Commits 1.0.0 规范
HEADER_PATTERN = re.compile(
    r'^(?P<type>[a-z]+)'           # type（小写字母）
    r'(?:\((?P<scope>[a-z0-9_-]+)\))?'  # 可选 scope（圆括号）
    r'(?P<breaking>!)?'            # 可选 breaking 标记
    r':\s+'                        # 冒号 + 至少一个空格
    r'(?P<subject>.+)$'            # subject
)

# Refs footer 正则：Refs: {task_name}
REFS_PATTERN = re.compile(r'^Refs:\s*(?P<task_name>\S+)\s*$', re.MULTILINE)

# WIP 检测正则
WIP_PATTERN = re.compile(r'^(?:fixup|squash|wip)\b', re.IGNORECASE)

# 祈使句检测：以 -ed 结尾的过去式（简单启发式）
IMPERATIVE_ANTI_PATTERN = re.compile(
    r'\b\w+(ed|s)\b(?=\s|$)', re.IGNORECASE
)

# R10: release commit subject 格式（v{X.Y.Z}，对齐 semver 语义化版本）
RELEASE_SUBJECT_PATTERN = re.compile(r'^v\d+\.\d+\.\d+$')


# ===========================================================================
# 数据结构
# ===========================================================================

class Issue:
    """校验问题。"""

    def __init__(self, rule, severity, message, line=1):
        self.rule = rule
        self.severity = severity  # 'ERROR' or 'WARNING'
        self.message = message
        self.line = line

    def to_dict(self):
        return {
            'rule': self.rule,
            'severity': self.severity,
            'message': self.message,
            'line': self.line,
        }


class LintResult:
    """校验结果。"""

    def __init__(self, passed, issues, parsed=None, exit_code=0):
        self.passed = passed
        self.issues = issues
        self.parsed = parsed or {}
        self.exit_code = exit_code

    def to_dict(self):
        return {
            'passed': self.passed,
            'exit_code': self.exit_code,
            'issues': [i.to_dict() for i in self.issues],
            'parsed': self.parsed,
        }


# ===========================================================================
# 核心函数：解析 commit message
# ===========================================================================

def parse_commit_message(msg):
    """解析 commit message 为结构化字典。

    Args:
        msg: commit message 字符串（可能含多行）

    Returns:
        dict: {
            type, scope, subject, body, footers,
            breaking_change, has_refs, refs_task_name,
            is_wip, raw
        }
    """
    if not msg or not msg.strip():
        return {
            'type': None, 'scope': None, 'subject': None,
            'body': '', 'footers': [], 'breaking_change': False,
            'has_refs': False, 'refs_task_name': None,
            'is_wip': False, 'raw': msg or '',
        }

    # 统一换行符（Windows \r\n -> \n）
    msg_normalized = msg.replace('\r\n', '\n').replace('\r', '\n')
    lines = msg_normalized.split('\n')

    # 第一行 = header
    header = lines[0].strip()
    body_lines = lines[1:]

    # 检测 WIP
    is_wip = bool(WIP_PATTERN.match(header))

    # 解析 header
    match = HEADER_PATTERN.match(header)
    if not match:
        return {
            'type': None, 'scope': None, 'subject': header,
            'body': '\n'.join(body_lines).strip(),
            'footers': [], 'breaking_change': False,
            'has_refs': False, 'refs_task_name': None,
            'is_wip': is_wip, 'raw': msg,
        }

    parsed_type = match.group('type')
    parsed_scope = match.group('scope')
    parsed_subject = match.group('subject').strip()
    breaking_mark = bool(match.group('breaking'))

    # 解析 body 和 footers
    body = []
    footers = []
    has_breaking_footer = False
    has_refs = False
    refs_task_name = None

    # body 与 header 之间应有一个空行
    # footers 是 body 之后以 "Token: value" 格式的行
    in_footer_section = False

    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            # 空行：可能是 body 内分隔或 body->footer 分隔
            if body and not in_footer_section:
                # 检查后续是否进入 footer
                in_footer_section = True
            continue

        # footer 检测：形如 "Token: value" 或 "BREAKING CHANGE: ..."
        # Conventional Commits footer token 用 - 连字符分隔（如 Acked-by），允许首字母大写+小写
        footer_match = re.match(r'^([A-Z][a-zA-Z-]+|BREAKING CHANGE)\s*:\s*(.+)$', stripped)
        if footer_match and (in_footer_section or not body):
            token = footer_match.group(1)
            value = footer_match.group(2)
            footers.append({'token': token, 'value': value})

            if token == 'BREAKING CHANGE':
                has_breaking_footer = True

            if token == 'Refs':
                has_refs = True
                refs_task_name = value.strip()
        else:
            body.append(stripped)
            in_footer_section = False

    return {
        'type': parsed_type,
        'scope': parsed_scope,
        'subject': parsed_subject,
        'body': '\n'.join(body).strip(),
        'footers': footers,
        'breaking_change': breaking_mark or has_breaking_footer,
        'has_refs': has_refs,
        'refs_task_name': refs_task_name,
        'is_wip': is_wip,
        'raw': msg,
    }


# ===========================================================================
# 校验函数
# ===========================================================================

def validate_format(parsed):
    """校验格式规则 R1-R5, R9。"""
    issues = []

    # R1: type 必须有效
    if parsed['type'] is None:
        issues.append(Issue(
            'R1', 'ERROR',
            'Missing or invalid type. Header must be "<type>(scope): <subject>"',
            line=1,
        ))
    elif parsed['type'] not in VALID_TYPES:
        issues.append(Issue(
            'R1', 'ERROR',
            f"Invalid type '{parsed['type']}'. Must be one of: {', '.join(sorted(VALID_TYPES))}",
            line=1,
        ))

    # R2: subject 长度
    if parsed['subject']:
        subj_len = len(parsed['subject'])
        if subj_len > MAX_SUBJECT_LEN:
            issues.append(Issue(
                'R2', 'WARNING',
                f'Subject too long ({subj_len} chars, max {MAX_SUBJECT_LEN})',
                line=1,
            ))

    # R3: 祈使句（简单启发式：检测过去式 -ed）
    if parsed['subject']:
        first_word = parsed['subject'].split()[0] if parsed['subject'].split() else ''
        if first_word and re.match(r'^\w+ed$', first_word, re.IGNORECASE):
            issues.append(Issue(
                'R3', 'WARNING',
                f"Subject may use past tense '{first_word}'. Prefer imperative (e.g. 'add' not 'added')",
                line=1,
            ))

    # R4: subject 结尾不加句号
    if parsed['subject'] and parsed['subject'].rstrip().endswith('.'):
        issues.append(Issue(
            'R4', 'WARNING',
            "Subject should not end with '.'",
            line=1,
        ))

    # R5: body 每行长度
    if parsed['body']:
        for i, line in enumerate(parsed['body'].split('\n'), start=2):
            if len(line) > MAX_BODY_LINE_LEN:
                issues.append(Issue(
                    'R5', 'WARNING',
                    f'Body line {i} too long ({len(line)} chars, max {MAX_BODY_LINE_LEN})',
                    line=i,
                ))

    # R9: BREAKING CHANGE 格式
    # 如果 subject 含 BREAKING 但没用 ! 或 footer，报错
    if 'BREAKING' in (parsed['subject'] or '').upper() and not parsed['breaking_change']:
        issues.append(Issue(
            'R9', 'ERROR',
            "BREAKING CHANGE must be marked with '!' after type/scope or as a footer",
            line=1,
        ))

    return issues


def validate_task_ref(parsed, task_name=None):
    """校验任务名关联规则 R6, R7。"""
    issues = []

    # R6: WIP commit 必须用 chore(wip): 格式
    if parsed['is_wip']:
        if parsed['type'] != 'chore' or parsed['scope'] != 'wip':
            issues.append(Issue(
                'R6', 'ERROR',
                "WIP commit must use 'chore(wip): {description}' format",
                line=1,
            ))

    # R7: Refs footer 的 task_name 格式
    if parsed['has_refs'] and parsed['refs_task_name']:
        tn = parsed['refs_task_name']
        if not TASK_NAME_PATTERN.match(tn):
            issues.append(Issue(
                'R7', 'ERROR',
                f"Invalid task_name '{tn}' in Refs footer. Must match [a-z][a-z0-9_]*",
                line=1,
            ))

    # 如果外部传入 task_name，也校验
    if task_name and not TASK_NAME_PATTERN.match(task_name):
        issues.append(Issue(
            'R7', 'ERROR',
            f"Invalid --task '{task_name}'. Must match [a-z][a-z0-9_]*",
            line=1,
        ))

    return issues


def validate_atomic(parsed, changed_files=None):
    """校验原子性规则 R8（混合改动检测）。"""
    issues = []

    if not changed_files:
        return issues

    has_docs = any(f.startswith('docs_rj/') for f in changed_files)
    has_code = any(
        not f.startswith('docs_rj/') and not f.startswith('.')
        and (f.endswith('.py') or f.endswith('.js') or f.endswith('.ts')
             or f.endswith('.java') or f.endswith('.go') or f.endswith('.rs'))
        for f in changed_files
    )

    if has_docs and has_code:
        issues.append(Issue(
            'R8', 'WARNING',
            'Mixed changes detected: both docs_rj/ files and source code. '
            'Consider splitting into separate commits (see git_workflow.md §2.6)',
            line=1,
        ))

    return issues


def validate_release(parsed):
    """校验 release commit 规则 R10。

    R10: chore(release) 的 subject 必须是 v{X.Y.Z} 格式（对齐 semver）。
    触发条件：type=chore 且 scope=release（双条件，避免误报）。
    严重度：ERROR（阻断提交）。

    Args:
        parsed: parse_commit_message 返回的字典

    Returns:
        list: Issue 列表（可能为空）
    """
    issues = []

    # R10: 仅当 type=chore 且 scope=release 时触发（双条件避免误报）
    if parsed['type'] == 'chore' and parsed['scope'] == 'release':
        subject = parsed['subject'] or ''
        if not RELEASE_SUBJECT_PATTERN.match(subject):
            issues.append(Issue(
                'R10', 'ERROR',
                f"Release commit subject must be 'vX.Y.Z' format "
                f"(e.g. 'v1.0.0'), got '{subject}'",
                line=1,
            ))

    return issues


def lint(msg, task_name=None, changed_files=None):
    """主校验入口。

    Args:
        msg: commit message 字符串
        task_name: 可选，外部传入的任务名
        changed_files: 可选，改动文件列表（用于 R8）

    Returns:
        LintResult
    """
    parsed = parse_commit_message(msg)

    issues = []
    issues.extend(validate_format(parsed))
    issues.extend(validate_task_ref(parsed, task_name))
    issues.extend(validate_atomic(parsed, changed_files))
    issues.extend(validate_release(parsed))

    has_error = any(i.severity == 'ERROR' for i in issues)
    has_warning = any(i.severity == 'WARNING' for i in issues)

    if has_error:
        exit_code = 2
        passed = False
    elif has_warning:
        exit_code = 1
        passed = True  # WARNING 不阻断
    else:
        exit_code = 0
        passed = True

    return LintResult(passed=passed, issues=issues, parsed=parsed, exit_code=exit_code)


# ===========================================================================
# CLI 入口
# ===========================================================================

def get_changed_files():
    """获取当前暂存区改动文件列表（用于 R8 检测）。"""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split('\n') if f.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return []


def cmd_lint(args):
    """lint 子命令：校验单条 commit message 字符串。"""
    result = lint(args.message, task_name=args.task, changed_files=get_changed_files())
    output = result.to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2) if args.json else _format_human(output))
    return result.exit_code


def cmd_lint_file(args):
    """lint-file 子命令：校验文件中的 commit message。"""
    if not os.path.isfile(args.file):
        print(json.dumps({
            'passed': False, 'exit_code': 2,
            'issues': [{'rule': 'FILE', 'severity': 'ERROR',
                        'message': f'File not found: {args.file}', 'line': 0}],
            'parsed': {},
        }, ensure_ascii=False, indent=2))
        return 2

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            msg = f.read()
    except IOError as e:
        print(json.dumps({
            'passed': False, 'exit_code': 2,
            'issues': [{'rule': 'IO', 'severity': 'ERROR',
                        'message': f'Read error: {e}', 'line': 0}],
            'parsed': {},
        }, ensure_ascii=False, indent=2))
        return 2

    # commit message 文件中 git 会加 # 注释行，去掉
    msg = '\n'.join(
        line for line in msg.split('\n')
        if not line.strip().startswith('#')
    ).strip()

    result = lint(msg, task_name=args.task, changed_files=get_changed_files())
    output = result.to_dict()
    print(json.dumps(output, ensure_ascii=False, indent=2) if args.json else _format_human(output))
    return result.exit_code


def cmd_check_last(args):
    """check-last 子命令：校验最近 N 条 commit。"""
    n = args.n
    try:
        result = subprocess.run(
            ['git', 'log', f'-{n}', '--pretty=format:%H%n%B%n---END---'],
            capture_output=True, text=True, timeout=10,
            encoding='utf-8', errors='replace',
        )
        if result.returncode != 0:
            print(json.dumps({
                'passed': False, 'exit_code': 2,
                'issues': [{'rule': 'GIT', 'severity': 'ERROR',
                            'message': f'git log failed: {result.stderr}', 'line': 0}],
                'parsed': {},
            }, ensure_ascii=False, indent=2))
            return 2
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(json.dumps({
            'passed': False, 'exit_code': 2,
            'issues': [{'rule': 'GIT', 'severity': 'ERROR',
                        'message': f'git not available: {e}', 'line': 0}],
            'parsed': {},
        }, ensure_ascii=False, indent=2))
        return 2

    # 解析 git log 输出
    commits = result.stdout.split('---END---\n')
    commits = [c.strip() for c in commits if c.strip()]

    results = []
    overall_passed = True
    overall_exit = 0

    for commit_block in commits:
        lines = commit_block.split('\n')
        if len(lines) < 2:
            continue
        commit_hash = lines[0]
        msg = '\n'.join(lines[1:]).strip()
        r = lint(msg)
        results.append({
            'hash': commit_hash,
            'passed': r.passed,
            'exit_code': r.exit_code,
            'subject': r.parsed.get('subject', ''),
            'issues': [i.to_dict() for i in r.issues],
        })
        if r.exit_code == 2:
            overall_passed = False
            overall_exit = 2
        elif r.exit_code == 1 and overall_exit == 0:
            overall_exit = 1

    output = {
        'passed': overall_passed,
        'exit_code': overall_exit,
        'commits_checked': len(results),
        'commits': results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2) if args.json else _format_check_last_human(output))
    return overall_exit


def _format_human(output):
    """人类可读格式输出。"""
    lines = []
    if output['passed']:
        lines.append('[PASS] commit message 合规')
    else:
        lines.append('[FAIL] commit message 不合规')

    if output['issues']:
        lines.append('')
        lines.append('Issues:')
        for i in output['issues']:
            emoji = '❌' if i['severity'] == 'ERROR' else '⚠️'
            lines.append(f"  {emoji} [{i['rule']}] {i['message']}")

    p = output.get('parsed', {})
    if p:
        lines.append('')
        lines.append('Parsed:')
        lines.append(f"  type: {p.get('type')}")
        lines.append(f"  scope: {p.get('scope')}")
        lines.append(f"  subject: {p.get('subject')}")
        if p.get('has_refs'):
            lines.append(f"  refs: {p.get('refs_task_name')}")
        if p.get('breaking_change'):
            lines.append(f"  breaking_change: True")

    return '\n'.join(lines)


def _format_check_last_human(output):
    """check-last 人类可读格式。"""
    lines = []
    lines.append(f"Checked {output['commits_checked']} commits")
    lines.append(f"Overall: {'PASS' if output['passed'] else 'FAIL'}")
    lines.append('')
    for c in output['commits']:
        status = '✅' if c['passed'] else ('❌' if c['exit_code'] == 2 else '⚠️')
        lines.append(f"{status} {c['hash'][:8]} {c['subject']}")
        for i in c['issues']:
            emoji = '❌' if i['severity'] == 'ERROR' else '⚠️'
            lines.append(f"    {emoji} [{i['rule']}] {i['message']}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Git Commit Message 校验脚本（对齐 Conventional Commits + pdca-skill 框架规范）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
校验规则：
  R1 type 必须有效                    [ERROR]
  R2 subject ≤50 字符                 [WARNING]
  R3 subject 用祈使句                 [WARNING]
  R4 subject 结尾不加句号             [WARNING]
  R5 body 每行 ≤72 字符               [WARNING]
  R6 WIP 必须 chore(wip): 格式        [ERROR]
  R7 Refs task_name 格式 [a-z0-9_]+   [ERROR]
  R8 混合改动检测                     [WARNING]
  R9 BREAKING CHANGE 格式             [ERROR]
  R10 chore(release) subject 必须 vX.Y.Z 格式  [ERROR]

退出码：0=通过, 1=WARNING, 2=ERROR
        """,
    )
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # lint
    p_lint = subparsers.add_parser('lint', help='校验单条 commit message 字符串')
    p_lint.add_argument('message', help='commit message 字符串')
    p_lint.add_argument('--task', help='任务名（校验 R7）')
    p_lint.add_argument('--json', action='store_true', help='JSON 输出')
    p_lint.set_defaults(func=cmd_lint)

    # lint-file
    p_file = subparsers.add_parser('lint-file', help='校验文件中的 commit message')
    p_file.add_argument('file', help='commit message 文件路径（如 .git/COMMIT_EDITMSG）')
    p_file.add_argument('--task', help='任务名（校验 R7）')
    p_file.add_argument('--json', action='store_true', help='JSON 输出')
    p_file.set_defaults(func=cmd_lint_file)

    # check-last
    p_last = subparsers.add_parser('check-last', help='校验最近 N 条 commit')
    p_last.add_argument('--n', type=int, default=5, help='校验最近 N 条（默认 5）')
    p_last.add_argument('--json', action='store_true', help='JSON 输出')
    p_last.set_defaults(func=cmd_check_last)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())

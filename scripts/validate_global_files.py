#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_global_files.py — pdca-skill 全局文件验证器

作用
----
按 protocol.FIELD_CONTRACTS 验证项目文件是否符合字段合同。
对应铁律7 逐项核对：每个文档角色（spec / task / handoff / project_memory）
必须含合同声明的 required 字段（`**{label}**:` 格式），缺字段即记为 FAIL。

三个核心函数 + 一个 CLI：
  - walk_markdown_files(root_dir, max_depth=3)：遍历 .md 文件，限制深度
  - validate_file_against_contract(file_path, contract)：按合同逐字段验证
  - validate_global_files(skill_root)：遍历 FILE_ROLES × FIELD_CONTRACTS 汇总
  - main()：argparse CLI（--skill-dir / --json / --verbose）

借鉴来源: 业界全局文件验证实践
Traceability: SKILL.md §0 §1, references/common/pa/trigger_hooks.md, protocol/field_contracts.py
设计来源: SKILL.md §3 文档体系, protocol/file_roles.py + field_contracts.py

技术约束
--------
* 纯 Python 标准库（os / sys / re / json / argparse / logging / glob）。
* 依赖 protocol 包（FIELD_CONTRACTS / VALIDATION_POLICY / FILE_ROLES）。
* 零新增第三方依赖。
* 验证失败不崩溃，返回 failed 列表（B5 隔离）。

运行
----
  python scripts/validate_global_files.py [--skill-dir PATH] [--json] [--verbose]
"""

import os
import sys
import re
import json
import argparse
import logging
import glob

# 让脚本能 import protocol 包（skill 根目录在 scripts/ 的上一级）
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

# 延迟 import + try/except，避免 protocol 故障导致整个脚本崩溃
try:
    from protocol import FIELD_CONTRACTS, VALIDATION_POLICY, FILE_ROLES  # noqa: E402
    _HAVE_PROTOCOL = True
    _PROTOCOL_IMPORT_ERR = None
except Exception as exc:  # noqa: E722
    _HAVE_PROTOCOL = False
    _PROTOCOL_IMPORT_ERR = str(exc)

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# walk 时跳过的目录（与 route_check._collect_md_files 对齐，增补 .skill_graph_cache）
_IGNORE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', '.skill_graph_cache',
}

# 文件角色 → 合同名 映射（FILE_ROLES.role → FIELD_CONTRACTS key）
# 显式映射避免误推；不在映射表中的角色不验证合同
# v1.0.0 期2 T013 修复：新增 3 类全局文件映射，让 validate_global_files.py 真正验证全局文件
_ROLE_TO_CONTRACT = {
    'spec_doc': 'spec',
    'task_doc': 'task',
    'main_entry': 'skill_main',
    'project_doc': 'readme',
    'global_memory': 'global_memory',
}


# ===========================================================================
# 辅助函数
# ===========================================================================
def _read_text(path):
    """读取文本文件，失败返回空串（对齐 route_check._read_text 行为）。"""
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ''


def _expand_pattern(skill_root, pattern):
    """把 FILE_ROLES 中的路径模式展开为绝对路径列表。

    FILE_ROLES 的 key 是相对 skill 根的 glob 模式，如：
      - 'SKILL.md'              → 单文件
      - 'docs_rj/spec_rj/*.md' → 一级 glob
      - 'references/*.md'      → 一级 glob
      - 'scripts/*.py'          → 一级 glob

    Args:
        skill_root: skill 包根目录绝对路径。
        pattern: FILE_ROLES 中的路径模式字符串。

    Returns:
        list[str]: 匹配到的文件绝对路径列表（已排序，仅含文件，过滤目录）。
    """
    full_pattern = os.path.join(skill_root, pattern)
    # glob.glob 自动处理 * 通配符；无通配符则返回单文件（若存在）
    matches = glob.glob(full_pattern)
    files = [m for m in matches if os.path.isfile(m)]
    return sorted(files)


def _map_role_to_contract(role_name, path_pattern):
    """根据文件角色名和路径模式推导对应的合同名。

    Args:
        role_name: FILE_ROLES[key]['role'] 字段值，如 'spec_doc'。
        path_pattern: FILE_ROLES 的 key（路径模式），如 'docs_rj/spec_rj/*.md'。

    Returns:
        str or None: 合同名（FIELD_CONTRACTS 的 key），如 'spec'；
                     无对应合同返回 None（不验证）。
    """
    # 优先按显式映射表
    if role_name in _ROLE_TO_CONTRACT:
        return _ROLE_TO_CONTRACT[role_name]
    # 兜底：基于路径模式推导（覆盖 FILE_ROLES 未列全的 handoff_rj / memory_rj）
    if 'spec_rj' in path_pattern:
        return 'spec'
    if 'task_rj' in path_pattern:
        return 'task'
    if 'handoff_rj' in path_pattern:
        return 'handoff'
    if 'memory_rj' in path_pattern:
        return 'project_memory'
    return None


def _candidate_labels(field_name):
    """从字段名（snake_case）构造候选 label 列表，覆盖大小写/空格变体。

    例：'how_to' → ['how_to', 'How to', 'How To', 'HowTo', 'HOW TO', 'HOW_TO']
        'task' → ['task', 'Task', 'TASK']

    Args:
        field_name: 字段名（如 'task' / 'how_to' / 'current_status'）。

    Returns:
        list[str]: 候选 label 列表（去重，保序）。
    """
    labels = []
    seen = set()

    def _add(s):
        if s and s not in seen:
            seen.add(s)
            labels.append(s)

    # 1. 原样（snake_case）
    _add(field_name)
    # 2. 首字母大写（仅首词）
    _add(field_name.capitalize())
    # 3. Title Case（下划线转空格 + 每词首字母大写）
    _add(field_name.replace('_', ' ').title())
    # 4. 下划线转空格（原大小写）
    _add(field_name.replace('_', ' '))
    # 5. 全大写
    _add(field_name.upper())
    # 6. 下划线转空格 + 全大写
    _add(field_name.upper().replace('_', ' '))
    # 7. 驼峰（how_to → HowTo）
    parts = [p for p in field_name.split('_') if p]
    if parts:
        camel = ''.join(p[:1].upper() + p[1:] for p in parts)
        _add(camel)
    return labels


# ===========================================================================
# 1. walk_markdown_files
# ===========================================================================
def walk_markdown_files(root_dir, max_depth=3):
    """遍历 root_dir 下所有 .md 文件，限制目录深度。

    深度定义：root_dir 自身 depth=0；其直接子目录 depth=1；以此类推。
    max_depth=3 表示最多遍历到 depth=3 的目录；depth > max_depth 的子目录不进入。
    任何 depth <= max_depth 的目录内的 .md 文件都会被收集。

    Args:
        root_dir: 遍历根目录绝对路径。
        max_depth: 最大深度（默认 3）。root_dir 自身 depth=0。

    Returns:
        list[str]: .md 文件绝对路径列表（已排序）。
    """
    root_dir = os.path.abspath(root_dir)
    md_files = []
    for root, dirs, files in os.walk(root_dir):
        # 计算当前目录相对 root_dir 的深度
        rel = os.path.relpath(root, root_dir)
        if rel == '.':
            depth = 0
        else:
            # os.sep 自动适配 Windows '\\' / POSIX '/'
            depth = rel.count(os.sep) + 1

        # 过滤忽略目录（原地修改 dirs，阻止 os.walk 进入）
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]

        # 当前深度已达 max_depth：不进入子目录（当前目录的 .md 仍处理）
        if depth >= max_depth:
            dirs[:] = []

        for f in files:
            if f.endswith('.md'):
                md_files.append(os.path.join(root, f))

    return sorted(md_files)


# ===========================================================================
# 2. validate_file_against_contract
# ===========================================================================
def validate_file_against_contract(file_path, contract):
    """按合同逐字段验证单个文件。

    对合同的每个 required 字段，验证文件中是否存在 `**{label}**:` 格式
    （label 大小写/空格变体均接受，见 _candidate_labels）。

    Args:
        file_path: 待验证文件绝对路径。
        contract: FIELD_CONTRACTS 中的合同 dict，形如：
            {
                'required_when': '...',
                'fields': {
                    'task': {'level': 'required', 'source': 'file'},
                    'timestamp': {'level': 'required', 'source': 'file'},
                    ...
                }
            }
            仅验证 level=='required' 的字段；recommended/optional 跳过。

    Returns:
        dict: {
            'file': str,             # 文件绝对路径
            'passed': bool,          # 是否所有 required 字段都找到
            'missing_fields': list,  # 缺失的 required 字段名列表
            'found_fields': list,    # 找到的 required 字段名列表
        }
    """
    content = _read_text(file_path)
    if not content:
        return {
            'file': file_path,
            'passed': False,
            'missing_fields': [],
            'found_fields': [],
            'reason': '文件读取失败或为空',
        }

    fields = contract.get('fields', {}) if isinstance(contract, dict) else {}
    missing_fields = []
    found_fields = []

    for field_name, field_def in fields.items():
        if not isinstance(field_def, dict):
            continue
        level = field_def.get('level', '')
        if level != 'required':
            # 仅验证 required 字段（recommended/optional 跳过）
            continue
        # 匹配模式：默认 bold_label（**{label}**:），可选 markdown_header（^## .*{label}）
        # v1.0.0 期2 T013 修复：支持全局文件 markdown 章节验证
        match_mode = field_def.get('match', 'bold_label')
        # 构造候选 label 列表，任一匹配即算找到
        labels = _candidate_labels(field_name)
        found = False
        for label in labels:
            if match_mode == 'markdown_header':
                # markdown 章节匹配：^## 后含 label 的行（MULTILINE + 部分匹配）
                # 如 label='条铁律' 匹配 '## ⚡ 8条铁律'（不锁死条数）
                pattern = re.compile(
                    r'^##\s+.*' + re.escape(label),
                    re.IGNORECASE | re.MULTILINE,
                )
            else:
                # 默认 bold_label 模式：匹配 **{label}**: 格式
                # label 中含空格的也支持；冒号前可允许任意空白（**Task**: 或 **Task** : ）
                pattern = re.compile(
                    r'\*\*\s*' + re.escape(label) + r'\s*\*\*\s*:',
                    re.IGNORECASE,
                )
            if pattern.search(content):
                found = True
                break
        if found:
            found_fields.append(field_name)
        else:
            missing_fields.append(field_name)

    return {
        'file': file_path,
        'passed': len(missing_fields) == 0,
        'missing_fields': missing_fields,
        'found_fields': found_fields,
    }


# ===========================================================================
# 3. validate_global_files
# ===========================================================================
def validate_global_files(skill_root):
    """遍历 FILE_ROLES 每个角色的文件，按 FIELD_CONTRACTS 验证。

    逻辑：
      1. 遍历 FILE_ROLES 每个 (path_pattern, role_def)
      2. 用 _map_role_to_contract 推导合同名；无合同的角色跳过
      3. 用 _expand_pattern 把路径模式展开为具体文件列表
      4. 对每个文件调 validate_file_against_contract 验证
      5. 汇总 total_files / validated / passed / failed / results

    Args:
        skill_root: skill 包根目录绝对路径。

    Returns:
        dict: {
            'total_files': int,    # FILE_ROLES 覆盖到的文件总数
            'validated': int,      # 实际跑了合同验证的文件数
            'passed': int,         # 验证通过的文件数
            'failed': int,         # 验证失败的文件数
            'results': list[dict], # 每个文件的验证结果
            'skipped_roles': list, # 跳过（无对应合同）的角色列表
        }
    """
    skill_root = os.path.abspath(skill_root)
    results = []
    skipped_roles = []
    total_files = 0
    validated = 0
    passed_count = 0
    failed_count = 0

    if not _HAVE_PROTOCOL:
        return {
            'total_files': 0,
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'results': [],
            'skipped_roles': [],
            'reason': 'protocol 包不可用: %s' % _PROTOCOL_IMPORT_ERR,
        }

    for path_pattern, role_def in FILE_ROLES.items():
        role_name = role_def.get('role', '') if isinstance(role_def, dict) else ''
        contract_name = _map_role_to_contract(role_name, path_pattern)
        if contract_name is None:
            skipped_roles.append({
                'path_pattern': path_pattern,
                'role': role_name,
                'reason': '无对应合同（不在 _ROLE_TO_CONTRACT 映射）',
            })
            continue

        # 用户数据外置后 docs_rj/ 不在包内（实际在 ~/.pdca-skill/data/docs_rj/），
        # 本地开发环境的 docs_rj/ 是项目级文件，不归"全局文件验证"管，跳过避免误报。
        if path_pattern.startswith('docs_rj/'):
            skipped_roles.append({
                'path_pattern': path_pattern,
                'role': role_name,
                'reason': '用户数据外置：docs_rj/ 为项目级文件，不归全局文件验证',
            })
            continue

        contract = FIELD_CONTRACTS.get(contract_name)
        if not contract or not isinstance(contract, dict):
            skipped_roles.append({
                'path_pattern': path_pattern,
                'role': role_name,
                'contract': contract_name,
                'reason': '合同 %s 不存在或非 dict' % contract_name,
            })
            continue

        # 展开路径模式为具体文件列表
        files = _expand_pattern(skill_root, path_pattern)
        total_files += len(files)

        for fp in files:
            try:
                r = validate_file_against_contract(fp, contract)
                validated += 1
                if r.get('passed'):
                    passed_count += 1
                else:
                    failed_count += 1
                # 附加元数据（合同名、角色名），便于报告定位
                r['contract'] = contract_name
                r['role'] = role_name
                results.append(r)
            except Exception as exc:  # noqa: E722 防御性兜底
                logger.error("验证 %s 时异常: %s", fp, exc)
                failed_count += 1
                validated += 1
                results.append({
                    'file': fp,
                    'contract': contract_name,
                    'role': role_name,
                    'passed': False,
                    'missing_fields': [],
                    'found_fields': [],
                    'reason': '验证异常: %s' % exc,
                })

    return {
        'total_files': total_files,
        'validated': validated,
        'passed': passed_count,
        'failed': failed_count,
        'results': results,
        'skipped_roles': skipped_roles,
    }


# ===========================================================================
# CLI / main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='pdca-skill 全局文件验证器（stdlib-only）')
    parser.add_argument('--skill-dir', default=None,
                        help='skill 包根目录（默认：scripts/ 的上级目录）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果到 stdout（日志仍走 stderr）')
    parser.add_argument('--verbose', action='store_true',
                        help='详细输出（含每个文件的 found/missing 字段明细）')
    args = parser.parse_args()

    # 默认 skill-dir = 脚本所在 scripts/ 的上级目录（仓库根）
    if args.skill_dir:
        skill_dir = os.path.abspath(args.skill_dir)
    else:
        skill_dir = _SKILL_ROOT

    if not os.path.isdir(skill_dir):
        logger.error("skill 目录不存在: %s", skill_dir)
        return 2

    # 告警 protocol 包导入失败（仅告警不阻断，B5 隔离）
    if not _HAVE_PROTOCOL:
        logger.warning("protocol 包导入失败（仅告警，不阻断）: %s", _PROTOCOL_IMPORT_ERR)
    else:
        logger.info("protocol 包就绪：FIELD_CONTRACTS=%d 类 / FILE_ROLES=%d 角色",
                    len(FIELD_CONTRACTS), len(FILE_ROLES))

    logger.info("=== 全局文件验证（validate_global_files）开始，skill_dir=%s ===", skill_dir)
    summary = validate_global_files(skill_dir)

    total = summary.get('total_files', 0)
    validated = summary.get('validated', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    logger.info("=== 全局文件验证完成：total=%d / validated=%d / passed=%d / failed=%d ===",
                total, validated, passed, failed)

    if args.json:
        # JSON 到 stdout，日志仍在 stderr
        payload = {
            'skill_dir': skill_dir,
            'total_files': total,
            'validated': validated,
            'passed': passed,
            'failed': failed,
            'results': summary.get('results', []),
            'skipped_roles': summary.get('skipped_roles', []),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        # 人类可读输出到 stdout
        print('全局文件验证报告（validate_global_files.py）')
        print('skill_dir: %s' % skill_dir)
        print('-' * 60)
        print('total_files: %d' % total)
        print('validated:   %d' % validated)
        print('passed:      %d' % passed)
        print('failed:      %d' % failed)
        print('-' * 60)

        # 列出失败文件
        failed_results = [r for r in summary.get('results', []) if not r.get('passed')]
        if failed_results:
            print('\n失败文件清单：')
            for r in failed_results:
                print('  [FAIL] %s' % r.get('file', '?'))
                if r.get('missing_fields'):
                    print('         missing: %s' % ', '.join(r['missing_fields']))
                if r.get('reason'):
                    print('         reason: %s' % r['reason'])
        else:
            print('\n所有已验证文件均通过。')

        # verbose 模式：列出每个文件的 found/missing 明细
        if args.verbose:
            print('\n--- verbose 明细 ---')
            for r in summary.get('results', []):
                tag = 'PASS' if r.get('passed') else 'FAIL'
                print('[%s] %s (contract=%s)' % (
                    tag, r.get('file', '?'), r.get('contract', '?')))
                if r.get('found_fields'):
                    print('       found: %s' % ', '.join(r['found_fields']))
                if r.get('missing_fields'):
                    print('       missing: %s' % ', '.join(r['missing_fields']))

        skipped = summary.get('skipped_roles', [])
        if skipped:
            print('\n--- 跳过的角色（无对应合同）---')
            for s in skipped:
                print('  %s (role=%s): %s' % (
                    s.get('path_pattern', '?'), s.get('role', '?'), s.get('reason', '?')))

        print('-' * 60)
        print('共 %d 文件 / 验证 %d / 通过 %d / 失败 %d'
              % (total, validated, passed, failed))

    # 验证失败的文件 → exit 1；否则 exit 0
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

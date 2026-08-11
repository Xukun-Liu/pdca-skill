#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
route_check.py — pdca-skill 路由层检查脚本

作用
----
验证 memory_main.md 与 SKILL.md 的写入时序正确性（对应铁律1 Memory First：
memory 必须跟进最新 skill 变更）+ 检测 references/ 目录下的死引用（孤儿文件）。

两条 check 互补：
  - check_stage_writeback：纵向时序——memory 是否比 SKILL 旧（"改了 SKILL 没写 memory"）
  - check_orphan_references：横向引用——references/xxx.md 是否被任何 .md 引用

借鉴来源: 业界路由检查实践
Traceability: SKILL.md §0 §1, references/common/pa/trigger_hooks.md, references/common/pa/working_memory_rules.md
设计来源: SKILL.md §0 Memory First, references/common/pa/summary_view.md §五

技术约束
--------
* 纯 Python 标准库（os / sys / json / argparse / logging / datetime）。
* 依赖 protocol 包（ROUTE_TARGETS / FILE_ROLES）。
* 零新增第三方依赖。

运行
----
  python scripts/route_check.py [--skill-dir PATH] [--json]
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime

# 让脚本能 import protocol 包（skill 根目录在 scripts/ 的上一级）
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

# 延迟 import + try/except，避免 protocol 故障导致整个脚本崩溃
try:
    from protocol import ROUTE_TARGETS, FILE_ROLES  # noqa: E402
    _HAVE_PROTOCOL = True
    _PROTOCOL_IMPORT_ERR = None
except Exception as exc:  # noqa: E722
    _HAVE_PROTOCOL = False
    _PROTOCOL_IMPORT_ERR = str(exc)

# user_data_path 用于解析外部 memory_main.md 路径（用户数据外置方案 v1.0.0+）
# 失败时退回包内路径，不阻断脚本
try:
    import user_data_path  # noqa: E402
    _HAVE_USER_DATA_PATH = True
    _USER_DATA_PATH_ERR = None
except Exception as exc:  # noqa: E722
    _HAVE_USER_DATA_PATH = False
    _USER_DATA_PATH_ERR = str(exc)

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ===========================================================================
# 辅助函数
# ===========================================================================
def _read_text(path):
    """读取文本文件，失败返回空串（对齐 validate_skill.read_text 行为）。"""
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ''


def _collect_md_files(skill_dir):
    """递归收集 skill_dir 下所有 .md 文件绝对路径（排除 .git / 输出目录）。

    用于 check_orphan_references 在所有 markdown 文件中搜索引用字符串。
    """
    md_files = []
    ignore_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith('.md'):
                md_files.append(os.path.join(root, f))
    return md_files


# ===========================================================================
# Check 1: 写入时序检查（铁律1 Memory First）
# ===========================================================================
def check_stage_writeback(skill_dir):
    """L1 检查 - 验证 memory_main.md 的 mtime >= SKILL.md 的 mtime。

    对应铁律1 Memory First：每次 SKILL.md 变更后，memory/memory_main.md 必须跟进
    （写项目记忆时 write_project 会自动 upsert 全局 memory_main）。
    如果 memory_main.md 比 SKILL.md 旧，说明 memory 没跟进最新 skill 变更，告警。

    Args:
        skill_dir: skill 包根目录绝对路径。

    Returns:
        dict: {'passed': bool, 'detail': str, 'issues': [...]}
        issues 中每条形如：
            {'file': 'memory/memory_main.md', 'skill_mtime': '...', 'memory_mtime': '...',
             'gap_seconds': N, 'reason': 'memory 比 SKILL 旧 X 秒'}
    """
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    memory_md = os.path.join(skill_dir, 'memory', 'memory_main.md')

    issues = []

    if not os.path.isfile(skill_md):
        issues.append({
            'file': 'SKILL.md',
            'reason': 'SKILL.md 不存在，无法做时序检查',
        })
        return {
            'passed': False,
            'detail': 'SKILL.md 不存在',
            'issues': issues,
        }

    if not os.path.isfile(memory_md):
        issues.append({
            'file': 'memory/memory_main.md',
            'reason': 'memory/memory_main.md 不存在（首次使用未写记忆？）',
        })
        return {
            'passed': False,
            'detail': 'memory/memory_main.md 不存在',
            'issues': issues,
        }

    try:
        skill_mtime = os.path.getmtime(skill_md)
        memory_mtime = os.path.getmtime(memory_md)
    except OSError as exc:
        issues.append({
            'reason': '读取 mtime 失败: %s' % exc,
        })
        return {
            'passed': False,
            'detail': '读取 mtime 失败',
            'issues': issues,
        }

    skill_dt = datetime.fromtimestamp(skill_mtime).strftime('%Y-%m-%d %H:%M:%S')
    memory_dt = datetime.fromtimestamp(memory_mtime).strftime('%Y-%m-%d %H:%M:%S')
    gap = skill_mtime - memory_mtime  # 正数 = memory 比 skill 旧

    if memory_mtime < skill_mtime:
        issues.append({
            'file': 'memory/memory_main.md',
            'skill_mtime': skill_dt,
            'memory_mtime': memory_dt,
            'gap_seconds': round(gap, 1),
            'reason': 'memory_main.md 比 SKILL.md 旧 %.1f 秒（违反 Memory First：SKILL 变更未跟进记忆）' % gap,
        })
        return {
            'passed': False,
            'detail': 'memory_main.md 比 SKILL.md 旧（Memory First 违规）',
            'issues': issues,
        }

    return {
        'passed': True,
        'detail': 'memory_main.md 已跟进 SKILL.md 变更（skill=%s / memory=%s）' % (skill_dt, memory_dt),
        'issues': issues,
    }


# ===========================================================================
# Check 2: references/ 孤儿引用检查
# ===========================================================================
def check_orphan_references(skill_dir):
    """检测 references/ 目录下的 .md 文件是否被 SKILL.md 或其他 .md 引用。

    遍历 skill_dir/references/*.md，对每个文件名构造 "references/xxx.md"
    形式的引用字符串（POSIX + Windows 两种分隔符都试），在所有 .md 文件中搜索。
    未被任何 .md 引用的算孤儿。

    Args:
        skill_dir: skill 包根目录绝对路径。

    Returns:
        dict: {'passed': bool, 'detail': str, 'issues': [...]}
        issues 中每条形如：{'file': 'references/xxx.md', 'reason': '未被任何 .md 文件引用'}
    """
    references_dir = os.path.join(skill_dir, 'references')
    issues = []

    if not os.path.isdir(references_dir):
        return {
            'passed': False,
            'detail': 'references/ 目录不存在',
            'issues': [{'reason': 'references/ 目录不存在'}],
        }

    # 列出 references/ 下所有 .md（递归遍历子目录，收集 POSIX 相对路径）
    ref_files = []
    for root, dirs, files in os.walk(references_dir):
        for f in sorted(files):
            if f.endswith('.md'):
                rel = os.path.relpath(os.path.join(root, f), references_dir)
                ref_files.append(rel.replace(os.sep, '/'))
    ref_files.sort()

    if not ref_files:
        return {
            'passed': True,
            'detail': 'references/ 下无 .md 文件，跳过孤儿检查',
            'issues': [],
        }

    # 收集所有 .md 文件用于搜索引用字符串
    all_md_files = _collect_md_files(skill_dir)

    # 构建「文件名 → 是否被引用」的查表
    # 引用字符串候选：
    #   - POSIX: references/xxx.md
    #   - Windows: references\xxx.md
    #   - 仅文件名: xxx.md （可能在 markdown 链接 [text](xxx.md) 中）
    # 这里只算"带 references/ 前缀"的引用，避免误报（如 xxx.md 太通用）
    orphan_list = []
    for ref_name in ref_files:
        # ref_name 为 POSIX 相对路径（可能含子目录，如 pa/xxx.md）
        posix_pattern = 'references/%s' % ref_name
        # Windows 风格引用：把 POSIX 分隔符 / 转成 \ 以匹配子目录路径
        win_pattern = ('references\\%s' % ref_name).replace('/', '\\')
        referenced = False
        for md_path in all_md_files:
            # 不算"自己引用自己"
            if os.path.basename(md_path) == ref_name:
                # 但仍要看其他同名文件（理论上不会出现），保险起见仍扫
                pass
            content = _read_text(md_path)
            if not content:
                continue
            if posix_pattern in content or win_pattern in content:
                referenced = True
                break
        if not referenced:
            orphan_list.append({
                'file': posix_pattern,
                'reason': '未被任何 .md 文件引用（孤儿）',
            })

    if orphan_list:
        return {
            'passed': False,
            'detail': '发现 %d 个 references/ 孤儿文件（未被任何 .md 引用）' % len(orphan_list),
            'issues': orphan_list,
        }

    return {
        'passed': True,
        'detail': 'references/ 下 %d 个 .md 文件全部被引用（无孤儿）' % len(ref_files),
        'issues': [],
    }


# ===========================================================================
# run_all_checks
# ===========================================================================
def run_all_checks(skill_dir):
    """跑所有 check，返回结果列表。

    Args:
        skill_dir: skill 包根目录绝对路径。

    Returns:
        list[dict]: 每条形如 {'name': str, 'passed': bool, 'detail': str, 'issues': [...]}
    """
    skill_dir = os.path.abspath(skill_dir)
    results = []

    # Check 1: 写入时序
    try:
        r1 = check_stage_writeback(skill_dir)
        r1['name'] = 'check_stage_writeback'
        results.append(r1)
    except Exception as exc:  # noqa: E722 防御性兜底
        logger.error("check_stage_writeback 异常: %s", exc)
        results.append({
            'name': 'check_stage_writeback',
            'passed': False,
            'detail': '异常: %s' % exc,
            'issues': [{'reason': str(exc)}],
        })

    # Check 2: 孤儿引用
    try:
        r2 = check_orphan_references(skill_dir)
        r2['name'] = 'check_orphan_references'
        results.append(r2)
    except Exception as exc:  # noqa: E722
        logger.error("check_orphan_references 异常: %s", exc)
        results.append({
            'name': 'check_orphan_references',
            'passed': False,
            'detail': '异常: %s' % exc,
            'issues': [{'reason': str(exc)}],
        })

    return results


# ===========================================================================
# CLI / main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='pdca-skill 路由层检查脚本（stdlib-only）')
    parser.add_argument('path', nargs='?', default=None,
                        help='skill 包根目录（位置参数，默认：当前目录；与 --skill-dir 互斥，同时给以 --skill-dir 为准）')
    parser.add_argument('--skill-dir', default=None,
                        help='skill 包根目录（与位置参数 path 互斥，同时给以 --skill-dir 为准）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果到 stdout（日志仍走 stderr）')
    args = parser.parse_args()

    # CLI 一致性：支持位置参数（与 generate_host_rules.py 对齐）
    # 优先级：--skill-dir > 位置参数 path > 默认 _SKILL_ROOT
    if args.skill_dir:
        skill_dir = os.path.abspath(args.skill_dir)
    elif args.path:
        skill_dir = os.path.abspath(args.path)
    else:
        skill_dir = _SKILL_ROOT

    if not os.path.isdir(skill_dir):
        logger.error("skill 目录不存在: %s", skill_dir)
        return 2

    # 告警 protocol 包导入失败（仅告警不阻断，B5 隔离）
    if not _HAVE_PROTOCOL:
        logger.warning("protocol 包导入失败（仅告警，不阻断）: %s", _PROTOCOL_IMPORT_ERR)
    else:
        # 验证 protocol 关键常量可用（轻量自检，不阻断）
        if not ROUTE_TARGETS or not FILE_ROLES:
            logger.warning("protocol.ROUTE_TARGETS 或 FILE_ROLES 为空")
        else:
            logger.info("protocol 包就绪：ROUTE_TARGETS=%d 项 / FILE_ROLES=%d 项",
                        len(ROUTE_TARGETS), len(FILE_ROLES))

    logger.info("=== 路由层检查（route_check）开始，skill_dir=%s ===", skill_dir)
    results = run_all_checks(skill_dir)

    # 统计
    total = len(results)
    passed = sum(1 for r in results if r.get('passed'))
    failed = total - passed
    logger.info("=== 路由层检查完成：共 %d 条 / 通过 %d / 失败 %d ===", total, passed, failed)

    if args.json:
        # JSON 到 stdout，日志仍在 stderr
        payload = {
            'skill_dir': skill_dir,
            'total': total,
            'passed': passed,
            'failed': failed,
            'results': results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        # 人类可读输出到 stdout
        print('路由层检查报告（route_check.py）')
        print('skill_dir: %s' % skill_dir)
        print('-' * 60)
        for r in results:
            tag = '✓ PASS' if r.get('passed') else '✗ FAIL'
            print('[%s] %s' % (tag, r.get('name', '?')))
            print('  detail: %s' % r.get('detail', ''))
            for issue in r.get('issues', []):
                print('  issue: %s' % issue)
            print('-' * 60)
        print('共 %d 条 / 通过 %d / 失败 %d' % (total, passed, failed))

    # 全部通过 exit 0；任一失败 exit 1
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

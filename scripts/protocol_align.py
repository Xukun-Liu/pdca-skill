#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
protocol_align.py — riji-skill 协议对齐检查脚本

作用
----
验证 protocol/ 包与 SKILL.md/references 的反向链完整性。

核心思想（来自业界协议对齐实践）：
  protocol/ 里的常量不是凭空定义的，必须能"反向追溯"到 SKILL.md 或 references/。
  如果某个 protocol/*.py 没有回指任何上游文档，说明它是"协议无根"——
  修改它不会触发任何文档同步，存在漂移风险。

两个工具函数 + 一个核心 check：
  - detect_git_changed_files：subprocess 跑 git status --porcelain，返回变更文件列表
  - extract_traceability_sources：正则提取 .py docstring 中「设计来源」「Traceability」引用行
  - check_alignment：遍历 protocol/*.py 验证反向链 + 调 get_impacted_files 看影响范围

借鉴来源: 业界协议对齐实践
Traceability: SKILL.md §0 §1, references/common/pa/trigger_hooks.md, protocol/change_impact_map.py
设计来源: SKILL.md §0 Memory First, protocol/change_impact_map.py 的 get_impacted_files

技术约束
--------
* 纯 Python 标准库（os / sys / re / json / argparse / logging / subprocess / datetime）。
* 依赖 protocol 包的 get_impacted_files。
* 零新增第三方依赖。
* Windows 兼容：subprocess 捕获 FileNotFoundError（git 未装）+ TimeoutExpired。

运行
----
  python scripts/protocol_align.py [--skill-dir PATH] [--json]
"""

import os
import sys
import re
import json
import argparse
import logging
import subprocess
from datetime import datetime

# 让脚本能 import protocol 包（skill 根目录在 scripts/ 的上一级）
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

# 延迟 import + try/except，避免 protocol 故障导致整个脚本崩溃
try:
    from protocol import get_impacted_files  # noqa: E402
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


# ===========================================================================
# 工具函数 1: detect_git_changed_files（L7 检查）
# ===========================================================================
def detect_git_changed_files(cwd, timeout=10):
    """用 subprocess 跑 `git status --porcelain`，解析输出返回变更文件列表。

    L7 检查（铁律7 逐项核对的延伸）：当前工作区有哪些文件被改了，
    用于配合 get_impacted_files 反推受影响范围。

    Args:
        cwd: 跑 git 命令的工作目录。
        timeout: subprocess 超时秒数，默认 10。

    Returns:
        list[str]: 变更文件路径列表（相对 cwd）。非 git 仓库或超时返回空列表。
    """
    # Windows 上 git 可能是 git.exe，subprocess 会自动找
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        # git 可执行文件不存在（未装 git）
        logger.warning("git 命令不存在（未安装 git？），返回空列表")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("git status 超时（%ss），返回空列表", timeout)
        return []
    except OSError as exc:
        logger.warning("git status 执行失败：%s，返回空列表", exc)
        return []

    if result.returncode != 0:
        # 非 git 仓库（rc=128）或其它错误
        stderr = (result.stderr or '').strip()
        logger.warning("git status 返回码 %s（%s），返回空列表", result.returncode, stderr[:200])
        return []

    changed = []
    # git status --porcelain 每行格式：XY PATH（X=staged 状态，Y=worktree 状态）
    # 路径可能含空格、中文、引号；这里按"取前2字符状态码 + 剩余为路径"解析
    # 重命名（R）格式："R  OLD -> NEW"，需要取 NEW
    for line in result.stdout.splitlines():
        if not line:
            continue
        # 行格式："XY PATH" 或 "XY ORIG -> PATH"
        # X/Y 各一字符，第3字符是空格
        if len(line) < 4:
            continue
        path_part = line[3:]
        # 处理重命名："OLD -> NEW"
        if ' -> ' in path_part:
            path_part = path_part.split(' -> ', 1)[1]
        # 去掉可能的引号包围（git 对含特殊字符的路径会加引号）
        path_part = path_part.strip().strip('"')
        if path_part:
            changed.append(path_part)
    return changed


# ===========================================================================
# 工具函数 2: extract_traceability_sources
# ===========================================================================
# 匹配「设计来源」或「Traceability」开头的行，取冒号后的内容
_TRACEABILITY_LINE_RE = re.compile(r'(?:设计来源|Traceability)\s*:\s*(.+)')


def extract_traceability_sources(python_file_path):
    """正则匹配 Python 文件 docstring 中的「设计来源」「Traceability」行，提取引用的文件路径。

    示例输入（Python 文件 docstring 片段）：
        '''
        设计来源: SKILL.md §0, references/common/pa/trigger_hooks.md
        Traceability: 业界 AI PM 协议实践
        '''
    返回：['SKILL.md', 'references/common/pa/trigger_hooks.md',
           '业界 AI PM 协议实践']

    解析规则：
      1. 按「设计来源」「Traceability」行切分
      2. 每行冒号后的内容按英文逗号分隔成多段
      3. 每段 strip 空白
      4. 截掉章节标记（如 "SKILL.md §0" → "SKILL.md"），保留纯路径/描述

    Args:
        python_file_path: .py 文件绝对路径。

    Returns:
        list[str]: 引用源列表（去重，保持顺序）。读取失败返回空列表。
    """
    try:
        with open(python_file_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except (OSError, UnicodeDecodeError):
        return []

    matches = _TRACEABILITY_LINE_RE.findall(content)
    sources = []
    seen = set()
    for m in matches:
        for part in m.split(','):
            s = part.strip()
            if not s:
                continue
            # 截掉章节标记（§xxx / #xxx），保留纯路径
            # 例："SKILL.md §0" → "SKILL.md"
            m2 = re.match(r'^(.+?)\s*[§#]\s*\S*', s)
            if m2:
                s = m2.group(1).strip()
            if s and s not in seen:
                seen.add(s)
                sources.append(s)
    return sources


# ===========================================================================
# 核心 check: check_alignment
# ===========================================================================
def check_alignment(skill_dir):
    """用 get_impacted_files 找受影响文件 + 检查 protocol/*.py 是否回指 SKILL.md/references。

    具体逻辑：
      1. 遍历 protocol/*.py（跳过 __init__.py），提取每个文件的 traceability sources
      2. 验证每个 .py 至少回指 1 个 SKILL.md 或 references/*.md（否则算"协议无根"）
      3. 调 detect_git_changed_files + get_impacted_files，把当前 git 变更的影响范围
         作为 detail 附加（不强制要求处理，仅信息性）

    Args:
        skill_dir: skill 包根目录绝对路径。

    Returns:
        dict: {'passed': bool, 'detail': str, 'issues': [...]}
        issues 中每条形如：
            {'file': 'protocol/xxx.py', 'sources': [...], 'reason': '协议无根：未回指 SKILL.md 或 references/*.md'}
    """
    protocol_dir = os.path.join(skill_dir, 'protocol')

    if not os.path.isdir(protocol_dir):
        return {
            'passed': False,
            'detail': 'protocol/ 目录不存在',
            'issues': [{'reason': 'protocol/ 目录不存在'}],
        }

    # 列出 protocol/*.py，跳过 __init__.py（包导出声明，不算独立模块）
    py_files = []
    for f in sorted(os.listdir(protocol_dir)):
        if f.endswith('.py') and f != '__init__.py':
            py_files.append(f)

    if not py_files:
        return {
            'passed': True,
            'detail': 'protocol/ 下无 .py 业务模块（仅 __init__.py），跳过对齐检查',
            'issues': [],
        }

    # 1. 反向链检查：每个 protocol/*.py 至少回指 1 个 SKILL.md 或 references/*.md
    orphan_files = []
    for py_name in py_files:
        py_path = os.path.join(protocol_dir, py_name)
        sources = extract_traceability_sources(py_path)
        has_root = False
        for src in sources:
            # 严格匹配：src 完全等于 "SKILL.md"
            if src == 'SKILL.md':
                has_root = True
                break
            # 严格匹配：src 以 "references/" 或 "references\\" 开头
            if src.startswith('references/') or src.startswith('references\\'):
                has_root = True
                break
            # 模糊匹配：src 含 "references/xxx.md" 形式
            if ('references/' in src or 'references\\' in src) and src.endswith('.md'):
                has_root = True
                break
        if not has_root:
            orphan_files.append({
                'file': 'protocol/%s' % py_name,
                'sources': sources,
                'reason': '协议无根：未回指 SKILL.md 或 references/*.md',
            })

    # 2. 用 get_impacted_files 检测当前 git 变更影响范围（信息性，不强制）
    detail_extra = ''
    if _HAVE_PROTOCOL:
        try:
            changed = detect_git_changed_files(skill_dir)
            if changed:
                impacted = get_impacted_files(changed)
                detail_extra = '（git 变更 %d 个 → 受影响 %d 个：%s）' % (
                    len(changed), len(impacted), ', '.join(impacted[:5]) if impacted else '无'
                )
            else:
                detail_extra = '（无 git 变更或非 git 仓库）'
        except Exception as exc:  # noqa: E722 防御性兜底
            detail_extra = '（git 变更检测异常：%s）' % exc
    else:
        detail_extra = '（protocol 包不可用，未做 git 影响分析）'

    if orphan_files:
        return {
            'passed': False,
            'detail': '发现 %d 个 protocol/*.py 协议无根 %s' % (len(orphan_files), detail_extra),
            'issues': orphan_files,
        }

    return {
        'passed': True,
        'detail': 'protocol/ 下 %d 个 .py 全部回指 SKILL.md 或 references/*.md %s' % (len(py_files), detail_extra),
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

    try:
        r = check_alignment(skill_dir)
        r['name'] = 'check_alignment'
        results.append(r)
    except Exception as exc:  # noqa: E722
        logger.error("check_alignment 异常: %s", exc)
        results.append({
            'name': 'check_alignment',
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
        description='riji-skill 协议对齐检查脚本（stdlib-only）')
    parser.add_argument('--skill-dir', default=None,
                        help='skill 包根目录（默认：scripts/ 的上级目录）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果到 stdout（日志仍走 stderr）')
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
        logger.info("protocol 包就绪：get_impacted_files 可用")

    logger.info("=== 协议对齐检查（protocol_align）开始，skill_dir=%s ===", skill_dir)
    results = run_all_checks(skill_dir)

    # 统计
    total = len(results)
    passed = sum(1 for r in results if r.get('passed'))
    failed = total - passed
    logger.info("=== 协议对齐检查完成：共 %d 条 / 通过 %d / 失败 %d ===", total, passed, failed)

    if args.json:
        payload = {
            'skill_dir': skill_dir,
            'total': total,
            'passed': passed,
            'failed': failed,
            'results': results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('协议对齐检查报告（protocol_align.py）')
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

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

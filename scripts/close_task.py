#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
close_task.py — 任务闭合编排（v1.1.0 · B1 / O0）

把 /act 阶段散落在 SKILL.md 散文里的机械步骤收敛成一条命令：
  1. 解析主 docs（marker → MEMORY_RJ 约定 → 报错，不猜）
  2. 核对 8 要素骨架
  3. 收集本任务产物（spec / task / handoff / memory）
  4. 核对 SUMMARY_RJ.md 是否已挂上本任务链接
  5. 非 dry-run 时交给 handoff_tidy.py 做归档 + SUMMARY 刷新（不重复实现）

用法：
  python scripts/close_task.py --task skill_upgrade_20261028 --dry-run
  python scripts/close_task.py --task skill_upgrade_20261028

退出码：
  0 可闭合（dry-run）／已闭合（实跑）
  1 有阻断项（缺产物 / SUMMARY 断链 / 骨架缺项）
  2 环境错误（task 名非法 / 主 docs 解析失败 / handoff_tidy 不可用）

技术约束：仅 Python 标准库；复用 generate_docs（marker 解析）+ tidy_common（主 docs 解析）
          + handoff_tidy（归档与 SUMMARY 刷新）。
"""

import argparse
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402

TASK_NAME_RE = re.compile(r'^[a-z0-9_]+$')

SKELETON_DIRS = ('spec_rj', 'task_rj', 'handoff_rj', 'archive_rj', 'memory_rj')

ARTIFACT_KINDS = (
    ('spec', 'spec_rj', '%s_spec_*.md'),
    ('task', 'task_rj', '%s_task_*.md'),
    ('handoff', 'handoff_rj', '%s_handoff_*.md'),
)


def resolve_docs(primary_docs_arg=None):
    """解析主 docs 目录；解析不到返回 None（不静默退回 ./docs_rj）。"""
    try:
        docs = tidy_common.resolve_primary_docs(primary_docs_arg)
    except Exception as exc:  # noqa: BLE001 - 解析链任何异常都按环境错误处理
        print('错误：解析主 docs 失败: %s' % exc, file=sys.stderr)
        return None
    if not docs or not os.path.isdir(docs):
        return None
    return os.path.abspath(docs)


def check_skeleton(docs):
    """8 要素骨架检查，返回缺失项列表（不含 marker，marker 已在解析阶段校验）。"""
    missing = []
    for sub in SKELETON_DIRS:
        if not os.path.isdir(os.path.join(docs, sub)):
            missing.append('docs_rj/%s/' % sub)
    if not os.path.isfile(os.path.join(docs, 'SUMMARY_RJ.md')):
        missing.append('docs_rj/SUMMARY_RJ.md')
    return missing


def collect_artifacts(docs, task):
    """收集本任务产物；memory 按 v1.0.4 标签文件夹结构递归查找。"""
    found = {}
    for kind, sub, pattern in ARTIFACT_KINDS:
        hits = sorted(glob.glob(os.path.join(docs, sub, pattern % task)))
        found[kind] = [os.path.abspath(p) for p in hits]
    memory_pattern = os.path.join(docs, 'memory_rj', '**', '%s_memory_*.md' % task)
    found['memory'] = [os.path.abspath(p) for p in
                       sorted(glob.glob(memory_pattern, recursive=True))]
    return found


def check_summary_links(docs, task):
    """核对 SUMMARY_RJ.md 中是否存在指向本任务产物的相对链接。"""
    summary_path = os.path.join(docs, 'SUMMARY_RJ.md')
    if not os.path.isfile(summary_path):
        return None
    try:
        with open(summary_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        print('错误：读取 SUMMARY_RJ.md 失败: %s' % exc, file=sys.stderr)
        return None
    return content.count(task)


def run_handoff_tidy(docs, task):
    """实跑：委托 handoff_tidy.py 归档 + 刷新 SUMMARY/TASK_STATE。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'handoff_tidy.py')
    if not os.path.isfile(script):
        print('错误：handoff_tidy.py 不存在: %s' % script, file=sys.stderr)
        return 2
    cmd = [sys.executable, script, '--task', task, '--allow-any-dir']
    print('\n[执行] %s' % ' '.join(cmd))
    return subprocess.call(cmd, cwd=os.getcwd())


def print_artifact_block(artifacts):
    print('\n## 产物清单')
    for kind in ('spec', 'task', 'handoff', 'memory'):
        items = artifacts[kind]
        if not items:
            print('- %-8s 缺失' % kind)
            continue
        print('- %-8s %d 个' % (kind, len(items)))
        for path in items:
            print('    %s' % path)


def main():
    parser = argparse.ArgumentParser(
        description='任务闭合编排：核对产物 → 归档 → 刷新 SUMMARY（stdlib-only）')
    parser.add_argument('--task', required=True, help='任务名（只允许 [a-z0-9_]+）')
    parser.add_argument('--dry-run', action='store_true', help='只输出待归档清单，不落盘')
    parser.add_argument('--docs-dir', default=None, help='显式指定主 docs 目录（默认走 marker）')
    args = parser.parse_args()

    task = args.task
    if not TASK_NAME_RE.match(task):
        print('错误：任务名非法（只允许 [a-z0-9_]+）: %s' % task, file=sys.stderr)
        return 2

    docs = resolve_docs(args.docs_dir)
    if docs is None:
        print('错误：未解析到主 docs 目录。请先跑 generate_docs.py --declare-primary '
              '或传 --docs-dir。', file=sys.stderr)
        return 2

    mode = 'dry-run' if args.dry_run else '实跑'
    print('## close_task %s' % mode)
    print('- task    : %s' % task)
    print('- 主 docs : %s' % docs)
    print('- 工作目录: %s' % os.getcwd())

    blockers = []

    missing_skeleton = check_skeleton(docs)
    print('\n## 骨架检查（8 要素）')
    if missing_skeleton:
        for item in missing_skeleton:
            print('- 缺失 %s' % item)
        blockers.append('骨架缺 %d 项' % len(missing_skeleton))
    else:
        print('- 全部存在')

    artifacts = collect_artifacts(docs, task)
    print_artifact_block(artifacts)
    for kind in ('spec', 'task', 'memory'):
        if not artifacts[kind]:
            blockers.append('缺 %s 产物' % kind)

    link_hits = check_summary_links(docs, task)
    print('\n## SUMMARY 链接')
    if link_hits is None:
        print('- 无法读取 SUMMARY_RJ.md')
        blockers.append('SUMMARY 不可读')
    elif link_hits == 0:
        print('- 未挂上本任务链接')
        blockers.append('SUMMARY 缺本任务链接')
    else:
        print('- 命中 %d 处本任务链接' % link_hits)

    print('\n## 结论')
    if blockers:
        for item in blockers:
            print('- BLOCKER %s' % item)
        print('结果：不可闭合（%d 项阻断）' % len(blockers))
        return 1

    if args.dry_run:
        print('- 可闭合')
        print('\n[计划] python scripts/handoff_tidy.py --task %s --allow-any-dir' % task)
        return 0

    code = run_handoff_tidy(docs, task)
    if code != 0:
        print('结果：handoff_tidy 失败（退码 %d），未完成闭合' % code)
        return code if code in (1, 2) else 1
    print('结果：已闭合')
    return 0


if __name__ == '__main__':
    sys.exit(main())
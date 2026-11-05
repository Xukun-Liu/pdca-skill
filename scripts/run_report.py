#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_report.py — 单次运行报告（v1.1.0 · B4 / B4）

回答三个问题，一条命令出口径：
  1. 做了什么 —— 任务文档勾选项（已完成 / 总数）+ 最近一次 commit 主题
  2. 改了哪些文件 —— 最近一次 commit 的 name-status 列表 + 未提交改动
  3. 耗时 —— 任务文档/记忆的时间跨度 + 最近一次 commit 与上一 commit 的间隔

用法：
  python scripts/run_report.py --task skill_upgrade_20261028
  python scripts/run_report.py --task skill_upgrade_20261028 --last
  python scripts/run_report.py --task skill_upgrade_20261028 --root "<skill>" --json

退出码：
  0 正常出报告
  2 环境错误（主 docs 解析失败 / 找不到该任务任何文档与记忆）

技术约束：仅 Python 标准库；git 只读调用；主 docs 解析复用 tidy_common。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402

DOC_SUBDIRS = ('spec_rj', 'task_rj', 'check_rj', 'archive_rj', 'handoff_rj')
TASK_LINE_RE = re.compile(r'^\s*-\s*\[( |x|X)\]\s*(.+?)\s*$', re.MULTILINE)
TAG_LINE_RE = re.compile(r'\*\*标签\*\*[:：]\s*(.+)')


def resolve_docs(primary_docs_arg=None):
    try:
        docs = tidy_common.resolve_primary_docs(primary_docs_arg)
    except Exception as exc:  # noqa: BLE001 - 解析链异常统一按环境错误
        print('错误：解析主 docs 失败: %s' % exc, file=sys.stderr)
        return None
    if not docs or not os.path.isdir(docs):
        return None
    return os.path.abspath(docs)


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''


def collect_task_docs(docs, task):
    hits = []
    for sub in DOC_SUBDIRS:
        base = os.path.join(docs, sub)
        if not os.path.isdir(base):
            continue
        for cur, dirs, files in os.walk(base):
            dirs.sort()
            for name in sorted(files):
                if name.lower().endswith('.md') and task in name:
                    hits.append(os.path.join(cur, name))
    return sorted(hits)


def collect_memories(docs, task):
    hits = []
    base = os.path.join(docs, 'memory_rj')
    if not os.path.isdir(base):
        return hits
    for cur, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith('.md') and task in name and '_memory_' in name:
                hits.append(os.path.join(cur, name))
    return sorted(hits)


def scan_checkboxes(docs):
    done, pending, done_items = 0, 0, []
    for path in docs:
        for mark, text in TASK_LINE_RE.findall(read_text(path)):
            if mark.strip():
                done += 1
                done_items.append(text)
            else:
                pending += 1
    return done, pending, done_items


def scan_tags(memories):
    tags = []
    for path in memories:
        match = TAG_LINE_RE.search(read_text(path))
        if match:
            tags.append(match.group(1).strip())
    return tags


def git(root, *args):
    try:
        out = subprocess.run(['git'] + list(args), cwd=root, capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_last_commit(root):
    raw = git(root, 'log', '-1', '--pretty=format:%H|%ad|%s', '--date=iso')
    if not raw or '|' not in raw:
        return None
    sha, date, subject = raw.split('|', 2)
    files = git(root, 'show', '--name-status', '--format=', sha) or ''
    changed = [line for line in files.splitlines() if line.strip()]
    parent_date = git(root, 'log', '-1', '--pretty=format:%ad', '--date=iso', sha + '^')
    duration = None
    if parent_date:
        try:
            start = datetime.strptime(parent_date.strip()[:19], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(date.strip()[:19], '%Y-%m-%d %H:%M:%S')
            duration = int((end - start).total_seconds() // 60)
        except ValueError:
            duration = None
    dirty = git(root, 'status', '--porcelain') or ''
    return {
        'sha': sha[:7],
        'date': date,
        'subject': subject,
        'changed': changed,
        'duration_min': duration,
        'dirty': [line for line in dirty.splitlines() if line.strip()],
    }


def span(paths):
    times = []
    for path in paths:
        try:
            times.append(os.path.getmtime(path))
        except OSError:
            continue
    if not times:
        return None
    minutes = int((max(times) - min(times)) // 60)
    return {
        'first': datetime.fromtimestamp(min(times)).strftime('%Y-%m-%d %H:%M'),
        'last': datetime.fromtimestamp(max(times)).strftime('%Y-%m-%d %H:%M'),
        'minutes': minutes,
    }


def build_report(task, docs_root, root, with_last):
    docs = collect_task_docs(docs_root, task)
    memories = collect_memories(docs_root, task)
    done, pending, done_items = scan_checkboxes(docs)
    report = {
        'task': task,
        'docs_root': docs_root,
        'skill_root': root,
        'documents': [os.path.relpath(p, docs_root) for p in docs],
        'memories': [os.path.relpath(p, docs_root) for p in memories],
        'memory_tags': scan_tags(memories),
        'checkboxes': {'done': done, 'pending': pending, 'done_items': done_items},
        'span': span(docs + memories),
        'last_commit': None,
    }
    if with_last:
        report['last_commit'] = git_last_commit(root)
    return report


def render(report):
    print('# 运行报告 · %s' % report['task'])
    print('- docs: %s' % report['docs_root'])
    print('- skill: %s' % report['skill_root'])

    print('\n## 1. 做了什么')
    box = report['checkboxes']
    total = box['done'] + box['pending']
    print('- 任务勾选: %d/%d 完成' % (box['done'], total))
    for item in box['done_items'][:15]:
        print('  - [x] %s' % item[:90])
    if len(box['done_items']) > 15:
        print('  - … 其余 %d 条省略' % (len(box['done_items']) - 15))
    print('- 任务文档 %d 份，记忆 %d 条' % (len(report['documents']), len(report['memories'])))
    if report['memory_tags']:
        print('- 记忆标签: %s' % ' / '.join(report['memory_tags'][-5:]))

    print('\n## 2. 改了哪些文件')
    commit = report['last_commit']
    if commit:
        print('- 最近 commit: %s %s' % (commit['sha'], commit['subject']))
        for line in commit['changed'][:20]:
            print('  - %s' % line)
        if len(commit['changed']) > 20:
            print('  - … 其余 %d 条省略' % (len(commit['changed']) - 20))
        print('- 未提交改动: %d 项' % len(commit['dirty']))
    else:
        print('- 未取到 git 记录（非仓库或未加 --last）')

    print('\n## 3. 耗时')
    span_info = report['span']
    if span_info:
        print('- 任务跨度: %s → %s（%d 分钟）'
              % (span_info['first'], span_info['last'], span_info['minutes']))
    else:
        print('- 任务跨度: 无时间戳')
    if commit and commit['duration_min'] is not None:
        print('- 最近 commit 与上一 commit 间隔: %d 分钟' % commit['duration_min'])
    elif commit:
        print('- 最近 commit 与上一 commit 间隔: 无上一 commit')


def main(argv=None):
    parser = argparse.ArgumentParser(description='单次运行报告：做了什么 / 改了哪些文件 / 耗时')
    parser.add_argument('--task', required=True, help='任务名（文件名中的任务标识）')
    parser.add_argument('--last', action='store_true', help='附最近一次 git commit 明细')
    parser.add_argument('--root', default='.', help='技能目录（git 仓库根）')
    parser.add_argument('--docs', default=None, help='显式指定 docs 目录')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出（机器可读）')
    args = parser.parse_args(argv)

    docs_root = resolve_docs(args.docs)
    if not docs_root:
        print('错误：主 docs 解析失败（检查 .primary_docs_rj 或 --docs）', file=sys.stderr)
        return 2

    root = os.path.abspath(args.root)
    report = build_report(args.task, docs_root, root, args.last)
    if not report['documents'] and not report['memories']:
        print('错误：docs 下找不到任务「%s」的文档或记忆' % args.task, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
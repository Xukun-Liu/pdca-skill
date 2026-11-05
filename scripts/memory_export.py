#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_export.py — 单任务记忆自包含导出（v1.1.0 · B3 / 3.1）

把某个 task 的全部项目记忆打包成一个自包含目录，换机 / 换工具 / 换仓库都能原样带走：
  <out>/
    manifest.json     # 机器可读：源 docs 根、源记忆根、每条 class/月/路径/sha256/标题/标签
    manifest.md       # 人可读清单
    memory/<class>/<YYYYMM>/<原文件名>.md
    
用法：
  python scripts/memory_export.py --task skill_upgrade_20261028 --out D:\\tmp\\exp
  python scripts/memory_export.py --task xxx --out D:\\tmp\\exp --docs-dir C:\\docs_rj

退出码：
  0 导出成功
  1 未找到该任务的记忆文件
  2 环境错误（主 docs 解析失败 / 输出目录不可写）

技术约束：仅 Python 标准库；主 docs 解析与哈希复用 inventory.py。
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import memory_tags  # noqa: E402

BUNDLE_VERSION = '1.1.0'
MONTH_RE = re.compile(r'^\d{6}$')
TASK_RE = re.compile(r'^[a-z0-9_]+$')
TAG_LINE_RE = re.compile(r'^\*\*标签\*\*[：:]\s*(.*)$')
LESSON_LINE_RE = re.compile(r'^\*\*是否经验\*\*[：:]\s*(.*)$')


def resolve_memory_root(docs_arg=None):
    """解析 {主docs}/memory_rj；失败返回 None。"""
    docs = inventory.resolve_docs(docs_arg)
    if not docs:
        return None, None
    return docs, os.path.join(docs, 'memory_rj')


def collect_task_memories(memory_root, task):
    """递归收集 {task}_memory_*.md。

    Returns:
        [(abs_path, class_or_empty, month_or_empty)]，按 class/month/文件名排序
    """
    hits = []
    prefix = '%s_memory_' % task
    for root, dirs, files in os.walk(memory_root):
        dirs.sort()
        for name in sorted(files):
            if not (name.startswith(prefix) and name.endswith('.md')):
                continue
            rel = os.path.relpath(root, memory_root)
            parts = [] if rel == '.' else rel.split(os.sep)
            cls = parts[0] if parts and parts[0] in memory_tags.MEMORY_TAGS else ''
            month = parts[1] if len(parts) > 1 and MONTH_RE.match(parts[1]) else ''
            hits.append((os.path.join(root, name), cls, month))
    hits.sort(key=lambda item: (item[1], item[2], os.path.basename(item[0])))
    return hits


def parse_meta(path):
    """从记忆文件里抽出标题 / 标签 / 是否经验（缺失时给空值，不抛异常）。"""
    title, tags, lesson = '', [], False
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            for raw in handle:
                line = raw.rstrip('\n')
                if not title and line.startswith('# '):
                    title = line[2:].strip()
                found = TAG_LINE_RE.match(line)
                if found:
                    tags = [t.strip() for t in re.split(r'[,，]', found.group(1)) if t.strip()]
                found = LESSON_LINE_RE.match(line)
                if found:
                    lesson = found.group(1).strip().lower() in ('true', 'yes', '是')
    except OSError:
        pass
    return title, tags, lesson


def relative_source(memory_root, path):
    """相对 memory_rj 的路径（统一 / 分隔，供 manifest 与 import 复原目录结构）。"""
    return os.path.relpath(path, memory_root).replace(os.sep, '/')


def render_manifest_md(manifest):
    """人可读清单（表格 + 统计）。"""
    lines = [
        '# 记忆导出清单',
        '',
        '- 任务：`%s`' % manifest['task'],
        '- 导出时间：%s' % manifest['exported_at'],
        '- 源记忆根：`%s`' % manifest['source_memory_root'],
        '- 条目数：%d' % manifest['counts']['total'],
        '',
        '| # | 文件 | 主分类 | 月份 | 大小(B) | sha256 | 标题 |',
        '|---|---|---|---|---|---|---|',
    ]
    for idx, entry in enumerate(manifest['entries'], 1):
        lines.append('| %d | %s | %s | %s | %d | %s | %s |' % (
            idx, entry['file'], entry['class'] or '（平铺）', entry['month'] or '-',
            entry['size'], entry['sha256'], entry['title'] or '-'))
    lines += ['', '## 按主分类统计', '']
    for cls, count in sorted(manifest['counts']['by_class'].items()):
        lines.append('- %s：%d' % (cls or '（平铺）', count))
    lines += ['', '> 复原：`python scripts/memory_import.py --src <本目录>`（加 `--dry-run` 先看计划）', '']
    return '\n'.join(lines)


def build_manifest(task, docs_root, memory_root, items):
    entries = []
    for path, cls, month in items:
        title, tags, lesson = parse_meta(path)
        entries.append({
            'file': os.path.basename(path),
            'class': cls,
            'month': month,
            'source_relpath': relative_source(memory_root, path),
            'relpath': 'memory/%s' % relative_source(memory_root, path),
            'sha256': inventory.short_hash(path),
            'size': os.path.getsize(path),
            'title': title,
            'tags': tags,
            'is_lesson': lesson,
        })
    by_class = {}
    for entry in entries:
        by_class[entry['class']] = by_class.get(entry['class'], 0) + 1
    return {
        'bundle_version': BUNDLE_VERSION,
        'exported_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'task': task,
        'source_docs_root': docs_root,
        'source_memory_root': memory_root,
        'entries': entries,
        'counts': {'total': len(entries), 'by_class': by_class},
    }


def do_export(task, out_dir, docs_arg=None):
    docs_root, memory_root = resolve_memory_root(docs_arg)
    if not docs_root:
        print('错误：未解析到主 docs（可加 --docs-dir 显式指定）', file=sys.stderr)
        return 2
    if not os.path.isdir(memory_root):
        print('错误：记忆目录不存在: %s' % memory_root, file=sys.stderr)
        return 2

    items = collect_task_memories(memory_root, task)
    if not items:
        print('未找到任务 `%s` 的记忆文件（%s）' % (task, memory_root), file=sys.stderr)
        return 1

    manifest = build_manifest(task, docs_root, memory_root, items)
    try:
        os.makedirs(out_dir, exist_ok=True)
        for entry, (path, _cls, _month) in zip(manifest['entries'], items):
            target = os.path.join(out_dir, entry['relpath'].replace('/', os.sep))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(path, target)
        with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        with open(os.path.join(out_dir, 'manifest.md'), 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(render_manifest_md(manifest))
    except OSError as exc:
        print('错误：写入导出目录失败: %s' % exc, file=sys.stderr)
        return 2

    print('## 导出完成（memory_export）')
    print('- 任务：%s' % task)
    print('- 源记忆根：%s' % memory_root)
    print('- 输出目录：%s' % os.path.abspath(out_dir))
    print('- 条目：%d' % manifest['counts']['total'])
    for entry in manifest['entries']:
        print('  - %s/%s/%s → memory/%s' % (
            entry['class'] or '（平铺）', entry['month'] or '-', entry['file'],
            entry['source_relpath']))
    print('- manifest：manifest.json（机器）+ manifest.md（人读）')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='单任务记忆自包含导出（v1.1.0 · B3）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--task', required=True, help='任务名（只允许 [a-z0-9_]+）')
    parser.add_argument('--out', required=True, help='导出目录（不存在会自动创建）')
    parser.add_argument('--docs-dir', default=None, help='主 docs 目录（缺省按 marker 解析链）')
    args = parser.parse_args(argv)

    if not TASK_RE.match(args.task or ''):
        print('错误：非法任务名 `%s`（只允许 [a-z0-9_]+）' % args.task, file=sys.stderr)
        return 2
    return do_export(args.task, args.out, args.docs_dir)


if __name__ == '__main__':
    sys.exit(main())
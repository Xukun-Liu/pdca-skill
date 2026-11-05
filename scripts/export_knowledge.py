#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_knowledge.py — 记忆 → 结构化知识（v1.1.0 · B3 / 3.4）

把 memory_rj 下所有任务的记忆汇总成两套视图，供人按标签找经验、按时间看进展：
  --format md   → <out>/knowledge_by_tag.md + <out>/knowledge_by_time.md + <out>/README.md
  --format json → <out>/knowledge.json（机器可读，含 entries / by_tag / by_month）

用法：
  python scripts/export_knowledge.py --format md --out D:\\tmp\\kn
  python scripts/export_knowledge.py --format json --out D:\\tmp\\kn --docs-dir C:\\docs_rj

退出码：
  0 导出成功
  1 没有任何记忆条目
  2 环境错误（主 docs 解析失败 / 输出目录不可写 / 参数非法）

技术约束：仅 Python 标准库；主 docs 解析、路径哈希、记忆元信息解析复用既有模块。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import memory_export  # noqa: E402
import memory_tags  # noqa: E402

KNOWLEDGE_VERSION = '1.1.0'
# 任务名宽松匹配：v1.0.4 前遗留的记忆含大写/中文/连字符（违反 §0.6），
# 这里按 "_memory_" 切分而非套用 [a-z0-9_]+，避免历史记忆在知识视图中被静默丢弃。
MEMORY_NAME_RE = re.compile(r'^(?P<task>.+)_memory_(?P<date>\d{8})_(?P<clock>\d{4})\.md$')
UNTAGGED = '（无标签）'


def collect_entries(docs_root, memory_root):
    """递归收集所有 {task}_memory_YYYYMMDD_HHMM.md，返回按时间倒序的条目列表。"""
    entries = []
    for root, dirs, files in os.walk(memory_root):
        dirs.sort()
        for name in sorted(files):
            found = MEMORY_NAME_RE.match(name)
            if not found:
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(root, memory_root)
            parts = [] if rel == '.' else rel.split(os.sep)
            cls = parts[0] if parts and parts[0] in memory_tags.MEMORY_TAGS else ''
            month = parts[1] if len(parts) > 1 and memory_export.MONTH_RE.match(parts[1]) else ''
            title, tags, lesson = memory_export.parse_meta(path)
            date = found.group('date')
            clock = found.group('clock')
            entries.append({
                'task': found.group('task'),
                'date': '%s-%s-%s' % (date[:4], date[4:6], date[6:]),
                'time': '%s-%s-%s %s:%s' % (date[:4], date[4:6], date[6:], clock[:2], clock[2:]),
                'clock': clock,
                'month': month or '%s-%s' % (date[:4], date[4:6]),
                'class': cls,
                'file': name,
                'relpath': os.path.relpath(path, docs_root).replace(os.sep, '/'),
                'title': title or os.path.splitext(name)[0],
                'tags': tags,
                'is_lesson': lesson,
            })
    entries.sort(key=lambda item: (item['date'], item['clock'], item['file']), reverse=True)
    return entries


def group_by_tag(entries):
    """按标签分组；无标签条目归入 UNTAGGED。标签内按时间倒序（entries 本身已倒序）。"""
    groups = {}
    for entry in entries:
        tags = entry['tags'] or [UNTAGGED]
        for tag in tags:
            groups.setdefault(tag, []).append(entry)
    return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])))


def group_by_month(entries):
    """按月份分组（YYYY-MM），月份倒序，组内保持时间倒序。"""
    groups = {}
    for entry in entries:
        groups.setdefault(entry['month'], []).append(entry)
    return dict(sorted(groups.items(), reverse=True))


def render_by_tag(entries, docs_root):
    groups = group_by_tag(entries)
    lines = [
        '# 记忆知识库 · 按标签',
        '',
        '- 生成时间：%s' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        '- 主 docs：`%s`' % docs_root,
        '- 条目数：%d（标签组 %d）' % (len(entries), len(groups)),
        '- 时间视图见 [knowledge_by_time.md](knowledge_by_time.md)',
        '',
        '> 链接为目标文件相对主 docs 的路径，复制到资源管理器/编辑器根目录即可打开。',
        '',
    ]
    for tag, items in groups.items():
        lines += ['## %s（%d）' % (tag, len(items)), '',
                  '| 时间 | 任务 | 主分类 | 标题 | 正文 | 经验 |',
                  '|---|---|---|---|---|---|']
        for entry in items:
            lines.append('| %s | %s | %s | %s | [%s](%s) | %s |' % (
                entry['time'], entry['task'], entry['class'] or '（平铺）',
                entry['title'], entry['file'], entry['relpath'],
                '是' if entry['is_lesson'] else '-'))
        lines.append('')
    return '\n'.join(lines)


def render_by_time(entries, docs_root):
    groups = group_by_month(entries)
    lines = [
        '# 记忆知识库 · 按时间',
        '',
        '- 生成时间：%s' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        '- 主 docs：`%s`' % docs_root,
        '- 条目数：%d（月份 %d）' % (len(entries), len(groups)),
        '- 标签视图见 [knowledge_by_tag.md](knowledge_by_tag.md)',
        '',
    ]
    for month, items in groups.items():
        lines += ['## %s（%d）' % (month, len(items)), '',
                  '| 时间 | 任务 | 主分类 | 标题 | 标签 | 正文 |',
                  '|---|---|---|---|---|---|']
        for entry in items:
            lines.append('| %s | %s | %s | %s | %s | [%s](%s) |' % (
                entry['time'], entry['task'], entry['class'] or '（平铺）',
                entry['title'], ', '.join(entry['tags']) or '-',
                entry['file'], entry['relpath']))
        lines.append('')
    return '\n'.join(lines)


def render_readme(entries, docs_root, out_dir):
    by_tag = group_by_tag(entries)
    by_month = group_by_month(entries)
    tasks = sorted({entry['task'] for entry in entries})
    lines = [
        '# 记忆知识库（export_knowledge v%s）' % KNOWLEDGE_VERSION,
        '',
        '- 生成时间：%s' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        '- 主 docs：`%s`' % docs_root,
        '- 输出目录：`%s`' % os.path.abspath(out_dir),
        '- 条目：%d 条 / 任务 %d 个 / 标签组 %d 个 / 月份 %d 个' % (
            len(entries), len(tasks), len(by_tag), len(by_month)),
        '',
        '## 两份视图怎么用',
        '',
        '| 文件 | 视角 | 适合 |',
        '|---|---|---|',
        '| knowledge_by_tag.md | 按标签（tech_solution / pitfall / workflow / tool_usage / decision / status） | 找某类经验、复盘踩过的坑 |',
        '| knowledge_by_time.md | 按月份（YYYY-MM） | 看进展脉络、跨任务时间线 |',
        '',
        '## 任务分布',
        '',
        '| 任务 | 条目数 |',
        '|---|---|',
    ]
    for task in tasks:
        lines.append('| %s | %d |' % (task, sum(1 for e in entries if e['task'] == task)))
    lines += ['', '> 正文 source of truth 在 `docs_rj/memory_rj/`，本目录只是视图，不要在此编辑。',
              '> 重新生成：`python scripts/export_knowledge.py --format md --out <本目录>`', '']
    return '\n'.join(lines)


def build_json(entries, docs_root):
    by_tag = {tag: [item['relpath'] for item in items] for tag, items in group_by_tag(entries).items()}
    by_month = {month: [item['relpath'] for item in items]
                for month, items in group_by_month(entries).items()}
    return {
        'knowledge_version': KNOWLEDGE_VERSION,
        'generated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'docs_root': docs_root,
        'total': len(entries),
        'entries': entries,
        'by_tag': by_tag,
        'by_month': by_month,
    }


def do_export(fmt, out_dir, docs_arg=None):
    docs_root, memory_root = memory_export.resolve_memory_root(docs_arg)
    if not docs_root:
        print('错误：未解析到主 docs（可加 --docs-dir 显式指定）', file=sys.stderr)
        return 2
    if not os.path.isdir(memory_root):
        print('错误：记忆目录不存在: %s' % memory_root, file=sys.stderr)
        return 2

    entries = collect_entries(docs_root, memory_root)
    if not entries:
        print('未找到任何记忆文件（%s）' % memory_root, file=sys.stderr)
        return 1

    try:
        os.makedirs(out_dir, exist_ok=True)
        if fmt == 'json':
            payload = build_json(entries, docs_root)
            with open(os.path.join(out_dir, 'knowledge.json'), 'w', encoding='utf-8', newline='\n') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            files = ['knowledge.json']
        else:
            files = ['knowledge_by_tag.md', 'knowledge_by_time.md', 'README.md']
            bodies = [render_by_tag(entries, docs_root), render_by_time(entries, docs_root),
                      render_readme(entries, docs_root, out_dir)]
            for name, body in zip(files, bodies):
                with open(os.path.join(out_dir, name), 'w', encoding='utf-8', newline='\n') as handle:
                    handle.write(body)
    except OSError as exc:
        print('错误：写入输出目录失败: %s' % exc, file=sys.stderr)
        return 2

    by_tag = group_by_tag(entries)
    by_month = group_by_month(entries)
    print('## 导出完成（export_knowledge）')
    print('- 主 docs：%s' % docs_root)
    print('- 记忆根：%s' % memory_root)
    print('- 输出目录：%s' % os.path.abspath(out_dir))
    print('- 格式：%s' % fmt)
    print('- 条目：%d（任务 %d / 标签组 %d / 月份 %d）' % (
        len(entries), len({e['task'] for e in entries}), len(by_tag), len(by_month)))
    print('- 产出：%s' % '、'.join(files))
    print('- 标签分布：')
    for tag, items in by_tag.items():
        print('  - %s：%d' % (tag, len(items)))
    print('- 月份分布：%s' % '、'.join('%s(%d)' % (m, len(v)) for m, v in by_month.items()))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='记忆 → 结构化知识（按标签 / 按时间两视图，v1.1.0 · B3）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--format', choices=['md', 'json'], default='md', help='输出格式（默认 md）')
    parser.add_argument('--out', required=True, help='输出目录（不存在会自动创建）')
    parser.add_argument('--docs-dir', default=None, help='主 docs 目录（缺省按 marker 解析链）')
    args = parser.parse_args(argv)
    return do_export(args.format, args.out, args.docs_dir)


if __name__ == '__main__':
    sys.exit(main())
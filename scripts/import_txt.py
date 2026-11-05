#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_txt.py — 冷启动批量导入历史 txt/md → 分类记忆（v1.1.0 · B3 / 3.3）

把散落的历史笔记（txt / md）一次性吸进记忆体系，解决「新装 skill 一脸空白」：
  1. 按 `^#{1,3} ` 标题切节（无标题的整篇 / 前言算一节）
  2. 每节用 memory_tags.infer_memory_class 推断主分类（6 选 1）
  3. 每节落一条项目记忆（经 memory_shadow_write.write_project 唯一通道）

用法：
  python scripts/import_txt.py --src "D:\\notes\\指南.txt" --dry-run
  python scripts/import_txt.py --src "D:\\notes" --dry-run
  python scripts/import_txt.py --src "D:\\notes\\指南.txt" --task my_notes --min-lines 5

退出码：
  0 成功（dry-run 视为成功）
  1 未切出任何有效节
  2 参数/环境错误（--src 不存在、任务名非法、批量导入全部失败）

技术约束：仅 Python 标准库；分类推断复用 memory_tags，写入复用 memory_shadow_write。
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_shadow_write  # noqa: E402
import memory_tags  # noqa: E402

HEADING_RE = re.compile(r'^(#{1,3})\s+(.+?)\s*$')
SOURCES_EXT = ('.txt', '.md')
PREAMBLE_TITLE = '（前言 / 无标题块）'
STEM_SANITIZE_RE = re.compile(r'[^a-z0-9_]+')


def collect_sources(src):
    """--src 是文件直接返回；是目录则递归收 .txt/.md（按路径排序）。"""
    if os.path.isfile(src):
        return [src]
    hits = []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith(SOURCES_EXT):
                hits.append(os.path.join(root, name))
    return hits


def split_sections(text, min_lines):
    """按 1~3 级标题切节，返回 [{title, level, start, body, lines}]。

    少于 min_lines 行正文的节丢弃（标题党 / 空章节不产记忆）。
    """
    sections = []
    current = {'title': PREAMBLE_TITLE, 'level': 0, 'start': 1, 'lines': []}
    for lineno, raw in enumerate(text.splitlines(), 1):
        found = HEADING_RE.match(raw)
        if found:
            sections.append(current)
            current = {'title': found.group(2).strip(), 'level': len(found.group(1)),
                       'start': lineno, 'lines': []}
        else:
            current['lines'].append(raw)
    sections.append(current)

    kept = []
    for section in sections:
        body = '\n'.join(section['lines']).strip('\n')
        body_lines = [ln for ln in body.splitlines() if ln.strip()]
        if len(body_lines) < min_lines:
            continue
        section['body'] = body
        section['lines'] = len(body_lines)
        kept.append(section)
    return kept


def default_task_name(src):
    """从文件名抽任务名：小写化 + 非 [a-z0-9_] 转下划线。"""
    stem = os.path.splitext(os.path.basename(src))[0].lower()
    name = STEM_SANITIZE_RE.sub('_', stem).strip('_')
    return name or 'imported_notes'


def render_content(section, relpath):
    return '# %s\n\n> 来源：%s（第 %d 行起，标题层级 H%d，import_txt 冷启动导入）\n\n%s\n' % (
        section['title'], relpath, section['start'], section['level'], section['body'])


def excerpt(body, width=36):
    flat = ' '.join(body.split())
    return (flat[:width] + '…') if len(flat) > width else flat


def do_import(src, task_arg=None, dry_run=False, min_lines=3):
    sources = collect_sources(src)
    if not sources:
        print('错误：--src 下未找到 .txt / .md 文件：%s' % src, file=sys.stderr)
        return 2

    task = task_arg or default_task_name(src)
    if not memory_tags.TASK_NAME_RE.match(task):
        print('错误：非法任务名 `%s`（只允许 [a-z0-9_]+，可用 --task 显式指定）' % task, file=sys.stderr)
        return 2

    rows = []
    for path in sources:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                text = handle.read()
        except OSError as exc:
            print('警告：读取失败跳过 %s（%s）' % (path, exc), file=sys.stderr)
            continue
        relpath = os.path.basename(path)
        for section in split_sections(text, min_lines):
            cls = memory_tags.infer_memory_class('%s\n%s' % (section['title'], section['body']))
            rows.append({'source': relpath, 'section': section, 'class': cls})

    if not rows:
        print('未切出任何有效节（min-lines=%d）：%s' % (min_lines, src), file=sys.stderr)
        return 1

    print('## %s（import_txt）' % ('导入预演' if dry_run else '导入执行'))
    print('- 源：%s（%d 个文件）' % (os.path.abspath(src), len(sources)))
    print('- 目标任务名：%s' % task)
    print('- 切节规则：`^#{1,3} `；正文有效行 < %d 的节丢弃' % min_lines)
    print('')
    print('| # | 源文件 | 节标题 | 行数 | 推断分类 | 摘要 |')
    print('|---|---|---|---|---|---|')
    for idx, row in enumerate(rows, 1):
        section = row['section']
        print('| %d | %s | %s | %d | %s | %s |' % (
            idx, row['source'], section['title'], section['lines'], row['class'],
            excerpt(section['body'])))

    by_class = {}
    for row in rows:
        by_class[row['class']] = by_class.get(row['class'], 0) + 1
    print('')
    print('## 小结')
    print('- 有效节：%d' % len(rows))
    for cls in memory_tags.MEMORY_TAGS:
        if cls in by_class:
            print('  - %s：%d' % (cls, by_class[cls]))
    others = [c for c in by_class if c not in memory_tags.MEMORY_TAGS]
    for cls in others:
        print('  - %s：%d' % (cls, by_class[cls]))

    if dry_run:
        print('- 说明：dry-run 未写任何文件；去掉 --dry-run 会经 write_project 落 %d 条记忆' % len(rows))
        return 0

    ok = 0
    failed = 0
    for row in rows:
        content = render_content(row['section'], row['source'])
        try:
            receipt = memory_shadow_write.write_project(
                task, content,
                memory_class=row['class'],
                intent='冷启动批量导入历史笔记',
                tags=['import_txt'],
                importance_level='low',
                outcome='unknown')
        except Exception as exc:  # 单条失败不拖垮整批
            failed += 1
            print('  - 失败：%s（%s）' % (row['section']['title'], exc), file=sys.stderr)
            continue
        if isinstance(receipt, dict) and receipt.get('project_ok'):
            ok += 1
        else:
            failed += 1
    print('- 落盘成功 %d / 失败 %d' % (ok, failed))
    return 0 if ok else 2


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='冷启动批量导入 txt/md → 分类记忆（v1.1.0 · B3）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--src', required=True, help='txt/md 文件，或包含它们的目录（递归）')
    parser.add_argument('--task', default=None, help='任务名（缺省按文件名推断，仅 [a-z0-9_]+）')
    parser.add_argument('--dry-run', action='store_true', help='只打印切节与分类计划，不写文件')
    parser.add_argument('--min-lines', type=int, default=3, help='正文有效行下限，低于则丢弃该节（默认 3）')
    args = parser.parse_args(argv)

    if not os.path.exists(args.src):
        print('错误：--src 不存在：%s' % args.src, file=sys.stderr)
        return 2
    return do_import(args.src, args.task, args.dry_run, max(args.min_lines, 1))


if __name__ == '__main__':
    sys.exit(main())
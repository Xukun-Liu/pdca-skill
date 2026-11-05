#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_import.py — 记忆包导入（v1.1.0 · B3 / 3.2）

把 memory_export.py 产出的自包含包还原回本机 docs_rj/memory_rj：
  1. 读 manifest.json，逐条校验 sha256（防传输损坏 / 手改走样）
  2. 按 entry 的 class / month 复原标签文件夹路径
  3. 把文件内容里遗留的源机绝对路径（source_memory_root / source_docs_root）
     自动改写成本机前缀
  4. --dry-run 只打计划不动盘；目标已存在且未加 --force 时跳过

用法：
  python scripts/memory_import.py --src D:\\tmp\\exp --dry-run
  python scripts/memory_import.py --src D:\\tmp\\exp
  python scripts/memory_import.py --src D:\\tmp\\exp --force
  python scripts/memory_import.py --src D:\\tmp\\exp --docs-dir C:\\docs_rj

退出码：
  0 全部成功（含「已存在跳过」；不算错误）
  1 有条目校验失败或写入失败
  2 环境/参数错误（manifest 缺失、主 docs 解析失败）

技术约束：仅 Python 标准库；哈希与主 docs 解析复用 inventory.py。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import memory_export  # noqa: E402

ACTION_CREATE = '新建'
ACTION_OVERWRITE = '覆盖'
ACTION_SKIP_EXISTS = '跳过(已存在)'
ACTION_SKIP_HASH = '跳过(哈希不符)'


def load_manifest(src_dir):
    """读 manifest.json；缺失或损坏返回 (None, 错误说明)。"""
    path = os.path.join(src_dir, 'manifest.json')
    if not os.path.isfile(path):
        return None, '未找到 manifest.json：%s' % path
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, 'manifest.json 解析失败: %s' % exc
    if not isinstance(data, dict) or 'entries' not in data:
        return None, 'manifest.json 结构不符（缺 entries 字段）'
    return data, ''


def target_path(memory_root, entry):
    """按 class / month 复原目标路径；两者都缺时落到 memory_rj 根。"""
    parts = [p for p in (entry.get('class') or '', entry.get('month') or '') if p]
    parts.append(entry['file'])
    return os.path.join(memory_root, *parts)


def rewrite_prefixes(text, pairs):
    """把源机绝对路径前缀替换为本机前缀，返回 (新文本, 替换次数)。"""
    count = 0
    for old, new in pairs:
        if not old or not new or old == new:
            continue
        # 同时覆盖 / 与 \\ 两种分隔写法，避免跨平台导出后漏改
        for variant_old, variant_new in (
            (old, new),
            (old.replace('\\', '/'), new.replace('\\', '/')),
            (old.replace('/', '\\'), new.replace('/', '\\')),
        ):
            if variant_old and variant_old != variant_new and variant_old in text:
                count += text.count(variant_old)
                text = text.replace(variant_old, variant_new)
    return text, count


def plan_one(src_dir, memory_root, entry, target_docs_root, source_docs_root, force):
    """对单条 entry 生成执行计划，不落盘。

    Returns:
        dict(action, target, src_file, rewrites, note)
    """
    src_file = os.path.join(src_dir, entry.get('relpath', '').replace('/', os.sep))
    dest = target_path(memory_root, entry)
    result = {'target': dest, 'src_file': src_file, 'rewrites': 0, 'note': ''}

    if not os.path.isfile(src_file):
        result['action'] = ACTION_SKIP_HASH
        result['note'] = '包内文件缺失'
        return result

    actual = inventory.short_hash(src_file)
    if actual != entry.get('sha256'):
        result['action'] = ACTION_SKIP_HASH
        result['note'] = 'sha256 不符（期望 %s / 实际 %s）' % (entry.get('sha256'), actual)
        return result

    if os.path.exists(dest) and not force:
        result['action'] = ACTION_SKIP_EXISTS
        result['note'] = '加 --force 可覆盖'
        return result

    result['action'] = ACTION_OVERWRITE if os.path.exists(dest) else ACTION_CREATE
    pairs = [
        (entry.get('source_memory_root') or source_docs_root, memory_root),
        (source_docs_root, target_docs_root),
    ]
    try:
        # newline='' 保留原始换行符（CRLF/LF），否则 dry-run 与执行两次读取结果会漂移
        with open(src_file, 'r', encoding='utf-8', errors='replace', newline='') as handle:
            text = handle.read()
    except OSError as exc:
        result['action'] = ACTION_SKIP_HASH
        result['note'] = '读取失败: %s' % exc
        return result
    _new_text, result['rewrites'] = rewrite_prefixes(text, pairs)
    return result


def do_import(src_dir, docs_arg=None, dry_run=False, force=False):
    manifest, error = load_manifest(src_dir)
    if manifest is None:
        print('错误：%s' % error, file=sys.stderr)
        return 2

    docs_root, memory_root = memory_export.resolve_memory_root(docs_arg)
    if not docs_root:
        print('错误：未解析到主 docs（可加 --docs-dir 显式指定）', file=sys.stderr)
        return 2

    entries = manifest.get('entries') or []
    source_docs_root = manifest.get('source_docs_root') or ''
    if not entries:
        print('错误：manifest 内无条目（可能导出了空任务）', file=sys.stderr)
        return 2

    # manifest 顶层未存 memory_root 时，退回「源 docs 根 + memory_rj」推断
    for entry in entries:
        if not entry.get('source_memory_root'):
            entry['source_memory_root'] = os.path.join(source_docs_root, 'memory_rj')

    print('## %s（memory_import）' % ('导入预演' if dry_run else '导入执行'))
    print('- 任务：%s' % manifest.get('task', '-'))
    print('- 包版本：%s（导出于 %s）' % (manifest.get('bundle_version', '-'), manifest.get('exported_at', '-')))
    print('- 源目录：%s' % os.path.abspath(src_dir))
    print('- 目标记忆根：%s' % memory_root)
    print('- 模式：%s' % ('dry-run（不动盘）' if dry_run else ('force（覆盖已存在）' if force else '安全（跳过已存在）')))
    print('')
    print('| # | 动作 | 分类/月份 | 文件 | 目标 | 改前缀 | 备注 |')
    print('|---|---|---|---|---|---|---|')

    stats = {ACTION_CREATE: 0, ACTION_OVERWRITE: 0, ACTION_SKIP_EXISTS: 0, ACTION_SKIP_HASH: 0}
    rewrite_total = 0
    failures = 0

    for idx, entry in enumerate(entries, 1):
        plan = plan_one(src_dir, memory_root, entry, docs_root, source_docs_root, force)
        action = plan['action']
        stats[action] = stats.get(action, 0) + 1
        if action == ACTION_SKIP_HASH:
            failures += 1
        if not dry_run and action in (ACTION_CREATE, ACTION_OVERWRITE):
            try:
                os.makedirs(os.path.dirname(plan['target']), exist_ok=True)
                with open(plan['src_file'], 'r', encoding='utf-8', errors='replace', newline='') as handle:
                    text = handle.read()
                pairs = [
                    (entry.get('source_memory_root') or source_docs_root, memory_root),
                    (source_docs_root, docs_root),
                ]
                text, _ = rewrite_prefixes(text, pairs)
                # newline='' 原样写回，保证「导出 → 清空 → 导入」后字节级一致（含 CRLF）
                with open(plan['target'], 'w', encoding='utf-8', newline='') as handle:
                    handle.write(text)
            except OSError as exc:
                stats[action] -= 1
                stats[ACTION_SKIP_HASH] = stats.get(ACTION_SKIP_HASH, 0) + 1
                failures += 1
                plan['note'] = '写入失败: %s' % exc
        rewrite_total += plan['rewrites']
        print('| %d | %s | %s/%s | %s | %s | %d | %s |' % (
            idx, action,
            entry.get('class') or '（平铺）', entry.get('month') or '-',
            entry['file'],
            os.path.relpath(plan['target'], memory_root).replace(os.sep, '/'),
            plan['rewrites'], plan['note'] or '-'))

    print('')
    print('## 小结')
    print('- 新建 %d / 覆盖 %d / 跳过(已存在) %d / 跳过(失败) %d' % (
        stats.get(ACTION_CREATE, 0), stats.get(ACTION_OVERWRITE, 0),
        stats.get(ACTION_SKIP_EXISTS, 0), stats.get(ACTION_SKIP_HASH, 0)))
    print('- 路径前缀改写：%d 处' % rewrite_total)
    print('- 条目总数：%d（manifest 声明 %d）' % (len(entries), manifest.get('counts', {}).get('total', len(entries))))
    if dry_run:
        print('- 说明：dry-run 未写任何文件，去掉 --dry-run 即执行')
    if failures:
        print('- 结论：有 %d 条失败，请核对包完整性' % failures, file=sys.stderr)
        return 1
    print('- 结论：全部成功')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='记忆包导入（v1.1.0 · B3）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--src', required=True, help='memory_export 产出的包目录（含 manifest.json）')
    parser.add_argument('--docs-dir', default=None, help='目标主 docs 目录（缺省按 marker 解析链）')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不写文件')
    parser.add_argument('--force', action='store_true', help='目标已存在时覆盖')
    args = parser.parse_args(argv)
    return do_import(args.src, args.docs_dir, args.dry_run, args.force)


if __name__ == '__main__':
    sys.exit(main())
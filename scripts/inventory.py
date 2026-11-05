#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventory.py — 单一清单 + 骨架补建 + SUMMARY 死链检查（v1.1.0 · B2 / B2+S2+C3）

三个动作收敛成一条命令，替代手工 Get-ChildItem / ls / 逐链接点开：
  1. 默认：输出三类清单（文档 / 脚本 / 引用），每项带 sha256 前 12 位 + 大小
  2. --fix-skeleton：按 8 要素补建缺失骨架（幂等，第二次输出「0 项待建」）
  3. --check-summary：逐链接校验 SUMMARY_RJ.md，死链当场报（退码 1）

用法：
  python scripts/inventory.py
  python scripts/inventory.py --root "D:\\some\\skill"
  python scripts/inventory.py --fix-skeleton
  python scripts/inventory.py --check-summary

退出码：
  0 正常（含 --fix-skeleton 已补齐 / --check-summary 无死链）
  1 --check-summary 发现死链，或清单扫描发现非法主分类目录
  2 环境错误（主 docs 解析失败 / SUMMARY 不存在 / 参数冲突）

技术约束：仅 Python 标准库；主 docs 解析复用 tidy_common.resolve_primary_docs。
"""

import argparse
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402

SKELETON_DIRS = ('spec_rj', 'task_rj', 'handoff_rj', 'archive_rj', 'memory_rj', 'check_rj')

MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def resolve_docs(primary_docs_arg=None):
    """解析主 docs 目录；失败返回 None（不静默退回 ./docs_rj）。"""
    try:
        docs = tidy_common.resolve_primary_docs(primary_docs_arg)
    except Exception as exc:  # noqa: BLE001 - 解析链异常统一按环境错误
        print('错误：解析主 docs 失败: %s' % exc, file=sys.stderr)
        return None
    if not docs or not os.path.isdir(docs):
        return None
    return os.path.abspath(docs)


def short_hash(path, chunk=1 << 20):
    """文件 sha256 前 12 位（大文件分块读，避免一次性吃内存）。"""
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as handle:
            while True:
                block = handle.read(chunk)
                if not block:
                    break
                digest.update(block)
    except OSError:
        return 'ERR'
    return digest.hexdigest()[:12]


def walk_files(base, suffix):
    """递归收集指定后缀文件（按路径排序，输出稳定）。"""
    hits = []
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith(suffix):
                hits.append(os.path.join(root, name))
    return hits


def render_table(title, base, files):
    print('\n## %s（%d）' % (title, len(files)))
    if not files:
        print('- 无')
        return
    print('| 相对路径 | 大小(B) | sha256[:12] |')
    print('|---|---|---|')
    for path in files:
        rel = os.path.relpath(path, base).replace('\\', '/')
        try:
            size = os.path.getsize(path)
        except OSError:
            size = -1
        print('| %s | %s | %s |' % (rel, size, short_hash(path)))


def do_inventory(root, docs):
    print('## inventory')
    print('- root : %s' % root)
    print('- docs : %s' % docs)
    doc_files = walk_files(docs, '.md')
    script_files = walk_files(os.path.join(root, 'scripts'), '.py')
    ref_files = walk_files(os.path.join(root, 'references'), '.md')
    render_table('文档清单 docs_rj/**/*.md', docs, doc_files)
    render_table('脚本清单 scripts/**/*.py', root, script_files)
    render_table('引用清单 references/**/*.md', root, ref_files)
    print('\n## 合计')
    print('- 文档 %d / 脚本 %d / 引用 %d = %d 个文件'
          % (len(doc_files), len(script_files), len(ref_files),
             len(doc_files) + len(script_files) + len(ref_files)))
    return 0


def do_fix_skeleton(docs):
    """按 8 要素补建缺失骨架，幂等：第二次跑输出「0 项待建」。"""
    pending = []
    for sub in SKELETON_DIRS:
        path = os.path.join(docs, sub)
        if not os.path.isdir(path):
            pending.append(path)
    summary = os.path.join(docs, 'SUMMARY_RJ.md')
    need_summary = not os.path.isfile(summary)

    print('## fix-skeleton')
    print('- docs: %s' % docs)
    if not pending and not need_summary:
        print('- 0 项待建（骨架完整）')
        return 0

    for path in pending:
        os.makedirs(path, exist_ok=True)
        print('- 已建 %s' % path)
    if need_summary:
        # 只铺最小骨架，不做内容生成（内容走 summary_view 三触发①）
        with open(summary, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write('# 📚 文档汇总视图（SUMMARY）\n\n'
                         '> 骨架由 inventory.py --fix-skeleton 创建，'
                         '内容请按 references/common/pa/summary_view.md 三触发①补全。\n')
        print('- 已建 %s（最小骨架）' % summary)
    print('- 本次补建 %d 项' % (len(pending) + (1 if need_summary else 0)))
    return 0


def do_check_summary(docs):
    """C3：逐链接校验 SUMMARY_RJ.md，相对链接目标不存在即死链。"""
    summary = os.path.join(docs, 'SUMMARY_RJ.md')
    if not os.path.isfile(summary):
        print('错误：SUMMARY_RJ.md 不存在: %s' % summary, file=sys.stderr)
        return 2
    with open(summary, 'r', encoding='utf-8') as handle:
        lines = handle.readlines()

    total = 0
    dead = []
    for lineno, line in enumerate(lines, 1):
        for text, target in MD_LINK_RE.findall(line):
            target = target.strip()
            if not target or target.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            total += 1
            path_part = target.split('#')[0]
            if not path_part:
                continue
            resolved = os.path.normpath(os.path.join(docs, path_part))
            if not os.path.exists(resolved):
                dead.append((lineno, text, target))

    print('## check-summary（C3）')
    print('- SUMMARY: %s' % summary)
    print('- 相对链接 %d 条，死链 %d 条' % (total, len(dead)))
    for lineno, text, target in dead:
        print('  L%d: [%s](%s) → 目标不存在' % (lineno, text, target))
    return 1 if dead else 0


def main():
    parser = argparse.ArgumentParser(
        description='清单 / 骨架补建 / SUMMARY 死链检查（stdlib-only）')
    parser.add_argument('--root', default='.', help='技能根目录（默认当前目录）')
    parser.add_argument('--docs-dir', default=None, help='显式指定主 docs（默认走 marker）')
    parser.add_argument('--fix-skeleton', action='store_true', help='补建 8 要素骨架（幂等）')
    parser.add_argument('--check-summary', action='store_true', help='校验 SUMMARY 相对链接')
    args = parser.parse_args()

    if args.fix_skeleton and args.check_summary:
        print('错误：--fix-skeleton 与 --check-summary 不能同时使用', file=sys.stderr)
        return 2

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print('错误：--root 不存在: %s' % root, file=sys.stderr)
        return 2

    docs = resolve_docs(args.docs_dir)
    if docs is None and args.fix_skeleton:
        # 骨架补建需要明确落点：未解析到 marker 时退回 root/docs_rj（显式打印，不静默）
        docs = os.path.join(root, 'docs_rj')
        print('[提示] 未解析到 marker，骨架将建在 %s' % docs)
    if docs is None and args.check_summary:
        print('错误：未解析到主 docs，无法校验 SUMMARY', file=sys.stderr)
        return 2

    if args.fix_skeleton:
        return do_fix_skeleton(docs)
    if args.check_summary:
        return do_check_summary(docs)
    if docs is None:
        print('错误：未解析到主 docs 目录。请先跑 generate_docs.py --declare-primary '
              '或传 --docs-dir。', file=sys.stderr)
        return 2
    return do_inventory(root, docs)


if __name__ == '__main__':
    sys.exit(main())
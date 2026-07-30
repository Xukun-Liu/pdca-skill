#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
link_indexer.py — riji-skill 文件关系图构建器

作用
----
扫描 markdown 文件链接,构建关系图,检测两类问题:
  - broken_link: 链接的 target .md 文件不存在
  - missing_reverse_link: A→B 但 B 不→A(仅对同目录文件检测,跨目录引用不强制双向)

构建产物:
  - nodes: 所有 .md 文件列表(绝对路径)
  - edges: 链接关系 [{source, target, text, line_no}, ...]
  - issues: 检测到的问题 [{type, source, target, line_no, reason}, ...]

借鉴来源: 无(纯 Python 标准库自实现)
Traceability: SKILL.md §3 文档体系, references/common/pa/summary_view.md §五 漂移检查
设计来源: SKILL.md §0 流程优先, references/common/pda/document_specs.md 文档互链

技术约束
--------
* 纯 Python 标准库(os / sys / re / json / argparse / logging)。
* 零新增第三方依赖。
* 深度限制 max_depth 默认 3(root_dir 本身 depth=0)。

运行
----
  python scripts/link_indexer.py [--root PATH] [--max-depth N] [--json]
"""

import os
import sys
import re
import json
import argparse
import logging

# 风格对齐 route_check.py / protocol_align.py(虽不 import protocol,保留路径常量备用)
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

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
    """读取文本文件,失败返回空串(对齐 route_check._read_text 行为)。"""
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ''


# markdown 链接正则: [text](target.md)
# group(1)=text(链接显示文本),group(2)=target(必须 .md 结尾)
# 注:此正则不匹配带空格的 target(markdown 规范允许 <target with space>,
#     但项目内链接均无空格,不处理 <> 形式)
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')

# 扫描时忽略的目录名(对齐 route_check._collect_md_files 的 ignore_dirs + 项目特性)
_IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                 '.skill_graph_cache', '.idea', '.vscode'}


# ===========================================================================
# scan_links: 扫描单文件的 markdown 链接
# ===========================================================================
def scan_links(file_path):
    """扫描单个 markdown 文件,提取所有 markdown 链接(排除 http 链接)。

    正则: `\\[([^\\]]+)\\]\\(([^)]+\\.md)\\)`
    - group(1) = 链接文本
    - group(2) = 链接目标(必须以 .md 结尾)
    - 排除 http:// 和 https:// 开头的链接(那些是外部 URL,不算文件关系)

    Args:
        file_path: markdown 文件路径(相对或绝对均可,内部转绝对)。

    Returns:
        list[dict]: 每条形如
            {'source': str, 'target': str, 'text': str, 'line_no': int}
            source 为 file_path 的绝对路径;
            target 为 markdown 中写的原始路径(未解析相对路径,保留 # 锚点)。
            读取失败返回空列表。
    """
    content = _read_text(file_path)
    if not content:
        return []

    abs_source = os.path.abspath(file_path)
    links = []
    # 逐行匹配,记录行号(从 1 开始,对齐编辑器显示)
    for line_no, line in enumerate(content.splitlines(), start=1):
        for match in _MD_LINK_RE.finditer(line):
            text = match.group(1)
            target = match.group(2)
            # 排除 http/https 链接(外部 URL,不是文件关系)
            if target.startswith('http://') or target.startswith('https://'):
                continue
            links.append({
                'source': abs_source,
                'target': target,
                'text': text,
                'line_no': line_no,
            })
    return links


# ===========================================================================
# build_graph: 构建文件关系图
# ===========================================================================
def build_graph(root_dir, max_depth=3):
    """遍历 root_dir 下 .md 文件(限制深度 max_depth),构建关系图。

    深度定义:
      - root_dir 本身 depth=0(其下 .md 文件计入 nodes)
      - root_dir/a/ depth=1
      - root_dir/a/b/ depth=2
      - root_dir/a/b/c/ depth=3
      - max_depth=3 表示扫描深度 <=3 的目录(含 root_dir/a/b/c/),
        root_dir/a/b/c/d/ 不扫描

    Args:
        root_dir: 扫描根目录路径(相对或绝对均可,内部转绝对)。
        max_depth: 目录深度限制,默认 3。

    Returns:
        dict: {
            'root': str,                  # root_dir 绝对路径
            'max_depth': int,             # 实际使用的 max_depth
            'nodes': list[str],           # 所有 .md 文件绝对路径
            'edges': list[dict],          # 链接关系(scan_links 输出)
            'issues': list[dict],         # 检测到的问题(broken_link + missing_reverse_link)
        }
    """
    root_dir = os.path.abspath(root_dir)
    nodes = []

    # 深度限制遍历:手写栈式 DFS,控制 depth
    # (os.walk 改 dirs 列表也能限深度,但栈式更直观)
    walk_stack = [(root_dir, 0)]
    while walk_stack:
        cur_dir, depth = walk_stack.pop()
        try:
            entries = sorted(os.listdir(cur_dir))
        except OSError as exc:
            logger.warning("listdir 失败 %s: %s", cur_dir, exc)
            continue
        for name in entries:
            full_path = os.path.join(cur_dir, name)
            if os.path.isdir(full_path):
                # 跳过忽略目录
                if name in _IGNORE_DIRS:
                    continue
                # 深度限制:子目录 depth+1,不超过 max_depth 才入栈
                if depth + 1 <= max_depth:
                    walk_stack.append((full_path, depth + 1))
            elif name.endswith('.md'):
                nodes.append(full_path)

    # 收集 edges:对每个 .md 文件调 scan_links
    edges = []
    for node_path in nodes:
        edges.extend(scan_links(node_path))

    # 检测 issues:broken_link + missing_reverse_link
    issues = []
    issues.extend(_detect_broken_links(edges))
    issues.extend(_detect_missing_reverse_links(edges))

    return {
        'root': root_dir,
        'max_depth': max_depth,
        'nodes': nodes,
        'edges': edges,
        'issues': issues,
    }


def _resolve_target(source, target):
    """把 markdown 链接的 target 解析为绝对路径(去掉 # 锚点 + 相对 source 目录)。

    Args:
        source: source 文件绝对路径。
        target: markdown 中写的原始 target(可能含 # 锚点)。

    Returns:
        str: 解析后的绝对路径(无论是否存在)。纯锚点链接(#xxx)返回空串。
    """
    target_path = target.split('#', 1)[0].strip()
    if not target_path:
        return ''
    source_dir = os.path.dirname(source)
    return os.path.abspath(os.path.join(source_dir, target_path))


def _detect_broken_links(edges):
    """检测 broken_link:target .md 文件不存在。

    target 路径解析:
      - 去掉 # 锚点
      - 相对于 source 文件所在目录解析为绝对路径
      - 检查文件是否存在

    Args:
        edges: build_graph 收集的 edges 列表。

    Returns:
        list[dict]: 每条形如
            {'type': 'broken_link', 'source': str, 'target': str,
             'resolved': str, 'line_no': int, 'reason': str}
    """
    issues = []
    seen = set()  # 去重 (source, target, line_no)
    for edge in edges:
        source = edge['source']
        target = edge['target']
        line_no = edge['line_no']
        key = (source, target, line_no)
        if key in seen:
            continue
        seen.add(key)

        resolved = _resolve_target(source, target)
        if not resolved:
            continue  # 纯锚点链接,跳过

        if not os.path.isfile(resolved):
            issues.append({
                'type': 'broken_link',
                'source': source,
                'target': target,
                'resolved': resolved,
                'line_no': line_no,
                'reason': 'target .md 文件不存在(broken_link)',
            })
    return issues


def _detect_missing_reverse_links(edges):
    """检测 missing_reverse_link:A→B 但 B 不→A(仅对同目录文件检测)。

    同目录定义:os.path.dirname(A) == os.path.dirname(B)
    跨目录链接不强制双向(如 SUMMARY_RJ.md 引用各子目录文件是正常的单向引用)。

    Args:
        edges: build_graph 收集的 edges 列表。

    Returns:
        list[dict]: 每条形如
            {'type': 'missing_reverse_link', 'source': str, 'target': str,
             'line_no': int, 'reason': str}
        source/target 为解析后的绝对路径(A→B 中的 A 和 B)。
    """
    # 第 1 遍:构建 (A_abs, B_abs) 集合 + 保留有效 edge 元信息
    resolved_edges = set()
    edge_meta = []
    for edge in edges:
        source = edge['source']
        target = edge['target']
        resolved_target = _resolve_target(source, target)
        if not resolved_target:
            continue
        # 仅记录 target 文件存在的边(broken_link 在另一个 check 里报)
        if not os.path.isfile(resolved_target):
            continue
        # 仅对同目录文件检测
        if os.path.dirname(source) != os.path.dirname(resolved_target):
            continue
        resolved_edges.add((source, resolved_target))
        edge_meta.append({
            'source': source,
            'target': resolved_target,
            'original_target': target,
            'line_no': edge['line_no'],
        })

    # 第 2 遍:检查每条 A→B 是否存在 B→A
    issues = []
    seen = set()
    for meta in edge_meta:
        a = meta['source']
        b = meta['target']
        if (b, a) in resolved_edges:
            continue  # 存在反向链接,通过
        key = (a, b)
        if key in seen:
            continue  # 同一对 A→B 已报过(A 内多处链接同一 B)
        seen.add(key)
        issues.append({
            'type': 'missing_reverse_link',
            'source': a,
            'target': b,
            'line_no': meta['line_no'],
            'reason': '%s → %s 但 %s 未反向链接 %s(missing_reverse_link)' % (
                os.path.basename(a), os.path.basename(b),
                os.path.basename(b), os.path.basename(a)),
        })
    return issues


# ===========================================================================
# CLI / main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='riji-skill 文件关系图构建器(stdlib-only)')
    # 位置参数 root_pos(优先)+ --root 选项(兜底默认 docs_rj)
    # 用法: python link_indexer.py [ROOT] [--root PATH] [--max-depth N] [--json]
    #   python link_indexer.py docs_rj --json     → root=docs_rj(位置参数)
    #   python link_indexer.py --json              → root=docs_rj(--root 默认)
    #   python link_indexer.py --root other --json → root=other
    parser.add_argument('root_pos', nargs='?', default=None,
                        help='扫描根目录(位置参数,优先于 --root;默认与 --root 一致)')
    parser.add_argument('--root', default='docs_rj',
                        help='扫描根目录(选项,默认 docs_rj;位置参数存在时被覆盖)')
    parser.add_argument('--max-depth', type=int, default=3,
                        help='目录深度限制(默认 3,root 本身 depth=0)')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果到 stdout(日志仍走 stderr)')
    args = parser.parse_args()

    # 位置参数优先,无则用 --root 选项
    root_arg = args.root_pos if args.root_pos else args.root
    root_dir = os.path.abspath(root_arg)
    if not os.path.isdir(root_dir):
        logger.error("root 目录不存在: %s", root_dir)
        return 2

    logger.info("=== 文件关系图构建(link_indexer)开始,root=%s max_depth=%d ===",
                root_dir, args.max_depth)
    graph = build_graph(root_dir, max_depth=args.max_depth)

    nodes_count = len(graph['nodes'])
    edges_count = len(graph['edges'])
    issues_count = len(graph['issues'])
    broken_count = sum(1 for i in graph['issues'] if i.get('type') == 'broken_link')
    reverse_count = sum(1 for i in graph['issues'] if i.get('type') == 'missing_reverse_link')
    logger.info("=== 关系图构建完成:nodes=%d edges=%d issues=%d(broken=%d / reverse=%d) ===",
                nodes_count, edges_count, issues_count, broken_count, reverse_count)

    if args.json:
        payload = {
            'root': graph['root'],
            'max_depth': graph['max_depth'],
            'nodes_count': nodes_count,
            'edges_count': edges_count,
            'issues_count': issues_count,
            'nodes': graph['nodes'],
            'edges': graph['edges'],
            'issues': graph['issues'],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('文件关系图报告(link_indexer.py)')
        print('root: %s' % root_dir)
        print('max_depth: %d' % args.max_depth)
        print('-' * 60)
        print('nodes: %d 个 .md 文件' % nodes_count)
        print('edges: %d 条链接' % edges_count)
        print('issues: %d 条(broken_link=%d / missing_reverse_link=%d)' % (
            issues_count, broken_count, reverse_count))
        print('-' * 60)
        # 列出前 20 条 issues(避免输出过长;完整结果用 --json)
        for issue in graph['issues'][:20]:
            print('[%s] %s → %s (line %s)' % (
                issue.get('type', '?'),
                os.path.basename(issue.get('source', '?')),
                issue.get('target', '?'),
                issue.get('line_no', '?')))
            print('  reason: %s' % issue.get('reason', ''))
        if issues_count > 20:
            print('... 还有 %d 条 issues 未显示(用 --json 查看完整)' % (issues_count - 20))

    # 有 issues exit 1(检测到问题);无 issues exit 0;目录不存在 exit 2
    return 0 if issues_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

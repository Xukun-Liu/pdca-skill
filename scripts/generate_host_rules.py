#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_host_rules.py — pdca-skill host rules 索引生成器

作用
----
扫描 {skill_root}/references/*.md，提取每个文件第一个 `# 标题` 作为规则名，
生成 markdown 表格索引到 {skill_root}/docs/rules/index.md。

借鉴业界 host rules 索引实践：把散落的规则文件聚合成
一张索引表，便于人工浏览 / agent 快速定位 / learn 子流程读取。

策略由模块级 RULES_SYNC_POLICY 常量定义（对应业界 rules-sync 实践的
rulesSyncPolicy），当前默认 strategy='create_missing_only'（已有 index.md 不
覆盖，除非 --force）。

核心函数：
  - generate_host_rules(skill_root, dry_run=False, force=False) -> dict

借鉴来源: 业界 host rules 索引实践
Traceability: SKILL.md §3 文档体系, references/plan/route/skill_management.md
设计来源: SKILL.md §0 流程优先, references/plan/design/project_structure.md 目录结构

技术约束
--------
* 纯 Python 标准库（os / sys / re / json / argparse / logging）。
* 零新增第三方依赖。
* 不修改 scripts/ 目录外文件（仅在用户运行本脚本时才会创建 docs/rules/index.md）。

运行
----
  python scripts/generate_host_rules.py . --dry-run
  python scripts/generate_host_rules.py . --json
  python scripts/generate_host_rules.py . --force
"""

import os
import sys
import re
import json
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ===========================================================================
# 同步策略常量（对应业界 rules-sync 实践的 rulesSyncPolicy）
# ===========================================================================
RULES_SYNC_POLICY = {
    'source_dir': 'references',         # 源目录（扫描 .md）
    'target_dir': 'docs/rules',         # 目标目录（生成 index.md）
    'strategy': 'create_missing_only',  # 策略：create_missing_only/overwrite/skip_existing
    'allow_force_overwrite': False,     # 是否允许 --force 覆盖（False=默认禁，--force 时才开）
    'supports_dry_run': True,           # 是否支持 --dry-run
    'generated_file_header': '<!-- generated-by: pdca-skill generate_host_rules.py -->',
    'runtime_priority': 'low',          # 运行优先级（low/normal/high）
}


# 匹配 markdown 一级标题行：`# 标题`（允许前后空白，标题非空）
_FIRST_HEADING_RE = re.compile(r'^\s*#\s+(.+?)\s*$', re.MULTILINE)


# ===========================================================================
# 辅助函数
# ===========================================================================
def _read_text(path):
    """读取文本文件，失败返回空串（对齐 route_check._read_text 行为）。

    用 utf-8-sig 编码自动 strip UTF-8 BOM（PowerShell Set-Content -Encoding UTF8
    等场景会写 BOM，BOM 会让行首 `^#` 正则匹配失败，导致规则名走兜底）。
    无 BOM 文件用 utf-8-sig 读取也兼容（向后兼容 utf-8）。
    """
    try:
        with open(path, 'r', encoding='utf-8-sig') as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ''


def _extract_rule_name(md_path):
    """从 markdown 文件提取第一个 `# 标题` 作为规则名。

    匹配 `^# 标题`（一级标题），跳过 `## 二级`、`### 三级` 等。提取失败时返回
    文件名（去 .md 后缀）作为兜底，保证索引表不缺行。

    Args:
        md_path: markdown 文件绝对路径。

    Returns:
        str: 规则名（去首尾空白）。
    """
    content = _read_text(md_path)
    if content:
        match = _FIRST_HEADING_RE.search(content)
        if match:
            return match.group(1).strip()
    # 兜底：文件名去 .md
    return os.path.splitext(os.path.basename(md_path))[0]


def _scan_references(skill_root):
    """扫描 {skill_root}/references/*.md，返回 [(filename, rule_name), ...]。

    仅扫一级目录（不递归子目录），按文件名升序。

    Args:
        skill_root: skill 包根目录绝对路径。

    Returns:
        list[tuple[str, str]]: [(filename, rule_name), ...]；目录不存在返回空列表。
    """
    ref_dir = os.path.join(skill_root, RULES_SYNC_POLICY['source_dir'])
    if not os.path.isdir(ref_dir):
        logger.warning('源目录不存在: %s', ref_dir)
        return []

    items = []
    # 递归遍历 references/ 子目录，items 第一项存 POSIX 相对路径（含子目录）
    for root, dirs, files in os.walk(ref_dir):
        for name in sorted(files):
            if not name.endswith('.md'):
                continue
            full = os.path.join(root, name)
            if not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, ref_dir).replace(os.sep, '/')
            rule_name = _extract_rule_name(full)
            items.append((rel, rule_name))
    return items


def _build_index_markdown(items, skill_root):
    """构造 index.md 内容。

    表格行格式：| [xxx.md](../../references/xxx.md) | 提取的标题 |

    相对路径从 docs/rules/index.md 指向 references/xxx.md，需上两级：
        docs/rules/index.md → docs/rules/ → docs/ → skill_root/ → references/xxx.md
    即 `../../references/xxx.md`。

    Args:
        items: _scan_references 的返回值。
        skill_root: skill 包根目录绝对路径（仅用于日志，不参与路径生成）。

    Returns:
        str: 完整的 index.md markdown 文本。
    """
    header = RULES_SYNC_POLICY['generated_file_header']
    lines = []
    lines.append(header)
    lines.append('# Host Rules Index')
    lines.append('')
    lines.append('> 自动生成，请勿手工编辑。运行 `python scripts/generate_host_rules.py .` 刷新。')
    lines.append('')
    lines.append('| 文件 | 规则名 |')
    lines.append('|------|--------|')
    for filename, rule_name in items:
        link = '../../%s/%s' % (RULES_SYNC_POLICY['source_dir'], filename)
        # 转义 markdown 表格中的 | 字符
        safe_rule = rule_name.replace('|', '\\|')
        lines.append('| [%s](%s) | %s |' % (filename, link, safe_rule))
    lines.append('')
    return '\n'.join(lines)


# ===========================================================================
# 核心函数
# ===========================================================================
def generate_host_rules(skill_root, dry_run=False, force=False):
    """扫描 references/ 生成 docs/rules/index.md。

    Args:
        skill_root: skill 包根目录路径（相对或绝对）。
        dry_run: True 时只预览不写文件。
        force: True 时强制覆盖已有 index.md（默认 strategy='create_missing_only'）。

    Returns:
        dict: {
            'generated': bool,    # 是否生成/写入成功
            'rules_count': int,   # 扫描到的 .md 规则数
            'index_path': str,    # index.md 绝对路径
            'skipped': bool,      # 是否因已存在且未 --force 跳过
        }
    """
    skill_root = os.path.abspath(skill_root)
    if not os.path.isdir(skill_root):
        logger.error('skill_root 不存在: %s', skill_root)
        return {
            'generated': False,
            'rules_count': 0,
            'index_path': '',
            'skipped': False,
        }

    items = _scan_references(skill_root)
    rules_count = len(items)

    target_dir = os.path.join(skill_root, RULES_SYNC_POLICY['target_dir'])
    index_path = os.path.join(target_dir, 'index.md')
    index_exists = os.path.isfile(index_path)

    # 策略判定
    if index_exists and not force:
        logger.info('index.md 已存在且未指定 --force，跳过（strategy=create_missing_only）: %s',
                    index_path)
        return {
            'generated': False,
            'rules_count': rules_count,
            'index_path': index_path,
            'skipped': True,
        }

    if force and not RULES_SYNC_POLICY['allow_force_overwrite']:
        # 策略默认禁 force，但 CLI 显式 --force 时允许通过（仅告警）
        logger.warning('RULES_SYNC_POLICY.allow_force_overwrite=False，但 --force 显式指定，将覆盖: %s',
                       index_path)

    markdown = _build_index_markdown(items, skill_root)

    if dry_run:
        logger.info('DRY-RUN：不写入文件，预览 %d 条规则 → %s', rules_count, index_path)
        return {
            'generated': False,
            'rules_count': rules_count,
            'index_path': index_path,
            'skipped': False,
            'preview': markdown,
        }

    # 写入
    try:
        if target_dir and not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as handle:
            handle.write(markdown)
        logger.info('已生成 %s（%d 条规则）', index_path, rules_count)
        return {
            'generated': True,
            'rules_count': rules_count,
            'index_path': index_path,
            'skipped': False,
        }
    except OSError as exc:
        logger.error('写入 index.md 失败 %s: %s', index_path, exc)
        return {
            'generated': False,
            'rules_count': rules_count,
            'index_path': index_path,
            'skipped': False,
        }


# ===========================================================================
# CLI / main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='pdca-skill host rules 索引生成器（stdlib-only）')
    parser.add_argument('skill_root', nargs='?', default='.',
                        help='skill 包根目录（默认：当前目录）')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览不写文件')
    parser.add_argument('--force', action='store_true',
                        help='强制覆盖已有 index.md（默认 strategy=create_missing_only）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 输出结果到 stdout（日志仍走 stderr）')
    args = parser.parse_args()

    result = generate_host_rules(
        skill_root=args.skill_root,
        dry_run=args.dry_run,
        force=args.force,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('Host Rules 索引生成报告（generate_host_rules.py）')
        print('skill_root: %s' % os.path.abspath(args.skill_root))
        print('-' * 60)
        print('rules_count: %d' % result.get('rules_count', 0))
        print('index_path:  %s' % result.get('index_path', ''))
        print('generated:   %s' % result.get('generated', False))
        print('skipped:     %s' % result.get('skipped', False))
        if args.dry_run and 'preview' in result:
            print('-' * 60)
            print(result['preview'])
        print('-' * 60)

    # 退出码：
    #   - dry-run 永远 0（仅预览，不算失败）
    #   - 正式运行：generated 或 skipped 都 0；写入失败 1
    if args.dry_run:
        return 0
    if result.get('generated') or result.get('skipped'):
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())

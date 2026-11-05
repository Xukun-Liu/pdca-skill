#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
health_report.py — 遥测健康报告（v1.1.0 · B4 / B5）

三条趋势一眼看完，升级是否有成效不再靠感觉：
  1. 技能体量趋势：脚本数 / references 数 / SKILL.md 行数
  2. 记忆增长趋势：memory_rj 按月份条目数
  3. 死链趋势：data_verify 的死链条数（含历史快照）

每次运行把当前快照追加到 `{docs}/check_rj/health_history.jsonl`，趋势取最近 12 次。

用法：
  python scripts/health_report.py --root "<skill 目录>"
  python scripts/health_report.py --root "<skill 目录>" --json
  python scripts/health_report.py --root "<skill 目录>" --no-snapshot

退出码：
  0 正常出报告
  2 环境错误（root 下没有 SKILL.md / 主 docs 解析失败）

技术约束：仅 Python 标准库；死链统计复用 data_verify.check_links。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402
import data_verify  # noqa: E402

HISTORY_LIMIT = 12
MONTH_RE = re.compile(r'^(\d{6})$')
SPARK = '▁▂▃▄▅▆▇█'


def resolve_docs(primary_docs_arg=None):
    try:
        docs = tidy_common.resolve_primary_docs(primary_docs_arg)
    except Exception as exc:  # noqa: BLE001 - 解析链异常统一按环境错误
        print('错误：解析主 docs 失败: %s' % exc, file=sys.stderr)
        return None
    if not docs or not os.path.isdir(docs):
        return None
    return os.path.abspath(docs)


def count_files(base, suffix):
    total = 0
    for cur, dirs, files in os.walk(base):
        dirs.sort()
        total += sum(1 for name in files if name.lower().endswith(suffix))
    return total


def count_lines(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def memory_by_month(docs_root):
    """memory_rj 下按 YYYYMM 文件夹统计条目数。"""
    stats = {}
    base = os.path.join(docs_root, 'memory_rj')
    if not os.path.isdir(base):
        return stats
    for cur, dirs, files in os.walk(base):
        dirs.sort()
        month = None
        for part in os.path.relpath(cur, base).split(os.sep):
            if MONTH_RE.match(part):
                month = part
        if not month:
            continue
        stats[month] = stats.get(month, 0) + sum(
            1 for name in files if name.lower().endswith('.md'))
    return stats


def sparkline(values):
    """ASCII 迷你趋势图（单点也能看）。"""
    if not values:
        return '（无数据）'
    low, high = min(values), max(values)
    if high == low:
        return SPARK[3] * len(values)
    scale = (len(SPARK) - 1) / float(high - low)
    return ''.join(SPARK[int((v - low) * scale)] for v in values)


def read_history(path):
    rows = []
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows[-HISTORY_LIMIT:]


def append_history(path, snapshot):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(snapshot, ensure_ascii=False) + '\n')
    except OSError as exc:
        print('警告：健康快照写入失败: %s' % exc, file=sys.stderr)


def build_snapshot(root):
    scripts_dir = os.path.join(root, 'scripts')
    refs_dir = os.path.join(root, 'references')
    ok_links, checked, dead = data_verify.check_links(root)
    return {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'scripts': count_files(scripts_dir, '.py'),
        'references': count_files(refs_dir, '.md'),
        'skill_lines': count_lines(os.path.join(root, 'SKILL.md')),
        'links_checked': checked,
        'dead_links': len(dead),
        'links_ok': ok_links,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='遥测健康报告：技能体量 / 记忆增长 / 死链趋势')
    parser.add_argument('--root', default='.', help='技能目录（含 SKILL.md）')
    parser.add_argument('--docs', default=None, help='显式指定 docs 目录')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出')
    parser.add_argument('--no-snapshot', action='store_true', help='只读报告，不追加历史快照')
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, 'SKILL.md')):
        print('错误：root 下没有 SKILL.md', file=sys.stderr)
        return 2
    docs_root = resolve_docs(args.docs)
    if not docs_root:
        print('错误：主 docs 解析失败（检查 .primary_docs_rj 或 --docs）', file=sys.stderr)
        return 2

    snapshot = build_snapshot(root)
    history_path = os.path.join(docs_root, 'check_rj', 'health_history.jsonl')
    history = read_history(history_path)
    if not args.no_snapshot:
        append_history(history_path, snapshot)
    history.append(snapshot)  # 趋势图始终带上当前值，--no-snapshot 只是不落盘
    months = memory_by_month(docs_root)

    if args.json:
        print(json.dumps({'snapshot': snapshot, 'months': months,
                          'history': history, 'history_path': history_path},
                         ensure_ascii=False, indent=2))
        return 0

    print('# 健康报告 · %s' % root)
    print('- docs: %s' % docs_root)
    print('- 快照: %s' % snapshot['ts'])

    print('\n## 1. 技能体量趋势')
    print('- 当前: 脚本 %d 个 / references %d 个 / SKILL.md %d 行'
          % (snapshot['scripts'], snapshot['references'], snapshot['skill_lines']))
    if history:
        print('- 脚本数     %s  %s' % (sparkline([h['scripts'] for h in history]),
                                       [h['scripts'] for h in history]))
        print('- references %s  %s' % (sparkline([h['references'] for h in history]),
                                       [h['references'] for h in history]))
        print('- SKILL.md   %s  %s' % (sparkline([h['skill_lines'] for h in history]),
                                       [h['skill_lines'] for h in history]))

    print('\n## 2. 记忆增长趋势')
    if months:
        keys = sorted(months)[-6:]
        print('- 按月份: %s' % ' / '.join('%s=%d' % (k, months[k]) for k in keys))
        print('- 趋势   %s  %s' % (sparkline([months[k] for k in keys]),
                                   [months[k] for k in keys]))
        print('- 合计: %d 条' % sum(months.values()))
    else:
        print('- 暂无记忆条目')

    print('\n## 3. 死链趋势')
    print('- 当前: 相对链接 %d 条 / 死链 %d 条' % (snapshot['links_checked'], snapshot['dead_links']))
    if history:
        print('- 死链数 %s  %s' % (sparkline([h['dead_links'] for h in history]),
                                  [h['dead_links'] for h in history]))
    print('- 快照文件: %s（保留最近 %d 次）' % (history_path, HISTORY_LIMIT))
    print('\n- 结果: PASS（退码 0）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
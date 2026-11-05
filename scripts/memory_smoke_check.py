#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_smoke_check.py — 记忆体检（v1.3.0 新增）

一条命令回答「我以前的记忆还在吗、AI 下次能不能读到」。

检查三项：
  1. 全局记忆 memory_main.md —— 在不在、多大、最后何时更新
  2. 项目记忆 docs_rj/memory_rj —— 有多少条 memory 笔记
  3. 记忆索引 SUMMARY_RJ.md —— 有没有坏链（记忆能否被索引到）

用法：
  python scripts/memory_smoke_check.py
  python scripts/memory_smoke_check.py --root "<skill 目录>"

退出码：
  0 记忆齐全（可读）
  1 存在缺失 / 漂移
  2 环境错误（root 下没有 SKILL.md）

技术约束：仅 Python 标准库；只读不写；日志走 stderr。
"""

import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402
import user_data_path  # noqa: E402

# SUMMARY 里声明的 total_docs 口径（与 post_upgrade_check / tidy_common 对齐）
TOTAL_DOCS_RE = re.compile(r'^total_docs:\s*(\d+)', re.M)


def _fmt_size(num):
    if num < 1024:
        return '%dB' % num
    if num < 1024 * 1024:
        return '%.1fKB' % (num / 1024.0)
    return '%.1fMB' % (num / 1024.0 / 1024.0)


def _fmt_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    except OSError:
        return '未知'


# ---------------------------------------------------------------------------
# 1. 全局记忆
# ---------------------------------------------------------------------------
def check_global_memory(skill_root):
    """全局记忆 memory_main.md：在不在、多大、最后更新。"""
    try:
        path = user_data_path.get_memory_main_path_with_fallback(skill_root)
    except Exception as exc:  # noqa: BLE001 - 定位失败统一按缺失处理
        return 'FAIL', '定位全局记忆路径失败: %s' % exc

    if not os.path.isfile(path):
        return 'FAIL', '全局记忆文件不存在: %s' % path

    size = os.path.getsize(path)
    if size == 0:
        return 'WARN', '全局记忆是空文件（0 字节）: %s' % path

    return 'PASS', '%s · %s · 最后更新 %s' % (path, _fmt_size(size), _fmt_mtime(path))


# ---------------------------------------------------------------------------
# 2. 项目记忆
# ---------------------------------------------------------------------------
def check_primary_memory():
    """项目记忆 docs_rj/memory_rj：多少条 memory 笔记。"""
    try:
        primary = tidy_common.resolve_primary_docs()
    except Exception as exc:  # noqa: BLE001 - 解析异常按未解析处理
        primary = None

    memory_dir = None
    if primary and os.path.isdir(primary):
        memory_dir = os.path.join(primary, 'memory_rj')
    if not memory_dir or not os.path.isdir(memory_dir):
        # 退回外置用户数据目录下的 memory_rj
        try:
            memory_dir = str(user_data_path.get_memory_rj_path())
        except Exception:  # noqa: BLE001
            memory_dir = None

    if not memory_dir or not os.path.isdir(memory_dir):
        return 'FAIL', '项目记忆目录不存在（未解析到主 docs/memory_rj），可能尚未产生任何记忆'

    try:
        entries = list(tidy_common.iter_md_rel_paths(memory_dir))
    except Exception as exc:  # noqa: BLE001
        return 'FAIL', '读取项目记忆失败: %s' % exc

    count = len(entries)
    if count == 0:
        return 'WARN', '%s · 0 条记忆（目录为空）' % memory_dir

    return 'PASS', '%s · %d 条记忆笔记' % (memory_dir, count)


# ---------------------------------------------------------------------------
# 3. 记忆索引
# ---------------------------------------------------------------------------
def check_memory_index():
    """记忆索引 SUMMARY_RJ.md：有无坏链、total_docs 是否对齐。"""
    try:
        primary = tidy_common.resolve_primary_docs()
    except Exception:  # noqa: BLE001
        primary = None

    if not primary or not os.path.isdir(primary):
        return 'FAIL', '未解析到主 docs，无法检查记忆索引'

    summary_path = os.path.join(primary, 'SUMMARY_RJ.md')
    if not os.path.isfile(summary_path):
        return 'FAIL', 'SUMMARY_RJ.md 不存在: %s' % summary_path

    missing_count, missing_list = tidy_common.drift_check(summary_path)

    declared = None
    try:
        with open(summary_path, 'r', encoding='utf-8-sig') as handle:
            match = TOTAL_DOCS_RE.search(handle.read())
        if match:
            declared = int(match.group(1))
    except (OSError, UnicodeDecodeError):
        pass

    actual = 0
    for subdir in ('memory_rj', 'spec_rj', 'task_rj', 'handoff_rj', 'archive_rj'):
        sub_path = os.path.join(primary, subdir)
        if os.path.isdir(sub_path):
            actual += len(list(tidy_common.iter_md_rel_paths(sub_path)))

    problems = []
    if missing_count:
        problems.append('坏链 %d 条' % missing_count)
    if declared is None:
        problems.append('缺 total_docs 声明')
    elif declared != actual:
        problems.append('total_docs=%d 与实际 %d 份不符' % (declared, actual))

    if problems:
        return 'FAIL', '；'.join(problems) + (' · ' + '; '.join(missing_list[:5]) if missing_count else '')

    return 'PASS', '索引 0 坏链，total_docs=%d 与实际一致（记忆可被索引到）' % declared


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
ICON = {'PASS': '[OK ]', 'WARN': '[WARN]', 'FAIL': '[缺失]'}

HINTS = {
    '全局记忆': [
        '跑 python scripts/memory_shadow_write.py --help 看写记忆入口；手动补全局记忆到 ~/.pdca-skill/data/memory/memory_main.md',
    ],
    '项目记忆': [
        '在主项目根执行 python scripts/generate_docs.py --declare-primary "<项目根>/docs_rj"',
    ],
    '记忆索引': [
        'python -c "import tidy_common; tidy_common.refresh_summary(r\'<主 docs>\')"',
    ],
}


def render(checks):
    lines = ['# memory_smoke_check · 记忆体检']
    for idx, (name, status, detail) in enumerate(checks, 1):
        lines.append('%s %d. %s —— %s' % (ICON[status], idx, name, detail))
    fails = [c for c in checks if c[1] == 'FAIL']
    warns = [c for c in checks if c[1] == 'WARN']
    lines.append('')
    lines.append('## 结论')
    if fails:
        lines.append('结局：记忆有缺失 —— %d 项 FAIL，AI 下次可能读不全' % len(fails))
        lines.append('')
        lines.append('## 建议动作')
        for name, status, _ in fails:
            for hint in HINTS.get(name, []):
                lines.append('- [%s] %s' % (name, hint))
    else:
        tail = '（%d 项 WARN，注意查看）' % len(warns) if warns else '，可放心干活'
        lines.append('结局：记忆读到了%s' % tail)
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='记忆体检：全局记忆 / 项目记忆 / 记忆索引')
    parser.add_argument('--root', default=None,
                        help='技能目录（含 SKILL.md），默认取本脚本所在目录的父目录')
    args = parser.parse_args(argv)

    skill_root = os.path.abspath(args.root) if args.root else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isfile(os.path.join(skill_root, 'SKILL.md')):
        sys.stderr.write('错误：%s 下没有 SKILL.md，无法体检\n' % skill_root)
        return 2

    checks = [
        ('全局记忆',) + check_global_memory(skill_root),
        ('项目记忆',) + check_primary_memory(),
        ('记忆索引',) + check_memory_index(),
    ]
    print(render(checks))
    return 0 if all(status != 'FAIL' for _, status, _ in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
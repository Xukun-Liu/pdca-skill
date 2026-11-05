#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_memory.py — 副 agent 记忆追加（v1.1.0 · B5 / 阶段5）

把一次调研结论追加进 agent 自己的 memory/memory_agent.md，按时间戳分段，只追加不改写。

用法：
  python scripts/agent_factory/agent_memory.py --path "$env:TEMP\ag\demo" --content "结论：..."
  python scripts/agent_factory/agent_memory.py --path "$env:TEMP\ag\demo" --dry-run --content "..."
  python scripts/agent_factory/agent_memory.py --path "$env:TEMP\ag\demo" --show
  Get-Content -Raw note.md | python scripts/agent_factory/agent_memory.py --path ./demo   # 省略 --content 读 stdin

退出码：
  0 追加成功（含 dry-run / show）
  1 agent 目录非法 / 无内容可写
  2 环境错误（文件不可写）

技术约束：仅 Python 标准库；编码统一 UTF-8（读 stdin 时按 UTF-8 重配，防 Windows 默认 GBK）。
"""

import argparse
import datetime
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

MEMORY_REL = os.path.join('memory', 'memory_agent.md')


def read_stdin():
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    return sys.stdin.read()


def normalize(content):
    text = content.replace('\r\n', '\n').replace('\r', '\n').strip('\n')
    lines = [line.rstrip() for line in text.split('\n')]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def build_block(content, stamp):
    body = '\n'.join('- %s' % line if line else '' for line in content.split('\n'))
    return '\n## %s\n\n%s\n' % (stamp, body)


def main():
    parser = argparse.ArgumentParser(description='追加副 agent 记忆条目')
    parser.add_argument('--path', required=True, help='agent 目录（内含 memory/memory_agent.md）')
    parser.add_argument('--content', default=None, help='要追加的内容；省略则读 stdin')
    parser.add_argument('--dry-run', action='store_true', help='只打印将追加的段落，不落盘')
    parser.add_argument('--show', action='store_true', help='只显示现有记忆，不写入')
    args = parser.parse_args()

    agent_dir = os.path.abspath(args.path)
    if not os.path.isdir(agent_dir):
        print('错误：目录不存在：%s' % agent_dir, file=sys.stderr)
        return 2
    memory_file = os.path.join(agent_dir, MEMORY_REL)
    if not os.path.isfile(memory_file):
        print('错误：缺少 %s（先跑 new_agent.py）' % memory_file, file=sys.stderr)
        return 2

    try:
        with open(memory_file, 'r', encoding='utf-8-sig') as fh:
            existing = fh.read()
    except OSError as exc:
        print('错误：读取记忆失败：%s' % exc, file=sys.stderr)
        return 2

    if args.show:
        print(existing.rstrip('\n') if existing.strip() else '(空)')
        return 0

    raw = args.content if args.content is not None else read_stdin()
    content = normalize(raw or '')
    if not content:
        print('错误：没有可写入的内容（--content 为空且 stdin 无输入）', file=sys.stderr)
        return 2

    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    block = build_block(content, stamp)

    if args.dry_run:
        print('[DRY-RUN] 将追加到 %s：' % memory_file)
        print(block)
        return 0

    try:
        prefix = '' if existing.endswith('\n') or not existing else '\n'
        with open(memory_file, 'a', encoding='utf-8', newline='\n') as fh:
            fh.write(prefix + block)
    except OSError as exc:
        print('错误：写入记忆失败：%s' % exc, file=sys.stderr)
        return 2

    print('[OK] 已追加 %d 行到 %s' % (len(content.split('\n')), memory_file))
    return 0


if __name__ == '__main__':
    sys.exit(main())
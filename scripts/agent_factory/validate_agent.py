#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_agent.py — 副 agent 体检（v1.1.0 · B5 / 阶段5）

校验一个 agent 目录（或一整棵树）是否满足可被主 agent 调度的最小条件：
  1. agent.json 存在且可解析
  2. 必填字段齐全：name / role / description / knowledge / triggers / output_format / version / created_at
  3. name 匹配 ^[a-z0-9_]+$
  4. AGENT.md 存在，首行（去 BOM 后）为 `[subagent: <name>]`
  5. memory/memory_agent.md 存在
  6. knowledge 路径可落地（跳过 http(s) 与占位符；依次按 agent 目录 → skill 根 → 当前目录解析）

用法：
  python scripts/agent_factory/validate_agent.py --path "$env:TEMP\ag\demo"
  python scripts/agent_factory/validate_agent.py --root "$env:TEMP\ag"

退出码：
  0 全部通过（WARN 不计失败）
  1 至少一项 FAIL
  2 环境错误（路径不存在 / 一个 agent.json 都没找到）

技术约束：仅 Python 标准库。
"""

import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

NAME_RE = re.compile(r'^[a-z0-9_]+$')
REQUIRED_FIELDS = ('name', 'role', 'description', 'knowledge', 'triggers',
                   'output_format', 'version', 'created_at')
LIST_FIELDS = ('knowledge', 'triggers', 'output_format')
SKIP_PREFIX = ('http://', 'https://', 'mailto:')
PLACEHOLDER_CHARS = ('{', '}', '…', '<', '>')
SKIP_DIRS = ('.git', '__pycache__', 'node_modules', '.venv', 'venv')


def resolve_knowledge(entry, agent_dir):
    candidate_roots = (agent_dir, SKILL_ROOT, os.getcwd())
    for root in candidate_roots:
        if os.path.exists(os.path.join(root, entry)):
            return True
    return False


def check_agent(agent_dir):
    """返回 (fails, warns) 两个字符串列表。"""
    fails = []
    warns = []
    json_path = os.path.join(agent_dir, 'agent.json')
    if not os.path.isfile(json_path):
        return ['缺少 agent.json'], warns
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as fh:
            agent = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return ['agent.json 解析失败：%s' % exc], warns
    if not isinstance(agent, dict):
        return ['agent.json 顶层必须是对象'], warns

    missing = [f for f in REQUIRED_FIELDS if not agent.get(f)]
    if missing:
        fails.append('缺必填字段：%s' % ', '.join(missing))

    name = str(agent.get('name') or '')
    if name and not NAME_RE.match(name):
        fails.append('name 不合法（只允许 [a-z0-9_]+）：%r' % name)

    for field in LIST_FIELDS:
        value = agent.get(field)
        if value is not None and not isinstance(value, list):
            fails.append('%s 必须是数组' % field)
    if isinstance(agent.get('triggers'), list) and not agent.get('triggers'):
        fails.append('triggers 不能为空（主 agent 靠它路由）')

    dir_name = os.path.basename(os.path.normpath(agent_dir))
    if name and dir_name != name:
        warns.append('目录名 %r 与 name %r 不一致（不致命，但易混淆）' % (dir_name, name))

    agent_md = os.path.join(agent_dir, 'AGENT.md')
    if not os.path.isfile(agent_md):
        fails.append('缺少 AGENT.md')
    else:
        try:
            with open(agent_md, 'r', encoding='utf-8-sig') as fh:
                first_line = ''
                for line in fh:
                    if line.strip():
                        first_line = line.strip()
                        break
        except OSError as exc:
            fails.append('AGENT.md 读取失败：%s' % exc)
            first_line = ''
        expected = '[subagent: %s]' % name
        if first_line and first_line != expected:
            fails.append('AGENT.md 首行应为 %r，实际 %r' % (expected, first_line))

    memory_file = os.path.join(agent_dir, 'memory', 'memory_agent.md')
    if not os.path.isfile(memory_file):
        fails.append('缺少 memory/memory_agent.md')

    for entry in agent.get('knowledge') or []:
        if not isinstance(entry, str):
            fails.append('knowledge 项必须是字符串：%r' % (entry,))
            continue
        entry = entry.strip()
        if not entry or entry.startswith(SKIP_PREFIX) or any(c in entry for c in PLACEHOLDER_CHARS):
            continue
        if not resolve_knowledge(entry, agent_dir):
            fails.append('knowledge 路径不存在：%s' % entry)

    return fails, warns


def find_agent_dirs(root):
    hits = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if 'agent.json' in files:
            hits.append(current)
    return sorted(hits)


def main():
    parser = argparse.ArgumentParser(description='校验副 agent 目录结构')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--path', help='单个 agent 目录')
    group.add_argument('--root', help='批量扫描根目录（含 agent.json 的目录都校验）')
    args = parser.parse_args()

    if args.path:
        if not os.path.isdir(args.path):
            print('错误：目录不存在：%s' % args.path, file=sys.stderr)
            return 2
        targets = [os.path.abspath(args.path)]
    else:
        if not os.path.isdir(args.root):
            print('错误：目录不存在：%s' % args.root, file=sys.stderr)
            return 2
        targets = find_agent_dirs(os.path.abspath(args.root))
        if not targets:
            print('错误：%s 下没有找到任何 agent.json' % args.root, file=sys.stderr)
            return 2

    total_fail = 0
    for agent_dir in targets:
        fails, warns = check_agent(agent_dir)
        label = os.path.basename(os.path.normpath(agent_dir))
        if fails:
            total_fail += len(fails)
            print('[FAIL] %s（%s）' % (label, agent_dir))
            for item in fails:
                print('       - %s' % item)
        else:
            print('[OK] %s（%s）' % (label, agent_dir))
        for item in warns:
            print('       [WARN] %s' % item)

    print('汇总：%d 个 agent，%d 项失败' % (len(targets), total_fail))
    return 0 if total_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
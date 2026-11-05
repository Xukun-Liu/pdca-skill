#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
register_agent.py — 把副 agent 登记进注册表（v1.1.0 · B5 / 阶段5）

注册表默认落在用户数据目录（不污染 skill 包）：
  ~/.pdca-skill/data/agents_registry.json
结构对齐 agents_rj/subagent_config_rj.json：{version, last_updated, defaults, agents[]}。

行为：按 name 幂等合并——同名覆盖、异名追加，不删除其他条目。

用法：
  python scripts/agent_factory/register_agent.py --path "$env:TEMP\ag\demo"
  python scripts/agent_factory/register_agent.py --path ./demo --dry-run
  python scripts/agent_factory/register_agent.py --path ./demo --config .\agents_registry.json

退出码：
  0 登记成功（含 dry-run）
  1 agent 不合法（缺 agent.json / 缺必填字段 / name 非法）
  2 环境错误（注册表不可读写 / 用户数据目录不可用）

技术约束：仅 Python 标准库；注册表路径经 scripts/user_data_path.py 解析。
"""

import argparse
import datetime
import json
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import user_data_path  # noqa: E402

NAME_RE = re.compile(r'^[a-z0-9_]+$')
REGISTRY_NAME = 'agents_registry.json'
REQUIRED_FIELDS = ('name', 'role', 'description')
ENTRY_FIELDS = ('name', 'role', 'role_identity', 'description',
                'knowledge', 'triggers', 'output_format')
DEFAULT_REGISTRY = {
    'version': '1.0.0',
    'last_updated': '',
    'defaults': {
        'subagent_type': 'general_purpose_task',
        'permission': 'read_only',
        'parallel_capable': True,
    },
    'agents': [],
}


def load_agent(agent_dir):
    """读取并做最小校验；不合法返回 (None, 原因)。"""
    path = os.path.join(agent_dir, 'agent.json')
    if not os.path.isfile(path):
        return None, '缺少 agent.json（先跑 new_agent.py）'
    try:
        with open(path, 'r', encoding='utf-8-sig') as fh:
            agent = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return None, 'agent.json 读取/解析失败：%s' % exc
    if not isinstance(agent, dict):
        return None, 'agent.json 顶层必须是对象'
    missing = [f for f in REQUIRED_FIELDS if not agent.get(f)]
    if missing:
        return None, '缺必填字段：%s' % ', '.join(missing)
    if not NAME_RE.match(str(agent['name'])):
        return None, 'name 只允许 [a-z0-9_]+，收到 %r' % agent['name']
    return agent, None


def build_entry(agent):
    entry = {}
    for key in ENTRY_FIELDS:
        if key in agent:
            entry[key] = agent[key]
    for key in ('knowledge', 'triggers', 'output_format'):
        entry.setdefault(key, [])
    return entry


def read_registry(path):
    if not os.path.isfile(path):
        return json.loads(json.dumps(DEFAULT_REGISTRY))
    try:
        with open(path, 'r', encoding='utf-8-sig') as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('注册表读取/解析失败：%s' % exc)
    if not isinstance(data, dict):
        raise ValueError('注册表顶层必须是对象')
    data.setdefault('version', '1.0.0')
    data.setdefault('defaults', dict(DEFAULT_REGISTRY['defaults']))
    data.setdefault('agents', [])
    return data


def upsert(data, entry):
    """按 name 覆盖或追加，返回 (动作, 总条数)。"""
    agents = data['agents']
    for idx, existing in enumerate(agents):
        if isinstance(existing, dict) and existing.get('name') == entry['name']:
            agents[idx] = entry
            return 'updated', len(agents)
    agents.append(entry)
    return 'added', len(agents)


def main():
    parser = argparse.ArgumentParser(description='把副 agent 登记进注册表（默认写用户数据目录）')
    parser.add_argument('--path', required=True, help='agent 目录（内含 agent.json）')
    parser.add_argument('--config', default=None, help='注册表路径，默认 ~/.pdca-skill/data/agents_registry.json')
    parser.add_argument('--dry-run', action='store_true', help='只预览合并结果，不落盘')
    args = parser.parse_args()

    agent_dir = os.path.abspath(args.path)
    if not os.path.isdir(agent_dir):
        print('错误：agent 目录不存在：%s' % agent_dir, file=sys.stderr)
        return 2

    agent, reason = load_agent(agent_dir)
    if agent is None:
        print('错误：%s' % reason, file=sys.stderr)
        return 1

    if args.config:
        registry_path = os.path.abspath(args.config)
    else:
        try:
            registry_path = str(user_data_path.get_user_data_dir() / REGISTRY_NAME)
        except (PermissionError, OSError) as exc:
            print('错误：用户数据目录不可用：%s' % exc, file=sys.stderr)
            return 2

    try:
        data = read_registry(registry_path)
    except ValueError as exc:
        print('错误：%s' % exc, file=sys.stderr)
        return 2

    action, total = upsert(data, build_entry(agent))
    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    if args.dry_run:
        print('[DRY-RUN] 将%s %s → %s（共 %d 个 agent）'
              % ('更新' if action == 'updated' else '新增', agent['name'], registry_path, total))
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    try:
        parent = os.path.dirname(registry_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(registry_path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    except OSError as exc:
        print('错误：写入注册表失败：%s' % exc, file=sys.stderr)
        return 2

    print('[OK] %s %s → %s（共 %d 个 agent）'
          % ('已更新' if action == 'updated' else '已登记', agent['name'], registry_path, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
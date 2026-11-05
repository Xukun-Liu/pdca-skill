#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_agent.py — 副 agent 脚手架（v1.1.0 · B5 / 阶段5）

一条命令生成一个副 agent 的三件套，避免每次手抄 JSON 字段：
  <out>/<name>/agent.json              —— 机器读（schema 对齐 agents_rj/subagent_config_rj.json）
  <out>/<name>/AGENT.md                —— 人读，首行 `[subagent: <name>]` 声明身份
  <out>/<name>/memory/memory_agent.md  —— 该 agent 的长期记忆（由 agent_memory.py 追加）

用法：
  python scripts/agent_factory/new_agent.py --name demo --out "$env:TEMP\ag"
  python scripts/agent_factory/new_agent.py --name demo --out . --triggers 代码审查,体检 --force

退出码：
  0 生成成功
  1 参数非法 / 目标已存在且未加 --force
  2 环境错误（目录不可写）

技术约束：仅 Python 标准库；不读写用户数据目录（registry 由 register_agent.py 负责）。
"""

import argparse
import datetime
import json
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

NAME_RE = re.compile(r'^[a-z0-9_]+$')
DEFAULT_KNOWLEDGE = ('references/common/agent_factory/agent_factory.md',)
DEFAULT_OUTPUT_FORMAT = ('结论', '依据', '下一步')

AGENT_MD_TEMPLATE = """[subagent: {name}]
# {name} agent

> 由 `scripts/agent_factory/new_agent.py` 生成。改字段请同步 `agent.json`；两边冲突时以 `agent.json` 为准。

## 角色
{role_identity}

## 知识库（只读调研时按序加载）
{knowledge_list}

## 触发词
{trigger_list}

## 输出格式
{output_list}

## 权限
只读调研：不改业务代码 / 配置 / 已交付物 / memory。任何写操作回到主 agent 过 HARD-GATE。
"""

MEMORY_TEMPLATE = """# {name} agent memory

> 由 `scripts/agent_factory/agent_memory.py` 追加；手改请保持 `## YYYY-MM-DD HH:MM` 分段。
"""


def build_agent(name, role, description, triggers, knowledge):
    now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return {
        'name': name,
        'role': role,
        'role_identity': (
            '你是 %s 副 agent，只做只读调研与结论汇总：'
            '按 knowledge 顺序加载参考模块，输出结论 + 依据 + 下一步，不写业务文件。' % name
        ),
        'description': description,
        'knowledge': list(knowledge),
        'triggers': list(triggers),
        'output_format': list(DEFAULT_OUTPUT_FORMAT),
        'version': '1.0.0',
        'created_at': now,
    }


def render_list(items, ordered=True):
    if ordered:
        return '\n'.join('%d. %s' % (i + 1, item) for i, item in enumerate(items))
    return '\n'.join('- %s' % item for item in items)


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def split_csv(value, default):
    if not value:
        return list(default)
    items = [part.strip() for part in value.split(',') if part.strip()]
    return items or list(default)


def main():
    parser = argparse.ArgumentParser(description='生成副 agent 目录骨架（agent.json + AGENT.md + memory）')
    parser.add_argument('--name', required=True, help='agent 名（小写字母/数字/下划线）')
    parser.add_argument('--out', default='.', help='输出根目录，最终落在 <out>/<name>/')
    parser.add_argument('--role', default=None, help='角色名，默认 <name>_agent_pdca')
    parser.add_argument('--description', default=None, help='一句话描述')
    parser.add_argument('--triggers', default=None, help='触发词，逗号分隔')
    parser.add_argument('--knowledge', default=None, help='知识库路径，逗号分隔（相对 skill 根）')
    parser.add_argument('--force', action='store_true', help='目标已存在时覆盖三个文件')
    args = parser.parse_args()

    name = args.name.strip()
    if not NAME_RE.match(name):
        print('错误：--name 只允许 [a-z0-9_]+，收到 %r' % args.name, file=sys.stderr)
        return 1

    role = args.role or ('%s_agent_pdca' % name)
    description = args.description or ('%s 领域的只读调研副 agent' % name)
    triggers = split_csv(args.triggers, (name,))
    knowledge = split_csv(args.knowledge, DEFAULT_KNOWLEDGE)

    target = os.path.abspath(os.path.join(args.out, name))
    existed = os.path.isdir(target)
    if existed and not args.force:
        print('错误：%s 已存在。要覆盖请加 --force' % target, file=sys.stderr)
        return 1

    agent = build_agent(name, role, description, triggers, knowledge)
    agent_md = AGENT_MD_TEMPLATE.format(
        name=name,
        role_identity=agent['role_identity'],
        knowledge_list=render_list(agent['knowledge']),
        trigger_list=render_list(agent['triggers'], ordered=False),
        output_list=render_list(agent['output_format']),
    )

    try:
        write_text(os.path.join(target, 'agent.json'),
                   json.dumps(agent, ensure_ascii=False, indent=2) + '\n')
        write_text(os.path.join(target, 'AGENT.md'), agent_md)
        write_text(os.path.join(target, 'memory', 'memory_agent.md'),
                   MEMORY_TEMPLATE.format(name=name))
    except OSError as exc:
        print('错误：写入失败 %s' % exc, file=sys.stderr)
        return 2

    print('[OK] agent 已生成：%s' % target)
    print('     agent.json / AGENT.md / memory/memory_agent.md')
    print('下一步：python scripts/agent_factory/validate_agent.py --path "%s"' % target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
devlog_sync.py — riji-skill 开发日志同步工具

作用
----
把一条开发日志（devlog entry）追加到 docs/devlog.md（默认路径，可覆盖）。
对齐业界 devlog 同步实践：把零散的开发记录沉淀成
可追溯的 daily.md 风格日志，便于事后复盘 / 交接 / learn 子流程读取。

核心函数：
  - get_actor(cwd=None) -> str：取 git user.name，失败降级 'unknown'
  - append_devlog(devlog_path, entry) -> dict：追加模板化条目，返回 written/path

借鉴来源: 业界 devlog 同步实践
Traceability: SKILL.md §0 流程优先, references/common/pa/working_memory_rules.md RAM/Disk 心智模型
设计来源: SKILL.md §1 启动检查 / §3 文档体系, assets/daily_log_template.md

技术约束
--------
* 纯 Python 标准库（os / sys / json / argparse / logging / datetime / subprocess）。
* 零新增第三方依赖。
* 不修改 scripts/ 目录外文件（除非用户显式传 --output 指向外部路径）。

运行
----
  python scripts/devlog_sync.py --title "test entry" --dry-run
  python scripts/devlog_sync.py --title "实现 T19" --goal "..." --action "..." \\
      --result "..." --stage do --output docs/devlog.md
"""

import os
import sys
import json
import argparse
import logging
import subprocess
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ===========================================================================
# 常量
# ===========================================================================
DEFAULT_DEVLOG_PATH = 'docs/devlog.md'

# PDCA 四阶段合法值（对应 SKILL.md §0 PDCA 4 环循环）
PDCA_STAGES = ('plan', 'do', 'check', 'act')


# ===========================================================================
# 辅助函数
# ===========================================================================
def get_actor(cwd=None):
    """获取当前 git 仓库的 user.name，作为 devlog 条目的执行者。

    用 subprocess 跑 `git config user.name`，任何失败（git 未安装 / 不在 git
    仓库 / user.name 未配置）一律降级返回 'unknown'，不抛异常。

    Args:
        cwd: 可选的工作目录；None 时使用当前进程的 cwd。

    Returns:
        str: git user.name（去掉首尾空白）或 'unknown'。
    """
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug('git config user.name 返回非零: %s', result.stderr.strip())
            return 'unknown'
        name = result.stdout.strip()
        if not name:
            return 'unknown'
        return name
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug('git config user.name 调用失败，降级 unknown: %s', exc)
        return 'unknown'


def _format_section(heading, body):
    """格式化一个段落（### heading + body），body 为空则返回空串。"""
    if not body:
        return ''
    return '### %s\n\n%s\n\n' % (heading, body)


def _format_entry(entry):
    """把 entry dict 渲染成 markdown 字符串。

    模板对齐业界 daily.md 格式：二级标题 + 元信息块 + 多个段落。
    空字段省略对应段落，避免空行污染。

    Args:
        entry: dict，含字段 title/goal/action/result/actor/date/time/files/
            stage/conclusion/next/reflection。

    Returns:
        str: 渲染后的 markdown 文本（不含文件头）。
    """
    title = entry.get('title', '').strip() or '(untitled)'
    actor = entry.get('actor', '').strip() or 'unknown'
    date = entry.get('date', '').strip() or ''
    time = entry.get('time', '').strip() or ''
    stage = entry.get('stage', '').strip() or ''
    files = entry.get('files', '').strip() or ''

    lines = []
    lines.append('## %s' % title)
    lines.append('')
    # 元信息块（非空字段才出现）
    meta_pairs = []
    if actor:
        meta_pairs.append('**Actor**: %s' % actor)
    if date and time:
        meta_pairs.append('**Date/Time**: %s %s' % (date, time))
    elif date:
        meta_pairs.append('**Date**: %s' % date)
    if stage:
        meta_pairs.append('**Stage**: %s' % stage)
    if files:
        meta_pairs.append('**Files**: %s' % files)
    if meta_pairs:
        lines.append('- ' + '\n- '.join(meta_pairs))
        lines.append('')

    # 段落（空字段省略）
    body = ''
    body += _format_section('Goal', entry.get('goal', '').strip())
    body += _format_section('Action', entry.get('action', '').strip())
    body += _format_section('Result', entry.get('result', '').strip())
    body += _format_section('Conclusion', entry.get('conclusion', '').strip())
    body += _format_section('Next', entry.get('next', '').strip())
    body += _format_section('Reflection', entry.get('reflection', '').strip())
    lines.append(body.rstrip())
    lines.append('')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)


def append_devlog(devlog_path, entry):
    """把 entry 渲染后追加到 devlog_path（不存在则创建，含文件头）。

    Args:
        devlog_path: devlog 文件路径（相对或绝对）。默认调用方传 docs/devlog.md。
        entry: dict，含字段同 _format_entry。

    Returns:
        dict: {'written': bool, 'path': str}
            written=True 表示已写入；False 表示 dry-run 或写入失败（同时 logger.error）。
    """
    devlog_path = os.path.abspath(devlog_path)
    rendered = _format_entry(entry)

    # 文件不存在则先创建（含文件头）
    file_existed = os.path.isfile(devlog_path)
    try:
        # 父目录不存在则创建
        parent = os.path.dirname(devlog_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

        with open(devlog_path, 'a', encoding='utf-8') as handle:
            if not file_existed:
                handle.write('# Devlog\n\n')
                handle.write('> 由 scripts/devlog_sync.py 维护。每条记录追加到末尾。\n\n')
            handle.write(rendered)
            if not rendered.endswith('\n'):
                handle.write('\n')
        return {'written': True, 'path': devlog_path}
    except OSError as exc:
        logger.error('写入 devlog 失败 %s: %s', devlog_path, exc)
        return {'written': False, 'path': devlog_path}


# ===========================================================================
# CLI / main
# ===========================================================================
def _build_entry_from_args(args):
    """从 argparse Namespace 构造 entry dict。"""
    files_str = ''
    if args.files:
        # 逗号分隔转成 markdown 列表友好形式（保留原分隔符也行，这里用 ', '）
        files_str = ', '.join([f.strip() for f in args.files.split(',') if f.strip()])
    return {
        'title': args.title or '',
        'goal': args.goal or '',
        'action': args.action or '',
        'result': args.result or '',
        'actor': args.actor or '',
        'date': args.date or '',
        'time': args.time or '',
        'files': files_str,
        'stage': (args.stage or '').lower(),
        'conclusion': args.conclusion or '',
        'next': args.next or '',
        'reflection': args.reflection or '',
    }


def main():
    parser = argparse.ArgumentParser(
        description='riji-skill 开发日志同步工具（stdlib-only）')
    parser.add_argument('--title', required=True,
                        help='日志标题（必填）')
    parser.add_argument('--goal', default=None,
                        help='目标')
    parser.add_argument('--action', default=None,
                        help='动作')
    parser.add_argument('--result', default=None,
                        help='结果')
    parser.add_argument('--actor', default=None,
                        help='执行者（默认：git user.name）')
    parser.add_argument('--date', default=None,
                        help='日期 YYYY-MM-DD（默认：今天）')
    parser.add_argument('--time', default=None,
                        help='时间 HH:MM（默认：当前）')
    parser.add_argument('--files', default=None,
                        help='涉及文件，逗号分隔')
    parser.add_argument('--stage', default=None,
                        help='PDCA 阶段：plan/do/check/act')
    parser.add_argument('--conclusion', default=None,
                        help='结论')
    parser.add_argument('--next', default=None,
                        help='下一步')
    parser.add_argument('--reflection', default=None,
                        help='反思')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览不写文件')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 输出结果到 stdout（日志仍走 stderr）')
    parser.add_argument('--output', default=DEFAULT_DEVLOG_PATH,
                        help='devlog 文件路径（默认：%(default)s）')
    args = parser.parse_args()

    # 校验 stage
    if args.stage and args.stage.lower() not in PDCA_STAGES:
        logger.error('--stage 必须是 %s 之一，得到：%s', '/'.join(PDCA_STAGES), args.stage)
        return 2

    # 默认 actor / date / time
    actor = args.actor or get_actor()
    now = datetime.now()
    date = args.date or now.strftime('%Y-%m-%d')
    time = args.time or now.strftime('%H:%M')

    # 覆盖 args 中的字段（便于 _build_entry_from_args 统一取值）
    args.actor = actor
    args.date = date
    args.time = time

    entry = _build_entry_from_args(args)

    if args.dry_run:
        rendered = _format_entry(entry)
        payload = {
            'written': False,
            'path': os.path.abspath(args.output),
            'dry_run': True,
            'entry': entry,
            'preview': rendered,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print('=== DRY-RUN devlog entry（不写入文件）===')
            print('target: %s' % payload['path'])
            print('-' * 60)
            print(rendered)
        return 0

    result = append_devlog(args.output, entry)
    if args.json:
        payload = dict(result)
        payload['entry'] = entry
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if result['written']:
            print('已追加 devlog 条目到: %s' % result['path'])
        else:
            print('写入失败: %s' % result['path'])
    return 0 if result['written'] else 1


if __name__ == '__main__':
    sys.exit(main())

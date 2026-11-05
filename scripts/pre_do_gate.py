#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pre_do_gate.py — /do 文档门禁（v1.3.0）

进入 /do 之前强制核对「本任务是否已有文档」，把"没写文档就动手"从自觉约束
变成程序闸门。

三档模式：
  默认（复杂任务）   spec + task 都必须在，缺一个就拦
  --lite（简单任务） 只要 spec（lite spec：目标/范围/验收 各一行即可）
  --exempt（豁免）   文章/文案类等不产 spec 的任务，直接放行并打印豁免原因

用法：
  python scripts/pre_do_gate.py --task my_task
  python scripts/pre_do_gate.py --task my_task --lite
  python scripts/pre_do_gate.py --task my_task --exempt --reason "写公众号文章"
  python scripts/pre_do_gate.py --task my_task --docs-dir ./docs_rj --json

退出码：
  0 通过
  1 缺 spec（必须先回 /plan，或补 lite spec）
  2 缺 task（spec 已有，缺执行清单）
  3 参数或环境错误（任务名非法 / 找不到 docs_rj）

技术约束：仅 Python 标准库；不写任何文件，纯只读检查。
"""

import argparse
import json
import os
import re
import sys

TASK_NAME_RE = re.compile(r'^[a-z0-9_]+$')

SPEC_DIR = 'spec_rj'
TASK_DIR = 'task_rj'


def resolve_docs(docs_dir_arg):
    """解析主 docs 目录：显式参数 > 当前目录 ./docs_rj；都不存在返回 None。"""
    if docs_dir_arg:
        candidate = os.path.abspath(docs_dir_arg)
        return candidate if os.path.isdir(candidate) else None
    convention = os.path.join(os.getcwd(), 'docs_rj')
    return convention if os.path.isdir(convention) else None


def _name_matches(filename, task, kind):
    """判断文件名是否属于 {task} 且是 {kind} 类文档。

    兼容两种真实命名：
      1. 标准：{task}_spec_YYYYMMDD_HHMM.md
      2. 带前缀：20261105_1026_pdca-skill_spec_{task}.md
    做法：按 `_` 切词，要求 task 作为连续词序列出现，且 kind 也在词序列里。
    """
    if not filename.lower().endswith('.md'):
        return False
    tokens = filename[:-3].lower().split('_')
    wanted = task.lower().split('_')
    if kind.lower() not in tokens:
        return False
    span = len(wanted)
    return any(tokens[i:i + span] == wanted for i in range(len(tokens) - span + 1))


def find_artifacts(docs, sub, task, kind):
    """递归查找 {task} 的 {kind} 文档（兼容扁平与分层两种目录结构）。"""
    root = os.path.join(docs, sub)
    if not os.path.isdir(root):
        return []
    hits = []
    for current, _dirs, files in os.walk(root):
        for name in files:
            if _name_matches(name, task, kind):
                hits.append(os.path.abspath(os.path.join(current, name)))
    return sorted(hits)


def spec_is_usable(paths, lite):
    """lite 模式下要求 spec 非空（至少 3 行有效内容），防止占位空文件放行。"""
    if not lite:
        return True
    for path in paths:
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                lines = [line.strip() for line in handle if line.strip()]
        except (OSError, UnicodeDecodeError):
            continue
        if len(lines) >= 3:
            return True
    return False


def build_result(task, docs, lite, exempt, reason, spec_paths, task_paths):
    """汇总检查结论，返回 (payload, exit_code)。"""
    payload = {
        'task': task,
        'docs_dir': docs,
        'mode': 'exempt' if exempt else ('lite' if lite else 'full'),
        'spec': spec_paths,
        'task_doc': task_paths,
        'passed': False,
        'reason': '',
    }

    if exempt:
        payload['passed'] = True
        payload['reason'] = '豁免：%s' % (reason or '文章/文案类任务，不产 spec')
        return payload, 0

    if not spec_paths:
        payload['reason'] = '缺 spec：docs_rj/spec_rj/ 下没有 %s_spec_*.md' % task
        return payload, 1

    if lite and not spec_is_usable(spec_paths, lite=True):
        payload['reason'] = 'lite spec 内容不足 3 行（目标/范围/验收）'
        return payload, 1

    if not lite and not task_paths:
        payload['reason'] = '缺 task：docs_rj/task_rj/ 下没有 %s_task_*.md' % task
        return payload, 2

    payload['passed'] = True
    payload['reason'] = '通过'
    return payload, 0


def print_human(payload, code):
    print('## pre_do_gate %s' % ('通过' if code == 0 else '拦截'))
    print('- task    : %s' % payload['task'])
    print('- 主 docs : %s' % payload['docs_dir'])
    print('- 模式    : %s' % payload['mode'])
    print('- spec    : %s' % (payload['spec'][0] if payload['spec'] else '缺失'))
    print('- task    : %s' % (payload['task_doc'][0] if payload['task_doc'] else '缺失'))
    print('- 结论    : %s' % payload['reason'])

    if code == 1:
        print('\n下一步（二选一）：')
        print('  1) 回 /plan 走完方案设计，再 generate_docs.py 生成 spec/task')
        print('  2) 简单任务：手写 lite spec（目标 / 范围 / 验收 各一行），'
              '再跑 --lite 复核')
        print('  命令：python scripts/generate_docs.py --task %s' % payload['task'])
    elif code == 2:
        print('\n下一步：基于已有 spec 补 task 清单（逐条含验证步骤），'
              '或跑 generate_docs.py --task %s' % payload['task'])
    elif code == 3:
        print('\n检查 docs_rj 是否存在，或用 --docs-dir 显式指定主 docs 目录。')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='/do 文档门禁：spec/task 缺失就不许动手（stdlib-only，只读）')
    parser.add_argument('--task', required=True, help='任务名（只允许 [a-z0-9_]+）')
    parser.add_argument('--docs-dir', default=None, help='主 docs 目录（默认 ./docs_rj）')
    parser.add_argument('--lite', action='store_true',
                        help='简单任务模式：只要求 spec，且内容至少 3 行')
    parser.add_argument('--exempt', action='store_true',
                        help='豁免模式：文章/文案类任务直接放行')
    parser.add_argument('--reason', default='', help='豁免原因（配合 --exempt）')
    parser.add_argument('--json', action='store_true', dest='as_json',
                        help='输出 JSON 报告')
    args = parser.parse_args(argv)

    if not TASK_NAME_RE.match(args.task):
        message = '任务名非法（只允许 [a-z0-9_]+）: %s' % args.task
        if args.as_json:
            print(json.dumps({'passed': False, 'reason': message}, ensure_ascii=False))
        else:
            print('错误：%s' % message, file=sys.stderr)
        return 3

    docs = resolve_docs(args.docs_dir)
    if docs is None:
        message = '未解析到主 docs 目录（默认 ./docs_rj，可用 --docs-dir 指定）'
        if args.as_json:
            print(json.dumps({'passed': False, 'reason': message}, ensure_ascii=False))
        else:
            print('错误：%s' % message, file=sys.stderr)
        return 3

    spec_paths = find_artifacts(docs, SPEC_DIR, args.task, 'spec')
    task_paths = find_artifacts(docs, TASK_DIR, args.task, 'task')

    payload, code = build_result(
        args.task, docs, args.lite, args.exempt, args.reason, spec_paths, task_paths)

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(payload, code)
    return code


if __name__ == '__main__':
    sys.exit(main())
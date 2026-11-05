#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""post_upgrade_check.py — 升级后体检（v1.1.0 新增）

背景：升级 = 解压覆盖 skill 包目录。如果 docs_rj 曾经落在 skill 包目录里，
下一次升级就会把文档覆盖掉，SUMMARY / INDEX 与真实文件随即对不上——这就是
「每次升级文档就乱」的成因。本脚本把这件事变成一条命令、几秒出结论。

五项检查：
  1. 包内 docs_rj 污染 —— skill 根目录下的 docs_rj 是否还残留文档（升级会被覆盖）
  2. 主 docs 落点      —— 解析出的主 docs 是否指向 skill 包内目录
  3. 版本号一致性      —— 复用 data_verify.check_version（五方版本联动）
  4. 死引用            —— 复用 data_verify.check_links
  5. SUMMARY 漂移      —— 复用 tidy_common.drift_check + total_docs 校准

用法：
  python scripts/post_upgrade_check.py
  python scripts/post_upgrade_check.py --root "<skill 目录>"
  python scripts/post_upgrade_check.py --docs "<docs_rj>" --json

退出码：
  0 全过（WARN 不阻断）
  1 存在 FAIL
  2 环境错误（root 下没有 SKILL.md）

技术约束：仅 Python 标准库；不写任何文件（只读体检）；所有日志走 stderr。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_verify  # noqa: E402
import tidy_common  # noqa: E402

# SUMMARY 计数口径与 reconcile_doc_links 保持一致的 5 个 canonical 子目录
CANONICAL_SUBDIRS = ('memory_rj', 'spec_rj', 'task_rj', 'handoff_rj', 'archive_rj')
TOTAL_DOCS_RE = re.compile(r'^total_docs:\s*(\d+)', re.M)
# .gitignore 中"整目录忽略 docs_rj"的等价写法：docs_rj / docs_rj/ / /docs_rj/ /
# docs_rj/** / **/docs_rj/ 等（不支持行尾注释，见 docs_rj_gitignored 说明）
DOCS_RJ_IGNORE_RE = re.compile(r'^/?(\*\*/)?docs_rj/?(\*\*)?/?$')
# 命中 docs_rj 目录内的任意规则（含 !例外行），用于按 gitignore「后匹配优先」回推
DOCS_RJ_RELATED_RE = re.compile(r'^/?(\*\*/)?docs_rj(/|$)')
# 发布骨架：package_skill.py 的 _SKELETON_WHITELIST 会把这两个文件按模板写进发布包
# （首次启动 §1 启动检查要读，缺失会 BLOCKER），因此包内 docs_rj 只有它们属打包预期、
# 不是污染。路径相对 docs_rj/，POSIX 风格。
RELEASE_SKELETON_FILES = ('SUMMARY_RJ.md', 'spec_rj/spec_main_rj.md')


# ===========================================================================
# 工具函数
# ===========================================================================
def _abspath_norm(path):
    return os.path.normcase(os.path.abspath(path))


def _same_path(a, b):
    if not a or not b:
        return False
    return _abspath_norm(a) == _abspath_norm(b)


def _is_inside(child, parent):
    """child 是否位于 parent 内部（含 parent 本身）。"""
    try:
        child_n = _abspath_norm(child)
        parent_n = _abspath_norm(parent)
        return os.path.commonpath([child_n, parent_n]) == parent_n
    except ValueError:
        # 跨盘符等情况：commonpath 会抛 ValueError
        return False


def list_md_files(base):
    """递归列出 base 下全部 .md 的相对路径（POSIX 风格，跳过隐藏目录）。"""
    results = []
    for cur_dir, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for name in sorted(files):
            if name.lower().endswith('.md'):
                rel = os.path.relpath(os.path.join(cur_dir, name), base)
                results.append(rel.replace(os.sep, '/'))
    return results


def _normalize_ignore_line(raw):
    """去掉空行/注释行，返回可用于匹配的 pattern（空串表示该行跳过）。"""
    line = raw.strip()
    if not line or line.startswith('#'):
        return ''
    return line


def docs_rj_gitignored(skill_root):
    """skill 根目录的 .gitignore 是否把 docs_rj 整个忽略（不随包发布）。

    支持写法：docs_rj、docs_rj/、/docs_rj/、docs_rj/**、/docs_rj/**、**/docs_rj/。
    按 gitignore「后匹配优先」逐行推演：!docs_rj/... 例外行会把状态翻回未忽略，
    之后再出现整体忽略行又翻回忽略（本仓库正是这种形态）。
    只忽略局部内容的写法（如 docs_rj/*.md）不算整体忽略。
    注：.gitignore 不支持行尾注释，`docs_rj/  # 注释` 在 git 里是字面 pattern、
    不会真正忽略该目录，因此这里也不认——否则会给出假 PASS。
    """
    ignore_path = os.path.join(skill_root, '.gitignore')
    if not os.path.isfile(ignore_path):
        return False
    try:
        with open(ignore_path, 'r', encoding='utf-8', errors='ignore') as handle:
            lines = handle.read().splitlines()
    except OSError:
        return False

    ignored = False
    for raw in lines:
        line = _normalize_ignore_line(raw)
        if not line:
            continue
        if line.startswith('!'):
            if DOCS_RJ_RELATED_RE.match(line[1:]):
                ignored = False
            continue
        if DOCS_RJ_IGNORE_RE.match(line):
            ignored = True
    return ignored


def _result(item, status, detail, extra=None):
    return {'item': item, 'status': status, 'detail': detail, 'extra': extra or {}}


# ===========================================================================
# 1. 包内 docs_rj 污染
# ===========================================================================
def check_package_docs(skill_root, primary_docs):
    pkg_docs = os.path.join(skill_root, 'docs_rj')
    if not os.path.isdir(pkg_docs):
        return _result('包内 docs_rj', 'PASS', 'skill 根目录下没有 docs_rj，升级不会被文档污染')

    files = list_md_files(pkg_docs)
    if not files:
        return _result('包内 docs_rj', 'WARN',
                       '包内 docs_rj 是空壳目录，建议删除，避免被误判为主 docs')

    if _same_path(pkg_docs, primary_docs):
        if docs_rj_gitignored(skill_root):
            return _result('包内 docs_rj', 'PASS',
                           'docs_rj 就是当前主 docs，且已被 .gitignore 排除（不随包发布）',
                           {'count': len(files)})
        return _result('包内 docs_rj', 'FAIL',
                       'docs_rj 位于 skill 包内且未被 .gitignore 排除：一旦按包覆盖升级，'
                       '%d 份文档会被覆盖丢失' % len(files),
                       {'count': len(files), 'samples': files[:10]})

    # 包内 docs_rj 不是主 docs：只有发布骨架时属打包预期（package_skill 的
    # _SKELETON_WHITELIST 会写入模板骨架），不算污染
    non_skeleton = [f for f in files if f not in RELEASE_SKELETON_FILES]
    if not non_skeleton:
        return _result('包内 docs_rj', 'PASS',
                       '包内 docs_rj 仅含发布骨架 %d 份（模板内容，首次启动用，非污染）' % len(files),
                       {'count': len(files), 'skeletons': files})

    return _result('包内 docs_rj', 'FAIL',
                   '包内存在孤立的 docs_rj（%d 份文档），升级解压覆盖会丢文档、并造成双份索引'
                   '（真实主 docs 另有其处）' % len(non_skeleton),
                   {'count': len(non_skeleton), 'samples': non_skeleton[:10]})


# ===========================================================================
# 2. 主 docs 落点
# ===========================================================================
def check_primary_docs(skill_root, docs_arg):
    try:
        primary = tidy_common.resolve_primary_docs(docs_arg)
    except Exception as exc:  # noqa: BLE001 - 解析链异常统一按失败处理
        return _result('主 docs 落点', 'FAIL', '解析主 docs 抛异常: %s' % exc), None

    if not primary or not os.path.isdir(primary):
        return _result('主 docs 落点', 'FAIL',
                       '未解析到主 docs（无 .primary_docs_rj 标记，且当前目录树下无 docs_rj）'), None

    if _is_inside(primary, skill_root):
        if docs_rj_gitignored(skill_root):
            return _result('主 docs 落点', 'WARN',
                           '主 docs 在 skill 包内（%s），但 docs_rj 已被 .gitignore 排除，'
                           '不会被覆盖升级影响' % primary), primary
        return _result('主 docs 落点', 'FAIL',
                       '主 docs 落在 skill 包内（%s）：升级覆盖会直接丢失文档' % primary), primary

    return _result('主 docs 落点', 'PASS', primary), primary


# ===========================================================================
# 3. 版本号一致性
# ===========================================================================
def check_versions(skill_root):
    ok, message, details = data_verify.check_version(skill_root)
    return _result('版本号一致性', 'PASS' if ok else 'FAIL', message, details)


# ===========================================================================
# 4. 死引用
# ===========================================================================
def check_dead_links(skill_root):
    ok, checked, dead = data_verify.check_links(skill_root)
    detail = '扫描相对链接 %d 条，死链 %d 条' % (checked, len(dead))
    return _result('入口文档死引用', 'PASS' if ok else 'FAIL', detail,
                   {'checked': checked, 'dead': dead[:30]})


# ===========================================================================
# 5. SUMMARY 漂移 + total_docs 校准
# ===========================================================================
def check_summary(primary_docs):
    if not primary_docs:
        return _result('SUMMARY 漂移', 'FAIL', '主 docs 未解析，无法检查 SUMMARY')

    summary_path = os.path.join(primary_docs, 'SUMMARY_RJ.md')
    if not os.path.isfile(summary_path):
        return _result('SUMMARY 漂移', 'FAIL', 'SUMMARY_RJ.md 不存在: %s' % summary_path)

    missing_count, missing_list = tidy_common.drift_check(summary_path)

    declared = None
    try:
        with open(summary_path, 'r', encoding='utf-8-sig') as handle:
            text = handle.read()
        match = TOTAL_DOCS_RE.search(text)
        if match:
            declared = int(match.group(1))
    except (OSError, UnicodeDecodeError):
        pass

    actual = 0
    for subdir in CANONICAL_SUBDIRS:
        sub_path = os.path.join(primary_docs, subdir)
        if os.path.isdir(sub_path):
            actual += len(tidy_common.iter_md_rel_paths(sub_path))

    problems = []
    if missing_count:
        problems.append('坏链 %d 条' % missing_count)
    if declared is None:
        problems.append('缺 total_docs 声明')
    elif declared != actual:
        problems.append('total_docs=%d 与实际 %d 份不符' % (declared, actual))

    if problems:
        return _result('SUMMARY 漂移', 'FAIL', '；'.join(problems),
                       {'missing': missing_list[:30], 'declared': declared, 'actual': actual})

    return _result('SUMMARY 漂移', 'PASS',
                   '链接 0 坏链，total_docs=%d 与实际一致' % declared,
                   {'declared': declared, 'actual': actual})


# ===========================================================================
# 输出
# ===========================================================================
STATUS_ICON = {'PASS': '[PASS]', 'WARN': '[WARN]', 'FAIL': '[FAIL]'}

HINTS = {
    '包内 docs_rj': [
        '把包内 docs_rj 里的文档搬到真实项目目录，再删掉包内目录',
        '或 python scripts/generate_docs.py --declare-primary "<真实 docs_rj>" 指定主 docs',
    ],
    '主 docs 落点': [
        '在项目根运行：python scripts/generate_docs.py --declare-primary "<项目根>/docs_rj"',
    ],
    'SUMMARY 漂移': [
        'python -c "import tidy_common; tidy_common.refresh_summary(r\'<主 docs>\')"',
    ],
}


def render_text(skill_root, results, primary_docs):
    lines = ['# post_upgrade_check · %s' % skill_root,
             '- 主 docs: %s' % (primary_docs or '未解析')]
    for idx, item in enumerate(results, 1):
        lines.append('%s %d. %s —— %s' % (
            STATUS_ICON.get(item['status'], '[????]'), idx, item['item'], item['detail']))
        extra = item.get('extra') or {}
        for sample in extra.get('samples', [])[:10]:
            lines.append('        · %s' % sample)
        for sample in extra.get('dead', [])[:10]:
            lines.append('        · 死链 %s' % sample)
        for sample in extra.get('missing', [])[:10]:
            lines.append('        · 漂移 %s' % sample)

    fails = [i for i in results if i['status'] == 'FAIL']
    warns = [i for i in results if i['status'] == 'WARN']
    lines.append('')
    lines.append('## 汇总')
    lines.append('- PASS %d / WARN %d / FAIL %d' % (
        len(results) - len(fails) - len(warns), len(warns), len(fails)))
    lines.append('- 结果: %s' % ('PASS（退码 0）' if not fails else 'FAIL（退码 1）'))
    if fails:
        lines.append('')
        lines.append('## 建议动作')
        for item in fails:
            for hint in HINTS.get(item['item'], []):
                lines.append('- [%s] %s' % (item['item'], hint))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='升级后体检：包内 docs_rj / 主 docs 落点 / 版本号 / 死链 / SUMMARY 漂移')
    parser.add_argument('--root', default=None,
                        help='技能目录（含 SKILL.md），默认取本脚本所在目录的父目录')
    parser.add_argument('--docs', default=None, help='显式指定主 docs 目录')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args(argv)

    skill_root = os.path.abspath(args.root) if args.root else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isfile(os.path.join(skill_root, 'SKILL.md')):
        sys.stderr.write('错误：%s 下没有 SKILL.md，无法体检\n' % skill_root)
        return 2

    primary_result, primary_docs = check_primary_docs(skill_root, args.docs)
    results = [
        check_package_docs(skill_root, primary_docs),
        primary_result,
        check_versions(skill_root),
        check_dead_links(skill_root),
        check_summary(primary_docs),
    ]

    if args.json:
        payload = {
            'skill_root': skill_root,
            'primary_docs': primary_docs,
            'results': results,
            'fail': sum(1 for item in results if item['status'] == 'FAIL'),
            'warn': sum(1 for item in results if item['status'] == 'WARN'),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(skill_root, results, primary_docs))

    return 0 if all(item['status'] != 'FAIL' for item in results) else 1


if __name__ == '__main__':
    sys.exit(main())
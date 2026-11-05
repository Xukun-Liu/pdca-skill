#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_verify.py — 数据/文档一致性校验（v1.1.0 · B4 / B3+B7）

三查合一，替代「升级完靠感觉判断对不对」：
  1. 版本号一致性：SKILL.md frontmatter == HISTORY.md frontmatter ==
     HISTORY.md 页脚 == README.md 徽章 == evals.json version
  2. 死引用：SKILL.md / README.md / HISTORY.md / references/**/*.md 中的
     markdown 相对链接是否都能落到真实文件（跳过 http/https/mailto/# 与代码块）
  3. 口径三状态：文档里的数据口径标记是否符合三状态规范
     （`88.52｜官方口径｜来源` / `xx.xx｜来源待补` / `暂无数据`）；
     汇报类文档里「有百分数但无口径标记」记为警告

用法：
  python scripts/data_verify.py --root "<skill 目录>"
  python scripts/data_verify.py --root "<skill 目录>" --docs "<docs_rj>"
  python scripts/data_verify.py --root "<skill 目录>" --strict-caliber

退出码：
  0 三查全过（口径仅有警告不算失败）
  1 版本不一致 / 有死引用 / --strict-caliber 下口径不合规
  2 环境错误（root 不存在 / 关键文件缺失导致无法判定）

技术约束：仅 Python 标准库；主 docs 解析复用 tidy_common.resolve_primary_docs。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402

MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
FENCE_RE = re.compile(r'^```.*?^```', re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r'`[^`\n]*`')
SKIP_PREFIX = ('http://', 'https://', 'mailto:', '#', 'tel:', 'file:')

# 第三方随包内容（与 validate_skill.VENDORED_REF_PREFIXES 对齐），不参与死链判定
VENDORED_PREFIXES = (
    'references/common/da/diagram-design/',
)
# 文档里的占位/示例路径特征
PLACEHOLDER_CHARS = ('{', '}', '…', '<', '>')
# 用户数据目录：不随包发布，指向它们的链接不参与死链判定
USER_DATA_SEGMENTS = ('docs_rj', 'memory_rj', 'spec_rj', 'task_rj',
                      'handoff_rj', 'archive_rj', 'check_rj')

# 口径三状态
CALIBER_OFFICIAL = '官方口径'
CALIBER_PENDING = '来源待补'
CALIBER_EMPTY = '暂无数据'
CALIBER_OFFICIAL_RE = re.compile(r'[\d.,]+\s*(?:%|％)?\s*｜\s*官方口径\s*｜\s*[^\s|]+')
CALIBER_PENDING_RE = re.compile(r'[\d.,]+\s*(?:%|％)?\s*｜\s*来源待补')
CALIBER_OFFICIAL_CLAIM = re.compile(r'[\d.,]+\s*(?:%|％)?\s*｜\s*官方口径')
CALIBER_PENDING_CLAIM = re.compile(r'[\d.,]+\s*(?:%|％)?\s*｜\s*来源待补')
PERCENT_RE = re.compile(r'\d+(?:\.\d+)?\s*%')

REPORT_DOC_HINTS = ('leader_report', 'hand-drawn-report', '汇报', '周报', '月报')


def strip_fences(text):
    """去掉围栏代码块，避免把示例里的假链接/假数据当校验对象。"""
    return FENCE_RE.sub('', text)


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return None


# ---------- 1. 版本号 ----------

def check_version(root):
    """五方版本号联动：返回 (ok, message, details)。"""
    errors = []
    details = {}

    def pick(text, pattern, label):
        if text is None:
            errors.append('%s 读取失败' % label)
            return None
        match = re.search(pattern, text)
        if not match:
            errors.append('%s 未找到版本号' % label)
            return None
        return match.group(1)

    skill_text = read_text(os.path.join(root, 'SKILL.md'))
    details['SKILL.md frontmatter'] = pick(
        skill_text, r'version:\s*"?v(\d+\.\d+\.\d+)"?', 'SKILL.md frontmatter')

    hist_text = read_text(os.path.join(root, 'HISTORY.md'))
    details['HISTORY.md frontmatter'] = pick(
        hist_text, r'version:\s*v(\d+\.\d+\.\d+)', 'HISTORY.md frontmatter')
    details['HISTORY.md 页脚'] = pick(
        hist_text, r'\*\*版本\*\*:\s*v(\d+\.\d+\.\d+)', 'HISTORY.md 页脚')

    readme_text = read_text(os.path.join(root, 'README.md'))
    details['README.md 徽章'] = pick(
        readme_text, r'version-v(\d+\.\d+\.\d+)-', 'README.md 徽章')

    evals_path = os.path.join(root, 'evals', 'evals.json')
    try:
        with open(evals_path, 'r', encoding='utf-8') as handle:
            evals_ver = str(json.load(handle).get('version', ''))
        match = re.match(r'v(\d+\.\d+\.\d+)', evals_ver)
        details['evals.json'] = match.group(1) if match else None
        if not details['evals.json']:
            errors.append('evals.json version 格式错误: %s' % evals_ver)
    except (OSError, ValueError) as exc:
        errors.append('读取 evals.json 失败: %s' % exc)
        details['evals.json'] = None

    if errors:
        return False, '版本探针提取失败: %s' % '; '.join(errors), details
    unique = set(v for v in details.values() if v)
    if len(unique) != 1:
        drift = ', '.join('%s=v%s' % (k, v) for k, v in details.items())
        return False, '版本不一致（漂移）: %s' % drift, details
    return True, '五方版本一致: v%s' % unique.pop(), details


# ---------- 2. 死引用 ----------

def collect_targets(root):
    """校验范围：入口三件 + references 下全部 md。"""
    targets = []
    for name in ('SKILL.md', 'README.md', 'HISTORY.md'):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            targets.append(path)
    ref_root = os.path.join(root, 'references')
    for cur, dirs, files in os.walk(ref_root):
        dirs.sort()
        for name in sorted(files):
            if name.lower().endswith('.md'):
                targets.append(os.path.join(cur, name))
    return targets


def check_links(root):
    """返回 (ok, 检查数, 死链列表)。

    跳过：外链 / 代码块内示例 / 占位符路径（含 {} … <>）/ 无扩展名路径 /
    解析后落在包外的用户数据路径 / 第三方随包目录。
    """
    dead = []
    checked = 0
    root_parts = root.rstrip(os.sep) + os.sep
    for path in collect_targets(root):
        rel_file = os.path.relpath(path, root).replace(os.sep, '/')
        if any(rel_file.startswith(prefix) for prefix in VENDORED_PREFIXES):
            continue
        text = read_text(path)
        if text is None:
            continue
        # 去掉代码块与行内代码：其中的链接是写法示例，不参与死链判定
        body = INLINE_CODE_RE.sub('', strip_fences(text))
        for _, target in MD_LINK_RE.findall(body):
            link = target.strip().split('#')[0].strip()
            if not link or link.startswith(SKIP_PREFIX):
                continue
            if any(char in link for char in PLACEHOLDER_CHARS):
                continue
            segments = link.replace('\\', '/').split('/')
            if any(seg in USER_DATA_SEGMENTS for seg in segments):
                continue  # 指向用户数据目录（不随包发布）
            if not os.path.splitext(link.split('?')[0])[1]:
                continue  # 无扩展名（如 `path` / `路径`）：示意写法，不判定
            candidate = link.replace('/', os.sep).replace('\\', os.sep)
            paths = [os.path.normpath(os.path.join(os.path.dirname(path), candidate)),
                     os.path.normpath(os.path.join(root, candidate))]
            if not any(item.startswith(root_parts) for item in paths):
                continue  # 指向包外的用户数据（docs_rj / 桌面等）
            checked += 1
            if not any(os.path.exists(item) for item in paths):
                dead.append('%s -> %s' % (rel_file, link))
    return (not dead), checked, dead


# ---------- 3. 口径 ----------

def resolve_docs(docs_arg=None):
    try:
        docs = tidy_common.resolve_primary_docs(docs_arg)
    except Exception:  # noqa: BLE001 - 解析失败只是跳过口径检查
        return None
    if not docs or not os.path.isdir(docs):
        return None
    return os.path.abspath(docs)


def check_caliber(docs_root):
    """口径三状态校验：返回 (ok, 扫描文件数, 问题列表, 警告列表)。"""
    problems = []
    warnings = []
    scanned = 0
    if not docs_root:
        return True, 0, problems, ['未解析到 docs 目录，口径检查跳过']

    for sub in ('spec_rj', 'task_rj', 'check_rj', 'archive_rj'):
        base = os.path.join(docs_root, sub)
        if not os.path.isdir(base):
            continue
        for cur, dirs, files in os.walk(base):
            dirs.sort()
            for name in sorted(files):
                if not name.lower().endswith('.md'):
                    continue
                scanned += 1
                text = read_text(os.path.join(cur, name)) or ''
                rel = os.path.relpath(os.path.join(cur, name), docs_root)
                # 去掉行内代码：规则说明里的 `xx.xx｜来源待补` 是格式示例，不是数据口径
                body = INLINE_CODE_RE.sub('', strip_fences(text))
                for line in body.splitlines():
                    if (CALIBER_OFFICIAL_CLAIM.search(line)
                            and not CALIBER_OFFICIAL_RE.search(line)):
                        problems.append('%s: 官方口径缺来源 -> %s' % (rel, line.strip()[:80]))
                    if (CALIBER_PENDING_CLAIM.search(line)
                            and not CALIBER_PENDING_RE.search(line)):
                        problems.append('%s: 来源待补格式错误 -> %s' % (rel, line.strip()[:80]))
                    if (any(hint in name for hint in REPORT_DOC_HINTS)
                            and PERCENT_RE.search(line)
                            and not any(mark in line
                                        for mark in (CALIBER_OFFICIAL, CALIBER_PENDING, CALIBER_EMPTY))):
                        warnings.append('%s: 百分数无口径标记 -> %s' % (rel, line.strip()[:80]))
    return (not problems), scanned, problems, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='数据/文档一致性校验：版本号 / 死引用 / 口径三状态')
    parser.add_argument('--root', default='.', help='技能目录（含 SKILL.md）')
    parser.add_argument('--docs', default=None, help='显式指定 docs 目录（默认按 marker 解析）')
    parser.add_argument('--strict-caliber', action='store_true',
                        help='口径不合规也计入失败（默认只报警告）')
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    print('# data_verify · %s' % root)
    if not os.path.isfile(os.path.join(root, 'SKILL.md')):
        print('错误：root 下没有 SKILL.md，无法校验', file=sys.stderr)
        return 2

    failures = 0

    ok, msg, details = check_version(root)
    print('\n## 1. 版本号一致性')
    for key, value in details.items():
        print('- %s: %s' % (key, ('v' + value) if value else '未提取到'))
    print('- 结论: %s' % ('PASS · ' + msg if ok else 'FAIL · ' + msg))
    if not ok:
        failures += 1

    ok, checked, dead = check_links(root)
    print('\n## 2. 死引用')
    print('- 扫描相对链接 %d 条，死链 %d 条' % (checked, len(dead)))
    for item in dead[:30]:
        print('  - %s' % item)
    if len(dead) > 30:
        print('  - … 其余 %d 条省略' % (len(dead) - 30))
    print('- 结论: %s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        failures += 1

    docs_root = resolve_docs(args.docs)
    ok, scanned, problems, warnings = check_caliber(docs_root)
    print('\n## 3. 口径三状态')
    print('- docs: %s' % (docs_root or '未解析'))
    print('- 扫描文档 %d 份，违规 %d 条，警告 %d 条' % (scanned, len(problems), len(warnings)))
    for item in problems[:20]:
        print('  - [违规] %s' % item)
    for item in warnings[:10]:
        print('  - [警告] %s' % item)
    print('- 结论: %s' % ('PASS' if ok else 'FAIL'))
    if not ok:
        if args.strict_caliber:
            failures += 1
        else:
            print('  （未加 --strict-caliber，口径违规仅提示，不计入失败）')

    print('\n## 汇总')
    print('- 失败项: %d' % failures)
    print('- 结果: %s' % ('PASS（退码 0）' if failures == 0 else 'FAIL（退码 1）'))
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
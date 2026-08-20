#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tidy_common.py — 启动/交接共享函数库（期3新增）

提供 startup_tidy 和 handoff_tidy 共享的函数：
- ensure_project_structure()：项目结构守卫
- resolve_primary_docs()：解析主 docs 目录
- scan_and_archive_scattered()：扫描散落文档+归档
- refresh_summary()：刷新 SUMMARY_RJ.md
- drift_check()：漂移检查
- cleanup_legacy_memory()：外部记忆扫描清理（广扫描+用户确认）
- force_sync_project_to_global()：强制 #3→#4 同步

技术约束：仅 Python 标准库；复用 generate_docs / memory_shadow_write。
"""

import os
import sys
import re
import json
import shutil
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_docs  # noqa: E402
import memory_shadow_write  # noqa: E402
import user_data_path  # noqa: E402

import logging
logger = logging.getLogger(__name__)


# ===========================================================================
# 共享函数（从 startup_tidy.py 抽取）
# ===========================================================================

def resolve_user_data_dir():
    """解析用户数据外置目录路径（不阻塞启动）。

    内部调用 user_data_path.get_user_data_dir()，返回外置目录路径对象。
    外置目录无权限时 raise PermissionError，由调用方（T005b startup_tidy main）捕获告警。

    Returns:
        Path: 用户数据目录路径（~/.pdca-skill/data/）
    """
    return user_data_path.get_user_data_dir()


def ensure_project_structure():
    """项目结构守卫（报告型）：检测项目结构完整性，缺失仅报告、绝不静默建。
    
    检测项：docs_rj/ + docs_rj 5类文件夹（含 memory_rj） + outputs_rj/ + .agent/
    返回缺失清单 list[dict]，每条：{path, reason, layer}
    """
    missing = []
    root_dirs = ['docs_rj', 'outputs_rj']
    for d in root_dirs:
        p = os.path.join(os.getcwd(), d)
        if not os.path.isdir(p):
            missing.append({'path': d + '/', 'reason': '项目结构缺失：目录不存在', 'layer': 'project'})
    # .agent/ 为推荐项，不纳入 missing 清单（对齐 SKILL.md §0 启动前置检查 8 要素，不含 .agent/）
    for d in ('.agent/memory', '.agent/skills'):
        p = os.path.join(os.getcwd(), d)
        if not os.path.isdir(p):
            logger.info("[推荐] agent 侧目录 %s 不存在，可跳过", d)
    for sub in generate_docs.DOC_RJ_SUBDIRS:
        p = os.path.join(os.getcwd(), 'docs_rj', sub)
        if not os.path.isdir(p):
            missing.append({'path': 'docs_rj/%s/' % sub, 'reason': 'docs 常驻文件夹缺失', 'layer': 'docs'})
    summary_path = os.path.join(os.getcwd(), 'docs_rj', 'SUMMARY_RJ.md')
    if not os.path.isfile(summary_path):
        missing.append({'path': 'docs_rj/SUMMARY_RJ.md', 'reason': '项目根索引缺失', 'layer': 'docs'})
    return missing


def resolve_primary_docs(primary_docs_arg=None):
    """解析主 docs 目录（R3 优先级：显式 > 标记 > 约定 > 路由）"""
    if primary_docs_arg:
        candidate = os.path.abspath(primary_docs_arg)
        if os.path.isdir(candidate):
            return candidate
    marker = generate_docs.read_primary_docs_marker()
    if marker:
        return marker
    mem = generate_docs.read_primary_docs_from_memory()
    if mem:
        return mem
    return generate_docs.find_docs_dir(create=False)


def scan_and_archive_scattered(primary_docs, dry_run=False):
    """扫描散落文档 + 归档到主 docs"""
    scattered = generate_docs.scan_scattered_docs(primary_docs)
    archive = generate_docs.archive_scattered_docs(primary_docs, dry_run=dry_run)
    return {'scattered': scattered, 'archived': archive.get('archived', []),
            'skipped': archive.get('skipped', []), 'errors': archive.get('errors', [])}


def drift_check(summary_path):
    """漂移检查：grep SUMMARY 所有链接 → ls 确认存在"""
    if not summary_path or not os.path.isfile(summary_path):
        return (0, [])
    try:
        with open(summary_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except (OSError, UnicodeDecodeError):
        return (0, [])
    base_dir = os.path.dirname(os.path.abspath(summary_path))
    link_re = re.compile(r'\]\(([^)]+)\)')
    missing = []
    seen = set()
    for match in link_re.finditer(content):
        target = match.group(1).strip()
        if not target or target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        if target in seen:
            continue
        seen.add(target)
        abs_target = target if os.path.isabs(target) else os.path.normpath(os.path.join(base_dir, target))
        if not os.path.isfile(abs_target):
            missing.append(target)
    return (len(missing), missing)


def reconcile_doc_links(summary_path, primary_docs):
    """增量补全文档链接（修复 SUMMARY 刷新 bug）。

    扫描 docs_rj/ 5 子目录（memory_rj/spec_rj/task_rj/handoff_rj/archive_rj）的 .md 文件，
    对比 SUMMARY 现有链接，把缺失的追加到对应段末尾。同时更新 frontmatter 的 total_docs。

    设计原则（对齐 A3 不覆盖独有内容）：
    - 只追加缺失链接，不重写已有链接
    - 不删除用户手工写的描述
    - 段内已有链接保持原序

    Args:
        summary_path: SUMMARY_RJ.md 绝对路径
        primary_docs: 主 docs 目录绝对路径

    Returns:
        int: 追加的链接数
    """
    # 段标题映射：子目录名 → SUMMARY 段标题
    section_map = {
        'memory_rj': '## 🧠 Memory 文档',
        'spec_rj': '## 📋 Spec 文档',
        'task_rj': '## ✅ Task 文档',
        'handoff_rj': '## 🤝 Handoff 文档',
        'archive_rj': '## 🗄️ Archive 文档',
    }

    try:
        with open(summary_path, 'r', encoding='utf-8') as handle:
            lines = handle.readlines()
    except (OSError, UnicodeDecodeError):
        return 0

    # 收集所有现有链接的文件名（用于去重）
    existing_files = set()
    for ln in lines:
        m = re.search(r'\[[^\]]*\]\(([^)]+)\)', ln)
        if m:
            existing_files.add(os.path.basename(m.group(1)))

    # 扫描 5 子目录，收集缺失文件
    reconciled = 0
    new_lines_by_section = {}
    total_docs = 0
    for subdir, section_title in section_map.items():
        subdir_path = os.path.join(primary_docs, subdir)
        if not os.path.isdir(subdir_path):
            continue
        new_links = []
        # archive_rj 特殊处理：扫描子文件夹（新结构）+ 扁平文件（legacy）
        if subdir == 'archive_rj':
            all_entries = os.listdir(subdir_path)
            # 子文件夹（新结构：{task}_{ts}/）—— 链接指向文件夹本身
            subfolders = sorted([d for d in all_entries
                                 if os.path.isdir(os.path.join(subdir_path, d))])
            for dname in subfolders:
                total_docs += 1
                if dname in existing_files:
                    continue
                new_links.append('- [%s/%s/](%s/%s/) — %s\n' % (subdir, dname, subdir, dname, dname))
                reconciled += 1
            # 扁平文件（legacy：{task}_{type}_{ts}_archived.md）
            flat_files = sorted([f for f in all_entries
                                 if f.endswith('.md') and f != 'INDEX.md'])
            for fname in flat_files:
                total_docs += 1
                if fname in existing_files:
                    continue
                desc = os.path.splitext(fname)[0]
                new_links.append('- [%s/%s](%s/%s) — %s\n' % (subdir, fname, subdir, fname, desc))
                reconciled += 1
        else:
            for fname in sorted(os.listdir(subdir_path)):
                if not fname.endswith('.md'):
                    continue
                if fname == 'SUMMARY_RJ.md':
                    continue
                total_docs += 1
                if fname in existing_files:
                    continue
                desc = os.path.splitext(fname)[0]
                new_links.append('- [%s/%s](%s/%s) — %s\n' % (subdir, fname, subdir, fname, desc))
                reconciled += 1
        if new_links:
            new_lines_by_section[section_title] = new_links

    # 如果有新增链接，插入到对应段末尾
    if new_lines_by_section:
        new_lines_out = []
        i = 0
        while i < len(lines):
            new_lines_out.append(lines[i])
            for section_title, new_links in new_lines_by_section.items():
                if lines[i].rstrip('\n') == section_title:
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith('## '):
                        new_lines_out.append(lines[j])
                        j += 1
                    for link_line in new_links:
                        new_lines_out.append(link_line)
                    i = j
                    break
            else:
                i += 1

        # 更新 frontmatter total_docs
        for k, ln in enumerate(new_lines_out):
            if ln.startswith('total_docs:'):
                new_lines_out[k] = 'total_docs: %d\n' % total_docs
                break

        generate_docs.atomic_write(summary_path, ''.join(new_lines_out))
        logger.info("SUMMARY 增量补全：追加 %d 个文档链接", reconciled)

    return reconciled


def refresh_summary(primary_docs, dry_run=False):
    """刷新 SUMMARY_RJ.md（last_updated + 增量补全 + 漂移检查）。

    修复：原版只更新 last_updated 不重扫文档列表，导致 SUMMARY 过期。
    现在调用 reconcile_doc_links 增量补全缺失的文档链接。
    """
    if not primary_docs:
        return {'summary_path': None, 'refreshed': False, 'drift': 0, 'missing': [], 'reconciled': 0}
    summary_path = os.path.join(primary_docs, 'SUMMARY_RJ.md')
    if not os.path.isfile(summary_path):
        return {'summary_path': None, 'refreshed': False, 'drift': 0, 'missing': [], 'reconciled': 0}
    if dry_run:
        return {'summary_path': summary_path, 'refreshed': False, 'drift': 0, 'missing': [], 'reconciled': 0}
    # 更新 last_updated
    try:
        with open(summary_path, 'r', encoding='utf-8') as handle:
            lines = handle.readlines()
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith('last_updated:') and not replaced:
                new_lines.append('last_updated: %s\n' % now)
                replaced = True
            else:
                new_lines.append(line)
        if replaced:
            generate_docs.atomic_write(summary_path, ''.join(new_lines))
    except (OSError, UnicodeDecodeError):
        pass
    # 增量补全文档链接
    reconciled_count = reconcile_doc_links(summary_path, primary_docs)
    drift_count, missing = drift_check(summary_path)
    return {'summary_path': summary_path, 'refreshed': True, 'drift': drift_count, 'missing': missing, 'reconciled': reconciled_count}


# ===========================================================================
# 外部记忆扫描清理（广扫描+用户确认）
# ===========================================================================

MEMORY_SCAN_ROOTS = [
    # WorkBuddy：只扫 memory/ 子目录 + 指定全局文件
    '~/.workbuddy/memory/',
    '~/.workbuddy/MEMORY.md',   # 全局记忆（融入但不删除，见 M6）
    '~/.workbuddy/USER.md',     # 全局用户画像（同上）
    # Trae：只扫 memory/ 子目录
    '~/.trae-cn/memory/',
    # 其他平台：只扫 memory/ 子目录（不扫整个应用目录）
    '~/.cursor/memory/',
    '~/.claude/memory/',
    '~/.continue/memory/',
    '~/.windsurf/memory/',
    '~/.codeium/memory/',
    '~/.agent/memory/',
    # 项目级
    './memory/',
    './memory_rj/',
]

# 从关键词包含改为正则精确匹配，避免 working_memory_rules.md 等误伤
MEMORY_FILE_PATTERNS = [
    re.compile(r'^MEMORY\.md$', re.IGNORECASE),
    re.compile(r'^USER\.md$', re.IGNORECASE),
    re.compile(r'^[\w-]+_memory\.md$', re.IGNORECASE),       # 哈希命名如 3195a049_memory.md
    re.compile(r'^project_memory\.md$', re.IGNORECASE),
    re.compile(r'^feedback\.md$', re.IGNORECASE),
    re.compile(r'^MEMORY_\d{4}-\d{2}-\d{2}\.md$', re.IGNORECASE),  # 按日记忆
]

MEMORY_EXCLUDE_FILES = {'memory_main.md', 'summary_rj.md'}

# 硬性排除目录，防止误扫 skills/ 等非记忆目录
MEMORY_EXCLUDE_DIRS = {'skills', 'skills-marketplace', 'connectors', 'mcp', '.git', 'node_modules'}


def _is_memory_file(fname):
    """判断文件名是否是 memory 文件（正则精确匹配，替代关键词包含）"""
    fname_lower = fname.lower()
    if not fname_lower.endswith('.md'):
        return False
    if fname_lower in MEMORY_EXCLUDE_FILES:
        return False
    return any(p.match(fname) for p in MEMORY_FILE_PATTERNS)


def _is_excluded_dir(dirpath):
    """检查路径是否位于排除目录内（新增 M3）"""
    parts = dirpath.replace('\\', '/').lower().split('/')
    return any(excluded in parts for excluded in MEMORY_EXCLUDE_DIRS)


# 已知平台记忆目录前缀（用于 _categorize_file）
_KNOWN_PLATFORM_DIRS = (
    '/.workbuddy/memory/', '/.trae-cn/memory/', '/.cursor/memory/',
    '/.claude/memory/', '/.continue/memory/', '/.windsurf/memory/',
    '/.codeium/memory/', '/.agent/memory/',
)


def _categorize_file(fpath):
    """判断文件类别（新增 M4）

    判断顺序（关键：先精确后泛化，避免覆盖）：
    1. project_memory：文件名为 project_memory.md（先于 platform 判断，避免被平台目录吞掉）
    2. platform_memory：位于已知平台记忆目录下（.workbuddy/memory/ 等）
    3. global_user_memory：精确匹配 ~/.workbuddy/MEMORY.md 和 ~/.workbuddy/USER.md
    4. suspicious：其余匹配但不在此三类中
    """
    path_lower = fpath.replace('\\', '/').lower()
    # 1. 项目级记忆（先判断，避免被平台目录覆盖）
    if path_lower.endswith('/project_memory.md'):
        return 'project_memory'
    # 2. 已知平台记忆目录
    if any(d in path_lower for d in _KNOWN_PLATFORM_DIRS):
        return 'platform_memory'
    # 3. 全局用户记忆（精确匹配 ~/.workbuddy/MEMORY.md 和 USER.md）
    if re.search(r'/\.workbuddy/(memory|user)\.md$', path_lower):
        return 'global_user_memory'
    # 4. 其余为可疑文件
    return 'suspicious'


def _inspect_memory_file(fpath):
    """检查单个 memory 文件，返回清单条目"""
    try:
        size = os.path.getsize(fpath)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            preview = f.read(200)
        return {'path': os.path.abspath(fpath), 'size': size,
                'preview': preview, 'suggested_action': 'merge' if size > 0 else 'skip'}
    except OSError as e:
        return {'path': os.path.abspath(fpath), 'size': 0, 'preview': '',
                'error': str(e), 'suggested_action': 'skip'}


def scan_all_memory_files():
    """广扫描：扫描所有根目录下的 memory 相关文件（增加目录排除剪枝）"""
    found = []
    home = os.environ.get('USERPROFILE') or os.environ.get('HOME') or ''
    for root_pattern in MEMORY_SCAN_ROOTS:
        root = root_pattern.replace('~', home)
        if not os.path.exists(root):
            continue
        if os.path.isfile(root):
            if _is_memory_file(os.path.basename(root)):
                found.append(_inspect_memory_file(root))
        elif os.path.isdir(root):
            for dirpath, dirs, files in os.walk(root):
                # M3：剪枝——排除目录直接跳过
                if _is_excluded_dir(dirpath):
                    dirs[:] = []
                    continue
                depth = dirpath[len(root):].count(os.sep)
                if depth > 2:
                    dirs[:] = []
                    continue
                for fname in files:
                    if _is_memory_file(fname):
                        fpath = os.path.join(dirpath, fname)
                        found.append(_inspect_memory_file(fpath))
    return found


def _infer_tool_from_path(path):
    """从路径推断来源工具名"""
    path_lower = path.lower()
    tool_map = {
        'workbuddy': 'workbuddy', 'trae': 'trae', 'cursor': 'cursor',
        'claude': 'claude_code', 'continue': 'continue',
        'windsurf': 'windsurf', 'codeium': 'codeium',
        'memory_rj': 'skill_shadow',
    }
    for key, tool in tool_map.items():
        if key in path_lower:
            return tool
    return 'unknown'


def cleanup_legacy_memory(dry_run=False, interactive=True):
    """平台记忆融入技能记忆（原"外部记忆扫描清理"）

    流程：扫描 → 用户确认 → 融入（upsert_global_memory 幂等去重）→ 删除原件
    修复：
    - H2：无 tty 时返回 interactive_unavailable 状态，不静默跳过
    - M1：选 'all' 时二次确认 + 备份原件到 memory/_cleanup_backup_{timestamp}/
    - H1/M16：upsert_global_memory 已支持幂等去重（首行标题作为 key）
    修复（安全加固）：
    - M4：dry-run preview 增加 category 字段，区分平台记忆/全局用户记忆/可疑文件
    - M5：--non-interactive 只自动处理 platform_memory/project_memory/global_user_memory
    - M6：删除前校验路径不在 skills/ 等排除目录；global_user_memory 融入但不删除
    - S1：M5 confirmed 包含 global_user_memory，M6 负责跳过删除
    - S2：result 初始化新增 merged_but_kept 键
    """
    result = {'scanned': [], 'confirmed': [], 'merged': [], 'deleted': [],
              'failed': [], 'skipped': [], 'warnings': [], 'merged_but_kept': []}
    found = scan_all_memory_files()
    result['scanned'] = found
    if not found:
        return result
    if dry_run:
        # M4：dry-run preview 增加 category 字段
        result['preview'] = [
            {
                'path': f['path'],
                'tool': _infer_tool_from_path(f['path']),
                'target_section': '## 外部记忆归档',
                'will_delete': _categorize_file(f['path']) in ('platform_memory', 'project_memory'),
                'category': _categorize_file(f['path']),
                'content_preview': f.get('preview', '')[:200],
            } for f in found
        ]
        return result

    if interactive:
        # H2：无 tty 时返回特殊状态，不静默跳过
        if not sys.stdin.isatty():
            result['warnings'].append('interactive_unavailable: 无 tty，需用户在对话内确认后用 --non-interactive 重跑')
            result['interactive_available'] = False
            return result
        confirmed = _ask_user_confirm(found)
    else:
        # M5/S1：non-interactive 只处理 platform_memory/project_memory/global_user_memory
        # global_user_memory 在 M6 删除前校验中跳过删除（融入但保留）
        # suspicious 类文件不自动处理，需人工确认
        allowed_categories = ('platform_memory', 'project_memory', 'global_user_memory')
        confirmed = [
            f for f in found
            if f.get('suggested_action') == 'merge'
            and _categorize_file(f['path']) in allowed_categories
        ]
        skipped_count = len(found) - len(confirmed)
        if skipped_count > 0:
            logger.warning(
                "非交互模式跳过 %d 个 suspicious 类文件（需人工确认）",
                skipped_count
            )
    result['confirmed'] = confirmed

    # M1：删除前备份原件到 memory/_cleanup_backup_{timestamp}/
    backup_dir = None
    if confirmed:
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'memory', '_cleanup_backup_%s' % datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(backup_dir, exist_ok=True)

    for item in confirmed:
        path = item['path']
        try:
            # M6：删除前最终安全校验
            # 只用 _is_excluded_dir 做精确路径段匹配，不用 'skills' in path（会误伤项目名含 skills 的合法路径）
            if _is_excluded_dir(path):
                result['skipped'].append({
                    'path': path, 'reason': '位于排除目录，禁止删除'
                })
                continue

            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if not content.strip():
                result['skipped'].append({'path': path, 'reason': '内容为空'})
                continue
            tool_name = _infer_tool_from_path(path)
            # L7：sanitize content 中的 ### 标题行，防嵌套
            sanitized_content = '\n'.join(
                '> ' + line if line.strip().startswith('###') else line
                for line in content.split('\n')
            )
            block = "### 外部记忆归档 · %s（%s）\n来源路径：%s\n\n%s\n" % (
                tool_name, datetime.now().strftime('%Y-%m-%d %H:%M'), path, sanitized_content
            )
            memory_shadow_write.upsert_global_memory('外部记忆归档', block)

            # M6：global_user_memory 融入但不删除
            if _categorize_file(path) == 'global_user_memory':
                result['merged_but_kept'].append({
                    'path': path, 'reason': '全局用户记忆，融入但保留原件'
                })
                continue

            result['merged'].append({'path': path, 'tool': tool_name})
            # M1：删除前先备份原件
            if backup_dir:
                try:
                    backup_name = os.path.basename(path).replace(os.sep, '_')
                    shutil.copy2(path, os.path.join(backup_dir, backup_name))
                except OSError as e:
                    logger.warning("备份失败（继续删除）: %s", e)
            try:
                os.remove(path)
                result['deleted'].append({'path': path})
            except OSError as e:
                logger.warning("删除失败（已合并，需手动清理）: %s", e)
        except Exception as e:
            result['failed'].append({'path': path, 'error': str(e)})
    if backup_dir:
        result['backup_dir'] = backup_dir
    return result


def _ask_user_confirm(found_files):
    """交互式用户确认：列出扫描到的文件，让用户选择哪些合并

    M1：选 'all' 时强制二次确认（输入 DELETE ALL 全大写）
    M-2：表格增加 category 列和 action_hint 列
    """
    if not found_files:
        return []
    print("\n🔍 扫描到 %d 个 memory 文件：\n" % len(found_files))
    print("┌────┬──────────────┬──────────────────────────────────────────┬────────┬──────────────────┬──────┐")
    print("│ #  │ 来源工具     │ 路径                                     │ 大小   │ 类别             │ 操作 │")
    print("├────┼──────────────┼──────────────────────────────────────────┼────────┼──────────────────┼──────┤")
    for i, item in enumerate(found_files, 1):
        tool = _infer_tool_from_path(item['path'])
        path_short = item['path'][-40:] if len(item['path']) > 40 else item['path']
        size = '%dKB' % (item.get('size', 0) // 1024)
        category = _categorize_file(item['path'])
        action_hint = '删除' if category in ('platform_memory', 'project_memory') else '保留'
        print("│ %-3d│ %-12s │ %-40s │ %-6s │ %-16s │ %-4s │" % (
            i, tool, path_short, size, category, action_hint))
    print("└────┴──────────────┴──────────────────────────────────────────┴────────┴──────────────────┴──────┘")
    try:
        choice = input("\n要合并哪些？（输入编号如 1,3 / all 全部 / skip 都不合并）> ").strip()
    except (EOFError, KeyboardInterrupt):
        return []
    if choice.lower() == 'skip':
        return []
    if choice.lower() == 'all':
        # M1：选 all 时强制二次确认
        try:
            confirm = input("\n⚠️ 将删除所有扫描到的 memory 文件原件（已备份）。输入 DELETE ALL 确认 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("取消")
            return []
        if confirm != 'DELETE ALL':
            print("二次确认失败，跳过 all")
            return []
        return [f for f in found_files if f.get('suggested_action') == 'merge']
    try:
        indices = [int(x.strip()) for x in choice.split(',') if x.strip().isdigit()]
        return [found_files[i-1] for i in indices if 1 <= i <= len(found_files)]
    except ValueError:
        print("输入无效，跳过所有")
        return []


def force_sync_project_to_global(project_memory_dir=None):
    """强制 #3→#4 同步：扫描项目级 memory_rj 所有文件 → 逐个 upsert 到 memory_main.md

    路径解析优先级（与 write_project 对齐，修路径分裂 bug）：
      1. 显式传入 project_memory_dir
      2. primary_docs marker（.primary_docs_rj 标记，项目级 docs）
      3. user_data_path.get_memory_rj_path()（外置用户数据目录）
    """
    if project_memory_dir is None:
        # 与 write_project 同一 R3 解析链（修路径分裂 bug 第二处，v1.0.3）
        primary = generate_docs.find_docs_dir(create=False)
        external_docs = os.path.abspath(str(user_data_path.get_docs_rj_path()))
        if primary and os.path.isdir(primary) and os.path.abspath(primary) != external_docs:
            project_memory_dir = os.path.join(primary, 'memory_rj')
        else:
            logger.warning("[force_sync] R3 解析链无结果，fallback 用户目录: %s",
                           user_data_path.get_memory_rj_path())
            project_memory_dir = str(user_data_path.get_memory_rj_path())
    result = {'synced': [], 'skipped': [], 'errors': []}
    if not os.path.isdir(project_memory_dir):
        result['skipped'].append({'reason': '项目级 memory 目录不存在: %s' % project_memory_dir})
        return result
    project_name = os.path.basename(os.getcwd())
    for fname in sorted(os.listdir(project_memory_dir)):
        if not fname.endswith('.md') or fname in MEMORY_EXCLUDE_FILES:
            continue
        fpath = os.path.join(project_memory_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if content.strip():
                memory_shadow_write.upsert_global_memory(project_name, content)
                result['synced'].append({'file': fname})
        except Exception as e:
            result['errors'].append({'file': fname, 'error': str(e)})
    return result

# ---------------------------------------------------------------------------
# spec_main_rj.md 刷新（/act 阶段自动刷新 §1 指针）
# ---------------------------------------------------------------------------
def refresh_spec_main(primary=".", task_name=None, task_status=None, dry_run=False):
    """刷新 spec_main_rj.md：§1§2§7.2§7.4 自动 + §7.1§7.3 候选提取（agent 在 /act 步骤3.5a/3.5b 确认）+ §3-§6 不修改（手工维护段）。

    此函数在 /act 阶段被 handoff_tidy.py 调用，确保 spec_main 反映最新项目状态。
    - §1 指针（最新 memory / TASK_STATE / handoff）：自动刷新（已有逻辑保留）
    - §2 活跃任务表：task_name 非 None 时自动刷新（从 TASK_STATE 提取）
    - §7.1 ADR 候选：扫 memory_rj 关键词输出候选清单（agent 确认后写入）
    - §7.2 Sync Impact：检测 version 变更自动追加
    - §7.3 风险候选：扫 task_rj 关键词输出候选清单（agent 确认后写入）
    - §7.4 跨任务依赖：扫 task_rj 自动提取 depends_on/blocks

    返回 dict: {updated: bool, sections: list[str], error: str|None,
                adr_candidates: list, risk_candidates: list}
    """
    result = {"updated": False, "sections": [], "error": None,
              "adr_candidates": [], "risk_candidates": []}
    # task_name 空字符串当 None 处理（向后兼容）
    if task_name is not None and not task_name.strip():
        task_name = None
    spec_main_path = os.path.join(primary, "spec_main_rj.md")
    # 兼容 spec_main_rj.md 在 spec_rj/ 子目录的情况
    if not os.path.isfile(spec_main_path):
        spec_rj_candidate = os.path.join(primary, "spec_rj", "spec_main_rj.md")
        if os.path.isfile(spec_rj_candidate):
            spec_main_path = spec_rj_candidate
    if not os.path.isfile(spec_main_path):
        result["error"] = "spec_main_rj.md 不存在于 %s 或 %s/spec_rj/" % (primary, primary)
        return result

    try:
        with open(spec_main_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        result["error"] = "读取 spec_main_rj.md 失败: %s" % e
        return result

    memory_dir = os.path.join(primary, "memory_rj")
    handoff_dir = os.path.join(primary, "handoff_rj")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1. 扫描最新 memory 文件（按时间戳排序）
    latest_memory_files = []
    if os.path.isdir(memory_dir):
        mem_files = sorted(
            [f for f in os.listdir(memory_dir) if f.endswith(".md") and not f.startswith("TASK_STATE")],
            reverse=True
        )
        latest_memory_files = mem_files[:2]  # 取最新 2 条

    # 2. 扫描最新 TASK_STATE
    latest_task_state = None
    if os.path.isdir(memory_dir):
        ts_files = sorted(
            [f for f in os.listdir(memory_dir) if f.startswith("TASK_STATE_")],
            reverse=True
        )
        latest_task_state = ts_files[0] if ts_files else None

    # 3. 扫描最新 handoff
    latest_handoff = None
    if os.path.isdir(handoff_dir):
        hf_files = sorted(
            [f for f in os.listdir(handoff_dir) if f.endswith(".md")],
            reverse=True
        )
        latest_handoff = hf_files[0] if hf_files else None

    # 4. 更新 frontmatter last_updated
    content = re.sub(
        r"last_updated:\s*[\d\-: ]+",
        "last_updated: %s" % now,
        content
    )

    # 5. 更新 §1 最新项目记忆
    if latest_memory_files:
        mem_section_start = content.find("**最新项目记忆**：")
        mem_section_end = content.find("**最新任务状态**：")
        if mem_section_start >= 0 and mem_section_end > mem_section_start:
            new_mem_lines = ["**最新项目记忆**："]
            for fname in latest_memory_files:
                fpath = os.path.join("memory_rj", fname)
                summary = ""
                try:
                    with open(os.path.join(primary, "memory_rj", fname), "r", encoding="utf-8") as mf:
                        for line in mf:
                            stripped = line.strip()
                            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                                summary = stripped[:80]
                                break
                except Exception:
                    pass
                ts_match = re.search(r"(\d{8})_(\d{4})", fname)
                ts_str = ""
                if ts_match:
                    try:
                        d = ts_match.group(1)
                        t = ts_match.group(2)
                        ts_str = "%s-%s-%s %s:%s" % (d[:4], d[4:6], d[6:8], t[:2], t[2:4])
                    except Exception:
                        ts_str = ""
                new_mem_lines.append(
                    "- [%s](./%s)%s" % (fname, fpath, ("（%s，%s）" % (ts_str, summary)) if ts_str else "")
                )
            new_mem_block = "\n".join(new_mem_lines) + "\n"
            content = content[:mem_section_start] + new_mem_block + content[mem_section_end:]
            result["sections"].append("§1 最新项目记忆")
        else:
            result["error"] = (result.get("error") or "") + "; §1 最新项目记忆段未找到标记（**最新项目记忆**：或**最新任务状态**：缺失）"

    # 6. 更新 §1 最新任务状态
    if latest_task_state:
        ts_start = content.find("**最新任务状态**：")
        ts_end = content.find("**最近交接文档**：")
        if ts_start >= 0 and ts_end > ts_start:
            new_ts = "**最新任务状态**：\n- [%s](./memory_rj/%s)（当前最新任务状态）\n" % (latest_task_state, latest_task_state)
            content = content[:ts_start] + new_ts + content[ts_end:]
            result["sections"].append("§1 最新任务状态")

    # 7. 更新 §1 最近交接文档
    if latest_handoff:
        hf_start = content.find("**最近交接文档**：")
        hf_end = content.find("**全局聚合记忆**：")
        if hf_start >= 0 and hf_end > hf_start:
            new_hf = "**最近交接文档**：\n- [%s](./handoff_rj/%s)（最新 handoff 文档）\n" % (latest_handoff, latest_handoff)
            content = content[:hf_start] + new_hf + content[hf_end:]
            result["sections"].append("§1 最近交接文档")

    # 8-12. §2/§7.x 刷新（task_name 非 None 时执行；task_name=None 时只刷 §1，向后兼容 AC-013）
    if task_name:
        # §2 活跃任务表自动刷新
        new_content = _refresh_section2(content, primary, task_name, task_status, result)
        if new_content is not None:
            content = new_content

        # §7.1 ADR 候选提取（输出到 result.adr_candidates，不写入表格）
        _extract_adr_candidates(primary, result)

        # §7.2 Sync Impact Report 自动追加
        new_content = _refresh_section7_2(content, primary, result)
        if new_content is not None:
            content = new_content

        # §7.3 风险候选提取（输出到 result.risk_candidates，不写入表格）
        _extract_risk_candidates(primary, result)

        # §7.4 跨任务依赖自动提取
        new_content = _refresh_section7_4(content, primary, result)
        if new_content is not None:
            content = new_content

    if result["sections"]:
        result["updated"] = True

    if dry_run:
        result["dry_run"] = True
        return result

    # 写入
    try:
        with open(spec_main_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        result["error"] = "写入 spec_main_rj.md 失败: %s" % e
        return result

    return result


# ---------------------------------------------------------------------------
# spec_main §2/§7 刷新子函数（/act 阶段自动刷新）
# ---------------------------------------------------------------------------

def _refresh_section2(content, primary, task_name, task_status, result):
    """§2 活跃任务表：从 TASK_STATE 提取 task 名+状态，更新表格，>5行归档最老。

    表格表头：| 任务名 | 状态 | 派生自 | TASK_STATE | 最近更新 |
    若表格不存在（空骨架），自动创建表头+插入行（选项B 健壮性设计）。
    返回更新后的 content；异常路径返回 None（调用方用 `or content` 回退）。
    """
    memory_dir = os.path.join(primary, "memory_rj")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1. 从 TASK_STATE 文件提取 status（若 task_status 已传则用传入值）
    actual_status = task_status or "unknown"
    if not task_status:
        ts_files = sorted(glob.glob(os.path.join(memory_dir, "TASK_STATE_*.md")), reverse=True)
        if ts_files:
            try:
                with open(ts_files[0], "r", encoding="utf-8") as f:
                    ts_content = f.read()
                status_match = re.search(r"status:\s*(\w+)", ts_content)
                if status_match:
                    actual_status = status_match.group(1)
            except Exception:
                pass

    # 2. 定位 §2 表格（表头：| 任务名 | 状态 |）
    table_header = "| 任务名 |"
    table_start = content.find(table_header)

    # 3. 表格不存在 → 跳过 §2+告警（AC-017 修复：贴合 spec"空骨架跳过+告警，不报错"）
    #    spec §3 前置条件：spec_main 必须先 Bootstrap 填充章节结构，刷新逻辑不负责创建章节/表头
    if table_start < 0:
        result["error"] = (result.get("error") or "") + "; §2 表格不存在（spec_main 未 Bootstrap 填充章节结构），跳过 §2 刷新"
        return None

    # 4. 表格存在 → 找表格结束位置（第一个空行）
    table_end = content.find("\n\n", table_start)
    if table_end < 0:
        table_end = len(content)

    table_block = content[table_start:table_end]
    table_lines = table_block.split("\n")

    new_row = "| %s | %s | spec_main_rj.md §6 | [TASK_STATE_%s.md](./memory_rj/TASK_STATE_%s.md) | %s |" % (
        task_name, actual_status, task_name, task_name, now)

    # 5. 找同 task_name 行：存在→更新；不存在→第一行插入
    found = False
    for i, line in enumerate(table_lines):
        if line.startswith("| %s |" % task_name):
            table_lines[i] = new_row
            found = True
            break
    if not found:
        if len(table_lines) >= 2:
            table_lines.insert(2, new_row)
        else:
            table_lines.append(new_row)

    # 6. >5 行 → 移除"最近更新"最老的一行
    data_lines = [l for l in table_lines if l.startswith("| ") and "任务名" not in l and "---" not in l]
    if len(data_lines) > 5:
        try:
            data_lines.sort(key=lambda x: x.split("|")[-2].strip(), reverse=True)
            data_lines = data_lines[:5]
        except Exception:
            pass
        table_lines = [table_lines[0], table_lines[1]] + data_lines

    new_table = "\n".join(table_lines)
    content = content[:table_start] + new_table + content[table_end:]
    result["sections"].append("§2 活跃任务")
    return content


def _extract_adr_candidates(primary, result):
    """§7.1 ADR 候选：扫 memory_rj 关键词，输出候选清单（不写入表格，agent 确认后写入）。

    关键词：关键决策|ADR|决策|决定|约定|不可逆
    去重：同关键词只取第一条（seen_keywords set）
    候选清单≤5 条，每条含 keyword/context/source_file/line_no。
    """
    memory_dir = os.path.join(primary, "memory_rj")
    mem_files = sorted(glob.glob(os.path.join(memory_dir, "*_memory_*.md")), reverse=True)[:2]
    keywords = r"关键决策|ADR|决策|决定|约定|不可逆"
    candidates = []
    seen_keywords = set()
    for mf in mem_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                m = re.search(keywords, line)
                if m:
                    kw = m.group()
                    if kw in seen_keywords:
                        continue
                    seen_keywords.add(kw)
                    context = "".join(lines[max(0, i - 2):i + 3]).strip()
                    candidates.append({
                        "keyword": kw,
                        "context": context[:200],
                        "source_file": os.path.basename(mf),
                        "line_no": i + 1
                    })
                    if len(candidates) >= 5:
                        break
            if len(candidates) >= 5:
                break
        except Exception:
            continue
    result["adr_candidates"] = candidates


def _refresh_section7_2(content, primary, result):
    """§7.2 Sync Impact：检测 spec_main frontmatter version 变更自动追加。

    表头：| 修订日期 | 版本变更 | 修改项 | 下游影响 | 状态 |
    若表格不存在，自动创建表头+追加行（选项B）。
    version cache 存 memory_rj/.spec_main_version_cache。
    返回更新后的 content；异常路径返回 None。
    """
    version_match = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
    if not version_match:
        return None
    current_version = version_match.group(1).strip()

    cache_path = os.path.join(primary, "memory_rj", ".spec_main_version_cache")
    old_version = None
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                old_version = f.read().strip()
        except Exception:
            pass

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_row = None
    if old_version and old_version != current_version:
        new_row = "| %s | %s→%s | 自动检测 | spec_main frontmatter | ⚠待agent确认 |" % (
            now, old_version, current_version)

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(current_version)
    except Exception:
        result["error"] = (result.get("error") or "") + "; §7.2 cache 写入失败"

    if not new_row:
        return None

    table_header = "| 修订日期 | 版本变更 |"
    table_start = content.find(table_header)

    if table_start < 0:
        sec7_2_start = content.find("### §7.2")
        if sec7_2_start < 0:
            # §7.2 章节不存在 → 在文件末尾追加整个 §7.2 章节（空骨架自动 Bootstrap）
            sec7_2_section = (
                "\n\n### §7.2 Sync Impact Report（同步影响报告）\n\n"
                "| 修订日期 | 版本变更 | 修改项 | 下游影响 | 状态 |\n"
                "|---|---|---|---|---|\n"
                + new_row + "\n"
            )
            content = content.rstrip() + sec7_2_section
            result["sections"].append("§7.2 Sync Impact")
            return content
        sec7_2_end = content.find("### §7.3", sec7_2_start)
        if sec7_2_end < 0:
            sec7_2_end = content.find("\n---", sec7_2_start)
        if sec7_2_end < 0:
            sec7_2_end = len(content)
        new_table = (
            "\n\n| 修订日期 | 版本变更 | 修改项 | 下游影响 | 状态 |\n"
            "|---|---|---|---|---|\n"
            + new_row + "\n"
        )
        content = content[:sec7_2_end] + new_table + content[sec7_2_end:]
        result["sections"].append("§7.2 Sync Impact")
        return content

    table_end = content.find("\n\n", table_start)
    if table_end < 0:
        table_end = len(content)
    content = content[:table_end] + new_row + "\n" + content[table_end:]
    result["sections"].append("§7.2 Sync Impact")
    return content


def _extract_risk_candidates(primary, result):
    """§7.3 风险候选：扫 task_rj 关键词，输出候选清单（不写入表格，agent 确认后写入）。

    关键词：风险|影响|概率|缓解
    去重：同关键词只取第一条（seen_keywords set）
    候选清单≤5 条。
    """
    task_dir = os.path.join(primary, "task_rj")
    task_files = sorted(glob.glob(os.path.join(task_dir, "*_task_*.md")), reverse=True)[:2]
    keywords = r"风险|影响|概率|缓解"
    candidates = []
    seen_keywords = set()
    for tf in task_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                m = re.search(keywords, line)
                if m:
                    kw = m.group()
                    if kw in seen_keywords:
                        continue
                    seen_keywords.add(kw)
                    context = "".join(lines[max(0, i - 2):i + 3]).strip()
                    candidates.append({
                        "keyword": kw,
                        "context": context[:200],
                        "source_file": os.path.basename(tf),
                        "line_no": i + 1
                    })
                    if len(candidates) >= 5:
                        break
            if len(candidates) >= 5:
                break
        except Exception:
            continue
    result["risk_candidates"] = candidates


def _refresh_section7_4(content, primary, result):
    """§7.4 跨任务依赖：扫 task_rj 提 depends_on/blocks 自动写入表格。

    表头：| 上游任务 | 下游任务 | 依赖类型 | 产出物 | 状态 | 最近更新 |
    若表格不存在，自动创建表头+插入行（选项B）。
    返回更新后的 content；异常路径返回 None。
    """
    task_dir = os.path.join(primary, "task_rj")
    task_files = glob.glob(os.path.join(task_dir, "*_task_*.md"))
    relations = []
    seen_relations = set()  # 去重：同 (upstream, downstream, rel_type) 只保留一条
    for tf in task_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                tcontent = f.read()
            basename = os.path.basename(tf)
            task_name = basename.rsplit('_task_', 1)[0]  # 只剥离最后一个 _task_时间戳.md
            # 限定只匹配 frontmatter（--- 之间），避免误匹配 docstring 示例（如 task.md T006 验证步骤里的 `depends_on: spec_main_setup`）
            # 用户声明依赖应在 frontmatter 写 depends_on/blocks 字段，不在 docstring 写示例
            fm_match = re.search(r"^---\n(.*?)\n---", tcontent, re.DOTALL | re.MULTILINE)
            if not fm_match:
                continue
            fm_content = fm_match.group(1)
            for match in re.finditer(r"^(depends_on|blocks|related|依赖|阻塞)[:\s]+([a-zA-Z0-9_]+)", fm_content, re.MULTILINE):
                rel_type = match.group(1)
                target = match.group(2)
                key = (task_name, target, rel_type)
                if key in seen_relations:
                    continue
                seen_relations.add(key)
                relations.append((task_name, target, rel_type))
        except Exception:
            continue

    if not relations:
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_rows = []
    for upstream, downstream, rel_type in relations:
        new_row = "| %s | %s | %s | 自动提取 | ✅已完成 | %s |" % (
            upstream, downstream, rel_type, now)
        new_rows.append(new_row)
    new_rows_str = "\n".join(new_rows) + "\n"

    table_header = "| 上游任务 | 下游任务 |"
    table_start = content.find(table_header)

    if table_start < 0:
        sec7_4_start = content.find("### §7.4")
        if sec7_4_start < 0:
            # §7.4 章节不存在 → 在文件末尾追加整个 §7.4 章节（空骨架自动 Bootstrap）
            sec7_4_section = (
                "\n\n### §7.4 跨任务依赖管理\n\n"
                "| 上游任务 | 下游任务 | 依赖类型 | 产出物 | 状态 | 最近更新 |\n"
                "|---|---|---|---|---|---|\n"
                + new_rows_str
            )
            content = content.rstrip() + sec7_4_section
            result["sections"].append("§7.4 跨任务依赖")
            return content
        sec7_4_end = content.find("\n---", sec7_4_start)
        if sec7_4_end < 0:
            sec7_4_end = len(content)
        new_table = (
            "\n\n| 上游任务 | 下游任务 | 依赖类型 | 产出物 | 状态 | 最近更新 |\n"
            "|---|---|---|---|---|---|\n"
            + new_rows_str
        )
        content = content[:sec7_4_end] + new_table + content[sec7_4_end:]
        result["sections"].append("§7.4 跨任务依赖")
        return content

    table_end = content.find("\n\n", table_start)
    if table_end < 0:
        table_end = len(content)
    existing_block = content[table_start:table_end]
    rows_to_add = []
    for upstream, downstream, rel_type in relations:
        new_row = "| %s | %s | %s | 自动提取 | ✅已完成 | %s |" % (
            upstream, downstream, rel_type, now)
        pattern = r"\| %s \| %s \| %s \|" % (re.escape(upstream), re.escape(downstream), re.escape(rel_type))
        if re.search(pattern, existing_block):
            existing_block = re.sub(
                r"(\| %s \| %s \| %s \| 自动提取 \| ✅已完成 \| )[\d\-: ]+(\|)" % (
                    re.escape(upstream), re.escape(downstream), re.escape(rel_type)),
                r"\g<1>%s\g<2>" % now,
                existing_block
            )
        else:
            rows_to_add.append(new_row)
    if rows_to_add:
        content = content[:table_start] + existing_block.rstrip() + "\n" + "\n".join(rows_to_add) + "\n" + content[table_end:]
    else:
        content = content[:table_start] + existing_block + content[table_end:]
    result["sections"].append("§7.4 跨任务依赖")
    return content


# ===========================================================================
# 文档时效标注（/act 整理 docs 时调用）
# - _group_by_task_prefix: 按任务前缀分组 .md 文件
# - _classify_file_status: 判定 active/superseded 状态
# ===========================================================================

# 任务文件名模式：{task_prefix}_{type}_{timestamp}.md
# 如 server_lite_v2_spec_20260722_2345.md
# 如 learn_cycle_20260723_memory_20260723_1114.md
# 如 fix_docs_project_click_task_20260723_1358.md
# 如 fix_docs_project_click_archive_20260723_1358.md
# 类型词: spec / task / memory / handoff / archive
_TASK_FILE_RE = re.compile(
    r'^([a-z0-9_]+?)_(spec|task|memory|handoff|archive)_(\d{8}_\d{4}|memory)\.md$',
    re.IGNORECASE
)

# 跳过分组的特殊文件（项目级常驻 / 根索引）
_SPECIAL_FILES_SKIP_GROUP = {
    'spec_main_rj.md',        # 项目总 spec，永远 active
    'SUMMARY_RJ.md',          # 根索引，永远 active
}

# TASK_STATE_*.md 状态文件前缀
_TASK_STATE_PREFIX = 'TASK_STATE_'


def _group_by_task_prefix(file_list):
    """按"任务前缀 + 文件类型"联合分组 .md 文件。

    修复（v1.0.1）：原仅按 task_prefix 分组，导致同任务同时间戳的 spec/task
    互相淘汰（如 server_lite_v2_spec_20260722_2345 vs server_lite_v2_task_20260722_2345
    时间戳相同，被算法判 superseded）。现按 (task_prefix, type) 联合分组，
    只让同任务同类型的多版本互相淘汰（这才是"版本"语义）。

    规则：
    - spec_main_rj.md / SUMMARY_RJ.md：跳过分组，单文件一组（active）
    - TASK_STATE_*.md：状态文件，单文件一组（active）
    - {task}_{type}_{ts}.md：按 (task_prefix, type) 联合分组
    - 其余孤儿文件：单文件一组（active，保守不误判）

    Args:
        file_list: 文件名 list（不含目录路径）

    Returns:
        dict: {group_key: [filename, ...]}，group_key 取值：
        - 'SPECIAL:{filename}' 特殊单文件
        - 'TASK_STATE:{filename}' 状态文件
        - 'TASK:{task_prefix}_{type}' 同任务同类型组
        - 'ORPHAN:{filename}' 孤儿文件
    """
    groups = {}
    for fname in file_list:
        if not fname.endswith('.md'):
            continue
        if fname in _SPECIAL_FILES_SKIP_GROUP:
            groups.setdefault('SPECIAL:%s' % fname, []).append(fname)
            continue
        if fname.startswith(_TASK_STATE_PREFIX):
            groups.setdefault('TASK_STATE:%s' % fname, []).append(fname)
            continue
        m = _TASK_FILE_RE.match(fname)
        if m:
            task_prefix = m.group(1)
            file_type = m.group(2)
            groups.setdefault('TASK:%s_%s' % (task_prefix, file_type), []).append(fname)
        else:
            groups.setdefault('ORPHAN:%s' % fname, []).append(fname)
    return groups


def _parse_file_timestamp(filename):
    """从文件名解析时间戳（YYYYMMDD_HHMM → datetime）。

    支持格式：
    - {task}_{type}_YYYYMMDD_HHMM.md → datetime
    - {task}_{type}_memory.md → None（无时间戳兜底文件）
    - 其余无时间戳 → None
    """
    m = _TASK_FILE_RE.match(filename)
    if not m:
        return None
    ts_str = m.group(3)
    if ts_str == 'memory':
        return None
    try:
        return datetime.strptime(ts_str, '%Y%m%d_%H%M')
    except ValueError:
        return None


def _classify_file_status(file_list):
    """判定每个文件的 active/superseded 状态。

    规则：
    - SPECIAL:* / TASK_STATE:* / ORPHAN:* → active（保守，不误埋）
    - TASK:{prefix} 组内：
      * 按时间戳降序排序
      * 最新 = active
      * 其余 = superseded
      * 无时间戳文件 = active（如 {task}_memory.md，不与有时间戳的互斥）

    Args:
        file_list: 文件名 list

    Returns:
        dict: {filename: {
            'status': 'active'/'superseded',
            'group': str,
            'task_prefix': str|None,
            'timestamp': datetime|None,
        }}
    """
    groups = _group_by_task_prefix(file_list)
    result = {}
    for group_key, files in groups.items():
        if group_key.startswith(('SPECIAL:', 'TASK_STATE:', 'ORPHAN:')):
            for fname in files:
                ts = _parse_file_timestamp(fname)
                result[fname] = {
                    'status': 'active',
                    'group': group_key,
                    'task_prefix': None,
                    'timestamp': ts,
                }
            continue

        # TASK: 组内按时间戳降序
        # group_key 形如 TASK:server_lite_v2_spec，拆出 task_prefix（去掉 _type 后缀）
        key_body = group_key[len('TASK:'):]
        type_match = re.match(r'^(.+)_(spec|task|memory|handoff)$', key_body)
        if type_match:
            task_prefix = type_match.group(1)
        else:
            task_prefix = key_body  # 兜底（不应到达）
        with_ts = []
        without_ts = []
        for fname in files:
            ts = _parse_file_timestamp(fname)
            if ts:
                with_ts.append((fname, ts))
            else:
                without_ts.append((fname, ts))

        with_ts.sort(key=lambda x: x[1], reverse=True)
        for i, (fname, ts) in enumerate(with_ts):
            result[fname] = {
                'status': 'active' if i == 0 else 'superseded',
                'group': group_key,
                'task_prefix': task_prefix,
                'timestamp': ts,
            }
        # 无时间戳的保守标 active（不与有时间戳的同组互斥，避免误埋兜底文件）
        for fname, ts in without_ts:
            result[fname] = {
                'status': 'active',
                'group': group_key,
                'task_prefix': task_prefix,
                'timestamp': None,
            }

    return result


# ===========================================================================
# 全局记忆结构 + 共享读
# - read_text: 给 route_check/protocol_align 共享的纯读函数
# - ensure_global_structure: 建 memory/ + memory_main.md + docs_rj/memory_rj/
# - upsert_global_memory: task+timestamp 双 key 去重 upsert (自实现版)
#   注: memory_shadow_write.py 已有同名函数但接口不兼容 (见函数 docstring)
# ===========================================================================

def read_text(path):
    """读取文件文本内容(编码 utf-8,errors='ignore')。

    失败返回 None,不抛异常。
    给 route_check/protocol_align 共享。
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return None


def ensure_global_structure(skill_root):
    """确保全局记忆结构存在(memory/ + memory_main.md + docs_rj/memory_rj/)。

    返回 dict:created/existed/errors 列表。
    """
    created = []
    existed = []
    errors = []

    # memory/ 目录
    mem_dir = os.path.join(skill_root, 'memory')
    if os.path.isdir(mem_dir):
        existed.append('memory/')
    else:
        try:
            os.makedirs(mem_dir, exist_ok=True)
            created.append('memory/')
        except Exception as e:
            errors.append('memory/: %s' % e)

    # memory/memory_main.md
    mem_main = os.path.join(mem_dir, 'memory_main.md')
    if os.path.isfile(mem_main):
        existed.append('memory/memory_main.md')
    else:
        try:
            with open(mem_main, 'w', encoding='utf-8') as f:
                f.write('# 全局聚合记忆\n\n> ⚠️ 仅供参考,以你当前指令为准\n\n')
            created.append('memory/memory_main.md')
        except Exception as e:
            errors.append('memory/memory_main.md: %s' % e)

    # docs_rj/memory_rj/ 目录
    mem_rj_dir = os.path.join(skill_root, 'docs_rj', 'memory_rj')
    if os.path.isdir(mem_rj_dir):
        existed.append('docs_rj/memory_rj/')
    else:
        try:
            os.makedirs(mem_rj_dir, exist_ok=True)
            created.append('docs_rj/memory_rj/')
        except Exception as e:
            errors.append('docs_rj/memory_rj/: %s' % e)

    return {'created': created, 'existed': existed, 'errors': errors}


def upsert_global_memory(skill_root, task, content, timestamp=None):
    """task+timestamp 双 key 去重 upsert 到 {skill_root}/memory/memory_main.md。

    对齐 H1 修复后的逻辑(按 task 去重,timestamp 仅作展示)。

    与 memory_shadow_write.upsert_global_memory 的关系:
    - memory_shadow_write.py 行 154 已有 upsert_global_memory(project_name, block),
      但接口与本函数不兼容:
        * 签名: memory_shadow_write 版接 (project_name, block),block 是预组装字符串
        * 返回: memory_shadow_write 版无返回值,本函数返回 {'action': ...}
        * 格式: memory_shadow_write 版用 `### 记忆条目 · {task}（{stamp}）`,
                本函数按任务要求用 `### {task}（{timestamp}）`
        * skill_root: memory_shadow_write 版固定 _SKILL_DIR,本函数接受参数
    - 因此本函数按任务描述自实现,不调用 memory_shadow_write 版本。
      如需统一调用 memory_shadow_write 版,需先对齐接口(待用户确认)。

    Args:
        skill_root: skill 包根目录(全局 memory/ 在其下)。
        task: 任务名(作为段标题 key)。
        content: 记忆内容文本。
        timestamp: 时间戳字符串(YYYY-MM-DD HH:MM);None 取当前时间。

    Returns:
        dict: {'action': 'inserted'/'updated'/'error', 'detail': str}
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    mem_dir = os.path.join(skill_root, 'memory')
    mem_main = os.path.join(mem_dir, 'memory_main.md')

    # 确保目录存在
    try:
        os.makedirs(mem_dir, exist_ok=True)
    except Exception as e:
        return {'action': 'error', 'detail': 'mkdir memory/ failed: %s' % e}

    # 读现有内容(不存在则用标准头初始化)
    existing = ''
    if os.path.isfile(mem_main):
        existing = read_text(mem_main)
        if existing is None:
            return {'action': 'error', 'detail': 'read memory_main.md failed'}
    else:
        existing = '# 全局聚合记忆\n\n> ⚠️ 仅供参考,以你当前指令为准\n\n'

    # 组装新 block
    block_header = '### %s（%s）' % (task, timestamp)
    new_block = block_header + '\n' + (content or '').rstrip() + '\n'

    lines = existing.split('\n')

    # 找已有同 task 段(任意 timestamp):格式 `### {task}（{ts}）`
    pattern = re.compile(r'^### %s（[^）]*）\s*$' % re.escape(task))

    replace_idx = None
    block_end = None
    for i, ln in enumerate(lines):
        if pattern.match(ln.strip()):
            replace_idx = i
            block_end = i + 1
            while block_end < len(lines):
                nxt = lines[block_end].strip()
                if nxt.startswith('### ') or nxt.startswith('## '):
                    break
                block_end += 1
            break

    if replace_idx is not None:
        # 替换该段
        new_lines = new_block.split('\n')
        lines[replace_idx:block_end] = new_lines
        action = 'updated'
    else:
        # 追加(确保与前文有空行分隔)
        if lines and lines[-1].strip():
            lines.append('')
        for nl in new_block.split('\n'):
            lines.append(nl)
        action = 'inserted'

    # 写回
    try:
        with open(mem_main, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    except Exception as e:
        return {'action': 'error', 'detail': 'write memory_main.md failed: %s' % e}

    return {'action': action, 'detail': 'task=%s, timestamp=%s' % (task, timestamp)}

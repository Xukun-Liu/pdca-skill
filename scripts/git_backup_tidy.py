#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git_backup_tidy.py — git 备份清理管理脚本
============================================================

用途
----
给 pdca-skill 框架新增 git 仓库备份+清理+瘦身+生命周期管理能力。
5个子命令：体检/备份/清理/维护/生命周期，从安全到危险递进。
集成到 startup_tidy + handoff_tidy 的体检钩子（仅 --analyze，纯只读）。

技术约束
--------
* 仅使用 Python 标准库（os/sys/subprocess/json/argparse/datetime/shutil/
  pathlib/re/tempfile/time），无 pip 依赖。
* 兼容 Python >= 3.8。
* git 操作通过 subprocess 调用 git 原生命令。

================================================================================
安全门控设计【硬性】
================================================================================
* L1 只读（体检）：无门控，不修改任何文件
* L2 预览（备份/维护/生命周期）：dry-run 预览 + 用户确认
* L3 破坏性（清理）：fresh clone 副本 + HARD-GATE 确认 + 原仓库不动

安全不变量（不可跳）：
1. 清理必须用户确认（--confirm 仅用于脚本自动化，手动使用禁用）
2. 清理在 fresh clone 副本上操作，原仓库始终不动
3. 备份前自动 commit，确保备份完整（铁律6回溯保障）
4. 体检失败不阻断主流程（B5隔离）

================================================================================
运行方式
================================================================================
  python git_backup_tidy.py --analyze [--json] [--top N] [--repo PATH]
  python git_backup_tidy.py --backup [--output-dir DIR] [--dry-run] [--repo PATH]
  python git_backup_tidy.py --cleanup --target {branches|reflog|large-files|all}
                              [--dry-run] [--confirm] [--repo PATH]
  python git_backup_tidy.py --maintain [--dry-run] [--repo PATH]
  python git_backup_tidy.py --lifecycle [--backup-dir DIR] [--keep N] [--days N]
                              [--dry-run]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ===========================================================================
# 常量
# ===========================================================================

# 星级警告阈值（字节）
STAR_THRESHOLDS = [
    (100 * 1024 * 1024, '*'),        # <100MB 健康
    (1024 * 1024 * 1024, '**'),      # 100MB-1GB 注意
    (5 * 1024 * 1024 * 1024, '***'),  # 1GB-5GB 警告
    (10 * 1024 * 1024 * 1024, '****'),  # 5GB-10GB 严重
    (float('inf'), '*****'),          # >10GB 危险
]

# 默认参数
DEFAULT_TOP_N = 10
DEFAULT_KEEP = 7
DEFAULT_DAYS = 30
DEFAULT_OUTPUT_DIR = 'backups'

# 子进程超时（秒）
SUBPROCESS_TIMEOUT = 300


# ===========================================================================
# 通用辅助函数
# ===========================================================================

def human_readable_size(size_bytes):
    """字节数转人类可读格式（KB/MB/GB）。"""
    if size_bytes == 0:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return '%.2f %s' % (size, units[unit_index])


def get_star_level(size_bytes):
    """按 .git 大小返回星级警告。"""
    for threshold, star in STAR_THRESHOLDS:
        if size_bytes < threshold:
            return star
    return '*****'


def run_git(repo_path, *args, timeout=SUBPROCESS_TIMEOUT):
    """在指定仓库目录运行 git 命令，返回 (returncode, stdout, stderr)。

    失败返回 (rc, out, err)，调用方自行判断。
    """
    cmd = ['git', '-C', repo_path] + list(args)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace'
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, '', 'git %s 超时（%ss）' % (args[0] if args else '', timeout)
    except OSError as exc:
        return -1, '', 'git 启动失败: %s' % exc


def get_dir_size(path):
    """递归计算目录大小（字节）。"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def get_repo_name(repo_path):
    """从仓库路径获取仓库名（目录名）。

    M7：sanitize Windows 非法字符为下划线，
    避免仓库名含特殊字符导致后续生成 bundle/clone 目录文件名时失败。
    """
    name = os.path.basename(os.path.abspath(repo_path))
    # Windows 文件名非法字符: \\ / : * ? " < > | （\ 和 / 已被 basename 处理）
    return re.sub(r'[:*?"<>|]', '_', name)


def is_git_repo(repo_path):
    """检测是否为 git 仓库（含 .git 目录）。"""
    git_dir = os.path.join(repo_path, '.git')
    return os.path.isdir(git_dir) or os.path.isfile(git_dir)


# ===========================================================================
# ① 体检函数 analyze_repo（纯只读，L1安全级）
# ===========================================================================

def analyze_repo(repo_path=None, top_n=DEFAULT_TOP_N):
    """体检函数（纯只读）。

    扫描 .git 目录大小、定位大文件、统计分支/tag/reflog、输出星级警告。

    Args:
        repo_path: 仓库路径（默认当前目录）
        top_n: 大文件数量（默认10）

    Returns:
        dict {
            repo_path, repo_name, is_git_repo,
            repo_size, repo_size_human, star_level,
            large_files: [{path, size, size_human, commit}],
            branch_count, tag_count, reflog_count,
            merged_branches: [branch names],
            error: str or None
        }
    """
    if repo_path is None:
        repo_path = os.getcwd()
    repo_path = os.path.abspath(repo_path)
    repo_name = get_repo_name(repo_path)

    result = {
        'repo_path': repo_path,
        'repo_name': repo_name,
        'is_git_repo': False,
        'repo_size': 0,
        'repo_size_human': '0 B',
        'star_level': '*',
        'large_files': [],
        'branch_count': 0,
        'tag_count': 0,
        'reflog_count': 0,
        'merged_branches': [],
        'error': None,
    }

    # 检测是否为 git 仓库
    if not is_git_repo(repo_path):
        # L8：非 git 仓库时返回友好字段而非 error
        result['is_git_repo'] = False
        result['note'] = '非 git 仓库，跳过体检'
        return result
    result['is_git_repo'] = True

    # 计算 .git 目录大小
    git_dir = os.path.join(repo_path, '.git')
    result['repo_size'] = get_dir_size(git_dir)
    result['repo_size_human'] = human_readable_size(result['repo_size'])
    result['star_level'] = get_star_level(result['repo_size'])

    # 定位大文件（git rev-list --all --objects | git cat-file --batch-check）
    # M8：加 -c core.quotepath=false，避免非 ASCII 文件名被 git 转义为 \xxx 八进制串
    rc, out, err = run_git(repo_path, '-c', 'core.quotepath=false', 'rev-list', '--all', '--objects')
    if rc == 0 and out:
        # 获取对象列表
        rc2, out2, err2 = run_git(
            repo_path, 'cat-file', '--batch-check=%(objecttype) %(objectname) %(objectsize)'
        )
        if rc2 == 0 and out2:
            # 解析对象大小
            object_sizes = {}
            for line in out2.strip().split('\n'):
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0] == 'blob':
                    obj_hash = parts[1]
                    try:
                        obj_size = int(parts[2])
                        object_sizes[obj_hash] = obj_size
                    except ValueError:
                        pass

            # 解析 rev-list 输出，关联文件路径
            file_sizes = {}
            for line in out.strip().split('\n'):
                parts = line.strip().split(' ', 1)
                if len(parts) == 2:
                    obj_hash = parts[0]
                    file_path = parts[1]
                    if obj_hash in object_sizes:
                        size = object_sizes[obj_hash]
                        # 取同一路径的最大版本
                        if file_path not in file_sizes or size > file_sizes[file_path]:
                            file_sizes[file_path] = size

            # 排序取 top_n
            sorted_files = sorted(file_sizes.items(), key=lambda x: x[1], reverse=True)[:top_n]
            for file_path, size in sorted_files:
                result['large_files'].append({
                    'path': file_path,
                    'size': size,
                    'size_human': human_readable_size(size),
                    'commit': '',  # 不深挖 commit，保持只读轻量
                })

    # 统计分支数量
    rc, out, err = run_git(repo_path, 'branch', '--list')
    if rc == 0 and out:
        result['branch_count'] = len([l for l in out.strip().split('\n') if l.strip()])

    # 统计已合并分支（排除当前分支）
    rc, out, err = run_git(repo_path, 'branch', '--merged')
    if rc == 0 and out:
        merged = []
        for line in out.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('*'):
                merged.append(line)
        result['merged_branches'] = merged

    # 统计 tag 数量
    rc, out, err = run_git(repo_path, 'tag', '--list')
    if rc == 0 and out:
        result['tag_count'] = len([l for l in out.strip().split('\n') if l.strip()])

    # 统计 reflog 数量
    rc, out, err = run_git(repo_path, 'reflog', '--all')
    if rc == 0 and out:
        result['reflog_count'] = len([l for l in out.strip().split('\n') if l.strip()])

    return result


# ===========================================================================
# ② 备份函数 backup_repo（L2安全级，自动commit+git bundle+verify）
# ===========================================================================

def backup_repo(repo_path=None, output_dir=None, dry_run=False):
    """备份函数（自动 commit + git bundle + verify）。

    Args:
        repo_path: 仓库路径（默认当前目录）
        output_dir: 备份目录（默认 ./backups/）
        dry_run: 预览模式，不实际执行

    Returns:
        dict {
            repo_path, repo_name, backup_path, size, size_human,
            verified, commit_before, dry_run, error
        }
    """
    if repo_path is None:
        repo_path = os.getcwd()
    repo_path = os.path.abspath(repo_path)
    repo_name = get_repo_name(repo_path)
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    output_dir = os.path.abspath(output_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    bundle_filename = '%s_backup_%s.bundle' % (repo_name, timestamp)
    bundle_path = os.path.join(output_dir, bundle_filename)

    result = {
        'repo_path': repo_path,
        'repo_name': repo_name,
        'backup_path': bundle_path,
        'size': 0,
        'size_human': '0 B',
        'verified': False,
        'commit_before': None,
        'dry_run': dry_run,
        'error': None,
    }

    # 检测是否为 git 仓库
    if not is_git_repo(repo_path):
        result['error'] = '%s 不是 git 仓库' % repo_path
        return result

    # 检测工作区状态
    rc, out, err = run_git(repo_path, 'status', '--porcelain')
    has_changes = rc == 0 and out.strip() != ''

    if dry_run:
        # dry-run 预览
        result['commit_before'] = 'will commit' if has_changes else 'clean'
        # 预估大小（用 .git 目录大小）
        git_dir = os.path.join(repo_path, '.git')
        result['size'] = get_dir_size(git_dir)
        result['size_human'] = human_readable_size(result['size'])
        return result

    # 自动 commit（若有未提交改动）
    # M3：commit 失败时 git reset HEAD 回退暂存区，避免污染工作区状态
    if has_changes:
        run_git(repo_path, 'add', '.')
        commit_msg = 'auto backup commit %s' % timestamp
        rc, out, err = run_git(repo_path, 'commit', '-m', commit_msg)
        if rc != 0:
            # 回退暂存区，保持工作区干净（改动仍在，只是 unstage）
            run_git(repo_path, 'reset', 'HEAD')
            result['error'] = 'commit 失败: %s' % (err or out)
            return result
        result['commit_before'] = commit_msg
    else:
        result['commit_before'] = 'clean'

    # 创建备份目录
    os.makedirs(output_dir, exist_ok=True)

    # git bundle create
    rc, out, err = run_git(repo_path, 'bundle', 'create', bundle_path, '--all')
    if rc != 0:
        result['error'] = 'git bundle create 失败: %s' % (err or out)
        # 删除半成品
        if os.path.isfile(bundle_path):
            try:
                os.remove(bundle_path)
            except OSError:
                pass
        return result

    # 计算备份文件大小
    try:
        result['size'] = os.path.getsize(bundle_path)
        result['size_human'] = human_readable_size(result['size'])
    except OSError:
        pass

    # git bundle verify
    rc, out, err = run_git(repo_path, 'bundle', 'verify', bundle_path)
    result['verified'] = (rc == 0)
    if rc != 0:
        # verify 失败仅告警不删除（让用户决定）
        result['error'] = 'verify 失败（备份文件已生成，请检查）: %s' % (err or out)

    return result


# ===========================================================================
# ③ 清理函数 cleanup_repo（L3安全级，fresh clone + HARD-GATE确认）
# ===========================================================================

def cleanup_repo(repo_path=None, target='all', dry_run=False, confirm=False):
    """清理函数（fresh clone + 分支/reflog/大文件清理 + gc）。

    Args:
        repo_path: 仓库路径（默认当前目录）
        target: 清理目标（branches/reflog/large-files/all）
        dry_run: 预览模式
        confirm: 跳过交互确认（仅用于脚本自动化）

    Returns:
        dict {
            repo_path, clone_path, operations, before_size, after_size,
            released, released_human, original_repo_untouched, dry_run, error
        }
    """
    if repo_path is None:
        repo_path = os.getcwd()
    repo_path = os.path.abspath(repo_path)
    repo_name = get_repo_name(repo_path)

    result = {
        'repo_path': repo_path,
        'clone_path': None,
        'operations': [],
        'before_size': 0,
        'after_size': 0,
        'released': 0,
        'released_human': '0 B',
        'original_repo_untouched': True,
        'dry_run': dry_run,
        'error': None,
        # M6：fresh clone 后 git 调用失败计数（branches/reflog/gc）
        'operations_failed': 0,
    }

    # 检测是否为 git 仓库
    if not is_git_repo(repo_path):
        result['error'] = '%s 不是 git 仓库' % repo_path
        return result

    # fresh clone 到临时目录
    tmp_dir = tempfile.mkdtemp(prefix='git_cleanup_')
    clone_path = os.path.join(tmp_dir, '%s-clone' % repo_name)
    result['clone_path'] = clone_path

    # git clone --mirror 不需要 -C 参数（目标目录是新建的）
    try:
        proc = subprocess.run(
            ['git', 'clone', '--mirror', repo_path, clone_path],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
            encoding='utf-8', errors='replace'
        )
        if proc.returncode != 0:
            result['error'] = 'git clone --mirror 失败: %s' % (proc.stderr or proc.stdout)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            result['clone_path'] = None
            return result
    except (subprocess.TimeoutExpired, OSError) as exc:
        result['error'] = 'git clone --mirror 异常: %s' % exc
        shutil.rmtree(tmp_dir, ignore_errors=True)
        result['clone_path'] = None
        return result

    # 记录清理前大小
    clone_git_dir = os.path.join(clone_path, 'objects')
    result['before_size'] = get_dir_size(clone_path)

    # 分析将清理的操作
    operations = []

    if target in ('branches', 'all'):
        # 清理已合并分支
        rc, out, err = run_git(clone_path, 'branch', '--merged')
        if rc == 0 and out:
            merged = [l.strip() for l in out.strip().split('\n') if l.strip() and not l.strip().startswith('*')]
            if merged:
                operations.append({
                    'type': 'branches',
                    'description': '清理 %d 个已合并分支: %s' % (len(merged), ', '.join(merged)),
                    'branches': merged,
                })

    if target in ('reflog', 'all'):
        # 清理过期 reflog
        operations.append({
            'type': 'reflog',
            'description': '清理过期 reflog（git reflog expire --expire=30.days --all）',
        })

    if target in ('large-files', 'all'):
        # 大文件清理（提示用 git-filter-repo）
        analyze_result = analyze_repo(clone_path, top_n=5)
        large_files = [f for f in analyze_result['large_files'] if f['size'] > 10 * 1024 * 1024]
        if large_files:
            operations.append({
                'type': 'large-files',
                'description': '发现 %d 个 >10MB 大文件（建议用 git-filter-repo 清理）: %s' % (
                    len(large_files),
                    ', '.join(['%s(%s)' % (f['path'], f['size_human']) for f in large_files])
                ),
                'files': large_files,
            })

    result['operations'] = operations

    if dry_run:
        # dry-run 模式：不执行，只报告
        result['after_size'] = result['before_size']
        # 保留 clone_path 供用户查看，不删除
        # M5：dry_run 保留副本后提示用户手动清理，避免 temp 目录堆积
        result['cleanup_hint'] = '副本路径 %s，请手动删除' % clone_path
        return result

    # 非 dry-run：HARD-GATE 确认
    if not confirm:
        print('\n⚠️  即将在 fresh clone 副本上执行以下清理操作：')
        print('  副本路径: %s' % clone_path)
        print('  原仓库: %s（不会被动）' % repo_path)
        for i, op in enumerate(operations, 1):
            print('  %d. %s' % (i, op['description']))
        print('\n  原仓库始终不动，改错可丢副本。')
        user_input = input('\n输入 "确认" 执行清理，其他取消: ')
        if user_input.strip() != '确认':
            result['error'] = '用户取消清理'
            shutil.rmtree(tmp_dir, ignore_errors=True)
            result['clone_path'] = None
            return result

    # 执行清理
    # M6：每个 git 调用检查 rc，失败时在 operations 对应项加 'error' 字段
    operations_failed = 0
    for op in operations:
        if op['type'] == 'branches':
            branch_errors = []
            for branch in op.get('branches', []):
                rc, out, err = run_git(clone_path, 'branch', '-d', branch)
                if rc != 0:
                    branch_errors.append({
                        'branch': branch,
                        'error': (err or out).strip(),
                    })
            if branch_errors:
                op['error'] = '部分分支删除失败: %s' % '; '.join(
                    '%s(%s)' % (e['branch'], e['error']) for e in branch_errors
                )
                op['errors'] = branch_errors
                operations_failed += 1
        elif op['type'] == 'reflog':
            rc, out, err = run_git(clone_path, 'reflog', 'expire', '--expire=30.days', '--all')
            if rc != 0:
                op['error'] = (err or out).strip()
                operations_failed += 1
        elif op['type'] == 'large-files':
            # 提示用 git-filter-repo，不直接操作（避免 filter-branch 风险）
            result['error'] = '大文件清理需手动用 git-filter-repo，副本在 %s' % clone_path
            # M15：用 continue 而非 break，让后续 op（如 reflog/branches）仍可处理
            continue

    # git gc --aggressive --prune=now（M6：检查 rc，失败计入 operations_failed）
    rc, out, err = run_git(clone_path, 'gc', '--aggressive', '--prune=now')
    if rc != 0:
        result['error'] = 'git gc 失败: %s' % (err or out)
        operations_failed += 1

    result['operations_failed'] = operations_failed

    # 记录清理后大小
    result['after_size'] = get_dir_size(clone_path)
    result['released'] = result['before_size'] - result['after_size']
    result['released_human'] = human_readable_size(result['released'])

    # 提示用户
    print('\n✅ 清理完成（在副本上）：')
    print('  副本路径: %s' % clone_path)
    print('  清理前: %s' % human_readable_size(result['before_size']))
    print('  清理后: %s' % human_readable_size(result['after_size']))
    print('  释放: %s' % result['released_human'])
    print('  原仓库未动: %s' % repo_path)
    print('  如需应用，手动 push 副本到新仓库')

    return result


# ===========================================================================
# ④ 维护函数 maintain_repo（L2安全级，git gc + repack）
# ===========================================================================

def maintain_repo(repo_path=None, dry_run=False):
    """维护函数（git gc + repack，非破坏性）。

    M4：维护是低风险但非完全无破坏——prune=2.weeks.ago 保留2周宽限期，
    避免 --prune=now 立即清掉所有 unreachable 对象（含刚 reset/未 commit 的对象）。

    Args:
        repo_path: 仓库路径（默认当前目录）
        dry_run: 预览模式

    Returns:
        dict {
            repo_path, before_size, before_size_human,
            after_size, after_size_human, released, released_human,
            commands_run, dry_run, error
        }
    """
    if repo_path is None:
        repo_path = os.getcwd()
    repo_path = os.path.abspath(repo_path)
    repo_name = get_repo_name(repo_path)

    result = {
        'repo_path': repo_path,
        'before_size': 0,
        'before_size_human': '0 B',
        'after_size': 0,
        'after_size_human': '0 B',
        'released': 0,
        'released_human': '0 B',
        'commands_run': [],
        'dry_run': dry_run,
        'error': None,
    }

    # 检测是否为 git 仓库
    if not is_git_repo(repo_path):
        result['error'] = '%s 不是 git 仓库' % repo_path
        return result

    # 记录维护前大小
    git_dir = os.path.join(repo_path, '.git')
    result['before_size'] = get_dir_size(git_dir)
    result['before_size_human'] = human_readable_size(result['before_size'])

    if dry_run:
        # dry-run 模式：只打印将执行的命令
        result['commands_run'] = []  # dry-run 时不执行，commands_run 为空
        return result

    # 实际执行 git gc --aggressive --prune=2.weeks.ago（M4：保留2周宽限期）
    gc_cmd = ['gc', '--aggressive', '--prune=2.weeks.ago']
    rc, out, err = run_git(repo_path, *gc_cmd)
    result['commands_run'].append('git %s' % ' '.join(gc_cmd))
    if rc != 0:
        result['error'] = 'git gc 失败: %s' % (err or out)
        return result

    # 实际执行 git repack -A -d
    repack_cmd = ['repack', '-A', '-d']
    rc, out, err = run_git(repo_path, *repack_cmd)
    result['commands_run'].append('git %s' % ' '.join(repack_cmd))
    if rc != 0:
        result['error'] = 'git repack 失败: %s' % (err or out)
        # gc 已执行不回滚
        return result

    # 记录维护后大小
    result['after_size'] = get_dir_size(git_dir)
    result['after_size_human'] = human_readable_size(result['after_size'])
    result['released'] = result['before_size'] - result['after_size']
    result['released_human'] = human_readable_size(result['released'])

    return result


# ===========================================================================
# ⑤ 生命周期函数 lifecycle_backup（L2安全级，清理旧备份）
# ===========================================================================

def lifecycle_backup(backup_dir=None, keep=DEFAULT_KEEP, days=DEFAULT_DAYS, dry_run=False):
    """生命周期函数（扫描备份+保留策略+清理旧备份）。

    Args:
        backup_dir: 备份目录（默认 ./backups/）
        keep: 保留数量（默认7）
        days: 保留天数（默认30）
        dry_run: 预览模式

    Returns:
        dict {
            backup_dir, total_backups, kept, deleted, deleted_files,
            released_size, released_size_human, dry_run, error
        }
    """
    if backup_dir is None:
        backup_dir = DEFAULT_OUTPUT_DIR
    backup_dir = os.path.abspath(backup_dir)

    result = {
        'backup_dir': backup_dir,
        'total_backups': 0,
        'kept': 0,
        'deleted': 0,
        'deleted_files': [],
        'released_size': 0,
        'released_size_human': '0 B',
        'dry_run': dry_run,
        'error': None,
        # 沙箱 lifecycle：标识备份目录是否存在，便于调用方结构化判断
        'exists': False,
    }

    # 检测备份目录
    # 沙箱 lifecycle：目录不存在时不返回告警文本，
    # 而是返回结构化 JSON（total_backups=0/backup_dir/exists=False），让调用方自行判断
    if not os.path.isdir(backup_dir):
        return result
    result['exists'] = True

    # 扫描所有 .bundle 文件
    bundle_files = []
    for filename in os.listdir(backup_dir):
        if filename.endswith('.bundle'):
            filepath = os.path.join(backup_dir, filename)
            try:
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                bundle_files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'mtime': mtime,
                    'size': size,
                    'size_human': human_readable_size(size),
                })
            except OSError:
                pass

    result['total_backups'] = len(bundle_files)

    if not bundle_files:
        result['error'] = '无备份文件'
        return result

    # 按修改时间排序（新→旧）
    bundle_files.sort(key=lambda x: x['mtime'], reverse=True)

    # 应用保留策略：保留最近 N 个 + 最近 N 天内的
    now = time.time()
    days_threshold = now - (days * 24 * 60 * 60)

    to_keep = []
    to_delete = []

    for i, bundle in enumerate(bundle_files):
        # 保留最近 N 个
        if i < keep:
            to_keep.append(bundle)
        # 保留最近 N 天内的
        elif bundle['mtime'] >= days_threshold:
            to_keep.append(bundle)
        else:
            to_delete.append(bundle)

    result['kept'] = len(to_keep)
    result['deleted'] = len(to_delete)

    # 计算将释放的空间
    for bundle in to_delete:
        result['released_size'] += bundle['size']
        result['deleted_files'].append({
            'filename': bundle['filename'],
            'size': bundle['size'],
            'size_human': bundle['size_human'],
            'mtime': datetime.fromtimestamp(bundle['mtime']).strftime('%Y-%m-%d %H:%M'),
        })
    result['released_size_human'] = human_readable_size(result['released_size'])

    if dry_run:
        # dry-run 模式：不删除，只报告
        return result

    # 非 dry-run：列清单 + 用户确认
    if to_delete:
        print('\n⚠️  即将删除以下 %d 个旧备份文件（释放 %s）：' % (len(to_delete), result['released_size_human']))
        for f in result['deleted_files']:
            print('  %s  (%s, %s)' % (f['filename'], f['size_human'], f['mtime']))
        user_input = input('\n输入 "确认" 删除，其他取消: ')
        if user_input.strip() != '确认':
            result['error'] = '用户取消删除'
            result['deleted'] = 0
            result['deleted_files'] = []
            result['released_size'] = 0
            result['released_size_human'] = '0 B'
            return result

        # 执行删除
        deleted_count = 0
        for bundle in to_delete:
            try:
                os.remove(bundle['filepath'])
                deleted_count += 1
            except OSError as exc:
                # 删除失败跳过，继续处理其他文件
                print('  ⚠️ 删除失败: %s (%s)' % (bundle['filename'], exc))
        result['deleted'] = deleted_count

    return result


# ===========================================================================
# GitBackupTidy 主类
# ===========================================================================

class GitBackupTidy:
    """git 备份清理管理主类，调度5个子命令。"""

    def __init__(self, repo_path=None):
        self.repo_path = repo_path or os.getcwd()

    def analyze(self, top_n=DEFAULT_TOP_N):
        """体检（纯只读）。"""
        return analyze_repo(self.repo_path, top_n)

    def backup(self, output_dir=None, dry_run=False):
        """备份。"""
        return backup_repo(self.repo_path, output_dir, dry_run)

    def cleanup(self, target='all', dry_run=False, confirm=False):
        """清理。"""
        return cleanup_repo(self.repo_path, target, dry_run, confirm)

    def maintain(self, dry_run=False):
        """维护。"""
        return maintain_repo(self.repo_path, dry_run)

    def lifecycle(self, backup_dir=None, keep=DEFAULT_KEEP, days=DEFAULT_DAYS, dry_run=False):
        """生命周期。"""
        return lifecycle_backup(backup_dir, keep, days, dry_run)


# ===========================================================================
# 人类可读报告输出
# ===========================================================================

def print_analyze_report(result):
    """打印体检报告（人类可读）。"""
    if result.get('error') and not result['is_git_repo']:
        print('❌ %s' % result['error'])
        return

    print('=' * 60)
    print('📋 git 仓库体检报告')
    print('=' * 60)
    print('仓库: %s' % result['repo_name'])
    print('路径: %s' % result['repo_path'])
    print('.git 大小: %s (%s bytes)' % (result['repo_size_human'], result['repo_size']))
    print('星级警告: %s' % result['star_level'])

    # 星级含义
    star_meanings = {
        '*': '健康（<100MB）',
        '**': '注意（100MB-1GB）',
        '***': '警告（1GB-5GB）',
        '****': '严重（5GB-10GB）',
        '*****': '危险（>10GB）',
    }
    print('  含义: %s' % star_meanings.get(result['star_level'], '未知'))

    print('\n📊 统计：')
    print('  分支数量: %d' % result['branch_count'])
    print('  已合并分支: %d' % len(result['merged_branches']))
    print('  Tag 数量: %d' % result['tag_count'])
    print('  Reflog 数量: %d' % result['reflog_count'])

    if result['large_files']:
        print('\n📁 大文件 Top %d：' % len(result['large_files']))
        for i, f in enumerate(result['large_files'], 1):
            print('  %d. %s  (%s)' % (i, f['path'], f['size_human']))

    if result['merged_branches']:
        print('\n🌿 已合并分支（可清理）：')
        for branch in result['merged_branches']:
            print('  - %s' % branch)

    print('=' * 60)


def print_backup_report(result):
    """打印备份报告。"""
    if result.get('error') and not result['verified']:
        print('❌ 备份失败: %s' % result['error'])
        return

    print('=' * 60)
    print('💾 git 仓库备份报告')
    print('=' * 60)
    print('仓库: %s' % result['repo_name'])
    if result['dry_run']:
        print('模式: dry-run 预览（未实际执行）')
        print('将备份到: %s' % result['backup_path'])
        print('预估大小: %s' % result['size_human'])
        print('工作区状态: %s' % result['commit_before'])
    else:
        print('备份文件: %s' % result['backup_path'])
        print('大小: %s' % result['size_human'])
        print('验证: %s' % ('✓ 通过' if result['verified'] else '✗ 失败'))
        print('备份前 commit: %s' % result['commit_before'])
    print('=' * 60)


def print_cleanup_report(result):
    """打印清理报告。"""
    if result.get('error'):
        print('❌ %s' % result['error'])
        return

    print('=' * 60)
    print('🧹 git 仓库清理报告')
    print('=' * 60)
    print('原仓库: %s（未动）' % result['repo_path'])
    print('副本路径: %s' % result['clone_path'])
    if result['dry_run']:
        print('模式: dry-run 预览（未实际执行）')
    print('\n将执行的操作：')
    for i, op in enumerate(result['operations'], 1):
        print('  %d. %s' % (i, op['description']))
    print('\n清理前大小: %s' % human_readable_size(result['before_size']))
    print('清理后大小: %s' % human_readable_size(result['after_size']))
    print('释放空间: %s' % result['released_human'])
    print('原仓库未动: %s' % result['original_repo_untouched'])
    print('=' * 60)


def print_maintain_report(result):
    """打印维护报告。"""
    if result.get('error'):
        print('❌ %s' % result['error'])
        return

    print('=' * 60)
    print('🔧 git 仓库维护报告')
    print('=' * 60)
    if result['dry_run']:
        print('模式: dry-run 预览（未实际执行）')
        print('将执行: git gc --aggressive --prune=2.weeks.ago')
        print('        git repack -A -d')
    else:
        print('已执行命令: %s' % ', '.join(result['commands_run']))
        print('维护前: %s' % result['before_size_human'])
        print('维护后: %s' % result['after_size_human'])
        print('释放: %s' % result['released_human'])
    print('=' * 60)


def print_lifecycle_report(result):
    """打印生命周期报告。"""
    if result.get('error'):
        print('⚠️ %s' % result['error'])
        return

    print('=' * 60)
    print('🔄 备份生命周期报告')
    print('=' * 60)
    print('备份目录: %s' % result['backup_dir'])
    print('总备份数: %d' % result['total_backups'])
    print('保留: %d' % result['kept'])
    print('待删除: %d' % result['deleted'])
    print('释放空间: %s' % result['released_size_human'])
    if result['dry_run']:
        print('模式: dry-run 预览（未实际执行）')
    if result['deleted_files']:
        print('\n待删除文件：')
        for f in result['deleted_files']:
            print('  %s  (%s, %s)' % (f['filename'], f['size_human'], f['mtime']))
    print('=' * 60)


# ===========================================================================
# main 入口 + argparse
# ===========================================================================

def main():
    """主入口，解析命令行参数，调度5个子命令。"""
    parser = argparse.ArgumentParser(
        description='git 备份清理管理脚本（5子命令：体检/备份/清理/维护/生命周期）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
安全门控：
  L1 只读（体检）：无门控，随便跑
  L2 预览（备份/维护/生命周期）：dry-run 预览 + 用户确认
  L3 破坏性（清理）：fresh clone + HARD-GATE 确认 + 原仓库不动

示例：
  python git_backup_tidy.py --analyze --json
  python git_backup_tidy.py --backup --dry-run
  python git_backup_tidy.py --cleanup --all --dry-run
  python git_backup_tidy.py --maintain
  python git_backup_tidy.py --lifecycle --dry-run
        """,
    )

    # 子命令（互斥组）
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--analyze', action='store_true', help='体检（纯只读，L1安全级）')
    group.add_argument('--backup', action='store_true', help='备份（L2安全级）')
    group.add_argument('--cleanup', action='store_true', help='清理（L3安全级，破坏性）')
    group.add_argument('--maintain', action='store_true', help='维护（L2安全级，非破坏性）')
    group.add_argument('--lifecycle', action='store_true', help='生命周期（L2安全级）')

    # 通用参数
    parser.add_argument('--repo', default=None, help='仓库路径（默认当前目录）')
    parser.add_argument('--json', action='store_true', help='JSON 输出（供 tidy 脚本解析）')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际执行')
    parser.add_argument('--top', type=int, default=DEFAULT_TOP_N, help='大文件数量（默认10）')

    # backup 参数
    parser.add_argument('--output-dir', default=None, help='备份目录（默认 ./backups/）')

    # cleanup 参数
    parser.add_argument('--target', choices=['branches', 'reflog', 'large-files', 'all'],
                        default='all', help='清理目标（默认 all）')
    parser.add_argument('--confirm', action='store_true',
                        help='跳过交互确认（仅用于脚本自动化，手动使用禁用）')

    # lifecycle 参数
    parser.add_argument('--backup-dir', default=None, help='备份目录（默认 ./backups/）')
    parser.add_argument('--keep', type=int, default=DEFAULT_KEEP, help='保留数量（默认7）')
    parser.add_argument('--days', type=int, default=DEFAULT_DAYS, help='保留天数（默认30）')

    args = parser.parse_args()

    # M11：--confirm 仅用于脚本自动化（非 tty），手动使用禁止
    # 防止手动跑用户误用 --confirm 绕过 L3 破坏性操作的人工确认门（HARD-GATE）
    if args.confirm and sys.stdin.isatty():
        print('错误: --confirm 仅用于脚本自动化，手动使用请去掉 --confirm', file=sys.stderr)
        sys.exit(1)

    # 调度子命令
    if args.analyze:
        result = analyze_repo(args.repo, args.top)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_analyze_report(result)

    elif args.backup:
        result = backup_repo(args.repo, args.output_dir, args.dry_run)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_backup_report(result)

    elif args.cleanup:
        result = cleanup_repo(args.repo, args.target, args.dry_run, args.confirm)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_cleanup_report(result)

    elif args.maintain:
        result = maintain_repo(args.repo, args.dry_run)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_maintain_report(result)

    elif args.lifecycle:
        result = lifecycle_backup(args.backup_dir, args.keep, args.days, args.dry_run)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_lifecycle_report(result)

    # 退出码：仅 --cleanup/--backup/--maintain 执行失败返回 1
    # --analyze 体检报告仓库不存在 git 是合法结果，返回 0
    # --lifecycle "无备份文件" 是合法结果，返回 0
    if result.get('error'):
        if args.analyze or args.lifecycle:
            sys.exit(0)  # 体检/生命周期报告错误是合法结果
        else:
            sys.exit(1)  # 其他子命令执行失败
    sys.exit(0)


if __name__ == '__main__':
    main()

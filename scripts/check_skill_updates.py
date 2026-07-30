#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_skill_updates.py — riji-skill skill 更新检查脚本

作用
----
检查 skill 仓库是否落后于远端(是否有 remote 新 commit 需要拉取)。
4 级降级:任一失败 return False 不报错,不阻塞主流程。

检查链(任一失败即降级,返回 False):
  1. check_git_available:        cwd 是 git 仓库?           (git rev-parse --is-inside-work-tree)
  2. check_remote_configured:    配置了 remote?              (git remote)
  3. check_network_and_fetch:    git fetch --dry-run 能跑通? (网络+权限)
  4. get_behind_count:           本地落后远端多少 commit?    (git rev-list HEAD..@{u} --count)

主流程(对齐用户伪代码):
    if not check_git_available(cwd):       return False, "not git"
    if not check_remote_configured(cwd):   return False, "no remote"
    if not check_network_and_fetch(cwd):   return False, "fetch failed"
    behind = get_behind_count(cwd)
    return behind == 0, "behind=%d" % behind

借鉴来源: 无(纯 Python 标准库 subprocess)
Traceability: SKILL.md §0 流程优先, references/common/pa/trigger_hooks.md 报错询问机制
设计来源: SKILL.md §10 安全边界(4s 超时+降级,不阻塞主流程)

技术约束
--------
* 纯 Python 标准库(os / sys / json / argparse / logging / subprocess)。
* 每步 4 秒超时,失败降级 return False / 0,不抛异常。
* Windows 兼容:FileNotFoundError(git 未装)+ TimeoutExpired + OSError 兜底。

运行
----
  python scripts/check_skill_updates.py [--skill-dir PATH] [--json]
"""

import os
import sys
import json
import argparse
import logging
import subprocess

# 风格对齐 route_check.py / protocol_align.py(虽不 import protocol,保留路径常量备用)
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 默认超时秒数(对齐任务要求:4s)
_DEFAULT_TIMEOUT = 4


# ===========================================================================
# 统一 git 命令封装(失败降级,不抛异常)
# ===========================================================================
def _run_git(args, cwd, timeout=_DEFAULT_TIMEOUT):
    """跑 git 命令的统一封装,失败返回 None(不抛异常)。

    所有 4 个 check 函数共用此封装,统一处理:
      - FileNotFoundError: git 可执行文件不存在(未装 git)
      - TimeoutExpired:   超时(默认 4s)
      - OSError:           其它 OS 层错误(权限/路径等)

    Args:
        args: git 参数列表,如 ['rev-parse', '--is-inside-work-tree']
        cwd: 工作目录。
        timeout: 超时秒数,默认 4。

    Returns:
        subprocess.CompletedProcess 或 None(失败时)。失败原因见日志。
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return result
    except FileNotFoundError:
        logger.warning("git 命令不存在(未安装 git?)")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("git %s 超时(%ss)", ' '.join(args), timeout)
        return None
    except OSError as exc:
        logger.warning("git %s 执行失败: %s", ' '.join(args), exc)
        return None


# ===========================================================================
# 4 级 check 函数(任一失败降级,不抛异常)
# ===========================================================================
def check_git_available(cwd):
    """Check 1: 检查 cwd 是 git 仓库(`git rev-parse --is-inside-work-tree`),4s 超时。

    Args:
        cwd: 待检查的工作目录。

    Returns:
        bool: True=cwd 是 git 仓库;False=不是 git 仓库/git 未装/超时/异常。
    """
    result = _run_git(['rev-parse', '--is-inside-work-tree'], cwd)
    if result is None:
        return False
    if result.returncode != 0:
        return False
    stdout = (result.stdout or '').strip()
    return stdout == 'true'


def check_remote_configured(cwd):
    """Check 2: 检查 cwd 的 git 仓库配置了 remote(`git remote`),4s 超时。

    Args:
        cwd: 待检查的工作目录。

    Returns:
        bool: True=至少有 1 个 remote;False=无 remote 或失败/异常。
    """
    result = _run_git(['remote'], cwd)
    if result is None:
        return False
    if result.returncode != 0:
        return False
    remotes = [r for r in (result.stdout or '').splitlines() if r.strip()]
    return len(remotes) > 0


def check_network_and_fetch(cwd):
    """Check 3: 跑 `git fetch --dry-run` 检测网络+权限,4s 超时。

    Args:
        cwd: 待检查的工作目录。

    Returns:
        dict: {'ok': bool, 'error': str}
        ok=True 表示 fetch 成功(网络通+权限足+remote 可达);
        ok=False 时 error 给出降级原因(网络断/权限不足/超时/git 未装/其它)。
    """
    result = _run_git(['fetch', '--dry-run'], cwd)
    if result is None:
        return {'ok': False, 'error': 'git fetch 执行失败(超时或 git 未装)'}
    if result.returncode != 0:
        stderr = (result.stderr or '').strip()
        # 常见错误:network unreachable / permission denied / auth failure
        return {'ok': False, 'error': 'git fetch rc=%d: %s' % (result.returncode, stderr[:200])}
    return {'ok': True, 'error': ''}


def get_behind_count(cwd):
    """Check 4: 跑 `git rev-list HEAD..@{u} --count`,返回本地落后远端的 commit 数。

    0 表示最新(本地与远端同步,或无 upstream 时降级返回 0)。

    Args:
        cwd: 待检查的工作目录。

    Returns:
        int: 落后的 commit 数。0=最新/无 upstream/失败降级。
    """
    result = _run_git(['rev-list', 'HEAD..@{u}', '--count'], cwd)
    if result is None:
        return 0
    if result.returncode != 0:
        # 无 upstream(@{u} 解析失败)或其它错误,降级返回 0
        stderr = (result.stderr or '').strip()
        logger.warning("get_behind_count 失败(降级返回 0): %s", stderr[:200])
        return 0
    stdout = (result.stdout or '').strip()
    try:
        return int(stdout)
    except ValueError:
        logger.warning("get_behind_count 输出非整数(降级返回 0): %r", stdout)
        return 0


# ===========================================================================
# 主流程(对齐用户伪代码)
# ===========================================================================
def check_updates(cwd):
    """主流程:4 级降级检查 skill 是否有更新。

    任一 check 失败即降级返回 (False, reason),不抛异常、不阻塞调用方。

    Args:
        cwd: skill 仓库根目录。

    Returns:
        tuple[bool, str]: (is_up_to_date, reason)
        is_up_to_date=True 表示本地最新无需更新;
        is_up_to_date=False 表示需更新或某 check 失败(看 reason 区分)。
        reason 给出 human-readable 原因,如 "not git" / "no remote" /
        "fetch failed: ..." / "behind=3" / "up-to-date"。
    """
    if not check_git_available(cwd):
        return False, 'not git'
    if not check_remote_configured(cwd):
        return False, 'no remote'
    fetch_result = check_network_and_fetch(cwd)
    if not fetch_result['ok']:
        return False, 'fetch failed: %s' % fetch_result['error']
    behind = get_behind_count(cwd)
    if behind == 0:
        return True, 'up-to-date'
    return False, 'behind=%d' % behind


# ===========================================================================
# CLI / main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='riji-skill skill 更新检查脚本(stdlib-only)')
    parser.add_argument('--skill-dir', default=None,
                        help='skill 包根目录(默认: scripts/ 的上级目录)')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果到 stdout(日志仍走 stderr)')
    args = parser.parse_args()

    # 默认 skill-dir = 脚本所在 scripts/ 的上级目录(仓库根)
    if args.skill_dir:
        skill_dir = os.path.abspath(args.skill_dir)
    else:
        skill_dir = _SKILL_ROOT

    if not os.path.isdir(skill_dir):
        logger.error("skill 目录不存在: %s", skill_dir)
        return 2

    logger.info("=== skill 更新检查(check_skill_updates)开始, skill_dir=%s ===", skill_dir)
    is_up_to_date, reason = check_updates(skill_dir)
    logger.info("=== 检查完成: is_up_to_date=%s reason=%s ===", is_up_to_date, reason)

    if args.json:
        payload = {
            'skill_dir': skill_dir,
            'is_up_to_date': is_up_to_date,
            'reason': reason,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('skill 更新检查报告(check_skill_updates.py)')
        print('skill_dir: %s' % skill_dir)
        print('-' * 60)
        tag = '✓ UP-TO-DATE' if is_up_to_date else '✗ NEEDS-UPDATE'
        print('[%s] %s' % (tag, reason))
        print('-' * 60)

    # is_up_to_date=True exit 0;False exit 1;目录不存在 exit 2
    return 0 if is_up_to_date else 1


if __name__ == '__main__':
    sys.exit(main())

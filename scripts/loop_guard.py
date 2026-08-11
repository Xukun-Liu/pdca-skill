#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loop_guard.py — pdca-skill 自动循环熔断器
============================================

用途
----
维护 `outputs_rj/loop_ledger.json`，记录每次 `/do` 尝试；对重复失败、无进展、
超迭代、超预算等场景触发 escalate 或 report-only，把人拉回决策环。

约束
----
* 仅使用 Python 标准库（argparse / json / re / os / sys / datetime）。
* 无外部依赖，内网可用。

用法
----
    # 记录一次尝试并检查是否需要熔断
    python scripts/loop_guard.py --check \
        --task-id "fix_utils_format" \
        --error "IndentationError: unexpected indent at line 42" \
        --tokens 15000 \
        --budget 80000

    # 归档当前任务的 ledger（通常在 /act 阶段调用）
    python scripts/loop_guard.py --finalize --task-id "fix_utils_format"

输出（stdout + 写入 ledger）
-----------------------------
    {
      "status": "active|escalate|pause|report-only",
      "reason": "...",
      "task_id": "fix_utils_format",
      "attempts": 3,
      "error_signature": "IndentationError: unexpected indent at line <n>",
      "thresholds": {
        "stagnation": 3,
        "no_progress": 5,
        "max_iterations": 10
      }
    }
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 默认阈值（可被 spec 或命令行覆盖）
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "stagnation": 3,       # 同一 error_signature 连续 N 次
    "no_progress": 5,      # 任意失败连续 N 次
    "max_iterations": 10,  # 单次任务总迭代上限
}

LEDGER_DIR = "outputs_rj"
LEDGER_FILE = os.path.join(LEDGER_DIR, "loop_ledger.json")

# ---------------------------------------------------------------------------
# error_signature 归一化
# ---------------------------------------------------------------------------
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]+|/[^\s]*")
_LINE_COL_RE = re.compile(r"\b(line|column)\s+\d+\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\b\d+\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE)
_HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)


def error_signature(error: str) -> str:
    """归一化错误签名：去掉时间戳、路径、行号、数字、随机 ID。"""
    if not error:
        return ""
    s = error
    s = _PATH_RE.sub("<path>", s)
    s = _LINE_COL_RE.sub(lambda m: "%s <n>" % m.group(1).lower(), s)
    s = _NUMBER_RE.sub("<n>", s)
    s = _UUID_RE.sub("<uuid>", s)
    s = _HASH_RE.sub("<hash>", s)
    # 压缩连续空白
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------
# spec.md max_iterations 读取（支持 spec.md 配置 max_iterations）
# ---------------------------------------------------------------------------
def read_spec_max_iterations(task_id, root="."):
    """从 docs_rj/spec_rj/ 中匹配任务 spec 的 frontmatter 读取 max_iterations。

    扫描规则：按文件名前缀匹配 task_id（下划线转连字符双向匹配）。
    返回 (max_iterations, spec_file) 或 (None, None)。
    """
    spec_dir = os.path.join(root, "docs_rj", "spec_rj")
    if not os.path.isdir(spec_dir):
        return None, None
    # 规范化 task_id 用于匹配：下划线→连字符
    task_id_norm = task_id.replace("_", "-").lower()
    try:
        files = sorted(os.listdir(spec_dir), reverse=True)  # 最新优先
    except OSError:
        return None, None
    for fname in files:
        if not fname.endswith(".md"):
            continue
        fname_norm = fname.replace("_", "-").lower()
        if task_id_norm not in fname_norm:
            continue
        spec_path = os.path.join(spec_dir, fname)
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                content = f.read(4096)  # 只读前 4KB（frontmatter 在头部）
        except Exception:
            continue
        # 匹配 YAML frontmatter 中的 max_iterations
        m = re.search(r"max_iterations\s*:\s*(\d+)", content)
        if m:
            val = int(m.group(1))
            if val >= 1:
                return val, fname
    return None, None


# ---------------------------------------------------------------------------
# ledger 读写
# ---------------------------------------------------------------------------
def read_ledger(path):
    """读取 ledger；不存在或损坏时返回空结构。"""
    if not os.path.isfile(path):
        return {"tasks": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {"tasks": {}}
        if "tasks" not in data or not isinstance(data["tasks"], dict):
            data["tasks"] = {}
        return data
    except (OSError, json.JSONDecodeError):
        return {"tasks": {}}


def write_ledger(path, ledger):
    """原子化写入 ledger（先写临时文件再重命名）。"""
    out_dir = os.path.dirname(path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def now_iso():
    """返回当前 UTC 时间 ISO 格式字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 熔断规则
# ---------------------------------------------------------------------------
def check_guard(task_id, error, tokens, budget, thresholds, ledger):
    """追加本次尝试并检查熔断规则。

    Returns
    -------
    dict: 含 status / reason / attempts / error_signature 等。
    """
    sig = error_signature(error)
    task = ledger["tasks"].get(task_id, {"attempts": []})

    attempt = {
        "timestamp": now_iso(),
        "error": error,
        "error_signature": sig,
        "tokens": tokens,
    }
    task.setdefault("attempts", []).append(attempt)
    ledger["tasks"][task_id] = task

    attempts = task["attempts"]
    total = len(attempts)

    # 1. max_iterations
    if total >= thresholds["max_iterations"]:
        return {
            "status": "escalate",
            "reason": "单次任务总迭代达到上限 %d 次" % thresholds["max_iterations"],
            "task_id": task_id,
            "attempts": total,
            "error_signature": sig,
            "thresholds": thresholds,
        }

    # 2. stagnation：最近 N 次签名相同
    recent = attempts[-thresholds["stagnation"]:]
    if len(recent) >= thresholds["stagnation"]:
        recent_sigs = [a.get("error_signature", "") for a in recent]
        if recent_sigs[0] and all(s == recent_sigs[0] for s in recent_sigs):
            return {
                "status": "escalate",
                "reason": "同一错误签名连续 %d 次（stagnation）"
                          % thresholds["stagnation"],
                "task_id": task_id,
                "attempts": total,
                "error_signature": sig,
                "thresholds": thresholds,
            }

    # 3. no_progress：最近 N 次均失败且签名不全相同
    recent_np = attempts[-thresholds["no_progress"]:]
    if len(recent_np) >= thresholds["no_progress"]:
        np_sigs = [a.get("error_signature", "") for a in recent_np]
        if all(np_sigs) and len(set(np_sigs)) > 1:
            return {
                "status": "escalate",
                "reason": "连续 %d 次失败但错误签名不同（no_progress）"
                          % thresholds["no_progress"],
                "task_id": task_id,
                "attempts": total,
                "error_signature": sig,
                "thresholds": thresholds,
            }

    return {
        "status": "active",
        "reason": "循环继续",
        "task_id": task_id,
        "attempts": total,
        "error_signature": sig,
        "thresholds": thresholds,
    }


def finalize_task(task_id, ledger):
    """归档任务：标记 final_status 并把 attempts 移到 archived。"""
    task = ledger["tasks"].get(task_id)
    if task is None:
        # 无 ledger 属于正常情况（如首次交接或任务未进入 /do）
        return {"status": "ok", "reason": "无运行记录，无需归档", "task_id": task_id}
    task["finalized_at"] = now_iso()
    task["final_status"] = task.get("last_status", "unknown")
    ledger.setdefault("archived", {})[task_id] = task
    del ledger["tasks"][task_id]
    return {"status": "ok", "reason": "任务已归档", "task_id": task_id}


# ---------------------------------------------------------------------------
# denylist 路径检查（spec §4.5）
# ---------------------------------------------------------------------------
# 对齐 loop_constraints.md L15-16 完整列表
# 路径段用路径边界 (^|/)dirname([/.]|$) 避免误命中 author.py/secretary.py/authentication.py
# .env 用词边界避免误命中 .environment
# 关键字用 \b 词边界避免误命中 password_hash.py/tokenize.py 等合法文件
# key 用 (?:\b|[_/.])key\b 覆盖 private_key.pem/api.key 但排除 keyboard/monkey
DENYLIST_PATTERNS = [
    r'(^|/)auth([/.]|$)',
    r'(^|/)payments([/.]|$)',
    r'(^|/)secret(s)?([/.]|$)',
    r'(^|/)credentials([/.]|$)',
    r'(^|/)infrastructure([/.]|$)',
    r'(^|/)migrations([/.]|$)',
    r'\.env($|[/.])',
    r'\bpassword\b',
    r'\btoken\b',
    r'(?:\b|[_/.])key\b',
]


def check_denylist(path):
    """检查路径是否命中 denylist。

    Args:
        path: 文件路径（相对或绝对）

    Returns:
        True = 命中 denylist（应触发 escalate）
        False = 安全
    """
    if not path:
        return False
    normalized = path.replace('\\', '/').lower()
    for pattern in DENYLIST_PATTERNS:
        if re.search(pattern, normalized):
            return True
    return False


def count_changed_files(root='.'):
    """统计当前 git 改动文件数。

    Args:
        root: 项目根目录

    Returns:
        改动文件数（git diff + untracked）；非 git 仓库返回 -1
    """
    try:
        rev_result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=root, capture_output=True, text=True, timeout=2,
        )
        if rev_result.returncode != 0 or rev_result.stdout.strip() != 'true':
            return -1  # 非 git 仓库
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1

    try:
        diff_result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd=root, capture_output=True, text=True, timeout=2,
        )
        diff_files = diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else []

        untracked_result = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            cwd=root, capture_output=True, text=True, timeout=2,
        )
        untracked_files = untracked_result.stdout.strip().split('\n') if untracked_result.stdout.strip() else []

        return len(diff_files) + len(untracked_files)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1


# 用户喊停关键词（stop-check 子命令用）
STOP_KEYWORDS = ["停", "stop", "pause", "中断"]


def check_stop(text):
    """检查文本中是否出现用户喊停关键词。

    Args:
        text: 对话历史文本

    Returns:
        dict: {"stopped": True, "keyword": "停"} 或 {"stopped": False}
    """
    if not text:
        return {"stopped": False}
    text_lower = text.lower()
    for kw in STOP_KEYWORDS:
        if kw.lower() in text_lower:
            return {"stopped": True, "keyword": kw}
    return {"stopped": False}


def check_loop_allow(task_id, root='.'):
    """检查是否满足 /loop 准入条件（代码层 L1/L0 拒绝）。

    Args:
        task_id: 任务 ID
        root: 项目根目录

    Returns:
        dict: {"allow": True/False, "reason": "...", "checks": {...}}
    """
    import os
    checks = {}

    # 检查 1：git 仓库
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=root, capture_output=True, text=True, timeout=2,
        )
        checks['git_repo'] = result.returncode == 0 and result.stdout.strip() == 'true'
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        checks['git_repo'] = False

    # 检查 2：TASK_STATE 存在
    task_state_path = os.path.join(root, 'docs_rj', 'memory_rj', 'TASK_STATE_%s.md' % task_id)
    checks['task_state'] = os.path.isfile(task_state_path)

    # 综合判定
    if checks['git_repo'] and checks['task_state']:
        allow = True
        reason = "满足 /loop 准入条件（git 仓库 + TASK_STATE 存在）"
    elif not checks['git_repo']:
        allow = False
        reason = "不满足 /loop 准入条件：非 git 仓库（L1/L0 拒绝）"
    else:
        allow = False
        reason = "不满足 /loop 准入条件：TASK_STATE_%s.md 不存在（L1/L0 拒绝）" % task_id

    return {"allow": allow, "reason": reason, "checks": checks}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="pdca-skill 自动循环熔断器（stdlib-only）")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="记录一次尝试并检查熔断条件")
    check.add_argument("--task-id", required=True, help="任务 ID")
    check.add_argument("--error", default="", help="错误信息原文")
    check.add_argument("--tokens", type=int, default=0, help="已消耗 token 数（保留兼容）")
    check.add_argument("--stagnation", type=int, default=DEFAULT_THRESHOLDS["stagnation"])
    check.add_argument("--no-progress", type=int, default=DEFAULT_THRESHOLDS["no_progress"])
    check.add_argument("--max-iterations", type=int, default=None, help="最大迭代次数（默认：优先读 spec.md，其次 %d）" % DEFAULT_THRESHOLDS["max_iterations"])
    check.add_argument("--ledger", default=LEDGER_FILE, help="ledger 文件路径")
    # /loop 模式扩展参数
    check.add_argument("--status", choices=["success", "failure"], help="本次迭代结果（success 不计入 attempt，failure 计入）")
    check.add_argument("--denylist-check", help="检查指定路径是否命中 denylist")
    check.add_argument("--changed-files-check", action="store_true", help="检查改动文件数是否 >5")
    check.add_argument("--root", default=".", help="项目根目录（--changed-files-check / spec 读取用）")

    fin = sub.add_parser("finalize", help="归档指定任务的 ledger")
    fin.add_argument("--task-id", required=True, help="任务 ID")
    fin.add_argument("--ledger", default=LEDGER_FILE, help="ledger 文件路径")

    # 用户喊停检测
    stop = sub.add_parser("stop-check", help="检查对话历史中是否出现停/stop/pause/中断关键词")
    stop.add_argument("--task-id", required=True, help="任务 ID")
    stop.add_argument("--text", required=True, help="对话历史文本")
    stop.add_argument("--ledger", default=LEDGER_FILE, help="ledger 文件路径")

    # /loop 准入检查（代码层 L1/L0 拒绝）
    allow = sub.add_parser("loop-allow", help="检查是否满足 /loop 准入条件（git 仓库 + TASK_STATE 存在）")
    allow.add_argument("--task-id", required=True, help="任务 ID")
    allow.add_argument("--root", default=".", help="项目根目录")
    allow.add_argument("--ledger", default=LEDGER_FILE, help="ledger 文件路径")

    return parser.parse_args()


def main():
    args = parse_args()
    ledger = read_ledger(args.ledger)

    if args.command == "check":
        # 1. denylist 检查（独立于 status，命中即 escalate）
        if args.denylist_check:
            if check_denylist(args.denylist_check):
                result = {
                    "status": "escalate",
                    "reason": "denylist 路径触碰：%s" % args.denylist_check,
                    "task_id": args.task_id,
                    "attempts": len(ledger["tasks"].get(args.task_id, {}).get("attempts", [])),
                    "error_signature": "",
                    "thresholds": DEFAULT_THRESHOLDS,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1

        # 2. 改动文件数检查（独立于 status，>5 即 escalate；非 git 仓库 -1 也 escalate）
        if args.changed_files_check:
            count = count_changed_files(args.root)
            if count < 0:
                result = {
                    "status": "escalate",
                    "reason": "非 git 仓库，无法统计改动文件数（count_changed_files 返回 -1）",
                    "task_id": args.task_id,
                    "attempts": len(ledger["tasks"].get(args.task_id, {}).get("attempts", [])),
                    "error_signature": "",
                    "thresholds": DEFAULT_THRESHOLDS,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1
            if count > 5:
                result = {
                    "status": "escalate",
                    "reason": "改动文件数 %d > 5" % count,
                    "task_id": args.task_id,
                    "attempts": len(ledger["tasks"].get(args.task_id, {}).get("attempts", [])),
                    "error_signature": "",
                    "thresholds": DEFAULT_THRESHOLDS,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1

        # 3. status 处理：success 不计入 attempt，failure 计入
        # 优先从 spec.md 读取 max_iterations，其次 CLI 参数，最后默认值
        max_iter = args.max_iterations
        if max_iter is None:
            spec_max, spec_file = read_spec_max_iterations(args.task_id, args.root)
            if spec_max is not None:
                max_iter = spec_max
            else:
                max_iter = DEFAULT_THRESHOLDS["max_iterations"]
        thresholds = {
            "stagnation": args.stagnation,
            "no_progress": args.no_progress,
            "max_iterations": max_iter,
        }

        if args.status == "success":
            # 成功不计入 attempt
            task = ledger["tasks"].get(args.task_id, {"attempts": []})
            total = len(task.get("attempts", []))
            result = {
                "status": "active",
                "reason": "循环继续（success 不计入 attempt）",
                "task_id": args.task_id,
                "attempts": total,
                "error_signature": "",
                "thresholds": thresholds,
            }
            # 更新 last_status
            if args.task_id not in ledger["tasks"]:
                ledger["tasks"][args.task_id] = {"attempts": []}
            ledger["tasks"][args.task_id]["last_status"] = result["status"]
            write_ledger(args.ledger, ledger)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        # failure 或未指定 status：走现有 check_guard 逻辑（记录 attempt + 熔断检查）
        result = check_guard(
            args.task_id, args.error, args.tokens, 0,
            thresholds, ledger,
        )
        # 把最后一次状态写回 task 便于查看
        ledger["tasks"][args.task_id]["last_status"] = result["status"]
        write_ledger(args.ledger, ledger)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in ("active", "report-only") else 1

    # stop-check 子命令（用户喊停检测）
    if args.command == "stop-check":
        result = check_stop(args.text)
        result["task_id"] = args.task_id
        if result["stopped"]:
            # 更新 ledger 标记任务已停止
            if args.task_id not in ledger["tasks"]:
                ledger["tasks"][args.task_id] = {"attempts": []}
            ledger["tasks"][args.task_id]["stopped"] = True
            ledger["tasks"][args.task_id]["stop_keyword"] = result.get("keyword", "")
            write_ledger(args.ledger, ledger)
            result["reason"] = "检测到用户喊停关键词：%s" % result.get("keyword", "")
        else:
            result["reason"] = "未检测到停关键词"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["stopped"] else 0

    # loop-allow 子命令（/loop 准入检查）
    if args.command == "loop-allow":
        result = check_loop_allow(args.task_id, args.root)
        result["task_id"] = args.task_id
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["allow"] else 1

    if args.command == "finalize":
        result = finalize_task(args.task_id, ledger)
        write_ledger(args.ledger, ledger)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loop_audit.py — riji-skill PDCA Ready Score 评分器
===================================================

用途
----
量化 skill 健康度，输出 0–100 分的 PDCA Ready Score 和 L1/L2 等级，
帮助判断当前项目是否适合进入 /plan 后的自动循环执行阶段。

约束
----
* 仅使用 Python 标准库（argparse / json / os / re / sys / py_compile）。
* 无外部依赖，内网可用。

用法
----
    python scripts/loop_audit.py
    python scripts/loop_audit.py --project-root /path/to/riji-skill
    python scripts/loop_audit.py --json outputs_rj/loop_audit_result.json

评分维度（总分 100）
---------------------
* 核心文件 20：SKILL.md / HISTORY.md / README.md 存在 + 版本一致
* references 完整性 20：references/*.md 存在 + frontmatter 完整
* 记忆系统 15：memory/memory_main.md + docs_rj/memory_rj/ + docs_rj/SUMMARY_RJ.md
* PDCA 标签一致性 15：所有 reference 文件含「阶段标签：」
* 脚本健康 15：scripts/*.py 可通过 py_compile
* 最近活动 15：最近 7 天有 memory 或 TASK_STATE 更新

等级阈值
--------
* L1 ≥ 40
* L2 ≥ 60
"""

import argparse
import json
import os
import py_compile
import re
import sys
import tempfile
from datetime import datetime, timezone, timedelta

# AC-005 修补（T008 遗漏）：用户数据外置后，记忆系统路径检查需走 user_data_path 解析，
# 否则 loop_audit 会误报 project_root/memory/memory_main.md 缺失（实际数据在 ~/.riji-skill/data/）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_data_path

# ---------------------------------------------------------------------------
# 权重配置
# ---------------------------------------------------------------------------
DIMENSIONS = {
    "core_files":      {"weight": 20, "name": "核心文件"},
    "references":      {"weight": 20, "name": "references 完整性"},
    "memory_system":   {"weight": 15, "name": "记忆系统"},
    "pdca_tags":       {"weight": 15, "name": "PDCA 标签一致性"},
    "scripts_health":  {"weight": 15, "name": "脚本健康"},
    "recent_activity": {"weight": 15, "name": "最近活动"},
}

REQUIRED_CORE = ["SKILL.md", "HISTORY.md", "README.md"]
REQUIRED_REFS = [
    "loop_constraints.md", "loop_triage.md", "loop_verifier.md",
    "trigger_hooks.md", "sync-matrix.md", "red_flags.md",
    "acceptance_criteria.md", "document_specs.md", "summary_view.md",
]
REQUIRED_MEMORY = [
    "memory/memory_main.md",
    "docs_rj/memory_rj",
    "docs_rj/SUMMARY_RJ.md",
]

OUTPUT_DIR = "outputs_rj"
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "loop_audit_result.json")

TAG_RE = re.compile(r"阶段标签：")
FRONTMATTER_RE = re.compile(r"^---\s*$")
VERSION_RE = re.compile(r"版本[：:]\s*v?(\d+\.\d+)")


# ---------------------------------------------------------------------------
# 文件读取辅助
# ---------------------------------------------------------------------------
def read_text(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return default


def list_refs(ref_dir):
    if not os.path.isdir(ref_dir):
        return []
    try:
        # 递归遍历 references/ 子目录，返回 POSIX 相对路径列表
        result = []
        for root, dirs, files in os.walk(ref_dir):
            for f in sorted(files):
                if f.endswith(".md"):
                    rel = os.path.relpath(os.path.join(root, f), ref_dir)
                    result.append(rel.replace(os.sep, "/"))
        result.sort()
        return result
    except OSError:
        return []


def list_scripts(script_dir):
    if not os.path.isdir(script_dir):
        return []
    try:
        return sorted(f for f in os.listdir(script_dir) if f.endswith(".py"))
    except OSError:
        return []


# ---------------------------------------------------------------------------
# 各维度评分
# ---------------------------------------------------------------------------
def score_core_files(project_root):
    detail = {}
    score = 0.0
    per_file = DIMENSIONS["core_files"]["weight"] / len(REQUIRED_CORE)
    versions = []

    for name in REQUIRED_CORE:
        path = os.path.join(project_root, name)
        exists = os.path.isfile(path)
        detail[name] = {"exists": exists}
        if exists:
            score += per_file
            text = read_text(path)
            m = VERSION_RE.search(text)
            if m:
                detail[name]["version"] = m.group(1)
                versions.append(m.group(1))

    # 版本一致：如果三个文件都有版本号，版本号相同加额外分（已在满分内，不一致则扣分）
    if len(versions) >= 2 and len(set(versions)) > 1:
        score = max(0, score - 5)
        detail["version_consistent"] = False
        detail["versions_found"] = versions
    else:
        detail["version_consistent"] = True if versions else None
        detail["versions_found"] = versions

    return round(score, 2), detail


def score_references(project_root):
    ref_dir = os.path.join(project_root, "references")
    all_refs = list_refs(ref_dir)
    detail = {"total": len(all_refs), "required_present": 0, "missing": []}

    per_required = DIMENSIONS["references"]["weight"] / len(REQUIRED_REFS)
    score = 0.0

    # 构建 basename → 完整路径 映射（迁移后 references/ 含子目录，REQUIRED_REFS 按 basename 查找）
    ref_by_basename = {}
    for rel in all_refs:
        basename = os.path.basename(rel)
        ref_by_basename[basename] = os.path.join(ref_dir, rel)

    for name in REQUIRED_REFS:
        path = ref_by_basename.get(name)
        if path and os.path.isfile(path):
            detail["required_present"] += 1
            text = read_text(path)
            has_frontmatter = text.startswith("---") and "---" in text[3:]
            if has_frontmatter:
                score += per_required * 0.7
            has_description = "description:" in text or "name:" in text
            if has_description:
                score += per_required * 0.3
        else:
            detail["missing"].append(name)

    # 额外：reference 总数不少于 10 个不扣分
    if len(all_refs) < 10:
        score = max(0, score - 3)
        detail["too_few"] = True

    return round(score, 2), detail


def _resolve_required_path(item, project_root):
    """根据 REQUIRED_MEMORY 的逻辑标识解析实际路径（用户数据外置支持）。

    AC-005 修补（T008 遗漏）：用户数据外置后路径经 user_data_path 解析，
    避免误报缺失（实际数据在 ~/.riji-skill/data/ 而非 project_root/）。
    解析失败时回退到 project_root 拼接（兼容老用户包内数据或外置目录不可创建场景）。

    Args:
        item: REQUIRED_MEMORY 中的逻辑标识
            - "memory/memory_main.md" → user_data_path.get_memory_main_path()
            - "docs_rj/memory_rj" → user_data_path.get_docs_rj_path() / "memory_rj"
            - "docs_rj/SUMMARY_RJ.md" → user_data_path.get_docs_rj_path() / "SUMMARY_RJ.md"
        project_root: 项目根目录（未知 item 或解析失败时的回退基准）。

    Returns:
        str: 实际路径（可能在外置目录 ~/.riji-skill/data/ 下）。
    """
    try:
        if item == "memory/memory_main.md":
            return str(user_data_path.get_memory_main_path())
        elif item == "docs_rj/memory_rj":
            return str(user_data_path.get_docs_rj_path() / "memory_rj")
        elif item == "docs_rj/SUMMARY_RJ.md":
            return str(user_data_path.get_docs_rj_path() / "SUMMARY_RJ.md")
    except (PermissionError, OSError):
        # 外置目录不可创建：回退到 project_root 拼接（兼容老用户包内数据）
        pass
    # 未知 item 或解析失败：回退到原逻辑（project_root 拼接）
    return os.path.join(project_root, item)


def score_memory_system(project_root):
    """评分记忆系统完整性（用户数据外置后经 user_data_path 解析）。"""
    detail = {}
    score = 0.0
    per_item = DIMENSIONS["memory_system"]["weight"] / len(REQUIRED_MEMORY)

    for item in REQUIRED_MEMORY:
        path = _resolve_required_path(item, project_root)
        exists = os.path.exists(path)
        detail[item] = {"exists": exists, "resolved_path": path}
        if exists:
            score += per_item

    return round(score, 2), detail


def score_pdca_tags(project_root):
    ref_dir = os.path.join(project_root, "references")
    all_refs = list_refs(ref_dir)
    if not all_refs:
        return 0.0, {"total": 0, "tagged": 0, "untagged": []}

    tagged = 0
    untagged = []
    for name in all_refs:
        path = os.path.join(ref_dir, name)
        text = read_text(path)
        if TAG_RE.search(text):
            tagged += 1
        else:
            untagged.append(name)

    score = (tagged / len(all_refs)) * DIMENSIONS["pdca_tags"]["weight"]
    return round(score, 2), {
        "total": len(all_refs),
        "tagged": tagged,
        "untagged": untagged,
    }


def score_scripts_health(project_root):
    script_dir = os.path.join(project_root, "scripts")
    scripts = list_scripts(script_dir)
    if not scripts:
        return 0.0, {"total": 0, "compile_ok": 0, "failed": []}

    ok = 0
    failed = []
    tmp_dir = tempfile.mkdtemp(prefix="hh_audit_compile_")
    try:
        for name in scripts:
            path = os.path.join(script_dir, name)
            try:
                py_compile.compile(path, doraise=True)
                ok += 1
            except py_compile.PyCompileError as exc:
                failed.append({"file": name, "error": str(exc)})
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    score = (ok / len(scripts)) * DIMENSIONS["scripts_health"]["weight"]
    return round(score, 2), {
        "total": len(scripts),
        "compile_ok": ok,
        "failed": failed,
    }


def score_recent_activity(project_root):
    """评分最近活动（用户数据外置后扫描外置 docs_rj/）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    detail = {"memory_files": 0, "task_state_files": 0, "recent_paths": []}
    score = 0.0

    # AC-005 修补（T008 遗漏）：扫描外置 docs_rj/ 而非 project_root/docs_rj/，
    # 解析失败回退到 project_root（兼容老用户包内数据或外置目录不可创建场景）。
    try:
        docs_rj_path = user_data_path.get_docs_rj_path()
    except (PermissionError, OSError):
        docs_rj_path = os.path.join(project_root, "docs_rj")
    scan_dirs = [
        os.path.join(str(docs_rj_path), "memory_rj"),
        os.path.join(str(docs_rj_path), "task_rj"),
    ]

    recent_count = 0
    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        try:
            for entry in os.listdir(scan_dir):
                path = os.path.join(scan_dir, entry)
                if not os.path.isfile(path):
                    continue
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
                except OSError:
                    continue
                if mtime >= cutoff:
                    recent_count += 1
                    if len(detail["recent_paths"]) < 5:
                        detail["recent_paths"].append(path)
        except OSError:
            continue

    if recent_count > 0:
        score = DIMENSIONS["recent_activity"]["weight"]
        if recent_count < 3:
            score *= 0.7
    detail["recent_count"] = recent_count

    return round(score, 2), detail


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def stars(score):
    """把 0–100 分转成 1–5 星。"""
    return min(5, max(1, int(score / 20) + (1 if score % 20 >= 10 else 0)))


def determine_level(score):
    if score >= 60:
        return "L2"
    if score >= 40:
        return "L1"
    return "L0"


def run_audit(project_root):
    project_root = os.path.abspath(project_root)

    core_score, core_detail = score_core_files(project_root)
    ref_score, ref_detail = score_references(project_root)
    mem_score, mem_detail = score_memory_system(project_root)
    tag_score, tag_detail = score_pdca_tags(project_root)
    script_score, script_detail = score_scripts_health(project_root)
    activity_score, activity_detail = score_recent_activity(project_root)

    breakdown = {
        "core_files":      {"score": core_score,      "weight": DIMENSIONS["core_files"]["weight"],      "detail": core_detail},
        "references":      {"score": ref_score,       "weight": DIMENSIONS["references"]["weight"],      "detail": ref_detail},
        "memory_system":   {"score": mem_score,       "weight": DIMENSIONS["memory_system"]["weight"],   "detail": mem_detail},
        "pdca_tags":       {"score": tag_score,       "weight": DIMENSIONS["pdca_tags"]["weight"],       "detail": tag_detail},
        "scripts_health":  {"score": script_score,    "weight": DIMENSIONS["scripts_health"]["weight"],  "detail": script_detail},
        "recent_activity": {"score": activity_score,  "weight": DIMENSIONS["recent_activity"]["weight"], "detail": activity_detail},
    }

    total = round(sum(v["score"] for v in breakdown.values()), 2)

    return {
        "status": "ok",
        "project_root": project_root,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pdca_ready_score": total,
        "stars": "*" * stars(total),
        "level": determine_level(total),
        "thresholds": {"L1": 40, "L2": 60},
        "breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="riji-skill PDCA Ready Score 评分器（stdlib-only）")
    parser.add_argument("--project-root", default=os.getcwd(),
                        help="项目根目录（默认当前目录）")
    parser.add_argument("--json", default=DEFAULT_OUTPUT,
                        help="JSON 输出路径（默认 outputs_rj/loop_audit_result.json）")
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.isdir(args.project_root):
        result = {
            "status": "error",
            "reason": "项目目录不存在: %s" % args.project_root,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    try:
        result = run_audit(args.project_root)
    except Exception as exc:
        result = {
            "status": "error",
            "reason": "审计异常: %s" % exc,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.json:
        out_dir = os.path.dirname(os.path.abspath(args.json))
        if out_dir and not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as exc:
                print("警告：无法创建输出目录 %s: %s" % (out_dir, exc), file=sys.stderr)
        try:
            with open(args.json, "w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            print("警告：写入 JSON 失败: %s" % exc, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

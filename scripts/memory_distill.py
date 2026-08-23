#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_distill.py — 记忆蒸馏中间层

读取 memory_main.md 中 is_lesson=true 条目，蒸馏为经验库 JSON。
对应 spec REQ-005 ~ REQ-008。

PDCA标签：A.learn（/act 阶段记忆蒸馏）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

_SKILL_ROOT = Path(__file__).resolve().parent.parent

# 导入用户数据路径模块（与 write_project/learn_tidy 对齐）
sys.path.insert(0, str(_SKILL_ROOT / "scripts"))
try:
    import user_data_path  # noqa: E402
except ImportError:
    user_data_path = None


def parse_memory_entries(memory_content: str, project_name: str = None) -> List[Dict[str, Any]]:
    """解析 memory_main.md 提取条目。

    格式：
    ## {project_name}
    ### 记忆条目 · {task}（{timestamp}）
    **重要性**: {level}
    **是否经验**: {bool}
    **经验标签**: {tags}
    {content}
    """
    entries = []
    lines = memory_content.split('\n')
    i = 0
    current_project = None
    while i < len(lines):
        line = lines[i].strip()
        # 项目分段
        if line.startswith('## ') and not line.startswith('### '):
            current_project = line[3:].strip()
            i += 1
            continue
        # 记忆条目
        if line.startswith('### 记忆条目 · '):
            # 提取 task 名和时间戳
            match = re.match(r'^### 记忆条目 · (.+?)(?:（(\d{4}-\d{2}-\d{2} \d{2}:\d{2})）)?$', line)
            if match:
                task_name = match.group(1).strip()
                timestamp = match.group(2) or ""
                entry = {
                    "task": task_name,
                    "timestamp": timestamp,
                    "project": current_project,
                    "importance_level": "medium",
                    "is_lesson": False,
                    "experience_tags": [],
                    "content_lines": [],
                }
                i += 1
                # 读取 frontmatter 和内容
                while i < len(lines):
                    fl = lines[i].strip()
                    if fl.startswith('### 记忆条目 · ') or (fl.startswith('## ') and not fl.startswith('### ')):
                        break
                    if fl.startswith('**重要性**: '):
                        entry["importance_level"] = fl.replace('**重要性**: ', '').strip()
                    elif fl.startswith('**是否经验**: '):
                        entry["is_lesson"] = fl.replace('**是否经验**: ', '').strip().lower() == 'true'
                    elif fl.startswith('**经验标签**: '):
                        tags_str = fl.replace('**经验标签**: ', '').strip()
                        if tags_str and tags_str != "无":
                            entry["experience_tags"] = [t.strip() for t in tags_str.split(',')]
                    elif fl.startswith('**状态**: '):
                        # v103t3 修复#3：解析状态字段，供 distill 阶段过滤 archived/demoted
                        entry["status"] = fl.replace('**状态**: ', '').strip().lower()
                    else:
                        if fl:
                            entry["content_lines"].append(fl)
                    i += 1
                entry["content"] = '\n'.join(entry["content_lines"])
                entries.append(entry)
                continue
        i += 1

    # 按项目过滤
    if project_name:
        entries = [e for e in entries if e["project"] == project_name]
    # v103t3 修复#3：跳过 archived/demoted 条目，避免把已经下线/归档的经验再次蒸馏
    entries = [e for e in entries if e.get("status", "active") not in ("archived", "demoted")]
    return entries


def distill(project_name: str, memory_file: str = None, output_dir: str = None) -> Dict[str, Any]:
    """蒸馏经验库。

    读取 memory_main.md → 过滤 is_lesson=true → 输出结构化经验条目。
    """
    if memory_file is None:
        # 对齐 user_data_path 外置化设计：与 write_project/learn_tidy 写入路径一致
        if user_data_path is not None:
            memory_file = str(user_data_path.get_memory_main_path())
        else:
            # fallback：skill 包内（向后兼容）
            memory_file = str(_SKILL_ROOT / "memory" / "memory_main.md")
    if not os.path.isfile(memory_file):
        logger.error("memory_main.md 不存在: %s", memory_file)
        return {"total_lessons": 0, "lessons": [], "error": "memory_file_not_found"}

    with open(memory_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    entries = parse_memory_entries(content, project_name)
    lesson_entries = [e for e in entries if e["is_lesson"]]

    if not lesson_entries:
        logger.warning("无 is_lesson=true 条目，经验库为空")

    lessons = []
    for idx, entry in enumerate(lesson_entries, 1):
        lesson = {
            "lesson_id": f"lesson_{idx:03d}",
            "title": entry["task"],
            "content": entry["content"],
            "source_memory": f"{entry['project']}/{entry['task']}({entry['timestamp']})",
            "importance_level": entry["importance_level"],
            "experience_tags": entry["experience_tags"],
            "reflection": "",  # 留空，由 agent 在 /act 阶段填充
            "adopted": False,
        }
        lessons.append(lesson)

    result = {
        "total_lessons": len(lessons),
        "lessons": lessons,
        "distill_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_file": memory_file,
    }

    # 写入 output_dir
    if output_dir:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = Path(output_dir) / timestamp / "lessons.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("经验库已写入: %s", out_path)

    return result


def cmd_distill(args):
    """distill 子命令"""
    result = distill(
        project_name=args.project,
        memory_file=args.memory_file,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"经验库总数: {result['total_lessons']}")
        for lesson in result.get("lessons", []):
            print(f"  - [{lesson['lesson_id']}] {lesson['title']} ({lesson['importance_level']})")
    # H4 修复：distill 成功执行即返回 0（空经验库用 total_lessons=0 表达，不用退出码 1）
    # 原 return 1 与 spec §9"不阻断 /act"矛盾——shell 会误判为失败而中断 /act 流程
    return 0


def main():
    parser = argparse.ArgumentParser(description="记忆蒸馏中间层")
    sub = parser.add_subparsers(dest="command", required=True)

    p_distill = sub.add_parser("distill", help="蒸馏经验库")
    p_distill.add_argument("--project", required=True, help="项目名")
    p_distill.add_argument("--memory-file", default=None, help="memory_main.md 路径")
    p_distill.add_argument("--output-dir", default=None, help="输出目录")
    p_distill.add_argument("--json", action="store_true", help="JSON 输出")

    args = parser.parse_args()
    if args.command == "distill":
        return cmd_distill(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())

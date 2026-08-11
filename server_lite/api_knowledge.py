"""知识管理 Blueprint

端点：
- GET /api/knowledge — 读取全部知识数据
- POST /api/knowledge — 保存全部知识数据
- POST /api/knowledge/note — 添加笔记
- DELETE /api/knowledge/note/<note_id> — 删除笔记
- PUT /api/knowledge/entry/<entry_id> — 更新条目（标签/掌握度/备注）
- GET /api/knowledge/extract — 从memory文件提取知识条目
- GET /api/knowledge/memories — 解析全局记忆条目
- GET /api/knowledge/project-memories — 列出项目级记忆
- POST /api/knowledge/promote — 提炼项目记忆到全局
- GET /api/knowledge/lessons — 获取经验库（memory_distill 产出的 lessons.json）
"""
from flask import Blueprint, jsonify, request, current_app
from .file_protocol import read_knowledge_data, write_knowledge_data, read_markdown_file
from dataclasses import asdict
from .contracts import KnowledgeEntry, KnowledgeNote
from .config import user_data_path
import os
import re
import json
import hashlib
import uuid
from datetime import datetime

knowledge_bp = Blueprint("knowledge", __name__)

# 预置技术关键词表（v1规则匹配，后续可引入向量检索）
TECH_KEYWORDS = [
    "Python", "Flask", "FastAPI", "Django", "React", "Vue", "TypeScript",
    "JavaScript", "Node.js", "Docker", "Kubernetes", "Git", "GitHub",
    "Pytest", "SQLite", "PostgreSQL", "MySQL", "Redis", "MongoDB",
    "HTML", "CSS", "Tailwind", "Bootstrap", "jQuery",
    "MCP", "LLM", "Agent", "RAG", "Prompt", "OpenAI", "Claude",
    "Playwright", "Selenium", "Puppeteer",
    "Pandas", "NumPy", "Matplotlib", "Jupyter",
    "Linux", "Bash", "PowerShell", "Nginx",
    "JWT", "OAuth", "REST", "GraphQL", "WebSocket",
    "CI/CD", "Jenkins", "GitHub Actions",
]

# 解决方案关键词
SOLUTION_KEYWORDS = ["修复", "解决", "fix", "solved", "debug", "调试", "bug", "error", "报错"]


def _generate_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


@knowledge_bp.route("/knowledge", methods=["GET"])
def get_knowledge():
    """读取全部知识数据"""
    data_dir = current_app.config["DATA_DIR"]
    data = read_knowledge_data(data_dir)
    return jsonify(data)


@knowledge_bp.route("/knowledge", methods=["POST"])
def save_knowledge():
    """保存全部知识数据"""
    data_dir = current_app.config["DATA_DIR"]
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "invalid JSON body"}), 400

    if "schema_version" not in data:
        data["schema_version"] = "1.0"
    if "extracted" not in data:
        data["extracted"] = []
    if "notes" not in data:
        data["notes"] = []

    success = write_knowledge_data(data_dir, data)
    if success:
        return jsonify({"status": "ok", "saved": True})
    else:
        return jsonify({"error": "write failed"}), 500


@knowledge_bp.route("/knowledge/note", methods=["POST"])
def add_note():
    """添加笔记"""
    data_dir = current_app.config["DATA_DIR"]
    body = request.get_json(silent=True)
    if not body or "title" not in body:
        return jsonify({"error": "missing 'title' field"}), 400

    title = body["title"]
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title must be non-empty string"}), 400

    data = read_knowledge_data(data_dir)
    note = {
        "id": _generate_id(),
        "title": title.strip(),
        "category": body.get("category", ""),
        "content": body.get("content", ""),
        "tags": body.get("tags", []),
        "created_at": _now_iso()
    }
    data["notes"].append(note)

    success = write_knowledge_data(data_dir, data)
    if success:
        return jsonify({"status": "ok", "note": note})
    else:
        return jsonify({"error": "write failed"}), 500


@knowledge_bp.route("/knowledge/note/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    """删除笔记"""
    data_dir = current_app.config["DATA_DIR"]
    data = read_knowledge_data(data_dir)

    original_len = len(data["notes"])
    data["notes"] = [n for n in data["notes"] if n.get("id") != note_id]

    if len(data["notes"]) == original_len:
        return jsonify({"error": "note not found"}), 404

    success = write_knowledge_data(data_dir, data)
    if success:
        return jsonify({"status": "ok", "deleted": True})
    else:
        return jsonify({"error": "write failed"}), 500


@knowledge_bp.route("/knowledge/entry/<entry_id>", methods=["PUT"])
def update_entry(entry_id):
    """更新条目（标签/掌握度/备注）"""
    data_dir = current_app.config["DATA_DIR"]
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "invalid JSON body"}), 400

    data = read_knowledge_data(data_dir)
    found = False
    for entry in data["extracted"]:
        if entry.get("id") == entry_id:
            if "tags" in body:
                entry["tags"] = body["tags"]
            if "mastery" in body:
                entry["mastery"] = body["mastery"]
            if "user_notes" in body:
                entry["user_notes"] = body["user_notes"]
            found = True
            break

    if not found:
        return jsonify({"error": "entry not found"}), 404

    success = write_knowledge_data(data_dir, data)
    if success:
        return jsonify({"status": "ok", "updated": True})
    else:
        return jsonify({"error": "write failed"}), 500


@knowledge_bp.route("/knowledge/extract", methods=["GET"])
def extract_knowledge():
    """从memory文件提取知识条目

    扫描 memory_main.md + docs_rj/memory_rj/*.md，提取：
    - 技术关键词（SKILL类型）
    - 项目名（EXPERIENCE类型，从##标题提取）
    - 解决方案（SOLUTION类型，从修复/解决/fix附近提取）
    """
    skill_root = current_app.config["SKILL_ROOT"]
    data_dir = current_app.config["DATA_DIR"]

    # 收集待扫描的文件
    scan_files = []

    # 1. memory_main.md
    memory_main_path = str(user_data_path.get_memory_main_path())
    if os.path.exists(memory_main_path):
        scan_files.append(("memory/memory_main.md", memory_main_path))

    # 2. docs_rj/memory_rj/*.md
    memory_rj_dir = str(user_data_path.get_docs_rj_path() / "memory_rj")
    if os.path.isdir(memory_rj_dir):
        for fname in sorted(os.listdir(memory_rj_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(memory_rj_dir, fname)
                scan_files.append((f"docs_rj/memory_rj/{fname}", fpath))

    # 3. docs_rj/spec_rj/*.md（spec文件也包含技术决策）
    spec_rj_dir = str(user_data_path.get_docs_rj_path() / "spec_rj")
    if os.path.isdir(spec_rj_dir):
        for fname in sorted(os.listdir(spec_rj_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(spec_rj_dir, fname)
                scan_files.append((f"docs_rj/spec_rj/{fname}", fpath))

    entries = []
    seen_names = set()  # 去重

    for rel_path, abs_path in scan_files:
        content = read_markdown_file(abs_path)
        if not content:
            continue

        lines = content.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # 提取技术关键词（SKILL类型）
            for kw in TECH_KEYWORDS:
                kw_lower = kw.lower()
                # 单词边界匹配
                pattern = r'(?<![a-zA-Z0-9_])' + re.escape(kw_lower) + r'(?![a-zA-Z0-9_])'
                if re.search(pattern, line_lower):
                    entry_key = (kw, "SKILL")
                    if entry_key not in seen_names:
                        seen_names.add(entry_key)
                        entries.append({
                            "id": _generate_id(),
                            "type": "SKILL",
                            "name": kw,
                            "context": line.strip()[:200],
                            "source_file": rel_path,
                            "source_line": i + 1,
                            "tags": [],
                            "mastery": None,
                            "user_notes": ""
                        })

            # 提取项目名（EXPERIENCE类型，从##标题提取）
            if line.startswith("## ") and not line.startswith("## §"):
                project_name = line[3:].strip()
                # 过滤掉太短或模板格式的标题
                if len(project_name) > 2 and not project_name.startswith("{"):
                    entry_key = (project_name, "EXPERIENCE")
                    if entry_key not in seen_names:
                        seen_names.add(entry_key)
                        entries.append({
                            "id": _generate_id(),
                            "type": "EXPERIENCE",
                            "name": project_name,
                            "context": line.strip()[:200],
                            "source_file": rel_path,
                            "source_line": i + 1,
                            "tags": [],
                            "mastery": None,
                            "user_notes": ""
                        })

            # 提取解决方案（SOLUTION类型）
            for sol_kw in SOLUTION_KEYWORDS:
                if sol_kw in line_lower:
                    # 取当前行+下一行作为上下文
                    ctx = line.strip()
                    if i + 1 < len(lines):
                        ctx += " " + lines[i + 1].strip()
                    # 生成唯一key（解决方案不去重，因为不同上下文有价值）
                    entries.append({
                        "id": _generate_id(),
                        "type": "SOLUTION",
                        "name": line.strip()[:80],
                        "context": ctx[:200],
                        "source_file": rel_path,
                        "source_line": i + 1,
                        "tags": [],
                        "mastery": None,
                        "user_notes": ""
                    })
                    break  # 一行只算一个解决方案

    # 合并到已有数据（保留用户标注的tags/mastery/user_notes）
    existing = read_knowledge_data(data_dir)
    existing_entries = {e["id"]: e for e in existing.get("extracted", [])}
    existing_by_name = {}
    for e in existing.get("extracted", []):
        key = (e.get("name", ""), e.get("type", ""))
        if key not in existing_by_name:
            existing_by_name[key] = e

    merged = []
    for new_entry in entries:
        key = (new_entry["name"], new_entry["type"])
        if key in existing_by_name:
            # 保留用户标注，更新context/source
            old = existing_by_name[key]
            new_entry["tags"] = old.get("tags", [])
            new_entry["mastery"] = old.get("mastery")
            new_entry["user_notes"] = old.get("user_notes", "")
            new_entry["id"] = old["id"]  # 保留原ID
        merged.append(new_entry)

    # 保存提取结果
    existing["extracted"] = merged
    write_knowledge_data(data_dir, existing)

    return jsonify({
        "status": "ok",
        "total_entries": len(merged),
        "by_type": {
            "SKILL": len([e for e in merged if e["type"] == "SKILL"]),
            "EXPERIENCE": len([e for e in merged if e["type"] == "EXPERIENCE"]),
            "SOLUTION": len([e for e in merged if e["type"] == "SOLUTION"])
        },
        "scanned_files": len(scan_files)
    })


@knowledge_bp.route("/knowledge/sources", methods=["GET"])
def list_sources():
    """列出记忆源文件（只读浏览）"""
    skill_root = current_app.config["SKILL_ROOT"]

    sources = []

    # memory_main.md
    memory_main_path = str(user_data_path.get_memory_main_path())
    if os.path.exists(memory_main_path):
        sources.append({
            "path": "memory/memory_main.md",
            "name": "全局记忆 (memory_main.md)",
            "size": os.path.getsize(memory_main_path)
        })

    # docs_rj/memory_rj/*.md
    memory_rj_dir = str(user_data_path.get_docs_rj_path() / "memory_rj")
    if os.path.isdir(memory_rj_dir):
        for fname in sorted(os.listdir(memory_rj_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(memory_rj_dir, fname)
                sources.append({
                    "path": f"docs_rj/memory_rj/{fname}",
                    "name": fname,
                    "size": os.path.getsize(fpath)
                })

    return jsonify(sources)


@knowledge_bp.route("/knowledge/source/<path:file_path>", methods=["GET"])
def read_source(file_path):
    """读取记忆源文件内容（只读）"""
    skill_root = current_app.config["SKILL_ROOT"]

    # 安全检查：只允许 memory/ 和 docs_rj/ 下的 .md 文件
    if not file_path.endswith(".md"):
        return jsonify({"error": "only .md files allowed"}), 400
    if not (file_path.startswith("memory/") or file_path.startswith("docs_rj/")):
        return jsonify({"error": "access denied"}), 403

    abs_path = os.path.join(skill_root, file_path.replace("/", os.sep))
    # 防止路径穿越
    real_path = os.path.realpath(abs_path)
    if not real_path.startswith(os.path.realpath(skill_root)):
        return jsonify({"error": "path traversal detected"}), 403

    content = read_markdown_file(abs_path)
    if not content:
        return jsonify({"error": "file not found or empty"}), 404

    return jsonify({
        "path": file_path,
        "content": content,
        "size": len(content)
    })


def _parse_memory_entries(content, project_name, source_file=""):
    """解析 memory 条目格式，返回结构化条目列表

    格式：
        ### 记忆条目 · {task_name}（{timestamp}）
        **意图**：{intent}
        **上下文**：{context}
        **工具**：{tools}  (逗号分隔)
        **反馈**：{feedback}
        **结果**：{outcome}
        **标签**：{tags}  (逗号分隔)

        正文body...
    """
    if not content:
        return []

    entries = []
    # 匹配每个条目头
    header_pattern = re.compile(r'### 记忆条目 · (.+?)（(.+?)）')
    headers = list(header_pattern.finditer(content))

    # 六个字段名
    field_names = ["意图", "上下文", "工具", "反馈", "结果", "标签"]
    field_pattern = re.compile(
        r'\*\*(' + '|'.join(field_names) + r')\*\*：\s*(.*?)(?=\n\*\*|\n\n|\n###|\Z)',
        re.DOTALL
    )

    for i, m in enumerate(headers):
        task_name = m.group(1).strip()
        timestamp = m.group(2).strip()
        header_end = m.end()

        # 下一个 ### 或 ## 的位置（用于截断 body）
        next_section_match = re.search(r'\n(###|##) ', content[header_end:])
        if next_section_match:
            section_end = header_end + next_section_match.start()
        else:
            section_end = len(content)

        section_text = content[header_end:section_end]

        # 匹配六个字段
        fields = {}
        for fm in field_pattern.finditer(section_text):
            fields[fm.group(1)] = fm.group(2).strip()

        # tools 和 tags 按逗号分隔
        tools_raw = fields.get("工具", "")
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()] if tools_raw else []

        tags_raw = fields.get("标签", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        # body = 结构化头之后到下一个 ### 或 ## 之间的内容，前 300 字截断
        # 找到六个字段块结束位置之后的剩余内容作为 body
        all_field_matches = list(field_pattern.finditer(section_text))
        if all_field_matches:
            body_start = all_field_matches[-1].end()
            body = section_text[body_start:].strip()
        else:
            body = section_text.strip()

        body = body[:300]

        # id = md5(task_name|timestamp)[:12]
        entry_id = hashlib.md5(f"{task_name}|{timestamp}".encode()).hexdigest()[:12]

        entries.append({
            "id": entry_id,
            "project": project_name,
            "task_name": task_name,
            "timestamp": timestamp,
            "intent": fields.get("意图", ""),
            "context": fields.get("上下文", ""),
            "tools": tools,
            "feedback": fields.get("反馈", ""),
            "outcome": fields.get("结果", ""),
            "tags": tags,
            "body": body,
            "source_file": source_file
        })

    return entries


@knowledge_bp.route("/knowledge/memories", methods=["GET"])
def get_memory_entries():
    """解析全局记忆 memory_main.md，返回记忆条目列表"""
    skill_root = current_app.config["SKILL_ROOT"]
    memory_main_path = str(user_data_path.get_memory_main_path())
    content = read_markdown_file(memory_main_path)
    if not content:
        return jsonify({"status": "ok", "entries": [], "total": 0, "projects": []})

    # 按 ## 分段
    entries = []
    projects = []
    current_project = ""
    lines = content.split("\n")
    section_lines = []

    for line in lines:
        if line.startswith("## ") and not line.startswith("## §"):
            # 先处理上一个分段
            if section_lines and current_project:
                section_content = "\n".join(section_lines)
                entries.extend(_parse_memory_entries(section_content, current_project, "memory/memory_main.md"))
                projects.append(current_project)
            current_project = line[3:].strip()
            section_lines = []
        else:
            section_lines.append(line)

    # 最后一个分段
    if section_lines and current_project:
        section_content = "\n".join(section_lines)
        entries.extend(_parse_memory_entries(section_content, current_project, "memory/memory_main.md"))
        projects.append(current_project)

    return jsonify({
        "status": "ok",
        "entries": entries,
        "total": len(entries),
        "projects": list(set(projects))
    })


@knowledge_bp.route("/knowledge/project-memories", methods=["GET"])
def list_project_memories():
    """列出 docs_rj/memory_rj/ 下的项目级记忆文件并解析"""
    skill_root = current_app.config["SKILL_ROOT"]
    memory_rj_dir = str(user_data_path.get_docs_rj_path() / "memory_rj")

    entries = []
    if os.path.isdir(memory_rj_dir):
        for fname in sorted(os.listdir(memory_rj_dir)):
            if not fname.endswith(".md"):
                continue
            if fname == "INDEX.md" or fname.startswith("TASK_STATE_"):
                continue
            fpath = os.path.join(memory_rj_dir, fname)
            content = read_markdown_file(fpath)
            if not content:
                continue
            project = fname.replace(".md", "")
            file_entries = _parse_memory_entries(content, project, f"docs_rj/memory_rj/{fname}")
            entries.extend(file_entries)

    return jsonify({
        "status": "ok",
        "entries": entries,
        "total": len(entries)
    })


@knowledge_bp.route("/knowledge/promote", methods=["POST"])
def promote_memories():
    """将项目级记忆提升到全局 memory_main.md"""
    skill_root = current_app.config["SKILL_ROOT"]
    body = request.get_json(silent=True)
    if not body or "files" not in body:
        return jsonify({"error": "missing 'files' field"}), 400

    files = body["files"]
    if not isinstance(files, list) or len(files) == 0:
        return jsonify({"error": "files must be non-empty list"}), 400

    memory_main_path = str(user_data_path.get_memory_main_path())
    memory_rj_dir = str(user_data_path.get_docs_rj_path() / "memory_rj")

    # 读现有全局记忆
    existing_content = read_markdown_file(memory_main_path)
    if not existing_content:
        existing_content = ""

    # 提取已有的 task_name 用于去重
    existing_task_names = set()
    for match in re.finditer(r'### 记忆条目 · (.+?)（', existing_content):
        existing_task_names.add(match.group(1).strip())

    promoted = 0
    skipped = 0
    skipped_tasks = []
    details = []

    # 确保有 ## pdca-skill-public v1.0 分段
    target_section = "## pdca-skill-public v1.0"

    for fname in files:
        fpath = os.path.join(memory_rj_dir, fname)
        if not os.path.exists(fpath):
            details.append({"file": fname, "status": "not_found"})
            continue

        file_content = read_markdown_file(fpath)
        if not file_content:
            details.append({"file": fname, "status": "empty"})
            continue

        # 解析文件中的条目
        file_entries = _parse_memory_entries(file_content, "pdca-skill-public v1.0", f"docs_rj/memory_rj/{fname}")

        # 检查去重
        all_exist = all(e["task_name"] in existing_task_names for e in file_entries)
        if all_exist and file_entries:
            skipped += 1
            skipped_tasks.extend([e["task_name"] for e in file_entries])
            details.append({"file": fname, "status": "skipped", "tasks": [e["task_name"] for e in file_entries]})
            continue

        # 追加到全局记忆
        # 确保分段存在
        if target_section not in existing_content:
            existing_content += f"\n{target_section}\n"

        # 在分段末尾追加文件内容
        # 找到分段位置，在该分段的下一个 ## 之前插入
        section_idx = existing_content.index(target_section)
        after_section = existing_content[section_idx + len(target_section):]

        # 找下一个 ## 的位置
        next_section_match = re.search(r'\n## ', after_section)
        if next_section_match:
            insert_pos = section_idx + len(target_section) + next_section_match.start()
            insert_content = "\n" + file_content.strip() + "\n"
            existing_content = existing_content[:insert_pos] + insert_content + existing_content[insert_pos:]
        else:
            existing_content = existing_content.rstrip() + "\n" + file_content.strip() + "\n"

        # 更新已存在的 task_name
        for e in file_entries:
            existing_task_names.add(e["task_name"])

        promoted += 1
        details.append({"file": fname, "status": "promoted", "tasks": [e["task_name"] for e in file_entries]})

    # 写回
    os.makedirs(os.path.dirname(memory_main_path), exist_ok=True)
    with open(memory_main_path, 'w', encoding='utf-8') as f:
        f.write(existing_content)

    return jsonify({
        "status": "ok",
        "promoted": promoted,
        "skipped": skipped,
        "skipped_tasks": skipped_tasks,
        "details": details
    })


# 时间戳目录名正则：YYYYMMDD-HHMMSS 格式（对齐 learn_tidy.py / memory_distill.py 产出格式）
_TIMESTAMP_DIR_RE = re.compile(r'^\d{8}-\d{6}$')


@knowledge_bp.route("/knowledge/lessons", methods=["GET"])
def get_lessons():
    """获取经验库（memory_distill 产出的 lessons.json）。

    从 docs_rj/learn_rj/{timestamp}/lessons.json 读取最新的经验库。
    路径对齐 user_data_path.get_docs_rj_path() / "learn_rj"（与 learn_tidy.py 一致），
    不是 DATA_DIR/learn_rj（DATA_DIR 是 server_lite_data/，与 docs_rj/ 平级兄弟）。

    边界处理：
    - learn_rj 目录不存在 → 200 + 空经验库 + message
    - 时间戳目录存在但无 lessons.json → 跳过，继续找下一个；全找不到 → 200 + 空经验库
    - lessons.json 损坏 → 502 + 错误信息（Bad Gateway，上游数据源异常）
    """
    docs_rj_path = user_data_path.get_docs_rj_path()
    learn_dir = os.path.join(str(docs_rj_path), "learn_rj")
    if not os.path.isdir(learn_dir):
        return jsonify({
            "total_lessons": 0,
            "lessons": [],
            "message": "无经验库（learn_rj 目录不存在，请先运行 distill）"
        })

    # 列出所有时间戳目录，按名称降序排列（YYYYMMDD-HHMMSS 字典序 = 时间序）
    # 过滤非时间戳目录名（如临时目录、备份目录等），避免误读
    subdirs = []
    for name in os.listdir(learn_dir):
        full_path = os.path.join(learn_dir, name)
        if os.path.isdir(full_path) and _TIMESTAMP_DIR_RE.match(name):
            subdirs.append(name)
    subdirs.sort(reverse=True)

    for subdir in subdirs:
        lessons_path = os.path.join(learn_dir, subdir, "lessons.json")
        if not os.path.isfile(lessons_path):
            continue
        try:
            with open(lessons_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except (json.JSONDecodeError, ValueError) as e:
            return jsonify({
                "error": "lessons.json 解析失败: %s" % str(e),
                "source": "learn_rj/%s/lessons.json" % subdir,
            }), 502
        except OSError as e:
            return jsonify({
                "error": "lessons.json 读取失败: %s" % str(e),
                "source": "learn_rj/%s/lessons.json" % subdir,
            }), 500

    return jsonify({
        "total_lessons": 0,
        "lessons": [],
        "message": "无经验库（未找到 lessons.json，请先运行 distill）"
    })

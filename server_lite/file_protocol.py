"""文件层协议：sidecar JSON 读写 + 项目扫描

文件层是前端后端 agent 三方的共同底座。
文件格式约定 = 协议（spec §4.5）。
"""
import json
import os
from datetime import datetime


def read_sidecar_json(filepath: str) -> dict:
    """读取 sidecar JSON，不存在/解析失败返回空 dict"""
    json_path = filepath.rsplit('.', 1)[0] + '.json'
    if not os.path.exists(json_path):
        return {}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def write_sidecar_json(filepath: str, data: dict) -> bool:
    """写入 sidecar JSON，返回成功/失败"""
    json_path = filepath.rsplit('.', 1)[0] + '.json'
    try:
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError):
        return False


def read_knowledge_data(data_dir: str) -> dict:
    """读取知识管理数据，不存在返回默认空结构"""
    knowledge_path = os.path.join(data_dir, 'knowledge_data.json')
    if not os.path.exists(knowledge_path):
        return {"schema_version": "1.0", "extracted": [], "notes": []}
    try:
        with open(knowledge_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"schema_version": "1.0", "extracted": [], "notes": []}


def write_knowledge_data(data_dir: str, data: dict) -> bool:
    """写入知识管理数据"""
    knowledge_path = os.path.join(data_dir, 'knowledge_data.json')
    os.makedirs(data_dir, exist_ok=True)
    try:
        with open(knowledge_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError):
        return False


def read_skill_metadata(metadata_dir: str, skill_name: str) -> dict:
    """读取技能频率元数据 sidecar JSON

    元数据文件路径：metadata_dir/{skill_name}.json
    不存在返回默认零调用结构（冷启动全零，用户确认）
    """
    meta_path = os.path.join(metadata_dir, skill_name + '.json')
    if not os.path.exists(meta_path):
        return {
            "schema_version": "1.0",
            "name": skill_name,
            "pdca_tag": "",
            "call_count": 0,
            "last_called": "",
            "related_agents": []
        }
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            "schema_version": "1.0",
            "name": skill_name,
            "pdca_tag": "",
            "call_count": 0,
            "last_called": "",
            "related_agents": []
        }


def _find_docs_dir(project_path: str) -> str:
    """在项目目录下查找 docs*/ 目录（docs、docs_rj、docs_v2 等），返回第一个匹配

    返回 docs 目录的绝对路径；找不到返回空字符串
    """
    if not os.path.isdir(project_path):
        return ""
    for entry in os.listdir(project_path):
        if not entry.startswith("docs"):
            continue
        full = os.path.join(project_path, entry)
        if os.path.isdir(full):
            return full
    return ""


def scan_projects(scan_root: str) -> list:
    """扫描上级一层含 docs*/ 目录的项目目录（不递归，用户确认）

    兼容 docs/、docs_rj/、docs_v2/ 等任何以 docs 开头的目录

    返回 [{name, path, has_summary, has_spec_main, last_active, docs_dir}]
    """
    projects = []
    if not os.path.exists(scan_root):
        return projects

    for entry in os.listdir(scan_root):
        entry_path = os.path.join(scan_root, entry)
        if not os.path.isdir(entry_path):
            continue
        docs_dir = _find_docs_dir(entry_path)
        if not docs_dir:
            continue

        summary_path = os.path.join(docs_dir, "SUMMARY_RJ.md")
        if not os.path.exists(summary_path):
            for f in os.listdir(docs_dir):
                if f.upper().startswith("SUMMARY") and f.lower().endswith(".md"):
                    summary_path = os.path.join(docs_dir, f)
                    break

        spec_main_path = os.path.join(docs_dir, "spec_main_rj.md")
        if not os.path.exists(spec_main_path):
            spec_main_path = os.path.join(docs_dir, "spec_rj", "spec_main_rj.md")

        has_summary = os.path.exists(summary_path)
        has_spec_main = os.path.exists(spec_main_path)

        # last_active 取 docs 目录最新修改时间
        try:
            mtime = os.path.getmtime(docs_dir)
            last_active = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M")
        except OSError:
            last_active = ""

        projects.append({
            "name": entry,
            "path": entry_path,
            "docs_dir": docs_dir,
            "has_summary": has_summary,
            "has_spec_main": has_spec_main,
            "last_active": last_active
        })

    return projects


def scan_project_files(project_path: str) -> list:
    """扫描项目的 docs*/ 目录下所有 .md 文件，返回文件树结构

    递归扫描 docs 目录及子目录。
    每个文件返回: {name, relative_path, size, modified}
    relative_path 是相对于 docs 目录的路径。
    按路径排序。
    """
    docs_dir = _find_docs_dir(project_path)
    if not docs_dir:
        return []

    files = []
    for root, _dirs, filenames in os.walk(docs_dir):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, docs_dir)
            rel_path = rel_path.replace("\\", "/")  # 统一用 / 分隔符
            try:
                stat = os.stat(full_path)
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M")
            except OSError:
                size = 0
                modified = ""
            files.append({
                "name": fname,
                "relative_path": rel_path,
                "size": size,
                "modified": modified
            })

    files.sort(key=lambda f: f["relative_path"])
    return files


def load_scan_roots(config_path: str) -> list:
    """读取扫描根目录配置，不存在返回空列表"""
    if not os.path.exists(config_path):
        return []
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, IOError):
        return []


def save_scan_roots(config_path: str, roots: list) -> bool:
    """写入扫描根目录配置，返回成功/失败"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(roots, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError):
        return False


def read_markdown_file(filepath: str) -> str:
    """读取 markdown 文件内容，不存在返回空字符串"""
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except IOError:
        return ""


def read_md_head(filepath: str, lines: int = 30) -> str:
    """读取 markdown 文件前 N 行，不存在返回空字符串"""
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return "".join(f.readline() for _ in range(lines))
    except IOError:
        return ""




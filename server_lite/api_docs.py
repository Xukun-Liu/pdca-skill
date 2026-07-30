"""知识/docs 管理 Blueprint

端点：
- GET /api/projects — 扫描项目列表（含 docs*/ 的子目录）
- GET /api/project/<name>/summary — 读取项目的 SUMMARY
- GET /api/project/<name>/spec_main — 读取项目的 spec_main
- GET /api/project/<name>/files — 列出项目文档树
- GET /api/project/<name>/file?path=... — 读取项目指定文件
- GET /api/scan-roots — 列出所有扫描根目录
- POST /api/scan-roots — 添加扫描根目录
- DELETE /api/scan-roots — 删除扫描根目录
"""
from flask import Blueprint, jsonify, current_app, request
from .file_protocol import scan_projects, scan_project_files, read_markdown_file, load_scan_roots, save_scan_roots
from .contracts import ProjectInfo
from .config import PACKAGE_DIR, user_data_path
from dataclasses import asdict
import os
import re

# 安全：项目名白名单（允许字母数字下划线连字符空格中文点号，禁止路径穿越字符 / \ ..）
_SAFE_NAME_PATTERN = re.compile(r'^[\w\u4e00-\u9fa5 \-.]+$')


def _validate_name(name: str) -> bool:
    """校验 name 是否安全（防路径穿越）"""
    if not name or len(name) > 200:
        return False
    return bool(_SAFE_NAME_PATTERN.match(name))


def _find_docs_dir_for_project(project_path: str) -> str:
    """在项目目录下查找 docs*/ 目录（docs、docs_rj、docs_v2 等）"""
    if not os.path.isdir(project_path):
        return ""
    for entry in os.listdir(project_path):
        if entry.startswith("docs") and os.path.isdir(os.path.join(project_path, entry)):
            return os.path.join(project_path, entry)
    return ""


docs_bp = Blueprint("docs", __name__)


def _get_scan_roots_path():
    """获取 scan_roots.json 配置文件路径"""
    return str(user_data_path.get_server_lite_data_path() / "scan_roots.json")


def _collect_all_projects():
    """收集默认 SCAN_ROOT + 额外 scan_roots 中的所有项目（去重按 name）"""
    seen = set()
    result = []

    # 默认 SCAN_ROOT
    scan_root = current_app.config["SCAN_ROOT"]
    for p in scan_projects(scan_root):
        if p["name"] not in seen:
            seen.add(p["name"])
            result.append(p)

    # 额外 scan_roots
    roots = load_scan_roots(_get_scan_roots_path())
    for root in roots:
        if os.path.isdir(root):
            for p in scan_projects(root):
                if p["name"] not in seen:
                    seen.add(p["name"])
                    result.append(p)

    return result


@docs_bp.route("/projects", methods=["GET"])
def list_projects():
    """扫描默认 SCAN_ROOT + 额外 scan_roots 中含 docs*/ 的项目目录"""
    projects = _collect_all_projects()
    # 只返回 ProjectInfo 契约支持的字段（去除 docs_dir 内部字段）
    contract_fields = {f.name for f in ProjectInfo.__dataclass_fields__.values()}
    result = []
    for p in projects:
        filtered = {k: v for k, v in p.items() if k in contract_fields}
        result.append(asdict(ProjectInfo(**filtered)))
    return jsonify(result)


def _find_project_path(name):
    """在所有扫描根中查找项目路径"""
    scan_root = current_app.config["SCAN_ROOT"]
    candidate = os.path.join(scan_root, name)
    if os.path.isdir(candidate):
        return candidate

    roots = load_scan_roots(_get_scan_roots_path())
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.isdir(candidate):
            return candidate

    return None


@docs_bp.route("/project/<name>/summary", methods=["GET"])
def get_project_summary(name):
    """读取项目的 SUMMARY_RJ.md（兼容任意 docs*/ 目录）"""
    if not _validate_name(name):
        return jsonify({"error": "invalid project name", "content": ""}), 400

    project_path = _find_project_path(name)
    if not project_path:
        return jsonify({"error": "project not found", "content": ""}), 404

    docs_dir = _find_docs_dir_for_project(project_path)
    if not docs_dir:
        return jsonify({"error": "docs directory not found", "content": ""}), 404

    summary_path = os.path.join(docs_dir, "SUMMARY_RJ.md")
    if not os.path.exists(summary_path):
        for f in os.listdir(docs_dir):
            if f.upper().startswith("SUMMARY") and f.lower().endswith(".md"):
                summary_path = os.path.join(docs_dir, f)
                break

    content = read_markdown_file(summary_path)
    if not content:
        return jsonify({"error": "SUMMARY not found", "content": ""}), 404
    return jsonify({"name": name, "content": content})


@docs_bp.route("/project/<name>/spec_main", methods=["GET"])
def get_project_spec_main(name):
    """读取项目的 spec_main_rj.md（兼容任意 docs*/ 目录）"""
    if not _validate_name(name):
        return jsonify({"error": "invalid project name", "content": ""}), 400

    project_path = _find_project_path(name)
    if not project_path:
        return jsonify({"error": "project not found", "content": ""}), 404

    docs_dir = _find_docs_dir_for_project(project_path)
    if not docs_dir:
        return jsonify({"error": "docs directory not found", "content": ""}), 404

    # 尝试多个位置
    candidates = [
        os.path.join(docs_dir, "spec_main_rj.md"),
        os.path.join(docs_dir, "spec_rj", "spec_main_rj.md"),
    ]
    for path in candidates:
        content = read_markdown_file(path)
        if content:
            return jsonify({"name": name, "content": content})

    return jsonify({"error": "spec_main not found", "content": ""}), 404


@docs_bp.route("/scan-roots", methods=["GET"])
def get_scan_roots():
    """列出所有扫描根目录"""
    config_path = _get_scan_roots_path()
    roots = load_scan_roots(config_path)
    default_root = current_app.config["SCAN_ROOT"]
    return jsonify({"roots": roots, "default_root": default_root})


@docs_bp.route("/scan-roots", methods=["POST"])
def add_scan_root():
    """添加扫描根目录"""
    data = request.get_json(silent=True) or {}
    path = data.get("path", "").strip()

    if not path:
        return jsonify({"error": "path is required"}), 400

    # 校验路径必须存在且是目录
    if not os.path.isdir(path):
        return jsonify({"error": "path does not exist or is not a directory"}), 400

    config_path = _get_scan_roots_path()
    roots = load_scan_roots(config_path)

    # 去重：已存在则跳过
    if path in roots:
        return jsonify({"ok": True, "roots": roots})

    roots.append(path)
    if not save_scan_roots(config_path, roots):
        return jsonify({"error": "failed to save scan roots"}), 500

    return jsonify({"ok": True, "roots": roots})


@docs_bp.route("/scan-roots", methods=["DELETE"])
def delete_scan_root():
    """删除扫描根目录"""
    data = request.get_json(silent=True) or {}
    path = data.get("path", "").strip()

    if not path:
        return jsonify({"error": "path is required"}), 400

    default_root = current_app.config["SCAN_ROOT"]

    # 不允许删除 default_root
    if path == default_root:
        return jsonify({"error": "cannot delete default scan root"}), 400

    config_path = _get_scan_roots_path()
    roots = load_scan_roots(config_path)

    if path not in roots:
        return jsonify({"ok": True, "roots": roots})

    roots.remove(path)
    if not save_scan_roots(config_path, roots):
        return jsonify({"error": "failed to save scan roots"}), 500

    return jsonify({"ok": True, "roots": roots})


def _find_project_path(name):
    """在所有扫描根中查找项目路径"""
    scan_root = current_app.config["SCAN_ROOT"]
    candidate = os.path.join(scan_root, name)
    if os.path.isdir(candidate):
        return candidate

    roots = load_scan_roots(_get_scan_roots_path())
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.isdir(candidate):
            return candidate

    return None


@docs_bp.route("/project/<name>/files", methods=["GET"])
def get_project_files(name):
    """列出项目文档树"""
    if not _validate_name(name):
        return jsonify({"error": "invalid project name", "files": []}), 400

    project_path = _find_project_path(name)
    if not project_path:
        return jsonify({"error": "project not found", "files": []}), 404

    files = scan_project_files(project_path)
    return jsonify({"name": name, "files": files})


@docs_bp.route("/project/<name>/file", methods=["GET"])
def get_project_file(name):
    """读取项目 docs*/ 下的指定文件"""
    if not _validate_name(name):
        return jsonify({"error": "invalid project name", "content": ""}), 400

    relative_path = request.args.get("path", "").strip()
    if not relative_path:
        return jsonify({"error": "path parameter is required", "content": ""}), 400

    # 安全：禁止路径穿越
    if ".." in relative_path.split(os.sep) or ".." in relative_path.split("/"):
        return jsonify({"error": "invalid path", "content": ""}), 400

    project_path = _find_project_path(name)
    if not project_path:
        return jsonify({"error": "project not found", "content": ""}), 404

    docs_dir = _find_docs_dir_for_project(project_path)
    if not docs_dir:
        return jsonify({"error": "docs directory not found", "content": ""}), 404

    file_path = os.path.join(docs_dir, relative_path)

    # 安全：确保解析后的路径仍在 docs_dir 内
    if not os.path.abspath(file_path).startswith(os.path.abspath(docs_dir)):
        return jsonify({"error": "path traversal denied", "content": ""}), 400

    # 只允许 .md 文件
    if not file_path.lower().endswith(".md"):
        return jsonify({"error": "only .md files are allowed", "content": ""}), 400

    content = read_markdown_file(file_path)
    if not content:
        return jsonify({"error": "file not found", "content": ""}), 404

    return jsonify({"name": name, "path": relative_path, "content": content})

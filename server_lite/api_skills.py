"""技能管理 Blueprint

端点：
- GET /api/skills — 列出 references/ 全部参考模块 + 频率统计
- GET /api/skill/<name>/content — 读取参考模块 md 前 30 行（访问时call_count自增）
- DELETE /api/skill/<name> — 删除零调用参考模块（二次确认在前端）
- GET /api/agents — 列出 agents_rj/ 全部子机器人
"""
from flask import Blueprint, jsonify, current_app
from .file_protocol import read_skill_metadata, read_md_head, read_markdown_file, write_sidecar_json
from .contracts import SkillInfo, AgentInfo
from dataclasses import asdict
from datetime import datetime
import os
import re
import json

# 安全：技能名白名单（允许字母数字下划线连字符，防路径穿越）
_SAFE_SKILL_NAME = re.compile(r'^[\w\-]+$')

skills_bp = Blueprint("skills", __name__)


def _extract_pdca_tag(filepath: str) -> str:
    """从参考模块 md 头部提取 PDCA 标签（如 P.route）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            head = f.read(500)
        # 匹配 PDCA 标签：兼容 "PDCA: P.route" / "PDCA标签：P.design" / "PDCA 标签：P.route" 等格式
        match = re.search(r'PDCA[^：:\n]*[:：]\s*([PDCA]\.\w+)', head)
        if match:
            return match.group(1)
    except IOError:
        pass
    return ""


def _extract_description(filepath: str) -> str:
    """从参考模块 md 提取描述：优先从 > 用途/描述/说明 引用行提取，否则取第一个非标题非注释的有效文本行"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            in_multiline_comment = False
            fallback_text = ""
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('<!--'):
                    if '-->' not in line:
                        in_multiline_comment = True
                    continue
                if in_multiline_comment:
                    if '-->' in line:
                        in_multiline_comment = False
                    continue
                if line.startswith('---') or line.startswith('/*') or line.startswith('*/'):
                    continue
                if re.match(r'^#+\s', line):
                    continue
                if line.startswith('>'):
                    quote_text = line.lstrip('>').strip()
                    m = re.match(r'(?:用途|描述|说明|功能)[:：]\s*(.+)', quote_text)
                    if m:
                        desc = m.group(1).strip()
                        if desc:
                            return desc[:100]
                    continue
                list_match = re.match(r'^[-*+]\s+(.+)', line)
                if list_match:
                    text = list_match.group(1).strip()
                    if not fallback_text and text and not text.startswith('**') and not text.startswith('🔴') and not text.startswith('📖'):
                        fallback_text = text[:100]
                    continue
                num_match = re.match(r'^\d+\.\s+(.+)', line)
                if num_match:
                    text = num_match.group(1).strip()
                    if not fallback_text and text:
                        fallback_text = text[:100]
                    continue
                text = re.sub(r'^[*_`#]+|[*_`#]+$', '', line).strip()
                if text and not re.match(r'^[\W_]+$', text):
                    return text[:100]
            if fallback_text:
                return fallback_text
    except IOError:
        pass
    return ""


def _frequency_level(call_count: int) -> str:
    """频率分级：高≥20/中5-19/低1-4/零0"""
    if call_count >= 20:
        return "high"
    elif call_count >= 5:
        return "medium"
    elif call_count >= 1:
        return "low"
    else:
        return "zero"


def _load_agent_config(agents_dir: str) -> dict:
    """加载 subagent_config_rj.json，返回 {skill_basename: [agent_display_names]} 反向映射"""
    config_path = os.path.join(agents_dir, "subagent_config_rj.json")
    skill_to_agents = {}
    if not os.path.exists(config_path):
        return skill_to_agents
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        for agent in config.get("agents", []):
            agent_name = agent.get("name", "")
            display_name = agent_name.replace("_agent_riji", "").replace("_riji", "")
            for kn in agent.get("knowledge", []):
                if isinstance(kn, str) and kn.startswith("references/") and kn.endswith(".md"):
                    base = kn[len("references/"):-len(".md")]
                    skill_to_agents.setdefault(base, []).append(display_name)
    except (json.JSONDecodeError, IOError):
        pass
    return skill_to_agents


@skills_bp.route("/skills", methods=["GET"])
def list_skills():
    """列出 references/ 全部参考模块 + 频率统计"""
    references_dir = current_app.config["REFERENCES_DIR"]
    metadata_dir = current_app.config["METADATA_DIR"]
    agents_dir = current_app.config["AGENTS_DIR"]

    if not os.path.exists(references_dir):
        return jsonify([])

    skill_to_agents = _load_agent_config(agents_dir)

    skills = []
    for entry in sorted(os.listdir(references_dir)):
        if not entry.endswith('.md'):
            continue
        skill_name = entry[:-3]  # 去掉 .md
        filepath = os.path.join(references_dir, entry)

        # 读取 sidecar JSON 元数据（冷启动全零）
        meta = read_skill_metadata(metadata_dir, skill_name)
        call_count = meta.get("call_count", 0)
        pdca_tag = meta.get("pdca_tag", "") or _extract_pdca_tag(filepath)
        description = _extract_description(filepath)
        last_called = meta.get("last_called", "")
        related_agents = skill_to_agents.get(skill_name, [])

        skills.append(asdict(SkillInfo(
            name=skill_name,
            pdca_tag=pdca_tag,
            description=description,
            call_count=call_count,
            frequency_level=_frequency_level(call_count),
            last_called=last_called,
            related_agents=related_agents
        )))

    return jsonify(skills)


@skills_bp.route("/skill/<name>/content", methods=["GET"])
def get_skill_content(name):
    """读取参考模块 md 前 30 行，同时更新调用计数和last_called"""
    if not _SAFE_SKILL_NAME.match(name):
        return jsonify({"error": "invalid skill name", "content": ""}), 400
    references_dir = current_app.config["REFERENCES_DIR"]
    metadata_dir = current_app.config["METADATA_DIR"]
    filepath = os.path.join(references_dir, name + ".md")

    content = read_md_head(filepath, 30)
    if not content:
        return jsonify({"error": "skill not found", "content": ""}), 404

    meta = read_skill_metadata(metadata_dir, name)
    meta["call_count"] = meta.get("call_count", 0) + 1
    meta["last_called"] = datetime.now().isoformat(timespec="seconds")
    meta["name"] = name
    json_path = os.path.join(metadata_dir, name + ".json")
    write_sidecar_json(json_path, meta)

    return jsonify({"name": name, "content": content})


@skills_bp.route("/skill/<name>", methods=["DELETE"])
def delete_skill(name):
    """删除零调用参考模块（需前端二次确认，后端校验频率为 zero 才允许删）"""
    if not _SAFE_SKILL_NAME.match(name):
        return jsonify({"error": "invalid skill name"}), 400
    references_dir = current_app.config["REFERENCES_DIR"]
    metadata_dir = current_app.config["METADATA_DIR"]
    md_path = os.path.join(references_dir, name + ".md")

    if not os.path.exists(md_path):
        return jsonify({"error": "skill not found"}), 404

    # 安全校验：只允许删除零调用的技能
    meta = read_skill_metadata(metadata_dir, name)
    call_count = meta.get("call_count", 0)
    if call_count > 0:
        return jsonify({"error": "cannot delete skill with call_count > 0", "call_count": call_count}), 403

    try:
        os.remove(md_path)
        # 同时删除 sidecar JSON
        json_path = os.path.join(metadata_dir, name + ".json")
        if os.path.exists(json_path):
            os.remove(json_path)
        return jsonify({"status": "ok", "deleted": name})
    except OSError as e:
        return jsonify({"error": str(e)}), 500


@skills_bp.route("/agents", methods=["GET"])
def list_agents():
    """列出 agents_rj/ 全部子机器人（从 subagent_config_rj.json 读取）"""
    agents_dir = current_app.config["AGENTS_DIR"]
    config_path = os.path.join(agents_dir, "subagent_config_rj.json")

    if not os.path.exists(config_path):
        return jsonify([])

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError):
        return jsonify([])

    agents = []
    for agent in config.get("agents", []):
        agents.append(asdict(AgentInfo(
            name=agent.get("name", ""),
            role=agent.get("role", ""),
            description=agent.get("description", ""),
            knowledge=agent.get("knowledge", []),
            triggers=agent.get("triggers", []),
            output_format=agent.get("output_format", [])
        )))

    return jsonify(agents)

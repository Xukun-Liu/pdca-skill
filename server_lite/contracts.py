"""API 契约单源（source of truth）

所有 API 返回类型在此定义，Flask import 用，启动时导出 /api/contracts.json 供前端校验。
解决"前端改了字段后端不知道"的漂移问题。
"""
from dataclasses import dataclass, fields, asdict
from typing import List, Optional
import json


@dataclass
class ProjectInfo:
    """项目列表返回的单个项目"""
    name: str
    path: str
    has_summary: bool
    has_spec_main: bool
    last_active: str  # ISO 格式时间


@dataclass
class SkillInfo:
    """技能列表返回的单个技能"""
    name: str
    pdca_tag: str  # 如 "P.route"
    description: str
    call_count: int
    frequency_level: str  # high/medium/low/zero
    last_called: str  # ISO 格式时间，空字符串表示从未调用
    related_agents: List[str]  # 关联的子机器人名称列表


@dataclass
class AgentInfo:
    """子机器人列表返回的单个 agent（从 subagent_config_rj.json 读取）"""
    name: str
    role: str  # 角色定位，如"方案设计专家"
    description: str  # 职责描述
    knowledge: List[str]  # 关联的参考模块文件路径列表
    triggers: List[str]  # 触发关键词列表
    output_format: List[str]  # 输出格式列表


@dataclass
class KnowledgeEntry:
    """知识管理：从对话/memory沉淀的条目"""
    id: str
    type: str  # SKILL / EXPERIENCE / SOLUTION
    name: str
    context: str  # 提取的上下文片段
    source_file: str  # 来源文件路径
    source_line: int  # 来源行号
    tags: List[str]
    mastery: Optional[str]  # beginner/familiar/proficient/expert，null=未标注
    user_notes: str  # 用户备注


@dataclass
class KnowledgeNote:
    """知识管理：用户手动添加的笔记"""
    id: str
    title: str
    category: str  # 自定义分类
    content: str
    tags: List[str]
    created_at: str  # ISO 格式


def export_contracts() -> dict:
    """导出所有 dataclass 的字段定义，供前端校验"""
    contracts = {}
    for cls in [ProjectInfo, SkillInfo, AgentInfo, KnowledgeEntry, KnowledgeNote]:
        contracts[cls.__name__] = {
            "fields": [
                {"name": f.name, "type": str(f.type)}
                for f in fields(cls)
            ]
        }
    return contracts

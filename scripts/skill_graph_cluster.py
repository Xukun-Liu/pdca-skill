#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_graph_cluster.py — 阶段2：LLM 归纳分类 + 多源差距分析

输入：skills_raw.json（左轨）+ master_taxonomy.json（右轨）
输出：skills_clustered.json（含 mastered + not_mastered + extra_mastered 三段）

核心逻辑：
  1. 读取左轨已掌握技能 + 右轨全集
  2. LLM/规则 归纳分类（3-7 类）
  3. 差距分析：
     - mastered：左轨有 ∩ 右轨有（已掌握且在全集内）
     - not_mastered：左轨无 + 右轨有（应掌握但未掌握）
     - extra_mastered：左轨有 − 右轨有（已掌握但不在全集内）

用法：
  python scripts/skill_graph_cluster.py
    --input skills_raw.json
    --taxonomy master_taxonomy.json
    --output skills_clustered.json

LLM 策略：
  - --llm-mode rule（默认）：规则分类（按 category_hint 聚合）
  - --llm-mode dialog：对话模式，导出 prompt → 用户 AI 对话 → 导入回复 JSON
  - --llm-mode api：API 模式（待实现）
"""

import os
import sys
import json
import re
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_CACHE_DIR = os.path.join(_SKILL_DIR, 'docs_rj', 'memory_rj', '.skill_graph_cache')


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class ClusteredSkill:
    """已分类的技能（含掌握状态）。"""
    name: str
    category: str
    confidence: float
    status: str  # 'mastered' / 'not_mastered' / 'extra_mastered'
    evidence_count: int = 0
    source_tools: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    # not_mastered 专属
    reason: str = ''
    roadmap_ref: str = ''
    priority: str = ''  # 'high' / 'medium' / 'low'
    learning_link: str = ''
    sources: List[str] = field(default_factory=list)  # 哪些全集源提到它
    first_seen: str = ''
    last_seen: str = ''


@dataclass
class ClusterResult:
    """阶段2最终输出。"""
    schema_version: str = '1.0'
    generated_at: str = ''
    categories: List[Dict] = field(default_factory=list)
    skills: List[Dict] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)


# ===========================================================================
# 工具函数
# ===========================================================================

def _load_json(filepath: str) -> Optional[dict]:
    """安全加载 JSON 文件。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error('加载 JSON 失败 %s: %s', filepath, e)
        return None


def _atomic_write_json(filepath: str, data) -> bool:
    """原子写入 JSON。"""
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    tmp = filepath + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filepath)
        return True
    except (OSError, IOError) as e:
        logger.error('写入 JSON 失败 %s: %s', filepath, e)
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def _normalize_skill_name(name: str) -> str:
    """归一化技能名用于比较（小写+去空格+去标点）。"""
    # 去掉版本号、括号说明、常见后缀
    cleaned = re.sub(r'\s*[\(（].*?[\)）]', '', name)
    cleaned = re.sub(r'\s*\.js$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', '', cleaned).lower()
    return cleaned.strip(' -_/.')


# ===========================================================================
# LLM 归纳分类（对话模式 + 规则降级）
# ===========================================================================

def _map_skills_to_llm_categories(
    raw_skills: List[dict],
    llm_result: Dict,
) -> Tuple[List[dict], Dict]:
    """把 LLM 对话回复的分类映射到 raw_skills。

    LLM 回复格式（由 _export_llm_dialog_prompt 约定）：
    {
      "categories": [{"name": "分类名", "skill_count": N, "avg_confidence": 0.X}],
      "category_map": {"分类名": ["技能名1", "技能名2", ...]}
    }
    """
    category_map = llm_result.get('category_map', {})

    # 构建技能名 → 分类 的映射（归一化技能名匹配）
    skill_to_category: Dict[str, str] = {}
    for cat_name, skill_names in category_map.items():
        for sn in skill_names:
            norm = _normalize_skill_name(sn)
            if norm:
                skill_to_category[norm] = cat_name

    # 更新 raw_skills 的 category_hint（浅拷贝不修改原数据）
    updated_skills: List[dict] = []
    for skill in raw_skills:
        skill_copy = dict(skill)
        norm = _normalize_skill_name(skill_copy.get('name', ''))
        if norm in skill_to_category:
            skill_copy['category_hint'] = skill_to_category[norm]
        updated_skills.append(skill_copy)

    # 构建 category_info（保留 LLM 返回的 categories + 补全 category_map 的技能对象）
    categories = llm_result.get('categories', [])
    mapped_category_map: Dict[str, List[dict]] = {}
    for cat_name, skill_names in category_map.items():
        norm_names = {_normalize_skill_name(sn) for sn in skill_names}
        mapped_category_map[cat_name] = [
            s for s in updated_skills
            if _normalize_skill_name(s.get('name', '')) in norm_names
        ]

    logger.info('LLM 对话分类完成: %d 个分类', len(categories))
    return updated_skills, {'categories': categories, 'category_map': mapped_category_map}


def cluster_with_llm(
    raw_skills: List[dict],
    master_taxonomy: List[dict],
    llm_response_path: Optional[str] = None,
) -> Tuple[List[dict], Dict]:
    """LLM 归纳分类（对话模式）。

    通过人工对话方式使用 LLM 归纳分类：
    1. 用 --llm-mode dialog 导出 prompt 到文件（由 main 函数调用 _export_llm_dialog_prompt）
    2. 用户把 prompt 复制到 AI 对话框，获取 LLM 回复 JSON
    3. 用 --llm-response <回复.json> 导入回复
    4. 本函数解析回复并映射技能到 LLM 归纳的分类

    如果 llm_response_path 为 None 或导入失败，降级到规则版本。

    完整流程见 --llm-mode dialog 的使用说明。
    """
    if llm_response_path:
        llm_result = _load_json(llm_response_path)
        if llm_result and 'categories' in llm_result and 'category_map' in llm_result:
            logger.info('cluster_with_llm: LLM 对话回复已导入，%d 个分类',
                        len(llm_result.get('categories', [])))
            return _map_skills_to_llm_categories(raw_skills, llm_result)
        logger.warning('cluster_with_llm: LLM 回复格式无效（缺 categories 或 category_map），降级到规则版本')

    logger.info('cluster_with_llm: 降级到规则版本（用 --llm-mode dialog --llm-response <文件> 启用 LLM 对话分类）')
    return cluster_with_rules(raw_skills, master_taxonomy)


def _export_llm_dialog_prompt(
    raw_skills: List[dict],
    master_taxonomy: List[dict],
    output_path: str,
) -> bool:
    """导出 LLM 对话模式的 prompt 到文件。

    用户把这个文件内容复制到 AI 对话框，AI 回复 JSON 后保存，
    再用 --llm-response 参数导入。

    Prompt 要求 AI 输出以下 JSON 格式：
    {
      "categories": [
        {"name": "分类名", "skill_count": N, "avg_confidence": 0.X},
        ...
      ],
      "category_map": {
        "分类名": [技能名1, 技能名2, ...],
        ...
      }
    }
    """
    # 准备技能列表（精简版，只含 name + category_hint + confidence）
    skills_summary = []
    for s in raw_skills[:100]:  # 限制 100 个避免 prompt 过长
        skills_summary.append({
            'name': s.get('name', ''),
            'category_hint': s.get('category_hint', ''),
            'confidence': s.get('confidence', 0),
        })

    prompt = f"""# 技能图谱 LLM 归纳分类请求

请把以下 {len(skills_summary)} 个已掌握技能归纳为 3-7 个分类。

## 已掌握技能列表

```json
{json.dumps(skills_summary, ensure_ascii=False, indent=2)}
```

## 输出要求

请输出以下 JSON 格式（不要输出其他内容）：

```json
{{
  "categories": [
    {{"name": "分类名1", "skill_count": N, "avg_confidence": 0.X}},
    ...
  ],
  "category_map": {{
    "分类名1": ["技能名1", "技能名2", ...],
    ...
  }}
}}
```

## 规则

1. 分类数必须在 3-7 个之间
2. 每个技能必须归到一个分类下
3. 分类名要简洁（2-6 字）
4. avg_confidence 是该分类下技能的平均置信度
5. 只输出 JSON，不要输出其他内容

## 你的回复
"""

    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        logger.info('LLM 对话 prompt 导出: %s', output_path)
        return True
    except (OSError, IOError) as e:
        logger.error('导出 prompt 失败: %s', e)
        return False


def cluster_with_rules(raw_skills: List[dict], master_taxonomy: List[dict]) -> Tuple[List[dict], Dict]:
    """规则分类：按 category_hint 聚合，强制 3-7 类。"""
    # 收集所有分类
    category_map: Dict[str, List[dict]] = defaultdict(list)

    for skill in raw_skills:
        cat = skill.get('category_hint', '其他')
        if not cat:
            cat = '其他'
        category_map[cat].append(skill)

    # 如果分类数 < 3，合并到"其他"
    if len(category_map) < 3:
        merged = []
        for skills in category_map.values():
            merged.extend(skills)
        category_map = {'其他技能': merged}

    # 如果分类数 > 7，按技能数排序，合并末尾小分类到"其他"
    if len(category_map) > 7:
        sorted_cats = sorted(category_map.items(), key=lambda x: len(x[1]), reverse=True)
        top_cats = sorted_cats[:6]
        rest_cats = sorted_cats[6:]

        category_map = dict(top_cats)
        merged_rest = []
        for _, skills in rest_cats:
            merged_rest.extend(skills)
        if merged_rest:
            category_map['其他技能'] = merged_rest

    # 构建分类列表
    categories = []
    for cat_name, skills in category_map.items():
        categories.append({
            'name': cat_name,
            'skill_count': len(skills),
            'avg_confidence': round(
                sum(s.get('confidence', 0) for s in skills) / max(len(skills), 1), 2
            ),
        })

    # 按技能数降序
    categories.sort(key=lambda c: c['skill_count'], reverse=True)

    logger.info('规则分类: %d 个分类', len(categories))
    return raw_skills, {'categories': categories, 'category_map': dict(category_map)}


# ===========================================================================
# 差距分析（mastered / not_mastered / extra_mastered）
# ===========================================================================

def gap_analysis(
    raw_skills: List[dict],
    master_taxonomy: List[dict],
    category_info: Dict,
) -> List[ClusteredSkill]:
    """三段式差距分析。

    - mastered：左轨有 ∩ 右轨有
    - not_mastered：左轨无 + 右轨有
    - extra_mastered：左轨有 − 右轨有
    """
    # 归一化左轨技能名集合
    mastered_names: Dict[str, dict] = {}  # normalized_name → raw_skill
    for skill in raw_skills:
        norm = _normalize_skill_name(skill.get('name', ''))
        if norm:
            mastered_names[norm] = skill

    # 归一化右轨技能名集合
    taxonomy_names: Dict[str, dict] = {}  # normalized_name → taxonomy_skill
    for skill in master_taxonomy:
        norm = _normalize_skill_name(skill.get('name', ''))
        if norm:
            taxonomy_names[norm] = skill

    mastered_norm_set = set(mastered_names.keys())
    taxonomy_norm_set = set(taxonomy_names.keys())

    # 集合运算
    mastered_intersection = mastered_norm_set & taxonomy_norm_set  # 已掌握 ∩ 全集
    not_mastered_set = taxonomy_norm_set - mastered_norm_set       # 全集 - 已掌握
    extra_mastered_set = mastered_norm_set - taxonomy_norm_set     # 已掌握 - 全集

    logger.info('差距分析: 已掌握∩全集=%d, 未掌握=%d, 额外掌握=%d',
                len(mastered_intersection), len(not_mastered_set), len(extra_mastered_set))

    clustered: List[ClusteredSkill] = []

    # 1. mastered（已掌握 ∩ 全集）
    category_map = category_info.get('category_map', {})
    for norm_name in mastered_intersection:
        raw = mastered_names[norm_name]
        tax = taxonomy_names[norm_name]
        evidence = raw.get('evidence', [])
        source_tools = list({e.get('source_tool', '') for e in evidence if e.get('source_tool')})

        # 时间戳
        timestamps = [e.get('timestamp', '') for e in evidence if e.get('timestamp')]
        first_seen = min(timestamps) if timestamps else ''
        last_seen = max(timestamps) if timestamps else ''

        clustered.append(ClusteredSkill(
            name=raw.get('name', ''),
            category=raw.get('category_hint', tax.get('category', '其他')),
            confidence=raw.get('confidence', 0.0),
            status='mastered',
            evidence_count=len(evidence),
            source_tools=source_tools,
            evidence_refs=[f'raw#{i}' for i in range(len(evidence))],
            sources=[tax.get('source', '')] if tax.get('source') else [],
            first_seen=first_seen,
            last_seen=last_seen,
        ))

    # 2. extra_mastered（已掌握 − 全集）
    for norm_name in extra_mastered_set:
        raw = mastered_names[norm_name]
        evidence = raw.get('evidence', [])
        source_tools = list({e.get('source_tool', '') for e in evidence if e.get('source_tool')})

        timestamps = [e.get('timestamp', '') for e in evidence if e.get('timestamp')]
        first_seen = min(timestamps) if timestamps else ''
        last_seen = max(timestamps) if timestamps else ''

        clustered.append(ClusteredSkill(
            name=raw.get('name', ''),
            category=raw.get('category_hint', '其他'),
            confidence=raw.get('confidence', 0.0),
            status='extra_mastered',
            evidence_count=len(evidence),
            source_tools=source_tools,
            evidence_refs=[f'raw#{i}' for i in range(len(evidence))],
            sources=[],
            first_seen=first_seen,
            last_seen=last_seen,
            reason='用户独有技能（不在标准全集内）',
        ))

    # 3. not_mastered（全集 − 已掌握）
    for norm_name in not_mastered_set:
        tax = taxonomy_names[norm_name]

        # 推断优先级（基于分类）
        category = tax.get('category', '')
        priority = _infer_priority(category, tax.get('source', ''))

        clustered.append(ClusteredSkill(
            name=tax.get('name', ''),
            category=category,
            confidence=0.0,
            status='not_mastered',
            evidence_count=0,
            source_tools=[],
            evidence_refs=[],
            sources=[tax.get('source', '')] if tax.get('source') else [],
            reason=f'未在记忆中检测到「{tax.get("name", "")}」相关证据',
            roadmap_ref=tax.get('source', ''),
            priority=priority,
            learning_link=tax.get('learning_link', ''),
        ))

    # 排序：mastered > extra_mastered > not_mastered，同类按 confidence 降序
    status_order = {'mastered': 0, 'extra_mastered': 1, 'not_mastered': 2}
    clustered.sort(key=lambda s: (status_order.get(s.status, 3), -s.confidence, s.name))

    logger.info('差距分析完成: 共 %d 个技能', len(clustered))
    return clustered


def _infer_priority(category: str, source: str) -> str:
    """根据分类和来源推断学习优先级。"""
    # 高优先级：核心编程语言、数据库、DevOps
    high_cats = {'编程语言', '数据库', 'DevOps与云原生', 'topic', 'subtopic'}
    if category in high_cats:
        return 'high'
    # 中优先级：框架、工具链
    medium_cats = {'前端框架', '后端框架', '工具链', '消息队列', '云平台'}
    if category in medium_cats:
        return 'medium'
    # 低优先级：其他
    return 'low'


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='阶段2：LLM 归纳分类 + 多源差距分析',
    )
    parser.add_argument(
        '--input', default=os.path.join(_CACHE_DIR, 'skills_raw.json'),
        help='skills_raw.json 路径',
    )
    parser.add_argument(
        '--taxonomy', default=os.path.join(_CACHE_DIR, 'master_taxonomy.json'),
        help='master_taxonomy.json 路径',
    )
    parser.add_argument(
        '--output', default=os.path.join(_CACHE_DIR, 'skills_clustered.json'),
        help='skills_clustered.json 输出路径',
    )
    parser.add_argument(
        '--no-cache', action='store_true',
        help='忽略缓存（当前版本无缓存逻辑，占位）',
    )
    parser.add_argument(
        '--llm-mode', choices=['rule', 'dialog', 'api'], default='rule',
        help='LLM 模式：rule=规则降级(默认) | dialog=导出prompt到文件(用户复制到对话框) | api=调LLM服务(待实现)',
    )
    parser.add_argument(
        '--llm-response', default=None,
        help='dialog 模式下导入的 LLM 回复 JSON 文件路径（用户把 AI 回复贴回来）',
    )

    args = parser.parse_args()

    # 加载输入
    raw_data = _load_json(args.input)
    if not raw_data:
        logger.error('无法加载 skills_raw.json: %s', args.input)
        sys.exit(1)

    taxonomy_data = _load_json(args.taxonomy)
    if not taxonomy_data:
        logger.error('无法加载 master_taxonomy.json: %s', args.taxonomy)
        sys.exit(1)

    raw_skills = raw_data.get('raw_skills', [])
    master_taxonomy = taxonomy_data.get('skills', [])

    logger.info('加载: 左轨 %d 个已掌握技能，右轨 %d 个全集技能',
                len(raw_skills), len(master_taxonomy))

    # 归纳分类
    if args.llm_mode == 'dialog' and not args.llm_response:
        # dialog 模式第一步：导出 prompt 到文件，提示用户去对话
        prompt_path = os.path.join(_CACHE_DIR, 'llm_cluster_prompt.md')
        _export_llm_dialog_prompt(raw_skills, master_taxonomy, prompt_path)
        print(f'\n=== LLM 对话模式 ===')
        print(f'Prompt 已导出到: {prompt_path}')
        print(f'请把该文件内容复制到 AI 对话框，AI 回复后保存为 JSON，再用以下命令继续:')
        print(f'  python scripts/skill_graph_cluster.py --llm-mode dialog --llm-response <回复.json>')
        print(f'\n当前先用规则降级版本生成结果...')

    # 统一调用 cluster_with_llm（内部处理 llm_response_path）
    _, category_info = cluster_with_llm(raw_skills, master_taxonomy, args.llm_response)

    # 差距分析
    clustered_skills = gap_analysis(raw_skills, master_taxonomy, category_info)

    # 统计
    mastered_count = sum(1 for s in clustered_skills if s.status == 'mastered')
    not_mastered_count = sum(1 for s in clustered_skills if s.status == 'not_mastered')
    extra_mastered_count = sum(1 for s in clustered_skills if s.status == 'extra_mastered')

    # 核心掌握率（仅算高优先级全集技能）
    # 用户说"掌握概念知道怎么用即可，AI 能做到很多"——核心技能掌握率更有参考价值
    high_priority_not_mastered = sum(
        1 for s in clustered_skills
        if s.status == 'not_mastered' and s.priority == 'high'
    )
    # 高优先级全集 = 已掌握中属于高优先级分类的 + 高优先级未掌握
    # 简化：核心掌握率 = 已掌握 / (已掌握 + 高优先级未掌握)
    core_denominator = mastered_count + high_priority_not_mastered
    core_mastery_rate = round(mastered_count / max(core_denominator, 1), 4)

    # 全集掌握率（原算法）
    full_mastery_rate = round(mastered_count / max(len(clustered_skills), 1), 4)

    # 构建输出
    result = ClusterResult(
        generated_at=datetime.now().astimezone().isoformat(),
        categories=category_info.get('categories', []),
        skills=[asdict(s) for s in clustered_skills],
        summary={
            'total_skills': len(clustered_skills),
            'mastered_count': mastered_count,
            'not_mastered_count': not_mastered_count,
            'extra_mastered_count': extra_mastered_count,
            # 双维度掌握率
            'mastery_rate': full_mastery_rate,  # 全集掌握率（向后兼容）
            'full_mastery_rate': full_mastery_rate,  # 全集掌握率
            'core_mastery_rate': core_mastery_rate,  # 核心掌握率（仅高优先级全集）
            'high_priority_not_mastered': high_priority_not_mastered,
            'mastery_note': '掌握门槛=知道概念+知道怎么用（AI 辅助下不需要精通）；核心掌握率仅算高优先级全集技能，更有参考价值',
            'raw_skills_count': len(raw_skills),
            'taxonomy_skills_count': len(master_taxonomy),
            'sources_scanned': raw_data.get('sources_scanned', []),
            'taxonomy_sources': taxonomy_data.get('sources_hit', []),
        },
    )

    # 写入
    if _atomic_write_json(args.output, asdict(result)):
        logger.info('skills_clustered.json 写入: %s', args.output)
    else:
        logger.error('写入失败')
        sys.exit(1)

    # 汇总
    print(f'\n=== 阶段2 归纳分类 + 差距分析完成 ===')
    print(f'分类数: {len(result.categories)} (3-7 合规: {3 <= len(result.categories) <= 7})')
    print(f'已掌握 (mastered): {mastered_count}')
    print(f'未掌握 (not_mastered): {not_mastered_count} (其中高优先级: {high_priority_not_mastered})')
    print(f'额外掌握 (extra_mastered): {extra_mastered_count}')
    print(f'全集掌握率: {full_mastery_rate:.1%}')
    print(f'核心掌握率: {core_mastery_rate:.1%} (仅高优先级全集，更有参考价值)')
    print(f'输出: {args.output}')


if __name__ == '__main__':
    main()

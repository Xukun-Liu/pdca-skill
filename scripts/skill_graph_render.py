#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_graph_render.py — 阶段3：三格式渲染

输入：skills_clustered.json
输出：
  1. memory/skill_graph.md       — markdown + 内联 SVG（人看）
  2. docs_master_graph/skill_graph.csv — CSV（Excel/程序消费）
  3. docs_master_graph/skill_graph.svg — 独立 SVG（浏览器/分享）
  4. docs_master_graph/manifest.json   — 三文件 hash 校验同步

设计要点：
  - 问答式 SVG：已掌握=深绿点亮，未掌握=灰色，额外掌握=橙色
  - 径向树布局：中心=用户角色，中圈=分类，外圈=技能
  - CSV：UTF-8 BOM（防中文乱码），分号分隔多值字段
  - manifest.json：三文件 SHA256 + 时间戳，保证同步

用法：
  python scripts/skill_graph_render.py
    --input skills_clustered.json
    --md-output memory/skill_graph.md
    --csv-output docs_master_graph/skill_graph.csv
    --svg-output docs_master_graph/skill_graph.svg
"""

import os
import sys
import re
import json
import csv
import hashlib
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)

sys.path.insert(0, _SCRIPT_DIR)
import user_data_path  # noqa: E402  用户数据外置：提供 get_docs_rj_path()

_CACHE_DIR = os.path.join(user_data_path.get_docs_rj_path(), 'memory_rj', '.skill_graph_cache')
_OUTPUT_DIR = os.path.join(user_data_path.get_docs_rj_path(), 'skill_graph')


# ===========================================================================
# 颜色方案（色盲友好，参考 zalando tech-radar）
# ===========================================================================

COLOR = {
    'mastered':        '#16a34a',  # 深绿（已掌握点亮）
    'not_mastered':    '#9ca3af',  # 灰色（未掌握）
    'extra_mastered':  '#ea580c',  # 橙色（额外掌握）
    'recommend':       '#f59e0b',  # 橙黄（推荐补的高优先级未掌握）
    'root':            '#1e40af',  # 深蓝（根节点）
    'category':        '#fbbf24',  # 黄色（分类节点）
    'line_mastered':   '#16a34a',
    'line_not':        '#d1d5db',
    'background':      '#ffffff',
    'text_dark':       '#111827',
    'text_light':      '#ffffff',
    'text_gray':       '#6b7280',
}


# ===========================================================================
# 工具函数
# ===========================================================================

def _load_json(filepath: str) -> Optional[dict]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error('加载 JSON 失败 %s: %s', filepath, e)
        return None


def _atomic_write(filepath: str, content: str, encoding: str = 'utf-8') -> bool:
    """原子写入文本文件。"""
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    tmp = filepath + '.tmp'
    try:
        with open(tmp, 'w', encoding=encoding, newline='') as f:
            f.write(content)
        os.replace(tmp, filepath)
        return True
    except (OSError, IOError) as e:
        logger.error('写入失败 %s: %s', filepath, e)
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def _compute_hash(filepath: str) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return ''


def _truncate(text: str, max_len: int = 20) -> str:
    """截断文本，超长加省略号。"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + '…'


# ===========================================================================
# SVG 渲染：径向树布局
# ===========================================================================

def render_svg_radial_tree(
    skills: List[dict],
    categories: List[dict],
    user_name: str = '我',
    width: int = 1200,
    height: int = 800,
) -> str:
    """渲染径向树 SVG。

    布局：
    - 中心：用户节点（深蓝大圆）
    - 中圈：分类节点（黄色，环绕中心）
    - 外圈：技能节点（已掌握深绿/未掌握灰色/额外掌握橙色）
    - 连线：已掌握实线绿，未掌握虚线灰
    """
    import math

    cx, cy = width // 2, height // 2
    radius_root = 30
    radius_category = 180
    radius_skill = 320

    # 限制每分类显示的技能数（避免过密）
    MAX_SKILLS_PER_CAT = 15

    # 按分类分组技能
    cat_skills: Dict[str, List[dict]] = {}
    for skill in skills:
        cat = skill.get('category', '其他')
        cat_skills.setdefault(cat, []).append(skill)

    # 分类节点角度
    cat_count = len(categories)
    if cat_count == 0:
        cat_count = 1
    cat_angle_step = 2 * math.pi / cat_count

    svg_parts: List[str] = []
    svg_parts.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="background:{COLOR["background"]};font-family:Segoe UI,Microsoft YaHei,sans-serif;">'
    )

    # 定义箭头/样式
    svg_parts.append(f'''
      <defs>
        <style>
          .skill-text {{ font-size: 10px; }}
          .cat-text {{ font-size: 13px; font-weight: bold; }}
          .root-text {{ font-size: 16px; font-weight: bold; fill: {COLOR["text_light"]}; }}
          .legend-text {{ font-size: 11px; fill: {COLOR["text_dark"]}; }}
        </style>
      </defs>
    ''')

    # 1. 根节点（用户）
    svg_parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{radius_root}" fill="{COLOR["root"]}" stroke="#1e3a8a" stroke-width="2"/>'
    )
    svg_parts.append(
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" class="root-text">{xml_escape(_truncate(user_name, 6))}</text>'
    )

    # 2. 分类节点 + 3. 技能节点
    for i, cat in enumerate(categories):
        cat_name = cat.get('name', f'分类{i+1}')
        angle = i * cat_angle_step - math.pi / 2  # 从正上方开始

        cat_x = cx + radius_category * math.cos(angle)
        cat_y = cy + radius_category * math.sin(angle)

        # 根 → 分类 连线
        svg_parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cat_x:.1f}" y2="{cat_y:.1f}" '
            f'stroke="{COLOR["category"]}" stroke-width="2"/>'
        )

        # 分类节点
        svg_parts.append(
            f'<circle cx="{cat_x:.1f}" cy="{cat_y:.1f}" r="22" fill="{COLOR["category"]}" '
            f'stroke="#d97706" stroke-width="2"/>'
        )
        svg_parts.append(
            f'<text x="{cat_x:.1f}" y="{cat_y + 4:.1f}" text-anchor="middle" class="cat-text" '
            f'fill="{COLOR["text_dark"]}">{xml_escape(_truncate(cat_name, 4))}</text>'
        )

        # 该分类下的技能
        skill_list = cat_skills.get(cat_name, [])
        # 按 status 排序：mastered 优先
        status_order = {'mastered': 0, 'extra_mastered': 1, 'not_mastered': 2}
        skill_list.sort(key=lambda s: (status_order.get(s.get('status', ''), 3), s.get('name', '')))

        # 限制数量
        display_skills = skill_list[:MAX_SKILLS_PER_CAT]
        skill_count = len(display_skills)
        if skill_count == 0:
            continue

        # 技能角度范围：以分类角度为中心，向两侧展开
        skill_angle_span = cat_angle_step * 0.9  # 留间隙
        if skill_count > 1:
            skill_angles = [
                angle - skill_angle_span / 2 + skill_angle_span * j / (skill_count - 1)
                for j in range(skill_count)
            ]
        else:
            skill_angles = [angle]

        for j, skill in enumerate(display_skills):
            s_angle = skill_angles[j]
            s_x = cx + radius_skill * math.cos(s_angle)
            s_y = cy + radius_skill * math.sin(s_angle)

            status = skill.get('status', 'not_mastered')
            name = skill.get('name', '')
            priority = skill.get('priority', '')

            # 颜色和样式
            if status == 'mastered':
                fill = COLOR['mastered']
                stroke = '#15803d'
                r = 8
                line_stroke = COLOR['line_mastered']
                line_dash = ''
            elif status == 'extra_mastered':
                fill = COLOR['extra_mastered']
                stroke = '#c2410c'
                r = 7
                line_stroke = COLOR['extra_mastered']
                line_dash = ''
            else:  # not_mastered
                fill = COLOR['not_mastered']
                stroke = '#6b7280'
                r = 5
                line_stroke = COLOR['line_not']
                line_dash = 'stroke-dasharray="3,2"'
                # 高优先级未掌握加橙色边框
                if priority == 'high':
                    stroke = COLOR['recommend']
                    r = 6

            # 分类 → 技能 连线
            svg_parts.append(
                f'<line x1="{cat_x:.1f}" y1="{cat_y:.1f}" x2="{s_x:.1f}" y2="{s_y:.1f}" '
                f'stroke="{line_stroke}" stroke-width="1" {line_dash}/>'
            )

            # 技能节点
            svg_parts.append(
                f'<circle cx="{s_x:.1f}" cy="{s_y:.1f}" r="{r}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="1.5">'
                f'<title>{xml_escape(name)} [{status}]</title></circle>'
            )

            # 技能名（在外侧）
            text_x = cx + (radius_skill + 15) * math.cos(s_angle)
            text_y = cy + (radius_skill + 15) * math.sin(s_angle) + 3
            text_anchor = 'start' if math.cos(s_angle) > 0 else 'end'
            text_color = COLOR['text_dark'] if status == 'mastered' else COLOR['text_gray']
            svg_parts.append(
                f'<text x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="{text_anchor}" '
                f'class="skill-text" fill="{text_color}">{xml_escape(_truncate(name, 14))}</text>'
            )

        # 如果技能被截断了，显示 +N
        if len(skill_list) > MAX_SKILLS_PER_CAT:
            more_count = len(skill_list) - MAX_SKILLS_PER_CAT
            more_angle = angle
            more_x = cx + (radius_skill + 30) * math.cos(more_angle)
            more_y = cy + (radius_skill + 30) * math.sin(more_angle)
            svg_parts.append(
                f'<text x="{more_x:.1f}" y="{more_y:.1f}" text-anchor="middle" '
                f'class="skill-text" fill="{COLOR["text_gray"]}">+{more_count}</text>'
            )

    # 4. 图例（右下角）
    legend_x = width - 200
    legend_y = height - 100
    svg_parts.append(f'<g transform="translate({legend_x}, {legend_y})">')
    svg_parts.append(f'<rect x="0" y="0" width="190" height="90" fill="{COLOR["background"]}" stroke="#d1d5db" rx="4"/>')
    svg_parts.append(f'<text x="10" y="18" class="legend-text" font-weight="bold">图例</text>')
    # 已掌握
    svg_parts.append(f'<circle cx="20" cy="35" r="7" fill="{COLOR["mastered"]}"/>')
    svg_parts.append(f'<text x="35" y="39" class="legend-text">已掌握</text>')
    # 未掌握
    svg_parts.append(f'<circle cx="20" cy="55" r="5" fill="{COLOR["not_mastered"]}"/>')
    svg_parts.append(f'<text x="35" y="59" class="legend-text">未掌握</text>')
    # 额外掌握
    svg_parts.append(f'<circle cx="110" cy="35" r="6" fill="{COLOR["extra_mastered"]}"/>')
    svg_parts.append(f'<text x="125" y="39" class="legend-text">额外掌握</text>')
    # 推荐补
    svg_parts.append(f'<circle cx="110" cy="55" r="6" fill="{COLOR["not_mastered"]}" stroke="{COLOR["recommend"]}" stroke-width="2"/>')
    svg_parts.append(f'<text x="125" y="59" class="legend-text">推荐补</text>')
    svg_parts.append(f'</g>')

    # 5. 生成时间戳
    svg_parts.append(
        f'<text x="{width - 10}" y="20" text-anchor="end" class="skill-text" fill="{COLOR["text_gray"]}">'
        f'生成于 {datetime.now().strftime("%Y-%m-%d %H:%M")}</text>'
    )

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def render_ascii_tree_fallback(
    skills: List[dict],
    categories: List[dict],
    user_name: str = '我',
) -> str:
    """ASCII 树状图降级（SVG 失败时用）。"""
    lines = [f'{user_name}']
    # 按分类分组
    cat_skills: Dict[str, List[dict]] = {}
    for skill in skills:
        cat = skill.get('category', '其他')
        cat_skills.setdefault(cat, []).append(skill)

    status_order = {'mastered': 0, 'extra_mastered': 1, 'not_mastered': 2}
    status_icon = {
        'mastered': '[*]',
        'extra_mastered': '[+]',
        'not_mastered': '[ ]',
    }

    for cat in categories:
        cat_name = cat.get('name', '分类')
        skill_list = cat_skills.get(cat_name, [])
        if not skill_list:
            continue
        skill_list.sort(key=lambda s: (status_order.get(s.get('status', ''), 3), s.get('name', '')))

        lines.append(f'  ├─ {cat_name} ({len(skill_list)})')
        for i, skill in enumerate(skill_list[:10]):  # 限制10个
            icon = status_icon.get(skill.get('status', 'not_mastered'), '[?]')
            name = skill.get('name', '')
            is_last = (i == len(skill_list[:10]) - 1) and (len(skill_list) <= 10)
            prefix = '  │  └─' if is_last else '  │  ├─'
            lines.append(f'{prefix} {icon} {name}')
        if len(skill_list) > 10:
            lines.append(f'  │  └─ ... +{len(skill_list) - 10} more')

    lines.append('')
    lines.append('图例: [*]=已掌握  [ ]=未掌握  [+]=额外掌握')
    return '\n'.join(lines)


# ===========================================================================
# Markdown 渲染
# ===========================================================================

def render_markdown(
    skills: List[dict],
    categories: List[dict],
    summary: Dict,
    svg_content: str,
    ascii_tree: str,
    user_name: str = '我',
) -> str:
    """渲染 markdown 文档（含 SVG + ASCII + 表格 + 证据）。"""
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')

    parts: List[str] = []

    # 头部
    parts.append(f'# {user_name}的技能图谱')
    parts.append('')
    parts.append(f'> ⚠️ 自动生成于 {generated_at}，请勿手动修改。重新生成请运行 `python scripts/skill_graph_build.py`')
    parts.append('')

    # 概览
    parts.append('## 概览')
    parts.append('')
    total = summary.get('total_skills', 0)
    mastered = summary.get('mastered_count', 0)
    not_mastered = summary.get('not_mastered_count', 0)
    extra = summary.get('extra_mastered_count', 0)
    rate = summary.get('mastery_rate', 0)
    core_rate = summary.get('core_mastery_rate', 0)
    high_not = summary.get('high_priority_not_mastered', 0)
    mastery_note = summary.get('mastery_note', '')

    parts.append(f'- **全集技能数**：{total}')
    parts.append(f'- **已掌握**：{mastered} ({mastered/max(total,1):.1%})')
    parts.append(f'- **未掌握**：{not_mastered} ({not_mastered/max(total,1):.1%})，其中高优先级 {high_not} 个')
    parts.append(f'- **额外掌握**：{extra}（不在全集内的独有技能）')
    parts.append(f'- **全集掌握率**：{rate:.1%}（已掌握 / 全部全集技能）')
    parts.append(f'- **核心掌握率**：{core_rate:.1%}（已掌握 / (已掌握+高优先级未掌握)，**更有参考价值**）')
    if mastery_note:
        parts.append(f'- **掌握门槛说明**：{mastery_note}')
    parts.append(f'- **数据源**：{", ".join(summary.get("sources_scanned", []))}')
    parts.append(f'- **全集源**：{", ".join(summary.get("taxonomy_sources", []))}')
    parts.append('')

    # SVG 图
    parts.append('## 技能图谱（SVG 交互图）')
    parts.append('')
    parts.append('**颜色说明**：绿色=已掌握，灰色=未掌握，橙色=额外掌握，橙边=推荐补的高优先级。')
    parts.append('')
    parts.append('```svg')
    parts.append(svg_content)
    parts.append('```')
    parts.append('')

    # ASCII 降级
    parts.append('<details>')
    parts.append('<summary>ASCII 树状图（降级视图）</summary>')
    parts.append('')
    parts.append('```')
    parts.append(ascii_tree)
    parts.append('```')
    parts.append('')
    parts.append('</details>')
    parts.append('')

    # 已掌握技能表
    mastered_skills = [s for s in skills if s.get('status') == 'mastered']
    parts.append(f'## 已掌握技能（{len(mastered_skills)} 个）')
    parts.append('')
    parts.append('| 技能 | 分类 | 置信度 | 证据数 | 来源工具 | 首次出现 | 最近出现 |')
    parts.append('|------|------|--------|--------|----------|----------|----------|')
    for s in mastered_skills:
        name = s.get('name', '')
        cat = s.get('category', '')
        conf = f"{s.get('confidence', 0):.0%}"
        ev_count = s.get('evidence_count', 0)
        tools = ';'.join(s.get('source_tools', []))
        first = s.get('first_seen', '')
        last = s.get('last_seen', '')
        parts.append(f'| {name} | {cat} | {conf} | {ev_count} | {tools} | {first} | {last} |')
    parts.append('')

    # 额外掌握技能
    extra_skills = [s for s in skills if s.get('status') == 'extra_mastered']
    if extra_skills:
        parts.append(f'## 额外掌握技能（{len(extra_skills)} 个，不在全集内）')
        parts.append('')
        parts.append('| 技能 | 分类 | 置信度 | 证据数 | 来源工具 |')
        parts.append('|------|------|--------|--------|----------|')
        for s in extra_skills:
            name = s.get('name', '')
            cat = s.get('category', '')
            conf = f"{s.get('confidence', 0):.0%}"
            ev_count = s.get('evidence_count', 0)
            tools = ';'.join(s.get('source_tools', []))
            parts.append(f'| {name} | {cat} | {conf} | {ev_count} | {tools} |')
        parts.append('')

    # 未掌握技能（按优先级分组）
    not_mastered_skills = [s for s in skills if s.get('status') == 'not_mastered']
    if not_mastered_skills:
        parts.append(f'## 未掌握技能（{len(not_mastered_skills)} 个）')
        parts.append('')
        parts.append('按学习优先级分组：')
        parts.append('')

        for priority in ['high', 'medium', 'low']:
            pri_skills = [s for s in not_mastered_skills if s.get('priority') == priority]
            if not pri_skills:
                continue
            pri_label = {'high': '高优先级', 'medium': '中优先级', 'low': '低优先级'}[priority]
            parts.append(f'### {pri_label}（{len(pri_skills)} 个）')
            parts.append('')
            parts.append('| 技能 | 分类 | 全集来源 | 学习链接 |')
            parts.append('|------|------|----------|----------|')
            for s in pri_skills[:30]:  # 每优先级最多30个
                name = s.get('name', '')
                cat = s.get('category', '')
                sources = ';'.join(s.get('sources', []))
                link = s.get('learning_link', '')
                link_md = f'[链接]({link})' if link else '-'
                parts.append(f'| {name} | {cat} | {sources} | {link_md} |')
            if len(pri_skills) > 30:
                parts.append(f'\n*... 还有 {len(pri_skills) - 30} 个，详见 CSV*')
            parts.append('')

    # 分类汇总
    parts.append('## 分类汇总')
    parts.append('')
    parts.append('| 分类 | 技能数 | 平均置信度 |')
    parts.append('|------|--------|------------|')
    for cat in categories:
        name = cat.get('name', '')
        count = cat.get('skill_count', 0)
        avg_conf = cat.get('avg_confidence', 0)
        parts.append(f'| {name} | {count} | {avg_conf:.0%} |')
    parts.append('')

    # 元数据
    parts.append('## 生成元数据')
    parts.append('')
    parts.append(f'- 生成时间：{generated_at}')
    parts.append(f'- 左轨已掌握技能：{summary.get("raw_skills_count", 0)}')
    parts.append(f'- 右轨全集技能：{summary.get("taxonomy_skills_count", 0)}')
    parts.append(f'- 记忆数据源：{", ".join(summary.get("sources_scanned", []))}')
    parts.append(f'- 全集数据源：{", ".join(summary.get("taxonomy_sources", []))}')
    parts.append(f'- 同步校验：见 `docs_master_graph/manifest.json`')
    parts.append('')

    return '\n'.join(parts)


# ===========================================================================
# CSV 渲染
# ===========================================================================

def render_csv(skills: List[dict]) -> str:
    """渲染 CSV（UTF-8 BOM + 13 列）。

    列：skill_name, category, status, confidence, evidence_count,
        source_tools, evidence_files, first_seen, last_seen,
        reason, roadmap_ref, priority, learning_link
    """
    import io
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # 表头
    headers = [
        'skill_name', 'category', 'status', 'confidence', 'evidence_count',
        'source_tools', 'evidence_files', 'first_seen', 'last_seen',
        'reason', 'roadmap_ref', 'priority', 'learning_link',
    ]
    writer.writerow(headers)

    def _csv_safe(value) -> str:
        """CSV 注入防护：以 = + - @ 及 \t \r 开头的单元格加单引号前缀。

        覆盖 Excel/表格软件公式注入向量（含全角变体 ＝＋－＠）。
        """
        text = str(value)
        if not text:
            return text
        if re.match(r'^[\t\r=+\-@＝＋－＠]', text):
            return "'" + text
        return text

    for s in skills:
        # 多值字段用分号分隔
        source_tools = ';'.join(s.get('source_tools', []))
        # evidence_refs 转成简化字符串
        ev_refs = ';'.join(s.get('evidence_refs', []))

        writer.writerow([
            _csv_safe(s.get('name', '')),
            _csv_safe(s.get('category', '')),
            _csv_safe(s.get('status', '')),
            f"{s.get('confidence', 0):.2f}",
            s.get('evidence_count', 0),
            _csv_safe(source_tools),
            _csv_safe(ev_refs),
            _csv_safe(s.get('first_seen', '')),
            _csv_safe(s.get('last_seen', '')),
            _csv_safe(s.get('reason', '')),
            _csv_safe(s.get('roadmap_ref', '')),
            _csv_safe(s.get('priority', '')),
            _csv_safe(s.get('learning_link', '')),
        ])

    # UTF-8 BOM
    content = output.getvalue()
    return '\ufeff' + content


# ===========================================================================
# Manifest（三文件同步校验）
# ===========================================================================

def write_manifest(
    md_path: str,
    csv_path: str,
    svg_path: str,
    summary: Dict,
) -> str:
    """写 manifest.json 记录三文件 hash。"""
    manifest = {
        'generated_at': datetime.now().astimezone().isoformat(),
        'files': {
            'markdown': {
                'path': md_path,
                'sha256': _compute_hash(md_path),
            },
            'csv': {
                'path': csv_path,
                'sha256': _compute_hash(csv_path),
            },
            'svg': {
                'path': svg_path,
                'sha256': _compute_hash(svg_path),
            },
        },
        'summary': summary,
        'sync_check': 'all three files generated from same skills_clustered.json',
    }

    manifest_path = os.path.join(os.path.dirname(csv_path), 'manifest.json')
    _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest_path


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='阶段3：三格式渲染（markdown + CSV + SVG）',
    )
    parser.add_argument(
        '--input', default=os.path.join(_CACHE_DIR, 'skills_clustered.json'),
        help='skills_clustered.json 路径',
    )
    parser.add_argument(
        '--md-output', default=os.path.join(_OUTPUT_DIR, 'skill_graph.md'),
        help='markdown 输出路径',
    )
    parser.add_argument(
        '--csv-output',
        default=os.path.join(_OUTPUT_DIR, 'skill_graph.csv'),
        help='CSV 输出路径',
    )
    parser.add_argument(
        '--svg-output',
        default=os.path.join(_OUTPUT_DIR, 'skill_graph.svg'),
        help='SVG 输出路径',
    )
    parser.add_argument(
        '--user-name', default='我',
        help='用户名（显示在图谱中心）',
    )

    args = parser.parse_args()

    # 加载
    data = _load_json(args.input)
    if not data:
        logger.error('无法加载 %s', args.input)
        sys.exit(1)

    skills = data.get('skills', [])
    categories = data.get('categories', [])
    summary = data.get('summary', {})

    logger.info('加载: %d 个技能，%d 个分类', len(skills), len(categories))

    # 1. 渲染 SVG
    logger.info('渲染 SVG...')
    svg_content = render_svg_radial_tree(skills, categories, args.user_name)
    if not _atomic_write(args.svg_output, svg_content):
        logger.error('SVG 写入失败')
        sys.exit(1)
    logger.info('SVG 写入: %s', args.svg_output)

    # 2. 渲染 ASCII 降级
    ascii_tree = render_ascii_tree_fallback(skills, categories, args.user_name)

    # 3. 渲染 Markdown
    logger.info('渲染 Markdown...')
    md_content = render_markdown(skills, categories, summary, svg_content, ascii_tree, args.user_name)
    if not _atomic_write(args.md_output, md_content):
        logger.error('Markdown 写入失败')
        sys.exit(1)
    logger.info('Markdown 写入: %s', args.md_output)

    # 4. 渲染 CSV
    logger.info('渲染 CSV...')
    csv_content = render_csv(skills)
    if not _atomic_write(args.csv_output, csv_content):
        logger.error('CSV 写入失败')
        sys.exit(1)
    logger.info('CSV 写入: %s', args.csv_output)

    # 5. 写 manifest.json（三文件同步校验）
    manifest_path = write_manifest(args.md_output, args.csv_output, args.svg_output, summary)
    logger.info('Manifest 写入: %s', manifest_path)

    # 6. 扫描占位符
    placeholders = []
    for pattern in ['TBD', 'TODO', 'FIXME', '占位', '待补', '...', 'xxx']:
        if pattern.lower() in md_content.lower() and pattern != '...':
            placeholders.append(pattern)

    # 汇总
    print(f'\n=== 阶段3 渲染完成 ===')
    print(f'Markdown: {args.md_output}')
    print(f'CSV:      {args.csv_output}')
    print(f'SVG:      {args.svg_output}')
    print(f'Manifest: {manifest_path}')
    print(f'技能数:   {len(skills)}')
    print(f'分类数:   {len(categories)}')
    print(f'占位符:   {len(placeholders)} 个 {placeholders if placeholders else "(无)"}')


if __name__ == '__main__':
    main()

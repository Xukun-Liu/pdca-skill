#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_graph_build.py — 总入口：串联三阶段 + 缓存

用法：
  python scripts/skill_graph_build.py                    # 默认全量
  python scripts/skill_graph_build.py --source all       # 指定数据源
  python scripts/skill_graph_build.py --no-cache         # 强制重算
  python scripts/skill_graph_build.py --skip-taxonomy    # 仅左轨（调试）
  python scripts/skill_graph_build.py --user-name 你的名字   # 自定义用户名

阶段：
  T1 extract  : 双轨提取（左轨记忆 + 右轨全集）→ skills_raw.json + master_taxonomy.json
  T2 cluster  : 归纳分类 + 差距分析 → skills_clustered.json
  T3 render   : 三格式渲染 → skill_graph.md + .csv + .svg + manifest.json

缓存：
  - 对每个输入记忆文件算 SHA256
  - 文件未变 → 跳过阶段1
  - 阶段2/3 依赖阶段1输出，阶段1跳过则阶段2/3也跳过（除非 --no-cache）
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_CACHE_DIR = os.path.join(_SKILL_DIR, 'docs_rj', 'memory_rj', '.skill_graph_cache')
_MANIFEST_PATH = os.path.join(_CACHE_DIR, 'cache_manifest.json')


# ===========================================================================
# 缓存管理
# ===========================================================================

def _compute_hash(filepath: str) -> str:
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return ''


def _collect_input_files(skill_dir: str) -> list:
    """收集所有左轨输入记忆文件路径。"""
    files = []
    # riji memory_main.md
    p = os.path.join(skill_dir, 'memory', 'memory_main.md')
    if os.path.isfile(p):
        files.append(p)
    # memory_rj/*.md
    memory_rj = os.path.join(skill_dir, 'docs_rj', 'memory_rj')
    if os.path.isdir(memory_rj):
        for f in os.listdir(memory_rj):
            if f.endswith('.md') and not f.startswith('.'):
                files.append(os.path.join(memory_rj, f))
    return files


def _load_cache_manifest() -> dict:
    """加载缓存 manifest。"""
    try:
        with open(_MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache_manifest(manifest: dict) -> bool:
    """保存缓存 manifest。"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        with open(_MANIFEST_PATH, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, IOError) as e:
        logger.error('保存缓存 manifest 失败: %s', e)
        return False


def _check_cache(input_files: list, cached_manifest: dict) -> bool:
    """检查缓存是否命中（所有输入文件 hash 未变）。"""
    if not cached_manifest:
        return False

    cached_hashes = cached_manifest.get('input_hashes', {})
    for filepath in input_files:
        current_hash = _compute_hash(filepath)
        cached_hash = cached_hashes.get(filepath)
        if current_hash != cached_hash:
            logger.info('缓存 miss: %s 变化', filepath)
            return False

    # 检查输出文件是否存在
    outputs = cached_manifest.get('outputs', {})
    for name, path in outputs.items():
        if not os.path.isfile(path):
            logger.info('缓存 miss: %s 不存在', path)
            return False

    return True


def _update_cache(input_files: list, outputs: dict) -> dict:
    """更新缓存 manifest。"""
    manifest = {
        'updated_at': datetime.now().astimezone().isoformat(),
        'input_hashes': {f: _compute_hash(f) for f in input_files},
        'outputs': outputs,
    }
    _save_cache_manifest(manifest)
    return manifest


# ===========================================================================
# 阶段执行
# ===========================================================================

def _run_script(script_name: str, args: list) -> bool:
    """执行子脚本，返回是否成功。"""
    script_path = os.path.join(_SCRIPT_DIR, script_name)
    cmd = [sys.executable, script_path] + args
    logger.info('执行: %s', ' '.join(cmd))
    try:
        result = subprocess.run(
            cmd, cwd=_SKILL_DIR, capture_output=True, text=True, encoding='utf-8',
        )
        # 输出 stderr 日志（PowerShell 的 NativeCommandError 不影响）
        if result.stderr:
            for line in result.stderr.splitlines():
                logger.info('  %s | %s', script_name, line)
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0:
            logger.error('%s 失败 (exit %d)', script_name, result.returncode)
            return False
        return True
    except Exception as e:
        logger.error('执行 %s 异常: %s', script_name, e)
        return False


def run_stage1(args) -> bool:
    """阶段1：双轨提取。"""
    extract_args = [
        '--source', args.source,
        '--output', os.path.join(_CACHE_DIR, 'skills_raw.json'),
        '--taxonomy-output', os.path.join(_CACHE_DIR, 'master_taxonomy.json'),
    ]
    if args.no_cache:
        extract_args.append('--no-cache')
    if args.skip_taxonomy:
        extract_args.append('--skip-taxonomy')
    return _run_script('skill_graph_extract.py', extract_args)


def run_stage2(args) -> bool:
    """阶段2：归纳分类 + 差距分析。"""
    cluster_args = [
        '--input', os.path.join(_CACHE_DIR, 'skills_raw.json'),
        '--taxonomy', os.path.join(_CACHE_DIR, 'master_taxonomy.json'),
        '--output', os.path.join(_CACHE_DIR, 'skills_clustered.json'),
    ]
    return _run_script('skill_graph_cluster.py', cluster_args)


def run_stage3(args) -> bool:
    """阶段3：三格式渲染。"""
    render_args = [
        '--input', os.path.join(_CACHE_DIR, 'skills_clustered.json'),
        '--md-output', os.path.join(_SKILL_DIR, 'memory', 'skill_graph.md'),
        '--csv-output', os.path.join(_SKILL_DIR, 'docs_master_graph', 'skill_graph.csv'),
        '--svg-output', os.path.join(_SKILL_DIR, 'docs_master_graph', 'skill_graph.svg'),
        '--user-name', args.user_name,
    ]
    return _run_script('skill_graph_render.py', render_args)


# ===========================================================================
# 主入口
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='技能图谱生成器（总入口：串联三阶段 + 缓存）',
    )
    parser.add_argument(
        '--source', choices=['riji', 'ai_tools', 'riji', 'all'],
        default='all', help='数据源（默认 all）',
    )
    parser.add_argument(
        '--no-cache', action='store_true',
        help='忽略缓存，强制重新计算',
    )
    parser.add_argument(
        '--skip-taxonomy', action='store_true',
        help='跳过右轨多源全集拉取（调试用）',
    )
    parser.add_argument(
        '--user-name', default='我',
        help='用户名（显示在图谱中心）',
    )
    parser.add_argument(
        '--force-stage', choices=['1', '2', '3', 'all'], default='all',
        help='强制只跑指定阶段（调试用）',
    )

    args = parser.parse_args()

    start_time = datetime.now()
    print(f'\n{"=" * 60}')
    print(f'技能图谱生成器')
    print(f'开始时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"=" * 60}')

    # 检查缓存
    input_files = _collect_input_files(_SKILL_DIR)
    cached_manifest = _load_cache_manifest()
    cache_hit = (not args.no_cache) and _check_cache(input_files, cached_manifest)

    if cache_hit and args.force_stage == 'all':
        print('\n✅ 缓存命中：所有输入文件未变化，跳过全部阶段')
        print(f'  上次生成: {cached_manifest.get("updated_at", "未知")}')
        print(f'  输出文件:')
        for name, path in cached_manifest.get('outputs', {}).items():
            print(f'    {name}: {path}')
        return

    # 执行阶段
    success = True

    # 阶段1
    if args.force_stage in ('1', 'all'):
        print(f'\n--- 阶段1: 双轨提取 ---')
        if not run_stage1(args):
            logger.error('阶段1失败，终止')
            sys.exit(1)

    # 阶段2
    if args.force_stage in ('2', 'all'):
        print(f'\n--- 阶段2: 归纳分类 + 差距分析 ---')
        if not run_stage2(args):
            logger.error('阶段2失败，终止')
            sys.exit(1)

    # 阶段3
    if args.force_stage in ('3', 'all'):
        print(f'\n--- 阶段3: 三格式渲染 ---')
        if not run_stage3(args):
            logger.error('阶段3失败，终止')
            sys.exit(1)

    # 更新缓存
    outputs = {
        'markdown': os.path.join(_SKILL_DIR, 'memory', 'skill_graph.md'),
        'csv': os.path.join(_SKILL_DIR, 'docs_master_graph', 'skill_graph.csv'),
        'svg': os.path.join(_SKILL_DIR, 'docs_master_graph', 'skill_graph.svg'),
        'manifest': os.path.join(_SKILL_DIR, 'docs_master_graph', 'manifest.json'),
        'skills_raw': os.path.join(_CACHE_DIR, 'skills_raw.json'),
        'master_taxonomy': os.path.join(_CACHE_DIR, 'master_taxonomy.json'),
        'skills_clustered': os.path.join(_CACHE_DIR, 'skills_clustered.json'),
    }
    _update_cache(input_files, outputs)

    # 汇总
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f'\n{"=" * 60}')
    print(f'✅ 技能图谱生成完成')
    print(f'耗时: {duration:.1f}s')
    print(f'{"=" * 60}')
    print(f'\n输出文件:')
    print(f'  Markdown: {outputs["markdown"]}')
    print(f'  CSV:      {outputs["csv"]}')
    print(f'  SVG:      {outputs["svg"]}')
    print(f'  Manifest: {outputs["manifest"]}')
    print(f'\n在 Trae 预览器打开 Markdown 查看技能图谱')


if __name__ == '__main__':
    main()

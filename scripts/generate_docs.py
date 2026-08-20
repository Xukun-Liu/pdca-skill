#!/usr/bin/env python3
"""
文档生成脚本 - 自动创建任务目录结构和模板文件

遵循规则：
1. 主 docs 目录：一个项目只有一个主 docs，位置不固定，默认 ./docs_rj/
2. 分类文件夹结构（扁平）：docs_rj 下直接常驻 5 类文件夹（spec_rj/task_rj/handoff_rj/memory_rj/archive_rj），不再按任务名分子目录（archive_rj 例外：归档时按 `{task}_YYYYMMDD_HHMM/` 子文件夹聚合，内放 spec.md/task.md/handoff.md/memory.md）
3. 精确时间戳：文件名和内容都精确到分钟
4. 命名体系：{task}_{type}_YYYYMMDD_HHMM.md（任务名进文件名，无编号前缀）
5. 散落归档：检测散落在非主 docs 的 pdca-skill 文档，归档到主 docs
6. 命名空间隔离：所有运行时产物加_rj后缀，避免与各大agent平台通用命名撞车
7. 项目记忆：docs_rj/memory_rj/ 下按 {task}_memory_YYYYMMDD_HHMM.md 命名
"""

import os
import sys
import argparse
import json
import logging
import shutil
import tempfile
import re
from datetime import datetime

# 复用 tidy_common 的 ensure_global_structure (bootstrap_host 依赖)
# 用模块级 import + 函数体内属性访问,避免循环 import 时 (tidy_common → memory_shadow_write → generate_docs)
# ensure_global_structure 尚未定义的问题。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402
import user_data_path  # noqa: E402  用户数据外置：提供 get_docs_rj_path() 返回 ~/.pdca-skill/data/docs_rj

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

DOC_TYPES = {
    'spec': {'template': 'spec_template.md', 'dir': 'spec_rj'},
    'task': {'template': 'task_template.md', 'dir': 'task_rj'},
    'handoff': {'template': 'handoff_template.md', 'dir': 'handoff_rj'},
    'archive': {'template': 'archive_template.md', 'dir': 'archive_rj'},
}

# docs_rj 下常驻的 5 类文档文件夹（按类型聚合，任务名进文件名；memory_rj 为项目级记忆）
DOC_RJ_SUBDIRS = ['spec_rj', 'task_rj', 'handoff_rj', 'memory_rj', 'archive_rj']

PRIORITY_PATHS = [
    str(user_data_path.get_docs_rj_path()),
    './.agent/documents',
    './src/docs',
]

# pdca-skill 文档特征（扁平结构）：docs_rj 下直接 5 类 _rj 文件夹；
# 文件名 = {task}_{type}_YYYYMMDD_HHMM.md（无编号前缀，任务名进文件名）
# 注意：项目级记忆 memory_rj 在 docs_rj/memory_rj/（见 memory_shadow_write.write_project）。
pdca_SUBDIRS = {'spec_rj', 'task_rj', 'handoff_rj', 'memory_rj', 'archive_rj'}
pdca_FILE_PATTERN = re.compile(
    r'^\w+_(spec|task|handoff|memory)_\d{8}_\d{4}\.md$'
)

# 跳过的目录
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.pytest_cache', '.trae'}

# 任务名校验：仅允许小写字母、数字、下划线
TASK_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def validate_task_name(task_name):
    """校验任务名格式"""
    if not task_name:
        raise ValueError("任务名不能为空")
    if not TASK_NAME_RE.match(task_name):
        raise ValueError(
            f"任务名 '{task_name}' 格式不合法。"
            f"必须为小写字母+数字+下划线，且以字母开头。示例：my_task"
        )
    if len(task_name) > 64:
        raise ValueError(f"任务名过长（{len(task_name)}字符），最多64字符")


def find_memory_file():
    """双读兼容：优先新名 memory_rj/MEMORY_RJ.md，降级老名 memory/MEMORY.md

    返回：(文件路径, 是否老命名) 元组，找不到返回 (None, False)
    """
    new_path = os.path.abspath('./memory_rj/MEMORY_RJ.md')
    if os.path.isfile(new_path):
        return (new_path, False)
    old_path = os.path.abspath('./memory/MEMORY.md')
    if os.path.isfile(old_path):
        logger.info("检测到老命名 memory/MEMORY.md，建议运行 --migrate-rj 升级到新命名")
        return (old_path, True)
    return (None, False)


def read_primary_docs_from_memory():
    """从 memory_rj/MEMORY_RJ.md 约定区块读取主 docs 路径（双读兼容老命名）"""
    memory_path, is_old = find_memory_file()
    if memory_path is None:
        return None
    try:
        with open(memory_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 匹配 "主 docs 路径：xxx" 或 "主 docs 路径: xxx"
        match = re.search(r'主\s*docs\s*路径[：:]\s*(.+)', content)
        if match:
            path = match.group(1).strip().rstrip('（').rstrip('(').strip()
            # 去掉括号注释
            path = re.sub(r'[（(][^/\\]*[）)]\s*$', '', path).strip()
            if os.path.isdir(path):
                logger.info(f"从 {os.path.basename(memory_path)} 读取主 docs 路径: {path}")
                return os.path.abspath(path)
            logger.warning(f"{os.path.basename(memory_path)} 记录的主 docs 路径不存在: {path}")
        return None
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"读取 {memory_path} 失败: {e}")
        return None


def read_primary_docs_marker(marker_name='.primary_docs_rj'):
    """读取隐藏标记文件 .primary_docs_rj（含主 docs 绝对路径，R3）。

    标记由 --declare-primary 写入，优先级高于 MEMORY_RJ.md 约定区块（见 document_specs.md R3）。
    找不到或内容指向的目录不存在时返回 None。
    """
    marker_path = os.path.abspath(marker_name)
    if not os.path.isfile(marker_path):
        return None
    try:
        # utf-8-sig：有 BOM 自动剥、无 BOM 无副作用（G1 修复 D1——marker 带 BOM 不再导致解析失败）
        with open(marker_path, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
    except (OSError, UnicodeDecodeError):
        return None
    if content and os.path.isdir(content):
        return os.path.abspath(content)
    return None


def declare_primary_docs(path=None):
    """宣告主 docs 唯一性（R3）。

    1. 解析目标目录（path 或 find_docs_dir 检测）
    2. 写隐藏标记 .primary_docs_rj（含绝对路径）——启动整理与读取均以它为准
    3. 确保 memory_rj/MEMORY_RJ.md「约定」区块含"主 docs 路径"；
       缺失或不一致时提示用户确认（不静默改写，遵循 A3）

    Returns:
        最终采用的主 docs 绝对路径。
    """
    target = path or find_docs_dir()
    target_abs = os.path.abspath(target)
    if not os.path.isdir(target_abs):
        raise FileNotFoundError(f"主 docs 目录不存在: {target_abs}")

    # 1) 写隐藏标记
    marker = os.path.abspath('.primary_docs_rj')
    atomic_write(marker, target_abs + '\n')
    logger.info(f"已写入主 docs 标记: {marker} -> {target_abs}")

    # 2) 确保 MEMORY_RJ.md 约定区块记录
    _ensure_primary_in_memory_rj(target_abs)
    return target_abs


def _ensure_primary_in_memory_rj(abs_path):
    """确保 MEMORY_RJ.md「约定」区块含"主 docs 路径"；缺失/不一致时提示确认，不静默改写。"""
    mem_path, _is_old = find_memory_file()
    if mem_path is None:
        logger.warning("MEMORY_RJ.md 不存在，跳过'主 docs 路径'写入。"
                       "请先运行 Bootstrap 初始化（见 references/plan/bootstrap/bootstrap.md）。")
        return

    try:
        with open(mem_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("读取 MEMORY_RJ.md 失败: %s", e)
        return

    line_re = re.compile(r'主\s*docs\s*路径[：:]\s*(.+)')
    match = line_re.search(content)
    new_line = f"主 docs 路径：{abs_path}"
    if match:
        current = match.group(1).strip()
        if current == abs_path:
            logger.info("MEMORY_RJ.md 已记录主 docs 路径: %s", abs_path)
            return
        # 不一致 → 提示确认（不静默覆盖）
        prompt = (f"MEMORY_RJ.md 记录的'主 docs 路径'为 [{current}]，"
                  f"与主 docs 检测值 [{abs_path}] 不一致。是否更新为后者？(y/N) ")
    else:
        prompt = (f"MEMORY_RJ.md「约定」区块未记录'主 docs 路径'。"
                  f"是否添加 [{abs_path}]？(y/N) ")

    if not _prompt_yes(prompt):
        logger.info("用户取消写入主 docs 路径，保留原值（不静默改写）。")
        return

    if match:
        new_content = line_re.sub(re.escape(new_line), content, count=1)
    else:
        # 追加到「约定」区块末尾
        new_content = _append_to_section(content, '约定', new_line)
    atomic_write(mem_path, new_content)
    logger.info("已更新 MEMORY_RJ.md 主 docs 路径: %s", abs_path)


def _prompt_yes(prompt):
    """交互确认；非 TTY 环境直接返回 False（不静默改写）。"""
    try:
        if not sys.stdin.isatty():
            logger.warning("非交互环境，跳过确认（默认不改写）：%s", prompt)
            return False
        return input(prompt).strip().lower() in ('y', 'yes', '是')
    except (OSError, EOFError):
        return False


def _append_to_section(content, section_title, new_line):
    """在指定 '## 标题' 区块末尾追加一行（区块结束 = 下一个 '#' 标题或文件尾）。"""
    lines = content.splitlines()
    target_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith('#') and section_title in line:
            target_idx = i
            break
    if target_idx is None:
        # 区块不存在：直接追加到文件尾
        return content.rstrip() + '\n\n' + new_line + '\n'
    # 找区块结束
    end_idx = len(lines)
    for j in range(target_idx + 1, len(lines)):
        if lines[j].lstrip().startswith('#'):
            end_idx = j
            break
    result = lines[:end_idx]
    result.append('')
    result.append(new_line)
    result.extend(lines[end_idx:])
    return '\n'.join(result) + '\n'


# docs/ 子目录 → docs_rj/ 子目录的映射（兼容老命名和新命名）
DOCS_SUBDIR_MAP = {
    'spec': 'spec_rj', 'spec_rj': 'spec_rj',
    'task': 'task_rj', 'task_rj': 'task_rj',
    'handoff': 'handoff_rj', 'handoff_rj': 'handoff_rj',
    'memory': 'memory_rj', 'memory_rj': 'memory_rj',
    'archive': 'archive_rj', 'archive_rj': 'archive_rj',
}


def merge_docs_to_docs_rj(docs_path, docs_rj_path, dry_run=False):
    """将 docs/ 目录的内容合并到 docs_rj/，合并后删除 docs/。

    合并规则：
    - 子目录按 DOCS_SUBDIR_MAP 映射（spec→spec_rj 等）
    - 直接 .md 文件移到 docs_rj/ 根目录
    - 文件名冲突时重命名（加 _merged 后缀）
    - 合并后删除空的 docs/ 目录

    Returns:
        dict: {merged: [...], skipped: [...], errors: [...]}
    """
    result = {'merged': [], 'skipped': [], 'errors': []}

    if not os.path.isdir(docs_path):
        return result

    docs_rj_abs = os.path.abspath(docs_rj_path)
    docs_abs = os.path.abspath(docs_path)

    try:
        entries = os.listdir(docs_abs)
    except OSError as e:
        logger.warning(f"扫描 docs/ 目录失败: {e}")
        result['errors'].append({'src': docs_abs, 'error': str(e)})
        return result

    for entry in entries:
        src_path = os.path.join(docs_abs, entry)

        if os.path.isdir(src_path):
            # 子目录映射
            mapped_dir = DOCS_SUBDIR_MAP.get(entry, entry)
            dst_dir = os.path.join(docs_rj_abs, mapped_dir)
            if not os.path.isdir(dst_dir):
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                except OSError as e:
                    result['errors'].append({'src': src_path, 'error': str(e)})
                    continue

            # 移动子目录下所有文件
            try:
                for fname in os.listdir(src_path):
                    src_file = os.path.join(src_path, fname)
                    dst_file = os.path.join(dst_dir, fname)
                    if os.path.exists(dst_file):
                        # 冲突：重命名
                        name, ext = os.path.splitext(fname)
                        dst_file = os.path.join(dst_dir, f"{name}_merged{ext}")
                        logger.warning(f"文件冲突，重命名: {fname} → {os.path.basename(dst_file)}")
                    if dry_run:
                        result['merged'].append({
                            'src': src_file, 'dst': dst_file, 'dry_run': True
                        })
                    else:
                        shutil.move(src_file, dst_file)
                        result['merged'].append({
                            'src': src_file, 'dst': dst_file
                        })
            except OSError as e:
                result['errors'].append({'src': src_path, 'error': str(e)})
        elif os.path.isfile(src_path):
            # 直接文件移到 docs_rj/ 根目录
            dst_file = os.path.join(docs_rj_abs, entry)
            if os.path.exists(dst_file):
                name, ext = os.path.splitext(entry)
                dst_file = os.path.join(docs_rj_abs, f"{name}_merged{ext}")
                logger.warning(f"文件冲突，重命名: {entry} → {os.path.basename(dst_file)}")
            if dry_run:
                result['merged'].append({
                    'src': src_path, 'dst': dst_file, 'dry_run': True
                })
            else:
                shutil.move(src_path, dst_file)
                result['merged'].append({
                    'src': src_path, 'dst': dst_file
                })

    # 合并完成后删除 docs/ 目录（如果为空）
    if not dry_run:
        try:
            # 检查 docs/ 是否为空（递归）
            remaining = []
            for root, dirs, files in os.walk(docs_abs):
                if files:
                    remaining.append(os.path.join(root, files[0]))
            if not remaining:
                shutil.rmtree(docs_abs)
                logger.info(f"合并完成，已删除空的 docs/ 目录: {docs_abs}")
            else:
                logger.warning(f"docs/ 目录仍有残留文件，未删除: {remaining[:3]}")
                result['skipped'].append({
                    'src': docs_abs,
                    'reason': f'目录非空，残留 {len(remaining)} 个文件'
                })
        except OSError as e:
            logger.warning(f"删除 docs/ 目录失败: {e}")
            result['errors'].append({'src': docs_abs, 'error': str(e)})

    return result


def auto_merge_if_conflict(docs_dir='./docs', docs_rj_dir=None, verbose=True):
    """检测到 docs/ 和 docs_rj/ 同时存在时，自动合并 docs/ → docs_rj/。

    全模式入口：在脚本所有模式启动前调用此函数，做到任何模式
    运行时发现冲突都先自动合并，避免平台 docs/ 与 pdca-skill docs_rj/ 冲突。

    Args:
        docs_dir: 平台 docs/ 路径（默认 ./docs）
        docs_rj_dir: pdca-skill docs_rj/ 路径（默认 None → 外置 ~/.pdca-skill/data/docs_rj）
        verbose: 是否输出详细日志（默认 True）

    Returns:
        dict: merge_docs_to_docs_rj 的返回结果
              {merged: [...], skipped: [...], errors: [...]}
    """
    if docs_rj_dir is None:
        docs_rj_dir = str(user_data_path.get_docs_rj_path())
    docs_abs = os.path.abspath(docs_dir)
    docs_rj_abs = os.path.abspath(docs_rj_dir)

    if not (os.path.isdir(docs_abs) and os.path.isdir(docs_rj_abs)):
        return {'merged': [], 'skipped': [], 'errors': []}

    if verbose:
        logger.warning("⚠️ 检测到平台自动创建的 docs/ 和 pdca-skill 规范的 docs_rj/ 同时存在")
        logger.warning("   按 pdca-skill 规范，自动合并 docs/ 内容到 docs_rj/，然后删除 docs/")

    result = merge_docs_to_docs_rj(docs_abs, docs_rj_abs)

    if verbose:
        merged_count = len(result['merged'])
        if merged_count > 0:
            logger.info(f"   合并完成：{merged_count} 个文件已移至 docs_rj/")
        if result['errors']:
            logger.warning(f"   合并出错 {len(result['errors'])} 个，详见 JSON 输出")

    return result


def find_docs_dir(custom_dir=None, create=True):
    """查找 docs 目录，遵循主 docs 目录策略

    优先级：
    1. 命令行 --docs-dir 参数
    2. .primary_docs_rj 标记文件
    3. memory_rj/MEMORY_RJ.md 约定区块记录的主 docs 路径（双读兼容老命名）
    4. 优先级路由（./docs_rj > ./.agent/documents > ./src/docs）
    5. 第一个找到的 docs_rj 目录

    【硬性规则】：当同时存在 ./docs 和 ./docs_rj 时，**必须优先使用 docs_rj**，
    拒绝使用平台自动创建的 docs 目录，避免与 pdca-skill 规范冲突。

    Args:
        custom_dir: 显式指定的 docs 目录（优先于自动检测）。
        create: 当未找到任何 docs 目录时是否自动创建默认 ./docs_rj。
                报告型场景（如 startup_tidy 守卫）应传 False，
                仅返回候选路径、绝不静默创建（遵循 bootstrap.md §四）。
    """
    if custom_dir:
        if os.path.isdir(custom_dir):
            logger.info(f"使用指定目录: {custom_dir}")
            return os.path.abspath(custom_dir)
        raise FileNotFoundError(f"指定的 docs 目录不存在: {custom_dir}")

    # 1. 先读 .primary_docs_rj 标记（最高优先级，R3）
    marker_docs = read_primary_docs_marker()
    if marker_docs:
        return marker_docs

    # 2. 读 MEMORY_RJ.md（双读兼容）
    memory_docs = read_primary_docs_from_memory()
    if memory_docs:
        return memory_docs

    # 3. 扫描项目找所有 docs 目录
    found_dirs = []
    found_rj = False
    found_docs = False
    try:
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if root == '.':
                if 'docs_rj' in dirs:
                    # 用户数据外置：已迁移（.migrated 标记）则跳过包内 docs_rj，
                    # 但仍设 found_rj=True 防止包内 docs/ 被误用为主 docs
                    migrated_marker = os.path.join(os.getcwd(), '.migrated')
                    if os.path.isfile(migrated_marker):
                        found_rj = True
                        logger.info("检测到 .migrated 标记，跳过包内 docs_rj（已迁移到外置目录）")
                    else:
                        found_rj = True
                        found_dirs.append(os.path.abspath('./docs_rj'))
                if 'docs' in dirs:
                    found_docs = True
                    # 【硬性规则】：只有在没有 docs_rj 时才考虑 docs
                    if not found_rj:
                        found_dirs.append(os.path.abspath('./docs'))
                        logger.warning("⚠️ 检测到平台自动创建的 docs/ 目录（非 pdca-skill 规范），建议创建 docs_rj/ 并使用 --declare-primary 宣告主 docs")
                continue
            depth = root.count(os.sep)
            if depth > 2:
                continue
            if 'docs_rj' in dirs:
                full_path = os.path.join(root, 'docs_rj')
                abs_path = os.path.abspath(full_path)
                if abs_path not in found_dirs:
                    found_dirs.append(abs_path)
            elif 'docs' in dirs and not found_rj:
                full_path = os.path.join(root, 'docs')
                abs_path = os.path.abspath(full_path)
                if abs_path not in found_dirs:
                    found_dirs.append(abs_path)
    except OSError as e:
        logger.warning(f"遍历目录时出错: {e}")

    # 去重
    found_dirs = list(dict.fromkeys(found_dirs))

    # 【硬性规则】：同时存在 docs 和 docs_rj 时，合并 docs → docs_rj，然后忽略 docs
    if found_rj and found_docs:
        auto_merge_if_conflict(verbose=False)  # find_docs_dir 内部调用，关闭 verbose 避免重复日志
        found_dirs = [d for d in found_dirs if 'docs_rj' in d or 'documents' in d]

    if not found_dirs:
        default_path = str(user_data_path.get_docs_rj_path())
        if create:
            logger.info(f"未找到 docs 目录，在根目录创建 pdca-skill 规范目录: {default_path}")
            try:
                os.makedirs(default_path, exist_ok=True)
            except OSError as e:
                raise RuntimeError(f"无法创建 docs 目录 '{default_path}': {e}")
            return default_path
        else:
            logger.info(f"未找到 docs 目录，返回候选路径（不创建，报告型）: {default_path}")
            return default_path

    if len(found_dirs) == 1:
        logger.info(f"找到唯一 docs 目录: {found_dirs[0]}")
        return found_dirs[0]

    logger.warning(f"检测到多个 docs 目录: {found_dirs}")
    for priority in PRIORITY_PATHS:
        priority_abs = os.path.abspath(priority)
        for found in found_dirs:
            if os.path.abspath(found) == priority_abs:
                logger.info(f"按优先级选择: {found}")
                logger.warning("建议：运行 python generate_docs.py --declare-primary 宣告主 docs，避免每次扫描")
                return found

    logger.info(f"选择第一个找到的目录: {found_dirs[0]}")
    logger.warning("建议：运行 python generate_docs.py --declare-primary 宣告主 docs，避免每次扫描")
    return found_dirs[0]


def get_timestamp():
    """获取当前时间戳（精确到分钟）"""
    now = datetime.now()
    return {
        'datetime': now.strftime('%Y-%m-%d %H:%M'),
        'date': now.strftime('%Y%m%d'),
        'time': now.strftime('%H%M'),
        'date_dash': now.strftime('%Y-%m-%d'),
    }


def generate_filename(doc_type, task_name, timestamp):
    """生成文件名（扁平命名：{task}_{type}_YYYYMMDD_HHMM.md）"""
    return f"{task_name}_{doc_type}_{timestamp['date']}_{timestamp['time']}.md"


def create_dir_structure(docs_dir, task_name=None):
    """创建扁平文档目录结构：docs_dir 下直接常驻 5 类 _rj 文件夹。

    task_name 不再作为子目录（任务名进文件名），参数保留仅为兼容旧调用。
    """
    try:
        os.makedirs(docs_dir, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"无法创建主 docs 目录 '{docs_dir}': {e}")

    for sub_dir in DOC_RJ_SUBDIRS:
        sub_path = os.path.join(docs_dir, sub_dir)
        try:
            os.makedirs(sub_path, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"无法创建子目录 '{sub_path}': {e}")

    return docs_dir


def load_template(assets_dir, template_name):
    """加载模板文件"""
    template_path = os.path.join(assets_dir, template_name)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")
    if not os.access(template_path, os.R_OK):
        raise PermissionError(f"无权限读取模板文件: {template_path}")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError as e:
        raise RuntimeError(f"模板文件编码错误 '{template_path}': {e}")
    if not content.strip():
        raise ValueError(f"模板文件为空: {template_path}")
    return content


def replace_placeholders(content, task_name, timestamp):
    """替换模板中的占位符"""
    replacements = {
        '{任务名}': task_name,
        '{日期}': timestamp['date'],
        '{时间}': timestamp['time'],
        'YYYY-MM-DD HH:MM': timestamp['datetime'],
        'YYYY-MM-DD': timestamp['date_dash'],
        'HH:MM': timestamp['time'],
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def atomic_write(file_path, content, max_retries=5):
    """原子写入：先写临时文件，再重命名，避免写入中断导致文件损坏。

    对 Windows 下 os.replace 偶发的共享冲突（WinError 5 / PermissionError，常见于
    其他线程/进程正以独占方式打开目标文件）做有限指数退避重试，
    提升并发读写健壮性（对抗性测试 D7 / D10）。
    """
    import time as _time
    dir_name = os.path.dirname(file_path)
    last_err = None
    for attempt in range(max_retries):
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp', prefix='.generate_docs_')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
            os.replace(tmp_path, file_path)  # 原子操作（Windows Python 3.3+ 支持）
            return
        except (OSError, PermissionError) as e:
            last_err = e
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            _time.sleep(0.05 * (attempt + 1))
    raise RuntimeError(f"写入文件失败 '{file_path}': {last_err}")


def generate_doc(docs_dir, task_name, doc_type, assets_dir, timestamp):
    """生成单个文档"""
    info = DOC_TYPES[doc_type]
    template = load_template(assets_dir, info['template'])
    content = replace_placeholders(template, task_name, timestamp)
    filename = generate_filename(doc_type, task_name, timestamp)
    file_path = os.path.join(docs_dir, info['dir'], filename)

    atomic_write(file_path, content)
    logger.info(f"创建: {file_path}")
    return True


def print_tree(task_dir):
    """打印目录树（带错误处理）"""
    try:
        for root, dirs, files in os.walk(task_dir):
            level = root.replace(task_dir, '').count(os.sep)
            indent = '│   ' * level
            subindent = '│   ' * (level + 1)
            print(f"{indent}{os.path.basename(root)}/")
            for file in sorted(files):
                print(f"{subindent}{file}")
    except OSError as e:
        logger.error(f"扫描目录树失败: {e}")


# ============================================================
# 散落文档检测与归档
# ============================================================

def detect_pdca_task_docs(docs_dir):
    """扫描一个 docs 目录，返回 pdca-skill 特征的文档集列表（兼容扁平+旧结构）

    返回格式：[{task_name, path, doc_types: [...], flat: bool}, ...]
    - 扁平结构：docs_dir 下直接是 5 类 _rj 文件夹，任务名从文件名提取；
      额外返回一条 docs_dir 自身作为整体文档集（供 scan 汇总）。
    - 旧结构：docs_dir 下按任务名分子目录，子目录内含 pdca_SUBDIRS。
    """
    results = []
    if not os.path.isdir(docs_dir):
        return results

    try:
        entries = sorted(os.listdir(docs_dir))
    except OSError as e:
        logger.warning(f"扫描 docs 目录失败 {docs_dir}: {e}")
        return results

    # 扁平结构：docs_dir 下直接是 5 类 _rj 文件夹（无 task 子目录）
    top_type_dirs = [e for e in entries
                     if os.path.isdir(os.path.join(docs_dir, e)) and e in pdca_SUBDIRS]
    if top_type_dirs:
        # 收集各类型目录下符合命名模式的任务名
        task_types = {}
        for td in top_type_dirs:
            td_path = os.path.join(docs_dir, td)
            try:
                for fname in os.listdir(td_path):
                    if pdca_FILE_PATTERN.match(fname):
                        tname = fname.split('_', 1)[0]
                        task_types.setdefault(tname, set()).add(td)
            except OSError:
                continue
        for tname, dts in sorted(task_types.items()):
            results.append({
                'task_name': tname,
                'path': os.path.join(docs_dir, tname),  # 占位（扁平结构无 task 子目录）
                'doc_types': sorted(dts),
                'flat': True,
            })
        # 扁平结构本身作为一条整体文档集返回（供 scan 汇总/校验）
        results.append({
            'task_name': os.path.basename(os.path.normpath(docs_dir)),
            'path': os.path.abspath(docs_dir),
            'doc_types': sorted(top_type_dirs),
            'flat': True,
        })
        return results

    # 兼容旧结构（按任务名分子目录）
    for entry in entries:
        entry_path = os.path.join(docs_dir, entry)
        if not os.path.isdir(entry_path) or entry.startswith('.'):
            continue
        if entry in ('archive_rj', 'archive'):
            continue
        subdirs = set()
        try:
            subdirs = {d for d in os.listdir(entry_path)
                      if os.path.isdir(os.path.join(entry_path, d))}
        except OSError:
            continue
        pdca_subs = subdirs & pdca_SUBDIRS
        if not pdca_subs:
            continue
        has_pdca_files = False
        doc_types_found = set()
        for sub in pdca_subs:
            sub_path = os.path.join(entry_path, sub)
            try:
                for fname in os.listdir(sub_path):
                    if fname.endswith('.md') and pdca_FILE_PATTERN.match(fname):
                        has_pdca_files = True
                        doc_types_found.add(sub)
            except OSError:
                continue
        if has_pdca_files:
            results.append({
                'task_name': entry,
                'path': os.path.abspath(entry_path),
                'doc_types': sorted(doc_types_found),
                'flat': False,
            })
    return results


def find_all_docs_dirs():
    """扫描项目，返回所有 docs 目录的绝对路径列表（兼容 docs_rj 和老命名 docs）"""
    found = []
    try:
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            # 优先 docs_rj，兼容老命名 docs
            for docs_name in ('docs_rj', 'docs'):
                if docs_name in dirs:
                    full_path = os.path.join(root, docs_name)
                    abs_path = os.path.abspath(full_path)
                    if abs_path not in found:
                        found.append(abs_path)
            # 只扫2层深度
            depth = root.count(os.sep)
            if depth > 2:
                dirs[:] = []  # 超过2层深度，清空 dirs 列表以阻止 os.walk 继续递归
    except OSError as e:
        logger.warning(f"遍历目录时出错: {e}")
    return found


def scan_scattered_docs(primary_docs):
    """扫描非主 docs 目录，汇总散落任务文档清单

    返回格式：{docs_dir: [{task_name, path, doc_types}, ...], ...}
    """
    all_docs = find_all_docs_dirs()
    primary_abs = os.path.abspath(primary_docs)
    scattered = {}

    for docs_dir in all_docs:
        if os.path.abspath(docs_dir) == primary_abs:
            continue
        task_docs = detect_pdca_task_docs(docs_dir)
        if task_docs:
            scattered[docs_dir] = task_docs

    return scattered


def archive_scattered_docs(primary_docs, dry_run=False):
    """执行归档：移动散落任务文档到主 docs

    返回格式：{archived: [...], skipped: [...], errors: [...]}
    """
    primary_abs = os.path.abspath(primary_docs)
    scattered = scan_scattered_docs(primary_docs)

    result = {'archived': [], 'skipped': [], 'errors': []}

    if not scattered:
        return result

    for source_docs, task_list in scattered.items():
        for task in task_list:
            # 扁平结构：docs_dir 本身作为整体文档集返回，不整体移动（按类型常驻）
            if task.get('flat'):
                result['skipped'].append({
                    'task_name': task['task_name'],
                    'src': task['path'],
                    'reason': '扁平结构文档集，按类型常驻，不整体移动',
                })
                continue
            task_name = task['task_name']
            src_path = task['path']
            dst_path = os.path.join(primary_abs, task_name)

            # 冲突检查
            if os.path.exists(dst_path):
                result['skipped'].append({
                    'task_name': task_name,
                    'src': src_path,
                    'dst': dst_path,
                    'reason': '同名任务已存在于主 docs',
                })
                logger.warning(f"跳过（同名冲突）: {task_name}")
                continue

            if dry_run:
                result['archived'].append({
                    'task_name': task_name,
                    'src': src_path,
                    'dst': dst_path,
                    'doc_types': task['doc_types'],
                    'dry_run': True,
                })
                continue

            # 执行移动
            try:
                shutil.move(src_path, dst_path)
                result['archived'].append({
                    'task_name': task_name,
                    'src': src_path,
                    'dst': dst_path,
                    'doc_types': task['doc_types'],
                })
                logger.info(f"归档: {task_name} ({', '.join(task['doc_types'])})")
            except (OSError, shutil.Error) as e:
                result['errors'].append({
                    'task_name': task_name,
                    'src': src_path,
                    'error': str(e),
                })
                logger.error(f"归档失败 {task_name}: {e}")

    return result


# ============================================================
# 命名空间迁移
# ============================================================

# 文件内路径引用替换规则（用于更新文件内容）
# 注意：只替换带路径前缀的引用，不做裸 'MEMORY.md' 替换，避免误伤全局记忆 ~/.agent/memory/MEMORY.md
PATH_REPLACEMENTS = [
    ('memory/MEMORY.md', 'memory_rj/MEMORY_RJ.md'),
    ('memory/YYYY-MM-DD.md', 'memory_rj/YYYY-MM-DD.md'),
    ('./memory/', './memory_rj/'),
    ('./docs/', './docs_rj/'),
    ('docs/SUMMARY.md', 'docs_rj/SUMMARY_RJ.md'),
    ('{主docs}/SUMMARY.md', '{主docs}/SUMMARY_RJ.md'),
]


def migrate_to_rj(dry_run=True):
    """将老命名迁移到 _rj 新命名

    返回格式：{migrated: [...], skipped: [...], errors: [...]}
    """
    result = {'migrated': [], 'skipped': [], 'errors': []}

    def _do_migrate(old_path, new_path, path_type):
        """执行单个迁移项的辅助函数"""
        if not os.path.exists(old_path):
            return
        if os.path.exists(new_path):
            result['skipped'].append({
                'old': old_path, 'new': new_path,
                'reason': '目标已存在',
            })
            logger.warning(f"跳过（目标已存在）: {old_path} → {new_path}")
            return

        if dry_run:
            result['migrated'].append({
                'old': old_path, 'new': new_path,
                'type': path_type, 'dry_run': True,
            })
            return

        try:
            os.makedirs(os.path.dirname(new_path) or '.', exist_ok=True)
            shutil.move(old_path, new_path)
            result['migrated'].append({
                'old': old_path, 'new': new_path, 'type': path_type,
            })
            logger.info(f"迁移: {old_path} → {new_path}")
        except (OSError, shutil.Error) as e:
            result['errors'].append({
                'old': old_path, 'error': str(e),
            })
            logger.error(f"迁移失败 {old_path}: {e}")

    # 1a. 先迁移根级目录（memory→memory_rj, docs→docs_rj, outputs→outputs_rj）
    dir_migrations = [
        ('./memory', './memory_rj'),
        ('./docs', './docs_rj'),
        ('./outputs', './outputs_rj'),
    ]
    for old_dir, new_dir in dir_migrations:
        _do_migrate(old_dir, new_dir, 'dir')

    # 1b. 再重命名已迁移目录内的文件（此时老路径已不存在，用新目录路径）
    file_renames = [
        ('./memory_rj/MEMORY.md', './memory_rj/MEMORY_RJ.md', 'file'),
        ('./docs_rj/SUMMARY.md', './docs_rj/SUMMARY_RJ.md', 'file'),
    ]
    for old_file, new_file, ftype in file_renames:
        _do_migrate(old_file, new_file, ftype)

    # 1c. 根级独立文件（不在已迁移目录内）
    _do_migrate('./SOUL.md', './SOUL_HH.md', 'file')

    # 2. 迁移任务子目录（docs_rj/{任务名}/ 下的 spec/ → spec_rj/ 等）
    docs_dir = './docs_rj' if os.path.isdir('./docs_rj') else './docs'
    if os.path.isdir(docs_dir):
        sub_migrations = [
            ('spec', 'spec_rj'), ('task', 'task_rj'),
            ('handoff', 'handoff_rj'), ('memory', 'memory_rj'),
            ('archive', 'archive_rj'),
        ]
        try:
            for entry in os.listdir(docs_dir):
                entry_path = os.path.join(docs_dir, entry)
                if not os.path.isdir(entry_path) or entry.startswith('.'):
                    continue
                if entry in ('archive_rj', 'archive'):
                    continue
                for old_sub, new_sub in sub_migrations:
                    old_sub_path = os.path.join(entry_path, old_sub)
                    new_sub_path = os.path.join(entry_path, new_sub)
                    if not os.path.isdir(old_sub_path):
                        continue
                    if os.path.exists(new_sub_path):
                        result['skipped'].append({
                            'old': old_sub_path, 'new': new_sub_path,
                            'reason': '目标已存在',
                        })
                        continue
                    if dry_run:
                        result['migrated'].append({
                            'old': old_sub_path, 'new': new_sub_path,
                            'type': 'subdir', 'dry_run': True,
                        })
                        continue
                    try:
                        shutil.move(old_sub_path, new_sub_path)
                        result['migrated'].append({
                            'old': old_sub_path, 'new': new_sub_path, 'type': 'subdir',
                        })
                        logger.info(f"迁移子目录: {old_sub_path} → {new_sub_path}")
                    except (OSError, shutil.Error) as e:
                        result['errors'].append({
                            'old': old_sub_path, 'error': str(e),
                        })
        except OSError as e:
            logger.warning(f"扫描 docs 目录失败: {e}")

    # 3. 更新文件内部路径引用
    if not dry_run and result['migrated']:
        files_to_update = []
        # MEMORY_RJ.md
        if os.path.isfile('./memory_rj/MEMORY_RJ.md'):
            files_to_update.append('./memory_rj/MEMORY_RJ.md')
        # SUMMARY_RJ.md
        for summary_path in ['./docs_rj/SUMMARY_RJ.md', './docs/SUMMARY.md']:
            if os.path.isfile(summary_path):
                files_to_update.append(summary_path)
        # 任务子目录下所有 .md 文件（spec_rj/task_rj/handoff_rj/memory_rj）
        docs_dir = './docs_rj' if os.path.isdir('./docs_rj') else './docs'
        if os.path.isdir(docs_dir):
            try:
                for entry in os.listdir(docs_dir):
                    entry_path = os.path.join(docs_dir, entry)
                    if not os.path.isdir(entry_path) or entry.startswith('.'):
                        continue
                    if entry in ('archive_rj', 'archive'):
                        continue
                    for sub_name in ('spec_rj', 'task_rj', 'handoff_rj',
                                     'memory_rj',
                                     'spec', 'task', 'handoff',
                                     'memory'):
                        sub_path = os.path.join(entry_path, sub_name)
                        if not os.path.isdir(sub_path):
                            continue
                        for fname in os.listdir(sub_path):
                            if fname.endswith('.md'):
                                files_to_update.append(os.path.join(sub_path, fname))
            except OSError as e:
                logger.warning(f"扫描任务子目录失败: {e}")

        for file_path in files_to_update:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                original = content
                for old_str, new_str in PATH_REPLACEMENTS:
                    content = content.replace(old_str, new_str)
                if content != original:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"更新路径引用: {file_path}")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"更新文件引用失败 {file_path}: {e}")

    return result


# ============================================================
# 引导式建项目骨架 + 文件头注释 + 大文件拆分
# - bootstrap_host: 引导式建项目骨架(调 tidy_common.ensure_global_structure)
# - generate_doc_with_comment: 文件头部加 generated-by 注释
# - split_if_needed: 超 max_lines 按 ## 章节拆为主文件索引+子目录+子文件
# 注意:bootstrap_host 必须在 main 之前定义(Python 函数定义顺序)。
# ============================================================

def bootstrap_host(skill_root, dry_run=False):
    """引导式建项目骨架(调 tidy_common.ensure_global_structure)。

    Args:
        skill_root: skill 包根目录(memory/ 与 docs_rj/memory_rj/ 在其下创建)。
        dry_run: True 时只返回报告不写盘;False 时实际创建结构。

    Returns:
        dict: {'created': [...], 'existed': [...], 'errors': [...]}
              dry_run 时 created/existed 为空(不实际检查也不创建),
              只返回 dry_run 标记与目标路径,供调用方预览。
    """
    if dry_run:
        return {
            'created': [],
            'existed': [],
            'errors': [],
            'dry_run': True,
            'target': skill_root,
            'plan': [
                'memory/',
                'memory/memory_main.md',
                'docs_rj/memory_rj/',
            ],
        }
    return tidy_common.ensure_global_structure(skill_root)


def generate_doc_with_comment(content, source_path, output_path):
    """在 content 开头加 3 行 generated-by 注释,写到 output_path。

    注释格式:
        <!-- generated-by: pdca-skill generate_docs.py -->
        <!-- source: {source_path} -->
        <!-- generated-at: {YYYY-MM-DD HH:MM} -->

    Args:
        content: 文档正文内容(不加注释的原始内容)。
        source_path: 源文件路径(写入注释 source 行)。
        output_path: 输出文件路径(含注释的完整文档)。

    Returns:
        None
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    header = (
        '<!-- generated-by: pdca-skill generate_docs.py -->\n'
        '<!-- source: %s -->\n'
        '<!-- generated-at: %s -->\n\n'
    ) % (source_path, timestamp)
    final_content = header + (content or '')
    # 复用本文件已有的 atomic_write,保证写入原子性
    atomic_write(output_path, final_content)


def split_if_needed(file_path, max_lines=400):
    """超 max_lines 行的 markdown 按 `^## ` 章节拆为主文件索引+子目录+子文件。

    Args:
        file_path: 待拆分的 markdown 文件路径。
        max_lines: 触发拆分的行数阈值,默认 400。

    Returns:
        dict:
        - 未触发拆分: {'split': False, 'reason': 'below threshold',
                       'lines': int, 'max_lines': int}
        - 触发拆分:   {'split': True, 'main_file': str, 'parts_dir': str,
                       'parts_count': int, 'parts_files': [...]}
        - 出错:       {'split': False, 'reason': 'error: ...'}
    """
    if not os.path.isfile(file_path):
        return {'split': False, 'reason': 'error: file not found: %s' % file_path}

    # 读文件
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return {'split': False, 'reason': 'error: read failed: %s' % e}

    lines = content.split('\n')
    total_lines = len(lines)

    # 未达阈值,不拆
    if total_lines <= max_lines:
        return {
            'split': False,
            'reason': 'below threshold',
            'lines': total_lines,
            'max_lines': max_lines,
        }

    # 按 `^## ` 章节拆分
    # 章节 = 标题行 + 后续非 ## 行
    sections = []  # [{'title': str, 'title_line': str, 'body_lines': [str]}, ...]
    current = None
    pre_section_lines = []  # 第一个 ## 之前的内容(标题/前言)
    for ln in lines:
        if ln.startswith('## '):
            if current is not None:
                sections.append(current)
            title = ln[3:].strip()
            current = {'title': title, 'title_line': ln, 'body_lines': []}
        else:
            if current is None:
                pre_section_lines.append(ln)
            else:
                current['body_lines'].append(ln)
    if current is not None:
        sections.append(current)

    # 章节数太少无法有效拆分(只有 0 或 1 个章节,拆了也没意义)
    if len(sections) < 2:
        return {
            'split': False,
            'reason': 'less than 2 ## sections, cannot split',
            'lines': total_lines,
            'max_lines': max_lines,
            'sections': len(sections),
        }

    # 建 parts 目录
    parts_dir = file_path + '.parts'
    try:
        os.makedirs(parts_dir, exist_ok=True)
    except Exception as e:
        return {'split': False, 'reason': 'error: mkdir parts_dir failed: %s' % e}

    # 写子文件 + 收集索引
    parts_files = []
    index_entries = []  # [(title, filename), ...]
    for sec in sections:
        # 文件名:章节标题 → 安全文件名(去非法字符,空格转_)
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', sec['title'])
        safe_name = safe_name.strip(' .').replace(' ', '_')
        if not safe_name:
            safe_name = 'untitled'
        filename = safe_name + '.md'
        # 防文件名冲突
        dst_path = os.path.join(parts_dir, filename)
        counter = 1
        while os.path.exists(dst_path):
            filename = '%s_%d.md' % (safe_name, counter)
            dst_path = os.path.join(parts_dir, filename)
            counter += 1

        # 子文件内容:标题行 + body
        sub_content = sec['title_line'] + '\n' + '\n'.join(sec['body_lines'])
        if not sub_content.endswith('\n'):
            sub_content += '\n'
        try:
            atomic_write(dst_path, sub_content)
        except Exception as e:
            return {
                'split': False,
                'reason': 'error: write part %s failed: %s' % (filename, e),
                'parts_dir': parts_dir,
                'parts_written': len(parts_files),
            }
        parts_files.append(filename)
        index_entries.append((sec['title'], filename))

    # 主文件保留索引(前言 + 章节标题+链接)
    index_lines = []
    # 保留原前言(第一个 ## 之前的内容)
    pre_text = '\n'.join(pre_section_lines).rstrip()
    if pre_text:
        index_lines.append(pre_text)
        index_lines.append('')
    index_lines.append('<!-- 拆分索引:本文件超过 %d 行,已按 ## 章节拆分到 %s/ -->' % (max_lines, os.path.basename(parts_dir)))
    index_lines.append('')
    index_lines.append('## 章节索引')
    index_lines.append('')
    for title, fname in index_entries:
        index_lines.append('- [%s](./%s/%s)' % (title, os.path.basename(parts_dir), fname))
    index_lines.append('')
    new_main_content = '\n'.join(index_lines)

    try:
        atomic_write(file_path, new_main_content)
    except Exception as e:
        return {
            'split': False,
            'reason': 'error: rewrite main file failed: %s' % e,
            'parts_dir': parts_dir,
            'parts_count': len(parts_files),
            'parts_files': parts_files,
        }

    return {
        'split': True,
        'main_file': file_path,
        'parts_dir': parts_dir,
        'parts_count': len(parts_files),
        'parts_files': parts_files,
    }


def main():
    parser = argparse.ArgumentParser(description='生成任务文档目录结构')
    parser.add_argument('--task', help='任务名称（小写+下划线，如 my_feature）')
    parser.add_argument(
        '--type', default='all',
        choices=['all', 'spec', 'task', 'handoff', 'memory'],
        help='文档类型（默认 all）',
    )
    parser.add_argument('--docs-dir', help='自定义 docs 目录路径')
    # 默认 assets 目录基于脚本位置推导（脚本在 scripts/，assets 在 ../assets/）
    # 修复实战 bug：原默认 './assets' 相对当前工作目录，用户在新项目跑会报"模板目录不存在"
    DEFAULT_ASSETS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets'
    )
    parser.add_argument('--assets-dir', default=DEFAULT_ASSETS_DIR,
                        help=f'模板文件目录（默认基于脚本位置: {DEFAULT_ASSETS_DIR}）')

    # 散落归档模式
    parser.add_argument('--scan-docs', action='store_true',
                        help='扫描所有 docs 目录，输出 pdca-skill 任务文档清单（JSON）')
    parser.add_argument('--archive-scattered', action='store_true',
                        help='将散落的 pdca-skill 任务文档归档到主 docs 目录')
    parser.add_argument('--dry-run', action='store_true',
                        help='归档预演（只输出会做什么，不实际移动文件）')
    parser.add_argument('--primary-docs', help='指定主 docs 目录路径（用于 --archive-scattered）')

    # 命名迁移模式
    parser.add_argument('--migrate-rj', action='store_true',
                        help='将老命名（memory/、MEMORY.md、docs/、SUMMARY.md 等）迁移到新命名（_rj后缀）')

    # 主 docs 唯一性宣告（R3）
    parser.add_argument('--declare-primary', nargs='?', const='', default=None,
                        help='宣告主 docs 唯一性（R3）：写 .primary_docs_rj 标记并确保 '
                             'MEMORY_RJ.md 约定区块记录主 docs 路径；可跟可选路径，'
                             '省略则用检测到的主 docs')

    # 合并 docs → docs_rj
    parser.add_argument('--merge-docs', action='store_true',
                        help='将 docs/ 目录内容合并到 docs_rj/，合并后删除 docs/')

    args = parser.parse_args()

    # ---- 全局钩子：所有模式入口都先检查 docs/docs_rj 冲突并自动合并 ----
    # 唯一例外：--merge-docs 模式自身就是合并，重复执行会重复提示，所以关闭
    if not args.merge_docs:
        auto_merge_if_conflict(verbose=True)

    # ---- 模式分发 ----
    if args.scan_docs:
        # 模式1：扫描所有 docs 目录，输出 JSON
        print("=" * 60)
        print("🔍 docs 目录扫描")
        print("=" * 60)
        all_docs = find_all_docs_dirs()
        # R3：解析主 docs（标记 > 约定 > 路由），作为字段附加到每个元素
        primary = (read_primary_docs_marker()
                   or read_primary_docs_from_memory()
                   or find_docs_dir())
        output = []
        for docs_dir in sorted(all_docs):
            task_docs = detect_pdca_task_docs(docs_dir)
            output.append({
                'docs_dir': docs_dir,
                'task_docs': task_docs,
                'task_count': len(task_docs),
                'primary_docs': primary,
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.archive_scattered:
        # 模式2：归档散落文档
        print("=" * 60)
        print("📦 散落文档归档")
        print("=" * 60)
        primary = args.primary_docs or find_docs_dir(args.docs_dir)
        if not os.path.isdir(primary):
            logger.error(f"主 docs 目录不存在: {primary}")
            sys.exit(1)
        print(f"\n📁 主 docs: {primary}")
        if args.dry_run:
            print("🔄 预演模式（不实际移动文件）\n")
        result = archive_scattered_docs(primary, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.dry_run:
            print(f"\n✅ 归档 {len(result['archived'])} 个，跳过 {len(result['skipped'])} 个，失败 {len(result['errors'])} 个")
        return

    if args.migrate_rj:
        # 模式4：命名迁移
        print("=" * 60)
        print("🔄 命名空间迁移：_rj 后缀")
        print("=" * 60)
        if args.dry_run:
            print("🔄 预演模式（不实际移动文件）\n")
        result = migrate_to_rj(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.dry_run:
            print(f"\n✅ 迁移 {len(result['migrated'])} 项，跳过 {len(result['skipped'])} 项，失败 {len(result['errors'])} 项")
            if result['migrated']:
                print("💡 建议检查文件内部路径引用是否已更新")
        return

    if args.declare_primary is not None:
        # 模式5：主 docs 唯一性宣告（R3）
        print("=" * 60)
        print("📌 主 docs 唯一性宣告（R3）")
        print("=" * 60)
        declared = declare_primary_docs(args.declare_primary or None)
        print(json.dumps({'primary_docs': declared}, ensure_ascii=False, indent=2))
        return

    if args.merge_docs:
        # 模式6：合并 docs → docs_rj
        print("=" * 60)
        print("📦 合并 docs/ → docs_rj/")
        print("=" * 60)
        docs_abs = os.path.abspath('./docs')
        docs_rj_abs = str(user_data_path.get_docs_rj_path())
        if not os.path.isdir(docs_abs):
            print(f"❌ docs/ 目录不存在: {docs_abs}")
            sys.exit(1)
        if not os.path.isdir(docs_rj_abs):
            print(f"❌ docs_rj/ 目录不存在: {docs_rj_abs}")
            sys.exit(1)
        print(f"\n📁 源: {docs_abs}")
        print(f"📁 目标: {docs_rj_abs}")
        if args.dry_run:
            print("🔄 预演模式（不实际移动文件）\n")
        result = merge_docs_to_docs_rj(docs_abs, docs_rj_abs, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.dry_run:
            print(f"\n✅ 合并 {len(result['merged'])} 个，跳过 {len(result['skipped'])} 个，失败 {len(result['errors'])} 个")
        return

    # 模式3：生成文档（原有功能，--task 必填）
    if not args.task:
        parser.error("生成文档模式需要 --task 参数（或使用 --scan-docs / --archive-scattered / --migrate-rj）")

    # --task 模式不支持 --dry-run（生成操作无法预演，违反 dry-run 契约）
    if args.dry_run:
        print("[ERROR] --task 模式不支持 --dry-run（生成操作无法预演）")
        print("       --dry-run 仅适用于 --archive-scattered / --migrate-rj / --merge-docs 模式")
        sys.exit(1)

    # ---- 参数校验 ----
    try:
        validate_task_name(args.task)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # 校验 assets-dir
    assets_dir = os.path.abspath(args.assets_dir)
    if not os.path.isdir(assets_dir):
        logger.error(f"模板目录不存在: {assets_dir}")
        sys.exit(1)

    task_name = args.task
    doc_types = [args.type] if args.type != 'all' else list(DOC_TYPES.keys())

    print("=" * 60)
    print("📋 文档生成脚本")
    print("=" * 60)

    # ---- 主流程 ----
    try:
        docs_dir = find_docs_dir(args.docs_dir)
        create_dir_structure(docs_dir, task_name)
        timestamp = get_timestamp()

        print(f"\n📅 当前时间: {timestamp['datetime']}")
        print(f"📁 主 docs: {docs_dir}")
        print(f"📋 任务名: {task_name}")
        print("\n开始生成文档...")

        success_count = 0
        errors = []
        for doc_type in doc_types:
            try:
                if generate_doc(docs_dir, task_name, doc_type, assets_dir, timestamp):
                    success_count += 1
            except Exception as e:
                logger.error(f"生成 {doc_type} 失败: {e}")
                errors.append((doc_type, str(e)))

        print(f"\n🎉 完成！成功生成 {success_count}/{len(doc_types)} 个文档")
        if errors:
            print(f"⚠️ 失败 {len(errors)} 个:")
            for dt, err in errors:
                print(f"   - {dt}: {err}")

        print("\n目录结构:")
        print_tree(docs_dir)

    except Exception as e:
        logger.error(f"脚本执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
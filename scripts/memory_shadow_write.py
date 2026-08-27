#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_shadow_write.py — 记忆写入器

对话中写记忆时调用：经本模块的 ``write_project(task, content)`` 做"主次跟进双写"。
  * 项目级 store：``{项目根}/docs_rj/memory_rj/{task}_memory_YYYYMMDD_HHMM.md``
    （默认新路径；向后兼容回退 ``./memory/``）
  * 全局聚合 store：``skill包/memory/memory_main.md``（按 ``## {项目名}`` 分段幂等 upsert）

复用 generate_docs.atomic_write 做原子追加（读现有 + 追加 + 原子替换），保证：
  * 不整文件覆写（append-only 语义）；
  * 不互相覆盖独有内容（A3）；
  * 写入原子，避免中断损坏。

变更（2026-07-13）：
  - 删除 write() 方法和 MemoryShadowWriter 类（废弃 #1 平台主存储 + #2 副存储）
  - write_project 提为顶层函数，默认路径改为 docs_rj/memory_rj/
  - GLOBAL_MEMORY_FILE 改名 主memory.md → memory_main.md
  - 加向后兼容：project_memory_dir=None 时自动检测新旧路径

技术约束
--------
* 仅 Python 标准库（os / sys / logging）。
* 复用 generate_docs.atomic_write（import 直接调用）。
* 零新增第三方依赖。
"""

import os
import sys
import json
import logging
import shutil
from datetime import datetime
import re
import threading

# 复用 generate_docs 的 atomic_write（同目录，import 直接调用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_docs  # noqa: E402
import user_data_path  # noqa: E402
from memory_tags import validate_memory_class, infer_memory_class  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 全局记忆聚合目录（skill 包内 memory/）：本脚本位于 scripts/，父目录即包根（与项目位置无关）
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBAL_MEMORY_DIR = str(user_data_path.get_user_data_dir() / "memory")
GLOBAL_MEMORY_FILE = str(user_data_path.get_memory_main_path())


# ---------------------------------------------------------------------------
# 安全层：文件名 sanitize + 并发写锁
# 目的：防御 (1) task 名含 ../ 或 Windows 非法字符导致路径穿越 / 崩溃
# ---------------------------------------------------------------------------

_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CONTENT_CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _sanitize_filename(name):
    """文件名 sanitize：替换非法字符为 _，防止路径穿越/崩溃。"""
    if not name:
        return 'untitled'
    safe = _FILENAME_ILLEGAL.sub('_', str(name))
    safe = safe.strip(' .')
    return safe or 'untitled'


def _sanitize_content(text):
    """内容 sanitize：
    - 剥离控制字符（保留换行/制表符）
    - 行首 2-6 个 # 的 markdown 标题转为加粗（修复 write_project 标题污染 BUG），
      防污染 upsert_global_memory 逻辑（## 切断 ## {项目名} 分段，### 提前截断 block_end）
    """
    if not text:
        return ''
    s = _CONTENT_CTRL.sub('', str(text))
    # 行首 2-6 个 # 标题转加粗（保留视觉强调，去除标题语法）
    # 不处理 # 一级标题（memory_main.md 不用一级标题，且 content 里 # 极少见）
    lines = s.split('\n')
    for i, ln in enumerate(lines):
        stripped = ln.lstrip()
        m = re.match(r'^(#{2,6})\s+(.+?)\s*#*\s*$', stripped)
        if m:
            content = m.group(2).strip()
            lines[i] = '**' + content + '**'
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 跨进程文件锁
# ---------------------------------------------------------------------------

try:
    import msvcrt
    _HAVE_MSVC = True
except ImportError:
    _HAVE_MSVC = False

try:
    import fcntl
    _HAVE_FCNTL = True
except ImportError:
    _HAVE_FCNTL = False


class _CrossProcessLock:
    """可重入跨进程文件锁。同进程线程安全由调用方的 threading.RLock 保证；
    跨进程互斥由 msvcrt(Windows) / fcntl(Linux) 文件锁保证。可重入（depth 计数），
    避免 write_project 内部再调 upsert_global_memory 时重复加锁死锁。

    fd 存于 threading.local（每线程独立），避免多线程下实例属性 self._fd 被互相覆盖
    导致解锁错位（对抗性测试 D7 / D10 并发偶发丢段的根因）。
    """
    _state = threading.local()

    def __init__(self, path):
        self.lockpath = path + '.lock'

    def __enter__(self):
        if not hasattr(self._state, 'depth'):
            self._state.depth = 0
        if self._state.depth == 0:
            # 首跑保护：锁文件路径的父目录（即全局 memory/）可能尚不存在，
            # 必须在 os.open 前预创建，否则 FileNotFoundError 崩溃（红队 P0 已修）。
            os.makedirs(os.path.dirname(self.lockpath), exist_ok=True)
            self._state.fd = os.open(self.lockpath, os.O_CREAT | os.O_RDWR)
            if _HAVE_MSVC:
                msvcrt.locking(self._state.fd, msvcrt.LK_LOCK, 1)
            elif _HAVE_FCNTL:
                fcntl.flock(self._state.fd, fcntl.LOCK_EX)
        self._state.depth += 1
        return self

    def __exit__(self, *exc):
        self._state.depth -= 1
        if self._state.depth == 0:
            try:
                if _HAVE_MSVC:
                    msvcrt.locking(self._state.fd, msvcrt.LK_UNLCK, 1)
                elif _HAVE_FCNTL:
                    fcntl.flock(self._state.fd, fcntl.LOCK_UN)
            finally:
                os.close(self._state.fd)


_WRITE_LOCK = threading.RLock()
_GLOBAL_CP_LOCK = _CrossProcessLock(GLOBAL_MEMORY_FILE)


def check_schema_version():
    """检测外置数据目录结构版本（v1.0.4 tag_folder_monthly，对抗审查 M3 修复）。

    返回 True=已迁移到标签文件夹结构；False=旧结构/无标记（此时 write_project
    降级为 v1.0.3 行为：正文落 memory_rj 根目录 + 全局写完整 block，
    防新旧版本混写撕裂结构）。
    """
    try:
        p = user_data_path.get_user_data_dir() / '.schema_version'
        if not p.is_file():
            return False
        # utf-8-sig 容错 BOM（PowerShell Set-Content -Encoding UTF8 会写 BOM，历史坑）
        with open(str(p), 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return data.get('structure') == 'tag_folder_monthly'
    except Exception:
        return False


def _extract_summary(content, limit=40):
    """从记忆正文提取一句话摘要（首个非空行，去 markdown 加粗符号，截 limit 字）。"""
    for line in (content or '').split('\n'):
        text = line.strip()
        if not text:
            continue
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # 去加粗
        text = re.sub(r'^[-*]\s+', '', text)  # 去列表符
        text = re.sub(r'[|`]', ' ', text)  # 去管道/反引号（防污染索引行分隔）
        text = text.strip()
        if text:
            return text[:limit]
    return '（无摘要）'


def _index_line_time_key(line):
    """提取索引行时间戳作排序键（'- YYYY-MM-DD HH:MM | task | ...'）。

    v1.0.4 修复（实测报告 P2）：追加式写入会让分段内索引行时间乱序，
    本 key 供 stable sort 用。解析失败/脏行返回 '9999' 排块尾，不阻塞正常行顺序。
    """
    m = re.match(r'^-\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|', line)
    return m.group(1) if m else '9999'


def upsert_global_index(project_name, task, index_line):
    """幂等把一行索引 upsert 进全局 memory_main.md 的 ``## {project_name}`` 分段（v1.0.4）。

    与 upsert_global_memory 的分工：本函数只写一行索引（时间|主分类|重要性|is_lesson|摘要|正文链接），
    正文完整条目在项目侧标签文件夹内（source of truth）。同 task 旧索引行被替换（保最新），
    语义对齐 upsert_global_memory 的"每 task 保 1 条最新"。

    v1.0.4 修复（实测报告 P2）：
      ① 同 task 历史可能残留多行 → 全部清除只保留最新 1 行；
      ② 分段内索引行区按时间戳升序 stable 排序，修复纯追加导致的时间乱序。
    """
    heading = '## %s' % project_name
    if not os.path.isfile(GLOBAL_MEMORY_FILE):
        with open(GLOBAL_MEMORY_FILE, 'w', encoding='utf-8') as f:
            f.write('# 主记忆（全局聚合 · 主次跟进）\n\n')
    with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8') as f:
        raw = f.read()
    lines = raw.split('\n')

    # 定位项目分段
    seg_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == heading:
            seg_idx = i
            break

    # 索引行 task key：行内含 [task] 标记（索引行格式含 | {task} | 槽位）
    task_key = '| %s |' % task

    if seg_idx is not None:
        seg_end = len(lines)
        for j in range(seg_idx + 1, len(lines)):
            if lines[j].startswith('## '):
                seg_end = j
                break
        # 先清同 task 旧完整条目块（### 记忆条目 · {task}…到下一 ### / ## 前）——
        # 覆盖"迁移前旧通道写过完整 block，迁移后新通道写索引行"的混合态
        j = seg_idx + 1
        while j < seg_end:
            m = re.match(r'^### 记忆条目 · (.+?)(?:（\d{4}-\d{2}-\d{2} \d{2}:\d{2}）)?\s*$', lines[j].strip())
            if m and m.group(1).strip() == task:
                block_end = j + 1
                while block_end < seg_end and not lines[block_end].startswith('### ') \
                        and not lines[block_end].startswith('## '):
                    block_end += 1
                # 顺带吃掉条目块后的空行（防分段内空洞累积）
                while block_end < seg_end and lines[block_end].strip() == '':
                    block_end += 1
                del lines[j:block_end]
                seg_end -= (block_end - j)
                continue
            j += 1
        # 分段内收集全部同 task 索引行（"- " 开头且含 task_key）
        hits = [j for j in range(seg_idx + 1, seg_end)
                if lines[j].startswith('- ') and task_key in lines[j]]
        if hits:
            # v1.0.4 P2 去重：历史可能残留多行同 task，倒序全删，第一处替换为最新
            for j in reversed(hits[1:]):
                del lines[j]
                seg_end -= 1
            lines[hits[0]] = index_line
        else:
            # 无同 task 行 → 插到分段内已有的索引行块尾部（### 完整条目块之前），
            # 保持"索引行区在上、历史完整 block 区在下"的段内布局
            insert_at = seg_idx + 1
            while insert_at < seg_end and lines[insert_at].strip() == '':
                insert_at += 1
            while insert_at < seg_end and lines[insert_at].startswith('- '):
                insert_at += 1
            lines.insert(insert_at, index_line)

        # v1.0.4 P2 时间严格排序：分段头部连续索引行块按时间戳升序 stable sort
        # （脏行 key='9999' 排块尾；同时间戳保持原有相对次序）
        blk_start = seg_idx + 1
        while blk_start < len(lines) and lines[blk_start].strip() == '':
            blk_start += 1
        blk_end = blk_start
        while blk_end < len(lines) and lines[blk_end].startswith('- '):
            blk_end += 1
        lines[blk_start:blk_end] = sorted(lines[blk_start:blk_end],
                                          key=_index_line_time_key)

        generate_docs.atomic_write(GLOBAL_MEMORY_FILE, '\n'.join(lines))
        return

    # 分段不存在 → 新建（索引行紧跟分段标题；确保与上文有空行）
    if lines and lines[-1].strip():
        lines.append('')
    lines.append(heading)
    lines.append('')
    lines.append(index_line)
    generate_docs.atomic_write(GLOBAL_MEMORY_FILE, '\n'.join(lines))


def upsert_global_memory(project_name, block):
    """幂等把一条记忆 entry upsert 进全局 memory_main.md 的 ``## {project_name}`` 分段（主次跟进）。

    若该分段不存在则新建；存在则在分段标题下追加 entry（append-only，不覆盖独有内容）。
    **幂等去重**：融入前检查 block 首行标题是否已存在于分段内，
    已存在则跳过（真正幂等，避免重复 append 污染全局记忆）。
    全局文件不存在时按标准头创建。

    并发安全：整个读-改-写过程在进程内 RLock + 跨进程文件锁保护下串行化，
    避免多 agent / 多线程同时写 memory_main 导致段丢失（对抗性测试 D3 / D7 / D10）。

    block 合法性校验【learn_cycle 20260723-102312 建议 #2】：
    融入前校验 block 不含 ## 分段标题行 + 不含 --- frontmatter 分隔符，
    防止 TASK_STATE 文件内容（含 ## 标题 + --- frontmatter）被当 memory block
    传入后污染全局 memory（历史执行中 memory_main.md L85-L209 曾被污染）。
    校验失败 → 告警 + 拒绝融入 + 返回 False；校验通过 → 返回 None（继续原逻辑）。
    """
    # block 合法性校验：防 TASK_STATE/外部文件内容污染全局 memory
    if block:
        for ln in block.split('\n'):
            stripped = ln.strip()
            if stripped.startswith('## '):
                logging.warning(
                    "[memory_shadow_write] upsert_global_memory 拒绝融入 block："
                    "含 ## 分段标题行（疑似 TASK_STATE/外部文件污染），project=%s, line=%r",
                    project_name, stripped
                )
                return False
            if stripped == '---':
                logging.warning(
                    "[memory_shadow_write] upsert_global_memory 拒绝融入 block："
                    "含 --- frontmatter 分隔符（疑似 TASK_STATE/外部文件污染），project=%s",
                    project_name
                )
                return False
    with _WRITE_LOCK, _GLOBAL_CP_LOCK:
        os.makedirs(GLOBAL_MEMORY_DIR, exist_ok=True)
        heading = '## %s' % project_name
        if os.path.isfile(GLOBAL_MEMORY_FILE):
            try:
                # errors='replace'：文件含乱码时以替换符读入而非抛 UnicodeDecodeError，
                # 避免 except 分支把 existing 置空导致整体覆盖历史记忆（红队 P1）
                with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as handle:
                    lines = handle.readlines()
            except OSError:
                # 文件损坏（读失败）→ 以标准头重建，不静默清空历史（红队 P1）
                lines = [
                    '# 主记忆（全局聚合 · 主次跟进）\n',
                    '\n',
                    '> ⚠️ 仅供参考，以你当前指令为准。本文件聚合所有项目的项目级记忆。\n',
                    '\n',
                ]
        else:
            lines = [
                '# 主记忆（全局聚合 · 主次跟进）\n',
                '\n',
                '> ⚠️ 仅供参考，以你当前指令为准。本文件聚合所有项目的项目级记忆。\n',
                '\n',
            ]

        # 定位 ## {project_name} 分段
        seg_idx = None
        for i, ln in enumerate(lines):
            if ln.rstrip('\n') == heading:
                seg_idx = i
                break

        # 幂等去重检查（+ 重建修复）：
        # 原逻辑用 block 首行（含时间戳）作为去重 key，每次 stamp 不同导致去重永不命中 → 重复 append 漂移
        # 修复：提取 task 名（去掉时间戳），同 task 已有则替换最新版，无则追加
        # 完整历史保留在 docs_rj/memory_rj/{task}_memory_*.md，memory_main 只保留每 task 1 条最新
        import re as _re
        block_first_line = block.split('\n', 1)[0].strip() if block else ''
        # 提取 task 名：匹配 `### 记忆条目 · {task}（{stamp}）` 或 `### 记忆条目 · {task}`
        _task_match = _re.match(r'^### 记忆条目 · (.+?)(?:（\d{4}-\d{2}-\d{2} \d{2}:\d{2}）)?$', block_first_line)
        block_task_name = _task_match.group(1).strip() if _task_match else block_first_line
        if block_task_name and seg_idx is not None:
            seg_end = len(lines)
            for j in range(seg_idx + 1, len(lines)):
                if lines[j].startswith('## ') and lines[j].rstrip('\n') != heading:
                    seg_end = j
                    break
            # 扫描分段内是否已有同 task 的条目（任意时间戳）
            for j in range(seg_idx + 1, seg_end):
                existing_match = _re.match(r'^### 记忆条目 · (.+?)(?:（\d{4}-\d{2}-\d{2} \d{2}:\d{2}）)?$', lines[j].strip())
                if existing_match and existing_match.group(1).strip() == block_task_name:
                    # 同 task 已有 → 替换为新版本（保留最新时间戳）
                    # 找到原条目的结束位置（下一个 ### 或 ## 或段尾）
                    # v1.0.4 check-fix（BUG-B）：索引行（- … | [正文](file:///…)）也是条目边界——
                    # 旧通道块替换若不在此终止，会把后随索引行当"块内容"整片吃掉（实测吃掉 44 行索引）
                    block_end = j + 1
                    while block_end < seg_end and not lines[block_end].startswith('### ') \
                            and not lines[block_end].startswith('## ') \
                            and not _is_entry_line(lines[block_end]):
                        block_end += 1
                    # 用新 block 替换原条目（按行拆分，确保每行有换行符）
                    new_block_lines = []
                    for blk_line in block.split('\n'):
                        new_block_lines.append(blk_line + '\n' if blk_line else '\n')
                    lines[j:block_end] = new_block_lines
                    generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))
                    return

        if seg_idx is None:
            # 追加新分段（确保与上文有空行）
            if lines and not lines[-1].endswith('\n'):
                lines.append('\n')
            elif lines and lines[-1].strip():
                lines.append('\n')
            lines.append('\n')
            lines.append(heading + '\n')
            lines.append('\n')
            # block 按行拆分后逐行插入，避免多行 block 作为单元素导致去重检查失败
            for blk_line in block.split('\n'):
                lines.append(blk_line + '\n' if blk_line else '\n')
        else:
            # 在分段标题后（跳过紧随的空行）插入 entry
            insert_at = seg_idx + 1
            while insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
            # block 按行拆分后逐行插入，避免多行 block 作为单元素导致去重检查失败
            blk_lines = block.split('\n')
            # 确保每行都有换行符
            for k in range(len(blk_lines)):
                if not blk_lines[k].endswith('\n'):
                    blk_lines[k] = blk_lines[k] + '\n'
            lines[insert_at:insert_at] = blk_lines

        generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))


# ---------------------------------------------------------------------------
# write_project 顶层函数（从 MemoryShadowWriter 类提取）
# ---------------------------------------------------------------------------

def write_project(task, content, project_memory_dir=None, project_name=None,
                  intent="", context="", tools_used=None, feedback_signals=None,
                  outcome="unknown", tags=None,
                  importance_level="medium", is_lesson=False, experience_tags=None,
                  status="active", archive_reason="", reflection="",
                  memory_class=None):
    """项目级记忆双写（主次跟进）+ 评估参数 + 治理 flag：

    1. 落 docs_rj/memory_rj/[{memory_class}/{YYYYMM}/]{task}_memory_YYYYMMDD_HHMM.md
       （schema 已迁移 v1.0.4 时按标签+月份路由；未迁移时降级扁平根目录，v1.0.3 兼容）
    2. 幂等 upsert 进全局 memory/memory_main.md（按 ``## {项目名}`` 分段）：
       schema 已迁移 → 写一行索引行（时间|task|主分类|重要性|is_lesson|摘要|正文链接）；
       未迁移 → 写完整 block（v1.0.3 行为，防旧环境混合撕裂）

    Args:
        task: 任务名（文件名前缀）。
        content: 记忆内容。
        project_memory_dir: 项目记忆目录，None 时自动检测
            （优先 ./docs_rj/memory_rj/，回退 ./memory/ 向后兼容）。
        project_name: 全局聚合用的项目名，默认取当前工作目录基名。
        intent: 用户意图摘要（800字以内）。
        context: 上下文摘要（600字以内）。
        tools_used: 使用的工具列表。
        feedback_signals: 反馈信号列表（positive/negative/mixed）。
        outcome: 结果标签（success/fail/mixed/unknown）。
        tags: 自定义标签列表。
        importance_level: 记忆重要性等级（high/medium/low），agent 自身 LLM 评估。
        is_lesson: 是否为可复用经验（True/False），agent 自身 LLM 评估。
        experience_tags: 经验标签列表（如 ["bugfix", "architecture"]）。
        status: 治理状态（active/archived/demoted），默认 active。
            archived=已归档（软隐藏，不物理移动）；demoted=已降级（全局→项目）。
        archive_reason: 归档/降级原因（status 非 active 时填写）。
        reflection: 反思备注（memory_rethink 工具填写）。
        memory_class: 主分类（v1.0.4，决定正文落哪个标签文件夹）。合法值见
            memory_tags.MEMORY_TAGS；None 时按 content 关键词启发式推断；
            非法值兜底 workflow（validate_memory_class 保证）。

    Returns:
        dict: {'project_ok': True, 'global_ok': True}
    """
    # === 评估参数校验（方案A：agent 调用前自评，非脚本内调 API）===
    valid_levels = {"high", "medium", "low"}
    if importance_level not in valid_levels:
        logger.warning("[memory_shadow_write] importance_level 非法值 %r，用默认 medium", importance_level)
        importance_level = "medium"
    if not isinstance(is_lesson, bool):
        logger.warning("[memory_shadow_write] is_lesson 非布尔值 %r，用默认 False", is_lesson)
        is_lesson = False
    if experience_tags is None:
        experience_tags = []
    elif not isinstance(experience_tags, list):
        logger.warning("[memory_shadow_write] experience_tags 非列表 %r，用默认 []", experience_tags)
        experience_tags = []

    # === 治理 flag 校验（方案 3-R 阶段2）===
    valid_status = {"active", "archived", "demoted"}
    if status not in valid_status:
        logger.warning("[memory_shadow_write] status 非法值 %r，用默认 active", status)
        status = "active"

    # === 主分类处理（v1.0.4）：None 时推断，非法值兜底 workflow ===
    if memory_class is None:
        memory_class = infer_memory_class(content)
        logger.info("[memory_shadow_write] 未传 memory_class，按内容启发式推断为 '%s'", memory_class)
    else:
        memory_class = validate_memory_class(memory_class)

    # === 评估参数 + 治理 flag frontmatter 构建 ===
    tags_str = ", ".join([_sanitize_content(t) for t in experience_tags]) if experience_tags else "无"
    eval_frontmatter_lines = [
        '**重要性**: %s' % importance_level,
        '**是否经验**: %s' % str(is_lesson).lower(),
        '**经验标签**: %s' % tags_str,
        '**状态**: %s' % status,
    ]
    if archive_reason and status != "active":
        eval_frontmatter_lines.append('**归档原因**: %s' % _sanitize_content(archive_reason))
    if reflection:
        eval_frontmatter_lines.append('**反思**: %s' % _sanitize_content(reflection))
    eval_frontmatter = '\n'.join(eval_frontmatter_lines)

    if content is None:
        content = ''
    content = str(content)
    # content 经 _sanitize_content 处理（修复 write_project 标题污染 BUG），
    # 把行首 ## / ### 等标题转加粗，防污染 upsert_global_memory 分段/去重逻辑
    content = _sanitize_content(content)
    if content and not content.endswith('\n'):
        content = content + '\n'

    tools_used = tools_used or []
    feedback_signals = feedback_signals or []
    tags = tags or []

    # 类型规范化：防止字符串被当列表迭代（修复 feedback_signals="positive" 被拆成单字符的 bug）
    if isinstance(tools_used, str):
        tools_used = [tools_used]
    if isinstance(feedback_signals, str):
        feedback_signals = [feedback_signals]
    if isinstance(tags, str):
        tags = [tags]
    if isinstance(experience_tags, str):
        experience_tags = [experience_tags]

    # 向后兼容：project_memory_dir 为 None 时自动检测
    # 优先级（与 handoff_tidy/archive_tidy 对齐，修路径分裂 bug）：
    #   1. primary_docs marker（.primary_docs_rj 标记，项目级 docs）
    #   2. user_data_path.get_memory_rj_path()（外置用户数据目录）
    #   3. 老路径 ./memory/（向后兼容）
    fallback_used = False
    if project_memory_dir is None:
        # 对齐 startup_tidy 的 R3 解析链（marker→MEMORY_RJ约定→路由 ./docs_rj>./.agent/documents>./src/docs>首个docs_rj）
        # 原实现只认 marker：marker 空/带BOM/指向死路径时 startup_tidy 能路由到项目 docs，
        # 这里却静默落用户目录（D2 根因，v1.0.3 修复）
        primary = generate_docs.find_docs_dir(create=False)
        # 微调：find_docs_dir 无项目 docs 时返回外置用户目录（非 None），
        # 解析结果等于外置目录视为 fallback（告警+置位），保证"真 fallback 可见"
        external_docs = os.path.abspath(str(user_data_path.get_docs_rj_path()))
        if primary and os.path.isdir(primary) and os.path.abspath(primary) != external_docs:
            project_memory_dir = os.path.join(primary, 'memory_rj')
        else:
            # v1.0.4（REQ-105）：fallback 回项目 ./docs_rj/memory_rj（文档跟项目走），
            # 不再默认落外置用户目录——旧版此处落外置导致项目记忆跑去主目录
            fallback_dir = os.path.abspath('./docs_rj/memory_rj')
            logger.warning("[write_project] R3 解析链无结果，记忆 fallback 项目目录: %s", fallback_dir)
            project_memory_dir = fallback_dir
            fallback_used = True
        # marker 存在但无效（空/BOM/坏路径）→ 显式告警提示修复（不静默、不代写 marker，守 R3）
        if os.path.isfile('.primary_docs_rj') and generate_docs.read_primary_docs_marker() is None:
            logger.warning(".primary_docs_rj 存在但无效（空/BOM/路径不存在），"
                           "建议运行 python generate_docs.py --declare-primary 修复")
        # 向后兼容：检测老路径 ./memory/（仅当新路径不存在且老路径存在时回退）
        old_path = './memory'
        if not os.path.isdir(project_memory_dir) and os.path.isdir(old_path):
            logger.warning("检测到老路径 ./memory/，建议迁移到 %s", project_memory_dir)
            project_memory_dir = old_path

    safe_task = _sanitize_filename(task)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 构建增强格式条目（含评估参数 frontmatter 注入，H6 修复：两个分支都注入）
    if intent or context or tools_used or feedback_signals or outcome != "unknown" or tags:
        # 新格式：包含元数据字段
        block_lines = []
        block_lines.append('### 记忆条目 · %s（%s）' % (_sanitize_content(task), stamp))
        if intent:
            block_lines.append('**意图**：%s' % _sanitize_content(intent))
        if context:
            block_lines.append('**上下文**：%s' % _sanitize_content(context))
        if tools_used:
            block_lines.append('**工具**：%s' % ', '.join([_sanitize_content(t) for t in tools_used]))
        if feedback_signals:
            block_lines.append('**反馈**：%s' % ', '.join([_sanitize_content(f) for f in feedback_signals]))
        else:
            block_lines.append('**反馈**：none')
        block_lines.append('**结果**：%s' % _sanitize_content(outcome))
        if tags:
            block_lines.append('**标签**：%s' % ', '.join([_sanitize_content(t) for t in tags]))
        # 评估参数 frontmatter 注入（在元数据末尾、content 前）
        block_lines.append(eval_frontmatter)
        block_lines.append('')
        block_lines.append(content)
        block = '\n'.join(block_lines)
    else:
        # 旧格式：兼容原有调用（也注入 eval_frontmatter，保证 AC-002 向后兼容测试通过）
        block = (
            '### 记忆条目 · %s（%s）\n' % (_sanitize_content(task), stamp)
            + eval_frontmatter + '\n\n'
            + content
        )

    # === schema 版本检测（v1.0.4，对抗审查 M3）：旧结构降级为 v1.0.3 行为 ===
    schema_ok = check_schema_version()
    if not schema_ok:
        logger.warning("[memory_shadow_write] 数据结构未迁移 v1.0.4（.schema_version 缺失或"
                       " structure!=tag_folder_monthly），本次按旧扁平结构落盘；"
                       "如需启用标签文件夹请先跑 scripts/migrate_memory_v104.py")

    with _WRITE_LOCK, _GLOBAL_CP_LOCK:
        # 1) 项目级 memory 文件（append-only）
        #    schema 已迁移 → {memory_rj}/{主分类}/{YYYYMM}/{task}_memory_{ts}.md
        #    schema 未迁移 → {memory_rj}/{task}_memory_{ts}.md（v1.0.3 扁平兼容）
        if schema_ok:
            month_dir = os.path.join(project_memory_dir, memory_class,
                                     datetime.now().strftime('%Y%m'))
            try:
                _ensure_parent(os.path.join(month_dir, '.keep'))
                proj_path = os.path.join(month_dir, '%s_memory_%s.md' % (safe_task, ts))
            except Exception as exc:
                # 标签文件夹创建失败 → 降级根目录（不丢数据，告警可见）
                logger.warning("[memory_shadow_write] 标签文件夹创建失败（%s），降级落 %s 根目录",
                               exc, project_memory_dir)
                _ensure_parent(os.path.join(project_memory_dir, '.keep'))
                proj_path = os.path.join(project_memory_dir, '%s_memory_%s.md' % (safe_task, ts))
        else:
            _ensure_parent(os.path.join(project_memory_dir, '.keep'))
            proj_path = os.path.join(project_memory_dir, '%s_memory_%s.md' % (safe_task, ts))
        _append_atomic(proj_path, block)

        # 2) 全局 upsert（按项目分段）：
        #    schema 已迁移 → 索引行（时间|task|主分类|重要性|is_lesson|摘要|正文链接）
        #    schema 未迁移 → 完整 block（v1.0.3 行为）
        project_name = project_name or os.path.basename(os.getcwd())
        if schema_ok:
            abs_path = os.path.abspath(proj_path).replace('\\', '/')
            file_url = 'file:///%s' % abs_path
            index_line = ('- %s | %s | %s | 重要性%s | is_lesson=%s | %s | [正文](%s)'
                          % (stamp, _sanitize_content(task), memory_class,
                             importance_level, str(is_lesson).lower(),
                             _extract_summary(content), file_url))
            upsert_global_index(project_name, task, index_line)
        else:
            upsert_global_memory(project_name, block)

        # S7 修复：write_project 后自动检查容量阈值（超限告警，不自动清洗）
        try:
            cap = check_capacity_threshold(project_name)
            if cap['exceeded']:
                logger.warning("[write_project] 容量超限告警: %s（建议跑 memory_rethink 清洗）", cap)
        except Exception as exc:
            logger.debug("[write_project] 容量检查失败（不影响写入）: %s", exc)

    # G5：返回落点信息（fallback 标志 + 实际目录 + 主分类），CLI stdout 可核对每次记忆落点
    return {'project_ok': True, 'global_ok': True,
            'fallback': fallback_used, 'project_memory_dir': project_memory_dir,
            'memory_class': memory_class, 'schema_v104': schema_ok}


def _ensure_parent(path):
    """确保文件父目录存在（不存在则创建）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _append_atomic(path, content):
    """原子追加：读现有内容 + 拼接 + atomic_write 整体替换。

    保证 append-only 语义且不整文件覆写独有内容（A3）。
    """
    existing = ''
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                existing = handle.read()
        except OSError:
            existing = ''
    new_content = existing + content
    generate_docs.atomic_write(path, new_content)


# ---------------------------------------------------------------------------
# 备份与回滚（方案 3-R 阶段1：5 工具操作前的安全网）
# ---------------------------------------------------------------------------

def _resolve_memory_rj_dir():
    """统一解析项目记忆目录（与 write_project 路径优先级一致）。

    v1.0.4（/check 第2轮对抗审查 H1 修复）：原实现只有两级（marker → 外置），
    与 write_project 新链路分裂——无 marker 时记忆落项目而备份/回滚找外置，
    治理工具（delete/archive/promote/demote/rethink）的安全网静默失效。
    现统一走 find_docs_dir R3 解析链（含项目 ./docs_rj 默认落点），
    解析不出可用目录时兜底项目 ./docs_rj/memory_rj。

    优先级：
      1. R3 解析链（.primary_docs_rj 标记 > MEMORY_RJ 约定 > 项目扫描 > 项目 ./docs_rj 候选）
      2. 兜底 ./docs_rj/memory_rj（项目侧）
    """
    try:
        primary = generate_docs.find_docs_dir(create=False)
    except Exception:
        primary = None
    if primary:
        return os.path.join(primary, 'memory_rj')
    return os.path.abspath('./docs_rj/memory_rj')


def _backup_before_operation(tool_name):
    """操作前备份 memory_main.md + memory_rj/ 到 undo 目录。

    供 5 个治理工具（delete/archive/promote/demote/rethink）调用。
    备份位置：{user_data_dir}/undo/{tool_name}_{ts}/

    Returns:
        str: undo 目录绝对路径（失败返回 None）
    """
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    undo_dir = os.path.join(str(user_data_path.get_user_data_dir()), "undo",
                            "%s_%s" % (tool_name, ts))
    try:
        os.makedirs(undo_dir, exist_ok=True)
        # 备份全局 memory_main.md
        if os.path.isfile(GLOBAL_MEMORY_FILE):
            shutil.copy2(GLOBAL_MEMORY_FILE,
                         os.path.join(undo_dir, "memory_main.md.bak"))
        # 备份项目记忆目录 memory_rj/
        mem_rj_dir = _resolve_memory_rj_dir()
        if os.path.isdir(mem_rj_dir):
            shutil.copytree(mem_rj_dir,
                            os.path.join(undo_dir, "memory_rj.bak"),
                            dirs_exist_ok=True)
        logger.info("[backup] 已备份到 %s", undo_dir)
        return undo_dir
    except Exception as e:
        logger.warning("[backup] 备份失败（操作继续执行）：%s", e)
        return None


def memory_rollback(timestamp):
    """从 undo 目录回滚 memory_main.md + memory_rj/。

    按 timestamp 模糊匹配 undo 目录名（如传入 "20260730_1030" 匹配
    "memory_delete_20260730_103022"）。

    Args:
        timestamp: undo 目录名中的时间戳片段

    Returns:
        dict: {'rolled_back': bool, 'undo_dir': str, 'reason': str}
    """
    undo_base = os.path.join(str(user_data_path.get_user_data_dir()), "undo")
    if not os.path.isdir(undo_base):
        return {'rolled_back': False, 'reason': 'undo 目录不存在: %s' % undo_base}

    # 模糊匹配 timestamp —— S4 修复：排除 rollback_pre_restore 目录（防回滚到"回滚前状态"）
    matched = []
    for d in os.listdir(undo_base):
        if timestamp in d and os.path.isdir(os.path.join(undo_base, d)):
            # 排除 rollback_pre_restore 目录，避免选错（rollback_pre_restore 是回滚前的备份，非原操作备份）
            if 'rollback_pre_restore' in d:
                continue
            matched.append(d)
    if not matched:
        return {'rolled_back': False, 'reason': '未找到匹配 %s 的 undo 目录（已排除 rollback_pre_restore）' % timestamp}
    matched.sort(reverse=True)  # 取最新匹配
    undo_dir = os.path.join(undo_base, matched[0])

    try:
        # 恢复 memory_main.md
        bak_main = os.path.join(undo_dir, "memory_main.md.bak")
        if os.path.isfile(bak_main):
            # 恢复前先备份当前状态（防回滚后想再回滚）
            _backup_before_operation("rollback_pre_restore")
            shutil.copy2(bak_main, GLOBAL_MEMORY_FILE)

        # 恢复 memory_rj/
        bak_rj = os.path.join(undo_dir, "memory_rj.bak")
        mem_rj_dir = _resolve_memory_rj_dir()
        if os.path.isdir(bak_rj) and mem_rj_dir:
            if os.path.isdir(mem_rj_dir):
                shutil.rmtree(mem_rj_dir, ignore_errors=True)
            shutil.copytree(bak_rj, mem_rj_dir, dirs_exist_ok=True)

        logger.info("[rollback] 已从 %s 恢复", undo_dir)
        return {'rolled_back': True, 'undo_dir': undo_dir}
    except Exception as e:
        return {'rolled_back': False, 'reason': '恢复失败: %s' % e, 'undo_dir': undo_dir}


def _cleanup_old_undos(max_age_days=30):
    """清理超期 undo 备份（默认保留 30 天）。"""
    undo_base = os.path.join(str(user_data_path.get_user_data_dir()), "undo")
    if not os.path.isdir(undo_base):
        return 0
    import time
    now = time.time()
    max_age_sec = max_age_days * 86400
    cleaned = 0
    for d in os.listdir(undo_base):
        dpath = os.path.join(undo_base, d)
        if not os.path.isdir(dpath):
            continue
        try:
            age = now - os.path.getmtime(dpath)
            if age > max_age_sec:
                shutil.rmtree(dpath, ignore_errors=True)
                cleaned += 1
        except OSError:
            continue
    return cleaned


# ---------------------------------------------------------------------------
# 治理 flag 操作（方案 3-R 阶段2：upsert 支持 flag + 容量阈值 + 隔离机制）
# ---------------------------------------------------------------------------

# flag 字段正则（解析现有条目的状态/归档原因/反思）
_FLAG_STATUS_RE = re.compile(r'^\*\*状态\*\*:\s*(active|archived|demoted)\s*$', re.MULTILINE)
_FLAG_REASON_RE = re.compile(r'^\*\*归档原因\*\*:\s*(.+?)$', re.MULTILINE)
_FLAG_REFLECTION_RE = re.compile(r'^\*\*反思\*\*:\s*(.+?)$', re.MULTILINE)


def _parse_entry_flag(block_text):
    """解析 memory 条目的 flag 字段。

    Returns:
        dict: {'status': str, 'archive_reason': str, 'reflection': str}
              旧条目无 flag 时 status='active'（默认）
    """
    status = 'active'
    reason = ''
    reflection = ''
    if block_text:
        m = _FLAG_STATUS_RE.search(block_text)
        if m:
            status = m.group(1)
        m = _FLAG_REASON_RE.search(block_text)
        if m:
            reason = m.group(1).strip()
        m = _FLAG_REFLECTION_RE.search(block_text)
        if m:
            reflection = m.group(1).strip()
    return {'status': status, 'archive_reason': reason, 'reflection': reflection}


def _update_entry_flag(block_text, new_status, archive_reason='', reflection=''):
    """修改 memory 条目的 flag 字段（不替换整个 block）。

    供 memory_archive/memory_demote/memory_rethink 工具调用。

    Args:
        block_text: 原始 block 文本（### 记忆条目 ...）
        new_status: 新状态（active/archived/demoted）
        archive_reason: 归档/降级原因（可选）
        reflection: 反思备注（可选）

    Returns:
        str: 修改后的 block 文本
    """
    if not block_text:
        return block_text
    lines = block_text.split('\n')
    new_lines = []
    status_updated = False
    reason_updated = False
    reflection_updated = False
    for ln in lines:
        # 替换状态行
        if _FLAG_STATUS_RE.match(ln):
            new_lines.append('**状态**: %s' % new_status)
            status_updated = True
            # 如果状态变 active，移除归档原因行
            if new_status == 'active':
                continue
        # 替换/跳过归档原因行
        elif _FLAG_REASON_RE.match(ln):
            if archive_reason and new_status != 'active':
                new_lines.append('**归档原因**: %s' % archive_reason)
                reason_updated = True
            # 否则跳过（移除原因）
        # 替换/跳过反思行
        elif _FLAG_REFLECTION_RE.match(ln):
            if reflection:
                new_lines.append('**反思**: %s' % reflection)
                reflection_updated = True
            # 否则跳过（移除反思）
        else:
            new_lines.append(ln)
    # 如果原 block 没有 flag 行，在 eval_frontmatter 后插入
    if not status_updated:
        # 找到 **经验标签**: 行后插入
        insert_idx = 0
        for i, ln in enumerate(new_lines):
            if ln.startswith('**经验标签**:'):
                insert_idx = i + 1
                break
        if insert_idx > 0:
            new_lines.insert(insert_idx, '**状态**: %s' % new_status)
            if archive_reason and new_status != 'active':
                new_lines.insert(insert_idx + 1, '**归档原因**: %s' % archive_reason)
            if reflection:
                new_lines.insert(insert_idx + 2, '**反思**: %s' % reflection)
        else:
            # 无 eval_frontmatter，在首行后插入
            if len(new_lines) > 0:
                new_lines.insert(1, '**状态**: %s' % new_status)
    elif not reason_updated and archive_reason and new_status != 'active':
        # 状态已更新但原因未加，在状态行后插入
        for i, ln in enumerate(new_lines):
            if ln.startswith('**状态**:'):
                new_lines.insert(i + 1, '**归档原因**: %s' % archive_reason)
                break
    elif not reflection_updated and reflection:
        # 反思未加，在归档原因后或状态后插入
        insert_after = '**状态**:'
        for i, ln in enumerate(new_lines):
            if ln.startswith(insert_after) or ln.startswith('**归档原因**:'):
                insert_after = '**归档原因**:' if ln.startswith('**归档原因**:') else '**状态**:'
            else:
                if ln.startswith('**状态**:') or ln.startswith('**归档原因**:'):
                    continue
        # 简化：追加到 block 末尾
        new_lines.append('**反思**: %s' % reflection)
    return '\n'.join(new_lines)


# ---------------------------------------------------------------------------
# 容量阈值检查（方案 3-R 阶段2：防膨胀）
# ---------------------------------------------------------------------------

# 阈值常量（可在 spec 中调整）
SEGMENT_MAX_ENTRIES = 30       # 单项目段最大条目数
SEGMENT_MAX_CHARS = 50000      # 单项目段最大字符数
GLOBAL_MAX_ENTRIES = 500       # 全局最大条目数
MEMORY_RJ_MAX_LINES = 500      # memory_rj/ 单文件最大行数


def _is_entry_line(line):
    """判断一行是否记忆条目：v1.0.3 完整条目（### 记忆条目 ·）或 v1.0.4 索引行
    （- {ts} | {task} | {tag} | 重要性… | is_lesson=… | … | [正文](file:///…)）。"""
    if line.startswith('### 记忆条目 ·'):
        return True
    if line.startswith('- ') and '[正文](file:///' in line:
        return True
    return False


def _count_segment_entries(lines, seg_start, seg_end):
    """统计项目段内的条目数（v1.0.3 ### 条目 + v1.0.4 索引行，对抗审查 M4 修复）。"""
    count = 0
    for i in range(seg_start, seg_end):
        if _is_entry_line(lines[i]):
            count += 1
    return count


def _count_segment_chars(lines, seg_start, seg_end):
    """统计项目段内的总字符数。"""
    return sum(len(lines[i]) for i in range(seg_start, seg_end))


def _count_global_entries(lines):
    """统计全局 memory_main.md 的总条目数（v1.0.4 含索引行口径）。"""
    count = 0
    for ln in lines:
        if _is_entry_line(ln):
            count += 1
    return count


def _find_segment_range(lines, project_name):
    """找到 ## {project_name} 分段的 [seg_start, seg_end) 范围。"""
    heading = '## %s' % project_name
    seg_idx = None
    for i, ln in enumerate(lines):
        if ln.rstrip('\n') == heading:
            seg_idx = i
            break
    if seg_idx is None:
        return (None, None)
    seg_end = len(lines)
    for j in range(seg_idx + 1, len(lines)):
        if lines[j].startswith('## ') and lines[j].rstrip('\n') != heading:
            seg_end = j
            break
    return (seg_idx, seg_end)


def check_capacity_threshold(project_name=None):
    """检查 memory_main.md 容量是否超阈值。

    Args:
        project_name: 指定项目名则只检查该段，None 则检查全局总量

    Returns:
        dict: {
            'exceeded': bool,
            'level': 'segment' / 'global' / 'none',
            'details': dict  # 具体数值
        }
    """
    if not os.path.isfile(GLOBAL_MEMORY_FILE):
        return {'exceeded': False, 'level': 'none', 'details': {}}
    try:
        with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return {'exceeded': False, 'level': 'none', 'details': {}}

    # 全局检查
    global_count = _count_global_entries(lines)
    if global_count > GLOBAL_MAX_ENTRIES:
        return {
            'exceeded': True,
            'level': 'global',
            'details': {'global_count': global_count, 'limit': GLOBAL_MAX_ENTRIES}
        }

    # 段检查
    if project_name:
        seg_start, seg_end = _find_segment_range(lines, project_name)
        if seg_start is not None:
            seg_count = _count_segment_entries(lines, seg_start + 1, seg_end)
            seg_chars = _count_segment_chars(lines, seg_start + 1, seg_end)
            if seg_count > SEGMENT_MAX_ENTRIES or seg_chars > SEGMENT_MAX_CHARS:
                return {
                    'exceeded': True,
                    'level': 'segment',
                    'details': {
                        'project': project_name,
                        'seg_count': seg_count,
                        'seg_chars': seg_chars,
                        'max_entries': SEGMENT_MAX_ENTRIES,
                        'max_chars': SEGMENT_MAX_CHARS,
                    }
                }
    return {'exceeded': False, 'level': 'none', 'details': {'global_count': global_count}}


# ---------------------------------------------------------------------------
# 隔离机制（方案 3-R 阶段2：无 LLM 时只隔离不删除）
# ---------------------------------------------------------------------------

def _get_quarantine_dir():
    """隔离区目录：{user_data_dir}/quarantine/"""
    return os.path.join(str(user_data_path.get_user_data_dir()), "quarantine")


def _quarantine_entry(project_name, block_text, reason='capacity_threshold'):
    """将条目移到隔离区（不删除，供 LLM 复核）。

    Args:
        project_name: 项目名
        block_text: 被隔离的条目文本
        reason: 隔离原因

    Returns:
        str: 隔离文件路径（失败返回 None）
    """
    quarantine_dir = _get_quarantine_dir()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_project = _sanitize_filename(project_name)
    fname = 'quarantine_%s_%s.md' % (safe_project, ts)
    fpath = os.path.join(quarantine_dir, fname)
    try:
        os.makedirs(quarantine_dir, exist_ok=True)
        content = '# 隔离条目（%s）\n\n' % reason
        content += '> 来源项目: %s\n' % project_name
        content += '> 隔离时间: %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        content += '> 状态: 待 LLM 复核（无 LLM 时不自动删除）\n\n'
        content += '---\n\n'
        content += block_text
        generate_docs.atomic_write(fpath, content)
        logger.info("[quarantine] 已隔离条目到 %s", fpath)
        return fpath
    except Exception as e:
        logger.warning("[quarantine] 隔离失败：%s", e)
        return None


# ---------------------------------------------------------------------------
# 治理工具（方案 3-R 阶段3：delete/archive/promote/demote）
# ---------------------------------------------------------------------------

def _find_entry_in_segment(lines, project_name, task_name, timestamp=None):
    """在 ## {project_name} 分段内查找 ### 记忆条目 · {task}（{ts}） 的位置。

    Args:
        lines: memory_main.md 全部行
        project_name: 项目名（## 分段标题）
        task_name: 任务名
        timestamp: 时间戳片段（如 "2026-07-30 14:35"），None 则匹配任意时间戳

    Returns:
        tuple: (entry_start, entry_end, block_text)
              entry_start/entry_end 是行号范围（entry_end 不含）
              block_text 是条目全文
              未找到返回 (None, None, None)
    """
    heading = '## %s' % project_name
    seg_idx = None
    for i, ln in enumerate(lines):
        if ln.rstrip('\n') == heading:
            seg_idx = i
            break
    if seg_idx is None:
        return (None, None, None)
    seg_end = len(lines)
    for j in range(seg_idx + 1, len(lines)):
        if lines[j].startswith('## ') and lines[j].rstrip('\n') != heading:
            seg_end = j
            break
    # 扫描分段内的 ### 记忆条目
    for j in range(seg_idx + 1, seg_end):
        line = lines[j].strip()
        m = re.match(r'^### 记忆条目 · (.+?)(?:（(\d{4}-\d{2}-\d{2} \d{2}:\d{2})）)?$', line)
        if m:
            entry_task = m.group(1).strip()
            entry_ts = m.group(2)
            if entry_task == task_name:
                if timestamp is None or (entry_ts and timestamp in entry_ts):
                    # 找到匹配，定位 block 结束
                    entry_end = j + 1
                    while entry_end < seg_end and not lines[entry_end].startswith('### ') and not lines[entry_end].startswith('## '):
                        entry_end += 1
                    block_text = ''.join(lines[j:entry_end])
                    return (j, entry_end, block_text)
    return (None, None, None)


def memory_delete(task, timestamp=None, project_name=None, hard_delete=False):
    """删除 memory_main.md 中的条目（双键 task+timestamp）。

    HARD-GATE 工具：破坏性操作，调用前应备份。

    Args:
        task: 任务名（必填）
        timestamp: 时间戳片段（如 "2026-07-30 14:35"），None 则删该 task 最新版
        project_name: 项目名，None 则用当前工作目录基名
        hard_delete: True=物理删除；False=标记 archived（默认，软删除可恢复）

    Returns:
        dict: {'deleted': bool, 'soft': bool, 'entry_task': str, 'reason': str}
    """
    if project_name is None:
        project_name = os.path.basename(os.getcwd())
    # 备份
    _backup_before_operation("memory_delete")
    with _WRITE_LOCK, _GLOBAL_CP_LOCK:
        if not os.path.isfile(GLOBAL_MEMORY_FILE):
            return {'deleted': False, 'reason': 'memory_main.md 不存在'}
        try:
            with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            return {'deleted': False, 'reason': 'memory_main.md 读取失败'}
        entry_start, entry_end, block_text = _find_entry_in_segment(lines, project_name, task, timestamp)
        if entry_start is None:
            return {'deleted': False, 'reason': '未找到匹配条目: task=%s ts=%s' % (task, timestamp)}
        if hard_delete:
            # 物理删除（移到 quarantine）—— S2 修复：quarantine 失败时拒绝删除（防数据丢失）
            q_path = _quarantine_entry(project_name, block_text, "hard_delete by memory_delete")
            if q_path is None:
                return {'deleted': False, 'soft': False, 'reason': 'quarantine 失败，拒绝物理删除（防数据丢失）'}
            del lines[entry_start:entry_end]
            generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))
            return {'deleted': True, 'soft': False, 'entry_task': task, 'quarantine_path': q_path}
        else:
            # 软删除（标记 archived）
            new_block = _update_entry_flag(block_text, 'archived', archive_reason='memory_delete 软删除')
            new_lines = new_block.split('\n')
            new_lines = [ln + '\n' if not ln.endswith('\n') else ln for ln in new_lines]
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] = new_lines[-1] + '\n'
            lines[entry_start:entry_end] = new_lines
            generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))
            return {'deleted': True, 'soft': True, 'entry_task': task}


def memory_archive(task, archive_reason, timestamp=None, project_name=None):
    """归档 memory_main.md 中的条目（flag 标记，不物理移动）。

    可逆操作：archived 条目仍在原位，只是被标记。

    Args:
        task: 任务名（必填）
        archive_reason: 归档原因（必填）
        timestamp: 时间戳片段，None 则归档该 task 最新版
        project_name: 项目名，None 则用当前工作目录基名

    Returns:
        dict: {'archived': bool, 'entry_task': str, 'reason': str}
    """
    if not archive_reason:
        return {'archived': False, 'reason': 'archive_reason 不能为空'}
    if project_name is None:
        project_name = os.path.basename(os.getcwd())
    _backup_before_operation("memory_archive")
    with _WRITE_LOCK, _GLOBAL_CP_LOCK:
        if not os.path.isfile(GLOBAL_MEMORY_FILE):
            return {'archived': False, 'reason': 'memory_main.md 不存在'}
        try:
            with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            return {'archived': False, 'reason': 'memory_main.md 读取失败'}
        entry_start, entry_end, block_text = _find_entry_in_segment(lines, project_name, task, timestamp)
        if entry_start is None:
            return {'archived': False, 'reason': '未找到匹配条目: task=%s ts=%s' % (task, timestamp)}
        new_block = _update_entry_flag(block_text, 'archived', archive_reason=archive_reason)
        new_lines = new_block.split('\n')
        new_lines = [ln + '\n' if not ln.endswith('\n') else ln for ln in new_lines]
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] = new_lines[-1] + '\n'
        lines[entry_start:entry_end] = new_lines
        generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))
        return {'archived': True, 'entry_task': task}


def memory_promote(task, timestamp=None, project_name=None, **kwargs):
    """升格：项目记忆 → 全局（复用 upsert_global_memory，自动执行）。

    本工具是 write_project 的别名，强调"升格"语义。
    实际升格已在 write_project 的双写中自动完成。

    Args:
        task: 任务名
        timestamp: 时间戳片段（用于从项目记忆文件定位具体版本）
        project_name: 项目名
        **kwargs: 透传给 write_project 的参数

    Returns:
        dict: {'promoted': bool, 'reason': str}
    """
    # 从项目记忆文件读取指定版本
    mem_rj_dir = _resolve_memory_rj_dir()
    if not os.path.isdir(mem_rj_dir):
        return {'promoted': False, 'reason': '项目记忆目录不存在: %s' % mem_rj_dir}
    # 查找匹配的文件
    matched_files = []
    for f in os.listdir(mem_rj_dir):
        if f.startswith('%s_memory_' % task):
            if timestamp is None or timestamp in f:
                matched_files.append(f)
    if not matched_files:
        return {'promoted': False, 'reason': '未找到项目记忆文件: task=%s ts=%s' % (task, timestamp)}
    matched_files.sort(reverse=True)
    fpath = os.path.join(mem_rj_dir, matched_files[0])
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        # 复用 write_project 升格到全局
        result = write_project(task, content, project_name=project_name, **kwargs)
        result['promoted'] = result.get('global_ok', False)
        return result
    except OSError as e:
        return {'promoted': False, 'reason': '读取项目记忆失败: %s' % e}


def memory_demote(task, demote_reason, timestamp=None, project_name=None):
    """降级：全局 memory_main.md 条目标记 demoted（不删除，软引用）。

    HARD-GATE 工具：改全局状态。

    Args:
        task: 任务名（必填）
        demote_reason: 降级原因（必填）
        timestamp: 时间戳片段
        project_name: 项目名

    Returns:
        dict: {'demoted': bool, 'entry_task': str, 'reason': str}
    """
    if not demote_reason:
        return {'demoted': False, 'reason': 'demote_reason 不能为空'}
    if project_name is None:
        project_name = os.path.basename(os.getcwd())
    _backup_before_operation("memory_demote")
    with _WRITE_LOCK, _GLOBAL_CP_LOCK:
        if not os.path.isfile(GLOBAL_MEMORY_FILE):
            return {'demoted': False, 'reason': 'memory_main.md 不存在'}
        try:
            with open(GLOBAL_MEMORY_FILE, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            return {'demoted': False, 'reason': 'memory_main.md 读取失败'}
        entry_start, entry_end, block_text = _find_entry_in_segment(lines, project_name, task, timestamp)
        if entry_start is None:
            return {'demoted': False, 'reason': '未找到匹配条目: task=%s ts=%s' % (task, timestamp)}
        new_block = _update_entry_flag(block_text, 'demoted', archive_reason=demote_reason)
        new_lines = new_block.split('\n')
        new_lines = [ln + '\n' if not ln.endswith('\n') else ln for ln in new_lines]
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] = new_lines[-1] + '\n'
        lines[entry_start:entry_end] = new_lines
        generate_docs.atomic_write(GLOBAL_MEMORY_FILE, ''.join(lines))
        return {'demoted': True, 'entry_task': task}


def main():
    """命令行入口：
    - 项目级双写（主次跟进）：python memory_shadow_write.py --project <task> [--content ...]
    - 回滚：python memory_shadow_write.py --rollback <timestamp>
    """
    import argparse
    parser = argparse.ArgumentParser(description='记忆写入器')
    parser.add_argument('--project', default=None,
                        help='项目级记忆模式：指定任务名，双写 docs_rj/memory_rj/ 与全局 memory_main.md')
    parser.add_argument('--content', default=None,
                        help='要写入的内容（省略则从 stdin 读取）')
    parser.add_argument('--rollback', default=None,
                        help='回滚模式：指定 undo 目录的 timestamp（如 20260730_103022）')
    parser.add_argument('--memory-class', default=None,
                        help='主分类（v1.0.4）：tech_solution/pitfall/workflow/tool_usage/decision/status；'
                             '省略时按内容启发式推断；非法值兜底 workflow')
    args = parser.parse_args()

    # 回滚模式
    if args.rollback:
        result = memory_rollback(args.rollback)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('rolled_back') else 1

    # 项目级双写模式
    if not args.project:
        parser.error('必须指定 --project 或 --rollback')
    if args.content is not None:
        content = args.content
    else:
        if sys.stdin.isatty():
            content = ''
        else:
            try:
                sys.stdin.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError, OSError):
                pass
            content = sys.stdin.read()
            if '\ufffd' in content and any(ord(c) > 0x4E00 for c in content[:200]):
                logger.warning('stdin 读入含 U+FFFD 替换符（疑似 GBK→UTF-8 误解码）— 写入可能含乱码，建议 PowerShell 用 `[Console]::InputEncoding=[Text.UTF8Encoding]::UTF8`')

    result = write_project(args.project, content, memory_class=args.memory_class)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('project_ok') else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_tidy.py — 归档整理脚本（GAP2+5+6 修复：归档链路缺失）

功能：
1. scan_completed()：扫描 TASK_STATE 文件，返回候选归档清单
2. archive_completed_task()：将已完成任务的所有文档归档到 archive_rj/
3. scan_convergence()：扫描 task.md 中 Convergence Phase >5 的任务
4. archive_convergence_phases()：将旧 Convergence Phase 抽出归档

运行：
  python scripts/archive_tidy.py --scan                  # 扫描候选归档
  python scripts/archive_tidy.py --archive {task_name}    # 归档指定任务
  python scripts/archive_tidy.py --scan-convergence       # 扫描 Convergence 溢出
  python scripts/archive_tidy.py --convergence {task}     # 归档旧 Convergence Phase
  python scripts/archive_tidy.py --dry-run                # 预演模式（不实际移动/删除）

决策依据：
  - H.1=C：用户显式确认 + B 作为提示条件
  - H.2=D：移动 + 刷新 SUMMARY（原文件删除，归档到 archive_rj）
  - H.3=D：/act 自动 + 手动 CLI 兜底
"""

import os
import sys
import re
import json
import argparse
import logging
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tidy_common  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class ArchiveReport:
    """归档操作结果载体"""

    def __init__(self):
        self.candidates = []       # 候选归档清单
        self.archived = []         # 已归档列表
        self.errors = []           # 错误列表
        self.convergence = []      # Convergence 溢出清单
        self.convergence_archived = []  # 已归档 Convergence

    def to_dict(self):
        return {
            'candidates': self.candidates,
            'archived': self.archived,
            'errors': self.errors,
            'convergence': self.convergence,
            'convergence_archived': self.convergence_archived,
        }


class ArchiveTidy:
    """归档整理管线"""

    def __init__(self, dry_run=False):
        self.dry_run = bool(dry_run)
        self.report = ArchiveReport()

    def scan_completed(self):
        """扫描 TASK_STATE 文件，返回候选归档清单（决策 H.1=C）。

        扫描逻辑：
        1. 读取 docs_rj/memory_rj/TASK_STATE_*.md
        2. 筛选 status=completed 且已有 Sign-off 段的任务
        3. 返回候选清单（供 agent 在 /act 步骤4 前询问用户）

        Returns:
            list: 候选归档任务列表 [{task_name, status, has_signoff, created_at}]
        """
        primary = tidy_common.resolve_primary_docs()
        memory_dir = os.path.join(primary, 'memory_rj') if primary else str(user_data_path.get_memory_rj_path())

        if not os.path.isdir(memory_dir):
            logger.warning("memory_rj 目录不存在: %s", memory_dir)
            return []

        candidates = []
        for f in os.listdir(memory_dir):
            if not f.startswith('TASK_STATE_') or not f.endswith('.md'):
                continue
            path = os.path.join(memory_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except OSError:
                continue

            # 提取 status
            m = re.search(r'^status:\s*(.+)$', content, re.MULTILINE)
            status = m.group(1).strip() if m else 'unknown'

            # 提取 task name
            m = re.search(r'^task:\s*(.+)$', content, re.MULTILINE)
            task_name = m.group(1).strip() if m else f.replace('TASK_STATE_', '').replace('.md', '')

            # 检查是否有 Sign-off
            has_signoff = bool(re.search(r'^## Sign-off\s*$', content, re.MULTILINE))

            # 提取 created_at
            m = re.search(r'^created_at:\s*(.+)$', content, re.MULTILINE)
            created_at = m.group(1).strip() if m else ''

            if status == 'completed' and has_signoff:
                candidates.append({
                    'task_name': task_name,
                    'status': status,
                    'has_signoff': has_signoff,
                    'created_at': created_at,
                    'path': path,
                })

        self.report.candidates = candidates
        logger.info("扫描完成：发现 %d 个候选归档任务", len(candidates))
        return candidates

    def archive_completed_task(self, task_name):
        """归档已完成任务的所有文档到 archive_rj/（决策 H.2=D：移动 + 刷新 SUMMARY）。

        执行流程：
        1. 读取 task.md / spec.md / handoff.md（从 docs_rj/{type}_rj/ 匹配 task_name）
        2. 按 assets/archive_template.md 模板填充归档元数据
        3. 写入 docs_rj/archive_rj/{task}_{type}_{YYYYMMDD_HHMM}_archived.md
        4. 删除原文件 docs_rj/{type}_rj/{task}_{type}_*.md
        5. 刷新 SUMMARY_RJ.md（链接指向 archive_rj）
        6. 更新 TASK_STATE status 为 archived

        风险缓解：归档前要求 git commit（铁律6 回溯保障），误归档可 git revert。

        Args:
            task_name: 任务名

        Returns:
            dict: 归档结果
        """
        primary = tidy_common.resolve_primary_docs()
        if not primary:
            return {'error': '无法解析主 docs 目录', 'task_name': task_name}

        archive_dir = os.path.join(primary, 'archive_rj')
        os.makedirs(archive_dir, exist_ok=True)

        now = datetime.now()
        archived = []
        errors = []

        # 匹配三种文档类型
        doc_types = {
            'spec_rj': 'spec',
            'task_rj': 'task',
            'handoff_rj': 'handoff',
        }

        # 提取任务启动时间戳（从原文件名，取最旧，兜底当前时间）
        # 不依赖 mtime，避免 touch/checkout 漂移（对齐 spec §3.2）
        ts_pattern = re.compile(r'(\d{8}_\d{4})')
        all_ts = []
        for subdir, doc_type in doc_types.items():
            src_dir = os.path.join(primary, subdir)
            if not os.path.isdir(src_dir):
                continue
            for f in os.listdir(src_dir):
                if task_name not in f or not f.endswith('.md'):
                    continue
                m = ts_pattern.search(f)
                if m:
                    all_ts.append(m.group(1))

        if all_ts:
            task_timestamp = min(all_ts)  # 最旧时间戳作为任务启动时间
        else:
            task_timestamp = now.strftime('%Y%m%d_%H%M')

        # 创建任务子文件夹 {task}_{ts}（对齐 spec §3.1 D1 方案）
        task_dir_name = '%s_%s' % (task_name, task_timestamp)
        task_dir = os.path.join(archive_dir, task_dir_name)
        if not self.dry_run:
            os.makedirs(task_dir, exist_ok=True)

        for subdir, doc_type in doc_types.items():
            src_dir = os.path.join(primary, subdir)
            if not os.path.isdir(src_dir):
                continue

            for f in os.listdir(src_dir):
                if task_name not in f or not f.endswith('.md'):
                    continue
                src_path = os.path.join(src_dir, f)

                try:
                    with open(src_path, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                except OSError as exc:
                    errors.append({'path': src_path, 'error': str(exc)})
                    continue

                # 生成归档文档（子文件夹内放 {type}.md，对齐 spec §3.1）
                dst_name = doc_type + '.md'
                dst_path = os.path.join(task_dir, dst_name)

                archive_content = self._build_archive_doc(
                    task_name=task_name,
                    doc_type=doc_type,
                    original_content=content,
                    src_path=src_path,
                    timestamp=now.strftime('%Y-%m-%d %H:%M'),
                )

                if self.dry_run:
                    logger.info("[dry-run] 将归档: %s -> %s", src_path, dst_path)
                    archived.append({
                        'src': src_path,
                        'dst': dst_path,
                        'action': 'would_archive',
                    })
                else:
                    # 写入归档文档
                    with open(dst_path, 'w', encoding='utf-8') as fh:
                        fh.write(archive_content)
                    # 删除原文件
                    os.remove(src_path)
                    logger.info("已归档: %s -> %s", src_path, dst_path)
                    archived.append({
                        'src': src_path,
                        'dst': dst_path,
                        'action': 'archived',
                    })

        # 更新 TASK_STATE status 为 archived
        if not self.dry_run and archived:
            self._update_task_state_to_archived(primary, task_name)

        # 刷新 SUMMARY
        if not self.dry_run:
            try:
                tidy_common.refresh_summary(primary, dry_run=False)
                logger.info("SUMMARY 已刷新")
            except Exception as exc:
                errors.append({'stage': 'refresh_summary', 'error': str(exc)})

        self.report.archived = archived
        self.report.errors = errors
        logger.info("归档完成：%d 个文件，%d 个错误", len(archived), len(errors))
        return {'archived': archived, 'errors': errors, 'dry_run': self.dry_run}

    def _build_archive_doc(self, task_name, doc_type, original_content, src_path, timestamp):
        """按 archive_template.md 格式构建归档文档。

        Args:
            task_name: 任务名
            doc_type: 文档类型（spec/task/handoff）
            original_content: 原始文档内容
            src_path: 原始文件路径
            timestamp: 归档时间戳

        Returns:
            str: 归档文档内容
        """
        # 提取关键结论（取前500字作为摘要）
        summary = original_content[:500].strip()
        if len(original_content) > 500:
            summary += '\n\n（完整内容见下方）'

        lines = [
            '# 归档文档 · %s (%s)' % (task_name, doc_type),
            '',
            '> 版本：v1 | 更新：%s' % timestamp,
            '',
            '## 背景',
            '任务 %s 已完成并通过验收（status=completed + Sign-off），归档至 archive_rj。' % task_name,
            '',
            '## 归档内容',
            '- 来源路径：%s' % src_path,
            '- 归档原因：完成',
            '- 归档时间：%s' % timestamp,
            '',
            '## 摘要',
            summary,
            '',
            '## 原始完整内容',
            '',
            original_content,
            '',
            '---',
            '> 本文档由 pdca-skill archive_tidy.py 自动归档。',
        ]
        return '\n'.join(lines)

    def _update_task_state_to_archived(self, primary, task_name):
        """更新 TASK_STATE.md 的 status 为 archived。

        Args:
            primary: 主 docs 目录
            task_name: 任务名
        """
        memory_dir = os.path.join(primary, 'memory_rj')
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            logger.warning("TASK_STATE 文件不存在，无法更新: %s", path)
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            logger.error("读取 TASK_STATE 失败: %s", exc)
            return

        content = re.sub(r'^status:\s*.+$', 'status: archived', content, flags=re.MULTILINE)
        content = re.sub(r'^## Status\s*\n.+$', '## Status\narchived', content, flags=re.MULTILINE)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info("TASK_STATE status 已更新为 archived: %s", path)

    def scan_convergence(self):
        """扫描 task.md 中 Convergence Phase >5 的任务（决策 H.3=D）。

        扫描逻辑：
        1. 遍历 docs_rj/task_rj/*.md
        2. 统计 ## Convergence Phase 出现次数
        3. 返回 >5 的任务清单

        Returns:
            list: Convergence 溢出清单 [{task_name, phase_count, path}]
        """
        primary = tidy_common.resolve_primary_docs()
        task_dir = os.path.join(primary, 'task_rj') if primary else ''

        if not os.path.isdir(task_dir):
            logger.warning("task_rj 目录不存在: %s", task_dir)
            return []

        overflow = []
        for f in os.listdir(task_dir):
            if not f.endswith('.md'):
                continue
            path = os.path.join(task_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except OSError:
                continue

            # 统计 Convergence Phase 数量
            phases = re.findall(r'^##+\s*Convergence Phase', content, re.MULTILINE)
            count = len(phases)

            if count > 5:
                # 提取任务名
                task_name = f.replace('.md', '')
                overflow.append({
                    'task_name': task_name,
                    'phase_count': count,
                    'path': path,
                })

        self.report.convergence = overflow
        logger.info("Convergence 扫描完成：发现 %d 个溢出任务（>5 Phase）", len(overflow))
        return overflow

    def archive_convergence_phases(self, task_name, keep=5):
        """将旧 Convergence Phase 抽出归档（决策 H.3=D）。

        执行流程：
        1. 读取 task.md
        2. 定位所有 ## Convergence Phase 段
        3. 保留最近 keep 个 Phase，旧 Phase 抽出到 archive_rj/convergence_{task}_{YYYYMMDD_HHMM}_archived.md
        4. 更新 task.md（删除旧 Phase，保留最近 keep 个）

        Args:
            task_name: 任务名（对应 task_rj/{task_name}.md 或含 task_name 的文件）
            keep: 保留最近几个 Phase（默认 5）

        Returns:
            dict: 归档结果
        """
        primary = tidy_common.resolve_primary_docs()
        task_dir = os.path.join(primary, 'task_rj') if primary else ''

        if not os.path.isdir(task_dir):
            return {'error': 'task_rj 目录不存在', 'task_name': task_name}

        # 查找匹配的 task.md
        task_path = None
        for f in os.listdir(task_dir):
            if task_name in f and f.endswith('.md'):
                task_path = os.path.join(task_dir, f)
                break

        if not task_path:
            return {'error': '未找到 task.md', 'task_name': task_name}

        try:
            with open(task_path, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except OSError as exc:
            return {'error': str(exc), 'task_name': task_name}

        # 分割所有 Convergence Phase
        # 使用正则分割：匹配 ## Convergence Phase 或 ### Convergence Phase
        parts = re.split(r'(?=^##+\s*Convergence Phase)', content, flags=re.MULTILINE)

        # 第一部分是 Convergence 之前的内容
        before_convergence = parts[0]
        convergence_blocks = parts[1:] if len(parts) > 1 else []

        if len(convergence_blocks) <= keep:
            logger.info("Convergence Phase 数量 %d <= %d，无需归档", len(convergence_blocks), keep)
            return {'task_name': task_name, 'phase_count': len(convergence_blocks), 'archived': 0}

        # 分离旧 Phase 和保留 Phase
        old_blocks = convergence_blocks[:-keep]
        keep_blocks = convergence_blocks[-keep:]

        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M')

        if self.dry_run:
            logger.info("[dry-run] 将归档 %d 个旧 Convergence Phase（保留 %d 个）", len(old_blocks), keep)
            return {
                'task_name': task_name,
                'phase_count': len(convergence_blocks),
                'to_archive': len(old_blocks),
                'keep': keep,
                'dry_run': True,
            }

        # 写入归档文档
        archive_dir = os.path.join(primary, 'archive_rj')
        os.makedirs(archive_dir, exist_ok=True)
        archive_path = os.path.join(archive_dir, 'convergence_%s_%s_archived.md' % (task_name, timestamp))

        archive_content = '\n'.join([
            '# Convergence Phase 归档 · %s' % task_name,
            '',
            '> 归档时间：%s | 保留最近 %d 个 Phase' % (now.strftime('%Y-%m-%d %H:%M'), keep),
            '',
            '## 已归档的 Convergence Phase（共 %d 个）' % len(old_blocks),
            '',
        ] + old_blocks)

        with open(archive_path, 'w', encoding='utf-8') as fh:
            fh.write(archive_content)

        # 更新 task.md（只保留最近 keep 个 Phase）
        new_content = before_convergence.rstrip('\n') + '\n\n' + '\n'.join(keep_blocks)
        with open(task_path, 'w', encoding='utf-8') as fh:
            fh.write(new_content)

        logger.info("Convergence 归档完成：%d 个旧 Phase -> %s", len(old_blocks), archive_path)
        self.report.convergence_archived.append({
            'task_name': task_name,
            'archived_count': len(old_blocks),
            'archive_path': archive_path,
            'keep': keep,
        })
        return {
            'task_name': task_name,
            'phase_count_original': len(convergence_blocks),
            'archived': len(old_blocks),
            'keep': keep,
            'archive_path': archive_path,
        }


def main():
    parser = argparse.ArgumentParser(description='归档整理脚本（GAP2+5+6 修复）')
    parser.add_argument('--scan', action='store_true', help='扫描候选归档任务')
    parser.add_argument('--archive', default=None, help='归档指定任务')
    parser.add_argument('--scan-convergence', action='store_true', help='扫描 Convergence Phase 溢出')
    parser.add_argument('--convergence', default=None, help='归档指定任务的旧 Convergence Phase')
    parser.add_argument('--keep', type=int, default=5, help='保留最近几个 Convergence Phase（默认 5）')
    parser.add_argument('--dry-run', action='store_true', help='预演模式（不实际移动/删除）')
    args = parser.parse_args()

    tidy = ArchiveTidy(dry_run=args.dry_run)

    if args.scan:
        candidates = tidy.scan_completed()
        print(json.dumps({'candidates': candidates}, ensure_ascii=False, indent=2))
    elif args.archive:
        result = tidy.archive_completed_task(args.archive)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.scan_convergence:
        overflow = tidy.scan_convergence()
        print(json.dumps({'convergence': overflow}, ensure_ascii=False, indent=2))
    elif args.convergence:
        result = tidy.archive_convergence_phases(args.convergence, keep=args.keep)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
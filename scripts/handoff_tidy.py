#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handoff_tidy.py — 交接整理管线（期3新增）

交接时自动整理文档 + 对齐记忆。与 startup_tidy 的差异：
- 共享动作相同（守卫/归档/刷新/漂移）
- 交接专属：五问预跑 + sync-matrix 核对 + 强制 #3→#4 同步 + 外部记忆扫描清理
- 无 PARA 下沉（PARA 是启动专属）

运行：python scripts/handoff_tidy.py --task <任务名> [--dry-run]
"""

import os
import sys
import re
import json
import argparse
import logging
import subprocess
import pathlib
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 让脚本能 import protocol 包（skill 根目录在 scripts/ 的上一级）
# 风格对齐 route_check.py / protocol_align.py / validate_global_files.py
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)
import tidy_common  # noqa: E402
import memory_shadow_write  # noqa: E402
import user_data_path  # noqa: E402  用户数据外置：提供 get_memory_main_path() / get_docs_rj_path()
# 延迟 import + try/except，避免模块故障导致整个 tidy 崩溃
try:
    import git_backup_tidy  # noqa: E402
    _HAVE_GIT_BACKUP = True
    _GIT_BACKUP_IMPORT_ERR = None
except Exception as exc:  # noqa: E722
    _HAVE_GIT_BACKUP = False
    _GIT_BACKUP_IMPORT_ERR = str(exc)

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# 原子写入 + 重试机制，消除 WinError 5 表面告警
def _atomic_write(path, content, max_retries=3, delay=0.5):
    """原子写入文件：先写 .tmp 再 rename，含重试机制。

    解决问题：Windows 上偶发 WinError 5（.tmp 文件被占用导致 rename 失败）。
    重试策略：失败后 sleep delay 秒重试，最多 max_retries 次。

    用法：
        with _atomic_write(path, content) as f:
            pass  # 写入由本函数完成
    或直接调用：
        _atomic_write(path, content)
    """
    import time
    import tempfile

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    last_err = None
    for attempt in range(max_retries):
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(os.path.abspath(path)),
                prefix='.generate_docs_atomic_'
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.replace(tmp_path, path)  # 原子 rename
                return open(path, 'r', encoding='utf-8')  # 返回只读句柄供 with 用
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                logger.warning("写入 %s 失败（尝试 %d/%d：%s），%.1fs 后重试",
                               path, attempt + 1, max_retries, e, delay)
                time.sleep(delay)
            else:
                logger.error("写入 %s 最终失败（%d 次重试后）：%s",
                             path, max_retries, e)
    raise IOError("写入 %s 失败（%d 次重试后）：%s" % (path, max_retries, last_err))


def _extract_frontmatter_summary(filepath):
    """从 Markdown 文件 frontmatter 提取 summary 字段值。

    用于 INDEX.md 概括列数据来源。frontmatter 是文件头部 `---` 包裹的 YAML 块。

    Args:
        filepath: 文件绝对路径

    Returns:
        str: summary 值；无 frontmatter/无 summary/解析失败返回占位符
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.startswith('---'):
            return '（无 frontmatter）'
        parts = content.split('---', 2)
        if len(parts) < 3:
            return '（解析失败）'
        fm_block = parts[1]
        for line in fm_block.splitlines():
            line = line.strip()
            if line.startswith('summary:'):
                value = line[len('summary:'):].strip()
                # 去除引号包裹
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # 转义管道符（markdown 表格分隔符）
                value = value.replace('|', '\\|')
                return value if value else '（无概括）'
        return '（无概括）'
    except Exception:
        return '（解析失败）'


class HandoffReport:
    """交接整理结果载体"""
    def __init__(self):
        self.primary_docs = None
        self.missing_dirs = []
        self.scattered = {}
        self.archived = []
        self.skipped = []
        self.errors = []
        self.summary = None
        self.drift = 0
        self.drift_missing = []
        self.memory_cleanup = None
        self.sync_result = None
        self.five_questions = None
        self.handoff_memory = None
        self.loop_guard_finalize = None
        self.task_state = None
        self.sync_matrix_check = None
        self.git_health = None                   # git仓库体检（git_backup_cleanup新增）
        self.temp_cleanup = None                  # 临时文件清理结果
        self.signoff = None                       # --mark-completed Sign-off 结果
        self.summary_recency_annotation = None    # SUMMARY 时效标注（最新/历史）
        self.category_indexes = None              # 每类目 INDEX.md 刷新结果
        self.dependency_map = None                # DEPENDENCY_MAP.md 刷新结果（REQ-002/003）
        self.adr_pending_agent = False            # §7.1 ADR 候选待 agent 确认标志（REQ-009）
        self.spec_main_refresh = None             # spec_main 刷新结果（显式声明，避免动态属性）

    def to_dict(self):
        return {
            'primary_docs': self.primary_docs,
            'missing_dirs': self.missing_dirs,
            'scattered': self.scattered,
            'archived': self.archived,
            'skipped': self.skipped,
            'errors': self.errors,
            'summary': self.summary,
            'drift': self.drift,
            'drift_missing': self.drift_missing,
            'memory_cleanup': self.memory_cleanup,
            'sync_result': self.sync_result,
            'five_questions': self.five_questions,
            'handoff_memory': self.handoff_memory,
            'loop_guard_finalize': self.loop_guard_finalize,
            'task_state': self.task_state,
            'sync_matrix_check': self.sync_matrix_check,
            'git_health': self.git_health,
            'temp_cleanup': self.temp_cleanup,
            'signoff': self.signoff,
            'summary_recency_annotation': self.summary_recency_annotation,
            'category_indexes': self.category_indexes,
            'adr_pending_agent': self.adr_pending_agent,
            'spec_main_refresh': self.spec_main_refresh,
        }


class HandoffTidy:
    """交接整理管线"""

    CLEANUP_PATTERNS = [
        '**/__pycache__/',
        '**/*.pyc',
        '**/.pytest_cache/',
        '**/_tmp_*',
        '**/_temp_*',
        '**/_verify_*',
    ]

    def __init__(self, dry_run=False, task_name=None, project_name=None, task_status=None):
        self.dry_run = bool(dry_run)
        self.task_name = task_name  # 让 None 透传，refresh_spec_main 收到 None 时只刷 §1（REQ-009）
        self.task_status = task_status  # §2 状态列数据源（REQ-009 对抗审查P0修复）
        self.project_name = project_name or os.path.basename(os.getcwd())
        self.report = HandoffReport()
        # handoff_gate_fix：4 闸门判定缺项清单（_check_task_completion 写入，_write_signoff 读取）
        self._last_blocked_gates = []

    def run(self):
        """执行完整交接管线"""
        logger.info("=== 交接整理管线（handoff_tidy）===")
        # === 共享动作 ===
        self.report.missing_dirs = tidy_common.ensure_project_structure()
        primary = tidy_common.resolve_primary_docs()
        self.report.primary_docs = primary
        if primary and os.path.isdir(primary):
            archive_result = tidy_common.scan_and_archive_scattered(primary, dry_run=self.dry_run)
            self.report.scattered = archive_result['scattered']
            self.report.archived = archive_result['archived']
            self.report.skipped = archive_result['skipped']
            self.report.errors.extend(archive_result['errors'])
            self.report.summary = tidy_common.refresh_summary(primary, dry_run=self.dry_run)
            self.report.drift = self.report.summary.get('drift', 0)
            self.report.drift_missing = self.report.summary.get('missing', [])
            # 刷新 spec_main_rj.md §1§2§7 指针（REQ-007 + REQ-009）
            try:
                self.report.spec_main_refresh = tidy_common.refresh_spec_main(
                    primary,
                    task_name=self.task_name,
                    task_status=getattr(self, 'task_status', None),
                    dry_run=self.dry_run
                )
                # adr_pending_agent 判定：有候选则置 True，提醒 agent 在 /act 步骤3.5a 确认
                if self.report.spec_main_refresh and self.report.spec_main_refresh.get('adr_candidates'):
                    self.report.adr_pending_agent = True
            except Exception as exc:
                logger.error("spec_main 刷新失败: %s", exc)
                self.report.errors.append({'stage': 'spec_main_refresh', 'error': str(exc)})

        # 1.5 临时文件清理（Python缓存+临时脚本，dry_run预览+用户确认）
        try:
            self.report.temp_cleanup = self._cleanup_temp_files()
        except Exception as exc:
            logger.error("临时文件清理失败: %s", exc)
            self.report.errors.append({'stage': 'temp_cleanup', 'error': str(exc)})

        # === 交接专属动作 ===
        # 1. 平台记忆融入技能记忆（原"外部记忆扫描清理"）
        #    扫描 .trae-cn/memory/ 等平台记忆 → 去重融入 memory_main.md "## 外部记忆归档"段 → 删除原平台记忆
        #    对应 SKILL.md Memory First 第5条硬规则：技能记忆优先于平台记忆，融入后删除原件
        try:
            self.report.memory_cleanup = tidy_common.cleanup_legacy_memory(dry_run=self.dry_run)
        except Exception as exc:
            logger.error("平台记忆融入技能记忆失败: %s", exc)
            self.report.errors.append({'stage': 'memory_cleanup', 'error': str(exc)})

        # 2. 强制 #3→#4 同步
        try:
            self.report.sync_result = tidy_common.force_sync_project_to_global()
        except Exception as exc:
            logger.error("强制同步失败: %s", exc)
            self.report.errors.append({'stage': 'force_sync', 'error': str(exc)})

        # 3. 五问预跑
        try:
            self.report.five_questions = self._run_five_questions(primary)
        except Exception as exc:
            logger.error("五问预跑失败: %s", exc)
            self.report.errors.append({'stage': 'five_questions', 'error': str(exc)})

        # 4. 写交接 memory
        if not self.dry_run:
            try:
                self.report.handoff_memory = self._write_handoff_memory()
            except Exception as exc:
                logger.error("写交接memory失败: %s", exc)
                self.report.errors.append({'stage': 'handoff_memory', 'error': str(exc)})

        # 4.5 loop_guard 归档当前任务 ledger
        try:
            self.report.loop_guard_finalize = self._run_loop_guard_finalize()
        except Exception as exc:
            logger.error("loop_guard finalize 失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'loop_guard_finalize', 'error': str(exc)})

        # 4.6 生成 TASK_STATE.md
        if not self.dry_run:
            try:
                self.report.task_state = self._write_task_state()
            except Exception as exc:
                logger.error("生成 TASK_STATE.md 失败: %s", exc)
                self.report.errors.append({'stage': 'task_state', 'error': str(exc)})

        # 4.7 SUMMARY 时效标注 + 每类目 INDEX.md 刷新
        #    解决"docs_rj/ 每个类目文件越积越多，不知道哪个最新"痛点
        #    顺序：先生成 INDEX.md，再跑 SUMMARY 标注+入口插入
        #    原因：_annotate_summary_recency 内部调 _ensure_index_entries_in_summary
        #    检查 INDEX.md 存在性，必须先有 INDEX.md 才能插入入口块
        #    - _refresh_category_indexes: 每类目建 INDEX.md，含状态列（active/superseded/archived）
        #    - _annotate_summary_recency: SUMMARY_RJ.md 每个文件链接后加 `最新·{ts}` / `历史·{ts}` 标注 + INDEX 入口块
        try:
            self.report.category_indexes = self._refresh_category_indexes(primary)
        except Exception as exc:
            logger.error("类目 INDEX 刷新失败: %s", exc)
            self.report.errors.append({'stage': 'category_indexes', 'error': str(exc)})
        # 刷新 DEPENDENCY_MAP.md（新增功能，REQ-002/003）
        try:
            self.report.dependency_map = self._refresh_dependency_map(primary)
        except Exception as exc:
            logger.error("DEPENDENCY_MAP 刷新失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'dependency_map', 'error': str(exc)})
            self.report.dependency_map = {'path': None, 'refreshed': False, 'families': 0}
        try:
            self.report.summary_recency_annotation = self._annotate_summary_recency(primary)
        except Exception as exc:
            logger.error("SUMMARY 时效标注失败: %s", exc)
            self.report.errors.append({'stage': 'summary_recency_annotation', 'error': str(exc)})

        # 5. sync-matrix 核对
        try:
            self.report.sync_matrix_check = self._run_sync_matrix_check(primary)
        except Exception as exc:
            logger.error("sync-matrix核对失败: %s", exc)
            self.report.errors.append({'stage': 'sync_matrix_check', 'error': str(exc)})

        # 6. git 仓库体检（git_backup_cleanup新增，纯只读，失败仅告警不阻断 B5）
        # 判断 _HAVE_GIT_BACKUP，模块缺失时仅告警不崩溃
        if not _HAVE_GIT_BACKUP:
            logger.warning("git_backup_tidy 模块不可用（%s），跳过 git 体检", _GIT_BACKUP_IMPORT_ERR)
            self.report.git_health = {'available': False, 'error': _GIT_BACKUP_IMPORT_ERR}
            self.report.errors.append({'stage': 'git_health', 'error': 'module_unavailable: %s' % _GIT_BACKUP_IMPORT_ERR})
        else:
            try:
                self.report.git_health = git_backup_tidy.analyze_repo(os.getcwd())
            except Exception as exc:
                logger.error("git 仓库体检失败（仅告警）: %s", exc)
                self.report.errors.append({'stage': 'git_health', 'error': str(exc)})

        # === 方案 3-R 阶段4：自动触发 distill（try/except 隔离，失败不阻断交接）===
        # S1 修复：dry_run 模式跳过 distill（避免预演时真写文件）
        if self.dry_run:
            logger.info("[dry-run] 跳过 distill")
            self.report.distill_result = {'skipped': True, 'reason': 'dry_run'}
        else:
            try:
                import memory_distill
                distill_result = memory_distill.distill(
                    project_name=self.task_name or '',
                    memory_file=str(user_data_path.get_memory_main_path()),
                    output_dir=str(user_data_path.get_docs_rj_path() / 'learn_rj')
                )
                self.report.distill_result = distill_result
                if distill_result.get('error'):
                    logger.warning("[handoff_tidy] distill 完成（有警告）: %s", distill_result['error'])
                else:
                    logger.info("[handoff_tidy] distill 完成: %d 条经验",
                                distill_result.get('total_lessons', 0))
            except Exception as exc:
                # 区分错误类型（对抗性审查 D3）
                if isinstance(exc, ImportError):
                    logger.error("[handoff_tidy] distill 模块缺失（环境配置问题）: %s", exc)
                elif isinstance(exc, (PermissionError, OSError)):
                    logger.error("[handoff_tidy] distill 系统级故障（需人工介入）: %s", exc)
                else:
                    logger.warning("[handoff_tidy] distill 自动触发失败（交接不受影响）: %s", exc)
                self.report.distill_result = {'error': str(exc), 'error_type': type(exc).__name__}

        logger.info("=== 交接整理完成 ===")
        return self.report

    def _run_five_questions(self, primary):
        """五问预跑：读 memory/spec/task，回答5个问题。

        task_name=None 时（--task 未传，向后兼容）返回默认占位答案，
        避免 `None in string` 报错（AC-015 修复）。
        """
        if not self.task_name:
            return {
                'current_location': {'task': None, 'phase': '未传 --task，跳过五问预跑'},
                'next_step': {'next': '未传 --task，跳过', 'blocked': []},
                'final_goal': '未传 --task，跳过',
                'lessons': '未传 --task，跳过',
                'completed': [],
            }
        answers = {
            'current_location': self._read_current_location(primary),
            'next_step': self._read_next_step(primary),
            'final_goal': self._read_final_goal(primary),
            'lessons': self._read_lessons(),
            'completed': self._read_completed(primary),
        }
        return answers

    def _read_current_location(self, primary):
        """Q1: 我在哪？"""
        task_files = self._find_task_files(primary, 'task_rj')
        for tf in task_files:
            if self.task_name in os.path.basename(tf):
                content = self._read_file(tf)
                phase_match = re.search(r'当前阶段[：:]\s*(.+)', content)
                if phase_match:
                    return {'task': self.task_name, 'phase': phase_match.group(1).strip()}
        return {'task': self.task_name, 'phase': '未找到'}

    def _read_next_step(self, primary):
        """Q2: 接下来去哪？"""
        task_files = self._find_task_files(primary, 'task_rj')
        for tf in task_files:
            if self.task_name in os.path.basename(tf):
                content = self._read_file(tf)
                unchecked = re.findall(r'- \[ \] (.+)', content)
                if unchecked:
                    return {'next': unchecked[0], 'blocked': []}
        return {'next': '未找到', 'blocked': []}

    def _read_final_goal(self, primary):
        """Q3: 最终目标是什么？"""
        spec_files = self._find_task_files(primary, 'spec_rj')
        for sf in spec_files:
            if self.task_name in os.path.basename(sf):
                content = self._read_file(sf)
                goal_match = re.search(r'最终目标[：:]\s*(.+)', content)
                if goal_match:
                    return goal_match.group(1).strip()
        return '未找到'

    def _read_lessons(self):
        """Q4: 学到了什么？

        按 task_name 过滤记忆条目，避免串档（H2 修复）。

        修复前 bug：取项目分段内最新一条记忆条目（decisions[-1]），
        不区分 task_name，导致 test 任务读到 excel_skill_intranet_verify 的记忆。
        修复后：只取标题含 task_name 的记忆条目，取最新一条。
        """
        global_memory = str(user_data_path.get_memory_main_path())
        if not os.path.isfile(global_memory):
            return '未找到全局memory'
        content = self._read_file(global_memory)
        heading = '## %s' % self.project_name
        idx = content.find(heading)
        if idx == -1:
            return '未找到项目分段'
        end_idx = content.find('\n## ', idx + len(heading))
        section = content[idx:end_idx] if end_idx != -1 else content[idx:]
        # H2 修复：按 task_name 过滤记忆条目，避免串档
        # 根因：旧正则 ### 记忆条目[··](.+?) 期望"记忆条目"后紧跟中点（无空格），
        #       但实际格式是 ### 记忆条目 · task_name（空格+中点U+00B7+空格），
        #       导致正则永远匹配失败，走 return section[:500] 返回项目分段前500字符（串档）。
        # 修复：正则改为匹配"记忆条目"后任意空白+中点+任意空白，并按 task_name 过滤。
        decisions = re.findall(r'### 记忆条目\s*·\s*(.+?)(?=###|$)', section, re.DOTALL)
        if decisions:
            if self.task_name:
                # 过滤：只保留标题含 task_name 的记忆条目
                task_decisions = [d for d in decisions if self.task_name in d[:200]]
                if task_decisions:
                    return task_decisions[-1].strip()[:500]
                # task_name 无匹配，返回空（不串档其他任务的记忆）
                return '未找到任务 %s 的记忆条目' % self.task_name
            return decisions[-1].strip()[:500]
        return section[:500]

    def _read_completed(self, primary):
        """Q5: 做了什么？"""
        task_files = self._find_task_files(primary, 'task_rj')
        for tf in task_files:
            if self.task_name in os.path.basename(tf):
                content = self._read_file(tf)
                checked = re.findall(r'- \[[xX]\] (.+)', content)
                return checked
        return []

    def _find_task_files(self, primary, subdir):
        """查找指定子目录下的文件"""
        if not primary:
            return []
        dir_path = os.path.join(primary, subdir)
        if not os.path.isdir(dir_path):
            return []
        return [os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith('.md')]

    def _read_file(self, path):
        """读取文件内容"""
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except OSError:
            return ''

    def _write_handoff_memory(self):
        """写交接 memory。

        task_name=None 时（--task 未传，向后兼容）跳过，
        避免 None + '_handoff' 报错（AC-015 同类修复）。
        """
        if not self.task_name:
            return {'skipped': True, 'reason': 'task_name is None（--task 未传，向后兼容）'}
        content = "交接时点：%s，任务=%s\n" % (datetime.now().strftime('%Y-%m-%d %H:%M'), self.task_name)
        return memory_shadow_write.write_project(self.task_name + '_handoff', content)

    def _run_loop_guard_finalize(self):
        """调用 loop_guard.py --finalize 归档当前任务 ledger。

        task_name=None 时（--task 未传，向后兼容）跳过 finalize，
        避免 subprocess 传 None 报错（AC-015 修复）。
        """
        if not self.task_name:
            return {'skipped': True, 'reason': 'task_name is None（--task 未传，向后兼容）'}
        guard_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'loop_guard.py')
        cmd = [sys.executable, guard_script, 'finalize', '--task-id', self.task_name]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {'raw_stdout': proc.stdout, 'stderr': proc.stderr}
        data['exit_code'] = proc.returncode
        return data

    def _read_existing_status(self, memory_dir, task_name):
        """读取现有 TASK_STATE 的 status 字段（M3 修复：避免每次 handoff_tidy 重置为 pending）。

        status 与 loop_status 语义分工：
        - status：任务级状态（pending/completed/failed/paused），由 handoff_tidy 设置
          paused 值由 /do 阶段"执行中插入新任务处置"规则写入（SKILL.md §6 /do 第10项），
          handoff_tidy 必须保留不覆盖，否则原任务挂起状态丢失。
        - loop_status：循环级状态（active/paused/completed/escalated），由 /loop 设置

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名

        Returns:
            str: status 值（如 'pending'/'completed'/'paused'），文件不存在或字段缺失时返回 None。
        """
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            # YAML frontmatter 格式：status: value
            m = re.search(r'^status:\s*(.+)$', content, re.MULTILINE)
            if m:
                return m.group(1).strip()
            # Markdown 格式：## Status\nvalue
            m = re.search(r'^## Status\s*\n(.+)$', content, re.MULTILINE)
            if m:
                return m.group(1).strip()
        except OSError:
            pass
        return None

    def _read_existing_loop_state(self, memory_dir, task_name):
        """读取现有 TASK_STATE 的 loop 字段（续传保留，修 LC-01）。

        为什么需要这个方法：_write_task_state 默认用全覆盖模式生成 TASK_STATE，
        会把 /loop 退出后写入的 loop_status=paused 等续传状态覆盖为 none。
        本方法在覆盖前先读取现有值，供 _write_task_state 回写。

        格式兼容（M3 修复）：
        - 格式 A（列表项）：`- loop_mode: value`
        - 格式 B（YAML frontmatter）：`loop_mode: value`
        - 格式 C（key-value）：`loop_mode = value`
        任一格式命中即停止，提高容错性。

        status 与 loop_status 语义分工（M3 修复）：
        - status：任务级状态（pending/completed/failed），由 handoff_tidy 设置
        - loop_status：循环级状态（active/paused/completed/escalated），由 /loop 设置
        两者独立维护，不互相覆盖。

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名

        Returns:
            dict: loop 字段（loop_mode/loop_iteration/loop_status），
                  文件不存在或字段缺失时返回默认值。
        """
        default = {
            'loop_mode': 'none',
            'loop_iteration': 0,
            'loop_status': 'none',
        }
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            for key in default:
                # 格式 A：列表项 "- loop_mode: value"
                m = re.search(r'^- %s:\s*(.+)$' % key, content, re.MULTILINE)
                if m:
                    val = m.group(1).strip()
                    if key == 'loop_iteration':
                        try:
                            default[key] = int(val)
                        except ValueError:
                            pass
                    else:
                        default[key] = val
                    continue
                # 格式 B：YAML frontmatter "loop_mode: value"
                m = re.search(r'^%s:\s*(.+)$' % key, content, re.MULTILINE)
                if m:
                    val = m.group(1).strip()
                    if key == 'loop_iteration':
                        try:
                            default[key] = int(val)
                        except ValueError:
                            pass
                    else:
                        default[key] = val
                    continue
                # 格式 C：key-value "loop_mode = value"
                m = re.search(r'^%s\s*=\s*(.+)$' % key, content, re.MULTILINE)
                if m:
                    val = m.group(1).strip()
                    if key == 'loop_iteration':
                        try:
                            default[key] = int(val)
                        except ValueError:
                            pass
                    else:
                        default[key] = val
        except OSError:
            pass  # 读取失败保持默认值
        return default

    def _read_existing_paused_reason(self, memory_dir, task_name):
        """读取现有 TASK_STATE 的 paused_reason 字段（续传保留，SKILL.md §6 /do 第10项配套）。

        为什么需要这个方法：_write_task_state 默认用全覆盖模式生成 TASK_STATE，
        会把 /do 阶段"执行中插入新任务处置"规则写入的 paused_reason 字段擦除。
        本方法在覆盖前先读取现有值，供 _write_task_state 回写。

        paused_reason 字段位置：
        - frontmatter：paused_reason: value（与 status 同级，机器读取）
        - body：## Paused Reason 段下的文本（人读叙事）

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名

        Returns:
            str: paused_reason 值，文件不存在或字段缺失时返回 None。
        """
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 格式 A：YAML frontmatter "paused_reason: value"
            m = re.search(r'^paused_reason:\s*(.+)$', content, re.MULTILINE)
            if m:
                return m.group(1).strip()
            # 格式 B：## Paused Reason 段下第一行非空文本
            m = re.search(r'^## Paused Reason\s*\n(.+?)(?=\n## |\Z)', content, re.MULTILINE | re.DOTALL)
            if m:
                return m.group(1).strip()
        except OSError:
            pass
        return None

    def _read_existing_verification(self, memory_dir, task_name):
        """读取现有 TASK_STATE 的 Verification 段（续传保留，GAP3 修复）。

        Verification 段格式（决策 G.1=C 混合粒度）：
        ```
        ## Verification
        - total: N
        - passed: N
        - failed: N
        - blocked: N

        ### 逐条结果
        - AC-001: pass | 证据: path#Lline
        ```

        为什么需要这个方法：_write_task_state 生成 TASK_STATE 时，若已有
        verification 结果（来自 /check 步骤5 批量写入），应保留不覆盖。
        本方法在覆盖前先读取现有值，供 _write_task_state 回写。

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名

        Returns:
            dict: verification 字段（aggregate 聚合 + items 逐条列表），
                  文件不存在或未找到 Verification 段时返回 None。
        """
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return None

        # 定位 Verification 段
        m = re.search(r'^## Verification\s*\n(.*?)(?=\n## |\Z)', content, re.MULTILINE | re.DOTALL)
        if not m:
            return None

        section = m.group(1)

        # 解析聚合字段
        total = re.search(r'- total:\s*(\d+)', section)
        passed = re.search(r'- passed:\s*(\d+)', section)
        failed = re.search(r'- failed:\s*(\d+)', section)
        blocked = re.search(r'- blocked:\s*(\d+)', section)

        aggregate = {
            'total': int(total.group(1)) if total else 0,
            'passed': int(passed.group(1)) if passed else 0,
            'failed': int(failed.group(1)) if failed else 0,
            'blocked': int(blocked.group(1)) if blocked else 0,
        }

        # 解析逐条结果
        items = []
        item_matches = re.findall(r'- (AC-\d+):\s*(pass|fail|blocked)\s*\|\s*证据:\s*(.+)', section)
        for ac_id, result, evidence in item_matches:
            items.append({'ac_id': ac_id, 'result': result, 'evidence': evidence.strip()})

        return {'aggregate': aggregate, 'items': items}

    def _verify_gate_evidence_file(self, path):
        """校验审查报告证据文件（handoff_gate_fix 新增）。

        证据有效条件：文件存在 + 内容含 '0 HIGH' 字样（正则 0\\s*HIGH）。
        纯 touch 空文件会被拒，防止"无实际审查的假证据"。

        Args:
            path: 报告文件路径（允许带 #L 行号后缀，校验前剥离）

        Returns:
            tuple[bool, str]: (是否有效, 原因说明)
        """
        if not path:
            return (False, '证据路径为空')
        clean = re.sub(r'#L?\d+$', '', path.strip())
        if not os.path.isfile(clean):
            return (False, '证据文件不存在: %s' % clean)
        try:
            with open(clean, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            return (False, '证据文件读取失败: %s' % exc)
        if re.search(r'0\s*HIGH', content):
            return (True, '证据有效: %s' % clean)
        return (False, '证据文件内容不含 0 HIGH: %s' % clean)

    def _read_gate_evidence(self, memory_dir, task_name):
        """读取 TASK_STATE 的 '## Gate Evidence' 段（handoff_gate_fix 新增）。

        段格式（写入方：/check 步骤 6.5，见 SKILL.md）：
        ```
        ## Gate Evidence
        - gate1_spec_verification: pass (10/10)
        - gate2_adversarial: pass (0 HIGH) | 证据: docs_rj/check_rj/{task}_adversarial_20260806_1200.md#L12
        - gate3_consistency: pass (0 HIGH) | 证据: docs_rj/check_rj/{task}_consistency_20260806_1200.md#L8
        - gate4_user_confirm: confirm | 时间戳: 2026-08-06 12:00 | 用户原话: "可以，通过了"
        ```

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名

        Returns:
            dict 或 None：
            - gate1_status / gate1_ratio
            - gate2_status / gate2_evidence（证据文件路径，剥离 #L 行号）
            - gate3_status / gate3_evidence
            - gate4_status（confirm / loop_auto / 其他）
            - raw：Gate Evidence 段原始文本（供 _write_task_state 回读保留）
            段缺失或无法定位 → None
        """
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return None

        m = re.search(r'^## Gate Evidence\s*\n(.*?)(?=\n## |\Z)', content, re.MULTILINE | re.DOTALL)
        if not m:
            return None
        section = m.group(1)

        result = {'raw': section.rstrip('\n')}

        g1 = re.search(r'gate1_spec_verification:\s*(pass|fail)\s*\((\d+)/(\d+)\)', section)
        if g1:
            result['gate1_status'] = g1.group(1)
            result['gate1_ratio'] = (int(g1.group(2)), int(g1.group(3)))
        else:
            result['gate1_status'] = 'missing'

        for key, short in (('gate2_adversarial', 'gate2'), ('gate3_consistency', 'gate3')):
            m2 = re.search(r'%s:\s*(pass|fail)[^\n]*?\|\s*证据:\s*([^\s|]+)' % key, section)
            if m2:
                result[short + '_status'] = m2.group(1)
                result[short + '_evidence'] = re.sub(r'#L?\d+$', '', m2.group(2).strip())
            else:
                result[short + '_status'] = 'missing'

        m4 = re.search(r'gate4_user_confirm:\s*(\S+)', section)
        result['gate4_status'] = m4.group(1).strip() if m4 else 'missing'

        return result

    def _check_task_completion(self, memory_dir, task_name, level):
        """判定任务是否可进入 ready_to_close 状态（GAP4 修复 + handoff_gate_fix 4 闸门证据驱动）。

        判定逻辑（决策 I.3=D + 本任务决策 D-001 证据驱动）：
        - 4 闸门全过 → 返回 ready_to_close
          - 闸门1：/check 步骤5 spec AC 全 pass（verification aggregate passed==total）
          - 闸门2：Gate Evidence 段 gate2_adversarial=pass 且报告文件含 0 HIGH
          - 闸门3：Gate Evidence 段 gate3_consistency=pass 且报告文件含 0 HIGH
          - 闸门4：Gate Evidence 段 gate4_user_confirm=confirm 或 loop_auto
        - 任一闸门不过 → 返回 pending，缺项清单写入 self._last_blocked_gates
        - task.md 全打勾不再单独判定（以 4 闸门证据为准）

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名
            level: 任务等级（L1/L2）

        Returns:
            str: 'ready_to_close' 或 'pending'；blocked_gates 明细经 self._last_blocked_gates 暴露
        """
        self._last_blocked_gates = []
        existing_status = self._read_existing_status(memory_dir, task_name)
        # 已完成/已归档/已挂起不再降级
        # paused 保留：挂起状态不可被 _check_task_completion 降级为 pending
        if existing_status in ('completed', 'archived', 'ready_to_close', 'paused'):
            return existing_status

        blocked = []

        # 闸门1：spec AC 全 pass（verification 聚合）
        verification = self._read_existing_verification(memory_dir, task_name)
        if not verification:
            blocked.append('gate1_spec_verification（Verification 段缺失）')
        else:
            agg = verification.get('aggregate', {})
            total = agg.get('total', 0)
            passed = agg.get('passed', 0)
            if total > 0 and passed == total:
                pass
            else:
                blocked.append('gate1_spec_verification（verification %d/%d）' % (passed, total))

        # 闸门2/3/4：Gate Evidence 段
        evidence = self._read_gate_evidence(memory_dir, task_name)
        if not evidence:
            blocked.append('gate2_adversarial（Gate Evidence 段缺失）')
            blocked.append('gate3_consistency（Gate Evidence 段缺失）')
            blocked.append('gate4_user_confirm（Gate Evidence 段缺失）')
        else:
            # 闸门2：对抗审查报告
            if evidence.get('gate2_status') == 'pass' and evidence.get('gate2_evidence'):
                ok, reason = self._verify_gate_evidence_file(evidence['gate2_evidence'])
                if not ok:
                    blocked.append('gate2_adversarial（%s）' % reason)
            else:
                blocked.append('gate2_adversarial（gate2 行缺失或非 pass）')
            # 闸门3：跨产物一致性报告
            if evidence.get('gate3_status') == 'pass' and evidence.get('gate3_evidence'):
                ok, reason = self._verify_gate_evidence_file(evidence['gate3_evidence'])
                if not ok:
                    blocked.append('gate3_consistency（%s）' % reason)
            else:
                blocked.append('gate3_consistency（gate3 行缺失或非 pass）')
            # 闸门4：人类确认或无人值守标记
            if evidence.get('gate4_status') not in ('confirm', 'loop_auto'):
                blocked.append('gate4_user_confirm（gate4 行缺失或非 confirm/loop_auto）')

        self._last_blocked_gates = blocked
        if not blocked:
            return 'ready_to_close'
        return 'pending'

    def _write_signoff(self, memory_dir, task_name, level, force=False):
        """追加 Sign-off 段到 TASK_STATE.md（决策 I.2=D：--mark-completed 触发）。

        handoff_gate_fix：新增 4 闸门证据校验。
        - 证据不全且非 force → 拒签：返回 {'signoff_blocked': True, 'blocked_gates': [...], 'verification': agg}
        - force=True → 豁免全部闸门校验（含 H3），Sign-off 声明段追加
          '- 强制完成: forced: true（用户明确要求）' 作为审计标记

        Sign-off 段格式：
        ```
        ## Sign-off
        - 声明时间: YYYY-MM-DD HH:MM
        - Agent 版本: {agent_version}
        - 4 闸门状态:
          - 闸门1 (spec AC): pass (N/N)
          - 闸门2 (对抗审查): pass (0 HIGH)
          - 闸门3 (跨产物): pass (0 HIGH)
          - 闸门4 (人类决策): pass (用户 YYYY-MM-DD HH:MM 确认)
        - Verification 聚合: total=N, passed=N, failed=0, blocked=0
        - 声明: spec 验收通过，任务进入 completed 状态
        ```

        Args:
            memory_dir: memory_rj 目录路径
            task_name: 任务名
            level: 任务等级
            force: 是否强制完成（跳过 4 闸门证据校验，审计标记 forced: true）

        Returns:
            dict: sign-off 信息
        """
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % task_name)
        if not os.path.isfile(path):
            logger.warning("TASK_STATE 文件不存在，无法写 Sign-off: %s", path)
            return {'error': 'TASK_STATE not found', 'path': path}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            logger.error("读取 TASK_STATE 失败: %s", exc)
            return {'error': str(exc), 'path': path}

        # 检查是否已有 Sign-off（避免重复追加）
        if re.search(r'^## Sign-off\s*$', content, re.MULTILINE):
            logger.info("Sign-off 已存在，跳过")
            return {'skipped': True, 'reason': 'Sign-off already exists', 'path': path}

        # 读取 verification 聚合数据
        verification = self._read_existing_verification(memory_dir, task_name)
        agg = verification['aggregate'] if verification else {'total': 0, 'passed': 0, 'failed': 0, 'blocked': 0}

        # H3 防御：Verification total=0 时禁止生成 Sign-off（违反铁律7"看到预期结果才能打勾"）
        # 原逻辑：无论 Verification 是否有实际验证结果，都允许写 Sign-off
        # 新逻辑：total=0 说明未实际跑验证，拒绝写 Sign-off，避免"0/0 但 completed"的虚假完成
        # force=True 时豁免（用户明确要求强制完成）
        if agg.get('total', 0) == 0 and not force:
            logger.warning("Verification total=0，拒绝写入 Sign-off（违反铁律7 Verification-before-Completion）")
            return {
                'error': 'Verification total=0, cannot mark completed (rule: Verification-before-Completion)',
                'path': path,
                'verification': agg,
            }

        # handoff_gate_fix：4 闸门证据校验（挡"假完成"：未验收任务被标 completed）
        # 复用 _check_task_completion 判定；缺项明细经 self._last_blocked_gates 暴露
        if not force:
            current_status = self._check_task_completion(memory_dir, task_name, level)
            if current_status != 'ready_to_close':
                logger.warning("4 闸门证据不全，拒签 Sign-off: %s", self._last_blocked_gates)
                return {
                    'signoff_blocked': True,
                    'blocked_gates': self._last_blocked_gates,
                    'verification': agg,
                    'path': path,
                }

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        signoff_lines = [
            '',
            '## Sign-off',
            '',
            '- 声明时间: %s' % now,
            '- Task Level: %s' % level,
            '- 4 闸门状态:',
            '  - 闸门1 (spec AC): pass (%d/%d)' % (agg.get('passed', 0), agg.get('total', 0)),
            '  - 闸门2 (对抗审查): pass (0 HIGH)',
            '  - 闸门3 (跨产物): pass (0 HIGH)',
            '  - 闸门4 (人类决策): pass (用户确认)',
            '- Verification 聚合: total=%d, passed=%d, failed=%d, blocked=%d' % (
                agg.get('total', 0), agg.get('passed', 0),
                agg.get('failed', 0), agg.get('blocked', 0)),
            '- 声明: spec 验收通过，任务进入 completed 状态',
        ]
        if force:
            signoff_lines.append('- 强制完成: forced: true（用户明确要求，绕过 4 闸门证据校验）')

        # 更新 status 为 completed
        content = re.sub(r'^status:\s*.+$', 'status: completed', content, flags=re.MULTILINE)
        content = re.sub(r'^## Status\s*\n.+$', '## Status\ncompleted', content, flags=re.MULTILINE)

        # 追加 Sign-off 段
        content = content.rstrip('\n') + '\n' + '\n'.join(signoff_lines) + '\n'

        with _atomic_write(path, content) as f:
            pass  # 写入由 _atomic_write 完成

        logger.info("Sign-off 已写入: %s", path)
        return {'written': True, 'path': path, 'timestamp': now}

    def _write_task_state(self):
        """生成 TASK_STATE.md，供下一轮 /plan 读取"""
        primary = self.report.primary_docs or tidy_common.resolve_primary_docs()
        memory_dir = os.path.join(primary, 'memory_rj') if primary else str(user_data_path.get_memory_rj_path())
        os.makedirs(memory_dir, exist_ok=True)

        def _to_str(value):
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False, indent=2)
            return str(value) if value is not None else '未记录'

        location = _to_str(self.report.five_questions.get('location', '未记录'))
        next_step = _to_str(self.report.five_questions.get('next_step', '未记录'))
        goal = _to_str(self.report.five_questions.get('final_goal', '未记录'))
        lessons = _to_str(self.report.five_questions.get('lessons', '未记录'))
        completed = _to_str(self.report.five_questions.get('completed', '未记录'))

        # 默认 L2；如检测到为纯分析任务可后续调整
        level = 'L2'
        if self.task_name and ('report-only' in self.task_name.lower() or '分析' in self.task_name):
            level = 'L1'

        # 读取现有 status（续传保留，M3 修复：避免每次 handoff_tidy 重置为 pending）
        existing_status = self._read_existing_status(memory_dir, self.task_name)
        # 若已有 completed/archived/ready_to_close/paused 则保留；否则走状态机判定
        # paused 保留：/do 阶段"执行中插入新任务处置"规则写入的挂起状态不可被覆盖
        if existing_status in ('completed', 'archived'):
            task_status = existing_status
        elif existing_status == 'ready_to_close':
            task_status = existing_status
        elif existing_status == 'paused':
            task_status = existing_status
        else:
            # 走 ready_to_close 状态机（GAP4 修复）
            task_status = self._check_task_completion(memory_dir, self.task_name, level)

        # 读取现有 paused_reason（续传保留，SKILL.md §6 /do 第10项配套）
        # 为什么：全覆盖生成会丢失 /do 阶段"执行中插入新任务处置"写入的挂起原因
        existing_paused_reason = self._read_existing_paused_reason(memory_dir, self.task_name)
        # 一致性保障（H1 修复）：status≠paused 时强制清空 paused_reason
        # 为什么：agent 改 status=pending（恢复原任务）但忘删 paused_reason 时，
        # 避免 status=pending + paused_reason 共存的矛盾状态；不依赖 agent 手工删除
        if task_status != 'paused':
            existing_paused_reason = None

        # 构建 frontmatter（有 paused_reason 时加入，避免空字段）
        frontmatter = [
            '---',
            'task: %s' % self.task_name,
            'level: %s' % level,
            'status: %s' % task_status,
            'created_at: %s' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        ]
        if existing_paused_reason:
            frontmatter.append('paused_reason: %s' % existing_paused_reason)
        frontmatter.append('---')

        lines = frontmatter + [
            '',
            '# TASK_STATE: %s' % self.task_name,
            '',
            '## Goal',
            goal,
            '',
            '## Level',
            level,
            '',
            '## Status',
            task_status,
        ]
        # 有 paused_reason 时在 Status 段后插入 Paused Reason 段（人读叙事）
        if existing_paused_reason:
            lines.extend([
                '',
                '## Paused Reason',
                existing_paused_reason,
            ])
        lines.extend([
            '',
            '## High Priority（遗留/下一步）',
            next_step,
            '',
            '## Watch List',
            '- loop_guard 阈值监控：stagnation=3, no_progress=5, max_iterations=10',
            '',
            '## Lessons Learned',
            lessons,
            '',
            '## Completed',
            completed,
            '',
            '## Current Location',
            location,
        ])

        # 读取现有 verification 字段（续传保留，GAP3 修复）
        # 为什么：/check 步骤5 批量写入的 verification 结果应保留，不被 handoff_tidy 覆盖
        existing_verification = self._read_existing_verification(memory_dir, self.task_name)
        if existing_verification:
            agg = existing_verification['aggregate']
            items = existing_verification['items']
            lines.extend([
                '',
                '## Verification',
                '- total: %d' % agg.get('total', 0),
                '- passed: %d' % agg.get('passed', 0),
                '- failed: %d' % agg.get('failed', 0),
                '- blocked: %d' % agg.get('blocked', 0),
            ])
            if items:
                lines.append('')
                lines.append('### 逐条结果')
                for item in items:
                    lines.append('- %s: %s | 证据: %s' % (item['ac_id'], item['result'], item['evidence']))
        else:
            lines.extend([
                '',
                '## Verification',
                '- total: 0',
                '- passed: 0',
                '- failed: 0',
                '- blocked: 0',
                '',
                '### 逐条结果',
                '（/check 步骤5 完成后由 agent 批量写入）',
            ])

        # handoff_gate_fix：回读保留 Gate Evidence 段（防全覆盖生成丢失 4 闸门证据）
        # 为什么：/check 步骤6.5 写入的 Gate Evidence 段是 4 闸门判定的唯一证据，
        # 若被全覆盖生成覆盖，已过闸门会因证据丢失回落 pending
        existing_evidence = self._read_gate_evidence(memory_dir, self.task_name)
        if existing_evidence and existing_evidence.get('raw'):
            lines.extend([
                '',
                '## Gate Evidence',
                existing_evidence['raw'],
            ])

        # 读取现有 loop 字段（续传保留，修 LC-01）
        # 为什么：全覆盖生成会丢失 /loop 退出后的 loop_status=paused 等续传状态
        existing_loop = self._read_existing_loop_state(memory_dir, self.task_name)
        lines.extend([
            '',
            '## Loop 状态（/loop 指令用）',
            '- loop_mode: %s' % existing_loop['loop_mode'],
            '- loop_iteration: %s' % existing_loop['loop_iteration'],
            '- loop_status: %s' % existing_loop['loop_status'],
        ])
        path = os.path.join(memory_dir, 'TASK_STATE_%s.md' % self.task_name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return {'path': path, 'level': level, 'status': task_status}

    def _cleanup_temp_files(self):
        """扫描并清理临时文件/缓存（dry_run模式只预览不删）"""
        root = pathlib.Path(os.getcwd())
        found = []
        for pattern in self.CLEANUP_PATTERNS:
            for p in root.glob(pattern):
                if p.is_dir():
                    file_count = sum(1 for _ in p.rglob('*') if _.is_file())
                    found.append({'path': str(p), 'type': 'dir', 'files_inside': file_count})
                else:
                    found.append({'path': str(p), 'type': 'file', 'size': p.stat().st_size})

        if not found:
            logger.info("没有发现需要清理的临时文件/缓存")
            return {'found': [], 'deleted': [], 'dry_run': self.dry_run}

        logger.info("=== 临时文件清理预览 ===")
        for item in found:
            if item['type'] == 'dir':
                logger.info("  [目录] %s（内含 %d 个文件）", item['path'], item['files_inside'])
            else:
                size_kb = item['size'] / 1024
                logger.info("  [文件] %s（%.1f KB）", item['path'], size_kb)
        logger.info("共 %d 个文件/目录待清理", len(found))

        if self.dry_run:
            logger.info("[dry-run] 以上为预览，未实际删除")
            return {'found': found, 'deleted': [], 'dry_run': True}

        if sys.stdin.isatty():
            answer = input("\n确认删除以上文件？[y/N] ").strip().lower()
        else:
            logger.info("[非交互环境] 跳过临时文件清理确认，直接清理")
            answer = 'y'
        if answer != 'y':
            logger.info("用户取消删除")
            return {'found': found, 'deleted': [], 'dry_run': False, 'cancelled': True}

        deleted = []
        errors = []
        for item in found:
            p = pathlib.Path(item['path'])
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                deleted.append(item['path'])
                logger.info("  已删除: %s", item['path'])
            except OSError as e:
                errors.append({'path': item['path'], 'error': str(e)})
                logger.error("  删除失败: %s - %s", item['path'], e)

        logger.info("清理完成：删除 %d/%d 项", len(deleted), len(found))
        return {'found': found, 'deleted': deleted, 'errors': errors, 'dry_run': False}

    def _annotate_summary_recency(self, primary):
        """在 SUMMARY_RJ.md 每个文件链接后追加 `最新·{ts}` / `历史·{ts}` 标注。

        规则：
        - 全文扫描 markdown 链接 `](path)`
        - 对每个链接，提取文件名 → 调 _classify_file_status 判定状态
        - active + 有时间戳 → `最新·YYYY-MM-DD HH:MM`
        - active + 无时间戳 → `最新·无时间戳`
        - superseded + 有时间戳 → `历史·YYYY-MM-DD HH:MM`
        - superseded + 无时间戳 → `历史·无时间戳`
        - 同行已有 `最新·` / `历史·` 标注 → 先剥离再重写（防重复）
        - 不修改外部链接（http/https/mailto）

        Args:
            primary: 主 docs 目录

        Returns:
            dict: {'annotated': int, 'skipped_external': int, 'no_status': int, 'path': str}
        """
        if not primary:
            return {'annotated': 0, 'skipped_external': 0, 'no_status': 0, 'path': None}
        summary_path = os.path.join(primary, 'SUMMARY_RJ.md')
        if not os.path.isfile(summary_path):
            return {'annotated': 0, 'skipped_external': 0, 'no_status': 0, 'path': None}

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            logger.error("读 SUMMARY 失败: %s", exc)
            return {'annotated': 0, 'skipped_external': 0, 'no_status': 0,
                    'path': summary_path, 'error': str(exc)}

        # 收集所有 .md 文件名 → 调用共享层 _classify_file_status
        all_files = set()
        for sub in ('memory_rj', 'spec_rj', 'task_rj', 'handoff_rj', 'archive_rj'):
            sub_dir = os.path.join(primary, sub)
            if not os.path.isdir(sub_dir):
                continue
            for fname in os.listdir(sub_dir):
                if fname.endswith('.md'):
                    all_files.add(fname)
        status_map = tidy_common._classify_file_status(list(all_files))

        # 链接正则：匹配 `](path)` 后面可选紧跟 ` `最新·...` ` 标注（先剥离再重写，防重复）
        link_re = re.compile(r'(\[[^\]]*\]\([^)]+\))(\s*`[最新历史]+·[^`]*`)?')

        annotated = 0
        skipped_external = 0
        no_status = 0

        def replace_link(m):
            nonlocal annotated, skipped_external, no_status
            link_part = m.group(1)
            link_match = re.search(r'\]\(([^)]+)\)', link_part)
            if not link_match:
                return link_part
            path = link_match.group(1)
            # 跳过外部链接
            if path.startswith(('http://', 'https://', 'mailto:', '#')):
                skipped_external += 1
                return link_part
            fname = os.path.basename(path)
            if not fname.endswith('.md'):
                return link_part
            info = status_map.get(fname)
            if not info:
                # 文件不在类目（可能是其他子目录的链接），不标注
                no_status += 1
                return link_part
            status = info['status']
            ts = info['timestamp']
            ts_str = ts.strftime('%Y-%m-%d %H:%M') if ts else '无时间戳'
            label = '最新·%s' % ts_str if status == 'active' else '历史·%s' % ts_str
            annotated += 1
            return '%s `%s`' % (link_part, label)

        new_content = link_re.sub(replace_link, content)

        if self.dry_run:
            logger.info("[dry-run] SUMMARY 时效标注预览：将标注 %d 个链接", annotated)
            return {'annotated': annotated, 'skipped_external': skipped_external,
                    'no_status': no_status, 'path': summary_path, 'dry_run': True}

        if new_content != content:
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except OSError as exc:
                logger.error("写 SUMMARY 失败: %s", exc)
                return {'annotated': 0, 'skipped_external': skipped_external,
                        'no_status': no_status, 'path': summary_path, 'error': str(exc)}

        # 在时效标注后，追加 INDEX 入口块（方案 A：SUMMARY → INDEX 单向导航）
        index_entries_result = self._ensure_index_entries_in_summary(summary_path, primary)

        return {'annotated': annotated, 'skipped_external': skipped_external,
                'no_status': no_status, 'path': summary_path,
                'index_entries': index_entries_result}

    def _ensure_index_entries_in_summary(self, summary_path, primary):
        """在 SUMMARY 的"项目级文档"段后插入 INDEX.md 入口块（方案 A：单向导航）。

        规则：
        - 找 `## ` 开头且含 "项目级文档" 或 "docs_rj" 的段标题
        - 在段标题后第一行插入入口块（若已有则更新，幂等）
        - 入口块用 HTML 注释标记包裹：<!-- INDEX_ENTRIES_START --> ... <!-- INDEX_ENTRIES_END -->
        - 只在对应 INDEX.md 存在时才加入口行
        - dry_run 模式不写文件，仅打印预览

        Args:
            summary_path: SUMMARY_RJ.md 绝对路径
            primary: 主 docs 目录

        Returns:
            dict: {'inserted': int, 'updated': bool, 'entries': list[str], 'dry_run': bool}
        """
        if not summary_path or not os.path.isfile(summary_path):
            return {'inserted': 0, 'updated': False, 'entries': [], 'dry_run': self.dry_run}

        # 检查 5 类目 INDEX.md 是否存在（含 archive_rj）
        available_indexes = []
        for subdir in ('memory_rj', 'spec_rj', 'task_rj', 'handoff_rj', 'archive_rj'):
            index_path = os.path.join(primary, subdir, 'INDEX.md')
            if os.path.isfile(index_path):
                available_indexes.append(subdir)

        if not available_indexes:
            return {'inserted': 0, 'updated': False, 'entries': [],
                    'dry_run': self.dry_run, 'reason': 'no INDEX.md available'}

        # 构造入口块内容
        entry_lines = ['<!-- INDEX_ENTRIES_START -->']
        entry_lines.append('> 📂 **类目全量索引**（含时效状态 active/superseded/archived）：')
        for subdir in available_indexes:
            entry_lines.append('- [%s/INDEX.md](%s/INDEX.md) — %s 全量文件 + 状态标注'
                               % (subdir, subdir, subdir))
        entry_lines.append('<!-- INDEX_ENTRIES_END -->')
        entry_block = '\n'.join(entry_lines) + '\n'

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            logger.error("读 SUMMARY 失败（_ensure_index_entries）: %s", exc)
            return {'inserted': 0, 'updated': False, 'entries': [],
                    'dry_run': self.dry_run, 'error': str(exc)}

        # 先尝试替换已有入口块（幂等更新）
        pattern = re.compile(
            r'<!-- INDEX_ENTRIES_START -->.*?<!-- INDEX_ENTRIES_END -->\n?',
            re.DOTALL
        )
        existing_match = pattern.search(content)
        if existing_match:
            new_content = pattern.sub(entry_block, content)
            updated = True
            inserted = 0
        else:
            # 未找到已有块，找"项目级文档"段标题后插入
            section_re = re.compile(r'^(## .*?(?:项目级文档|docs_rj).*?)$', re.MULTILINE)
            match = section_re.search(content)
            if not match:
                # 兜底：找任意 ## 开头的段
                section_re = re.compile(r'^(## [^\n]+)$', re.MULTILINE)
                matches = list(section_re.finditer(content))
                if not matches:
                    return {'inserted': 0, 'updated': False, 'entries': available_indexes,
                            'dry_run': self.dry_run, 'reason': 'no ## section found'}
                # 插在第一个 ## 段标题后
                match = matches[0]
            insert_pos = match.end()
            # 段标题后可能有空行，保留空行后插入
            new_content = content[:insert_pos] + '\n' + entry_block + content[insert_pos:]
            updated = False
            inserted = len(available_indexes)

        if self.dry_run:
            logger.info("[dry-run] SUMMARY INDEX 入口块：%s %d 个入口",
                        "更新" if updated else "插入", len(available_indexes))
            return {'inserted': inserted, 'updated': updated,
                    'entries': available_indexes, 'dry_run': True}

        if new_content != content:
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except OSError as exc:
                logger.error("写 SUMMARY 入口块失败: %s", exc)
                return {'inserted': 0, 'updated': False, 'entries': available_indexes,
                        'dry_run': self.dry_run, 'error': str(exc)}

        logger.info("SUMMARY INDEX 入口块：%s %d 个入口",
                    "更新" if updated else "插入", len(available_indexes))
        return {'inserted': inserted, 'updated': updated,
                'entries': available_indexes, 'dry_run': False}

    def _refresh_category_indexes(self, primary):
        """每个类目目录生成 INDEX.md，含状态列（active/superseded）。

        Args:
            primary: 主 docs 目录

        Returns:
            dict: {'indexes': [{category, path, files_count, active_count, superseded_count}],
                   'dry_run': bool}
        """
        if not primary:
            return {'indexes': [], 'dry_run': self.dry_run}

        # 类目列表（含 archive_rj，归档文件用 archived 状态）
        categories = [
            ('memory_rj', 'Memory 文档', False),
            ('spec_rj', 'Spec 文档', False),
            ('task_rj', 'Task 文档', False),
            ('handoff_rj', 'Handoff 文档', False),
            ('archive_rj', 'Archive 归档', True),  # is_archive=True
        ]
        results = []
        for subdir, _label, is_archive in categories:
            sub_dir = os.path.join(primary, subdir)
            if not os.path.isdir(sub_dir):
                continue

            # 扫描：archive_rj 区分子文件夹（新结构）和扁平文件（legacy）
            if is_archive:
                all_entries = os.listdir(sub_dir)
                # 子文件夹（新结构：{task}_{ts}/）
                subfolders = [d for d in all_entries
                              if os.path.isdir(os.path.join(sub_dir, d))]
                # 扁平文件（legacy：{task}_{type}_{ts}_archived.md）
                files = [f for f in all_entries
                         if f.endswith('.md') and f != 'INDEX.md']
                # 子文件夹单独构建 entries
                folder_entries = []
                for d in subfolders:
                    m = re.search(r'(\d{8}_\d{4})', d)
                    ts = None
                    if m:
                        try:
                            ts = datetime.strptime(m.group(1), '%Y%m%d_%H%M')
                        except ValueError:
                            pass
                    folder_entries.append({
                        'name': d,
                        'timestamp': ts,
                        'status': 'archived',
                    })
            else:
                files = [f for f in os.listdir(sub_dir)
                         if f.endswith('.md') and f != 'INDEX.md']
                folder_entries = []

            if not files and not folder_entries:
                continue
            status_map = tidy_common._classify_file_status(files)

            if is_archive:
                # archive_rj：扁平文件标 legacy，子文件夹标 archived
                for fname in files:
                    status_map[fname]['status'] = 'legacy'
                # 排序：子文件夹（archived）在前，扁平文件（legacy）在后
                sorted_folders = sorted(
                    folder_entries,
                    key=lambda e: e['timestamp'] or datetime.min,
                    reverse=True
                )
                sorted_files = sorted(
                    files,
                    key=lambda f: status_map[f]['timestamp'] or datetime.min,
                    reverse=True
                )
                active_count = 0
                superseded_count = 0
                archived_count = len(sorted_folders)
                legacy_count = len(sorted_files)
            else:
                # 排序：active 在前，superseded 在后；同状态内按时间戳降序
                active_files = [f for f in files if status_map[f]['status'] == 'active']
                superseded_files = [f for f in files if status_map[f]['status'] == 'superseded']
                active_files.sort(
                    key=lambda f: status_map[f]['timestamp'] or datetime.min,
                    reverse=True
                )
                superseded_files.sort(
                    key=lambda f: status_map[f]['timestamp'] or datetime.min,
                    reverse=True
                )
                sorted_files = active_files + superseded_files
                active_count = len(active_files)
                superseded_count = len(superseded_files)
                archived_count = 0
                legacy_count = 0
            now = datetime.now().strftime('%Y-%m-%d %H:%M')

            lines = []
            lines.append('# %s/ 类目索引\n' % subdir)
            lines.append('> 自动生成，请勿手工编辑。由 handoff_tidy.py /act 时刷新。')
            lines.append('> 最后刷新：%s\n' % now)
            if is_archive:
                # archive_rj 表格加"类型"列（对齐 spec §3.4）
                lines.append('| 状态 | 类型 | 名称 | 任务前缀 | 最后更新 |')
                lines.append('|------|------|------|----------|----------|')
                for entry in sorted_folders:
                    tp = entry['name'].rsplit('_', 1)[0] if '_' in entry['name'] else entry['name']
                    ts = entry['timestamp']
                    ts_str = ts.strftime('%Y-%m-%d %H:%M') if ts else '无时间戳'
                    link = '[%s/](./%s/%s/)' % (entry['name'], subdir, entry['name'])
                    lines.append('| %s | %s | %s | %s | %s |' % ('⚪ archived', 'folder', link, tp, ts_str))
                for fname in sorted_files:
                    info = status_map[fname]
                    tp = info.get('task_prefix') or '-'
                    ts = info.get('timestamp')
                    ts_str = ts.strftime('%Y-%m-%d %H:%M') if ts else '无时间戳'
                    link = '[%s](./%s/%s)' % (fname, subdir, fname)
                    lines.append('| %s | %s | %s | %s | %s |' % ('🟠 legacy', 'file', link, tp, ts_str))
                lines.append('')
                lines.append('## 状态说明')
                lines.append('- ⚪ archived: 已归档任务子文件夹（新结构，{task}_{ts}/）')
                lines.append('- 🟠 legacy: 旧结构扁平归档文件（保留原位，不迁移）')
            else:
                lines.append('| 状态 | 文件 | 概括 | 任务前缀 | 最后更新 |')
                lines.append('|------|------|------|----------|----------|')
                for fname in sorted_files:
                    info = status_map[fname]
                    status = info['status']
                    if status == 'active':
                        status_icon = '🟢 active'
                    elif status == 'superseded':
                        status_icon = '🟡 superseded'
                    else:  # archived
                        status_icon = '⚪ archived'
                    tp = info.get('task_prefix') or '-'
                    ts = info.get('timestamp')
                    ts_str = ts.strftime('%Y-%m-%d %H:%M') if ts else '无时间戳'
                    link = '[%s](./%s/%s)' % (fname, subdir, fname)
                    # 提取 frontmatter summary 作为概括列（REQ-001）
                    full_path = os.path.join(sub_dir, fname)
                    summary = _extract_frontmatter_summary(full_path)
                    lines.append('| %s | %s | %s | %s | %s |' % (status_icon, link, summary, tp, ts_str))
                lines.append('')
                lines.append('## 状态说明')
                lines.append('- 🟢 active: 当前最新版本，应优先查看')
                lines.append('- 🟡 superseded: 同任务有更新版本或任务已结束，仅供参考')
                lines.append('- ⚪ archived: 已归档（仅 archive_rj/ 列此状态）')

            content = '\n'.join(lines) + '\n'
            index_path = os.path.join(sub_dir, 'INDEX.md')

            if self.dry_run:
                if is_archive:
                    logger.info("[dry-run] 将创建/更新 INDEX.md: %s/INDEX.md（%d folder archived, %d legacy）",
                                subdir, archived_count, legacy_count)
                else:
                    logger.info("[dry-run] 将创建/更新 INDEX.md: %s/INDEX.md（%d 文件，%d active / %d superseded）",
                                subdir, len(files), active_count, superseded_count)
            else:
                try:
                    with open(index_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                except OSError as exc:
                    logger.error("写 INDEX.md 失败 %s: %s", index_path, exc)
                    results.append({'category': subdir, 'path': index_path, 'error': str(exc)})
                    continue

            results.append({
                'category': subdir,
                'path': index_path,
                'files_count': len(files) + len(folder_entries) if is_archive else len(files),
                'active_count': active_count,
                'superseded_count': superseded_count,
                'archived_count': archived_count,
                'legacy_count': legacy_count if is_archive else 0,
            })

        return {'indexes': results, 'dry_run': self.dry_run}

    def _refresh_dependency_map(self, primary):
        """生成 docs_rj/DEPENDENCY_MAP.md 文件级依赖关系图。

        数据源：protocol/change_impact_map.py 的 CHANGE_IMPACT_MAP 字典（含 docs_rj family）。
        输出：正向依赖表（改 X → 影响 Y）+ 反向依赖表（Y ← 被 X 影响）+ family 清单。
        双端刷新：handoff_tidy.py /act 时调用 + startup_tidy.py 启动时调用。

        Args:
            primary: 主 docs 目录路径（如 'docs_rj'）

        Returns:
            dict: {'path': str, 'refreshed': bool, 'families': int}
        """
        if not primary:
            return {'path': None, 'refreshed': False, 'families': 0}

        try:
            from protocol.change_impact_map import CHANGE_IMPACT_MAP
        except Exception as exc:
            logger.error("加载 change_impact_map 失败: %s", exc)
            dep_path = os.path.join(primary, 'DEPENDENCY_MAP.md')
            try:
                with open(dep_path, 'w', encoding='utf-8') as f:
                    f.write('# docs_rj/ 文件依赖关系图\n\n')
                    f.write('> ⚠️ 依赖图数据源加载失败，请检查 protocol/change_impact_map.py\n')
                return {'path': dep_path, 'refreshed': True, 'families': 0}
            except Exception as write_exc:
                logger.error("写入 DEPENDENCY_MAP.md 失败: %s", write_exc)
                return {'path': dep_path, 'refreshed': False, 'families': 0}

        import glob
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        cwd = os.getcwd()
        lines = []
        lines.append('# docs_rj/ 文件依赖关系图\n')
        lines.append('> 自动生成，请勿手工编辑。由 handoff_tidy.py /act 时刷新 + startup_tidy.py 启动时刷新。')
        lines.append('> 最后刷新：%s\n' % now)
        lines.append('## 正向依赖（改 X → 影响 Y）\n')
        lines.append('| 触发文件 | 受影响文件 |')
        lines.append('|----------|-----------|')

        # 筛选 docs_rj 相关 family（含 docs 根 family）
        docs_families = {k: v for k, v in CHANGE_IMPACT_MAP.items()
                         if k.startswith('docs_rj') or k == 'docs'}
        family_count = 0
        for family_name, rule in sorted(docs_families.items()):
            for trigger in rule['trigger_files']:
                if '*' in trigger:
                    matched = glob.glob(os.path.join(cwd, trigger))
                    # Windows 路径分隔符修正为正斜杠（markdown 兼容）
                    matched = [os.path.relpath(m, cwd).replace('\\', '/') for m in matched]
                else:
                    matched = [trigger]
                for m in matched:
                    if not os.path.exists(os.path.join(cwd, m)):
                        lines.append('| %s ⚠️文件缺失 | - |' % m)
                        continue
                    impacted = ', '.join(rule['impacted_files'])
                    lines.append('| %s | %s |' % (m, impacted))
                    family_count += 1

        lines.append('')
        lines.append('## 反向依赖（Y ← 被 X 影响）\n')
        lines.append('| 文件 | 被哪些文件变更触发 |')
        lines.append('|------|-------------------|')

        reverse_map = {}
        for family_name, rule in sorted(docs_families.items()):
            for trigger in rule['trigger_files']:
                if '*' in trigger:
                    matched = glob.glob(os.path.join(cwd, trigger))
                    matched = [os.path.relpath(m, cwd).replace('\\', '/') for m in matched]
                else:
                    matched = [trigger]
                for m in matched:
                    for imp in rule['impacted_files']:
                        reverse_map.setdefault(imp, []).append(m)

        for target, triggers in sorted(reverse_map.items()):
            lines.append('| %s | %s |' % (target, ', '.join(triggers)))

        lines.append('')
        lines.append('## family 清单\n')
        lines.append('| family | trigger 模式 | 受影响文件数 |')
        lines.append('|--------|-------------|-------------|')
        for family_name, rule in sorted(docs_families.items()):
            lines.append('| %s | %s | %d |' % (family_name, ', '.join(rule['trigger_files']), len(rule['impacted_files'])))

        content = '\n'.join(lines) + '\n'
        dep_path = os.path.join(primary, 'DEPENDENCY_MAP.md')

        if self.dry_run:
            logger.info("[dry-run] 将创建/更新 DEPENDENCY_MAP.md: %s（%d 条依赖）", dep_path, family_count)
        else:
            try:
                with open(dep_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info("已刷新 DEPENDENCY_MAP.md: %s（%d 条依赖）", dep_path, family_count)
            except Exception as exc:
                logger.error("写入 DEPENDENCY_MAP.md 失败: %s", exc)
                return {'path': dep_path, 'refreshed': False, 'families': 0}

        return {'path': dep_path, 'refreshed': True, 'families': family_count}

    def _run_sync_matrix_check(self, primary):
        """sync-matrix 核对：检查关键文件是否存在"""
        checks = {'passed': [], 'failed': []}
        # 检查 handoff 文件存在
        handoff_dir = os.path.join(primary, 'handoff_rj') if primary else ''
        if handoff_dir and os.path.isdir(handoff_dir):
            checks['passed'].append('handoff_rj 目录存在')
        else:
            checks['failed'].append('handoff_rj 目录缺失')
        # 检查 memory_main.md 存在
        global_memory = str(user_data_path.get_memory_main_path())
        if os.path.isfile(global_memory):
            checks['passed'].append('memory_main.md 存在')
        else:
            checks['failed'].append('memory_main.md 缺失')
        return checks


def main():
    parser = argparse.ArgumentParser(description='交接整理管线（期3新增）')
    parser.add_argument('--task', required=False, default=None, help='交接的任务名（不传则只刷 §1，向后兼容）')
    parser.add_argument('--dry-run', action='store_true', help='预演模式')
    parser.add_argument('--project', default=None, help='项目名（默认取当前目录基名）')
    parser.add_argument('--mark-completed', action='store_true',
                        help='标记任务为 completed 并追加 Sign-off 段（决策 I.2=D）')
    parser.add_argument('--force', action='store_true',
                        help='强制完成：跳过 4 闸门证据校验（含 H3），Sign-off 标 forced: true（handoff_gate_fix 新增）')
    args = parser.parse_args()

    tidy = HandoffTidy(dry_run=args.dry_run, task_name=args.task, project_name=args.project)
    report = tidy.run()

    # --mark-completed：追加 Sign-off 段 + 更新 status 为 completed（决策 I.2=D）
    if args.mark_completed and not args.dry_run:
        primary = report.primary_docs or tidy_common.resolve_primary_docs()
        memory_dir = os.path.join(primary, 'memory_rj') if primary else os.path.join(str(user_data_path.get_docs_rj_path()), 'memory_rj')
        level = 'L2'
        if 'report-only' in args.task.lower() or '分析' in args.task:
            level = 'L1'
        signoff_result = tidy._write_signoff(memory_dir, args.task, level, force=args.force)
        report.signoff = signoff_result

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
startup_tidy.py — pdca-skill 启动整理管线

每次对话启动前自动整理文档（参考 PARA / Obsidian startup hook 等开源做法）：
  1. 确保项目结构完整（Bootstrap 守卫·报告型）——检测 docs_rj 5类（含 memory_rj）+ outputs_rj/ + .agent/ 是否齐备，缺失仅报告、绝不静默建
  2. 解析主 docs 目录（.primary_docs_rj 标记 > MEMORY_RJ.md 约定 > 优先级路由，R3）
  3. 扫描散落文档（scan_scattered_docs）
  4. 归档散落文档（archive_scattered_docs）
  5. 刷新 SUMMARY_RJ.md（SummaryRefresher.refresh，复用 summary_view.md §三/§五）
  6. 漂移检查（drift_check，复用 summary_view.md §五；已纳入 run() 末尾，R4）
  7. PARA 下沉（_para_sink，R6，默认阈值 30 天，可跳过，T05）

技术约束
--------
* 仅 Python 标准库（os / sys / re / json / argparse / logging / shutil / datetime）。
* 复用 generate_docs.py 的函数（import 直接调用，不 subprocess、不复制逻辑）。
* 零新增第三方依赖。
* 归档类错误不阻断启动，仅告警（B5）。
* JSON 输出到 stdout；日志到 stderr，互不影响。

运行
----
  python scripts/startup_tidy.py [--dry-run] [--primary-docs PATH] [--para-threshold N] [--skip-para]
"""

import os
import sys
import re
import json
import argparse
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# 复用 generate_docs 的函数（同目录，import 直接调用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_docs  # noqa: E402
import tidy_common  # noqa: E402  期3新增：共享函数库
import user_data_path  # noqa: E402
import migrate_user_data  # noqa: E402
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


# ===========================================================================
# 漂移检查（复用 summary_view.md §五）
# ===========================================================================
def drift_check(summary_path):
    """漂移检查（复用 summary_view.md §五）。

    提取 SUMMARY 内全部 markdown 链接 `[text](path)`，解析相对路径（相对主 docs），
    逐个确认文件存在；返回 ``(missing_count, missing_list)``。文件不存在 → 记为漂移。

    支持说明：markdown 链接可能跨行，此处按行内 ``](path)`` 提取；跨行链接在
    summary_view.md §五 已要求维护时强制写成单行，故单行匹配足够。
    """
    if not summary_path or not os.path.isfile(summary_path):
        return (0, [])
    try:
        with open(summary_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("读取 SUMMARY 失败: %s", exc)
        return (0, [])

    base_dir = os.path.dirname(os.path.abspath(summary_path))
    link_re = re.compile(r'\]\(([^)]+)\)')
    missing = []
    seen = set()
    for match in link_re.finditer(content):
        target = match.group(1).strip()
        if not target:
            continue
        # 跳过外部链接（非文件漂移）
        if target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        if target in seen:
            continue
        seen.add(target)
        if os.path.isabs(target):
            abs_target = target
        else:
            abs_target = os.path.normpath(os.path.join(base_dir, target))
        if not os.path.isfile(abs_target):
            missing.append(target)
    return (len(missing), missing)


# ===========================================================================
# SUMMARY_RJ.md 刷新器（复用 summary_view.md §三 / §五）
# ===========================================================================
class SummaryRefresher:
    """SUMMARY_RJ.md 刷新器。

    复用 summary_view.md §三（三触发）与 §五（漂移检查）。
    刷新策略：SUMMARY 存在时才刷新（不静默创建）；刷新 = 更新 last_updated 时间戳
    + 跑漂移检查。完整重生成需模板/交互，不在启动管线内做（避免覆盖独有内容，遵循 A3）。
    """

    def __init__(self, primary_docs):
        """初始化刷新器。

        Args:
            primary_docs: 主 docs 目录绝对路径（SUMMARY_RJ.md 位于其下）。
        """
        self.primary_docs = primary_docs

    def _find_summary(self):
        """定位主 docs 下的 SUMMARY_RJ.md；不存在返回 None。"""
        if not self.primary_docs:
            return None
        candidate = os.path.join(self.primary_docs, 'SUMMARY_RJ.md')
        return candidate if os.path.isfile(candidate) else None

    def refresh(self):
        """刷新 SUMMARY 并返回结果字典。

        Returns:
            dict: {summary_path, refreshed, drift, missing, reconciled}
        """
        summary_path = self._find_summary()
        if not summary_path:
            logger.info("SUMMARY_RJ.md 不存在，跳过刷新（按三触发：存在时才刷新）")
            return {'summary_path': None, 'refreshed': False, 'drift': 0, 'missing': [], 'reconciled': 0}

        # 更新 last_updated 时间戳（仅 frontmatter，不重写正文，避免覆盖独有内容，A3）
        self._touch_last_updated(summary_path)

        # 增量补全文档链接（修复 SUMMARY 刷新 bug）
        # 扫描 docs_rj/ 5 子目录，把缺失的 .md 文件链接追加到对应段末尾
        reconciled_count = self._reconcile_doc_links(summary_path)

        # 漂移检查（§五）
        drift_count, missing = drift_check(summary_path)
        if drift_count:
            logger.warning("漂移检查：发现 %d 个失效链接：%s", drift_count, missing)
        else:
            logger.info("漂移检查通过：无失效链接")

        return {
            'summary_path': summary_path,
            'refreshed': True,
            'drift': drift_count,
            'missing': missing,
            'reconciled': reconciled_count,
        }

    def _reconcile_doc_links(self, summary_path):
        """增量补全文档链接（修复 SUMMARY 刷新 bug）。

        委托给 tidy_common.reconcile_doc_links（共享函数，避免代码重复）。
        扫描 docs_rj/ 5 子目录，把缺失的 .md 文件链接追加到对应段末尾。

        Returns:
            int: 追加的链接数
        """
        return tidy_common.reconcile_doc_links(summary_path, self.primary_docs)

    def _touch_last_updated(self, summary_path):
        """更新 SUMMARY frontmatter 的 last_updated 时间戳（保留其余内容）。"""
        try:
            with open(summary_path, 'r', encoding='utf-8') as handle:
                lines = handle.readlines()
        except (OSError, UnicodeDecodeError):
            return
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith('last_updated:') and not replaced:
                new_lines.append('last_updated: %s\n' % now)
                replaced = True
            else:
                new_lines.append(line)
        if replaced:
            generate_docs.atomic_write(summary_path, ''.join(new_lines))


# ===========================================================================
# TidyReport —— 启动整理结果（JSON 可序列化）
# ===========================================================================
class TidyReport:
    """启动整理结果载体，可序列化为 JSON（散落清单/归档跳过失败数/漂移数/PARA 下沉清单）。"""

    def __init__(self):
        self.primary_docs = None                 # 主 docs 目录
        self.missing_dirs = []                   # 项目结构缺失清单（报告型，不静默建）
        self.scattered = {}                      # {docs_dir: [task...]}
        self.archived = []                       # 已归档清单
        self.skipped = []                        # 跳过清单
        self.errors = []                         # 归档失败清单
        self.summary = None                      # SummaryRefresher.refresh() 结果
        self.drift = 0                           # 漂移数
        self.drift_missing = []                  # 漂移失效链接
        self.para_sink = []                      # 已下沉清单
        self.para_manual = []                    # 需人工确认清单
        self.memory_cleanup = None               # 外部记忆扫描清理（期3新增）
        self.git_health = None                   # git仓库体检（git_backup_cleanup新增）
        self.protocol_alignment = {}             # protocol/ 9 .py 齐全性体检
        self.skill_update = {}                   # skill 更新体检（T06 未实现时跳过）
        self.dependency_map = None               # DEPENDENCY_MAP.md 刷新结果（双端刷新·启动端，REQ-002/003）

    def to_dict(self):
        """转为可 JSON 序列化的字典。"""
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
            'para_sink': self.para_sink,
            'para_manual': self.para_manual,
            'memory_cleanup': self.memory_cleanup,
            'git_health': self.git_health,
            'protocol_alignment': self.protocol_alignment,
            'skill_update': self.skill_update,
            'dependency_map': self.dependency_map,
        }


# ===========================================================================
# protocol 对齐 + skill 更新 体检钩子（纯只读，失败仅告警不阻断 B5）
# ===========================================================================
# protocol/ 9 个常驻 .py（缺一即对齐失败）
_PROTOCOL_FILES = (
    '__init__.py',
    'constants.py',
    'file_roles.py',
    'field_contracts.py',
    'stages.py',
    'routing.py',
    'validation.py',
    'markdown_structure.py',
    'change_impact_map.py',
)


def check_protocol_alignment(skill_dir):
    """验证 protocol/ 9 .py 齐全性（纯只读）。

    Args:
        skill_dir: skill 根目录绝对路径（其下应有 protocol/ 子目录）。

    Returns:
        dict: {'passed': bool, 'missing': [...], 'total': 9, 'found': N}
              异常时返回 {'passed': False, 'error': str}，不抛出（B5）。
    """
    try:
        protocol_dir = os.path.join(skill_dir, 'protocol')
        missing = []
        found = 0
        for fname in _PROTOCOL_FILES:
            fpath = os.path.join(protocol_dir, fname)
            if os.path.isfile(fpath):
                found += 1
            else:
                missing.append(fname)
        passed = (len(missing) == 0)
        if passed:
            logger.info("protocol 对齐检查通过：%d/%d .py 齐全", found, len(_PROTOCOL_FILES))
        else:
            logger.warning("protocol 对齐检查：缺失 %d/%d：%s",
                           len(missing), len(_PROTOCOL_FILES), missing)
        return {
            'passed': passed,
            'missing': missing,
            'total': len(_PROTOCOL_FILES),
            'found': found,
        }
    except Exception as exc:
        logger.error("protocol 对齐检查异常（仅告警）: %s", exc)
        return {'passed': False, 'error': str(exc)}


def check_skill_update(skill_dir):
    """跑 scripts/check_skill_updates.py（T06 未实现时跳过，可选）。

    T06 尚未实现 check_skill_updates.py，本钩子做成可选：
      - 脚本不存在 → 返回 {'passed': True, 'skipped': True, 'reason': ...}，不报错
      - 脚本存在   → subprocess 调用，捕获超时/失败，返回执行结果

    Args:
        skill_dir: skill 根目录绝对路径（其下应有 scripts/check_skill_updates.py）。

    Returns:
        dict: 见上述分支；异常时返回 {'passed': False, 'error': str}，不抛出（B5）。
    """
    try:
        checker = os.path.join(skill_dir, 'scripts', 'check_skill_updates.py')
        if not os.path.isfile(checker):
            # T06 未实现：可选跳过，不报错（passed=True + skipped=True）
            logger.info("skill 更新检查：scripts/check_skill_updates.py 不存在，跳过（T06 未实现）")
            return {
                'passed': True,
                'skipped': True,
                'reason': 'check_skill_updates.py not yet implemented',
            }

        # T06 已实现：subprocess 调用，超时 8s（v1.0.4 实测报告 P1/F6：
        # 更新检查不应阻塞启动主链路），捕获 stdout/stderr
        import subprocess
        try:
            proc = subprocess.run(
                [sys.executable, checker, '--json'],
                cwd=skill_dir,
                capture_output=True,
                text=True,
                timeout=8,
                encoding='utf-8', errors='replace',
            )
        except subprocess.TimeoutExpired:
            logger.warning("skill 更新检查：执行超时（>8s），已跳过（WARN，不阻塞启动）")
            return {
                'passed': True,
                'warn': True,
                'behind_count': -1,
                'detail': 'timeout: check_skill_updates.py 未在 8s 内完成（网络慢或环境干扰），已跳过',
            }

        stdout = (proc.stdout or '').strip()
        stderr = (proc.stderr or '').strip()
        if proc.returncode != 0:
            logger.warning("skill 更新检查：脚本退出码 %d", proc.returncode)
            return {
                'passed': False,
                'behind_count': -1,
                'detail': 'exit=%d stderr=%s' % (proc.returncode, stderr[:500]),
            }

        # 尝试解析 JSON 输出（约定 check_skill_updates.py --json 输出 {behind_count, ...}）
        behind_count = 0
        try:
            payload = json.loads(stdout) if stdout else {}
            if isinstance(payload, dict) and 'behind_count' in payload:
                behind_count = int(payload.get('behind_count', 0))
        except (ValueError, TypeError):
            payload = {}

        logger.info("skill 更新检查完成：behind_count=%d", behind_count)
        return {
            'passed': True,
            'behind_count': behind_count,
            'detail': stdout[:500] if stdout else '',
        }
    except Exception as exc:
        logger.error("skill 更新检查异常（仅告警）: %s", exc)
        return {'passed': False, 'error': str(exc)}


# ===========================================================================
# StartupTidy —— 启动整理管线主类
# ===========================================================================
class StartupTidy:
    """启动整理管线。

    按序执行：Bootstrap 守卫 → 解析主 docs → 扫描散落 → 归档散落 →
    刷新 SUMMARY → 漂移检查 → PARA 下沉。所有归档类错误仅告警不阻断（B5）。
    """

    def __init__(self, dry_run=False, primary_docs=None, para_threshold=30, run_para=True, create_summary=False):
        """初始化管线。

        Args:
            dry_run: 预演模式，不实际移动/下沉文件。
            primary_docs: 显式指定的主 docs 目录（优先于自动检测）。
            para_threshold: PARA 下沉阈值（天），默认 30（A1）。
            run_para: 是否执行 PARA 下沉（T05，默认可选执行）。
        """
        self.dry_run = bool(dry_run)
        self.primary_docs_arg = primary_docs
        self.para_threshold = int(para_threshold)
        self.run_para = bool(run_para)
        self.create_summary = bool(create_summary)  # --create-summary 开关（确认后才创建，严守不静默创建）
        self._summary_blocker = False     # SUMMARY 缺失 BLOCKER 标记
        self.report = TidyReport()

    def run(self):
        """执行完整管线，返回 TidyReport。任何单步异常被捕获并记入 errors，不抛出（B5）。"""
        logger.info("=== 启动整理管线（startup_tidy）===")
        primary = self._resolve_primary_docs()
        self.report.primary_docs = primary
        # marker 健康检查：文件存在但 reader 返回 None（空/BOM/坏路径）→ 显式告警，防记忆静默 fallback（G4）
        # 注意：不能用 "and not primary" 作条件——R3 路由会在 marker 无效时仍解析出 primary（那样永不触发）
        if os.path.isfile('.primary_docs_rj') and generate_docs.read_primary_docs_marker() is None:
            logger.warning(".primary_docs_rj 存在但无效（空/BOM/路径不存在），"
                           "建议运行 python generate_docs.py --declare-primary 修复，否则项目记忆 fallback 项目 ./docs_rj/memory_rj（v1.0.4 起不再落外置用户目录）")
            self.report.errors.append({'stage': 'marker_invalid',
                                       'error': '.primary_docs_rj 存在但无效'})

        self.report.missing_dirs = self._ensure_project_structure()
        if not primary or not os.path.isdir(primary):
            logger.warning("主 docs 目录不存在（%s），跳过扫描/归档/SUMARY刷新（报告型守卫，不创建）", primary)
            logger.info("=== 启动整理完成：归档 0 / 跳过 0 / 失败 0 / 漂移 0 / 下沉 0 / 待人工 0 ===")
            return self.report

        # 3) 扫描散落文档
        try:
            self.report.scattered = generate_docs.scan_scattered_docs(primary)
        except Exception as exc:  # B5：归档类错误不阻断
            logger.error("扫描散落文档失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'scan_scattered', 'error': str(exc)})

        # 4) 归档散落文档
        try:
            archive = generate_docs.archive_scattered_docs(primary, dry_run=self.dry_run)
            self.report.archived = archive.get('archived', [])
            self.report.skipped = archive.get('skipped', [])
            self.report.errors.extend(archive.get('errors', []))
        except Exception as exc:  # B5
            logger.error("归档散落文档失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'archive_scattered', 'error': str(exc)})

        # 5) 刷新 SUMMARY（dry-run 仅报告，绝不修改任何文件，符合报告型守卫契约）
        if self.dry_run:
            logger.info("dry-run：跳过 SUMMARY 刷新（报告型守卫，不修改文件）")
            self.report.summary = {'summary_path': None, 'refreshed': False,
                                    'drift': 0, 'missing': []}
        else:
            try:
                refresher = SummaryRefresher(primary)
                self.report.summary = refresher.refresh()
                self.report.drift = self.report.summary.get('drift', 0)
                self.report.drift_missing = self.report.summary.get('missing', [])
            except Exception as exc:  # B5
                logger.error("刷新 SUMMARY 失败（仅告警）: %s", exc)
                self.report.errors.append({'stage': 'summary_refresh', 'error': str(exc)})

        # 6) 漂移检查（已纳入 run() 末尾，R4）——SummaryRefresher.refresh 内部已跑；
        #    此处对无 SUMMARY 的情况也补一次显式检查（基于主 docs 自身一致性）。
        try:
            self._drift_check_explicit(primary, auto_create=self.create_summary)
        except Exception as exc:  # B5
            logger.error("漂移检查失败（仅告警）: %s", exc)

        # 外部记忆扫描清理（期3新增）
        try:
            self.report.memory_cleanup = tidy_common.cleanup_legacy_memory(dry_run=self.dry_run)
        except Exception as exc:  # B5
            logger.error("外部记忆扫描清理失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'memory_cleanup', 'error': str(exc)})

        # 7) PARA 下沉（可选，T05）
        if self.run_para:
            try:
                sinked, manual = self._para_sink(self.para_threshold)
                self.report.para_sink = sinked
                self.report.para_manual = manual
            except Exception as exc:  # B5
                logger.error("PARA 下沉失败（仅告警）: %s", exc)
                self.report.errors.append({'stage': 'para_sink', 'error': str(exc)})

        # git 仓库体检（git_backup_cleanup新增，纯只读，失败仅告警不阻断 B5）
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

        # protocol 对齐 + skill 更新 体检（git_health 后、汇总前）
        # 纯只读，失败仅告警不阻断（B5）
        try:
            self.report.protocol_alignment = check_protocol_alignment(os.getcwd())
        except Exception as exc:  # B5
            logger.error("protocol 对齐检查失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'protocol_alignment', 'error': str(exc)})

        try:
            self.report.skill_update = check_skill_update(os.getcwd())
        except Exception as exc:  # B5
            logger.error("skill 更新检查失败（仅告警）: %s", exc)
            self.report.errors.append({'stage': 'skill_update', 'error': str(exc)})

        # DEPENDENCY_MAP 刷新（双端刷新：启动端，REQ-002/003）
        # 复用 handoff_tidy 的 _refresh_dependency_map 方法，保持双端一致
        if self.dry_run:
            logger.info("dry-run：跳过 DEPENDENCY_MAP 刷新（报告型守卫，不修改文件）")
            self.report.dependency_map = {'path': None, 'refreshed': False, 'families': 0}
        else:
            try:
                from handoff_tidy import HandoffTidy
                ht = HandoffTidy(dry_run=False)
                self.report.dependency_map = ht._refresh_dependency_map(primary)
            except Exception as exc:
                logger.error("DEPENDENCY_MAP 刷新失败（仅告警）: %s", exc)
                self.report.errors.append({'stage': 'dependency_map', 'error': str(exc)})
                self.report.dependency_map = {'path': None, 'refreshed': False, 'families': 0}

        if self._summary_blocker:
            logger.warning("=== [BLOCKER] 启动整理完成但发现 SUMMARY_RJ.md 缺失，请按三触发①引导式创建"
                           "（startup_tidy.py --create-summary 确认后生成）===")

        logger.info("=== 启动整理完成：归档 %d / 跳过 %d / 失败 %d / 漂移 %d / 下沉 %d / 待人工 %d ===",
                    len(self.report.archived), len(self.report.skipped),
                    len(self.report.errors), self.report.drift,
                    len(self.report.para_sink), len(self.report.para_manual))
        return self.report

    # ------------------------------------------------------------------ #
    # 内部步骤
    # ------------------------------------------------------------------ #
    def _ensure_project_structure(self):
        """Bootstrap 守卫（报告型）：检测项目结构完整性，缺失仅报告、绝不静默建。

        检测项（相对当前工作目录 = 项目根）：
          - docs_rj/                    主文档目录
          - docs_rj/{spec,task,handoff,memory,archive}_rj/   5 类常驻文件夹（含项目级记忆 memory_rj）
          - docs_rj/SUMMARY_RJ.md       项目根索引
          - outputs_rj/                 输出目录
          - .agent/memory/、.agent/skills/   agent 侧目录

        返回缺失清单 ``list[dict]``，每条：``{path, reason, layer}``。
        始终不抛出、不创建（遵循 bootstrap.md §四「禁止静默创建」）。
        """
        missing = []
        # v1.0.4（REQ-103 + /check 第2轮对抗审查 H2 修订）：docs_rj 属项目，检查项目根 ./docs_rj；
        # outputs_rj 仍外置。外置遗留数据=只读存档（原地保留），不作为"齐备"依据——
        # 老用户首跑会报缺失，由 bootstrap 在项目内建 8 要素，新链路从此在项目内延续。
        project_docs_rj = os.path.join(os.getcwd(), 'docs_rj')
        if not os.path.isdir(project_docs_rj):
            if user_data_path.external_docs_has_content():
                logger.info("外置存在遗留 docs 存档（只读保留）：%s；项目根缺 docs_rj，按缺失上报",
                            user_data_path.get_docs_rj_path())
            missing.append({'path': 'docs_rj/', 'reason': '项目结构缺失：项目根无 docs_rj 目录', 'layer': 'project'})
        if not os.path.isdir(str(user_data_path.get_outputs_rj_path())):
            missing.append({'path': 'outputs_rj/', 'reason': '项目结构缺失：外置目录不存在', 'layer': 'project'})
        # .agent 子目录（包内，agent 配置属项目级）—— 推荐项，不进 missing_dirs
        # 原因：SKILL.md §0 启动前置检查 8 要素不含 .agent/，它是可选的用户 agent 配置
        for d in ['.agent']:
            p = os.path.join(os.getcwd(), d)
            if not os.path.isdir(p):
                logger.info("推荐项：%s/ 不存在（agent 配置目录，非必需）", d)
        for d in ('.agent/memory', '.agent/skills'):
            p = os.path.join(os.getcwd(), d)
            if not os.path.isdir(p):
                logger.info("推荐项：%s/ 不存在（agent 侧目录，非必需）", d)
        # docs_rj 5 类常驻文件夹（优先用主 docs 路径；v1.0.4 REQ-104：无标记时回退项目 ./docs_rj；
        # 外置遗留=只读存档，不参与 5 类检查——检查对象永远是项目侧）
        if self.report.primary_docs:
            docs_rj_path = self.report.primary_docs
        else:
            docs_rj_path = os.path.join(os.getcwd(), 'docs_rj')
        for sub in generate_docs.DOC_RJ_SUBDIRS:
            p = os.path.join(docs_rj_path, sub)
            if not os.path.isdir(p):
                missing.append({'path': 'docs_rj/%s/' % sub, 'reason': 'docs 常驻文件夹缺失', 'layer': 'docs'})
        # SUMMARY_RJ.md 索引文件（外置目录下）
        summary_path = os.path.join(docs_rj_path, 'SUMMARY_RJ.md')
        if not os.path.isfile(summary_path):
            missing.append({'path': 'docs_rj/SUMMARY_RJ.md', 'reason': '项目根索引缺失', 'layer': 'docs'})

        if missing:
            logger.warning("项目结构完整性检查：发现 %d 处缺失（报告型，不静默创建）：", len(missing))
            for item in missing:
                logger.warning("  - %s（%s）", item['path'], item['reason'])
        else:
            logger.info("项目结构完整性检查通过：docs_rj 5类（含 memory_rj）+ 索引齐备")
        return missing

    def _resolve_primary_docs(self):
        """解析主 docs 目录（R3 优先级：显式 > .primary_docs_rj 标记 > MEMORY_RJ.md 约定 > 路由）。"""
        if self.primary_docs_arg:
            candidate = os.path.abspath(self.primary_docs_arg)
            if os.path.isdir(candidate):
                return candidate
            logger.warning("指定的主 docs 不存在: %s，回退自动检测", candidate)

        marker = generate_docs.read_primary_docs_marker()
        if marker:
            logger.info("从 .primary_docs_rj 标记读取主 docs: %s", marker)
            return marker

        mem = generate_docs.read_primary_docs_from_memory()
        if mem:
            return mem

        return generate_docs.find_docs_dir(create=False)

    def _drift_check_explicit(self, primary, auto_create=False):
        """无 SUMMARY 时的显式漂移兜底。

        缺失处理策略（严守「不静默创建」红线）：
          - auto_create=True  → 经确认（--create-summary）后引导式创建（复用模板+扫描）
          - auto_create=False → 升级为 [BLOCKER] 警告，提示 agent 按三触发①创建，绝不静默跳过
        """
        if not primary or not os.path.isdir(primary):
            return
        summary_path = os.path.join(primary, 'SUMMARY_RJ.md')
        if os.path.isfile(summary_path):
            return  # 已由 SummaryRefresher 处理
        if auto_create:
            created = self._create_summary_guided(primary)
            if created:
                logger.info("SUMMARY_RJ.md 已按 summary_view.md 三触发①引导式创建（--create-summary 确认后）")
                return
        # 未确认创建 → 强提示，不静默跳过
        self._summary_blocker = True
        logger.warning(
            "⚠️ [BLOCKER] 主 docs 下未发现 SUMMARY_RJ.md。"
            "按 summary_view.md 三触发①，必须由 agent 引导式创建（脚本不静默创建）。"
            "创建路径：读 assets/summary_template.md 模板 + 扫描 docs_rj 各子目录生成；"
            "或运行本脚本加 --create-summary 在确认后自动生成。"
        )

    def _create_summary_guided(self, primary):
        """引导式创建 SUMMARY_RJ.md（经 --create-summary 确认后调用）。

        复用 assets/summary_template.md 模板 + 扫描 docs_rj 5 类子目录，
        用 generate_docs.atomic_write 写出，并跑漂移检查确保 0 死链。
        返回 True 表示已创建；False 表示失败（仅告警，不阻断启动，B5）。
        """
        template = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'assets', 'summary_template.md')
        subs = ['memory_rj', 'spec_rj', 'task_rj', 'handoff_rj', 'archive_rj']
        icons = {'memory_rj': '🧠 Memory 文档', 'spec_rj': '📋 Spec 文档',
                 'task_rj': '✅ Task 文档', 'handoff_rj': '🤝 Handoff 文档',
                 'archive_rj': '🗄️ Archive 文档'}
        leads = {
            'memory_rj': '项目记忆体系——全局 memory/memory_main.md + 项目 docs_rj/memory_rj/{任务名}_memory_*.md（写入即落盘 + 自动 upsert 全局）。',
            'spec_rj': '需求规格——每个任务一个 spec.md，含 2-3 方案对比，通过 Self-Review。',
            'task_rj': '任务清单——每个任务一个 task.md，每条含「怎么做+怎么验证」。',
            'handoff_rj': '交接文档——当前状态、已完成、待办、阻塞项，30 秒接手。',
            'archive_rj': '归档沉淀——按任务子文件夹聚合（{task}_{ts}/），保留决策轨迹。',
        }
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        parts = ['---', 'title: pdca-skill', 'version: v1.0.1',
                 'last_updated: %s' % now, 'total_docs: 0',
                 'require-rule-mention: true', '---', '',
                 '# 📚 文档汇总视图（SUMMARY）', '',
                 '本文件汇总项目全部文档（memory+spec+task+handoff+archive），用 markdown 链接互连成知识图谱。纯 markdown 实现，零系统依赖。自动生成/更新：启动检查时 + 对话结束归档时 + 交接时（三触发硬性）。', '']
        total = 1  # memory/memory_main.md 全局记忆
        for sub in subs:
            sub_dir = os.path.join(primary, sub)
            files = sorted(f for f in os.listdir(sub_dir) if f.endswith('.md')) \
                if os.path.isdir(sub_dir) else []
            total += len(files)
            parts.append('## %s' % icons[sub])
            parts.append('')
            parts.append(leads[sub])
            parts.append('')
            if not files:
                parts.append('暂无')
            else:
                for f in files:
                    name = f.replace('.md', '')
                    parts.append('- [%s/%s](%s/%s) — %s' % (sub, f, sub, f, name))
            parts.append('')
        parts.append('## 🔗 漂移检查清单')
        parts.append('')
        parts.append('每次更新 SUMMARY 后必跑（三触发都跑）。用 grep + ls 做漂移检查。')
        parts.append('')
        parts.append('```bash')
        parts.append("grep -oP '\\]\\(\\K[^)]+' docs_rj/SUMMARY_RJ.md")
        parts.append('ls ../memory/memory_main.md')
        parts.append('ls docs_rj/memory_rj/*.md')
        parts.append('```')
        parts.append('')
        content = '\n'.join(parts)
        summary_path = os.path.join(primary, 'SUMMARY_RJ.md')
        try:
            generate_docs.atomic_write(summary_path, content)
        except Exception as exc:  # B5：创建失败仅告警
            logger.error("引导式创建 SUMMARY 失败（仅告警）: %s", exc)
            return False
        # 漂移检查：解析所有链接，确认文件存在
        links = re.findall(r'\]\(([^)]+)\)', content)
        broken = [ln for ln in links
                  if not ln.startswith('http')
                  and not os.path.exists(os.path.normpath(os.path.join(primary, ln)))]
        if broken:
            logger.warning("引导式创建 SUMMARY 存在 %d 个死链，请检查：%s", len(broken), broken)
        else:
            logger.info("引导式创建 SUMMARY 完成，漂移检查 0 死链（total_docs=%d）", total)
        return True

    def _para_sink(self, threshold):
        """PARA 下沉（R6，T05）。

        判定"过期" = spec_rj/task_rj 最新修改 > 阈值(默认30)天 且无活跃编辑
        → 移动到主 docs/archive_rj/{task}_{ts}/（按任务子文件夹聚合，对齐 D1 方案）。
        无法自动判定（无 spec/task、目标冲突、移动失败）→ 列入人工确认清单，不静默移动。

        Returns:
            (sinked, manual) 两个清单。
        """
        primary = self.report.primary_docs
        sinked = []
        manual = []
        if not primary or not os.path.isdir(primary):
            return sinked, manual

        archive_dir = os.path.join(primary, 'archive_rj')
        try:
            entries = sorted(os.listdir(primary))
        except OSError as exc:
            logger.warning("扫描主 docs 失败: %s", exc)
            return sinked, manual

        now = datetime.now()
        for entry in entries:
            entry_path = os.path.join(primary, entry)
            if not os.path.isdir(entry_path) or entry.startswith('.'):
                continue
            if entry in ('archive_rj', 'archive'):
                continue

            # 仅看 spec_rj / task_rj 的活跃度（无活跃 spec/task 编辑 = 过期候选）
            spec_dir = os.path.join(entry_path, 'spec_rj')
            task_dir = os.path.join(entry_path, 'task_rj')
            newest = None
            for sub in (spec_dir, task_dir):
                if not os.path.isdir(sub):
                    continue
                try:
                    for fname in os.listdir(sub):
                        fpath = os.path.join(sub, fname)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        except OSError:
                            continue
                        if newest is None or mtime > newest:
                            newest = mtime
                except OSError:
                    continue

            if newest is None:
                # 无 spec/task → 无法自动判定 → 人工确认清单
                manual.append({
                    'task_name': entry,
                    'path': entry_path,
                    'reason': '无 spec_rj/task_rj，无法自动判定过期',
                })
                continue

            age_days = (now - newest).days
            if age_days <= threshold:
                continue  # 仍活跃，不下沉

            dst = os.path.join(archive_dir, '%s_%s' % (entry, now.strftime('%Y%m%d_%H%M')))
            if os.path.exists(dst):
                manual.append({
                    'task_name': entry,
                    'path': entry_path,
                    'reason': '归档目标已存在，跳过避免冲突',
                })
                continue

            if self.dry_run:
                sinked.append({
                    'task_name': entry,
                    'src': entry_path,
                    'dst': dst,
                    'age_days': age_days,
                    'dry_run': True,
                })
                continue

            try:
                os.makedirs(archive_dir, exist_ok=True)
                shutil.move(entry_path, dst)
                sinked.append({
                    'task_name': entry,
                    'src': entry_path,
                    'dst': dst,
                    'age_days': age_days,
                })
                logger.info("PARA 下沉: %s（%d 天未编辑）→ %s", entry, age_days, dst)
            except (OSError, shutil.Error) as exc:
                manual.append({
                    'task_name': entry,
                    'path': entry_path,
                    'reason': '移动失败: %s' % exc,
                })

        if manual:
            logger.warning("PARA 下沉产出 %d 项需人工确认（不静默移动）", len(manual))
        return sinked, manual


# ===========================================================================
# CLI / main
# ===========================================================================
def run_migration_and_cleanup(skill_root):
    """启动时跑迁移 + 7 天后清理（HIGH-003 方向B：_cleanup_legacy 独立调用）。

    迁移归 migrate_if_needed，清理归 _cleanup_legacy——两者解耦。
    清理失败不阻断启动（与迁移失败一致，仅告警）。
    """
    report = {"migrate": None, "cleanup": None}
    try:
        report["migrate"] = migrate_user_data.migrate_if_needed(skill_root)
    except Exception as e:
        report["migrate"] = {"status": "migrate_error", "error": str(e)}
        sys.stderr.write("[WARN] 迁移失败（不阻断启动）: %s\n" % e)
    try:
        report["cleanup"] = migrate_user_data._cleanup_legacy(skill_root)
    except Exception as e:
        report["cleanup"] = {"status": "cleanup_error", "error": str(e)}
        sys.stderr.write("[WARN] 清理失败（不阻断启动）: %s\n" % e)
    return report


def _integrate_migration_to_main():
    """在 startup_tidy.py main() 最开头调用此函数（仅告警不阻断启动）。

    迁移 + 7 天清理的启动集成入口。HIGH-003 方向B。
    cycle 5 MEDIUM-2 修复：加 INFO 日志输出用户数据目录路径。
    """
    skill_root = str(Path(__file__).resolve().parent.parent)
    try:
        user_data_dir = user_data_path.get_user_data_dir(ensure_subdirs=False)
        sys.stderr.write("[INFO] 用户数据目录：%s\n" % user_data_dir)
    except Exception as e:
        sys.stderr.write("[WARN] 获取用户数据目录失败（不阻断）：%s\n" % e)
    migration_report = run_migration_and_cleanup(skill_root)
    if migration_report["migrate"]["status"] not in ("success", "skip_no_source", "skip_target_not_empty", "skip_lock_busy"):
        sys.stderr.write("[WARN] 迁移异常: %s\n" % migration_report["migrate"])
    if migration_report["cleanup"]["status"] == "cleaned":
        sys.stderr.write("[INFO] 包内 7 天保留期已过，已清理\n")


def main():
    parser = argparse.ArgumentParser(
        description='pdca-skill 启动整理管线（stdlib-only）')
    parser.add_argument('--dry-run', action='store_true',
                        help='预演：不实际移动/下沉文件，仅输出会做什么')
    parser.add_argument('--primary-docs', default=None,
                        help='指定主 docs 目录路径（优先于自动检测）')
    parser.add_argument('--para-threshold', type=int, default=30,
                        help='PARA 下沉阈值天数（默认 30，A1）')
    parser.add_argument('--skip-para', action='store_true',
                        help='跳过 PARA 下沉步骤（T05，可选）')
    parser.add_argument('--create-summary', action='store_true',
                        help='SUMMARY_RJ.md 缺失时，经确认后按模板引导式创建（不静默创建，需显式开启）')
    args = parser.parse_args()

    # T005b: 迁移+清理集成（最开头调用，仅告警不阻断启动）
    _integrate_migration_to_main()

    tidy = StartupTidy(
        dry_run=args.dry_run,
        primary_docs=args.primary_docs,
        para_threshold=args.para_threshold,
        run_para=not args.skip_para,
        create_summary=args.create_summary,
    )
    report = tidy.run()
    # JSON 输出到 stdout；日志已在 stderr
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

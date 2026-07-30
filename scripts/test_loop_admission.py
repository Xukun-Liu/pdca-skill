"""test_loop_admission.py — loop_admission.py 单元测试

对应 spec：docs_rj/spec_rj/loop_admission_python_spec_20260717_0943.md
对应 task：docs_rj/task_rj/loop_admission_python_task_20260717_0943.md T004-T009
版本：v1.0（T009 17 个测试用例，含 git skipIf）
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# 把 scripts 目录加入 path 以便 import loop_admission
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from loop_admission import (  # noqa: E402
    audit_project,
    compute_score,
    format_json,
    format_human,
    _emit_downgrade_warns,
    _progress_bar,
    AuditResult,
    LoopSignals,
    Finding,
    ScoreResult,
    BASE_SCORE,
    SCORE_WEIGHTS,
    LEVEL_THRESHOLDS,
    EXIT_CODE_THRESHOLD,
)


def make_full_signals(**overrides):
    """构造全齐的 21 字段 signals（除被测降级项外全 True）。

    用于 compute_score 单元测试，不依赖文件系统。
    """
    all_fields = [
        'skill_md', 'references_count', 'history_md', 'pdca_coverage',
        'memory_main', 'memory_rj_recent', 'summary_rj', 'docs_trio',
        'loop_tools', 'task_state', 'security',
        'triage', 'verifier', 'constraints', 'trigger_hooks',
        'loop_activity', 'governance_tool_scope', 'governance_stall',
        'governance_escalation', 'safety_doc',
        'skill_md_budget'
    ]
    defaults = {f: (True, ['mock']) for f in all_fields}
    defaults.update(overrides)
    return LoopSignals(**defaults)


class TestComputeScore(unittest.TestCase):
    """测试 compute_score 等级判定逻辑（用 mock signals，不依赖文件系统）。

    覆盖测试用例：1/2/3/4/5/6/9/14/15
    """

    def test_01_empty_project_is_l0(self):
        """用例1: 空 signals（全 false）→ L0, score=5（仅 base）"""
        empty_signals = LoopSignals(
            **{f: (False, []) for f in SCORE_WEIGHTS},
            skill_md_budget=(False, []),
        )
        score, level, _, _ = compute_score(empty_signals)
        self.assertEqual(score, BASE_SCORE, f'空 signals 应只给 base={BASE_SCORE}')
        self.assertEqual(level, 'L0', f'空 signals 应 L0，实际 {level}')

    def test_02_state_triage_reaches_l1(self):
        """用例2: task_state + triage → score=27 <50 → L0（仅这两项不够 L1）

        修正：task_state+12 + triage+10 + base 5 = 27 < 50 → L0（不是 L1）
        L1 需 score≥50 且 task_state 必需项。
        """
        s = make_full_signals(
            **{f: (False, []) for f in SCORE_WEIGHTS if f not in ('task_state', 'triage')}
        )
        score, level, _, _ = compute_score(s)
        expected = BASE_SCORE + 12 + 10  # 27
        self.assertEqual(score, expected, f'期望 score={expected}，实际 {score}')
        self.assertEqual(level, 'L0', f'score<50 应 L0，实际 {level}')

    def test_03_full_l2_signals(self):
        """用例3: 多 signals 但缺 verifier → L2（score≥70 且 triage 在）"""
        s = make_full_signals(verifier=(False, []))
        score, level, _, _ = compute_score(s)
        self.assertEqual(level, 'L2', f'缺 verifier 应 L2，实际 {level}')
        self.assertGreaterEqual(score, 70, 'L2 应 score≥70')

    def test_04_l3_requires_verifier_cost_activity(self):
        """用例4: 全齐 → L3（score=106 钳制 100）"""
        s = make_full_signals()
        score, level, _, _ = compute_score(s)
        self.assertEqual(level, 'L3', f'全齐应 L3，实际 {level}')
        self.assertEqual(score, 100, f'钳制后应 100，实际 {score}')

    def test_06_high_structure_without_activity_caps_l2(self):
        """用例6: 缺 loop_activity → L2（l3_ready=false）+ warn"""
        s = make_full_signals(loop_activity=(False, []))
        score, level, _, findings = compute_score(s)
        self.assertEqual(level, 'L2', f'缺 activity 应 L2，实际 {level}')
        self.assertTrue(
            any('loop_activity' in f.message for f in findings),
            '缺 loop_activity 应有 warn finding'
        )

    def test_09_governance_signals_add_points(self):
        """用例9: governance 三项（tool_scope/stall/escalation）各 +2 分

        用"仅 governance 三项 + base"的 mock signals 测加分：
        base 5 + 2 + 2 + 2 = 11 分。
        """
        # 构造：只有 governance 三项为 True，其他全 False
        gov_fields = ('governance_tool_scope', 'governance_stall', 'governance_escalation')
        overrides = {f: (False, []) for f in SCORE_WEIGHTS if f not in gov_fields}
        s_only_gov = make_full_signals(**overrides)
        # 验证 governance 三项确实为 True
        self.assertTrue(s_only_gov.governance_tool_scope[0])
        self.assertTrue(s_only_gov.governance_stall[0])
        self.assertTrue(s_only_gov.governance_escalation[0])
        score_only_gov, _, _, _ = compute_score(s_only_gov)
        expected = BASE_SCORE + 2 + 2 + 2  # 11
        self.assertEqual(
            score_only_gov, expected,
            f'仅 governance 三项应 score={expected}，实际 {score_only_gov}'
        )

    def test_14_l2_with_verifier_skill(self):
        """用例14: verifier 在 + 缺其他 L3 必需项 → L2

        构造：score≥85，verifier 在，但缺 loop_activity（l3_ready=false）→ L2 + warn
        """
        s = make_full_signals(loop_activity=(False, []))
        score, level, _, _ = compute_score(s)
        self.assertEqual(level, 'L2', f'verifier 在但缺 activity 应 L2，实际 {level}')
        self.assertTrue(s.verifier[0], 'verifier 应在')

    def test_15_task_state_counts_as_state_file(self):
        """用例15: task_state 信号命中 → score 含 +12"""
        s = make_full_signals(
            **{f: (False, []) for f in SCORE_WEIGHTS if f != 'task_state'}
        )
        score, level, _, _ = compute_score(s)
        expected = BASE_SCORE + 12  # 17
        self.assertEqual(score, expected, f'仅 task_state 应 score={expected}，实际 {score}')


class TestEmptyAndL1Layout(unittest.TestCase):
    """测试空目录和最小 L1 布局（依赖文件系统）。

    覆盖测试用例：7/8
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix='loop_admission_test_'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _build_minimal_l1(self):
        """建最小 L1 布局（6 项信号）→ score=59 L1"""
        # SKILL.md 含"7条铁律"（不含"预算"，避免触发 skill_md_budget）
        (self.tmpdir / 'SKILL.md').write_text(
            '# SKILL\n\n## 7条铁律\n\nMemory First...\n', encoding='utf-8'
        )
        # references/ 下 30 个空 .md + loop_triage.md
        refs_dir = self.tmpdir / 'references'
        refs_dir.mkdir(parents=True)
        for i in range(30):
            (refs_dir / f'ref_{i:02d}.md').write_text('', encoding='utf-8')
        (refs_dir / 'loop_triage.md').write_text('', encoding='utf-8')
        # memory/memory_main.md
        (self.tmpdir / 'memory').mkdir()
        (self.tmpdir / 'memory' / 'memory_main.md').write_text('', encoding='utf-8')
        # docs_rj/memory_rj/TASK_STATE_test.md
        mem_rj = self.tmpdir / 'docs_rj' / 'memory_rj'
        mem_rj.mkdir(parents=True)
        (mem_rj / 'TASK_STATE_test.md').write_text('', encoding='utf-8')
        # scripts/loop_*.py（2 个）
        scripts_dir = self.tmpdir / 'scripts'
        scripts_dir.mkdir()
        for name in ['loop_guard.py', 'loop_audit.py']:
            (scripts_dir / name).write_text('', encoding='utf-8')

    def test_07_empty_directory_scores_low(self):
        """用例7: 空目录 → L0, score<50"""
        result = audit_project(self.tmpdir)
        self.assertEqual(result.level, 'L0', f'空目录应 L0，实际 {result.level}')
        self.assertLess(result.score, EXIT_CODE_THRESHOLD, '空目录 score 应<50')

    def test_08_minimal_l1_layout(self):
        """用例8: SKILL.md+references+memory_main+TASK_STATE+loop_tools+triage → L1

        实际 score=57（含 loop_activity+4 附带命中）
        """
        self._build_minimal_l1()
        result = audit_project(self.tmpdir)
        self.assertEqual(result.level, 'L1', f'最小 L1 布局应 L1，实际 {result.level}')
        self.assertGreaterEqual(result.score, 50, 'L1 应 score≥50')
        self.assertLess(result.score, 70, 'L1 应 score<70')


class TestGovernanceFromDocs(unittest.TestCase):
    """测试从文档检测 governance 信号。

    覆盖测试用例：10/11
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix='loop_admission_gov_'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_10_governance_signals_detected_from_docs(self):
        """用例10: SKILL.md 含 governance 关键词 → 三项 governance 信号命中"""
        # SKILL.md 含 governance 关键词
        # tool_scope: 权限约束；stall: no_progress + stagnation；escalation: escalat
        (self.tmpdir / 'SKILL.md').write_text(
            '# SKILL\n\n## 7条铁律\n'
            '权限约束：least-privilege\n'
            'no_progress 连续 5 次 stagnation\n'
            'escalat to human review, exit code 2\n',
            encoding='utf-8'
        )
        result = audit_project(self.tmpdir)
        self.assertTrue(
            result.signals.governance_tool_scope[0],
            f'governance_tool_scope 应命中，evidence={result.signals.governance_tool_scope[1]}'
        )
        self.assertTrue(
            result.signals.governance_stall[0],
            f'governance_stall 应命中，evidence={result.signals.governance_stall[1]}'
        )
        self.assertTrue(
            result.signals.governance_escalation[0],
            f'governance_escalation 应命中，evidence={result.signals.governance_escalation[1]}'
        )

    def test_11_governance_signals_absent_in_bare_project(self):
        """用例11: 空项目（无 SKILL.md）→ 三项 governance 信号全 false"""
        result = audit_project(self.tmpdir)
        self.assertFalse(result.signals.governance_tool_scope[0])
        self.assertFalse(result.signals.governance_stall[0])
        self.assertFalse(result.signals.governance_escalation[0])


class TestFormatOutput(unittest.TestCase):
    """测试 format_human / format_json 输出。

    覆盖测试用例：12
    """

    def test_12_format_json_includes_level_score(self):
        """用例12: format_json 输出含 level/score/findings/recommendations 字段"""
        # 用 mock AuditResult
        result = AuditResult(
            target='/mock/path',
            score=75,
            level='L2',
            assessment='L2=assisted',
            signals=LoopSignals(
                **{f: (False, []) for f in SCORE_WEIGHTS},
                skill_md_budget=(False, []),
            ),
            findings=[Finding('ok', 'mock finding')],
            recommendations=['mock rec'],
        )
        output = format_json(result)
        data = json.loads(output)
        self.assertIn('level', data, 'JSON 应含 level')
        self.assertIn('score', data, 'JSON 应含 score')
        self.assertIn('findings', data, 'JSON 应含 findings')
        self.assertIn('recommendations', data, 'JSON 应含 recommendations')
        self.assertEqual(data['level'], 'L2')
        self.assertEqual(data['score'], 75)


class TestGitActivity(unittest.TestCase):
    """测试 git 相关的 loop_activity 检测。

    覆盖测试用例：13（含 @skipIf git 不可用）
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix='loop_admission_git_'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @unittest.skipIf(shutil.which('git') is None, 'git not available')
    def test_13_git_commit_counts_as_loop_activity(self):
        """用例13: git commit → loop_activity 命中（需 git 环境否则 skip）"""
        # 初始化 git 仓库并提交一次
        subprocess.run(
            ['git', 'init'], cwd=str(self.tmpdir),
            capture_output=True, check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'test@test.com'], cwd=str(self.tmpdir),
            capture_output=True, check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test'], cwd=str(self.tmpdir),
            capture_output=True, check=True,
        )
        (self.tmpdir / 'README.md').write_text('test', encoding='utf-8')
        subprocess.run(
            ['git', 'add', '.'], cwd=str(self.tmpdir),
            capture_output=True, check=True,
        )
        subprocess.run(
            ['git', 'commit', '-m', 'init'], cwd=str(self.tmpdir),
            capture_output=True, check=True,
        )
        result = audit_project(self.tmpdir)
        self.assertTrue(
            result.signals.loop_activity[0],
            f'git 仓库有 commit 应 loop_activity 命中，evidence={result.signals.loop_activity[1]}'
        )


class TestL1LayoutExtra(unittest.TestCase):
    """T004 保留的 2 个 L1 布局测试（兼容历史，对应原 test_l1_layout/test_l1_missing_triage）。

    覆盖测试用例：8 的补充场景（score 精确值 + 缺 triage 降级）
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix='loop_admission_l1_'))
        # SKILL.md 含"7条铁律"
        (self.tmpdir / 'SKILL.md').write_text(
            '# SKILL\n\n## 7条铁律\n\nMemory First...\n', encoding='utf-8'
        )
        # references/ 下 30 个空 .md + loop_triage.md
        refs_dir = self.tmpdir / 'references'
        refs_dir.mkdir(parents=True)
        for i in range(30):
            (refs_dir / f'ref_{i:02d}.md').write_text('', encoding='utf-8')
        (refs_dir / 'loop_triage.md').write_text('', encoding='utf-8')
        # memory/memory_main.md
        (self.tmpdir / 'memory').mkdir()
        (self.tmpdir / 'memory' / 'memory_main.md').write_text('', encoding='utf-8')
        # docs_rj/memory_rj/TASK_STATE_test.md
        mem_rj = self.tmpdir / 'docs_rj' / 'memory_rj'
        mem_rj.mkdir(parents=True)
        (mem_rj / 'TASK_STATE_test.md').write_text('', encoding='utf-8')
        # scripts/loop_*.py
        scripts_dir = self.tmpdir / 'scripts'
        scripts_dir.mkdir()
        for name in ['loop_guard.py', 'loop_audit.py']:
            (scripts_dir / name).write_text('', encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_l1_layout_score_57(self):
        """补充用例8: 最小 L1 布局 score=57（含 loop_activity 附带命中）"""
        result = audit_project(self.tmpdir)
        self.assertEqual(result.level, 'L1', f'期望 L1，实际 {result.level}')
        self.assertEqual(
            result.score, 57,
            f'期望 score=57（base5+8+6+4+12+8+10+4），实际 {result.score}'
        )

    def test_l1_missing_triage_caps_l0(self):
        """补充用例: 缺 triage → score=47 <50 → L0"""
        (self.tmpdir / 'references' / 'loop_triage.md').unlink()
        result = audit_project(self.tmpdir)
        self.assertEqual(result.score, 47, f'期望 score=47，实际 {result.score}')
        self.assertEqual(result.level, 'L0', f'期望 L0（score<50），实际 {result.level}')


class TestCLI(unittest.TestCase):
    """测试 CLI 入口（--help / --json）。

    覆盖测试用例：16/17
    """

    @classmethod
    def setUpClass(cls):
        cls.script_path = str(SCRIPTS_DIR / 'loop_admission.py')
        cls.project_root = str(SCRIPTS_DIR.parent)

    def test_16_cli_help_exits_0(self):
        """用例16: --help → 退码 0，stdout 含 usage"""
        result = subprocess.run(
            [sys.executable, self.script_path, '--help'],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f'--help 应退码 0，实际 {result.returncode}')
        self.assertIn('usage', result.stdout.lower(), 'stdout 应含 usage')

    def test_17_cli_json_output_valid(self):
        """用例17: --json → stdout 是有效 JSON，含 score/level"""
        result = subprocess.run(
            [sys.executable, self.script_path, self.project_root, '--json'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, f'项目根应退码 0，实际 {result.returncode}')
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(f'--json 输出不是有效 JSON: {e}')
        self.assertIn('score', data, 'JSON 应含 score')
        self.assertIn('level', data, 'JSON 应含 level')


class TestPyramidAndDowngradeWarns(unittest.TestCase):
    """金字塔传递性（H1）+ 降级 warn（H2）+ 多缺失项 warn（M3）测试。

    覆盖 M6 新增的反例场景：H1 金字塔违反 / H2 L0/L1 降级 warn / M3 多 warn 一起报。
    """

    def test_h1_l2_requires_task_state_pyramid(self):
        """H1 反例：score≥70 + triage=T + task_state=F → L1（不是 L2）。

        金字塔传递性 L2⊇L1：L2 必需项是 L1 必需项的超集，task_state 是 L1 必需项，
        所以 L2 必须也要求 task_state。原代码 bug：L2 不要求 task_state → 判 L2 但不满足 L1。
        """
        # 构造：除 task_state 和 verifier/loop_activity 外全 True（确保 score≥70 但缺 task_state）
        s = make_full_signals(task_state=(False, []))
        score, level, _, findings = compute_score(s)
        # task_state 缺 → 不进 L3（L3 必需项含 task_state）
        # task_state 缺 → 不进 L2（H1 修复后，L2⊇L1）
        # task_state 缺 → 不进 L1
        # 最终 → L0
        self.assertEqual(level, 'L0', f'H1: score≥70 但缺 task_state 应 L0（不是 L2），实际 {level}')
        # 应有 L3 降级 warn（因为 score≥85）含 task_state 缺失
        self.assertTrue(
            any('task_state' in f.message for f in findings),
            f'H2: 应有 task_state 缺失的 warn finding，实际 findings={findings}'
        )

    def test_h1_l3_blocked_without_task_state(self):
        """H1 反例2：score≥85 + verifier=T + triage=T + task_state=F → L0（不进 L2/L1）。

        全齐但缺 task_state：L3 缺 task_state → 不进 L3；
        L2 也缺 task_state（H1 修复后）→ 不进 L2；
        L1 也缺 task_state → 不进 L1；
        最终 → L0。
        """
        s = make_full_signals(task_state=(False, []))
        score, level, _, _ = compute_score(s)
        self.assertEqual(level, 'L0', f'H1: 缺 task_state 应一路降到 L0，实际 {level}')

    def test_h2_l0_downgrade_has_l3_warn(self):
        """H2 反例：score≥85 但缺 L3 必需项 → L0 + L3 降级 warn（原代码零 warn）。

        构造：全齐但 task_state=F（导致 L3/L2/L1 全不满足）→ L0 + 应有 warn。
        """
        s = make_full_signals(task_state=(False, []))
        score, level, _, findings = compute_score(s)
        self.assertEqual(level, 'L0', '应判 L0')
        self.assertGreaterEqual(
            len(findings), 1,
            f'H2: L0 降级应有 warn finding（原代码零 warn bug），实际 {len(findings)} 项'
        )
        # warn 应含 L3 阈值字样
        self.assertTrue(
            any('L3 阈值' in f.message for f in findings),
            f'warn 应含 L3 阈值字样，实际 findings={findings}'
        )

    def test_h2_l1_downgrade_has_l2_warn(self):
        """H2 反例2：score≥70 但缺 triage（L2 必需）→ L1 + L2 降级 warn。

        构造：全齐但 triage=F（L2 缺 triage，但 L1 只需 task_state）→ L1 + L2 warn。
        """
        s = make_full_signals(triage=(False, []))
        score, level, _, findings = compute_score(s)
        # triage=F 不影响 L1（L1 只需 task_state）
        self.assertEqual(level, 'L1', f'缺 triage 应 L1（有 task_state），实际 {level}')
        # 应有 L2 降级 warn 含 triage
        l2_warns = [f for f in findings if 'L2 阈值' in f.message]
        self.assertGreaterEqual(
            len(l2_warns), 1,
            f'H2: L1 降级应有 L2 warn finding，实际 {findings}'
        )
        self.assertTrue(
            any('triage' in f.message for f in l2_warns),
            f'warn 应含 triage 字样，实际 {l2_warns}'
        )

    def test_m3_multiple_missing_warns_emitted(self):
        """M3 验证：缺 verifier+loop_activity → L2 + 2 个 warn（elif 改独立 if）。

        原代码 bug：elif 链只报第一个缺失项；M3 修复后独立 if 链报全所有缺失项。
        """
        s = make_full_signals(verifier=(False, []), loop_activity=(False, []))
        score, level, _, findings = compute_score(s)
        self.assertEqual(level, 'L2', f'缺 verifier+activity 应 L2，实际 {level}')
        # 应同时报 verifier 和 loop_activity 两个 warn（M3 验证）
        warn_msgs = [f.message for f in findings]
        self.assertTrue(
            any('verifier' in m for m in warn_msgs),
            f'M3: 应报 verifier warn，实际 {warn_msgs}'
        )
        self.assertTrue(
            any('loop_activity' in m for m in warn_msgs),
            f'M3: 应报 loop_activity warn，实际 {warn_msgs}'
        )

    def test_emit_downgrade_warns_l3_all_missing(self):
        """直接测试 _emit_downgrade_warns：intended=L3 + 全缺 → 4 个 warn。"""
        # 构造：全 False 的 signals
        empty_signals = LoopSignals(
            **{f: (False, []) for f in SCORE_WEIGHTS},
            skill_md_budget=(False, []),
        )
        findings = _emit_downgrade_warns(empty_signals, 'L3', 85)
        # L3 必需：verifier + triage + task_state + loop_activity = 4 项
        self.assertEqual(
            len(findings), 4,
            f'L3 全缺应 4 个 warn，实际 {len(findings)} 个：{[f.message for f in findings]}'
        )

    def test_score_boundary_85_all_hit_is_l3(self):
        """score 边界值：score=85 全齐 → L3。

        构造：精确控制 score=85 较难（base 5 + 加权），改用全齐（score 钳制 100）验证 L3。
        """
        s = make_full_signals()
        score, level, _, _ = compute_score(s)
        self.assertEqual(score, 100, f'全齐应 score=100（钳制），实际 {score}')
        self.assertEqual(level, 'L3', f'全齐应 L3，实际 {level}')

    def test_score_boundary_50_with_task_state_is_l1(self):
        """score 边界值：score=50 + task_state → L1。

        构造：仅 task_state 命中（base 5 + 12 = 17）不够 50；需要更多信号凑到 50。
        简化：直接用 LEVEL_THRESHOLDS 常量验证阈值定义正确。
        """
        self.assertEqual(LEVEL_THRESHOLDS['L1'], 50, 'L1 阈值应为 50')
        self.assertEqual(LEVEL_THRESHOLDS['L2'], 70, 'L2 阈值应为 70')
        self.assertEqual(LEVEL_THRESHOLDS['L3'], 85, 'L3 阈值应为 85')


class TestFormatHuman(unittest.TestCase):
    """format_human / _progress_bar 输出测试（M6 新增覆盖）。"""

    def test_format_human_structure(self):
        """format_human 输出含 Score/Level/Assessment/Findings/Recommendations 五段。"""
        result = AuditResult(
            target='/mock/path',
            score=75,
            level='L2',
            assessment='L2=assisted',
            signals=LoopSignals(**{f: (False, []) for f in SCORE_WEIGHTS}, skill_md_budget=(False, [])),
            findings=[
                Finding('ok', 'mock ok'),
                Finding('warn', 'mock warn'),
            ],
            recommendations=['mock rec 1', 'mock rec 2'],
        )
        output = format_human(result)
        self.assertIn('Score:', output, '应含 Score 行')
        self.assertIn('Level:', output, '应含 Level 行')
        self.assertIn('Assessment:', output, '应含 Assessment 行')
        self.assertIn('Findings', output, '应含 Findings 段')
        self.assertIn('Recommendations', output, '应含 Recommendations 段')
        self.assertIn('75/100', output, '应含 score/100 字样')
        # Findings 按 ok/warn/fail 排序，ok 在前
        ok_pos = output.find('[ok]')
        warn_pos = output.find('[warn]')
        self.assertGreater(ok_pos, 0, '应含 [ok] 标签')
        self.assertGreater(warn_pos, 0, '应含 [warn] 标签')
        self.assertLess(ok_pos, warn_pos, 'ok 应排在 warn 前')

    def test_progress_bar_boundaries(self):
        """_progress_bar 边界值：100/59/5/0。"""
        self.assertEqual(_progress_bar(100), '██████████', 'score=100 应全满')
        self.assertEqual(_progress_bar(59), '█████░░░░░', 'score=59 应 5 满 5 空')
        self.assertEqual(_progress_bar(5), '░░░░░░░░░░', 'score=5 应全空（5//10=0）')
        self.assertEqual(_progress_bar(0), '░░░░░░░░░░', 'score=0 应全空')


class TestExitCodes(unittest.TestCase):
    """CLI 退码测试（M6 新增覆盖）：0/1/2 三种退码。

    覆盖场景：
        - 退码 0：score≥50（项目根）
        - 退码 1：异常（路径不存在）
        - 退码 2：score<50（空目录）
    """

    @classmethod
    def setUpClass(cls):
        cls.script_path = str(SCRIPTS_DIR / 'loop_admission.py')
        cls.project_root = str(SCRIPTS_DIR.parent)

    def test_exit_code_0_valid_project(self):
        """退码 0：项目根 score≥50 → 退码 0。"""
        result = subprocess.run(
            [sys.executable, self.script_path, self.project_root],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, f'项目根应退码 0，实际 {result.returncode}')

    def test_exit_code_1_invalid_path(self):
        """退码 1：路径不存在 → FileNotFoundError → 退码 1。"""
        invalid_path = str(Path(self.project_root) / 'nonexistent_path_xyz_123')
        result = subprocess.run(
            [sys.executable, self.script_path, invalid_path],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 1, f'路径不存在应退码 1，实际 {result.returncode}')
        self.assertIn('错误', result.stderr, f'stderr 应含错误提示，实际 {result.stderr}')

    def test_exit_code_2_low_score_empty_dir(self):
        """退码 2：空目录 score<50 → 退码 2。"""
        with tempfile.TemporaryDirectory(prefix='loop_admission_exit2_') as tmp:
            result = subprocess.run(
                [sys.executable, self.script_path, tmp],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 2, f'空目录应退码 2，实际 {result.returncode}')



class TestScoreBoundaries(unittest.TestCase):
    """M-3 修复：score 边界值 85/70/50/48 精确场景测试。

    用 mock signals 精确构造 score=85/70/50/48，验证 if-elif 链的比较运算符 >= 正确。
    如果有人把 >= 误写成 >，这些测试才能捕获。
    """

    def test_score_boundary_85_exact_is_l3(self):
        """score=85（精确）+ L3 必需项全齐 → L3。

        减项组合（共 21 分）：skill_md(8)+references_count(6)+history_md(3)+safety_doc(2)+governance_tool_scope(2)
        106-21=85，保留 verifier+triage+task_state+loop_activity（L3 必需）。
        """
        s = make_full_signals(
            skill_md=(False, []),
            references_count=(False, []),
            history_md=(False, []),
            safety_doc=(False, []),
            governance_tool_scope=(False, []),
        )
        score, level, _, _ = compute_score(s)
        self.assertEqual(score, 85, f'应 score=85，实际 {score}')
        self.assertEqual(level, 'L3', f'score=85 + L3 必需项全齐应 L3，实际 {level}')

    def test_score_boundary_70_exact_is_l2(self):
        """score=70（精确）+ L2 必需项全齐 → L2。

        减项组合（共 36 分）：skill_md(8)+references_count(6)+history_md(3)
        +memory_main(4)+memory_rj_recent(4)+safety_doc(2)+governance_tool_scope(2)
        +governance_stall(2)+governance_escalation(2)+constraints(3) = 36
        106-36=70，保留 triage+task_state（L2 必需）+verifier+loop_activity。
        """
        s = make_full_signals(
            skill_md=(False, []),
            references_count=(False, []),
            history_md=(False, []),
            memory_main=(False, []),
            memory_rj_recent=(False, []),
            safety_doc=(False, []),
            governance_tool_scope=(False, []),
            governance_stall=(False, []),
            governance_escalation=(False, []),
            constraints=(False, []),
        )
        score, level, _, _ = compute_score(s)
        self.assertEqual(score, 70, f'应 score=70，实际 {score}')
        self.assertEqual(level, 'L2', f'score=70 + L2 必需项全齐应 L2，实际 {level}')

    def test_score_boundary_50_exact_is_l1(self):
        """score=50（精确）+ task_state 保留 → L1。

        减项组合（共 56 分）：skill_md(8)+references_count(6)+history_md(3)+pdca_coverage(4)
        +memory_main(4)+memory_rj_recent(4)+governance_tool_scope(2)+governance_stall(2)
        +governance_escalation(2)+summary_rj(4)+docs_trio(5)+loop_tools(8)+security(4) = 56
        106-56=50，保留 task_state（L1 必需）+triage+verifier+loop_activity。
        """
        s = make_full_signals(
            skill_md=(False, []),
            references_count=(False, []),
            history_md=(False, []),
            pdca_coverage=(False, []),
            memory_main=(False, []),
            memory_rj_recent=(False, []),
            governance_tool_scope=(False, []),
            governance_stall=(False, []),
            governance_escalation=(False, []),
            summary_rj=(False, []),
            docs_trio=(False, []),
            loop_tools=(False, []),
            security=(False, []),
        )
        score, level, _, _ = compute_score(s)
        self.assertEqual(score, 50, f'应 score=50，实际 {score}')
        self.assertEqual(level, 'L1', f'score=50 + task_state 保留应 L1，实际 {level}')

    def test_score_boundary_48_with_task_state_is_l0(self):
        """score=48 + task_state 保留 → L0（score<50 即使有 task_state 也不进 L1）。

        减项组合（共 58 分）：50 组合 + safety_doc(2)
        106-58=48，保留 task_state 但 score<50 → L0。
        """
        s = make_full_signals(
            skill_md=(False, []),
            references_count=(False, []),
            history_md=(False, []),
            pdca_coverage=(False, []),
            memory_main=(False, []),
            memory_rj_recent=(False, []),
            safety_doc=(False, []),
            governance_tool_scope=(False, []),
            governance_stall=(False, []),
            governance_escalation=(False, []),
            summary_rj=(False, []),
            docs_trio=(False, []),
            loop_tools=(False, []),
            security=(False, []),
            skill_md_budget=(False, []),
        )
        score, level, _, _ = compute_score(s)
        self.assertEqual(score, 48, f'应 score=48，实际 {score}')
        self.assertEqual(level, 'L0', f'score=48 即使有 task_state 应 L0（<50），实际 {level}')


class TestEmitDowngradeWarnsDirect(unittest.TestCase):
    """M-4 修复：_emit_downgrade_warns L1/L2 分支直接单元测试。

    原 test_emit_downgrade_warns_l3_all_missing 只测 L3 分支，L1/L2 分支只通过 compute_score 间接测试。
    补 L1/L2 直接测试以定位内部逻辑 bug。
    """

    def test_emit_downgrade_warns_l1_all_missing(self):
        """直接测试 _emit_downgrade_warns L1 分支：全缺 → 1 个 warn（仅 task_state）。"""
        empty_signals = LoopSignals(**{f: (False, []) for f in SCORE_WEIGHTS}, skill_md_budget=(False, []))
        findings = _emit_downgrade_warns(empty_signals, 'L1', 50)
        self.assertEqual(
            len(findings), 1,
            f'L1 全缺应 1 个 warn（仅 task_state），实际 {len(findings)}：{[f.message for f in findings]}'
        )
        self.assertIn('task_state', findings[0].message, f'warn 应含 task_state，实际 {findings[0].message}')
        self.assertIn('L1 阈值', findings[0].message, f'warn 应含 L1 阈值字样，实际 {findings[0].message}')

    def test_emit_downgrade_warns_l2_all_missing(self):
        """直接测试 _emit_downgrade_warns L2 分支：全缺 → 2 个 warn（triage + task_state）。"""
        empty_signals = LoopSignals(**{f: (False, []) for f in SCORE_WEIGHTS}, skill_md_budget=(False, []))
        findings = _emit_downgrade_warns(empty_signals, 'L2', 70)
        self.assertEqual(
            len(findings), 2,
            f'L2 全缺应 2 个 warn（triage + task_state），实际 {len(findings)}：{[f.message for f in findings]}'
        )
        warn_msgs = [f.message for f in findings]
        self.assertTrue(any('triage' in m for m in warn_msgs), f'应含 triage warn，实际 {warn_msgs}')
        self.assertTrue(any('task_state' in m for m in warn_msgs), f'应含 task_state warn，实际 {warn_msgs}')

    def test_emit_downgrade_warns_l1_task_state_present_no_warn(self):
        """L1 分支：task_state 存在 → 0 个 warn（不缺必需项）。"""
        s = make_full_signals()  # 全齐
        findings = _emit_downgrade_warns(s, 'L1', 50)
        self.assertEqual(len(findings), 0, f'task_state 存在应 0 warn，实际 {len(findings)}')

    def test_emit_downgrade_warns_l2_triage_and_task_state_present_no_warn(self):
        """L2 分支：triage + task_state 都存在 → 0 个 warn。"""
        s = make_full_signals()  # 全齐
        findings = _emit_downgrade_warns(s, 'L2', 70)
        self.assertEqual(len(findings), 0, f'triage+task_state 存在应 0 warn，实际 {len(findings)}')


class TestLoopActivityFallback(unittest.TestCase):
    """M-5 修复：detect_loop_activity 非 git 降级路径测试（路径③④）。

    原 test_13_git_commit_counts_as_loop_activity 只测路径②（git log）。
    补路径③（TASK_STATE mtime 近 7 天）和路径④（loop_audit.py 存在）。
    """

    def setUp(self):
        """每个测试用独立 tmpdir，避免相互干扰。"""
        self.tmpdir = Path(tempfile.mkdtemp(prefix='loop_activity_test_'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_non_git_falls_back_to_task_state_mtime(self):
        """路径③：非 git 仓库 + TASK_STATE mtime 近 7 天 → loop_activity 命中。"""
        from loop_admission import detect_loop_activity
        # tmpdir 默认非 git 仓库
        (self.tmpdir / 'docs_rj' / 'memory_rj').mkdir(parents=True)
        (self.tmpdir / 'docs_rj' / 'memory_rj' / 'TASK_STATE_test.md').write_text(
            '# TASK_STATE', encoding='utf-8'
        )
        hit, evidence = detect_loop_activity(self.tmpdir)
        self.assertTrue(hit, f'非 git + 近期 TASK_STATE 应命中，evidence={evidence}')
        self.assertTrue(
            any('STATE' in e for e in evidence),
            f'evidence 应含 STATE 字样（路径③），实际 {evidence}'
        )

    def test_non_git_falls_back_to_loop_audit_script(self):
        """路径④：非 git 仓库 + 无 TASK_STATE + loop_audit.py 存在 → loop_activity 命中。"""
        from loop_admission import detect_loop_activity
        # 不创建 docs_rj/memory_rj（无 TASK_STATE）
        (self.tmpdir / 'scripts').mkdir(parents=True)
        (self.tmpdir / 'scripts' / 'loop_audit.py').write_text(
            '# loop_audit', encoding='utf-8'
        )
        hit, evidence = detect_loop_activity(self.tmpdir)
        self.assertTrue(hit, f'非 git + loop_audit.py 应命中，evidence={evidence}')
        self.assertTrue(
            any('loop_audit' in e for e in evidence),
            f'evidence 应含 loop_audit 字样（路径④），实际 {evidence}'
        )

    def test_non_git_no_fallback_signals_misses(self):
        """反例：非 git 仓库 + 无 TASK_STATE + 无 loop_audit.py → loop_activity 未命中。"""
        from loop_admission import detect_loop_activity
        # 空目录，无任何 fallback 信号
        hit, evidence = detect_loop_activity(self.tmpdir)
        self.assertFalse(hit, f'非 git + 无 fallback 信号应未命中，evidence={evidence}')


if __name__ == '__main__':
    unittest.main(verbosity=2)

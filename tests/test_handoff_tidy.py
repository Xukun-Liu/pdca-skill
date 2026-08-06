#!/usr/bin/env python3
"""tests/test_handoff_tidy.py - handoff_tidy.py 4 闸门证据驱动判定单元测试。

对应 handoff_gate_fix 任务：
- _verify_gate_evidence_file 证据文件校验（存在 + 内容含 0 HIGH，拒伪证）
- _read_gate_evidence 解析 TASK_STATE 的 '## Gate Evidence' 段
- _check_task_completion 4 闸门判定（verification / gate2对抗 / gate3一致性 / gate4确认）
- _write_signoff 拒签路径 + --force 豁免通道（forced: true 审计标记）
- 老任务 completed 不翻案

覆盖 6 个用例（对应 task 文档 T004）：
- test_gate_evidence_file: 证据文件三态（0 HIGH 通过 / 不存在 / 空报告拒绝）
- test_missing_evidence: 有 Verification 无 Gate Evidence → pending + 3 缺项
- test_all_gates_pass: 4 闸门全过 → ready_to_close
- test_forged_evidence_rejected: 报告存在但无 0 HIGH → pending + 拒签
- test_legacy_completed_untouched: 老任务 completed 不翻案
- test_force_signoff: --force → written + forced: true + status completed
"""

import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from handoff_tidy import HandoffTidy  # noqa: E402

BASE_STATE = """---
task: t
status: pending
---

## Verification
- total: 2
- passed: 2
"""

GATE_EVIDENCE = """
## Gate Evidence
- gate1_spec_verification: pass (2/2)
- gate2_adversarial: pass (0 HIGH) | 证据: {report}#L12
- gate3_consistency: pass (0 HIGH) | 证据: {report}#L8
- gate4_user_confirm: confirm | 时间戳: 2026-08-06 12:00 | 用户原话: "可以，通过了"
"""


def _write_state(tmp_path, name, content):
    """写入 TASK_STATE_<name>.md 到 tmp_path。"""
    path = os.path.join(str(tmp_path), "TASK_STATE_%s.md" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _make_ok_report(tmp_path, name):
    """构造含 '0 HIGH' 的有效审查报告，返回正斜杠路径。"""
    rep = os.path.join(str(tmp_path), name)
    with open(rep, "w", encoding="utf-8") as f:
        f.write("结论: 0 HIGH, 0 MEDIUM")
    return rep.replace("\\", "/")


class TestVerifyGateEvidenceFile:
    """_verify_gate_evidence_file：证据文件三态校验。"""

    def test_gate_evidence_file(self, tmp_path):
        h = HandoffTidy(dry_run=True)
        # 有效报告（含 0 HIGH），允许 #L 行号后缀
        rep = _make_ok_report(tmp_path, "t_adversarial.md")
        ok, reason = h._verify_gate_evidence_file(rep + "#L12")
        assert ok, reason
        # 不存在的文件
        ok3, reason3 = h._verify_gate_evidence_file(os.path.join(str(tmp_path), "no_such.md"))
        assert not ok3
        assert "证据文件不存在" in reason3
        # 空报告（伪造证据）
        empty = os.path.join(str(tmp_path), "t_empty.md")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("空报告")
        ok4, reason4 = h._verify_gate_evidence_file(empty)
        assert not ok4
        assert "不含 0 HIGH" in reason4


class TestCheckTaskCompletion:
    """_check_task_completion：4 闸门判定。"""

    def test_missing_evidence(self, tmp_path):
        _write_state(tmp_path, "t1", BASE_STATE)
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t1", "L2")
        assert status == "pending"
        assert len(h._last_blocked_gates) == 3

    def test_all_gates_pass(self, tmp_path):
        rep = _make_ok_report(tmp_path, "t2_adversarial_20260806_1200.md")
        _write_state(tmp_path, "t2", BASE_STATE + GATE_EVIDENCE.format(report=rep))
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t2", "L2")
        assert status == "ready_to_close", h._last_blocked_gates
        assert h._last_blocked_gates == []

    def test_forged_evidence_rejected(self, tmp_path):
        empty = os.path.join(str(tmp_path), "t3_adversarial.md")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("空报告")
        _write_state(tmp_path, "t3", BASE_STATE + GATE_EVIDENCE.format(report=empty.replace("\\", "/")))
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t3", "L2")
        assert status == "pending"
        assert any("不含 0 HIGH" in g for g in h._last_blocked_gates)

    def test_legacy_completed_untouched(self, tmp_path):
        _write_state(tmp_path, "t4", "---\ntask: t4\nstatus: completed\n---\n")
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t4", "L2")
        assert status == "completed"


class TestWriteSignoff:
    """_write_signoff：拒签路径 + force 豁免通道。"""

    def test_signoff_blocked_without_evidence(self, tmp_path):
        p = _write_state(tmp_path, "t5", BASE_STATE)
        h = HandoffTidy(dry_run=True)
        r = h._write_signoff(str(tmp_path), "t5", "L2")
        assert r.get("signoff_blocked") is True
        assert r.get("blocked_gates")
        content = open(p, encoding="utf-8").read()
        assert "## Sign-off" not in content  # 拒签未写入

    def test_force_signoff(self, tmp_path):
        p = _write_state(tmp_path, "t6", BASE_STATE)
        h = HandoffTidy(dry_run=True)
        r = h._write_signoff(str(tmp_path), "t6", "L2", force=True)
        assert r.get("written") is True
        content = open(p, encoding="utf-8").read()
        assert "- 强制完成: forced: true" in content
        assert "status: completed" in content

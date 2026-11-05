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
import tidy_common  # noqa: E402

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

    def test_ten_high_rejected(self, tmp_path):
        """对抗审查 CRITICAL 修复：'10 HIGH'/'20 HIGH' 不得被误判为通过。"""
        h = HandoffTidy(dry_run=True)
        for name, content in (
            ("t_10.md", "结论: 10 HIGH, 2 MEDIUM"),
            ("t_20.md", "结论: 20 HIGH"),
        ):
            rep = os.path.join(str(tmp_path), name)
            with open(rep, "w", encoding="utf-8") as f:
                f.write(content)
            ok, _ = h._verify_gate_evidence_file(rep)
            assert not ok, "%s 不应通过" % name

    def test_relative_to_primary_docs(self, tmp_path):
        """对抗审查 C4 修复：相对 docs_rj 写法（check_rj/x.md）也能解析到。"""
        h = HandoffTidy(dry_run=True)
        h.report.primary_docs = str(tmp_path)
        os.makedirs(os.path.join(str(tmp_path), "check_rj"), exist_ok=True)
        rep = os.path.join(str(tmp_path), "check_rj", "t_rel.md")
        with open(rep, "w", encoding="utf-8") as f:
            f.write("结论: 0 HIGH")
        ok, reason = h._verify_gate_evidence_file("check_rj/t_rel.md#L12")
        assert ok, reason


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

    def test_forged_ready_to_close_rejected(self, tmp_path):
        """对抗审查修复：伪造 status=ready_to_close（无任何 Gate Evidence）必须回落 pending 并拒签。"""
        s = "---\ntask: t7\nstatus: ready_to_close\n---\n\n## Verification\n- total: 2\n- passed: 2\n"
        p = _write_state(tmp_path, "t7", s)
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t7", "L2")
        assert status == "pending", "伪造 ready_to_close 不得免检"
        assert len(h._last_blocked_gates) >= 3
        r = h._write_signoff(str(tmp_path), "t7", "L2")
        assert r.get("signoff_blocked") is True
        content = open(p, encoding="utf-8").read()
        assert "## Sign-off" not in content

    def test_loop_auto_allows_ready_to_close(self, tmp_path):
        """/loop 无人值守：gate4=loop_auto 时 4 闸门全过 → ready_to_close（等用户确认，不假完成）。"""
        rep = _make_ok_report(tmp_path, "t8_adversarial.md")
        s = BASE_STATE + """
## Gate Evidence
- gate1_spec_verification: pass (2/2)
- gate2_adversarial: pass (0 HIGH) | 证据: {report}#L12
- gate3_consistency: pass (0 HIGH) | 证据: {report}#L8
- gate4_user_confirm: loop_auto | 说明: /loop 无人值守，待用户确认
""".format(report=rep)
        _write_state(tmp_path, "t8", s)
        h = HandoffTidy(dry_run=True)
        status = h._check_task_completion(str(tmp_path), "t8", "L2")
        assert status == "ready_to_close", h._last_blocked_gates


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


class TestCwdGuard:
    """cwd 防呆：非仓库根目录运行直接 exit 2。"""

    def test_cwd_guard(self, tmp_path):
        import subprocess

        script = os.path.join(SKILL_ROOT, "scripts", "handoff_tidy.py")
        # 临时目录无 .primary_docs_rj / docs_rj → 退出码 2
        r = subprocess.run(
            [sys.executable, script, "--dry-run"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r.returncode == 2
        assert "仓库根" in r.stderr
        # 逃生舱参数透传不崩
        HandoffTidy(dry_run=True, allow_any_dir=True)


# ===========================================================================
# v1.1.0：记忆分层（{class}/{YYYYMM}/）后，索引/计数/标注三路径必须递归
# ===========================================================================

def _make_layered_primary(tmp_path):
    """构造 docs_rj：memory_rj 分层 3 个 + 旧扁平 1 个，其余类目空。"""
    primary = os.path.join(str(tmp_path), "docs_rj")
    for sub in ("memory_rj", "spec_rj", "task_rj", "handoff_rj", "archive_rj"):
        os.makedirs(os.path.join(primary, sub), exist_ok=True)
    layered = [
        (("status", "202610"), "alpha_memory_20261001_0900.md"),
        (("decision", "202610"), "alpha_memory_20261002_0900.md"),
        (("pitfall", "202609"), "beta_memory_20260915_0900.md"),
    ]
    for (cls, month), name in layered:
        d = os.path.join(primary, "memory_rj", cls, month)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write("---\nsummary: %s\n---\n正文\n" % name)
    with open(os.path.join(primary, "memory_rj", "legacy_memory_20260801_0900.md"),
              "w", encoding="utf-8") as f:
        f.write("---\nsummary: legacy\n---\n正文\n")
    return primary


def _broken_links_relative_to(md_path):
    """返回 md 中所有相对链接解析不存在的目标。"""
    import re as _re

    base = os.path.dirname(md_path)
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    broken = []
    for m in _re.finditer(r"\]\(([^)]+)\)", text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#", 1)[0]
        abs_t = clean if os.path.isabs(clean) else os.path.normpath(os.path.join(base, clean))
        if not (os.path.isfile(abs_t) or os.path.isdir(abs_t)):
            broken.append(target)
    return broken


class TestLayeredIndexRecursion:
    """写入分层、读取扁平 = 索引隐身；这些用例锁死三路径同源。"""

    def test_iter_md_rel_paths_recursive(self, tmp_path):
        root = os.path.join(str(tmp_path), "cat")
        os.makedirs(os.path.join(root, "status", "202610"))
        open(os.path.join(root, "status", "202610", "a_memory_20261001_0900.md"),
             "w", encoding="utf-8").close()
        open(os.path.join(root, "b_memory_20261002_0900.md"), "w", encoding="utf-8").close()
        open(os.path.join(root, "INDEX.md"), "w", encoding="utf-8").close()
        os.makedirs(os.path.join(root, ".hidden"))
        open(os.path.join(root, ".hidden", "c.md"), "w", encoding="utf-8").close()

        rels = tidy_common.iter_md_rel_paths(root)
        assert rels == ["b_memory_20261002_0900.md",
                        "status/202610/a_memory_20261001_0900.md"]

    def test_reconcile_adds_layered_links_and_total_docs(self, tmp_path):
        primary = _make_layered_primary(tmp_path)
        summary = os.path.join(primary, "SUMMARY_RJ.md")
        with open(summary, "w", encoding="utf-8") as f:
            f.write("---\ntitle: t\ntotal_docs: 1\n---\n\n"
                    "## 🧠 Memory 文档\n\n## 📋 Spec 文档\n")

        added = tidy_common.reconcile_doc_links(summary, primary)
        assert added == 4

        with open(summary, "r", encoding="utf-8") as f:
            content = f.read()
        assert "total_docs: 4" in content
        assert "memory_rj/status/202610/alpha_memory_20261001_0900.md" in content
        assert "memory_rj/legacy_memory_20260801_0900.md" in content
        # 链接全部可解析（不含子目录前缀错误）
        assert _broken_links_relative_to(summary) == []

    def test_reconcile_fixes_stale_total_docs_without_new_links(self, tmp_path):
        primary = _make_layered_primary(tmp_path)
        summary = os.path.join(primary, "SUMMARY_RJ.md")
        links = "\n".join([
            "- [a](memory_rj/status/202610/alpha_memory_20261001_0900.md)",
            "- [b](memory_rj/decision/202610/alpha_memory_20261002_0900.md)",
            "- [c](memory_rj/pitfall/202609/beta_memory_20260915_0900.md)",
            "- [d](memory_rj/legacy_memory_20260801_0900.md)",
        ])
        with open(summary, "w", encoding="utf-8") as f:
            f.write("---\ntitle: t\ntotal_docs: 12\n---\n\n"
                    "## 🧠 Memory 文档\n%s\n\n" % links)

        added = tidy_common.reconcile_doc_links(summary, primary)
        assert added == 0
        with open(summary, "r", encoding="utf-8") as f:
            content = f.read()
        assert "total_docs: 4" in content
        assert "total_docs: 12" not in content

    def test_category_index_layered_links_resolve(self, tmp_path):
        primary = _make_layered_primary(tmp_path)
        h = HandoffTidy(dry_run=False, allow_any_dir=True)
        result = h._refresh_category_indexes(primary)

        mem = [i for i in result["indexes"] if i["category"] == "memory_rj"][0]
        assert mem["files_count"] == 4
        assert mem["active_count"] == 3
        assert mem["superseded_count"] == 1

        index_path = os.path.join(primary, "memory_rj", "INDEX.md")
        assert _broken_links_relative_to(index_path) == []

    def test_archive_index_links_resolve(self, tmp_path):
        primary = _make_layered_primary(tmp_path)
        arc = os.path.join(primary, "archive_rj")
        os.makedirs(os.path.join(arc, "old_task_20260101_0900"))
        open(os.path.join(arc, "old_task_20260101_0900", "a_spec_20260101_0900.md"),
             "w", encoding="utf-8").close()
        open(os.path.join(arc, "legacy_task_20251201_0900_archived.md"),
             "w", encoding="utf-8").close()

        h = HandoffTidy(dry_run=False, allow_any_dir=True)
        h._refresh_category_indexes(primary)
        index_path = os.path.join(arc, "INDEX.md")
        assert _broken_links_relative_to(index_path) == []

    def test_annotate_summary_recency_layered(self, tmp_path):
        primary = _make_layered_primary(tmp_path)
        summary = os.path.join(primary, "SUMMARY_RJ.md")
        with open(summary, "w", encoding="utf-8") as f:
            f.write("---\ntitle: t\ntotal_docs: 4\n---\n\n## 🧠 Memory 文档\n\n"
                    "- [a](memory_rj/status/202610/alpha_memory_20261001_0900.md)\n"
                    "- [b](memory_rj/pitfall/202609/beta_memory_20260915_0900.md)\n")

        h = HandoffTidy(dry_run=False, allow_any_dir=True)
        result = h._annotate_summary_recency(primary)
        assert result["annotated"] == 2
        assert result["no_status"] == 0

        with open(summary, "r", encoding="utf-8") as f:
            content = f.read()
        assert "最新·2026-09-15" in content or "`最新·" in content


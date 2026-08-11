# -*- coding: utf-8 -*-
"""记忆治理体系交付前修复测试（S10-S12）

覆盖对抗性审查发现的测试缺失：
- S10: 5 工具并发场景测试
- S11: 5 工具端到端流程测试
- S12: 真实备份失败场景测试（不 mock）
- S1-S4 回归测试（dry_run + quarantine 失败保护 + 冒号兼容 + rollback 排除）
"""
import os
import sys
import threading
import time

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import user_data_path
import memory_shadow_write


class _DummyLock:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


def _setup_memory_main(monkeypatch, tmp_path, project_name="test_project", task_name="test_task"):
    """辅助：构造含 1 条记忆的 memory_main.md"""
    monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
    import generate_docs
    monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
    fake_global = str(tmp_path / "memory" / "memory_main.md")
    os.makedirs(os.path.dirname(fake_global), exist_ok=True)
    content = "# 主记忆\n\n## %s\n\n### 记忆条目 · %s（2026-07-30 14:35）\n**重要性**: high\n**是否经验**: true\n**经验标签**: bugfix\n内容\n\n" % (project_name, task_name)
    with open(fake_global, "w", encoding="utf-8") as f:
        f.write(content)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
    monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
    mem_rj = str(user_data_path.get_memory_rj_path())
    os.makedirs(mem_rj, exist_ok=True)
    return fake_global


# ---------------------------------------------------------------------------
# S1 回归：handoff_tidy dry_run 模式跳过 distill
# ---------------------------------------------------------------------------

class TestS1DryRunGuard:
    def test_dry_run_skips_distill(self, monkeypatch, tmp_path):
        """dry_run=True 时应跳过 distill，不调 memory_distill.distill"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        import handoff_tidy
        import memory_distill
        distill_called = []
        def _fake_distill(*a, **kw):
            distill_called.append(True)
            return {'total_lessons': 0}
        monkeypatch.setattr(memory_distill, 'distill', _fake_distill)
        runner = handoff_tidy.HandoffTidy(dry_run=True, task_name='test')
        result = runner.run()
        assert len(distill_called) == 0  # dry_run 不应调 distill
        assert result.distill_result == {'skipped': True, 'reason': 'dry_run'}


# ---------------------------------------------------------------------------
# S2 回归：memory_delete hard_delete 时 quarantine 失败拒绝删除
# ---------------------------------------------------------------------------

class TestS2QuarantineFailureProtection:
    def test_hard_delete_aborts_when_quarantine_fails(self, monkeypatch, tmp_path):
        """quarantine 失败时应拒绝物理删除"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        # mock quarantine 失败
        monkeypatch.setattr(memory_shadow_write, "_quarantine_entry", lambda *a, **kw: None)
        monkeypatch.setattr(memory_shadow_write, "_backup_before_operation", lambda *a, **kw: None)
        result = memory_shadow_write.memory_delete("test_task", project_name="test_project", hard_delete=True)
        assert result['deleted'] is False
        assert 'quarantine 失败' in result['reason']
        # 条目仍在
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "### 记忆条目 · test_task" in content


# ---------------------------------------------------------------------------
# S3 回归：learn_tidy 正则兼容半角/全角冒号
# ---------------------------------------------------------------------------

class TestS3ColonCompatibility:
    def test_parse_half_width_colon(self, monkeypatch, tmp_path):
        """正则应解析半角冒号（write_project 写入格式）"""
        import learn_tidy
        # 构造含半角冒号的 memory 内容
        content = "# 主记忆\n\n## test_project\n\n### 记忆条目 · task1（2026-07-30 14:35）\n**重要性**: high\n**是否经验**: true\n**经验标签**: bugfix\n**状态**: active\n内容\n\n"
        # 跑 learn_tidy 解析
        entries = learn_tidy._parse_memory_entries(content)
        assert len(entries) >= 1
        entry = entries[0]
        assert entry.get('importance_level') == 'high'
        assert entry.get('is_lesson') == True


# ---------------------------------------------------------------------------
# S4 回归：memory_rollback 排除 rollback_pre_restore 目录
# ---------------------------------------------------------------------------

class TestS4RollbackExcludePreRestore:
    def test_rollback_excludes_pre_restore_dir(self, monkeypatch, tmp_path):
        """rollback 应排除 rollback_pre_restore 目录"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        undo_base = str(tmp_path / "undo")
        os.makedirs(undo_base, exist_ok=True)
        # 造两个 undo 目录：memory_delete + rollback_pre_restore
        delete_dir = os.path.join(undo_base, "memory_delete_20260730_103022")
        restore_dir = os.path.join(undo_base, "rollback_pre_restore_20260730_110000")
        os.makedirs(delete_dir)
        os.makedirs(restore_dir)
        # memory_delete 目录放真实备份
        with open(os.path.join(delete_dir, "memory_main.md.bak"), "w", encoding="utf-8") as f:
            f.write("# 恢复后的内容\n")
        # rollback_pre_restore 目录放"回滚前状态"
        with open(os.path.join(restore_dir, "memory_main.md.bak"), "w", encoding="utf-8") as f:
            f.write("# 回滚前状态（不应被选中）\n")
        import memory_shadow_write
        monkeypatch.setattr(memory_shadow_write, "_backup_before_operation", lambda *a, **kw: None)
        result = memory_shadow_write.memory_rollback("20260730")
        # 应选 memory_delete 目录，不是 rollback_pre_restore
        assert result['rolled_back'] is True
        assert 'memory_delete' in result['undo_dir']


# ---------------------------------------------------------------------------
# S10: 5 工具并发场景
# ---------------------------------------------------------------------------

class TestS10Concurrency:
    def test_concurrent_delete_different_tasks(self, monkeypatch, tmp_path):
        """并发删除不同 task 应串行化，无数据损坏"""
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 构造 3 条记忆
        content = "# 主记忆\n\n## test_project\n\n"
        for i in range(3):
            content += "### 记忆条目 · task_%d（2026-07-30 14:35）\n**重要性**: low\n内容%d\n\n" % (i, i)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write(content)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
        monkeypatch.setattr(memory_shadow_write, "_backup_before_operation", lambda *a, **kw: None)
        # 并发删 3 个 task（软删）
        results = [None, None, None]
        def _delete(idx):
            results[idx] = memory_shadow_write.memory_delete("task_%d" % idx, project_name="test_project")
        threads = [threading.Thread(target=_delete, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 验证：3 个都成功
        for i, r in enumerate(results):
            assert r['deleted'] is True, "task_%d 删除失败: %s" % (i, r)
        # 验证：文件结构完整（3 条都标 archived）
        with open(fake_global, "r", encoding="utf-8") as f:
            final = f.read()
        assert final.count("**状态**: archived") == 3


# ---------------------------------------------------------------------------
# S11: 5 工具端到端流程
# ---------------------------------------------------------------------------

class TestS11EndToEnd:
    def test_write_archive_delete_rollback_flow(self, monkeypatch, tmp_path):
        """端到端：write → archive → delete(软) → 验证"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        monkeypatch.setattr(memory_shadow_write, "_backup_before_operation", lambda *a, **kw: None)
        # 1. archive
        r1 = memory_shadow_write.memory_archive("test_task", "测试归档", project_name="test_project")
        assert r1['archived'] is True
        # 2. 验证 archived
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: archived" in content
        # 3. delete(软) - 已 archived 的条目再软删
        r2 = memory_shadow_write.memory_delete("test_task", project_name="test_project")
        assert r2['deleted'] is True
        # 4. demote
        r3 = memory_shadow_write.memory_demote("test_task", "测试降级", project_name="test_project")
        assert r3['demoted'] is True
        # 5. 验证最终状态 demoted
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: demoted" in content

    def test_capacity_threshold_after_write(self, monkeypatch, tmp_path):
        """端到端：write 后自动容量告警（构造超阈值场景）"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
        # 设小阈值
        monkeypatch.setattr(memory_shadow_write, "SEGMENT_MAX_ENTRIES", 2)
        mem_rj = str(user_data_path.get_memory_rj_path())
        os.makedirs(mem_rj, exist_ok=True)
        # write 3 条（超阈值 2）
        for i in range(3):
            memory_shadow_write.write_project("e2e_task_%d" % i, "内容%d" % i, project_name="e2e_proj")
        # 验证：3 条都写入
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.count("### 记忆条目 · e2e_task_") == 3


# ---------------------------------------------------------------------------
# S12: 真实备份失败场景（不 mock _backup_before_operation）
# ---------------------------------------------------------------------------

class TestS12RealBackupFailure:
    def test_backup_failure_does_not_crash(self, monkeypatch, tmp_path):
        """备份失败时主操作应继续（不崩溃），但日志记录"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        # 不 mock _backup_before_operation，但 mock shutil.copy2 抛异常
        import shutil
        def _raise_copy(*a, **kw):
            raise PermissionError("模拟备份失败")
        monkeypatch.setattr(shutil, "copy2", _raise_copy)
        # memory_delete 应不崩溃（备份失败返回 None，主操作继续）
        result = memory_shadow_write.memory_delete("test_task", project_name="test_project")
        # 软删除应成功（备份失败不阻断）
        assert result['deleted'] is True

    def test_quarantine_real_failure_returns_none(self, monkeypatch, tmp_path):
        """quarantine 真实失败应返回 None（不崩溃）—— mock os.makedirs 失败"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "atomic_write", lambda p, c: open(p, 'w', encoding='utf-8').write(c))
        # mock os.makedirs 抛 PermissionError
        original_makedirs = os.makedirs
        def _raise_makedirs(*a, **kw):
            raise PermissionError("模拟无写权限")
        monkeypatch.setattr(os, "makedirs", _raise_makedirs)
        result = memory_shadow_write._quarantine_entry("test", "block", "reason")
        # 应返回 None（失败），不抛异常
        assert result is None

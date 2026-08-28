# -*- coding: utf-8 -*-
"""记忆治理体系 3-R 阶段2 测试：flag 机制 + 容量阈值 + 隔离机制

覆盖：
- T009/T010: flag 字段定义 + upsert 支持 flag
- T011: 容量阈值检查函数
- T012: 无 LLM 时隔离机制（quarantine/）
"""
import os
import sys

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


# T009: _parse_entry_flag()
class TestFlagParsing:
    def test_parse_active_default(self):
        block = "### 记忆条目 · task1（2026-07-30）\n**重要性**: high\n内容\n"
        result = memory_shadow_write._parse_entry_flag(block)
        assert result['status'] == 'active'
        assert result['archive_reason'] == ''
        assert result['reflection'] == ''

    def test_parse_archived(self):
        block = "**状态**: archived\n**归档原因**: 容量超限\n**重要性**: low\n内容\n"
        result = memory_shadow_write._parse_entry_flag(block)
        assert result['status'] == 'archived'
        assert '容量超限' in result['archive_reason']

    def test_parse_demoted_with_reflection(self):
        block = "**状态**: demoted\n**归档原因**: 项目降级\n**反思**: 需重新评估\n内容\n"
        result = memory_shadow_write._parse_entry_flag(block)
        assert result['status'] == 'demoted'
        assert '项目降级' in result['archive_reason']
        assert '需重新评估' in result['reflection']


# T010: _update_entry_flag()
class TestFlagUpdate:
    def test_update_active_to_archived(self):
        block = "**重要性**: low\n**是否经验**: false\n**经验标签**: 无\n**状态**: active\n内容\n"
        result = memory_shadow_write._update_entry_flag(block, 'archived', archive_reason='容量超限')
        assert '**状态**: archived' in result
        assert '**归档原因**: 容量超限' in result

    def test_update_archived_to_active_removes_reason(self):
        block = "**状态**: archived\n**归档原因**: 容量超限\n内容\n"
        result = memory_shadow_write._update_entry_flag(block, 'active')
        assert '**状态**: active' in result
        assert '**归档原因**' not in result

    def test_add_flag_to_old_block_without_flag(self):
        block = "**重要性**: high\n**是否经验**: true\n**经验标签**: bugfix\n内容\n"
        result = memory_shadow_write._update_entry_flag(block, 'archived', archive_reason='历史')
        assert '**状态**: archived' in result
        assert '**归档原因**: 历史' in result


# T009: write_project 支持 status 参数
class TestWriteProjectWithFlag:
    def test_write_with_archived_status(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        # v1.0.4：chdir 到 tmp 项目目录，防污染仓库真实 docs_rj（§2.14 加粗要求）
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # mock 返回 None 模拟"项目无任何 docs 目录"
        monkeypatch.setattr(generate_docs, "find_docs_dir", lambda custom_dir=None, create=True: None)
        # v1.0.4（REQ-105）：expected_dir 改项目路径 ./docs_rj/memory_rj
        expected_dir = os.path.abspath('./docs_rj/memory_rj')
        os.makedirs(expected_dir, exist_ok=True)
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
        result = memory_shadow_write.write_project(
            "test_flag_task", "test archived content",
            status='archived', archive_reason='test_reason'
        )
        assert result['project_ok'] is True
        files = os.listdir(expected_dir)
        mem_file = [f for f in files if f.startswith("test_flag_task_memory_")][0]
        with open(os.path.join(expected_dir, mem_file), "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: archived" in content
        assert "**归档原因**: test_reason" in content


# T011: check_capacity_threshold()
class TestCapacityThreshold:
    def _setup_memory_main(self, monkeypatch, tmp_path, entries_per_seg=0, num_segs=1):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        content = ""
        for s in range(num_segs):
            content += "## project_%d\n" % s
            for e in range(entries_per_seg):
                content += "### 记忆条目 · task_%d_%d（2026-07-30）\n内容%d\n\n" % (s, e, e)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write(content)
        return fake_global

    def test_under_threshold(self, monkeypatch, tmp_path):
        self._setup_memory_main(monkeypatch, tmp_path, entries_per_seg=5, num_segs=1)
        result = memory_shadow_write.check_capacity_threshold("project_0")
        assert result['exceeded'] is False
        assert result['level'] == 'none'

    def test_segment_exceeded_entries(self, monkeypatch, tmp_path):
        monkeypatch.setattr(memory_shadow_write, "SEGMENT_MAX_ENTRIES", 3)
        self._setup_memory_main(monkeypatch, tmp_path, entries_per_seg=5, num_segs=1)
        result = memory_shadow_write.check_capacity_threshold("project_0")
        assert result['exceeded'] is True
        assert result['level'] == 'segment'
        assert result['details']['seg_count'] == 5

    def test_global_exceeded(self, monkeypatch, tmp_path):
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MAX_ENTRIES", 3)
        self._setup_memory_main(monkeypatch, tmp_path, entries_per_seg=5, num_segs=1)
        result = memory_shadow_write.check_capacity_threshold()
        assert result['exceeded'] is True
        assert result['level'] == 'global'

    def test_segment_not_found(self, monkeypatch, tmp_path):
        self._setup_memory_main(monkeypatch, tmp_path, entries_per_seg=1, num_segs=1)
        result = memory_shadow_write.check_capacity_threshold("nonexistent_project")
        assert result['exceeded'] is False

    def test_no_memory_main(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", str(tmp_path / "nonexistent.md"))
        result = memory_shadow_write.check_capacity_threshold()
        assert result['exceeded'] is False
        assert result['level'] == 'none'


# T012: _quarantine_entry()
class TestQuarantine:
    def test_quarantine_creates_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "atomic_write", lambda p, c: open(p, 'w', encoding='utf-8').write(c))
        result = memory_shadow_write._quarantine_entry(
            "test_project", "### 记忆条目\n内容\n", "test_reason"
        )
        assert result is not None
        assert os.path.isfile(result)
        assert "quarantine" in result
        with open(result, "r", encoding="utf-8") as f:
            content = f.read()
        assert "test_project" in content
        assert "test_reason" in content
        assert "待 LLM 复核" in content

    def test_quarantine_dir_location(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "atomic_write", lambda p, c: open(p, 'w', encoding='utf-8').write(c))
        memory_shadow_write._quarantine_entry("test", "block", "reason")
        q_dir = memory_shadow_write._get_quarantine_dir()
        assert q_dir == os.path.join(str(tmp_path), "quarantine")
        assert os.path.isdir(q_dir)

    def test_quarantine_failure_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        def _raise(p, c):
            raise PermissionError("denied")
        monkeypatch.setattr(generate_docs, "atomic_write", _raise)
        result = memory_shadow_write._quarantine_entry("test", "block", "reason")
        assert result is None

    def test_quarantine_preserves_original_block(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "atomic_write", lambda p, c: open(p, 'w', encoding='utf-8').write(c))
        original_block = "### 记忆条目 · task1（2026-07-30）\n**重要性**: high\n关键经验\n"
        result = memory_shadow_write._quarantine_entry("proj", original_block, "容量超限")
        with open(result, "r", encoding="utf-8") as f:
            content = f.read()
        assert original_block in content

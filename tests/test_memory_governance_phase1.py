# -*- coding: utf-8 -*-
"""记忆治理体系 3-R 阶段1 测试：路径分裂修复 + 备份回滚机制

覆盖：
- T001: user_data_path.get_memory_rj_path()
- T002-T005: 4 处路径解析一致性
- T006: _backup_before_operation()
- T007: memory_rollback()
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

# 脚本路径
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import user_data_path
import memory_shadow_write


# ---------------------------------------------------------------------------
# T001: get_memory_rj_path 路径解析
# ---------------------------------------------------------------------------

class TestGetMemoryRjPath:
    """T001: user_data_path 新增 get_memory_rj_path()"""

    def test_returns_path_under_docs_rj(self, monkeypatch, tmp_path):
        """get_memory_rj_path() 应返回 docs_rj/memory_rj/"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        result = user_data_path.get_memory_rj_path()
        assert isinstance(result, Path)
        assert result.name == "memory_rj"
        assert result.parent.name == "docs_rj"
        assert "memory_rj" in str(result)

    def test_consistent_with_get_docs_rj_path(self, monkeypatch, tmp_path):
        """get_memory_rj_path() 应等于 get_docs_rj_path() / 'memory_rj'"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        expected = user_data_path.get_docs_rj_path() / "memory_rj"
        actual = user_data_path.get_memory_rj_path()
        assert actual == expected


# ---------------------------------------------------------------------------
# T002-T005: 4 处路径解析一致性
# ---------------------------------------------------------------------------

class TestPathAlignment:
    """T002-T005: write_project / force_sync / archive_tidy / handoff_tidy 路径对齐"""

    def test_resolve_memory_rj_dir_returns_user_data_path(self, monkeypatch, tmp_path):
        """无 primary_docs marker 时，_resolve_memory_rj_dir 应走 user_data_path"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        # mock read_primary_docs_marker 返回 None
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        result = memory_shadow_write._resolve_memory_rj_dir()
        expected = str(user_data_path.get_memory_rj_path())
        assert result == expected

    def test_resolve_memory_rj_dir_prefers_primary_marker(self, monkeypatch, tmp_path):
        """有 primary_docs marker 时，_resolve_memory_rj_dir 应走 primary/memory_rj"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        primary_dir = str(tmp_path / "primary_docs")
        os.makedirs(primary_dir, exist_ok=True)
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: primary_dir)
        result = memory_shadow_write._resolve_memory_rj_dir()
        assert result == os.path.join(primary_dir, "memory_rj")

    def test_write_project_uses_user_data_path_when_no_marker(self, monkeypatch, tmp_path):
        """write_project 无 marker 时应写到 user_data_path.get_memory_rj_path()"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 预先创建新路径目录，避免老路径 ./memory/ 回退触发
        expected_dir = str(user_data_path.get_memory_rj_path())
        os.makedirs(expected_dir, exist_ok=True)
        # mock GLOBAL_MEMORY_FILE 到临时目录
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        # mock 锁避免跨进程锁干扰
        monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
        # 写入
        result = memory_shadow_write.write_project("test_task", "test content")
        assert result['project_ok'] is True
        # 验证项目记忆写到 user_data_path
        files = os.listdir(expected_dir) if os.path.isdir(expected_dir) else []
        assert any(f.startswith("test_task_memory_") for f in files), \
            "项目记忆应写到 user_data_path.get_memory_rj_path()"


class _DummyLock:
    """测试用空锁，避免跨进程文件锁干扰"""
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# T006: _backup_before_operation 备份机制
# ---------------------------------------------------------------------------

class TestBackupBeforeOperation:
    """T006: _backup_before_operation()"""

    def test_backup_creates_undo_dir(self, monkeypatch, tmp_path):
        """备份应创建 undo/{tool}_{ts}/ 目录"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 准备 fake memory_main.md
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write("# test memory main\n")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        # 执行备份
        undo_dir = memory_shadow_write._backup_before_operation("test_tool")
        assert undo_dir is not None
        assert os.path.isdir(undo_dir)
        assert "test_tool" in os.path.basename(undo_dir)
        # 验证 memory_main.md.bak 存在
        bak_path = os.path.join(undo_dir, "memory_main.md.bak")
        assert os.path.isfile(bak_path)
        with open(bak_path, "r", encoding="utf-8") as f:
            assert "# test memory main" in f.read()

    def test_backup_includes_memory_rj(self, monkeypatch, tmp_path):
        """备份应包含 memory_rj/ 目录"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 准备 fake memory_main.md
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write("# test\n")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        # 准备 fake memory_rj/
        mem_rj = user_data_path.get_memory_rj_path()
        os.makedirs(str(mem_rj), exist_ok=True)
        with open(os.path.join(str(mem_rj), "test_memory.md"), "w", encoding="utf-8") as f:
            f.write("# test memory\n")
        # 执行备份
        undo_dir = memory_shadow_write._backup_before_operation("test_tool")
        bak_rj = os.path.join(undo_dir, "memory_rj.bak")
        assert os.path.isdir(bak_rj)
        assert "test_memory.md" in os.listdir(bak_rj)

    def test_backup_returns_none_on_failure(self, monkeypatch, tmp_path):
        """备份失败应返回 None，不抛异常"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 创建 fake GLOBAL_MEMORY_FILE
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write("# test\n")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        # 创建 memory_rj 目录让 copytree 被调用
        mem_rj = str(user_data_path.get_memory_rj_path())
        os.makedirs(mem_rj, exist_ok=True)
        # mock shutil.copytree 抛异常（模拟磁盘满/权限拒绝）
        def _raise(*a, **kw):
            raise PermissionError("copytree denied")
        monkeypatch.setattr(memory_shadow_write.shutil, "copytree", _raise)
        undo_dir = memory_shadow_write._backup_before_operation("test_tool")
        assert undo_dir is None


# ---------------------------------------------------------------------------
# T007: memory_rollback 回滚机制
# ---------------------------------------------------------------------------

class TestMemoryRollback:
    """T007: memory_rollback()"""

    def test_rollback_restores_memory_main(self, monkeypatch, tmp_path):
        """回滚应恢复 memory_main.md"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # 准备 fake memory_main.md
        fake_global = str(tmp_path / "memory" / "memory_main.md")
        os.makedirs(os.path.dirname(fake_global), exist_ok=True)
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write("# original\n")
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
        # 备份
        undo_dir = memory_shadow_write._backup_before_operation("test_tool")
        # 修改 memory_main.md
        with open(fake_global, "w", encoding="utf-8") as f:
            f.write("# modified\n")
        # 回滚（用 undo_dir 的 timestamp 片段）
        ts_fragment = os.path.basename(undo_dir).split("_", 2)[-1]  # 取 timestamp 部分
        result = memory_shadow_write.memory_rollback(ts_fragment)
        assert result['rolled_back'] is True
        # 验证恢复
        with open(fake_global, "r", encoding="utf-8") as f:
            assert "# original" in f.read()

    def test_rollback_no_match_returns_false(self, monkeypatch, tmp_path):
        """无匹配 timestamp 应返回 rolled_back=False"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        result = memory_shadow_write.memory_rollback("nonexistent_timestamp")
        assert result['rolled_back'] is False
        assert 'reason' in result

    def test_rollback_no_undo_dir_returns_false(self, monkeypatch, tmp_path):
        """undo 目录不存在应返回 rolled_back=False"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        result = memory_shadow_write.memory_rollback("20260730")
        assert result['rolled_back'] is False


# ---------------------------------------------------------------------------
# T007 扩展: _cleanup_old_undos 清理
# ---------------------------------------------------------------------------

class TestCleanupOldUndos:
    """T007 扩展: _cleanup_old_undos()"""

    def test_cleanup_removes_old_undos(self, monkeypatch, tmp_path):
        """清理应删除超期 undo 目录"""
        monkeypatch.setenv("PDCA_DATA_DIR", str(tmp_path))
        undo_base = os.path.join(str(tmp_path), "undo")
        os.makedirs(undo_base, exist_ok=True)
        # 创建一个"老"目录（修改 mtime 为 35 天前）
        old_dir = os.path.join(undo_base, "old_tool_20260101_000000")
        os.makedirs(old_dir, exist_ok=True)
        import time
        old_time = time.time() - 35 * 86400
        os.utime(old_dir, (old_time, old_time))
        # 创建一个"新"目录
        new_dir = os.path.join(undo_base, "new_tool_20260730_000000")
        os.makedirs(new_dir, exist_ok=True)
        # 清理（30 天）
        cleaned = memory_shadow_write._cleanup_old_undos(max_age_days=30)
        assert cleaned >= 1
        assert not os.path.isdir(old_dir)
        assert os.path.isdir(new_dir)

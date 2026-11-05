# -*- coding: utf-8 -*-
"""记忆治理体系 3-R 阶段3 测试：5 工具（delete/archive/promote/demote）

覆盖：
- T014: memory_delete（双键 + 备份）
- T015: memory_archive（flag 不移动 + 归档原因）
- T016: memory_promote（复用 upsert）
- T017: memory_demote（flag 标记）
"""
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

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
    # REQ-105（v1.0.4）后项目记忆落 R3 解析出的 docs 目录（不再默认落外置用户目录）；
    # 把解析结果钉到 tmp_path，使 memory_promote 查找目录与测试写入目录一致。
    monkeypatch.setattr(generate_docs, "find_docs_dir", lambda create=False: str(tmp_path))
    fake_global = str(tmp_path / "memory" / "memory_main.md")
    os.makedirs(os.path.dirname(fake_global), exist_ok=True)
    content = "# 主记忆\n\n## %s\n\n### 记忆条目 · %s（2026-07-30 14:35）\n**重要性**: high\n**是否经验**: true\n**经验标签**: bugfix\n内容\n\n" % (project_name, task_name)
    with open(fake_global, "w", encoding="utf-8") as f:
        f.write(content)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
    monkeypatch.setattr(memory_shadow_write, "_GLOBAL_CP_LOCK", _DummyLock())
    # mock 备份避免跨进程锁
    monkeypatch.setattr(memory_shadow_write, "_backup_before_operation", lambda *a, **kw: None)
    # 预创建 memory_rj 目录（promote 需要）
    os.makedirs(os.path.join(str(tmp_path), "memory_rj"), exist_ok=True)
    return fake_global


# T014: memory_delete
class TestMemoryDelete:
    def test_soft_delete_marks_archived(self, monkeypatch, tmp_path):
        """软删除应标记 archived"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_delete("test_task", project_name="test_project")
        assert result['deleted'] is True
        assert result['soft'] is True
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: archived" in content
        assert "### 记忆条目 · test_task" in content  # 条目仍在

    def test_hard_delete_removes_entry(self, monkeypatch, tmp_path):
        """硬删除应移除条目（到 quarantine）"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_delete("test_task", project_name="test_project", hard_delete=True)
        assert result['deleted'] is True
        assert result['soft'] is False
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "### 记忆条目 · test_task" not in content

    def test_delete_not_found(self, monkeypatch, tmp_path):
        """未找到条目应返回 deleted=False"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_delete("nonexistent_task", project_name="test_project")
        assert result['deleted'] is False

    def test_delete_by_timestamp(self, monkeypatch, tmp_path):
        """按 timestamp 双键删除"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_delete("test_task", timestamp="2026-07-30 14:35", project_name="test_project")
        assert result['deleted'] is True


# T015: memory_archive
class TestMemoryArchive:
    def test_archive_marks_flag(self, monkeypatch, tmp_path):
        """归档应标记 archived + 归档原因"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_archive("test_task", "容量超限", project_name="test_project")
        assert result['archived'] is True
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: archived" in content
        assert "**归档原因**: 容量超限" in content

    def test_archive_empty_reason_fails(self, monkeypatch, tmp_path):
        """空归档原因应失败"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_archive("test_task", "", project_name="test_project")
        assert result['archived'] is False

    def test_archive_not_found(self, monkeypatch, tmp_path):
        """未找到条目应失败"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_archive("nonexistent", "reason", project_name="test_project")
        assert result['archived'] is False


# T016: memory_promote
class TestMemoryPromote:
    def test_promote_from_project_memory(self, monkeypatch, tmp_path):
        """从项目记忆文件升格到全局"""
        _setup_memory_main(monkeypatch, tmp_path)
        # 创建项目记忆文件（落点与实际解析结果保持一致）
        mem_rj = memory_shadow_write._resolve_memory_rj_dir()
        with open(os.path.join(mem_rj, "promote_task_memory_20260730_143500.md"), "w", encoding="utf-8") as f:
            f.write("# 项目记忆\n内容\n")
        result = memory_shadow_write.memory_promote("promote_task", project_name="test_project")
        assert result['promoted'] is True

    def test_promote_finds_layered_memory(self, monkeypatch, tmp_path):
        """{memory_class}/{YYYYMM}/ 分层目录下的记忆也要能升格"""
        _setup_memory_main(monkeypatch, tmp_path)
        month_dir = os.path.join(memory_shadow_write._resolve_memory_rj_dir(), "decision", "202607")
        os.makedirs(month_dir, exist_ok=True)
        with open(os.path.join(month_dir, "promote_task_memory_20260730_143500.md"), "w", encoding="utf-8") as f:
            f.write("# 项目记忆\n内容\n")
        result = memory_shadow_write.memory_promote("promote_task", project_name="test_project")
        assert result['promoted'] is True

    def test_promote_no_file(self, monkeypatch, tmp_path):
        """无项目记忆文件应失败"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_promote("nonexistent_task", project_name="test_project")
        assert result['promoted'] is False


# T017: memory_demote
class TestMemoryDemote:
    def test_demote_marks_flag(self, monkeypatch, tmp_path):
        """降级应标记 demoted + 原因"""
        fake_global = _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_demote("test_task", "项目降级", project_name="test_project")
        assert result['demoted'] is True
        with open(fake_global, "r", encoding="utf-8") as f:
            content = f.read()
        assert "**状态**: demoted" in content
        assert "**归档原因**: 项目降级" in content

    def test_demote_empty_reason_fails(self, monkeypatch, tmp_path):
        """空降级原因应失败"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_demote("test_task", "", project_name="test_project")
        assert result['demoted'] is False

    def test_demote_not_found(self, monkeypatch, tmp_path):
        """未找到条目应失败"""
        _setup_memory_main(monkeypatch, tmp_path)
        result = memory_shadow_write.memory_demote("nonexistent", "reason", project_name="test_project")
        assert result['demoted'] is False

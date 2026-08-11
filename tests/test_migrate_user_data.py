#!/usr/bin/env python3
"""tests/test_migrate_user_data.py - migrate_user_data 迁移测试（9 用例）。

覆盖场景（按 task.md T004 要求）：
1. test_migrate_success：正常迁移 + HIGH-003 方向B 验证（report 不含 cleanup 字段）
2. test_skip_no_source：包内无数据 → skip_no_source
3. test_skip_target_not_empty：外置非空 → skip_target_not_empty
4. test_atomic_interrupt：mock copytree 抛 OSError → failed_rolled_back + 包内保留 + 外置清理 + 锁释放
5. test_migrated_marker：迁移后 .migrated 标记含时间戳/文件数/字节数
6. test_cleanup_legacy：.migrated 超 7 天 → 清理包内 + 写 .cleaned + 删 .migrated（cycle 5 LOW-6 验证）
7. test_concurrent_lock：_acquire_lock 失败 → skip_lock_busy + HIGH-001 锁可重用 + MEDIUM-001 锁文件残留
8. test_verify_mismatch_rollback：mock _count_files 不一致 → 删外置 + failed_verify_mismatch
9. test_rollback_within_retention：迁移后删外置 + 删 .migrated → 重新迁移成功

设计原则：
- 用 tmp_path 创建模拟 skill 包结构 + 模拟外置目录，不污染真实 ~/.pdca-skill/
- monkeypatch 改 LOCK_FILE/CONFIG_FILE/DEFAULT_DATA_DIR 路径到 tmp_path
- mock time.sleep 避免 skip_lock_busy 测试等待 5 秒
- 每个测试独立隔离，不依赖执行顺序
"""
import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta

import pytest

# 确保 scripts/ 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import user_data_path  # noqa: E402
import migrate_user_data  # noqa: E402


# ---------------------------------------------------------------------------
# 辅助 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def isolate_paths(tmp_path, monkeypatch):
    """隔离路径常量到 tmp_path，避免污染真实 ~/.pdca-skill/。

    - 删除 PDCA_DATA_DIR 环境变量
    - Path.home 改为 tmp_path（_check_path_safety 用 is_relative_to(home) 校验）
    - DEFAULT_DATA_DIR 改为 tmp_path/data
    - CONFIG_FILE 改为 tmp_path/config.json
    - migrate_user_data.LOCK_FILE 改为 tmp_path/.migrate.lock
    """
    monkeypatch.delenv("PDCA_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    mock_default = tmp_path / "data"
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", mock_default)
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(migrate_user_data, "LOCK_FILE", tmp_path / ".migrate.lock")
    # 重置模块级 _lock_fd，防止上一测试残留
    migrate_user_data._lock_fd = None
    return tmp_path


def create_skill_with_data(skill_root: Path):
    """构造模拟 skill 包结构（含用户数据）。

    创建：
    - memory/memory_main.md（含测试内容）
    - docs_rj/SUMMARY_RJ.md
    - docs_rj/spec_rj/test_spec.md
    - server_lite_data/knowledge_data.json
    """
    for sub in ["memory", "docs_rj", "docs_rj/spec_rj", "server_lite_data"]:
        (skill_root / sub).mkdir(parents=True, exist_ok=True)

    (skill_root / "memory" / "memory_main.md").write_text(
        "# 全局聚合记忆\n\n## test-project\n\n- 测试数据\n", encoding="utf-8"
    )
    (skill_root / "docs_rj" / "SUMMARY_RJ.md").write_text(
        "# SUMMARY\n", encoding="utf-8"
    )
    (skill_root / "docs_rj" / "spec_rj" / "test_spec.md").write_text(
        "# 测试 spec\n", encoding="utf-8"
    )
    (skill_root / "server_lite_data" / "knowledge_data.json").write_text(
        json.dumps({"key": "value"}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# ① test_migrate_success：正常迁移 + HIGH-003 方向B 验证
# ---------------------------------------------------------------------------

def test_migrate_success(isolate_paths):
    """正常迁移：包内有数据 + 外置为空 → success + .migrated 标记 + report 不含 cleanup 字段。

    HIGH-003 方向B 验证：_cleanup_legacy 改由 startup_tidy 独立调用，
    migrate_if_needed 报告**不含** cleanup 字段（与 migrate_if_needed 解耦）。

    GWT:
    - Given 包内有 memory/ docs_rj/ server_lite_data/ 数据，外置目录为空
    - When 调用 migrate_if_needed(skill_root)
    - Then status=success + 包内有 .migrated 标记 + report 不含 cleanup 字段
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    report = migrate_user_data.migrate_if_needed(str(skill_root))

    assert report["status"] == "success"
    assert report["file_count"] > 0
    assert report["bytes"] > 0
    assert "target" in report and report["target"]
    assert "timestamp" in report

    # HIGH-003 方向B 验证：report 不含 cleanup 字段
    assert "cleanup" not in report, "migrate_if_needed 报告不应含 cleanup 字段（HIGH-003 方向B：与 _cleanup_legacy 解耦）"

    # 包内有 .migrated 标记
    marker = skill_root / migrate_user_data.MIGRATED_MARKER
    assert marker.exists(), "包内应有 .migrated 标记"
    marker_data = json.loads(marker.read_text(encoding="utf-8"))
    assert "migrated_at" in marker_data
    assert "file_count" in marker_data
    assert "bytes" in marker_data

    # 外置目录有数据
    target = Path(report["target"])
    assert (target / "memory" / "memory_main.md").exists()
    assert (target / "docs_rj" / "SUMMARY_RJ.md").exists()
    assert (target / "server_lite_data" / "knowledge_data.json").exists()

    # 锁已释放
    assert migrate_user_data._lock_fd is None


# ---------------------------------------------------------------------------
# ② test_skip_no_source：包内无数据 → skip_no_source
# ---------------------------------------------------------------------------

def test_skip_no_source(isolate_paths):
    """包内无用户数据 → skip_no_source（新用户首次启动）。

    GWT:
    - Given 包内无 memory/ docs_rj/ outputs_rj/ server_lite_data/ 数据
    - When 调用 migrate_if_needed(skill_root)
    - Then status=skip_no_source
    """
    skill_root = isolate_paths / "skill"
    skill_root.mkdir(parents=True, exist_ok=True)
    # 不创建任何用户数据目录

    report = migrate_user_data.migrate_if_needed(str(skill_root))

    assert report["status"] == "skip_no_source"
    assert report["file_count"] == 0
    assert report["bytes"] == 0

    # 无 .migrated 标记
    assert not (skill_root / migrate_user_data.MIGRATED_MARKER).exists()

    # 锁已释放
    assert migrate_user_data._lock_fd is None


# ---------------------------------------------------------------------------
# ③ test_skip_target_not_empty：外置非空 → skip_target_not_empty
# ---------------------------------------------------------------------------

def test_skip_target_not_empty(isolate_paths):
    """外置目录已有数据 → skip_target_not_empty（不覆盖）。

    GWT:
    - Given 包内有数据 + 外置目录已有数据
    - When 调用 migrate_if_needed(skill_root)
    - Then status=skip_target_not_empty（不覆盖外置数据）
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # 外置目录预置数据（模拟已迁移过）
    target = user_data_path.get_user_data_dir(ensure_subdirs=False)
    target.mkdir(parents=True, exist_ok=True)
    (target / "existing_file.txt").write_text("已存在数据", encoding="utf-8")

    report = migrate_user_data.migrate_if_needed(str(skill_root))

    assert report["status"] == "skip_target_not_empty"

    # 外置原有数据未被覆盖
    assert (target / "existing_file.txt").exists()
    assert (target / "existing_file.txt").read_text(encoding="utf-8") == "已存在数据"

    # 包内数据保留（未被清理）
    assert (skill_root / "memory" / "memory_main.md").exists()

    # 锁已释放
    assert migrate_user_data._lock_fd is None


# ---------------------------------------------------------------------------
# ④ test_atomic_interrupt：mock copytree 抛 OSError → failed_rolled_back + 锁释放
# ---------------------------------------------------------------------------

def test_atomic_interrupt(isolate_paths, monkeypatch):
    """模拟迁移中断：mock shutil.copytree 抛 OSError → failed_rolled_back + 包内保留 + 外置清理 + 锁释放。

    GWT:
    - Given 包内有数据，迁移过程中 mock shutil.copytree 抛 OSError
    - When 调用 migrate_if_needed(skill_root)
    - Then status=failed_rolled_back + 包内原件保留 + 外置半成品清理 + 锁释放
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # mock shutil.copytree 抛 OSError（模拟磁盘满/权限错误中断）
    def mock_copytree(src, dst, **kwargs):
        raise OSError("模拟磁盘满中断")
    monkeypatch.setattr(migrate_user_data.shutil, "copytree", mock_copytree)

    report = migrate_user_data.migrate_if_needed(str(skill_root))

    assert report["status"] == "failed_rolled_back"
    assert "模拟磁盘满中断" in report["error"]

    # 包内原件保留（中断不丢数据）
    assert (skill_root / "memory" / "memory_main.md").exists()
    assert (skill_root / "docs_rj" / "SUMMARY_RJ.md").exists()

    # 外置半成品已清理（rmtree）
    target = user_data_path.get_user_data_dir(ensure_subdirs=False)
    if target.exists():
        # 目录可能存在但应为空（半成品已 rmtree）
        remaining_files = list(target.rglob("*"))
        assert len(remaining_files) == 0, "外置目录应为空（半成品已清理），实际剩余: %s" % remaining_files

    # 无 .migrated 标记（迁移未成功）
    assert not (skill_root / migrate_user_data.MIGRATED_MARKER).exists()

    # 锁已释放（finally 块）
    assert migrate_user_data._lock_fd is None


# ---------------------------------------------------------------------------
# ⑤ test_migrated_marker：.migrated 标记含时间戳/文件数/字节数
# ---------------------------------------------------------------------------

def test_migrated_marker(isolate_paths):
    """迁移后包内有 .migrated 标记 + JSON 含时间戳/文件数/字节数。

    GWT:
    - Given 包内有数据，外置为空
    - When 调用 migrate_if_needed(skill_root)
    - Then .migrated 标记存在 + JSON 含 migrated_at（ISO 格式）+ file_count + bytes
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    report = migrate_user_data.migrate_if_needed(str(skill_root))
    assert report["status"] == "success"

    marker = skill_root / migrate_user_data.MIGRATED_MARKER
    assert marker.exists()

    marker_data = json.loads(marker.read_text(encoding="utf-8"))

    # 时间戳是 ISO 格式（可 fromisoformat 解析）
    migrated_at = datetime.fromisoformat(marker_data["migrated_at"])
    assert isinstance(migrated_at, datetime)

    # 文件数 + 字节数与 report 一致
    assert marker_data["file_count"] == report["file_count"]
    assert marker_data["bytes"] == report["bytes"]
    assert marker_data["file_count"] > 0
    assert marker_data["bytes"] > 0


# ---------------------------------------------------------------------------
# ⑥ test_cleanup_legacy：.migrated 超 7 天 → 清理 + .cleaned + 删 .migrated
# ---------------------------------------------------------------------------

def test_cleanup_legacy(isolate_paths):
    """ .migrated 超 7 天 → 清理包内 + 写 .cleaned + 删 .migrated（cycle 5 LOW-6 验证）。

    GWT:
    - Given 包内有数据 + .migrated 标记时间为 8 天前
    - When 调用 _cleanup_legacy(skill_root)
    - Then status=cleaned + 包内 memory/docs_rj 已删 + .cleaned 标记存在 + .migrated 已删
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # 写 8 天前的 .migrated 标记（超 7 天回滚窗口）
    old_time = (datetime.now() - timedelta(days=8)).isoformat()
    marker = skill_root / migrate_user_data.MIGRATED_MARKER
    marker.write_text(
        json.dumps({"migrated_at": old_time, "file_count": 4, "bytes": 200}),
        encoding="utf-8"
    )

    report = migrate_user_data._cleanup_legacy(str(skill_root))

    assert report["status"] == "cleaned"

    # 包内用户数据已清理
    assert not (skill_root / "memory").exists()
    assert not (skill_root / "docs_rj").exists()
    assert not (skill_root / "server_lite_data").exists()

    # .cleaned 标记存在（清理完成证据）
    assert (skill_root / migrate_user_data.CLEANED_MARKER).exists()

    # .migrated 标记已删（cycle 5 LOW-6 修复：清理流程完结后删除）
    assert not marker.exists(), ".migrated 标记应已删除（cycle 5 LOW-6 修复）"

    # .cleaning 标记已删（清理完成后清理中标记应删除）
    assert not (skill_root / migrate_user_data.CLEANING_MARKER).exists()


# ---------------------------------------------------------------------------
# ⑦ test_concurrent_lock：_acquire_lock 失败 → skip_lock_busy + 锁可重用 + 锁文件残留
# ---------------------------------------------------------------------------

def test_concurrent_lock(isolate_paths, monkeypatch):
    """模拟并发迁移：_acquire_lock 失败 → skip_lock_busy + HIGH-001 锁可重用 + MEDIUM-001 锁文件残留。

    HIGH-001 验证：_release_lock 通过 os.close(_lock_fd) 真正释放锁，
    释放后可再次获取锁（原版仅 unlink 文件名不释放 fcntl/msvcrt 锁导致并发保护失效）。

    MEDIUM-001 验证：_release_lock 不 unlink 锁文件（防 TOCTOU 竞态），
    锁文件残留但 O_CREAT 可复用，不影响下次获取锁。

    GWT:
    - Given mock _acquire_lock 总返回 False（模拟另一进程持锁）
    - When 调用 migrate_if_needed(skill_root)
    - Then status=skip_lock_busy
    - And 恢复 mock 后 _acquire_lock 能成功 + _release_lock 后能再成功 + 锁文件残留
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # mock time.sleep 避免等待 5 秒
    monkeypatch.setattr(migrate_user_data.time, "sleep", lambda s: None)

    # mock _acquire_lock 总返回 False（模拟另一进程持锁）
    monkeypatch.setattr(migrate_user_data, "_acquire_lock", lambda: False)

    report = migrate_user_data.migrate_if_needed(str(skill_root))
    assert report["status"] == "skip_lock_busy"

    # 恢复 _acquire_lock mock
    monkeypatch.undo()

    # HIGH-001 验证：_release_lock 通过 os.close(_lock_fd) 真正释放锁
    # 获取锁 → 释放 → 再获取（验证锁可重用，原版仅 unlink 文件名锁不释放）
    assert migrate_user_data._acquire_lock() is True
    assert migrate_user_data._lock_fd is not None
    migrate_user_data._release_lock()
    assert migrate_user_data._lock_fd is None

    # 释放后能再次获取锁（HIGH-001 核心验证）
    assert migrate_user_data._acquire_lock() is True
    migrate_user_data._release_lock()

    # MEDIUM-001 验证：_release_lock 不 unlink 锁文件，锁文件残留
    assert migrate_user_data.LOCK_FILE.exists(), "锁文件应残留（MEDIUM-001：不 unlink 防 TOCTOU 竞态）"


# ---------------------------------------------------------------------------
# ⑧ test_verify_mismatch_rollback：mock _count_files 不一致 → 删外置 + failed_verify_mismatch
# ---------------------------------------------------------------------------

def test_verify_mismatch_rollback(isolate_paths, monkeypatch):
    """mock _count_files 返回不一致 → 删外置半成品 + failed_verify_mismatch。

    GWT:
    - Given 包内有数据，mock _count_files 第一次返回 (10, 1000)，第二次返回 (5, 500)
    - When 调用 migrate_if_needed(skill_root)
    - Then status=failed_verify_mismatch + 外置半成品已删 + 包内原件保留
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # mock _count_files 返回不一致（src_count=10, dst_count=5）
    call_count = [0]
    def mock_count(base, dirs):
        call_count[0] += 1
        if call_count[0] == 1:
            return (10, 1000)  # src 统计
        return (5, 500)  # dst 统计（不一致）
    monkeypatch.setattr(migrate_user_data, "_count_files", mock_count)

    report = migrate_user_data.migrate_if_needed(str(skill_root))

    assert report["status"] == "failed_verify_mismatch"

    # 外置半成品已清理（rmtree）
    target = user_data_path.get_user_data_dir(ensure_subdirs=False)
    if target.exists():
        remaining_files = list(target.rglob("*"))
        assert len(remaining_files) == 0, "外置目录应为空（半成品已清理），实际剩余: %s" % remaining_files

    # 包内原件保留
    assert (skill_root / "memory" / "memory_main.md").exists()

    # 无 .migrated 标记（校验失败不算迁移成功）
    assert not (skill_root / migrate_user_data.MIGRATED_MARKER).exists()

    # 锁已释放
    assert migrate_user_data._lock_fd is None


# ---------------------------------------------------------------------------
# ⑨ test_rollback_within_retention：迁移后删外置 + 删 .migrated → 重新迁移成功
# ---------------------------------------------------------------------------

def test_rollback_within_retention(isolate_paths):
    """迁移后删外置 + 删 .migrated → 重启重新迁移成功（7 天保留期内回滚）。

    GWT:
    - Given 第一次迁移成功 → 删外置数据 + 删 .migrated 标记（模拟用户手动回滚）
    - When 第二次调用 migrate_if_needed(skill_root)
    - Then status=success（重新迁移成功，包内数据仍在）
    """
    skill_root = isolate_paths / "skill"
    create_skill_with_data(skill_root)

    # 第一次迁移
    report1 = migrate_user_data.migrate_if_needed(str(skill_root))
    assert report1["status"] == "success"

    target = Path(report1["target"])
    assert (target / "memory" / "memory_main.md").exists()

    # 模拟用户手动回滚：删外置数据 + 删 .migrated 标记
    shutil.rmtree(target, ignore_errors=True)
    marker = skill_root / migrate_user_data.MIGRATED_MARKER
    marker.unlink()
    assert not marker.exists()
    assert not target.exists()

    # 第二次迁移（重新迁移成功）
    report2 = migrate_user_data.migrate_if_needed(str(skill_root))
    assert report2["status"] == "success"
    assert report2["file_count"] == report1["file_count"]
    assert report2["bytes"] == report1["bytes"]

    # .migrated 标记重新写入
    assert marker.exists()

    # 外置数据恢复
    assert (target / "memory" / "memory_main.md").exists()
    assert (target / "docs_rj" / "SUMMARY_RJ.md").exists()
    assert (target / "server_lite_data" / "knowledge_data.json").exists()

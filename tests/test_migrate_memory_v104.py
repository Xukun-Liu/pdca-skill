"""migrate_memory_v104.py 单元测试（T004）：三格式解析/归类落盘/对账/幂等。"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import migrate_memory_v104 as mig  # noqa: E402


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    """把迁移脚本的全部数据路径指到 tmp_path，隔离真实用户数据目录。"""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    legacy = memory_dir / "legacy_body"
    docs_rj = tmp_path / "docs_rj"
    memory_rj = docs_rj / "memory_rj"
    memory_rj.mkdir(parents=True)

    global_memory = memory_dir / "memory_main.md"
    global_memory.write_text(
        "# 主记忆\n\n"
        "## proj_alpha\n\n"
        "### 记忆条目 · fix_bug（2026-08-20 10:00）\n"
        "**重要性**: high\n"
        "**是否经验**: true\n"
        "**经验标签**: bugfix, sandbox_workaround\n"
        "**状态**: active\n\n"
        "沙箱拦截 mkstemp 的坑：改用 open() 直写。\n\n"
        "### 记忆条目 · fix_bug（2026-08-21 11:00）\n"
        "**重要性**: medium\n"
        "**是否经验**: false\n"
        "**经验标签**: 无\n"
        "**状态**: active\n\n"
        "第二轮修复完成，用了分层架构设计。\n\n"
        "### 记忆条目 · weekly_check（2026-08-22 09:00）\n"
        "**重要性**: low\n"
        "**是否经验**: false\n"
        "**经验标签**: 无\n\n"
        "巡检任务，4 项无变动。\n\n"
        "## proj_beta\n\n"
        "- **2026-08-01 19:07** | 摘要式条目：改写推文方向\n",
        encoding="utf-8",
    )
    # 扁平 memory_rj 文件（应被物理迁移到深层）
    (memory_rj / "alpha_memory_20260819_1000.md").write_text(
        "### 记忆条目 · alpha（2026-08-19 10:00）\n**经验标签**: 无\n\n安装配置记录。\n",
        encoding="utf-8",
    )
    (memory_rj / "TASK_STATE_alpha.md").write_text("task: alpha\nstatus: completed\n",
                                                   encoding="utf-8")  # 不迁（留原地）

    monkeypatch.setattr(mig, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mig, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(mig, "GLOBAL_MEMORY", global_memory)
    monkeypatch.setattr(mig, "LEGACY_BODY", legacy)
    monkeypatch.setattr(mig, "SCHEMA_FILE", tmp_path / ".schema_version")
    import user_data_path
    monkeypatch.setattr(user_data_path, "get_memory_rj_path",
                        lambda: memory_rj)
    return {"tmp": tmp_path, "memory_rj": memory_rj, "legacy": legacy,
            "global": global_memory, "schema": tmp_path / ".schema_version"}


def test_migrate_three_formats_and_reconcile(isolated_data):
    """三种格式（完整式×3 + 一行摘要式×1）全部迁移，对账相等。"""
    report = mig.migrate()
    assert not report.get("errors"), report.get("errors")
    assert report["before_total"] == 4
    assert report["reconcile"]["equal"] is True
    assert report["reconcile"]["legacy_body_actual_files"] == 4
    # 归类：两条 fix_bug 的 task 名含 "bug"（强 pitfall 信号）→ 都归 pitfall；
    # "巡检"→ status；摘要式兜底 workflow
    assert report["tag_counts"]["pitfall"] == 2
    assert report["tag_counts"]["status"] == 1
    assert report["tag_counts"]["workflow"] == 1
    # memory_main 重建为纯索引（无 ### 完整条目残留）
    content = isolated_data["global"].read_text(encoding="utf-8")
    assert "### 记忆条目" not in content
    idx_lines = [l for l in content.split("\n") if l.startswith("- ")]
    assert len(idx_lines) == 4
    assert all("[正文](file:///" in l for l in idx_lines)
    # legacy_body 文件夹结构 {tag}/{YYYYMM}/
    assert (isolated_data["legacy"] / "pitfall" / "202608").is_dir()
    # schema_version 写入
    sv = json.loads(isolated_data["schema"].read_text(encoding="utf-8"))
    assert sv["structure"] == "tag_folder_monthly"
    assert sv["entries"] == 4


def test_migrate_moves_flat_memory_rj_files(isolated_data):
    """扁平 *_memory_*.md 物理迁到 {tag}/{YYYYMM}/，TASK_STATE 留原地。"""
    report = mig.migrate()
    assert report["moved_flat_files"] == 1
    # 深层出现（内容含"安装/配置"→ tool_usage）
    deep = list(isolated_data["memory_rj"].rglob("alpha_memory_20260819_1000.md"))
    assert len(deep) == 1
    assert deep[0].parent.parent.name == "tool_usage"
    assert deep[0].parent.name == "202608"
    # 扁平根目录不再有该文件；TASK_STATE 保留
    assert not (isolated_data["memory_rj"] / "alpha_memory_20260819_1000.md").exists()
    assert (isolated_data["memory_rj"] / "TASK_STATE_alpha.md").exists()


def test_migrate_idempotent_rerun(isolated_data):
    """重跑幂等：schema 已标记 → already_migrated 跳过，不重复迁移。"""
    first = mig.migrate()
    assert first["reconcile"]["equal"] is True
    second = mig.migrate()
    assert second.get("already_migrated") is True
    # 索引行数不变
    content = isolated_data["global"].read_text(encoding="utf-8")
    idx = [l for l in content.split("\n") if l.startswith("- ")]
    assert len(idx) == 4


def test_migrate_backups_created(isolated_data):
    """双备份存在：memory_main.md.bak_v103 + memory_rj_backup_v103/。"""
    mig.migrate()
    assert (isolated_data["tmp"] / "memory" / "memory_main.md.bak_v103").is_file()
    assert (isolated_data["tmp"] / "docs_rj" / "memory_rj_backup_v103").is_dir()

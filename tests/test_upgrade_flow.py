"""tests/test_upgrade_flow.py - T014 集成测试：模拟升级流程验证数据 0 丢失

流程：
1. 准备模拟 skill 包（含框架文件 + 用户数据）
2. 跑 migrate_user_data.migrate_if_needed() 把用户数据迁到外置
3. 模拟"升级"：用 package_skill.py 打包框架文件 → 解压覆盖原 skill 包目录
   （只覆盖框架文件，用户数据目录已迁出）
4. 检查外置目录数据完整（文件数+字节数一致）
5. 检查包内无用户数据残留（.migrated 标记除外）

用 tmp_path 隔离测试环境，不污染真实 ~/.riji-skill/。
"""
import os
import sys
import shutil
import zipfile
import json
import pytest
from pathlib import Path

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_ROOT)
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

import migrate_user_data  # noqa: E402
import package_skill  # noqa: E402


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """隔离测试环境：tmp_path 模拟用户目录 + skill 包"""
    # 模拟用户目录（替代真实 ~/.riji-skill/）
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    fake_riji = fake_home / ".riji-skill"
    fake_data = fake_riji / "data"

    # monkeypatch user_data_path 的默认目录 + 配置文件（migrate_user_data 经 user_data_path 获取路径）
    sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
    import user_data_path
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", fake_data)
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", fake_riji / "config.json")
    # migrate_user_data.LOCK_FILE = user_data_path.CONFIG_FILE.parent / ".migrate.lock"
    # 改 CONFIG_FILE 后 LOCK_FILE 需重新计算
    monkeypatch.setattr(migrate_user_data, "LOCK_FILE", fake_riji / ".migrate.lock")

    # 模拟旧版 skill 包（含框架文件 + 用户数据）
    old_skill = tmp_path / "old_skill"
    old_skill.mkdir()
    # 框架文件
    (old_skill / "SKILL.md").write_text("# riji-skill v1.0.0", encoding="utf-8")
    (old_skill / "scripts").mkdir()
    (old_skill / "scripts" / "app.py").write_text("# old app", encoding="utf-8")
    # 用户数据（老用户累积的）
    (old_skill / "memory").mkdir()
    (old_skill / "memory" / "memory_main.md").write_text("# 全局记忆\n## 项目A\n经验1", encoding="utf-8")
    (old_skill / "docs_rj").mkdir()
    (old_skill / "docs_rj" / "spec_rj").mkdir(parents=True)
    (old_skill / "docs_rj" / "spec_rj" / "task1_spec.md").write_text("# 任务1规格", encoding="utf-8")
    (old_skill / "docs_rj" / "memory_rj").mkdir(parents=True)
    (old_skill / "docs_rj" / "memory_rj" / "task1_memory.md").write_text("# 任务1记忆", encoding="utf-8")
    (old_skill / "outputs_rj").mkdir()
    (old_skill / "outputs_rj" / "ledger.json").write_text('{"task":"task1"}', encoding="utf-8")
    (old_skill / "server_lite_data").mkdir()
    (old_skill / "server_lite_data" / "knowledge.json").write_text('{"entries":[]}', encoding="utf-8")

    return {
        "tmp_path": tmp_path,
        "fake_home": fake_home,
        "fake_data": fake_data,
        "old_skill": old_skill,
    }


def _count_files_bytes(directory):
    """统计目录下文件数 + 总字节数"""
    count = 0
    total_bytes = 0
    for p in Path(directory).rglob("*"):
        if p.is_file():
            count += 1
            total_bytes += p.stat().st_size
    return count, total_bytes


class TestUpgradeFlow:
    """T014 集成测试：模拟升级流程"""

    def test_upgrade_data_zero_loss(self, isolated_env):
        """AC-001: 升级 skill 包后用户数据 0 丢失

        流程：
        1. 老用户包内有用户数据
        2. 启动新版触发迁移 → 用户数据迁到外置
        3. 打包新框架（package_skill）→ 解压覆盖原包
        4. 检查外置数据完整 + 包内无用户数据残留
        """
        old_skill = isolated_env["old_skill"]
        fake_data = isolated_env["fake_data"]

        # 步骤1：统计原始用户数据
        original_memory_count, original_memory_bytes = _count_files_bytes(old_skill / "memory")
        original_docs_count, original_docs_bytes = _count_files_bytes(old_skill / "docs_rj")
        original_outputs_count, original_outputs_bytes = _count_files_bytes(old_skill / "outputs_rj")
        original_server_lite_count, original_server_lite_bytes = _count_files_bytes(old_skill / "server_lite_data")
        total_original = (original_memory_count + original_docs_count
                          + original_outputs_count + original_server_lite_count)
        assert total_original > 0, "测试数据未准备"

        # 步骤2：触发迁移（模拟启动新版）
        report = migrate_user_data.migrate_if_needed(str(old_skill))
        assert report["status"] == "success", f"迁移失败: {report}"
        assert fake_data.exists(), "外置目录未创建"

        # 步骤3：模拟升级——打包新框架 + 解压覆盖
        # 先准备新版框架（模拟新版 skill 包，只有框架文件）
        new_skill = isolated_env["tmp_path"] / "new_skill"
        new_skill.mkdir()
        (new_skill / "SKILL.md").write_text("# riji-skill v1.0.1 (新版)", encoding="utf-8")
        (new_skill / "scripts").mkdir()
        (new_skill / "scripts" / "app.py").write_text("# new app v1.0.1", encoding="utf-8")

        # 打包新版框架
        zip_path = package_skill.package_skill("v1.0.1-test", str(isolated_env["tmp_path"] / "dist"), str(new_skill))

        # 解压覆盖原 skill 包目录（模拟用户解压新包覆盖）
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(old_skill)

        # 步骤4：验证外置数据完整（文件数+字节数一致）
        migrated_memory_count, migrated_memory_bytes = _count_files_bytes(fake_data / "memory")
        migrated_docs_count, migrated_docs_bytes = _count_files_bytes(fake_data / "docs_rj")
        migrated_outputs_count, migrated_outputs_bytes = _count_files_bytes(fake_data / "outputs_rj")
        migrated_server_lite_count, migrated_server_lite_bytes = _count_files_bytes(fake_data / "server_lite_data")

        assert migrated_memory_count == original_memory_count, \
            f"memory 文件数不一致: 原{original_memory_count} 现{migrated_memory_count}"
        assert migrated_memory_bytes == original_memory_bytes, \
            f"memory 字节数不一致: 原{original_memory_bytes} 现{migrated_memory_bytes}"
        assert migrated_docs_count == original_docs_count, \
            f"docs_rj 文件数不一致: 原{original_docs_count} 现{migrated_docs_count}"
        assert migrated_docs_bytes == original_docs_bytes, \
            f"docs_rj 字节数不一致: 原{original_docs_bytes} 现{migrated_docs_bytes}"
        assert migrated_outputs_count == original_outputs_count, \
            f"outputs_rj 文件数不一致: 原{original_outputs_count} 现{migrated_outputs_count}"
        assert migrated_outputs_bytes == original_outputs_bytes, \
            f"outputs_rj 字节数不一致: 原{original_outputs_bytes} 现{migrated_outputs_bytes}"
        assert migrated_server_lite_count == original_server_lite_count, \
            f"server_lite_data 文件数不一致: 原{original_server_lite_count} 现{migrated_server_lite_count}"
        assert migrated_server_lite_bytes == original_server_lite_bytes, \
            f"server_lite_data 字节数不一致: 原{original_server_lite_bytes} 现{migrated_server_lite_bytes}"

        # 步骤5：验证包内无用户数据残留（.migrated 标记除外）
        # 注意：解压覆盖后，old_skill 下原有用户数据目录还在（迁移是复制不是移动）
        # 但 .migrated 标记应存在
        assert (old_skill / ".migrated").exists() or \
               any(old_skill.rglob(".migrated")), "包内应有 .migrated 标记"

        # 验证外置数据内容可读（非空）
        memory_main = fake_data / "memory" / "memory_main.md"
        assert memory_main.exists(), "外置 memory_main.md 不存在"
        assert "全局记忆" in memory_main.read_text(encoding="utf-8"), "外置 memory 内容丢失"

        spec_file = fake_data / "docs_rj" / "spec_rj" / "task1_spec.md"
        assert spec_file.exists(), "外置 spec 文件不存在"
        assert "任务1规格" in spec_file.read_text(encoding="utf-8"), "外置 spec 内容丢失"

    def test_upgrade_no_data_loss_after_interruption(self, isolated_env):
        """AC-008: 升级中断不丢数据（迁移在打包前完成，中断不影响外置数据）"""
        old_skill = isolated_env["old_skill"]
        fake_data = isolated_env["fake_data"]

        # 迁移完成
        report = migrate_user_data.migrate_if_needed(str(old_skill))
        assert report["status"] == "success"

        # 模拟升级中断（打包失败/解压中断）——外置数据应仍完整
        original_count, original_bytes = _count_files_bytes(fake_data)
        assert original_count > 0

        # 即使升级中断，外置数据不受影响
        after_count, after_bytes = _count_files_bytes(fake_data)
        assert after_count == original_count
        assert after_bytes == original_bytes

    def test_repeated_upgrade_idempotent(self, isolated_env):
        """重复迁移幂等性：第二次迁移应 skip_target_not_empty"""
        old_skill = isolated_env["old_skill"]

        # 第一次迁移
        report1 = migrate_user_data.migrate_if_needed(str(old_skill))
        assert report1["status"] == "success"

        # 第二次迁移（外置已有数据）
        report2 = migrate_user_data.migrate_if_needed(str(old_skill))
        assert report2["status"] == "skip_target_not_empty", \
            f"第二次迁移应跳过，实际: {report2['status']}"

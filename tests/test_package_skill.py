"""tests/test_package_skill.py - T012 打包脚本测试

验证：
1. 打包成功生成 zip
2. 排除用户数据目录（memory/ docs_rj/ outputs_rj/ server_lite_data/）
3. 排除标记文件（.migrated .cleaning .cleaned）
4. 排除 __pycache__/.pyc/.git/dist/
5. 包含框架文件（SKILL.md scripts/ references/）
6. _should_exclude 单元测试（含 server_lite/data 历史写法）
7. 打包后验证函数 _verify_package 正确检测违规
8. 边界：排除目录不存在不报错
"""
import os
import sys
import zipfile
import pytest
from pathlib import Path

# 把项目根加入 sys.path
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_ROOT)
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

import package_skill  # noqa: E402


class TestShouldExclude:
    """_should_exclude 单元测试"""

    def test_exclude_memory_dir(self):
        # memory/ 下文件默认排除
        assert package_skill._should_exclude("memory/other.md") is True
        # 但发布骨架 memory_main.md 是白名单例外（必须保留）
        assert package_skill._should_exclude("memory/memory_main.md") is False

    def test_exclude_docs_rj_dir(self):
        assert package_skill._should_exclude("docs_rj/spec_rj/test.md") is True
        # 但发布骨架 spec_main_rj.md 是白名单例外（必须保留）
        assert package_skill._should_exclude("docs_rj/spec_rj/spec_main_rj.md") is False
        assert package_skill._should_exclude("docs_rj/SUMMARY_RJ.md") is False

    def test_exclude_outputs_rj_dir(self):
        assert package_skill._should_exclude("outputs_rj/loop_ledger.json") is True

    def test_exclude_server_lite_data(self):
        assert package_skill._should_exclude("server_lite_data/knowledge.json") is True

    def test_exclude_server_lite_data_historical(self):
        """兼容历史写法 server_lite/data/"""
        assert package_skill._should_exclude("server_lite/data/knowledge.json") is True

    def test_exclude_migrated_marker(self):
        assert package_skill._should_exclude("memory/.migrated") is True
        assert package_skill._should_exclude("docs_rj/.migrated") is True

    def test_exclude_cleaning_marker(self):
        assert package_skill._should_exclude(".cleaning") is True

    def test_exclude_cleaned_marker(self):
        assert package_skill._should_exclude(".cleaned") is True

    def test_exclude_pycache(self):
        assert package_skill._should_exclude("__pycache__/foo.pyc") is True
        assert package_skill._should_exclude("scripts/__pycache__/foo.pyc") is True

    def test_exclude_pyc(self):
        assert package_skill._should_exclude("scripts/foo.pyc") is True

    def test_exclude_git(self):
        assert package_skill._should_exclude(".git/config") is True

    def test_exclude_dist(self):
        assert package_skill._should_exclude("dist/pdca-skill-v1.0.1.zip") is True

    def test_keep_skill_md(self):
        assert package_skill._should_exclude("SKILL.md") is False

    def test_keep_scripts(self):
        assert package_skill._should_exclude("scripts/user_data_path.py") is False

    def test_keep_references(self):
        assert package_skill._should_exclude("references/code_rules.md") is False

    def test_keep_server_lite_code(self):
        """server_lite/ 框架代码保留，只有 server_lite_data/ 排除"""
        assert package_skill._should_exclude("server_lite/app.py") is False
        assert package_skill._should_exclude("server_lite/static/index.html") is False


class TestPackageSkill:
    """package_skill 集成测试"""

    @pytest.fixture
    def fake_skill_root(self, tmp_path):
        """构造模拟 skill 包结构"""
        # 框架文件（应保留）
        (tmp_path / "SKILL.md").write_text("# pdca-skill", encoding="utf-8")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "user_data_path.py").write_text("# path", encoding="utf-8")
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "code_rules.md").write_text("# code", encoding="utf-8")
        (tmp_path / "server_lite").mkdir()
        (tmp_path / "server_lite" / "app.py").write_text("# app", encoding="utf-8")

        # 用户数据（应排除，但骨架文件是白名单例外）
        (tmp_path / "memory").mkdir()
        (tmp_path / "memory" / "memory_main.md").write_text("# memory skeleton", encoding="utf-8")
        (tmp_path / "memory" / "user_data.md").write_text("# user data", encoding="utf-8")
        (tmp_path / "docs_rj").mkdir()
        (tmp_path / "docs_rj" / "SUMMARY_RJ.md").write_text("# summary skeleton", encoding="utf-8")
        (tmp_path / "docs_rj" / "spec_rj").mkdir(parents=True)
        (tmp_path / "docs_rj" / "spec_rj" / "spec_main_rj.md").write_text("# spec skeleton", encoding="utf-8")
        (tmp_path / "docs_rj" / "spec_rj" / "test.md").write_text("# spec", encoding="utf-8")
        (tmp_path / "outputs_rj").mkdir()
        (tmp_path / "outputs_rj" / "loop_ledger.json").write_text("{}", encoding="utf-8")
        (tmp_path / "server_lite_data").mkdir()
        (tmp_path / "server_lite_data" / "knowledge.json").write_text("{}", encoding="utf-8")

        # 标记文件（应排除）
        (tmp_path / "memory" / ".migrated").write_text("{}", encoding="utf-8")
        (tmp_path / ".cleaning").write_text("", encoding="utf-8")
        (tmp_path / ".cleaned").write_text("", encoding="utf-8")

        # 缓存/构建产物（应排除）
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "foo.pyc").write_text("", encoding="utf-8")
        (tmp_path / "scripts" / "__pycache__").mkdir()
        (tmp_path / "scripts" / "__pycache__" / "bar.pyc").write_text("", encoding="utf-8")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "old.zip").write_text("", encoding="utf-8")

        return tmp_path

    def test_package_creates_zip(self, fake_skill_root, tmp_path):
        """打包成功生成 zip"""
        out_dir = str(tmp_path / "output")
        zip_path = package_skill.package_skill("v1.0.1-test", out_dir, str(fake_skill_root))
        assert os.path.exists(zip_path)
        assert zip_path.endswith(".zip")
        assert "v1.0.1-test" in zip_path

    def test_package_excludes_user_data(self, fake_skill_root, tmp_path):
        """排除用户数据目录"""
        out_dir = str(tmp_path / "output")
        zip_path = package_skill.package_skill("v1.0.1-test", out_dir, str(fake_skill_root))
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        # 不含用户数据（白名单骨架文件除外：memory/memory_main.md, docs_rj/SUMMARY_RJ.md, docs_rj/spec_rj/spec_main_rj.md）
        skeleton_whitelist = {
            "memory/memory_main.md",
            "docs_rj/SUMMARY_RJ.md",
            "docs_rj/spec_rj/spec_main_rj.md",
        }
        memory_files = [n for n in names if n.startswith("memory/") and n not in skeleton_whitelist]
        docs_rj_files = [n for n in names if n.startswith("docs_rj/") and n not in skeleton_whitelist]
        assert not memory_files, f"不应有 memory/ 文件，但有: {memory_files}"
        assert not docs_rj_files, f"不应有 docs_rj/ 文件，但有: {docs_rj_files}"
        # 但骨架文件应该存在
        for skeleton in skeleton_whitelist:
            assert skeleton in names, f"骨架文件应存在: {skeleton}"
        assert not any(n.startswith("outputs_rj/") for n in names)
        assert not any(n.startswith("server_lite_data/") for n in names)
        # 不含标记文件
        assert not any(n.endswith(".migrated") for n in names)
        assert not any(n.endswith(".cleaning") for n in names)
        assert not any(n.endswith(".cleaned") for n in names)
        # 不含缓存
        assert not any("__pycache__" in n for n in names)
        assert not any(n.endswith(".pyc") for n in names)
        # 不含 dist
        assert not any(n.startswith("dist/") for n in names)

    def test_package_includes_framework_files(self, fake_skill_root, tmp_path):
        """包含框架文件"""
        out_dir = str(tmp_path / "output")
        zip_path = package_skill.package_skill("v1.0.1-test", out_dir, str(fake_skill_root))
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "SKILL.md" in names
        assert "scripts/user_data_path.py" in names
        assert "references/code_rules.md" in names
        assert "server_lite/app.py" in names

    def test_verify_package_passes_for_clean_zip(self, fake_skill_root, tmp_path):
        """_verify_package 对干净 zip 返回 valid=True"""
        out_dir = str(tmp_path / "output")
        zip_path = package_skill.package_skill("v1.0.1-test", out_dir, str(fake_skill_root))
        report = package_skill._verify_package(zip_path)
        assert report["valid"] is True
        assert report["violations_count"] == 0
        assert report["total_files"] > 0

    def test_verify_package_detects_violations(self, tmp_path):
        """_verify_package 对含违规文件的 zip 返回 valid=False"""
        zip_path = str(tmp_path / "bad.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("SKILL.md", "# ok")
            # 用非白名单的 memory 文件作为违规示例（白名单文件不算违规）
            zf.writestr("memory/user_data.md", "# should be excluded")
            zf.writestr("docs_rj/spec.md", "# should be excluded")
        report = package_skill._verify_package(zip_path)
        assert report["valid"] is False
        assert report["violations_count"] == 2

    def test_package_missing_exclude_dir_no_error(self, tmp_path):
        """排除目录不存在不报错"""
        # 只有框架文件，无 memory/ docs_rj/ 等用户数据目录
        skill_root = tmp_path / "minimal"
        skill_root.mkdir()
        (skill_root / "SKILL.md").write_text("# minimal", encoding="utf-8")
        out_dir = str(tmp_path / "output")
        zip_path = package_skill.package_skill("v1.0.0", out_dir, str(skill_root))
        assert os.path.exists(zip_path)
        report = package_skill._verify_package(zip_path)
        assert report["valid"] is True

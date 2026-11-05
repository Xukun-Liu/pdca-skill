#!/usr/bin/env python3
"""tests/test_v105_docs2proj_lite.py - v1.0.4 文档回项目 + 轻量模板回归（7 用例）

映射 spec v105_docs2proj_lite_plan 验收标准：
- AC-001 空项目默认落点=项目根 ./docs_rj（外置无真实内容时）
- AC-002 外置有真实遗留（递归 *.md >0）→ 只读存档，新文档仍落项目（/check H2 修订）
- AC-003 --full 无理由 exit 2；带理由正常产重型模板
- AC-004 轻量模板行数上限（spec ≤90 / task ≤70）
- AC-005 write_project fallback 回项目 ./docs_rj/memory_rj
- AC-009 外置仅空子目录（get_user_data_dir 自动创建）不算遗留（对抗审查 H1）
- AC-010 遗留用户 + write_project → 记忆落项目、备份/回滚同落点（/check H1+H2 补盲）

设计原则（对齐 test_user_data_path.py）：
- isolate fixture 隔离 tmp_path，不污染真实 ~/.pdca-skill/
- monkeypatch Path.home / DEFAULT_DATA_DIR / CONFIG_FILE
- CLI 门禁用 subprocess 跑真实命令行，断言退出码
"""
import sys
import os
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import user_data_path  # noqa: E402
import generate_docs  # noqa: E402

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATE_DOCS = os.path.join(SKILL_ROOT, "scripts", "generate_docs.py")


@pytest.fixture
def isolate(tmp_path, monkeypatch):
    """隔离外置数据目录到 tmp_path，并 mock home 使路径安全检测通过。"""
    monkeypatch.delenv("PDCA_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """干净项目目录（无任何 docs 与标记），并 chdir 进去。"""
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    return proj


def _run_cli(proj, *args):
    """在项目目录里跑 generate_docs.py CLI（隔离 PDCA_DATA_DIR 到子进程环境）。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, GENERATE_DOCS, *args],
        cwd=str(proj), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


# ---------------------------------------------------------------------------
# AC-001：空项目 + 空外置 → 默认落点=项目根 ./docs_rj
# ---------------------------------------------------------------------------

def test_default_creation_in_project(isolate, project_dir, monkeypatch):
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    result = _run_cli(project_dir, "--task", "ac001_probe", "--type", "spec")
    assert result.returncode == 0, result.stderr
    produced = list((project_dir / "docs_rj" / "spec_rj").glob("*_spec_ac001_probe.md"))
    assert len(produced) == 1, "spec 应落在项目根 docs_rj/spec_rj/"
    external_md = list((isolate / "data").rglob("*.md"))
    assert external_md == [], "外置目录不应出现任何新增 md"


# ---------------------------------------------------------------------------
# AC-002：外置有真实遗留（*.md >0）→ 只读存档，新文档仍落项目（/check H2 修订）
# ---------------------------------------------------------------------------

def test_external_legacy_readonly_archive(isolate, project_dir, monkeypatch):
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    legacy = isolate / "data" / "docs_rj" / "spec_rj"
    legacy.mkdir(parents=True)
    legacy_file = legacy / "old_task_spec_20260101_0000.md"
    legacy_file.write_text("# legacy\n", encoding="utf-8")
    found = generate_docs.find_docs_dir(create=False)
    expect_proj = os.path.abspath("./docs_rj")
    assert os.path.normcase(found) == os.path.normcase(expect_proj), \
        "v1.0.4（H2 修订）：遗留=只读存档，find_docs_dir 仍返回项目候选，不得返回外置"
    assert legacy_file.read_text(encoding="utf-8") == "# legacy\n", "遗留存档必须原地保留"
    # 生成场景：新文档落项目，不进外置
    result = _run_cli(project_dir, "--task", "ac002_probe", "--type", "spec")
    assert result.returncode == 0, result.stderr
    assert list((project_dir / "docs_rj" / "spec_rj").glob("*_spec_ac002_probe.md")), \
        "遗留用户的新 spec 也应落项目（防 spec/task 与 memory 撕裂两处）"
    assert not list(legacy.glob("*ac002_probe*")), "外置存档不得被续写"


# ---------------------------------------------------------------------------
# AC-003：--full 无理由拒绝（exit 2）；带理由产出重型模板
# ---------------------------------------------------------------------------

def test_full_requires_reason(isolate, project_dir, monkeypatch):
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    denied = _run_cli(project_dir, "--task", "ac003_probe", "--type", "spec", "--full")
    assert denied.returncode == 2, "--full 无理由必须 exit 2"
    assert list((project_dir / "docs_rj").glob("**/*ac003_probe*")) == [], "拒绝时不得产出文件"
    allowed = _run_cli(project_dir, "--task", "ac003_probe", "--type", "spec",
                       "--full", "--full-reason", "架构级改动需全套防失败字段")
    assert allowed.returncode == 0, allowed.stderr
    produced = list((project_dir / "docs_rj" / "spec_rj").glob("*_spec_ac003_probe.md"))
    assert len(produced) == 1
    content = produced[0].read_text(encoding="utf-8")
    assert "Self-Review" in content, "--full 带理由应产出重型模板（含 Self-Review 节）"


# ---------------------------------------------------------------------------
# AC-004：轻量模板行数上限
# ---------------------------------------------------------------------------

def test_default_lite_templates():
    spec_lite = Path(SKILL_ROOT) / "assets" / "spec_template_lite.md"
    task_lite = Path(SKILL_ROOT) / "assets" / "task_template_lite.md"
    assert spec_lite.is_file() and task_lite.is_file()
    assert len(spec_lite.read_text(encoding="utf-8").splitlines()) <= 90
    assert len(task_lite.read_text(encoding="utf-8").splitlines()) <= 70


# ---------------------------------------------------------------------------
# AC-005：write_project fallback 回项目 ./docs_rj/memory_rj
# ---------------------------------------------------------------------------

def test_memory_fallback_to_project(isolate, project_dir, monkeypatch):
    import memory_shadow_write as msw
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    ext_mem = isolate / "data" / "memory"
    ext_mem.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_DIR", str(ext_mem))
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_FILE", str(ext_mem / "memory_main.md"))
    monkeypatch.setattr(msw, "_GLOBAL_CP_LOCK",
                        msw._CrossProcessLock(str(ext_mem / "memory_main.md")))
    result = msw.write_project("ac005_probe", "fallback 落点验证", project_name="v105_test_proj")
    assert result["project_ok"] is True
    assert result["fallback"] is True
    expect = os.path.abspath("./docs_rj/memory_rj")
    assert result["project_memory_dir"] == expect, \
        "fallback 应落项目 ./docs_rj/memory_rj，不得落外置"
    assert not str(isolate / "data") in result["project_memory_dir"]


# ---------------------------------------------------------------------------
# AC-009：外置仅空子目录（自动创建的骨架）不算遗留（对抗审查 H1）
# ---------------------------------------------------------------------------

def test_external_empty_subdirs_not_legacy(isolate, project_dir, monkeypatch):
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    user_data_path.get_user_data_dir()  # 自动创建 memory/docs_rj/outputs_rj/server_lite_data 空骨架
    assert (isolate / "data" / "docs_rj").is_dir(), "前置：外置 docs_rj 空骨架应已创建"
    assert user_data_path.external_docs_has_content() is False, \
        "仅空子目录不算遗留（防新项目被误路由回外置）"
    result = _run_cli(project_dir, "--task", "ac009_probe", "--type", "spec")
    assert result.returncode == 0, result.stderr
    assert list((project_dir / "docs_rj" / "spec_rj").glob("*_spec_ac009_probe.md")), \
        "空骨架外置不拦截：应落项目根"


# ---------------------------------------------------------------------------
# AC-010（/check 第2轮对抗审查 H2 补盲）：遗留用户 + write_project → 记忆落项目
# 防"同一任务 spec/task 与 memory 撕裂两处"回归
# ---------------------------------------------------------------------------

def test_legacy_user_memory_stays_in_project(isolate, project_dir, monkeypatch):
    import memory_shadow_write as msw
    monkeypatch.setenv("PDCA_DATA_DIR", str(isolate / "data"))
    legacy = isolate / "data" / "docs_rj" / "memory_rj"
    legacy.mkdir(parents=True)
    (legacy / "old_task_memory_20260101_0000.md").write_text("# legacy\n", encoding="utf-8")
    ext_mem = isolate / "data" / "memory"
    ext_mem.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_DIR", str(ext_mem))
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_FILE", str(ext_mem / "memory_main.md"))
    monkeypatch.setattr(msw, "_GLOBAL_CP_LOCK",
                        msw._CrossProcessLock(str(ext_mem / "memory_main.md")))
    result = msw.write_project("ac010_probe", "遗留用户记忆落点验证", project_name="v104_test_proj")
    assert result["project_ok"] is True
    expect = os.path.abspath("./docs_rj/memory_rj")
    assert os.path.normcase(result["project_memory_dir"]) == os.path.normcase(expect), \
        "H2：遗留用户的新记忆必须落项目，不得进外置（与 spec/task 同侧，防断链）"
    assert not list(legacy.glob("ac010_probe_*")), "外置存档不得被续写"
    # _resolve_memory_rj_dir（治理工具备份/回滚用）必须与写入同侧（H1）
    resolved = msw._resolve_memory_rj_dir()
    assert os.path.normcase(resolved) == os.path.normcase(expect), \
        "H1：备份/回滚解析必须与写入同落点"

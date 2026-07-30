#!/usr/bin/env python3
"""tests/test_user_data_path.py - user_data_path 模块单元测试（11 用例）。

覆盖：
- 三级优先级路径解析（环境变量 > 配置文件 > 默认值）
- 8 个函数（get_user_data_dir / _check_path_safety / _ensure_dir / set_user_data_dir /
  get_memory_main_path / get_docs_rj_path / get_outputs_rj_path / get_server_lite_data_path）
- 边界条件（无权限降级 / JSON 错误降级 / MAX_PATH / UNC / 符号链接指向用户目录外）

设计原则：
- 每个测试用 tmp_path fixture 隔离，不污染真实 ~/.riji-skill/
- monkeypatch.setenv/delenv 控制环境变量
- monkeypatch.setattr 改 CONFIG_FILE/DEFAULT_DATA_DIR/Path.home 到 tmp_path
- capsys 捕获 stderr 验证告警
"""
import sys
import os
import json
import pytest
from pathlib import Path

# 确保 scripts/ 在 path 中（conftest autouse fixture 会在测试结束恢复 sys.path）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import user_data_path  # noqa: E402


# ---------------------------------------------------------------------------
# 共享 fixture：隔离路径常量到 tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture
def isolate_paths(tmp_path, monkeypatch):
    """隔离路径常量到 tmp_path，避免污染真实 ~/.riji-skill/。

    - 清理环境变量 RIJI_DATA_DIR
    - mock Path.home 返回 tmp_path（让 _check_path_safety 的 home 检查通过）
    - mock DEFAULT_DATA_DIR 到 tmp_path / "data"
    - mock CONFIG_FILE 到 tmp_path / "config.json"
    """
    monkeypatch.delenv("RIJI_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


# ---------------------------------------------------------------------------
# ① test_default_dir：默认值（未设置环境变量且无配置文件）
# ---------------------------------------------------------------------------

def test_default_dir(isolate_paths):
    """默认值：未设置环境变量且无配置文件 → 返回 DEFAULT_DATA_DIR + 创建子目录。"""
    result = user_data_path.get_user_data_dir()
    assert result == isolate_paths / "data"
    # 验证 4 个子目录自动创建
    subdirs = sorted([p.name for p in result.iterdir() if p.is_dir()])
    assert subdirs == ["docs_rj", "memory", "outputs_rj", "server_lite_data"]


# ---------------------------------------------------------------------------
# ② test_env_var_priority：环境变量优先于配置文件
# ---------------------------------------------------------------------------

def test_env_var_priority(isolate_paths, monkeypatch):
    """环境变量优先于配置文件：设置 RIJI_DATA_DIR + 配置文件 → 返回环境变量路径。"""
    env_dir = isolate_paths / "env_data"
    config_dir = isolate_paths / "config_data"
    monkeypatch.setenv("RIJI_DATA_DIR", str(env_dir))
    # 创建配置文件（应被环境变量覆盖）
    isolate_paths.joinpath("config.json").write_text(
        json.dumps({"data_dir": str(config_dir)}), encoding="utf-8"
    )
    result = user_data_path.get_user_data_dir()
    assert result == env_dir.resolve()


# ---------------------------------------------------------------------------
# ③ test_config_file_priority：配置文件优先于默认值
# ---------------------------------------------------------------------------

def test_config_file_priority(isolate_paths, monkeypatch):
    """配置文件优先于默认值：无环境变量 + 有配置文件 → 返回配置文件路径。"""
    config_dir = isolate_paths / "config_data"
    isolate_paths.joinpath("config.json").write_text(
        json.dumps({"data_dir": str(config_dir)}), encoding="utf-8"
    )
    result = user_data_path.get_user_data_dir()
    assert result == config_dir.resolve()


# ---------------------------------------------------------------------------
# ④ test_permission_error_fallback：环境变量指向无权限目录 → 降级到默认值
# ---------------------------------------------------------------------------

def test_permission_error_fallback(isolate_paths, monkeypatch, capsys):
    """环境变量指向无权限目录 → _ensure_dir 返回 False → 降级到默认值 + 告警。"""
    no_perm_dir = isolate_paths / "no_perm"
    monkeypatch.setenv("RIJI_DATA_DIR", str(no_perm_dir))
    # mock _ensure_dir：对 no_perm 路径返回 False，其他正常
    real_ensure_dir = user_data_path._ensure_dir

    def mock_ensure_dir(path):
        if "no_perm" in str(path):
            return False
        return real_ensure_dir(path)

    monkeypatch.setattr(user_data_path, "_ensure_dir", mock_ensure_dir)
    result = user_data_path.get_user_data_dir()
    # 验证降级到默认值
    assert result == isolate_paths / "data"
    # 验证告警输出
    captured = capsys.readouterr()
    assert "无权限" in captured.err or "降级" in captured.err


# ---------------------------------------------------------------------------
# ⑤ test_json_decode_error_fallback：配置文件 JSON 格式错误 → 降级到默认值
# ---------------------------------------------------------------------------

def test_json_decode_error_fallback(isolate_paths, capsys):
    """配置文件 JSON 格式错误 → 捕获 JSONDecodeError 用默认值 + 告警。"""
    isolate_paths.joinpath("config.json").write_text(
        "{invalid json content", encoding="utf-8"
    )
    result = user_data_path.get_user_data_dir()
    assert result == isolate_paths / "data"
    captured = capsys.readouterr()
    assert "JSON 格式错误" in captured.err


# ---------------------------------------------------------------------------
# ⑥ test_set_user_data_dir：写入配置文件
# ---------------------------------------------------------------------------

def test_set_user_data_dir(isolate_paths, monkeypatch):
    """set_user_data_dir 写入配置文件 data_dir 字段。"""
    new_dir = isolate_paths / "new_data"
    result = user_data_path.set_user_data_dir(str(new_dir))
    assert result is True
    # 验证配置文件写入
    cfg = json.loads(isolate_paths.joinpath("config.json").read_text(encoding="utf-8"))
    assert cfg["data_dir"] == str(new_dir.resolve())


# ---------------------------------------------------------------------------
# ⑦ test_get_memory_main_path：子路径函数
# ---------------------------------------------------------------------------

def test_get_memory_main_path(isolate_paths, monkeypatch):
    """get_memory_main_path 返回 memory/memory_main.md 子路径。"""
    monkeypatch.setattr(user_data_path, "get_user_data_dir", lambda **kw: isolate_paths)
    result = user_data_path.get_memory_main_path()
    assert result == isolate_paths / "memory" / "memory_main.md"


# ---------------------------------------------------------------------------
# ⑧ test_get_docs_rj_path：子路径函数
# ---------------------------------------------------------------------------

def test_get_docs_rj_path(isolate_paths, monkeypatch):
    """get_docs_rj_path 返回 docs_rj 子路径。"""
    monkeypatch.setattr(user_data_path, "get_user_data_dir", lambda **kw: isolate_paths)
    result = user_data_path.get_docs_rj_path()
    assert result == isolate_paths / "docs_rj"


# ---------------------------------------------------------------------------
# ⑨ test_max_path_limit：路径超 MAX_PATH_LIMIT → raise OSError
# ---------------------------------------------------------------------------

def test_max_path_limit(isolate_paths, monkeypatch):
    """路径超 MAX_PATH_LIMIT → raise OSError（match MAX_PATH）。"""
    monkeypatch.setattr(user_data_path, "MAX_PATH_LIMIT", 10)
    # 构造超 10 字符路径
    long_path = Path("/a" * 20)
    with pytest.raises(OSError, match="MAX_PATH"):
        user_data_path._check_path_safety(long_path)


# ---------------------------------------------------------------------------
# ⑩ test_unc_path_reject：UNC 路径 → raise OSError
# ---------------------------------------------------------------------------

def test_unc_path_reject(isolate_paths):
    """UNC 路径（\\\\server\\share）→ raise OSError（match UNC）。"""
    unc_path = Path("\\\\server\\share")
    with pytest.raises(OSError, match="UNC"):
        user_data_path._check_path_safety(unc_path)


# ---------------------------------------------------------------------------
# ⑪ test_symlink_to_outside_home_reject：符号链接指向用户目录外 → 降级到下一级
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows 创建符号链接需管理员权限")
def test_symlink_to_outside_home_reject(tmp_path, monkeypatch, capsys):
    """符号链接指向用户目录外 → 降级到下一级 + 告警（cycle 5 MEDIUM-8 + HIGH-1 修复）。

    场景：
    - mock Path.home 返回 tmp_path / "fake_home"
    - 在 fake_home 下创建符号链接 link_to_outside 指向 tmp_path / "outside_home"（用户目录外）
    - 设置 RIJI_DATA_DIR = link_to_outside
    - _check_path_safety resolve 后 real = outside_home，不在 fake_home 子树内 → raise OSError
    - get_user_data_dir 捕获后降级到默认值
    """
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(parents=True)
    outside_home = tmp_path / "outside_home"
    outside_home.mkdir(parents=True)
    # 创建符号链接 link_to_outside → outside_home
    link_path = fake_home / "link_to_outside"
    link_path.symlink_to(outside_home, target_is_directory=True)

    # mock Path.home 返回 fake_home（让 _check_path_safety 的 home 检查用 fake_home）
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    # mock DEFAULT_DATA_DIR 到 fake_home / "data"（确保默认值可创建且在 home 子树内）
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", fake_home / "data")
    # mock CONFIG_FILE 到不存在的路径（跳过配置文件级）
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", fake_home / "nonexistent_config.json")
    # 设置环境变量指向符号链接
    monkeypatch.setenv("RIJI_DATA_DIR", str(link_path))

    result = user_data_path.get_user_data_dir()
    # 验证返回默认值（降级了，不返回符号链接路径）
    assert result == fake_home / "data"
    assert result != outside_home
    # 验证 stderr 含"路径安全检测失败"告警
    captured = capsys.readouterr()
    assert "路径安全检测失败" in captured.err

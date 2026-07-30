#!/usr/bin/env python3
"""tests/test_user_data_path_boundary.py - user_data_path 边界测试（3 用例）。

覆盖边界条件：
- 无权限告警退出（mock _ensure_dir 返回 False → raise PermissionError + 不降级包内）
- MAX_PATH 限制（构造超 260 字符路径 → raise OSError）
- UNC 路径拒绝（构造 \\\\server\\share → raise OSError）

设计原则：
- 用 monkeypatch.setattr mock _ensure_dir 和 DEFAULT_DATA_DIR
- 验证 raise + 不降级到包内（不创建 os.getcwd()/memory 等目录）
"""
import sys
import os
import pytest
from pathlib import Path

# 确保 scripts/ 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import user_data_path  # noqa: E402


# ---------------------------------------------------------------------------
# ① test_default_dir_permission_denied_raises：无权限 → raise PermissionError + 不降级包内
# ---------------------------------------------------------------------------

def test_default_dir_permission_denied_raises(tmp_path, monkeypatch):
    """mock _ensure_dir 返回 False → raise PermissionError + 不创建包内目录。

    GWT:
    - Given mock _ensure_dir 返回 False（模拟无权限）
    - When 调用 get_user_data_dir()
    - Then raise PermissionError + 不创建包内目录
    """
    # 隔离路径常量到 tmp_path
    monkeypatch.delenv("RIJI_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    mock_default = tmp_path / "data"
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", mock_default)
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", tmp_path / "nonexistent_config.json")
    # mock _ensure_dir 返回 False（模拟无权限）
    monkeypatch.setattr(user_data_path, "_ensure_dir", lambda p: False)

    # 记录测试前包内（os.getcwd()）目录列表
    cwd_before = set(os.listdir(os.getcwd()))

    # 调用 get_user_data_dir() → 应 raise PermissionError
    with pytest.raises(PermissionError, match="无法创建用户数据目录"):
        user_data_path.get_user_data_dir()

    # 验证 mock_default 目录未被创建（_ensure_dir mock 返回 False，未真正 mkdir）
    assert not mock_default.exists()
    # 验证子目录未被创建
    assert not (mock_default / "memory").exists()
    assert not (mock_default / "docs_rj").exists()
    # 验证包内（os.getcwd()）未新增 memory/ docs_rj/ 等目录（不降级到包内）
    cwd_after = set(os.listdir(os.getcwd()))
    new_dirs = cwd_after - cwd_before
    forbidden = {"memory", "docs_rj", "outputs_rj", "server_lite_data"}
    assert not (new_dirs & forbidden), "不应在包内创建用户数据目录: %s" % (new_dirs & forbidden)


# ---------------------------------------------------------------------------
# ② test_path_safety_max_path：构造超 260 字符路径 → raise OSError
# ---------------------------------------------------------------------------

def test_path_safety_max_path():
    """构造超 260 字符路径 → raise OSError（match MAX_PATH）。

    GWT:
    - Given 路径字符串长度 > MAX_PATH_LIMIT(260)
    - When 调用 _check_path_safety(long_path)
    - Then raise OSError
    """
    # 构造超 260 字符路径（300 个字符）
    long_path = Path("/" + "a" * 300)
    assert len(str(long_path)) > 260  # 确保确实超限
    with pytest.raises(OSError, match="MAX_PATH"):
        user_data_path._check_path_safety(long_path)


# ---------------------------------------------------------------------------
# ③ test_path_safety_unc：构造 UNC 路径 → raise OSError
# ---------------------------------------------------------------------------

def test_path_safety_unc():
    """构造 \\\\server\\share UNC 路径 → raise OSError（match UNC）。

    GWT:
    - Given UNC 路径 \\\\server\\share
    - When 调用 _check_path_safety(unc_path)
    - Then raise OSError
    """
    unc_path = Path("\\\\server\\share")
    with pytest.raises(OSError, match="UNC"):
        user_data_path._check_path_safety(unc_path)

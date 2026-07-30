"""server_lite/api_settings.py 测试套件

T010b: 8 个测试用例覆盖路径遍历防护 + 正常流程
- GET /api/settings/data-path 正常返回
- POST /api/settings/data-path 合法路径 + 各种非法路径（..、skill 包内、系统目录、空）
- POST /api/settings/migrate 合法 target + 路径遍历拦截

设计要点：
- fixture 用 tmp_path 隔离 + monkeypatch Path.home 返回 tmp_path
  （使 _validate_path 的"必须在用户目录下"检查通过）
- monkeypatch user_data_path.CONFIG_FILE/DEFAULT_DATA_DIR/get_user_data_dir 指向 tmp_path
- test_migrate_success 用 monkeypatch migrate_user_data.migrate_if_needed 返回 mock success
"""
import os
import sys
import pytest
from pathlib import Path

# 把 riji-skill-public v1.0 加入 sys.path
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)

# 把 scripts/ 目录加入 sys.path，以便 import user_data_path / migrate_user_data
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  T010b: 测试需 monkeypatch user_data_path 函数
import migrate_user_data  # noqa: E402  T010b: 测试需 monkeypatch migrate_if_needed

from server_lite.app import create_app


@pytest.fixture
def app(monkeypatch, tmp_path):
    """隔离测试环境：tmp_path 作为用户目录 + 数据目录

    T010b: monkeypatch Path.home 返回 tmp_path，使 _validate_path 的"必须在用户目录下"检查通过。
    monkeypatch user_data_path.CONFIG_FILE/DEFAULT_DATA_DIR/get_user_data_dir 指向 tmp_path 下的测试结构。
    """
    # monkeypatch Path.home 返回 tmp_path（classmethod 方式，Path.home() 调用传 cls）
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    # 创建测试数据目录
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # monkeypatch user_data_path 函数 + 常量
    monkeypatch.setattr(user_data_path, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(user_data_path, "DEFAULT_DATA_DIR", data_dir)
    monkeypatch.setattr(user_data_path, "get_user_data_dir", lambda: data_dir)

    app = create_app({"TESTING": True})
    yield app


@pytest.fixture
def c(app):
    return app.test_client()


class TestSettingsGetDataPath:
    """GET /api/settings/data-path"""

    def test_01_get_data_path_returns_200_with_stats(self, c):
        """GET 返回 200 + JSON 含 path/size_mb/file_count/last_modified"""
        r = c.get('/api/settings/data-path')
        assert r.status_code == 200
        data = r.get_json()
        assert 'path' in data
        assert 'size_mb' in data
        assert 'file_count' in data
        assert 'last_modified' in data
        assert isinstance(data['file_count'], int)
        assert isinstance(data['size_mb'], (int, float))


class TestSettingsSetDataPath:
    """POST /api/settings/data-path"""

    def test_02_set_data_path_success(self, c, tmp_path):
        """POST 合法路径 → 200 + 写配置成功

        合法路径条件：在 tmp_path（用户目录）下 + 父目录存在 + 不含 .. + 不指向 skill 包内 + 不指向系统目录
        """
        new_path = str(tmp_path / "new_data_dir")
        r = c.post('/api/settings/data-path', json={'path': new_path})
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'ok'
        assert data['new_path'] == new_path

    def test_03_set_data_path_traversal_rejected(self, c):
        """POST 含 .. → 400 拒绝路径遍历攻击"""
        r = c.post('/api/settings/data-path', json={'path': '../../../etc'})
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data
        assert '..' in data['error'] or '路径遍历' in data['error']

    def test_04_set_data_path_skill_root_rejected(self, c):
        """POST 指向 skill 包内 → 400 不能指向 skill 包内

        skill_root = api_settings.py 所在目录的上级 = 项目根目录
        测试文件路径：server_lite/tests/test_api_settings.py
        项目根 = Path(__file__).resolve().parent.parent.parent
        """
        skill_root = Path(__file__).resolve().parent.parent.parent
        target = str(skill_root / "some_subdir")
        r = c.post('/api/settings/data-path', json={'path': target})
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data
        assert 'skill 包内' in data['error']

    def test_05_set_data_path_system_dir_rejected(self, c):
        """POST 系统目录 → 400 不能指向系统目录

        跨平台：Windows 用 C:\\Windows，Unix 用 /etc
        """
        if sys.platform == 'win32':
            sys_dir = "C:\\Windows"
        else:
            sys_dir = "/etc"
        r = c.post('/api/settings/data-path', json={'path': sys_dir})
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data
        assert '系统目录' in data['error']

    def test_06_set_data_path_empty_rejected(self, c):
        """POST 空路径 → 400 路径不能为空"""
        r = c.post('/api/settings/data-path', json={'path': ''})
        assert r.status_code == 400
        data = r.get_json()
        assert data['error'] == '路径不能为空'


class TestSettingsMigrate:
    """POST /api/settings/migrate"""

    def test_07_migrate_success(self, c, tmp_path, monkeypatch):
        """POST /migrate 合法 target_path → 200 + 迁移报告

        mock migrate_if_needed 返回 success，验证：
        - 端点返回 200
        - JSON 含 status=success + file_count
        - migrate_if_needed 被调用（参数是 skill_root）
        """
        # 记录调用参数
        call_args = []

        def mock_migrate(skill_root):
            call_args.append(skill_root)
            return {
                "status": "success",
                "target": str(tmp_path / "migrate_target"),
                "file_count": 5,
                "bytes": 1024
            }
        monkeypatch.setattr(migrate_user_data, 'migrate_if_needed', mock_migrate)

        # 合法 target_path：在 tmp_path（用户目录）下
        target_path = str(tmp_path / "migrate_target")
        r = c.post('/api/settings/migrate', json={'target_path': target_path})
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['file_count'] == 5
        # 验证 migrate_if_needed 被调用
        assert len(call_args) == 1
        assert call_args[0] is not None  # skill_root 参数非空

    def test_08_migrate_traversal_rejected(self, c):
        """POST /migrate 含 .. → 400 拒绝路径遍历

        路径遍历在 _validate_path 阶段拦截，不会调 migrate_if_needed
        """
        r = c.post('/api/settings/migrate', json={'target_path': '../etc'})
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data
        assert '..' in data['error'] or '路径遍历' in data['error']

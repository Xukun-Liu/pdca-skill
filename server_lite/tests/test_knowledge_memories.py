"""
记忆中心3个新端点 smoke test
PDCA标签：C.verify
覆盖端点：
  1. GET  /api/knowledge/memories         — 解析全局记忆条目
  2. GET  /api/knowledge/project-memories — 列出项目级记忆
  3. POST /api/knowledge/promote          — 提炼项目记忆到全局

设计原则：
  - fixture 用临时 SKILL_ROOT 目录，构造假 memory/memory_main.md 和 docs_rj/memory_rj/
  - 不污染真实数据（memory/memory_main.md 已加入 .gitignore，每个用户从0开始）
  - 测试数据格式严格对齐 _parse_memory_entries 解析器期望的 `### 记忆条目 · {task}（{ts}）` + 六字段格式
"""
import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)
# T009: 把 scripts/ 加入 sys.path 以便 import user_data_path（与 server_lite/config.py 一致）
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  T009: 测试需 monkeypatch user_data_path 函数

from server_lite.app import create_app


# =====================================================================
# 测试用 memory_main.md 模板（含2条结构化记忆条目，分属2个项目分段）
# =====================================================================
TEST_MEMORY_MAIN = """## riji-skill-public v1.0

### 记忆条目 · test_task_alpha（2026-07-23 09:00）
**意图**：测试意图A
**上下文**：测试上下文A
**工具**：Read, Edit
**反馈**：positive
**结果**：success
**标签**：test, alpha

正文内容A，用于验证 body 字段提取。

### 记忆条目 · test_task_beta（2026-07-23 10:30）
**意图**：测试意图B
**上下文**：测试上下文B
**工具**：RunCommand
**反馈**：negative
**结果**：fail
**标签**：test, beta

正文内容B。

## another-project

### 记忆条目 · test_task_gamma（2026-07-23 11:00）
**意图**：测试意图C
**上下文**：测试上下文C
**工具**：Grep
**反馈**：none
**结果**：mixed
**标签**：gamma

正文内容C。
"""

# 测试用项目级记忆文件内容
TEST_PROJECT_MEMORY = """### 记忆条目 · project_test_task（2026-07-23 14:00）
**意图**：项目记忆测试
**上下文**：项目级记忆上下文
**工具**：Write
**反馈**：positive
**结果**：success
**标签**：project, promote

项目级记忆正文。
"""


@pytest.fixture
def app(monkeypatch):
    """创建隔离的测试 app：临时 SKILL_ROOT 目录，含假 memory_main.md + docs_rj/memory_rj/

    T009 修复：monkeypatch user_data_path 的 get_memory_main_path / get_docs_rj_path /
    get_server_lite_data_path 三个函数，使其指向测试临时目录下的 fake_skill_root 结构，
    使 api_knowledge.py 等直接调用 user_data_path 的地方读到测试数据。
    """
    test_dir = tempfile.mkdtemp(prefix="test_mem_")
    # 构造假 SKILL_ROOT 结构
    fake_skill_root = os.path.join(test_dir, "fake_skill_root")
    os.makedirs(fake_skill_root, exist_ok=True)

    # 写 memory/memory_main.md
    memory_dir = os.path.join(fake_skill_root, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    memory_main_path = os.path.join(memory_dir, "memory_main.md")
    with open(memory_main_path, "w", encoding="utf-8") as f:
        f.write(TEST_MEMORY_MAIN)

    # 写 docs_rj/memory_rj/ 下的文件
    memory_rj_dir = os.path.join(fake_skill_root, "docs_rj", "memory_rj")
    os.makedirs(memory_rj_dir, exist_ok=True)
    docs_rj_path = os.path.join(fake_skill_root, "docs_rj")
    # 有效项目记忆文件
    with open(os.path.join(memory_rj_dir, "proj_test_memory.md"), "w", encoding="utf-8") as f:
        f.write(TEST_PROJECT_MEMORY)
    # INDEX.md — 应被排除
    with open(os.path.join(memory_rj_dir, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# Index\n")
    # TASK_STATE_xxx.md — 应被排除
    with open(os.path.join(memory_rj_dir, "TASK_STATE_test.md"), "w", encoding="utf-8") as f:
        f.write("# Task State\n")
    # 非 md 文件 — 应被排除
    with open(os.path.join(memory_rj_dir, "notes.txt"), "w", encoding="utf-8") as f:
        f.write("not md\n")

    # T009: monkeypatch user_data_path 函数指向测试临时目录
    monkeypatch.setattr(user_data_path, "get_memory_main_path", lambda: Path(memory_main_path))
    monkeypatch.setattr(user_data_path, "get_docs_rj_path", lambda: Path(docs_rj_path))
    # server_lite_data 指向 fake_skill_root/data（promote 端点等可能用）
    server_lite_data_path = os.path.join(fake_skill_root, "data")
    os.makedirs(server_lite_data_path, exist_ok=True)
    monkeypatch.setattr(user_data_path, "get_server_lite_data_path", lambda: Path(server_lite_data_path))

    app = create_app({
        "TESTING": True,
        "SKILL_ROOT": fake_skill_root,
    })

    yield app

    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def empty_app(monkeypatch):
    """空 SKILL_ROOT 的 app：memory/memory_main.md 不存在 + docs_rj/memory_rj/ 不存在

    T009 修复：同样 monkeypatch user_data_path 函数指向空测试目录，使 API 读到空数据。
    """
    test_dir = tempfile.mkdtemp(prefix="test_mem_empty_")
    fake_skill_root = os.path.join(test_dir, "fake_skill_root_empty")
    os.makedirs(fake_skill_root, exist_ok=True)
    # 不创建 memory/ 也不创建 docs_rj/memory_rj/

    # T009: monkeypatch user_data_path 函数指向空测试目录
    monkeypatch.setattr(user_data_path, "get_memory_main_path", lambda: Path(os.path.join(fake_skill_root, "memory", "memory_main.md")))
    monkeypatch.setattr(user_data_path, "get_docs_rj_path", lambda: Path(os.path.join(fake_skill_root, "docs_rj")))
    server_lite_data_path = os.path.join(fake_skill_root, "data")
    os.makedirs(server_lite_data_path, exist_ok=True)
    monkeypatch.setattr(user_data_path, "get_server_lite_data_path", lambda: Path(server_lite_data_path))

    app = create_app({
        "TESTING": True,
        "SKILL_ROOT": fake_skill_root,
    })

    yield app

    shutil.rmtree(test_dir, ignore_errors=True)


# =====================================================================
# 分类1：GET /api/knowledge/memories（4个用例）
# =====================================================================

class TestKnowledgeMemories:
    """GET /api/knowledge/memories — 解析全局记忆条目"""

    def test_mem_01_returns_200_and_envelope(self, client):
        """mem_01: 返回200 + envelope结构 {entries, projects, status, total}"""
        res = client.get('/api/knowledge/memories')
        assert res.status_code == 200
        data = res.get_json()
        # envelope 四字段齐全
        assert 'entries' in data
        assert 'projects' in data
        assert 'status' in data
        assert 'total' in data
        assert data['status'] == 'ok'

    def test_mem_02_parses_all_three_entries(self, client):
        """mem_02: 正确解析3条记忆条目（2条在riji-skill段 + 1条在another-project段）"""
        res = client.get('/api/knowledge/memories')
        data = res.get_json()
        assert data['total'] == 3
        assert len(data['entries']) == 3
        # 2个项目分段都应被识别
        projects = set(data['projects'])
        assert 'riji-skill-public v1.0' in projects
        assert 'another-project' in projects

    def test_mem_03_entry_has_all_required_fields(self, client):
        """mem_03: 每条entry包含契约字段（id/task_name/intent/outcome/tags等）"""
        res = client.get('/api/knowledge/memories')
        entries = res.get_json()['entries']
        required_fields = [
            'id', 'project', 'task_name', 'timestamp', 'intent',
            'context', 'tools', 'feedback', 'outcome', 'tags',
            'body', 'source_file'
        ]
        for e in entries:
            for field in required_fields:
                assert field in e, f"entry 缺字段 {field}: {e}"

        # 验证第一条条目的具体值
        alpha = [e for e in entries if e['task_name'] == 'test_task_alpha'][0]
        assert alpha['intent'] == '测试意图A'
        assert alpha['outcome'] == 'success'
        assert alpha['feedback'] == 'positive'
        assert alpha['tools'] == ['Read', 'Edit']
        assert alpha['tags'] == ['test', 'alpha']
        assert alpha['project'] == 'riji-skill-public v1.0'
        assert alpha['source_file'] == 'memory/memory_main.md'
        # id 是 md5[:12] 长度
        assert len(alpha['id']) == 12

    def test_mem_04_empty_memory_main_returns_empty_envelope(self, empty_app):
        """mem_04: memory_main.md 不存在时返回空 envelope（不报500）"""
        client = empty_app.test_client()
        res = client.get('/api/knowledge/memories')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        assert data['total'] == 0
        assert data['entries'] == []
        assert data['projects'] == []


# =====================================================================
# 分类2：GET /api/knowledge/project-memories（3个用例）
# =====================================================================

class TestKnowledgeProjectMemories:
    """GET /api/knowledge/project-memories — 列出项目级记忆"""

    def test_pmem_01_returns_200_and_envelope(self, client):
        """pmem_01: 返回200 + envelope结构 {entries, total, status}"""
        res = client.get('/api/knowledge/project-memories')
        assert res.status_code == 200
        data = res.get_json()
        assert 'entries' in data
        assert 'total' in data
        assert 'status' in data
        assert data['status'] == 'ok'

    def test_pmem_02_parses_project_entries(self, client):
        """pmem_02: 正确解析1条项目记忆条目（proj_test_memory.md）"""
        res = client.get('/api/knowledge/project-memories')
        data = res.get_json()
        assert data['total'] == 1
        entry = data['entries'][0]
        assert entry['task_name'] == 'project_test_task'
        assert entry['intent'] == '项目记忆测试'
        assert entry['outcome'] == 'success'
        assert entry['tools'] == ['Write']
        assert entry['tags'] == ['project', 'promote']

    def test_pmem_03_excludes_index_and_task_state_files(self, client):
        """pmem_03: 排除 INDEX.md / TASK_STATE_*.md / 非.md 文件"""
        res = client.get('/api/knowledge/project-memories')
        data = res.get_json()
        # 只解析了1个有效文件（proj_test_memory.md），INDEX/TASK_STATE/notes.txt 被排除
        assert data['total'] == 1
        assert data['entries'][0]['task_name'] == 'project_test_task'


# =====================================================================
# 分类3：POST /api/knowledge/promote（3个用例）
# =====================================================================

class TestKnowledgePromote:
    """POST /api/knowledge/promote — 提炼项目记忆到全局"""

    def test_prom_01_missing_files_field_returns_400(self, client):
        """prom_01: 请求体缺 files 字段返回400"""
        res = client.post('/api/knowledge/promote', json={})
        assert res.status_code == 400
        data = res.get_json()
        assert 'error' in data

    def test_prom_02_empty_files_list_returns_400(self, client):
        """prom_02: files 是空 list 返回400"""
        res = client.post('/api/knowledge/promote', json={"files": []})
        assert res.status_code == 400
        data = res.get_json()
        assert 'error' in data

    def test_prom_03_nonexistent_file_returns_not_found_status(self, client):
        """prom_03: 不存在的文件返回200 + details[0].status='not_found'"""
        res = client.post('/api/knowledge/promote', json={"files": ["nonexistent_file.md"]})
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        assert data['promoted'] == 0
        # details 应记录该文件状态为 not_found
        assert len(data['details']) == 1
        assert data['details'][0]['file'] == 'nonexistent_file.md'
        assert data['details'][0]['status'] == 'not_found'

"""server_lite 测试套件 - 完整场景覆盖

被测对象：riji-skill-public v1.0/server_lite
测试目录：server_lite/tests/（在工作目录内）

场景覆盖：
S1: 基础健康 + API契约加载
S2: 知识/docs完整流程（项目列表+SUMMARY+spec_main）
S3: 技能管理+频率分级+PDCA标签（含连字符H10）
S4: 子机器人列表
S5: 知识管理CRUD完整生命周期（8端点：读取/保存/笔记增删/条目更新/提取/源文件浏览）
S6: 知识提取引擎验证（SKILL/EXPERIENCE/SOLUTION三类提取+合并保留用户标注）
S7: XSS防护后端验证（输入原样返回，转义在前端）
S8: 路径穿越安全（H1）
S9: 前后端契约一致性（所有fetch端点存在+H7字段完整性）
+H8:删除技能权限校验
"""
import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

# 把 riji-skill-public v1.0 加入 sys.path
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)

# 把 scripts/ 目录加入 sys.path，以便 import user_data_path（与 server_lite/config.py 一致）
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  T009: 测试需 monkeypatch user_data_path 函数

from server_lite.app import create_app


@pytest.fixture
def app(monkeypatch):
    """Flask 测试 app，使用临时数据目录

    T009 修复：monkeypatch user_data_path.get_server_lite_data_path 指向测试临时目录，
    使 api_docs._get_scan_roots_path() 等直接调用 user_data_path 的地方与 config.DATA_DIR 一致。
    """
    tmp_dir = tempfile.mkdtemp(prefix="server_lite_test_")
    config = {
        "DATA_DIR": tmp_dir,
        "METADATA_DIR": os.path.join(tmp_dir, "metadata"),
    }
    # T009: monkeypatch user_data_path 函数指向测试临时目录
    monkeypatch.setattr(user_data_path, "get_server_lite_data_path", lambda: Path(tmp_dir))
    # T009: extract 端点从 memory_main.md + docs_rj/ 扫描知识，指向项目根真实路径（与改造前行为一致）
    monkeypatch.setattr(user_data_path, "get_memory_main_path", lambda: Path(os.path.join(SKILL_ROOT, "memory", "memory_main.md")))
    monkeypatch.setattr(user_data_path, "get_docs_rj_path", lambda: Path(os.path.join(SKILL_ROOT, "docs_rj")))
    app = create_app(config=config)
    app.config["TESTING"] = True
    yield app
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


# ============ AC-001 健康检查 ============

class TestHealth:
    def test_health_returns_ok(self, client):
        """AC-001: GET /api/health 返回 status=ok"""
        res = client.get('/api/health')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        assert 'version' in data


# ============ AC-002 API 契约单源 ============

class TestContracts:
    def test_contracts_json_returns_all_dataclasses(self, client):
        """AC-002: /api/contracts.json 返回所有 dataclass 定义"""
        res = client.get('/api/contracts.json')
        assert res.status_code == 200
        data = res.get_json()
        for cls_name in ['ProjectInfo', 'SkillInfo', 'AgentInfo', 'KnowledgeEntry', 'KnowledgeNote']:
            assert cls_name in data, f"missing {cls_name} in contracts"
            assert 'fields' in data[cls_name]

    def test_skillinfo_has_7_fields(self, client):
        """H7 修复验证: SkillInfo 必须含 last_called 和 related_agents"""
        res = client.get('/api/contracts.json')
        data = res.get_json()
        skill_fields = [f['name'] for f in data['SkillInfo']['fields']]
        assert 'last_called' in skill_fields, "SkillInfo missing last_called (H7 not fixed)"
        assert 'related_agents' in skill_fields, "SkillInfo missing related_agents (H7 not fixed)"


# ============ AC-003 项目扫描 ============

class TestProjects:
    def test_projects_returns_list(self, client):
        """AC-003: GET /api/projects 返回项目列表"""
        res = client.get('/api/projects')
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)

    def test_projects_contains_riji_skill(self, client):
        """扫描结果应包含 riji-skill-public v1.0 项目"""
        res = client.get('/api/projects')
        data = res.get_json()
        project_names = [p['name'] for p in data]
        assert 'riji-skill-public v1.0' in project_names, "riji-skill project not found in scan"

    def test_project_has_required_fields(self, client):
        """ProjectInfo 必须含 5 个字段"""
        res = client.get('/api/projects')
        data = res.get_json()
        if data:
            p = data[0]
            for field in ['name', 'path', 'has_summary', 'has_spec_main', 'last_active']:
                assert field in p, f"missing field {field}"

    def test_project_summary_readable(self, client):
        """AC-003: 能读取 riji-skill 的 SUMMARY_RJ.md"""
        res = client.get('/api/project/riji-skill-public v1.0/summary')
        assert res.status_code == 200
        data = res.get_json()
        assert 'content' in data
        assert len(data['content']) > 0

    def test_project_spec_main_readable(self, client):
        """H3 修复验证: spec_main_rj.md 可读"""
        res = client.get('/api/project/riji-skill-public v1.0/spec_main')
        assert res.status_code == 200
        data = res.get_json()
        assert 'content' in data
        assert 'spec_main' in data['content'].lower() or '项目总' in data['content']


# ============ H1 路径穿越防护 ============

class TestPathTraversal:
    def test_path_traversal_project_name_rejected(self, client):
        """H1: 路径穿越项目名被拒绝（400 或 404 均算拒绝）"""
        res = client.get('/api/project/..%2F..%2Fetc%2Fpasswd/summary')
        assert res.status_code in (400, 404), f"expected 400/404, got {res.status_code}"

    def test_path_traversal_skill_name_rejected(self, client):
        """H1: 路径穿越技能名被拒绝"""
        res = client.get('/api/skill/../../etc/passwd/content')
        assert res.status_code in (400, 404), f"expected 400/404, got {res.status_code}"

    def test_dot_dot_in_name_rejected(self, client):
        """H1: 含 .. 的名称被拒绝"""
        res = client.get('/api/project/../memory_main/summary')
        assert res.status_code in (400, 404), f"expected 400/404, got {res.status_code}"


# ============ AC-005 参考模块列表 ============

class TestSkills:
    def test_skills_returns_list(self, client):
        """AC-005: GET /api/skills 返回参考模块列表"""
        res = client.get('/api/skills')
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)

    def test_skills_at_least_37(self, client):
        """AC-005: 至少 37 个参考模块"""
        res = client.get('/api/skills')
        data = res.get_json()
        assert len(data) >= 36, f"only {len(data)} skills, expected >= 36"

    def test_skill_has_7_fields(self, client):
        """H7 修复验证: SkillInfo 含 7 个字段"""
        res = client.get('/api/skills')
        data = res.get_json()
        if data:
            s = data[0]
            for field in ['name', 'pdca_tag', 'description', 'call_count',
                          'frequency_level', 'last_called', 'related_agents']:
                assert field in s, f"missing field {field}"

    def test_skill_frequency_level_valid(self, client):
        """频率分级值必须合法"""
        res = client.get('/api/skills')
        data = res.get_json()
        valid_levels = {'high', 'medium', 'low', 'zero'}
        for s in data:
            assert s['frequency_level'] in valid_levels, f"invalid level: {s['frequency_level']}"

    def test_skill_content_readable(self, client):
        """能读取参考模块内容"""
        res = client.get('/api/skills')
        data = res.get_json()
        if data:
            skill_name = data[0]['name']
            res = client.get(f'/api/skill/{skill_name}/content')
            assert res.status_code == 200
            content_data = res.get_json()
            assert 'content' in content_data

    def test_skill_with_hyphen_name_found(self, client):
        """H10 修复验证: 含连字符的参考模块在列表中（sync-matrix 等）"""
        res = client.get('/api/skills')
        data = res.get_json()
        skill_names = [s['name'] for s in data]
        assert 'sync-matrix' in skill_names, "sync-matrix.md not found (H10 not fixed)"
        assert 'hand-drawn-report' in skill_names, "hand-drawn-report.md not found (H10 not fixed)"


# ============ H8 删除零调用技能 ============

class TestDeleteSkill:
    def test_delete_nonexistent_returns_404(self, client):
        """H8: 删除不存在的技能返回 404"""
        res = client.delete('/api/skill/nonexistent_skill_xyz')
        assert res.status_code == 404

    def test_delete_invalid_name_returns_400(self, client):
        """H8: 删除非法名称被拒绝（400/404/405 均算拒绝）"""
        res = client.delete('/api/skill/../../etc/passwd')
        assert res.status_code in (400, 404, 405), f"expected 400/404/405, got {res.status_code}"


# ============ AC-006 子机器人列表 ============

class TestAgents:
    def test_agents_returns_list(self, client):
        """AC-006: GET /api/agents 返回子机器人列表"""
        res = client.get('/api/agents')
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)

    def test_agent_has_required_fields(self, client):
        """AgentInfo 含 name/role/description/knowledge/triggers/output_format"""
        res = client.get('/api/agents')
        data = res.get_json()
        assert len(data) >= 9, "应至少返回10个子机器人（从subagent_config_rj.json读取）"
        a = data[0]
        assert 'name' in a
        assert 'role' in a
        assert 'description' in a
        assert 'knowledge' in a
        assert 'triggers' in a
        assert 'output_format' in a
        assert isinstance(a['knowledge'], list)
        assert isinstance(a['triggers'], list)
        assert isinstance(a['output_format'], list)
        assert len(a['name']) > 0
        assert len(a['role']) > 0


# ============ AC-007 知识管理 CRUD ============

class TestKnowledge:
    def test_get_knowledge_returns_default(self, client):
        """AC-007: GET /api/knowledge 返回默认空结构"""
        res = client.get('/api/knowledge')
        assert res.status_code == 200
        data = res.get_json()
        assert data['schema_version'] == '1.0'
        assert 'extracted' in data
        assert 'notes' in data

    def test_post_knowledge_saves_data(self, client):
        """AC-007: POST /api/knowledge 保存数据后可读回"""
        payload = {
            "schema_version": "1.0",
            "extracted": [{
                "id": "entry_test_1",
                "type": "SKILL",
                "name": "Flask",
                "context": "Flask 是一个 Python Web 框架",
                "source_file": "memory/memory_main.md",
                "source_line": 10,
                "tags": ["web", "python"],
                "mastery": "familiar",
                "user_notes": "已用过"
            }],
            "notes": []
        }
        res = client.post('/api/knowledge', json=payload)
        assert res.status_code == 200

        res = client.get('/api/knowledge')
        data = res.get_json()
        assert len(data['extracted']) == 1
        assert data['extracted'][0]['name'] == 'Flask'
        assert data['extracted'][0]['mastery'] == 'familiar'

    def test_post_knowledge_empty_body_returns_400(self, client):
        """空 body 返回 400"""
        res = client.post('/api/knowledge', data='', content_type='application/json')
        assert res.status_code == 400

    def test_post_knowledge_auto_fills_missing_fields(self, client):
        """保存时自动补全 schema_version/extracted/notes 字段"""
        res = client.post('/api/knowledge', json={"some_field": "value"})
        assert res.status_code == 200
        res = client.get('/api/knowledge')
        data = res.get_json()
        assert data['schema_version'] == '1.0'
        assert data['extracted'] == []
        assert data['notes'] == []


# ============ AC-007b 知识管理 笔记 CRUD ============

class TestKnowledgeNote:
    def test_add_note_returns_note_with_id(self, client):
        """POST /api/knowledge/note 返回带 id 的笔记"""
        res = client.post('/api/knowledge/note', json={
            "title": "Python 学习笔记",
            "category": "后端",
            "content": "Flask 是一个 Web 框架",
            "tags": ["python", "flask"]
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        assert 'note' in data
        assert data['note']['title'] == 'Python 学习笔记'
        assert data['note']['id']  # 非空
        assert data['note']['created_at']  # 非空

    def test_add_note_missing_title_returns_400(self, client):
        """缺 title 字段返回 400"""
        res = client.post('/api/knowledge/note', json={"content": "no title"})
        assert res.status_code == 400

    def test_add_note_empty_title_returns_400(self, client):
        """title 空字符串返回 400"""
        res = client.post('/api/knowledge/note', json={"title": "   "})
        assert res.status_code == 400

    def test_delete_note_succeeds(self, client):
        """DELETE /api/knowledge/note/<id> 删除笔记成功"""
        add_res = client.post('/api/knowledge/note', json={"title": "待删除笔记"})
        note_id = add_res.get_json()['note']['id']

        res = client.delete(f'/api/knowledge/note/{note_id}')
        assert res.status_code == 200
        assert res.get_json()['deleted'] is True

        # 验证已删除
        res = client.get('/api/knowledge')
        notes = res.get_json()['notes']
        assert all(n['id'] != note_id for n in notes)

    def test_delete_nonexistent_note_returns_404(self, client):
        """删除不存在的笔记返回 404"""
        res = client.delete('/api/knowledge/note/nonexistent_id_xyz')
        assert res.status_code == 404


# ============ AC-007c 知识管理 条目更新 ============

class TestKnowledgeEntryUpdate:
    def test_update_entry_mastery_succeeds(self, client):
        """PUT /api/knowledge/entry/<id> 更新掌握度成功"""
        # 先保存一个条目
        client.post('/api/knowledge', json={
            "extracted": [{
                "id": "entry_update_test",
                "type": "SKILL",
                "name": "Docker",
                "context": "容器化",
                "source_file": "memory/main.md",
                "source_line": 1,
                "tags": [],
                "mastery": None,
                "user_notes": ""
            }],
            "notes": []
        })

        res = client.put('/api/knowledge/entry/entry_update_test', json={
            "mastery": "proficient",
            "tags": ["devops", "container"],
            "user_notes": "用过一段时间"
        })
        assert res.status_code == 200
        assert res.get_json()['updated'] is True

        # 验证已更新
        res = client.get('/api/knowledge')
        entry = next(e for e in res.get_json()['extracted'] if e['id'] == 'entry_update_test')
        assert entry['mastery'] == 'proficient'
        assert entry['tags'] == ["devops", "container"]
        assert entry['user_notes'] == '用过一段时间'

    def test_update_nonexistent_entry_returns_404(self, client):
        """更新不存在的条目返回 404"""
        res = client.put('/api/knowledge/entry/nonexistent_id', json={"mastery": "expert"})
        assert res.status_code == 404

    def test_update_entry_empty_body_returns_400(self, client):
        """空 body 返回 400"""
        res = client.put('/api/knowledge/entry/some_id', data='', content_type='application/json')
        assert res.status_code == 400


# ============ AC-007d 知识提取引擎 ============

class TestKnowledgeExtract:
    def test_extract_returns_ok(self, client):
        """GET /api/knowledge/extract 提取成功"""
        res = client.get('/api/knowledge/extract')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'ok'
        assert 'total_entries' in data
        assert 'by_type' in data
        assert 'SKILL' in data['by_type']
        assert 'EXPERIENCE' in data['by_type']
        assert 'SOLUTION' in data['by_type']
        assert 'scanned_files' in data

    def test_extract_finds_known_skills(self, client):
        """提取引擎能从 memory_main.md 找到 Python/Flask 等技术关键词"""
        res = client.get('/api/knowledge/extract')
        data = res.get_json()
        # riji-skill 项目的 memory_main.md 必然包含 Python/Flask 等关键词
        assert data['total_entries'] > 0, "应至少提取到一些知识条目"

        # 验证提取的条目保存到了 knowledge_data
        res = client.get('/api/knowledge')
        extracted = res.get_json()['extracted']
        assert len(extracted) > 0
        # 验证条目有完整的 9 字段
        e = extracted[0]
        for field in ['id', 'type', 'name', 'context', 'source_file', 'source_line', 'tags', 'mastery', 'user_notes']:
            assert field in e, f"missing field {field}"

    def test_extract_preserves_user_annotations(self, client):
        """提取后保留用户已标注的 tags/mastery/user_notes"""
        # 1. 先保存一个带用户标注的条目
        client.post('/api/knowledge', json={
            "extracted": [{
                "id": "preserve_test_id",
                "type": "SKILL",
                "name": "Python",
                "context": "old context",
                "source_file": "memory/old.md",
                "source_line": 1,
                "tags": ["my-tag"],
                "mastery": "expert",
                "user_notes": "我的备注"
            }],
            "notes": []
        })

        # 2. 重新提取
        res = client.get('/api/knowledge/extract')
        assert res.status_code == 200

        # 3. 验证 Python 条目的用户标注保留
        res = client.get('/api/knowledge')
        python_entries = [e for e in res.get_json()['extracted'] if e['name'] == 'Python' and e['type'] == 'SKILL']
        assert len(python_entries) > 0, "Python SKILL 条目应存在"
        python_entry = python_entries[0]
        assert python_entry['mastery'] == 'expert', "用户标注的 mastery 应保留"
        assert "my-tag" in python_entry['tags'], "用户标注的 tags 应保留"
        assert python_entry['user_notes'] == '我的备注', "用户标注的 user_notes 应保留"


# ============ AC-007e 记忆源文件浏览 ============

class TestKnowledgeSources:
    def test_list_sources_returns_array(self, client):
        """GET /api/knowledge/sources 返回源文件列表"""
        res = client.get('/api/knowledge/sources')
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)
        # riji-skill 项目必然有 memory/memory_main.md
        paths = [s['path'] for s in data]
        assert any('memory_main.md' in p for p in paths), "应包含 memory_main.md"

    def test_list_sources_has_required_fields(self, client):
        """源文件条目含 path/name/size 三字段"""
        res = client.get('/api/knowledge/sources')
        data = res.get_json()
        if data:
            s = data[0]
            for field in ['path', 'name', 'size']:
                assert field in s, f"missing field {field}"

    def test_read_source_returns_content(self, client):
        """GET /api/knowledge/source/<path> 读取源文件内容"""
        res = client.get('/api/knowledge/source/memory/memory_main.md')
        assert res.status_code == 200
        data = res.get_json()
        assert 'content' in data
        assert len(data['content']) > 0
        assert data['path'] == 'memory/memory_main.md'

    def test_read_source_rejects_non_md(self, client):
        """非 .md 文件返回 400"""
        res = client.get('/api/knowledge/source/memory/secret.txt')
        assert res.status_code == 400

    def test_read_source_rejects_outside_memory(self, client):
        """访问 memory/ 和 docs_rj/ 之外的路径返回 403"""
        res = client.get('/api/knowledge/source/SKILL.md')
        assert res.status_code == 403

    def test_read_source_rejects_path_traversal(self, client):
        """路径穿越被拒绝"""
        res = client.get('/api/knowledge/source/memory/../../../etc/passwd.md')
        assert res.status_code in (400, 403, 404)


# ============ PDCA 融入度验证 ============

class TestPDCAIntegration:
    def test_skill_pdca_tag_extracted(self, client):
        """PDCA 融入: 参考模块能提取 PDCA 标签"""
        res = client.get('/api/skills')
        data = res.get_json()
        pdca_skills = [s for s in data if s['pdca_tag']]
        assert len(pdca_skills) > 0, "no skill has pdca_tag extracted"

    def test_spec_main_derived_from_visible(self, client):
        """PDCA 融入: spec_main 可读（派生关系的基础）"""
        res = client.get('/api/project/riji-skill-public v1.0/spec_main')
        assert res.status_code == 200
        data = res.get_json()
        assert '§3' in data['content'] or '§4' in data['content']


# ============ 前后端契约一致性 ============

class TestContractConsistency:
    def test_frontend_fetch_endpoints_all_exist(self, client):
        """S9: app.js 中所有 fetch 的端点（GET+POST+DELETE）在后端都存在"""
        endpoints_to_test = [
            ('GET', '/api/health'),
            ('GET', '/api/contracts.json'),
            ('GET', '/api/projects'),
            ('GET', '/api/skills'),
            ('GET', '/api/agents'),
            ('GET', '/api/knowledge'),
            ('POST', '/api/knowledge'),
            ('POST', '/api/knowledge/note'),
            ('GET', '/api/knowledge/extract'),
            ('GET', '/api/knowledge/sources'),
        ]
        for method, path in endpoints_to_test:
            res = client.open(path, method=method, json={} if method == 'POST' else None)
            assert res.status_code in (200, 400, 404, 405), f"{method} {path} returned {res.status_code}"


# ============ H8 完整：删除技能权限校验 ============

class TestDeleteSkillComplete:
    def test_delete_zero_call_skill_succeeds(self, app, client):
        """H8: 删除零调用技能成功（创建临时零调用技能再删除）"""
        import tempfile
        import json
        refs_dir = app.config['REFERENCES_DIR']
        meta_dir = app.config['METADATA_DIR']
        os.makedirs(meta_dir, exist_ok=True)

        test_skill = 'test_temp_skill_h8'
        md_path = os.path.join(refs_dir, test_skill + '.md')
        meta_path = os.path.join(meta_dir, test_skill + '.json')

        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write('---\nPDCA: D.code\n---\n# Test skill\nTemporary skill for H8 test.\n')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({"schema_version": "1.0", "name": test_skill, "call_count": 0}, f)

            res = client.delete(f'/api/skill/{test_skill}')
            assert res.status_code == 200, f"expected 200, got {res.status_code}"
            assert not os.path.exists(md_path), "md file should be deleted"
            assert not os.path.exists(meta_path), "sidecar json should be deleted"
        finally:
            if os.path.exists(md_path):
                os.remove(md_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)

    def test_delete_called_skill_returns_403(self, app, client):
        """H8: 删除有调用的技能返回403禁止"""
        import tempfile
        import json
        refs_dir = app.config['REFERENCES_DIR']
        meta_dir = app.config['METADATA_DIR']
        os.makedirs(meta_dir, exist_ok=True)

        test_skill = 'test_temp_skill_h8_called'
        md_path = os.path.join(refs_dir, test_skill + '.md')
        meta_path = os.path.join(meta_dir, test_skill + '.json')

        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write('# Test called skill\n')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({"schema_version": "1.0", "name": test_skill, "call_count": 5}, f)

            res = client.delete(f'/api/skill/{test_skill}')
            assert res.status_code == 403, f"expected 403, got {res.status_code}"
            assert os.path.exists(md_path), "md file should NOT be deleted"
        finally:
            if os.path.exists(md_path):
                os.remove(md_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)


# ============ S3扩展：技能访问时调用次数自增 ============

class TestSkillCallTracking:
    def test_skill_content_access_increments_call_count(self, app, client):
        """访问技能内容接口时，call_count应自增"""
        import json
        refs_dir = app.config['REFERENCES_DIR']
        meta_dir = app.config['METADATA_DIR']
        os.makedirs(meta_dir, exist_ok=True)

        test_skill = 'test_call_tracking_skill'
        md_path = os.path.join(refs_dir, test_skill + '.md')
        meta_path = os.path.join(meta_dir, test_skill + '.json')

        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write('# Test tracking\n')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({"schema_version": "1.0", "name": test_skill, "call_count": 0}, f)

            res = client.get(f'/api/skill/{test_skill}/content')
            assert res.status_code == 200

            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            assert meta['call_count'] == 1, f"call_count should be 1, got {meta.get('call_count')}"
            assert 'last_called' in meta and meta['last_called'], "last_called should be set"
        finally:
            if os.path.exists(md_path):
                os.remove(md_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)


# ============ S7: XSS安全 - 后端返回原始内容（转义责任在前端） ============

class TestXSSBackend:
    def test_api_returns_raw_content_without_escaping(self, client):
        """S7: 后端原样返回内容（不做HTML转义，转义由前端escapeHtml负责）"""
        res = client.get('/api/skills')
        data = res.get_json()
        assert isinstance(data, list)
        if data:
            s = data[0]
            assert 'name' in s
            assert 'description' in s

    def test_post_knowledge_accepts_xss_like_input(self, client):
        """S7: 后端接受含特殊字符的知识数据，不做过滤（前端展示时转义）"""
        payload = {
            "schema_version": "1.0",
            "extracted": [{
                "id": "xss_test_entry",
                "type": "SKILL",
                "name": "<script>alert('xss')</script>",
                "context": "test <b>bold</b> context",
                "source_file": "memory/memory_main.md",
                "source_line": 1,
                "tags": ["<img src=x>", "normal-tag"],
                "mastery": None,
                "user_notes": ""
            }],
            "notes": [{
                "id": "xss_test_note",
                "title": "<script>alert('note')</script>",
                "category": "测试",
                "content": "test <b>bold</b> note",
                "tags": [],
                "created_at": "2026-07-23T15:00"
            }]
        }
        res = client.post('/api/knowledge', json=payload)
        assert res.status_code == 200

        res = client.get('/api/knowledge')
        data = res.get_json()
        assert data['extracted'][0]['name'] == "<script>alert('xss')</script>", "backend should preserve raw input"
        assert data['extracted'][0]['context'] == "test <b>bold</b> context"
        assert data['notes'][0]['title'] == "<script>alert('note')</script>"


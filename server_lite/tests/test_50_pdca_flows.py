"""
50个PDCA四环节完整用户流程测试
P(Plan)10 + D(Do)20 + C(Check)12 + A(Act)8 = 50
每个测试都是完整端到端用户故事
"""
import os, sys, json, tempfile, shutil, glob, pytest
from pathlib import Path
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SKILL_ROOT)
# T009: 把 scripts/ 加入 sys.path 以便 import user_data_path（与 server_lite/config.py 一致）
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  T009: 测试需 monkeypatch user_data_path 函数
from server_lite.app import create_app

@pytest.fixture
def app(monkeypatch):
    td = tempfile.mkdtemp()
    dd = os.path.join(td, "data"); md = os.path.join(dd, "metadata")
    os.makedirs(dd); os.makedirs(md)
    # 知识管理后端 file_protocol.py 会自动创建默认 knowledge_data.json，无需预置
    smd = os.path.join(SKILL_ROOT, "server_lite", "data", "metadata")
    if os.path.exists(smd):
        for jf in glob.glob(os.path.join(smd, "*.json")):
            shutil.copy2(jf, md)
    # T009: monkeypatch user_data_path 函数指向测试临时目录，使 api_docs 等直接调用 user_data_path 的地方与 config.DATA_DIR 一致
    monkeypatch.setattr(user_data_path, "get_server_lite_data_path", lambda: Path(dd))
    # T009: extract 端点从 memory_main.md + docs_rj/ 扫描知识，指向项目根真实路径（与改造前行为一致）
    monkeypatch.setattr(user_data_path, "get_memory_main_path", lambda: Path(os.path.join(SKILL_ROOT, "memory", "memory_main.md")))
    monkeypatch.setattr(user_data_path, "get_docs_rj_path", lambda: Path(os.path.join(SKILL_ROOT, "docs_rj")))
    a = create_app({"TESTING": True, "DATA_DIR": dd, "METADATA_DIR": md})
    yield a
    shutil.rmtree(td)

@pytest.fixture
def c(app): return app.test_client()

def _riji(c):
    ps = c.get('/api/projects').get_json()
    for p in ps:
        if 'riji-skill' in p['name']: return p['name']
    return ps[0]['name'] if ps else None

# ========== P 10个 ==========
class TestP:
    def test_p01_first_open(self, c):
        r = c.get('/'); assert r.status_code == 200
        assert '日积面板' in r.data.decode('utf-8')
        h = c.get('/api/health').get_json()
        assert h['status'] == 'ok' and h['version'].startswith('v')

    def test_p02_dashboard_stats(self, c):
        p,s,a = c.get('/api/projects'), c.get('/api/skills'), c.get('/api/agents')
        assert p.status_code == s.status_code == a.status_code == 200
        pj, sk, ag = p.get_json(), s.get_json(), a.get_json()
        assert len(pj) >= 1 and len(sk) >= 36 and isinstance(ag, list)
        z = len([x for x in sk if x.get('frequency_level')=='zero'])
        assert 0 <= z <= len(sk)

    def test_p03_sidebar_nav(self, c):
        for ep in ['/api/projects','/api/skills','/api/knowledge','/api/health']:
            assert c.get(ep).status_code == 200

    def test_p04_contracts(self, c):
        ct = c.get('/api/contracts.json').get_json()
        for n in ['AgentInfo','KnowledgeEntry','KnowledgeNote','ProjectInfo','SkillInfo']:
            assert n in ct and len(ct[n]['fields'])>0

    def test_p05_static(self, c):
        assert c.get('/').status_code == 200
        assert c.get('/style.css').status_code == 200
        assert b'escapeHtml' in c.get('/app.js').data

    def test_p06_dark_theme(self, c):
        css = c.get('/style.css').data.decode('utf-8')
        assert '--black' in css and '--white' in css

    def test_p07_all_menus(self, c):
        ok = sum(1 for e in ['/api/health','/api/projects','/api/skills','/api/knowledge'] if c.get(e).status_code==200)
        assert ok == 4

    def test_p08_refresh(self, c):
        c.get('/'); c.get('/api/health')
        assert c.get('/').status_code == 200
        assert c.get('/api/health').get_json()['status'] == 'ok'

    def test_p09_health_then_data(self, c):
        assert c.get('/api/health').get_json()['status']=='ok'
        for e in ['/api/projects','/api/skills','/api/agents','/api/knowledge']:
            assert c.get(e).status_code==200
        # 健康检查后能访问知识数据：返回默认空结构
        k = c.get('/api/knowledge').get_json()
        assert k['schema_version'] == '1.0'
        assert 'extracted' in k and 'notes' in k
        assert isinstance(k['extracted'], list) and isinstance(k['notes'], list)

    def test_p10_project_badges(self, c):
        n = _riji(c); ps = c.get('/api/projects').get_json()
        r = [p for p in ps if p['name']==n][0]
        assert r['has_summary'] and r['has_spec_main']

# ========== D 20个 ==========
class TestD:
    def test_d01_summary(self, c):
        n = _riji(c); d = c.get(f'/api/project/{n}/summary').get_json()
        assert len(d['content'])>100 and 'title:' in d['content']

    def test_d02_spec(self, c):
        n = _riji(c); d = c.get(f'/api/project/{n}/spec_main').get_json()
        assert len(d['content'])>100

    def test_d03_diff(self, c):
        n = _riji(c)
        s = c.get(f'/api/project/{n}/summary').get_json()['content']
        sp = c.get(f'/api/project/{n}/spec_main').get_json()['content']
        assert s != sp

    def test_d04_pdca_tags(self, c):
        sk = c.get('/api/skills').get_json(); assert len(sk)>=36
        tags = {s.get('pdca_tag') for s in sk if s.get('pdca_tag') not in (None,'-')}
        assert len(tags) > 0

    def test_d05_view_skill(self, c):
        s = c.get('/api/skills').get_json()[0]
        d = c.get(f'/api/skill/{s["name"]}/content').get_json()
        assert d['name']==s['name'] and len(d['content'])>0

    def test_d06_count_inc(self, c):
        sk = c.get('/api/skills').get_json()
        t = [s for s in sk if s['frequency_level']=='zero'][0]
        b = t['call_count']
        c.get(f'/api/skill/{t["name"]}/content')
        a = [s for s in c.get('/api/skills').get_json() if s['name']==t['name']][0]
        assert a['call_count'] == b+1 and a['last_called'] is not None

    def test_d07_agents(self, c):
        assert isinstance(c.get('/api/agents').get_json(), list)
        assert len(c.get('/api/skills').get_json()) >= 36

    def test_d08_save_entry(self, c):
        # POST /api/knowledge 保存 1 个条目
        e = {"id":"d08e1","type":"SKILL","name":"Flask","context":"Web框架",
             "source_file":"memory/memory_main.md","source_line":1,
             "tags":[],"mastery":None,"user_notes":""}
        r = c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        assert r.status_code == 200 and r.get_json()['status'] == 'ok'

    def test_d09_read_entry_back(self, c):
        # GET /api/knowledge 读回验证保存的条目
        e = {"id":"d09e1","type":"SKILL","name":"Python","context":"编程语言",
             "source_file":"memory/memory_main.md","source_line":5,
             "tags":["lang"],"mastery":"familiar","user_notes":"d09备注"}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        d = c.get('/api/knowledge').get_json()
        assert len(d['extracted']) == 1
        assert d['extracted'][0]['name'] == 'Python'
        assert d['extracted'][0]['mastery'] == 'familiar'

    def test_d10_save_two_entries(self, c):
        # POST /api/knowledge 保存多个条目（2 个）
        e1 = {"id":"d10e1","type":"SKILL","name":"Docker","context":"容器化",
              "source_file":"a.md","source_line":1,"tags":[],"mastery":None,"user_notes":""}
        e2 = {"id":"d10e2","type":"EXPERIENCE","name":"项目A","context":"实战经验",
              "source_file":"b.md","source_line":2,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e1,e2],"notes":[]})
        assert len(c.get('/api/knowledge').get_json()['extracted']) == 2

    def test_d11_add_note(self, c):
        # POST /api/knowledge/note 添加 1 个笔记
        r = c.post('/api/knowledge/note', json={"title":"d11笔记","content":"Flask学习"})
        assert r.status_code == 200
        n = r.get_json()['note']
        assert n['title'] == 'd11笔记' and n['id'] and n['created_at']

    def test_d12_delete_note(self, c):
        # DELETE /api/knowledge/note/<id> 删除笔记
        add = c.post('/api/knowledge/note', json={"title":"待删除"}).get_json()['note']
        r = c.delete(f'/api/knowledge/note/{add["id"]}')
        assert r.status_code == 200 and r.get_json()['deleted'] is True
        notes = c.get('/api/knowledge').get_json()['notes']
        assert all(n['id'] != add['id'] for n in notes)

    def test_d13_empty_note_title_400(self, c):
        # POST /api/knowledge/note 空 title 返回 400
        assert c.post('/api/knowledge/note', json={"title":""}).status_code == 400
        assert c.post('/api/knowledge/note', json={"title":"   "}).status_code == 400
        assert c.post('/api/knowledge/note', json={"content":"无title"}).status_code == 400

    def test_d14_special_chars_in_note(self, c):
        # 特殊字符在笔记 title/content 中原样保存
        title = "&<>\"'特殊"
        r = c.post('/api/knowledge/note', json={"title":title,"content":"<script>alert(1)</script>"})
        assert r.status_code == 200
        sv = c.get('/api/knowledge').get_json()['notes'][-1]
        assert sv['title'] == title
        assert sv['content'] == "<script>alert(1)</script>"

    def test_d15_add_three_notes(self, c):
        # POST /api/knowledge/note 添加多个笔记（3 个）
        titles = ["n15_1","n15_2","n15_3"]
        for t in titles:
            r = c.post('/api/knowledge/note', json={"title":t})
            assert r.status_code == 200
        notes = c.get('/api/knowledge').get_json()['notes']
        for t in titles:
            assert any(n['title'] == t for n in notes)

    def test_d16_update_mastery(self, c):
        # PUT /api/knowledge/entry/<id> 更新 mastery
        e = {"id":"d16e1","type":"SKILL","name":"Git","context":"版本控制",
             "source_file":"x.md","source_line":1,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        r = c.put('/api/knowledge/entry/d16e1', json={"mastery":"proficient"})
        assert r.status_code == 200 and r.get_json()['updated'] is True
        sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='d16e1')
        assert sv['mastery'] == 'proficient'

    def test_d17_update_tags(self, c):
        # PUT /api/knowledge/entry/<id> 更新 tags
        e = {"id":"d17e1","type":"SKILL","name":"Linux","context":"操作系统",
             "source_file":"y.md","source_line":2,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        r = c.put('/api/knowledge/entry/d17e1', json={"tags":["ops","shell"]})
        assert r.status_code == 200 and r.get_json()['updated'] is True
        sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='d17e1')
        assert sv['tags'] == ["ops","shell"]

    def test_d18_extract(self, c):
        # GET /api/knowledge/extract 提取知识条目
        r = c.get('/api/knowledge/extract')
        assert r.status_code == 200
        d = r.get_json()
        assert d['status'] == 'ok'
        assert 'total_entries' in d and 'by_type' in d and 'scanned_files' in d
        assert 'SKILL' in d['by_type'] and 'EXPERIENCE' in d['by_type'] and 'SOLUTION' in d['by_type']

    def test_d19_list_sources(self, c):
        # GET /api/knowledge/sources 源文件列表 + GET /api/knowledge/source/<path> 读取单个源文件
        r = c.get('/api/knowledge/sources')
        assert r.status_code == 200
        d = r.get_json()
        assert isinstance(d, list)
        # riji-skill 项目必然有 memory/memory_main.md
        paths = [s['path'] for s in d]
        assert any('memory_main.md' in p for p in paths)
        # 读取 memory_main.md 内容（第 8 个端点）
        src = c.get('/api/knowledge/source/memory/memory_main.md')
        assert src.status_code == 200
        sd = src.get_json()
        assert 'content' in sd and len(sd['content']) > 0
        assert sd['path'] == 'memory/memory_main.md'

    def test_d20_freq_levels(self, c):
        v = {'high','medium','low','zero'}
        for s in c.get('/api/skills').get_json(): assert s['frequency_level'] in v

# ========== C 12个 ==========
class TestC:
    def test_c01_extract_structure(self, c):
        # 提取返回结构完整：total_entries/by_type/scanned_files
        d = c.get('/api/knowledge/extract').get_json()
        assert d['status'] == 'ok'
        assert isinstance(d['total_entries'], int) and d['total_entries'] >= 0
        assert 'SKILL' in d['by_type'] and 'EXPERIENCE' in d['by_type'] and 'SOLUTION' in d['by_type']
        assert isinstance(d['scanned_files'], int) and d['scanned_files'] >= 1

    def test_c02_extract_finds_known_skills(self, c):
        # 提取找到 Python/Flask 等已知技能
        c.get('/api/knowledge/extract')
        entries = c.get('/api/knowledge').get_json()['extracted']
        names = {e['name'] for e in entries if e['type']=='SKILL'}
        # riji-skill 项目 memory_main.md 必然包含 Python/Flask 等技术关键词
        assert 'Python' in names or 'Flask' in names
        # 验证条目 9 字段完整
        e = entries[0]
        for f in ['id','type','name','context','source_file','source_line','tags','mastery','user_notes']:
            assert f in e, f"missing field {f}"

    def test_c03_extract_preserves_annotations(self, c):
        # 提取保留用户标注（tags/mastery/user_notes）
        e = {"id":"c03id","type":"SKILL","name":"Python","context":"old",
             "source_file":"old.md","source_line":1,
             "tags":["my-tag"],"mastery":"expert","user_notes":"我的备注"}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        c.get('/api/knowledge/extract')  # 重新提取
        py = [x for x in c.get('/api/knowledge').get_json()['extracted']
              if x['name']=='Python' and x['type']=='SKILL'][0]
        assert py['mastery'] == 'expert' and 'my-tag' in py['tags']
        assert py['user_notes'] == '我的备注'

    def test_c04_mastery_four_levels(self, c):
        # mastery 4 级更新验证：beginner→familiar→proficient→expert
        e = {"id":"c04id","type":"SKILL","name":"c04skill","context":"x",
             "source_file":"a.md","source_line":1,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        for level in ["beginner","familiar","proficient","expert"]:
            r = c.put('/api/knowledge/entry/c04id', json={"mastery":level})
            assert r.status_code == 200
            sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='c04id')
            assert sv['mastery'] == level

    def test_c05_notes_persist(self, c):
        # 笔记持久化验证
        for t in ["c05_1","c05_2","c05_3"]:
            c.post('/api/knowledge/note', json={"title":t})
        notes = c.get('/api/knowledge').get_json()['notes']
        for t in ["c05_1","c05_2","c05_3"]:
            assert any(n['title']==t for n in notes)

    def test_c06_knowledge_data_persist(self, c):
        # 知识数据持久化验证
        e = {"id":"c06id","type":"EXPERIENCE","name":"c06项目","context":"实战",
             "source_file":"x.md","source_line":3,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        d = c.get('/api/knowledge').get_json()
        assert d['schema_version'] == '1.0'
        assert any(x['id']=='c06id' for x in d['extracted'])

    def test_c07_entries_persist(self, c):
        # 条目持久化验证
        entries = [
            {"id":"c07e1","type":"SKILL","name":"c07a","context":"a",
             "source_file":"a.md","source_line":1,"tags":[],"mastery":None,"user_notes":""},
            {"id":"c07e2","type":"SOLUTION","name":"c07b","context":"b",
             "source_file":"b.md","source_line":2,"tags":[],"mastery":None,"user_notes":""},
        ]
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":entries,"notes":[]})
        d = c.get('/api/knowledge').get_json()
        assert len(d['extracted']) == 2
        ids = {e['id'] for e in d['extracted']}
        assert 'c07e1' in ids and 'c07e2' in ids

    def test_c08_hyphen_skills(self, c):
        sk = c.get('/api/skills').get_json()
        hyp = [s['name'] for s in sk if '-' in s['name']]
        for n in hyp[:2]: assert c.get(f'/api/skill/{n}/content').status_code == 200

    def test_c09_skill_7fields(self, c):
        ct = c.get('/api/contracts.json').get_json()
        fields = {f['name'] for f in ct['SkillInfo']['fields']}
        assert len(fields) == 7
        for s in c.get('/api/skills').get_json()[:5]:
            for f in fields: assert f in s

    def test_c10_path_traversal_blocked(self, c):
        for bad in ["../etc/passwd","..\\windows","a/../../b"]:
            assert c.get(f'/api/project/{bad}/summary').status_code in (400,404)
            assert c.get(f'/api/skill/{bad}/content').status_code in (400,404)

    def test_c11_xss_in_note_title(self, c):
        # XSS 输入到笔记 title 不崩溃
        bad = "<script>alert('xss')</script>"
        r = c.post('/api/knowledge/note', json={"title":bad,"content":"<img src=x onerror=alert(1)>"})
        assert r.status_code == 200
        sv = c.get('/api/knowledge').get_json()['notes'][-1]
        assert sv['title'] == bad  # 原样保存

    def test_c12_boundary_data_saved(self, c):
        # 边界数据保存验证（空 tags/空 user_notes/特殊字符 name/source_line=0）
        e = {"id":"c12id","type":"SKILL","name":"边界&<>测试","context":"",
             "source_file":"","source_line":0,"tags":[],"mastery":None,"user_notes":""}
        r = c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        assert r.status_code == 200
        sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='c12id')
        assert sv['name'] == "边界&<>测试"
        assert sv['tags'] == [] and sv['user_notes'] == ""

# ========== A 8个 ==========
class TestA:
    def test_a01_note_id_unique(self, c):
        # 笔记 id 唯一性：多次添加 id 不同
        r1 = c.post('/api/knowledge/note', json={"title":"n1"}).get_json()['note']
        r2 = c.post('/api/knowledge/note', json={"title":"n2"}).get_json()['note']
        r3 = c.post('/api/knowledge/note', json={"title":"n3"}).get_json()['note']
        ids = {r1['id'], r2['id'], r3['id']}
        assert len(ids) == 3  # 三个 id 互不相同

    def test_a02_empty_post_400(self, c):
        # POST /api/knowledge + /api/knowledge/note 空 body 返回 400
        assert c.post('/api/knowledge', data='', content_type='application/json').status_code == 400
        assert c.post('/api/knowledge/note', data='', content_type='application/json').status_code == 400

    def test_a03_nonexistent_404(self, c):
        # 不存在的 entry/note 返回 404（PUT entry + DELETE note）
        assert c.put('/api/knowledge/entry/nonexist_xyz123', json={"mastery":"expert"}).status_code == 404
        assert c.delete('/api/knowledge/note/nonexist_xyz123').status_code == 404

    def test_a04_full_knowledge_loop(self, c):
        # 完整知识闭环：save → note → update → extract
        # 1. save entry
        e = {"id":"a04id","type":"SKILL","name":"Python","context":"a04",
             "source_file":"x.md","source_line":1,"tags":[],"mastery":None,"user_notes":""}
        assert c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]}).status_code == 200
        # 2. add note
        assert c.post('/api/knowledge/note', json={"title":"a04笔记"}).status_code == 200
        # 3. update entry mastery
        assert c.put('/api/knowledge/entry/a04id', json={"mastery":"proficient"}).status_code == 200
        # 4. extract
        r = c.get('/api/knowledge/extract')
        assert r.status_code == 200 and r.get_json()['status'] == 'ok'
        # 验证 Python 条目保留 mastery
        sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='a04id')
        assert sv['mastery'] == 'proficient'

    def test_a05_zero_stats_consistent(self, c):
        sk = c.get('/api/skills').get_json()
        z1 = len([s for s in sk if s['frequency_level']=='zero'])
        z2 = sum(1 for s in sk if s.get('call_count',0)==0)
        assert z1 == z2

    def test_a06_knowledge_entry_fields(self, c):
        # KnowledgeEntry 字段完整性（9 字段）
        ct = c.get('/api/contracts.json').get_json()
        ef = {f['name'] for f in ct['KnowledgeEntry']['fields']}
        # 9 字段：id/type/name/context/source_file/source_line/tags/mastery/user_notes
        assert ef == {'id','type','name','context','source_file','source_line','tags','mastery','user_notes'}
        e = {"id":"a06id","type":"SKILL","name":"a06","context":"x",
             "source_file":"a.md","source_line":1,"tags":[],"mastery":None,"user_notes":""}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        sv = next(x for x in c.get('/api/knowledge').get_json()['extracted'] if x['id']=='a06id')
        for f in ef:
            assert f in sv, f"missing field {f}"

    def test_a07_knowledge_note_fields(self, c):
        # KnowledgeNote 字段完整性（6 字段）
        ct = c.get('/api/contracts.json').get_json()
        nf = {f['name'] for f in ct['KnowledgeNote']['fields']}
        # 6 字段：id/title/category/content/tags/created_at
        assert nf == {'id','title','category','content','tags','created_at'}
        r = c.post('/api/knowledge/note', json={"title":"a07","category":"cat","content":"c","tags":["t"]})
        assert r.status_code == 200
        sv = r.get_json()['note']
        for f in nf:
            assert f in sv, f"missing field {f}"

    def test_a08_complete_pdca_cycle(self, c):
        # 完整 PDCA 闭环：提取→保存→笔记→更新→再提取验证保留标注
        # 1. Plan: 健康检查 + 项目扫描
        assert c.get('/api/health').get_json()['status'] == 'ok'
        assert len(c.get('/api/projects').get_json()) >= 1
        assert len(c.get('/api/skills').get_json()) >= 36
        # 2. Do: 提取
        r1 = c.get('/api/knowledge/extract').get_json()
        assert r1['status'] == 'ok' and r1['total_entries'] >= 0
        # 3. Do: 保存一个带用户标注的 Python 条目
        e = {"id":"a08id","type":"SKILL","name":"Python","context":"a08",
             "source_file":"x.md","source_line":1,
             "tags":["a08-tag"],"mastery":"expert","user_notes":"a08备注"}
        c.post('/api/knowledge', json={"schema_version":"1.0","extracted":[e],"notes":[]})
        # 4. Do: 添加笔记
        assert c.post('/api/knowledge/note', json={"title":"a08闭环笔记"}).status_code == 200
        # 5. Do: 更新条目 user_notes
        assert c.put('/api/knowledge/entry/a08id', json={"user_notes":"更新后备注"}).status_code == 200
        # 6. Check: 重新提取，验证 Python 条目保留用户标注
        c.get('/api/knowledge/extract')
        py = [x for x in c.get('/api/knowledge').get_json()['extracted']
              if x['name']=='Python' and x['type']=='SKILL']
        assert len(py) > 0
        pe = py[0]
        assert pe['mastery'] == 'expert'  # 保留标注
        assert 'a08-tag' in pe['tags']
        assert pe['user_notes'] == '更新后备注'  # 更新后的值
        # 7. Act: 验证笔记持久化
        notes = c.get('/api/knowledge').get_json()['notes']
        assert any(n['title']=='a08闭环笔记' for n in notes)
        # 8. COMPLETE!
        assert True

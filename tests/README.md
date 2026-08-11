# tests/ - pdca-skill 测试套件

> 测试基础设施,基于 pytest。纯 Python 标准库,零外部依赖。

## 📁 目录结构

```
tests/
├── conftest.py              # 共享 fixture(tmp_skill_dir/create_memory/create_summary)
├── test_negative_cases.py   # 负向测试(无循环 import/无个人路径/无死引用)
├── pytest.ini               # pytest 配置
├── run_tests.cmd            # Windows 一键运行脚本
└── README.md                # 本文件
```

## 🚀 运行测试

### 方式 1:一键脚本(Windows)
```cmd
tests\run_tests.cmd
```

### 方式 2:直接用 pytest
```bash
# 在项目根执行
python -m pytest tests/ -v

# 仅跑负向测试
python -m pytest tests/test_negative_cases.py -v

# 仅收集测试不执行(验证语法)
python -m pytest tests/test_negative_cases.py --collect-only
```

## 📋 测试清单

### test_negative_cases.py(3+1 个测试)
| 测试名 | 验证内容 |
|--------|---------|
| `test_no_circular_imports` | protocol/ 包无循环 import |
| `test_no_personal_paths` | 项目源码无硬编码个人路径(C:\\Users\\xxx) |
| `test_no_dead_references` | SKILL.md 引用的关键文件确实存在 |
| `test_protocol_importable_without_errors` | protocol/ 包可独立导入 |

## 🎯 共享 fixture

### `tmp_skill_dir`(autouse=False)
临时 skill 目录,包含最小骨架(SKILL.md + 各子目录)。测试结束自动清理。

```python
def test_xxx(tmp_skill_dir):
    skill_md = tmp_skill_dir / "SKILL.md"
    assert skill_md.exists()
```

### `create_memory_fixture`
构造 memory_main.md 测试 fixture 工厂。

```python
def test_memory(create_memory_fixture):
    mem = create_memory_fixture(task="my_task", content="custom content")
    assert "my_task" in mem
```

### `create_summary_fixture`
构造 SUMMARY_RJ.md 测试 fixture 工厂。

```python
def test_summary(create_summary_fixture):
    s = create_summary_fixture(total_docs=10, version="v1.0.0")
    assert "v1.0.0" in s
```

## ⚠️ 未覆盖的脚本清单(8 个,待补测试)

以下脚本尚未有专门测试,待补充:

1. `scripts/route_check.py` - 路由检查(待 T03 完成后补测试)
2. `scripts/protocol_align.py` - 协议对齐检查(待 T04 完成后补测试,T17)
3. `scripts/link_indexer.py` - 链接索引器(待 T05 完成后补测试,T29)
4. `scripts/check_skill_updates.py` - skill 更新检查(待 T06 完成后补测试,T29)
5. `scripts/devlog_sync.py` - devlog 同步(待 T19 完成后补测试,T29)
6. `scripts/generate_host_rules.py` - host rules 生成(待 T20 完成后补测试,T29)
7. `scripts/validate_global_files.py` - 全局文件验证(待 T21 完成后补测试,T29)
8. `scripts/learn_tidy.py`(Phase 5 + rule 子命令) - 待 T07/T15 完成后补测试

## 🔧 设计原则

1. **纯标准库**:不引入第三方依赖(pytest 本身除外)
2. **隔离性**:每个测试独立 tmp_path,不污染真实项目文件
3. **负向优先**:优先测"不应该出现 X"(防回归)
4. **快速反馈**:单测试 < 1s,全套 < 5s
5. **可读性**:测试名清楚表达意图,失败信息含具体位置

## 📝 版本历史

| 版本 | 时间 | 变更 |
|------|------|------|
| v1.0.0 | 2026-07-21 | 初版:conftest + 3 负向测试 + pytest.ini + run_tests.cmd |

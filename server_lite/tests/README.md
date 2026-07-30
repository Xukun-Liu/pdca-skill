# server_lite 测试套件保留说明

> 本文件说明为何 server_lite 当前不主动引导使用，但测试套件仍然保留。

## 保留原因

server_lite（日积面板）是已完整实现的 Flask Web 管理台（v2.0.0），但当前版本不主动引导用户使用——其功能与 AI 对话定位重叠。

测试套件保留的原因：
1. **代码保留 = 测试保留**：server_lite 代码完整保留供未来扩展或用户主动启用，测试同步保留可确保代码行为正确性
2. **恢复启用时无需重写测试**：将来恢复引导使用时，测试已就位，无需重新编写
3. **测试通过 ≠ 推荐使用**：测试通过仅说明代码层行为正确，不代表推荐用户使用 server_lite

## 测试文件清单

| 文件 | 覆盖范围 |
|------|----------|
| test_50_pdca_flows.py | PDCA 流程测试（50次） |
| test_50_real_scenarios.py | 真实场景测试（50次） |
| test_server_lite.py | server_lite 核心 API 测试 |
| test_knowledge_memories.py | 知识记忆功能测试 |
| test_api_settings.py | 数据管理 API 测试 |

## 决策依据

详见 `docs_rj/spec_rj/server_lite_retention_spec_20260725_0110.md`。

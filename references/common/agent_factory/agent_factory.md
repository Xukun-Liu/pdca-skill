<!-- PDCA标签：D.code P.design -->
<!-- 子标签场景：副 agent 脚手架与注册 -->
<!-- 关键词清单：agent_factory/new_agent/register_agent/validate_agent/agent_memory/副agent/子agent/agent.json/AGENT.md -->
<!-- 引用范围：main + skill_mgmt_agent -->

# Agent Factory（副 agent 工厂）
> 阶段标签：D.code · P.design

> 版本：v1.1.0 | 更新：2026-10-28

## 📖 什么时候读这个文件

- 要新建一个副 agent（新增领域调研角色），不想手抄 JSON 字段
- 手上有个 agent 目录，想知道它能不能被主 agent 正常调度
- 想把副 agent 的调研结论沉淀成它自己的长期记忆

## 一、为什么要工厂化（第一性原理）

副 agent 的最小可调度条件只有三条：**能被路由（triggers）、能被读懂（knowledge）、不越权（只读）**。手写时最容易漏的偏偏是这三条——写了角色忘了触发词、knowledge 指向不存在的文件、AGENT.md 首行身份声明写错，主 agent 就会「以为召回来了，其实是个空壳」。

四个脚本各管一段，合起来把「建 → 登 → 检 → 记」变成可复跑的命令：

| 脚本 | 管什么 | 一句话 |
|---|---|---|
| `new_agent.py` | 建 | 生成 `agent.json` + `AGENT.md` + `memory/memory_agent.md` |
| `register_agent.py` | 登 | 按 name 幂等合并进注册表 |
| `validate_agent.py` | 检 | 六项体检，FAIL 即不可用 |
| `agent_memory.py` | 记 | 按时间戳追加记忆，只追加不改写 |

## 二、目录形态（不可改的最小集）

```
<agent 目录>/
├── agent.json                 # 机器读：name/role/description/knowledge/triggers/output_format/version/created_at
├── AGENT.md                   # 人读：首行必须是 [subagent: <name>]
└── memory/
    └── memory_agent.md        # 该 agent 的长期记忆
```

- `agent.json` 的字段与 `agents_rj/subagent_config_rj.json` 的 `agents[]` 对齐，注册时直接映射进去
- `AGENT.md` 首行身份声明是**硬门**——`validate_agent.py` 会逐字比对 `[subagent: <name>]`，写错就 FAIL
- `memory/memory_agent.md` 缺失同样 FAIL：没有记忆的 agent 每次召回都是从零开始

## 三、端到端四条命令

```powershell
# 1. 建（目标已存在时会拒绝，确认覆盖加 --force）
python scripts\agent_factory\new_agent.py --name demo --out "$env:TEMP\ag"

# 2. 登（默认写 ~/.pdca-skill/data/agents_registry.json，先看结果加 --dry-run）
python scripts\agent_factory\register_agent.py --path "$env:TEMP\ag\demo"

# 3. 检（0 = 可调度；1 = 有 FAIL，按提示修）
python scripts\agent_factory\validate_agent.py --path "$env:TEMP\ag\demo"

# 4. 记（省略 --content 则读 stdin；先预演加 --dry-run，想看历史加 --show）
python scripts\agent_factory\agent_memory.py --path "$env:TEMP\ag\demo" --content "结论：……"
```

批量体检：`python scripts\agent_factory\validate_agent.py --root <agent 根目录>`（递归找 `agent.json`）。

## 四、注册表落哪、长什么样

默认落**用户数据目录**（`~/.pdca-skill/data/agents_registry.json`），不写进 skill 包——升级 skill 包时注册信息不会丢，也不会污染 dev 仓库。

```json
{
  "version": "1.0.0",
  "last_updated": "2026-10-28T23:50:00",
  "defaults": { "subagent_type": "general_purpose_task", "permission": "read_only", "parallel_capable": true },
  "agents": [
    { "name": "demo", "role": "demo_agent_pdca", "role_identity": "……",
      "description": "……", "knowledge": ["…"], "triggers": ["demo"], "output_format": ["结论", "依据", "下一步"] }
  ]
}
```

合并规则：**同 name 覆盖、异 name 追加**，不删除其他条目；`--config <路径>` 可指定别的注册表（CI / 多环境用）。

## 五、和主流程的关系

- 建完的 agent 由主 agent 经 `Task` 工具（`general_purpose_task`）召起，权限仍受 `references/common/pda/subagents_rj.md` 的**只读白名单**约束
- 想让它「能写」是刻意不做的事：写操作一律回主 agent 过 HARD-GATE，避免副 agent 绕过门禁改文件
- 注册表只是索引，不等于自动生效——主 agent 侧的角色配置仍以 `agents_rj/subagent_config_rj.json` 为准

## 六、失败对照表

| 退出码 | 含义 | 怎么办 |
|---|---|---|
| 0 | 通过 / 成功 | — |
| 1 | 内容问题（name 非法 / 缺字段 / AGENT.md 首行不符 / knowledge 不存在 / 目标已存在） | 按打印的 `[FAIL]` 逐条修 |
| 2 | 环境问题（目录不存在 / 用户数据目录不可用 / 注册表损坏） | 先修路径或权限，再重跑 |
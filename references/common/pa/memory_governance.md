<!-- PDCA标签：P.bootstrap A.persist -->
<!-- 子标签场景：记忆治理工具触发条件+容量阈值 -->
<!-- 关键词清单：记忆归档/记忆降级/记忆升格/记忆删除/记忆重评/记忆治理/容量超限/记忆隔离/记忆回滚 -->
<!-- 引用范围：main + bootstrap_agent -->

# 记忆治理规则（memory_governance）
> 阶段标签：P · A（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 创建：2026-07-30 | 方案：3-R（混合完整治理）
> 职责：治理动作的触发条件 + HARD-GATE 矩阵 + 容量阈值
> 边界：参数定义见 [working_memory_rules.md](working_memory_rules.md)，本文件只管"何时触发+如何执行"

---

## 1. 治理工具清单

| 工具 | 归属脚本 | 语义 | HARD-GATE | 可逆 |
|------|----------|------|-----------|------|
| write_project | memory_shadow_write.py | 双写（项目+全局）+ 自动容量告警 | 否 | N/A |
| memory_delete | memory_shadow_write.py | 删除条目（默认软删除=标记 archived） | 是 | 软删可逆/硬删不可逆 |
| memory_archive | memory_shadow_write.py | 归档条目（flag 标记，不移动） | 否 | 可逆（改回 active） |
| memory_promote | memory_shadow_write.py | 升格（项目→全局，复用 upsert） | 否 | N/A |
| memory_demote | memory_shadow_write.py | 降级（全局条目标记 demoted） | 是 | 可逆（改回 active） |
| memory_rethink | learn_tidy.py | LLM 重评给建议清单（只读，不加锁） | 是 | 建议不自动执行 |
| memory_rollback | memory_shadow_write.py | 从 undo 目录回滚（先备份当前） | 否 | 可逆（rollback_pre_restore 备份） |
| check_capacity_threshold | memory_shadow_write.py | 容量阈值检查（只读，write_project 后自动调） | 否 | N/A |

**调用时机**：
- write_project：每次写入后自动调 check_capacity_threshold 告警（不自动清洗）
- memory_rollback：用户显式调 CLI `--rollback <timestamp>`
- 其他工具：agent 根据触发词/容量告警决定调用

---

## 2. 容量阈值决策表

| 阈值 | 触发动作 | 无 LLM 时 | high 条目 | 实现状态 |
|------|----------|-----------|-----------|----------|
| 单项目段 > 30 条 | 告警（建议跑 memory_rethink） | 只隔离不删 | 不参与 | ✅ 已实现（check_capacity_threshold） |
| 单项目段 > 50K 字符 | 同上 | 同上 | 同上 | ✅ 已实现 |
| 全局总量 > 500 条 | 跨项目告警 | 只隔离不删 | 不参与 | ✅ 已实现 |
| memory_rj/ 单文件 > 500 行 | 整文件移到 archive_rj/memory_rj/ | 保留最近 5 条 | N/A | ⚠️ 未实现（MEMORY_RJ_MAX_LINES 常量已定义，归档逻辑待补） |
| 滞后阈值（达 35 才触发，回退到 25） | 防止边界反复触发 | N/A | N/A | ⚠️ 未实现（未来优化，当前简单 >30 触发） |

**已实现 vs 未实现清单**：
- ✅ 容量阈值检查（check_capacity_threshold）
- ✅ write_project 后自动告警
- ✅ flag 机制（active/archived/demoted）
- ✅ 5 工具（delete/archive/promote/demote/rethink）+ rollback
- ⚠️ 整文件归档（保留最近 5 条）—— 未来优化
- ⚠️ 滞后阈值（35/25 hysteresis）—— 未来优化
- ⚠️ 7 天宽限期（升级后首次启动不触发容量阈值）—— 未来优化（当前因 check_capacity_threshold 只告警不清洗，老用户升级不受影响）
- ⚠️ 自动清洗触发（容量超限时自动调 memory_archive）—— 未来优化（当前需 agent 手动调 memory_rethink + memory_archive）

**"条目"定义**：`### 记忆条目 · {task}（{timestamp}）` 开头的 block（与 upsert_global_memory 去重逻辑一致）。

---

## 3. 隔离机制（无 LLM 安全网）

无 LLM 介入时，容量阈值触发的清洗**只隔离不删除**：

```
隔离区：{user_data_dir}/quarantine/quarantine_{project}_{ts}.md
内容：原 block 全文 + 来源项目 + 隔离时间 + "待 LLM 复核"标记
```

- 隔离区文件永不自动删除，需 LLM/用户复核后决定保留/删除
- 隔离失败不阻断主操作（try/except 包裹）

---

## 4. 备份与回滚

### 4.1 备份机制

5 个治理工具（delete/archive/promote/demote/rethink）每次操作前自动备份：

```
备份位置：{user_data_dir}/undo/{tool_name}_{ts}/
备份内容：
  - memory_main.md.bak（全局记忆备份）
  - memory_rj.bak/（项目记忆目录备份）
保留期：30 天（_cleanup_old_undos 自动清理）
```

### 4.2 回滚 CLI

```bash
# 按 timestamp 模糊匹配 undo 目录回滚
python scripts/memory_shadow_write.py --rollback 20260730_1030
```

回滚会先备份当前状态（防回滚后想再回滚），再从 undo 目录恢复。

---

## 5. 并发安全

5 个治理工具复用同一把锁（与 write_project 一致），锁顺序：

```python
with _WRITE_LOCK, _GLOBAL_CP_LOCK:  # 先 RL 再 CPL，顺序不可反
    # 读-改-写 串行化
```

- 锁顺序不一致会导致 AB-BA 死锁（对抗性审查 A1）
- 跨进程文件锁（_GLOBAL_CP_LOCK）默认无限等待，建议加超时（未来优化）

---

## 6. 向后兼容

### 6.1 老条目无 flag 字段

旧 memory_main.md 的条目无 `**状态**` 字段时：
- `_parse_entry_flag` 默认返回 `status='active'`
- 不报错，不阻塞读写
- 容量阈值触发时按 unknown 处理（与 low 同级，参与清洗）

### 6.2 老用户升级

- 无需迁移脚本（flag 字段向后兼容）
- 首次启动时建议跑 `learn_tidy.memory_rethink(scope='all')` 全扫给建议
- 7 天宽限期（未来优化：升级后首次启动不触发容量阈值）

---

## 7. 与现有规则的关系

| 现有规则 | 本文件关系 |
|----------|-----------|
| [working_memory_rules.md](working_memory_rules.md) §2 三层结构 | 本文件加 flag 机制（不新增层级，archived 是 active 的子状态） |
| [working_memory_rules.md](working_memory_rules.md) §7 评估参数 | 本文件复用 importance_level/is_lesson，不新起参数体系 |
| [learn_cycle.md](../../act/learn/learn_cycle.md) §6 禁删 | 本文件的 memory_delete 不违反（禁删范围仅限核心规则，不含 memory 数据条目） |
| [trigger_hooks.md](trigger_hooks.md) | 触发词用"记忆归档/记忆降级"专用词，避开"archive"裸词 |
| [SKILL.md](../../../SKILL.md) §Memory First | 本文件符合"无独立归档步骤"（flag 软引用不物理移动） |

---

## 8. 变更历史

| 时间 | 版本 | 变更 |
|------|------|------|
| 2026-07-30 | v1.0.0 | 初始版本，方案 3-R 阶段4 实施 |

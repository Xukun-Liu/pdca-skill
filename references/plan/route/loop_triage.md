<!-- PDCA标签：P.route -->
<!-- 子标签场景：/plan 阶段 triage 输出、优先级分类 -->
<!-- 关键词清单：triage/priority/plan/High Priority/Watch/Noise -->
<!-- 引用范围：main + loop_agent -->

---
name: loop-triage
description: >
  /plan 阶段的 triage 输出规范。把复杂输入分类成 High Priority / Watch / Noise。
pdca: P.route
keywords: [triage, priority, plan]
---

> 版本：v1.0.0
> 阶段标签：P.route

# Loop Triage

## 输出格式

每次 `/plan` 必须输出三段：

### High Priority（立即行动）
- 影响范围明确、≤5 文件、风险可控。
- 有明确验收标准。

### Watch List（持续观察）
- 需要更多信息或用户决策。
- 影响范围大、涉及 denylist、或与其他任务冲突。

### Noise（忽略，但记录原因）
- 与当前目标无关。
- 超出能力范围。
- 重复或已解决。

## 分类规则

| 条件 | 分类 |
|------|------|
| 用户明确要改、≤5 文件、不碰 denylist | High Priority |
| 用户要改但 >5 文件或需拆分 | High Priority（拆分子任务） |
| 涉及 auth/payments/secrets/infrastructure/migrations | Watch → escalate |
| 信息不足 | Watch |
| 无关/重复/已解决 | Noise |

<!-- PDCA标签：D.comm C.verify -->
<!-- 子标签场景：占位符硬门 -->
<!-- 关键词清单：C1/占位符/TBD/TODO/适当处理/类似XX/伪代码/待补充/半成品 placeholder-gate:ignore -->
<!-- 引用范围：main + code_eng_agent + doc_proc_agent -->

# 占位符硬门（Placeholder Gate · C1）
> 阶段标签：D.comm · C.verify

> 版本：v1.1.0 | 更新：2026-10-28

## 📖 什么时候读这个文件

- 你（agent）准备交付 spec / task / 文档 / 代码片段前
- 铁律 4（No Placeholders）需要落地成**可执行检查**时
- 用户抱怨「这东西看着写完了，其实是空的」时

## 一、这道门拦什么

半成品比没做更危险：它看起来像完成品，于是没人再回来补。C1 把「像完成品」变成「机械可判定」——扫命中词，命中即拦。

## 二、六类检测词表（内置，改词表请同步本表与脚本）

<!-- placeholder-gate:ignore 以下 6 行是词表本体，自指豁免 -->

| 类型 | 命中样例 | 为什么必须拦 |
|---|---|---|
| TBD | `TBD` / `待定` | 决策没做完 <!-- placeholder-gate:ignore --> |
| TODO | `TODO` / `待补充` / `待完善` | 工作没做完 <!-- placeholder-gate:ignore --> |
| 适当处理 | `适当处理` / `酌情处理` | 标准没定义，等于没写 <!-- placeholder-gate:ignore --> |
| 类似XX | `类似 XX` / `类似上一步` / `类似某某` | 复制粘贴的偷懒态 <!-- placeholder-gate:ignore --> |
| 伪代码 | `伪代码` | 不能直接跑 <!-- placeholder-gate:ignore --> |
| 自定义 | 通过 `--placeholder-words` 传入 | 项目专有偷懒词 |

> 表格内 6 行带 `placeholder-gate:ignore` 标记，扫描本文件时自动跳过——避免「拦截器把自己拦下」。

## 三、怎么跑

```powershell
# 扫单个交付物（交付前必跑）
python scripts\validate_skill.py --placeholder-check "docs_rj\spec_rj\xxx_spec_20261028_1847.md"

# 扫一个目录（递归 *.md）
python scripts\validate_skill.py --placeholder-check "docs_rj\spec_rj"

# 追加项目专有词（逗号分隔，叠加内置 6 类）
python scripts\validate_skill.py --placeholder-check "docs_rj" --placeholder-words "回头再说,先放着"
```

**退出码**：`0` = 全清；`1` = 命中（输出 `路径:行号: [类型] 原文`）；`2` = 路径不存在。

## 四、豁免规则（唯一一条）

单行需要**作为示例/词表**出现时，在该行加注 `placeholder-gate:ignore`，脚本跳过该行。除此外没有任何豁免——「这次先不写」「大概这样」都不算理由。

## 五、反向验证（必做一次，防假绿灯）

新接入或改词表后，必须证明「它会响」：

```powershell
"# t`nTBD" | Set-Content "$env:TEMP\c1_probe.md" -Encoding utf8
python scripts\validate_skill.py --placeholder-check "$env:TEMP\c1_probe.md"   # 期望退码 1 + 命中行号 2
Remove-Item "$env:TEMP\c1_probe.md"
```

只贴绿灯不贴红灯 = 没有验证「这门能不能拦住」，等于没验证。

## 六、与其他门的关系

| 门 | 管什么 | 时机 |
|---|---|---|
| C1 占位符（本文件） | 内容有没有偷懒 | 交付前 |
| C4 写后校验（[write_verify.md](write_verify.md)） | 文件有没有真落盘 | 每次写文件后 |
| `close_task.py`（O0） | 任务产物齐不齐、SUMMARY 挂没挂 | /act 收尾 |
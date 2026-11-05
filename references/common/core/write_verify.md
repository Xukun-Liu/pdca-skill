<!-- PDCA标签：D.comm C.verify A.persist -->
<!-- 子标签场景：写后校验硬门 -->
<!-- 关键词清单：C4/写后校验/写完没落/回读校验/字节数/关键块存在/假写入 -->
<!-- 引用范围：main + code_eng_agent -->

# 写后校验硬门（Write Verify · C4）
> 阶段标签：D.comm · C.verify · A.persist

> 版本：v1.1.0 | 更新：2026-10-28

## 📖 什么时候读这个文件

- 你（agent）刚用 Write / Edit / 脚本落盘了文件，准备说「已完成」时
- 交付物涉及 memory / SUMMARY / spec / task 等「写了但没落」会静默丢数据的文件时
- 用户反馈「你说写了，我怎么没看到」时

## 一、为什么需要这道门（第一性原理）

`Write` 返回 `success` 只代表**调用没报错**，不代表**内容真的落在目标路径**。真实踩坑过的四种「假写入」：

| 假写入形态 | 现象 | 根因 |
|---|---|---|
| 路径漂移 | 文件出现在别处 | 相对路径按 CWD 解析，CWD 不是你以为的目录 |
| 编码漂移 | 打开是乱码 / 开头多一个 `﻿` | UTF-8 带 BOM（Windows PowerShell 5 `Set-Content -Encoding utf8`） |
| 空壳写入 | 文件存在但 0 字节 / 只有 frontmatter | 变量为空、内容被截断 |
| 覆盖丢失 | 旧内容没了，新内容只有一半 | 本意追加却用了覆盖写 |

这四种的共同点：**没有任何报错**。所以校验必须发生在「写之后」，而不是相信写入返回值。

## 二、四条校验（写完立刻做，全部只读）

| # | 校验项 | 判定 | 命令（PowerShell） |
|---|---|---|---|
| 1 | 存在性 | `Test-Path` 为 True | `Test-Path "<绝对路径>"` |
| 2 | 非空 | 字节数 > 0 | `(Get-Item "<路径>").Length` |
| 3 | 关键块存在 | 至少 1 个特征串命中 | `Select-String -Path "<路径>" -Pattern "<特征串>"` |
| 4 | 无 BOM | 首字节不是 `EF BB BF` | `Format-Hex -Path "<路径>" -Count 3` |

> **特征串怎么选**：不是选一句话，而是选「这段内容独有的一段」——例如写 memory 就校验 `task 名 + memory_class + 时间戳`；写 SUMMARY 就校验那条链接的相对路径。

## 三、与 write_project 的配合

`scripts/memory_shadow_write.py` 的 `write_project()` **已经内置校验**：返回 dict 里有 `project_ok` / `global_ok` / `fallback`。

- `project_ok: True` = 项目记忆落盘成功（这是硬要求，False 必须重试或降级手写）
- `global_ok: True` = 全局 `memory_main.md` upsert 成功（False 只告警，不阻断——B5 隔离策略）
- **不要用返回值里的路径字符串推断成功**，用布尔字段判定

## 四、失败处理（不猜、不重试三次以上）

1. 第一次失败 → 打印实际路径 + 实际字节数，重跑一次写入
2. 第二次失败 → 换绝对路径重写（排除 CWD 漂移）
3. 第三次失败 → 停下，如实告知用户「写了但没落」，附三条证据（路径/字节数/首字节），不假完成

## 五、反模式（做了等于没做）

- ❌ 只 `Read` 一眼文件名就宣布完成（没看内容）
- ❌ 用 `Write` 覆盖后不核对旧内容是否该保留
- ❌ 写 UTF-8 文件时用 `Set-Content -Encoding utf8`（PS5 会加 BOM，改用 `[IO.File]::WriteAllText($p, $s, (New-Object Text.UTF8Encoding($false)))`）
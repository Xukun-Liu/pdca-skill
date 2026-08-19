<!-- PDCA标签：D.code -->
<!-- 子标签场景：文件转 Markdown -->
<!-- 关键词清单：转Markdown/转md/文件转markdown/PDF转md/Word转md/PPT转md/Excel转md/HTML转md/文档转markdown/提取成markdown -->
<!-- 引用范围：main + doc_proc_agent -->

# 文件转 Markdown（PDF / Word / PPT / Excel / HTML → MD）

> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.1.0 | 更新：2026-08-11
> v1.0 变更：四期交付。综合网上最佳实践（微软 某工具，82.9k★，2025 检索）+ 本地 office_processing.md（二期），沉淀「各类文件→Markdown」为纯文本参考模块，内网离线可用、零外部依赖。沙箱实测纠正——`某工具` 安装命令改为「extras 必装」（`某工具[pdf,docx,pptx,xlsx]`），裸装转不了 Office 文件（`MissingDependencyException`）；§一、§五加沙箱踩坑说明。核心四格式纯 Python 离线路径已实测全 PASS。

> 📖 **什么时候读这个文件**：
> - 任务涉及「把某个文件转成 Markdown」——"转 md / 提取成 md / 变成纯文本 / 喂给 AI 前先转一下"
> - 用户说"把这个 PDF 转成 md""Word 提取成 Markdown""Excel 表格弄成 MD""网页存成 MD"
> - 需要选「用 某工具 一行搞定，还是用专用库精细控制」
> - 交付转出的 MD 前，按本文件「验收」一节对照（配合 acceptance_criteria.md 的 4 道质量闸门）

🔴 **不要在这时候读**：
> - 纯问答、不涉及任何文件转 MD
> - 要做的是"改 Office 文件"而非"转成 MD"——那是 office_processing.md（二期）

---

## 〇、先搞懂为什么转 Markdown（大白话）

- **Markdown 是什么**：一个"纯文本记事本"，但带简单标记——`# 标题`、`**粗体**`、`| 表格 |`。人能直接读，AI 更懂它（主流 LLM 训练数据里大量是 Markdown，token 能省 30%+）。
- **转 MD 等于做什么**：把"密封的礼盒"（docx/xlsx/pptx/pdf 这些二进制文件）**拆开，把里面的内容列成一张清单**。丢了包装（排版/颜色/字体），留下内容（文字/结构/表格）。
- **什么时候要转**：①喂给 AI/大模型前先统一格式；②做知识库/检索；③二次编辑成笔记（Obsidian/Notion 直接吃 MD）。

> ⚠️ 关键认知：**MD 本就是纯文本，没有"排版"概念**。所以"转 MD"一定会丢失字体/颜色/页面布局，只保留文字+结构（标题层级/列表/表格/链接）。这是特性不是 bug——要保排版请用 office_processing.md 的原生读写，别转 MD。

---

## 一、离线环境首选：某工具（微软开源，纯 Python，一行搞定）

> 这是离线转 MD 的"瑞士军刀"——一个工具覆盖 90% 的日常文件，且**纯 Python、私有 PyPI 源可 pip**，离线可用。

**支持格式**：PDF · Word(.docx) · PPT(.pptx) · Excel(.xlsx/.xls) · HTML · CSV/JSON/XML · 图片(元数据) · 音频(转写) · EPub 等。

**安装（内网私有源）**
```bash
# ✅ 正确：必须带 extras，否则转不了 Office 文件
pip install --index-url <私有源URL> '某工具[pdf,docx,pptx,xlsx]'
# 想全功能（含 EPub/音频等）：'某工具[all]'
```
> 把 `<私有源URL>` 换成你们内网的 PyPI 镜像地址。纯 Python + 预编译 wheel，不需要 C 编译器。

> 🔴 **沙箱实测踩坑（2026-07-13）**：**绝不能只装 `pip install 某工具`（裸装）**。裸装虽然能导入，但转 docx/pptx/pdf 时会抛 `MissingDependencyException`——因为这些格式的转换器按 **extras 门控**，必须显式装 `某工具[docx,pptx,pdf,xlsx]`（或 `[all]`）。裸装只能处理 html/csv/json 等纯文本格式。此坑在内网私有源同样存在，务必把 extras 写进安装命令。

**用法**
```bash
# 命令行：一行转 MD
某工具 年报.pdf > 年报.md
某工具 幻灯片.pptx -o 输出.md
cat 表格.xlsx | 某工具 > 数据.md
```
```python
# Python API
from 某工具 import MarkItDown
md = MarkItDown()
print(md.convert("会议记录.docx").text_content)   # 直接拿 Markdown 文本
```

**特点**：
- ✅ 保留结构：标题层级（`#`/`##`）、列表、表格（`| 列 |`）、链接都会尽量保留。
- ❌ 不保样式：字体/颜色/页面布局丢失（MD 无此概念）。
- ⚠️ 离线注意：某工具 的"图片 OCR 识别文字 / 音频转写"依赖 Tesseract / OpenAI，**离线不可用**；但纯文本/表格类转换完全不受影响。

---

## 二、分格式精确控制（某工具 不够用时）

某工具 快但"粗放"。要精确控制表格/格式/公式，换下面的专用库（全部纯 Python、离线可用）：

| 来源 | 精确工具 | 做法 | 离线 |
|------|----------|------|------|
| **PDF** | **pdfplumber** | 逐页 `extract_text()` 拼 MD；`extract_table()` 转 MD 表格 | ✅ |
| **Word** | **python-docx** | 遍历 `doc.paragraphs` / `doc.tables` → 写 MD（标题按 style 映射 `#`） | ✅ |
| **PPT** | **python-pptx** | 遍历 `slide.shapes` → 每页标题+正文写 MD | ✅ |
| **Excel** | **openpyxl / pandas** | `df.to_markdown()` 一键转 MD 表格（见第三节） | ✅ |
| **HTML** | **html2text / markdownify** | `html2text.HTML2Text().handle(html)` 洗成干净 MD | ✅ |

> 选型口诀：**先 某工具 一行试**，结果不满意（表格错位/层级乱）再上对应专用库精修。

---

## 三、Excel → Markdown 表格（最高频需求，单独给命令）

```python
import pandas as pd

# 单 sheet
df = pd.read_excel("数据.xlsx")
with open("数据.md", "w", encoding="utf-8") as f:
    f.write(df.to_markdown(index=False))   # index=False 不输出行号列

# 多 sheet：逐个转，用标题分隔
xl = pd.ExcelFile("数据.xlsx")
with open("数据.md", "w", encoding="utf-8") as f:
    for sheet in xl.sheet_names:
        f.write(f"\n## {sheet}\n\n")
        f.write(xl.parse(sheet).to_markdown(index=False))
```
> 不用 pandas 也行：`openpyxl` 读单元格，自己拼 `| 列1 | 列2 |` 表格字符串。

### ⚠️ Excel 转 MD 注意事项

| 场景 | 问题 | 处理方式 |
|------|------|----------|
| **公式** | 转 MD 只保留当前值，不保留公式 | 需要公式时在 `excel_analysis.md` 中用 openpyxl 读公式（`data_only=False`），或保留 `xlsx` 原文件 |
| **合并单元格** | 合并格只保留左上角值，其余为 NaN | 转前先用 pandas `ffill()` 填充合并值 |
| **多级表头** | 转 MD 后表头可能变 MultiIndex | 转前 `df.columns = ['_'.join(col).strip() for col in df.columns]` 拉平 |
| **日期格式** | 转 MD 后日期可能变时间戳 | 转前 `df['日期'] = df['日期'].astype(str)` 固化字符串 |
| **大数据量（>10万行）** | MD 文件过大（>10MB），AI 读取困难 | 先抽样（`df.sample(1000)`）或只转关键列 |
| **条件格式/颜色** | MD 无颜色概念，语义色丢失 | 颜色编码见 `excel_analysis.md` §十六，转 MD 前用额外列标注语义 |

> 需要先分析再转 MD（如清洗→透视→转 MD 做报告）？测 `excel_analysis.md` 的分析流程，再做转换。

---

## 四、能力边界（离线环境，一眼看清能 / 不能）

| ✅ 能转成 MD | ⚠️ 不能 / 受限 |
|--------------|----------------|
| 所有 Office（docx/pptx/xlsx）+ HTML 的**文字与结构** | 扫描件 PDF（图片里没文字）→ MD（需 OCR，离线不可用，见 office_processing.md §六 边界） |
| 表格 → MD 表格（`|` 格式） | 保留原**排版/字体/颜色/图片位置**（MD 无此概念，必然丢失） |
| 标题层级 / 列表 / 链接保留 | PDF 复杂多栏排版可能错乱 → 用 pdfplumber 精修（第二节） |
| CSV/JSON/XML → MD | 富媒体（图片内嵌、音频）仅留文字/元数据，不嵌二进制 |

---

## 五、离线安装清单（私有 PyPI 源）

```bash
pip install --index-url <私有源URL> \
    '某工具[pdf,docx,pptx,xlsx]' pdfplumber python-docx python-pptx openpyxl pandas lxml html2text
```
> 这行装齐"任意文件→MD"所需全部纯 Python 依赖。运行时不联网。
> ⚠️ 注意 `某工具` **必须带 extras**（`[pdf,docx,pptx,xlsx]`），裸装转不了 Office 文件（沙箱实测，见 §一）。

---

## 六、交付验收（配合 acceptance_criteria.md）

转出 MD 后勾选：
- [ ] 文字无大量缺失 / 乱码（对比原文件扫一遍）
- [ ] 表格正确转为 MD 表格（列对齐、`|` 完整）
- [ ] 标题层级合理（`#` 对应原文档层级）
- [ ] 如涉及扫描件 PDF，已说明"离线无法 OCR，转不出文字"
- [ ] 叠加 acceptance_criteria.md 的 4 道质量闸门（规格自检 → diff 复查 → 测试证据 → 你签收）

> 本模块与 office_processing.md（二期，管"读写 Office 文件"）、excel_analysis.md（三期，管"分析 Excel"）分工明确：**本模块只管"转成 MD"这一条单向通道**。

---

## 引用来源

- 网上最佳实践（2026-07-13 检索）：
  - 微软开源 MarkItDown 多篇实测（CSDN / RealPython / 82.9k★ GitHub）——支持格式、安装、CLI/API、与 pandoc 对比、离线纯 Python 特性
  - 结论：MarkItDown 定位"为 LLM 准备文档"，保留结构而非高保真排版，正合离线转 MD 场景
- 本框架内：
  - `references/do/code/office_processing.md`（二期）——通用 Office 读写与离线边界（scan 件 OCR / 系统软件限制同源）
  - `pdf` / `docx` / `pptx` / `xlsx` 本地 skill —— 各格式精确读取的底层 API

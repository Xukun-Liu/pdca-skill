<!-- PDCA标签：D.code -->
<!-- 子标签场景：Office 文档处理 -->
<!-- 关键词清单：处理PDF/Word/PPT/Excel文件/读/写/改/转/合并/拆分/提取表格/做PPT/Excel公式/Office文档操作/文档转换/PDF/Word/PPT/Excel -->
<!-- 引用范围：main + doc_proc_agent -->

# Office 文档处理（PDF / Word / PPT / Excel）

> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.0.0 | 更新：2026-07-13
> v1.0 变更：二期交付。综合本地技能库（pdf/docx/pptx/xlsx 四个 skill）+ 网上最佳实践，沉淀为纯文本参考模块，内网可用、零外部依赖。离线边界纠正：用户环境确认=内网离线机只有 Python、不能装系统软件、但私有 PyPI 源可 pip 纯 Python 包。将 pandoc/LibreOffice/Tesseract/Poppler 标「内网离线不可用」，公式重算补纯 Python 替代库 `formulas`，§六 重写为「私有源 pip 装纯 Python + 能力边界表」。沙箱实测纠正——§6.1 依赖清单 `某工具` 加 extras（`某工具[pdf,docx,pptx,xlsx]`），裸装转不了 Office 文件。核心四格式纯 Python 离线路径已实测全 PASS（openpyxl/python-docx/python-pptx/reportlab+pdfplumber）。

> 📖 **什么时候读这个文件**：
> - 任务涉及「处理 Office 文档」——读/写/改/合并/拆分/提取/转换 PDF·Word·PPT·Excel 任意一种
> - 用户说"帮我做个 PPT""把这个 Word 改成…""从 PDF 抽表格""合并这几个 Excel""转成 PDF"
> - 需要选「用哪个库/工具」时（避免凭印象选错）
> - 交付 Office 文件前，按本文件「验收自检」一节对照（配合 acceptance_criteria.md 的 4 道质量闸门）

🔴 **不要在这时候读**：
> - 纯问答、不涉及任何 Office 文件操作
> - 只是聊文档格式概念（直接回答即可，无需按流程）

---

## 〇、先搞懂本质（决定用什么工具）

用两个生活类比记住四种格式的区别，能少踩 80% 的坑：

| 格式 | 本质类比 | 对操作的含义 |
|------|----------|--------------|
| **.docx / .pptx / .xlsx** | 一个**打包好的文件夹（ZIP 里装 XML）**，像「乐高说明书+零件清单」 | 可以**拆开改 XML 再装回去**；结构规整、可编程 |
| **.pdf** | 一张**固定版面的快照/照片**，像「打印出来的纸」 | 主要**只读/提取**；改内容难（要重排版面），扫描件更甚 |

> ⚠️ 关键推论：docx/pptx/xlsx 用「拆包改 XML」或专用库（python-docx / python-pptx / openpyxl）都能精确改；pdf 优先「提取」而非「改」，要改就用 reportlab 重画或用 LibreOffice 转格式再改。

**四大格式的「通用读取」捷径**（不确定用啥时先试这个）：
```bash
# 任意 Office 文件 → 纯文本/Markdown，一行命令
python -m 某工具 任意文件.docx    # 也支持 .pptx/.xlsx/.pdf
```
> 某工具 是「瑞士军刀」，快速看内容够用；要精确控制（表格/格式/公式）再换下面的专用库。

> 🔴 **内网离线环境红线（务必先看）**：你的离线机**只有 Python、不能装系统软件**，但内网有私有 PyPI 源能 pip 纯 Python 包。因此：
> - ⚠️ **pandoc / LibreOffice(`soffice`) / Tesseract / Poppler 全部离线不可用**（都是要装的系统软件，装不了）。
> - ✅ 本文档里**所有标注「⚠️内网离线不可用」的命令请跳过**；替代方案：转 Markdown 用 `某工具`、Excel 公式重算用纯 Python 库 `formulas`、PDF 提取用 `pdfplumber`、PDF 转图 QA 改用 `某工具` 文本核对。
> - 详见 §六「内网离线能力边界」。

---

## 一、PDF 处理

| 任务 | 首选工具 | 命令/做法 |
|------|----------|-----------|
| 提取文本（保留版面） | **pdfplumber** | `import pdfplumber; pdfplumber.open("f.pdf").pages[0].extract_text()` |
| 提取文本（速度快） | **PyMuPDF** (`fitz`) | `doc = fitz.open("f.pdf"); doc[0].get_text()` |
| 提取**表格**（有边框） | **pdfplumber** | `page.extract_table()` 返回二维数组 |
| 提取表格（高精度/无边框） | **camelot** | `camelot.read_pdf("f.pdf", pages="1")` |
| 合并 / 拆分 / 旋转 | **pypdf** | `PdfReader` / `PdfWriter` 拼接或切片 |
| 创建 PDF | **reportlab** | 用代码画文字/表格/图形生成 |
| Markdown→PDF | **pandoc** / **weasyprint** | `pandoc in.md -o out.pdf` |
| 转 Word / 图片 | **LibreOffice 无头** | `soffice --headless --convert-to docx f.pdf` |
| 扫描件 OCR（图→字） | **pdf2image + pytesseract** | 先 `pdf2image` 转图，再 `pytesseract.image_to_string(img)`（需 Tesseract OCR 引擎） |

**QA（交付前核对）**
> ⚠️ 内网离线不可用：下面 `soffice`/`pdftoppm` 转图 QA 需系统软件，离线机请跳过，改用 `某工具` 提取文本做内容核对（见 §六 边界）。
```bash
soffice --headless --convert-to pdf f.pdf 2>/dev/null  # 【离线不可用】确保最新
pdftoppm -jpeg -r 150 f.pdf page                       # 【离线不可用】生成 page-01.jpg...
# ✅ 离线替代：某工具 提取文本核对
python -m 某工具 f.pdf > f_check.md
```

**坑**：①PDF 表格经常「看得到、抽不准」——优先 pdfplumber，复杂表格上 camelot；②扫描件无法直接提取，必须 OCR；③加密 PDF 先解密再处理。

---

## 二、Word（.docx）处理

| 任务 | 首选工具 | 命令/做法 |
|------|----------|-----------|
| 读内容 | **python-docx** | `from docx import Document; Document("f.docx").paragraphs` |
| 读（含修订痕迹） | **pandoc** | `pandoc --track-changes=all f.docx -o out.md` |
| 新建文档（简单） | **python-docx** | `doc = Document(); doc.add_paragraph("正文"); doc.save("out.docx")` |
| 新建文档（排版强） | **docx-js**（JS） | `npm install -g docx`，用 JS 控制页边距/样式/目录 |
| 改已有文档（精确） | **拆包改 XML** | `unpack.py → 改 word/document.xml → pack.py`（见下方「Word 改文档铁律」） |
| 转 PDF / 图片 | **LibreOffice 无头** | `soffice --headless --convert-to pdf f.docx` → `pdftoppm` |

### Word 改文档铁律（来自 docx skill，违反必翻车）
1. **页码尺寸显式设**：docx-js 默认 A4，做美标用 `12240×15840` DXA（US Letter）。
2. **别手敲项目符号**：用 `numbering` 配置 + `LevelFormat.BULLET`，禁用 `•` 字符硬塞。
3. **表格要双宽度**：`columnWidths`（列宽数组）+ 每个单元格 `width`，二者都要、且相加=表宽（DXA 单位，1440=1英寸）；用 `ShadingType.CLEAR` 别用 SOLID（否则黑底）。
4. **分页符在段落内**：`new Paragraph({ children: [new PageBreak()] })`，独立写会生成非法 XML。
5. **图片 ImageRun 必带 type**：`type:"png"`（png/jpg/jpeg/gif/bmp/svg 必填）。
6. **目录只认 HeadingLevel**：标题必须用 `HeadingLevel.HEADING_1/2`，不能自定义样式，否则 TOC 不认。
7. **智能引号用实体**：新增文本含引号用 `&#x201C;`/`&#x2019;` 等 XML 实体，避免乱码。

> 改已有文件的稳妥路径：`unpack` → 用 Edit 工具直接改 `unpacked/word/document.xml`（不要写 Python 脚本）→ `pack --original 原文件`（自动修复 durableId、xml:space 等）。

---

## 三、PPT（.pptx）处理

| 任务 | 首选工具 | 命令/做法 |
|------|----------|-----------|
| 读内容 | **某工具** | `python -m 某工具 deck.pptx` |
| 读（精确/取形状） | **python-pptx** | `from pptx import Presentation; [s.text for s in prs.slides]` |
| 新建（无模板） | **pptxgenjs**（JS） | `npm install -g pptxgenjs`，代码生成幻灯片 |
| 新建（简单） | **python-pptx** | `prs.slides.add_slide(...)` |
| 改模板 | **拆包改 XML** | `unpack → 改 slides/slideN.xml → pack`（同 Word 思路） |
| 转图片做 QA | **LibreOffice+pdftoppm** | `soffice --headless --convert-to pdf deck.pptx` → `pdftoppm -jpeg -r 150 deck.pdf slide` |

### PPT 设计要点（来自 pptx skill，避免「AI 味」丑幻灯片）
- **配色有主有次**：一个主色占 60–70% 视觉权重，1–2 个辅色 + 1 个强调色；别默认蓝。
- **深/浅夹心**：封面+结尾深底，内容页浅底；或全程深底走高级感。
- **每页都要有视觉元素**：图/图表/图标/形状，纯文字页=废片。
- **排版变换**：别每页同款版式；两栏、图标+文字行、2×2/2×3 网格、半幅大图轮换用。
- **字号拉开对比**：标题 36–44pt 粗，正文 14–16pt，标题居中、正文左对齐。
- **禁用项**：标题下别加装饰线（AI 标志）、别做纯文字页、别混用随机间距、别浅字配浅底。

### PPT 验收（交付前必做，来自 pptx skill）
```bash
python -m 某工具 deck.pptx | grep -iE "xxxx|lorem|ipsum|this.*(page|slide).*layout"  # 查残留占位符
```
> 转图片后**用子代理做视觉 QA**（你自己看代码会「看预期不是看实际」）：查重叠、文字溢出、对比度低、间距不均、距边 <0.5″。至少做一轮「修→再验」才算完。

---

## 四、Excel（.xlsx）处理

| 任务 | 首选工具 | 命令/做法 |
|------|----------|-----------|
| 数据分析 / 清洗 | **pandas** | `df = pd.read_excel("f.xlsx"); df.describe()`；`df.to_excel("out.xlsx", index=False)` |
| 读（保留公式/格式） | **openpyxl** | `load_workbook("f.xlsx")`（公式用 `data_only=True` 读计算值） |
| 新建 / 改（格式·公式） | **openpyxl** | `wb = Workbook(); ws['A1']='x'; ws['B2']='=SUM(B3:B9)'` |
| 公式重算（必做） | **`formulas` 库（纯 Python ✅离线）** | `import formulas; m=formulas.ExcelModel().loads("f.xlsx").finish(); m.calculate(); m.write()` 算出值再写回 |

### Excel 铁律（来自 xlsx skill）
1. **用公式，别硬编码**：`ws['B10'] = '=SUM(B2:B9)'` ✅；在 Python 算完塞数字 ❌（源数据一变就失效）。
2. **公式必须重算**：openpyxl 写的是「公式字符串」不是「算好的值」。**⚠️内网离线不可用 LibreOffice**——改用纯 Python 库 `formulas`（`pip install formulas`）在离线机重算并写回计算值；否则打开是 0/空白。
3. **零公式错误**：交付前扫 `#REF! #DIV/0! #VALUE! #N/A #NAME?`，逐个修（#DIV/0! 先判分母非零，`=IF(denom=0,"",num/denom)`）。
4. **假设值单独放**：增长率/倍数等放独立「假设单元格」，公式里用单元格引用（`=B5*(1+$B$6)`），别把 1.05 写死。
5. **金融配色约定**（如涉及）：蓝字=手填输入、黑字=公式、绿字=同簿跨表引用、红字=跨文件链接、黄底=需关注假设。
6. **openpyxl 索引 1 基**：`row=1,col=1` = A1；DataFrame 第 5 行 = Excel 第 6 行，注意偏移。
7. **⚠️ data_only=True 存盘会丢公式**：只读值用 `data_only=True`，但**不要 save**；要保留公式用默认 `load_workbook`。

### 公式验证清单
- [ ] 抽 2–3 个公式核对取值是否正确
- [ ] 列映射对（第 64 列是 BL 不是 BK）
- [ ] 处理 NaN（`pd.notna()`）、除零、跨表引用格式 `Sheet1!A1`

---

## 五、通用转换枢纽（任意格式互转）

| 工具 | 能力 | 命令示例 |
|------|------|----------|
| **pandoc** ⚠️内网离线不可用 | 万能转换：md↔docx↔pdf↔html↔pptx 等（需系统软件，离线装不了） | `pandoc in.md -o out.docx` |
| **LibreOffice 无头** ⚠️内网离线不可用 | docx/xlsx/pptx/pdf 互转（需系统软件，离线装不了） | `soffice --headless --convert-to <格式> 输入文件` |
| **某工具** ✅内网离线可用 | 任意 Office → 文本/Markdown（纯 Python，私有源可 pip） | `python -m 某工具 f.pdf` |

> 一张图记住：pandoc 是「翻译官」（格式互译）、LibreOffice 是「打印机」（重排重算）——**这俩内网离线都没有，用不了**；某工具 是「朗读员」（只读出内容），**纯 Python、离线可用**，是离线环境的通用转换首选。

---

## 六、内网 / 离线可用说明（重要：本模块依赖纯 Python 包，系统软件离线不可用）

你的离线环境：**只有 Python，不能装系统软件（exe），但内网有私有 PyPI 源可 pip 装纯 Python 包**。据此：

### 6.1 ✅ 离线可用（纯 Python 包，私有源 pip 安装）
```bash
# 用内网私有源安装（把 <私有源URL> 换成你们内网的 PyPI 镜像地址）
pip install --index-url <私有源URL> \
    pdfplumber PyMuPDF pypdf python-docx python-pptx openpyxl pandas reportlab '某工具[pdf,docx,pptx,xlsx]' lxml
# 按需：PDF 表格高精度提取（camelot 依赖 opencv，纯 Python 可装但体积大）
pip install --index-url <私有源URL> camelot-py
# 按需：Excel 公式离线重算（纯 Python，替代 LibreOffice）
pip install --index-url <私有源URL> formulas
```
> 这些全是纯 Python（或带预编译 wheel），**不需要 C 编译器**，私有源里都有，离线机 pip 即得。

### 6.2 ⚠️ 离线不可用（需系统软件，装不了 → 以下功能受限）
| 系统软件 | 用途 | 离线影响 |
|----------|------|----------|
| **LibreOffice**（`soffice`） | PDF 互转、公式重算、PPT/docx 转图 | 装不了 → 见下方「能力边界」受限项 |
| **Poppler**（`pdftoppm`） | PDF→图片做视觉 QA | 装不了 → 转图 QA 做不了（用 某工具 文本核对替代） |
| **Tesseract OCR** | 扫描件 PDF 文字识别 | 装不了 → 扫描件无法 OCR（纯图片 PDF 转不出文字） |
| **pandoc** | 任意格式互转 | 装不了 → 用 某工具 替代「转 Markdown」 |
| Node 库（docx/pptxgenjs） | 排版更强的 Word/PPT 生成 | npm 全局装在离线机通常也受限 → 用 python-docx / python-pptx 替代 |

### 6.3 📊 内网离线能力边界（一眼看清能 / 不能）
| 格式 | ✅ 能（离线） | ⚠️ 不能（离线，缺系统软件） |
|------|--------------|------------------------------|
| Excel `.xlsx` | 读/写/改/公式/数据分析（openpyxl/pandas）、公式重算（`formulas`） | — 全都能 |
| Word `.docx` | 读/写/改/提取（python-docx） | 转 PDF（保排版）、修订痕迹比对（pandoc） |
| PPT `.pptx` | 读/写/改/提取（python-pptx） | 转图做视觉 QA、转 PDF（保排版） |
| PDF | 提取文字/表格（pdfplumber）、合并/拆分（pypdf）、生成（reportlab） | 扫描件 OCR、PDF↔Word/PPT 互转、转图 QA |
| 任意 → Markdown | **某工具 一行搞定**（pdf/docx/pptx/xlsx/html） | 保原排版（MD 本就是纯文本，只留结构不留样式） |

> 📌 结论：**读/写/改 Office 文件 + 提取内容 + 转 Markdown，离线全搞定**；受限的是「格式互转美化 / 扫描件识别 / 渲染成图」这类需系统软件的花活。详见四期 `references/do/code/file_to_markdown.md`（专讲转 MD）。

---

## 七、交付验收自检（配合 acceptance_criteria.md）

交付任何 Office 文件前，按格式勾选：

| 格式 | 必过项 |
|------|--------|
| PDF | 文本/表格提取准确（⚠️离线：扫描件 OCR 与转图 QA 不可用，见 §六 边界） |
| Word | 能正常打开无报错；页码/边距正确；表格不乱；TOC 正常（如有） |
| PPT | 无占位符残留；转图后无重叠/溢出/低对比；每页有视觉元素 |
| Excel | **零公式错误**；公式已重算（值正确）；假设单元格独立；源数据变动能联动 |

> 这四项是 DoD 的「专项底线」，叠加 acceptance_criteria.md 的 4 道质量闸门（规格自检→diff 复查→测试证据→你签收）构成完整验收闭环。

---

## 引用来源

- 本地技能库（本机已装，纯文本可用）：
  - `pdf` skill — PDF 读取/转换/OCR 流程
  - `docx` skill — Word 新建/改 XML/排版铁律/设计要点
  - `pptx` skill — PPT 读取/设计/视觉 QA 流程
  - `xlsx` skill — Excel 公式优先/重算/零错误/金融配色规范
- 网上最佳实践（2026-07-13 检索）：
  - 今日头条《Python全能文档提取：Word/Excel/PDF/PPT 一站式》（库选型对比）
  - CSDN《Python 办公自动化实战教程》（openpyxl/pandas/python-docx/PyMuPDF 安装与用法）
  - CSDN CANN 社区《跨格式处理关键技术栈》（pdfplumber vs PyPDF2、unstructured 多格式）
  - CSDN《使用 Python 一站式提取四种文档》（按扩展名自动路由的提取函数示例）

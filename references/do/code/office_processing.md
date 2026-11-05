<!-- PDCA标签：D.code -->
<!-- 子标签场景：Office 文档处理 -->
<!-- 关键词清单：处理PDF/Word/PPT/Excel文件/读/写/改/转/合并/拆分/提取表格/做PPT/Excel公式/Excel作图/Excel图表/Word插图/文档里加图/Office文档操作/文档转换/PDF/Word/PPT/Excel -->
<!-- 引用范围：main + doc_proc_agent -->

# Office 文档处理（PDF / Word / PPT / Excel）

> 阶段标签：D（旧标签，以头部 PDCA 标签为准）

> 版本：v1.2.0 | 更新：2026-11-05
> v1.2 变更：补「Excel 原生图表」（`openpyxl.chart`：BarChart/LineChart/PieChart/ScatterChart，活图可二次编辑）与「Word 插图」（matplotlib PNG → `doc.add_picture()`，含图题与编号），解决「只在文件里排表格、不会在文件里放图」的缺口；选图与 matplotlib 模板统一外链 [chart_cookbook.md](../../common/pd/chart_cookbook.md)。来源：openpyxl/python-docx 官方文档 + FT Visual Vocabulary 选型约束。
> v1.1.0 变更：二期交付。综合本地技能库（pdf/docx/pptx/xlsx 四个 skill）+ 网上最佳实践，沉淀为纯文本参考模块，内网可用、零外部依赖。离线边界纠正：用户环境确认=内网离线机只有 Python、不能装系统软件、但私有 PyPI 源可 pip 纯 Python 包。将 pandoc/LibreOffice/Tesseract/Poppler 标「内网离线不可用」，公式重算补纯 Python 替代库 `formulas`，§六 重写为「私有源 pip 装纯 Python + 能力边界表」。沙箱实测纠正——§6.1 依赖清单 `某工具` 加 extras（`某工具[pdf,docx,pptx,xlsx]`），裸装转不了 Office 文件。核心四格式纯 Python 离线路径已实测全 PASS（openpyxl/python-docx/python-pptx/reportlab+pdfplumber）。

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
| **插图 / 放图表** | **python-docx** | `doc.add_picture("chart.png", width=Inches(6))`（见下方「Word 插图」） |
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

### Word 插图（matplotlib 出 PNG → `doc.add_picture()`）

> Word 里放的是**死图**（一张定格的 PNG，对方不能点数据改图）。要活图用 Excel 原生图表（§四）。**画什么图、怎么画**先看 [chart_cookbook.md](../../common/pd/chart_cookbook.md)（关系驱动选型 + 6 个 matplotlib 模板），本节只管"把图塞进 Word 并排好版"。

```python
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()
doc.add_heading("2026 年三季度经营复盘", level=1)
doc.add_paragraph("三季度营收同比 +18%，主要来自华东区新客。")

# 1) 插图：PNG 由 matplotlib 预先保存（dpi=200 以上，宽度按版心定）
doc.add_picture("revenue_trend.png", width=Inches(6.0))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER      # ① 图居中

# 2) 图题：图下、居中、9pt、编号连续（图 1 / 图 2 …）
cap = doc.add_paragraph("图 1  2026 年 1–9 月营收趋势（口径：含税确认收入，来源：财务系统）")
cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap.runs[0].font.size = Pt(9)

doc.save("report.docx")
```

**四条规矩**
1. **宽度 ≤ 版心**：A4 默认页边距 2.54cm，版心约 16cm；`Inches(6.0)` ≈ 15.2cm 安全，别超过 `Inches(6.3)`。
2. **图题在图下**：编号连续（图 1、图 2…），图题写"看什么 + 口径 + 数据来源"，不要只写"图 1 营收"。
3. **分辨率**：matplotlib 保存时 `dpi=200` 起（默认 100 打印会糊），`bbox_inches="tight"` 去白边。
4. **一图一结论**：图上方正文先写结论句，图只是证据；别放"装饰图"。

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
| **作图（原生图表·活图）** | **openpyxl.chart** | `ws.add_chart(chart, "E2")`（见下方「Excel 原生图表」；选图先看 chart_cookbook） |

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

### Excel 原生图表（`openpyxl.chart`，活图）

> **活图 = 图表对象存在 xlsx 里**（对方点一下能改数据、换类型、调样式），比贴 PNG 强的地方就在这。**选什么图**先看 [chart_cookbook.md](../../common/pd/chart_cookbook.md) §一（关系驱动决策表），本节只讲怎么写进 xlsx。

**选型对照（与 chart_cookbook 的 6 类关系一一对应）**

| 想表达 | 用哪个类 | 关键参数 |
|--------|----------|----------|
| 比大小（类别 ≤ 12） | `BarChart` | `type="col"`（竖）/"bar"（横）+ `grouping="clustered"` |
| 看趋势（时间序列） | `LineChart` | `marker=True` 标数据点；**别开 smooth**（会伪造中间值） |
| 看占比（≤ 5 类） | `PieChart` | 单列数据 + `dataLabels.showPercent=True` |
| 看相关（两个数值列） | `ScatterChart` | 用 `Series(values, xvalues)`，**不是** `add_data` |
| 看构成变化 | `BarChart` | `grouping="stacked"` / `"percentStacked"` |

**完整可跑示例（簇状柱：一季度分区营收）**

```python
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList

wb = Workbook()
ws = wb.active
ws.title = "月度营收"

# ① 先把数据写进单元格——图表只认单元格区域，不认 Python 里的 list
ws.append(["月份", "华东", "华北"])                      # A1:C1 表头
for row in [["1月", 120, 90], ["2月", 135, 88], ["3月", 158, 102]]:
    ws.append(row)                                      # A2:C4 数据

# ② 引用区域（openpyxl 行列均 1 基）
cats = Reference(ws, min_col=1, min_row=2, max_row=4)                    # 分类轴 A2:A4
data = Reference(ws, min_col=2, max_col=3, min_row=1, max_row=4)         # B1:C4（含表头）

# ③ 建图 + 绑定数据
chart = BarChart()
chart.type = "col"                  # col=纵向柱 / bar=横向条
chart.grouping = "clustered"        # clustered / stacked / percentStacked
chart.title = "一季度分区营收（万元）"
chart.x_axis.title = "月份"
chart.y_axis.title = "营收（万元）"
chart.add_data(data, titles_from_data=True)   # 表头 → 图例
chart.set_categories(cats)                    # 分类轴
chart.dLbls = DataLabelList()
chart.dLbls.showVal = True                    # 柱顶显示数值
chart.height, chart.width = 8, 16             # 单位 cm
chart.legend.position = "b"

# ④ 锚定到单元格（锚点=图表左上角，别压住数据区）
ws.add_chart(chart, "E2")
wb.save("report.xlsx")
```

**另外三种的最小差异**

```python
# 折线（趋势）
from openpyxl.chart import LineChart
lc = LineChart(); lc.title = "月度营收趋势"; lc.marker = True
lc.add_data(data, titles_from_data=True); lc.set_categories(cats)

# 饼图（占比，单列数据 + 百分比标签）
from openpyxl.chart import PieChart
pc = PieChart(); pc.title = "三季度渠道占比"
pc.add_data(Reference(ws, min_col=2, min_row=1, max_row=4), titles_from_data=True)
pc.set_categories(cats)
pc.dataLabels = DataLabelList(); pc.dataLabels.showPercent = True   # 注意是 dataLabels 不是 dLbls

# 散点（相关，两个数值列 → Series(values, xvalues)，下面示例 x=B 列、y=C 列）
from openpyxl.chart import ScatterChart, Series
sc = ScatterChart(); sc.title = "投入 vs 产出"
xv = Reference(ws, min_col=2, min_row=2, max_row=20)
yv = Reference(ws, min_col=3, min_row=2, max_row=20)
sc.series.append(Series(yv, xv))
sc.x_axis.title = "投入"; sc.y_axis.title = "产出"
```

**六条铁律**
1. **先落数据再画图**：图表只认 `Reference` 指向的单元格，Python 变量喂不进去；数据区（分类列 + 数值列）必须相邻且表头唯一。
2. **`titles_from_data=True` 才有图例**：`min_row` 必须含表头行，否则图例变成 "Series 1"。
3. **openpyxl 不渲染图**：它只写 XML，**Excel/WPS 打开那一刻才画出来**——所以"打开前看不到图"不是失败，别为验证去装 LibreOffice（§六 已说明离线装不了）。
4. **图型选择回到 chart_cookbook**：3D、爆炸饼、双 Y 轴属于"视觉噪音"，除非对方明确要求。
5. **锚点与尺寸**：`add_chart(chart, "E2")` 的锚点要避开数据区；`height/width` 以 cm 计，常用于 8×16（横向）或 10×14（纵向）。
6. **一表多图要排版**：同一 Sheet 超过 2 张图就按网格对齐锚点，或者拆到独立「看板」Sheet。

### 📎 交叉引用

| 需要做什么 | 读哪个文件 |
|-----------|-----------|
| **选什么图 / matplotlib 怎么画（Word 插图的 PNG 从哪来）** | **[chart_cookbook.md](../../common/pd/chart_cookbook.md)**（关系驱动选型 6 类 + 6 个可复制模板 + 诚实性红线） |
| 数据分析（清洗/透视/统计/图表/趋势/拆解/异常/看板/报告） | **[data_analysis.md](../../common/pd/data_analysis.md)**（数据分析方法论，D.code/P.design） |
| 颜色编码体系（金融模型蓝/黑/绿/红标准） | `data_analysis.md` 第十六章 |
| 可视化设计原则（反"AI 生成味"） | `data_analysis.md` 第十七章 |
| 专业表格格式规范（斑马纹/边框/KPI 高亮/样式助手函数） | `data_analysis.md` 第十八章 |
| 做表前规划方法论（Sheet/Schema/Style 三计划） | `data_analysis.md` 第十九章 |
| 文件转 Markdown | **[file_to_markdown.md](file_to_markdown.md)**（D.code，单向转换） |

> 关系：三个模块分工——**office_processing.md** 管"文件层"（Excel/Word 读写改 + 图怎么落进文件：Excel 原生图表 / Word 插图）；**data_analysis.md** 管"分析层"（数据怎么算出结论）；**chart_cookbook.md** 管"选型 + 画图层"（选什么图、matplotlib 怎么写）。涉及分析/透视时先读 `data_analysis.md`，涉及作图先读 `chart_cookbook.md`。

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
# 按需：Word 插图 / matplotlib 出 PNG（带预编译 wheel，离线机可用；选型与模板见 chart_cookbook.md）
pip install --index-url <私有源URL> matplotlib
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
| Excel `.xlsx` | 读/写/改/公式/数据分析（openpyxl/pandas）、公式重算（`formulas`）、**原生图表**（`openpyxl.chart`） | — 全都能（图表由对方 Excel/WPS 打开时渲染） |
| Word `.docx` | 读/写/改/提取（python-docx）、**插图**（matplotlib PNG + `add_picture`） | 转 PDF（保排版）、修订痕迹比对（pandoc） |
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
| Word | 能正常打开无报错；页码/边距正确；表格不乱；TOC 正常（如有）；**插图不超版心、图题居中且编号连续、图上正文有结论句** |
| PPT | 无占位符残留；转图后无重叠/溢出/低对比；每页有视觉元素 |
| Excel | **零公式错误**；公式已重算（值正确）；假设单元格独立；源数据变动能联动；**图表引用区域正确、锚点不压数据、图型与结论匹配（chart_cookbook）** |

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

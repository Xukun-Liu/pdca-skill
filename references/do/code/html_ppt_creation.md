<!-- PDCA标签：D.code -->
<!-- 子标签场景：HTML 网页制作 / PPT 幻灯片制作 自包含方法论 -->
<!-- 关键词清单：做网页/前端/HTML/落地页/网站/组件/页面/landing/做PPT/幻灯片/演示文稿/课件/汇报/讲课/deck/HTML制作/PPT制作/网页制作/做PPTX/生成PPT -->
<!-- 引用范围：main + doc_proc_agent -->

# HTML / PPT 制作方法论（自包含 · 内网离线可用）

> 阶段标签：D.code
> 版本：v1.0.1 | 更新：2026-08-13
> 本文档是"做 HTML 网页 / 做 PPT 幻灯片"的**自包含方法论**——不依赖任何外部插件/skill，纯本地可执行，内网离线可用（环境边界见 §四）。
> 与 office_processing.md 的分工：office_processing 管"python-pptx 读写 .pptx 文件"（文件操作层）；本文档管"HTML/PPT 怎么做得好"（视觉方法论 + 制作路线 + 可执行骨架）。

---

## 📖 什么时候读这个文件

> - 用户说"帮我做个网页/落地页/网站/前端页面/组件"
> - 用户说"帮我做个 PPT/幻灯片/演示文稿/课件/汇报/讲课 deck"
> - 需要选"HTML 用什么方式 / PPT 用什么路线"时（避免凭印象硬上）
> - 交付网页/PPT 前，按本文档「验收要点」一节对照

🔴 **不要在这时候读**：
> - 只是处理已有 Office 文件（读/改/转换）→ 走 office_processing.md
> - 只是画一张示意图/速览图（非网页非 PPT）→ 走 hand-drawn-report.md
> - 纯问答、不涉及制作 → 直接回答

---

## 〇、先搞懂本质（决定走哪条路线）

用两个类比记住"HTML 网页"和"PPT 幻灯片"的区别：

| 形态 | 本质 | 典型场景 | 交付物 |
|------|------|----------|--------|
| **HTML 网页** | 一个**可交互的应用程序**（浏览器里跑） | 落地页/官网/组件/数据看板 | `.html`（可挂到任意静态服务器） |
| **PPT 幻灯片** | 一页页**固定幅面的演示** | 汇报/讲课/提案/产品演示 | `.pptx`（可编辑）或 `.html`（网页 PPT） |

**三条自包含路线**（全部内网可执行，无需外部插件）：

| 路线 | 实现方式 | 何时选它 |
|------|----------|----------|
| **A. 可编辑 .pptx** | python-pptx（纯 Python）或 PptxGenJS（Node，内网可用时） | 用户要能在 PowerPoint 里改、要正式交付的演示文件 |
| **B. HTML 幻灯片** | 手写单文件 HTML（16:9 舞台 + 键盘翻页），Node 可导出 pptx/pdf | 要快速出网页 PPT、带交互/动画、方便在线分享 |
| **C. HTML 网页/前端** | 手写 HTML/CSS/JS | 做落地页/官网/组件/看板等真正的网页 |

> 核心判断：用户要"能编辑的文件"→ 路线 A；用户要"好看能演示/在线看"→ 路线 B；用户要"真正的网站/页面"→ 路线 C。

---

## 一、PPT 幻灯片制作（路线 A：可编辑 .pptx）

### 1.1 工具选型

| 工具 | 环境 | 适用 |
|------|------|------|
| **python-pptx** | 纯 Python（pip 安装） | 最稳妥，内网必可用；适合从零建、批量生成、表格图表 |
| **PptxGenJS** | Node（npm） | 内网有 Node 时可选；适合重复版式、原生图表、模板、程序化检查 |

> 内网边界（§四）：优先 python-pptx；若内网 Node 可用，要"可编辑 + 原生图表/模板"时用 PptxGenJS 更顺手。两者做出来的都是可编辑 .pptx，可按环境二选一。

### 1.2 PPT 视觉方法论（六风格配方 + 构图纪律）

**先写"风格简报"再排版**：受众 → 要促成的判断/行动 → 内容类型 → 展示场景 → 情绪基调，浓缩成三个形容词 + 一个设计张力 + 密度/配色/字体逻辑。

**风格配方按任务挑**（每套只选最接近的一份，混合时声明主次）：

| 任务类型 | 风格方向 | 配色基调 | 版式倾向 |
|----------|----------|----------|----------|
| 咨询/研究报告 | 咨询研报风 | 深蓝+灰+单强调色 | 左结论右证据、数据网格、图表密集 |
| 管理/工作汇报 | 正式工作汇报风 | 沉稳（藏蓝/墨绿/灰）+白 | 标题栏+正文区、要点式、留白克制 |
| 党建/civic 活动 | 社区党建风 | 红金、庄重 | 对称、大字标语、实景配图 |
| 创意/市集/海报 | 艺术市集风 | 高饱和撞色 | 大图满版、非对称、字体大胆 |
| 编辑/文化/画廊 | 编辑画册风 | 黑白+点缀色 | 杂志网格、大留白、衬线字体 |
| 历史教学/博物馆 | 历史教学风 | 做旧纸张感+复古色 | 时间线、档案式图文、横版插图 |

**构图五纪律**：
1. 每页只设一个主要结论，选能表达它的页面轮廓（证据网格/对比/时间线/表格/满版图/海报构图/综合结论）
2. 先建垂直结构：页眉、标题、标题与正文间距、主体内容区、结论或来源区、页脚安全区
3. 先靠分组/对齐/证据结构增加信息密度，再考虑缩小字号（密度优先于字号）
4. 字体/外边距/颜色角色/线条/页脚规则一致，在此前提下变化页面轮廓
5. 深/浅夹心：封面+结尾深底、内容页浅底；或全程深底走高级感。每页都要有视觉元素（图/图表/图标/形状），纯文字页=废片

### 1.3 python-pptx 代码骨架（可直接落地）

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width = Inches(13.33)   # 16:9
prs.slide_height = Inches(7.5)

# 空白版式
blank = prs.slide_layouts[6]

# ---- 封面页（深底） ----
slide = prs.slides.add_slide(blank)
bg = slide.background.fill
bg.solid(); bg.fore_color.rgb = RGBColor(0x1F, 0x2A, 0x44)  # 深藏蓝
tb = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(2))
tf = tb.text_frame; tf.text = "主标题"
p = tf.paragraphs[0]
r = p.add_run(); r.text = "副标题/日期"
r.font.size = Pt(18); r.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

# ---- 内容页：标题 + 要点 ----
slide2 = prs.slides.add_slide(blank)
t = slide2.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(12), Inches(0.9))
t.text_frame.text = "章节标题"
t.text_frame.paragraphs[0].font.size = Pt(32); t.text_frame.paragraphs[0].font.bold = True

# 正文要点（14-16pt 正文，左对齐）
body = slide2.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12), Inches(5))
tf2 = body.text_frame
for line in ["要点一：…", "要点二：…", "要点三：…"]:
    p = tf2.add_paragraph(); p.text = line; p.font.size = Pt(16)

prs.save("out.pptx")
```

> 更多 python-pptx 用法（表格/图片/形状/改已有文件）见 office_processing.md §三；**交付前务必按 §三验收**。

### 1.4 PptxGenJS 要点（内网有 Node 时）

- 用 npm 安装 `pptxgenjs`，JS 里 `const pptx = new PptxGenJS(); pptx.defineLayout({name:'W',width:13.33,height:7.5});` 建 16:9
- 序号/日期/百分比/金额/页码用**单行文本保护**（不要拆多行导致换行错位）
- 图表/表格/形状用原生 API（`slide.addChart` / `addTable` / `addShape`），保持可编辑
- 复用模板时保持文字、表格、图表可编辑，不做位图化
- 交叉渲染（PowerPoint/LibreOffice）仅当字体、裁剪、图表存在已知风险时才做

---

## 二、HTML 幻灯片制作（路线 B：单文件，零依赖）

### 2.1 单文件骨架（内网浏览器直接打开即用）

```html
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>演示文稿标题</title>
<style>
  html,body{margin:0;background:#e8e8e8;font-family:system-ui,"Microsoft YaHei",sans-serif}
  .deck{max-width:1280px;margin:24px auto}
  .slide{width:1280px;height:720px;background:#fff;margin-bottom:24px;
         box-shadow:0 2px 12px rgba(0,0,0,.15);position:relative;overflow:hidden;
         display:flex;flex-direction:column;justify-content:center;padding:56px;box-sizing:border-box}
  .kicker{font-size:16px;color:#888;letter-spacing:2px;margin-bottom:8px}
  h1,h2{margin:0 0 16px;line-height:1.3}
  .body{font-size:20px;line-height:1.7;color:#333;max-width:1000px}
  @media print{ body{background:#fff} .slide{page-break-after:always;box-shadow:none} }
</style>
</head>
<body>
<div class="deck" id="deck">
  <section class="slide"><div class="kicker">01 · 封面</div><h1>主标题</h1><div class="body">副标题 / 汇报人 / 日期</div></section>
  <section class="slide"><div class="kicker">02 · 目录</div><h1>本次内容</h1><div class="body">一、…　二、…　三、…</div></section>
  <section class="slide"><div class="kicker">03 · 正文</div><h1>一个核心观点</h1><div class="body">支撑证据 / 数据 / 图。</div></section>
</div>
<script>
// 键盘翻页（浏览器演示）：F 全屏、左右键翻页
document.addEventListener('keydown', e => {
  const slides = document.querySelectorAll('.slide');
  let i = [...slides].findIndex(s => s.getBoundingClientRect().top >= 0);
  if (e.key === 'ArrowRight' || e.key === ' ') i = Math.min(i+1, slides.length-1);
  if (e.key === 'ArrowLeft') i = Math.max(i-1, 0);
  slides[i].scrollIntoView({behavior:'smooth'});
});
</script>
</body>
</html>
```

> 骨架要点：固定 `16:9` 舞台整体缩放（禁视口断点覆写内排版）、垂直卡片流、打印时 `page-break-after:always` 便于存 PDF。图片路径用相对路径（与 HTML 同目录 `images/`）。

### 2.2 叙事方法（先想故事再排版）

1. **先做 Story Plan 再选版式**：每页只给一个"叙事任务" + 一个"主观点"；整份 deck 有叙事弧——开场（抛主题/悬念）→ 发展（证据/机制/对比）→ 收束（结论/建议/下一步）
2. **默认 8–10 页**（含封面 + 结尾页）；连续多页纯文字 = 信号，补证据不补废话
3. **布局 5 大类轮换**：结构页（封面/目录/结尾，必含）+ 内容页（品牌/网格/卡片/列表/观点/图表）+ 图片页（画廊/分屏/双图/三图/主角）+ 高密度页（表格/指标/对比/看板）+ 自由页
4. **图片是默认不是例外**：多数页面应带图（用户提供的图 / 截图 / 图表）；仅有"纯排版更强"的例外才用纯文字（定义/论点/引语/指标）

### 2.3 Node 导出 pptx/pdf（内网有 Node 时，用户明确要才做）

- 用 `pptxgenjs` 的 HTML→PPT 思路：逐页重建文字/图表/形状（HTML 结构映射到 pptx API）
- 用无头浏览器（如 puppeteer 或 `playwright`，内网需能 pip/npm 到）把 HTML 打印成 PDF
- 交付原则：默认交付 HTML；用户明确要 .pptx/.pdf 才导出；优先可编辑 pptx

---

## 三、HTML 网页制作（路线 C：手写，零依赖）

### 3.1 前端设计五原则（反"AI 味"红线）

1. **先定审美方向再写码**：目的 → 基调（极简/复古未来/编辑杂志/艺术装饰…）→ 约束 → 差异化。挑一个概念方向执行到底，比均匀混搭更高级
2. **字体是第一印象**：禁用 Arial/Inter/Roboto 等通用字体；选有辨识度的标题字体 + 精良正文字体搭配
3. **配色"主次分明"**：1 个主色占 60–70% 视觉权重 + 1–2 辅色 + 1 强调色；用 CSS 变量统一；禁"白底紫渐变"等烂大街组合
4. **动效只做高光时刻**：一次编排良好的页面加载（staggered reveals 用 `animation-delay`）胜过散落微交互；优先 CSS-only
5. **构图敢打破网格**：不对称/叠层/对角线/破格元素/留白或高密度二选一；背景用渐变网格/噪点/纹理营造层次，别用纯色

### 3.2 网页结构规范

- **语义化标签**：`<header>/<main>/<section>/<footer>`，标题层级 h1→h3 不跳级
- **CSS 变量统一主题**：`--color-primary/--color-bg/--font-display/--radius` 等，全局引用，改一处全站生效
- **响应式基础**：`clamp()` 控制字号、`grid`/`flex` 自适应、移动端断点只调容器不调内容
- **性能**：图片给 `width/height` 防布局抖动，`loading="lazy"` 懒加载，动效用 `transform/opacity`（GPU 友好）

### 3.3 网页图表（内网无 CDN → 手写 SVG 或本地 ECharts）

内网离线**不能依赖 CDN**。两种做法：

**① 手写 SVG（零依赖，最简单）**——柱状图/折线图/环形图都够用：

```html
<svg viewBox="0 0 600 300" width="100%" height="300">
  <!-- 柱状图：每组柱子 rect + 数值 text -->
  <rect x="40"  y="120" width="70" height="150" fill="#4a7dff"/>
  <text x="75"  y="110" text-anchor="middle" font-size="14">150</text>
  <rect x="160" y="80"  width="70" height="190" fill="#6c8cff"/>
  <text x="195" y="70"  text-anchor="middle" font-size="14">190</text>
  <rect x="280" y="40"  width="70" height="230" fill="#a78bfa"/>
  <text x="315" y="30"  text-anchor="middle" font-size="14">230</text>
  <!-- 轴 -->
  <line x1="30" y1="270" x2="570" y2="270" stroke="#999" stroke-width="2"/>
</svg>
```

**② 本地 ECharts**——若内网已有 `echarts.min.js` 本地文件，引入后用 `echarts.init(el).setOption({...})`；没有本地文件则用方案①。

> 图表纪律：选型匹配数据任务（比较→柱状、趋势→折线、占比→环形）、坐标轴有单位、数值与源数据一致、容器不空白。

### 3.4 图片素材（内网规则）

- **内网无在线图像生成**。图片来源优先级：① 用户提供 → ② 现有素材/截图 → ③ 纯排版（无图时用色块/图标/图表/几何装饰填补视觉，禁用占位图）
- 图片路径用相对路径，放 HTML 同目录 `images/`；给 `alt` 描述文本
- 若内网环境未来提供图像生成能力，按其接口用；当前默认"无在线生成"

### 3.5 验收（网页）

无占位图残留；无通用字体/烂大街配色；图片真实可加载；动效不喧宾夺主；响应式基本可用；纯色背景有纹理/层次补充

---

## 四、内网环境边界（重要）

你的内网环境（本文档假设）：**纯 Python（私有 PyPI 可 pip 纯 Python 包）+ 有 Node 环境 + 无外网/CDN**。据此：

| 能力 | ✅ 可用 | ⚠️ 注意 |
|------|---------|---------|
| python-pptx 做 .pptx | ✅ `pip install python-pptx` | 做出来的 .pptx 可用 PowerPoint 打开编辑 |
| PptxGenJS 做 .pptx | ✅ 内网有 Node + npm | 优先可编辑、原生图表/模板 |
| 手写 HTML 网页/幻灯片 | ✅ 零依赖 | 图片用用户提供/本地，无在线生成 |
| 网页图表 | ✅ 手写 SVG 或本地 echarts.min.js | 无 CDN，禁 `<script src="https://...">` |
| 转图视觉 QA | ⚠️ LibreOffice/渲染器内网可能不可用 | 用 python-pptx 读回文本核对；HTML 用浏览器/打印预览核对 |

> 结论：**做 PPT（python-pptx / pptxgenjs）+ 做 HTML（手写）内网全搞定**；受限的只是"在线图片生成 / CDN 图表 / 渲染成图 QA"这类联网花活。

---

## 五、验收要点（交付前必做）

| 产出 | 必过项 |
|------|--------|
| **可编辑 .pptx** | 无占位符残留（lorem/ipsum/待定/xx）；每页有视觉元素；python-pptx 读回核对文字与结构；转图 QA（若有渲染器）无重叠/溢出/低对比 |
| **HTML 幻灯片** | 每张是完整卡片（舞台+内容+页码）；无 `[占位]` 残留；图片相对路径可加载；浏览器打开正常、键盘翻页可用 |
| **HTML 网页** | 无占位图；无通用字体/烂大街配色；图片真实可加载；动效不喧宾夺主；响应式基本可用 |
| **通用** | 视觉 QA 用独立子代理看实际效果（自己看代码会"看预期不看实际"），至少"修→再验"一轮 |

---

## 六、交叉引用

| 需要做什么 | 读哪个文件 |
|-----------|-----------|
| 处理已有 Office 文件（读/写/改 .pptx 等） | **[office_processing.md](office_processing.md)**（D.code，文件操作层） |
| Office 文件转 Markdown | **[file_to_markdown.md](file_to_markdown.md)**（D.code） |
| 画示意图/速览图/报告顶图（非网页非 PPT） | **[hand-drawn-report.md](../../common/da/hand-drawn-report.md)**（D+A，手绘 SVG） |
| 数据分析 + 图表方法 | **[excel_analysis.md](../../common/pd/excel_analysis.md)**（P+D，第十七章可视化设计原则） |
| 网页/PPT 视觉 QA 交子代理 | **[subagents_rj.md](../../common/pda/subagents_rj.md)**（doc_proc_agent） |

> 关系：office_processing 管"PPT 文件怎么读写"，本文档管"HTML/PPT 怎么做得好"（视觉方法论 + 可执行骨架），两者互补。

---

## 引用来源

- 方法论提炼自本机已装 trae 插件（frontend-design 前端美学 / web-app-development·uicraft UI/UX / jingmei-ppt PPT 视觉配方 / ppt-generator HTML 幻灯片叙事与布局 / ppt-page 教学画廊 / chart-visualization 图表选型），已**内化为自包含模块，不依赖插件**——换到无插件的内网环境仍可照本文档执行

<!-- PDCA标签：P.design D.code -->
<!-- 子标签场景：数据图表选型（关系驱动）+ matplotlib 可复制模板 -->
<!-- 关键词清单：画数据图/画个图表/柱状图/条形图/折线图/趋势图/直方图/箱线图/散点图/堆叠柱/占比图/排名图/图表选型/用什么图/matplotlib模板/中文乱码/图表配色/图表标题 -->
<!-- 引用范围：main + doc_proc_agent -->

# 图表代码模板库（关系驱动选型 + 可复制模板）

> 版本：v1.0.0 | 更新：2026-11-05
> 阶段标签：P.design D.code
> 方法论底座：FT Visual Vocabulary（按"数据关系"分类，而非按图型分类）+《用数据讲故事》（诚实性红线）

> 📖 **什么时候读这个文件**：
> - 要画数据图，但不确定该用哪种图
> - 已有图，但读者反馈"看不出想说什么"
> - matplotlib 中文乱码、图丑、图例挤成一团
> 🔴 **不要在这时候读**：
> - 画流程图/架构图/时序图/桑基图/鱼骨图等结构图 → [diagram-design.md](../da/diagram-design.md)
> - 只要 Excel 原生图表或 Word 插图 → [office_processing.md](../../do/code/office_processing.md)
> - 还没做数据清洗和对账，结论都还没出来 → 先读 [data_analysis.md](data_analysis.md)

---

## 〇、本质：先定关系，再定图型

一句话：**图型是结果，数据关系才是输入。**

三种驱动方式的差别，决定了图能不能替你说清事：

| 驱动方式 | 思考起点 | 典型翻车 | 结论 |
|----------|----------|----------|------|
| 图型驱动 | "我会画柱状图" | 所有数据都画成柱状图 | 工具反而限制表达 |
| 工具驱动 | "Excel 里第一个按钮是饼图" | 5 个类别硬塞饼图 | 图和结论错配 |
| **关系驱动** | **"我想让人看到什么关系"** | —— | **推荐：先关系后图型** |

固定五步，别跳：

1. **写一句结论**：「华东贡献六成销售额，但增速最慢」——写不出这句话说明还不知道要说什么，此时画图只是装饰数据
2. **判关系**：这句话在比较大小、看变化、看构成、看分散、看相关、还是看排名？
3. **查表选图**：见第一节
4. **套模板**：见第二节，改数据即可
5. **过诚实性检查**：见第三节，六条红线逐条过

> 这句结论同时就是图表标题——图标题写结论，不写"XX 图"。

---

## 一、选图决策表（6 类关系）

| 关系 | 30 秒自问 | 推荐图型 | 数据形态 | 避免 |
|------|-----------|----------|----------|------|
| **对比** | 几个对象在同一条尺子上比大小？ | 横向条形图（类别名长）/ 纵向柱形图（类别名短） | 1 个分类列 + 1 个数值列，3-12 类 | 折线（会暗示连续性）、饼图 |
| **趋势** | 同一个指标随时间怎么变？ | 折线图（≤5 条线）/ 小倍数图（>5 条线） | 时间列 + 数值列，≥6 个时间点 | 柱状图（时间点多了像梳子）、饼图 |
| **分布** | 数值集中在哪、尾巴有多长？ | 直方图（看形状）/ 箱线图（多组对比） | 单列数值，≥30 条 | 只报平均值（掩盖双峰和长尾） |
| **构成** | 整体由哪几块拼成、各占多少？ | 百分比堆叠柱（跨时间/跨组）/ 饼图（仅 2-3 类） | 分类列 + 数值列，各组和为整体 | 饼图超过 3 类、环形图堆装饰 |
| **相关** | 两个数值变量是否同涨同落？ | 散点图（+ 拟合线 + 相关系数） | 两列连续数值，≥20 点 | 相关系数当因果结论 |
| **排名** | 谁前谁后、差距多大？ | 排序条形图（Top N + 其他） | 分类列 + 数值列，降序 | 按字母序排列、把 Top 20 全画进去 |

**关系判断不了时的兜底**：先问「读者看完这张图，应该能做哪个决定？」——决定的形态决定关系类型（选哪家=对比，什么时候进场=趋势，集中投哪=排名）。

---

## 二、matplotlib 模板（每类 1 个，复制即用）

### 2.0 通用底座（所有模板先跑这一段）

```python
import matplotlib
matplotlib.use("Agg")            # 无界面环境也能存图
import matplotlib.pyplot as plt
from matplotlib import font_manager

def setup_cn():
    """中文字体：按平台常见字体依次探测，找不到就明确报错，不静默变方块。"""
    candidates = ["Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC"]
    for name in candidates:
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [name]
            break
    else:
        raise RuntimeError("未找到中文字体，请先安装 Noto Sans CJK 或 SimHei")
    plt.rcParams["axes.unicode_minus"] = False   # 负号不变方块

setup_cn()

# 主色 + 中性色：同源数据用同一色族，只有"被强调的那一项"用对比色
PALETTE = ["#2E5C8A", "#7FA8C9", "#C9D9E8", "#E8A33D", "#B0483C", "#8C8C8C"]

def style_ax(ax, title, xlabel="", ylabel=""):
    """统一去 chart junk：去上右边框、浅网格、标题左对齐写结论。"""
    ax.set_title(title, fontsize=13, loc="left", pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
```

### 2.1 对比 → 横向条形图

```python
regions = ["华东", "华南", "华北", "西南", "东北"]
sales = [620, 480, 410, 260, 150]
order = sorted(range(len(sales)), key=lambda i: sales[i])   # 升序，最大值在顶部
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.barh([regions[i] for i in order], [sales[i] for i in order], color=PALETTE[0], height=0.6)
ax.bar_label(bars, fmt="%d", padding=4, fontsize=10)
style_ax(ax, "华东贡献六成销售额，是第二名华南的 1.3 倍", xlabel="销售额（万元）")
ax.grid(axis="y", visible=False)
ax.grid(axis="x", linewidth=0.6, alpha=0.35)
fig.tight_layout()
fig.savefig("compare.png", dpi=160)
```

改三处即可复用：`regions` / `sales` / `style_ax` 的标题（**标题必须是结论句**）。

### 2.2 趋势 → 折线图（末点标注数值）

```python
months = ["1月", "2月", "3月", "4月", "5月", "6月"]
gmv = [120, 135, 128, 160, 175, 210]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(months, gmv, color=PALETTE[0], linewidth=2, marker="o", markersize=4)
ax.annotate(f"{gmv[-1]}", xy=(months[-1], gmv[-1]), xytext=(6, 0),
            textcoords="offset points", va="center", fontsize=10, color=PALETTE[0])
style_ax(ax, "GMV 连续三月上行，6 月创半年新高", ylabel="GMV（万元）")
fig.tight_layout()
fig.savefig("trend.png", dpi=160)
```

多条线时：颜色只用 `PALETTE[0:3]` 同一色族 + 1 个强调色；超过 5 条线改用 `plt.subplots(2, 3)` 小倍数图，不要堆在一张图上比颜色。

### 2.3 分布 → 直方图（含中位数线）

```python
import numpy as np
rng = np.random.default_rng(7)
amount = np.concatenate([rng.normal(120, 25, 400), rng.normal(300, 40, 120)])  # 双峰
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(amount, bins=30, color=PALETTE[1], edgecolor="white", linewidth=0.6)
ax.axvline(np.median(amount), color=PALETTE[3], linewidth=1.6, linestyle="--")
ax.text(np.median(amount), ax.get_ylim()[1] * 0.92, f" 中位数 {np.median(amount):.0f}",
        color=PALETTE[3], fontsize=10)
style_ax(ax, "订单金额呈双峰分布，均值掩盖了小额高频与大额低频两群人", xlabel="订单金额（元）", ylabel="订单数")
fig.tight_layout()
fig.savefig("distribution.png", dpi=160)
```

多组对比改用箱线图：`ax.boxplot([g1, g2], labels=["A组","B组"])`，比并排直方图更省地方。

### 2.4 构成 → 百分比堆叠柱

```python
import numpy as np
channels = ["线上", "门店", "分销"]
quarters = ["Q1", "Q2", "Q3", "Q4"]
data = np.array([[52, 28, 20], [55, 26, 19], [58, 25, 17], [61, 24, 15]])  # 每行和为 100

fig, ax = plt.subplots(figsize=(7, 4))
bottom = np.zeros(len(quarters))
for i, name in enumerate(channels):
    ax.bar(quarters, data[:, i], bottom=bottom, label=name, color=PALETTE[i], width=0.6)
    bottom += data[:, i]
ax.set_ylim(0, 100)
ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
style_ax(ax, "线上占比一年内从 52% 升到 61%，门店与分销同步收缩", ylabel="占比（%）")
ax.grid(axis="y", linewidth=0.6, alpha=0.35)
fig.tight_layout()
fig.savefig("composition.png", dpi=160, bbox_inches="tight")
```

> 构成图的硬约束：**各段相加必须等于整体**。百分比、转化率、中位数不能堆叠（分母不同）。

### 2.5 相关 → 散点图（+ 拟合线 + r）

```python
import numpy as np
rng = np.random.default_rng(11)
ad_spend = rng.uniform(10, 100, 60)
orders = 0.8 * ad_spend + rng.normal(0, 12, 60) + 20
r = np.corrcoef(ad_spend, orders)[0, 1]
k, b = np.polyfit(ad_spend, orders, 1)

fig, ax = plt.subplots(figsize=(7, 4))
ax.scatter(ad_spend, orders, s=26, color=PALETTE[0], alpha=0.75, edgecolor="white", linewidth=0.5)
xs = np.linspace(ad_spend.min(), ad_spend.max(), 50)
ax.plot(xs, k * xs + b, color=PALETTE[3], linewidth=1.8, linestyle="--")
style_ax(ax, f"投放与订单正相关（r={r:.2f}），但只能说明同向变化，不能证明因果",
         xlabel="广告投放（万元）", ylabel="订单数（单）")
fig.tight_layout()
fig.savefig("correlation.png", dpi=160)
```

红线：**r 只描述同向程度**，标题里不许出现"导致/带来/提升"。真要讲因果，另做对照实验。

### 2.6 排名 → 排序条形图（Top N + 其他）

```python
items = ["A款", "B款", "C款", "D款", "E款", "F款", "G款", "H款", "其他 12 款"]
values = [980, 760, 640, 520, 410, 300, 220, 140, 260]
fig, ax = plt.subplots(figsize=(7, 4.5))
colors = [PALETTE[0]] + [PALETTE[2]] * (len(items) - 1)
bars = ax.barh(items[::-1], values[::-1], color=colors[::-1], height=0.62)
ax.bar_label(bars, fmt="%d", padding=4, fontsize=9)
style_ax(ax, "A 款单品销量是第 2 名的 1.3 倍，长尾 12 款合计仍不及 A 款", xlabel="销量（件）")
ax.grid(axis="y", visible=False)
ax.grid(axis="x", linewidth=0.6, alpha=0.35)
fig.tight_layout()
fig.savefig("ranking.png", dpi=160)
```

排序图的规矩：**降序 + 只强调第一项 + 长尾合并成"其他"**，不要把 40 个 SKU 全画出来。

---

## 三、诚实性检查（图不撒谎的 6 条红线）

画完逐条过，不合格就改图，不是改数据：

| 红线 | 常见犯法 | 正确做法 |
|------|----------|----------|
| **柱状纵轴不从 0 起** | 为了"看出差异"把 ylim 设成 90-100，差异被放大 10 倍 | 柱状图必须从 0 开始（长度编码）；折线图可不从 0（位置编码），但要在轴旁标明 |
| **双纵轴混量纲** | 左轴销售额、右轴转化率叠一张图，两条线交叉处毫无意义 | 拆成上下两张小图共享 x 轴（`sharex=True`） |
| **面积编码数量** | 用气泡大小、3D 饼、面积图宽度表示数值 | 用长度/位置编码；面积感知误差大且系统性低估 |
| **饼图超过 3 类** | 8 个扇区，读者只能读出"有一块最大" | 改排序条形图，或 Top 3 + 其他 |
| **标题写图名不写结论** | "各区域销售情况图" | "华东贡献六成销售额，但增速最慢" |
| **截取有利时间窗** | 只画最近 3 个月掩盖全年下滑 | 时间窗要么全量、要么在标题或角标注明"仅含 Q3" |

补充两条自查：

- **删掉任意一条网格线/图例/颜色，信息少了吗？** 没少就删——chart junk 的定义是"不承载信息的墨水"。
- **把图给一个不懂业务的人看 5 秒**，他能复述出标题那句话吗？不能就是图没画对。

---

## 四、交叉引用（别在本文件重复维护）

| 你还需要什么 | 读哪里 |
|--------------|--------|
| 数据清洗 / 透视 / 对账 / 异常识别 / 结论怎么来 | [data_analysis.md](data_analysis.md) |
| 图表感知精度阶梯（为什么别用饼图）、配色递增梯度、表格样式 | [data_analysis.md](data_analysis.md) §5.3 / §十七 / §十八 |
| Excel 原生图表（openpyxl.chart，活图）/ Word 插图（add_picture） | [office_processing.md](../../do/code/office_processing.md) §四 |
| 流程图 / 架构图 / 时序图 / 桑基图 / 鱼骨图 / 甘特图 | [diagram-design.md](../da/diagram-design.md) |
| 图要进领导汇报文档（SCQA / 金字塔 / 结论先行） | [leader_report.md](../da/leader_report.md) |
| 一次完整报告从取数到分发 | [report_pipeline.md](report_pipeline.md) |
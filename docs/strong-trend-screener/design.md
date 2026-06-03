# 强势趋势追踪 — 设计文档 v1

> **状态：** 设计阶段
> **分支：** `feat/strong-trend-screener`

---

## 0. 前端原型总览

> 📸 **先看图，再看字。** 本章放置功能原型截图，让读者一翻开就能直观看到"这个功能做出来长什么样"。

*图0-1：强势趋势追踪页面原型（待截图补充）*

**布局说明：** 页面分为三部分——筛选条件栏（顶部）→ 候选股列表（中部）→ 底部导航。

**核心布局一句话总结：** 从强势板块筛选出趋势完好的个股，按综合评分排序展示，每张卡片含板块信息、趋势指标、调整质量。

---

## 1. 背景与问题

**现状：** 当前系统发现个股的方式有：
1. **涨幅榜（TopGainers）** — 从全市场找特定区间涨幅最大的个股
2. **自选股/持仓** — 用户手动添加和维护
3. **逻辑追踪** — 从信息源推理最强逻辑
4. **买点信号** — 等技术回踩触发

**痛点/断层：**
- 市场风格正在变化——强势个股和板块 "一涨一波"，调整浅而短
- 很多强势股没有标准回踩（EMA5不破），不触发买点信号
- 涨幅榜只看历史涨幅，不看板块趋势延续性
- 缺乏一个"从板块出发找个股"的发现方式

**目标：** 从强势板块筛选趋势完好的个股，作独立于涨幅榜的另一条个股发现路径。

**屏幕内外：**

- **做什么：**
  - 基于板块20日涨幅筛选强势行业/概念
  - 对每个强势板块，找出成分股中趋势完好的个股
  - 按综合评分排序展示候选股
  - 每张卡片包含板块强度、趋势斜率、调整深度等关键信息
  - 支持点击展开查看个股分析

- **不做什么：**
  - 不涉及买卖点判定
  - 不做实时数据拉取（只读本地已缓存数据）
  - 不替代涨幅榜，两者并列作为不同发现路径

---

## 2. 设计思想

### 2.1 核心理念

**板块→个股**的正向筛选路径，与涨幅榜的**个股→回顾**反向路径互补。两者独立运行，结果可交叉验证。

### 2.2 方案选择

| 候选方案 | 优点 | 缺点 | 结论 |
|:--------|:----|:----|:----:|
| 从个股筛：全市场5000只扫EMA | 覆盖面最广 | 计算量大，无板块上下文 | ❌ |
| **双窗口板块筛：20日涨幅 + 5日涨幅** | 兼顾已确认主线+刚启动板块 | 依赖板块成分股映射完整性 | ✅ |
| 从概念筛：概念波谷页面扩展 | 数据已就绪 | 概念更新晚，可能漏行业板块 | ❌ |

### 2.3 设计原则

1. **板块优先：** 所有候选股必须有明确的强势板块归属（行业或概念）
2. **趋势质量 > 绝对涨幅：** 评分侧重趋势延续性（斜率、调整深度），而非过去涨了多少
3. **全读本地：** 不拉任何外部数据，只读 `sector_daily.json` 和 `all_stocks_60d.json`

---

## 3. 数据模型

### 3.1 核心数据结构

#### API 响应格式 (`GET /api/strong-trend-candidates`)

```json
{
  "date": "20260603",
  "top_industries": [
    {"name": "元件", "chg_20d": 24.16, "stock_count": 82}
  ],
  "top_concepts": [
    {"name": "国家大基金持股", "chg_20d": 17.09, "stock_count": 45}
  ],
  "candidates": [
    {
      "code": "300xxx",
      "name": "股票名",
      "price": 28.46,
      "chg_1d": 2.3,
      "chg_5d": 8.1,
      "chg_20d": 15.2,
      "sectors": [
        {"type": "industry", "name": "半导体", "chg_20d": 6.29, "rank": 7},
        {"type": "concept", "name": "AI PC", "chg_20d": 8.90, "rank": 15}
      ],
      "trend_metrics": {
        "ema5_slope": 0.8,
        "ema10_slope": 0.6,
        "ema20_slope": 0.4,
        "ema_alignment": "bullish",
        "price_vs_ema20_pct": 3.5
      },
      "adjustment_quality": {
        "max_drawdown_10d": -2.3,
        "max_consecutive_down_10d": 1,
        "vol_ratio_5d_20d": 1.12
      },
      "score": 8.5,
      "score_breakdown": {
        "sector_strength": 3.2,
        "trend": 3.0,
        "adjustment": 2.3
      }
    }
  ]
}
```

### 3.2 数据流

```
用户访问页面
  ↓
GET /api/strong-trend-candidates
  ↓
strong_trend_service.py:
  ① 读 sector_daily.json → 算行业/概念 20日涨幅 + 5日涨幅
     取 20日涨幅TOP 8 (已确认主线) + 5日涨幅TOP 8 (刚启动) → 合并去重
  ② 读 stock_industry_map.json → 构建行业→成分股反向索引
  ③ 读 concept_list.json → 获取概念→成分股
  ④ 读 all_stocks_60d.json → 获取个股K线
  ⑤ 对每个强势板块的成分股：
     a. 查 EMA5/10/20 趋势指标
     b. 查近10日调整深度
     c. 计算综合评分
  ⑥ 去重、排序、TOP 30 返回
  ↓
前端 StrongTrendCandidates.tsx 渲染卡片列表
```

---

## 4. 系统设计

### 4.1 架构总览

```
backend/services/strong_trend_service.py   — 筛选逻辑（新增）
backend/api/strong_trend.py                — API端点（新增）
frontend/src/pages/StrongTrendCandidates.tsx — 页面（新增）
frontend/src/__tests__/strong_trend.test.tsx  — 测试（新增）
frontend/src/components/NavBar.tsx          — 导航项（修改）
```

### 4.2 核心算法

#### 板块强度排名（双窗口）

```python
def get_top_sectors(industries: dict, concepts: dict, top_n=8):
    """取行业/概念各 TOP N，分 20日 和 5日 两个窗口"""
    # 对每个板块，算5日涨幅和20日涨幅
    # 20日涨幅TOP 8 → 已确认强势板块
    # 5日涨幅TOP 8 → 刚启动板块
    # 合并去重后得到板块候选池
    ...
```

#### 趋势质量评分

```python
def score_stock(klines: list) -> dict:
    """基于K线计算趋势质量"""
    ema5, ema10, ema20 = calc_emas(klines, [5, 10, 20])
    idx = -1  # 最新日
    
    # 1. 趋势对齐
    bullish = ema5[idx] > ema10[idx] > ema20[idx]
    # 2. EMA5斜率（近3日EMA5变化/最新价，排除当天）
    ema5_slope = (ema5[idx] - ema5[idx-3]) / klines[idx]['close'] * 100
    # 3. 调整深度（近10日最大回撤）
    recent = klines[max(0, idx-9):idx+1]
    max_drawdown = max(0, min(0, min(...最高点回撤)))
    # 4. 连跌天数
    consec_down = max(...近10日连续下跌)
    ...
```

#### 综合评分

```python
score = (
    sector_strength_weight  # 板块排名分 (0~4分)
    + trend_alignment        # EMA趋势对齐 (0~3分)
    + adjustment_quality     # 调整质量 (0~3分)
)  # 满分10分
```

### 4.3 API 设计

#### `GET /api/strong-trend-candidates`

**参数：**

| 参数 | 类型 | 默认 | 说明 |
|:----|:----|:----|:-----|
| `top_industries` | int | 8 | 取前N个强势行业（20日）|
| `hot_industries` | int | 8 | 取前N个活跃行业（5日）|
| `top_concepts` | int | 8 | 取前N个强势概念（20日）|
| `hot_concepts` | int | 8 | 取前N个活跃概念（5日）|
| `limit` | int | 30 | 返回最多N只候选股 |
| `min_score` | float | 5.0 | 最低评分过滤 |

**响应：** 见 3.1 节数据模型。

### 4.4 前端设计

#### 页面布局

```
┌─ 筛选栏 ──────────────────────────────────┐
│ [🏭 行业TOP] 元件+24% | 电子化学品+14% | ...  │
│ [💡 概念TOP] 国家大基金+17% | 培育钻石+15% |... │
│ 行业TOP N: [10] 概念TOP N: [10] 最低评分: [5]│
├─ 候选股列表 ───────────────────────────────┤
│  ╭─ 卡片1 ──────────────────────────────╮  │
│  │ 评分 8.5 | 🏆 元件 | 💡 PCB概念     │  │
│  │ 300xxx 股票名 现价28.46 +5.2%        │  │
│  │ EMA5↑EMA10↑EMA20↑ 多头排列           │  │
│  │ 近10日最大回撤 -2.3% 连跌1天          │  │
│  │ [查看分析]                            │  │
│  ╰─────────────────────────────────────╯  │
│  ╭─ 卡片2 ...                            │  │
└───────────────────────────────────────────┘
```

#### 分组过滤

候选股列表默认全部展示，可拖动到涨幅榜页面下方的"📈 涨幅榜"分组同级区域。

#### 导航位置

放在"个股管理"分组，涨幅榜下方：

```
个股管理: 自选股 | 持仓 | 个股分析 | 趋势候选 | 涨幅榜 | 强势趋势(新增)
```

---

## 5. 执行计划

详见：[强势趋势追踪 — 执行计划](plan.md)

---

## 6. 附录

### 6.1 替代方案

1. **全市场扫描：** 不按板块过滤，直接对自选股+全市场5000+股做趋势筛选。缺点：无板块上下文，且计算量太大（5000×60天K线）。
2. **与概念波谷整合：** 在概念波谷页面增加个股展示。缺点：概念更新晚（21:00），混合两个不同目的的功能。

### 6.2 开放问题

- 行业和概念的评分权重是否需要分开调整？
- "强势板块"的边界（20日涨幅 TOP 10？还是20日涨幅 > 3%？）
- 候选股去重策略（一只股同时属于行业和概念，取最高评分）

### 6.3 文件清单

```
新增：
  server/backend/services/strong_trend_service.py  — 筛选逻辑
  server/backend/api/strong_trend.py               — API端点
  server/frontend/src/pages/StrongTrendCandidates.tsx — 前端页面
  server/frontend/src/__tests__/strong_trend.test.tsx  — 测试
  docs/strong-trend-screener/design.md              — 本设计文档
  docs/strong-trend-screener/plan.md                — 执行计划

修改：
  server/frontend/src/App.tsx                       — 添加路由
  server/frontend/src/components/NavBar.tsx         — 导航项
```

### 6.4 变更日志

| 版本 | 日期 | 变更内容 |
|:----|:----|:--------|
| v1 | 2026-06-03 | 初稿 — 强势趋势追踪方案 |

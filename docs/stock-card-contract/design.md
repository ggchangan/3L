# 个股卡片数据合约 (StockCardData) — 设计文档 v1

## 0. 现状总览

### 当前问题

`get_stock_card()` 返回字段丰富（signal/fusion_type/structure/stage...），但缺少**展示层需要的操作类型字段**，导致两处不一致推导：

```
后端 review_compute_service._make_item_action()
  └─ 用 signal + fusion_type + stage 推导 action_type（买入/卖出/持有/加仓/减仓/换股）
  └─ 结果供 TradingPlan 组件使用

前端 StockCard 组件（第28行）
  └─ 直接用 signal 自行推导："buy"→"⚡买入" "hold"→"✅持有" "sell"→"❌卖出"
  └─ 结果供 自选股/持仓/热门股/涨幅榜 使用
```

**两套逻辑，输出不一致**：
- signal='buy' 时 StockCard 显示"⚡买入"，但 `_make_item_action` 可能输出"强势买入·缩量回踩(85)" 
- signal='hold' 时 StockCard 显示"✅持有"，但 fusion_type='bullish_wait' 时 `_make_item_action` 输出"偏多等确认"
- signal='sell' 时 StockCard 显示"❌卖出"，但融合引擎可能已标记为"卖出信号·量价背离(75)"

### 目标

统一所有个股操作类型的展示：**一律从卡片读取 `action_type`/`action_signal`**，不再外部推导。

## 1. 数据合约：StockCardData

`data_models.py` 新增 `StockCardData` dataclass，定义 `get_stock_card()` 的返回值结构：

```python
@dataclass
class StockCardData:
    """个股卡片统一数据合约 — get_stock_card() 输出

    所有个股展示数据唯一来源。外部代码只读不做推导。
    """
    # ── 基础字段 ──
    code: str                    # 6位股票代码
    name: str                    # 股票名称
    sector: str                  # 所属行业/板块
    direction: str               # 方向（大类.子类）
    price: float                 # 当前价格
    change: float                # 当日涨跌幅%
    date: str                    # 数据日期 YYYYMMDD

    # ── 技术分析 ──
    structure: str               # '上涨趋势'/'区间震荡'/'下降趋势'
    stage: str                   # '上行'/'加速'/'缩量整理'/'滞涨'/'转弱'/...
    ema: str                     # EMA排列状态（多头/空头/交叉...）
    ema5: Optional[float]        # EMA5值
    ema10: Optional[float]       # EMA10值
    ema20: Optional[float]       # EMA20值
    deviation_pct: float         # 偏离率（远离EMA5的%）
    vol_ratio: float             # 量比（当日/5日均量）
    vol_analysis: str            # 量能分析文字

    # ── 信号和融合判定 ──
    signal: str                  # 原始信号：'buy'/'hold'/'sell'（保留，用于过滤和统计）
    signal_text: str             # 信号文字（如'缩量回踩(65%)'）
    buy_point: str               # 买点类型
    profit_model1: bool          # 是否盈利模式1（涨停回踩）
    trend_stock: bool            # 是否趋势交易股
    trading_system: str          # '3l'/'trend'
    triggered_signals: list      # 触发的关键信号列表 [{name, confidence, direction}]
    fusion_type: str             # 融合判定类型：'strong_buy'/'signal_sell'/'bullish_wait'/...
    fusion_reason: str           # 融合判定理由
    score: int                   # 综合评分

    # ── ✅ 新增：展示层统一字段 ──
    action_type: str             # 操作类型：'买入'/'卖出'/'持有'/'加仓'/'减仓'/'换股'
    action_signal: str           # 操作子标签：'强势买入·缩量回踩(85)'/'偏多等确认'/...
    action_priority: str         # 优先级：'高'/'中'/'低'
    action_reason: str           # 操作理由：'结构偏多但无信号触发...'

    # ── 其他 ──
    mainline_level: str          # 主线定位：'主线'/'次级主线'/'非主线'
    stop_loss: Optional[float]   # 止损价
    stop_loss_pct: Optional[float]  # 止损百分比
    conclusion: str              # 结论文字（前端展示用）
    tags: list                   # 标签列表
```

**新增字段的推导逻辑（与旧的 `_make_item_action` 完全一致）：**

```
action_type:
  fusion_type='strong_buy' + signal='buy'  → '买入'
  fusion_type='signal_buy' + signal='buy'  → '买入'
  fusion_type='signal_sell' + signal='sell' → '卖出'
  fusion_type='bullish_wait'               → '持有'
  fusion_type='conflict_bearish'           → '减仓'
  fusion_type='conflict_bullish'           → '持有'
  signal='sell'（熔合为空）→ '卖出'
  signal='buy'（熔合为空） → '买入'
  stage='加速'              → '持有'
  stage='缩量整理'          → '持有'
  stage='上行'              → '持有'
  stage='滞涨'              → '减仓'
  stage='转弱'              → '换股'
  stage='区间底部'          → '加仓'
  stage='区间顶部'          → '减仓'
  stage='区间中段'          → '持有'
  其他                      → '持有'

action_signal:
  strong_buy + signal='buy' → '强势买入·' + 前3个信号名和置信度
  signal_buy + signal='buy' → '买入信号·' + 前2个信号名和置信度
  signal_sell + signal='sell' → '卖出信号·' + 前2个信号名和置信度
  bullish_wait → '偏多等确认'
  conflict_bearish → '空头冲突'
  conflict_bullish → '多头冲突'
  stage='加速' → '关注止盈'
  stage='缩量整理' → '可加仓'
  stage='区间底部' → '支撑位'
  stage='区间顶部' → '压力位'
  其他 → ''

action_priority:
  融合有输出（非空）→ '高'
  signal='buy'/'sell' → '高'
  stage='加速'/'滞涨'/'转弱'/'区间顶部' → '高'
  stage='缩量整理'/'区间底部' → '中'
  stage='上行'/'区间中段' → '低'
  其他 → '中'

action_reason:
  fusion_reason 非空 → fusion_reason
  signal='sell' → structure·stage
  signal='buy' → structure·stage + 买点补充
  按 stage 生成补充文字（与现有 _build_conclusion 一致）
```

## 2. 数据流

```
get_stock_card()
  输入：code, date_str, market_position, main_lines, klines
  输出：card = {signal, structure, stage, fusion_type,
                ✅ action_type, action_signal, action_priority, action_reason,
                ...}
      ▲
      │
      └──────────────┬────────────────────┬─────────────────┐
                     │                    │                  │
          generate_holdings_review()    generate_buy_      get_watchlist_
          【持仓复盘】                   signals_review()    analysis()
          for each 持仓:                 【自选股买点信号】  【自选股分析】
            调 get_stock_card()           for each 买点:     调 get_stock_card()
            ↓                            调 get_stock_card() ↓
          holdings_review[i]             ↓                  watchlist[i]
          = {action_type, ...}         buy_signals_review[i]
                                       = {action_type, ...}
                     │                    │
                     └──────────┬─────────┘
                                │
                    generate_trading_plan()
                    【交易计划生成】
                    从 review 数据读 action_type
                    → holdings_action[i].action_type = h.action_type
                    → buy_priority[i].action_type = bs.action_type
                    ❌ 删掉 _make_item_action()
                    ✅ 保留 reason_chain 组装（大盘→板块）
                                │
                    ┌───────────┴───────────┐
                    │                       │
            StockCard 组件              TradingPlan 组件
            "操作"字段：                 "操作"字段：
            用 action_signal            用 action_type
            || action_type              （已使用，不变）
            || 回退 signalText
```

## 3. 影响分析

### 受影响文件

| 文件 | 改动类型 | 说明 |
|:----|:--------|:-----|
| `server/backend/core/data_models.py` | **新增** | 添加 `StockCardData` dataclass |
| `server/backend/services/stock_card_service.py` | **修改** | get_stock_card() 新增 action_type/action_signal/action_priority/action_reason 计算和输出 |
| `server/backend/core/review_analysis.py` | **修改** | generate_holdings_review() 和 generate_buy_signals_review() 透传 4 个新字段 |
| `server/backend/services/review_compute_service.py` | **修改** | 删掉 _make_item_action()，直接从 review 数据读 action_type |
| `server/frontend/src/components/StockCard.tsx` | **修改** | "操作"字段改为用 action_signal，保留 signal 回退 |
| `server/frontend/src/lib/types.ts` | **修改** | BuySignalItem 接口新增 action_type/action_signal/action_priority/action_reason |

### 不受影响文件

- `server/backend/api/workbench.py` — 直接传 trading_plan['holdings_action']，字段名不变
- `server/backend/services/trend_service.py` (get_watchlist_analysis) — 未使用 action_type，不受影响
- `server/backend/services/holdings_service.py` — 未使用 action_type
- `server/frontend/src/pages/HotStocks.tsx` — 使用 signal 做过滤（signal 保留），不受影响
- `server/frontend/src/pages/StrongTrendCandidates.tsx` — 使用 signal 做过滤（signal 保留），不受影响

### 向后兼容

- `signal` 字段**保留不变**，已有依赖（HotStocks 按 signal 筛选、StrongTrendCandidates 按 signal 筛选）不受影响
- `fusion_type` 字段保留不变
- StockCard 组件的 signalText 回退逻辑保留（`action_signal || action_type || signalText`）

## 4. 文件清单

```
新增：
  (无新文件，3个后端+2个前端文件修改)

修改：
  server/backend/core/data_models.py          — 新增 StockCardData 合约
  server/backend/services/stock_card_service.py — 新增 4 字段计算
  server/backend/core/review_analysis.py       — 透传 4 字段
  server/backend/services/review_compute_service.py — 删 _make_item_action
  server/frontend/src/components/StockCard.tsx  — 改用 action_signal
  server/frontend/src/lib/types.ts             — 新增 4 字段类型
```

## 5. 变更记录

| 版本 | 日期 | 变更内容 |
|:----|:----|:--------|
| v1 | 2026-06-07 | 初稿 |

# 板块数据处理流程（2026-05-20 最终定稿）

## 整体流程

```
① GET /api/industry-boards → 全部板块今日涨跌幅（快，akshare同花顺）
② 按今日涨跌幅排序 → 取TOP15
③ 并行拉取15个板块的60日OHLCV（akshare stock_board_industry_index_ths）
   → 存入 review_charts/sector_{name}_kline.json（1小时TTL）
   → 同时在拉取时计算突破点（第2类关键点label='突'）
④ 从60日缓存计算每个板块的所有字段：
   - 结构：取最近15条closes → EMA10形态法
   - 阶段：线性回归半段对比
   - 区间位置（区间震荡时）：支撑=突破点 压力=15日最高
   - 5日涨幅：close[-1] / close[-6] - 1
   - 昨日涨跌幅：今日闭市后用close[-1]/close[-2]-1
⑤ 返回 today_top5（按今日涨幅排） + chg5d_top5（按5日涨幅排）
```

## 关键点

- **只拉TOP15**，不拉全部90个板块
- **结构只用最近15日收盘价**，不从60日全部数据算
- **缓存TTL**：1小时（60日OHLCV），行业板块缓存按天
- **废弃**：旧的 `sector_hist_chgs.json`（15日×90板块）、`sector_5d_chg.json`（5日涨幅独立缓存）
- **突破点计算**：`highs[i] > max(highs[max(0,i-10):i]) and closes[i] > opens[i]`
- **60日缓存可复用**：板块关键点图（📊）也读同一个 `sector_{name}_kline.json`

## 代码位置

- 数据拉取：`monitor_data.py` → `_fetch_60d()`
- 字段计算：`monitor_data.py` → `_compute_one()`
- 图表绘制：`server.py` → `/api/sector-chart` 端点
- SVG支撑/压力线：同上端点，在关键点绘制后加绿色虚线（支撑）和红色虚线（压力）

## 版本演进（区间震荡位置判断）

| 版本 | 方法 | 电池结果 | 问题 |
|:----|:-----|:--------|:-----|
| v1 | 60日全范围min/max | 74.9%→区间顶部 | 60日前低点19009是历史低点 |
| v2 | 最近20日min/max | 40.3%→区间中段 | 无关键点支撑 |
| v3 | 突破点+前高 | 49.6%→区间中段 | 压力23337太近，用户说不对 |
| **v4** | **突破点+15日最高** | **13.7%→区间底部** | 用户确认最终版 |

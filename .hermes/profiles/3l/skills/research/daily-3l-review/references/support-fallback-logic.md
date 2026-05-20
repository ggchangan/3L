# 区间震荡stage的支撑回退逻辑（2026-05-21 修正）

## 问题

`generate_review_data.py` 生成 `holdings_review` 时，对`structure='区间震荡'`的股票需要用关键点支撑而非15日极值计算stage。

**初版bug：** 最近支撑距当前<1.5%被过滤后，直接设`support=None`，fallback到`20日最低`。

**实例（深圳华强 000062）：**
```
最近突支撑: 34.34 (距当前0.2%, 过滤)
旧逻辑: support=None → 20日最低29.58 → 位置45.8% → 区间中段 ❌
正确:  取下一档33.10 (距当前3.8%) → 位置18.6% → 区间底部 ✅
```

## 修复后逻辑

```python
# 1. 找所有"突"关键点，取support_price（突破前10日最高价）
_all_supports = sorted([
    max(highs[i-10:i])
    for i in range(10, len(kls))
    if closes[i] > max(highs[i-10:i]) and closes[i] > opens[i]
    and max(highs[i-10:i]) < cur  # 在当前价下方
], reverse=True)  # 从高到低

# 2. 取第一档距当前≥1.5%的
_support = None
for s in _all_supports:
    if (cur - s) / cur >= 0.015:
        _support = s
        break

# 3. 全过滤掉才回退
_support = _support or min(lows[-20:])
```

## 同步要求

`generate_review_data.py` 和 `batch_gen_charts.py` 两处独立实现了相同的支撑过滤+下一档逻辑。改一处时必须同步改另一处。

| 文件 | 位置 | 作用 |
|------|:----:|------|
| `daily-3l-review/scripts/batch_gen_charts.py` | lines 137-148 | SVG图绿色支撑线 |
| `www/generate_review_data.py` | holdings_review生成段 | stage重算 |

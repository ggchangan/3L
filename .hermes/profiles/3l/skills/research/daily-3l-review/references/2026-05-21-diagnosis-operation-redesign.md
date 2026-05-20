# 复盘页面④⑤区重构（2026-05-21）

## 背景

用户反馈：持仓区的"操作建议"和买点区的"买点信号"布局不合理。持仓区应该展示结论性诊断（结构/阶段/量能），而不是历史买点信息。操作建议应合并到决策区。

## 改动

### 后端（`generate_review_data.py`）

**修复1：vol字段名**
```python
# 错误 ❌
vols_60 = [k.get('vol', 0) for k in _kls]  # all_stocks_60d.json 存的是 'volume' 字段

# 正确 ✅
vols_60 = [k.get('volume', k.get('vol', 0)) for k in _kls]
```
这个bug导致所有量能都为0，get_stage()的缩量整理判断永远走不到（vol_prev10=0不满足>0条件），国际复材只能返回"滞涨"。

**修复2：量能分析产出**
在cache中添加 `vol_analysis` 字段（如"缩量65%"、"量能正常112%"、"放量180%"），通过 `signals['holdings']` → `holdings_review` 传递到前端。

**修复3：ema传递**
cache已有 `ema` 字段但未传到 `signals['holdings']` → `holdings_review`，补充传递。

**⚠️ 坑：** 当整个 `generate_review_data.py` 文件被重写时，必须保留或重写 `fetch_index_klines()` 和 `fetch_market_quote()` 两个函数，否则主流程会报错。保险做法：从 git 版本做 patch 而非手写全文。

### 前端（`review.html`）

**④ 个股诊断卡**（原"持仓个股复盘"）

旧卡片：
```
买点:持有观察  结构:上涨趋势  阶段:滞涨
✅ 持有
```

新诊断卡：
```
📈 国际复材 301526          18.78 +0.43%
阶段: 🔄 缩量整理  EMA:多头排列  量能:缩量65%  📊
💡 缩量蓄力中继，可持股待涨
```

阶段颜色映射：
- 上行 / 区间底部 / 转强 → `#4ecdc4` 青色（积极）
- 缩量整理 / 区间中段 → `#ffd700` 金色（中性等待）
- 滞涨 / 转弱 / 区间顶部 → `#ff6b6b` 橙红（警惕）
- 加速 / 加速跌 → `#e94560` 红色（极端）

**⑤ 操作决策**（原"自选股买点信号"）

合并两区：
1. 📋 持仓操作建议 — 每只股一行（名称 + 操作图标 + 文字）
   - 🔄 持有·可加仓（缩量整理）
   - ✅ 持有（上行/正常）
   - ⏳ 持有·关注止盈（加速）
   - ⚠️ 警惕·考虑减仓（滞涨）
   - ⚡ 关注·可换股（转弱）
   - ❌ 卖出（卖出信号）
2. 🎯 买点信号 — 候选股票列表（信号类型 + 价格 + 涨幅）
   - 从 `data.buy_signals_review` 读取（与 `data.buy_signals` 格式一致但有独立路径）

### 数据流

```
all_stocks_60d.json
  → get_buy_sell_signals()   ← 修复vol字段名、算vol_analysis
    → signals['holdings']    ← 新增 ema, vol_analysis
      → holdings_review[]    ← 诊断卡数据
        → review.html #stockReviewList
          → signalStockCard() ← 重写：阶段彩色+EMA+量能+结论

buy_signals
  → buy_signals_review[]
    → review.html #buySignalList (global reviewData注入)
      → updateBuySignalsUI() ← 重写：持仓操作建议 + 买点信号
```

## 验证方法

```bash
cd /home/ubuntu/www
python3 -c "
from generate_review_data import get_buy_sell_signals
import json
holdings = [{'code': '301526', 'name': '国际复材'}]
result = get_buy_sell_signals(holdings, [])
h = result['holdings'][0]
print(f'阶段={h[\"stage\"]} ema={h[\"ema\"]} 量能={h[\"vol_analysis\"]}')
# 预期输出: 阶段=缩量整理 ema=多头排列 量能=缩量65%
"
```

## 效果对比

| 维度 | 改前 | 改后 |
|------|------|------|
| 国际复材阶段 | 滞涨（误判，全零量能） | 缩量整理（正确，量缩65%） |
| ④区卡片 | 买点/结构/阶段三行 + 操作信号 | 阶段彩色标识+EMA+量能+结论 |
| ⑤区 | 仅候选买点信号列表 | 持仓操作建议 + 买点信号 |

## 后续工作

- 诊断卡的"结论"文字目前固定在 JS 内，后续可从后端 `signal_text` 或 `note` 字段拉取，更灵活
- 操作建议的图标规则同样暂定在 JS 内，后续可后端 `stage` 前置映射

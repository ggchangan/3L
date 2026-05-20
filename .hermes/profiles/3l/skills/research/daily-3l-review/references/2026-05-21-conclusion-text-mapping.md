# 诊断卡结论文字映射表（2026-05-21 终版）

`signalStockCard()` 中结论文字独立于 `judge_signal()` 的 `signal_text`，由 stage + vol_analysis 直接生成。

## 映射规则

```javascript
let conclusion = `阶段${s.stage}，${s.structure}`;  // fallback
const volDesc = s.vol_analysis || '';

if (s.signal === 'buy') {
    conclusion = `触发${s.buy_point}，${s.stage}阶段确认，可执行买入计划`;
} else if (s.stage === '缩量整理') {
    conclusion = `量能${volDesc}卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待放量突破`;
} else if (s.stage === '上行') {
    conclusion = `斜率正常，EMA10持续向上，上行趋势健康，继续持有不动`;
} else if (s.stage === '加速') {
    conclusion = `EMA10斜率加速变陡，拉升阶段，关注放量滞涨等左侧止盈信号`;
} else if (s.stage === '滞涨') {
    conclusion = `EMA10走平涨不动${volDesc ? '，量能'+volDesc+'未有效萎缩' : ''}，警惕回调，考虑减仓`;
} else if (s.stage === '转弱') {
    conclusion = `EMA10已拐头向下，趋势转弱，关注关键支撑位是否破位`;
} else if (s.stage === '区间底部') {
    conclusion = `价格在支撑位附近，区间底部企稳，可考虑加仓博反弹`;
} else if (s.stage === '区间顶部') {
    conclusion = `价格接近压力位，区间顶部受阻，注意减仓回避`;
} else if (s.stage === '区间中段') {
    conclusion = `区间中部无明确方向，等待价格靠近支撑或压力再做决定`;
}
```

## 设计原则

1. **数据驱动** — 每句话引用具体数据（volDesc如"缩量65%"、EMA10位置）
2. **隐含操作方向** — 不直接说"买入/卖出/持有"（这些已在操作字段），而是给判断依据
3. **负面状态给路径** — 滞涨→"警惕回调，考虑减仓"；转弱→"关注关键支撑位是否破位"
4. **buy信号特有** — 触发买点时结论直接关联买点类型和阶段

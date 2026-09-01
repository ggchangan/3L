# 3L 结构化供需事件检测器 P0.4-B

> 状态：实验旁路。它消费 P0.2 `transition_points`，输出结构化 `SupplyDemandEvent`；不替换生产买点，不接复盘页。

## 目标

现有 P0.2 已能识别突破、跌破、反转、中继、恐慌滞跌、高潮滞涨等点，但所有点都放在 `transition_points` 里，语义容易被前端或后续逻辑误解成“买点”。

P0.4-B 的目标是先新增一层稳定语义：

```text
P0.2 transition_point
  ↓
P0.4 SupplyDemandEvent
  ↓
未来 TradeSignal 买卖点派生层
```

## 事件模型

```json
{
  "version": "supply-demand-event-v1",
  "event_type": "breakout|failure|continuation|reversal|exhaustion",
  "subtype": "upward_breakout",
  "direction": "bullish",
  "dominant_force": "demand",
  "status": "confirmed",
  "confidence": 78.5,
  "tier": "core",
  "position_context": {},
  "wave_context": {},
  "structure_context": {},
  "volume_price_evidence": {},
  "trade_implication": "candidate_right_buy_context",
  "is_trade_decision": false
}
```

## 映射规则

| P0.2 类型 | P0.4 event_type | 方向 | 主导力量 | 3L 含义 |
|---|---|---|---|---|
| `upward_breakout` | `breakout` | bullish | demand | 需求放量打破压力/平台 |
| `downward_breakdown` | `breakout` | bearish | supply | 供应放量打破支撑/平台 |
| `failed_breakout` | `failure` | bearish | supply | 需求突破失败，供应重新占优 |
| `failed_breakdown` | `failure` | bullish | demand | 供应跌破失败，需求承接 |
| `bullish_continuation` | `continuation` | bullish | demand | 供应不足，无法改变需求占优 |
| `bearish_continuation` | `continuation` | bearish | supply | 需求不足，无法改变供应占优 |
| `bullish_reversal` | `reversal` | bullish | demand | 需求出现，弱转强 |
| `bearish_reversal` | `reversal` | bearish | supply | 供应出现，强转弱 |
| `panic_stagnation` | `exhaustion` | bullish | supply_exhaustion | 恐慌/天量滞跌，供应快速释放后衰竭 |
| `climax_stagnation` | `exhaustion` | bearish | demand_exhaustion | 高潮/天量滞涨，需求透支后衰竭 |

## 硬边界

- `SupplyDemandEvent` 仍然不是交易信号；
- 所有事件必须输出 `is_trade_decision=false`；
- 中继事件必须保留“continuation”语义，不能在本层升级成“买入”；
- 恐慌/高潮归为衰竭类事件，交易层后续再决定是否生成左侧买卖点；
- 旧 `transition_points` 保留在 `legacy_transition_points`，方便对照和逐步迁移。

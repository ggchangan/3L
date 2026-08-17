import type { BuySignalItem } from './types'

type TriggeredSignal = NonNullable<BuySignalItem['triggered_signals']>[number]

export function signalRejectReason(item: Pick<BuySignalItem,
  'structural_compatible' |
  'structural_compatibility_reason' |
  'market_compatibility_reason' |
  'attention_reason' |
  'triggered_signals'
>): string {
  if (item.structural_compatible === false) {
    return item.structural_compatibility_reason
      || item.market_compatibility_reason
      || item.attention_reason
      || '关键点位置不支持该买点'
  }
  const rejected = item.triggered_signals?.find(signalIsKeypointRejected)
  return rejected?.keypoint_reject_reason || ''
}

export function isRejectedTechnicalBuy(item: Pick<BuySignalItem,
  'technical_signal' | 'signal' | 'structural_compatible' | 'structural_compatibility_reason' | 'triggered_signals'
>): boolean {
  return (item.technical_signal === 'buy' || item.signal === 'buy')
    && (item.structural_compatible === false || Boolean(item.triggered_signals?.some(signalIsKeypointRejected)))
}

export function signalIsKeypointRejected(signal: TriggeredSignal): boolean {
  return signal.direction === 'bullish' && signal.keypoint_allowed === false
}

export function triggeredSignalStyle(signal: TriggeredSignal): {
  color: string
  icon: string
  suffix: string
  title: string
} {
  if (signalIsKeypointRejected(signal)) {
    return {
      color: '#ff9800',
      icon: '⛔',
      suffix: ' · 位置不成立',
      title: signal.keypoint_reject_reason || '该看多技术信号未通过3L关键点/结构门禁',
    }
  }
  if (signal.direction === 'bullish') return { color: '#4ecdc4', icon: '🟢', suffix: '', title: signal.detail || '' }
  if (signal.direction === 'bearish') return { color: '#e94560', icon: '🔴', suffix: '', title: signal.detail || '' }
  return { color: '#ffd700', icon: '🟡', suffix: '', title: signal.detail || '' }
}

export function fusionDisplayLabel(fusionType?: string): string {
  const fusionLabels: Record<string,string> = {
    strong_buy: '🟢强买',
    signal_buy: '🟢买入',
    conflict_bearish: '⚠️警惕',
    signal_sell: '🔴卖出',
    conflict_bullish: '⚠️等确认',
    keypoint_rejected_bullish: '⛔位置不成立',
    buy_point_only: '⏳买点',
    bearish_watch: '👀偏空',
    bullish_wait: '⏳等待',
    balance: '⚖️平衡',
  }
  return fusionType ? (fusionLabels[fusionType] || fusionType) : ''
}

export function prioritizedTriggeredSignals(signals: BuySignalItem['triggered_signals'], limit: number) {
  const items = signals || []
  const rejected = items.filter(signalIsKeypointRejected)
  const rest = items.filter(signal => !signalIsKeypointRejected(signal))
  return [...rejected, ...rest].slice(0, limit)
}

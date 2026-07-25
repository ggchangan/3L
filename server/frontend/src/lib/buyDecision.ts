export type BuyDecisionStatus = 'executable' | 'candidate' | 'signal_only' | 'blocked'

interface BuyDecisionLike {
  decision_status?: BuyDecisionStatus
  action_type?: string
}

/**
 * 复盘买点的执行语义只能由 decision_status 决定。
 * legacyFallback='signal' 用于复盘旧缓存：缺少新字段时保守降级为技术信号；
 * raw 用于其他页面，保持既有卡片操作语义。
 */
export function buyDecisionAction(
  item: BuyDecisionLike,
  legacyFallback: 'signal' | 'raw' = 'raw',
): string {
  const fixedActions: Record<BuyDecisionStatus, string> = {
    executable: '买入',
    candidate: '观察',
    signal_only: '技术信号',
    blocked: '待确认',
  }
  if (item.decision_status) return fixedActions[item.decision_status]
  if (legacyFallback === 'signal') return '技术信号'
  return item.action_type || ''
}

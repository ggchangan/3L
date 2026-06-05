import { useEffect, useState } from 'react'
import { fetchWorkbenchPlan, getYesterdayStr, fetchActiveAlarms, fetchReviewToday } from '../lib/api'
import type { PlanItem, StoredAlarm } from '../lib/api'
import type { BuySignalItem } from '../lib/types'

const ALARM_TYPE_ICONS: Record<string, string> = { price: '🔴', deviation: '🟡', time: '⏰' }
const ALARM_TYPE_LABELS: Record<string, string> = { price: '价格', deviation: '偏差', time: '时间' }

/** 从 "华工科技(000988)" 提取 "000988" */
function extractCode(stock: string): string {
  const m = stock.match(/\((\d{6})\)/)
  return m ? m[1] : stock
}

/** 获取今天日期 YYYY-MM-DD */
function getTodayStr(): string {
  return new Date().toISOString().slice(0, 10)
}

/** 合并两个计划，按 stock 去重，today 优先 */
function mergePlans(yesterday: PlanItem[], today: PlanItem[]): PlanItem[] {
  const seen = new Set<string>()
  const merged = [...today]
  today.forEach(p => { if (p.stock) seen.add(p.stock) })
  yesterday.forEach(p => {
    if (p.stock && !seen.has(p.stock)) {
      merged.push(p)
      seen.add(p.stock)
    }
  })
  return merged
}

// ── 计划方向标签映射 ──
const DIRECTION_LABELS: Record<string, string> = { buy: '买入', sell: '卖出', watch: '观察' }

// ── 子组件 ──

/** 单个持仓操作行 */
function HoldingRow({ h, planInfo }: { h: BuySignalItem; planInfo?: { direction: string; condition?: string } }) {
  const sp = h.stop_loss_price ?? (h as any).stop_loss
  const spPct = (h as any).stop_loss_pct
  const spFormatted = spPct != null ? ` (${spPct >= 0 ? '+' : ''}${spPct.toFixed(2)}%)` : ''
  return (
    <div className="plan-row" style={{ background: 'rgba(233,69,96,0.06)' }}>
      <span className="plan-stock">{h.name}({h.code})</span>
      {planInfo && (
        <span className="plan-direction">→ {DIRECTION_LABELS[planInfo.direction] || planInfo.direction}</span>
      )}
      {planInfo?.condition && (
        <span className="plan-condition">{planInfo.condition}</span>
      )}
      {sp != null && (
        <span className="plan-stop-loss">止损{sp}{spFormatted}</span>
      )}
      {h.price != null && (
        <span className="plan-price">
          现价 {h.price} {h.change != null ? `${h.change >= 0 ? '+' : ''}${h.change.toFixed(1)}%` : ''}
        </span>
      )}
    </div>
  )
}

/** 单行候选/计划行 */
function CandidateRow({ p, _cat }: { p: PlanItem; _cat: string }) {
  return (
    <div className="plan-row" style={{ background: 'rgba(255,255,255,0.02)' }}>
      <span className="plan-stock">{p.stock || '--'}</span>
      <span className="plan-condition">{p.condition || ''}</span>
      {p.stop_loss != null && (
        <span className="plan-stop-loss">
          止损{p.stop_loss}{p.stop_loss_pct != null ? `(${p.stop_loss_pct}%)` : ''}
        </span>
      )}
      {renderAlertIcon(p)}
    </div>
  )
}

function renderAlertIcon(p: PlanItem) {
  if (!p.alert || !p.alert.enabled) return null
  const labels: Record<string, string> = { price: '🔴价格', deviation: '🟡偏差', time: '⏰时间' }
  return (
    <span className="plan-alert-icon" title={`${labels[p.alert.type] || ''}报警已设`}>🔔</span>
  )
}

// ── 主组件 ──

export default function PlanLayer() {
  const [collapsed, setCollapsed] = useState(false)
  const [buy, setBuy] = useState<PlanItem[]>([])
  const [sell, setSell] = useState<PlanItem[]>([])
  const [watch, setWatch] = useState<PlanItem[]>([])
  const [alarms, setAlarms] = useState<StoredAlarm[]>([])
  const [holdings, setHoldings] = useState<BuySignalItem[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const yst = getYesterdayStr()
    const tdy = getTodayStr()

    Promise.all([
      fetchWorkbenchPlan(yst),
      fetchWorkbenchPlan(tdy),
      fetchActiveAlarms().catch(() => ({ alarms: [], count: 0 })),
      fetchReviewToday().catch(() => ({ holdings: [] })),
    ]).then(([yData, tData, alarmData, reviewData]) => {
      const yPlan = yData.plan || { buy: [], sell: [], watch: [] }
      const tPlan = tData.plan || { buy: [], sell: [], watch: [] }
      setBuy(mergePlans(yPlan.buy || [], tPlan.buy || []))
      setSell(mergePlans(yPlan.sell || [], tPlan.sell || []))
      setWatch(mergePlans(yPlan.watch || [], tPlan.watch || []))
      setAlarms((alarmData as any).alarms || [])
      setHoldings((reviewData as any).holdings || [])
      setLoaded(true)
    }).catch(() => setLoaded(true))
  }, [])

  // ── 分组逻辑 ──

  // 持仓股（有止损价的）
  const holdingsWithStop = holdings.filter(h =>
    (h as any).stop_loss_price != null || h.stop_loss != null
  )
  const holdingCodes = new Set(holdingsWithStop.map(h => h.code))

  // 建立持仓 → 计划映射
  const planByCode = new Map<string, { direction: string; condition?: string; plan: PlanItem }>()
  for (const p of [...buy, ...sell, ...watch]) {
    if (!p.stock) continue
    const code = extractCode(p.stock)
    if (!planByCode.has(code)) {
      // 从 buy/sell/watch 中找该股属于哪个分类
      const direction = buy.find(x => x.stock === p.stock) ? 'buy'
        : sell.find(x => x.stock === p.stock) ? 'sell' : 'watch'
      planByCode.set(code, { direction, condition: p.condition, plan: p })
    }
  }

  // 持仓操作组：有止损的持仓，合并计划信息
  const holdingsGroup = holdingsWithStop.map(h => {
    const planInfo = planByCode.get(h.code)
    return { h, planInfo }
  })

  // 候选组：非持仓的计划项（按 buy → sell → watch 排序）
  const allPlanItems = [
    ...buy.map(p => ({ ...p, _sortCat: 'buy' as const })),
    ...sell.map(p => ({ ...p, _sortCat: 'sell' as const })),
    ...watch.map(p => ({ ...p, _sortCat: 'watch' as const })),
  ]
  const candidateItems = allPlanItems.filter(p => {
    if (!p.stock) return false
    const code = extractCode(p.stock)
    return !holdingCodes.has(code)
  })
  // 候选去重（同股不同方向只保留一次）
  const seenCodes = new Set<string>()
  const candidateDeduped = candidateItems.filter(p => {
    if (!p.stock) return false
    const code = extractCode(p.stock)
    if (seenCodes.has(code)) return false
    seenCodes.add(code)
    return true
  })

  const hasHoldings = holdingsGroup.length > 0
  const hasCandidates = candidateDeduped.length > 0

  // 报警：过滤持仓股的价格报警（持仓止损已在持仓操作区展示）
  const planAlarms = alarms.filter(a => {
    if (a.type === 'price' && holdingCodes.has(a.stock_code)) return false
    return true
  })

  const totalCount = holdingsGroup.length + candidateDeduped.length
  const badgeBg = totalCount > 0 ? '#e94560' : '#555'
  const badgeText = loaded ? `${totalCount}项` : '加载中'

  return (
    <div className="layer plan-layer">
      <div className="layer-title" style={{ cursor: 'pointer' }} onClick={() => setCollapsed(v => !v)}>
        <span className="badge-layer">②</span> 📋 今日计划
        <span className="badge" style={{ background: badgeBg }}>{badgeText}</span>
        <span className="collapse-indicator">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (!loaded ? (
        <div className="empty">正在加载计划…</div>
      ) : (
        <div id="todayPlanArea">

          {/* ── 🔴 持仓操作 ── */}
          {hasHoldings && (
            <>
              <div className="plan-section-title" style={{ marginBottom: 4 }}>
                🔴 持仓操作 <span className="badge" style={{ background: '#e94560', fontSize: 9, padding: '1px 6px' }}>{holdingsGroup.length}只</span>
              </div>
              {holdingsGroup.map((item, i) => (
                <HoldingRow key={`h-${i}`} h={item.h} planInfo={item.planInfo} />
              ))}
            </>
          )}

          {/* ── 🟢 候选 ── */}
          {hasCandidates && (
            <>
              {hasHoldings && <div className="plan-separator" />}
              <div className="plan-section-title" style={{ marginBottom: 4 }}>
                🟢 候选 <span className="badge" style={{ background: '#4CAF50', fontSize: 9, padding: '1px 6px' }}>{candidateDeduped.length}只</span>
              </div>
              {candidateDeduped.map((p, i) => (
                <CandidateRow key={`c-${i}`} p={p} _cat={p._sortCat} />
              ))}
            </>
          )}

          {/* 空提示 */}
          {!hasHoldings && !hasCandidates && planAlarms.length === 0 && (
            <div className="empty">暂无计划</div>
          )}

          {/* ── 🟡 计划报警 ── */}
          {planAlarms.length > 0 && (
            <>
              <div className="plan-separator" />
              <div className="plan-section-title" style={{ marginBottom: 4 }}>
                🟡 计划报警 <span className="badge" style={{ background: '#ff9800', fontSize: 9, padding: '1px 6px' }}>{planAlarms.length}</span>
              </div>
              {planAlarms.map((a, i) => (
                <div key={`alarm-${i}`} className="plan-row" style={{ background: 'rgba(255,152,0,0.06)' }}>
                  <span title={ALARM_TYPE_LABELS[a.type]}>{ALARM_TYPE_ICONS[a.type] || '🔔'}</span>
                  <span className="plan-stock">{a.stock}</span>
                  {a.type === 'price' && a.stop_loss != null && (
                    <span className="plan-stop-loss">
                      止损 {a.stop_loss}{a.stop_loss_pct != null ? `(${a.stop_loss_pct}%)` : ''}
                    </span>
                  )}
                  {a.type === 'deviation' && (
                    <span className="plan-deviation">±{a.condition || 6}%</span>
                  )}
                  <span className="plan-date">{a.created?.slice(0, 10) || ''}</span>
                </div>
              ))}
            </>
          )}

        </div>
      ))}
    </div>
  )
}

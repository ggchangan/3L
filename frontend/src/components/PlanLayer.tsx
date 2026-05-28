import { useEffect, useState } from 'react'
import { fetchWorkbenchPlan, getYesterdayStr, fetchActiveAlarms, fetchReviewToday } from '../lib/api'
import type { PlanItem, StoredAlarm } from '../lib/api'
import type { BuySignalItem } from '../lib/types'

const ALARM_TYPE_ICONS: Record<string, string> = { price: '🔴', deviation: '🟡', time: '⏰' }
const ALARM_TYPE_LABELS: Record<string, string> = { price: '价格', deviation: '偏差', time: '时间' }

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

export default function PlanLayer() {
  const [buy, setBuy] = useState<PlanItem[]>([])
  const [sell, setSell] = useState<PlanItem[]>([])
  const [watch, setWatch] = useState<PlanItem[]>([])
  const [alarms, setAlarms] = useState<StoredAlarm[]>([])
  const [holdings, setHoldings] = useState<BuySignalItem[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const yst = getYesterdayStr()
    const tdy = getTodayStr()

    // 并行加载计划、报警、持仓数据
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

  // 持仓止损：只取有止损价的持仓
  const holdingsStopLoss = holdings.filter(h => h.stop_loss != null)
  const holdingCodes = new Set(holdings.map(h => h.code))

  // 计划报警：过滤掉持仓股的价格报警
  const planAlarms = alarms.filter(a => {
    if (a.type === 'price' && holdingCodes.has(a.stock_code)) return false
    return true
  })

  const total = buy.length + sell.length + watch.length
  const badgeBg = total > 0 ? '#e94560' : '#555'
  const badgeText = loaded ? `${total}项` : '加载中'

  return (
    <div className="layer plan-layer">
      <div className="layer-title">
        <span className="badge-layer">②</span> 📋 今日计划
        <span className="badge" style={{ background: badgeBg }}>{badgeText}</span>
      </div>
      {!loaded ? (
        <div className="empty">正在加载计划…</div>
      ) : (
        <div id="todayPlanArea">
          {/* ── 今日计划列表 ── */}
          {total > 0 && (
            <>
              {buy.length > 0 && (
                <>
                  <div style={{ fontSize: 11, marginBottom: 4 }}>🟢 买入：</div>
                  {buy.map((p, i) => renderPlanItem(p, i, 'buy'))}
                </>
              )}
              {sell.length > 0 && (
                <>
                  <div style={{ fontSize: 11, margin: '6px 0 4px' }}>🔴 卖出：</div>
                  {sell.map((p, i) => renderPlanItem(p, i, 'sell'))}
                </>
              )}
              {watch.length > 0 && (
                <>
                  <div style={{ fontSize: 11, margin: '6px 0 4px' }}>👁️ 观察：</div>
                  {watch.map((p, i) => (
                    <div key={`w-${i}`} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '3px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)', marginBottom: 2, fontSize: 12 }}>
                      <span style={{ color: '#e0e0e0' }}>{p.stock || p.sector || '--'}</span>
                      {p.focus && <span style={{ color: '#888' }}>→ {p.focus}</span>}
                      {renderStopLoss(p)}
                      {renderAlertIcon(p)}
                    </div>
                  ))}
                </>
              )}
            </>
          )}
          {total === 0 && holdingsStopLoss.length === 0 && planAlarms.length === 0 && (
            <div className="empty">暂无计划</div>
          )}

          {/* ── 🔴 持仓止损 ── */}
          {holdingsStopLoss.length > 0 && (
            <>
              <div style={{ borderTop: '1px solid #2a2a4e', margin: '8px 0' }} />
              <div style={{ fontSize: 11, marginBottom: 4 }}>
                🔴 持仓止损 <span className="badge" style={{ background: '#e94560', fontSize: 9, padding: '1px 6px' }}>{holdingsStopLoss.length}</span>
              </div>
              {holdingsStopLoss.map((h, i) => (
                <div key={`sl-${i}`} style={{
                  display: 'flex', gap: 6, alignItems: 'center',
                  padding: '3px 8px', borderRadius: 4,
                  background: 'rgba(233,69,96,0.06)', marginBottom: 2, fontSize: 12,
                }}>
                  <span style={{ color: '#e0e0e0' }}>{h.name}({h.code})</span>
                  <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                    止损 {h.stop_loss}
                    {h.stop_loss_pct != null ? ` (${h.stop_loss_pct >= 0 ? '+' : ''}${h.stop_loss_pct.toFixed(2)}%)` : ''}
                  </span>
                  {h.price != null && (
                    <span style={{ fontSize: 9, color: '#888', marginLeft: 'auto' }}>
                      现价 {h.price} {h.change != null ? `${h.change >= 0 ? '+' : ''}${h.change.toFixed(1)}%` : ''}
                    </span>
                  )}
                </div>
              ))}
            </>
          )}

          {/* ── 🟡 计划报警 ── */}
          {planAlarms.length > 0 && (
            <>
              <div style={{ borderTop: '1px solid #2a2a4e', margin: '8px 0' }} />
              <div style={{ fontSize: 11, marginBottom: 4 }}>
                🟡 计划报警 <span className="badge" style={{ background: '#ff9800', fontSize: 9, padding: '1px 6px' }}>{planAlarms.length}</span>
              </div>
              {planAlarms.map((a, i) => (
                <div key={`alarm-${i}`} style={{
                  display: 'flex', gap: 6, alignItems: 'center',
                  padding: '3px 8px', borderRadius: 4,
                  background: 'rgba(255,152,0,0.06)', marginBottom: 2, fontSize: 12,
                }}>
                  <span title={ALARM_TYPE_LABELS[a.type]}>{ALARM_TYPE_ICONS[a.type] || '🔔'}</span>
                  <span style={{ color: '#e0e0e0' }}>{a.stock}</span>
                  {a.type === 'price' && a.stop_loss != null && (
                    <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                      止损 {a.stop_loss}{a.stop_loss_pct != null ? `(${a.stop_loss_pct}%)` : ''}
                    </span>
                  )}
                  {a.type === 'deviation' && (
                    <span style={{ fontSize: 10, color: '#ffd700', whiteSpace: 'nowrap' }}>
                      ±{a.condition || 6}%
                    </span>
                  )}
                  <span style={{ fontSize: 9, color: '#555', marginLeft: 'auto' }}>
                    {a.created?.slice(0, 10) || ''}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function renderPlanItem(p: PlanItem, i: number, _cat: string) {
  return (
    <div key={`${_cat}-${i}`} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '3px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)', marginBottom: 2, fontSize: 12 }}>
      <span style={{ color: '#e0e0e0' }}>{p.stock || '--'}</span>
      <span style={{ color: '#888', fontSize: 10 }}>{p.condition || ''}</span>
      {renderStopLoss(p)}
      {renderAlertIcon(p)}
    </div>
  )
}

function renderStopLoss(p: PlanItem) {
  if (p.stop_loss == null) return null
  return (
    <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
      止损{p.stop_loss}{p.stop_loss_pct != null ? `(${p.stop_loss_pct}%)` : ''}
    </span>
  )
}

function renderAlertIcon(p: PlanItem) {
  if (!p.alert || !p.alert.enabled) return null
  const labels: Record<string, string> = { price: '🔴价格', deviation: '🟡偏差', time: '⏰时间' }
  return (
    <span style={{ fontSize: 10, color: '#ff9800', marginLeft: 'auto' }} title={`${labels[p.alert.type] || ''}报警已设`}>
      🔔
    </span>
  )
}

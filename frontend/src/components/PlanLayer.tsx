import { useEffect, useState } from 'react'
import { fetchWorkbenchPlan, getYesterdayStr, fetchActiveAlarms } from '../lib/api'
import type { PlanItem, StoredAlarm } from '../lib/api'

const ALARM_TYPE_ICONS: Record<string, string> = { price: '🔴', deviation: '🟡', time: '⏰' }
const ALARM_TYPE_LABELS: Record<string, string> = { price: '价格', deviation: '偏差', time: '时间' }

export default function PlanLayer() {
  const [buy, setBuy] = useState<PlanItem[]>([])
  const [sell, setSell] = useState<PlanItem[]>([])
  const [watch, setWatch] = useState<PlanItem[]>([])
  const [alarms, setAlarms] = useState<StoredAlarm[]>([])
  const [loaded, setLoaded] = useState(false)
  const dateStr = getYesterdayStr()

  useEffect(() => {
    fetchWorkbenchPlan(dateStr).then(data => {
      const plan = data.plan || {}
      setBuy(plan.buy || [])
      setSell(plan.sell || [])
      setWatch(plan.watch || [])
      setLoaded(true)
    }).catch(() => setLoaded(true))

    // 加载持久化报警清单
    fetchActiveAlarms().then(data => {
      setAlarms(data.alarms || [])
    }).catch(() => {})
  }, [])

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
        <div className="empty">正在加载昨日计划…</div>
      ) : (
        <div id="todayPlanArea">
          <div style={{ fontSize: 11, color: '#555', marginBottom: 6 }}>📅 {dateStr} 计划</div>
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

          {/* 🔔 报警清单 — 从 alarms.json 持久化读取 */}
          {alarms.length > 0 && (
            <>
              <div style={{ borderTop: '1px solid #2a2a4e', margin: '8px 0' }} />
              <div style={{ fontSize: 11, marginBottom: 4 }}>
                🔔 报警清单 <span className="badge" style={{ background: '#ff9800', fontSize: 9, padding: '1px 6px' }}>{alarms.length}</span>
              </div>
              {alarms.map((a, i) => (
                <div key={`alarm-${i}`} style={{
                  display: 'flex', gap: 6, alignItems: 'center',
                  padding: '3px 8px', borderRadius: 4,
                  background: 'rgba(255,152,0,0.06)', marginBottom: 2, fontSize: 12,
                }}>
                  <span title={ALARM_TYPE_LABELS[a.type]}>{ALARM_TYPE_ICONS[a.type] || '🔔'}</span>
                  <span style={{ color: '#e0e0e0' }}>{a.stock}</span>
                  {a.type === 'price' && a.stop_loss != null && (
                    <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                      止损{a.stop_loss}{a.stop_loss_pct != null ? `(${a.stop_loss_pct}%)` : ''}
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

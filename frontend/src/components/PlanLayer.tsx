import { useEffect, useState } from 'react'
import { fetchWorkbenchPlan, getYesterdayStr } from '../lib/api'
import type { PlanItem } from '../lib/types'

export default function PlanLayer() {
  const [buy, setBuy] = useState<PlanItem[]>([])
  const [sell, setSell] = useState<PlanItem[]>([])
  const [watch, setWatch] = useState<PlanItem[]>([])
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
      ) : total === 0 ? (
        <div className="empty">昨日无计划</div>
      ) : (
        <div id="todayPlanArea">
          <div style={{ fontSize: 11, color: '#555', marginBottom: 6 }}>📅 {dateStr} 计划</div>
          {buy.length > 0 && (
            <>
              <div style={{ fontSize: 11, marginBottom: 4 }}>🟢 买入：</div>
              {buy.map((p, i) => renderPlanItem(p, i))}
            </>
          )}
          {sell.length > 0 && (
            <>
              <div style={{ fontSize: 11, margin: '6px 0 4px' }}>🔴 卖出：</div>
              {sell.map((p, i) => renderPlanItem(p, i))}
            </>
          )}
          {watch.length > 0 && (
            <>
              <div style={{ fontSize: 11, margin: '6px 0 4px' }}>👁️ 观察：</div>
              {watch.map((p, i) => (
                <div key={`w-${i}`} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '3px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)', marginBottom: 2, fontSize: 12 }}>
                  <span style={{ color: '#e0e0e0' }}>{p.stock || p.sector || '--'}</span>
                  <span style={{ color: '#888' }}>→</span>
                  <span style={{ color: '#aaa' }}>{p.focus || ''}</span>
                  <span style={{ marginLeft: 'auto' }}>{statusLabel(p.status)}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function renderPlanItem(p: PlanItem, i: number) {
  return (
    <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '3px 8px', borderRadius: 4, background: 'rgba(255,255,255,0.02)', marginBottom: 2, fontSize: 12 }}>
      <span style={{ color: '#e0e0e0' }}>{p.stock || '--'}</span>
      <span style={{ color: '#888', fontSize: 10 }}>{p.condition || ''}</span>
      <span style={{ color: '#555', fontSize: 10 }}>{p.qty || ''}</span>
      <span style={{ marginLeft: 'auto' }}>{statusLabel(p.status)}</span>
    </div>
  )
}

function statusLabel(s?: string) {
  switch (s) {
    case 'executed': return <span style={{ color: '#22c55e' }}>✅ 已执行</span>
    case 'triggered': return <span style={{ color: '#ffd700' }}>⚡ 已触发</span>
    case 'not_triggered': return <span style={{ color: '#e94560' }}>❌ 未触发</span>
    default: return <span style={{ color: '#888' }}>⏳ 待触发</span>
  }
}

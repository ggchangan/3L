import { useEffect, useState } from 'react'
import { fetchStopLoss } from '../lib/api'
import type { StopLossItem } from '../lib/types'

export default function StopLossArea() {
  const [items, setItems] = useState<StopLossItem[]>([])

  useEffect(() => {
    fetchStopLoss().then(d => setItems(d.triggered || []))
    const timer = setInterval(() => {
      fetchStopLoss().then(d => setItems(d.triggered || []))
    }, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <>
      <div className="block-title">
        🛑 止损预警
        <span className="badge" style={{ background: items.length > 0 ? '#e94560' : '#555' }}>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="empty">✅ 暂无触发止损</div>
      ) : (
        items.map((s, i) => (
          <div key={i} className="stop-loss-item">
            <div>{s.name} ({s.code})</div>
            <div style={{ fontSize: 11, display: 'flex', gap: 12, color: '#aaa', marginTop: 2 }}>
              <span>现价: <b style={{ color: '#e94560' }}>{s.current_price.toFixed(2)}</b></span>
              <span>止损: {s.stop_loss.toFixed(2)}</span>
              <span>亏损: <b style={{ color: '#e94560' }}>{s.loss_pct}%</b></span>
              <span>理由: {s.reason || '-'}</span>
            </div>
          </div>
        ))
      )}
    </>
  )
}

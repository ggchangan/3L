import type { ReviewData } from '../lib/types'

interface Props {
  plan: ReviewData['trading_plan']
}

const PRI_COLORS: Record<string, string> = { '高': '#e94560', '中': '#ffd700', '低': '#888' }

export default function TradingPlan({ plan }: Props) {
  if (!plan) return <div className="empty">暂无交易计划</div>

  return (
    <div className="plan-card">
      <div className="plan-title">📌 {plan.overall_strategy || '正常交易'}</div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
        <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>仓位:</span> {plan.position_level || '--'}</span>
        <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>建仓:</span> {plan.build_per_stock_pct || '--'}</span>
        {plan.main_lines && plan.main_lines.length > 0 && (
          <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>主线:</span> {plan.main_lines.join(' · ')}</span>
        )}
      </div>

      {plan.position_detail && (
        <div style={{ marginBottom: 12, padding: '6px 10px', background: 'rgba(78,205,196,0.08)', borderRadius: 6, fontSize: 12, color: '#4ecdc4' }}>
          📋 {plan.position_detail}
        </div>
      )}

      {plan.holdings_action && plan.holdings_action.length > 0 && (
        <>
          <div style={{ marginBottom: 8 }}><strong style={{ color: '#4ecdc4', fontSize: 13 }}>📦 个股操作</strong></div>
          {plan.holdings_action.map((item, i) => {
            const color = PRI_COLORS[item.priority] || '#888'
            return (
              <div key={i} className="plan-item" style={{ borderLeft: `3px solid ${color}`, paddingLeft: 8, marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>{item.stock}</span>
                <span style={{ color }}> → {item.action}</span>
                <span style={{ color: '#888', fontSize: 11 }}> {item.reason}</span>
                <span style={{ color, fontSize: 10, marginLeft: 6 }}>{item.priority}</span>
              </div>
            )
          })}
        </>
      )}

      {plan.buy_priority && plan.buy_priority.length > 0 && (
        <>
          <div style={{ marginBottom: 6, marginTop: 12 }}><strong style={{ color: '#ffd700', fontSize: 13 }}>🎯 关注买点（优先级排序）</strong></div>
          {plan.buy_priority.map((s, i) => (
            <div key={i} className="plan-item" style={{ fontSize: 12 }}>
              <span style={{ color: '#e94560', fontWeight: 'bold' }}>#{i + 1}</span>
              <span style={{ fontWeight: 600 }}> {s.name}</span>
              <span style={{ color: '#888' }}> {s.buy_point}</span>
              {s.is_main && <span className="tag red" style={{ fontSize: 10 }}>主线</span>}
              {s.profit_model1 && <span className="tag" style={{ background: '#e94560', fontSize: 10, padding: '1px 6px' }}>🏆</span>}
              {s.trend_stock && <span className="tag" style={{ background: '#2196f3', fontSize: 10, padding: '1px 6px' }}>📈</span>}
              <span style={{ color: (s.change || 0) >= 0 ? '#ff4444' : '#44aa44' }}> {(s.change || 0) >= 0 ? '+' : ''}{s.change}%</span>
              {s.stop_loss != null && <span style={{ color: '#ff9800', fontSize: 10 }}> 止损{s.stop_loss}{s.stop_loss_pct != null ? `(${s.stop_loss_pct}%)` : ''}</span>}
            </div>
          ))}
        </>
      )}

      {plan.risk_items && plan.risk_items.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {plan.risk_items.map((item, i) => {
            const isRed = item.includes('🔴')
            return (
              <div key={i} style={{
                padding: '5px 8px', margin: '3px 0', borderRadius: 4, fontSize: 12,
                background: isRed ? 'rgba(233,69,96,0.08)' : 'rgba(255,255,255,0.02)',
                color: isRed ? '#e94560' : '#aaa',
              }}>{item}</div>
            )
          })}
        </div>
      )}
    </div>
  )
}

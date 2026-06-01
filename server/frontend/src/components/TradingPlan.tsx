import type { ReviewData } from '../lib/types'

interface Props {
  plan: ReviewData['trading_plan']
}

const PRI_COLORS: Record<string, string> = { '高': '#e94560', '中': '#ffd700', '低': '#888' }

// 机会类型配置
const OPP_CONFIG: Record<string, { label: string; emoji: string; color: string; order: number }> = {
  '主线回调': { label: '主线回调', emoji: '🎯', color: '#e94560', order: 0 },
  '次线机会': { label: '次线机会', emoji: '🎯', color: '#ffd700', order: 1 },
  '波谷观察': { label: '波谷观察', emoji: '🔮', color: '#4ecdc4', order: 2 },
  '趋势延续': { label: '趋势延续', emoji: '📈', color: '#44aa44', order: 3 },
  '回调中': { label: '回调中', emoji: '📉', color: '#888', order: 4 },
  '见顶风险': { label: '见顶风险', emoji: '⚠️', color: '#ff6b00', order: 5 },
  '主线观察': { label: '主线观察', emoji: '👀', color: '#666', order: 6 },
  '次级观察': { label: '次级观察', emoji: '👀', color: '#666', order: 7 },
  '其他': { label: '其他（暂无方向阶段数据）', emoji: '⚪', color: '#555', order: 99 },
}

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
            const oppColor: Record<string, string> = {
              '主线回调': '#e94560', '次线机会': '#ffd700', '波谷观察': '#4ecdc4',
              '趋势延续': '#44aa44', '见顶风险': '#ff6b00', '回调中': '#888',
            }
            const opp = (item as any).opportunity || ''
            const oppC = oppColor[opp] || ''
            return (
              <div key={i} className="plan-item" style={{ borderLeft: `3px solid ${color}`, paddingLeft: 8, marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600 }}>{item.stock}</span>
                  <span style={{ color }}> → {item.action}</span>
                  {oppC && <span style={{ color: oppC, fontSize: 10, fontWeight: 600 }}>{opp}</span>}
                  <span style={{ color, fontSize: 10, marginLeft: 'auto' }}>{item.priority}</span>
                </div>
                <div style={{ color: '#888', fontSize: 11, marginTop: 2 }}>{item.reason}</div>
              </div>
            )
          })}
        </>
      )}

      {plan.buy_priority && plan.buy_priority.length > 0 && (
        <>
          <div style={{ marginBottom: 6, marginTop: 12 }}><strong style={{ color: '#ffd700', fontSize: 13 }}>🎯 关注买点（机会类型排序）</strong></div>
          {/* 分组展示 */}
          {groupedBuyPriority(plan.buy_priority).map(([opp, items]) => {
            const cfg = OPP_CONFIG[opp] || { label: opp, emoji: '📋', color: '#888', order: 99 }
            return (
              <div key={opp} style={{ marginBottom: 8 }}>
                <div style={{ color: cfg.color, fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                  {cfg.emoji} {cfg.label} ({items.length})
                </div>
                {items.map((s, i) => (
                  <div key={i} className="plan-item" style={{ fontSize: 12, paddingLeft: 8, borderLeft: `2px solid ${cfg.color}20`, marginBottom: 2 }}>
                    <span style={{ color: '#e94560', fontWeight: 'bold' }}>#{i + 1}</span>
                    <span style={{ fontWeight: 600 }}> {s.name}</span>
                    <span style={{ color: '#888' }}> {s.buy_point}</span>
                    {s.is_main && <span className="tag red" style={{ fontSize: 10 }}>主线</span>}
                    {s.profit_model1 && <span className="tag" style={{ background: '#e94560', fontSize: 10, padding: '1px 6px' }}>🏆</span>}
                    {s.trend_stock && <span className="tag" style={{ background: '#2196f3', fontSize: 10, padding: '1px 6px' }}>📈</span>}
                    <span style={{ color: (s.change || 0) >= 0 ? '#ff4444' : '#44aa44' }}> {(s.change || 0) >= 0 ? '+' : ''}{s.change}%</span>
                    {s.stop_loss != null && <span style={{ color: '#ff9800', fontSize: 10 }}> 止损{s.stop_loss}{s.stop_loss_pct != null ? `(${s.stop_loss_pct}%)` : ''}</span>}
                    {/* 显示理由 */}
                    {(opp === '其他') && (s as any).opp_reason && (
                      <span style={{ color: '#555', fontSize: 10, marginLeft: 4 }}>· {(s as any).opp_reason}</span>
                    )}
                    {s.sector && <span style={{ color: '#555', fontSize: 10, marginLeft: 4 }}>· {s.sector}</span>}
                  </div>
                ))}
              </div>
            )
          })}
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

/** 按机会类型分组 buy_priority */
function groupedBuyPriority(items: NonNullable<NonNullable<Props['plan']>['buy_priority']>) {
  const groups: Record<string, typeof items> = {}
  for (const item of items) {
    let opp = (item as any).opportunity || '--'
    if (opp === '--') opp = '其他'
    if (!groups[opp]) groups[opp] = []
    groups[opp].push(item)
  }
  const OPP_ORDER: Record<string, number> = {
    '主线回调': 0, '次线机会': 1, '波谷观察': 2,
    '趋势延续': 3, '回调中': 4, '见顶风险': 5,
    '主线观察': 6, '次级观察': 7, '其他': 99,
  }
  return Object.entries(groups).sort(([a], [b]) => {
    const oa = OPP_ORDER[a] ?? 99
    const ob = OPP_ORDER[b] ?? 99
    return oa - ob
  })
}

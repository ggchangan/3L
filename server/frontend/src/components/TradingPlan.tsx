import type { ReviewData } from '../lib/types'

interface Props {
  plan: ReviewData['trading_plan']
}

const PRI_COLORS: Record<string, string> = { '高': '#e94560', '中': '#ffd700', '低': '#888' }

const OPP_CFG: Record<string, { emoji: string; color: string; order: number }> = {
  '主线回调': { emoji: '🎯', color: '#e94560', order: 0 },
  '次线机会': { emoji: '🎯', color: '#ffd700', order: 1 },
  '波谷观察': { emoji: '🔮', color: '#4ecdc4', order: 2 },
  '趋势延续': { emoji: '📈', color: '#44aa44', order: 3 },
  '回调中': { emoji: '📉', color: '#888', order: 4 },
  '见顶风险': { emoji: '⚠️', color: '#ff6b00', order: 5 },
  '主线观察': { emoji: '👀', color: '#666', order: 6 },
  '次级观察': { emoji: '👀', color: '#666', order: 7 },
  '其他': { emoji: '⚪', color: '#555', order: 99 },
}
const OPP_ORDER: Record<string, number> = {}
Object.entries(OPP_CFG).forEach(([k, v]) => { OPP_ORDER[k] = v.order })

export default function TradingPlan({ plan }: Props) {
  if (!plan) return <div className="empty">暂无交易计划</div>

  return (
    <div className="plan-card">
      <div className="plan-title">📌 {plan.overall_strategy || '正常交易'}</div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
        <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>仓位:</span> {plan.position_level || '--'}</span>
        <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>建仓:</span> {plan.build_per_stock_pct || '--'}</span>
        {plan.main_lines?.length ? <span style={{ fontSize: 13 }}><span style={{ color: '#888' }}>主线:</span> {plan.main_lines.join(' · ')}</span> : null}
      </div>
      {plan.position_detail && (
        <div style={{ marginBottom: 12, padding: '6px 10px', background: 'rgba(78,205,196,0.08)', borderRadius: 6, fontSize: 12, color: '#4ecdc4' }}>
          📋 {plan.position_detail}
        </div>
      )}

      {/* 个股操作 */}
      <PlanSection
        title="📦 个股操作"
        items={plan.holdings_action}
        groupKey={g => g.opportunity || '其他'}
        renderRow={item => {
          const priColor = PRI_COLORS[item.priority] || '#888'
          const m = (item.stock || '').match(/\(([^)]+)\)/)
          const name = (item.stock || '').replace(/\([^)]+\)/, '')
          const code = m ? m[1] : ''
          return (
            <div style={{ padding: '4px 8px', borderBottom: '1px solid #222' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <b style={{ fontSize: 12 }}>{name}</b>
                <span style={{ color: '#555', fontSize: 10 }}>{code}</span>
                <span style={{ color: priColor, fontWeight: 600, fontSize: 11 }}>→ {item.action}</span>
                <span style={{ color: '#888', fontSize: 10 }}>{item.sector || ''}</span>
                <span style={{ color: priColor, fontSize: 10, marginLeft: 'auto' }}>{item.priority}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 1, fontSize: 10, color: '#888' }}>
                {item.stop_loss != null ? <span style={{ color: '#ff9800' }}>⬇ {Number(item.stop_loss).toFixed(2)}{item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}</span> : null}
                <span>{item.reason}</span>
              </div>
            </div>
          )
        }}
      />

      {/* 关注买点 */}
      <PlanSection
        title="🎯 关注买点"
        items={plan.buy_priority}
        groupKey={g => g.opportunity || '其他'}
        renderRow={item => {
          return (
            <div style={{ padding: '4px 8px', borderBottom: '1px solid #222' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <b style={{ fontSize: 12 }}>{item.name}</b>
                <span style={{ color: '#888', fontSize: 10 }}>{item.buy_point}</span>
                <span style={{ color: '#555', fontSize: 10 }}>{item.sector || ''}</span>
                {item.is_main && <span className="tag red" style={{ fontSize: 9 }}>主线</span>}
                {item.profit_model1 && <span className="tag" style={{ background: '#e94560', fontSize: 9, padding: '1px 4px' }}>🏆</span>}
                {item.trend_stock && <span className="tag" style={{ background: '#2196f3', fontSize: 9, padding: '1px 4px' }}>📈</span>}
                <span style={{ color: (item.change || 0) >= 0 ? '#ff4444' : '#44aa44', fontSize: 11, marginLeft: 'auto' }}>
                  {(item.change || 0) >= 0 ? '+' : ''}{item.change}%
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 1, fontSize: 10, color: '#888' }}>
                {item.stop_loss != null ? <span style={{ color: '#ff9800' }}>⬇ {Number(item.stop_loss).toFixed(2)}{item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}</span> : null}
                {(item as any).opp_reason ? <span>{(item as any).opp_reason}</span> : null}
              </div>
            </div>
          )
        }}
      />

      {plan.risk_items?.length ? (
        <div style={{ marginTop: 12 }}>
          {plan.risk_items.map((item, i) => (
            <div key={i} style={{
              padding: '5px 8px', margin: '3px 0', borderRadius: 4, fontSize: 12,
              background: item.includes('🔴') ? 'rgba(233,69,96,0.08)' : 'rgba(255,255,255,0.02)',
              color: item.includes('🔴') ? '#e94560' : '#aaa',
            }}>{item}</div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

/* 分组展示组件 */
function PlanSection({ title, items, groupKey, renderRow }: {
  title: string
  items?: any[]
  groupKey: (item: any) => string
  renderRow: (item: any) => React.ReactNode
}) {
  if (!items?.length) return <div className="empty" style={{marginTop:12}}>{title.replace(/^[^\s]+\s/,'')} 暂无</div>

  const groups: Record<string, any[]> = {}
  for (const item of items) {
    const k = groupKey(item)
    if (!groups[k]) groups[k] = []
    groups[k].push(item)
  }
  const sorted = Object.entries(groups).sort(([a], [b]) => (OPP_ORDER[a] ?? 99) - (OPP_ORDER[b] ?? 99))

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ marginBottom: 6 }}><strong style={{ color: '#4ecdc4', fontSize: 13 }}>{title}</strong></div>
      {sorted.map(([opp, rows]) => {
        const cfg = OPP_CFG[opp] || { emoji: '📋', color: '#888', order: 99 }
        const bgColor = cfg.color + '15'
        return (
          <div key={opp} style={{ marginBottom: 8, background: bgColor, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ color: cfg.color, fontSize: 11, fontWeight: 600, padding: '4px 8px' }}>
              {cfg.emoji} {opp} ({rows.length})
            </div>
            <div style={{ background: 'rgba(0,0,0,0.2)' }}>
              {rows.map((item, i) => renderRow(item))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

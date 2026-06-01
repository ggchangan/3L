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

      {/* 统一决策表头 */}
      <PlanTable
        title="📦 个股操作"
        items={plan.holdings_action}
        groupKey={g => g.opportunity || '其他'}
        oppLabel={g => g.sector || ''}
        columns={[
          { label: '个股', w: '1fr', render: item => {
            const m = (item.stock || '').match(/\(([^)]+)\)/)
            return <><b>{item.stock?.replace(/\([^)]+\)/, '')}</b> <span style={{color:'#555',fontSize:10}}>{m?.[1]}</span></>
          }},
          { label: '操作', w: 'auto', render: item => <span style={{color:PRI_COLORS[item.priority]||'#888',fontWeight:600}}>{item.action}</span> },
          { label: '止损', w: 'auto', render: item => item.stop_loss != null ? <span style={{color:'#ff9800',fontSize:10}}>⬇ {Number(item.stop_loss).toFixed(2)}{item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}</span> : null },
        ]}
      />

      <PlanTable
        title="🎯 关注买点"
        items={plan.buy_priority}
        groupKey={g => g.opportunity || '其他'}
        oppLabel={g => g.sector || ''}
        columns={[
          { label: '个股', w: '1fr', render: item => <><b>{item.name}</b> <span style={{color:'#555',fontSize:10}}>·{item.sector||'--'}</span></> },
          { label: '买点', w: 'auto', render: item => <span style={{fontSize:10,color:'#aaa'}}>{item.buy_point}</span> },
          { label: '止损', w: 'auto', render: item => item.stop_loss != null ? <span style={{color:'#ff9800',fontSize:10}}>⬇ {Number(item.stop_loss).toFixed(2)}{item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}</span> : null },
        ]}
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

/* 统一决策表组件 */
function PlanTable({ title, items, groupKey, oppLabel, columns }: {
  title: string
  items?: any[]
  groupKey: (item: any) => string
  oppLabel: (item: any) => string
  columns: { label: string; w: string; render: (item: any) => React.ReactNode }[]
}) {
  if (!items?.length) return <div className="empty" style={{marginTop:12}}>{title.replace(/^[^\s]+\s/,'')} 暂无</div>

  // 分组
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
        return (
          <div key={opp} style={{ marginBottom: 8 }}>
            <div style={{ color: cfg.color, fontSize: 11, fontWeight: 600, marginBottom: 3 }}>
              {cfg.emoji} {opp} ({rows.length})
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <tbody>
                {rows.map((item, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    {columns.map((col, ci) => (
                      <td key={ci} style={{
                        padding: '3px 6px', whiteSpace: 'nowrap',
                        width: col.w !== 'auto' ? col.w : undefined,
                      }}>
                        {col.render(item)}
                      </td>
                    ))}
                    {/* 右侧 opp 标签 */}
                    <td style={{ textAlign: 'right', padding: '3px 6px', whiteSpace: 'nowrap' }}>
                      {oppLabel(item) ? <span style={{color:'#555',fontSize:10}}>{oppLabel(item)}</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}
    </div>
  )
}

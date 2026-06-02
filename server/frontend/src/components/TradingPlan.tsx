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
      <UnifiedTable
        title="📦 个股操作"
        items={plan.holdings_action}
        groupKey={g => g.opportunity || '其他'}
        renderAction={item => {
          const c = PRI_COLORS[item.priority] || '#888'
          return <span style={{ color: c, fontWeight: 600 }}>{item.action_type || item.action}</span>
        }}
        renderSignal={item => {
          const sig = item.signal || ''
          const sigs = item.triggered_signals || []
          const ft = item.fusion_type || ''
          return (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
              {sig ? <span style={{ color: '#aaa', fontSize: 10 }}>{sig}</span> : null}
              {(sigs.length > 0) && sigs.slice(0,2).map((s: any, i: number) => {
                const c = s.direction === 'bullish' ? '#4ecdc4' : s.direction === 'bearish' ? '#e94560' : '#ffd700'
                return <span key={i} style={{fontSize:9,color:c,background:'rgba(255,255,255,0.05)',padding:'1px 4px',borderRadius:3}}>{s.name}</span>
              })}
              {ft && (
                <span style={{fontSize:9,color:'#58a6ff',background:'rgba(88,166,255,0.1)',padding:'1px 4px',borderRadius:3}}>
                  {({strong_buy:'强买',signal_buy:'买入',conflict_bearish:'⚠️',signal_sell:'卖出',conflict_bullish:'等确认',buy_point_only:'买点',bearish_watch:'偏空',bullish_wait:'等待',balance:'平衡'})[ft] || ft}
                </span>
              )}
            </div>
          )
        }}
        renderExtra={item => {
          const m = (item.stock || '').match(/\(([^)]+)\)/)
          return m ? <span style={{ color: '#555', fontSize: 10 }}>{m[1]}</span> : null
        }}
        rightCol={item => {
          const chg = item.change || 0
          const chgStr = <span style={{color: chg >= 0 ? '#ff4444' : '#44aa44', fontSize: 11, marginRight: 6}}>{(chg >= 0 ? '+' : '')}{chg}%</span>
          const tags: React.ReactNode[] = [chgStr]
          if (item.is_main) tags.push(<span key="m" className="tag red" style={{fontSize:9}}>主线</span>)
          if (item.profit_model1) tags.push(<span key="p" className="tag" style={{background:'#e94560',fontSize:9,padding:'1px 4px'}}>🏆</span>)
          if (item.trend_stock) tags.push(<span key="t" className="tag" style={{background:'#2196f3',fontSize:9,padding:'1px 4px'}}>📈</span>)
          tags.push(<span key="pr" style={{color: PRI_COLORS[item.priority] || '#888', fontSize: 10, marginLeft: 4}}>{item.priority}</span>)
          return <>{tags}</>
        }}
      />

      {/* 关注买点 */}
      <UnifiedTable
        title="🎯 关注买点"
        items={plan.buy_priority}
        groupKey={g => g.opportunity || '其他'}
        renderAction={item => <span style={{ color: '#4ecdc4', fontWeight: 600, fontSize: 11 }}>买入</span>}
        renderSignal={item => {
          const sig = item.signal || item.buy_point || ''
          return <span style={{ color: '#aaa', fontSize: 10 }}>{sig}</span>
        }}
        renderExtra={item => null}
        rightCol={item => {
          const chg = item.change || 0
          const chgStr = <span style={{color: chg >= 0 ? '#ff4444' : '#44aa44', fontSize: 11, marginRight: 6}}>{(chg >= 0 ? '+' : '')}{chg}%</span>
          const tags: React.ReactNode[] = [chgStr]
          if (item.is_main) tags.push(<span key="m" className="tag red" style={{fontSize:9}}>主线</span>)
          if (item.profit_model1) tags.push(<span key="p" className="tag" style={{background:'#e94560',fontSize:9,padding:'1px 4px'}}>🏆</span>)
          if (item.trend_stock) tags.push(<span key="t" className="tag" style={{background:'#2196f3',fontSize:9,padding:'1px 4px'}}>📈</span>)
          return <>{tags}</>
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

/* 统一决策表 */
function UnifiedTable({ title, items, groupKey, renderAction, renderSignal, renderExtra, rightCol }: {
  title: string
  items?: any[]
  groupKey: (item: any) => string
  renderAction: (item: any) => React.ReactNode
  renderSignal: (item: any) => React.ReactNode
  renderExtra: (item: any) => React.ReactNode
  rightCol: (item: any) => React.ReactNode
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
        return (
          <div key={opp} style={{ marginBottom: 8 }}>
            <div style={{ color: cfg.color, fontSize: 11, fontWeight: 600, marginBottom: 3 }}>
              {cfg.emoji} {opp} ({rows.length})
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <colgroup>
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: '1fr' }} />
                <col style={{ width: 'auto' }} />
              </colgroup>
              <thead>
                <tr style={{ color: '#555', fontSize: 10 }}>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>个股</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>操作</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>信号</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>止损</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>板块</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>原因</th>
                  <th style={{ textAlign: 'right', padding: '2px 4px', borderBottom: '1px solid #333' }}>优先</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap' }}>
                      <b>{item.name || item.stock?.replace(/\([^)]+\)/, '')}</b>
                      {renderExtra(item)}
                    </td>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap' }}>
                      {renderAction(item)}
                    </td>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap' }}>
                      {renderSignal(item)}
                    </td>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap' }}>
                      {item.stop_loss != null ? (
                        <span style={{ color: '#ff9800', fontSize: 10 }}>
                          ⬇ {Number(item.stop_loss).toFixed(2)}{item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}
                        </span>
                      ) : null}
                    </td>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap', color: '#555', fontSize: 10 }}>
                      {item.sector || ''}
                    </td>
                    <td style={{ padding: '3px 4px', color: '#888', fontSize: 10, width: '100%' }}>
                      {item.reason}
                    </td>
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                      {rightCol(item)}
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

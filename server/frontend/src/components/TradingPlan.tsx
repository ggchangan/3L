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
          <div style={{ marginBottom: 8 }}><strong style={{ color: '#4ecdc4', fontSize: 13 }}>📦 个股操作（按板块机会分组）</strong></div>
          {groupedHoldingsAction(plan.holdings_action).map(([opp, secGroups]) => {
            const cfg = OPP_CONFIG[opp] || { label: opp, emoji: '📋', color: '#888', order: 99 }
            const total = secGroups.reduce((s, g) => s + g.items.length, 0)
            return (
              <div key={opp} style={{ marginBottom: 10 }}>
                <div style={{ color: cfg.color, fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  {cfg.emoji} {cfg.label} ({total})
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr style={{ color: '#555', fontSize: 10 }}>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>个股</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>操作</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>板块</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>原因</th>
                      <th style={{ textAlign: 'center', padding: '2px 6px', borderBottom: '1px solid #333' }}>优先</th>
                    </tr>
                  </thead>
                  <tbody>
                    {secGroups.map((secGroup, gi) => (
                      secGroup.items.map((item, i) => {
                        const color = PRI_COLORS[item.priority] || '#888'
                        const stockName = item.stock || ''
                        const codeMatch = stockName.match(/\(([^)]+)\)/)
                        const code = codeMatch ? codeMatch[1] : ''
                        const name = stockName.replace(/\([^)]+\)/, '')
                        return (
                          <tr key={`${gi}-${i}`} style={{ borderBottom: '1px solid #222' }}>
                            <td style={{ padding: '3px 6px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                              {name}
                              <span style={{ color: '#555', fontSize: 10, marginLeft: 2 }}>{code}</span>
                            </td>
                            <td style={{ padding: '3px 6px', color, fontWeight: 600, whiteSpace: 'nowrap' }}>
                              {item.action}
                            </td>
                            <td style={{ padding: '3px 6px', color: '#666', fontSize: 10, whiteSpace: 'nowrap' }}>
                              {secGroup.sector !== '未分类' ? secGroup.sector : ''}
                            </td>
                            <td style={{ padding: '3px 6px', color: '#888', fontSize: 10 }}>
                              {item.reason}
                            </td>
                            <td style={{ padding: '3px 6px', textAlign: 'center', color, fontSize: 10 }}>
                              {item.priority}
                            </td>
                          </tr>
                        )
                      })
                    ))}
                  </tbody>
                </table>
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
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr style={{ color: '#555', fontSize: 10 }}>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>个股</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>买点</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>涨跌</th>
                      <th style={{ textAlign: 'left', padding: '2px 6px', borderBottom: '1px solid #333' }}>止损</th>
                      <th style={{ textAlign: 'center', padding: '2px 6px', borderBottom: '1px solid #333' }}>标签</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((s, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '3px 6px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                          {s.name}
                          {s.sector && <span style={{ color: '#555', fontSize: 10, marginLeft: 2 }}>·{s.sector}</span>}
                        </td>
                        <td style={{ padding: '3px 6px', color: '#aaa', fontSize: 10, whiteSpace: 'nowrap' }}>
                          {s.buy_point}
                        </td>
                        <td style={{ padding: '3px 6px', color: (s.change || 0) >= 0 ? '#ff4444' : '#44aa44', whiteSpace: 'nowrap' }}>
                          {(s.change || 0) >= 0 ? '+' : ''}{s.change}%
                        </td>
                        <td style={{ padding: '3px 6px', color: '#ff9800', fontSize: 10, whiteSpace: 'nowrap' }}>
                          {s.stop_loss != null ? `${s.stop_loss}${s.stop_loss_pct != null ? `(${s.stop_loss_pct}%)` : ''}` : ''}
                        </td>
                        <td style={{ padding: '3px 6px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                          {s.is_main && <span className="tag red" style={{ fontSize: 9 }}>主线</span>}
                          {s.profit_model1 && <span className="tag" style={{ background: '#e94560', fontSize: 9, padding: '1px 4px' }}>🏆</span>}
                          {s.trend_stock && <span className="tag" style={{ background: '#2196f3', fontSize: 9, padding: '1px 4px' }}>📈</span>}
                          {(opp === '其他') && (s as any).opp_reason && (
                            <span style={{ color: '#555', fontSize: 9 }}>{(s as any).opp_reason}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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

/** 按机会类型→行业分组持仓操作 */
function groupedHoldingsAction(items: NonNullable<NonNullable<Props['plan']>['holdings_action']>) {
  // 先按 opp 分组
  const oppGroups: Record<string, { sector: string; items: typeof items }[]> = {}
  for (const item of items) {
    let opp = (item as any).opportunity || '--'
    if (opp === '--') opp = '其他'
    const sec = (item as any).sector || '未分类'
    if (!oppGroups[opp]) oppGroups[opp] = []
    let secGroup = oppGroups[opp].find(g => g.sector === sec)
    if (!secGroup) {
      secGroup = { sector: sec, items: [] }
      oppGroups[opp].push(secGroup)
    }
    secGroup.items.push(item)
  }
  const OPP_ORDER: Record<string, number> = {
    '主线回调': 0, '次线机会': 1, '波谷观察': 2,
    '趋势延续': 3, '回调中': 4, '见顶风险': 5,
    '主线观察': 6, '次级观察': 7, '其他': 99,
  }
  return Object.entries(oppGroups).sort(([a], [b]) => {
    const oa = OPP_ORDER[a] ?? 99
    const ob = OPP_ORDER[b] ?? 99
    return oa - ob
  })
}

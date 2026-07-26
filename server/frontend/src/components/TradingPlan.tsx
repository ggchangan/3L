import { useState } from 'react'
import type { ReviewData } from '../lib/types'
import { formatSectorEnvironment } from '../lib/review'
import { buyDecisionAction } from '../lib/buyDecision'

interface Props {
  plan: ReviewData['trading_plan']
}

const PRI_COLORS: Record<string, string> = { '高': '#e94560', '中': '#ffd700', '低': '#888' }

const DIRECTION_CFG: Record<string, { emoji: string; color: string; order: number }> = {
  '主线': { emoji: '🔥', color: '#e94560', order: 0 },
  '次级主线': { emoji: '⚡', color: '#ffd700', order: 1 },
  '其他方向': { emoji: '📊', color: '#888', order: 2 },
}
const DIRECTION_ORDER: Record<string, number> = {}
Object.entries(DIRECTION_CFG).forEach(([k, v]) => { DIRECTION_ORDER[k] = v.order })

function directionGroup(item: any) {
  return item.mainline_level === '主线' || item.mainline_level === '次级主线'
    ? item.mainline_level
    : '其他方向'
}

export default function TradingPlan({ plan }: Props) {
  const [showOrdinary, setShowOrdinary] = useState(false)
  if (!plan) return <div className="empty">暂无交易计划</div>
  const buyItems = plan.buy_priority || []
  const hasLegacyTierItems = buyItems.some(item => !item.attention_tier)
  // 旧缓存没有分层字段，必须保守归为普通信号，不能把历史 executable
  // 直接升级成“重点关注”。
  const tierOf = (item: any) => item.attention_tier || 'ordinary'
  const focusItems = buyItems.filter(item => tierOf(item) === 'focus')
  const watchItems = buyItems.filter(item => tierOf(item) === 'watch')
  const ordinaryItems = buyItems.filter(item => tierOf(item) === 'ordinary')
  const summary = plan.buy_summary || {
    total: buyItems.length,
    focus: focusItems.length,
    watch: watchItems.length,
    ordinary: ordinaryItems.length,
    market_regime: undefined,
    conclusion: focusItems.length ? `优先跟踪 ${focusItems.length} 个重点买点。` : '当前暂无一级重点买点。',
    ranking_rule: '市场过滤 → 主线/强动量 → 个股买点质量 → 板块环境 → 止损风险',
  }
  const marketStrategy = plan.market_strategy

  return (
    <div className="plan-card" style={{ overflowX: 'auto' }}>
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
      {marketStrategy && (
        <div style={{ marginBottom: 12, padding: '9px 10px', border: '1px solid #333', borderRadius: 6, fontSize: 12 }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
            <strong style={{ color: '#ddd' }}>{marketStrategy.environment_label}</strong>
            <span style={{ color: marketStrategy.risk_phase === 'main_decline' ? '#e94560' : '#ffd700' }}>风险：{marketStrategy.risk_label}</span>
            <span style={{ color: '#aaa' }}>波段：{marketStrategy.wave_label}</span>
            <span style={{ color: '#aaa' }}>可执行重点买点：{marketStrategy.executable_buy_count}</span>
          </div>
          <div style={{ color: '#aaa', lineHeight: 1.7 }}>
            <div>买点偏好：{marketStrategy.allowed_buy_points.join('、')}</div>
            <div>交易节奏：{marketStrategy.holding_style}；{marketStrategy.exit_style}</div>
          </div>
        </div>
      )}

      {/* 个股操作 */}
      <UnifiedTable
        title="📦 个股操作"
        items={plan.holdings_action}
        groupKey={directionGroup}
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
        renderExtra={item => null}
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

      {/* 买点先分交易关注层级，普通技术信号默认折叠。 */}
      {buyItems.length > 0 && (
        <div style={{ marginTop: 14, padding: '10px 12px', border: '1px solid #333', borderRadius: 8, background: 'rgba(255,255,255,0.025)' }}>
          <div style={{ color: '#ddd', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
            🎯 今日买点重点
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: 12, marginBottom: 6 }}>
            <span style={{ color: '#e94560' }}>重点 {summary.focus}</span>
            <span style={{ color: '#ffd700' }}>次级观察 {summary.watch}</span>
            <span style={{ color: '#888' }}>普通信号 {summary.ordinary}</span>
            <span style={{ color: '#666' }}>共 {summary.total}</span>
          </div>
          <div style={{ color: summary.market_regime === 'weak' ? '#ff9800' : '#4ecdc4', fontSize: 12 }}>
            {summary.conclusion}
          </div>
          {hasLegacyTierItems && (
            <div style={{ color: '#ff9800', fontSize: 10, marginTop: 5 }}>
              历史缓存未按当前规则重新分层，动量名次仅供参考。
            </div>
          )}
          <div style={{ color: '#666', fontSize: 10, marginTop: 5 }}>排序：{summary.ranking_rule}</div>
          <details style={{ marginTop: 7, color: '#888', fontSize: 11 }}>
            <summary style={{ cursor: 'pointer', color: '#58a6ff' }}>指标说明：如何理解动量与质量？</summary>
            <div style={{ marginTop: 6, lineHeight: 1.7 }}>
              <div>
                <strong style={{ color: '#aaa' }}>动量排名</strong>：对应行业或概念在当日板块动量榜中的位置。
                名次越靠前，说明该方向近期量价表现越强；前20进入重点条件，21–50进入次级观察。
              </div>
              <div>
                <strong style={{ color: '#aaa' }}>质量分</strong>：0–100 的个股买点确认强度，由3L买点等级或多信号融合置信度换算。
                对可计算质量分的3L/融合信号，60分是进入重点/次级的最低条件；趋势买点当前不计算质量分，按已命中买点参与方向分层。
                它不是上涨概率，也不能替代大盘和主线判断。
              </div>
            </div>
          </details>
        </div>
      )}

      {focusItems.length > 0
        ? <BuyActionTable title={`🔥 重点关注 (${focusItems.length})`} items={focusItems} />
        : buyItems.length > 0 && <div className="empty" style={{ marginTop: 10 }}>🔥 今日暂无主线/强动量重点买点</div>}
      {watchItems.length > 0 && <BuyActionTable title={`👀 次级观察 (${watchItems.length})`} items={watchItems} />}
      {ordinaryItems.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <button
            type="button"
            onClick={() => setShowOrdinary(value => !value)}
            style={{ cursor: 'pointer', border: '1px solid #333', borderRadius: 6, background: '#181824', color: '#888', padding: '5px 10px', fontSize: 11 }}
          >
            {showOrdinary ? '收起' : '展开'}普通技术信号 ({ordinaryItems.length})
          </button>
          {showOrdinary && <BuyActionTable title={`📋 普通信号 (${ordinaryItems.length})`} items={ordinaryItems} />}
        </div>
      )}

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

function BuyActionTable({ title, items }: { title: string; items: any[] }) {
  return (
    <UnifiedTable
      title={title}
      items={items}
      groupKey={directionGroup}
      renderAction={item => {
        const action = buyDecisionAction(item, 'signal')
        const color = action === '待确认' ? '#ffd700' : PRI_COLORS[item.priority] || '#22c55e'
        return <span style={{ color, fontWeight: 600 }}>{action}</span>
      }}
      renderSignal={item => {
        const sigs = item.triggered_signals || []
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <span style={{ color: '#aaa', fontSize: 10 }}>{item.signal || item.buy_point || ''}</span>
            {sigs.slice(0, 2).map((s: any, i: number) => (
              <span key={i} style={{fontSize:9,color:s.direction === 'bullish' ? '#4ecdc4' : s.direction === 'bearish' ? '#e94560' : '#ffd700',background:'rgba(255,255,255,0.05)',padding:'1px 4px',borderRadius:3}}>{s.name}</span>
            ))}
          </div>
        )
      }}
      renderExtra={() => null}
      rightCol={item => {
        const chg = item.change || 0
        const momentumPercent = item.momentum_total && item.momentum_rank
          ? Math.max(1, Math.ceil(item.momentum_rank / item.momentum_total * 100))
          : null
        const momentumText = item.momentum_rank && item.momentum_rank < 10000
          ? `动量第${item.momentum_rank}${item.momentum_total ? `/${item.momentum_total}` : ''}${momentumPercent ? `（前${momentumPercent}%）` : ''}`
          : ''
        const momentumHelp = [
          item.momentum_source ? `${item.momentum_source}动量榜` : '板块动量榜',
          item.momentum_direction ? `匹配方向：${item.momentum_direction}` : '',
          item.momentum_total ? `共${item.momentum_total}个方向` : '',
          '名次越靠前代表近期量价动量越强；前20为重点条件，21–50为次级观察。',
        ].filter(Boolean).join('；')
        const qualityText = item.quality_score != null ? Math.round(item.quality_score) : null
        const qualityHelp = [
          '质量分表示个股买点确认强度，不是上涨概率',
          item.quality_basis ? `来源：${item.quality_basis}` : '',
          '满分100；对可计算质量分的3L/融合信号，60分为进入重点/次级的最低条件',
        ].filter(Boolean).join('；')
        return <>
          <span style={{color: chg >= 0 ? '#ff4444' : '#44aa44', fontSize: 11, marginRight: 6}}>{chg >= 0 ? '+' : ''}{chg}%</span>
          {item.is_main && <span className="tag red" style={{fontSize:9}}>主线</span>}
          {momentumText && (
            <span title={momentumHelp} style={{ color: '#58a6ff', fontSize: 9, marginLeft: 4, cursor: 'help' }}>
              {momentumText}
            </span>
          )}
          {qualityText != null && (
            <span title={qualityHelp} style={{ color: '#aaa', fontSize: 9, marginLeft: 4, cursor: 'help' }}>
              质量{qualityText}/100
            </span>
          )}
        </>
      }}
    />
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
  const sorted = Object.entries(groups).sort(([a], [b]) => (DIRECTION_ORDER[a] ?? 99) - (DIRECTION_ORDER[b] ?? 99))

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ marginBottom: 6 }}><strong style={{ color: '#4ecdc4', fontSize: 13 }}>{title}</strong></div>
      {sorted.map(([direction, rows]) => {
        const cfg = DIRECTION_CFG[direction] || { emoji: '📋', color: '#888', order: 99 }
        return (
          <div key={direction} style={{ marginBottom: 8 }}>
            <div style={{ color: cfg.color, fontSize: 11, fontWeight: 600, marginBottom: 3 }}>
              {cfg.emoji} {direction} ({rows.length})
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <colgroup>
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: 'auto' }} />
                <col style={{ width: '40%' }} />
                <col style={{ width: 'auto' }} />
              </colgroup>
              <thead>
                <tr style={{ color: '#555', fontSize: 10 }}>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>个股</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>操作</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>信号</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>止损</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>板块环境</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px', borderBottom: '1px solid #333' }}>条件与依据</th>
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
                    <td style={{ padding: '3px 4px', whiteSpace: 'nowrap', color: '#777', fontSize: 10 }}>
                      {item.sector || ''}{item.opportunity && item.opportunity !== '--' ? ` · ${formatSectorEnvironment(item.opportunity, item.mainline_level)}` : ''}
                    </td>
                    <td style={{ padding: '3px 4px', color: '#888', fontSize: 10, wordBreak: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal', minWidth: 80 }}>
                      {item.trigger_condition && (
                        <div style={{ marginBottom: 3, lineHeight: 1.5 }}>
                          <div style={{ color: '#4ecdc4' }}>如果：{item.trigger_condition}</div>
                          {item.action_when_triggered && <div style={{ color: '#ddd' }}>那么：{item.action_when_triggered}</div>}
                          {item.invalidation_condition && <div style={{ color: '#ff9800' }}>失效：{item.invalidation_condition}</div>}
                          {item.stop_condition && <div style={{ color: item.plan_readiness === 'needs_stop' ? '#e94560' : '#888' }}>止损：{item.stop_condition}</div>}
                          {item.valid_for && <div style={{ color: '#666' }}>有效：{item.valid_for}</div>}
                        </div>
                      )}
                      {item.attention_reason && <div style={{ color: '#bbb' }}>{item.attention_reason}</div>}
                      {item.reason && <div>{item.reason}</div>}
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

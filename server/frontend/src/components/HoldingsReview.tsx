import { useState } from 'react'
import StockCard from './StockCard'
import type { BuySignalItem, HoldingsRiskExposure } from '../lib/types'

const DIR_COLORS: Record<string, string> = {
  '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
  '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
  'AI应用': '#00BCD4', '商业航天': '#FF5722', '先进封装': '#FF6B6B',
  'PCB概念': '#FFD93D',
}

const displayNumber = (value: number | null | undefined, digits = 2, suffix = '') => (
  value != null && Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)}${suffix}` : '--'
)

export function RiskExposurePanel({ exposure }: { exposure?: HoldingsRiskExposure }) {
  if (!exposure) return null
  const topDirection = exposure.direction_concentration?.[0]
  const hasWarning = exposure.status === 'partial'
    || exposure.breached_stop_codes.length > 0
    || exposure.uncovered_position_pct > 0
    || exposure.unassessable_position_pct > 0
    || exposure.stop_warnings.length > 0
  return (
    <section className={`holdings-risk-exposure ${hasWarning ? 'warning' : ''}`} aria-label="持仓风险暴露">
      <div className="holdings-risk-header">
        <div><span>持仓真实风险暴露</span><strong>{exposure.status === 'confirmed' ? '已确认' : '部分数据'}</strong></div>
        <span>按记录仓位</span>
      </div>
      <div className="holdings-risk-metrics">
        <div><span>总仓位 / 现金</span><strong>{displayNumber(exposure.total_position_pct, 1, '%')} / {displayNumber(exposure.cash_pct, 1, '%')}</strong></div>
        <div><span>到止损组合最大回撤</span><strong>{displayNumber(exposure.portfolio_downside_to_stops_pct, 2, '%')}</strong><small>占总资产</small></div>
        <div><span>有效止损覆盖仓位</span><strong>{displayNumber(exposure.stop_covered_position_pct, 1, '%')}</strong><small>未设 {displayNumber(exposure.uncovered_position_pct, 1, '%')} · 无价格 {displayNumber(exposure.unassessable_position_pct, 1, '%')}</small></div>
        <div><span>已触发止损仓位</span><strong>{displayNumber(exposure.breached_position_pct, 1, '%')}</strong><small>需执行既定计划</small></div>
      </div>
      <div className="holdings-risk-concentration">
        <span>最大单股：{exposure.largest_position ? `${exposure.largest_position.name} ${displayNumber(exposure.largest_position.position_pct, 1, '%')}` : '--'}</span>
        <span>最大方向：{topDirection ? `${topDirection.name} ${displayNumber(topDirection.position_pct, 1, '%')}` : '--'}</span>
      </div>
      {exposure.breached_stop_codes.length > 0 && <div className="holdings-risk-alert">已跌破止损：{exposure.breached_stop_codes.join('、')}</div>}
      {exposure.stop_warnings?.length > 0 && <div className="holdings-risk-missing">止损记录告警：{exposure.stop_warnings.map(item => `${item.name || item.code}·${item.message}`).join('；')}</div>}
      {exposure.missing.length > 0 && <div className="holdings-risk-missing">数据缺口：{exposure.missing.join('；')}</div>}
      <details className="holdings-risk-details">
        <summary>查看单股风险与计算口径</summary>
        <div className="holdings-risk-table">
          {exposure.items.map(item => (
            <div key={item.code} className={item.stop_status === 'breached' ? 'breached' : ''}>
              <strong>{item.name}({item.code})</strong>
              <span>仓位 {displayNumber(item.position_pct, 1, '%')}</span>
              <span>距止损 {displayNumber(item.downside_to_stop_pct, 1, '%')}</span>
              <span>组合风险 {displayNumber(item.portfolio_risk_pct, 2, '%')}</span>
              <span>浮盈亏 {displayNumber(item.unrealized_pnl_pct, 1, '%')}</span>
            </div>
          ))}
        </div>
        <p>{exposure.basis}</p>
      </details>
    </section>
  )
}

export default function HoldingsReview({ stocks, directionOrder: dirOrder, opportunityMap, exposure }: {
  stocks: BuySignalItem[]; directionOrder?: string[]; opportunityMap?: Record<string, string>; exposure?: HoldingsRiskExposure
}) {
  const [activeDir, setActiveDir] = useState('')
  const hasStocks = stocks.length > 0

  const groups: Record<string, BuySignalItem[]> = {}
  stocks.forEach(s => {
    const dir = s.direction || s.sector || '其他'
    if (!groups[dir]) groups[dir] = []
    groups[dir].push(s)
  })

  const dirs = Object.keys(groups)
  const order = dirOrder && dirOrder.length > 0 ? dirOrder : Object.keys(groups)
  const sortedDirs = order.filter(d => dirs.includes(d)).concat(dirs.filter(d => !order.includes(d)))
  if (hasStocks && (!activeDir || !groups[activeDir])) {
    if (!sortedDirs[0]) return null
    if (activeDir !== sortedDirs[0]) setActiveDir(sortedDirs[0])
  }

  return (
    <>
      <RiskExposurePanel exposure={exposure} />
      {!hasStocks && <div className="empty">持仓卡片暂不可用，风险数据缺口已在上方列出</div>}
      {hasStocks && <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10, borderBottom: '1px solid #333', paddingBottom: 6 }}>
        {sortedDirs.map(dir => {
          const color = DIR_COLORS[dir] || '#888'
          const isActive = dir === activeDir
          return (
            <span key={dir}
              onClick={() => setActiveDir(dir)}
              style={{
                cursor: 'pointer', padding: '4px 12px', fontSize: 12, borderRadius: 12, display: 'inline-block',
                background: isActive ? color : 'rgba(255,255,255,0.05)',
                color: isActive ? '#fff' : color,
              }}
            >{dir} ({groups[dir].length})</span>
          )
        })}
      </div>
      {(groups[activeDir] || []).map((s, i) => (
        <StockCard key={s.code + '-' + i} s={s} idx={i + 1} chartPrefix="hr_" mode="review" decisionContext="holding" opportunityMap={opportunityMap} />
      ))}
      <div style={{ marginTop: 6, textAlign: 'right', color: '#555', fontSize: 11 }}>
        共{stocks.length}只持仓
      </div>
      </>}
    </>
  )
}

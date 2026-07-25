import { useEffect, useState } from 'react'
import { fetchAllIndexData, INDEX_CODES_LIST, INDEX_CODE_NAMES } from '../lib/api'
import type { MarketStrategy } from '../lib/types'

export interface MarketData {
  price?: number | string
  change?: number
  score?: number
  position?: string
  position_pct?: string
  strategy?: string
  build_per_stock_pct?: string
  pk_score?: number
  vl_score?: number
  bias20?: number
  bias20_chg_3d?: number
  ma20?: number
  ma60?: number
  data_date?: string
  structure?: string
  market_regime?: MarketRegime
  wave_side?: 'valley' | 'peak' | 'none'
  wave_phase?: 'left' | 'forming' | 'biased' | 'confirmed' | 'none'
  wave_label?: string
  supply_demand_state?: string
  context?: Record<string, number>
  evidence?: Record<string, number>
  hard_gates?: string[]
  explanation?: string[]
  algorithm_version?: string
}

export type MarketRegime = 'strong' | 'neutral' | 'weak' | 'unknown'

export function classifyMarketRegime(structure?: string, market?: MarketData): MarketRegime {
  if (structure === '上涨趋势') return 'strong'
  if (structure === '下降趋势') return 'weak'
  if (structure === '区间震荡') return 'neutral'

  const price = Number(market?.price)
  const ma20 = Number(market?.ma20)
  const ma60 = Number(market?.ma60)
  if (![price, ma20, ma60].every(Number.isFinite) || ma20 <= 0 || ma60 <= 0) return 'unknown'
  if (price >= ma20 && ma20 >= ma60) return 'strong'
  if (price < ma20 && ma20 < ma60) return 'weak'
  return 'neutral'
}

type TabState = Record<string, { showScore: boolean; showChart: boolean }>

interface MarketCycleProps {
  mode?: 'review' | 'monitor'
  reviewMarket?: MarketData
  reviewIndexDate?: string
  marketStrategy?: MarketStrategy
}

const normalizeDate = (value?: string) => (value || '').replaceAll('-', '')

export function selectReviewIndexData(
  fetched: Record<string, MarketData>,
  reviewMarket?: MarketData,
  reviewIndexDate?: string,
  mode: 'review' | 'monitor' = 'review',
) {
  const expectedDate = normalizeDate(reviewIndexDate || reviewMarket?.data_date)
  const compatible: Record<string, MarketData> = {}
  INDEX_CODES_LIST.forEach(code => {
    const item = fetched[code]
    if (!item) return
    if (mode === 'monitor' || !expectedDate || normalizeDate(item.data_date) === expectedDate) {
      compatible[code] = item
    }
  })
  if (reviewMarket) {
    compatible['000985'] = {
      ...compatible['000985'],
      ...reviewMarket,
      data_date: reviewIndexDate || reviewMarket.data_date,
    }
  }
  return compatible
}

export function resolveActiveIndexCode(data: Record<string, MarketData>, activeCode: string) {
  if (data[activeCode]) return activeCode
  return INDEX_CODES_LIST.find(code => data[code]) || ''
}

export default function MarketCycle({ mode = 'review', reviewMarket, reviewIndexDate, marketStrategy }: MarketCycleProps) {
  const [allData, setAllData] = useState<Record<string, MarketData> | null>(null)
  const [activeTab, setActiveTab] = useState<string>('000985')
  const [tabStates, setTabStates] = useState<TabState>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchAllIndexData().then(data => {
      const fetched = data as Record<string, MarketData>
      setAllData(selectReviewIndexData(fetched, reviewMarket, reviewIndexDate, mode))
      setLoading(false)
    }).catch(() => {
      const fallback: Record<string, MarketData> = {}
      fallback['000985'] = reviewMarket || { price: '--', position: '波中', position_pct: '半仓', strategy: '中等仓位·精选个股' }
      setAllData(fallback)
      setLoading(false)
    })
  }, [mode, reviewMarket, reviewIndexDate])

  const getTabState = (code: string) => tabStates[code] || { showScore: false, showChart: false }
  const setTabState = (code: string, patch: Partial<{ showScore: boolean; showChart: boolean }>) => {
    setTabStates(prev => ({
      ...prev,
      [code]: { ...getTabState(code), ...patch }
    }))
  }

  if (loading || !allData) return <div className="empty">加载中...</div>

  const availableCodes = INDEX_CODES_LIST.filter(code => allData[code])
  const selectedCode = resolveActiveIndexCode(allData, activeTab)
  const current = allData[selectedCode]
  if (!current) return <div className="empty">暂无数据</div>

  const change = current.change || 0
  const priceClass = change >= 0 ? 'value up' : 'value down'
  const phaseText = { none: '未形成', left: '左侧观察', forming: '形成中', biased: '供需偏向', confirmed: '转折确认' }
  const scoreText = (value?: number) => typeof value === 'number' ? `${value.toFixed(0)}/100` : '--'
  const evidenceSide = current.wave_side === 'peak' || current.wave_side === 'valley' ? current.wave_side : 'none'
  const hasSupplyDemandDetails = current.algorithm_version === 'supply_demand_v3'
  const locationText = evidenceSide === 'peak' ? scoreText(current.context?.high_location)
    : evidenceSide === 'valley' ? scoreText(current.context?.low_location)
    : `低 ${scoreText(current.context?.low_location)} / 高 ${scoreText(current.context?.high_location)}`
  const exhaustionText = evidenceSide === 'peak' ? scoreText(current.evidence?.demand_exhaustion)
    : evidenceSide === 'valley' ? scoreText(current.evidence?.supply_exhaustion)
    : `供 ${scoreText(current.evidence?.supply_exhaustion)} / 需 ${scoreText(current.evidence?.demand_exhaustion)}`
  const effortResultText = evidenceSide === 'peak' ? scoreText(current.evidence?.distribution)
    : evidenceSide === 'valley' ? scoreText(current.evidence?.absorption)
    : `吸收 ${scoreText(current.evidence?.absorption)} / 派发 ${scoreText(current.evidence?.distribution)}`
  const reverseEntryText = evidenceSide === 'peak' ? scoreText(current.evidence?.supply_entry)
    : evidenceSide === 'valley' ? scoreText(current.evidence?.demand_entry)
    : `需求 ${scoreText(current.evidence?.demand_entry)} / 供应 ${scoreText(current.evidence?.supply_entry)}`

  const ts = getTabState(selectedCode)
  const primary = allData['000985'] || current
  const regime = primary.market_regime || classifyMarketRegime(primary.structure, primary)
  const hiddenIndexCount = INDEX_CODES_LIST.length - availableCodes.length
  const regimeConfig = {
    strong: {
      title: '强势市场',
      badge: '突破与中继均可，允许持股',
      detail: '优先在主线和强动量方向中选择个股买点，让有效买入和卖出自然形成仓位。',
    },
    neutral: {
      title: '震荡市场',
      badge: '控制节奏，精选个股',
      detail: '中证全指处于区间震荡。降低出手频率，优先选择强方向中的高质量个股买点。',
    },
    weak: {
      title: '弱势市场',
      badge: '提高买点要求，缩短交易周期',
      detail: '优先恐慌、供应衰竭和明确反转买点；弱势本身不设固定仓位，主跌风险才暂停新增仓位。',
    },
    unknown: {
      title: '市场强弱待确认',
      badge: '数据不足',
      detail: '当前缺少足够的趋势数据，暂不生成强弱结论，请等待数据确认。',
    },
  }[regime]

  return (
    <>
      <div className={`market-regime-banner ${regime} risk-${marketStrategy?.risk_phase || 'unknown'}`}>
        <div className="market-dimension environment">
          <div className="market-regime-label">市场环境</div>
          <div className="market-regime-title">{regimeConfig.title}</div>
        </div>
        <div className={`market-dimension risk ${marketStrategy?.risk_phase || 'unknown'}`}>
          <div className="market-regime-label">风险阶段</div>
          <div className="market-regime-title">{marketStrategy?.risk_label || '待确认'}</div>
        </div>
        <div className="market-dimension wave">
          <div className="market-regime-label">波段位置</div>
          <div className="market-regime-title">{marketStrategy?.wave_label || primary.position || '待确认'}</div>
        </div>
        <div className="market-regime-copy">
          <strong>{regimeConfig.badge}</strong>
          <span>{regimeConfig.detail}</span>
        </div>
        <div className="market-regime-meta">
          <span>趋势：{primary.structure || '--'}</span>
          <span>{marketStrategy?.current_position_pct != null ? `当前仓位：${marketStrategy.current_position_pct}%` : '当前仓位：未记录'}</span>
          {(reviewIndexDate || primary.data_date) && <span>数据：{reviewIndexDate || primary.data_date}</span>}
        </div>
      </div>

      {marketStrategy && (
        <div style={{ margin: '10px 0 12px', padding: '10px 12px', border: '1px solid #333', borderRadius: 8, background: 'rgba(78,205,196,0.05)' }}>
          <div style={{ color: marketStrategy.risk_phase === 'main_decline' ? '#e94560' : '#4ecdc4', fontWeight: 700, marginBottom: 6 }}>
            {marketStrategy.position_action}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', color: '#aaa', fontSize: 12 }}>
            <span>适用买点：{marketStrategy.allowed_buy_points.join('、')}</span>
            <span>避免：{marketStrategy.avoid_buy_points.join('、')}</span>
            <span>持股：{marketStrategy.holding_style}</span>
            <span>退出：{marketStrategy.exit_style}</span>
          </div>
        </div>
      )}

      {hiddenIndexCount > 0 && (
        <div className="market-index-date-note">
          其他 {hiddenIndexCount} 个指数缺少本次复盘交易日数据，已隐藏，避免混用当前行情。
        </div>
      )}

      {/* Tab Bar */}
      <div className="index-tab-bar">
        {availableCodes.map(code => (
          <button
            key={code}
            className={`index-tab ${selectedCode === code ? 'active' : ''}`}
            onClick={() => setActiveTab(code)}
          >
            {INDEX_CODE_NAMES[code] || code}
          </button>
        ))}
      </div>

      {/* Current Tab Content */}
      <div className="grid-4" id="marketGrid">
        <div className="info-card">
          <div className="label">{INDEX_CODE_NAMES[selectedCode] || selectedCode}</div>
          <div className={priceClass}>{current.price || '--'}</div>
          <div className="meta" id="marketChange">涨跌 {change ? `${change >= 0 ? '+' : ''}${change}%` : '--'}</div>
        </div>
        <div className="info-card">
          <div className="label">大盘周期位置</div>
          <div className="value" style={{ fontSize: 18 }}>{current.wave_label || current.position || '--'}</div>
          <div className="meta" id="cycleScore">{current.supply_demand_state || '供需待确认'}</div>
        </div>
        <div className="info-card">
          <div className="label">动态仓位</div>
          <div className="value" style={{ fontSize: 18 }}>
            {marketStrategy?.current_position_pct != null ? `${marketStrategy.current_position_pct}%` : '--'}
            {marketStrategy?.position_after_exits_pct != null && marketStrategy.planned_exit_pct ? ` → ${marketStrategy.position_after_exits_pct}%` : ''}
          </div>
          <div className="meta" id="positionRule">{marketStrategy?.planned_exit_pct ? `明确卖出 ${marketStrategy.planned_exit_pct}%` : '随有效买卖点变化'}</div>
        </div>
        <div className="info-card">
          <div className="label">仓位动作</div>
          <div className="value" style={{ fontSize: 14 }}>{marketStrategy?.position_action || current.strategy || '--'}</div>
          <div className="meta" id="strategyAdvice">不预设目标仓位</div>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <table id="scoreDetailTable" style={{ display: ts.showScore ? '' : 'none' }}>
          <thead>
            <tr><th>维度</th><th>评分</th><th>明细</th></tr>
          </thead>
          <tbody>
            <tr><td colSpan={3} style={{ fontSize: 13, color: '#4ecdc4', fontWeight: 'bold', paddingBottom: 8 }}>{current.wave_label || current.position} · {current.supply_demand_state || '供需待确认'}</td></tr>
            <tr>
              <td style={{ color: '#888', width: 80 }}>当前阶段</td>
              <td style={{ width: 120, textAlign: 'center' }}>{hasSupplyDemandDetails ? phaseText[current.wave_phase || 'none'] : '供需证据不可用'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>{hasSupplyDemandDetails ? '阶段按“位置背景 → 供需事件 → 反向力量进入”依次升级，不等同于未来涨跌预测' : '旧缓存或数据不足，刷新并补齐至少80根有效K线后查看'}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>位置背景</td>
              <td style={{ textAlign: 'center' }}>{hasSupplyDemandDetails ? locationText : '--'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>{evidenceSide === 'none' ? '当前未形成峰谷方向，同时展示低位与高位背景' : `${evidenceSide === 'peak' ? '高位' : '低位'}背景只表示所处区域，不能单独确认峰谷`}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>{evidenceSide === 'peak' ? '需求衰竭' : evidenceSide === 'valley' ? '供应衰竭' : '供需衰竭'}</td>
              <td style={{ textAlign: 'center' }}>{hasSupplyDemandDetails ? exhaustionText : '--'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>推进速度、波动与成交量收缩后，原方向的推动力是否减弱</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>{evidenceSide === 'peak' ? '派发/滞涨' : evidenceSide === 'valley' ? '吸收/滞跌' : '努力与结果'}</td>
              <td style={{ textAlign: 'center' }}>{hasSupplyDemandDetails ? effortResultText : '--'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>成交努力较大，但价格沿原方向推进效率下降</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>{evidenceSide === 'peak' ? '供应进入' : evidenceSide === 'valley' ? '需求进入' : '反向力量'}</td>
              <td style={{ textAlign: 'center' }}>{hasSupplyDemandDetails ? reverseEntryText : '--'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>反向价格推进、短期关键位收复/跌破及连续性证据</td>
            </tr>
            {current.hard_gates?.map(gate => <tr key={gate}><td style={{ color: '#e0a800' }}>未满足</td><td>—</td><td style={{ color: '#aaa', fontSize: 11 }}>{gate}</td></tr>)}
            <tr><td colSpan={3} style={{ textAlign: 'center', color: '#555', fontSize: 11, paddingTop: 6 }}>算法：{current.algorithm_version || 'legacy'}；峰谷决定交易节奏，不替代主线方向和个股买点</td></tr>
          </tbody>
        </table>
        <div style={{ marginTop: 6, textAlign: 'right' }}>
          <span style={{ cursor: 'pointer', color: '#4ecdc4', fontSize: 12 }} onClick={() => setTabState(selectedCode, { showScore: !ts.showScore })}>
            📊 {ts.showScore ? '隐藏' : '查看'}评分明细
          </span>
          <span style={{ color: '#333', margin: '0 6px' }}>|</span>
          <span style={{ cursor: 'pointer', color: '#e94560', fontSize: 12 }} onClick={() => setTabState(selectedCode, { showChart: !ts.showChart })}>
            📈 {ts.showChart ? '隐藏' : '查看'}关键点图
          </span>
        </div>
      </div>

      {ts.showChart && (
        <div style={{ marginTop: 8 }}>
          <div style={{ width: '100%', maxWidth: 750, height: 550, overflow: 'hidden', borderRadius: 8, margin: '0 auto' }}>
            <img src={`/api/index-chart?code=${selectedCode}&mode=${mode}`} alt={`${INDEX_CODE_NAMES[selectedCode]}关键点图`}
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
          </div>
        </div>
      )}

      {/* Comparison Table */}
      <IndexComparison data={allData} codes={availableCodes} />
    </>
  )
}

function IndexComparison({ data, codes }: { data: Record<string, MarketData>; codes: readonly string[] }) {
  const entries = codes.map(code => ({
    code,
    name: INDEX_CODE_NAMES[code] || code,
    ...data[code] || {},
  }))

  const changes = entries.map(e => e.change || 0)
  const maxChange = Math.max(...changes)
  const minChange = Math.min(...changes)

  // 对比结论
  const positions = entries.map(e => e.position || '波中')
  const isDivergent = new Set(positions).size > 2

  const bestIdx = changes.indexOf(maxChange)
  const worstIdx = changes.indexOf(minChange)
  const conclusion = isDivergent
    ? `${entries[bestIdx].name}领涨(+${maxChange.toFixed(1)}%)，${entries[worstIdx].name}最弱(${minChange.toFixed(1)}%)，指数走势分化，注意结构性机会，以对应指数为准指导仓位。`
    : `各指数走势协同，${entries[bestIdx].name}相对最强(+${maxChange.toFixed(1)}%)。当前大盘整体处于${entries[0].position || '波中'}阶段，方向一致，按仓位策略执行。`

  return (
    <div style={{ marginTop: 24, borderTop: '1px solid #2a2a4e', paddingTop: 16 }}>
      <div className="section-title" style={{ marginBottom: 12 }}>
        <span className="step">对比</span>
        多指对照表
      </div>
      <table className="comparison-table" style={{
        width: '100%', borderCollapse: 'collapse', fontSize: 13,
      }}>
        <thead>
          <tr style={{ background: '#1a1a30', borderBottom: '1px solid #2a2a4e' }}>
            <th style={{ padding: '8px 6px', textAlign: 'left', color: '#888' }}>指数</th>
            <th style={{ padding: '8px 6px', textAlign: 'right', color: '#888' }}>涨跌幅</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>周期位置</th>
            <th style={{ padding: '8px 6px', textAlign: 'right', color: '#888' }}>BIAS20</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>波峰分</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>波谷分</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(e => {
            const chg = e.change || 0
            const chgStr = chg >= 0 ? `+${chg.toFixed(1)}%` : `${chg.toFixed(1)}%`
            const isMax = chg === maxChange && entries.length > 1
            const isMin = chg === minChange && entries.length > 1
            return (
              <tr key={e.code} style={{ borderBottom: '1px solid #1e1e3a' }}>
                <td style={{ padding: '8px 6px', color: '#ccc' }}>{e.name}</td>
                <td style={{
                  padding: '8px 6px', textAlign: 'right',
                  color: chg >= 0 ? '#e94560' : '#4ecdc4',
                  fontWeight: isMax || isMin ? 700 : 400,
                }}>
                  {chgStr}
                  {isMax && <span style={{ fontSize: 10, color: '#e94560', marginLeft: 4 }}>↑最强</span>}
                  {isMin && <span style={{ fontSize: 10, color: '#4ecdc4', marginLeft: 4 }}>↓最弱</span>}
                </td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.position || '--'}</td>
                <td style={{ padding: '8px 6px', textAlign: 'right', color: '#aaa' }}>
                  {typeof e.bias20 === 'number' ? `${e.bias20 >= 0 ? '+' : ''}${e.bias20.toFixed(1)}%` : '--'}
                </td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.pk_score ?? 0}</td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.vl_score ?? 0}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div style={{
        marginTop: 12, padding: '10px 14px', background: '#111128',
        borderLeft: '3px solid #ffd700', borderRadius: 4, fontSize: 13, color: '#ddd', lineHeight: 1.6,
      }}>
        <strong style={{ color: '#ffd700' }}>📋 对比结论：</strong>{conclusion}
      </div>
    </div>
  )
}

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
  features?: Record<string, number | string | boolean>
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
type MarketInfoKind = 'environment' | 'risk' | 'wave'

interface MarketDimensionInfo {
  title: string
  rule: string[]
  values: Array<{ label: string; value: string }>
  conclusion: string
  blockers?: string[]
}

interface MarketCycleProps {
  mode?: 'review' | 'monitor'
  reviewMarket?: MarketData
  reviewIndexDate?: string
  marketStrategy?: MarketStrategy
}

const normalizeDate = (value?: string) => (value || '').replaceAll('-', '')
const numericText = (value: unknown, digits = 1, suffix = '') => {
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : '--'
}

export function buildMarketDimensionInfo(
  kind: MarketInfoKind,
  market: MarketData,
  strategy?: MarketStrategy,
): MarketDimensionInfo {
  const structure = market.structure || '待确认'
  const phase = market.wave_phase || 'none'
  const side = market.wave_side || 'none'
  const context = market.context || {}
  const evidence = market.evidence || {}
  const features = market.features || {}
  const isV3 = market.algorithm_version === 'supply_demand_v3'

  if (kind === 'environment') {
    const canonicalRegime = classifyMarketRegime(structure, market)
    const regimeLabel = {
      strong: '强势环境', neutral: '震荡环境', weak: '弱势环境', unknown: '环境待确认',
    }[canonicalRegime]
    return {
      title: `市场环境：${regimeLabel}`,
      rule: isV3 ? [
          '强势：收盘价 ≥ MA20 ≥ MA60，且 MA20 的5日斜率不为负。',
          '弱势：收盘价 < MA20 < MA60，且 MA20 的5日斜率不为正。',
          '其余组合归为震荡；市场环境影响买点要求和交易节奏，不直接给固定仓位。',
        ] : [
          '兼容判定强势：收盘价 ≥ MA20 ≥ MA60；弱势：收盘价 < MA20 < MA60；其余为震荡。',
          '当前快照没有 V3 斜率与供需证据，刷新或重新生成复盘后可查看完整判断。',
        ],
      values: [
        { label: '算法口径', value: isV3 ? '供需峰谷 V3' : '兼容/旧快照' },
        { label: '当前结构', value: structure },
        { label: '收盘价', value: numericText(market.price ?? features.close, 2) },
        { label: 'MA20', value: numericText(market.ma20 ?? features.ma20, 2) },
        { label: 'MA60', value: numericText(market.ma60 ?? features.ma60, 2) },
        ...(isV3 ? [{ label: 'MA20 5日斜率', value: numericText(features.ma20_slope_5d, 2, '%') }] : []),
      ],
      conclusion: canonicalRegime === 'weak'
        ? '价格与中期均线处于空头排列，当前按弱势环境提高买点要求、缩短交易周期。'
        : canonicalRegime === 'strong'
          ? '价格与中期均线处于多头排列，当前按强势环境允许突破与中继买点。'
          : canonicalRegime === 'neutral'
            ? '均线未形成同向排列，当前按震荡环境控制出手频率。'
            : '有效数据不足，暂不形成市场环境结论。',
    }
  }

  if (kind === 'risk') {
    const riskPhase = strategy?.risk_phase || 'unknown'
    const riskLabel = strategy?.risk_label || '待确认'
    return {
      title: `风险阶段：${riskLabel}`,
      rule: isV3 ? [
        '主跌风险：下降趋势 + 下降背景分 ≥ 45 + 供应进入分 ≥ 55，且尚未形成偏波谷/波谷确认。',
        '风险升高：波峰达到供需偏向/确认，或 BIAS20 > 12%。',
        '波谷修复：波谷达到供需偏向/确认；其余为常态。弱势环境本身不等于主跌。',
      ] : [
        '兼容判定主跌：下降趋势且尚未形成明确波谷；风险升高：偏波峰、pk_score ≥ 4 或 BIAS20 > 12%。',
        '兼容判定波谷修复：位置为偏波谷或 vl_score ≥ 4；其余为常态。',
        '当前快照缺少 V3 供需证据，刷新或重新生成复盘后可查看 45/55 门槛值。',
      ],
      values: isV3 ? [
        { label: '当前结构', value: structure },
        { label: '下降背景', value: `${numericText(context.decline_context)}/100（门槛45）` },
        { label: '供应进入', value: `${numericText(evidence.supply_entry)}/100（门槛55）` },
        { label: '峰谷方向 / 阶段', value: side === 'none' ? '未形成' : `${side === 'valley' ? '波谷' : '波峰'} / ${phase}` },
        { label: 'BIAS20', value: numericText(market.bias20 ?? features.bias20, 2, '%') },
      ] : [
        { label: '算法口径', value: '兼容/旧快照' },
        { label: '当前结构', value: structure },
        { label: '五档位置', value: market.position || '待确认' },
        { label: 'pk_score / vl_score', value: `${numericText(market.pk_score, 0)} / ${numericText(market.vl_score, 0)}` },
        { label: 'BIAS20', value: numericText(market.bias20, 2, '%') },
      ],
      conclusion: riskPhase === 'main_decline'
        ? '下降过程仍在且供应继续占优，当前属于主跌风险，暂停新增仓位。'
        : riskPhase === 'risk_rising'
          ? '波峰供需风险或严重正乖离成立，当前不追高并优先处理风险持仓。'
          : riskPhase === 'valley_recovery'
            ? '波谷修复证据成立，但仍只随主线/强动量中的有效个股买点增加仓位。'
            : riskPhase === 'normal'
              ? '主跌、波峰风险和波谷修复门禁均未触发，按常态跟随买卖点。'
              : '缺少同一交易日的完整风险策略快照，暂不形成风险阶段结论。',
    }
  }

  const sideLabel = side === 'valley' ? '波谷' : side === 'peak' ? '波峰' : '未形成方向'
  if (!isV3) {
    return {
      title: `波段位置：${market.wave_label || market.position || '待确认'}`,
      rule: [
        '当前为兼容或旧快照，只能展示原五档位置与 pk/vl 分数，不能还原 V3 的供需证据链。',
        '刷新或重新生成复盘后，将按“左侧 → 形成中 → 供需偏向 → 转折确认”展示完整依据。',
      ],
      values: [
        { label: '算法口径', value: '兼容/旧快照' },
        { label: '五档位置', value: market.position || '待确认' },
        { label: 'pk_score / vl_score', value: `${numericText(market.pk_score, 0)} / ${numericText(market.vl_score, 0)}` },
      ],
      conclusion: '当前缺少同日 V3 供需证据，不对旧结果补造解释。',
    }
  }
  return {
    title: `波段位置：${market.wave_label || market.position || '待确认'}`,
    rule: [
      '先识别高低位与涨跌背景，再识别供应/需求衰竭、吸收/派发，最后确认反向力量是否进入。',
      '阶段依次为：左侧观察 → 形成中 → 供需偏向 → 转折确认；不能仅凭超跌、缩量或单根反转K线跳级。',
      '波段位置只提供节奏和环境加减分，不能替代主线方向与个股量价买点。',
    ],
    values: [
      { label: '识别方向', value: sideLabel },
      { label: '低位 / 高位背景', value: `${numericText(context.low_location)}/100 / ${numericText(context.high_location)}/100` },
      { label: '供应 / 需求衰竭', value: `${numericText(evidence.supply_exhaustion)}/100 / ${numericText(evidence.demand_exhaustion)}/100` },
      { label: '吸收 / 派发', value: `${numericText(evidence.absorption)}/100 / ${numericText(evidence.distribution)}/100` },
      { label: '需求 / 供应进入', value: `${numericText(evidence.demand_entry)}/100 / ${numericText(evidence.supply_entry)}/100` },
    ],
    conclusion: market.explanation?.join('；') || '当前没有可用的供需峰谷解释。',
    blockers: market.hard_gates || [],
  }
}

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
    const mergedPrimary: MarketData = {
      ...compatible['000985'],
      ...reviewMarket,
      data_date: reviewIndexDate || reviewMarket.data_date,
    }
    // 旧复盘不能继承同日实时接口的 V3 证据，否则会把旧策略结论和新算法依据拼在一起。
    if (reviewMarket.algorithm_version !== 'supply_demand_v3') {
      const v3OnlyKeys: Array<keyof MarketData> = [
        'context', 'evidence', 'features', 'hard_gates', 'explanation',
        'wave_side', 'wave_phase', 'wave_label', 'supply_demand_state',
      ]
      v3OnlyKeys.forEach(key => {
        if (!(key in reviewMarket)) delete mergedPrimary[key]
      })
      if (!reviewMarket.algorithm_version) delete mergedPrimary.algorithm_version
    }
    compatible['000985'] = mergedPrimary
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
  const [activeInfo, setActiveInfo] = useState<MarketInfoKind | null>(null)
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
  const regime = classifyMarketRegime(primary.structure, primary)
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
  const dimensionInfo = activeInfo ? buildMarketDimensionInfo(activeInfo, primary, marketStrategy) : null

  const infoButton = (kind: MarketInfoKind, label: string) => (
    <button
      type="button"
      className={`market-info-button ${activeInfo === kind ? 'active' : ''}`}
      aria-label={`${activeInfo === kind ? '收起' : '查看'}${label}判断依据`}
      aria-expanded={activeInfo === kind}
      aria-controls="market-dimension-info"
      onClick={() => setActiveInfo(activeInfo === kind ? null : kind)}
    >i</button>
  )

  return (
    <>
      <div className={`market-regime-banner ${regime} risk-${marketStrategy?.risk_phase || 'unknown'}`}>
        <div className="market-dimension environment">
          <div className="market-regime-label">市场环境 {infoButton('environment', '市场环境')}</div>
          <div className="market-regime-title">{regimeConfig.title}</div>
        </div>
        <div className={`market-dimension risk ${marketStrategy?.risk_phase || 'unknown'}`}>
          <div className="market-regime-label">风险阶段 {infoButton('risk', '风险阶段')}</div>
          <div className="market-regime-title">{marketStrategy?.risk_label || '待确认'}</div>
        </div>
        <div className="market-dimension wave">
          <div className="market-regime-label">波段位置 {infoButton('wave', '波段位置')}</div>
          <div className="market-regime-title">{marketStrategy?.wave_label || primary.position || '待确认'}</div>
        </div>
        {dimensionInfo && (
          <section id="market-dimension-info" className="market-dimension-info" role="region" aria-label={`${dimensionInfo.title}判断详情`}>
            <div className="market-dimension-info-title">{dimensionInfo.title}</div>
            <div className="market-dimension-info-grid">
              <div>
                <div className="market-dimension-info-heading">如何判断</div>
                <ol>{dimensionInfo.rule.map(item => <li key={item}>{item}</li>)}</ol>
              </div>
              <div>
                <div className="market-dimension-info-heading">本次判断值</div>
                <dl>{dimensionInfo.values.map(item => (
                  <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
                ))}</dl>
              </div>
            </div>
            <div className="market-dimension-info-conclusion"><strong>本次结论：</strong>{dimensionInfo.conclusion}</div>
            {!!dimensionInfo.blockers?.length && (
              <div className="market-dimension-info-blockers"><strong>尚未满足：</strong>{dimensionInfo.blockers.join('；')}</div>
            )}
          </section>
        )}
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

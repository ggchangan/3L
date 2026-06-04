import { useEffect, useState, useCallback, useMemo } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './ConceptWaveTracking.css'

/* ═══════════════════════ Types ═══════════════════════ */

interface KLineData {
  date: string       // 'YYYY-MM-DD'
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface ChartAnnotation {
  idx: number        // index in klines array
  type: 'peak' | 'trough' | 'shrink' | 'surge' | 'overheat'
  label: string
  price: number
}

interface WavePoint {
  date: string
  normalized: number
  change_pct: number
  volume_ratio: number
}

interface Annotation {
  date: string
  type: string
  score: number
  label: string
}

interface ReasoningChain {
  market: {
    position: string
    position_pct: string
    volume_level: string
    volume_amount: string
    top_mainlines: { name: string; rank: number; days: number }[]
  }
  concept_analysis: {
    reason: string
  }
  stock_signals: {
    code: string
    name: string
    signal: string
    buy_type: string
    reason: string
  }[]
}

interface ConceptItem {
  code: string
  name: string
  stage: string
  vl_score: number
  pk_score: number
  bias20: number
  change_5d: number
  change_1d: number
  volume_ratio: number
  mainline_rank: number | null
  mainline_badge: string | null
  volume_signal: string | null
  entry_window: boolean
  vs_market_5d: number
  related_stocks: string[]
  related_count: number
  stock_count: number
  wave_data: WavePoint[]
  annotations: Annotation[]
  reasoning_chain?: ReasoningChain
  klines: KLineData[]
  chart_annotations: ChartAnnotation[]
}

interface AlertItem {
  code: string
  name: string
  vl_score: number
  reason: string
  date: string
}

interface NewHotItem {
  code: string
  name: string
  gain_20d: number
  stock_count: number
}

interface WaveStats {
  total: number
  valley: number
  peak: number
  rise: number
  decline: number
  mid: number
  alerts_count: number
  new_this_week: number
}

interface WaveData {
  success: boolean
  date: string
  data_timestamp: string
  stats: WaveStats
  grouped: {
    valley: ConceptItem[]
    peak: ConceptItem[]
    rise: ConceptItem[]
    decline: ConceptItem[]
    mid: ConceptItem[]
  }
  alerts: AlertItem[]
  new_hot: NewHotItem[]
  index_klines: KLineData[]
  untracked_stocks?: string[]
  untracked_concepts?: { name: string; stock_count: number; stocks: string[] }[]
}

/* ═══════════════════════ Direction types ═══════════════════════ */

interface DirCategory {
  name: string
  enabled: boolean
  sub_count: number
  order: number
}

interface SubDirectionInfo {
  category: string
  enabled: boolean
  concepts: Array<{ code: string; name: string }>
}

interface DirectionData {
  categories?: DirCategory[]
  sub_directions?: Record<string, SubDirectionInfo>
  active?: string[]
  version?: number
}

const STAGE_PROB: Record<string, string> = {
  '波谷': '77.3%',
  '波峰': '61.3%',
  '上涨': '59.8%',
  '下跌': '40.5%',
  '波中': '',
};

const STAGE_META: Record<string, { label: string; color: string; bg: string; tag: string }> = {
  '波谷': { label: '重点关注 · 波谷阶段', color: '#34d399', bg: '#0b2e1a', tag: 'tag-green' },
  '波峰': { label: '警惕观望 · 波峰阶段', color: '#f97316', bg: '#2a1500', tag: 'tag-orange' },
  '上涨': { label: '趋势延续 · 上涨阶段', color: '#60a5fa', bg: '#0a1a2e', tag: 'tag-blue' },
  '下跌': { label: '筑底过程 · 或有反弹机会', color: '#ef4444', bg: '#2a0b0b', tag: 'tag-red' },
  '波中': { label: '正常观察 · 波中阶段', color: '#fbbf24', bg: '#2a2000', tag: 'tag-yellow' },
}

const CHART_COLORS = [
  '#34d399', '#60a5fa', '#f472b6', '#fbbf24', '#a78bfa',
  '#fb923c', '#22d3ee', '#f87171', '#4ade80', '#c084fc',
  '#facc15', '#38bdf8', '#fb7185', '#a3e635', '#e879f9',
]

/* ═══════════════════════ Helpers ═══════════════════════ */

function fmtPct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function calcEMA(data: number[], period: number): (number | null)[] {
  if (data.length === 0) return []
  const result: (number | null)[] = []
  const k = 2 / (period + 1)
  // SMA as initial EMA
  let ema = data.slice(0, period).reduce((a, b) => a + b, 0) / period
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else if (i === period - 1) {
      result.push(ema)
    } else {
      ema = (data[i] - ema) * k + ema
      result.push(ema)
    }
  }
  return result
}

/* ═══════════════════════ LocalStorage Keys ═══════════════════════ */

const FAVS_KEY = 'concept_wave_favs'
const HIDDEN_CONCEPTS_KEY = 'concept_wave_hidden'

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch { return new Set() }
}

function saveSet(key: string, set: Set<string>) {
  localStorage.setItem(key, JSON.stringify([...set]))
}

/* ═══════════════════════ K-line Chart Renderer ═══════════════════════ */

function renderKLineSVG(
  klines: KLineData[],
  annotations: ChartAnnotation[],
  fullKlines: KLineData[],
) {
  if (klines.length === 0) {
    return <text x="300" y="100" textAnchor="middle" fill="#555" fontSize="12">暂无K线数据</text>
  }

  const n = klines.length
  // Layout: left margin for Y-axis, right margin, top margin, bottom margin for X-axis + volume
  const marginL = 48
  const marginR = 8
  const marginT = 10
  const chartB = 148 // bottom of price chart area
  const volumeB = 192 // bottom of volume area
  const marginB = 196 // bottom of x-axis text

  const chartW = 600 - marginL - marginR // usable width for candles
  const chartH = chartB - marginT // height of price chart area
  const volumeH = volumeB - chartB // height of volume area

  // Price range
  let minPrice = Infinity
  let maxPrice = -Infinity
  let maxVolume = 0
  for (const k of klines) {
    if (k.low < minPrice) minPrice = k.low
    if (k.high > maxPrice) maxPrice = k.high
    if (k.volume > maxVolume) maxVolume = k.volume
  }
  const pricePadding = (maxPrice - minPrice) * 0.05 || 1
  minPrice -= pricePadding
  maxPrice += pricePadding
  const priceRange = maxPrice - minPrice || 1

  const priceToY = (p: number) => marginT + chartH - ((p - minPrice) / priceRange) * chartH
  const volumeToH = (v: number) => maxVolume > 0 ? (v / maxVolume) * volumeH : 0

  const slotW = chartW / n
  const candleW = Math.min(slotW * 0.6, 6) // max 6px wide

  // Calculate EMAs
  const closes = klines.map(k => k.close)
  const ema5 = calcEMA(closes, 5)
  const ema10 = calcEMA(closes, 10)
  const ema20 = calcEMA(closes, 20)

  // Build polyline points for EMAs (skip nulls)
  function emaPolyline(ema: (number | null)[]): string | null {
    const pts: string[] = []
    for (let i = 0; i < ema.length; i++) {
      if (ema[i] !== null) {
        const cx = marginL + i * slotW + slotW / 2
        pts.push(`${cx.toFixed(1)},${priceToY(ema[i]!).toFixed(1)}`)
      }
    }
    return pts.length >= 2 ? pts.join(' ') : null
  }

  const ema5Pts = emaPolyline(ema5)
  const ema10Pts = emaPolyline(ema10)
  const ema20Pts = emaPolyline(ema20)

  // Y-axis ticks: 4 labels
  const yTicks = 4
  const yTickLabels: { y: number; label: string }[] = []
  for (let i = 0; i <= yTicks; i++) {
    const price = maxPrice - (priceRange * i) / yTicks
    yTickLabels.push({ y: priceToY(price), label: price.toFixed(1) })
  }

  // X-axis labels: 6 evenly spaced
  const xLabelCount = Math.min(6, n)
  const xStep = Math.max(1, Math.floor(n / xLabelCount))
  const xLabels: { x: number; label: string }[] = []
  for (let i = 0; i < n; i += xStep) {
    xLabels.push({
      x: marginL + i * slotW + slotW / 2,
      label: klines[i].date.slice(5), // MM-DD
    })
  }
  // Always include last date
  if (xLabels.length === 0 || xLabels[xLabels.length - 1].label !== klines[n - 1].date.slice(5)) {
    xLabels.push({
      x: marginL + (n - 1) * slotW + slotW / 2,
      label: klines[n - 1].date.slice(5),
    })
  }

  // Build annotation markers
  const origIdxLookup = new Map<string, number>()
  fullKlines.forEach((k, i) => origIdxLookup.set(k.date, i))
  const annMarkers: React.ReactNode[] = []
  const annLabels: React.ReactNode[] = []

  for (const ann of annotations) {
    // Find the original kline date from the index
    if (ann.idx < 0 || ann.idx >= fullKlines.length) continue
    const origDate = fullKlines[ann.idx].date
    // Find this date in the filtered klines
    const fi = klines.findIndex(k => k.date === origDate)
    if (fi < 0) continue

    const cx = marginL + fi * slotW + slotW / 2
    const cy = priceToY(ann.price)

    if (ann.type === 'trough') {
      // Green dot with V marker
      annMarkers.push(
        <g key={`ann-${ann.idx}-marker`}>
          <circle cx={cx} cy={cy} r="4" fill="none" stroke="#34d399" strokeWidth="2" />
          <circle cx={cx} cy={cy} r="2" fill="#34d399" />
          <path d={`M${cx - 5},${cy + 4} L${cx},${cy + 10} L${cx + 5},${cy + 4}`}
            fill="none" stroke="#34d399" strokeWidth="1.5" />
        </g>
      )
      annLabels.push(
        <text key={`ann-${ann.idx}-label`} x={cx} y={cy - 8} textAnchor="middle"
          fill="#34d399" fontSize="9" fontWeight="600">
          {ann.label}
        </text>
      )
    } else if (ann.type === 'peak') {
      // Red dot with Λ marker
      annMarkers.push(
        <g key={`ann-${ann.idx}-marker`}>
          <circle cx={cx} cy={cy} r="4" fill="none" stroke="#ef4444" strokeWidth="2" />
          <circle cx={cx} cy={cy} r="2" fill="#ef4444" />
          <path d={`M${cx - 5},${cy - 4} L${cx},${cy - 10} L${cx + 5},${cy - 4}`}
            fill="none" stroke="#ef4444" strokeWidth="1.5" />
        </g>
      )
      annLabels.push(
        <text key={`ann-${ann.idx}-label`} x={cx} y={cy + 14} textAnchor="middle"
          fill="#ef4444" fontSize="9" fontWeight="600">
          {ann.label}
        </text>
      )
    } else if (ann.type === 'shrink') {
      annLabels.push(
        <text key={`ann-${ann.idx}-label`} x={cx} y={cy + 14} textAnchor="middle"
          fill="#60a5fa" fontSize="10">
          💧{ann.label}
        </text>
      )
    } else if (ann.type === 'surge') {
      annLabels.push(
        <text key={`ann-${ann.idx}-label`} x={cx} y={cy + 14} textAnchor="middle"
          fill="#ff6b6b" fontSize="10">
          🔥{ann.label}
        </text>
      )
    } else if (ann.type === 'overheat') {
      annLabels.push(
        <text key={`ann-${ann.idx}-label`} x={cx} y={cy - 8} textAnchor="middle"
          fill="#fbbf24" fontSize="10" fontWeight="600">
          ⚠️{ann.label}
        </text>
      )
    }
  }

  // "今天" vertical line at last candle
  const lastX = marginL + (n - 1) * slotW + slotW / 2

  return (
    <>
      {/* Grid lines */}
      {yTickLabels.map((t, i) => (
        <line key={`grid-${i}`} x1={marginL} y1={t.y} x2={600 - marginR} y2={t.y}
          stroke="#2a2b3d" strokeWidth="1" strokeDasharray="3,3" />
      ))}
      {/* Y-axis labels */}
      {yTickLabels.map((t, i) => (
        <text key={`ytick-${i}`} x={marginL - 4} y={t.y + 3} textAnchor="end"
          fill="#7a7b92" fontSize="9">
          {t.label}
        </text>
      ))}
      {/* X-axis labels */}
      {xLabels.map((xl, i) => (
        <text key={`xtick-${i}`} x={xl.x} y={marginB} textAnchor="middle"
          fill="#7a7b92" fontSize="9">
          {xl.label}
        </text>
      ))}
      {/* Candles */}
      {klines.map((k, i) => {
        const cx = marginL + i * slotW + slotW / 2
        const isUp = k.close >= k.open
        const bodyTop = priceToY(Math.max(k.open, k.close))
        const bodyBot = priceToY(Math.min(k.open, k.close))
        const bodyH = Math.max(bodyBot - bodyTop, 1)
        const wickTop = priceToY(k.high)
        const wickBot = priceToY(k.low)
        const color = isUp ? '#ff4444' : '#44aa44'
        const halfW = Math.max(candleW / 2, 1)

        // Volume bar
        const vh = volumeToH(k.volume)
        const volColor = isUp ? 'rgba(255,68,68,0.35)' : 'rgba(68,170,68,0.35)'

        return (
          <g key={i}>
            {/* Volume */}
            <rect x={cx - halfW} y={volumeB - vh} width={candleW} height={vh}
              fill={volColor} />
            {/* Wick */}
            <line x1={cx} y1={wickTop} x2={cx} y2={wickBot} stroke={color} strokeWidth="1" />
            {/* Body */}
            <rect x={cx - halfW} y={bodyTop} width={candleW} height={bodyH}
              fill={color} stroke={color} strokeWidth="0.5" />
          </g>
        )
      })}
      {/* EMA lines */}
      {ema5Pts && (
        <polyline points={ema5Pts} fill="none" stroke="#ffd700" strokeWidth="1.5" opacity="0.9" />
      )}
      {ema10Pts && (
        <polyline points={ema10Pts} fill="none" stroke="#ff6b6b" strokeWidth="1.5" opacity="0.9" />
      )}
      {ema20Pts && (
        <polyline points={ema20Pts} fill="none" stroke="#4ecdc4" strokeWidth="1.5" opacity="0.9" />
      )}
      {/* Annotation markers */}
      {annMarkers}
      {annLabels}
      {/* "今天" vertical line */}
      <line x1={lastX} y1={marginT} x2={lastX} y2={volumeB}
        stroke="#ef4444" strokeWidth="1" strokeDasharray="3,3" opacity="0.6" />
      <text x={lastX} y={marginT - 2} textAnchor="middle" fill="#ef4444" fontSize="9" fontWeight="600">
        今天
      </text>
    </>
  )
}

/* ═══════════════════════ Main Component ═══════════════════════ */

export default function ConceptWaveTracking() {
  const [data, setData] = useState<WaveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [favs, setFavs] = useState<Set<string>>(loadSet(FAVS_KEY))
  const [hiddenCodes, setHiddenCodes] = useState<Set<string>>(loadSet(HIDDEN_CONCEPTS_KEY))
  const [showHidden, setShowHidden] = useState(false)
  const [showAllStocks, setShowAllStocks] = useState<Record<string, boolean>>({})

  // Direction-based view state
  const [dirData, setDirData] = useState<DirectionData | null>(null)
  const [activeTab, setActiveTab] = useState('全部')

  // Date range state
  const [startDate, setStartDate] = useState(daysAgo(60))
  const [endDate, setEndDate] = useState(todayStr())

  const minDate = daysAgo(60)
  const maxDate = todayStr()

  // Persist favs and hiddenCodes
  useEffect(() => { saveSet(FAVS_KEY, favs) }, [favs])
  useEffect(() => { saveSet(HIDDEN_CONCEPTS_KEY, hiddenCodes) }, [hiddenCodes])

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      fetch('/api/concept-wave')
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }),
      fetch('/api/directions/get')
        .then(r => r.json())
        .catch(() => null), // directions API may not be deployed yet
    ])
      .then(([waveData, directions]) => {
        setData(waveData)
        if (directions && directions.categories) {
          setDirData(directions as DirectionData)
        }
      })
      .catch(e => setError(e.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  const toggleFav = useCallback((code: string) => {
    setFavs(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }, [])

  const toggleHide = useCallback((code: string) => {
    setHiddenCodes(prev => {
      const next = new Set(prev)
      next.add(code)
      return next
    })
  }, [])

  const restoreItem = useCallback((code: string) => {
    setHiddenCodes(prev => {
      const next = new Set(prev)
      next.delete(code)
      return next
    })
  }, [])

  function toggleExpand(id: string) {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  function toggleStocksExpand(cardId: string) {
    setShowAllStocks(prev => ({ ...prev, [cardId]: !prev[cardId] }))
  }

  const s = data?.stats
  const isEmpty = !loading && !data?.success

  // ── Direction-based view helpers ──

  // Build tab list: "全部" + enabled categories
  const tabs = useMemo(() => {
    const names: string[] = ['全部']
    if (dirData?.categories) {
      for (const cat of dirData.categories) {
        if (cat.enabled) {
          names.push(cat.name)
        }
      }
    }
    return names
  }, [dirData])

  // Map concept code → sub-direction full name (e.g. "科技.半导体")
  const conceptToSubDir = useMemo(() => {
    const map = new Map<string, string>()
    if (!dirData?.sub_directions) return map
    for (const [subDirName, info] of Object.entries(dirData.sub_directions)) {
      if (!info.enabled) continue
      for (const concept of info.concepts) {
        // Only the first sub-direction a concept belongs to (should be unique)
        if (!map.has(concept.code)) {
          map.set(concept.code, subDirName)
        }
      }
    }
    return map
  }, [dirData])

  // Get set of concept codes for the currently active category tab
  const activeCategory = activeTab === '全部' ? null : activeTab
  const categoryCodes = useMemo(() => {
    if (!activeCategory || !dirData?.sub_directions) return null
    const codes = new Set<string>()
    for (const [subDirName, info] of Object.entries(dirData.sub_directions)) {
      if (info.category === activeCategory && info.enabled) {
        for (const concept of info.concepts) {
          codes.add(concept.code)
        }
      }
    }
    return codes
  }, [activeCategory, dirData])

  // Filter grouped data by active category (null = show all)
  function getFilteredGrouped(): WaveData['grouped'] | null {
    if (!data?.grouped) return null
    if (!categoryCodes) return data.grouped // "全部" tab

    const stages = ['valley', 'peak', 'rise', 'decline', 'mid'] as const
    const result: WaveData['grouped'] = { valley: [], peak: [], rise: [], decline: [], mid: [] }
    for (const stage of stages) {
      result[stage] = (data.grouped[stage] || []).filter(i => categoryCodes.has(i.code))
    }
    return result
  }

  function allItems(): ConceptItem[] {
    if (!data?.grouped) return []
    return [
      ...data.grouped.valley,
      ...data.grouped.mid,
      ...data.grouped.decline,
    ]
  }

  // Visible items (not hidden)
  function visibleItems(): ConceptItem[] {
    return allItems().filter(i => !hiddenCodes.has(i.code))
  }

  function hiddenItems(): ConceptItem[] {
    return allItems().filter(i => hiddenCodes.has(i.code))
  }

  function favItems(): ConceptItem[] {
    return visibleItems().filter(i => favs.has(i.code))
  }

  // Filter klines by date range
  function filterKlines(klines: KLineData[]): KLineData[] {
    if (!klines || klines.length === 0) return []
    return klines.filter(k => k.date >= startDate && k.date <= endDate)
  }

  // 单张卡片的渲染
  function renderCard(item: ConceptItem, group: string, isFav?: boolean) {
    const chartId = `${group}-${item.code}`
    const isExpanded = expanded[chartId]
    const meta = STAGE_META[item.stage] || { label: '', color: '#888', bg: '#1a1b2e' }
    const stageIcon = item.stage === '波谷' ? '🟢' : item.stage === '波中' ? '🟡' : '🔴'

    // In direction view, show sub-direction name as prefix
    const subDirName = activeCategory ? conceptToSubDir.get(item.code) : undefined
    const displayName = subDirName
      ? `${subDirName.split('.').pop()} · ${item.name}`
      : item.name

    // Filtered klines for this card (computed only when expanded)
    const filteredKlines = isExpanded ? filterKlines(item.klines || []) : []
    const displayKlines = filteredKlines.length > 0 ? filteredKlines : (item.klines || [])
    const hasAnnotations = item.chart_annotations && item.chart_annotations.length > 0

    const stocksExpanded = showAllStocks[chartId]
    const totalRelated = item.related_count || item.related_stocks.length
    const showMore = item.related_stocks.length > 3

    // Determine signal tags for left info
    const signals: { label: string; className: string }[] = []
    if (item.volume_signal === 'shrink') signals.push({ label: '💧缩量', className: 'shrink' })
    if (item.volume_signal === 'surge') signals.push({ label: '🔥放量', className: 'surge' })
    if (item.entry_window) signals.push({ label: '↓切入窗口', className: 'entry' })
    if (item.chart_annotations?.some(a => a.type === 'overheat')) {
      signals.push({ label: '⚠️天量滞涨', className: 'overheat' })
    }

    return (
      <div key={chartId} className={`cw-card ${isExpanded ? 'expanded' : ''} ${isFav ? 'cw-card-fav' : ''}`}>
        {/* ====== 折叠态：全宽信息卡片 ====== */}
        <div className="cw-main" onClick={() => toggleExpand(chartId)}>
          {/* 第一行：名称 + 右侧操作区 */}
          <div className="cw-row-top">
            <span className="cw-name-block">
              <span className="cw-action-btn cw-star-btn" onClick={e => { e.stopPropagation(); toggleFav(item.code) }}
                title={favs.has(item.code) ? '取消特别关注' : '设为特别关注'}>
                {favs.has(item.code) ? '⭐' : '☆'}
              </span>
              {item.mainline_badge === 'gold' && <span className="cw-gold">[金]</span>}
              {item.mainline_badge === 'silver' && <span className="cw-silver">[银]</span>}
              <span className="cw-name">{displayName}</span>
              <span className="cw-vl">vl:<span className="cw-hl">{item.vl_score}</span></span>
            </span>
            <span className="cw-actions">
              <span className="cw-stage-badge" style={{ color: meta.color }}>
                {stageIcon} {item.stage}{STAGE_PROB[item.stage] ? ` (${STAGE_PROB[item.stage]})` : ''}
              </span>
              <span className="cw-action-btn" onClick={e => { e.stopPropagation(); toggleHide(item.code) }}
                title="隐藏此概念"
                style={{ fontSize: 15, opacity: 0.5 }}>🙈</span>
            </span>
          </div>
          {/* 第二行：信号标签 */}
          {signals.length > 0 && (
            <div className="cw-row-signals">
              {signals.map((s, si) => (
                <span key={si} className={`cw-signal-tag ${s.className}`}>{s.label}</span>
              ))}
            </div>
          )}
          {/* 第三行：核心指标 */}
          <div className="cw-row-stats">
            <span className="cw-stat-item">
              近5日 <span className={item.change_5d >= 0 ? 'up' : 'dn'}>{fmtPct(item.change_5d)}</span>
            </span>
            <span className="cw-stat-sep">|</span>
            <span className="cw-stat-item">
              BIAS20 <span className="dn">{fmtPct(item.bias20)}</span>
            </span>
            <span className="cw-stat-sep">|</span>
            <span className="cw-stat-item">
              vs大盘 <span className={item.vs_market_5d >= 0 ? 'up' : 'dn'}>{fmtPct(item.vs_market_5d)}</span>
            </span>
          </div>
          {/* 第四行：关联自选（带展开/收起全部） */}
          <div className="cw-row-related">
            <span className="cw-rl">关联:</span>
            {stocksExpanded ? (
              <>
                {item.related_stocks.map((stk, i) => (
                  <span key={i}>
                    <span className="cw-rstk">{stk}</span>
                    {i < item.related_stocks.length - 1 && <span className="cw-sep"> / </span>}
                  </span>
                ))}
                <span className="cw-more-hint clickable" onClick={e => { e.stopPropagation(); toggleStocksExpand(chartId) }}>
                  · 收起 ▲
                </span>
              </>
            ) : (
              <>
                {item.related_stocks.slice(0, 3).map((stk, i) => (
                  <span key={i}>
                    <span className="cw-rstk">{stk}</span>
                    {i < Math.min(item.related_stocks.length, 3) - 1 && <span className="cw-sep"> / </span>}
                  </span>
                ))}
                {showMore && (
                  <span className="cw-more-hint clickable" onClick={e => { e.stopPropagation(); toggleStocksExpand(chartId) }}>
                    · 共{item.related_stocks.length}只 ›
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        {/* ====== 展开态：仅K线图 ====== */}
        <div className={`cw-detail ${isExpanded ? 'show' : ''}`}>
          <div className="cw-chart-expanded">
            {isExpanded && item.klines && item.klines.length > 0 && (
              <svg viewBox="0 0 600 200" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                {renderKLineSVG(displayKlines, hasAnnotations ? item.chart_annotations : [], item.klines || [])}
              </svg>
            )}
            {isExpanded && (!item.klines || item.klines.length === 0) && (
              <div className="cw-chart-empty">暂无K线数据</div>
            )}
          </div>
          {/* 推理链 */}
          {isExpanded && item.reasoning_chain && (
            <div className="cw-reasoning-chain" style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(78,205,196,0.05)', borderRadius: 6, borderLeft: '3px solid #4ecdc4' }}>
              <div style={{ fontSize: 11, color: '#4ecdc4', fontWeight: 600, marginBottom: 6 }}>📊 推理链</div>
              <div style={{ fontSize: 11, color: '#bbb', lineHeight: 1.7 }}>
                <div>🏛 大盘周期：<span style={{ color: '#e0e0e0' }}>{item.reasoning_chain.market.position}</span>（建议仓位 <span style={{ color: '#34d399' }}>{item.reasoning_chain.market.position_pct}</span>）</div>
                <div style={{ marginLeft: 16, fontSize: 10, color: '#888' }}>成交量：{item.reasoning_chain.market.volume_level}（{item.reasoning_chain.market.volume_amount}）</div>
                {item.reasoning_chain.market.top_mainlines.length > 0 && (
                  <div style={{ marginLeft: 16, fontSize: 10, color: '#888' }}>
                    主线：{item.reasoning_chain.market.top_mainlines.map((m, i) => (
                      <span key={i}>{m.name}(第{m.rank}名{m.days}天){i < item.reasoning_chain.market.top_mainlines.length - 1 ? ' · ' : ''}</span>
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 3 }}>📦 概念分析：<span style={{ color: '#e0e0e0' }}>{item.reasoning_chain.concept_analysis.reason}</span></div>
                {item.reasoning_chain.stock_signals.filter(s => s.signal === 'buy').length > 0 && (
                  <div style={{ marginTop: 3 }}>
                    📈 个股买入信号：
                    {item.reasoning_chain.stock_signals.filter(s => s.signal === 'buy').map((s, i) => (
                      <span key={i} style={{ marginRight: 8, fontSize: 11 }}>
                        🟢 {s.name}({s.code}) — {s.buy_type}（{s.reason}）
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="page-wrap">
      <NavBar />
      <div className="content" style={{ maxWidth: 900, margin: '0 auto' }}>
        <div className="cw-title-bar">
          <h1 className="cw-title">📊 概念板块波谷追踪</h1>
          <div className="cw-title-actions">
            <div className="cw-date-range">
              📅
              <input
                type="date"
                className="cw-date-input"
                value={startDate}
                min={minDate}
                max={endDate}
                onChange={e => setStartDate(e.target.value)}
              />
              <span className="cw-date-sep">~</span>
              <input
                type="date"
                className="cw-date-input"
                value={endDate}
                min={startDate}
                max={maxDate}
                onChange={e => setEndDate(e.target.value)}
              />
            </div>
            <div className="cw-btn-sort">按阶段排序 ▼</div>
          </div>
        </div>

        {loading && !data && <div className="empty">正在加载概念板块数据…</div>}
        {error && <div className="empty" style={{ color: '#e94560' }}>⚠️ {error}</div>}
        {isEmpty && <div className="empty">暂无概念板块数据，请先运行数据更新</div>}

        {s && data?.success && (
          <>
            {/* 4 stat cards */}
            <div className="cw-stats-row">
              <div className="cw-stat-card">
                <div className="cw-stat-value">{s.valley}</div>
                <div className="cw-stat-label">当前波谷信号</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value" style={{ color: '#fbbf24' }}>{s.alerts_count}</div>
                <div className="cw-stat-label">强信号告警</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value">{s.total}</div>
                <div className="cw-stat-label">追踪概念总数</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value" style={{ color: '#34d399' }}>
                  {s.new_this_week > 0 ? `↑${s.new_this_week}%` : '--'}
                </div>
                <div className="cw-stat-label">上周新发现机会</div>
              </div>
            </div>

            {/* ══════════ ⭐ 特别关注区 ══════════ */}
            {favItems().length > 0 && (
              <>
                <div className="cw-fav-header">
                  <span className="cw-fav-title">⭐ 特别关注 · {favItems().length}个</span>
                  <span className="cw-fav-hint">点击☆可取消关注</span>
                </div>

                {/* 特别关注堆叠走势 — 独立行，不重叠 */}
                <div className="cw-fav-stack">
                  {favItems().map((item, fi) => {
                    const klines = item.klines || []
                    if (klines.length < 2) return null
                    const color = CHART_COLORS[fi % CHART_COLORS.length]
                    const closes = klines.map(k => k.close)
                    const base = closes[0]
                    const vals = closes.map(c => (c - base) / base * 100) // % change
                    const minV = Math.min(...vals)
                    const maxV = Math.max(...vals)
                    const rng = Math.max(maxV - minV, 1)
                    const n = vals.length
                    const svgW = 400, svgH = 60
                    const pts = vals.map((v, i) =>
                      `${((i / (n - 1 || 1)) * svgW).toFixed(0)},${(svgH - ((v - minV) / rng) * svgH * 0.8 - svgH * 0.1).toFixed(0)}`
                    ).join(' ')
                    const lastChg = vals[n - 1]
                    // 中证全指参考线
                    const indexCloses = (data?.index_klines || []).map(k => k.close)
                    let indexPolyline: string | null = null
                    if (indexCloses.length >= 2) {
                      const iBase = indexCloses[0]
                      const iVals = indexCloses.map(c => (c - iBase) / iBase * 100)
                      // 对齐到同一范围
                      const allVals = [...vals, ...iVals]
                      const allMin = Math.min(...allVals)
                      const allMax = Math.max(...allVals)
                      const allRng = Math.max(allMax - allMin, 1)
                      indexPolyline = iVals.map((v, i) =>
                        `${((i / (iVals.length - 1 || 1)) * svgW).toFixed(0)},${(svgH - ((v - allMin) / allRng) * svgH * 0.8 - svgH * 0.1).toFixed(0)}`
                      ).join(' ')
                    }
                    return (
                      <div key={item.code} className="cw-fav-row">
                        <span className="cw-fav-row-name">
                          <span className="cw-fav-row-star">{favs.has(item.code) ? '⭐' : '☆'}</span>
                          {item.name}
                          <span className="cw-fav-row-vl">vl:{item.vl_score}</span>
                        </span>
                        <span className="cw-fav-row-chart">
                          <svg viewBox={`0 0 ${svgW} ${svgH}`} preserveAspectRatio="none"
                            style={{ width: '100%', height: `${svgH}px` }}>
                            {/* 中证全指参考线（灰色虚线） */}
                            {indexPolyline && (
                              <polyline points={indexPolyline} fill="none" stroke="#555" strokeWidth="1"
                                strokeDasharray="4,3" opacity="0.5" />
                            )}
                            {/* 概念走势线 */}
                            <polyline points={pts} fill="none" stroke={color} strokeWidth="2"
                              strokeLinecap="round" strokeLinejoin="round" />
                            {/* 终点圆圈 */}
                            <circle cx={svgW} cy={svgH - ((vals[n - 1] - minV) / rng) * svgH * 0.8 - svgH * 0.1}
                              r="3" fill={color} stroke="#13141f" strokeWidth="1" />
                          </svg>
                        </span>
                        <span className="cw-fav-row-info">
                          <span className={`cw-fav-row-chg ${lastChg >= 0 ? 'up' : 'dn'}`}>
                            {lastChg >= 0 ? '+' : ''}{lastChg.toFixed(1)}%
                          </span>
                          <span className="cw-fav-row-label">区间涨跌</span>
                        </span>
                      </div>
                    )
                  })}
                </div>

                {/* Individual fav cards */}
                <div style={{ marginTop: 2 }}>
                  {favItems().map(item => renderCard(item, 'fav', true))}
                </div>
              </>
            )}

            {/* ══════════ Direction Tab Bar ══════════ */}
            {tabs.length > 1 && (
              <div className="cw-tab-bar">
                {tabs.map(tab => (
                  <span
                    key={tab}
                    className={`cw-tab ${activeTab === tab ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab}
                  </span>
                ))}
              </div>
            )}

            {/* ══════════ Grouped concept areas ══════════ */}
            <div className="cw-chart-area">
              {(['valley', 'peak', 'rise', 'decline', 'mid'] as const).map(group => {
                const grouped = getFilteredGrouped()
                if (!grouped) return null
                const items = grouped[group]
                if (!items || items.length === 0) return null
                const filtered = items.filter(i => !favs.has(i.code) && !hiddenCodes.has(i.code))
                if (filtered.length === 0) return null
                const meta = STAGE_META[items[0].stage] || { label: '', color: '#888', bg: '#1a1b2e' }
                const stageIcon = items[0].stage === '波谷' ? '🟢' : items[0].stage === '波中' ? '🟡' : '🔴'

                return (
                  <div key={group}>
                    <div className="cw-group-header">
                      <span className="cw-tag" style={{ borderColor: meta.color, color: meta.color, background: meta.bg }}>
                        {items[0].stage === '波谷' ? '🟢' : items[0].stage === '波峰' ? '🟠' : items[0].stage === '上涨' ? '🔵' : items[0].stage === '下跌' ? '🔴' : '🟡'} {items[0].stage}组{STAGE_PROB[items[0].stage] ? ` (${STAGE_PROB[items[0].stage]})` : ''}
                      </span>
                      <span className="cw-gc">{meta.label} · {filtered.length}个概念</span>
                    </div>
                    {filtered.map(item => renderCard(item, group))}
                  </div>
                )
              })}
            </div>

            {/* Time axis */}
            <div className="cw-axis-row">
              <span>← 60天前</span>
              <span className="cw-axis-today">今天</span>
              <span>当前位 →</span>
            </div>

            {/* ══════════ Hidden concepts section ══════════ */}
            {hiddenItems().length > 0 && (
              <div className="cw-hidden-section">
                <div className="cw-hidden-header" onClick={() => setShowHidden(v => !v)}>
                  <span className={`cw-hidden-icon ${showHidden ? 'open' : ''}`}>▶</span>
                  🙈 已隐藏（<span className="cw-hidden-count">{hiddenItems().length}</span>个概念）
                </div>
                <div className={`cw-hidden-body ${showHidden ? 'show' : ''}`}>
                  {hiddenItems().map(item => {
                    const meta = STAGE_META[item.stage] || { label: '', color: '#888', bg: '#1a1b2e' }
                    const stageIcon = item.stage === '波谷' ? '🟢' : item.stage === '波中' ? '🟡' : '🔴'
                    return (
                      <div key={item.code} className="cw-card" style={{ opacity: 0.6 }}>
                        <div className="cw-main" style={{ minHeight: 'auto', padding: '6px 10px' }}>
                          <span className="cw-info" style={{ flexDirection: 'row', width: 'auto', gap: 6, padding: 0 }}>
                            <span className="cw-name" style={{ fontSize: 13 }}>{item.name}</span>
                            <span className="cw-vl" style={{ fontSize: 11 }}>vl:{item.vl_score}</span>
                          </span>
                          <span style={{ fontSize: 11, color: meta.color }}>
                            {stageIcon} {item.stage}
                          </span>
                          <span className="cw-restore-btn" onClick={() => restoreItem(item.code)}>
                            恢复
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Valley alerts */}
            <div className="cw-section-title">
              ⚠️ 波谷告警（{data.alerts.length}条）
              <span className="cw-sc">· 强信号推荐关注</span>
            </div>
            {data.alerts.length === 0 && (
              <div className="empty" style={{ fontSize: 12, padding: '8px 0' }}>暂无告警</div>
            )}
            {data.alerts.map((alert, i) => (
              <div key={i} className="cw-alert">
                <div className="cw-alert-icon">⚠️</div>
                <div className="cw-alert-body">
                  <strong>{alert.name}</strong> <span className="cw-alert-hl">vl_score={alert.vl_score}</span> {alert.reason}
                </div>
              </div>
            ))}

            {/* New concepts scan */}
            {data.new_hot.length > 0 && (
              <>
                <div className="cw-section-title">
                  🔍 新概念扫描 <span className="cw-sc">· 本周新发现</span>
                </div>
                {data.new_hot.map((hot, i) => (
                  <div key={i} className="cw-scan-card">
                    <span className="cw-scan-name">💡 {hot.name}</span>
                    <span className="cw-scan-stat">+{hot.gain_20d}%</span>
                    <span className="cw-scan-label">20日涨幅 · {hot.stock_count}只成分股</span>
                    <span className="cw-scan-add">+ 添加追踪</span>
                  </div>
                ))}
              </>
            )}

            {/* Untracked stocks */}
            {data.untracked_concepts && data.untracked_concepts.length > 0 && (
              <>
                <div className="cw-section-title">
                  🏷️ 未追踪概念 <span className="cw-sc">· 自选股关联数不足</span>
                </div>
                <div style={{ padding: '4px 12px', fontSize: 11, color: '#888', marginBottom: 4 }}>
                  以下概念关联自选股数量不足6只，未纳入波谷追踪。
                  如想追踪，可在龙头观测手动添加。
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '0 12px 12px' }}>
                  {data.untracked_concepts.slice(0, 15).map((uc, i) => (
                    <div key={i} style={{
                      background: '#1a1a2a', borderRadius: 4, padding: '3px 8px', fontSize: 10,
                      border: '1px solid #2a2a4a',
                    }}>
                      {uc.name} <span style={{ color: '#666' }}>({uc.stock_count}只)</span>
                    </div>
                  ))}
                  {data.untracked_concepts.length > 15 && (
                    <div style={{ fontSize: 10, color: '#555', padding: '3px 4px' }}>
                      +{data.untracked_concepts.length - 15}个
                    </div>
                  )}
                </div>
                {data.untracked_stocks && data.untracked_stocks.length > 0 && (
                  <div style={{ padding: '0 12px 12px', fontSize: 10, color: '#666' }}>
                    涉及未追踪股票: {data.untracked_stocks.join('、')}
                  </div>
                )}
              </>
            )}

            {/* Legend */}
            <div className="cw-legend">
              <span><span className="cw-gold">[金]</span>主线前5</span>
              <span><span className="cw-silver">[银]</span>主线6-10</span>
              <span><span style={{ color: '#555' }}>— —</span> 大盘水位线</span>
              <span>💧 缩量</span>
              <span>🔥 放量</span>
              <span>⚠️ 天量滞涨</span>
              <span style={{ color: '#34d399' }}>↓切入窗口</span>
              <span><span style={{ color: '#888' }}>☆</span>点击星标特别关注</span>
              <span style={{ color: '#ffd700' }}>— EMA5</span>
              <span style={{ color: '#ff6b6b' }}>— EMA10</span>
              <span style={{ color: '#4ecdc4' }}>— EMA20</span>
            </div>

            <div style={{ fontSize: 10, color: '#444', textAlign: 'right', marginTop: 8 }}>
              {data.data_timestamp?.slice(0, 16) || data.date || ''}
            </div>
          </>
        )}
      </div>
      <BottomNav />
    </div>
  )
}

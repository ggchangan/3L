import { useEffect, useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import StockCard from '../components/StockCard'
import type { BuySignalItem } from '../lib/types'
import './Holdings.css'

interface HoldingItem {
  name: string; code: string; ratio: number; direction: string
  stop_loss_price: number | null; buy_price: number | null; price: number | null
  change: number | null; stop_loss_pct: number | null
  sector: string; structure: string; stage: string
  signal?: string
  buy_date?: string | null
  entry_signal_type?: string | null
  entry_signal_date?: string | null
  entry_anchor_price?: number | null
  stop_loss_source?: string | null
  original_stop_loss_price?: number | null
}

interface HoldingsData {
  holdings: HoldingItem[]
  cash_ratio: number
  update_date?: string
}

interface StopRecommendation {
  stop_loss: number
  recommendation_type: string
  reason: string
  price: number
  initial_stop: number | null
  buy_date_used: string | null
  protective_stop: number | null
  current_stop: number | null
  can_raise: boolean
  stop_loss_pct: number
  entry_signal_type: string | null
  entry_signal_confidence: number | null
  entry_signal_reason: string
  initial_stop_source: string | null
  initial_stop_anchor: { date: string; price: number; kind: string } | null
  protective_anchor: { date: string; price: number; kind: string } | null
}

const PIE_COLORS = [
  '#e94560', '#2196f3', '#4CAF50', '#ff9800', '#a855f7',
  '#00bcd4', '#ff5722', '#8bc34a', '#e91e63', '#3f51b5',
  '#009688', '#ffeb3b', '#9c27b0', '#795548', '#607d8b',
]

const STAGE_COLORS: Record<string, string> = {
  '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700',
  '滞涨': '#ff6b6b', '转弱': '#ff6b6b', '下行': '#666',
  '加速跌': '#e94560', '转强': '#4ecdc4',
  '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560',
}

function localToday(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().split('T')[0]
}

export default function Holdings() {
  const [data, setData] = useState<HoldingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [collapsed, setCollapsed] = useState(false)
  const [activeDir, setActiveDir] = useState('')

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editIdx, setEditIdx] = useState(-1)
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [selectedStock, setSelectedStock] = useState<{ name: string; code: string } | null>(null)
  const [modalDirection, setModalDirection] = useState('')
  const [modalRatio, setModalRatio] = useState('')
  const [modalStopLoss, setModalStopLoss] = useState('')
  const [originalModalStopLoss, setOriginalModalStopLoss] = useState('')
  const [modalSaving, setModalSaving] = useState(false)
  const [modalBuyPrice, setModalBuyPrice] = useState('')
  const [modalBuyDate, setModalBuyDate] = useState('')
  const [directions, setDirections] = useState<string[]>([])
  const [cachedPrice, setCachedPrice] = useState<number | null>(null)
  const [stopRecommendation, setStopRecommendation] = useState<StopRecommendation | null>(null)
  const [stopRecommendationLoading, setStopRecommendationLoading] = useState(false)
  const [stopRecommendationError, setStopRecommendationError] = useState('')
  const [manualStopEdited, setManualStopEdited] = useState(false)

  // Confirm state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleteIdx, setDeleteIdx] = useState(-1)
  const [deleteName, setDeleteName] = useState('')

  const stopRequestSeq = useRef(0)
  const searchRequestSeq = useRef(0)
  const manualStopEditedRef = useRef(false)

  useEffect(() => { loadData() }, [])
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setModalOpen(false); setConfirmOpen(false) }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  async function loadData() {
    setLoading(true); setError('')
    try {
      const r = await fetch('/api/holdings?_=' + Date.now())
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d: HoldingsData = await r.json()
      setData(d)
    } catch (err: any) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  async function loadDirections() {
    try {
      const r = await fetch('/api/directions/get')
      const d = await r.json()
      // 新分层格式：active 数组；旧格式：directions 字典
      if (d.active_ordered && d.active_ordered.length > 0) {
        setDirections(d.active_ordered)
      } else if (d.active && d.active.length > 0) {
        setDirections(d.active)
      } else {
        const dirs = Object.keys(d.directions || {})
        setDirections(dirs)
      }
    } catch { /* ignore */ }
  }

  function showToast(msg: string, isError?: boolean) {
    const el = document.createElement('div')
    el.textContent = msg
    el.style.cssText = `position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid ${isError ? '#e94560' : '#22c55e'};color:${isError ? '#e94560' : '#22c55e'};padding:8px 20px;border-radius:6px;font-size:13px;z-index:999;transition:opacity .3s`
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2000)
  }

  function inferSignal(h: HoldingItem): string {
    if (h.structure === '上涨趋势' && (h.stage === '上行' || h.stage === '缩量整理')) return 'hold'
    if (h.structure === '上涨趋势' && h.stage === '加速') return 'buy'
    if (h.structure === '下降趋势' || h.stage === '转弱' || h.stage === '滞涨' || h.stage === '下行') return 'sell'
    if (h.structure === '区间震荡' && h.stage === '区间底部') return 'buy'
    return 'hold'
  }

  function renderPie(holdings: HoldingItem[], cashRatio: number) {
    const dirMap: Record<string, { ratio: number; count: number }> = {}
    holdings.forEach(h => {
      const d = h.direction || '其他'
      if (!dirMap[d]) dirMap[d] = { ratio: 0, count: 0 }
      dirMap[d].ratio += h.ratio || 0
      dirMap[d].count += 1
    })
    if (cashRatio > 0) dirMap['现金'] = { ratio: cashRatio, count: 0 }
    const pieData = Object.entries(dirMap)
      .map(([name, v]) => ({ name, count: v.count, pct: parseFloat(v.ratio.toFixed(1)) }))
      .sort((a, b) => b.pct - a.pct)
    const total = pieData.reduce((s, d) => s + d.pct, 0)
    const svgW = 260, svgH = 260, cx = 130, cy = 130, r = 100

    let startAngle = -90
    let paths = ''
    let legendHtml = ''

    pieData.forEach((d, i) => {
      const angle = (d.pct / total) * 360
      const endAngle = startAngle + angle
      const color = d.name === '现金' ? '#666' : PIE_COLORS[i % PIE_COLORS.length]
      const sRad = startAngle * Math.PI / 180
      const eRad = endAngle * Math.PI / 180
      const x1 = cx + r * Math.cos(sRad); const y1 = cy + r * Math.sin(sRad)
      const x2 = cx + r * Math.cos(eRad); const y2 = cy + r * Math.sin(eRad)
      const largeArc = angle > 180 ? 1 : 0
      paths += `<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} Z" fill="${color}" stroke="#1a1a2e" stroke-width="1.5" opacity="0.9"/>`
      const labelAngle = (startAngle + endAngle) / 2
      const lRad = labelAngle * Math.PI / 180
      const textR = r * 0.65
      const tx = cx + textR * Math.cos(lRad); const ty = cy + textR * Math.sin(lRad)
      if (d.pct >= 5) {
        paths += `<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central" font-size="12" fill="#fff" font-weight="600">${d.pct.toFixed(0)}%</text>`
      }
      const countDisplay = d.count > 0 ? d.count + '只' : ''
      legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span class="legend-name">${d.name}</span>${countDisplay ? `<span class="legend-count">${countDisplay}</span>` : '<span class="legend-count"></span>'}<span class="legend-pct">${d.pct}%</span></div>`
      startAngle = endAngle
    })
    paths += `<circle cx="${cx}" cy="${cy}" r="38" fill="#0f0f1a" stroke="#2a2a4e" stroke-width="1"/><text x="${cx}" y="${cy - 5}" text-anchor="middle" font-size="20" font-weight="700" fill="#e94560">${holdings.length}</text><text x="${cx}" y="${cy + 12}" text-anchor="middle" font-size="11" fill="#888">只个股</text>`

    return {
      svg: `<svg width="100%" height="100%" viewBox="0 0 ${svgW} ${svgH}" style="max-width:260px;max-height:260px;">${paths}</svg>`,
      legend: legendHtml,
    }
  }

  function computeAssessment(holdings: HoldingItem[], cashRatio: number) {
    const totalRatio = 100 - cashRatio
    const items: { text: string; cls: string }[] = []

    if (totalRatio > 80) items.push({ text: `🔴 总仓位 ${totalRatio.toFixed(1)}% 偏高`, cls: 'high' })
    else if (totalRatio < 50) items.push({ text: `⚠️ 总仓位 ${totalRatio.toFixed(1)}% 偏低，资金利用率不足`, cls: 'medium' })
    else if (totalRatio <= 70) items.push({ text: `✅ 总仓位 ${totalRatio.toFixed(1)}%，控制合理`, cls: 'low' })
    else items.push({ text: `✅ 总仓位 ${totalRatio.toFixed(1)}%，偏积极但可控`, cls: 'low' })

    const dirMap: Record<string, number> = {}
    holdings.forEach(h => { const d = h.direction || '其他'; dirMap[d] = (dirMap[d] || 0) + (h.ratio || 0) })
    Object.entries(dirMap).sort((a, b) => b[1] - a[1]).forEach(([dir, ratio]) => {
      if (ratio >= 40) items.push({ text: `🔴 ${dir} ${ratio.toFixed(1)}% 严重集中`, cls: 'high' })
      else if (ratio >= 30) items.push({ text: `⚠️ ${dir} ${ratio.toFixed(1)}% 偏集中`, cls: 'medium' })
      else items.push({ text: `✅ ${dir} ${ratio.toFixed(1)}%`, cls: 'low' })
    })

    if (cashRatio < 5) items.push({ text: `🔴 现金仅 ${cashRatio.toFixed(1)}%，调仓空间有限`, cls: 'high' })
    else if (cashRatio > 40) items.push({ text: `⚠️ 现金 ${cashRatio.toFixed(1)}% 偏高，仓位利用率偏低`, cls: 'medium' })
    else items.push({ text: `✅ 现金 ${cashRatio.toFixed(1)}%，调仓空间充裕`, cls: 'low' })

    holdings.forEach(h => {
      if (h.ratio >= 15) items.push({ text: `🔴 ${h.name} 仓位 ${h.ratio}% 严重集中`, cls: 'high' })
      else if (h.ratio >= 10) items.push({ text: `⚠️ ${h.name} 仓位 ${h.ratio}% 偏集中`, cls: 'medium' })
    })

    const w: Record<string, number> = { high: 0, medium: 1, low: 2 }
    items.sort((a, b) => (w[a.cls] || 2) - (w[b.cls] || 2))
    return items
  }

  function computeSuggestions(holdings: HoldingItem[], cashRatio: number) {
    const totalRatio = 100 - cashRatio
    const suggestions: string[] = []
    if (totalRatio > 80) suggestions.push('建议适当减仓，控制总仓位在建议范围内')
    else if (totalRatio < 50) suggestions.push('当前仓位偏低，可在主线确认后适当加仓')

    holdings.forEach(h => {
      if (h.ratio >= 15) suggestions.push(`${h.name} 仓位过高，若跌破止损需果断减仓`)
      else if (h.ratio >= 10) suggestions.push(`${h.name} 仓位超过10%，注意分散风险`)
    })

    const dirMap: Record<string, number> = {}
    holdings.forEach(h => { const d = h.direction || '其他'; dirMap[d] = (dirMap[d] || 0) + (h.ratio || 0) })
    Object.entries(dirMap).forEach(([dir, ratio]) => {
      if (ratio >= 40) suggestions.push(`${dir} 方向占比过高，建议减仓分散`)
      else if (ratio >= 30) suggestions.push(`${dir} 方向 ${holdings.filter(h => (h.direction || '其他') === dir).length} 只标的，可考虑聚焦核心`)
    })

    if (cashRatio < 5) suggestions.push('现金不足5%，考虑适当减仓预留调仓空间')
    else if (cashRatio > 40) suggestions.push('现金较多，可在板块回调时择机加仓')

    const dirCount = Object.keys(dirMap).length
    if (dirCount > 5) suggestions.push(`涉及 ${dirCount} 个方向，考虑聚焦主营方向`)

    return suggestions
  }

  // ── Modal handlers ──

  function openAddModal() {
    setEditIdx(-1); setSelectedStock(null); setSearchQ(''); setModalDirection('')
    setModalRatio(''); setModalStopLoss(''); setOriginalModalStopLoss(''); setModalBuyPrice('')
    setModalBuyDate(localToday()); setCachedPrice(null)
    setStopRecommendation(null)
    setStopRecommendationError('')
    setManualStopEdited(false); manualStopEditedRef.current = false
    setSearchResults([]); setModalOpen(true)
    loadDirections()
  }

  function openEditModal(idx: number) {
    if (!data) return
    const h = data.holdings[idx]
    setEditIdx(idx); setSelectedStock({ name: h.name, code: h.code })
    setSearchQ(''); setModalDirection(h.direction || '')
    const savedStop = h.stop_loss_price ? String(h.stop_loss_price) : ''
    setModalRatio(String(h.ratio || '')); setModalStopLoss(savedStop); setOriginalModalStopLoss(savedStop)
    setModalBuyPrice(h.buy_price ? String(h.buy_price) : '')
    setModalBuyDate(h.buy_date || '')
    setCachedPrice(h.price ?? null); setSearchResults([])
    setStopRecommendation(null)
    setStopRecommendationError('')
    setManualStopEdited(false); manualStopEditedRef.current = false
    setModalOpen(true)
    loadDirections()
  }

  function closeModal() { setModalOpen(false) }

  function handleSearch(q: string) {
    setSearchQ(q)
    const requestSeq = ++searchRequestSeq.current
    if (q.length < 1) { setSearchResults([]); return }
    ;(async () => {
      try {
        const r = await fetch('/api/directions/stocks?q=' + encodeURIComponent(q))
        const d = await r.json()
        if (requestSeq === searchRequestSeq.current) {
          setSearchResults((d.stocks || []).slice(0, 10))
        }
      } catch {
        if (requestSeq === searchRequestSeq.current) setSearchResults([])
      }
    })()
  }

  function selectStock(name: string, code: string, price: number, direction?: string) {
    setSelectedStock({ name, code })
    setSearchQ(name); setSearchResults([])
    if (price > 0) {
      setCachedPrice(price)
      setModalBuyPrice(String(price))
    }
    else { setCachedPrice(null); setModalBuyPrice('') }
    setModalDirection(direction || '')
    if (direction) {
      setDirections(current => current.includes(direction) ? current : [...current, direction])
    }
    setStopRecommendation(null)
    setStopRecommendationError('')
    setModalStopLoss(''); setOriginalModalStopLoss('')
    setManualStopEdited(false); manualStopEditedRef.current = false
  }

  useEffect(() => {
    const buyPrice = Number(modalBuyPrice)
    if (!modalOpen || !selectedStock || !modalBuyDate || !Number.isFinite(buyPrice) || buyPrice <= 0) {
      stopRequestSeq.current += 1
      setStopRecommendationLoading(false)
      return
    }

    const requestSeq = ++stopRequestSeq.current
    setStopRecommendationLoading(true)
    setStopRecommendationError('')
    setStopRecommendation(null)
    const timer = setTimeout(async () => {
      try {
        const previous = editIdx >= 0 ? data?.holdings[editIdx] : undefined
        const usePersistedEntry = Boolean(
          previous && modalBuyDate === (previous.buy_date || '')
          && buyPrice === Number(previous.buy_price || 0)
        )
        const r = await fetch('/api/holdings/recommended-stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: selectedStock.code,
            buy_date: modalBuyDate,
            buy_price: buyPrice,
            current_stop: (manualStopEditedRef.current ? modalStopLoss : originalModalStopLoss)
              ? parseFloat(manualStopEditedRef.current ? modalStopLoss : originalModalStopLoss)
              : null,
            entry_signal_type: usePersistedEntry ? previous?.entry_signal_type || null : null,
            entry_signal_date: usePersistedEntry ? previous?.entry_signal_date || null : null,
            entry_anchor_price: usePersistedEntry ? previous?.entry_anchor_price || null : null,
            original_stop_loss_price: usePersistedEntry ? previous?.original_stop_loss_price || null : null,
          }),
        })
        const d = await r.json()
        if (requestSeq !== stopRequestSeq.current) return
        if (!d.success) {
          setStopRecommendationError(d.error || '数据不足，请手工填写止损')
          return
        }
        setStopRecommendation(d)
        if (d.price) setCachedPrice(d.price)
        if (Number(d.stop_loss) > 0 && !manualStopEditedRef.current) {
          setModalStopLoss(String(d.stop_loss))
          setManualStopEdited(false)
        }
      } catch {
        if (requestSeq === stopRequestSeq.current) setStopRecommendationError('止损建议请求失败，请手工填写止损')
      } finally {
        if (requestSeq === stopRequestSeq.current) setStopRecommendationLoading(false)
      }
    }, 350)

    return () => clearTimeout(timer)
    // 止损输入不参与依赖：自动建议只由股票、买入日期和买入价触发，避免覆盖用户随后手工修正的止损。
  }, [modalOpen, selectedStock?.code, modalBuyDate, modalBuyPrice, editIdx])

  function calcStopLossPct(): string {
    const slVal = parseFloat(modalStopLoss)
    if (!isNaN(slVal) && cachedPrice !== null && cachedPrice > 0) {
      const pct = ((slVal - cachedPrice) / cachedPrice * 100)
      const color = Math.abs(pct) > 8 ? '#e94560' : Math.abs(pct) > 5 ? '#ffd700' : '#4ecdc4'
      return `<span style="color:${color}">${pct.toFixed(2)}%</span>（当前价 ${cachedPrice.toFixed(2)}）`
    }
    if (!isNaN(slVal) && cachedPrice === null) return '当前价获取中，请稍后或手动填写'
    return ''
  }

  async function saveModal() {
    if (!selectedStock) { alert('请选择股票'); return }
    if (!modalDirection) { alert('请选择方向'); return }
    const ratio = parseFloat(modalRatio)
    if (isNaN(ratio) || ratio <= 0) { alert('请输入有效仓位比例'); return }
    const slVal = modalStopLoss.trim() !== '' ? parseFloat(modalStopLoss) : null
    if (slVal !== null && (isNaN(slVal) || slVal <= 0)) { alert('请输入有效止损价'); return }
    const previous = editIdx >= 0 ? data?.holdings[editIdx] : undefined
    const previousStop = previous?.stop_loss_price
    if (previousStop != null && (slVal == null || slVal < previousStop)) {
      alert(`已有止损 ${previousStop.toFixed(2)} 元只能维持或上调；如需纠正原始录入，请删除该持仓后重新添加`)
      return
    }

    setModalSaving(true)
    try {
      const holdings = [...(data?.holdings || [])]
      const preservingEntryMetadata = Boolean(
        previous && modalBuyDate === (previous.buy_date || '')
        && Number(modalBuyPrice || 0) === Number(previous.buy_price || 0)
      )
      const adoptedRecommendation = Boolean(
        stopRecommendation && !manualStopEdited
        && Number(modalStopLoss) === stopRecommendation.stop_loss
      )
      const stopWasManuallyChanged = manualStopEdited
      const stopValueUnchanged = Boolean(
        previous && previous.stop_loss_price != null && slVal === previous.stop_loss_price
      )
      const item: HoldingItem = {
        name: selectedStock.name, code: selectedStock.code,
        ratio, direction: modalDirection, stop_loss_price: slVal,
        price: null, buy_price: modalBuyPrice ? parseFloat(modalBuyPrice) : null,
        change: null, stop_loss_pct: null,
        sector: previous?.sector || '', structure: '--', stage: '--',
        buy_date: modalBuyDate || null,
        entry_signal_type: stopRecommendation?.entry_signal_type
          || (preservingEntryMetadata ? previous?.entry_signal_type || null : null),
        entry_signal_date: stopRecommendation?.entry_signal_type
          ? (stopRecommendation.buy_date_used || modalBuyDate)
          : (preservingEntryMetadata ? previous?.entry_signal_date || null : null),
        entry_anchor_price: stopRecommendation?.initial_stop_anchor?.price
          ?? (preservingEntryMetadata ? previous?.entry_anchor_price || null : null),
        stop_loss_source: stopValueUnchanged
          ? previous?.stop_loss_source || null
          : (stopWasManuallyChanged ? 'manual'
            : (adoptedRecommendation ? stopRecommendation.recommendation_type
              : (preservingEntryMetadata ? previous?.stop_loss_source || null : 'manual'))),
        original_stop_loss_price: stopRecommendation?.initial_stop
          ?? (preservingEntryMetadata ? previous?.original_stop_loss_price || null : null),
      }
      if (editIdx >= 0 && editIdx < holdings.length) holdings[editIdx] = item
      else holdings.push(item)

      const totalStockRatio = holdings.reduce((s, h) => s + (h.ratio || 0), 0)
      const cashRatio = Math.max(0, Math.min(100, 100 - totalStockRatio))
      const currentCash = data?.cash_ratio ?? 100

      const r = await fetch('/api/holdings/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings, cash_ratio: parseFloat(cashRatio.toFixed(2)) }),
      })
      const result = await r.json()
      if (result.success) {
        closeModal(); showToast(editIdx >= 0 ? '已更新' : '已新增')
        loadData()
      } else {
        alert('保存失败: ' + (result.error || '未知错误'))
      }
    } catch (err: any) {
      alert('保存失败: ' + err.message)
    } finally { setModalSaving(false) }
  }

  function openDeleteConfirm(idx: number) {
    if (!data) return
    setDeleteIdx(idx); setDeleteName(data.holdings[idx]?.name || '')
    setConfirmOpen(true)
  }
  function closeConfirm() { setConfirmOpen(false); setDeleteIdx(-1) }

  async function confirmDelete() {
    if (deleteIdx < 0 || !data) return
    try {
      const holdings = [...data.holdings]
      holdings.splice(deleteIdx, 1)
      const totalStockRatio = holdings.reduce((s, h) => s + (h.ratio || 0), 0)
      const cashRatio = Math.max(0, Math.min(100, 100 - totalStockRatio))
      const r = await fetch('/api/holdings/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings, cash_ratio: parseFloat(cashRatio.toFixed(2)) }),
      })
      const result = await r.json()
      if (result.success) { closeConfirm(); showToast('已删除'); loadData() }
      else { alert('删除失败: ' + (result.error || '未知错误')) }
    } catch (err: any) { alert('删除失败: ' + err.message) }
  }

  // ── Render ──

  const holdings = data?.holdings || []
  const cashRatio = data?.cash_ratio ?? 100
  const hasData = holdings.length > 0
  const pieResult = hasData ? renderPie(holdings, cashRatio) : null
  const assessment = hasData ? computeAssessment(holdings, cashRatio) : []
  const suggestions = computeSuggestions(holdings, cashRatio)

  // 按涨幅降序排列
  const sortedHoldings = [...holdings]
    .map((h, i) => ({ idx: i, item: h }))
    .sort((a, b) => (b.item.change ?? -999) - (a.item.change ?? -999))

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📋 持仓管理</h1>
        <div className="update-time" id="updateTime">
          {data?.update_date ? `📅 更新于 ${data.update_date}` : loading ? '加载中...' : '--'}
        </div>
      </div>

      <div className="container">
        {loading && <div className="loading-state">⌛ 加载持仓数据...</div>}

        {error && <div className="error-state">❌ 加载失败: {error}</div>}

        {/* Overview Block */}
        {hasData && pieResult && (
          <div className="overview-block" id="overviewArea">
            <div className="ov-title">📊 股票概况</div>
            <div className="ov-body">
              <div className="ov-pie" dangerouslySetInnerHTML={{ __html: pieResult.svg }} />
              <div className="ov-legend" dangerouslySetInnerHTML={{ __html: pieResult.legend }} />
              <div className="ov-assessment">
                <div className="oa-title">持仓评估</div>
                {assessment.map((a, i) => (
                  <div key={i} className={`oa-item ${a.cls}`}>{a.text}</div>
                ))}
              </div>
            </div>
            <div className="ov-stats">
              <span>📈 股票 <b>{holdings.length}</b> 只</span>
              <span>总仓位 <b>{(100 - cashRatio).toFixed(1)}%</b></span>
              <span>现金 <b>{cashRatio.toFixed(1)}%</b></span>
              <span>最大单只 <b>{Math.max(...holdings.map(h => h.ratio || 0)).toFixed(1)}%</b></span>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && !hasData && (
          <div className="empty-state" id="emptyState">
            <div className="empty-icon">📭</div>
            <p>暂无持仓，点击下方按钮添加</p>
            <button className="add-btn" onClick={openAddModal}>＋ 新增第一只持仓</button>
          </div>
        )}

        {/* Card Section */}
        {hasData && (
          <div id="cardArea">
            <div className="card-section-header" onClick={() => setCollapsed(!collapsed)}>
              <span id="cardToggleIcon">{collapsed ? '▶' : '▼'}</span>
              <span>个股信息 <span style={{ color: '#888', fontSize: 12 }}>({holdings.length}只)</span></span>
              <button className="add-btn-sm" onClick={(e) => { e.stopPropagation(); openAddModal() }}>＋ 新增</button>
            </div>
            {!collapsed && (
              <div id="cardBody">
                <div id="cardList">
                    {(() => {
                      const dirMap: Record<string, { items: typeof sortedHoldings; totalRatio: number }> = {}
                      sortedHoldings.forEach(sh => {
                        const d = sh.item.direction || '其他'
                        if (!dirMap[d]) dirMap[d] = { items: [], totalRatio: 0 }
                        dirMap[d].items.push(sh)
                        dirMap[d].totalRatio += sh.item.ratio || 0
                      })
                      const dirs = Object.keys(dirMap).sort((a, b) => dirMap[b].totalRatio - dirMap[a].totalRatio)
                      const curDir = activeDir && dirMap[activeDir] ? activeDir : (dirs[0] || '')
                      if (!activeDir && dirs.length > 0) { setTimeout(() => setActiveDir(dirs[0]), 0) }
                      const filtered = curDir ? (dirMap[curDir]?.items || []) : sortedHoldings
                      return (
                        <>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10, borderBottom: '1px solid #333', paddingBottom: 6 }}>
                            {dirs.map(dir => {
                              const isActive = dir === curDir
                              return (
                                <span key={dir} onClick={() => setActiveDir(dir)}
                                  style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 12, borderRadius: 12, display: 'inline-block',
                                    background: isActive ? '#4ecdc4' : 'rgba(255,255,255,0.05)',
                                    color: isActive ? '#fff' : '#999',
                                  }}
                                >{dir} ({dirMap[dir].items.length}只 · {dirMap[dir].totalRatio.toFixed(1)}%)</span>
                              )
                            })}
                          </div>
                          {filtered.map(({ idx: origIdx, item: h }, i) => {
                            const s: BuySignalItem = {
                      code: h.code,
                      name: h.name,
                      signal: h.signal || inferSignal(h),
                      stage: h.stage || '--',
                      structure: h.structure || '--',
                      trading_system: '3l',
                      price: h.price ?? undefined,
                      change: h.change ?? undefined,
                      direction: h.direction || '',
                      sector: h.sector || '',
                      stop_loss: h.stop_loss_price ?? undefined,
                      stop_loss_pct: h.stop_loss_pct ?? undefined,
                      profit_model1: false,
                      trend_stock: false,
                      trading_reason: '持仓管理',
                    }
                    const leftColor = STAGE_COLORS[h.stage] || '#888'
                    const barColor = h.ratio >= 10 ? '#e94560' : h.ratio >= 6 ? '#ffd700' : '#4ecdc4'
                    return (
                      <div key={h.code + origIdx} className="watchlist-card-wrapper" style={{ borderLeft: `3px solid ${leftColor}`, borderRadius: '12px 0 0 12px' }}>
                        <StockCard s={s} idx={i} />
                        <div className="watchlist-card-actions">
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                            <span style={{ color: '#ffd700', fontWeight: 600, fontSize: 12, whiteSpace: 'nowrap' }}>仓位: {(h.ratio || 0).toFixed(2)}%</span>
                            <div className="ratio-bar-bg" style={{ flex: 1, maxWidth: 100 }}>
                              <div className="ratio-bar" style={{ width: `${Math.min(h.ratio, 100)}%`, background: barColor }}></div>
                            </div>
                            {h.stop_loss_price !== null && h.stop_loss_price !== undefined && (
                              <span style={{ fontSize: 11, color: '#888', whiteSpace: 'nowrap' }}>
                                止损 {h.stop_loss_price.toFixed(2)}
                                {h.stop_loss_pct !== null && h.stop_loss_pct !== undefined && ` (${(h.stop_loss_pct as number).toFixed(2)}%)`}
                              </span>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                            <button className="act-btn" onClick={() => openEditModal(origIdx)}>✏️ 编辑</button>
                            <button className="act-btn" onClick={() => openDeleteConfirm(origIdx)}>🗑️ 删除</button>
                          </div>
                        </div>
                      </div>
                    )
                          })}
                        </>
                      )
                    })()}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="section-card" id="suggestionSection">
            <div className="section-title suggestion">📋 持仓建议</div>
            <div id="suggestionContent">
              {suggestions.map((s, i) => (
                <div key={i} className="item">💡 {s}</div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        {!loading && <div className="footer">仅你可见 · URL 请保密</div>}
      </div>

      <BottomNav />

      {/* Add/Edit Modal */}
      {modalOpen && (
        <div className="modal-overlay active" onClick={(e) => { if (e.target === e.currentTarget) closeModal() }}>
          <div className="modal">
            <h2>{editIdx >= 0 ? '编辑持仓' : '新增持仓'}</h2>
            <input type="hidden" id="editIndex" value={editIdx} />

            {editIdx < 0 && (
              <div className="form-row">
                <label>搜索股票</label>
                <input type="text" placeholder="输入股票名称或代码..." autoComplete="off"
                  value={searchQ} onChange={e => handleSearch(e.target.value)} />
                {searchResults.length > 0 && (
                  <div className="search-results">
                    {searchResults.map((s: any) => (
                      <div key={s.code} className="result-item" onClick={() => selectStock(s.name, s.code, s.price || 0, s.direction)}>
                        <span>{s.name} <span style={{ color: '#4ecdc4', fontSize: 11 }}>{s.price ? s.price.toFixed(2) : ''}</span></span>
                        <span className="ri-code">{s.code}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="form-row">
              <label>选中股票</label>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ fontWeight: 600, color: '#e0e0e0' }}>{selectedStock?.name || '-'}</span>
                <span style={{ color: '#666', fontSize: 11 }}>{selectedStock?.code || '-'}</span>
              </div>
              <div className="price-display">
                {cachedPrice !== null ? `${cachedPrice.toFixed(2)} 元` : '--'}
              </div>
            </div>

            <div className="form-row">
              <label htmlFor="holding-direction">方向</label>
              <select id="holding-direction" value={modalDirection} onChange={e => setModalDirection(e.target.value)}>
                <option value="">请选择方向</option>
                {modalDirection && !directions.includes(modalDirection) && (
                  <option value={modalDirection}>{modalDirection}</option>
                )}
                {directions.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <label htmlFor="holding-buy-date">买入日期</label>
              <input id="holding-buy-date" type="date" max={localToday()}
                value={modalBuyDate} onChange={e => { setModalBuyDate(e.target.value); setStopRecommendation(null) }} />
              <div className="hint">用于还原买入当日可见的价格结构，计算初始风险止损</div>
            </div>

            <div className="form-row">
              <label>买入价格 (元)</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="number" step="0.01" min="0" placeholder="0.00"
                  value={modalBuyPrice} onChange={e => { setModalBuyPrice(e.target.value); setStopRecommendation(null) }}
                  style={{ flex: 1 }} />
                <span style={{ fontSize: 11, color: '#888' }}>
                  当前价: {cachedPrice !== null ? cachedPrice.toFixed(2) : '--'}
                </span>
              </div>
            </div>

            <div className="form-row">
              <label>仓位 (%)</label>
              <input type="number" step="0.01" min="0" max="100" placeholder="0.00"
                value={modalRatio} onChange={e => setModalRatio(e.target.value)} />
            </div>

            <div className="form-row">
              <label>建仓买点识别</label>
              <div data-testid="entry-signal-status" style={{ color: stopRecommendation?.entry_signal_type ? '#4ecdc4' : '#aaa', fontWeight: 600 }}>
                {stopRecommendationLoading
                  ? '识别中…'
                  : stopRecommendation?.entry_signal_type || (stopRecommendation ? '无买点' : '等待股票、买入日期和买入价')}
              </div>
              <div className="hint">系统只使用买入日及之前的数据自动识别；没有符合 3L 定义的信号时显示“无买点”。</div>
            </div>

            <div className="form-row">
              <label htmlFor="holding-stop-loss">止损价 (元) — <span style={{ color: '#888' }}>不填则不设止损</span></label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input id="holding-stop-loss" type="number" step="0.01" min="0" placeholder="0.00"
                  value={modalStopLoss} onChange={e => {
                    setModalStopLoss(e.target.value)
                    setManualStopEdited(true); manualStopEditedRef.current = true
                  }}
                  style={{ flex: 1 }} />
              </div>
              <div className="hint">股票、买入日期和买入价确定后自动计算并默认采用；你仍可手工修正。已有持仓只维持或上调保护位。</div>
              <div className="hint" dangerouslySetInnerHTML={{ __html: calcStopLossPct() }} />
              {stopRecommendationError && (
                <div className="hint" role="alert" style={{ color: '#ffd700' }}>
                  {stopRecommendationError}；系统未覆盖已有止损。
                </div>
              )}
              {stopRecommendation && (
                <div className="stop-recommendation" data-testid="stop-recommendation">
                  <div><strong>建议 {stopRecommendation.stop_loss.toFixed(2)} 元</strong>（距现价 {stopRecommendation.stop_loss_pct.toFixed(2)}%）</div>
                  <div>{stopRecommendation.reason}</div>
                  {stopRecommendation.entry_signal_type && (
                    <div>识别买点：{stopRecommendation.entry_signal_type}
                      {stopRecommendation.entry_signal_confidence != null ? `（置信度 ${stopRecommendation.entry_signal_confidence.toFixed(1)}）` : ''}
                    </div>
                  )}
                  {stopRecommendation.entry_signal_reason && <div>{stopRecommendation.entry_signal_reason}</div>}
                  {stopRecommendation.initial_stop !== null && (
                    <div>建仓初始止损：{stopRecommendation.initial_stop.toFixed(2)} 元
                      {stopRecommendation.buy_date_used ? `（按 ${stopRecommendation.buy_date_used} K线）` : ''}
                    </div>
                  )}
                  {stopRecommendation.initial_stop_anchor && (
                    <div>初始失效锚点：{stopRecommendation.initial_stop_anchor.price.toFixed(2)}</div>
                  )}
                  {stopRecommendation.protective_stop !== null && (
                    <div>建仓后更高低点保护位：{stopRecommendation.protective_stop.toFixed(2)} 元
                      {stopRecommendation.protective_anchor?.date ? `（${stopRecommendation.protective_anchor.date}）` : ''}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="btn-row">
              <button className="btn-cancel" onClick={closeModal}>取消</button>
              <button className="btn-save" onClick={saveModal} disabled={modalSaving || stopRecommendationLoading}>
                {modalSaving ? '保存中...' : stopRecommendationLoading ? '自动计算中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {confirmOpen && (
        <div className="modal-overlay active" onClick={(e) => { if (e.target === e.currentTarget) closeConfirm() }}>
          <div className="modal" style={{ width: 320 }}>
            <div className="confirm-box">
              <p>确定要删除「{deleteName}」吗？</p>
              <div className="btn-row">
                <button className="btn-cancel" onClick={closeConfirm}>取消</button>
                <button className="btn-save" onClick={confirmDelete} style={{ background: '#e94560' }}>删除</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

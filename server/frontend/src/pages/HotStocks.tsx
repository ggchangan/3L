import { useEffect, useState, useMemo } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import StockCard from '../components/StockCard'
import type { BuySignalItem } from '../lib/types'
import './HotStocks.css'

interface HotStockItem extends BuySignalItem {
  hot_rank: number
  hot_value: number
  concept_tags: string[]
  popularity_tag: string
  price: number | null
  change: number
  sector: string
  structure: string
  stage: string
  signal: 'buy' | 'sell' | 'hold'
  trading_system?: '3l' | 'trend'
  buy_point: string
  stop_loss: number | null
  stop_loss_pct: number | null
  mainline_level: string
  triggered_signals: Array<{
    key: string
    name: string
    direction: 'bullish' | 'bearish' | 'neutral'
    confidence: number
    detail?: string
  }>
  fusion_type: string
  conclusion: string
}

interface HotStocksData {
  stocks: HotStockItem[]
  scan_time: string
  total: number
}

const PAGE_SIZE = 20

const SIGNAL_OPTIONS = ['全部', 'buy', 'hold', 'sell']
const STRUCT_OPTIONS = ['全部', '上涨趋势', '区间震荡', '下降趋势']
const SORT_OPTIONS = [
  { value: 'hot_rank', label: '热度排名' },
  { value: 'change', label: '涨跌幅' },
  { value: 'hot_value', label: '热度值' },
]

const SIGNAL_LABELS: Record<string, string> = {
  buy: '⚡买入',
  hold: '✅持有',
  sell: '❌卖出',
}

export default function HotStocks() {
  const [data, setData] = useState<HotStocksData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  const [watchlistCodes, setWatchlistCodes] = useState<Set<string>>(new Set())
  const [addingCodes, setAddingCodes] = useState<Set<string>>(new Set())

  // Filters
  const [signalFilter, setSignalFilter] = useState('全部')
  const [structFilter, setStructFilter] = useState('全部')
  const [buyOnly, setBuyOnly] = useState(false)
  const [mainlineOnly, setMainlineOnly] = useState(false)
  const [sortBy, setSortBy] = useState('hot_rank')
  const [page, setPage] = useState(1)

  useEffect(() => { loadData(); loadWatchlist() }, [])

  async function loadWatchlist() {
    try {
      const r = await fetch('/api/watchlist')
      if (!r.ok) return
      const d = await r.json()
      const stocks = Array.isArray(d) ? d : d.stocks || []
      setWatchlistCodes(new Set(stocks.map((s: any) => s.code)))
    } catch {}
  }

  async function addToWatchlist(code: string, name: string) {
    if (watchlistCodes.has(code)) return
    setAddingCodes(prev => new Set([...prev, code]))
    try {
      const r = await fetch('/api/watchlist/add-stock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, name }),
      })
      const d = await r.json()
      if (d.success) {
        setWatchlistCodes(prev => new Set([...prev, code]))
      }
    } catch {}
    setAddingCodes(prev => { const n = new Set(prev); n.delete(code); return n })
  }

  async function loadData() {
    setLoading(true); setError(''); setHint('加载中...')
    try {
      const r = await fetch('/api/hot-stocks?limit=100')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      if (d.error) throw new Error(d.error)
      setData(d)
      setHint(`共 ${d.stocks.length} 只热股`)
    } catch (err: any) {
      setError(err.message)
      setData(null)
      setHint('')
    } finally { setLoading(false) }
  }

  // Filter + sort
  const filtered = useMemo(() => {
    if (!data) return []
    let list = [...data.stocks]

    // Filter by signal
    if (signalFilter !== '全部') {
      list = list.filter(s => s.signal === signalFilter)
    }

    // Filter by structure
    if (structFilter !== '全部') {
      list = list.filter(s => s.structure === structFilter)
    }

    // Only buy signals
    if (buyOnly) {
      list = list.filter(s => s.signal === 'buy')
    }

    // Only mainline
    if (mainlineOnly) {
      list = list.filter(s => s.mainline_level === '主线' || s.mainline_level === '次级主线')
    }

    // Sort
    list.sort((a, b) => {
      if (sortBy === 'hot_rank') return (a.hot_rank || 999) - (b.hot_rank || 999)
      if (sortBy === 'change') return (b.change || 0) - (a.change || 0)
      if (sortBy === 'hot_value') return (b.hot_value || 0) - (a.hot_value || 0)
      return 0
    })

    return list
  }, [data, signalFilter, structFilter, buyOnly, mainlineOnly, sortBy])

  // Paginate
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [signalFilter, structFilter, buyOnly, mainlineOnly, sortBy])

  // Summary stats
  const stats = useMemo(() => {
    if (!data) return null
    const all = data.stocks
    const buyCount = all.filter(s => s.signal === 'buy').length
    const sellCount = all.filter(s => s.signal === 'sell').length
    const holdCount = all.filter(s => s.signal === 'hold').length
    const upCount = all.filter(s => (s.change || 0) >= 0).length
    const downCount = all.filter(s => (s.change || 0) < 0).length

    // Top sectors by frequency
    const sectorCount: Record<string, number> = {}
    all.forEach(s => {
      if (s.sector) {
        sectorCount[s.sector] = (sectorCount[s.sector] || 0) + 1
      }
    })
    const topSectors = Object.entries(sectorCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, count]) => ({ name, count }))

    return { buyCount, sellCount, holdCount, upCount, downCount, topSectors }
  }, [data])

  return (
    <div className="page-container">
      <NavBar />

      <div className="hot-header">
        <h1>🔥 热点个股追踪</h1>
        <div className="hot-subtitle">同花顺24h热股Top100 · 3L结构分析 · 买点筛选</div>
      </div>

      <div className="hot-container">
        {/* Controls */}
        <div className="hot-controls">
          <div className="hot-controls-row">
            <label>排序:</label>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
              {SORT_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <label>信号:</label>
            <select value={signalFilter} onChange={e => setSignalFilter(e.target.value)}>
              {SIGNAL_OPTIONS.map(o => (
                <option key={o} value={o}>{o === '全部' ? '全部' : SIGNAL_LABELS[o] || o}</option>
              ))}
            </select>

            <label>结构:</label>
            <select value={structFilter} onChange={e => setStructFilter(e.target.value)}>
              {STRUCT_OPTIONS.map(o => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>

            <label className="checkbox-label">
              <input type="checkbox" checked={buyOnly} onChange={e => setBuyOnly(e.target.checked)} />
              仅买点
            </label>

            <label className="checkbox-label">
              <input type="checkbox" checked={mainlineOnly} onChange={e => setMainlineOnly(e.target.checked)} />
              仅主线
            </label>
          </div>

          <div className="hot-controls-row2">
            <button className="btn-refresh" onClick={loadData} disabled={loading}>
              🔄 刷新
            </button>
            {data && (
              <span className="hot-scan-time">扫描时间: {data.scan_time}</span>
            )}
            <span className="loading-hint">{hint}</span>
          </div>
        </div>

        {/* Summary */}
        {stats && (
          <div className="hot-summary">
            <div className="summary-item">
              <div className="summary-label">总数量</div>
              <div className="summary-value">{data?.total || 0}</div>
            </div>
            <div className="summary-item">
              <div className="summary-label">⚡买入</div>
              <div className="summary-value buy">{stats.buyCount}</div>
            </div>
            <div className="summary-item">
              <div className="summary-label">✅持有</div>
              <div className="summary-value hold">{stats.holdCount}</div>
            </div>
            <div className="summary-item">
              <div className="summary-label">❌卖出</div>
              <div className="summary-value sell">{stats.sellCount}</div>
            </div>
            <div className="summary-item">
              <div className="summary-label">📈上涨</div>
              <div className="summary-value up">{stats.upCount}</div>
            </div>
            <div className="summary-item">
              <div className="summary-label">📉下跌</div>
              <div className="summary-value down">{stats.downCount}</div>
            </div>
            <div className="summary-item wide">
              <div className="summary-label">🏆 热门板块TOP3</div>
              <div className="summary-sectors">
                {stats.topSectors.map((s, i) => (
                  <span key={s.name} className="sector-tag">
                    {i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'}{s.name} {s.count}只
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Loading / Error */}
        {loading && <div className="loading-area">⏳ 正在获取热股数据+3L分析...</div>}
        {error && <div className="error-card">❌ {error}</div>}

        {/* Filter result info */}
        {data && !loading && !error && (
          <div className="hot-filter-info">
            筛选: {filtered.length} / {data.total} 只
            {signalFilter !== '全部' && ` · 信号=${signalFilter}`}
            {structFilter !== '全部' && ` · 结构=${structFilter}`}
            {buyOnly && ' · 仅买点'}
            {mainlineOnly && ' · 仅主线'}
          </div>
        )}

        {/* Stock List */}
        {paged.length > 0 && (
          <>
            <div className="hot-stock-grid">
              {paged.map((s, i) => (
                <div key={s.code} className="hot-stock-card-wrapper">
                  {/* Hot Rank Badge */}
                  <div className="hot-rank-badge">
                    <span className={`rank-badge rank-${s.hot_rank <= 3 ? 'top3' : s.hot_rank <= 10 ? 'top10' : 'normal'}`}>
                      #{s.hot_rank}
                    </span>
                    <span className="hot-value">🔥 {(s.hot_value / 10000).toFixed(0)}万</span>
                    {s.popularity_tag && (
                      <span className="popularity-tag">{s.popularity_tag}</span>
                    )}
                    {watchlistCodes.has(s.code) ? (
                      <span className="wl-added">✔ 已自选</span>
                    ) : (
                      <button
                        className="btn-add-wl"
                        onClick={() => addToWatchlist(s.code, s.name)}
                        disabled={addingCodes.has(s.code)}
                      >
                        {addingCodes.has(s.code) ? '...' : '+ 自选'}
                      </button>
                    )}
                  </div>

                  {/* Concept tags */}
                  {s.concept_tags && s.concept_tags.length > 0 && (
                    <div className="concept-tags">
                      {s.concept_tags.slice(0, 3).map((t, i) => (
                        <span key={i} className="concept-tag">{t}</span>
                      ))}
                      {s.concept_tags.length > 3 && (
                        <span className="concept-tag more">+{s.concept_tags.length - 3}</span>
                      )}
                    </div>
                  )}

                  <StockCard s={s} idx={i} chartPrefix="hot_" />
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>‹ 上一页</button>
                <span className="page-info">
                  {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => {
                    let pageNum: number
                    if (totalPages <= 10) {
                      pageNum = i + 1
                    } else if (page <= 5) {
                      pageNum = i + 1
                    } else if (page >= totalPages - 4) {
                      pageNum = totalPages - 9 + i
                    } else {
                      pageNum = page - 4 + i
                    }
                    return (
                      <span
                        key={pageNum}
                        className={`page-num ${pageNum === page ? 'active' : ''}`}
                        onClick={() => setPage(pageNum)}
                      >
                        {pageNum}
                      </span>
                    )
                  })}
                </span>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>下一页 ›</button>
              </div>
            )}
          </>
        )}

        {/* Empty result */}
        {data && filtered.length === 0 && !loading && !error && (
          <div className="error-card">
            没有符合条件的个股<br />
            <span style={{ fontSize: 12, color: '#666' }}>试试调整筛选条件</span>
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar, { BottomNav } from '../components/NavBar'
import './StrongTrendCandidates.css'

interface SectorInfo {
  type: string
  name: string
  chg_20d: number
  chg_5d: number
}

interface TrendMetrics {
  ema_alignment: string
  ema5_slope: number
  ema10_slope: number
  ema5: number
  ema10: number
  ema20: number
  price_vs_ema20_pct: number
}

interface AdjustmentQuality {
  max_drawdown_10d: number
  max_consecutive_down_10d: number
}

interface Candidate {
  code: string
  name: string
  price: number
  chg_1d: number
  chg_5d: number
  sectors: SectorInfo[]
  trend_metrics: TrendMetrics
  adjustment_quality: AdjustmentQuality
  score: number
  score_breakdown: { sector_strength: number; trend: number }
  signal: string
  signal_text: string
  buy_point: string
  stop_loss: number | null
  stop_loss_pct: number | null
  trading_system: string
  triggered_signals: string[]
  fusion_type: string
  mainline_level: string
  conclusion: string
}

interface TrendData {
  date: string
  top_industries: { name: string; chg_20d: number }[]
  hot_industries: { name: string; chg_5d: number }[]
  top_concepts: { name: string; chg_20d: number }[]
  hot_concepts: { name: string; chg_5d: number }[]
  candidates: Candidate[]
}

const ALIGNMENT_COLORS: Record<string, string> = {
  'bullish': '#4ecdc4',
  'partial': '#ffd700',
  'bearish': '#e94560',
}

const ALIGNMENT_LABELS: Record<string, string> = {
  'bullish': '多头排列',
  'partial': '偏多',
  'bearish': '空头排列',
}

export default function StrongTrendCandidates() {
  const navigate = useNavigate()
  const [data, setData] = useState<TrendData | null>(null)
  const [loading, setLoading] = useState(true)
  const [watchlistCodes, setWatchlistCodes] = useState<Set<string>>(new Set())
  const [addingCodes, setAddingCodes] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch('/api/strong-trend-candidates?limit=30')
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setData(d)
        }
      })
      .catch(e => console.error('Failed to load:', e))
      .finally(() => setLoading(false))
    loadWatchlist()
  }, [])

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

  if (loading) return (
    <div className="page-container">
      <NavBar />
      <div className="header">
        <h1>📈 强势趋势追踪</h1>
        <p className="subtitle">从强势板块筛选趋势完好的个股</p>
      </div>
      <div className="container">
        <div className="loading"><div className="spinner"></div><p>加载中...</p></div>
      </div>
      <BottomNav />
      <div className="footer">3L 交易体系 · 强势趋势追踪 · Hermes Agent</div>
    </div>
  )

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📈 强势趋势追踪</h1>
        <p className="subtitle">从强势板块筛选趋势完好的个股</p>
      </div>

      <div className="container">
        {data && (
          <>
          {/* 板块信息 */}
          <div className="section">
            <h2 className="section-title">🏭 强势行业</h2>
            <div className="sector-tags">
              {data.top_industries.map(s => (
                <span key={s.name} className="sector-tag">
                  {s.name} <span className="chg-up">+{s.chg_20d.toFixed(1)}%</span>
                </span>
              ))}
            </div>
          </div>

          <div className="section">
            <h2 className="section-title">🔥 活跃行业（5日）</h2>
            <div className="sector-tags">
              {data.hot_industries.map(s => (
                <span key={s.name} className="sector-tag">
                  {s.name} <span className="chg-up">+{s.chg_5d.toFixed(1)}%</span>
                </span>
              ))}
            </div>
          </div>

          <div className="section">
            <h2 className="section-title">💡 强势概念</h2>
            <div className="sector-tags">
              {data.top_concepts.map(s => (
                <span key={s.name} className="sector-tag concept-tag">
                  {s.name} <span className="chg-up">+{s.chg_20d.toFixed(1)}%</span>
                </span>
              ))}
            </div>
          </div>

          {/* 候选股列表 */}
          <div className="section">
            <h2 className="section-title">
              🎯 候选股 <span className="count-badge">{data.candidates.length}只</span>
            </h2>
            {data.candidates.length === 0 ? (
              <div className="empty">暂无符合条件的候选股</div>
            ) : (
              data.candidates.map(c => (
                <div key={c.code} className="candidate-card">
                  <div className="card-header">
                    <div className="card-score" style={{ color: c.score >= 8 ? '#4ecdc4' : c.score >= 6 ? '#ffd700' : '#e94560' }}>
                      {c.score.toFixed(1)}
                    </div>
                    <div className="card-name">
                      <span className="stock-name">{c.name}</span>
                      <span className="stock-code">{c.code}</span>
                      <span className="stock-price">¥{c.price.toFixed(2)}</span>
                      <span className={`chg-${c.chg_1d >= 0 ? 'up' : 'down'}`}>
                        {c.chg_1d >= 0 ? '+' : ''}{c.chg_1d.toFixed(2)}%
                      </span>
                    </div>
                    <div className="card-chg5d">
                      5日: <span className={`chg-${c.chg_5d >= 0 ? 'up' : 'down'}`}>
                        {c.chg_5d >= 0 ? '+' : ''}{c.chg_5d.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <div className="card-sectors">
                    {c.sectors.slice(0, 4).map(s => (
                      <span key={s.name} className={`sector-badge ${s.type === 'industry' ? 'industry-badge' : 'concept-badge'}`}>
                        {s.type === 'industry' ? '🏭' : '💡'} {s.name} {s.chg_20d > 0 ? `+${s.chg_20d.toFixed(1)}%` : ''}
                      </span>
                    ))}
                  </div>

                  <div className="card-metrics">
                    <div className="metric">
                      <span className="metric-label">趋势</span>
                      <span className="metric-val" style={{ color: ALIGNMENT_COLORS[c.trend_metrics.ema_alignment] || '#aaa' }}>
                        {ALIGNMENT_LABELS[c.trend_metrics.ema_alignment] || c.trend_metrics.ema_alignment}
                      </span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">EMA5斜率</span>
                      <span className={`metric-val ${c.trend_metrics.ema5_slope >= 0 ? 'chg-up' : 'chg-down'}`}>
                        {c.trend_metrics.ema5_slope.toFixed(2)}%
                      </span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">10日最大回撤</span>
                      <span className="metric-val chg-down">
                        {c.adjustment_quality.max_drawdown_10d.toFixed(1)}%
                      </span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">10日连跌</span>
                      <span className="metric-val">{c.adjustment_quality.max_consecutive_down_10d}天</span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">价/EMA20</span>
                      <span className={`metric-val ${c.trend_metrics.price_vs_ema20_pct >= 0 ? 'chg-up' : 'chg-down'}`}>
                        {c.trend_metrics.price_vs_ema20_pct >= 0 ? '+' : ''}{c.trend_metrics.price_vs_ema20_pct.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* 操作建议 */}
                  <div className="card-signal">
                    <span className={`sig-badge sig-${c.signal === 'buy' ? 'buy' : c.signal === 'sell' ? 'sell' : 'hold'}`}>
                      {c.signal === 'buy' ? '🔴 买入' : c.signal === 'sell' ? '🟢 卖出' : '⚪ 持有'}
                    </span>
                    {c.buy_point && <span className="sig-badge sig-point">{c.buy_point}</span>}
                    {c.trading_system === 'trend' ? (
                      <span className="sig-badge sig-trend">趋势</span>
                    ) : (
                      <span className="sig-badge sig-3l">3L</span>
                    )}
                    {c.mainline_level === '主线' && <span className="sig-badge sig-mainline">主线</span>}
                    {c.mainline_level === '次级主线' && <span className="sig-badge sig-submain">次级主线</span>}
                    {c.stop_loss_pct != null && (
                      <span className="sig-badge sig-sl">止损{c.stop_loss_pct.toFixed(1)}%</span>
                    )}
                  </div>
                  {c.conclusion && <div className="card-conclusion">{c.conclusion}</div>}

                  <div className="card-footer">
                    {watchlistCodes.has(c.code) ? (
                      <span className="wl-badge">✔ 已自选</span>
                    ) : (
                      <button
                        className="btn-add-wl-trend"
                        onClick={() => addToWatchlist(c.code, c.name)}
                        disabled={addingCodes.has(c.code)}
                      >
                        {addingCodes.has(c.code) ? '...' : '+ 自选'}
                      </button>
                    )}
                    <span className="analysis-link" onClick={() => navigate(`/stock_analysis?code=${c.code}`)}>🔍 个股分析</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}

    </div>
      <BottomNav />
      <div className="footer">3L 交易体系 · 强势趋势追踪 · Hermes Agent</div>
    </div>
  )
}

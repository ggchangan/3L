import { useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './StockAnalysis.css'

interface BacktestSignal {
  n: number; trading_system: string; date: string; type: string
  entry: number; exit_date: string; exit: number; days: number; gain: number
}

interface BacktestData {
  name: string; code: string; total: number; wins: number; losses: number
  win_rate: number; cumulative_return: number; avg_win: number; avg_loss: number
  has_chart: boolean; chart_svg?: string; signals: BacktestSignal[]
  error?: string
}

interface AnalysisData {
  code: string; name: string; price: number; change: number
  direction: string; sector: string
  structure: string; stage: string
  signal: string; buy_point: string
  profit_model1: boolean; trend_stock: boolean
  trading_system: string
  trend_buy?: { buy_type?: string; bias5?: number }
  [key: string]: any
}

const STAGE_COLORS: Record<string, string> = {
  '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700',
  '滞涨': '#ff6b6b', '转弱': '#ff6b6b', '下行': '#666',
  '加速跌': '#e94560', '转强': '#4ecdc4',
  '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560',
}

export default function StockAnalysis() {
  const [q, setQ] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null)
  const [btData, setBtData] = useState<BacktestData | null>(null)
  const [loading, setLoading] = useState(false)
  const [btLoading, setBtLoading] = useState(false)
  const [error, setError] = useState('')
  const [btError, setBtError] = useState('')
  const [chartOpen, setChartOpen] = useState(true)
  const lastCode = useRef('')

  async function search() {
    if (!q.trim()) return
    setLoading(true); setError(''); setAnalysis(null)
    try {
      const r = await fetch(`/api/stock-analysis?q=${encodeURIComponent(q.trim())}`)
      const d = await r.json()
      if (d.error) { setError(d.error); return }
      lastCode.current = d.code
      setAnalysis(d)
    } catch (err: any) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  async function runBacktest() {
    const code = lastCode.current || q.trim()
    if (!code) return
    setBtLoading(true); setBtError(''); setBtData(null)
    try {
      const r = await fetch(`/api/stock-backtest?code=${encodeURIComponent(code)}&days=60`)
      const d = await r.json()
      if (d.error) { setBtError(d.error); return }
      setBtData(d)
    } catch (err: any) {
      setBtError(err.message)
    } finally { setBtLoading(false) }
  }

  function renderCard(d: AnalysisData) {
    const signal = d.signal || 'hold'
    const signalLabel: Record<string, string> = { buy: '买入', hold: '持有', sell: '卖出', warn: '观望' }
    const signalBarCls = signal === 'buy' ? 'buy' : signal === 'hold' ? 'hold' : signal === 'warn' ? 'warn' : 'none'
    const changeCls = (d.change || 0) >= 0 ? 'up' : 'down'

    return (
      <div className="result-card">
        {/* Signal bar */}
        <div className={`signal-bar ${signalBarCls}`}>
          {signal === 'buy' ? '🟢' : signal === 'hold' ? '🟡' : signal === 'warn' ? '🟠' : '⚪'} {signalLabel[signal] || signal}
          {d.buy_point ? ` · ${d.buy_point}` : ''}
        </div>

        {/* Header */}
        <div className="result-header">
          <div>
            <span className="stock-name">{d.name}</span>
            <span className="stock-code">{d.code}</span>
          </div>
          <div className="stock-price">{d.price?.toFixed(2)}</div>
        </div>

        {/* Tags */}
        <div className="tags">
          {d.sector && <span className="tag">{d.sector}</span>}
          {d.direction && <span className="tag">{d.direction}</span>}
          {d.structure && <span className="tag">{d.structure}</span>}
          {d.stage && <span className="tag" style={{ color: STAGE_COLORS[d.stage] || '#888' }}>{d.stage}</span>}
          {d.trend_stock && <span className="tag trend-tag">趋势股</span>}
          {d.profit_model1 && <span className="tag pmi-tag">盈利模式1</span>}
          {d.trend_buy?.buy_type && <span className="tag trend-buy-tag">{d.trend_buy.buy_type}</span>}
        </div>

        {/* Info grid */}
        <div className="info-grid">
          <div className="info-item">
            <div className="l">涨跌幅</div>
            <div className={`v ${changeCls === 'up' ? 'good' : 'bad'}`}>
              {(d.change || 0) >= 0 ? '+' : ''}{(d.change || 0).toFixed(2)}%
            </div>
          </div>
          <div className="info-item">
            <div className="l">交易系统</div>
            <div className="v normal">{d.trading_system === 'trend' ? '🎯 趋势交易' : '📊 3L体系'}</div>
          </div>
          <div className="info-item">
            <div className="l">K线结构</div>
            <div className="v normal">{d.structure || '--'}</div>
          </div>
          <div className="info-item">
            <div className="l">当前阶段</div>
            <div className="v normal" style={{ color: STAGE_COLORS[d.stage] || '#e0e0e0' }}>{d.stage || '--'}</div>
          </div>
          <div className="info-item">
            <div className="l">BIAS5</div>
            <div className="v normal">{d.trend_buy?.bias5 !== undefined ? d.trend_buy.bias5.toFixed(2) + '%' : '--'}</div>
          </div>
        </div>

        {/* Chart */}
        {d.chart_svg && (
          <div className="chart-section">
            <details open={chartOpen} onToggle={e => setChartOpen((e.target as HTMLDetailsElement).open)}>
              <summary>📊 K线图（含关键点标注）</summary>
              <object data={`${d.chart_svg}?t=${Date.now()}`} type="image/svg+xml" style={{ width: '100%', borderRadius: 8 }} />
            </details>
          </div>
        )}

        {/* Detail table */}
        <div className="detail-section">
          <h3>📋 详细数据</h3>
          <table className="detail-table">
            <tbody>
              <tr><td>股票名称</td><td>{d.name || '--'}</td></tr>
              <tr><td>股票代码</td><td>{d.code || '--'}</td></tr>
              <tr><td>当前价格</td><td>{d.price?.toFixed(2) || '--'}</td></tr>
              <tr><td>所属行业</td><td>{d.sector || '--'}</td></tr>
              <tr><td>所属方向</td><td>{d.direction || '--'}</td></tr>
              <tr><td>交易系统</td><td>{d.trading_system || '--'}</td></tr>
              <tr><td>买点信号</td><td>{d.buy_point || '--'}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  function renderBacktest(d: BacktestData) {
    const totalCls = d.cumulative_return > 0 ? 'good' : 'bad'
    return (
      <div className="bt-summary">
        <div className="bt-header">
          <div>
            <span className="bt-name">{d.name}</span>
            <span className="bt-code">{d.code}</span>
          </div>
          <span className="bt-label">60天回测</span>
        </div>

        <div className="bt-stats">
          <div className="bt-stat"><div className="l">信号</div><div className="v">{d.total}笔</div></div>
          <div className="bt-stat"><div className="l">盈利</div><div className="v" style={{ color: '#4ecdc4' }}>{d.wins}</div></div>
          <div className="bt-stat"><div className="l">亏损</div><div className="v" style={{ color: '#e94560' }}>{d.losses}</div></div>
          <div className="bt-stat"><div className="l">胜率</div><div className="v">{d.win_rate}%</div></div>
          <div className="bt-stat"><div className="l">累计收益</div><div className={`v ${totalCls}`}>{d.cumulative_return > 0 ? '+' : ''}{d.cumulative_return}%</div></div>
          <div className="bt-stat"><div className="l">均盈/亏</div><div className="v" style={{ fontSize: 14 }}><span style={{ color: '#4ecdc4' }}>+{d.avg_win}%</span> / <span style={{ color: '#e94560' }}>{d.avg_loss}%</span></div></div>
        </div>

        {d.has_chart && (
          <div className="bt-chart">
            <details open>
              <summary>📊 K线图（含买卖标注）</summary>
              <object data={`${d.chart_svg}?t=${Date.now()}`} type="image/svg+xml" style={{ width: '100%', borderRadius: 8 }} />
            </details>
          </div>
        )}

        <h3 className="bt-section-title">📋 交易明细</h3>
        <table className="bt-table">
          <thead><tr><th>#</th><th>系统</th><th>入场日</th><th>类型</th><th>入场价</th><th>出场日</th><th>出场价</th><th>持有</th><th>盈亏</th></tr></thead>
          <tbody>
            {d.signals.map((s, i) => {
              const clr = s.gain > 0 ? '#4ecdc4' : '#e94560'
              const sysLabel = s.trading_system === 'trend'
                ? <span className="tag" style={{ background: '#4ecdc4', color: '#000' }}>趋势</span>
                : <span className="tag" style={{ background: '#e94560', color: '#fff' }}>3L</span>
              const typeCls = s.type.includes('突破') ? 'red' : s.type.includes('BIAS') ? 'green' : 'yellow'
              return (
                <tr key={i}>
                  <td>{s.n}</td>
                  <td>{sysLabel}</td>
                  <td>{s.date?.substring(5, 10) || '--'}</td>
                  <td><span className={`tag ${typeCls}`}>{s.type}</span></td>
                  <td>{s.entry?.toFixed(2) || '--'}</td>
                  <td>{s.exit_date?.substring(5, 10) || '--'}</td>
                  <td>{s.exit?.toFixed(2) || '--'}</td>
                  <td>{s.days || '--'}天</td>
                  <td style={{ color: clr, fontWeight: 600 }}>{s.gain > 0 ? '✅' : '❌'} {s.gain >= 0 ? '+' : ''}{s.gain}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📊 个股买点检测</h1>
        <div className="sub">输入股票代码或名称，查看3L量价分析</div>
      </div>

      <div className="container">
        {/* Search Box */}
        <div className="search-box">
          <input
            type="text"
            placeholder="股票代码（如 688126）或名称（如 沪硅产业）"
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') search() }}
          />
          <button onClick={search} disabled={loading}>分析</button>
          <button className="bt-btn" onClick={runBacktest} disabled={btLoading}>📊 回测</button>
        </div>

        {/* Analysis Result */}
        <div id="resultArea">
          {loading && <div className="loading"><div className="spinner"></div>正在分析...</div>}
          {error && <div className="error-box">❌ {error}</div>}
          {!loading && !error && analysis && renderCard(analysis)}
          {!loading && !error && !analysis && (
            <div className="no-result">输入股票代码或名称开始分析</div>
          )}
        </div>

        {/* Backtest Result */}
        <div id="btResultArea">
          {btLoading && <div className="loading"><div className="spinner"></div>正在跑回测...</div>}
          {btError && <div className="error-box">❌ {btError}</div>}
          {!btLoading && !btError && btData && renderBacktest(btData)}
        </div>

        <div className="hint">数据来源：all_stocks_60d.json · 3L量价择时系统</div>
      </div>

      <BottomNav />
    </div>
  )
}

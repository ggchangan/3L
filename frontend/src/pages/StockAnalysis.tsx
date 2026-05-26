import { useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import StockCard from '../components/StockCard'
import type { BuySignalItem } from '../lib/types'
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
  direction: string; sector: string; sector_chg?: number
  deviation_pct?: number
  structure: string; stage: string
  signal: string; buy_point: string
  profit_model1: boolean; trend_stock: boolean
  trading_system: string
  trend_buy?: { buy_type?: string; bias5?: number }
  [key: string]: any
}

export default function StockAnalysis() {
  const [q, setQ] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null)
  const [btData, setBtData] = useState<BacktestData | null>(null)
  const [loading, setLoading] = useState(false)
  const [btLoading, setBtLoading] = useState(false)
  const [error, setError] = useState('')
  const [btError, setBtError] = useState('')
  const lastCode = useRef('')

  async function search() {
    if (!q.trim()) return
    setLoading(true); setError(''); setAnalysis(null)
    try {
      const url = `/api/stock-analysis?q=${encodeURIComponent(q.trim())}`
      console.log('🔍 fetching:', url)
      const r = await fetch(url, { method: 'GET', credentials: 'same-origin' })
      console.log('🔍 response status:', r.status, r.statusText)
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`)
      let d
      try { d = await r.json() } catch (e) { throw new Error(`JSON解析失败: ${await r.text().catch(()=>'')}`) }
      if (d.error) { setError(d.error); return }
      lastCode.current = d.code
      setAnalysis(d)
    } catch (err: any) {
      console.error('🔍 fetch error:', err)
      setError(`请求失败: ${err.message}`)
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

  /** AnalysisData → BuySignalItem 适配 */
  function toBuySignalItem(d: AnalysisData): BuySignalItem {
    return {
      code: d.code,
      name: d.name,
      signal: (d.signal || 'hold') as 'buy' | 'sell' | 'hold',
      stage: d.stage,
      structure: d.structure,
      trading_system: d.trading_system as '3l' | 'trend' | undefined,
      buy_point: d.buy_point,
      stop_loss: d.stop_loss != null ? parseFloat(String(d.stop_loss)) : undefined,
      stop_loss_pct: d.stop_loss_pct != null ? parseFloat(String(d.stop_loss_pct)) : undefined,
      profit_model1: d.profit_model1,
      trend_stock: d.trend_stock,
      trend_bias: d.trend_bias ?? undefined,
      direction: d.direction,
      change: d.change ?? undefined,
      price: d.price ?? undefined,
      sector: d.sector ?? '',
      sector_chg: d.sector_chg ?? undefined,
      mainline_level: d.mainline_level,
    }
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
          {!loading && !error && analysis && <StockCard s={toBuySignalItem(analysis)} idx={0} />}
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

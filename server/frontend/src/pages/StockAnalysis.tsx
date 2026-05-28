import { useState, useRef, useEffect } from 'react'
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
  const [searchResults, setSearchResults] = useState<any[]>([])
  const lastCode = useRef('')
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()

  // 自动补全搜索（支持代码/名称/拼音首字母）
  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!q || q.length < 1) { setSearchResults([]); return }
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await fetch(`/api/watchlist/search?q=${encodeURIComponent(q)}`)
        const data = await r.json()
        setSearchResults(data.results || [])
      } catch { setSearchResults([]) }
    }, 200)
    return () => clearTimeout(searchTimer.current)
  }, [q])

  async function doSearch(code?: string) {
    const query = code || q.trim()
    if (!query) return
    setLoading(true); setError(''); setAnalysis(null); setSearchResults([])
    try {
      const url = `/api/stock-analysis?q=${encodeURIComponent(query)}`
      const r = await fetch(url, { method: 'GET', credentials: 'same-origin' })
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`)
      let d
      try { d = await r.json() } catch (e) { throw new Error(`JSON解析失败: ${await r.text().catch(()=>'')}`) }
      if (d.error) { setError(d.error); return }
      lastCode.current = d.code
      setAnalysis(d)
    } catch (err: any) {
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

  /** 诊断渲染 */
  function renderDiagnosis(a: any) {
    if (!a || !a.diagnosis) return null
    const di = a.diagnosis
    if (di.error) return <div className="error-box" style={{ marginBottom: 12, fontSize: 12 }}>诊断异常: {di.error}</div>
    const det = di.detail || {}
    const gradeColor = di.grade === 'A' ? '#4ecdc4' : di.grade === 'B' ? '#22c55e' : di.grade === 'C' ? '#f59e0b' : '#e94560'
    const gradeLabel = di.grade === 'A' ? '优秀' : di.grade === 'B' ? '良好' : di.grade === 'C' ? '一般' : '较差'

    const dims = [
      { icon: '📊', label: '趋势面', score: det.trend?.score ?? 0, remarks: det.trend?.remarks ?? [] },
      { icon: '💰', label: '财务面', score: det.financial?.score ?? 0, remarks: det.financial?.remarks ?? [] },
      { icon: '🛡️', label: '风险面', score: det.risk?.score ?? 0, remarks: det.risk?.items ?? [], riskLevel: det.risk?.level },
      { icon: '📰', label: '消息面', status: 'coming_soon' },
    ]

    const strengths: string[] = []
    const warnings: string[] = []
    det.financial?.remarks?.forEach((r: string) => {
      if (r.includes('优秀') || r.includes('良好') || r.includes('高速') || r.includes('稳健') || r.includes('健康')) strengths.push(r)
      else if (r.includes('偏低') || r.includes('下滑') || r.includes('偏高')) warnings.push(r)
    })
    det.trend?.remarks?.forEach((r: string) => {
      if (r.includes('+')) strengths.push(r.replace(/ [+-]\d+$/, ''))
      else warnings.push(r.replace(/ [-]\d+$/, ''))
    })
    det.risk?.items?.forEach((r: string) => warnings.push(r))

    return (
      <div className="diagnosis-section">
        <div className="diagnosis-bar">
          <span className="diagnosis-score" style={{ color: gradeColor }}>{di.total_score}</span>
          <span className="diagnosis-grade" style={{ background: gradeColor }}>{di.grade}</span>
          <span className="diagnosis-label">{gradeLabel} · {a.name}</span>
          <span className="diagnosis-cost">{di.cost_ms}ms</span>
        </div>
        <div className="diagnosis-cards">
          {dims.map((dim, i) => {
            if (dim.status === 'coming_soon') {
              return (
                <div key={i} className="diagnosis-card soon">
                  <div className="dc-icon">{dim.icon}</div>
                  <div className="dc-label">{dim.label}</div>
                  <div className="dc-placeholder">即将上线</div>
                </div>
              )
            }
            return (
              <div key={i} className="diagnosis-card">
                <div className="dc-icon">{dim.icon}</div>
                <div className="dc-label">{dim.label}</div>
                <div className="dc-score">{dim.score}/40</div>
                {dim.riskLevel && <div className="dc-risk" style={{ color: dim.riskLevel === '低风险' ? '#4ecdc4' : dim.riskLevel === '中风险' ? '#f59e0b' : '#e94560' }}>{dim.riskLevel}</div>}
                <div className="dc-remarks">
                  {dim.remarks.slice(0, 2).map((r, j) => (
                    <div key={j} className="dc-remark">{r}</div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
        {(strengths.length > 0 || warnings.length > 0) && (
          <div className="diagnosis-summary">
            {strengths.length > 0 && <div className="ds-s">✅ {strengths.slice(0, 3).join(' · ')}</div>}
            {warnings.length > 0 && <div className="ds-w">⚠️ {warnings.slice(0, 3).join(' · ')}</div>}
          </div>
        )}
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
          <div className="search-box-input" style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              placeholder="股票代码（如 688126）或名称（如 沪硅产业）"
              value={q}
              onChange={e => setQ(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') doSearch() }}
              onBlur={() => setTimeout(() => setSearchResults([]), 200)}
              style={{ width: '100%' }}
            />
            {searchResults.length > 0 && (
              <div className="sa-search-results">
                {searchResults.map((st: any, i) => (
                  <div key={i} className="sa-search-item"
                    onMouseDown={() => {
                      setQ(st.code)
                      doSearch(st.code)
                    }}>
                    <span><span className="sr-name">{st.name}</span> <span className="sr-code">{st.code}</span></span>
                    <span className="sr-ind">{st.direction || ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => doSearch()} disabled={loading}>分析</button>
          <button className="bt-btn" onClick={runBacktest} disabled={btLoading}>📊 回测</button>
        </div>

        {/* 诊断区块 */}
        {!loading && !error && analysis && renderDiagnosis(analysis)}

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

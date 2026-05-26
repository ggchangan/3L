import { useEffect, useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './Macro.css'

interface IndexData {
  price: number; change_pct: number; high?: number; low?: number
  prev_close?: number; time?: string
}

interface FxData {
  price: number; change_pct: number; time?: string
}

interface CpiData {
  date: string; value: number | null; forecast?: number | null; previous?: number | null
}

interface PpiData {
  date: string; value: number | null
}

interface MacroData {
  updated?: string; indices?: Record<string, IndexData>
  fx?: Record<string, FxData>; cpi?: CpiData[]; ppi?: PpiData[]
}

export default function Macro() {
  const [data, setData] = useState<MacroData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => { loadData(); return () => clearTimeout(timerRef.current) }, [])

  async function loadData() {
    try {
      const r = await fetch('/api/macro')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d: MacroData = await r.json()
      if ((d as any).error) throw new Error((d as any).error)
      setData(d)
      setLoading(false)
      // Auto-refresh every 30 seconds
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(loadData, 30000)
    } catch (err: any) {
      setError(err.message)
      setLoading(false)
    }
  }

  const indices = data?.indices || {}
  const fx = data?.fx || {}
  const cpi = data?.cpi || []
  const ppi = data?.ppi || []

  function renderIndexCard(name: string, idx: IndexData | undefined, showHighLow: boolean) {
    if (!idx) return null
    const cls = idx.change_pct >= 0 ? 'up' : 'down'
    const arrow = idx.change_pct >= 0 ? '▲' : '▼'
    return (
      <div className="index-card" key={name}>
        <div className="name">{name}</div>
        <div className="price">{idx.price.toFixed(2)}</div>
        <div className={`change ${cls}`}>{arrow} {idx.change_pct >= 0 ? '+' : ''}{idx.change_pct.toFixed(2)}%</div>
        {showHighLow && (
          <div className="highlow">
            <span>高 <span className="hl-up">{idx.high ? idx.high.toFixed(2) : '-'}</span></span>
            <span>低 <span className="hl-down">{idx.low ? idx.low.toFixed(2) : '-'}</span></span>
          </div>
        )}
        {!showHighLow && (
          <div className="range">前收 {idx.prev_close?.toFixed(2)}</div>
        )}
        <div className="time">{idx.time || ''}</div>
      </div>
    )
  }

  function renderCpiBars(dataArr: { date: string; value: number | null }[], scale: number) {
    return (
      <div className="cpi-bars">
        {dataArr.map((d, i) => {
          const v = d.value
          if (v === null || v === undefined) {
            return <div key={i} className="cpi-bar-empty" title="无数据" />
          }
          const barH = Math.max(4, Math.abs(v) * scale)
          const barBg = v >= 0 ? '#e94560' : '#4CAF50'
          return (
            <div key={i} className="cpi-bar-col">
              <span className="cpi-bar-label">{v.toFixed(1)}</span>
              <div className="cpi-bar-rect" style={{ height: `${barH}px`, background: barBg }} />
            </div>
          )
        })}
      </div>
    )
  }

  function renderCpiDateLabels(dataArr: { date: string }[], format: 'mm' | 'mon') {
    return (
      <div className="cpi-date-labels">
        {dataArr.map((d, i) => (
          <span key={i}>{format === 'mm' ? (d.date || '').slice(5, 7) + '月' : (d.date || '').slice(-2)}</span>
        ))}
      </div>
    )
  }

  // A股大盘
  const aShares = ['上证指数', '深证成指', '创业板指', '沪深300', '中证全指', '科创50']
  // 全球市场
  const globals = ['标普500', '纳斯达克', '道琼斯']
  // 汇率
  const fxPairs = [
    { key: '在岸人民币', cn: '美元/人民币', symbol: 'USDCNY' },
    { key: '欧元', cn: '欧元/人民币', symbol: 'EURCNY' },
    { key: '英镑', cn: '英镑/人民币', symbol: 'GBPCNY' },
    { key: '日元', cn: '100日元/人民币', symbol: 'JPYCNY' },
  ]

  const aCount = aShares.filter(n => indices[n]).length

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>🌍 宏观环境监控</h1>
        <div className="subtitle">A股大盘 · 全球指数 · 宏观数据 · 汇率</div>
        <div className="update-time">{data?.updated ? `更新于 ${data.updated}` : '—'}</div>
      </div>

      <div className="container">
        {loading && (
          <div className="loading" id="loading">
            <div className="spinner"></div>
            <p>正在获取宏观数据...</p>
          </div>
        )}

        {error && (
          <div className="loading" id="loading">
            <div className="error-card">❌ 加载失败: {error}</div>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {/* 1. A股大盘 */}
            <div className="section">
              <div className="section-title">
                📈 A股大盘 <span className="badge">{aCount}/6</span>
              </div>
              <div className="grid-4">
                {aShares.map(name => renderIndexCard(name, indices[name], true))}
              </div>
            </div>

            {/* 2. 全球市场 */}
            <div className="section">
              <div className="section-title">
                🌎 全球市场 <span className="badge">美股</span>
              </div>
              <div className="grid-3">
                {globals.map(name => renderIndexCard(name, indices[name], false))}
              </div>
              {globals.every(n => !indices[n]) && (
                <div className="error-card">美股非交易时段或无数据</div>
              )}
            </div>

            {/* 3. CPI */}
            <div className="section">
              <div className="section-title">
                📊 宏观数据 <span className="badge">CPI</span>
              </div>
              {cpi.length > 0 ? (
                <>
                  <div className="cpi-top-row">
                    <div className="risk-item">
                      <div className="label">最新CPI</div>
                      <div className={`value ${cpi[cpi.length - 1].value !== null && cpi[cpi.length - 1].value !== undefined ? ((cpi[cpi.length - 1].value as number) >= 0 ? 'cpi-positive' : 'cpi-negative') : ''}`}>
                        {cpi[cpi.length - 1].value !== null && cpi[cpi.length - 1].value !== undefined
                          ? `${(cpi[cpi.length - 1].value as number).toFixed(1)}%`
                          : '—'}
                      </div>
                      <div className="sub">{cpi[cpi.length - 1].date || ''}</div>
                    </div>
                    <div className="risk-item" style={{ flex: 2 }}>
                      <div className="label">近12个月走势</div>
                      {renderCpiBars(cpi, 12)}
                      {renderCpiDateLabels(cpi, 'short')}
                    </div>
                  </div>
                  <table className="cpi-table">
                    <thead>
                      <tr><th>日期</th><th>今值(%)</th><th>预测值(%)</th><th>前值(%)</th></tr>
                    </thead>
                    <tbody>
                      {cpi.slice().reverse().map((d, i) => {
                        const vCls = d.value !== null && d.value !== undefined ? ((d.value as number) >= 0 ? 'cpi-positive' : 'cpi-negative') : ''
                        return (
                          <tr key={i}>
                            <td>{d.date || '—'}</td>
                            <td className={vCls}>{d.value !== null && d.value !== undefined ? (d.value as number).toFixed(1) : '—'}</td>
                            <td>{d.forecast !== null && d.forecast !== undefined ? (d.forecast as number).toFixed(1) : '—'}</td>
                            <td>{d.previous !== null && d.previous !== undefined ? (d.previous as number).toFixed(1) : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="error-card">暂无CPI数据</div>
              )}
            </div>

            {/* 4. PPI */}
            <div className="section">
              <div className="section-title">
                📊 宏观数据 <span className="badge">PPI</span>
              </div>
              {ppi.length > 0 ? (
                <>
                  <div className="cpi-top-row">
                    <div className="risk-item">
                      <div className="label">最新PPI同比</div>
                      <div className={`value ${ppi[0].value !== null && ppi[0].value !== undefined ? ((ppi[0].value as number) >= 0 ? 'cpi-positive' : 'cpi-negative') : ''}`}>
                        {ppi[0].value !== null && ppi[0].value !== undefined
                          ? `${(ppi[0].value as number).toFixed(1)}%`
                          : '—'}
                      </div>
                      <div className="sub">{ppi[0].date || ''}</div>
                    </div>
                    <div className="risk-item" style={{ flex: 2 }}>
                      <div className="label">近12个月走势</div>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 60, padding: '8px 4px 0' }}>
                        {ppi.slice().reverse().map((d, i) => {
                          const v = d.value
                          if (v === null || v === undefined) return <div key={i} style={{ flex: 1, height: 8, background: '#2a2a4e', borderRadius: 2 }} title="无数据" />
                          const barH = Math.max(4, Math.abs(v) * 8)
                          const barBg = v >= 0 ? '#e94560' : '#4CAF50'
                          return (
                            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <span style={{ fontSize: 9, color: '#888', marginBottom: 2 }}>{v.toFixed(1)}</span>
                              <div style={{ width: '100%', height: `${barH}px`, background: barBg, borderRadius: '2px 2px 0 0', opacity: 0.7 }} />
                            </div>
                          )
                        })}
                      </div>
                      <div className="sub" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#555', padding: '2px 4px 0' }}>
                        {ppi.slice().reverse().map((d, i) => <span key={i}>{(d.date || '').slice(5, 7)}月</span>)}
                      </div>
                    </div>
                  </div>
                  <table className="cpi-table">
                    <thead><tr><th>月份</th><th>同比增长(%)</th></tr></thead>
                    <tbody>
                      {ppi.map((d, i) => {
                        const vCls = d.value !== null && d.value !== undefined ? ((d.value as number) >= 0 ? 'cpi-positive' : 'cpi-negative') : ''
                        return (
                          <tr key={i}>
                            <td>{d.date || '—'}</td>
                            <td className={vCls}>{d.value !== null && d.value !== undefined ? (d.value as number).toFixed(1) : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="error-card">暂无PPI数据</div>
              )}
            </div>

            {/* 5. 汇率 */}
            <div className="section">
              <div className="section-title">
                💱 汇率 <span className="badge">人民币中间价</span>
              </div>
              <div className="grid-2">
                {fxPairs.map(pair => {
                  let d = fx[pair.key]
                  if (!d) {
                    for (const [k, v] of Object.entries(fx)) {
                      if (k.includes(pair.key)) { d = v; break }
                    }
                  }
                  if (!d) {
                    return (
                      <div className="fx-card" key={pair.key}>
                        <div className="left">
                          <div className="name">{pair.cn}</div>
                          <div className="pair">{pair.symbol}</div>
                        </div>
                        <div className="right">
                          <div className="price">—</div>
                          <div className="change" style={{ color: '#666' }}>暂无数据</div>
                        </div>
                      </div>
                    )
                  }
                  const cls = d.change_pct >= 0 ? 'up' : 'down'
                  const arrow = d.change_pct >= 0 ? '▲' : '▼'
                  return (
                    <div className="fx-card" key={pair.key}>
                      <div className="left">
                        <div className="name">{pair.cn}</div>
                        <div className="pair">{pair.symbol} · {d.time || ''}</div>
                      </div>
                      <div className="right">
                        <div className="price">{d.price.toFixed(4)}</div>
                        <div className={`change ${cls}`}>{arrow} {d.change_pct >= 0 ? '+' : ''}{d.change_pct.toFixed(4)}%</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Footer */}
            <div style={{ textAlign: 'center', padding: 20, color: '#333', fontSize: 12 }}>
              数据来源: 腾讯财经 · 新浪财经 · akshare | 自动刷新
            </div>
          </>
        )}
      </div>

      <BottomNav />
    </div>
  )
}

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

interface UsStockData {
  price: number; change_pct: number; name: string; code?: string; time?: string
}

interface AbnormalAlert {
  name: string; code: string; change_pct: number; level: string; impact: string
}

interface AnalyzeResult {
  success: boolean; code?: string; name?: string; change_pct?: number
  news?: { title: string; time: string; source: string; url: string }[]
  summary?: string; related_a_shares?: string[]; error?: string
}

interface ExternalAsiaIndex {
  code: string; name: string; region: string; flag?: string
}

interface ExternalStock {
  code: string; name: string; impact?: string; sectors?: string
  suppliers?: string; potential?: string; counterparts?: string
}

interface ExternalCategory {
  name: string; stocks: ExternalStock[]
}

interface ExternalData {
  updated?: string; source?: string; source_url?: string
  asia_indices?: ExternalAsiaIndex[]
  categories?: ExternalCategory[]
}

interface PanicTrigger {
  index: string; change_pct: number; threshold: number; level: string
}

interface PanicPath {
  name: string; probability: number; action: string
}

interface PanicStrategy {
  paths: PanicPath[]; principle: string
}

interface PanicHistoryItem {
  date: string; time: string; level: string; trigger: string
}

interface PanicMonitor {
  level: string | null; triggered_at: string | null
  triggers: PanicTrigger[]
  strategy: PanicStrategy | Record<string, never>
  history: PanicHistoryItem[]
}

interface MacroData {
  updated?: string; indices?: Record<string, IndexData>
  fx?: Record<string, FxData>; cpi?: CpiData[]; ppi?: PpiData[]
  us_stocks?: Record<string, UsStockData>
  external?: ExternalData
  abnormal_alerts?: AbnormalAlert[]
  panic_monitor?: PanicMonitor
}

export default function Macro() {
  const [data, setData] = useState<MacroData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const [catOpen, setCatOpen] = useState<Record<string, boolean>>({})
  const [stockExpand, setStockExpand] = useState<Record<string, boolean>>({})
  const [modalShow, setModalShow] = useState(false)
  const [modalStock, setModalStock] = useState<AbnormalAlert | null>(null)
  const [modalResult, setModalResult] = useState<AnalyzeResult | null>(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState('')

  useEffect(() => { loadData(); return () => clearTimeout(timerRef.current) }, [])

  async function loadData() {
    try {
      const r = await fetch('/api/macro')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d: MacroData = await r.json()
      if ((d as any).error) throw new Error((d as any).error)
      setData(d)
      setLoading(false)
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
  const usStocks = data?.us_stocks || {}
  const extAsia = data?.external?.asia_indices || []
  const extCats = data?.external?.categories || []
  const abnormalAlerts = data?.abnormal_alerts || []
  const panicMon = data?.panic_monitor

  async function handleAnalyze(alert: AbnormalAlert) {
    setModalStock(alert)
    setModalResult(null)
    setModalError('')
    setModalLoading(true)
    setModalShow(true)
    try {
      const r = await fetch('/api/macro/analyze-abnormal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: alert.code, name: alert.name, change_pct: alert.change_pct }),
      })
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const result: AnalyzeResult = await r.json()
      if (!result.success) throw new Error(result.error || '分析失败')
      setModalResult(result)
    } catch (err: any) {
      setModalError(err.message)
    } finally {
      setModalLoading(false)
    }
  }

  function renderIndexCard(name: string, idx: IndexData | undefined, showHighLow: boolean) {
    if (!idx) return null
    const cls = idx.change_pct >= 0 ? 'up' : 'down'
    const arrow = idx.change_pct >= 0 ? '▲' : '▼'
    return (
      <div className="index-card" key={name}>
        <div className="name">{name}</div>
        <div className="price">{idx.price.toFixed(2)}</div>
        <div className={`change ${cls}`}>{arrow} {idx.change_pct >= 0 ? '+' : ''}{idx.change_pct.toFixed(2)}%</div>
        {showHighLow ? (
          <div className="highlow">
            <span>高 <span className="hl-up">{idx.high ? idx.high.toFixed(2) : '-'}</span></span>
            <span>低 <span className="hl-down">{idx.low ? idx.low.toFixed(2) : '-'}</span></span>
          </div>
        ) : (
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
          if (v === null || v === undefined) return <div key={i} className="cpi-bar-empty" title="无数据" />
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

  // A股大盘
  const aShares = ['上证指数', '深证成指', '创业板指', '沪深300', '中证全指', '科创50']
  // 全球市场（含外围指数）
  const globals = ['标普500', '纳斯达克', '道琼斯', '费城半导体', '罗素2000']

  const aCount = aShares.filter(n => indices[n]).length

  // 亚洲指数仿真数据（显示静态信息，不含实时行情）
  const asiaIndices = extAsia

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>🌍 宏观环境监控</h1>
        <div className="subtitle">A股大盘 · 全球指数 · 宏观数据 · 汇率 · 外围映射</div>
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
                🌎 全球市场 <span className="badge">美股指数</span>
              </div>
              <div className="grid-3">
                {globals.map(name => renderIndexCard(name, indices[name], false))}
              </div>
              {globals.every(n => !indices[n]) && (
                <div className="error-card">美股非交易时段或无数据</div>
              )}
            </div>

            {/* 3. 亚洲市场参考 */}
            {asiaIndices.length > 0 && (
              <div className="section">
                <div className="section-title">
                  🌏 亚洲市场参考
                </div>
                <div className="ext-index-grid">
                  <div className="ext-index-col">
                    {asiaIndices.slice(0, Math.ceil(asiaIndices.length / 2)).map((idx, i) => (
                      <div key={i} className="idx-row">
                        <span className="idx-flag">{idx.flag || '🌏'}</span>
                        <span className="idx-name">{idx.name}</span>
                        <span className="idx-region">{idx.region}</span>
                        <span className="idx-code-sm">{idx.code}</span>
                      </div>
                    ))}
                  </div>
                  <div className="ext-index-col">
                    {asiaIndices.slice(Math.ceil(asiaIndices.length / 2)).map((idx, i) => (
                      <div key={i} className="idx-row">
                        <span className="idx-flag">{idx.flag || '🌏'}</span>
                        <span className="idx-name">{idx.name}</span>
                        <span className="idx-region">{idx.region}</span>
                        <span className="idx-code-sm">{idx.code}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: '#555', marginTop: 6 }}>实时行情待接入 · 仅供参考</div>
              </div>
            )}

            {/* ⚠️ 外围异动监测 */}
            {abnormalAlerts.length > 0 && (
              <div className="section">
                <div className="abnormal-summary">
                  <div className="abnormal-summary-title">⚠️ 外围异动监测</div>
                  <div className="abnormal-summary-list">
                    {abnormalAlerts.map((a, i) => {
                      const chgCls = a.change_pct >= 0 ? 'up' : 'down'
                      const arrow = a.change_pct >= 0 ? '▲' : '▼'
                      return (
                        <div key={i} className="abnormal-summary-item" onClick={() => handleAnalyze(a)}>
                          <span className={`abnormal-level-tag ${a.level}`}>
                            {a.level === 'warning' ? '预警' : '注意'}
                          </span>
                          <span className="abnormal-name">{a.name}</span>
                          <span className={`abnormal-chg ${chgCls}`}>
                            {arrow} {a.change_pct >= 0 ? '+' : ''}{a.change_pct.toFixed(2)}%
                          </span>
                          <span className="abnormal-impact">→ {a.impact || ''}</span>
                          <button className="abnormal-analyze-btn" onClick={e => { e.stopPropagation(); handleAnalyze(a) }}>
                            🔍 分析原因
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* 🔴 恐慌监测 */}
            {panicMon && panicMon.level && (
              <div className="section">
                <div className="panic-section">
                  <div className={`panic-header ${panicMon.level}`}>
                    <span className="panic-icon">
                      {panicMon.level === 'warning' ? '🔴' : '⚠️'}
                    </span>
                    <span className="panic-title">
                      {panicMon.level === 'warning' ? '恐慌预警' : '恐慌注意'}
                    </span>
                    <span className="panic-time">{panicMon.triggered_at || ''}</span>
                    <span className="panic-expand-toggle">▼</span>
                  </div>

                  <div className="panic-body">
                    {/* 触发原因 */}
                    <div className="panic-triggers">
                      <div className="panic-subtitle">触发原因</div>
                      {panicMon.triggers.map((t, i) => (
                        <div key={i} className="panic-trigger-item">
                          <span className={`panic-trigger-level ${t.level}`}>
                            {t.level === 'warning' ? '🔴' : '⚠️'}
                          </span>
                          <span className="panic-trigger-name">{t.index}</span>
                          <span className={`panic-trigger-chg ${t.change_pct >= 0 ? 'up' : 'down'}`}>
                            {t.change_pct.toFixed(2)}%
                          </span>
                          <span className="panic-trigger-threshold">
                            阈值 {t.threshold}{t.is_decline_count ? '家' : '%'}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* 应对策略 */}
                    {panicMon.strategy && panicMon.strategy.paths && (
                      <div className="panic-strategy">
                        <div className="panic-subtitle">📋 应对策略</div>
                        {panicMon.strategy.paths.map((p, i) => (
                          <div key={i} className="panic-path-card">
                            <div className="panic-path-header">
                              <span className="panic-path-prob">{p.probability}%</span>
                              <span className="panic-path-name">{p.name}</span>
                            </div>
                            <div className="panic-path-action">{p.action}</div>
                          </div>
                        ))}
                        {panicMon.strategy.principle && (
                          <div className="panic-principle">
                            {'💡 '}{panicMon.strategy.principle}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 历史记录 */}
                    {panicMon.history && panicMon.history.length > 0 && (
                      <div className="panic-history">
                        <div className="panic-subtitle">📜 历史恐慌记录</div>
                        <div className="panic-history-list">
                          {panicMon.history.slice(0, 5).map((h, i) => (
                            <div key={i} className="panic-history-item">
                              <span className={`panic-history-level ${h.level}`}>
                                {h.level === 'warning' ? '🔴' : '⚠️'}
                              </span>
                              <span className="panic-history-date">{h.date}</span>
                              <span className="panic-history-trigger">{h.trigger}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 4. 外围美股供应链映射 */}
            {extCats.length > 0 && (
              <div className="section">
                <div className="section-title">
                  🔗 外围美股映射 <span className="badge">{extCats.length}类</span>
                </div>
                {extCats.map((cat, ci) => {
                  const catKey = `cat_${ci}`
                  const isOpen = catOpen[catKey] ?? false
                  return (
                    <div key={catKey} className="ext-cat-block">
                      <div
                        className="ext-cat-header"
                        onClick={() => setCatOpen(prev => ({ ...prev, [catKey]: !prev[catKey] }))}
                      >
                        <span className="ext-cat-arrow">{isOpen ? '▼' : '▶'}</span>
                        {cat.name}
                        <span className="badge-sm">{(cat.stocks || []).length}</span>
                      </div>
                      {isOpen && (
                        <div className="ext-stock-list">
                          {(cat.stocks || []).map((s, si) => {
                            const sk = `${ci}_${si}`
                            const usPrice = usStocks[s.name]
                            const isExpanded = stockExpand[sk] ?? false
                            const chgCls = usPrice ? (usPrice.change_pct >= 0 ? 'up' : 'down') : ''
                            const arrow = usPrice ? (usPrice.change_pct >= 0 ? '▲' : '▼') : ''
                            // 查找该股是否有异动
                            const alertInfo = abnormalAlerts.find(a => a.name === s.name)
                            const rowAbnormalCls = alertInfo
                              ? (alertInfo.level === 'warning' ? ' abnormal-warning' : ' abnormal-caution')
                              : ''
                            return (
                              <div key={sk} className="ext-stock-item">
                                <div
                                  className={`ext-stock-row${rowAbnormalCls}`}
                                  onClick={() => setStockExpand(prev => ({ ...prev, [sk]: !prev[sk] }))}
                                >
                                  <span className="ext-stock-code">{s.code}</span>
                                  {alertInfo ? (
                                    <span className={`abnormal-dot ${alertInfo.level}`} />
                                  ) : (
                                    <span className="abnormal-dot ok" />
                                  )}
                                  <span className="ext-stock-name">{s.name}</span>
                                  {usPrice ? (
                                    <>
                                      <span className="ext-stock-price">{usPrice.price.toFixed(2)}</span>
                                      <span className={`ext-stock-chg ${chgCls}`}>
                                        {arrow} {usPrice.change_pct >= 0 ? '+' : ''}{usPrice.change_pct.toFixed(2)}%
                                      </span>
                                    </>
                                  ) : (
                                    <>
                                      <span className="ext-stock-price">--</span>
                                      <span className="ext-stock-chg" style={{ color: '#555' }}>--</span>
                                    </>
                                  )}
                                  <span className="ext-stock-impact">→ {s.impact || ''}</span>
                                  {alertInfo && (
                                    <button className="abnormal-analyze-btn" onClick={e => { e.stopPropagation(); handleAnalyze(alertInfo) }}>
                                      🔍
                                    </button>
                                  )}
                                  <span className="ext-expand-icon">{isExpanded ? '▲' : '▼'}</span>
                                </div>
                                {isExpanded && (
                                  <div className="ext-stock-detail">
                                    {s.sectors && (
                                      <div className="ext-detail-row">
                                        <span className="ext-detail-label">影响板块</span>
                                        <span className="ext-detail-val">{s.sectors}</span>
                                      </div>
                                    )}
                                    {s.suppliers && s.suppliers !== '暂无直接供应商' && (
                                      <div className="ext-detail-row">
                                        <span className="ext-detail-label">A股供应商</span>
                                        <span className="ext-detail-val">{s.suppliers}</span>
                                      </div>
                                    )}
                                    {s.counterparts && (
                                      <div className="ext-detail-row">
                                        <span className="ext-detail-label">A股对标</span>
                                        <span className="ext-detail-val">{s.counterparts}</span>
                                      </div>
                                    )}
                                    {s.potential && (
                                      <div className="ext-detail-row">
                                        <span className="ext-detail-label">潜在受益</span>
                                        <span className="ext-detail-val">{s.potential}</span>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
                {data?.external?.source_url && (
                  <div className="ext-source">
                    📎 <a href={data.external.source_url} target="_blank" rel="noreferrer">{data.external.source || '数据来源'}</a>
                  </div>
                )}
              </div>
            )}

            {/* 5. CPI */}
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

            {/* 6. PPI */}
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

            {/* 7. 汇率 */}
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

            {/* 分析原因弹窗 */}
            {modalShow && (
              <div className="abnormal-modal-overlay" onClick={() => setModalShow(false)}>
                <div className="abnormal-modal" onClick={e => e.stopPropagation()}>
                  <div className="abnormal-modal-header">
                    <div className="abnormal-modal-title">
                      {modalStock ? modalStock.name : '分析中...'}
                    </div>
                    <button className="abnormal-modal-close" onClick={() => setModalShow(false)}>✕</button>
                  </div>
                  {modalLoading && (
                    <div className="abnormal-modal-loading">
                      <div className="spinner-sm" />
                      <p>正在搜索相关新闻...</p>
                    </div>
                  )}
                  {modalError && (
                    <div className="abnormal-modal-error">
                      ❌ {modalError}
                    </div>
                  )}
                  {modalResult && (
                    <>
                      <div className={`abnormal-modal-chg ${modalResult.change_pct && modalResult.change_pct >= 0 ? 'up' : 'down'}`}>
                        <span className="label">涨跌幅</span>{' '}
                        {modalResult.change_pct && (modalResult.change_pct >= 0 ? '+' : '')}{modalResult.change_pct?.toFixed(2)}%
                      </div>
                      {modalResult.summary && (
                        <div className="abnormal-modal-summary">{modalResult.summary}</div>
                      )}
                      {modalResult.related_a_shares && modalResult.related_a_shares.length > 0 && (
                        <div className="abnormal-modal-related">
                          <div className="label">影响A股方向</div>
                          {modalResult.related_a_shares.map((r, i) => (
                            <span key={i} className="tag">{r}</span>
                          ))}
                        </div>
                      )}
                      {modalResult.news && modalResult.news.length > 0 && (
                        <>
                          <div className="abnormal-modal-news-title">📰 相关新闻</div>
                          {modalResult.news.map((n, i) => (
                            <div key={i} className="abnormal-modal-news-item">
                              <div className="news-title">{n.title}</div>
                              <div className="news-meta">
                                <span>{n.source || ''}</span>
                                <span>{n.time || ''}</span>
                                {n.url && <a href={n.url} target="_blank" rel="noreferrer">查看原文 ↗</a>}
                              </div>
                            </div>
                          ))}
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}

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

// 汇率常量
const fxPairs = [
  { key: '在岸人民币', cn: '美元/人民币', symbol: 'USDCNY' },
  { key: '欧元', cn: '欧元/人民币', symbol: 'EURCNY' },
  { key: '英镑', cn: '英镑/人民币', symbol: 'GBPCNY' },
  { key: '日元', cn: '100日元/人民币', symbol: 'JPYCNY' },
]

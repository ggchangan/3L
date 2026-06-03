import { useEffect, useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './TopGainers.css'

interface GainStock {
  code: string; name: string; gain: number; days: number
  change?: number; price?: number; sector?: string
  structure?: string; stage?: string
  vol_analysis?: string; trading_system?: string
  signal?: string; buy_point?: string
  stop_loss?: number | null; stop_loss_pct?: number | null
  conclusion?: string; mainline_level?: string
  fusion_type?: string
}

interface PieItem {
  name: string; count: number; pct: number
}

interface GainData {
  stocks: GainStock[]; pie: PieItem[]; total: number
  start: string; end: string; days: number
}

const PIE_COLORS = [
  '#e94560', '#2196f3', '#4CAF50', '#ff9800', '#a855f7',
  '#00bcd4', '#ff5722', '#8bc34a', '#e91e63', '#3f51b5',
  '#009688', '#ffeb3b', '#9c27b0', '#795548', '#607d8b',
  '#cddc39', '#03a9f4', '#f44336', '#4caf50', '#ffc107',
]

const STAGE_COLORS: Record<string, string> = {
  '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700',
  '滞涨': '#ff6b6b', '转弱': '#ff6b6b', '下行': '#666',
  '加速跌': '#e94560', '转强': '#4ecdc4',
  '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560',
}

const SIGNAL_COLORS: Record<string, string> = {
  'buy': '#e94560',
  'hold': '#ffd700',
  'sell': '#4CAF50',
}

const SIGNAL_LABELS: Record<string, string> = {
  'buy': '买入',
  'hold': '持有',
  'sell': '卖出',
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

export default function TopGainers() {
  const today = new Date().toISOString().split('T')[0]
  const [startDate, setStartDate] = useState(() => daysAgo(30))
  const [endDate, setEndDate] = useState(today)
  const [limit, setLimit] = useState('50')
  const [data, setData] = useState<GainData | null>(null)
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { loadData() }, [])

  function formatDate(d: string) {
    return d.replace(/-/g, '')
  }

  async function loadData() {
    setLoading(true); setError(''); setHint('加载中...')
    try {
      // 日期校验
      if (startDate > endDate) {
        setError('起始日期不能晚于截止日期，已自动交换')
        const tmp = startDate; setStartDate(endDate); setEndDate(tmp)
        setLoading(false); setHint(''); return
      }
      const start = formatDate(startDate)
      const end = formatDate(endDate)
      const r = await fetch(`/api/top-gainers?start=${start}&end=${end}&limit=${limit}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      if (d.error) throw new Error(d.error)
      setData(d)
      setHint(`共 ${d.stocks.length} 只`)
      if (d.stocks.length === 0) {
        setHint('该区间无数据，可能是所选日期不在交易日期范围内')
      }
    } catch (err: any) {
      setError(err.message)
      setData(null)
      setHint('')
    } finally { setLoading(false) }
  }

  function renderPie(pie: PieItem[]) {
    if (!pie || pie.length === 0) return null
    const total = pie.reduce((s, d) => s + d.count, 0)
    const svgW = 280, svgH = 280, cx = 140, cy = 140, r = 110

    let startAngle = -90
    let paths = ''
    let legendHtml = ''

    pie.forEach((d, i) => {
      const angle = (d.count / total) * 360
      const endAngle = startAngle + angle
      const color = PIE_COLORS[i % PIE_COLORS.length]
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
        paths += `<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central" font-size="11" fill="#fff" font-weight="600">${d.pct.toFixed(0)}%</text>`
      }
      legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span class="legend-name">${d.name}</span><span class="legend-count">${d.count}只</span><span class="legend-pct">${d.pct}%</span></div>`
      startAngle = endAngle
    })

    paths += `<circle cx="${cx}" cy="${cy}" r="45" fill="#0f0f1a" stroke="#2a2a4e" stroke-width="1"/><text x="${cx}" y="${cy - 5}" text-anchor="middle" font-size="22" font-weight="700" fill="#e94560">${total}</text><text x="${cx}" y="${cy + 14}" text-anchor="middle" font-size="11" fill="#888">只个股</text>`

    return { svg: `<svg width="100%" height="100%" viewBox="0 0 ${svgW} ${svgH}" style="max-width:280px;max-height:280px;">${paths}</svg>`, legend: legendHtml }
  }

  const stocks = data?.stocks || []
  const pieResult = data?.pie ? renderPie(data.pie) : null
  const avgGain = stocks.length > 0 ? (stocks.reduce((s, st) => s + st.gain, 0) / stocks.length).toFixed(1) : '0'
  const maxGain = stocks.length > 0 ? stocks[0].gain.toFixed(1) : '0'
  const periodLabel = data
    ? `${data.start.slice(0,4)}-${data.start.slice(4,6)}-${data.start.slice(6,8)} → ${data.end.slice(0,4)}-${data.end.slice(4,6)}-${data.end.slice(6,8)}（${data.days}个交易日）`
    : ''

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📈 区间涨幅榜</h1>
        <div className="subtitle">全市场个股 · 指定区间涨幅排序 · 板块分布 · 操作信号</div>
      </div>

      <div className="container">
        {/* Controls */}
        <div className="controls">
          <label htmlFor="startPicker">📅 起始</label>
          <input type="date" id="startPicker" value={startDate} onChange={e => setStartDate(e.target.value)} />
          <label htmlFor="endPicker">→ 截止</label>
          <input type="date" id="endPicker" value={endDate} onChange={e => setEndDate(e.target.value)} />
          <label htmlFor="limitSelect">展示</label>
          <select id="limitSelect" value={limit} onChange={e => setLimit(e.target.value)}>
            <option value="30">30只</option>
            <option value="50">50只</option>
            <option value="66">66只</option>
            <option value="100">100只</option>
          </select>
          <button className="btn-query" onClick={loadData} disabled={loading}>
            🔍 查询
          </button>
          <span className="loading-hint">{hint}</span>
        </div>

        {/* Summary */}
        {data && stocks.length > 0 && (
          <div className="summary" style={{ display: 'flex' }}>
            <div className="summary-item">
              <div className="label">查询区间</div>
              <div className="value" style={{ fontSize: 14, color: '#e0e0e0' }}>{periodLabel}</div>
            </div>
            <div className="summary-item">
              <div className="label">展示个股</div>
              <div className="value" style={{ color: '#e94560' }}>{stocks.length}/{data.total}</div>
              <div className="sub">总符合条件的个股</div>
            </div>
            <div className="summary-item">
              <div className="label">平均涨幅</div>
              <div className="value" style={{ color: parseFloat(avgGain) >= 0 ? '#e94560' : '#4CAF50' }}>{avgGain}%</div>
              <div className="sub">区间</div>
            </div>
            <div className="summary-item">
              <div className="label">最高涨幅</div>
              <div className="value" style={{ color: '#e94560' }}>{maxGain}%</div>
              <div className="sub">{stocks[0]?.name || ''}</div>
            </div>
          </div>
        )}

        {/* Pie Chart */}
        {data && pieResult && (
          <div className="pie-section" style={{ display: 'block' }}>
            <div className="pie-title">📊 板块分布</div>
            <div className="pie-container">
              <div className="pie-svg-container" dangerouslySetInnerHTML={{ __html: pieResult.svg }} />
              <div className="pie-legend" dangerouslySetInnerHTML={{ __html: pieResult.legend }} />
            </div>
          </div>
        )}

        {/* Loading / Error */}
        {loading && <div className="loading-area">加载中...</div>}

        {error && (
          <div className="error-card">❌ 加载失败: {error}</div>
        )}

        {/* Stock List */}
        {data && stocks.length === 0 && !loading && !error && (
          <div className="error-card">
            该区间无数据<br/>
            <span style={{fontSize:12,color:'#666'}}>所选日期可能不在交易日范围内，系统会自动对齐到最近交易日，请尝试调整日期范围</span>
          </div>
        )}

        {data && stocks.length > 0 && (
          <div className="stock-grid">
            {stocks.map((s, i) => {
              const rankClass = i === 0 ? 'top1' : i < 5 ? 'top5' : i < 10 ? 'top10' : 'normal'
              const rankLabel = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`
              const leftColor = STAGE_COLORS[s.stage || ''] || '#888'
              const changeCls = (s.change || 0) >= 0 ? 'up' : 'down'
              const gainCls = s.gain >= 0 ? 'up' : 'down'
              const gainArrow = s.gain >= 0 ? '▲' : '▼'
              const signalColor = SIGNAL_COLORS[s.signal || 'hold']
              const signalLabel = SIGNAL_LABELS[s.signal || 'hold']

              return (
                <div key={s.code} className="stock-item-wrapper" style={{ borderLeft: `3px solid ${leftColor}` }}>
                  <div className="stock-item">
                    {/* Top: name + price */}
                    <div className="stock-top">
                      <div className="stock-left">
                        <span className="stock-name">{s.name}</span>
                        <span className={`gain-rank ${rankClass}`}>{rankLabel} {s.gain.toFixed(1)}%</span>
                        <span className="stock-code">{s.code}</span>
                      </div>
                      <div className="stock-right">
                        {s.price != null && <span className="price">{s.price.toFixed(2)}</span>}
                        {s.change != null && (
                          <span className={`change ${changeCls}`}>
                            {(s.change || 0) >= 0 ? '+' : ''}{(s.change || 0).toFixed(2)}%
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Signal + Trading System + Buy Point */}
                    <div className="stock-signal-row">
                      {s.signal && (
                        <span className="signal-badge" style={{ background: signalColor }}>
                          {signalLabel}
                        </span>
                      )}
                      {s.trading_system === 'trend' ? (
                        <span className="signal-badge trend-badge">趋势</span>
                      ) : s.trading_system === '3l' ? (
                        <span className="signal-badge badge-3l">3L</span>
                      ) : null}
                      {s.mainline_level && (
                        <span className={`mainline-badge ${s.mainline_level === '主线' ? 'main' : s.mainline_level === '次级主线' ? 'sub' : 'non'}`}>
                          {s.mainline_level}
                        </span>
                      )}
                      {s.buy_point && (
                        <span className="buy-point-badge">{s.buy_point}</span>
                      )}
                      {s.trading_system === 'trend' && (
                        <span className="tag" style={{ fontSize: 10, color: '#aaa' }}>趋势交易</span>
                      )}
                    </div>

                    {/* Tags */}
                    <div className="stock-tags">
                      {s.sector && <span className="tag">{s.sector}</span>}
                      {s.structure && <span className="tag">{s.structure}</span>}
                      {s.stage && <span className="tag" style={{ color: STAGE_COLORS[s.stage] || '#888' }}>{s.stage}</span>}
                      {s.stop_loss_pct != null && (
                        <span className="tag sl-tag">止损{s.stop_loss_pct.toFixed(1)}%</span>
                      )}
                    </div>

                    {/* Conclusion */}
                    {s.conclusion && (
                      <div className="stock-conclusion">{s.conclusion}</div>
                    )}

                    {/* 区间涨幅 field */}
                    <div className="stock-field">
                      <span className="field-label">区间涨幅:</span>
                      <span className={`field-value ${gainCls}`}>{gainArrow} {s.gain >= 0 ? '+' : ''}{s.gain.toFixed(2)}%</span>
                      <span className="field-label" style={{ marginLeft: 8 }}>（{s.days}日）</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  )
}

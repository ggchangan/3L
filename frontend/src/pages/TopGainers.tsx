import { useEffect, useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './TopGainers.css'

interface GainStock {
  code: string; name: string; gain_30d: number
  change?: number; price?: number; sector?: string
  structure?: string; stage?: string
  vol_analysis?: string; trading_system?: string
}

interface PieItem {
  name: string; count: number; pct: number
}

interface GainData {
  stocks: GainStock[]; pie: PieItem[]; total: number
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

export default function TopGainers() {
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0])
  const [limit, setLimit] = useState('50')
  const [data, setData] = useState<GainData | null>(null)
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true); setError(''); setHint('加载中...')
    try {
      const r = await fetch(`/api/top-gainers?date=${date}&limit=${limit}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      if (d.error) throw new Error(d.error)
      setData(d)
      setHint(`共 ${d.stocks.length} 只`)
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
  const avgGain = stocks.length > 0 ? (stocks.reduce((s, st) => s + st.gain_30d, 0) / stocks.length).toFixed(1) : '0'
  const maxGain = stocks.length > 0 ? stocks[0].gain_30d.toFixed(1) : '0'

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📈 30日涨幅榜</h1>
        <div className="subtitle">全市场个股 · 近30日涨幅排序 · 板块分布</div>
      </div>

      <div className="container">
        {/* Controls */}
        <div className="controls">
          <label htmlFor="datePicker">📅 截止日期</label>
          <input type="date" id="datePicker" value={date} onChange={e => setDate(e.target.value)} />
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
              <div className="label">截止日期</div>
              <div className="value" style={{ fontSize: 16, color: '#e0e0e0' }}>{date}</div>
            </div>
            <div className="summary-item">
              <div className="label">展示个股</div>
              <div className="value" style={{ color: '#e94560' }}>{stocks.length}/{data.total}</div>
              <div className="sub">总符合条件的个股</div>
            </div>
            <div className="summary-item">
              <div className="label">平均涨幅</div>
              <div className="value" style={{ color: parseFloat(avgGain) >= 0 ? '#e94560' : '#4CAF50' }}>{avgGain}%</div>
              <div className="sub">30日</div>
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
          <div className="error-card">该日期无数据</div>
        )}

        {data && stocks.length > 0 && (
          <div className="stock-grid">
            {stocks.map((s, i) => {
              const rankClass = i === 0 ? 'top1' : i < 5 ? 'top5' : i < 10 ? 'top10' : 'normal'
              const rankLabel = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`
              const leftColor = STAGE_COLORS[s.stage || ''] || '#888'
              const changeCls = (s.change || 0) >= 0 ? 'up' : 'down'
              const gainCls = s.gain_30d >= 0 ? 'up' : 'down'
              const gainArrow = s.gain_30d >= 0 ? '▲' : '▼'

              return (
                <div key={s.code} className="stock-item-wrapper" style={{ borderLeft: `3px solid ${leftColor}` }}>
                  <div className="stock-item">
                    {/* Top: name + price */}
                    <div className="stock-top">
                      <div className="stock-left">
                        <span className="stock-name">{s.name}</span>
                        <span className={`gain-rank ${rankClass}`}>{rankLabel} {s.gain_30d.toFixed(1)}%</span>
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

                    {/* Tags */}
                    <div className="stock-tags">
                      {s.sector && <span className="tag">{s.sector}</span>}
                      {s.structure && <span className="tag">{s.structure}</span>}
                      {s.stage && <span className="tag" style={{ color: STAGE_COLORS[s.stage] || '#888' }}>{s.stage}</span>}
                      {s.vol_analysis && <span className="tag">{s.vol_analysis}</span>}
                    </div>

                    {/* 30日涨幅 field */}
                    <div className="stock-field">
                      <span className="field-label">30日涨幅:</span>
                      <span className={`field-value ${gainCls}`}>{gainArrow} {s.gain_30d >= 0 ? '+' : ''}{s.gain_30d.toFixed(2)}%</span>
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

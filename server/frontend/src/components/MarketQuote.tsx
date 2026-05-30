import { useEffect, useState, useRef } from 'react'
import { Chart, registerables } from 'chart.js'
import { fetchVolume, fmtAmountYuan } from '../lib/api'
import type { VolumeData } from '../lib/types'

Chart.register(...registerables)

interface MarketHealth {
  structure: string
  stage: string
  pk_score: number
  vl_score: number
  position: string
  position_advice: string
  bias20: number
  last_close: number
  volume: {
    latest_volume: number
    avg5_volume: number
    avg20_volume: number
    vs_5day_pct: number
    vs_20day_pct: number
  }
  mainline: {
    top3: { name: string; days: number }[]
    gap_pct: number
  }
  updated: string
}

function fetchMarketHealth(): Promise<MarketHealth | null> {
  return fetch('/api/market-health')
    .then(r => r.json())
    .catch(() => null)
}

// 结构颜色
const STRUCT_COLORS: Record<string, string> = {
  '上涨趋势': '#4CAF50',
  '区间震荡': '#ffd700',
  '下降趋势': '#e94560',
}

export default function MarketQuote() {
  const [health, setHealth] = useState<MarketHealth | null>(null)
  const [volumeData, setVolumeData] = useState<VolumeData | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)

  useEffect(() => {
    loadAll()
    const timer = setInterval(loadAll, 30000)
    return () => clearInterval(timer)
  }, [])

  async function loadAll() {
    const [mh, vol] = await Promise.all([
      fetchMarketHealth(),
      fetchVolume(),
    ])
    if (mh) setHealth(mh)
    if (vol) {
      setVolumeData(vol)
      setTimeout(() => updateChart(vol), 50)
    }
  }

  function updateChart(d: VolumeData) {
    if (!canvasRef.current) return
    const curve = d.today_curve || []
    const labels = curve.map(p => p.time)
    const amounts = curve.map(p => p.amount || 0)

    if (chartRef.current) {
      chartRef.current.data.labels = labels
      chartRef.current.data.datasets[0].data = amounts
      chartRef.current.update('none')
      return
    }

    const ctx = canvasRef.current.getContext('2d')
    if (!ctx) return
    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: `今日(${d.current_time ? d.current_time.slice(0, 10) : ''})`,
          data: amounts,
          borderColor: '#ffd700',
          backgroundColor: 'rgba(255, 215, 0, 0.05)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: true, labels: { color: '#a0a0b0', font: { size: 10 }, boxWidth: 12, padding: 8 } },
          tooltip: { callbacks: { label: ctx => `今日: ${fmtAmountYuan(ctx.raw as number)}` } },
        },
        scales: {
          x: { display: true, ticks: { color: '#555', maxTicksLimit: 10, font: { size: 9 }, callback: (_, i) => labels[i] || '' }, grid: { display: false } },
          y: { display: true, ticks: { color: '#555', font: { size: 9 }, callback: v => fmtAmountYuan(v as number) }, grid: { color: 'rgba(255,255,255,0.03)' } },
        },
        animation: { duration: 0 },
      },
    })
  }

  // 关键数值
  const structColor = STRUCT_COLORS[health?.structure || ''] || '#888'
  const price = volumeData?.current_price || health?.last_close || 0
  const change = volumeData?.current_change ?? null

  return (
    <>
      {/* 顶部状态栏 */}
      <div
        className="block-title"
        style={{
          borderLeft: `4px solid ${structColor}`,
          paddingLeft: 8,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>
          📡 大盘观测
          <span style={{ color: structColor, fontWeight: 700, marginLeft: 8, fontSize: 13 }}>
            {health?.structure || '加载中'}
          </span>
          {health?.stage && (
            <span style={{ color: '#888', marginLeft: 6, fontSize: 12 }}>
              · {health.stage} · {health.position}
              <span style={{ color: '#ffd700', marginLeft: 6, fontSize: 11 }}>
                仓位建议 {health.position_advice}
              </span>
            </span>
          )}
        </span>
        <span style={{ fontSize: 12, color: '#999' }}>
          {health?.updated ? `更新 ${health.updated}` : ''}
        </span>
      </div>

      {/* 4 卡片网格 */}
      <div className="mh-card-grid">
        {/* 卡片1：结构·阶段 */}
        <div className="mh-card">
          <div className="mh-card-title">📐 结构·阶段</div>
          <div className="mh-card-body">
            <div className="mh-row">
              <span className="mh-label">结构</span>
              <span className="mh-val" style={{ color: structColor }}>{health?.structure || '—'}</span>
            </div>
            <div className="mh-row">
              <span className="mh-label">阶段</span>
              <span className="mh-val">{health?.stage || '—'}</span>
            </div>
            <div className="mh-row">
              <span className="mh-label">BIAS20</span>
              <span className="mh-val" style={{ color: (health?.bias20 || 0) >= 0 ? '#e94560' : '#4CAF50' }}>
                {(health?.bias20 ?? 0) >= 0 ? '+' : ''}{health?.bias20?.toFixed(2) || '—'}%
              </span>
            </div>
            <div className="mh-row">
              <span className="mh-label">仓位建议</span>
              <span className="mh-val" style={{ color: '#ffd700' }}>{health?.position_advice || '—'}</span>
            </div>
          </div>
        </div>

        {/* 卡片2：量能分析 */}
        <div className="mh-card">
          <div className="mh-card-title">📊 量能分析</div>
          <div className="mh-card-body">
            <div className="mh-row">
              <span className="mh-label">中证全指</span>
              <span className="mh-val">{price ? price.toFixed(2) : '—'}</span>
            </div>
            {change !== null && (
              <div className="mh-row">
                <span className="mh-label">涨跌幅</span>
                <span className="mh-val" style={{ color: change >= 0 ? '#e94560' : '#4CAF50' }}>
                  {change >= 0 ? '▲' : '▼'} {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                </span>
              </div>
            )}
            <div className="mh-row">
              <span className="mh-label">较5日均量</span>
              <span className="mh-val" style={{ color: (health?.volume?.vs_5day_pct || 0) > 0 ? '#e94560' : '#4CAF50' }}>
                {(health?.volume?.vs_5day_pct ?? 0) > 0 ? '+' : ''}{health?.volume?.vs_5day_pct?.toFixed(1) || '—'}%
              </span>
            </div>
            <div className="mh-row">
              <span className="mh-label">今日成交</span>
              <span className="mh-val">{volumeData?.today_amount_yuan ? fmtAmountYuan(volumeData.today_amount_yuan) : '—'}</span>
            </div>
          </div>
          {/* 成交额曲线 */}
          <div className="mh-chart-wrap">
            <canvas ref={canvasRef} id="volumeChart"></canvas>
          </div>
        </div>

        {/* 卡片3：主线强度 */}
        <div className="mh-card">
          <div className="mh-card-title">🎯 主线强度</div>
          <div className="mh-card-body">
            {(health?.mainline?.top3 || []).length > 0 ? (
              health!.mainline!.top3.map((item, i) => (
                <div className="mh-row" key={i}>
                  <span className="mh-label">{['①', '②', '③'][i]}</span>
                  <span className="mh-val">
                    {item.name}
                    <span className="mh-days"> {item.days}天</span>
                  </span>
                </div>
              ))
            ) : (
              <div className="mh-empty">暂无主线数据</div>
            )}
            {health?.mainline?.gap_pct ? (
              <div className="mh-row" style={{ marginTop: 4 }}>
                <span className="mh-label">TOP1-5差</span>
                <span className="mh-val" style={{ fontSize: 11, color: '#888' }}>{health.mainline.gap_pct}%</span>
              </div>
            ) : null}
          </div>
        </div>

        {/* 卡片4：异常事件（占位） */}
        <div className="mh-card">
          <div className="mh-card-title">⚡ 异常事件</div>
          <div className="mh-card-body">
            <div className="mh-empty">暂无异常</div>
          </div>
        </div>
      </div>
    </>
  )
}

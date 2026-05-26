import { useEffect, useState, useRef } from 'react'
import { Chart, registerables } from 'chart.js'
import { fetchVolume, fmtAmountYuan } from '../lib/api'
import type { VolumeData } from '../lib/types'

Chart.register(...registerables)

export default function MarketQuote() {
  const [data, setData] = useState<VolumeData | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)
  const [showIndexChart, setShowIndexChart] = useState(false)
  const chartTs = useRef(Date.now())

  useEffect(() => {
    fetchVolume().then(d => {
      setData(d)
      // 初次加载后更新图表
      setTimeout(() => updateChart(d), 50)
    })
    // 每30秒刷新
    const timer = setInterval(() => {
      fetchVolume().then(d => {
        setData(d)
        updateChart(d)
      })
    }, 30000)
    return () => clearInterval(timer)
  }, [])

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
          legend: {
            display: true,
            labels: { color: '#a0a0b0', font: { size: 10 }, boxWidth: 12, padding: 8 },
          },
          tooltip: {
            callbacks: {
              label: ctx => `今日: ${fmtAmountYuan(ctx.raw as number)}`,
            },
          },
        },
        scales: {
          x: {
            display: true,
            ticks: { color: '#555', maxTicksLimit: 10, font: { size: 9 }, callback: (_, i) => labels[i] || '' },
            grid: { display: false },
          },
          y: {
            display: true,
            ticks: { color: '#555', font: { size: 9 }, callback: v => fmtAmountYuan(v as number) },
            grid: { color: 'rgba(255,255,255,0.03)' },
          },
        },
        animation: { duration: 0 },
      },
    })
  }

  const price = data?.current_price
  const change = data?.current_change || 0
  const priceClass = change >= 0 ? 'qvalue up' : 'qvalue down'
  const ratioClass = (data?.amount_ratio || 0) >= 100 ? 'qvalue up' : 'qvalue down'
  const ratioColor = (data?.amount_ratio || 0) > 100 ? '#e94560' : '#4ecdc4'

  const yAmt = data?.yesterday_amount_yuan || 0
  const yIsEst = data?.yesterday_is_estimated

  return (
    <>
      <div className="block-title">📡 大盘观测</div>
      <div className="quote-grid">
        <div className="quote-item">
          <div className="qlabel">中证全指 000985</div>
          <div className={priceClass}>{price ? price.toFixed(2) : '--'}</div>
        </div>
        <div className="quote-item">
          <div className="qlabel">涨跌幅</div>
          <div className={priceClass}>{change ? `${change >= 0 ? '+' : ''}${change.toFixed(2)}%` : '--'}</div>
        </div>
        <div className="quote-item">
          <div className="qlabel">今日成交额</div>
          <div className="qvalue">{fmtAmountYuan(data?.today_amount_yuan)}</div>
        </div>
        <div className="quote-item">
          <div className="qlabel">较昨日同期</div>
          <div className={ratioClass}>{data?.amount_ratio ? `${data.amount_ratio.toFixed(1)}%` : '--'}</div>
        </div>
      </div>
      <div className="chart-container volume-chart-wrap">
        <canvas ref={canvasRef} id="volumeChart"></canvas>
      </div>
      <div className="chart-footer">
        今日累计 <span id="todayVolLabel">{fmtAmountYuan(data?.today_amount_yuan)}</span>&nbsp;&nbsp;|&nbsp;&nbsp;
        昨日全天 <span id="yesterdayVolLabel">{yAmt > 0 ? fmtAmountYuan(yAmt) : '待积累'}</span>&nbsp;&nbsp;
        <span id="yesterdayDateLabel" style={{ color: '#555' }}>{data?.yesterday_date ? `(${data.yesterday_date})${yIsEst ? ' *估算' : ''}` : ''}</span>&nbsp;&nbsp;|&nbsp;&nbsp;
        <span style={{ fontWeight: 'bold', color: ratioColor }}>{data?.amount_ratio ? `较昨日 ${data.amount_ratio}%` : ''}</span>
      </div>
      <div className="info-actions">
        <span className="action-link" onClick={() => setShowIndexChart(v => !v)}>📈 中证全指关键点图</span>
        <span className="action-link">⚠️ 异常事件</span>
      </div>
      {showIndexChart && (
        <div style={{ marginTop: 8 }}>
          <div style={{ width: '100%', height: 550, overflow: 'hidden', borderRadius: 8 }}>
            <img
              src={`/api/index-chart?mode=monitor&t=${chartTs.current}`}
              alt="中证全指关键点图"
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
            />
          </div>
        </div>
      )}
    </>
  )
}

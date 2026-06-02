/** 每日算法效果趋势折线图 — SVG 纯手绘，无外部依赖 */
interface DailyStat {
  date: string
  total: number
  success: number
  failure: number
  flat: number
  success_rate: number
  avg_change: number
  avg_gain: number
  avg_loss: number
}

interface Props {
  data: DailyStat[]
}

const W = 600
const H = 200
const PAD = { top: 20, right: 20, bottom: 35, left: 50 }
const IW = W - PAD.left - PAD.right
const IH = H - PAD.top - PAD.bottom

export default function DailyTrendChart({ data }: Props) {
  if (!data || data.length < 2) {
    return <div style={{ color: '#555', fontSize: 12, padding: 20, textAlign: 'center' }}>数据不足2天，无法绘制趋势</div>
  }

  // 坐标映射
  const dates = data.map(d => d.date.slice(5)) // MM-DD
  const rates = data.map(d => d.success_rate)
  const changes = data.map(d => d.avg_change)
  const totals = data.map(d => d.total)

  const maxRate = Math.max(...rates, 60)
  const minRate = Math.min(...rates, 0)
  const rateRange = Math.max(maxRate - minRate, 10)
  const minChg = Math.min(...changes, -10)
  const maxChg = Math.max(...changes, 10)
  const chgRange = Math.max(maxChg - minChg, 10)

  const maxTotal = Math.max(...totals, 5)

  const xScale = (i: number) => PAD.left + (i / (data.length - 1)) * IW
  const yRate = (v: number) => PAD.top + IH - ((v - minRate) / rateRange) * IH
  const yChg = (v: number) => PAD.top + IH - ((v - minChg) / chgRange) * IH

  // 折线 path
  let ratePath = ''
  let chgPath = ''
  data.forEach((d, i) => {
    const x = xScale(i)
    ratePath += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + yRate(d.success_rate).toFixed(1)
    chgPath += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + yChg(d.avg_change).toFixed(1)
  })

  // 网格线
  const gridLines = [0, 25, 50, 75, 100].filter(v => v >= minRate && v <= minRate + rateRange)

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>📈 算法效果趋势</div>
      <svg viewBox={`0 0 ${W} ${H + 30}`} style={{ width: '100%', maxWidth: W, borderRadius: 8 }}>
        {/* 网格 */}
        {gridLines.map(v => {
          const y = yRate(v)
          return (
            <g key={v}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#2a2a3e" strokeWidth={0.5} />
              <text x={PAD.left - 6} y={y + 3} textAnchor="end" fill="#666" fontSize={9}>{v}%</text>
            </g>
          )
        })}

        {/* 成功率线 */}
        <path d={ratePath} fill="none" stroke="#4ecdc4" strokeWidth={2} strokeLinejoin="round" />

        {/* 平均涨跌线 */}
        <path d={chgPath} fill="none" stroke="#ffd700" strokeWidth={1.5} strokeLinejoin="round" strokeDasharray="4,3" />

        {/* 数据点 + 标签 */}
        {data.map((d, i) => {
          const x = xScale(i)
          const yr = yRate(d.success_rate)
          const yc = yChg(d.avg_change)
          const color = d.success_rate >= 50 ? '#4ecdc4' : '#e94560'
          return (
            <g key={i}>
              {/* 成功率圆点 */}
              <circle cx={x} cy={yr} r={3.5} fill={color} stroke="#1a1a2e" strokeWidth={1.5} />
              {/* 涨跌圆点 */}
              <circle cx={x} cy={yc} r={2.5} fill={d.avg_change >= 0 ? '#ff4444' : '#44aa44'} stroke="#1a1a2e" strokeWidth={1} />
              {/* 标签 */}
              <text x={x} y={H - PAD.bottom + 16} textAnchor="middle" fill="#888" fontSize={9}>
                {dates[i]}
              </text>
            </g>
          )
        })}

        {/* 图例 */}
        <g transform={`translate(${W - 140}, ${PAD.top - 5})`}>
          <line x1={0} y1={0} x2={16} y2={0} stroke="#4ecdc4" strokeWidth={2} />
          <text x={20} y={4} fill="#aaa" fontSize={9}>成功率</text>
          <line x1={70} y1={0} x2={86} y2={0} stroke="#ffd700" strokeWidth={1.5} strokeDasharray="4,3" />
          <text x={90} y={4} fill="#aaa" fontSize={9}>平均涨跌</text>
        </g>
      </svg>

      {/* 数据表格摘要 */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
        {data.slice().reverse().map(d => (
          <div key={d.date} style={{
            background: 'rgba(255,255,255,0.03)', borderRadius: 6,
            padding: '5px 8px', fontSize: 10, minWidth: 100,
            border: '1px solid ' + (d.success_rate >= 50 ? 'rgba(78,205,196,0.2)' : 'rgba(233,69,96,0.2)'),
          }}>
            <div style={{ color: '#888', marginBottom: 2 }}>{d.date}</div>
            <div style={{ color: d.success_rate >= 50 ? '#4ecdc4' : '#e94560', fontWeight: 600 }}>
              成功率 {d.success_rate}%
            </div>
            <div style={{ color: '#888' }}>
              {d.total}条 | 胜{d.success}/败{d.failure}
              <span style={{ color: d.avg_gain > 0 ? '#ff4444' : '#888' }}> 胜均+{d.avg_gain}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

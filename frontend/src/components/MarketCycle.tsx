import { useEffect, useState } from 'react'
import { fetchMarket } from '../lib/api'

interface MarketData {
  price?: number | string
  change?: number
  score?: number
  position?: string
  position_pct?: string
  strategy?: string
  build_per_stock_pct?: string
  pk_score?: number
  vl_score?: number
  bias20?: number
  bias20_chg_3d?: number
}

export default function MarketCycle({ date: _date }: { date?: string }) {
  const [data, setData] = useState<MarketData | null>(null)
  const [showScore, setShowScore] = useState(false)
  const [showChart, setShowChart] = useState(false)
  const [showFlow, setShowFlow] = useState(false)

  useEffect(() => {
    // 直接调 /api/market，不读存档
    fetchMarket().then(setData).catch(() => setData({
      price: '--', position: '波中', position_pct: '半仓',
      strategy: '中等仓位·精选个股',
    }))
  }, [])

  if (!data) return <div className="empty">加载中...</div>

  const price = data.price
  const change = data.change || 0
  const priceClass = change >= 0 ? 'value up' : 'value down'
  const pk = data.pk_score || 0
  const vl = data.vl_score || 0
  const posName = data.position || '波中'

  const pkIcon = pk >= 4 ? '🟢' : pk >= 3 ? '🟡' : pk >= 1 ? '⚪' : '⚪'
  const pkDesc = pk >= 4 ? '✅ 趋势转跌+位置偏高+量价异常+方向确认 → 高度确信'
    : pk >= 3 ? '⚠️ 满足3个条件，可能偏峰'
    : pk >= 1 ? '🔸 满足1个条件，趋势有波动'
    : '— 无波峰信号'
  const vlIcon = vl >= 4 ? '🟢' : vl >= 3 ? '🟡' : vl >= 1 ? '⚪' : '⚪'
  const vlDesc = vl >= 4 ? '✅ 趋势转涨+位置偏低+恐慌出清+方向确认 → 高度确信'
    : vl >= 3 ? '⚠️ 满足3个条件，可能偏谷'
    : vl >= 1 ? '🔸 满足1个条件'
    : '— 无波谷信号'

  return (
    <>
      <div className="grid-4" id="marketGrid">
        <div className="info-card">
          <div className="label">中证全指 000985</div>
          <div className={priceClass}>{price || '--'}</div>
          <div className="meta" id="marketChange">涨跌 {change ? `${change >= 0 ? '+' : ''}${change}%` : '--'}</div>
        </div>
        <div className="info-card">
          <div className="label">大盘周期位置</div>
          <div className="value" style={{ fontSize: 18 }}>{data.position || '--'}</div>
          <div className="meta" id="cycleScore">综合评分 {data.score ?? '--'}</div>
        </div>
        <div className="info-card">
          <div className="label">建议总仓位</div>
          <div className="value" style={{ fontSize: 18 }}>{data.position_pct || '--'}</div>
          <div className="meta" id="positionRule">建仓 {data.build_per_stock_pct || '--'}/只</div>
        </div>
        <div className="info-card">
          <div className="label">策略</div>
          <div className="value" style={{ fontSize: 14 }}>{data.strategy || '--'}</div>
          <div className="meta" id="strategyAdvice">{data.strategy || '--'}</div>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <table id="scoreDetailTable" style={{ display: showScore ? '' : 'none' }}>
          <thead>
            <tr><th>维度</th><th>评分</th><th>明细</th></tr>
          </thead>
          <tbody>
            <tr><td colSpan={3} style={{ fontSize: 13, color: '#4ecdc4', fontWeight: 'bold', paddingBottom: 8 }}>{posName}</td></tr>
            <tr>
              <td style={{ color: '#888', width: 50 }}>波峰</td>
              <td style={{ width: 50, textAlign: 'center', fontSize: 16 }}>{pkIcon}</td>
              <td style={{ color: '#888', fontSize: 11 }}>{pkDesc}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>波谷</td>
              <td style={{ textAlign: 'center', fontSize: 16 }}>{vlIcon}</td>
              <td style={{ color: '#888', fontSize: 11 }}>{vlDesc}</td>
            </tr>
            <tr><td colSpan={3} style={{ borderTop: '1px solid #333', paddingTop: 6 }}></td></tr>
            <tr>
              <td style={{ color: '#888' }}>①趋势</td>
              <td style={{ textAlign: 'center' }}>{pk >= 1 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>前期bias上升+近期走平/掉头</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>②位置</td>
              <td style={{ textAlign: 'center' }}>{pk >= 2 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>MA20乖离率&gt;+1.5% {typeof data.bias20 === 'number' ? `(当前: ${data.bias20.toFixed(1)}%)` : ''}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>③量价</td>
              <td style={{ textAlign: 'center' }}>{pk >= 3 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>放量滞涨/长上影/加速衰竭</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>④方向</td>
              <td style={{ textAlign: 'center' }}>{pk >= 4 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>乖离率3日变化转负 {typeof data.bias20_chg_3d === 'number' ? `(${data.bias20_chg_3d.toFixed(1)}%)` : ''}</td>
            </tr>
            <tr><td colSpan={3} style={{ textAlign: 'center', color: '#555', fontSize: 11, paddingTop: 6 }}>pk≥4=峰 &nbsp; pk≥3=近峰 &nbsp; vl≥4=谷 &nbsp; vl≥3=近谷 &nbsp; 其余=波中</td></tr>
          </tbody>
        </table>
        <div style={{ marginTop: 6, textAlign: 'right' }}>
          <span style={{ cursor: 'pointer', color: '#4ecdc4', fontSize: 12 }} onClick={() => setShowScore(v => !v)}>📊 查看评分明细</span>
          <span style={{ color: '#333', margin: '0 6px' }}>|</span>
          <span style={{ cursor: 'pointer', color: '#ffd700', fontSize: 12 }} onClick={() => setShowFlow(v => !v)}>💰 资金流向</span>
          <span style={{ color: '#333', margin: '0 6px' }}>|</span>
          <span style={{ cursor: 'pointer', color: '#e94560', fontSize: 12 }} onClick={() => setShowChart(v => !v)}>📈 中证全指关键点图</span>
        </div>
      </div>

      {showChart && (
        <div style={{ marginTop: 8 }}>
          <div style={{ width: '100%', maxWidth: 750, height: 550, overflow: 'hidden', borderRadius: 8, margin: '0 auto' }}>
            <img src={`/api/index-chart?t=${Date.now()}`} alt="中证全指关键点图"
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
          </div>
        </div>
      )}
      {showFlow && (
        <div style={{ marginTop: 8 }}>
          <img src="/charts/fund_flow_chart.png" alt="资金流向"
            style={{ width: '100%', maxWidth: 700, borderRadius: 8, display: 'block', margin: '0 auto' }} />
        </div>
      )}
    </>
  )
}

import { useEffect, useState } from 'react'
import { fetchAllIndexData, INDEX_CODES_LIST, INDEX_CODE_NAMES } from '../lib/api'

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

type TabState = Record<string, { showScore: boolean; showChart: boolean }>

export default function MarketCycle({ mode = 'review' }: { mode?: 'review' | 'monitor' }) {
  const [allData, setAllData] = useState<Record<string, MarketData> | null>(null)
  const [activeTab, setActiveTab] = useState<string>('000985')
  const [tabStates, setTabStates] = useState<TabState>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchAllIndexData().then(data => {
      setAllData(data as Record<string, MarketData>)
      setLoading(false)
    }).catch(() => {
      const fallback: Record<string, MarketData> = {}
      INDEX_CODES_LIST.forEach(code => {
        fallback[code] = { price: '--', position: '波中', position_pct: '半仓', strategy: '中等仓位·精选个股' }
      })
      setAllData(fallback)
      setLoading(false)
    })
  }, [])

  const getTabState = (code: string) => tabStates[code] || { showScore: false, showChart: false }
  const setTabState = (code: string, patch: Partial<{ showScore: boolean; showChart: boolean }>) => {
    setTabStates(prev => ({
      ...prev,
      [code]: { ...getTabState(code), ...patch }
    }))
  }

  if (loading || !allData) return <div className="empty">加载中...</div>

  const current = allData[activeTab]
  if (!current) return <div className="empty">暂无数据</div>

  const change = current.change || 0
  const priceClass = change >= 0 ? 'value up' : 'value down'
  const pk = current.pk_score || 0
  const vl = current.vl_score || 0

  const pkDesc = pk >= 4 ? '✅ 趋势转跌+位置偏高+量价异常+方向确认 → 高度确信'
    : pk >= 3 ? '⚠️ 满足3个条件，可能偏峰'
    : pk >= 1 ? '🔸 满足1个条件，趋势有波动'
    : '— 无波峰信号'
  const vlDesc = vl >= 4 ? '✅ 趋势转涨+位置偏低+恐慌出清+方向确认 → 高度确信'
    : vl >= 3 ? '⚠️ 满足3个条件，可能偏谷'
    : vl >= 1 ? '🔸 满足1个条件'
    : '— 无波谷信号'

  const ts = getTabState(activeTab)

  return (
    <>
      {/* Tab Bar */}
      <div className="index-tab-bar">
        {INDEX_CODES_LIST.map(code => (
          <button
            key={code}
            className={`index-tab ${activeTab === code ? 'active' : ''}`}
            onClick={() => setActiveTab(code)}
          >
            {INDEX_CODE_NAMES[code] || code}
          </button>
        ))}
      </div>

      {/* Current Tab Content */}
      <div className="grid-4" id="marketGrid">
        <div className="info-card">
          <div className="label">{INDEX_CODE_NAMES[activeTab] || activeTab}</div>
          <div className={priceClass}>{current.price || '--'}</div>
          <div className="meta" id="marketChange">涨跌 {change ? `${change >= 0 ? '+' : ''}${change}%` : '--'}</div>
        </div>
        <div className="info-card">
          <div className="label">大盘周期位置</div>
          <div className="value" style={{ fontSize: 18 }}>{current.position || '--'}</div>
          <div className="meta" id="cycleScore">综合评分 {current.score ?? '--'}</div>
        </div>
        <div className="info-card">
          <div className="label">建议总仓位</div>
          <div className="value" style={{ fontSize: 18 }}>{current.position_pct || '--'}</div>
          <div className="meta" id="positionRule">建仓 {current.build_per_stock_pct || '--'}/只</div>
        </div>
        <div className="info-card">
          <div className="label">策略</div>
          <div className="value" style={{ fontSize: 14 }}>{current.strategy || '--'}</div>
          <div className="meta" id="strategyAdvice">{current.strategy || '--'}</div>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <table id="scoreDetailTable" style={{ display: ts.showScore ? '' : 'none' }}>
          <thead>
            <tr><th>维度</th><th>评分</th><th>明细</th></tr>
          </thead>
          <tbody>
            <tr><td colSpan={3} style={{ fontSize: 13, color: '#4ecdc4', fontWeight: 'bold', paddingBottom: 8 }}>{current.position}</td></tr>
            <tr>
              <td style={{ color: '#888', width: 50 }}>波峰</td>
              <td style={{ width: 50, textAlign: 'center', fontSize: 16 }}>{pk >= 4 ? '🟢' : pk >= 3 ? '🟡' : pk >= 1 ? '⚪' : '⚪'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>{pkDesc}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>波谷</td>
              <td style={{ textAlign: 'center', fontSize: 16 }}>{vl >= 4 ? '🟢' : vl >= 3 ? '🟡' : vl >= 1 ? '⚪' : '⚪'}</td>
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
              <td style={{ color: '#888', fontSize: 11 }}>MA20乖离率&gt;+1.5% {typeof current.bias20 === 'number' ? `(当前: ${current.bias20.toFixed(1)}%)` : ''}</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>③量价</td>
              <td style={{ textAlign: 'center' }}>{pk >= 3 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>放量滞涨/长上影/加速衰竭</td>
            </tr>
            <tr>
              <td style={{ color: '#888' }}>④方向</td>
              <td style={{ textAlign: 'center' }}>{pk >= 4 ? '✅' : '❌'}</td>
              <td style={{ color: '#888', fontSize: 11 }}>乖离率3日变化转负 {typeof current.bias20_chg_3d === 'number' ? `(${current.bias20_chg_3d.toFixed(1)}%)` : ''}</td>
            </tr>
            <tr><td colSpan={3} style={{ textAlign: 'center', color: '#555', fontSize: 11, paddingTop: 6 }}>pk≥4=峰 &nbsp; pk≥3=近峰 &nbsp; vl≥4=谷 &nbsp; vl≥3=近谷 &nbsp; 其余=波中</td></tr>
          </tbody>
        </table>
        <div style={{ marginTop: 6, textAlign: 'right' }}>
          <span style={{ cursor: 'pointer', color: '#4ecdc4', fontSize: 12 }} onClick={() => setTabState(activeTab, { showScore: !ts.showScore })}>
            📊 {ts.showScore ? '隐藏' : '查看'}评分明细
          </span>
          <span style={{ color: '#333', margin: '0 6px' }}>|</span>
          <span style={{ cursor: 'pointer', color: '#e94560', fontSize: 12 }} onClick={() => setTabState(activeTab, { showChart: !ts.showChart })}>
            📈 {ts.showChart ? '隐藏' : '查看'}关键点图
          </span>
        </div>
      </div>

      {ts.showChart && (
        <div style={{ marginTop: 8 }}>
          <div style={{ width: '100%', maxWidth: 750, height: 550, overflow: 'hidden', borderRadius: 8, margin: '0 auto' }}>
            <img src={`/api/index-chart?code=${activeTab}&mode=${mode}`} alt={`${INDEX_CODE_NAMES[activeTab]}关键点图`}
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
          </div>
        </div>
      )}

      {/* Comparison Table */}
      <IndexComparison data={allData} />
    </>
  )
}

function IndexComparison({ data }: { data: Record<string, MarketData> }) {
  const entries = INDEX_CODES_LIST.map(code => ({
    code,
    name: INDEX_CODE_NAMES[code] || code,
    ...data[code] || {},
  }))

  const changes = entries.map(e => e.change || 0)
  const maxChange = Math.max(...changes)
  const minChange = Math.min(...changes)

  // 对比结论
  const positions = entries.map(e => e.position || '波中')
  const isDivergent = new Set(positions).size > 2

  const bestIdx = changes.indexOf(maxChange)
  const worstIdx = changes.indexOf(minChange)
  const conclusion = isDivergent
    ? `${entries[bestIdx].name}领涨(+${maxChange.toFixed(1)}%)，${entries[worstIdx].name}最弱(${minChange.toFixed(1)}%)，指数走势分化，注意结构性机会，以对应指数为准指导仓位。`
    : `各指数走势协同，${entries[bestIdx].name}相对最强(+${maxChange.toFixed(1)}%)。当前大盘整体处于${entries[0].position || '波中'}阶段，方向一致，按仓位策略执行。`

  return (
    <div style={{ marginTop: 24, borderTop: '1px solid #2a2a4e', paddingTop: 16 }}>
      <div className="section-title" style={{ marginBottom: 12 }}>
        <span className="step">对比</span>
        多指对照表
      </div>
      <table className="comparison-table" style={{
        width: '100%', borderCollapse: 'collapse', fontSize: 13,
      }}>
        <thead>
          <tr style={{ background: '#1a1a30', borderBottom: '1px solid #2a2a4e' }}>
            <th style={{ padding: '8px 6px', textAlign: 'left', color: '#888' }}>指数</th>
            <th style={{ padding: '8px 6px', textAlign: 'right', color: '#888' }}>涨跌幅</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>周期位置</th>
            <th style={{ padding: '8px 6px', textAlign: 'right', color: '#888' }}>BIAS20</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>波峰分</th>
            <th style={{ padding: '8px 6px', textAlign: 'center', color: '#888' }}>波谷分</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(e => {
            const chg = e.change || 0
            const chgStr = chg >= 0 ? `+${chg.toFixed(1)}%` : `${chg.toFixed(1)}%`
            const isMax = chg === maxChange && entries.length > 1
            const isMin = chg === minChange && entries.length > 1
            return (
              <tr key={e.code} style={{ borderBottom: '1px solid #1e1e3a' }}>
                <td style={{ padding: '8px 6px', color: '#ccc' }}>{e.name}</td>
                <td style={{
                  padding: '8px 6px', textAlign: 'right',
                  color: chg >= 0 ? '#e94560' : '#4ecdc4',
                  fontWeight: isMax || isMin ? 700 : 400,
                }}>
                  {chgStr}
                  {isMax && <span style={{ fontSize: 10, color: '#e94560', marginLeft: 4 }}>↑最强</span>}
                  {isMin && <span style={{ fontSize: 10, color: '#4ecdc4', marginLeft: 4 }}>↓最弱</span>}
                </td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.position || '--'}</td>
                <td style={{ padding: '8px 6px', textAlign: 'right', color: '#aaa' }}>
                  {typeof e.bias20 === 'number' ? `${e.bias20 >= 0 ? '+' : ''}${e.bias20.toFixed(1)}%` : '--'}
                </td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.pk_score ?? 0}</td>
                <td style={{ padding: '8px 6px', textAlign: 'center', color: '#aaa' }}>{e.vl_score ?? 0}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div style={{
        marginTop: 12, padding: '10px 14px', background: '#111128',
        borderLeft: '3px solid #ffd700', borderRadius: 4, fontSize: 13, color: '#ddd', lineHeight: 1.6,
      }}>
        <strong style={{ color: '#ffd700' }}>📋 对比结论：</strong>{conclusion}
      </div>
    </div>
  )
}

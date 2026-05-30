import { useEffect, useState } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './PlanTracking.css'

interface PlanEntry {
  plan_date: string
  type: string
  stock: string
  code: string
  condition: string
  condition_category: string
  condition_detail: string
  stop_loss: number | null
  stop_loss_pct: number | null
  plan_close: number | null
  next_date: string | null
  next_close: number | null
  next_high: number | null
  next_low: number | null
  change_pct: number | null
  max_gain: number | null
  max_loss: number | null
  hit_stop_loss: boolean
  result: string
  executed: boolean | null
  user_note: string
}

interface Suggestion {
  type: string        // warning | best | info
  dimension: string   // condition | stock | stop_loss | type
  category: string
  rate_current: number
  rate_overall: number
  count: number
  message: string
}

interface PlanData {
  plans: PlanEntry[]
  summary: {
    total_plans: number
    success: number
    failure: number
    flat: number
    pending: number
    no_data: number
    success_rate: number
    avg_gain_pct: number
    avg_loss_pct: number
    best_gain: number
    worst_loss: number
    win_loss_ratio: number
  }
  by_condition: Record<string, { total: number; success: number; failure: number; flat: number }>
  by_type: Record<string, { total: number; success: number; failure: number; flat: number }>
  suggestions: Suggestion[]
  last_updated: string
}

const RESULT_LABELS: Record<string, string> = {
  success: '✅ 成功',
  failure: '❌ 失败',
  flat: '➖ 平盘',
  pending: '⏳ 待更新',
  no_data: '❓ 无数据',
}

const TYPE_LABELS: Record<string, string> = {
  buy: '🟢 买入',
  sell: '🔴 卖出',
  watch: '👁️ 观察',
}

function fmtDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function todayStr(): string {
  return fmtDate(new Date())
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return fmtDate(d)
}

export default function PlanTracking() {
  const [data, setData] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [condCollapsed, setCondCollapsed] = useState(false)
  const [sugCollapsed, setSugCollapsed] = useState(false)
  const [typeFilter, setTypeFilter] = useState('all')
  const [resultFilter, setResultFilter] = useState('all')
  const [startDate, setStartDate] = useState(daysAgo(30))
  const [endDate, setEndDate] = useState(todayStr())

  useEffect(() => {
    loadData()
  }, [])

  function loadData(sd?: string, ed?: string) {
    const s = sd || startDate
    const e = ed || endDate
    setLoading(true)
    setError('')
    const params = new URLSearchParams()
    if (s) params.set('start_date', s)
    if (e) params.set('end_date', e)
    fetch(`/api/plan-tracking?${params.toString()}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => setData(d))
      .catch(e => setError(e.message || '加载失败'))
      .finally(() => setLoading(false))
  }

  function handleRefresh() {
    setLoading(true)
    fetch('/api/plan-tracking/refresh', { method: 'POST' })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(() => loadData())
      .catch(e => { setError(e.message || '刷新失败'); setLoading(false) })
  }

  function setStartDateSafe(v: string) {
    const sd = new Date(v)
    const ed = new Date(endDate)
    if ((ed.getTime() - sd.getTime()) / (1000 * 86400) > 30) {
      // 超过30天，自动调整结束日期为起始+30天
      const newEnd = new Date(sd)
      newEnd.setDate(newEnd.getDate() + 30)
      if (newEnd > new Date()) {
        setEndDate(todayStr())
      } else {
        setEndDate(fmtDate(newEnd))
      }
    }
    setStartDate(v)
    loadData(v, endDate)
  }

  function setEndDateSafe(v: string) {
    const sd = new Date(startDate)
    const ed = new Date(v)
    if ((ed.getTime() - sd.getTime()) / (1000 * 86400) > 30) {
      return // 超过30天不予选择
    }
    setEndDate(v)
    loadData(startDate, v)
  }

  async function toggleExecuted(entry: PlanEntry) {
    const newVal = entry.executed === true ? false : true
    try {
      await fetch('/api/plan-tracking/annotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_date: entry.plan_date,
          type: entry.type,
          stock: entry.stock,
          executed: newVal,
          user_note: entry.user_note,
        }),
      })
      setData(prev => {
        if (!prev) return prev
        return {
          ...prev,
          plans: prev.plans.map(p =>
            p.plan_date === entry.plan_date && p.type === entry.type && p.stock === entry.stock
              ? { ...p, executed: newVal }
              : p
          ),
        }
      })
    } catch { /* silent */ }
  }

  const s = data?.summary
  const allPlans = data?.plans || []
  const trackingPlans = allPlans.filter(p => p.type !== 'watch')
  const suggestions = data?.suggestions || []

  // 过滤
  let filteredPlans = [...trackingPlans]
  if (typeFilter !== 'all') filteredPlans = filteredPlans.filter(p => p.type === typeFilter)
  if (resultFilter !== 'all') filteredPlans = filteredPlans.filter(p => p.result === resultFilter)
  filteredPlans.sort((a, b) => b.plan_date.localeCompare(a.plan_date))

  const hasData = allPlans.length > 0

  return (
    <div className="page-wrap">
      <NavBar />
      <div className="content" style={{ maxWidth: 900, margin: '0 auto' }}>
        <div className="section" style={{ marginTop: 16 }}>
          <div className="section-title">
            <span className="step">📊</span>
            操作计划追踪
          </div>

          {/* 日期选择器 */}
          <div className="info-card" style={{ marginTop: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: '#888' }}>📅</span>
            <input type="date" value={startDate} max={todayStr()}
              onChange={e => setStartDateSafe(e.target.value)}
              style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 6px', color: '#e0e0e0', fontSize: 11 }} />
            <span style={{ color: '#555' }}>—</span>
            <input type="date" value={endDate} min={startDate} max={todayStr()}
              onChange={e => setEndDateSafe(e.target.value)}
              style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 6px', color: '#e0e0e0', fontSize: 11 }} />
            <span style={{ fontSize: 10, color: '#666' }}>（最多30天）</span>
          </div>

          {!hasData && !loading && (
            <div className="empty" style={{ padding: 40, textAlign: 'center' }}>
              暂无计划数据，请先在<a href="/workbench" style={{ color: '#4ecdc4' }}>工作台</a>制定明日计划
            </div>
          )}

          {loading && !data && (
            <div className="empty">正在加载计划追踪数据…</div>
          )}

          {error && (
            <div className="empty" style={{ color: '#e94560' }}>⚠️ {error}</div>
          )}

          {s && hasData && (
            <>
              {/* 统计卡片行 */}
              <div className="card-row">
                <div className="stat-card">
                  <div className="stat-value" style={{ color: s.success_rate >= 50 ? '#4ecdc4' : '#e94560' }}>
                    {s.success_rate}%
                  </div>
                  <div className="stat-label">成功率</div>
                  <div className="stat-sub">{s.success}/{s.total_plans}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#4ecdc4' }}>
                    +{s.avg_gain_pct}%
                  </div>
                  <div className="stat-label">平均盈利</div>
                  <div className="stat-sub">最佳 +{s.best_gain}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{s.win_loss_ratio}</div>
                  <div className="stat-label">盈亏比</div>
                  <div className="stat-sub">最差 {s.worst_loss}%</div>
                </div>
              </div>

              {/* 📋 系统建议 */}
              {suggestions.length > 0 && (
                <div className="info-card" style={{ marginTop: 12, padding: 10 }}>
                  <div
                    style={{ fontSize: 12, color: '#888', marginBottom: 6, cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => setSugCollapsed(v => !v)}
                  >
                    📋 系统建议 ({suggestions.length}) {sugCollapsed ? '▶' : '▼'}
                  </div>
                  {!sugCollapsed && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {suggestions.map((sg, i) => {
                        const icon = sg.type === 'warning' ? '⚠️' : sg.type === 'best' ? '💡' : 'ℹ️'
                        const bg = sg.type === 'warning' ? 'rgba(233,69,96,0.08)' : 'rgba(78,205,196,0.08)'
                        const borderColor = sg.type === 'warning' ? 'rgba(233,69,96,0.3)' : 'rgba(78,205,196,0.3)'
                        return (
                          <div key={i} style={{
                            background: bg, border: `1px solid ${borderColor}`,
                            borderRadius: 6, padding: '6px 10px', fontSize: 11, lineHeight: 1.5
                          }}>
                            <span style={{ marginRight: 4 }}>{icon}</span>
                            {sg.message}
                            <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>
                              样本数: {sg.count} | 当前成功率: {sg.rate_current}%
                              {sg.rate_overall > 0 && ` | 整体: ${sg.rate_overall}%`}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* 按买入/卖出分类 */}
              {data.by_type && (
                <div className="info-card" style={{ marginTop: 12, padding: 10 }}>
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>📂 按交易方向</div>
                  <div className="type-row">
                    {Object.entries(data.by_type).map(([t, st]) => {
                      const rate = st.total > 0 ? (st.success / st.total * 100).toFixed(1) : '--'
                      return (
                        <div key={t} className="type-chip" style={{ background: t === 'buy' ? 'rgba(34,197,94,0.1)' : 'rgba(233,69,96,0.1)' }}>
                          <span style={{ fontSize: 11 }}>{TYPE_LABELS[t] || t}</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#e0e0e0' }}>{rate}%</span>
                          <span style={{ fontSize: 10, color: '#888' }}>{st.success}胜/{st.failure}败/{st.flat}平</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* 按条件类型统计 */}
              {data.by_condition && Object.keys(data.by_condition).length > 0 && (
                <div className="info-card" style={{ marginTop: 12, padding: 10 }}>
                  <div
                    style={{ fontSize: 12, color: '#888', marginBottom: 6, cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => setCondCollapsed(v => !v)}
                  >
                    📈 按条件类型 {condCollapsed ? '▶' : '▼'}
                  </div>
                  {!condCollapsed && (
                    <div className="cond-grid">
                      {Object.entries(data.by_condition).map(([cat, st]) => {
                        const rate = st.total > 0 ? (st.success / st.total * 100).toFixed(1) : '--'
                        return (
                          <div key={cat} className="cond-item">
                            <span style={{ fontSize: 11, color: '#e0e0e0' }}>{cat}</span>
                            <span style={{ fontSize: 12, fontWeight: 600, color: Number(rate) >= 50 ? '#4ecdc4' : '#e94560' }}>{rate}%</span>
                            <span style={{ fontSize: 10, color: '#888' }}>{st.success}/{st.total}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* 过滤栏 */}
              <div className="filter-bar" style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#888' }}>筛选：</span>
                <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                  style={selectStyle}>
                  <option value="all">全部方向</option>
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                </select>
                <select value={resultFilter} onChange={e => setResultFilter(e.target.value)}
                  style={selectStyle}>
                  <option value="all">全部结果</option>
                  <option value="success">成功</option>
                  <option value="failure">失败</option>
                  <option value="flat">平盘</option>
                  <option value="pending">待更新</option>
                  <option value="no_data">无数据</option>
                </select>
                <button className="action-btn sec" style={{ fontSize: 11, padding: '3px 10px', marginLeft: 'auto' }} onClick={handleRefresh}>
                  🔄 刷新
                </button>
              </div>

              {/* 计划详情表格 */}
              <div className="plan-table-wrap" style={{ marginTop: 8, overflowX: 'auto' }}>
                <table className="plan-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>方向</th>
                      <th>股票</th>
                      <th>条件</th>
                      <th>计划收盘</th>
                      <th>次日收盘</th>
                      <th>涨跌幅</th>
                      <th>结果</th>
                      <th>执行</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPlans.length === 0 && (
                      <tr><td colSpan={10} style={{ textAlign: 'center', color: '#666', padding: 20 }}>无匹配计划</td></tr>
                    )}
                    {filteredPlans.map((p, i) => (
                      <tr key={`${p.plan_date}-${p.type}-${p.stock}-${i}`}>
                        <td className="cell-date">{p.plan_date.slice(5)}</td>
                        <td><span className={`type-badge ${p.type}`}>{TYPE_LABELS[p.type] || p.type}</span></td>
                        <td className="cell-stock">
                          {p.stock}
                          {p.code && <span className="cell-code">{p.code}</span>}
                        </td>
                        <td className="cell-cond">{p.condition || '--'}</td>
                        <td className="cell-num">{p.plan_close != null ? p.plan_close.toFixed(2) : '--'}</td>
                        <td className="cell-num">{p.next_close != null ? p.next_close.toFixed(2) : '--'}</td>
                        <td className={`cell-change ${p.change_pct != null ? (p.change_pct >= 0 ? 'up' : 'down') : ''}`}>
                          {p.change_pct != null ? `${p.change_pct >= 0 ? '+' : ''}${p.change_pct.toFixed(2)}%` : '--'}
                        </td>
                        <td>{RESULT_LABELS[p.result] || p.result}</td>
                        <td>
                          {p.result === 'success' || p.result === 'failure' || p.result === 'flat' ? (
                            <span
                              className={`exec-badge ${p.executed === true ? 'yes' : p.executed === false ? 'no' : 'unk'}`}
                              onClick={() => toggleExecuted(p)}
                              title="点击切换"
                            >
                              {p.executed === true ? '✅ 已执行' : p.executed === false ? '❌ 未执行' : '⬜ 待标记'}
                            </span>
                          ) : (
                            <span style={{ color: '#555', fontSize: 10 }}>--</span>
                          )}
                        </td>
                        <td className="cell-note">{p.user_note || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 更新时间 */}
              <div style={{ fontSize: 10, color: '#444', textAlign: 'right', marginTop: 6 }}>
                最后更新: {data.last_updated?.slice(0, 16) || '--'}
              </div>
            </>
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  background: '#1a1a30',
  border: '1px solid #2a2a4e',
  borderRadius: 4,
  padding: '3px 8px',
  color: '#e0e0e0',
  fontSize: 11,
}

import { useEffect, useState } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './Workbench.css'

interface PlanItem {
  stock?: string
  sector?: string
  condition?: string
  focus?: string
  qty?: string
  status: string
  alert?: AlertItem | null
  stop_loss?: number
  stop_loss_pct?: number
}

interface AlertItem {
  type: 'price' | 'deviation' | 'time'
  stock?: string
  condition: string
  enabled: boolean
}

interface WorkbenchData {
  date?: string
  todos?: { text: string; done: boolean }[]
  plan?: { buy: PlanItem[]; sell: PlanItem[]; watch: PlanItem[] }
  alerts?: AlertItem[]
  operations?: string
  execution_review?: string
  reflection?: { discipline: string; rating: string; learned: string }
}

interface ReviewSummary {
  market?: string
  mainline?: string
  signals?: number
}

interface SuggestionItem {
  stock?: string
  name?: string
  code?: string
  action?: string
  reason?: string
  priority?: string
  sector?: string
  buy_point?: string
  change?: number
  focus?: string
  text?: string
  stop_loss?: number
  stop_loss_pct?: number
}

interface SuggestionsData {
  holdings_action: SuggestionItem[]
  buy_priority: SuggestionItem[]
  risk_items: SuggestionItem[]
}

export default function Workbench() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [data, setData] = useState<WorkbenchData>({})
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary>({})
  const [suggestions, setSuggestions] = useState<SuggestionsData | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [showAlertModal, setShowAlertModal] = useState<{ type: string; idx: number } | null>(null)

  // 加载数据
  useEffect(() => {
    loadLog(date)
    fetch('/api/review/today')
      .then(r => r.json())
      .then(d => setReviewSummary({
        market: d.market?.position || '--',
        mainline: (d.mainline?.lines || []).map((l: any) => l.name).join(', ') || '--',
        signals: d.buy_signals?.length || 0,
      }))
      .catch(() => {})
    // 加载复盘建议
    fetch('/api/workbench/suggestions')
      .then(r => r.json())
      .then(d => setSuggestions(d))
      .catch(() => {})
  }, [date])

  async function loadLog(d: string) {
    try {
      const r = await fetch(`/api/workbench/get?date=${d}`)
      setData(await r.json())
    } catch {
      setData({})
    }
  }

  /** 核心持久化 */
  function persist(updatedData: WorkbenchData) {
    const payload: WorkbenchData = {
      ...updatedData,
      date,
      operations: (document.getElementById('opText') as HTMLTextAreaElement)?.value || '',
      execution_review: (document.getElementById('execReviewText') as HTMLTextAreaElement)?.value || '',
      reflection: {
        discipline: (document.getElementById('refDiscipline') as HTMLSelectElement)?.value || '',
        rating: (document.getElementById('refRating') as HTMLSelectElement)?.value || '',
        learned: (document.getElementById('refLearned') as HTMLTextAreaElement)?.value || '',
      },
    }
    fetch('/api/workbench/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {})
  }

  function save() {
    persist(data)
    showToast('✅ 日志已保存')
  }

  function showToast(msg: string, isError?: boolean) {
    const el = document.createElement('div')
    el.textContent = msg
    el.style.cssText = `position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid ${isError ? '#e94560' : '#22c55e'};color:${isError ? '#e94560' : '#22c55e'};padding:8px 20px;border-radius:6px;font-size:13px;z-index:999`
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2500)
  }

  const todos = data.todos || []
  const plan = data.plan || { buy: [], sell: [], watch: [] }
  const alerts = data.alerts || []

  // ─── 勾选管理 ────────────────────────────
  function toggleCheck(id: string) {
    setCheckedIds(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }

  function importToPlan() {
    const newPlan = { buy: [...plan.buy], sell: [...plan.sell], watch: [...plan.watch] }
    const newAlerts: AlertItem[] = [...alerts]

    if (!suggestions) return

    // holdings_action → 根据action决定放buy/sell/watch
    suggestions.holdings_action.forEach((item, i) => {
      const id = `ha-${i}`
      if (!checkedIds.has(id)) return
      const stockName = item.stock || ''
      const act = (item.action || '').toLowerCase()
      const pi: PlanItem = { stock: stockName, condition: item.reason || '', qty: '', status: 'pending', alert: null, stop_loss: item.stop_loss, stop_loss_pct: item.stop_loss_pct }
      if (act.startsWith('卖出')) {
        newPlan.sell.push(pi)
      } else if (act.includes('买入') || act.includes('执行') || act.includes('加仓')) {
        newPlan.buy.push(pi)
      } else {
        newPlan.watch.push({ ...pi, focus: item.reason || '' })
      }
    })

    // buy_priority → 全放买入
    suggestions.buy_priority.forEach((item, i) => {
      const id = `bp-${i}`
      if (!checkedIds.has(id)) return
      const name = item.name || ''
      const code = item.code || ''
      newPlan.buy.push({
        stock: `${name}(${code})`,
        condition: `${item.buy_point || ''} ${item.change != null ? `${item.change > 0 ? '+' : ''}${item.change}%` : ''}`,
        qty: '', status: 'pending', alert: null,
        stop_loss: item.stop_loss,
        stop_loss_pct: item.stop_loss_pct,
      })
    })

    // risk_items → 观察
    suggestions.risk_items.forEach((item, i) => {
      const id = `ri-${i}`
      if (!checkedIds.has(id)) return
      newPlan.watch.push({ sector: '大盘', focus: item.text || item.focus || '', status: 'pending', alert: null })
      // 风险项自动加报警
      if (item.text?.includes('卖出')) {
        newAlerts.push({ type: 'deviation', stock: item.text?.match(/[\u4e00-\u9fa5]+/)?.[0] || '', condition: '触发卖出信号', enabled: true })
      }
    })

    const newData = { ...data, plan: newPlan, alerts: newAlerts }
    setData(newData)
    persist(newData)
    setCheckedIds(new Set())
    showToast(`🔄 已导入 ${checkedIds.size} 项到计划`)
  }

  const checkedCount = checkedIds.size

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>🧑 交易工作台</h1>
        <div className="sub">复盘建议 → 筛选 → 定计划 → 写日志</div>
        <div className="date-badge">{date}</div>
      </div>

      <div className="container">
        {/* STEP 1: 今日复盘摘要 */}
        <div className="section">
          <div className="section-title">
            <span className="step">STEP 1</span>
            今日复盘摘要
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>
              <a href="/review" style={{ color: '#22c55e' }}>📎 打开完整复盘</a>
            </span>
          </div>
          <div className="grid-3">
            <div className="info-card">
              <div className="label">大盘周期</div>
              <div className="value" style={{ fontSize: 16 }}>{reviewSummary.market || '--'}</div>
            </div>
            <div className="info-card">
              <div className="label">主线</div>
              <div className="meta" style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{reviewSummary.mainline || '--'}</div>
            </div>
            <div className="info-card">
              <div className="label">买点信号</div>
              <div className="value" style={{ fontSize: 16 }}>{reviewSummary.signals ?? 0}</div>
              <div className="meta">只</div>
            </div>
          </div>
        </div>

        {/* TODO: 待办 */}
        <div className="section">
          <div className="section-title">
            <span className="step">TODO</span>
            📌 待办
          </div>
          <div id="todoList">
            {todos.length === 0 ? (
              <div className="empty">暂无待办，下方添加</div>
            ) : (
              todos.map((t, i) => (
                <div key={i} className="todo-item" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
                  <input type="checkbox" checked={t.done} onChange={() => {
                    const newTodos = [...todos]
                    newTodos[i] = { ...newTodos[i], done: !newTodos[i].done }
                    setData({ ...data, todos: newTodos })
                    persist({ ...data, todos: newTodos })
                  }} />
                  <span style={{ textDecoration: t.done ? 'line-through' : 'none', color: t.done ? '#555' : '#e0e0e0' }}>{t.text}</span>
                  <span style={{ marginLeft: 'auto', color: '#e94560', cursor: 'pointer', fontSize: 11 }} onClick={() => {
                    const newTodos = todos.filter((_, j) => j !== i)
                    setData({ ...data, todos: newTodos })
                    persist({ ...data, todos: newTodos })
                  }}>✕</span>
                </div>
              )))}
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: '#4ecdc4', cursor: 'pointer' }} onClick={() => {
            const text = prompt('待办内容：')
            if (!text) return
            const newTodos = [...todos, { text, done: false }]
            setData({ ...data, todos: newTodos })
            persist({ ...data, todos: newTodos })
          }}>＋ 添加待办</div>
        </div>

        {/* 📋 复盘建议（新） */}
        <div className="section">
          <div className="section-title">
            <span className="step">STEP 2</span>
            📋 复盘建议
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>勾选 → 导入到计划</span>
          </div>
          {!suggestions ? (
            <div className="empty">加载复盘建议中…</div>
          ) : (
            <>
              {/* 持仓操作建议 */}
              {suggestions.holdings_action.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>📊 持仓操作建议</div>
                  {suggestions.holdings_action.map((item, i) => {
                    const id = `ha-${i}`
                    const priColor = item.priority === '高' ? '#e94560' : item.priority === '中' ? '#ffd700' : '#888'
                    return (
                      <div key={id} onClick={() => toggleCheck(id)}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, marginBottom: 2, cursor: 'pointer', background: checkedIds.has(id) ? 'rgba(34,197,94,0.08)' : 'transparent', border: checkedIds.has(id) ? '1px solid rgba(34,197,94,0.3)' : '1px solid transparent' }}>
                        <span style={{ color: checkedIds.has(id) ? '#22c55e' : '#555', fontSize: 14 }}>{checkedIds.has(id) ? '☑' : '☐'}</span>
                        <span style={{ fontSize: 10, color: priColor, fontWeight: 600 }}>[{item.priority}]</span>
                        <span style={{ fontSize: 12, color: '#e0e0e0' }}>{item.stock || ''}</span>
                        <span style={{ fontSize: 11, color: '#22c55e' }}>{item.action || ''}</span>
                        <span style={{ fontSize: 10, color: '#888' }}>{item.reason || ''}</span>
                        {(item.stop_loss != null || item.stop_loss_pct != null) && (
                          <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                            {item.stop_loss != null ? `止损${item.stop_loss}` : ''}
                            {item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}
                          </span>
                        )}
                        {item.change != null && (
                          <span style={{ fontSize: 11, color: item.change >= 0 ? '#e94560' : '#22c55e' }}>{item.change > 0 ? '+' : ''}{item.change}%</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* 买入候选 */}
              {suggestions.buy_priority.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>🎯 买入候选</div>
                  {suggestions.buy_priority.map((item, i) => {
                    const id = `bp-${i}`
                    const bpColors: Record<string, string> = { '中继买点': '#ffd700', '突破买点': '#22c55e', 'BIAS5乖离率买入': '#2196f3' }
                    const bpColor = bpColors[item.buy_point || ''] || '#888'
                    return (
                      <div key={id} onClick={() => toggleCheck(id)}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, marginBottom: 2, cursor: 'pointer', background: checkedIds.has(id) ? 'rgba(34,197,94,0.08)' : 'transparent', border: checkedIds.has(id) ? '1px solid rgba(34,197,94,0.3)' : '1px solid transparent' }}>
                        <span style={{ color: checkedIds.has(id) ? '#22c55e' : '#555', fontSize: 14 }}>{checkedIds.has(id) ? '☑' : '☐'}</span>
                        <span style={{ fontSize: 10, color: bpColor, fontWeight: 600 }}>[{item.priority}]</span>
                        <span style={{ fontSize: 12, color: '#e0e0e0' }}>{item.name || ''}({item.code || ''})</span>
                        <span style={{ fontSize: 10, color: bpColor }}>{item.buy_point || ''}</span>
                        <span style={{ fontSize: 10, color: '#888' }}>{item.structure || ''}{item.structure && item.stage ? '·' : ''}{item.stage || ''}</span>
                        {(item.stop_loss != null || item.stop_loss_pct != null) && (
                          <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                            {item.stop_loss != null ? `止损${item.stop_loss}` : ''}
                            {item.stop_loss_pct != null ? `(${item.stop_loss_pct}%)` : ''}
                          </span>
                        )}
                        {item.change != null && (
                          <span style={{ fontSize: 11, color: item.change >= 0 ? '#e94560' : '#22c55e' }}>{item.change > 0 ? '+' : ''}{item.change}%</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* 风险提示 */}
              {suggestions.risk_items.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>⚠️ 风险提示</div>
                  {suggestions.risk_items.map((item, i) => {
                    const id = `ri-${i}`
                    return (
                      <div key={id} onClick={() => toggleCheck(id)}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, marginBottom: 2, cursor: 'pointer', background: checkedIds.has(id) ? 'rgba(34,197,94,0.08)' : 'transparent', border: checkedIds.has(id) ? '1px solid rgba(34,197,94,0.3)' : '1px solid transparent' }}>
                        <span style={{ color: checkedIds.has(id) ? '#22c55e' : '#555', fontSize: 14 }}>{checkedIds.has(id) ? '☑' : '☐'}</span>
                        <span style={{ fontSize: 12, color: '#ffd700' }}>{item.text || item.focus || ''}</span>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* 导入按钮 */}
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="action-btn green" onClick={importToPlan} disabled={checkedCount === 0}
                  style={{ opacity: checkedCount === 0 ? 0.4 : 1 }}>
                  🔄 导入已选项到计划 ({checkedCount})
                </button>
                <button className="action-btn sec" onClick={() => setCheckedIds(new Set())}
                  style={{ opacity: checkedCount === 0 ? 0.3 : 1 }} disabled={checkedCount === 0}>
                  清空勾选
                </button>
              </div>
            </>
          )}
        </div>

        {/* PLAN: 明日计划 */}
        <div className="section">
          <div className="section-title">
            <span className="step">PLAN</span>
            📋 明日计划
          </div>
          {(['buy', 'sell', 'watch'] as const).map(type => {
            const label = type === 'buy' ? '🟢 买入' : type === 'sell' ? '🔴 卖出' : '👁️ 观察'
            const items = plan[type] || []
            return (
              <div key={type} style={{ marginTop: 12 }}>
                <div style={{ display: 'inline-block', background: type === 'buy' ? 'rgba(34,197,94,0.15)' : type === 'sell' ? 'rgba(233,69,96,0.15)' : 'rgba(255,215,0,0.15)', color: type === 'buy' ? '#22c55e' : type === 'sell' ? '#e94560' : '#ffd700', padding: '2px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600 }}>{label}</div>
                {items.map((p, i) => (
                  <div key={i} style={{ marginBottom: 2 }}>
                    <div className="plan-row" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6 }}>
                      <span style={{ fontSize: 12, color: '#e0e0e0' }}>{p.stock || (type === 'watch' ? (p.sector || '') : '') || '--'}</span>
                      <span style={{ fontSize: 10, color: '#888' }}>{type === 'watch' ? (p.focus || '') : (p.condition || '')}</span>
                      {(p.stop_loss != null || p.stop_loss_pct != null) && (
                        <span style={{ fontSize: 10, color: '#ff9800', whiteSpace: 'nowrap' }}>
                          {p.stop_loss != null ? `止损${p.stop_loss}` : ''}
                          {p.stop_loss_pct != null ? `(${p.stop_loss_pct}%)` : ''}
                        </span>
                      )}
                      {/* 🔔 报警按钮 */}
                      <span onClick={() => togglePlanAlert(type, i)}
                        style={{ cursor: 'pointer', fontSize: 13, color: p.alert ? '#ff9800' : '#555' }}
                        title={p.alert ? '已设置报警' : '点击设置报警'}>
                        {p.alert ? '🔔' : '🔕'}
                      </span>
                      <span style={{ color: '#e94560', cursor: 'pointer', fontSize: 11, marginLeft: 'auto' }} onClick={() => removePlanRow(type, i)}>✕</span>
                    </div>
                    {/* 报警配置（行内展开） */}
                    {p.alert && (
                      <div style={{ display: 'flex', gap: 6, padding: '4px 8px 4px 14px', background: 'rgba(255,152,0,0.06)', borderRadius: 4, marginTop: 2 }}>
                        <select value={p.alert.type} onChange={e => updateAlert(type, i, 'type', e.target.value)}
                          style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '2px 4px', color: '#e0e0e0', fontSize: 10 }}>
                          <option value="price">🔴 价格报警</option>
                          <option value="deviation">🟡 偏差报警</option>
                          <option value="time">⏰ 时间报警</option>
                        </select>
                        {p.alert.type === 'deviation' ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                            <input type="number" value={p.alert.condition || '6'} onChange={e => updateAlert(type, i, 'condition', e.target.value)}
                              style={{ width: 50, background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '2px 6px', color: '#e0e0e0', fontSize: 10, textAlign: 'right' }} min={1} max={20} step={0.5} />
                            <span style={{ fontSize: 10, color: '#888' }}>%</span>
                          </div>
                        ) : (
                          <input value={p.alert.condition || ''} onChange={e => updateAlert(type, i, 'condition', e.target.value)}
                            placeholder={p.alert.type === 'price' ? '自动绑止损价' : '条件说明'} style={{ flex: 1, background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '2px 6px', color: '#e0e0e0', fontSize: 10 }} />
                        )}
                        <label style={{ fontSize: 10, color: '#888', display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
                          <input type="checkbox" checked={p.alert.enabled} onChange={e => updateAlert(type, i, 'enabled', e.target.checked ? 'true' : 'false')} />
                          启用
                        </label>
                        <span style={{ color: '#e94560', cursor: 'pointer', fontSize: 11 }} onClick={() => togglePlanAlert(type, i)}>✕</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          })}
        </div>

        {/* DONE: 今日操作 */}
        <div className="section">
          <div className="section-title">
            <span className="step">DONE</span>
            ✍️ 今日操作
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>自由记录</span>
          </div>
          <textarea id="opText" defaultValue={data.operations || ''} style={{ width: '100%', minHeight: 80, background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 6, color: '#e0e0e0', fontSize: 13, padding: 10, resize: 'vertical', boxSizing: 'border-box' }} placeholder="记录今天的买卖操作、成交价格、执行情况…" />
        </div>

        {/* REVIEW: 执行复盘 */}
        <div className="section">
          <div className="section-title">
            <span className="step">REVIEW</span>
            🔄 执行复盘
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>昨日计划执行情况</span>
          </div>
          <YesterdayPlan date={date} />
          <textarea id="execReviewText" defaultValue={data.execution_review || ''} style={{ width: '100%', minHeight: 60, background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 6, color: '#e0e0e0', fontSize: 13, padding: 10, resize: 'vertical', boxSizing: 'border-box', marginTop: 8 }} placeholder="补充说明：哪些执行了，哪些没触发，有什么偏差…" />
        </div>

        {/* LEARN: 今日反思 */}
        <div className="section">
          <div className="section-title">
            <span className="step">LEARN</span>
            💡 今日反思
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>纪律遵守</div>
              <select id="refDiscipline" defaultValue={data.reflection?.discipline || ''} style={{ width: '100%', background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '5px 8px', color: '#e0e0e0', fontSize: 12 }}>
                <option value="">--</option>
                <option value="✅ 完全按计划执行">✅ 完全按计划执行</option>
                <option value="⚠️ 大部分执行，有1处偏差">⚠️ 大部分执行，有1处偏差</option>
                <option value="❌ 严重偏离计划">❌ 严重偏离计划</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>评分</div>
              <select id="refRating" defaultValue={data.reflection?.rating || ''} style={{ width: '100%', background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '5px 8px', color: '#e0e0e0', fontSize: 12 }}>
                <option value="">--</option>
                <option value="⭐⭐⭐⭐⭐">⭐⭐⭐⭐⭐</option>
                <option value="⭐⭐⭐⭐">⭐⭐⭐⭐</option>
                <option value="⭐⭐⭐">⭐⭐⭐</option>
                <option value="⭐⭐">⭐⭐</option>
                <option value="⭐">⭐</option>
              </select>
            </div>
          </div>
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>学到了什么 / 改进点</div>
            <textarea id="refLearned" defaultValue={data.reflection?.learned || ''} style={{ width: '100%', minHeight: 60, background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 6, color: '#e0e0e0', fontSize: 13, padding: 10, resize: 'vertical', boxSizing: 'border-box' }} placeholder="今天做对了什么？做错了什么？下次怎么改进？" />
          </div>
        </div>

        {/* 操作栏 */}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="action-btn green" onClick={save}>💾 保存交易日志</button>
          <button className="action-btn sec" onClick={() => {
            const d = new Date(date)
            d.setDate(d.getDate() - 1)
            setDate(d.toISOString().slice(0, 10))
          }}>← 前一天</button>
          <button className="action-btn sec" onClick={() => {
            const d = new Date(date)
            d.setDate(d.getDate() + 1)
            setDate(d.toISOString().slice(0, 10))
          }}>后一天 →</button>
        </div>
      </div>

      <BottomNav />
      <div className="footer">3L 交易体系 · 交易工作台 · 勾选建议→定计划→写日志</div>
    </>
  )

  // helpers
  function removePlanRow(type: string, i: number) {
    const newPlan = { ...plan }
    const items = (newPlan[type as keyof typeof newPlan] || []).filter((_, j) => j !== i)
    const newData = { ...data, plan: { ...newPlan, [type]: items } }
    setData(newData)
    persist(newData)
  }

  function togglePlanAlert(type: string, idx: number) {
    const newPlan = { ...plan }
    const items = [...(newPlan[type as keyof typeof newPlan] || [])]
    const item = items[idx]
    if (item.alert) {
      items[idx] = { ...item, alert: null }
    } else {
      const stockName = item.stock || item.sector || ''
      items[idx] = { ...item, alert: { type: 'price', stock: stockName, condition: '', enabled: true } }
    }
    const newData = { ...data, plan: { ...newPlan, [type]: items } }
    setData(newData)
    persist(newData)
  }

  function updateAlert(type: string, idx: number, field: string, value: string) {
    const newPlan = { ...plan }
    const items = [...(newPlan[type as keyof typeof newPlan] || [])]
    const item = items[idx]
    if (item.alert) {
      items[idx] = { ...item, alert: { ...item.alert, [field]: value } }
      const newData = { ...data, plan: { ...newPlan, [type]: items } }
      setData(newData)
      persist(newData)
    }
  }
}

function YesterdayPlan({ date }: { date: string }) {
  const [prevPlan, setPrevPlan] = useState<string>('加载中…')

  useEffect(() => {
    const d = new Date(date)
    d.setDate(d.getDate() - 1)
    const prev = d.toISOString().slice(0, 10)
    fetch(`/api/workbench/get?date=${prev}`)
      .then(r => r.json())
      .then(data => {
        const plan = data.plan || {}
        const parts: string[] = []
        if ((plan.buy || []).length > 0) {
          parts.push('🟢 买入：' + plan.buy.map((p: any) => `${p.stock || '--'}(${p.condition || ''})`).join('、'))
        }
        if ((plan.sell || []).length > 0) {
          parts.push('🔴 卖出：' + plan.sell.map((p: any) => `${p.stock || '--'}(${p.condition || ''})`).join('、'))
        }
        if ((plan.watch || []).length > 0) {
          parts.push('👁️ 观察：' + plan.watch.map((p: any) => `${p.stock || p.sector || '--'}→${p.focus || ''}`).join('、'))
        }
        if (parts.length === 0) parts.push('昨日无计划')
        setPrevPlan(parts.join('<br>'))
      })
      .catch(() => setPrevPlan('昨日无计划数据'))
  }, [date])

  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px dashed #2a2a4e', borderRadius: 8, padding: 12 }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>📋 昨日计划</div>
      <div style={{ fontSize: 11 }} dangerouslySetInnerHTML={{ __html: prevPlan }} />
    </div>
  )
}

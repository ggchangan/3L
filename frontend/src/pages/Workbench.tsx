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
}

interface WorkbenchData {
  date?: string
  todos?: { text: string; done: boolean }[]
  plan?: { buy: PlanItem[]; sell: PlanItem[]; watch: PlanItem[] }
  operations?: string
  execution_review?: string
  reflection?: { discipline: string; rating: string; learned: string }
}

interface ReviewSummary {
  market?: string
  mainline?: string
  signals?: number
}

export default function Workbench() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [data, setData] = useState<WorkbenchData>({})
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary>({})

  // 加载数据
  useEffect(() => {
    loadLog(date)
    fetch('/api/review/get')
      .then(r => r.json())
      .then(d => setReviewSummary({
        market: d.market?.structure || '--',
        mainline: d.mainline?.primary || '--',
        signals: d.timing_signals?.length || 0,
      }))
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

  function save() {
    const payload: WorkbenchData = {
      ...data,
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
    }).then(r => r.json()).then(d => {
      if (d.success) showToast('✅ 日志已保存')
      else showToast('⚠️ 保存失败', true)
    }).catch(() => showToast('⚠️ 保存失败', true))
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

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>🧑 交易工作台</h1>
        <div className="sub">分析 → 定计划 → 写日志</div>
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
                  }} />
                  <span style={{ textDecoration: t.done ? 'line-through' : 'none', color: t.done ? '#555' : '#e0e0e0' }}>{t.text}</span>
                  <span style={{ marginLeft: 'auto', color: '#e94560', cursor: 'pointer', fontSize: 11 }} onClick={() => {
                    const newTodos = todos.filter((_, j) => j !== i)
                    setData({ ...data, todos: newTodos })
                  }}>✕</span>
                </div>
              ))
            )}
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: '#4ecdc4', cursor: 'pointer' }} onClick={() => {
            const text = prompt('待办内容：')
            if (!text) return
            setData({ ...data, todos: [...todos, { text, done: false }] })
          }}>＋ 添加待办</div>
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
                  <div key={i} className="plan-row" style={{ display: 'grid', gridTemplateColumns: type === 'watch' ? '80px 1fr 60px 80px 30px' : '80px 1fr 60px 80px 30px', gap: 6, alignItems: 'center', fontSize: 11, padding: '4px 0' }}>
                    <input defaultValue={p.stock || ''} placeholder={type === 'watch' ? '标的/板块' : '代码/名称'} style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 6px', color: '#e0e0e0' }} onChange={e => updatePlanField(type, i, 'stock', e.target.value)} />
                    <input defaultValue={type === 'watch' ? p.focus || '' : p.condition || ''} placeholder={type === 'watch' ? '关注点' : '条件'} style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 6px', color: '#e0e0e0' }} onChange={e => updatePlanField(type, i, type === 'watch' ? 'focus' : 'condition', e.target.value)} />
                    {type !== 'watch' && <input defaultValue={p.qty || ''} placeholder="数量" style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 6px', color: '#e0e0e0' }} onChange={e => updatePlanField(type, i, 'qty', e.target.value)} />}
                    {type === 'watch' && <span></span>}
                    <select defaultValue={p.status || 'pending'} style={{ background: '#1a1a30', border: '1px solid #2a2a4e', borderRadius: 4, padding: '3px 4px', color: '#e0e0e0', fontSize: 11 }} onChange={e => updatePlanField(type, i, 'status', e.target.value)}>
                      <option value="pending">⏳ 待触发</option>
                      <option value="triggered">⚡ 已触发</option>
                      <option value="executed">✅ 已执行</option>
                      <option value="not_triggered">❌ 未触发</option>
                    </select>
                    <span style={{ color: '#e94560', cursor: 'pointer', fontSize: 11 }} onClick={() => removePlanRow(type, i)}>✕</span>
                  </div>
                ))}
                <div style={{ marginTop: 4, fontSize: 11, color: '#22c55e', cursor: 'pointer' }} onClick={() => addPlanRow(type)}>＋ 添加{type === 'buy' ? '买入计划' : type === 'sell' ? '卖出计划' : '观察项'}</div>
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
      <div className="footer">3L 交易体系 · 交易工作台 · 分析→定计划→写日志</div>
    </>
  )

  // help functions
  function updatePlanField(type: string, i: number, field: string, value: string) {
    const newPlan = { ...plan }
    const items = [...(newPlan[type as keyof typeof newPlan] || [])]
    items[i] = { ...items[i], [field]: value }
    setData({ ...data, plan: { ...newPlan, [type]: items } })
  }

  function addPlanRow(type: string) {
    const newPlan = { ...plan }
    const items = [...(newPlan[type as keyof typeof newPlan] || [])]
    items.push({ stock: '', condition: '', qty: '', status: 'pending' })
    setData({ ...data, plan: { ...newPlan, [type]: items } })
  }

  function removePlanRow(type: string, i: number) {
    const newPlan = { ...plan }
    const items = (newPlan[type as keyof typeof newPlan] || []).filter((_, j) => j !== i)
    setData({ ...data, plan: { ...newPlan, [type]: items } })
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

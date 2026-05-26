import { useEffect, useState, useRef, useCallback } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import StockCard from '../components/StockCard'
import type { BuySignalItem } from '../lib/types'
import './Watchlist.css'

interface WatchlistStock {
  code: string; name: string; direction?: string; industry?: string
  price?: number; change?: number; signal?: string
  structure?: string; stage?: string; sector?: string
  trading_system?: string; trend_bias?: number
  buy_point?: string; profit_model1?: boolean; trend_stock?: boolean
  vol_analysis?: string
}

interface DirData {
  directions: Record<string, boolean>
  active: string[]
  all: string[]
  suggestions: { industry?: string[]; custom?: string[] }
}

export default function Watchlist() {
  const [stocks, setStocks] = useState<WatchlistStock[]>([])
  const [trendCodes, setTrendCodes] = useState<Set<string>>(new Set())
  const [dirData, setDirData] = useState<DirData>({ directions: {}, active: [], all: [], suggestions: {} })
  const [activeDir, setActiveDir] = useState('全部')
  const [filter, setFilter] = useState('')
  const [dirPanelOpen, setDirPanelOpen] = useState(false)
  const [addTab, setAddTab] = useState<'single' | 'board'>('single')
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [boardQ, setBoardQ] = useState('')
  const [boardResults, setBoardResults] = useState<any[]>([])
  const [selectedCode, setSelectedCode] = useState('')
  const [selectedName, setSelectedName] = useState('')
  const [boardDir, setBoardDir] = useState('')
  const [boardAllChecked, setBoardAllChecked] = useState(true)
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()
  const boardTimer = useRef<ReturnType<typeof setTimeout>>()
  const dragSource = useRef<string | null>(null)

  const activeDirs = dirData.active || []
  const allDirs = dirData.all || []

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [r1, r2, r3] = await Promise.all([
        fetch('/api/watchlist/analysis'),
        fetch('/api/trend-tracked'),
        loadDirections(),
      ])
      setStocks((await r1.json()).stocks || [])
      const td = await r2.json()
      setTrendCodes(new Set((td.candidates || []).map((c: any) => c.code)))
    } catch { /* ignore */ }
  }

  async function loadDirections(): Promise<DirData> {
    try {
      const r = await fetch('/api/directions/get')
      const data = await r.json()
      setDirData(data)
      return data
    } catch {
      const empty: DirData = { directions: {}, active: [], all: [], suggestions: {} }
      setDirData(empty)
      return empty
    }
  }

  function showToast(msg: string, isError?: boolean) {
    const el = document.createElement('div')
    el.textContent = msg
    el.className = 'toast'
    el.style.cssText = `position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid ${isError ? '#e94560' : '#22c55e'};color:${isError ? '#e94560' : '#22c55e'};padding:8px 20px;border-radius:6px;font-size:13px;z-index:999;transition:opacity .3s`
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2000)
  }

  // 方向Tab
  const tracked = stocks.filter(s => activeDirs.includes(s.direction || '其他'))
  const dirCounts: Record<string, number> = { '全部': stocks.length }
  activeDirs.forEach(d => dirCounts[d] = 0)
  stocks.forEach(s => {
    const d = s.direction || '其他'
    if (activeDirs.includes(d)) dirCounts[d] = (dirCounts[d] || 0) + 1
  })
  const tabs = [
    { name: '全部', label: `全部 (${stocks.length})` },
    ...activeDirs.map(d => ({ name: d, label: `${d} (${dirCounts[d] || 0})` })),
  ]

  // 过滤+排序
  const filtered = stocks
    .filter(s => {
      if (activeDir !== '全部') {
        const d = s.direction || '其他'
        if (d !== activeDir || !activeDirs.includes(d)) return false
      }
      if (filter) {
        const f = filter.toLowerCase()
        if (s.code.includes(f)) return true
        const name = (s.name || '').toLowerCase()
        if (name.includes(f)) return true
        // 简单拼音首字母匹配（简化版）
        const initials = name.split(/\s+/).map(w => w[0]).join('').toLowerCase()
        if (initials.includes(f)) return true
        return false
      }
      return true
    })
    .sort((a, b) => {
      const aa = activeDirs.includes(a.direction || '其他') ? 0 : 10
      const bb = activeDirs.includes(b.direction || '其他') ? 0 : 10
      if (aa !== bb) return aa - bb
      const structOrder: Record<string, number> = { '上涨趋势': 0, '区间震荡': 1, '下降趋势': 2 }
      const sa = structOrder[a.structure || ''] ?? 3
      const sb = structOrder[b.structure || ''] ?? 3
      if (sa !== sb) return sa - sb
      return (b.change || 0) - (a.change || 0)
    })

  // 搜索个股
  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!searchQ || searchQ.length < 1) { setSearchResults([]); return }
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await fetch(`/api/watchlist/search?q=${encodeURIComponent(searchQ)}`)
        const data = await r.json()
        setSearchResults(data.results || [])
      } catch { setSearchResults([]) }
    }, 300)
    return () => clearTimeout(searchTimer.current)
  }, [searchQ])

  // 搜索板块
  useEffect(() => {
    clearTimeout(boardTimer.current)
    if (!boardQ || boardQ.length < 1) { setBoardResults([]); return }
    boardTimer.current = setTimeout(async () => {
      try {
        const r = await fetch(`/api/directions/stocks?q=${encodeURIComponent(boardQ)}`)
        const data = await r.json()
        setBoardResults(data.stocks || [])
      } catch { setBoardResults([]) }
    }, 400)
    return () => clearTimeout(boardTimer.current)
  }, [boardQ])

  const stageColors: Record<string, string> = {
    '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700', '滞涨': '#ff6b6b',
    '转弱': '#ff6b6b', '下行': '#666', '加速跌': '#e94560', '转强': '#4ecdc4',
    '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560',
  }

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>📋 自选股管理</h1>
        <div className="subtitle">增删自选股 · 方向管理 · 启用追踪</div>
        <div className="stats">
          共 <b>{stocks.length}</b> 只 · 跟踪 <b>{tracked.length}</b> 只 · 趋势 {trendCodes.size} 只
        </div>
      </div>

      <div className="container">
        {/* 方向管理入口 */}
        <div className="dir-icon-bar" onClick={() => setDirPanelOpen(!dirPanelOpen)}>
          <span>🎯 方向管理 {dirPanelOpen ? '▾' : '▸'}</span>
        </div>

        {dirPanelOpen && (
          <div className="dir-panel">
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '6px 0' }}>
              <DirNameInput dirData={dirData} onAdd={async (name) => {
                try {
                  const r = await fetch('/api/directions/add', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name }),
                  })
                  const data = await r.json()
                  if (data.success) { showToast(`✅ 已添加 "${name}"`); await loadDirections(); loadAll() }
                  else showToast('⚠️ ' + (data.error || '添加失败'), true)
                } catch { showToast('⚠️ 添加失败', true) }
              }} />
            </div>
            <div id="dirList">
              {allDirs.filter(n => n !== '其他').map(name => {
                const isActive = activeDirs.includes(name)
                return (
                  <div key={name} className={`dir-item ${isActive ? '' : 'inactive'}`}
                    draggable data-dir-name={name}
                    onDragStart={e => { dragSource.current = name; (e.currentTarget as HTMLElement).style.opacity = '0.4' }}
                    onDragOver={e => { e.preventDefault(); (e.currentTarget as HTMLElement).style.borderColor = '#22c55e' }}
                    onDrop={async e => {
                      e.preventDefault();
                      (e.currentTarget as HTMLElement).style.borderColor = ''
                      if (!dragSource.current || dragSource.current === name) return
                      const ordered = dirData.all || []
                      const si = ordered.indexOf(dragSource.current)
                      const ti = ordered.indexOf(name)
                      if (si === -1 || ti === -1) return
                      const newOrder = [...ordered]; newOrder.splice(si, 1); newOrder.splice(ti, 0, dragSource.current!)
                      try {
                        const r = await fetch('/api/directions/reorder', {
                          method: 'POST', headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ names: newOrder }),
                        })
                        const data = await r.json()
                        if (data.success) { await loadDirections(); loadAll() }
                        else showToast('⚠️ ' + (data.error || '排序失败'), true)
                      } catch { showToast('⚠️ 排序失败', true) }
                    }}
                    onDragEnd={e => { (e.currentTarget as HTMLElement).style.opacity = '1'; dragSource.current = null }}>
                    <div>
                      <span className="dir-item-name">{name}</span>
                      <span className="dir-item-count">{stocks.filter(s => (s.direction || '其他') === name).length} 只</span>
                      {isActive ? null : <span style={{ color: '#e94560', fontSize: 11, marginLeft: 6 }}>未跟踪</span>}
                    </div>
                    <div className="dir-item-actions">
                      <span style={{ cursor: 'grab', color: '#555', marginRight: 6, fontSize: 14 }}>⠿</span>
                      <button className={`dir-toggle ${isActive ? 'on' : 'off'}`} onClick={async () => {
                        try {
                          const r = await fetch('/api/directions/toggle', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, active: !isActive }),
                          })
                          const data = await r.json()
                          if (data.success) { showToast(isActive ? `⛔ 已禁用 "${name}"` : `✅ 已启用 "${name}"`); await loadDirections(); loadAll() }
                          else showToast('⚠️ 操作失败', true)
                        } catch { showToast('⚠️ 操作失败', true) }
                      }}>{isActive ? '✅ 启用' : '⛔ 禁用'}</button>
                      <button className="btn btn-red btn-sm" onClick={async () => {
                        const cnt = stocks.filter(s => (s.direction || '其他') === name).length
                        if (!confirm(`确认删除方向 "${name}"？该方向的 ${cnt} 只股票将同时从自选股删除`)) return
                        try {
                          const r = await fetch('/api/directions/remove', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name }),
                          })
                          const data = await r.json()
                          if (data.success) { showToast(`❌ 已删除 "${name}"`); await loadDirections(); loadAll() }
                          else showToast('⚠️ ' + (data.error || '删除失败'), true)
                        } catch { showToast('⚠️ 删除失败', true) }
                      }}>✕</button>
                    </div>
                  </div>
                )
              })}
              {allDirs.filter(n => n !== '其他').length === 0 && (
                <div style={{ color: '#888', padding: 10, textAlign: 'center', fontSize: 13 }}>暂无方向，点击上方添加</div>
              )}
            </div>
          </div>
        )}

        {/* 添加区 */}
        <div className="add-section">
          <div className="add-tabs">
            <div className={`add-tab ${addTab === 'single' ? 'active' : ''}`} onClick={() => setAddTab('single')}>🔍 搜个股</div>
            <div className={`add-tab ${addTab === 'board' ? 'active' : ''}`} onClick={() => setAddTab('board')}>🏢 搜板块</div>
          </div>

          {addTab === 'single' && (
            <div className="add-tab-content">
              <div className="add-row">
                <input className="search-input" placeholder="输入代码/名称/首字母搜索..." style={{ flex: 1 }}
                  value={searchQ} onChange={e => { setSearchQ(e.target.value); setSelectedCode(''); setSelectedName('') }}
                  onBlur={() => setTimeout(() => setSearchResults([]), 200)} />
                <select className="dir-select" value={boardDir || activeDirs[0] || ''}
                  onChange={e => setBoardDir(e.target.value)}>
                  {activeDirs.map(d => <option key={d} value={d}>{d}</option>)}
                  {activeDirs.length === 0 && <option value="">先建方向</option>}
                </select>
                <button className="btn btn-green" onClick={addStock}>添加</button>
              </div>
              {searchResults.length > 0 && (
                <div className="search-results">
                  {searchResults.map((st: any, i: number) => (
                    <div key={i} className="search-result-item" onMouseDown={() => {
                      setSelectedCode(st.code); setSelectedName(st.name)
                      setSearchQ(`${st.code} ${st.name}`)
                      setSearchResults([])
                    }}>
                      <span><span className="sr-name">{st.name}</span> <span className="sr-code">{st.code}</span></span>
                      <span className="sr-ind">{st.industry || ''} · {st.direction || '其他'}</span>
                    </div>
                  ))}
                </div>
              )}
              {searchQ && searchResults.length === 0 && (
                <div className="search-results"><div className="search-result-item" style={{ color: '#888' }}>无结果</div></div>
              )}
            </div>
          )}

          {addTab === 'board' && (
            <div className="add-tab-content">
              <div className="add-row">
                <input className="search-input" id="boardSearch" placeholder="输入行业/板块/方向名..." style={{ flex: 1 }}
                  value={boardQ} onChange={e => setBoardQ(e.target.value)} />
                <select className="dir-select" value={boardDir || activeDirs[0] || ''}
                  onChange={e => setBoardDir(e.target.value)}>
                  {activeDirs.map(d => <option key={d} value={d}>{d}</option>)}
                  {activeDirs.length === 0 && <option value="">先建方向</option>}
                </select>
                <button className="btn btn-green btn-sm" onClick={batchAddDirStocks}>添加</button>
              </div>
              {boardResults.length > 0 && (
                <div className="dir-stock-results">
                  <div className="dir-sr-info">共 {boardResults.length} 只匹配</div>
                  <label className="dir-sr-row" style={{ fontWeight: 'bold', borderBottom: '1px solid #2a2a4e' }}>
                    <input type="checkbox" checked={boardAllChecked}
                      onChange={e => setBoardAllChecked(e.target.checked)} />
                    <span>全选（全部添加到方向「{boardDir || activeDirs[0] || '待选'}」）</span>
                  </label>
                  {boardResults.map((s: any, i: number) => {
                    const pct = s.change_pct || 0
                    return (
                      <label key={i} className="dir-sr-row">
                        <input type="checkbox" className="dir-sr-cb"
                          checked={boardAllChecked} data-code={s.code} data-name={s.name} />
                        <span className="dir-sr-code">{s.code}</span>
                        <span className="dir-sr-name">{s.name}</span>
                        <span className="dir-sr-ind">{s.industry || ''}</span>
                        <span className="dir-sr-pct" style={{ color: pct >= 0 ? '#ff4444' : '#22c55e' }}>
                          {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                        </span>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 工具条 */}
        <div className="toolbar">
          <input className="search-input" placeholder="🔍 筛选..." style={{ maxWidth: 200 }}
            value={filter} onChange={e => setFilter(e.target.value)} />
          <div className="dir-tabs" style={{ flex: 1 }}>
            {tabs.map(t => (
              <div key={t.name} className={`dir-tab ${t.name === activeDir ? 'active' : ''}`}
                onClick={() => setActiveDir(t.name)}>{t.label}</div>
            ))}
          </div>
        </div>

        {/* 卡片区 */}
        <div className="cards-area">
          {filtered.length === 0 ? (
            <div className="empty">无匹配股票</div>
          ) : (
            (() => {
              let prevTracked: boolean | null = null
              let prevStruct: string | null = null
              const html: JSX.Element[] = []
              filtered.forEach((s, i) => {
                const tr = activeDirs.includes(s.direction || '其他')
                const struct = s.structure || '--'
                if (prevTracked !== tr || prevStruct !== struct) {
                  html.push(
                    <div key={`g-${i}`} style={{ padding: '8px 10px 2px', fontSize: 12, color: '#888', borderBottom: '1px solid #ffffff0d' }}>
                      {tr ? '✅ 启用方向' : '🚫 未跟踪'} · {struct === '上涨趋势' ? '📈' : struct === '区间震荡' ? '📊' : struct === '下降趋势' ? '📉' : '❓'} {struct}
                      {prevTracked === null || prevTracked !== tr
                        ? <span style={{ float: 'right', fontSize: 11, color: '#555' }}>{tr ? '已启用方向优先' : '未跟踪方向'}</span>
                        : null}
                    </div>
                  )
                  prevTracked = tr; prevStruct = struct
                }
                html.push(
                  <div key={`c-${i}`} className={`watchlist-card-wrapper${tr ? '' : ' untracked'}`}
                    style={{ borderLeft: `3px solid ${stageColors[s.stage || ''] || '#888'}`, borderRadius: '12px 0 0 12px' }}>
                    {/* Card内容 */}
                    <StockCard s={s as BuySignalItem} idx={i} />
                    {/* 底部操作栏 */}
                    <div className="watchlist-card-actions">
                      <div className="wca-left">
                        {tr ? null : <span className="tag-untracked">未跟踪</span>}
                        <select className="dir-select" style={{ width: 68 }} value={s.direction || '其他'}
                          onChange={async e => {
                            const newDir = e.target.value
                            const stock = stocks.find(x => x.code === s.code)
                            if (stock) {
                              stock.direction = newDir
                              try {
                                const payload = stocks.map(x => ({ code: x.code, name: x.name, direction: x.direction, industry: x.industry || '' }))
                                const r = await fetch('/api/watchlist/save', {
                                  method: 'POST', headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ stocks: payload, count: payload.length }),
                                })
                                const data = await r.json()
                                if (data.success) { showToast(`✅ ${stock.name || s.code} → ${newDir}`); loadAll() }
                                else showToast('⚠️ 保存失败', true)
                              } catch { showToast('⚠️ 保存失败', true) }
                            }
                          }}>
                          {[...new Set([...activeDirs, s.direction || '其他'])].map(d => (
                            <option key={d} value={d}>{d}</option>
                          ))}
                        </select>
                      </div>
                      <button className="btn btn-red btn-sm" onClick={async () => {
                        if (!confirm(`确认删除 ${s.name || s.code} ？`)) return
                        try {
                          const newStocks = stocks.filter(x => x.code !== s.code)
                          const r = await fetch('/api/watchlist/save', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ stocks: newStocks.map(x => ({ code: x.code, name: x.name, direction: x.direction, industry: x.industry || '' })), count: newStocks.length }),
                          })
                          const data = await r.json()
                          if (data.success) { showToast(`❌ 已删除 ${s.name || s.code}`); loadAll() }
                          else showToast('⚠️ 删除失败', true)
                        } catch { showToast('⚠️ 删除失败', true) }
                      }}>✕ 删除</button>
                    </div>
                  </div>
                )
              })
              return html
            })()
          )}
        </div>
      </div>

      <BottomNav />
      <div className="footer">自选股管理</div>
    </>
  )

  async function addStock() {
    if (!selectedCode) { showToast('⚠️ 请先搜索选择股票', true); return }
    const dir = boardDir || activeDirs[0]
    if (!dir) { showToast('⚠️ 请先创建方向', true); return }
    if (stocks.some(s => s.code === selectedCode)) {
      showToast(`⚠️ ${selectedName}(${selectedCode}) 已在自选股中`, true)
      return
    }
    let industry = ''
    try {
      const r = await fetch('/api/watchlist/search?q=' + selectedCode)
      const data = await r.json()
      if (data.results && data.results[0]) industry = data.results[0].industry || ''
    } catch { /* ignore */ }
    try {
      const newStocks = [...stocks.map(s => ({ code: s.code, name: s.name, direction: s.direction, industry: s.industry || '' })),
        { code: selectedCode, name: selectedName, direction: dir, industry }]
      const r = await fetch('/api/watchlist/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stocks: newStocks, count: newStocks.length }),
      })
      const data = await r.json()
      if (data.success) {
        showToast(`✅ 已添加 ${selectedName}(${selectedCode})`)
        setSearchQ(''); setSelectedCode(''); setSelectedName(''); setSearchResults([])
        loadAll()
      } else showToast('⚠️ 添加失败', true)
    } catch { showToast('⚠️ 添加失败: ' , true) }
  }

  async function batchAddDirStocks() {
    const targetDir = boardDir || activeDirs[0]
    if (!targetDir) { showToast('⚠️ 请先选择方向', true); return }
    const cbs = document.querySelectorAll('.dir-sr-cb:checked') as NodeListOf<HTMLInputElement>
    if (cbs.length === 0) { showToast('⚠️ 请至少勾选一只股票', true); return }
    const existing = new Set(stocks.map(s => s.code))
    const toAdd: { code: string; name: string; direction: string; industry: string }[] = []
    cbs.forEach(cb => {
      if (!existing.has(cb.dataset.code || '')) {
        toAdd.push({ code: cb.dataset.code || '', name: cb.dataset.name || '', direction: targetDir, industry: '' })
      }
    })
    if (toAdd.length === 0) { showToast('⚠️ 勾选的股票已在自选股中', true); return }
    // 获取行业信息
    for (const s of toAdd) {
      try {
        const r = await fetch('/api/watchlist/search?q=' + s.code)
        const data = await r.json()
        if (data.results && data.results[0]) s.industry = data.results[0].industry || ''
      } catch { /* ignore */ }
    }
    try {
      const newStocks = [...stocks.map(s => ({ code: s.code, name: s.name, direction: s.direction, industry: s.industry || '' })), ...toAdd]
      const r = await fetch('/api/watchlist/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stocks: newStocks, count: newStocks.length }),
      })
      const data = await r.json()
      if (data.success) { showToast(`✅ 已添加 ${toAdd.length} 只股票`); setBoardResults([]); setBoardQ(''); loadAll() }
      else showToast('⚠️ 保存失败', true)
    } catch { showToast('⚠️ 保存失败', true) }
  }
}

function DirNameInput({ dirData, onAdd }: { dirData: DirData; onAdd: (name: string) => void }) {
  const [val, setVal] = useState('')
  const suggestions = [
    ...(dirData.suggestions?.industry || []).slice(0, 8),
    ...(dirData.suggestions?.custom || []).slice(0, 6),
  ]
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input className="search-input" placeholder="新建方向名称..." maxLength={12} style={{ flex: 1 }}
          value={val} onChange={e => setVal(e.target.value)} />
        <button className="btn btn-blue btn-sm" onClick={() => { if (val.trim()) { onAdd(val.trim()); setVal('') } }}>新建</button>
      </div>
      {val && suggestions.length > 0 && (
        <div className="dir-suggestions" style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
          {suggestions.map(s => (
            <span key={s} className="dir-suggestion-tag" onClick={() => setVal(s)}>{s}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── ──

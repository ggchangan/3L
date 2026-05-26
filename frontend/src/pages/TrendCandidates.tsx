import { useEffect, useState, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import StockCard from '../components/StockCard'
import type { BuySignalItem } from '../lib/types'
import './TrendCandidates.css'

interface CandidateStock {
  code: string; name: string; sector?: string; direction?: string
  price?: number; change?: number; signal?: string
  structure?: string; stage?: string
  trading_system?: string; trend_bias?: number
  in_manual?: boolean
}

interface TrendData {
  candidates?: { main_lines?: Group[]; sub_main_lines?: Group[]; count?: number }
  tracked?: { candidates?: CandidateStock[]; count?: number }
  watchlist?: any[]
}

interface Group { industry: string; candidates: CandidateStock[] }

const PAGE_SIZE = 10

export default function TrendCandidates() {
  const [data, setData] = useState<TrendData>({})
  const [activeMain, setActiveMain] = useState<'auto' | 'tracked'>('auto')
  const [activeInd, setActiveInd] = useState<string | null>(null)
  const [curPage, setCurPage] = useState(1)
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [r1, r2, r3] = await Promise.all([
        fetch('/api/trend-candidates'),
        fetch('/api/trend-tracked'),
        fetch('/api/watchlist'),
      ])
      setData({
        candidates: await r1.json(),
        tracked: await r2.json(),
        watchlist: (await r3.json()).stocks || [],
      })
    } catch { /* ignore */ }
  }

  function showToast(msg: string) {
    const el = document.createElement('div')
    el.textContent = msg
    el.className = 'toast show'
    el.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid #22c55e;color:#22c55e;padding:8px 20px;border-radius:6px;font-size:13px;z-index:999'
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2000)
  }

  // 合并主线+次主线
  function getAutoCandidates(): Group[] {
    const main = data.candidates?.main_lines || []
    const sub = data.candidates?.sub_main_lines || []
    const merged: Record<string, Group> = {}
    ;[...main, ...sub].forEach((g: any) => {
      if (!merged[g.industry]) merged[g.industry] = { industry: g.industry, candidates: [] }
      ;(g.candidates || []).forEach((c: CandidateStock) => {
        if (!merged[g.industry].candidates.some(x => x.code === c.code)) {
          merged[g.industry].candidates.push(c)
        }
      })
    })
    return Object.values(merged)
  }

  const auto = getAutoCandidates()
  const tracked = data.tracked?.candidates || []
  const autoCount = auto.reduce((s, g) => s + g.candidates.length, 0)
  const trackedCount = tracked.length

  // 行业选择
  if (!activeInd || !auto.some(g => g.industry === activeInd)) {
    if (activeMain === 'auto' && auto.length > 0) setActiveInd(auto[0].industry)
  }

  // 当前显示的条目
  let items: CandidateStock[] = []
  if (activeMain === 'tracked') {
    items = tracked
  } else {
    const grp = auto.find(g => g.industry === activeInd)
    items = grp?.candidates || []
  }

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE))
  const safePage = Math.min(curPage, totalPages)
  const pageItems = items.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  // 搜索
  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!searchQ || searchQ.length < 1) { setSearchResults([]); return }
    searchTimer.current = setTimeout(() => {
      const manualCodes = new Set((data.tracked?.candidates || []).map(c => c.code))
      const wl = data.watchlist || []
      const q = searchQ.trim().toLowerCase()
      const results = wl.filter((s: any) => {
        const code = (s.code || '').toLowerCase()
        const name = (s.name || '').toLowerCase()
        const py = (s.name || '').split(/\s+/).map((w: string) => w[0]).join('').toLowerCase()
        return code.includes(q) || name.includes(q) || py.includes(q)
      })
      setSearchResults(results.slice(0, 20))
    }, 300)
    return () => clearTimeout(searchTimer.current)
  }, [searchQ, data.tracked, data.watchlist])

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>🎯 趋势交易候选</h1>
        <div className="subtitle">自动候选（主线+次主线行业）· 从自选股搜索加入 · 打勾即加入趋势交易</div>
        <div className="stats">自动候选 <b>{autoCount}</b> 只 · 已跟踪 <b>{trackedCount}</b> 只</div>
      </div>

      <div className="container">
        {/* 搜索框 */}
        <div className="search-section">
          <input className="search-input" placeholder="🔍 从自选股搜索加入趋势跟踪..."
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            onBlur={() => setTimeout(() => setSearchResults([]), 200)} />
          {searchResults.length > 0 && (
            <div className="search-results" style={{ display: 'block' }}>
              {searchResults.map((st: any, i) => {
                const inTrend = (data.tracked?.candidates || []).some(c => c.code === st.code)
                return (
                  <div key={i} className="search-result-item" style={{ cursor: 'pointer' }}
                    onMouseDown={async () => {
                      if (!inTrend) {
                        try {
                          const r = await fetch(`/api/trend-candidates/toggle?code=${st.code}&enable=true`)
                          const d = await r.json()
                          if (d.success === false) { showToast('❌ ' + (d.error || '')); return }
                          showToast(`✅ ${st.code} 已加入趋势交易`)
                          setSearchQ(''); setSearchResults([])
                          const [r1, r2] = await Promise.all([
                            fetch('/api/trend-candidates'),
                            fetch('/api/trend-tracked'),
                          ])
                          const c = await r1.json()
                          const t = await r2.json()
                          setData(prev => ({ ...prev, candidates: c, tracked: t }))
                        } catch { showToast('❌ 操作失败') }
                      }
                    }}>
                    <span><span className="sr-name">{st.name}</span> <span className="sr-code">{st.code}</span></span>
                    <span className="sr-ind">{st.direction || ''}</span>
                    <span style={{ float: 'right', color: inTrend ? '#4ecdc4' : '#2196f3', fontSize: 11 }}>
                      {inTrend ? '✅ 已加入' : '➕ 加入'}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 主Tab */}
        <div className="main-tabs">
          <div className={`main-tab ${activeMain === 'auto' ? 'active' : ''}`}
            onClick={() => { setActiveMain('auto'); setCurPage(1) }}>
            📈 自动候选 ({autoCount})
          </div>
          <div className={`main-tab ${activeMain === 'tracked' ? 'active' : ''}`}
            onClick={() => { setActiveMain('tracked'); setCurPage(1) }}>
            ✅ 已跟踪 ({trackedCount})
          </div>
        </div>

        {/* 行业子Tab（自动候选） */}
        {activeMain === 'auto' && auto.length > 0 && (
          <div className="ind-tabs-wrap">
            {auto.map(g => (
              <div key={g.industry}
                className={`ind-tab ${g.industry === activeInd ? 'active' : ''}`}
                onClick={() => { setActiveInd(g.industry); setCurPage(1) }}>
                {g.industry} <span className="count">({g.candidates.length})</span>
              </div>
            ))}
          </div>
        )}

        {/* 卡片区 */}
        <div className="cards-area">
          {items.length === 0 ? (
            <div className="empty">
              {activeMain === 'tracked'
                ? '✅ 暂无已跟踪趋势股\n在「自动候选」中打勾或使用搜索框添加'
                : '暂无自动候选'}
            </div>
          ) : (
            pageItems.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'stretch', gap: 0, marginBottom: 6 }}>
                <div style={{ flex: 1 }}>
                  <StockCard s={s as BuySignalItem} idx={(safePage - 1) * PAGE_SIZE + i} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', padding: '0 8px', borderLeft: '1px solid #1a1a30' }}>
                  <input type="checkbox"
                    checked={s.in_manual || false}
                    onChange={async e => {
                      try {
                        const r = await fetch(`/api/trend-candidates/toggle?code=${s.code}&enable=${e.target.checked}`)
                        const d = await r.json()
                        if (d.success === false && d.error) { showToast('❌ ' + d.error); return }
                        showToast(e.target.checked ? `✅ ${s.code} 已加入趋势交易` : `❌ ${s.code} 已移除`)
                        const [r1, r2] = await Promise.all([
                          fetch('/api/trend-candidates'),
                          fetch('/api/trend-tracked'),
                        ])
                        const c = await r1.json()
                        const t = await r2.json()
                        setData(prev => ({ ...prev, candidates: c, tracked: t }))
                      } catch { showToast('❌ 操作失败') }
                    }}
                    style={{ accentColor: '#4ecdc4', width: 18, height: 18, cursor: 'pointer' }} />
                </div>
              </div>
            ))
          )}
        </div>

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="pagination">
            <div className={`page-btn ${safePage <= 1 ? 'disabled' : ''}`}
              onClick={() => safePage > 1 && setCurPage(safePage - 1)}>◀ 上一页</div>
            <span className="page-info">{safePage}/{totalPages}</span>
            <div className={`page-btn ${safePage >= totalPages ? 'disabled' : ''}`}
              onClick={() => safePage < totalPages && setCurPage(safePage + 1)}>下一页 ▶</div>
          </div>
        )}
      </div>

      <BottomNav />
      <div className="footer">趋势候选管理 · 自动候选每天随复盘更新</div>
    </>
  )
}
// ──
import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import { pinyin } from 'pinyin-pro'
import './SectorFocus.css'

interface SectorItem {
  name: string
  ts_code: string
  count: number
  in_mainline: boolean
  watched: boolean
}

interface SectorListResponse {
  type: string
  count: number
  in_mainline: number
  sectors: SectorItem[]
}

type TabKey = 'industry' | 'concept'

export default function SectorFocus() {
  const [tab, setTab] = useState<TabKey>('industry')
  const [sectors, setSectors] = useState<SectorItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('')
  const [onlyWatched, setOnlyWatched] = useState(false)
  const [pending, setPending] = useState<string | null>(null) // 正在切换的 ts_code
  const reqSeqRef = useRef(0) // 请求序号：丢弃过期 Tab 的响应

  const load = useCallback((type: TabKey) => {
    const seq = ++reqSeqRef.current
    setLoading(true)
    setError('')
    fetch(`/api/sectors/list?type=${type}`)
      .then(r => r.json())
      .then((data: SectorListResponse) => {
        if (seq !== reqSeqRef.current) return // 已切换 Tab，丢弃过期响应
        setSectors(data.sectors || [])
        setLoading(false)
      })
      .catch(err => {
        if (seq !== reqSeqRef.current) return
        setError(err.message || '加载板块列表失败')
        setLoading(false)
      })
  }, [])

  useEffect(() => { load(tab) }, [tab, load])

  const toggle = (item: SectorItem) => {
    if (pending) return
    setPending(item.ts_code)
    fetch('/api/watched-sectors/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: tab, ts_code: item.ts_code }),
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setSectors(prev => prev.map(s => s.ts_code === item.ts_code ? { ...s, watched: res.watched } : s))
        } else {
          alert(res.error || '操作失败')
        }
      })
      .catch(() => alert('网络错误，请重试'))
      .finally(() => setPending(null))
  }

  // 预计算拼音首字母（板块名 → 拼音缩写），输入过滤时直接查
  const pyMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const s of sectors) {
      try {
        m[s.name] = pinyin(s.name, { pattern: 'first', toneType: 'none' }).replace(/\s+/g, '').toLowerCase()
      } catch {
        m[s.name] = ''
      }
    }
    return m
  }, [sectors])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    let list = sectors
    if (onlyWatched) list = list.filter(s => s.watched)
    if (q) {
      list = list.filter(s => {
        if (s.name.toLowerCase().includes(q)) return true
        if (s.ts_code.toLowerCase().includes(q)) return true
        const py = pyMap[s.name] || ''
        if (py.includes(q)) return true
        // 全拼匹配（如 "bandaoti" → 半导体）
        try {
          const full = pinyin(s.name, { toneType: 'none' }).replace(/\s+/g, '').toLowerCase()
          if (full.includes(q)) return true
        } catch { /* ignore */ }
        return false
      })
    }
    // 已关注优先，其次按名称
    return [...list].sort((a, b) => Number(b.watched) - Number(a.watched))
  }, [sectors, filter, onlyWatched, pyMap])

  const watchedCount = sectors.filter(s => s.watched).length
  const inMainlineCount = sectors.filter(s => s.in_mainline).length

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>⭐ 关注板块</h1>
        <div className="sub">勾选重点关注的同花顺板块/概念 · 复盘页 STEP 2–3 展示强度</div>
        <div className="sector-focus-stats">
          <span className="stat watched">已关注 {watchedCount} 个</span>
          <span className="stat">共 {sectors.length} 个</span>
          <span className="stat in-mainline">主线内 {inMainlineCount} 个</span>
        </div>
      </div>

      <div className="container">
        <div className="section">
          <div className="section-title">
            <span className="step">关注管理</span>
            选择 / 取消关注
            <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>
              → 勾选即保存 · 复盘页同数据源展示强度（今日/10日涨幅、阶段、领涨）
            </span>
          </div>

          {/* Tab + 工具条 */}
          <div className="sector-focus-toolbar">
            <div className="sector-focus-tabs">
              <button
                className={tab === 'industry' ? 'active industry' : ''}
                onClick={() => setTab('industry')}
              >🏭 行业</button>
              <button
                className={tab === 'concept' ? 'active concept' : ''}
                onClick={() => setTab('concept')}
              >💡 概念</button>
            </div>
            <input
              className="sector-focus-search"
              type="text"
              placeholder="搜索板块（中文 / 拼音，如 半导体 / bdt）"
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
            <label className="sector-focus-only-watched">
              <input
                type="checkbox"
                checked={onlyWatched}
                onChange={e => setOnlyWatched(e.target.checked)}
              />
              只看已关注
            </label>
          </div>

          {loading ? (
            <div className="empty">正在加载板块列表...</div>
          ) : error ? (
            <div className="empty" style={{ color: '#e94560' }}>{error}</div>
          ) : filtered.length === 0 ? (
            <div className="empty">{onlyWatched ? '暂无关注，取消「只看已关注」浏览全部板块' : '没有匹配的板块'}</div>
          ) : (
            <div className="sector-focus-list">
              {filtered.map(item => (
                <div
                  key={item.ts_code}
                  className={`sector-focus-row ${item.watched ? 'watched' : ''} ${pending === item.ts_code ? 'pending' : ''}`}
                  onClick={() => toggle(item)}
                >
                  <span className="check">{item.watched ? '✅' : '⬜'}</span>
                  <span className="name">{item.name}</span>
                  {item.in_mainline ? (
                    <span className="badge in-mainline">主线内</span>
                  ) : (
                    <span className="badge outside">主线外</span>
                  )}
                  <span className="count">{item.count || 0} 只</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <BottomNav />
      <div className="footer">3L 交易体系 · 关注板块管理 · 数据与复盘主线同源（MySQL ths_index）</div>
    </>
  )
}

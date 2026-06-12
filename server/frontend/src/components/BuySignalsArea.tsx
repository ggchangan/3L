import { useEffect, useState, useRef, useCallback } from 'react'
import { fetchBuySignals, fetchIndustryBoards, fetchIndustryMap } from '../lib/api'
import StockCard from './StockCard'
import { pinyin } from 'pinyin-pro'
import type { BuySignalItem, IndustryBoardItem, IndustryMap } from '../lib/types'

const DIR_COLORS: Record<string, string> = {
  '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
  '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
  'AI应用': '#00BCD4', '商业航天': '#FF5722',
}
const PER_PAGE = 10

export default function BuySignalsArea() {
  const [groups, setGroups] = useState<Record<string, BuySignalItem[]>>({})
  const [activeDir, setActiveDir] = useState('')
  const [page, setPage] = useState(1)
  const [scanMeta, setScanMeta] = useState<{ scan_time?: string; stocks_scanned?: number }>({})
  const [searchQ, setSearchQ] = useState('')
  const [prevActiveDir, setPrevActiveDir] = useState('')
  const [dirOrder, setDirOrder] = useState<string[]>([])

  // 提取扫描时间中的 HH:MM 部分
  const scanTimeShort = scanMeta.scan_time
    ? scanMeta.scan_time.length >= 16
      ? scanMeta.scan_time.slice(11, 16)
      : scanMeta.scan_time
    : ''

  // 初始加载 + 30s轮询（API秒回，后台缓存更新后自动刷新）
  useEffect(() => {
    const fetchData = () => {
      Promise.all([
        fetchBuySignals(),
        fetchIndustryBoards(),
        fetchIndustryMap(),
        fetch('/api/directions/get').then(r => r.json()),
      ]).then(([signalsData, boardsData, mapData, dirData]) => {
        setDirOrder(dirData.all || [])
        const boards: IndustryBoardItem[] = boardsData.data || []
        const sectorChg: Record<string, number> = {}
        boards.forEach(b => {
          const name = b['板块'] || b['名称'] || ''
          sectorChg[name] = parseFloat(String(b['涨跌幅'] || 0))
        })

        const enriched: BuySignalItem[] = (signalsData.signals || []).map(s => {
          const code = s.code.replace(/^sh|^sz|^SH|^SZ/, '')
          const mapEntry = (mapData as IndustryMap)[code] || (mapData as IndustryMap)[s.code] || {}
          const sectorName = mapEntry.ths_industry || ''
          return { ...s, sector: sectorName, sector_chg: sectorChg[sectorName] || 0 }
        })

        const g: Record<string, BuySignalItem[]> = {}
        enriched.forEach(s => {
          const dir = s.direction || '其他'
          if (!g[dir]) g[dir] = []
          g[dir].push(s)
        })
        setGroups(g)
        setScanMeta({ scan_time: signalsData.scan_time, stocks_scanned: signalsData.stocks_scanned })

        const dirs = Object.keys(g)
        if (dirs.length > 0 && !g[activeDir]) {
          setActiveDir(dirs[0])
        }
      })
    }
    fetchData()
    const timer = setInterval(fetchData, 30000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    setPage(1)
  }, [activeDir])

  const dirs = dirOrder.length > 0
    ? dirOrder.filter(d => groups[d])
    : Object.keys(groups)
  if (dirs.length === 0) return <div className="empty">正在扫描…</div>

  const activeData = groups[activeDir] || []
  // 搜索过滤（支持代码/名称/拼音首字母）
  const filtered = searchQ ? activeData.filter(s => {
    const q = searchQ.trim().toLowerCase()
    const codeMatch = (s.code || '').toLowerCase().includes(q)
    const nameMatch = (s.name || '').toLowerCase().includes(q)
    const pyMatch = pinyin(s.name || '', { pattern: 'first', toneType: 'none' }).replace(/\s+/g, '').toLowerCase().includes(q)
    return codeMatch || nameMatch || pyMatch
  }) : activeData
  const totalPages = Math.ceil(filtered.length / PER_PAGE)
  const pageStart = (page - 1) * PER_PAGE
  const pageItems = filtered.slice(pageStart, pageStart + PER_PAGE)

  const pct = activeData.length > 0 ? scanMeta.stocks_scanned ? ` | ${scanMeta.stocks_scanned}只扫描` : '' : ''
  const signalCount = activeData.length > 0 ? ` | ${activeData.length}个信号` : ''

  return (
    <>
      {/* 扫描时间指示器 */}
      {scanTimeShort && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '6px 8px', marginBottom: 6,
          background: 'rgba(78, 205, 196, 0.08)', borderRadius: 6,
          border: '1px solid rgba(78, 205, 196, 0.15)',
        }}>
          <span style={{ fontSize: 12, color: '#4ecdc4' }}>
            ⏱ 缓存时间: <strong>{scanTimeShort}</strong>
          </span>
          <span style={{ fontSize: 11, color: '#888' }}>
            {scanMeta.stocks_scanned || 0}只扫描 · {Object.values(groups).flat().length}个信号
          </span>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10, borderBottom: '1px solid #333', paddingBottom: 6 }}>
        {dirs.map(dir => {
          const color = DIR_COLORS[dir] || '#888'
          const isActive = dir === activeDir
          return (
            <span
              key={dir}
              onClick={() => setActiveDir(dir)}
              style={{
                cursor: 'pointer', padding: '4px 12px', fontSize: 12, borderRadius: 12, display: 'inline-block',
                background: isActive ? color : 'rgba(255,255,255,0.05)',
                color: isActive ? '#fff' : color,
              }}
            >{dir} ({groups[dir].length})</span>
          )
        })}
      </div>

      <div className="search-box">
        <input className="search-input" placeholder="🔍 输入代码/名称/首字母搜索..."
          value={searchQ}
          onChange={e => { setSearchQ(e.target.value); setPage(1) }} />
      </div>

      {filtered.length === 0 ? (
        <div className="empty" style={{ padding: '20px 0', color: '#888', fontSize: 13 }}>{searchQ ? '无匹配结果' : '暂无买点信号'}</div>
      ) : (
        pageItems.map((s, idx) => (
          <StockCard key={`${s.code}-${idx}`} s={s} idx={pageStart + idx + 1} chartPrefix={`ms_${activeDir}_`} mode="monitor" />
        ))
      )}

      {totalPages > 1 && (
        <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12 }}>
          <span
            onClick={() => setPage(p => Math.max(1, p - 1))}
            style={{ cursor: 'pointer', color: page > 1 ? '#4ecdc4' : '#333', margin: '0 8px' }}
          >◀</span>
          <span style={{ color: '#888' }}>第{page}/{totalPages}页</span>
          <span
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            style={{ cursor: 'pointer', color: page < totalPages ? '#4ecdc4' : '#333', margin: '0 8px' }}
          >▶</span>
        </div>
      )}

      <div style={{ textAlign: 'right', fontSize: 10, color: '#555', marginTop: 4 }}>
        扫描: {scanMeta.scan_time || ''}{pct}{signalCount}
      </div>
    </>
  )
}

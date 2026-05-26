import { useState } from 'react'
import StockCard from './StockCard'
import type { BuySignalItem } from '../lib/types'

const DIR_COLORS: Record<string, string> = {
  '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
  '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
  'AI应用': '#00BCD4', '商业航天': '#FF5722', '先进封装': '#FF6B6B',
  'PCB概念': '#FFD93D',
}
const PER_PAGE = 10

export default function BuySignalsReview({ signals, directionOrder: dirOrder }: { signals: BuySignalItem[]; directionOrder?: string[] }) {
  const [activeDir, setActiveDir] = useState('')
  const [page, setPage] = useState(1)

  if (!signals.length) return <div className="empty">暂无买点信号</div>

  const groups: Record<string, BuySignalItem[]> = {}
  signals.forEach(s => {
    const dir = s.direction || s.sector || '其他'
    if (!groups[dir]) groups[dir] = []
    groups[dir].push(s)
  })

  const dirs = Object.keys(groups)
  const order = dirOrder && dirOrder.length > 0 ? dirOrder : Object.keys(groups)
  const sortedDirs = order.filter(d => dirs.includes(d)).concat(dirs.filter(d => !order.includes(d)))
  if (!activeDir || !groups[activeDir]) {
    if (sortedDirs[0] && activeDir !== sortedDirs[0]) setActiveDir(sortedDirs[0])
  }

  const activeData = groups[activeDir] || []
  const totalPages = Math.ceil(activeData.length / PER_PAGE)
  const start = (page - 1) * PER_PAGE
  const pageItems = activeData.slice(start, start + PER_PAGE)

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10, borderBottom: '1px solid #333', paddingBottom: 6 }}>
        {sortedDirs.map(dir => {
          const color = DIR_COLORS[dir] || '#888'
          const isActive = dir === activeDir
          return (
            <span key={dir}
              onClick={() => { setActiveDir(dir); setPage(1) }}
              style={{
                cursor: 'pointer', padding: '4px 12px', fontSize: 12, borderRadius: 12, display: 'inline-block',
                background: isActive ? color : 'rgba(255,255,255,0.05)',
                color: isActive ? '#fff' : color,
              }}
            >{dir} ({groups[dir].length})</span>
          )
        })}
      </div>
      {pageItems.map((s, i) => (
        <StockCard key={s.code + '-' + i} s={s} idx={start + i + 1} chartPrefix="bs_" mode="review" />
      ))}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12 }}>
          <span style={{ color: '#888' }}>共{activeData.length}只</span>
          {page > 1 && (
            <span onClick={() => setPage(p => p - 1)} style={{ cursor: 'pointer', color: '#4ecdc4' }}>‹ 上一页</span>
          )}
          <span style={{ color: '#e94560', fontWeight: 600 }}>{page}/{totalPages}</span>
          {page < totalPages && (
            <span onClick={() => setPage(p => p + 1)} style={{ cursor: 'pointer', color: '#4ecdc4' }}>下一页 ›</span>
          )}
        </div>
      )}
    </>
  )
}

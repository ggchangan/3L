import { useState } from 'react'
import StockCard from './StockCard'
import type { BuySignalItem } from '../lib/types'

const DIR_COLORS: Record<string, string> = {
  '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
  '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
  'AI应用': '#00BCD4', '商业航天': '#FF5722', '先进封装': '#FF6B6B',
  'PCB概念': '#FFD93D',
}

export default function HoldingsReview({ stocks, directionOrder: dirOrder }: { stocks: BuySignalItem[]; directionOrder?: string[] }) {
  const [activeDir, setActiveDir] = useState('')
  if (!stocks.length) return <div className="empty">暂无持仓数据</div>

  const groups: Record<string, BuySignalItem[]> = {}
  stocks.forEach(s => {
    const dir = s.direction || s.sector || '其他'
    if (!groups[dir]) groups[dir] = []
    groups[dir].push(s)
  })

  const dirs = Object.keys(groups)
  const order = dirOrder && dirOrder.length > 0 ? dirOrder : Object.keys(groups)
  const sortedDirs = order.filter(d => dirs.includes(d)).concat(dirs.filter(d => !order.includes(d)))
  if (!activeDir || !groups[activeDir]) {
    if (!sortedDirs[0]) return null
    if (activeDir !== sortedDirs[0]) setActiveDir(sortedDirs[0])
  }

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10, borderBottom: '1px solid #333', paddingBottom: 6 }}>
        {sortedDirs.map(dir => {
          const color = DIR_COLORS[dir] || '#888'
          const isActive = dir === activeDir
          return (
            <span key={dir}
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
      {(groups[activeDir] || []).map((s, i) => (
        <StockCard key={s.code + '-' + i} s={s} idx={i + 1} chartPrefix="hr_" mode="review" />
      ))}
      <div style={{ marginTop: 6, textAlign: 'right', color: '#555', fontSize: 11 }}>
        共{stocks.length}只持仓
      </div>
    </>
  )
}

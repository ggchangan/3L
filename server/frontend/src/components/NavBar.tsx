/** 顶部导航栏 — 对应旧 nav.js 的渲染结果 */
import { useLocation } from 'react-router-dom'

const MAIN_NAV = [
  { label: '📡 盘中盯盘',  href: '/monitor',         id: 'monitor' },
  { label: '📋 每日复盘',  href: '/review',           id: 'review' },
  { label: '🧑 工作台',    href: '/journal.html',      id: 'workbench' },
  { label: '📋 自选股',    href: '/watchlist.html',    id: 'watchlist' },
  { label: '🔍 个股分析',  href: '/stock_analysis.html', id: 'stock_analysis' },
  { label: '🎯 趋势候选',  href: '/trend_candidates.html', id: 'trend' },
  { label: '🔬 行业追踪',  href: '/industry.html',    id: 'industry' },
  { label: '📈 涨幅榜',    href: '/top_gainers.html',  id: 'gainers' },
  { label: '🌍 宏观环境',  href: '/macro.html',        id: 'macro' },
  { label: '📝 交易技巧',  href: '/tips.html',         id: 'tips' },
  { label: '💡 逻辑追踪',  href: '/logic-tracking',    id: 'logic' },
]

const TOP_COLORS: Record<string, string> = {
  monitor: '#4ecdc4', review: '#e94560', workbench: '#f59e0b',
  watchlist: '#22c55e', stock_analysis: '#e94560',
  trend: '#4ecdc4', industry: '#22c55e', gainers: '#e94560',
  macro: '#2196f3', tips: '#f59e0b', logic: '#a855f7',
}

const FOOTER_LINKS = [
  { label: '📋 每日成果',  href: '/index.html',      id: 'home' },
  { label: '📖 Skills',   href: '/skills.html',      id: 'skills' },
  { label: '📊 模拟交易', href: '/simulation.html',  id: 'simulation' },
  { label: '🎵 报警音乐', href: '/alarm-sounds',     id: 'alarm-sounds' },
]

export default function NavBar() {
  const path = useLocation().pathname
  const currentId = MAIN_NAV.find(item => path.startsWith(item.href))?.id || null
  const sep = <span style={{ color: '#333', margin: '0 6px' }}>|</span>

  return (
    <div style={{ marginTop: 10 }}>
      {/* 顶部导航 */}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginTop: 10, marginBottom: 0 }}>
        {MAIN_NAV.map(item => {
          const isCurrent = item.id === currentId
          const color = isCurrent ? '#e94560' : (TOP_COLORS[item.id] || '#e67e22')
          if (isCurrent) {
            return <span key={item.id} style={{ color, textDecoration: 'none', fontSize: 12, fontWeight: 'bold' }}>{item.label}</span>
          }
          return (
            <a key={item.id} href={item.href} style={{ color, textDecoration: 'none', fontSize: 12 }}>
              {item.label}
            </a>
          )
        }).reduce((acc: React.ReactNode[], el, i) => i === 0 ? [el] : [...acc, sep, el], [])}
      </div>
    </div>
  )
}

export function BottomNav() {
  const path = useLocation().pathname
  const currentId = MAIN_NAV.find(item => path.startsWith(item.href))?.id || null
  const sep = <span style={{ color: '#333', margin: '0 6px' }}>|</span>

  return (
    <div id="nav-bottom" style={{ textAlign: 'center', marginTop: 24, paddingTop: 14, borderTop: '1px solid #2a2a4a' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', marginBottom: 6 }}>
        {MAIN_NAV.map(item => {
          const isCurrent = item.id === currentId
          const color = isCurrent ? '#e94560' : '#4ecdc4'
          if (isCurrent) {
            return <span key={item.id} style={{ color, textDecoration: 'none', fontSize: 13, fontWeight: 'bold' }}>{item.label}</span>
          }
          return (
            <a key={item.id} href={item.href} style={{ color, textDecoration: 'none', fontSize: 13 }}>
              {item.label}
            </a>
          )
        }).reduce((acc: React.ReactNode[], el, i) => i === 0 ? [el] : [...acc, sep, el], [])}
      </div>
      <div style={{ color: '#555', fontSize: 11 }}>
        {FOOTER_LINKS.map((item, i) => (
          <span key={item.id}>
            {i > 0 && <span style={{ color: '#444', margin: '0 4px' }}>·</span>}
            <a href={item.href} style={{ color: '#555', textDecoration: 'none', fontSize: 11 }}>{item.label}</a>
          </span>
        ))}
      </div>
    </div>
  )
}

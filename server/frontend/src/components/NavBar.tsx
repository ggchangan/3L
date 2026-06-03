/** 左侧固定侧边栏 — 替代原顶部水平导航 */
import { useLocation } from 'react-router-dom'

interface NavItem {
  label: string
  href: string
  id: string
  accent: string
  group: string
}

const NAV_ITEMS: NavItem[] = [
  // ── 核心流程 ──
  { label: '📡 盘中盯盘', href: '/monitor',             id: 'monitor',         accent: '#4ecdc4', group: '核心流程' },
  { label: '📋 每日复盘', href: '/review',              id: 'review',          accent: '#e94560', group: '核心流程' },
  { label: '🧑 工作台',   href: '/journal.html',        id: 'workbench',       accent: '#f59e0b', group: '核心流程' },

  // ── 个股管理 ──
  { label: '📋 自选股',   href: '/watchlist.html',      id: 'watchlist',       accent: '#22c55e', group: '个股管理' },
  { label: '📋 持仓',     href: '/holdings',            id: 'holdings',        accent: '#22c55e', group: '个股管理' },
  { label: '🔍 个股分析', href: '/stock_analysis.html', id: 'stock_analysis',  accent: '#e94560', group: '个股管理' },
  { label: '🎯 趋势候选', href: '/trend_candidates.html', id: 'trend',         accent: '#4ecdc4', group: '个股管理' },
  { label: '📈 涨幅榜',   href: '/top_gainers.html',     id: 'gainers',        accent: '#e94560', group: '个股管理' },

  // ── 板块/概念 ──
  { label: '🔬 行业追踪', href: '/industry.html',       id: 'industry',        accent: '#22c55e', group: '板块 / 概念' },
  { label: '🌊 概念波动', href: '/concept-wave',        id: 'concept-wave',    accent: '#00bcd4', group: '板块 / 概念' },
  { label: '💡 逻辑追踪', href: '/logic-tracking',      id: 'logic',           accent: '#a855f7', group: '板块 / 概念' },

  // ── 市场全景 ──
  { label: '🌍 宏观环境', href: '/macro.html',           id: 'macro',           accent: '#2196f3', group: '市场全景' },

  // ── 追踪回顾 ──
  { label: '📊 计划追踪', href: '/plan-tracking.html',   id: 'plan-tracking',   accent: '#4ecdc4', group: '追踪回顾' },
  { label: '📊 模拟交易', href: '/simulation.html',      id: 'simulation',      accent: '#f59e0b', group: '追踪回顾' },

  // ── 知识库 ──
  { label: '📝 交易技巧', href: '/tips.html',            id: 'tips',            accent: '#f59e0b', group: '知识库' },
]

const GROUPS = ['核心流程', '个股管理', '板块 / 概念', '市场全景', '追踪回顾', '知识库'] as const

const FOOTER_LINKS = [
  { label: '📋 每日成果',  href: '/index.html',      id: 'home' },
  { label: '📖 Skills',   href: '/skills.html',      id: 'skills' },
  { label: '🎵 报警音乐', href: '/alarm-sounds',     id: 'alarm-sounds' },
]

/** 判断当前路径是否匹配导航项 */
function matchPath(path: string, item: NavItem): boolean {
  // 精确匹配：/monitor → monitor
  if (path === item.href) return true
  // 前缀匹配（用于 /logic-tracking/123 → logic-tracking）
  if (item.href !== '/' && path.startsWith(item.href + '/')) return true
  // /workbench 也匹配工作台
  if (item.id === 'workbench' && (path === '/workbench' || path === '/journal')) return true
  return false
}

const SIDEBAR_STYLE: React.CSSProperties = {
  width: 200,
  minWidth: 200,
  background: '#141428',
  borderRight: '1px solid #2a2a4a',
  height: '100vh',
  position: 'fixed' as const,
  left: 0,
  top: 0,
  zIndex: 100,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}

const SIDEBAR_HEADER: React.CSSProperties = {
  padding: '18px 16px 14px',
  fontSize: 11,
  color: '#666',
  textTransform: 'uppercase',
  letterSpacing: 1,
  borderBottom: '1px solid #2a2a4a',
  flexShrink: 0,
}

const NAV_SCROLL: React.CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '6px 0',
}

const GROUP_LABEL: React.CSSProperties = {
  padding: '14px 16px 4px',
  fontSize: 10,
  color: '#555',
  textTransform: 'uppercase',
  letterSpacing: 1,
}

const ITEM_BASE: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '8px 16px',
  fontSize: 13,
  color: '#aaa',
  textDecoration: 'none',
  borderLeft: '3px solid transparent',
  transition: 'all 0.15s',
  cursor: 'pointer',
}

const FOOTER_STYLE: React.CSSProperties = {
  borderTop: '1px solid #2a2a4a',
  padding: '10px 16px',
  flexShrink: 0,
}

export default function NavBar() {
  const path = useLocation().pathname
  const currentId = NAV_ITEMS.find(item => matchPath(path, item))?.id || null

  return (
    <div className="sidebar" style={SIDEBAR_STYLE}>
      <div style={SIDEBAR_HEADER}>3L · NAV</div>

      <div className="sidebar-nav" style={NAV_SCROLL}>
        {GROUPS.map(group => (
          <div key={group}>
            <div style={GROUP_LABEL}>{group}</div>
            {NAV_ITEMS.filter(item => item.group === group).map(item => {
              const isCurrent = item.id === currentId
              return (
                <a
                  key={item.id}
                  href={item.href}
                  className={`nav-item${isCurrent ? ' active' : ''}`}
                  style={{
                    ...ITEM_BASE,
                    color: isCurrent ? '#fff' : '#aaa',
                    borderLeftColor: isCurrent ? item.accent : 'transparent',
                    background: isCurrent ? 'rgba(255,255,255,0.03)' : 'transparent',
                  }}
                  onMouseEnter={e => {
                    if (!isCurrent) {
                      (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'
                      ;(e.currentTarget as HTMLElement).style.color = '#eee'
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isCurrent) {
                      (e.currentTarget as HTMLElement).style.background = 'transparent'
                      ;(e.currentTarget as HTMLElement).style.color = '#aaa'
                    }
                  }}
                >
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: item.accent, flexShrink: 0 }} />
                  {item.label}
                </a>
              )
            })}
          </div>
        ))}
      </div>

      <div className="sidebar-footer" style={FOOTER_STYLE}>
        {FOOTER_LINKS.map((link, i) => (
          <span key={link.id}>
            {i > 0 && <span style={{ color: '#333', margin: '0 4px' }}>·</span>}
            <a
              href={link.href}
              style={{ color: '#555', textDecoration: 'none', fontSize: 11 }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#888' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#555' }}
            >
              {link.label}
            </a>
          </span>
        ))}
      </div>
    </div>
  )
}

/** 底部导航 — 辅助导航，每页底部显示 */
export function BottomNav() {
  const path = useLocation().pathname
  const currentId = NAV_ITEMS.find(item => matchPath(path, item))?.id || null
  const sep = (key: string) => <span key={`sep-${key}`} style={{ color: '#333', margin: '0 6px' }}>|</span>

  return (
    <div id="nav-bottom" style={{ textAlign: 'center', marginTop: 24, paddingTop: 14, borderTop: '1px solid #2a2a4a' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', marginBottom: 6 }}>
        {NAV_ITEMS.map((item, i) => {
          const isCurrent = item.id === currentId
          const color = isCurrent ? '#e94560' : '#4ecdc4'
          const el = isCurrent
            ? <span key={item.id} style={{ color, textDecoration: 'none', fontSize: 13, fontWeight: 'bold' }}>{item.label}</span>
            : <a key={item.id} href={item.href} style={{ color, textDecoration: 'none', fontSize: 13 }}>{item.label}</a>
          return i === 0 ? el : [sep(item.id), el]
        })}
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

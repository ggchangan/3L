/** 左侧固定侧边栏 — 桌面固定 / 手机汉堡菜单 */
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

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
  { label: '📈 强势趋势', href: '/strong-trend-candidates', id: 'strong-trend',  accent: '#4ecdc4', group: '个股管理' },
  { label: '🔥 热点追踪', href: '/hot-stocks',              id: 'hot-stocks',     accent: '#ff6b00', group: '个股管理' },

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
  if (path === item.href) return true
  if (item.href !== '/' && path.startsWith(item.href + '/')) return true
  if (item.id === 'workbench' && (path === '/workbench' || path === '/journal')) return true
  return false
}

export default function NavBar() {
  const path = useLocation().pathname
  const currentId = NAV_ITEMS.find(item => matchPath(path, item))?.id || null
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    setIsMobile(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const closeNav = () => setMobileOpen(false)

  // 点击导航链接后自动关闭（手机端）
  const handleNavClick = () => {
    if (isMobile) closeNav()
  }

  const sidebarVisible = !isMobile || mobileOpen

  return (
    <>
      {/* 手机端：汉堡按钮 */}
      {isMobile && (
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(v => !v)}
          aria-label="打开导航"
          style={{
            position: 'fixed',
            top: 10, left: 10, zIndex: 200,
            width: 36, height: 36, borderRadius: 8,
            background: '#141428', border: '1px solid #2a2a4a',
            color: '#aaa', fontSize: 18, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 0, lineHeight: 1,
          }}
        >
          {mobileOpen ? '✕' : '☰'}
        </button>
      )}

      {/* 手机端：遮罩层 */}
      {isMobile && mobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={closeNav}
          style={{
            position: 'fixed', inset: 0, zIndex: 99,
            background: 'rgba(0,0,0,0.6)',
          }}
        />
      )}

      {/* 侧边栏 */}
      <div
        className="sidebar"
        style={{
          width: 200,
          minWidth: 200,
          background: '#141428',
          borderRight: '1px solid #2a2a4a',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          // 手机端：滑出/滑入动画
          transform: isMobile ? (sidebarVisible ? 'translateX(0)' : 'translateX(-100%)') : 'none',
          transition: isMobile ? 'transform 0.3s ease' : 'none',
        }}
      >
        <div style={{ padding: '18px 16px 14px', fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: 1, borderBottom: '1px solid #2a2a4a', flexShrink: 0 }}>
          3L · NAV
        </div>

        <div className="sidebar-nav" style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
          {GROUPS.map(group => (
            <div key={group}>
              <div style={{ padding: '14px 16px 4px', fontSize: 10, color: '#555', textTransform: 'uppercase', letterSpacing: 1 }}>{group}</div>
              {NAV_ITEMS.filter(item => item.group === group).map(item => {
                const isCurrent = item.id === currentId
                return (
                  <a
                    key={item.id}
                    href={item.href}
                    onClick={handleNavClick}
                    className={`nav-item${isCurrent ? ' active' : ''}`}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 16px', fontSize: 13,
                      color: isCurrent ? '#fff' : '#aaa',
                      textDecoration: 'none',
                      borderLeft: '3px solid',
                      borderLeftColor: isCurrent ? item.accent : 'transparent',
                      background: isCurrent ? 'rgba(255,255,255,0.03)' : 'transparent',
                      transition: 'all 0.15s',
                      cursor: 'pointer',
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

        <div className="sidebar-footer" style={{ borderTop: '1px solid #2a2a4a', padding: '10px 16px', flexShrink: 0 }}>
          {FOOTER_LINKS.map((link, i) => (
            <span key={link.id}>
              {i > 0 && <span style={{ color: '#333', margin: '0 4px' }}>·</span>}
              <a
                href={link.href}
                onClick={handleNavClick}
                style={{ color: '#555', textDecoration: 'none', fontSize: 11 }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#888' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#555' }}
              >{link.label}</a>
            </span>
          ))}
        </div>
      </div>
    </>
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

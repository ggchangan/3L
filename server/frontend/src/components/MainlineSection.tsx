import { useState, useEffect } from 'react'
import { fetchReviewByDate } from '../lib/api'
import type { LineItem } from '../lib/types'

interface MainlineData {
  lines?: LineItem[]
  secondary?: LineItem[]
  persistence?: { name: string; days: number; status: string }[]
  all_ranked?: LineItem[]
  type?: string
  concept_mainline?: MainlineData
}

interface Props {
  data: MainlineData | null | undefined
  dates: string[]
  currentDate: string
}

const TAB_STYLE_BASE = { padding: '6px 16px', fontSize: 13, borderRadius: '6px 6px 0 0', cursor: 'pointer', border: 'none', fontWeight: 600 } as const

// 机会类型配置：emoji + 颜色 + 显示顺序
const OPP_GROUPS: { key: string; label: string; emoji: string; color: string; bg: string }[] = [
  { key: '主线回调', label: '主线回调机会', emoji: '🎯', color: '#e94560', bg: 'rgba(233,69,96,0.12)' },
  { key: '次线机会', label: '次线机会', emoji: '🎯', color: '#ffd700', bg: 'rgba(255,215,0,0.1)' },
  { key: '波谷观察', label: '波谷观察', emoji: '🔮', color: '#4ecdc4', bg: 'rgba(78,205,196,0.1)' },
  { key: '趋势延续', label: '趋势延续', emoji: '📈', color: '#44aa44', bg: 'rgba(68,170,68,0.08)' },
  { key: '见顶风险', label: '见顶风险', emoji: '⚠️', color: '#ff6b00', bg: 'rgba(255,107,0,0.1)' },
  { key: '回调中', label: '回调中', emoji: '📉', color: '#888', bg: 'rgba(136,136,136,0.06)' },
  { key: '主线观察', label: '主线观察', emoji: '👀', color: '#666', bg: 'rgba(102,102,102,0.06)' },
  { key: '次级观察', label: '次级观察', emoji: '👀', color: '#666', bg: 'rgba(102,102,102,0.06)' },
]

// 将 opp key 映射到分组索引
const OPP_GROUP_ORDER: Record<string, number> = {}
OPP_GROUPS.forEach((g, i) => { OPP_GROUP_ORDER[g.key] = i })

const STAGE_ICONS: Record<string, string> = {
  '波谷': '🟢', '波峰': '🔴', '上涨': '📈', '下跌': '📉', '波中': '➡️',
}
const STAGE_COLORS: Record<string, string> = {
  '波谷': '#4ecdc4', '波峰': '#e94560', '上涨': '#44aa44', '下跌': '#888', '波中': '#ffd700',
}

const chgColor = (v?: number) => {
  if (!v) return '#555'
  if (v > 0) return v > 5 ? '#ff4444' : '#ff6b6b'
  if (v < 0) return v < -5 ? '#00cc66' : '#44aa44'
  return '#555'
}
const chgSign = (v?: number) => {
  if (!v || v <= 0) return ''
  return '+'
}

export default function MainlineSection({ data, dates, currentDate }: Props) {
  const [prevRanked, setPrevRanked] = useState<string[]>([])
  const [rotationNote, setRotationNote] = useState('')
  const [tab, setTab] = useState<'industry' | 'concept'>('industry')

  // 选择当前 tab 的数据来源
  const activeData: MainlineData | null | undefined = tab === 'concept'
    ? data?.concept_mainline
    : data

  const allRanked = activeData?.all_ranked || []
  const persist = activeData?.persistence || []
  const mainNames = new Set((activeData?.lines || []).map(l => l.name))
  const secNames = new Set((activeData?.secondary || []).map(l => l.name))

  const persistDays: Record<string, number> = {}
  persist.forEach((p: any) => { persistDays[p.name] = p.days })

  // 获取前一天的排名
  useEffect(() => {
    if (!data || !dates.length || !currentDate) return
    const prevDates = dates.filter(d => d !== currentDate).sort().reverse()
    if (!prevDates.length) return
    fetchReviewByDate(prevDates[0])
      .then(prev => {
        const prevR = ((tab === 'concept' ? prev.mainline?.concept_mainline?.all_ranked : prev.mainline?.all_ranked) || []).slice(0, 10).map((l: any) => l.name)
        setPrevRanked(prevR)
      })
      .catch(() => {})
  }, [data, dates, currentDate, tab])

  // 轮动检测
  const escapeAlerts: { name: string; chg_1d: number }[] = []
  const newDirectionAlerts: { name: string; chg_1d: number }[] = []
  for (const l of allRanked) {
    const chg = l.chg_1d ?? 0
    if (chg < -3 && (mainNames.has(l.name) || secNames.has(l.name)))
      escapeAlerts.push(l)
    if (chg > 3 && !mainNames.has(l.name) && !secNames.has(l.name))
      newDirectionAlerts.push(l)
  }

  useEffect(() => {
    if (!prevRanked.length || !allRanked.length) return
    const top10Names = allRanked.slice(0, 10).map(l => l.name)
    const newEntry = top10Names.filter(n => !prevRanked.includes(n))
    const gone = prevRanked.filter(n => !top10Names.includes(n))
    const parts: string[] = []
    if (newEntry.length) parts.push(`🆕 新进前10: ${newEntry.join(' · ')}`)
    if (gone.length) parts.push(`📉 跌出前10: ${gone.join(' · ')}`)
    if (escapeAlerts.length) parts.push(`⚠️ 资金出逃: ${escapeAlerts.map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    if (newDirectionAlerts.length) parts.push(`🆕 新方向观察: ${newDirectionAlerts.slice(0, 5).map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    if (parts.length) setRotationNote(parts.join(' | '))
    else setRotationNote('↔️ 前10名无变化')
  }, [prevRanked])

  if (!data) return <div className="empty">暂无主线数据</div>

  // 按机会类型分组
  const groups: Record<string, LineItem[]> = {}
  for (const item of allRanked) {
    const opp = item.opportunity || '--'
    if (!groups[opp]) groups[opp] = []
    groups[opp].push(item)
  }

  // 组排序
  const sortedGroups = Object.entries(groups).sort(([a], [b]) => {
    const oa = OPP_GROUP_ORDER[a] ?? 99
    const ob = OPP_GROUP_ORDER[b] ?? 99
    return oa - ob
  })

  // 计算完整的 top10 排名
  const top10 = allRanked.slice(0, 10)

  return (
    <>
      {/* Tab 切换 */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 12 }}>
        <button
          onClick={() => setTab('industry')}
          style={{
            ...TAB_STYLE_BASE,
            background: tab === 'industry' ? '#1a1a2e' : '#2a2a3e',
            color: tab === 'industry' ? '#e94560' : '#888',
          }}
        >🏭 行业主线</button>
        <button
          onClick={() => setTab('concept')}
          style={{
            ...TAB_STYLE_BASE,
            background: tab === 'concept' ? '#1a1a2e' : '#2a2a3e',
            color: tab === 'concept' ? '#4ecdc4' : '#888',
          }}
        >💡 概念主线</button>
      </div>

      {/* 轮动提醒 */}
      {rotationNote && (
        <div style={{
          marginBottom: 10, minHeight: 20, fontSize: 12,
          color: rotationNote.includes('🆕') || rotationNote.includes('⚠️') ? '#4ecdc4' : rotationNote.includes('📉') ? '#e94560' : '#888',
          lineHeight: 1.6,
        }}>
          {rotationNote}
        </div>
      )}

      {/* 资金出逃 + 新方向 详细条 */}
      {(escapeAlerts.length > 0 || newDirectionAlerts.length > 0) && (
        <div style={{ marginBottom: 10, fontSize: 11, lineHeight: 1.8 }}>
          {escapeAlerts.length > 0 && (
            <div style={{ color: '#e94560' }}>
              ⚠️ 出逃：{escapeAlerts.map(e => `${e.name} ${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%`).join(' | ')}
            </div>
          )}
          {newDirectionAlerts.length > 0 && (
            <div style={{ color: '#4ecdc4' }}>
              🆕 新方向：{newDirectionAlerts.slice(0, 8).map(e => `${e.name} ${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%`).join(' | ')}
            </div>
          )}
        </div>
      )}

      {/* 按机会类型分组展示 */}
      {sortedGroups.map(([opp, items]) => {
        const groupConfig = OPP_GROUPS.find(g => g.key === opp)
        const emoji = groupConfig?.emoji || '📋'
        const label = groupConfig?.label || '其他'
        const color = groupConfig?.color || '#888'
        const bg = groupConfig?.bg || 'rgba(255,255,255,0.02)'
        const isOther = opp === '--'
        const isCollapsible = isOther || opp === '回调中' || opp === '次级观察'

        return (
          <GroupSection
            key={opp}
            emoji={emoji}
            label={label}
            color={color}
            bg={bg}
            count={items.length}
            defaultCollapsed={isCollapsible}
          >
            {items.slice(0, isOther ? 10 : undefined).map((item, i) => {
              const stage = item.stage || '--'
              const stageIcon = STAGE_ICONS[stage] || '•'
              const stageColor = STAGE_COLORS[stage] || '#888'
              const c = item.chg_1d ?? 0
              return (
                <div key={item.name} style={{
                  display: 'flex', alignItems: 'center',
                  padding: '5px 10px', marginBottom: 3,
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 6, fontSize: 12, flexWrap: 'wrap', gap: '2px 8px',
                }}>
                  <span style={{ fontWeight: 600, minWidth: 80 }}>{item.name}</span>
                  <span style={{ color: chgColor(c), fontSize: 11 }}>
                    今日{c > 0 ? '+' : ''}{c.toFixed(1)}%
                  </span>
                  <span style={{ color: item.chg_20d >= 0 ? '#ff4444' : '#44aa44', fontSize: 11 }}>
                    20日+{item.chg_20d.toFixed(1)}%
                  </span>
                  <span style={{ color: stageColor, fontSize: 11 }}>
                    {stageIcon} {stage}
                  </span>
                  {item.vl_score && item.vl_score > 0 ? (
                    <span style={{ color: '#4ecdc4', fontSize: 10 }}>vl{item.vl_score}</span>
                  ) : null}
                  {persistDays[item.name] ? (
                    <span style={{ color: '#888', fontSize: 10 }}>{persistDays[item.name]}天</span>
                  ) : null}
                  {opp !== '--' && (
                    <span style={{ color, fontSize: 10, fontWeight: 600 }}>
                      {emoji} {opp}
                    </span>
                  )}
                </div>
              )
            })}
            {isOther && items.length > 10 && (
              <div style={{ color: '#555', fontSize: 11, textAlign: 'center', padding: 4 }}>
                +{items.length - 10} 个板块未显示
              </div>
            )}
          </GroupSection>
        )
      })}

      {/* 完整排名表格 — 折叠 */}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: 'pointer', color: '#888', fontSize: 12 }}>
          📋 查看完整排名
        </summary>
        <table style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>#</th>
              <th>{tab === 'concept' ? '概念' : '行业'}</th>
              <th>20日涨幅</th>
              <th>今日涨跌</th>
              <th>阶段</th>
              <th>机会类型</th>
              <th>变动</th>
              <th>天数</th>
            </tr>
          </thead>
          <tbody>
            {top10.map((l, i) => {
              const days = persistDays[l.name] || 0
              const stage = l.stage || '--'
              const stageIcon = STAGE_ICONS[stage] || '•'
              const opp = l.opportunity || '--'
              const oppConfig = OPP_GROUPS.find(g => g.key === opp)
              const oppLabel = oppConfig ? `${oppConfig.emoji} ${opp}` : opp
              const oppColor = oppConfig?.color || '#888'

              let chgDisplay = <span style={{ color: '#555' }}>--</span>
              if (prevRanked.length) {
                const prevIdx = prevRanked.indexOf(l.name)
                if (prevIdx === i) chgDisplay = <span style={{ color: '#555' }}>—</span>
                else if (prevIdx >= 0) {
                  const dir = prevIdx > i ? '↑' : '↓'
                  const steps = Math.abs(prevIdx - i)
                  const color = prevIdx > i ? '#4ecdc4' : '#e94560'
                  chgDisplay = <span style={{ color }}>{dir}{steps} (昨#{prevIdx + 1})</span>
                } else {
                  chgDisplay = <span style={{ color: '#4ecdc4' }}>🆕新进</span>
                }
              }

              return (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td style={{ fontWeight: 600 }}>{l.name}</td>
                  <td style={{ color: l.chg_20d >= 0 ? '#ff4444' : '#44aa44' }}>
                    {l.chg_20d >= 0 ? '+' : ''}{l.chg_20d.toFixed(1)}%
                  </td>
                  <td style={{ color: chgColor(l.chg_1d), fontSize: 12 }}>
                    {chgSign(l.chg_1d)}{(l.chg_1d ?? 0).toFixed(1)}%
                  </td>
                  <td style={{ color: STAGE_COLORS[stage] || '#888', fontSize: 11 }}>
                    {stageIcon} {stage}
                  </td>
                  <td style={{ color: oppColor, fontSize: 11, fontWeight: 600 }}>
                    {oppLabel}
                  </td>
                  <td style={{ fontSize: 11 }}>{chgDisplay}</td>
                  <td>{days > 0 ? days + '天' : '--'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div style={{ marginTop: 4, color: '#555', fontSize: 10, textAlign: 'right' }}>
          20日涨幅排序 · 分组: 机会类型优先级
        </div>
      </details>
    </>
  )
}

// 分组渲染组件（含折叠功能）
function GroupSection({
  emoji, label, color, bg, count, defaultCollapsed, children,
}: {
  emoji: string; label: string; color: string; bg: string; count: number;
  defaultCollapsed?: boolean; children: React.ReactNode
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed ?? false)
  if (count === 0) return null
  return (
    <div style={{ marginBottom: 10 }}>
      <div
        onClick={() => setCollapsed(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          marginBottom: 6, cursor: 'pointer', userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 14 }}>{emoji}</span>
        <span style={{ color, fontWeight: 600, fontSize: 13 }}>{label}</span>
        <span style={{ color: '#888', fontSize: 11 }}>{count}个</span>
        <span style={{ color: '#555', fontSize: 10, marginLeft: 'auto' }}>
          {collapsed ? '展开 ▸' : '折叠 ▾'}
        </span>
      </div>
      {!collapsed && <div style={{ background: bg, borderRadius: 8, padding: 6 }}>{children}</div>}
    </div>
  )
}

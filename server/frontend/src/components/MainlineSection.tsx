import { useState, useEffect } from 'react'
import { fetchReviewByDate } from '../lib/api'
import type { LineItem } from '../lib/types'

interface MainlineData {
  ranking_status?: 'confirmed' | 'estimated' | 'partial' | 'stale'
  ranking_date?: string
  base_date?: string
  estimate_coverage?: number | null
  coverage?: number | null
  coverage_detail?: {
    covered?: number | null
    expected?: number | null
    missing?: string[]
  }
  calibration?: {
    status: 'pending' | 'completed'
    top5_overlap?: number
    top10_overlap?: number
    entered?: string[]
    exited?: string[]
  } | null
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

// 主线/动量决定方向优先级；板块量价阶段只在行内提供环境提示。
const DIRECTION_GROUPS = [
  { key: 'mainline', label: '主线方向', emoji: '🔥', color: '#e94560', bg: 'rgba(233,69,96,0.10)' },
  { key: 'secondary', label: '次级主线', emoji: '⚡', color: '#ffd700', bg: 'rgba(255,215,0,0.08)' },
  { key: 'other', label: '其他动量方向', emoji: '📊', color: '#888', bg: 'rgba(136,136,136,0.05)' },
] as const

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
  const [prevRanked, setPrevRanked] = useState<string[] | null>(null)
  const [comparisonDate, setComparisonDate] = useState('')
  const [comparisonStatus, setComparisonStatus] = useState<'idle' | 'loading' | 'ready' | 'unavailable' | 'error'>('idle')
  const [tab, setTab] = useState<'industry' | 'concept'>('industry')
  const [expandedLeader, setExpandedLeader] = useState<string | null>(null)

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
    setPrevRanked(null)
    setComparisonDate('')
    if (!data || !currentDate) {
      setComparisonStatus('idle')
      return
    }
    const prevDate = dates.filter(d => d < currentDate).sort().reverse()[0]
    if (!prevDate) {
      setComparisonStatus('unavailable')
      return
    }
    let cancelled = false
    setComparisonDate(prevDate)
    setComparisonStatus('loading')
    fetchReviewByDate(prevDate)
      .then(prev => {
        if (cancelled) return
        const prevR = ((tab === 'concept' ? prev.mainline?.concept_mainline?.all_ranked : prev.mainline?.all_ranked) || []).slice(0, 10).map((l: any) => l.name)
        setPrevRanked(prevR)
        setComparisonStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setComparisonStatus('error')
      })
    return () => { cancelled = true }
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

  const rotationNote = (() => {
    if (comparisonStatus === 'loading') return `正在读取 ${comparisonDate} 排名进行轮动比较…`
    if (comparisonStatus === 'unavailable') return '缺少上一交易日复盘，轮动比较待建立'
    if (comparisonStatus === 'error') return `${comparisonDate} 历史复盘读取失败，暂无法比较轮动`
    if (comparisonStatus !== 'ready') return ''
    if (!prevRanked?.length || !allRanked.length) return `${comparisonDate} 或当前排名数据不足，暂无法比较轮动`
    const top10Names = allRanked.slice(0, 10).map(l => l.name)
    const newEntry = top10Names.filter(n => !prevRanked.includes(n))
    const gone = prevRanked.filter(n => !top10Names.includes(n))
    const parts: string[] = []
    if (newEntry.length) parts.push(`🆕 新进前10: ${newEntry.join(' · ')}`)
    if (gone.length) parts.push(`📉 跌出前10: ${gone.join(' · ')}`)
    if (escapeAlerts.length) parts.push(`⚠️ 资金出逃: ${escapeAlerts.map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    if (newDirectionAlerts.length) parts.push(`🆕 新方向观察: ${newDirectionAlerts.slice(0, 5).map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    const detail = parts.length ? parts.join(' | ') : '↔️ 前10名无变化'
    return `对比 ${comparisonDate} · ${detail}`
  })()

  if (!data) return <div className="empty">暂无主线数据</div>

  const directionGroups = DIRECTION_GROUPS.map(group => ({
    ...group,
    items: allRanked.filter(item => {
      if (group.key === 'mainline') return mainNames.has(item.name)
      if (group.key === 'secondary') return secNames.has(item.name)
      return !mainNames.has(item.name) && !secNames.has(item.name)
    }),
  }))

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

      {activeData?.ranking_status === 'estimated' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#ffd166', background: 'rgba(255,209,102,0.1)' }}>
          当日预估 · 收盘快照覆盖 {((activeData.estimate_coverage || 0) * 100).toFixed(1)}% · 次日 06:00 用正式板块日线校准
        </div>
      )}
      {activeData?.ranking_status === 'stale' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#aaa', background: 'rgba(255,255,255,0.04)' }}>
          当日快照覆盖不足，暂沿用 {activeData.base_date || activeData.ranking_date || '上一交易日'} 已确认排名
        </div>
      )}
      {activeData?.ranking_status === 'partial' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#ffd166', background: 'rgba(255,209,102,0.1)' }}>
          正式日线部分缺失 · 覆盖 {((activeData.coverage || 0) * 100).toFixed(1)}%
          {activeData.coverage_detail?.covered != null && activeData.coverage_detail?.expected != null
            ? `（${activeData.coverage_detail.covered}/${activeData.coverage_detail.expected}）`
            : ''}
          · 缺失概念不参与当日排名
        </div>
      )}
      {activeData?.ranking_status === 'confirmed' && activeData.calibration?.status === 'completed' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#4ecdc4', background: 'rgba(78,205,196,0.08)' }}>
          已完成次日校准 · Top5 重合 {activeData.calibration.top5_overlap ?? 0}/5 · Top10 重合 {activeData.calibration.top10_overlap ?? 0}/10
        </div>
      )}

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

      <div style={{ marginBottom: 12, color: '#888', fontSize: 11, lineHeight: 1.6 }}>
        阅读顺序：先看主线/次级主线的动量排名，再看板块所处阶段。波谷是加分项，波中和波峰中的个股仍可能出现有效买点。
      </div>

      {/* 按方向层级展示，避免用板块阶段替代机会判断 */}
      {directionGroups.map(({ key, items, emoji, label, color, bg }) => {
        const isOther = key === 'other'
        return (
          <GroupSection
            key={key}
            emoji={emoji}
            label={label}
            color={color}
            bg={bg}
            count={items.length}
            defaultCollapsed={isOther}
          >
            {items.slice(0, isOther ? 10 : undefined).map((item, i) => {
              const stage = item.stage || '--'
              const stageIcon = STAGE_ICONS[stage] || '•'
              const stageColor = STAGE_COLORS[stage] || '#888'
              const c = item.chg_1d ?? 0
              const showLeaders = expandedLeader === item.name
              const leaders = item.leaders || []
              return (
                <div key={item.name} style={{
                  display: 'flex', alignItems: 'center',
                  padding: '5px 10px', marginBottom: 3,
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 6, fontSize: 12, flexWrap: 'wrap', gap: '2px 8px',
                }}>
                  <span style={{ fontWeight: 600, minWidth: 80 }}>{item.name}</span>
                  <span style={{ color: chgColor(c), fontSize: 11 }}>
                    {activeData?.ranking_status === 'estimated' && !item.estimate_applied
                      ? '今日--'
                      : `今日${c > 0 ? '+' : ''}${c.toFixed(1)}%`}
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
                  <span style={{ color, fontSize: 10, fontWeight: 600 }}>
                    {key === 'mainline' ? '主线' : key === 'secondary' ? '次级主线' : `动量#${allRanked.indexOf(item) + 1}`}
                  </span>
                  {leaders.length > 0 && (
                    <span
                      onClick={() => setExpandedLeader(showLeaders ? null : item.name)}
                      style={{ cursor: 'pointer', color: '#888', fontSize: 10, marginLeft: 'auto' }}
                    >📈 {showLeaders ? '收起' : '领涨'}</span>
                  )}
                  {showLeaders && leaders.length > 0 && (
                    <div style={{ width: '100%', padding: '6px 0 2px 0', fontSize: 11 }}>
                      {leaders.map((ld: any) => (
                        <span key={ld.code} style={{
                          display: 'inline-block', marginRight: 10, marginBottom: 3,
                          color: ld.chg_5d >= 5 ? '#ff6b6b' : ld.chg_5d > 0 ? '#44aa44' : '#888',
                        }}>
                          <span
                            onClick={() => {
                              fetch('/api/watchlist/add-stock', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({code: ld.code, name: ld.name}),
                              }).then(r => r.json()).then(res => {
                                if (res.success) alert(res.msg)
                              })
                            }}
                            style={{ cursor: 'pointer', marginRight: 2 }}
                            title="加自选"
                          >➕</span>
                          {ld.name}
                          <span style={{ color: '#555', fontSize: 10 }}>
                            {' '}{ld.chg_1d > 0 ? '+' : ''}{ld.chg_1d}% / 5d{ld.chg_5d > 0 ? '+' : ''}{ld.chg_5d}%
                          </span>
                          {ld.tag && <span style={{ fontSize: 10, marginLeft: 2 }}>{ld.tag}</span>}
                        </span>
                      ))}
                    </div>
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
              <th>方向层级</th>
              <th>变动</th>
              <th>天数</th>
            </tr>
          </thead>
          <tbody>
            {top10.map((l, i) => {
              const days = persistDays[l.name] || 0
              const stage = l.stage || '--'
              const stageIcon = STAGE_ICONS[stage] || '•'
              const level = mainNames.has(l.name) ? '主线' : secNames.has(l.name) ? '次级主线' : '其他动量'
              const levelColor = level === '主线' ? '#e94560' : level === '次级主线' ? '#ffd700' : '#888'

              let chgDisplay = <span style={{ color: '#555' }}>--</span>
              if (prevRanked?.length) {
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
                    {activeData?.ranking_status === 'estimated' && !l.estimate_applied
                      ? '--'
                      : `${chgSign(l.chg_1d)}${(l.chg_1d ?? 0).toFixed(1)}%`}
                  </td>
                  <td style={{ color: STAGE_COLORS[stage] || '#888', fontSize: 11 }}>
                    {stageIcon} {stage}
                  </td>
                  <td style={{ color: levelColor, fontSize: 11, fontWeight: 600 }}>
                    {level}
                  </td>
                  <td style={{ fontSize: 11 }}>{chgDisplay}</td>
                  <td>{days > 0 ? days + '天' : '--'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div style={{ marginTop: 4, color: '#555', fontSize: 10, textAlign: 'right' }}>
          20日涨幅排序 · 方向层级优先展示 · 板块阶段仅作环境提示
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

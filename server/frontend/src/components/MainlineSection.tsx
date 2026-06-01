import { useState, useEffect } from 'react'
import { fetchReviewByDate } from '../lib/api'

interface LineItem {
  name: string
  chg_20d: number
  chg_1d?: number
}

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

export default function MainlineSection({ data, dates, currentDate }: Props) {
  const [prevRanked, setPrevRanked] = useState<string[]>([])
  const [rotationNote, setRotationNote] = useState('')
  const [tab, setTab] = useState<'industry' | 'concept'>('industry')

  // 选择当前 tab 的数据来源
  const activeData: MainlineData | null | undefined = tab === 'concept'
    ? data?.concept_mainline
    : data

  // 获取前一天的排名（用于变动列）
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

  if (!data) return <div className="empty">暂无主线数据</div>

  const primary = activeData?.lines || []
  const secondary = activeData?.secondary || []
  const persist = activeData?.persistence || []
  const allRanked = activeData?.all_ranked || []
  const top10 = allRanked.slice(0, 10)

  const persistDays: Record<string, number> = {}
  persist.forEach((p: any) => { persistDays[p.name] = p.days })

  const mainNames = new Set(primary.map(l => l.name))
  const secNames = new Set(secondary.map(l => l.name))

  // 轮动检测 — 基于当日涨跌幅的资金流向
  const escapeAlerts: { name: string; chg_1d: number }[] = []
  const newDirectionAlerts: { name: string; chg_1d: number }[] = []
  for (const l of allRanked) {
    const chg = l.chg_1d ?? 0
    if (chg < -3 && (mainNames.has(l.name) || secNames.has(l.name)))
      escapeAlerts.push(l)
    // 新方向：不在前10但日涨幅>3%
    if (chg > 3 && !mainNames.has(l.name) && !secNames.has(l.name))
      newDirectionAlerts.push(l)
  }

  // 排名变动检测（对比前一天 top10）
  useEffect(() => {
    if (!prevRanked.length || !top10.length) return
    const todayNames = top10.map(l => l.name)
    const newEntry = todayNames.filter(n => !prevRanked.includes(n))
    const gone = prevRanked.filter(n => !todayNames.includes(n))
    const parts: string[] = []
    if (newEntry.length) parts.push(`🆕 新进前10: ${newEntry.join(' · ')}`)
    if (gone.length) parts.push(`📉 跌出前10: ${gone.join(' · ')}`)
    // 资金出逃
    if (escapeAlerts.length) parts.push(`⚠️ 资金出逃: ${escapeAlerts.map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    // 新方向
    if (newDirectionAlerts.length) parts.push(`🆕 新方向观察: ${newDirectionAlerts.slice(0, 5).map(e => `${e.name}(${e.chg_1d > 0 ? '+' : ''}${e.chg_1d?.toFixed(1)}%)`).join(' · ')}`)
    if (parts.length) setRotationNote(parts.join(' | '))
    else setRotationNote('↔️ 前10名无变化')
  }, [prevRanked])

  // 今日涨跌颜色
  const chgColor = (v?: number) => {
    if (!v) return '#555'
    if (v > 0) return v > 5 ? '#ff4444' : '#ff6b6b'
    if (v < 0) return v < -5 ? '#00cc66' : '#44aa44'
    return '#555'
  }
  const chgSign = (v?: number) => {
    if (!v) return ''
    return v > 0 ? '+' : ''
  }

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

      {/* 轮动提醒横幅 */}
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

      {/* 主线标签 */}
      {primary.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: '#e94560', fontWeight: 600, fontSize: 14 }}>🔴 主线</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            {primary.map((l, i) => (
              <span key={i} style={{ background: 'rgba(233,69,96,0.15)', border: '1px solid #e94560', borderRadius: 6, padding: '4px 12px', fontSize: 13, color: '#e94560' }}>
                {l.name}{' '}
                <span style={{ fontSize: 11, color: '#888' }}>
                  20日+{l.chg_20d.toFixed(1)}%
                  {l.chg_1d !== undefined && (
                    <span style={{ color: chgColor(l.chg_1d), marginLeft: 4 }}>
                      今日{chgSign(l.chg_1d)}{l.chg_1d.toFixed(1)}%
                    </span>
                  )}
                  {persistDays[l.name] ? ` · ${persistDays[l.name]}天` : ''}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 次级主线标签 */}
      {secondary.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: '#ffd700', fontWeight: 600, fontSize: 14 }}>🟡 次级主线</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            {secondary.map((l, i) => (
              <span key={i} style={{ background: 'rgba(255,215,0,0.1)', border: '1px solid rgba(255,215,0,0.3)', borderRadius: 6, padding: '4px 12px', fontSize: 13, color: '#ffd700' }}>
                {l.name}{' '}
                <span style={{ fontSize: 11, color: '#888' }}>
                  20日+{l.chg_20d.toFixed(1)}%
                  {l.chg_1d !== undefined && (
                    <span style={{ color: chgColor(l.chg_1d), marginLeft: 4 }}>
                      今日{chgSign(l.chg_1d)}{l.chg_1d.toFixed(1)}%
                    </span>
                  )}
                  {persistDays[l.name] ? ` · ${persistDays[l.name]}天` : ''}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 表格 */}
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>{tab === 'concept' ? '概念' : '行业'}</th>
            <th>20日涨幅</th>
            <th>今日涨跌</th>
            <th>变动</th>
            <th>持续天数</th>
            <th>标签</th>
          </tr>
        </thead>
        <tbody>
          {top10.map((l, i) => {
            const days = persistDays[l.name] || 0
            let tag = <span className="tag gray">其他</span>
            if (mainNames.has(l.name)) tag = <span className="tag red">主线</span>
            else if (secNames.has(l.name)) tag = <span className="tag" style={{ background: 'rgba(255,215,0,0.15)', color: '#ffd700', border: '1px solid rgba(255,215,0,0.3)' }}>次级</span>

            // 今日涨跌标记
            let chgNote = ''
            const c = l.chg_1d ?? 0
            if (c < -3) chgNote = ' ⚠️'
            else if (c > 3 && !mainNames.has(l.name) && !secNames.has(l.name)) chgNote = ' 🆕'

            // 变动列
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
                <td style={{ color: chgColor(c), fontSize: 12 }}>
                  {c > 0 ? '+' : ''}{c.toFixed(1)}%{chgNote}
                </td>
                <td style={{ fontSize: 11 }}>{chgDisplay}</td>
                <td>{days > 0 ? days + '天' : '--'}</td>
                <td>{tag}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div style={{ marginTop: 8, color: '#555', fontSize: 10, textAlign: 'right' }}>
        20日涨幅排序 · 前5=主线 · 6~10=次级主线
      </div>
    </>
  )
}

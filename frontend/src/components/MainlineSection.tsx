import { useState, useEffect } from 'react'
import { fetchReviewByDate } from '../lib/api'

interface MainlineData {
  lines?: { name: string; chg_20d: number }[]
  secondary?: { name: string; chg_20d: number }[]
  persistence?: { name: string; days: number }[]
  all_ranked?: { name: string; chg_20d: number }[]
}

interface Props {
  data: MainlineData | null | undefined
  dates: string[]
  currentDate: string
}

const SEC_ORDER = ['算力', '半导体', '机器人', '新能源', '商业航天', 'AI应用', '资源股', '创新药']

export default function MainlineSection({ data, dates, currentDate }: Props) {
  const [prevRanked, setPrevRanked] = useState<string[]>([])
  const [rotationNote, setRotationNote] = useState('')

  useEffect(() => {
    if (!data || !dates.length || !currentDate) return
    const prevDates = dates.filter(d => d !== currentDate).sort().reverse()
    if (!prevDates.length) return
    fetchReviewByDate(prevDates[0])
      .then(prev => {
        const prevR = (prev.mainline?.all_ranked || []).slice(0, 10).map(l => l.name)
        setPrevRanked(prevR)
      })
      .catch(() => {})
  }, [data, dates, currentDate])

  if (!data) return <div className="empty">暂无主线数据</div>

  const primary = data.lines || []
  const secondary = data.secondary || []
  const persist = data.persistence || []
  const allRanked = data.all_ranked || []
  const top10 = allRanked.slice(0, 10)

  const persistDays: Record<string, number> = {}
  persist.forEach(p => { persistDays[p.name] = p.days })

  const mainNames = new Set(primary.map(l => l.name))
  const secNames = new Set(secondary.map(l => l.name))

  // 轮动检测
  useEffect(() => {
    if (!prevRanked.length || !top10.length) return
    const todayNames = top10.map(l => l.name)
    const newEntry = todayNames.filter(n => !prevRanked.includes(n))
    const gone = prevRanked.filter(n => !todayNames.includes(n))
    if (newEntry.length || gone.length) {
      const parts: string[] = []
      if (newEntry.length) parts.push(`🆕 新进前10: ${newEntry.join(' · ')}`)
      if (gone.length) parts.push(`📉 跌出前10: ${gone.join(' · ')}`)
      setRotationNote(parts.join(' | '))
    } else {
      setRotationNote('↔️ 前10名无变化')
    }
  }, [prevRanked])

  return (
    <>
      {rotationNote && (
        <div style={{ marginBottom: 10, minHeight: 20, fontSize: 12, color: rotationNote.includes('🆕') ? '#4ecdc4' : '#888' }}>
          {rotationNote}
        </div>
      )}

      {primary.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: '#e94560', fontWeight: 600, fontSize: 14 }}>🔴 主线</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            {primary.map((l, i) => (
              <span key={i} style={{ background: 'rgba(233,69,96,0.15)', border: '1px solid #e94560', borderRadius: 6, padding: '4px 12px', fontSize: 13, color: '#e94560' }}>
                {l.name} <span style={{ fontSize: 11, color: '#888' }}>+{l.chg_20d.toFixed(1)}%{persistDays[l.name] ? ` · ${persistDays[l.name]}天` : ''}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {secondary.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: '#ffd700', fontWeight: 600, fontSize: 14 }}>🟡 次级主线</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            {secondary.map((l, i) => (
              <span key={i} style={{ background: 'rgba(255,215,0,0.1)', border: '1px solid rgba(255,215,0,0.3)', borderRadius: 6, padding: '4px 12px', fontSize: 13, color: '#ffd700' }}>
                {l.name} <span style={{ fontSize: 11, color: '#888' }}>+{l.chg_20d.toFixed(1)}%{persistDays[l.name] ? ` · ${persistDays[l.name]}天` : ''}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <table>
        <thead>
          <tr><th>#</th><th>行业</th><th>20日涨幅</th><th>变动</th><th>持续天数</th><th>标签</th></tr>
        </thead>
        <tbody>
          {top10.map((l, i) => {
            const days = persistDays[l.name] || 0
            let tag = <span className="tag gray">其他</span>
            if (mainNames.has(l.name)) tag = <span className="tag red">主线</span>
            else if (secNames.has(l.name)) tag = <span className="tag" style={{ background: 'rgba(255,215,0,0.15)', color: '#ffd700', border: '1px solid rgba(255,215,0,0.3)' }}>次级</span>

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

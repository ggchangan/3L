import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'

const SCORE_COLORS: Record<string, string> = {
  confirmed: '#4ecdc4',
  neutral: '#f59e0b',
  diverged: '#e94560',
}

const SCORE_LABELS: Record<string, string> = {
  confirmed: '✅ 印证',
  neutral: '➖ 一般',
  diverged: '❌ 背离',
}

export default function LogicTrackingDetail() {
  const { tagId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!tagId) return
    fetch(`/api/logic-tracking/tags/detail?id=${tagId}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tagId])

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}><NavBar /><p style={{ marginTop: 40 }}>加载中...</p></div>
  if (!data || data.error) {
    return (
      <div style={{ padding: '0 12px', maxWidth: 800, margin: '0 auto' }}>
        <NavBar />
        <div className="info-card" style={{ textAlign: 'center', padding: 30, marginTop: 20 }}>
          <p style={{ color: '#e94560' }}>{data?.error || '标签不存在'}</p>
          <button className="action-btn" onClick={() => navigate('/logic-tracking')} style={{ marginTop: 10 }}>← 返回</button>
        </div>
      </div>
    )
  }

  const { tag, entries, stats } = data

  return (
    <div style={{ padding: '0 12px', maxWidth: 800, margin: '0 auto' }}>
      <NavBar />
      <div style={{ marginTop: 16 }}>
        <button className="action-btn" onClick={() => navigate('/logic-tracking')} style={{ fontSize: 12, marginBottom: 8 }}>
          ← 返回逻辑列表
        </button>
      </div>

      {/* Tag info card */}
      <div className="info-card" style={{ padding: 14, marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, color: '#eee', fontSize: 16 }}>{tag.name}</h2>
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: '#1a1a2e', color: '#aaa' }}>
            {tag.tier === 'focused' ? '🌟 聚焦' : tag.tier === 'core' ? '📌 核心' : '👁️ 观察'}
          </span>
        </div>
        {tag.description && <div style={{ color: '#aaa', fontSize: 12, marginTop: 4 }}>{tag.description}</div>}
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12 }}>
          <span style={{ color: '#888' }}>📄 {stats.total_entries}个事件</span>
          <span style={{ color: '#888' }}>✅ {stats.confirmed}次印证</span>
          {stats.diverged > 0 && <span style={{ color: '#e94560' }}>❌ {stats.diverged}次背离</span>}
          {stats.avg_5d_return !== 0 && (
            <span style={{ color: stats.avg_5d_return > 0 ? '#4ecdc4' : '#e94560' }}>
              📊 5日均{stats.avg_5d_return > 0 ? '+' : ''}{stats.avg_5d_return}%
            </span>
          )}
          <span style={{ color: '#888' }}>印证率 {Math.round((stats.verify_rate || 0) * 100)}%</span>
        </div>
        {tag.related_industries?.length > 0 && (
          <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
            {tag.related_industries.map((ind: string) => (
              <span key={ind} style={{ fontSize: 10, padding: '1px 6px', background: '#1a1a2e', borderRadius: 3, color: '#888' }}>{ind}</span>
            ))}
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div className="info-card" style={{ flex: 1, textAlign: 'center', padding: 10 }}>
          <div style={{ fontSize: 22, fontWeight: 'bold', color: '#4ecdc4' }}>{stats.confirmed}</div>
          <div style={{ fontSize: 11, color: '#888' }}>印证</div>
        </div>
        <div className="info-card" style={{ flex: 1, textAlign: 'center', padding: 10 }}>
          <div style={{ fontSize: 22, fontWeight: 'bold', color: '#f59e0b' }}>{stats.total_entries - stats.confirmed - stats.diverged}</div>
          <div style={{ fontSize: 11, color: '#888' }}>待验证</div>
        </div>
        <div className="info-card" style={{ flex: 1, textAlign: 'center', padding: 10 }}>
          <div style={{ fontSize: 22, fontWeight: 'bold', color: '#e94560' }}>{stats.diverged}</div>
          <div style={{ fontSize: 11, color: '#888' }}>背离</div>
        </div>
      </div>

      {/* Timeline */}
      <h3 style={{ color: '#aaa', fontSize: 14, margin: '0 0 8px' }}>⏳ 事件时间线</h3>
      {entries.length === 0 ? (
        <div className="info-card" style={{ textAlign: 'center', padding: 20, color: '#666' }}>
          <p style={{ fontSize: 13 }}>暂无事件，去「📤 投喂」添加资料</p>
        </div>
      ) : (
        entries.map((entry: any, idx: number) => {
          const v = entry.verify || {}
          const dateStr = (entry.fed_at || '').slice(0, 10)
          const isToday = dateStr === new Date().toISOString().slice(0, 10)
          return (
            <div key={entry.id} className="info-card" style={{ padding: 10, marginBottom: 6, borderLeft: `3px solid ${SCORE_COLORS[v.score] || '#333'}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: 12, color: isToday ? '#4ecdc4' : '#aaa' }}>
                  {dateStr} {isToday && '🔥'}
                </div>
                <div style={{ fontSize: 11, color: '#666' }}>{entry.source_name || ''}</div>
              </div>
              <div style={{ color: '#ddd', fontSize: 13, marginTop: 2 }}>{entry.title}</div>
              {entry.summary && (
                <div style={{ color: '#777', fontSize: 11, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.summary.slice(0, 120)}
                </div>
              )}
              {v.verified_at && (
                <div style={{ display: 'flex', gap: 10, marginTop: 4, fontSize: 11 }}>
                  <span style={{ color: v['3d_return'] >= 0 ? '#4ecdc4' : '#e94560' }}>
                    3日{v['3d_return'] > 0 ? '+' : ''}{v['3d_return']}%
                  </span>
                  <span style={{ color: v['5d_return'] >= 0 ? '#4ecdc4' : '#e94560' }}>
                    5日{v['5d_return'] > 0 ? '+' : ''}{v['5d_return']}%
                  </span>
                  <span style={{ color: SCORE_COLORS[v.score] || '#888' }}>
                    {SCORE_LABELS[v.score] || ''}
                  </span>
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}

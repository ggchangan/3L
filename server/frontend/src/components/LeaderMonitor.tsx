import { useEffect, useState } from 'react'
import { fetchLeaderDashboard } from '../lib/api'
import type { LeaderDashboardData, WatchedIndustryItem, AnomalyData, SwitchingEvent } from '../lib/types'

interface ManualAddState {
  showInput: boolean
  input: string
  existing: string[]
}

export default function LeaderMonitor() {
  const [data, setData] = useState<LeaderDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(true)
  const [collapsedWatched, setCollapsedWatched] = useState(false)
  const [manual, setManual] = useState<ManualAddState>({ showInput: false, input: '', existing: [] })

  const load = () => {
    setLoading(true)
    fetchLeaderDashboard().then(d => {
      setData(d)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleAddIndustry = async () => {
    const name = manual.input.trim()
    if (!name) return
    // 调用后端API添加关注行业
    try {
      const r = await fetch('/api/monitor/add-watched-industry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry: name }),
      })
      if (r.ok) {
        setManual({ ...manual, input: '', showInput: false })
        load()
      }
    } catch {}
  }

  const handleRemoveIndustry = async (industry: string) => {
    try {
      await fetch('/api/monitor/remove-watched-industry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry }),
      })
      load()
    } catch {}
  }

  if (loading && !data) return <div className="empty">加载中...</div>
  if (!data || data.error) return <div className="empty">{data?.error || '暂无数据'}</div>

  const { watched, anomalies } = data

  return (
    <>
      <div className="block-title" style={{ marginBottom: 0, cursor: 'pointer' }} onClick={() => setCollapsed(v => !v)}>
        🏆 龙头观测
        <span className="badge">{watched.length + (anomalies?.surge?.length || 0) + (anomalies?.plunge?.length || 0) + (anomalies?.switching?.length || 0)}</span>
        <span className="collapse-indicator">{collapsed ? '▶' : '▼'}</span>
      </div>

      {!collapsed && (
        <>
          {/* 区块1: 关注的行业 */}
          <div className="info-block" style={{ marginTop: 4 }}>
            <div className="block-title-sm" style={{ cursor: 'pointer' }} onClick={() => setCollapsedWatched(v => !v)}>
              📋 关注的行业 <span className="badge">{watched.length}</span>
              <span className="collapse-indicator">{collapsedWatched ? '▶' : '▼'}</span>
            </div>
            {!collapsedWatched && (
              <table className="leader-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    <th>行业</th>
                    <th>龙头</th>
                    <th>涨跌</th>
                    <th>标记</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {watched.map((item, i) => (
                    <tr key={i}>
                      <td style={{ color: '#aaa', whiteSpace: 'nowrap' }}>
                        {item.industry}
                        {item.source_tags.length > 0 && (
                          <span style={{ fontSize: 9, color: '#666', marginLeft: 4 }}>
                            {item.source_tags.join('/')}
                          </span>
                        )}
                      </td>
                      <td><b>{item.leader_name}</b></td>
                      <td className={item.chg >= 0 ? 'up' : 'down'} style={{ whiteSpace: 'nowrap' }}>
                        {item.chg >= 0 ? '+' : ''}{item.chg}%
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {item.marks.length > 0 ? (
                          <span style={{ fontSize: 10 }}>
                            {item.marks.map((m, j) => (
                              <span key={j} style={{
                                padding: '1px 3px', marginRight: 2,
                                borderRadius: 3,
                                background: m.includes('突破') ? '#1a3a2a' :
                                           m.includes('领跌') ? '#3a1a1a' :
                                           m.includes('放量') ? '#1a2a3a' :
                                           m.includes('挑战') ? '#2a2a1a' :
                                           m.includes('背离') ? '#2a1a2a' : '#222',
                                color: m.includes('突破') ? '#4ecdc4' :
                                       m.includes('领跌') ? '#ff6b6b' :
                                       m.includes('放量') ? '#4ecdc4' :
                                       m.includes('挑战') ? '#ffd93d' :
                                       m.includes('背离') ? '#c084fc' : '#ccc',
                              }}>{m}</span>
                            ))}
                          </span>
                        ) : <span style={{ color: '#444' }}>-</span>}
                      </td>
                      <td>
                        {item.source_tags.includes('关注') && (
                          <span
                            style={{ cursor: 'pointer', color: '#666', fontSize: 10 }}
                            onClick={() => handleRemoveIndustry(item.industry)}
                            title="移除关注"
                          >✕</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={5}>
                      {manual.showInput ? (
                        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                          <input
                            value={manual.input}
                            onChange={e => setManual({ ...manual, input: e.target.value })}
                            onKeyDown={e => e.key === 'Enter' && handleAddIndustry()}
                            placeholder="输入行业名"
                            style={{
                              flex: 1, background: '#1a1a1a', border: '1px solid #333',
                              color: '#ccc', padding: '2px 6px', borderRadius: 3, fontSize: 11,
                            }}
                          />
                          <span className="action-btn" style={{ fontSize: 10 }} onClick={handleAddIndustry}>确定</span>
                          <span className="action-btn" style={{ fontSize: 10 }} onClick={() => setManual({ ...manual, showInput: false })}>取消</span>
                        </div>
                      ) : (
                        <span
                          className="action-btn" style={{ fontSize: 10 }}
                          onClick={() => setManual({ ...manual, showInput: true })}
                        >➕ 添加关注行业</span>
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            )}
          </div>

          {/* 区块2: 龙头异动 */}
          {anomalies && (
            <div className="info-block" style={{ marginTop: 4 }}>
              <div className="block-title-sm">⚡ 龙头异动</div>

              {/* 放量突破 */}
              {anomalies.surge && anomalies.surge.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, color: '#4ecdc4', marginBottom: 2 }}>🚀 放量突破 (涨幅&gt;3%)</div>
                  <table className="leader-table" style={{ fontSize: 11 }}>
                    <thead>
                      <tr><th>行业</th><th>股票</th><th>涨跌</th><th>现价</th></tr>
                    </thead>
                    <tbody>
                      {anomalies.surge.map((item, i) => (
                        <tr key={i}>
                          <td style={{ color: '#aaa', fontSize: 10 }}>{item.industry}</td>
                          <td><b>{item.name}</b></td>
                          <td className="up">+{item.chg}%</td>
                          <td style={{ color: '#ccc' }}>{item.price.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 领跌异动 */}
              {anomalies.plunge && anomalies.plunge.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, color: '#ff6b6b', marginBottom: 2 }}>⚠️ 领跌异动 (跌幅&gt;3%)</div>
                  <table className="leader-table" style={{ fontSize: 11 }}>
                    <thead>
                      <tr><th>行业</th><th>股票</th><th>涨跌</th><th>现价</th></tr>
                    </thead>
                    <tbody>
                      {anomalies.plunge.map((item, i) => (
                        <tr key={i}>
                          <td style={{ color: '#aaa', fontSize: 10 }}>{item.industry}</td>
                          <td><b>{item.name}</b></td>
                          <td className="down">{item.chg}%</td>
                          <td style={{ color: '#ccc' }}>{item.price.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 龙头切换 */}
              {anomalies.switching && anomalies.switching.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: '#ffd93d', marginBottom: 2 }}>🔄 龙头切换 (#2/#3 超越 #1)</div>
                  {anomalies.switching.map((item, i) => (
                    <div key={i} style={{
                      fontSize: 11, padding: '3px 6px', marginBottom: 2,
                      background: '#1a1a1a', borderRadius: 3,
                    }}>
                      <span style={{ color: '#aaa' }}>{item.industry}: </span>
                      <span className="down">{item.leader_name} {item.leader_chg >= 0 ? '+' : ''}{item.leader_chg}%</span>
                      <span style={{ color: '#555', margin: '0 4px' }}>vs</span>
                      <span className="up">{item.challenger_name} {item.challenger_chg >= 0 ? '+' : ''}{item.challenger_chg}%</span>
                      <span style={{ color: '#888', marginLeft: 4, fontSize: 10 }}>
                        → {item.direction} ({item.diff > 0 ? '+' : ''}{item.diff}%)
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {(!anomalies.surge || anomalies.surge.length === 0) &&
               (!anomalies.plunge || anomalies.plunge.length === 0) &&
               (!anomalies.switching || anomalies.switching.length === 0) && (
                <div className="empty" style={{ fontSize: 11 }}>暂无异常信号</div>
              )}
            </div>
          )}

          {/* 区块3: 概念板块异动 */}
          {data.concept_anomalies && (
            <div className="info-block" style={{ marginTop: 4 }}>
              <div className="block-title-sm">📦 概念板块异动</div>
              {data.concept_anomalies.surge && data.concept_anomalies.surge.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, color: '#4ecdc4', marginBottom: 2 }}>🚀 领涨 (涨幅&gt;3%)</div>
                  <table className="leader-table" style={{ fontSize: 11 }}>
                    <thead>
                      <tr><th>概念</th><th>涨幅</th><th>结构</th><th>阶段</th></tr>
                    </thead>
                    <tbody>
                      {data.concept_anomalies.surge.map((item, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 'bold' }}>{item.name}</td>
                          <td className="up">+{item.chg}%</td>
                          <td style={{ color: '#aaa', fontSize: 10 }}>{item.structure || '-'}</td>
                          <td style={{ fontSize: 10 }}>{item.phase || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {data.concept_anomalies.plunge && data.concept_anomalies.plunge.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, color: '#ff6b6b', marginBottom: 2 }}>⚠️ 领跌 (跌幅&gt;3%)</div>
                  <table className="leader-table" style={{ fontSize: 11 }}>
                    <thead>
                      <tr><th>概念</th><th>涨幅</th></tr>
                    </thead>
                    <tbody>
                      {data.concept_anomalies.plunge.map((item, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 'bold' }}>{item.name}</td>
                          <td className="down">{item.chg}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {(!data.concept_anomalies.surge || data.concept_anomalies.surge.length === 0) &&
               (!data.concept_anomalies.plunge || data.concept_anomalies.plunge.length === 0) && (
                <div className="empty" style={{ fontSize: 11 }}>暂无异动概念板块</div>
              )}
            </div>
          )}
        </>
      )}
    </>
  )
}

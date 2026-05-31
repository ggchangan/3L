import { useEffect, useState } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './ConceptWaveTracking.css'

interface WavePoint {
  date: string
  normalized: number
  change_pct: number
  volume_ratio: number
}

interface Annotation {
  date: string
  type: string
  score: number
  label: string
}

interface ConceptItem {
  code: string
  name: string
  stage: string
  vl_score: number
  pk_score: number
  bias20: number
  change_5d: number
  change_1d: number
  volume_ratio: number
  mainline_rank: number | null
  mainline_badge: string | null
  volume_signal: string | null
  entry_window: boolean
  vs_market_5d: number
  vs_market_20d: number
  historical_gain: number | null
  last_peak_date: string | null
  last_trough_date: string | null
  cycle_days: number | null
  cycle_count: number
  related_stocks: string[]
  related_count: number
  related_codes: string[]
  stock_count: number
  wave_data: WavePoint[]
  annotations: Annotation[]
}

interface AlertItem {
  code: string
  name: string
  vl_score: number
  reason: string
  date: string
}

interface NewHotItem {
  code: string
  name: string
  gain_20d: number
  stock_count: number
  source: string
}

interface WaveData {
  success: boolean
  date: string
  data_timestamp: string
  stats: {
    total: number
    valley: number
    mid: number
    declining: number
    alerts_count: number
    new_this_week: number
  }
  grouped: {
    valley: ConceptItem[]
    mid: ConceptItem[]
    declining: ConceptItem[]
  }
  alerts: AlertItem[]
  new_hot: NewHotItem[]
}

const STAGE_META: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  '波谷': { label: '重点关注', color: '#34d399', bg: '#0b2e1a', icon: '🟢' },
  '波中': { label: '正常观察', color: '#fbbf24', bg: '#2a2000', icon: '🟡' },
  '下跌': { label: '警惕观望', color: '#ef4444', bg: '#2a0b0b', icon: '🔴' },
}

const VOLUME_LABELS: Record<string, string> = {
  shrink: '💧 缩量',
  surge: '🔥 放量',
  overheat: '⚠️ 天量滞涨',
}

function fmtPct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

export default function ConceptWaveTracking() {
  const [data, setData] = useState<WaveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setLoading(true)
    setError('')
    fetch('/api/concept-wave')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => setData(d))
      .catch(e => setError(e.message || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  function toggleExpand(code: string) {
    setExpanded(prev => ({ ...prev, [code]: !prev[code] }))
  }

  const s = data?.stats
  const isEmpty = !loading && !data?.success

  return (
    <div className="page-wrap">
      <NavBar />
      <div className="content" style={{ maxWidth: 900, margin: '0 auto' }}>
        <div className="section" style={{ marginTop: 16 }}>
          <div className="section-title">
            <span className="step">📊</span>
            概念板块波谷追踪
          </div>

          {loading && !data && (
            <div className="empty">正在加载概念板块数据…</div>
          )}

          {error && (
            <div className="empty" style={{ color: '#e94560' }}>⚠️ {error}</div>
          )}

          {isEmpty && (
            <div className="empty">暂无概念板块数据，请先运行数据更新</div>
          )}

          {s && data?.success && (
            <>
              {/* 统计卡片行 */}
              <div className="card-row">
                <div className="stat-card">
                  <div className="stat-value" style={{ color: s.alerts_count > 0 ? '#34d399' : '#888' }}>{s.valley}</div>
                  <div className="stat-label">当前波谷信号</div>
                  <div className="stat-sub">共{s.total}个追踪</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#fbbf24' }}>{s.alerts_count}</div>
                  <div className="stat-label">强信号告警</div>
                  <div className="stat-sub">vl_score&ge;3</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value" style={{ color: '#34d399' }}>{s.new_this_week > 0 ? `+${s.new_this_week}` : 0}</div>
                  <div className="stat-label">本周新发现</div>
                  <div className="stat-sub">新增追踪机会</div>
                </div>
              </div>

              {/* 分组堆叠走势 */}
              <div style={{ marginTop: 12 }}>
                {(['valley', 'mid', 'declining'] as const).map(group => {
                  const items = data.grouped[group]
                  if (!items || items.length === 0) return null
                  const meta = STAGE_META[items[0].stage] || { label: '', color: '#888', bg: '#1a1b2e', icon: '🔵' }
                  return (
                    <div key={group}>
                      <div className="cw-group-header">
                        <span className="cw-tag" style={{ borderColor: meta.color, color: meta.color, background: meta.bg }}>
                          {meta.icon} {items[0].stage}组
                        </span>
                        <span className="cw-gc">{meta.label} · {items.length}个概念</span>
                      </div>

                      {items.map(item => (
                        <div key={item.code} className={`cw-card ${expanded[item.code] ? 'expanded' : ''}`}>
                          <div className="cw-main" onClick={() => toggleExpand(item.code)}>
                            <div className="cw-info">
                              <span className={item.mainline_badge === 'gold' ? 'cw-gold' : item.mainline_badge === 'silver' ? 'cw-silver' : ''}>
                                {item.mainline_badge === 'gold' ? '[金]' : item.mainline_badge === 'silver' ? '[银]' : ''}
                              </span>
                              <span className="cw-name">{item.name}</span>
                              <span className="cw-vl">vl:<span className="cw-hl">{item.vl_score}</span></span>
                            </div>

                            {/* 走势图 */}
                            <div className="cw-chart">
                              <svg viewBox="0 0 300 50" preserveAspectRatio="none">
                                {/* 大盘虚线 */}
                                {item.wave_data.length > 0 && (
                                  <polyline
                                    points={item.wave_data.map((w, i) => `${(i / (item.wave_data.length - 1 || 1)) * 300},${50 - ((w.normalized - 45) / 55) * 40}`).join(' ')}
                                    fill="none" stroke="#3a3b50" strokeWidth="1" strokeDasharray="3,3"
                                  />
                                )}
                                {/* 走势线 */}
                                {item.wave_data.length > 1 && (
                                  <polyline
                                    points={item.wave_data.map((w, i) => `${(i / (item.wave_data.length - 1 || 1)) * 300},${50 - ((w.normalized - 45) / 55) * 40}`).join(' ')}
                                    fill="none" stroke="#34d399" strokeWidth="2"
                                  />
                                )}
                                {/* 标注点 */}
                                {item.annotations.map((ann, i) => {
                                  const idx = item.wave_data.findIndex(w => w.date === ann.date)
                                  if (idx < 0) return null
                                  const x = (idx / (item.wave_data.length - 1 || 1)) * 300
                                  const y = 50 - ((item.wave_data[idx].normalized - 45) / 55) * 40
                                  const color = ann.type === 'valley' ? '#34d399' : ann.type === 'peak' ? '#ef4444' : '#fbbf24'
                                  return <circle key={i} cx={x} cy={y} r="4" fill={color} stroke="#13141f" strokeWidth="1.5" />
                                })}
                              </svg>
                              {/* 量价信号标注 */}
                              {item.volume_signal && (
                                <span className="cw-clabel" style={{ left: '50%', top: '-2px' }}>
                                  {VOLUME_LABELS[item.volume_signal]}
                                </span>
                              )}
                              {item.entry_window && (
                                <span className="cw-clabel" style={{ left: '48%', top: '35px', color: '#34d399', fontSize: 10, fontWeight: 600 }}>
                                  ↓切入窗口
                                </span>
                              )}
                            </div>

                            <div className="cw-badge" style={{ color: meta.color }}>
                              {meta.icon} {item.stage}
                            </div>
                            <div className={`cw-expand ${expanded[item.code] ? 'open' : ''}`}>▶</div>
                          </div>

                          {/* 展开详情 */}
                          <div className={`cw-detail ${expanded[item.code] ? 'show' : ''}`}>
                            <div className="cw-dline1">
                              <span className="cw-dl">近5日 <span className={`cw-dv ${item.change_5d >= 0 ? 'g' : 'r'}`}>{fmtPct(item.change_5d)}</span></span>
                              <span className="cw-dl">BIAS20 <span className="cw-dv r">{fmtPct(item.bias20)}</span></span>
                              <span className="cw-dl">vs大盘 <span className={`cw-ds ${item.vs_market_5d >= 0 ? '' : 'wk'}`}>{fmtPct(item.vs_market_5d)}</span></span>
                              <span className="cw-sep">|</span>
                              <span className="cw-dl">历史谷→峰 <span style={{ color: '#e8e9f0', fontWeight: 600 }}>{item.historical_gain ? `+${item.historical_gain}%` : '--'}</span></span>
                            </div>
                            <div className="cw-dline2">
                              <span className="cw-dl">关联自选:</span>
                              {item.related_stocks.map((stk, i) => (
                                <span key={i}>
                                  <span className="cw-dstk">{stk}</span>
                                  {i < item.related_stocks.length - 1 && <span className="cw-sep">/</span>}
                                </span>
                              ))}
                              {item.related_count > 3 && (
                                <span className="cw-dmore">+{item.related_count - 3}更多 ›</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                })}
              </div>

              {/* 波谷告警 */}
              {data.alerts.length > 0 && (
                <div className="cw-section-title">⚠️ 波谷告警（{data.alerts.length}条）</div>
              )}
              {data.alerts.map((alert, i) => (
                <div key={i} className="cw-alert">
                  <div className="cw-alert-icon">⚠️</div>
                  <div className="cw-alert-body">
                    <strong>{alert.name}</strong> <span className="cw-alert-hl">vl_score={alert.vl_score}</span> {alert.reason}
                  </div>
                </div>
              ))}

              {/* 新概念扫描 */}
              {data.new_hot.length > 0 && (
                <div className="cw-section-title">🔍 新概念扫描（本周新发现）</div>
              )}
              {data.new_hot.map((hot, i) => (
                <div key={i} className="cw-scan-card">
                  <span className="cw-scan-name">💡 {hot.name}</span>
                  <span className="cw-scan-stat">+{hot.gain_20d}%</span>
                  <span className="cw-scan-label">20日涨幅 · {hot.stock_count}只成分股</span>
                  <span className="cw-scan-add">+ 添加追踪</span>
                </div>
              ))}

              {/* 更新时间 */}
              <div style={{ fontSize: 10, color: '#444', textAlign: 'right', marginTop: 6 }}>
                {data.data_timestamp?.slice(0, 16) || data.date || ''}
              </div>
            </>
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  )
}

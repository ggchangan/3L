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
  related_stocks: string[]
  related_count: number
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
}

interface WaveStats {
  total: number
  valley: number
  mid: number
  declining: number
  alerts_count: number
  new_this_week: number
}

interface WaveData {
  success: boolean
  date: string
  data_timestamp: string
  stats: WaveStats
  grouped: {
    valley: ConceptItem[]
    mid: ConceptItem[]
    declining: ConceptItem[]
  }
  alerts: AlertItem[]
  new_hot: NewHotItem[]
}

const STAGE_META: Record<string, { label: string; color: string; bg: string; tag: string }> = {
  '波谷': { label: '重点关注 · 波谷阶段', color: '#34d399', bg: '#0b2e1a', tag: 'tag-green' },
  '波中': { label: '正常观察 · 波中阶段', color: '#fbbf24', bg: '#2a2000', tag: 'tag-yellow' },
  '下跌': { label: '警惕观望 · 下跌/波峰阶段', color: '#ef4444', bg: '#2a0b0b', tag: 'tag-red' },
}

function fmtPct(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function ConceptWaveTracking() {
  const [data, setData] = useState<WaveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [collapsed, setCollapsed] = useState(true) // 折叠低分项

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

  // 所有可视化的概念（折叠/展开控制）
  function visibleItems(group: ConceptItem[]): ConceptItem[] {
    if (!group) return []
    if (!collapsed) return group
    // 折叠时只显示前5个非波谷组或者其他组的全部
    return group
  }

  return (
    <div className="page-wrap">
      <NavBar />
      <div className="content" style={{ maxWidth: 900, margin: '0 auto' }}>
        {/* ══════════ 标题栏 ══════════ */}
        <div className="cw-title-bar">
          <h1 className="cw-title">📊 概念板块波谷追踪</h1>
          <div className="cw-title-actions">
            <div className="cw-date-range">
              📅 <span className="cw-date-val">{daysAgo(30)}</span> ~ <span className="cw-date-val">{todayStr()}</span>
            </div>
            <div className="cw-btn-sort">按阶段排序 ▼</div>
          </div>
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
            {/* ══════════ 4个统计卡片 ══════════ */}
            <div className="cw-stats-row">
              <div className="cw-stat-card">
                <div className="cw-stat-value">{s.valley}</div>
                <div className="cw-stat-label">当前波谷信号</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value" style={{ color: '#fbbf24' }}>{s.alerts_count}</div>
                <div className="cw-stat-label">强信号告警</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value">{s.total}</div>
                <div className="cw-stat-label">追踪概念总数</div>
              </div>
              <div className="cw-stat-card">
                <div className="cw-stat-value" style={{ color: '#34d399' }}>
                  {s.new_this_week > 0 ? `↑${s.new_this_week}%` : '--'}
                </div>
                <div className="cw-stat-label">上周新发现机会</div>
              </div>
            </div>

            {/* ══════════ 堆叠走势区域 ══════════ */}
            <div className="cw-chart-area">
              {(['valley', 'mid', 'declining'] as const).map(group => {
                const items = data.grouped[group]
                if (!items || items.length === 0) return null
                const meta = STAGE_META[items[0].stage] || { label: '', color: '#888', bg: '#1a1b2e', tag: '' }

                return (
                  <div key={group}>
                    {/* 组标题 */}
                    <div className="cw-group-header">
                      <span className="cw-tag" style={{ borderColor: meta.color, color: meta.color, background: meta.bg }}>
                        {items[0].stage === '波谷' ? '🟢' : items[0].stage === '波中' ? '🟡' : '🔴'} {items[0].stage}组
                      </span>
                      <span className="cw-gc">{meta.label} · {items.length}个概念</span>
                    </div>

                    {items.map(item => {
                      const chartId = `${group}-${item.code}`
                      const isExpanded = expanded[chartId]
                      const hasAnnotations = item.annotations && item.annotations.length > 0

                      return (
                        <div key={chartId} className={`cw-card ${isExpanded ? 'expanded' : ''}`}>
                          <div className="cw-main" onClick={() => toggleExpand(chartId)}>
                            {/* 左侧信息 */}
                            <div className="cw-info">
                              {item.mainline_badge === 'gold' && <span className="cw-gold">[金]</span>}
                              {item.mainline_badge === 'silver' && <span className="cw-silver">[银]</span>}
                              <span className="cw-name">{item.name}</span>
                              <span className="cw-vl">vl:<span className="cw-hl">{item.vl_score}</span></span>
                            </div>

                            {/* 走势图 */}
                            <div className="cw-chart">
                              <svg viewBox="0 0 300 50" preserveAspectRatio="none">
                                {/* 大盘虚线 */}
                                {item.wave_data.length > 1 && (
                                  <polyline
                                    points={item.wave_data.map((w, i) =>
                                      `${(i / (item.wave_data.length - 1 || 1)) * 300},${50 - ((w.normalized - 45) / 55) * 40}`
                                    ).join(' ')}
                                    fill="none" stroke="#3a3b50" strokeWidth="1" strokeDasharray="3,3"
                                  />
                                )}
                                {/* 走势线 */}
                                {item.wave_data.length > 1 && (
                                  <polyline
                                    points={item.wave_data.map((w, i) =>
                                      `${(i / (item.wave_data.length - 1 || 1)) * 300},${50 - ((w.normalized - 45) / 55) * 40}`
                                    ).join(' ')}
                                    fill="none" stroke={meta.color} strokeWidth="2"
                                  />
                                )}
                                {/* 标注点 */}
                                {hasAnnotations && item.annotations.map((ann, i) => {
                                  const idx = item.wave_data.findIndex(w => w.date === ann.date)
                                  if (idx < 0) return null
                                  const x = (idx / (item.wave_data.length - 1 || 1)) * 300
                                  const y = 50 - ((item.wave_data[idx].normalized - 45) / 55) * 40
                                  const ac = ann.type === 'valley' ? '#34d399' : ann.type === 'peak' ? '#ef4444' : '#fbbf24'
                                  return <circle key={i} cx={x} cy={y} r="4" fill={ac} stroke="#13141f" strokeWidth="1.5" />
                                })}
                                {/* 今日竖线 */}
                                <line x1="73%" y1="0" x2="73%" y2="100%" stroke="#ef4444" strokeWidth="1" strokeDasharray="2,2" opacity="0.6" />
                              </svg>
                              {/* 今日标签 */}
                              <span className="cw-today-label">今天</span>
                              {/* 量价信号 */}
                              {item.volume_signal === 'shrink' && (
                                <span className="cw-clabel" style={{ left: '50%', top: '-2px' }}>
                                  💧 <span className="cw-csub">缩量</span>
                                </span>
                              )}
                              {item.volume_signal === 'surge' && (
                                <span className="cw-clabel" style={{ left: '50%', top: '-2px' }}>
                                  🔥 <span className="cw-csub">放量</span>
                                </span>
                              )}
                              {item.entry_window && (
                                <span className="cw-clabel" style={{ left: '48%', top: '35px', color: '#34d399', fontSize: 10, fontWeight: 600 }}>
                                  ↓切入窗口
                                </span>
                              )}
                            </div>

                            {/* 阶段标签 */}
                            <div className="cw-badge" style={{ color: meta.color }}>
                              {item.stage === '波谷' ? '🟢' : item.stage === '波中' ? '🟡' : '🔴'} {item.stage}
                            </div>

                            {/* 展开按钮 */}
                            <div className={`cw-expand ${isExpanded ? 'open' : ''}`}>▶</div>
                          </div>

                          {/* 展开详情 */}
                          <div className={`cw-detail ${isExpanded ? 'show' : ''}`}>
                            <div className="cw-dline1">
                              <span className="cw-dl">近5日 <span className={`cw-dv ${item.change_5d >= 0 ? 'g' : 'r'}`}>{fmtPct(item.change_5d)}</span></span>
                              <span className="cw-dl">BIAS20 <span className="cw-dv r">{fmtPct(item.bias20)}</span></span>
                              <span className="cw-dl">vs大盘 <span className={`cw-ds ${item.vs_market_5d >= 0 ? '' : 'wk'}`}>{fmtPct(item.vs_market_5d)}</span></span>
                              <span className="cw-sep">|</span>
                              <span className="cw-dl">自选关联 <span style={{ color: '#e8e9f0', fontWeight: 600 }}>{item.related_count}只</span></span>
                            </div>
                            <div className="cw-dline2">
                              <span className="cw-dl">关联自选:</span>
                              {item.related_stocks.map((stk, i) => (
                                <span key={i}>
                                  <span className="cw-dstk">{stk}</span>
                                  {i < item.related_stocks.length - 1 && <span className="cw-sep">/</span>}
                                </span>
                              ))}
                              {item.related_count > 3 && item.related_stocks.length < item.related_count && (
                                <span className="cw-dmore">+{item.related_count - item.related_stocks.length}更多 ›</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>

            {/* 时间轴 */}
            <div className="cw-axis-row">
              <span>← 30天前</span>
              <span className="cw-axis-today">今天</span>
              <span>当前位 →</span>
            </div>

            {/* 波谷告警 */}
            <div className="cw-section-title">
              ⚠️ 波谷告警（{data.alerts.length}条）
              <span className="cw-sc">· 强信号推荐关注</span>
            </div>
            {data.alerts.length === 0 && (
              <div className="empty" style={{ fontSize: 12, padding: '8px 0' }}>暂无告警</div>
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
              <>
                <div className="cw-section-title">
                  🔍 新概念扫描 <span className="cw-sc">· 本周新发现</span>
                </div>
                {data.new_hot.map((hot, i) => (
                  <div key={i} className="cw-scan-card">
                    <span className="cw-scan-name">💡 {hot.name}</span>
                    <span className="cw-scan-stat">+{hot.gain_20d}%</span>
                    <span className="cw-scan-label">20日涨幅 · {hot.stock_count}只成分股</span>
                    <span className="cw-scan-add">+ 添加追踪</span>
                  </div>
                ))}
              </>
            )}

            {/* 图例 */}
            <div className="cw-legend">
              <span><span className="cw-gold">[金]</span>主线前5</span>
              <span><span className="cw-silver">[银]</span>主线6-10</span>
              <span><span style={{ color: '#555' }}>— —</span> 大盘水位线</span>
              <span>💧 缩量</span>
              <span>🔥 放量</span>
              <span>⚠️ 天量滞涨</span>
              <span style={{ color: '#34d399' }}>↓切入窗口</span>
            </div>

            {/* 更新时间 */}
            <div style={{ fontSize: 10, color: '#444', textAlign: 'right', marginTop: 8 }}>
              {data.data_timestamp?.slice(0, 16) || data.date || ''}
            </div>
          </>
        )}
      </div>
      <BottomNav />
    </div>
  )
}

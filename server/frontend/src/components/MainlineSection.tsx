import { useState, useEffect } from 'react'
import { fetchReviewByDate } from '../lib/api'
import type { LineItem } from '../lib/types'

interface MainlineData {
  model_type?: string
  model_label?: string
  is_l1_model?: boolean
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
  l1_shadow?: L1ShadowData
  type?: string
  concept_mainline?: MainlineData
}

interface L1ShadowData {
  model_type?: string
  experimental?: boolean
  as_of_date?: string
  data_status?: 'experimental' | 'partial' | 'error'
  calibration_status?: string
  source?: string
  input_coverage?: Record<string, number | string | null | undefined>
  quality_gates?: Record<string, boolean | null | undefined>
  rankings?: L1Ranking[]
  error?: string
  error_type?: string
}

interface L1Ranking {
  name: string
  momentum_stock_count?: number
  constituent_count?: number
  coverage?: number
  momentum_score?: number
  status?: string
  score_status?: string
  rotation_state?: string
  consecutive_days?: number
  new_high_count?: number | null
  new_high_overlap?: number | null
  top_stocks?: string[]
}

interface Props {
  data: MainlineData | null | undefined
  dates: string[]
  currentDate: string
  previousTradingDate?: string
  watchedSectors?: {
    industries?: Array<Partial<LineItem> & { name: string; matched?: boolean }>
    concepts?: Array<Partial<LineItem> & { name: string; matched?: boolean }>
  }
}

const TAB_STYLE_BASE = { padding: '6px 16px', fontSize: 13, borderRadius: '6px 6px 0 0', cursor: 'pointer', border: 'none', fontWeight: 600 } as const

type TabKey = 'industry' | 'concept' | 'watched-industry' | 'watched-concept'

const TABS: { key: TabKey; label: string; color: string; activeColor: string }[] = [
  { key: 'industry', label: '🏭 行业强度候选', color: '#e94560', activeColor: '#e94560' },
  { key: 'concept', label: '💡 概念强度候选', color: '#4ecdc4', activeColor: '#4ecdc4' },
  { key: 'watched-industry', label: '⭐ 关注行业', color: '#ffd700', activeColor: '#ffd700' },
  { key: 'watched-concept', label: '🔖 关注概念', color: '#ffb84d', activeColor: '#ffb84d' },
]

// 当前数据只是板块自身20日涨幅代理榜，不等同于 L1 动量主线。
const DIRECTION_GROUPS = [
  { key: 'mainline', label: '20日强度前5候选', emoji: '🔥', color: '#e94560', bg: 'rgba(233,69,96,0.10)' },
  { key: 'secondary', label: '20日强度6–10候选', emoji: '⚡', color: '#ffd700', bg: 'rgba(255,215,0,0.08)' },
  { key: 'other', label: '20日强度榜外', emoji: '📊', color: '#888', bg: 'rgba(136,136,136,0.05)' },
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

const pct = (v?: number | string | null) => {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${(n * 100).toFixed(1)}%`
}

const L1_STATUS_LABEL: Record<string, string> = {
  confirmed: '主线线索',
  climax_warning: '高潮预警',
  not_confirmed: '未确认',
  insufficient_data: '数据不足',
}

const L1_GATE_LABELS: Record<string, string> = {
  market_universe_ready: '全市场',
  kline_ready: '20日行情',
  listing_date_ready: '上市日期',
  target_date_ready: '目标日',
  industry_mapping_ready: '行业映射',
  constituent_as_of_ready: '历史成分',
  institution_holdings_ready: '机构持仓',
  institution_as_of_ready: '机构日期',
  new_high_validation_ready: '52周新高',
}

function L1ShadowPanel({ shadow }: { shadow?: L1ShadowData }) {
  if (!shadow) return null
  const rankings = (shadow.rankings || []).slice(0, 5)
  const gates = shadow.quality_gates || {}
  const gateEntries = Object.entries(L1_GATE_LABELS).filter(([key]) => key in gates)
  const blocked = gateEntries.filter(([key]) => gates[key] === false).map(([, label]) => label)
  const isPartial = shadow.data_status === 'partial'
  const isError = shadow.data_status === 'error'

  return (
    <div style={{
      marginBottom: 12,
      border: '1px solid rgba(78,205,196,0.22)',
      background: 'rgba(78,205,196,0.06)',
      borderRadius: 8,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 10px',
        display: 'flex',
        justifyContent: 'space-between',
        gap: 10,
        flexWrap: 'wrap',
        borderBottom: '1px solid rgba(78,205,196,0.14)',
      }}>
        <div>
          <span style={{ color: '#4ecdc4', fontWeight: 700, fontSize: 13 }}>L1 动量主线影子模型</span>
          <span style={{ color: '#888', fontSize: 11, marginLeft: 8 }}>
            全市场20日强势个股 → THS行业聚合
          </span>
        </div>
        <span style={{
          color: isError ? '#e94560' : isPartial ? '#ffd166' : '#4ecdc4',
          fontSize: 11,
          fontWeight: 700,
        }}>
          {isError ? '计算失败' : isPartial ? '数据门禁未过' : '实验运行'}
        </span>
      </div>

      <div style={{ padding: '8px 10px' }}>
        {isError ? (
          <div style={{ color: '#e94560', fontSize: 12 }}>{shadow.error || 'L1影子模型暂不可用'}</div>
        ) : (
          <>
            <div style={{ color: '#9ca3af', fontSize: 11, lineHeight: 1.6, marginBottom: 8 }}>
              {isPartial
                ? `当前只展示分值线索，不作为正式主线结论；未过门禁：${blocked.length ? blocked.join('、') : '待校准'}。`
                : '输入门禁已过，但THS口径阈值仍待历史校准，暂不替换20日强度候选。'}
              <span style={{ marginLeft: 8 }}>
                全市场覆盖 {pct(shadow.input_coverage?.market_universe)} · 20日行情 {pct(shadow.input_coverage?.kline_20d)} · 52周新高 {pct(shadow.input_coverage?.new_high_52w)}
              </span>
            </div>

            {rankings.length ? (
              <div style={{ display: 'grid', gap: 6, overflowX: 'auto' }}>
                {rankings.map((item, idx) => {
                  const rawStatus = item.score_status || item.status || ''
                  const statusLabel = L1_STATUS_LABEL[rawStatus] || rawStatus || '--'
                  const statusColor = rawStatus === 'climax_warning' ? '#e94560' : rawStatus === 'confirmed' ? '#4ecdc4' : '#888'
                  return (
                    <div key={item.name} style={{
                      display: 'grid',
                      gridTemplateColumns: '32px minmax(90px, 1fr) repeat(4, minmax(62px, auto))',
                      gap: 8,
                      alignItems: 'center',
                      padding: '6px 8px',
                      borderRadius: 6,
                      background: 'rgba(255,255,255,0.035)',
                      fontSize: 11,
                    }}>
                      <span style={{ color: '#888' }}>#{idx + 1}</span>
                      <span style={{ color: '#ddd', fontWeight: 700 }}>{item.name}</span>
                      <span style={{ color: '#9ca3af' }}>动量股 {item.momentum_stock_count ?? 0}/{item.constituent_count ?? '--'}</span>
                      <span style={{ color: '#9ca3af' }}>覆盖 {pct(item.coverage)}</span>
                      <span style={{ color: '#ffd166' }}>分值 {item.momentum_score?.toFixed?.(2) ?? '--'}</span>
                      <span style={{ color: statusColor, fontWeight: 700 }}>{statusLabel}</span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ color: '#666', fontSize: 12 }}>暂无可展示的L1影子线索</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function MainlineSection({ data, dates, currentDate, previousTradingDate, watchedSectors }: Props) {
  const [prevRanked, setPrevRanked] = useState<string[] | null>(null)
  const [comparisonDate, setComparisonDate] = useState('')
  const [comparisonStatus, setComparisonStatus] = useState<'idle' | 'loading' | 'ready' | 'unavailable' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('industry')
  const [expandedLeader, setExpandedLeader] = useState<string | null>(null)
  // 自选股代码集合（领涨股复选框用）：加载一次，toggle 后本地同步
  const [watchCodes, setWatchCodes] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch('/api/watchlist')
      .then(r => r.json())
      .then(wl => {
        const stocks = Array.isArray(wl) ? wl : (wl?.stocks || [])
        setWatchCodes(new Set(stocks.filter((s: any) => s?.code).map((s: any) => s.code)))
      })
      .catch(() => { /* 加载失败保持空集合，不阻断页面 */ })
  }, [])

  // 轻提示（非弹窗）：操作结果反馈
  function showToast(msg: string, isError?: boolean) {
    const el = document.createElement('div')
    el.textContent = msg
    el.style.cssText = `position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid ${isError ? '#e94560' : '#22c55e'};color:${isError ? '#e94560' : '#22c55e'};padding:8px 20px;border-radius:6px;font-size:13px;z-index:999;transition:opacity .3s`
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2000)
  }

  // 复盘页复选框只做"添加"：勾选=加自选；已勾选的点击无效（移除自选只在自选页面操作）
  const toggleWatch = (code: string, name: string) => {
    if (watchCodes.has(code)) {
      showToast(`「${name}」已在自选中，删除请到自选页面`, true)
      return  // 已在自选：不执行移除，复选框保持勾选
    }
    fetch('/api/watchlist/add-stock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, name }),
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          // 静默更新本地状态
          setWatchCodes(prev => {
            const next = new Set(prev)
            next.add(code)
            return next
          })
          showToast(`已加入自选：${name}`)
        } else {
          showToast(res.error || '添加失败', true)
        }
      })
      .catch(() => showToast('网络错误，添加失败', true))
  }

  const isWatchedTab = tab === 'watched-industry' || tab === 'watched-concept'

  // 选择当前 tab 的数据来源
  const activeData: MainlineData | null | undefined = tab === 'concept'
    ? data?.concept_mainline
    : data

  // 关注 tab：直接使用后端按用户匹配好的数据
  const watchedItems: Array<Partial<LineItem> & { name: string; matched?: boolean }> = tab === 'watched-industry'
    ? watchedSectors?.industries || []
    : tab === 'watched-concept'
      ? watchedSectors?.concepts || []
      : []

  const allRanked = activeData?.all_ranked || []
  const persist = activeData?.persistence || []
  const mainNames = new Set((activeData?.lines || []).map(l => l.name))
  const secNames = new Set((activeData?.secondary || []).map(l => l.name))

  const persistDays: Record<string, number> = {}
  persist.forEach((p: any) => { persistDays[p.name] = p.days })

  // 获取前一天的排名（关注 Tab 不展示轮动比较，跳过请求）
  useEffect(() => {
    setPrevRanked(null)
    setComparisonDate('')
    if (tab === 'watched-industry' || tab === 'watched-concept') {
      setComparisonStatus('idle')
      return
    }
    if (!data || !currentDate) {
      setComparisonStatus('idle')
      return
    }
    const prevDate = previousTradingDate || ''
    if (!prevDate || !dates.includes(prevDate)) {
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
  }, [data, dates, currentDate, previousTradingDate, tab])

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

  if (!data) return <div className="empty">暂无板块强度数据</div>

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
      <div style={{ display: 'flex', gap: 0, marginBottom: 12, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              ...TAB_STYLE_BASE,
              background: tab === t.key ? '#1a1a2e' : '#2a2a3e',
              color: tab === t.key ? t.activeColor : '#888',
            }}
          >{t.label}</button>
        ))}
      </div>

      <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#9ca3af', background: 'rgba(255,255,255,0.04)', lineHeight: 1.6 }}>
        {isWatchedTab
          ? '以下为你重点关注的同花顺板块/概念，强度数据与候选榜同源；主线暂无数据的显示「暂无数据」。'
          : '当前模型仅按板块自身20日涨幅排序；前5和第6–10名是强度候选，不是知识库定义的 L1 动量主线。'}
      </div>

      {!isWatchedTab && activeData?.ranking_status === 'estimated' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#ffd166', background: 'rgba(255,209,102,0.1)' }}>
          当日预估 · 收盘快照覆盖 {((activeData.estimate_coverage || 0) * 100).toFixed(1)}% · 次日 06:00 用正式板块日线校准
        </div>
      )}
      {!isWatchedTab && activeData?.ranking_status === 'stale' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#aaa', background: 'rgba(255,255,255,0.04)' }}>
          当日快照覆盖不足，暂沿用 {activeData.base_date || activeData.ranking_date || '上一交易日'} 已确认排名
        </div>
      )}
      {!isWatchedTab && activeData?.ranking_status === 'partial' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#ffd166', background: 'rgba(255,209,102,0.1)' }}>
          正式日线部分缺失 · 覆盖 {((activeData.coverage || 0) * 100).toFixed(1)}%
          {activeData.coverage_detail?.covered != null && activeData.coverage_detail?.expected != null
            ? `（${activeData.coverage_detail.covered}/${activeData.coverage_detail.expected}）`
            : ''}
          · 缺失概念不参与当日排名
        </div>
      )}
      {!isWatchedTab && activeData?.ranking_status === 'confirmed' && activeData.calibration?.status === 'completed' && (
        <div style={{ marginBottom: 10, padding: '7px 10px', borderRadius: 6, fontSize: 12, color: '#4ecdc4', background: 'rgba(78,205,196,0.08)' }}>
          已完成次日校准 · Top5 重合 {activeData.calibration.top5_overlap ?? 0}/5 · Top10 重合 {activeData.calibration.top10_overlap ?? 0}/10
        </div>
      )}

      {tab === 'industry' && <L1ShadowPanel shadow={data?.l1_shadow} />}

      {/* 轮动提醒 */}
      {!isWatchedTab && rotationNote && (
        <div style={{
          marginBottom: 10, minHeight: 20, fontSize: 12,
          color: rotationNote.includes('🆕') || rotationNote.includes('⚠️') ? '#4ecdc4' : rotationNote.includes('📉') ? '#e94560' : '#888',
          lineHeight: 1.6,
        }}>
          {rotationNote}
        </div>
      )}

      {/* 资金出逃 + 新方向 详细条 */}
      {!isWatchedTab && (escapeAlerts.length > 0 || newDirectionAlerts.length > 0) && (
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

      {!isWatchedTab && (
        <div style={{ marginBottom: 12, color: '#888', fontSize: 11, lineHeight: 1.6 }}>
          阅读顺序：先看20日板块强度候选，再看板块所处阶段。强度候选只提供方向线索；波谷是加分项，个股买点仍需独立判断。
        </div>
      )}

      {/* 关注 tab：渲染关注行业/概念列表 */}
      {isWatchedTab ? (
        watchedItems.length === 0 ? (
          <div className="empty">
            暂无关注{' '}
            <a href="/sector-focus" style={{ color: '#ffd700' }}>→ 前往「⭐ 关注板块」勾选</a>
          </div>
        ) : (
          <div style={{ background: 'rgba(255,215,0,0.05)', borderRadius: 8, padding: 6 }}>
            {watchedItems.map(item => {
              const c = item.chg_1d ?? 0
              const stage = item.stage || '--'
              const stageIcon = STAGE_ICONS[stage] || '•'
              const stageColor = STAGE_COLORS[stage] || '#888'
              const showLeaders = expandedLeader === item.name
              const leaders = item.leaders || []
              const rankLabel = item.strength_rank ? `强度#${item.strength_rank}` : ''
              return (
                <div key={item.name} style={{
                  display: 'flex', alignItems: 'center',
                  padding: '5px 10px', marginBottom: 3,
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: 6, fontSize: 12, flexWrap: 'wrap', gap: '2px 8px',
                }}>
                  <span style={{ fontWeight: 600, minWidth: 80 }}>{item.name}</span>
                  {item.matched === false ? (
                    <span style={{ color: '#555', fontSize: 11 }}>暂无数据</span>
                  ) : (
                    <>
                      <span style={{ color: chgColor(c), fontSize: 11 }}>
                        {item.matched !== true
                          ? (item.chg_1d == null ? '今日--' : `今日${c > 0 ? '+' : ''}${c.toFixed(2)}%`)
                          : (activeData?.ranking_status === 'estimated' && !item.estimate_applied
                            ? '今日--'
                            : item.chg_1d == null
                              ? '今日--'
                              : `今日${c > 0 ? '+' : ''}${c.toFixed(2)}%`)}
                      </span>
                      <span style={{ color: item.chg_20d != null ? (item.chg_20d >= 0 ? '#ff4444' : '#44aa44') : '#555', fontSize: 11 }}>
                        20日{item.chg_20d != null ? `${item.chg_20d > 0 ? '+' : ''}${item.chg_20d.toFixed(2)}%` : '--'}
                      </span>
                      {item.data_date && (() => {
                        const d = String(item.data_date).replace(/(\d{4})(\d{2})(\d{2})/, '$2-$3')
                        return (
                          <span style={{ color: '#888', fontSize: 10 }} title={`数据至 ${d}`}>📅至{d}</span>
                        )
                      })()}
                      <span style={{ color: stageColor, fontSize: 11 }}>
                        {stageIcon} {stage}
                      </span>
                      {item.vl_score && item.vl_score > 0 ? (
                        <span style={{ color: '#4ecdc4', fontSize: 10 }}>vl{item.vl_score}</span>
                      ) : null}
                      {persistDays[item.name] ? (
                        <span style={{ color: '#888', fontSize: 10 }}>{persistDays[item.name]}天</span>
                      ) : null}
                      {rankLabel && (
                        <span style={{ color: '#ffd700', fontSize: 10, fontWeight: 600 }}>{rankLabel}</span>
                      )}
                      {leaders.length > 0 && (
                        <span
                          onClick={() => setExpandedLeader(showLeaders ? null : item.name)}
                          style={{ cursor: 'pointer', color: '#888', fontSize: 10, marginLeft: 'auto' }}
                        >📈 {showLeaders ? '收起' : '领涨'}</span>
                      )}
                      {showLeaders && leaders.length > 0 && (
                        <div style={{ width: '100%', padding: '6px 0 2px 0', fontSize: 11 }}>
                          {leaders.map((ld: any) => {
                            const code = String(ld.code).split('.')[0]  // 归一化纯6位，兼容带后缀旧缓存数据
                            return (
                            <span key={code} style={{
                              display: 'inline-block', marginRight: 10, marginBottom: 3,
                              color: ld.chg_5d >= 5 ? '#ff6b6b' : ld.chg_5d > 0 ? '#44aa44' : '#888',
                            }}>
                              <span
                                onClick={(e) => { e.stopPropagation(); toggleWatch(code, ld.name) }}
                                style={{ cursor: 'pointer', marginRight: 2, display: 'inline-flex', alignItems: 'center' }}
                                title={watchCodes.has(code) ? '已在自选（删除请到自选页面）' : '加自选'}
                              >
                                <input
                                  type="checkbox"
                                  checked={watchCodes.has(code)}
                                  onChange={() => toggleWatch(code, ld.name)}
                                  onClick={(e) => e.stopPropagation()}
                                  style={{ margin: 0, cursor: 'pointer', accentColor: '#4ecdc4' }}
                                />
                              </span>
                              {ld.name}
                              <span style={{ color: '#555', fontSize: 10 }}>
                                {' '}{ld.chg_1d > 0 ? '+' : ''}{ld.chg_1d}% / 5d{ld.chg_5d > 0 ? '+' : ''}{ld.chg_5d}%
                              </span>
                              {ld.tag && <span style={{ fontSize: 10, marginLeft: 2 }}>{ld.tag}</span>}
                            </span>
                            )
                          })}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )
      ) : (
      /* 按方向层级展示，避免用板块阶段替代机会判断 */
      directionGroups.map(({ key, items, emoji, label, color, bg }) => {
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
                      : `今日${c > 0 ? '+' : ''}${c.toFixed(2)}%`}
                  </span>
                  <span style={{ color: item.chg_20d >= 0 ? '#ff4444' : '#44aa44', fontSize: 11 }}>
                    20日{item.chg_20d > 0 ? '+' : ''}{item.chg_20d.toFixed(2)}%
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
                    {key === 'mainline' ? '前5候选' : key === 'secondary' ? '6–10候选' : `强度#${allRanked.indexOf(item) + 1}`}
                  </span>
                  {leaders.length > 0 && (
                    <span
                      onClick={() => setExpandedLeader(showLeaders ? null : item.name)}
                      style={{ cursor: 'pointer', color: '#888', fontSize: 10, marginLeft: 'auto' }}
                    >📈 {showLeaders ? '收起' : '领涨'}</span>
                  )}
                  {showLeaders && leaders.length > 0 && (
                    <div style={{ width: '100%', padding: '6px 0 2px 0', fontSize: 11 }}>
                      {leaders.map((ld: any) => {
                        const code = String(ld.code).split('.')[0]  // 归一化纯6位，兼容带后缀旧缓存数据
                        return (
                        <span key={code} style={{
                          display: 'inline-block', marginRight: 10, marginBottom: 3,
                          color: ld.chg_5d >= 5 ? '#ff6b6b' : ld.chg_5d > 0 ? '#44aa44' : '#888',
                        }}>
                          <span
                            onClick={(e) => { e.stopPropagation(); toggleWatch(code, ld.name) }}
                            style={{ cursor: 'pointer', marginRight: 2, display: 'inline-flex', alignItems: 'center' }}
                            title={watchCodes.has(code) ? '已在自选（删除请到自选页面）' : '加自选'}
                          >
                            <input
                              type="checkbox"
                              checked={watchCodes.has(code)}
                              onChange={() => toggleWatch(code, ld.name)}
                              onClick={(e) => e.stopPropagation()}
                              style={{ margin: 0, cursor: 'pointer', accentColor: '#4ecdc4' }}
                            />
                          </span>
                          {ld.name}
                          <span style={{ color: '#555', fontSize: 10 }}>
                            {' '}{ld.chg_1d > 0 ? '+' : ''}{ld.chg_1d}% / 5d{ld.chg_5d > 0 ? '+' : ''}{ld.chg_5d}%
                          </span>
                          {ld.tag && <span style={{ fontSize: 10, marginLeft: 2 }}>{ld.tag}</span>}
                        </span>
                        )
                      })}
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
      })
      )
      }

      {/* 完整排名表格 — 折叠 */}
      {!isWatchedTab && (
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
              const level = mainNames.has(l.name) ? '前5候选' : secNames.has(l.name) ? '6–10候选' : '榜外'
              const levelColor = mainNames.has(l.name) ? '#e94560' : secNames.has(l.name) ? '#ffd700' : '#888'

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
                    {l.chg_20d >= 0 ? '+' : ''}{l.chg_20d.toFixed(2)}%
                  </td>
                  <td style={{ color: chgColor(l.chg_1d), fontSize: 12 }}>
                    {activeData?.ranking_status === 'estimated' && !l.estimate_applied
                      ? '--'
                      : `${chgSign(l.chg_1d)}${(l.chg_1d ?? 0).toFixed(2)}%`}
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
          板块自身20日涨幅排序 · 强度候选优先展示 · 板块阶段仅作环境提示
        </div>
      </details>
      )}
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

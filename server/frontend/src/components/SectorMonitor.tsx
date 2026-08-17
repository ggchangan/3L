import React, { useEffect, useState } from 'react'
import { fetchSectors } from '../lib/api'
import type { SectorData, SectorItem } from '../lib/types'

type TabType = 'industry_today' | 'industry_chg20d' | 'concept_today'

export default function SectorMonitor() {
  const [data, setData] = useState<SectorData | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'industry_today' | 'industry_chg20d' | 'concept_today'>('industry_today')
  const [chartVisible, setChartVisible] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const load = () => fetchSectors().then(d => {
      if (!active) return
      setData(d)
      setError('')
    }).catch(() => active && setError('板块数据刷新失败，当前显示上次结果'))
    load()
    const timer = setInterval(load, 10 * 60 * 1000)
    return () => { active = false; clearInterval(timer) }
  }, [])

  if (!data) return <div className="empty">{error || '加载中...'}</div>

  const isConcept = tab === 'concept_today'
  const isChg20d = tab === 'industry_chg20d'
  const activeItems = isConcept ? data.concept.today_top5
    : isChg20d ? data.industry.chg20d_top10
    : data.industry.today_top5

  const listEmpty = activeItems.length === 0

  if (listEmpty) return <div className="empty">暂无数据</div>

  return (
    <>
      {error && <div className="data-error">{error}</div>}
      <div role="tablist" style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid #2a2a4a', flexWrap: 'wrap' }}>
        <button type="button" role="tab" aria-selected={tab === 'industry_today'} onClick={() => setTab('industry_today')} className="monitor-tab" style={{
          padding: '6px 14px', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap',
          color: tab === 'industry_today' ? '#ffd700' : '#888',
          borderBottom: tab === 'industry_today' ? '2px solid #ffd700' : '2px solid transparent',
          fontWeight: tab === 'industry_today' ? 'bold' : 'normal',
        }}>🏭 行业·今日</button>
        <button type="button" role="tab" aria-selected={tab === 'industry_chg20d'} onClick={() => setTab('industry_chg20d')} className="monitor-tab" style={{
          padding: '6px 14px', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap',
          color: tab === 'industry_chg20d' ? '#ffd700' : '#888',
          borderBottom: tab === 'industry_chg20d' ? '2px solid #ffd700' : '2px solid transparent',
          fontWeight: tab === 'industry_chg20d' ? 'bold' : 'normal',
        }}>🏭 行业·10日</button>
        <button type="button" role="tab" aria-selected={tab === 'concept_today'} onClick={() => setTab('concept_today')} className="monitor-tab" style={{
          padding: '6px 14px', cursor: 'pointer', fontSize: 13, whiteSpace: 'nowrap',
          color: tab === 'concept_today' ? '#ffd700' : '#888',
          borderBottom: tab === 'concept_today' ? '2px solid #ffd700' : '2px solid transparent',
          fontWeight: tab === 'concept_today' ? 'bold' : 'normal',
        }}>📦 概念·今日</button>
      </div>

      {/* 行业板块：带结构/阶段 */}
      {!isConcept && (
        <table className="signal-table">
          <thead>
            <tr><th>#</th><th>板块</th><th>涨幅</th><th>结构</th><th>阶段</th><th style={{ width: 30 }}></th></tr>
          </thead>
          <tbody>
            {activeItems.map((b, i) => {
              const c = isChg20d ? (b.chg10d ?? b.chg20d ?? b.chg ?? 0) : (b.chg ?? b.chg10d ?? b.chg20d ?? 0)
              const chartId = `chart_${i}`
              return (
                <React.Fragment key={i}>
                  <tr>
                    <td style={{ color: '#555', width: 20 }}>{i + 1}</td>
                    <td style={{ fontWeight: 'bold' }}>{b.name || ''}</td>
                    <td style={{ color: Number(c) >= 0 ? '#ff4444' : '#44aa44' }}>{Number(c) >= 0 ? '+' : ''}{Number(c).toFixed(2)}%</td>
                    <td style={{ fontSize: 11, color: '#aaa' }}>{b.structure || '-'}</td>
                    <td style={{ fontSize: 11 }}>{b.phase || '-'}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button type="button" className="icon-button" aria-expanded={chartVisible === chartId}
                        onClick={() => setChartVisible(chartVisible === chartId ? null : chartId)} title="查看K线">📊</button>
                    </td>
                  </tr>
                  {chartVisible === chartId && (
                    <tr key={`c-${i}`}>
                      <td colSpan={6} style={{ padding: 0 }}>
                        <object data={`/api/sector-chart?name=${encodeURIComponent(b.name || '')}&t=${Date.now()}`}
                          type="image/svg+xml" style={{ width: '100%', height: 400, borderRadius: 6 }}></object>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      )}

      {/* 概念板块：纯排行，无结构/阶段 */}
      {isConcept && (
        <table className="signal-table">
          <thead>
            <tr><th>#</th><th>概念</th><th>涨幅</th></tr>
          </thead>
          <tbody>
            {activeItems.map((b, i) => {
              const c = b.chg ?? 0
              return (
                <tr key={i}>
                  <td style={{ color: '#555', width: 20 }}>{i + 1}</td>
                  <td style={{ fontWeight: 'bold' }}>{b.name || ''}</td>
                  <td style={{ color: Number(c) >= 0 ? '#ff4444' : '#44aa44' }}>{Number(c) >= 0 ? '+' : ''}{Number(c).toFixed(2)}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <div className="data-meta">
        接口返回 {data.meta?.updated_at || '—'} · {data.meta?.source || '—'}
        {data.meta?.concept_data_date ? ` · 概念数据日 ${data.meta.concept_data_date}` : ''}
        {data.meta?.concept_available === false ? ' · 概念数据不可用' : ''}
        {data.meta?.concept_stale ? '（非当日）' : ''}
      </div>
    </>
  )
}

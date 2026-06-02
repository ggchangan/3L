import React, { useEffect, useState } from 'react'
import { fetchSectors } from '../lib/api'
import type { SectorItem } from '../lib/types'

type TabType = 'industry_today' | 'industry_chg20d' | 'concept_today' | 'concept_chg20d'

export default function SectorMonitor() {
  const [data, setData] = useState<{
    industry: { today_top5: SectorItem[]; chg20d_top10: SectorItem[] }
    concept: { today_top5: SectorItem[]; chg20d_top10: SectorItem[] }
  } | null>(null)
  const [groupTab, setGroupTab] = useState<'industry' | 'concept'>('industry')
  const [timeTab, setTimeTab] = useState<'today' | 'chg20d'>('today')
  const [chartVisible, setChartVisible] = useState<string | null>(null)

  useEffect(() => {
    fetchSectors().then(d => {
      // 支持新版（industry/concept 嵌套）和旧版兼容
      if (d.industry && d.concept) {
        setData({
          industry: d.industry,
          concept: d.concept,
        })
      } else {
        // 旧版回退：直接把 d 当作 industry 数据
        setData({
          industry: {
            today_top5: d.today_top5 || [],
            chg20d_top10: d.chg20d_top10 || [],
          },
          concept: { today_top5: [], chg20d_top10: [] },
        })
      }
    })
  }, [])

  if (!data) return <div className="empty">加载中...</div>

  const group = groupTab === 'industry' ? data.industry : data.concept
  const activeItems = timeTab === 'today' ? group.today_top5 : group.chg20d_top10
  const listEmpty = group.today_top5.length === 0 && group.chg20d_top10.length === 0

  if (listEmpty) return <div className="empty">暂无数据</div>

  return (
    <>
      {/* 组切换（行业 vs 概念） */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 4, borderBottom: '1px solid #2a2a4a' }}>
        <div
          onClick={() => setGroupTab('industry')}
          style={{
            padding: '6px 18px', cursor: 'pointer', fontSize: 13,
            color: groupTab === 'industry' ? '#ffd700' : '#888',
            borderBottom: groupTab === 'industry' ? '2px solid #ffd700' : '2px solid transparent',
            fontWeight: groupTab === 'industry' ? 'bold' : 'normal',
          }}
        >🏭 行业板块</div>
        <div
          onClick={() => setGroupTab('concept')}
          style={{
            padding: '6px 18px', cursor: 'pointer', fontSize: 13,
            color: groupTab === 'concept' ? '#ffd700' : '#888',
            borderBottom: groupTab === 'concept' ? '2px solid #ffd700' : '2px solid transparent',
            fontWeight: groupTab === 'concept' ? 'bold' : 'normal',
          }}
        >📦 概念板块</div>
      </div>

      {/* 时间维度切换 */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid #2a2a4a' }}>
        <div
          onClick={() => setTimeTab('today')}
          style={{
            padding: '4px 14px', cursor: 'pointer', fontSize: 12,
            color: timeTab === 'today' ? '#ffd700' : '#888',
            borderBottom: timeTab === 'today' ? '2px solid #ffd700' : '2px solid transparent',
          }}
        >🔥 今日涨幅</div>
        <div
          onClick={() => setTimeTab('chg20d')}
          style={{
            padding: '4px 14px', cursor: 'pointer', fontSize: 12,
            color: timeTab === 'chg20d' ? '#ffd700' : '#888',
            borderBottom: timeTab === 'chg20d' ? '2px solid #ffd700' : '2px solid transparent',
          }}
        >📈 20日涨幅</div>
      </div>

      <table className="signal-table">
        <thead>
          <tr><th>#</th><th>板块</th><th>涨幅</th><th>结构</th><th>阶段</th><th style={{ width: 30 }}></th></tr>
        </thead>
        <tbody>
          {activeItems.map((b, i) => {
            const c = timeTab === 'chg20d' ? (b.chg20d ?? b.chg ?? 0) : (b.chg ?? b.chg20d ?? 0)
            const safeName = b.name
            const chartId = `${groupTab}_${timeTab}_chart_${i}`
            return (
              <React.Fragment key={`row-${i}`}>
                <tr>
                  <td style={{ color: '#555', width: 20 }}>{i + 1}</td>
                  <td style={{ fontWeight: 'bold' }}>{b.name || ''}</td>
                  <td style={{ color: Number(c) >= 0 ? '#ff4444' : '#44aa44' }}>{Number(c) >= 0 ? '+' : ''}{Number(c).toFixed(2)}%</td>
                  <td style={{ fontSize: 11, color: '#aaa' }}>{b.structure || '-'}</td>
                  <td style={{ fontSize: 11 }}>{b.phase || '-'}</td>
                  <td style={{ textAlign: 'right' }}>
                    <span
                      onClick={() => setChartVisible(chartVisible === chartId ? null : chartId)}
                      style={{ cursor: 'pointer', fontSize: 14, color: '#4ecdc4' }}
                      title="查看K线"
                    >📊</span>
                  </td>
                </tr>
                {chartVisible === chartId && (
                  <tr key={`chart-${i}`}>
                    <td colSpan={6} style={{ padding: 0 }}>
                      <object
                        data={`/api/sector-chart?name=${encodeURIComponent(safeName)}&type=${groupTab === 'concept' ? 'concept' : 'industry'}&t=${Date.now()}`}
                        type="image/svg+xml"
                        style={{ width: '100%', height: 400, borderRadius: 6 }}
                      ></object>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

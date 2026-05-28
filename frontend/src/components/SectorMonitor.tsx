import React, { useEffect, useState } from 'react'
import { fetchSectors } from '../lib/api'
import type { SectorItem } from '../lib/types'

export default function SectorMonitor() {
  const [data, setData] = useState<{ today: SectorItem[]; chg20d: SectorItem[] } | null>(null)
  const [tab, setTab] = useState<'today' | 'chg20d'>('today')
  const [chartVisible, setChartVisible] = useState<string | null>(null)

  useEffect(() => {
    fetchSectors().then(d => {
      setData({ today: d.today_top5 || [], chg20d: d.chg20d_top10 || [] })
    })
  }, [])

  if (!data) return <div className="empty">加载中...</div>
  if (data.today.length === 0 && data.chg20d.length === 0) return <div className="empty">暂无数据</div>

  const activeItems = tab === 'today' ? data.today : data.chg20d

  return (
    <>
      <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid #2a2a4a' }}>
        <div
          onClick={() => setTab('today')}
          style={{
            padding: '6px 18px', cursor: 'pointer', fontSize: 13,
            color: tab === 'today' ? '#ffd700' : '#888',
            borderBottom: tab === 'today' ? '2px solid #ffd700' : '2px solid transparent',
            fontWeight: tab === 'today' ? 'bold' : 'normal',
          }}
        >🔥 今日涨幅</div>
        <div
          onClick={() => setTab('chg20d')}
          style={{
            padding: '6px 18px', cursor: 'pointer', fontSize: 13,
            color: tab === 'chg20d' ? '#ffd700' : '#888',
            borderBottom: tab === 'chg20d' ? '2px solid #ffd700' : '2px solid transparent',
            fontWeight: tab === 'chg20d' ? 'bold' : 'normal',
          }}
        >📈 20日涨幅</div>
      </div>
      <table className="signal-table">
        <thead>
          <tr><th>#</th><th>板块</th><th>涨幅</th><th>结构</th><th>阶段</th><th style={{ width: 30 }}></th></tr>
        </thead>
        <tbody>
          {activeItems.map((b, i) => {
            const c = tab === 'chg20d' ? (b.chg20d ?? b.chg ?? 0) : (b.chg ?? b.chg20d ?? 0)
            const safeName = b.name
            const chartId = `${tab}_chart_${i}`
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
                        data={`/api/sector-chart?name=${encodeURIComponent(safeName)}&t=${Date.now()}`}
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

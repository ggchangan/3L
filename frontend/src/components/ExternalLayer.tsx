import { useEffect, useState } from 'react'
import { fetchExternalMapping } from '../lib/api'
import type { ExternalMappingData } from '../lib/types'

export default function ExternalLayer() {
  const [data, setData] = useState<ExternalMappingData | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [catCollapse, setCatCollapse] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetchExternalMapping().then(d => {
      setData(d)
      const cc: Record<string, boolean> = {}
      ;(d.categories || []).forEach((_, i) => { cc[`cat_${i}`] = false })
      setCatCollapse(cc)
    })
  }, [])

  return (
    <div className="layer external-layer">
      <div className="layer-title" onClick={() => setCollapsed(v => !v)} style={{ cursor: 'pointer' }}>
        <span className="badge-layer">②.5</span> 🌍 外围关联
        <span className="badge">{data?.updated || '加载中'}</span>
        <span className="collapse-indicator">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div id="externalBody">
          {!data ? (
            <div className="empty">正在加载美股映射数据…</div>
          ) : (
            <>
              <div style={{ fontSize: 9, color: '#555', marginBottom: 4 }}>实时行情待接入 · 涨跌幅为参考值</div>

              {/* 指数两列 */}
              <div className="ext-index-grid">
                <div className="ext-index-col">
                  <div className="ext-index-col-title">🌏 亚洲</div>
                  {(data.asia_indices || []).map((idx, i) => (
                    <div key={`asia-${i}`} className="idx-row">
                      <span className="idx-flag">{idx.flag || '🌏'}</span>
                      <span className="idx-name">{idx.name}</span>
                      <span className="idx-price">--</span>
                      <span className="idx-change" style={{ color: '#555' }}>--</span>
                      <span className="idx-arrow">--</span>
                      <span className="idx-status">—</span>
                    </div>
                  ))}
                </div>
                <div className="ext-index-col">
                  <div className="ext-index-col-title">🇺🇸 美股指数</div>
                  {(data.us_indices || []).map((idx, i) => (
                    <div key={`us-${i}`} className="idx-row">
                      <span className="idx-flag">🇺🇸</span>
                      <span className="idx-name">{idx.name}</span>
                      <span className="idx-price">--</span>
                      <span className="idx-change" style={{ color: '#555' }}>--</span>
                      <span className="idx-arrow">--</span>
                      <span className="idx-status">—</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 美股关注个股 */}
              <div className="ext-section">
                <div className="ext-section-title">📊 美股关注个股</div>
                {(data.categories || []).map((cat, ci) => {
                  const catId = `cat_${ci}`
                  const isCatClosed = catCollapse[catId]
                  return (
                    <div key={catId}>
                      <div
                        className="ext-cat-header"
                        onClick={() => setCatCollapse(prev => ({ ...prev, [catId]: !prev[catId] }))}
                      >
                        <span className="ext-cat-arrow">{isCatClosed ? '▶' : '▼'}</span>
                        {cat.name} <span style={{ color: '#555', fontSize: 9 }}>({(cat.stocks || []).length})</span>
                      </div>
                      {!isCatClosed && (
                        <div>
                          {(cat.stocks || []).map((s, si) => (
                            <div key={`s-${ci}-${si}`}>
                              <div className="ext-row">
                                <span className="ext-code">{s.code}</span>
                                <span className="ext-name">{s.name}</span>
                                <span className="ext-change" style={{ color: '#555' }}>--</span>
                                <span className="ext-arrow">--</span>
                                <span className="ext-impact">→ {s.impact ? s.impact.split('、')[0] : (s.sectors || '')}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {data.source_url && (
                <div className="ext-source">
                  📎 <a href={data.source_url} target="_blank" rel="noreferrer">{data.source || '原文'}</a>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

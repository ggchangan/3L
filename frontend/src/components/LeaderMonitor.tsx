import { useEffect, useState, useCallback } from 'react'
import { fetchIndustryLeaders, fetchMarketLeaders } from '../lib/api'
import type { LeaderItem, MarketLeaderItem } from '../lib/types'

type Tab = 'industry' | 'market'
type SortCol = 'industry' | 'chg' | 'mcap'

interface FlatLeader {
  industry: string
  name: string
  chg: number
  price: number | string
  mcap: number
}

const PAGE_SIZE = 10

export default function LeaderMonitor() {
  const [tab, setTab] = useState<Tab>('industry')
  const [industryLeaders, setIndustryLeaders] = useState<FlatLeader[]>([])
  const [marketLeaders, setMarketLeaders] = useState<MarketLeaderItem[]>([])
  const [marketMeta, setMarketMeta] = useState<{ scan_time?: string; total_industries?: number }>({})
  const [page, setPage] = useState(1)
  const [sortCol, setSortCol] = useState<SortCol>('chg')
  const [sortAsc, setSortAsc] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    if (tab === 'industry') {
      fetchIndustryLeaders().then(d => {
        const flat: FlatLeader[] = []
        Object.entries(d.by_industry || {}).forEach(([ind, items]) => {
          const top = items[0] || {}
          flat.push({
            industry: ind,
            name: top.name || '',
            chg: Number(top.chg) || 0,
            price: top.price || '',
            mcap: top.mcap ? Number(top.mcap) / 100000000 : 0,
          })
        })
        setIndustryLeaders(flat)
        setLoading(false)
      }).catch(() => setLoading(false))
    } else {
      fetchMarketLeaders().then(d => {
        setMarketLeaders(d.leaders || [])
        setMarketMeta({ scan_time: d.scan_time, total_industries: d.total_industries })
        setLoading(false)
      }).catch(() => setLoading(false))
    }
  }, [tab])

  const sorted = (() => {
    if (tab === 'market') return marketLeaders
    const items = [...industryLeaders]
    items.sort((a, b) => {
      if (sortCol === 'industry') return sortAsc ? a.industry.localeCompare(b.industry) : b.industry.localeCompare(a.industry)
      if (sortCol === 'chg') return sortAsc ? a.chg - b.chg : b.chg - a.chg
      if (sortCol === 'mcap') return sortAsc ? a.mcap - b.mcap : b.mcap - a.mcap
      return 0
    })
    return items
  })()

  const totalPages = tab === 'market' ? 1 : Math.ceil(sorted.length / PAGE_SIZE)
  const pageItems = tab === 'market'
    ? (sorted as MarketLeaderItem[])
    : (sorted as FlatLeader[]).slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const handleSort = useCallback((col: SortCol) => {
    if (sortCol === col) {
      setSortAsc(v => !v)
    } else {
      setSortCol(col)
      setSortAsc(true)
    }
  }, [sortCol])

  if (loading) return <div className="empty">加载中...</div>

  if (tab === 'industry' && sorted.length === 0) {
    return <div className="empty">暂无行业龙头数据</div>
  }

  return (
    <>
      <div className="block-title" style={{ marginBottom: 0, cursor: 'default' }}>
        🏆 龙头观测
        <span
          className={`tab-btn ${tab === 'industry' ? 'active' : ''}`}
          onClick={() => { setTab('industry'); setPage(1) }}
        >行业龙头</span>
        <span
          className={`tab-btn ${tab === 'market' ? 'active' : ''}`}
          onClick={() => { setTab('market'); setPage(1) }}
        >市场龙头</span>
      </div>

      {tab === 'market' && marketLeaders.length === 0 ? (
        <div className="empty">
          暂无符合条件的市场龙头<br />
          <span style={{ fontSize: 10, color: '#666' }}>条件：近5日行业涨幅第一 + 成交额第一 + MA10向上 + 换手率&gt;3%</span>
        </div>
      ) : tab === 'market' ? (
        <>
          <div style={{ fontSize: 11, color: '#888', marginBottom: 6 }}>
            扫描时间: {marketMeta.scan_time || '-'} | 共{marketMeta.total_industries || '-'}行业, 筛选出{marketLeaders.length}只龙头
          </div>
          <table className="leader-table">
            <thead>
              <tr><th>行业</th><th>股票</th><th>5日涨幅</th><th>今日涨跌</th><th>换手率</th><th>MA10方向</th><th>现价</th></tr>
            </thead>
            <tbody>
              {(pageItems as MarketLeaderItem[]).map((item, i) => (
                <tr key={i}>
                  <td style={{ color: '#aaa', fontSize: 10 }}>{item.industry}</td>
                  <td><b>{item.name}</b></td>
                  <td className={item.gain_5d >= 0 ? 'up' : 'down'}>{item.gain_5d >= 0 ? '+' : ''}{item.gain_5d}%</td>
                  <td className={item.change_pct >= 0 ? 'up' : 'down'}>{item.change_pct >= 0 ? '+' : ''}{item.change_pct}%</td>
                  <td style={{ color: '#888' }}>{item.turnover_rate}%</td>
                  <td>{item.ma10_up ? '📈' : '📉'}</td>
                  <td style={{ color: '#ccc' }}>{item.price.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ textAlign: 'right', fontSize: 10, color: '#444', marginTop: 4 }}>每10分钟刷新 · 数据缓存至收盘</div>
        </>
      ) : (
        <>
          <table className="leader-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('industry')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  细分行业 {sortCol === 'industry' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th>龙头股</th>
                <th onClick={() => handleSort('chg')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  涨跌幅 {sortCol === 'chg' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th>现价</th>
                <th onClick={() => handleSort('mcap')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                  总市值 {sortCol === 'mcap' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {(pageItems as FlatLeader[]).map((item, i) => (
                <tr key={i}>
                  <td style={{ color: '#aaa' }}>{item.industry}</td>
                  <td><b>{item.name}</b></td>
                  <td className={item.chg >= 0 ? 'up' : 'down'}>{item.chg >= 0 ? '+' : ''}{item.chg}%</td>
                  <td>{item.price}</td>
                  <td style={{ color: '#888', fontSize: 10 }}>{item.mcap > 0 ? `${item.mcap.toFixed(1)}亿` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12 }}>
              <span
                onClick={() => setPage(p => Math.max(1, p - 1))}
                style={{ cursor: 'pointer', color: page > 1 ? '#4ecdc4' : '#333', margin: '0 8px' }}
              >◀</span>
              <span style={{ color: '#888' }}>第{page}/{totalPages}页</span>
              <span
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                style={{ cursor: 'pointer', color: page < totalPages ? '#4ecdc4' : '#333', margin: '0 8px' }}
              >▶</span>
            </div>
          )}
          <div style={{ textAlign: 'right', fontSize: 10, color: '#555', marginTop: 4 }}>
            共{industryLeaders.length}个细分行业 | 按{sortCol === 'industry' ? '行业名称' : sortCol === 'chg' ? '涨跌幅' : '总市值'}{sortAsc ? '升序' : '降序'}排列
          </div>
        </>
      )}
    </>
  )
}

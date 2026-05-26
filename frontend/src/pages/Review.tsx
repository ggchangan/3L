import { useEffect, useState } from 'react'
import { fetchReviewToday } from '../lib/api'
import NavBar, { BottomNav } from '../components/NavBar'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HoldingsReview from '../components/HoldingsReview'
import BuySignalsReview from '../components/BuySignalsReview'
import TradingPlan from '../components/TradingPlan'
import type { ReviewData } from '../lib/types'
import './Review.css'

const WDS = ['日', '一', '二', '三', '四', '五', '六']

/** 从 watchlist 读 trend_stock 标记，覆盖存档中的 trading_system */
function overlayTrendFromWatchlist(
  items: any[],
  wlByCode: Record<string, any>
): any[] {
  return items.map(item => {
    const code = (item.code || '').replace(/^sh|^sz|^SH|^SZ/, '')
    const wl = wlByCode[code]
    if (!wl) return item
    if (wl.trend_stock || wl.trading_system === 'trend') {
      return { ...item, trading_system: 'trend', trend_stock: true }
    }
    return item
  })
}

function indexBy<T extends { code?: string }>(items: T[]): Record<string, T> {
  const m: Record<string, T> = {}
  items.forEach(s => {
    const code = (s.code || '').replace(/^sh|^sz|^SH|^SZ/, '')
    m[code] = s
  })
  return m
}

export default function Review() {
  const [data, setData] = useState<ReviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const now = new Date()
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const weekday = now.getDay()

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      fetchReviewToday(),
      fetch('/api/watchlist').then(r => r.json()).catch(() => ({ stocks: [] })),
    ]).then(([reviewData, wl]) => {
      const wlByCode = indexBy(wl.stocks || [])
      const holdings = reviewData.holdings_review || reviewData.holdings || []
      const buySignals = reviewData.buy_signals_review || []
      setData({
        mainline: reviewData.mainline,
        trading_plan: reviewData.trading_plan,
        holdings_review: overlayTrendFromWatchlist(holdings, wlByCode),
        buy_signals_review: overlayTrendFromWatchlist(buySignals, wlByCode),
      })
      setLoading(false)
    }).catch(err => {
      setError(err.message || '加载复盘数据失败')
      setData({})
      setLoading(false)
    })
  }, [])

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>📋 3L 每日复盘</h1>
        <div className="sub">② 主线 · ③ 量价择时</div>
        <div className="date-badge" id="todayDate">
          {todayStr} 星期{WDS[weekday]}
        </div>
      </div>

      <div className="container">
        {loading ? (
          <div className="empty">正在实时计算复盘数据...</div>
        ) : error ? (
          <div className="empty" style={{ color: '#e94560' }}>{error}</div>
        ) : (
          <>
            {/* STEP 1: 大盘周期判定 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 1</span>
                大盘周期判定
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 决定总仓位水位(4维评分)</span>
              </div>
              <MarketCycle />
            </div>

            {/* STEP 2: 主线 */}
            {data?.mainline && (
              <div className="section">
                <div className="section-title">
                  <span className="step">STEP 2</span>
                  主线
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 主线/次级主线 排名</span>
                </div>
                <div id="mainlineContainer">
                  <MainlineSection data={data.mainline} dates={[]} currentDate={todayStr} />
                </div>
              </div>
            )}

            {/* STEP 3: 持仓个股复盘 */}
            {data?.holdings_review && data.holdings_review.length > 0 && (
              <div className="section">
                <div className="section-title">
                  <span className="step">STEP 3</span>
                  持仓个股复盘
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>
                    → 量价择时诊断
                  </span>
                </div>
                <div id="stockReviewList">
                  <HoldingsReview stocks={data.holdings_review as any} />
                </div>
              </div>
            )}

            {/* STEP 4: 自选股买点信号 */}
            {data?.buy_signals_review && data.buy_signals_review.length > 0 && (
              <div className="section">
                <div className="section-title">
                  <span className="step">STEP 4</span>
                  自选股买点信号
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 关注买入机会</span>
                </div>
                <div id="buySignalList">
                  <BuySignalsReview signals={data.buy_signals_review as any} />
                </div>
              </div>
            )}

            {/* PLAN: 每日交易计划 */}
            {data?.trading_plan && (
              <div className="section">
                <div className="section-title">
                  <span className="step">PLAN</span>
                  每日交易计划
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 综合STEP 1~4 生成</span>
                </div>
                <div id="tradingPlanArea">
                  <TradingPlan plan={data.trading_plan} />
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <BottomNav />
      <div className="footer">3L 交易体系 · 每日复盘 · 实时计算</div>
    </>
  )
}

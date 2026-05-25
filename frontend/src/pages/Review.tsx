import { useEffect, useState } from 'react'
import { fetchReviewDates, fetchReviewByDate, fetchMarket } from '../lib/api'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HoldingsReview from '../components/HoldingsReview'
import BuySignalsReview from '../components/BuySignalsReview'
import TradingPlan from '../components/TradingPlan'
import HistoryReview from '../components/HistoryReview'
import type { ReviewData } from '../lib/types'
import './Review.css'

const WDS = ['日', '一', '二', '三', '四', '五', '六']

export default function Review() {
  const [data, setData] = useState<ReviewData | null>(null)
  const [dates, setDates] = useState<string[]>([])
  const [currentDate, setCurrentDate] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const dateParam = params.get('date')

    fetchReviewDates().then(dd => {
      const allDates = (dd.dates || []).sort().reverse()
      setDates(allDates)

      let targetDate = dateParam || ''
      if (!targetDate && allDates.length > 0) {
        const now = new Date()
        const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
        targetDate = allDates[0]
        // 18:00前降级到上一个交易日
        if (targetDate === todayStr && now.getHours() < 18 && allDates.length > 1) {
          targetDate = allDates[1]
        }
      }

      if (targetDate) {
        setCurrentDate(targetDate)
        fetchReviewByDate(targetDate).then(d => {
          setData(d)
          setLoading(false)
        }).catch(() => {
          fetchMarketFallback()
        })
      } else {
        fetchMarketFallback()
      }
    }).catch(() => {
      fetchMarketFallback()
    })
  }, [])

  function fetchMarketFallback() {
    setCurrentDate('')
    fetchMarket().then(d => {
      setData({ market: d as ReviewData['market'] })
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  const isToday = currentDate === new Date().toISOString().slice(0, 10)
  const dateLabel = currentDate
    ? (isToday ? `${currentDate} 今日复盘 ✓` : `${currentDate} 每日复盘（收盘后自动更新）`)
    : '暂无复盘数据'

  const weekday = currentDate ? new Date(currentDate).getDay() : -1

  return (
    <>
      <div style={{ marginTop: 10 }} id="nav-top"></div>
      <div className="header">
        <h1>📋 3L 每日复盘</h1>
        <div className="sub">② 主线 · ③ 量价择时</div>
        <div className="date-badge" id="todayDate">
          {currentDate ? `${currentDate} 星期${WDS[weekday]}` : '加载中...'}
        </div>
      </div>

      <div className="container">
        {loading ? (
          <div className="empty">加载中...</div>
        ) : (
          <>
            {/* STEP 1: 大盘周期判定 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 1</span>
                大盘周期判定
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 决定总仓位水位(4维评分)</span>
              </div>
              <MarketCycle date={currentDate} />
            </div>

            {/* STEP 2: 主线 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 2</span>
                主线
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 主线/次级主线 排名</span>
              </div>
              <div id="mainlineContainer">
                <MainlineSection data={data?.mainline} dates={dates} currentDate={currentDate} />
              </div>
            </div>

            {/* STEP 3: 持仓个股复盘 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 3</span>
                持仓个股复盘
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 量价择时诊断</span>
              </div>
              <div id="stockReviewList">
                <HoldingsReview stocks={(data?.holdings_review || data?.holdings || []) as any} />
              </div>
            </div>

            {/* STEP 4: 自选股买点信号 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 4</span>
                自选股买点信号
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 关注买入机会</span>
              </div>
              <div id="buySignalList">
                <BuySignalsReview signals={(data?.buy_signals_review || []) as any} />
              </div>
            </div>

            {/* PLAN: 每日交易计划 */}
            <div className="section">
              <div className="section-title">
                <span className="step">PLAN</span>
                每日交易计划
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 综合STEP 1~4 生成</span>
              </div>
              <div id="tradingPlanArea">
                <TradingPlan plan={data?.trading_plan} />
              </div>
            </div>

            {/* 历史复盘 */}
            <div className="section-title">📅 历史复盘</div>
            <div className="section">
              <div id="historyReviewList">
                <HistoryReview dates={dates} currentDate={currentDate} />
              </div>
            </div>
          </>
        )}
      </div>

      <div id="nav-bottom"></div>
      <div className="footer">3L 交易体系 · 每日复盘 · 4步完整复盘</div>
    </>
  )
}

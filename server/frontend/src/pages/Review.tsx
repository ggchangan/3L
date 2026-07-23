import { useEffect, useState, useCallback } from 'react'
import { fetchReviewToday, fetchReviewStatus, refreshReview } from '../lib/api'
import type { ReviewRefreshStatus } from '../lib/api'
import NavBar, { BottomNav } from '../components/NavBar'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HoldingsReview from '../components/HoldingsReview'
import BuySignalsReview from '../components/BuySignalsReview'
import TradingPlan from '../components/TradingPlan'
import ReviewDataStatus from '../components/ReviewDataStatus'
import type { ReviewData } from '../lib/types'
import './Review.css'

const WDS = ['日', '一', '二', '三', '四', '五', '六']

export default function Review() {
  const [data, setData] = useState<ReviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshStatus, setRefreshStatus] = useState<ReviewRefreshStatus | null>(null)

  const now = new Date()
  const fallbackDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const reviewDate = data?.date || fallbackDate
  const [reviewYear, reviewMonth, reviewDay] = reviewDate.split('-').map(Number)
  const weekday = new Date(reviewYear, reviewMonth - 1, reviewDay, 12).getDay()

  const loadData = useCallback(() => {
    setLoading(true)
    setError('')
    fetchReviewToday().then(reviewData => {
      setData({
        ...reviewData,
        holdings_review: reviewData.holdings_review || [],
        buy_signals_review: reviewData.buy_signals_review || [],
      })
      setRefreshStatus(reviewData.refresh_status || null)
      setLoading(false)
    }).catch(err => {
      setError(err.message || '加载复盘数据失败')
      setData({})
      setLoading(false)
    })
  }, [])

  const handleRefresh = useCallback(() => {
    setError('')
    refreshReview()
      .then(setRefreshStatus)
      .catch(err => setError(err.message || '启动复盘更新失败'))
  }, [])

  useEffect(() => {
    loadData()
    // 页面切回来时自动重刷（其他页面修改趋势股/持仓后）
    const onFocus = () => { if (!loading) loadData() }
    const onVisible = () => { if (!document.hidden && !loading) loadData() }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [loadData])

  useEffect(() => {
    if (refreshStatus?.status !== 'running') return
    const timer = window.setInterval(() => {
      fetchReviewStatus().then(status => {
        setRefreshStatus(status)
        if (status.status === 'completed') loadData()
        if (status.status === 'failed') setError(status.error || '后台复盘更新失败')
      }).catch(() => {})
    }, 2000)
    return () => window.clearInterval(timer)
  }, [refreshStatus?.status, loadData])

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>📋 3L 每日复盘</h1>
        <div className="sub">① 大盘强弱 · ② 主线动量 · ③ 板块环境 · ④ 个股买点</div>
        <div className="date-badge" id="todayDate">
          复盘交易日 {reviewDate} 星期{WDS[weekday]}
        </div>
        <div className="review-cache-bar">
          <span>
            {refreshStatus?.status === 'running'
              ? '后台正在更新复盘…'
              : refreshStatus?.status === 'failed'
                ? '更新失败，当前展示上次结果'
                : data?.cache_generated_at
                  ? `数据生成于 ${data.cache_generated_at.replace('T', ' ')}`
                  : '当前展示最近一次复盘结果'}
          </span>
          <button type="button" onClick={handleRefresh} disabled={refreshStatus?.status === 'running'}>
            {refreshStatus?.status === 'running' ? '更新中' : '重新计算'}
          </button>
        </div>
        {data && (
          <ReviewDataStatus
            dataStatus={data.data_status}
          />
        )}
      </div>

      <div className="container">
        {loading ? (
          <div className="empty">正在读取复盘缓存...</div>
        ) : error ? (
          <div className="empty" style={{ color: '#e94560' }}>{error}</div>
        ) : (
          <>
            {/* STEP 1: 大盘强弱与周期位置 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 1</span>
                大盘强弱与周期位置
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 先定风险偏好和总仓位</span>
              </div>
              <MarketCycle
                reviewMarket={data?.market}
                reviewIndexDate={data?.data_status?.index?.date || data?.market?.data_date}
              />
            </div>

            {/* STEP 2 + 3: 主线动量与板块环境 */}
            {data?.mainline && (
              <div className="section">
                <div className="section-title">
                  <span className="step">STEP 2–3</span>
                  主线动量与板块环境
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 方向决定优先级，阶段只作加分和风险提示</span>
                </div>
                <div id="mainlineContainer">
                  <MainlineSection data={data.mainline} dates={[]} currentDate={reviewDate} />
                </div>
              </div>
            )}

            {/* STEP 4: 持仓个股复盘 */}
            {data?.holdings_review && data.holdings_review.length > 0 && (
              <div className="section">
                <div className="section-title">
                  <span className="step">STEP 4</span>
                  持仓个股复盘
                  <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>
                    → 量价择时诊断
                  </span>
                </div>
                <div id="stockReviewList">
                  <HoldingsReview stocks={data.holdings_review as any} directionOrder={data.direction_order} opportunityMap={data.opportunity_map} />
                </div>
              </div>
            )}

            {/* STEP 4: 自选股买点信号 — section始终显示 */}
            <div className="section">
              <div className="section-title">
                <span className="step">STEP 4</span>
                自选股买点信号
                <span style={{ fontSize: 12, color: '#666', fontWeight: 'normal' }}>→ 个股量价信号决定是否出现买点</span>
              </div>
              <div id="buySignalList">
                {data?.buy_signals_review && data.buy_signals_review.length > 0 ? (
                  <BuySignalsReview signals={data.buy_signals_review as any} directionOrder={data.direction_order} opportunityMap={data.opportunity_map} />
                ) : (
                  <div className="empty">暂无买点信号</div>
                )}
              </div>
            </div>

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
      <div className="footer">3L 交易体系 · 每日复盘 · 后台更新</div>
    </>
  )
}

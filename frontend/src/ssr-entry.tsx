import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense } from 'react'

// SSR：eager import 所有页面（lazy 在 SSR 下只会渲染 Suspense fallback）
import Monitor from './pages/Monitor'
import Review from './pages/Review'
import Workbench from './pages/Workbench'
import Watchlist from './pages/Watchlist'
import TrendCandidates from './pages/TrendCandidates'
import Holdings from './pages/Holdings'
import Industry from './pages/Industry'
import Macro from './pages/Macro'
import TopGainers from './pages/TopGainers'
import StockAnalysis from './pages/StockAnalysis'
import Tips from './pages/Tips'
import Simulation from './pages/Simulation'
import Skills from './pages/Skills'
import LogicTracking from './pages/LogicTracking'
import LogicTrackingDetail from './pages/LogicTrackingDetail'

export function render(url: string): string {
  // 处理子路径（如 /logic-tracking/xxx）
  const basePath = '/' + url.split('/').filter(Boolean)[0]
  return renderToString(
    <StaticRouter location={url}>
      <Suspense fallback={<div className="empty">加载中...</div>}>
        <Routes>
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/review" element={<Review />} />
          <Route path="/journal" element={<Workbench />} />
          <Route path="/workbench" element={<Workbench />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/trend_candidates" element={<TrendCandidates />} />
          <Route path="/holdings" element={<Holdings />} />
          <Route path="/industry" element={<Industry />} />
          <Route path="/macro" element={<Macro />} />
          <Route path="/top_gainers" element={<TopGainers />} />
          <Route path="/stock_analysis" element={<StockAnalysis />} />
          <Route path="/tips" element={<Tips />} />
          <Route path="/simulation" element={<Simulation />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/logic-tracking" element={<LogicTracking />} />
          <Route path="/logic-tracking/:tagId" element={<LogicTrackingDetail />} />
          <Route path="/" element={<Monitor />} />
          {/* SSR 不处理 LegacyRedirect（类型不匹配会抛）和 catch-all */}
        </Routes>
      </Suspense>
    </StaticRouter>
  )
}

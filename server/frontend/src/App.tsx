import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'

const Monitor = lazy(() => import('./pages/Monitor'))
const Review = lazy(() => import('./pages/Review'))
const Workbench = lazy(() => import('./pages/Workbench'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const TrendCandidates = lazy(() => import('./pages/TrendCandidates'))
const Holdings = lazy(() => import('./pages/Holdings'))
const Industry = lazy(() => import('./pages/Industry'))
const Macro = lazy(() => import('./pages/Macro'))
const TopGainers = lazy(() => import('./pages/TopGainers'))
const StockAnalysis = lazy(() => import('./pages/StockAnalysis'))
const Tips = lazy(() => import('./pages/Tips'))
const Simulation = lazy(() => import('./pages/Simulation'))
const Skills = lazy(() => import('./pages/Skills'))
const LogicTracking = lazy(() => import('./pages/LogicTracking'))
const LogicTrackingDetail = lazy(() => import('./pages/LogicTrackingDetail'))
const AlarmSounds = lazy(() => import('./pages/AlarmSounds'))
const PlanTracking = lazy(() => import('./pages/PlanTracking'))
const ConceptWaveTracking = lazy(() => import('./pages/ConceptWaveTracking'))
const StrongTrendCandidates = lazy(() => import('./pages/StrongTrendCandidates'))

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="empty">加载中...</div>}>
        <Routes>
        {/* 已迁移的 React 页面 */}
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
        <Route path="/alarm-sounds" element={<AlarmSounds />} />
        <Route path="/plan-tracking" element={<PlanTracking />} />
        <Route path="/concept-wave" element={<ConceptWaveTracking />} />
        <Route path="/strong-trend-candidates" element={<StrongTrendCandidates />} />
        <Route path="/" element={<Monitor />} />

        {/* 旧 HTML 重定向到 React 路由 */}
        <Route path="/holdings.html" element={<LegacyRedirect to="/holdings" />} />
        <Route path="/industry.html" element={<LegacyRedirect to="/industry" />} />
        <Route path="/macro.html" element={<LegacyRedirect to="/macro" />} />
        <Route path="/top_gainers.html" element={<LegacyRedirect to="/top_gainers" />} />
        <Route path="/stock_analysis.html" element={<LegacyRedirect to="/stock_analysis" />} />
        <Route path="/tips.html" element={<LegacyRedirect to="/tips" />} />
        <Route path="/simulation.html" element={<LegacyRedirect to="/simulation" />} />
        <Route path="/skills.html" element={<LegacyRedirect to="/skills" />} />

        {/* 未迁移的旧页面：通过 window.location 跳转 */}
        <Route path="/tip-detail" element={<LegacyRedirect to="/tip-detail.html" />} />
        <Route path="*" element={<Navigate to="/monitor" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

/** 跳转到旧版 HTML 页面 */
function LegacyRedirect({ to }: { to: string }) {
  if (typeof window !== 'undefined') {
    window.location.href = to
  }
  return null
}

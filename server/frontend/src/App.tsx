import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { isLoggedIn } from './lib/auth'

const Login = lazy(() => import('./pages/Login'))
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
const HotStocks = lazy(() => import('./pages/HotStocks'))
const SectorFocus = lazy(() => import('./pages/SectorFocus'))

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="empty">加载中...</div>}>
        <Routes>
        {/* 登录页（无需鉴权） */}
        <Route path="/login" element={<Login />} />

        {/* 已迁移的 React 页面（全部需要登录） */}
        <Route path="/monitor" element={<RequireAuth><Monitor /></RequireAuth>} />
        <Route path="/review" element={<RequireAuth><Review /></RequireAuth>} />
        <Route path="/journal" element={<RequireAuth><Workbench /></RequireAuth>} />
        <Route path="/workbench" element={<RequireAuth><Workbench /></RequireAuth>} />
        <Route path="/watchlist" element={<RequireAuth><Watchlist /></RequireAuth>} />
        <Route path="/trend_candidates" element={<RequireAuth><TrendCandidates /></RequireAuth>} />
        <Route path="/holdings" element={<RequireAuth><Holdings /></RequireAuth>} />
        <Route path="/industry" element={<RequireAuth><Industry /></RequireAuth>} />
        <Route path="/macro" element={<RequireAuth><Macro /></RequireAuth>} />
        <Route path="/top_gainers" element={<RequireAuth><TopGainers /></RequireAuth>} />
        <Route path="/stock_analysis" element={<RequireAuth><StockAnalysis /></RequireAuth>} />
        <Route path="/tips" element={<RequireAuth><Tips /></RequireAuth>} />
        <Route path="/simulation" element={<RequireAuth><Simulation /></RequireAuth>} />
        <Route path="/skills" element={<RequireAuth><Skills /></RequireAuth>} />
        <Route path="/logic-tracking" element={<RequireAuth><LogicTracking /></RequireAuth>} />
        <Route path="/logic-tracking/:tagId" element={<RequireAuth><LogicTrackingDetail /></RequireAuth>} />
        <Route path="/alarm-sounds" element={<RequireAuth><AlarmSounds /></RequireAuth>} />
        <Route path="/plan-tracking" element={<RequireAuth><PlanTracking /></RequireAuth>} />
        <Route path="/concept-wave" element={<RequireAuth><ConceptWaveTracking /></RequireAuth>} />
        <Route path="/strong-trend-candidates" element={<RequireAuth><StrongTrendCandidates /></RequireAuth>} />
        <Route path="/hot-stocks" element={<RequireAuth><HotStocks /></RequireAuth>} />
        <Route path="/sector-focus" element={<RequireAuth><SectorFocus /></RequireAuth>} />
        <Route path="/" element={<RequireAuth><Monitor /></RequireAuth>} />

        {/* 旧 HTML 重定向到 React 路由 */}
        <Route path="/holdings.html" element={<LegacyRedirect to="/holdings" />} />
        <Route path="/industry.html" element={<LegacyRedirect to="/industry" />} />
        <Route path="/macro.html" element={<LegacyRedirect to="/macro" />} />
        <Route path="/top_gainers.html" element={<LegacyRedirect to="/top_gainers" />} />
        <Route path="/stock_analysis.html" element={<LegacyRedirect to="/stock_analysis" />} />
        <Route path="/tips.html" element={<LegacyRedirect to="/tips" />} />
        <Route path="/simulation.html" element={<LegacyRedirect to="/simulation" />} />
        <Route path="/skills.html" element={<LegacyRedirect to="/skills" />} />
        <Route path="/strong-trend-candidates.html" element={<LegacyRedirect to="/strong-trend-candidates" />} />

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

/** 登录守卫：未登录跳转 /login */
function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

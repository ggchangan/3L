import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
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

export default function App() {
  return (
    <BrowserRouter>
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
        <Route path="/" element={<Monitor />} />

        {/* 旧 HTML 重定向到 React 路由 */}
        <Route path="/holdings.html" element={<LegacyRedirect to="/holdings" />} />
        <Route path="/industry.html" element={<LegacyRedirect to="/industry" />} />
        <Route path="/macro.html" element={<LegacyRedirect to="/macro" />} />
        <Route path="/top_gainers.html" element={<LegacyRedirect to="/top_gainers" />} />
        <Route path="/stock_analysis.html" element={<LegacyRedirect to="/stock_analysis" />} />
        <Route path="/tips.html" element={<LegacyRedirect to="/tips" />} />
        <Route path="/simulation.html" element={<LegacyRedirect to="/simulation" />} />

        {/* 未迁移的旧页面：通过 window.location 跳转 */}
        <Route path="/tip-detail" element={<LegacyRedirect to="/tip-detail.html" />} />
        <Route path="/skills" element={<LegacyRedirect to="/skills.html" />} />
        <Route path="*" element={<Navigate to="/monitor" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

/** 跳转到旧版 HTML 页面 */
function LegacyRedirect({ to }: { to: string }) {
  window.location.href = to
  return null
}

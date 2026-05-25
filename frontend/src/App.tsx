import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Monitor from './pages/Monitor'
import Review from './pages/Review'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 已迁移的 React 页面 */}
        <Route path="/monitor" element={<Monitor />} />
        <Route path="/review" element={<Review />} />
        <Route path="/" element={<Monitor />} />

        {/* 未迁移的旧页面：通过 window.location 跳转 */}
        <Route path="/journal" element={<LegacyRedirect to="/journal.html" />} />
        <Route path="/watchlist" element={<LegacyRedirect to="/watchlist.html" />} />
        <Route path="/trend_candidates" element={<LegacyRedirect to="/trend_candidates.html" />} />
        <Route path="/holdings" element={<LegacyRedirect to="/holdings.html" />} />
        <Route path="/industry" element={<LegacyRedirect to="/industry.html" />} />
        <Route path="/macro" element={<LegacyRedirect to="/macro.html" />} />
        <Route path="/stock_analysis" element={<LegacyRedirect to="/stock_analysis.html" />} />
        <Route path="/simulation" element={<LegacyRedirect to="/simulation.html" />} />
        <Route path="/top_gainers" element={<LegacyRedirect to="/top_gainers.html" />} />
        <Route path="/tips" element={<LegacyRedirect to="/tips.html" />} />
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

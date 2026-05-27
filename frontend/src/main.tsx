import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App from './App'
import './index.css'

const rootEl = document.getElementById('root')!

if (rootEl.hasChildNodes()) {
  // SSR 服务端渲染了内容 → hydrate（不 StrictMode，避免 double-render 问题）
  hydrateRoot(rootEl,
    <App />,
  )
} else {
  // 纯客户端渲染
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

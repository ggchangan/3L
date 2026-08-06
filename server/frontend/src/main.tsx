import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// ═══ 全局 fetch 包装：自动附加 Authorization + 401 统一跳登录 ═══
// 必须在 React 渲染前生效，所有页面现有 fetch 调用自动带 token
import { getToken, clearAuth } from './lib/auth'

const _origFetch = window.fetch
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === 'string' ? input
    : input instanceof Request ? input.url : String(input)
  const token = getToken()
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
  // 只给同源 /api/* 请求附加 token；绝对 URL（外部域名）绝不携带凭据
  if (token && url.startsWith('/api/')
      && !url.startsWith('/api/auth/login') && !url.startsWith('/api/auth/register')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await _origFetch(input, { ...init, headers })
  // 401：登录失效 → 清理本地态并跳登录页（登录/注册接口自身 401 除外，避免死循环）
  if (res.status === 401 && url.startsWith('/api/')
      && !url.startsWith('/api/auth/login') && !url.startsWith('/api/auth/register')) {
    clearAuth()
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
  }
  return res
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

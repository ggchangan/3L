/** 认证工具 — token/用户存取 + 登录/注册/改密码/登出 API */
const TOKEN_KEY = '3l_auth_token'
const USER_KEY = '3l_auth_user'

export interface AuthUser {
  id: number
  username: string
  display_name: string
}

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function getUser(): AuthUser | null {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') } catch { return null }
}

export function setAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `HTTP ${res.status}`)
  }
  return data as T
}

interface AuthResponse {
  success: boolean
  token: string
  user: AuthUser
  error?: string
}

export async function apiLogin(username: string, password: string): Promise<AuthUser> {
  const data = await postJson<AuthResponse>('/api/auth/login', { username, password })
  if (!data.success || !data.token) throw new Error(data.error || '登录失败')
  setAuth(data.token, data.user)
  return data.user
}

export async function apiRegister(username: string, password: string, displayName?: string): Promise<AuthUser> {
  const data = await postJson<AuthResponse>('/api/auth/register', {
    username, password, display_name: displayName,
  })
  if (!data.success || !data.token) throw new Error(data.error || '注册失败')
  setAuth(data.token, data.user)
  return data.user
}

export async function apiChangePassword(oldPassword: string, newPassword: string): Promise<void> {
  await postJson<{ success: boolean; error?: string }>('/api/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

export async function apiLogout(): Promise<void> {
  try {
    await fetch('/api/auth/logout', { method: 'POST' })
  } catch { /* 忽略网络错误，本地仍清理 */ }
  clearAuth()
}

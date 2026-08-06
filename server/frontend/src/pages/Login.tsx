/** 登录 / 注册 / 修改密码 页面（暗色主题） */
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiLogin, apiRegister, apiChangePassword, getUser, isLoggedIn } from '../lib/auth'

type Tab = 'login' | 'register' | 'password'

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '12px 14px', borderRadius: 8,
  background: '#1a1a30', border: '1px solid #2a2a4a', color: '#eee',
  fontSize: 14, outline: 'none', boxSizing: 'border-box',
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, color: '#888', marginBottom: 6,
}
const btnStyle: React.CSSProperties = {
  width: '100%', padding: '12px', borderRadius: 8, border: 'none',
  background: 'linear-gradient(135deg, #e94560, #c0392b)', color: '#fff',
  fontSize: 15, fontWeight: 600, cursor: 'pointer', marginTop: 8,
}

export default function Login() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const initialTab: Tab = params.get('tab') === 'password' ? 'password' : 'login'
  const [tab, setTab] = useState<Tab>(initialTab)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  // 登录
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  // 注册
  const [regUser, setRegUser] = useState('')
  const [regPwd, setRegPwd] = useState('')
  const [regPwd2, setRegPwd2] = useState('')
  const [regName, setRegName] = useState('')
  // 改密码
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [newPwd2, setNewPwd2] = useState('')

  const switchTab = (t: Tab) => { setTab(t); setMsg(null) }

  const handleLogin = async () => {
    if (!username || !password) { setMsg({ type: 'err', text: '请输入用户名和密码' }); return }
    setBusy(true); setMsg(null)
    try {
      await apiLogin(username.trim(), password)
      navigate('/monitor', { replace: true })
    } catch (e) {
      setMsg({ type: 'err', text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const handleRegister = async () => {
    if (!regUser || !regPwd) { setMsg({ type: 'err', text: '请输入用户名和密码' }); return }
    if (regPwd.length < 6) { setMsg({ type: 'err', text: '密码至少6位' }); return }
    if (regPwd !== regPwd2) { setMsg({ type: 'err', text: '两次输入的密码不一致' }); return }
    setBusy(true); setMsg(null)
    try {
      await apiRegister(regUser.trim(), regPwd, regName.trim())
      setMsg({ type: 'ok', text: '注册成功，已自动登录' })
      navigate('/monitor', { replace: true })
    } catch (e) {
      setMsg({ type: 'err', text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const handleChangePwd = async () => {
    if (!isLoggedIn()) { setMsg({ type: 'err', text: '请先登录后再修改密码' }); return }
    if (!oldPwd || !newPwd) { setMsg({ type: 'err', text: '请输入原密码和新密码' }); return }
    if (newPwd.length < 6) { setMsg({ type: 'err', text: '新密码至少6位' }); return }
    if (newPwd !== newPwd2) { setMsg({ type: 'err', text: '两次输入的新密码不一致' }); return }
    setBusy(true); setMsg(null)
    try {
      await apiChangePassword(oldPwd, newPwd)
      setMsg({ type: 'ok', text: '密码修改成功' })
      setOldPwd(''); setNewPwd(''); setNewPwd2('')
    } catch (e) {
      setMsg({ type: 'err', text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const curUser = getUser()

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%)',
    }}>
      <div style={{
        width: 380, maxWidth: '92vw', padding: '36px 32px', borderRadius: 16,
        background: '#141428', border: '1px solid #2a2a4a', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 26, fontWeight: 700, color: '#fff', letterSpacing: 4 }}>3L 交易系统</div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 6, letterSpacing: 2 }}>多用户登录 · 数据按用户隔离</div>
        </div>

        {/* Tab 切换 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
          {([['login', '登 录'], ['register', '注 册'], ['password', '修改密码']] as [Tab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              style={{
                flex: 1, padding: '8px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                background: tab === t ? '#e94560' : '#1a1a30', color: tab === t ? '#fff' : '#888',
                fontSize: 13, fontWeight: tab === t ? 600 : 400,
              }}
            >{label}</button>
          ))}
        </div>

        {msg && (
          <div style={{
            padding: '10px 12px', borderRadius: 8, marginBottom: 14, fontSize: 13,
            background: msg.type === 'ok' ? 'rgba(78,205,196,0.12)' : 'rgba(233,69,96,0.12)',
            color: msg.type === 'ok' ? '#4ecdc4' : '#e94560',
            border: `1px solid ${msg.type === 'ok' ? '#4ecdc4' : '#e94560'}55`,
          }}>{msg.text}</div>
        )}

        {tab === 'login' && (
          <div>
            <label style={labelStyle}>用户名</label>
            <input style={inputStyle} value={username} onChange={e => setUsername(e.target.value)}
              placeholder="admin / user2~user5" autoFocus />
            <label style={{ ...labelStyle, marginTop: 14 }}>密码</label>
            <input style={inputStyle} type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="默认密码 123456（登录后请修改）"
              onKeyDown={e => e.key === 'Enter' && handleLogin()} />
            <button style={btnStyle} onClick={handleLogin} disabled={busy}>{busy ? '登录中...' : '登 录'}</button>
          </div>
        )}

        {tab === 'register' && (
          <div>
            <label style={labelStyle}>用户名（3-20位字母/数字/下划线）</label>
            <input style={inputStyle} value={regUser} onChange={e => setRegUser(e.target.value)} />
            <label style={{ ...labelStyle, marginTop: 14 }}>昵称（可选）</label>
            <input style={inputStyle} value={regName} onChange={e => setRegName(e.target.value)} />
            <label style={{ ...labelStyle, marginTop: 14 }}>密码（至少6位）</label>
            <input style={inputStyle} type="password" value={regPwd} onChange={e => setRegPwd(e.target.value)} />
            <label style={{ ...labelStyle, marginTop: 14 }}>确认密码</label>
            <input style={inputStyle} type="password" value={regPwd2} onChange={e => setRegPwd2(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRegister()} />
            <button style={btnStyle} onClick={handleRegister} disabled={busy}>{busy ? '注册中...' : '注 册'}</button>
          </div>
        )}

        {tab === 'password' && (
          <div>
            {!isLoggedIn() ? (
              <div style={{ fontSize: 13, color: '#e94560', textAlign: 'center', padding: '20px 0' }}>
                请先 <a href="/login" style={{ color: '#4ecdc4' }}>登录</a> 后再修改密码
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>
                  当前用户：<span style={{ color: '#4ecdc4' }}>{curUser?.display_name || curUser?.username}</span>
                </div>
                <label style={labelStyle}>原密码</label>
                <input style={inputStyle} type="password" value={oldPwd} onChange={e => setOldPwd(e.target.value)} />
                <label style={{ ...labelStyle, marginTop: 14 }}>新密码（至少6位）</label>
                <input style={inputStyle} type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)} />
                <label style={{ ...labelStyle, marginTop: 14 }}>确认新密码</label>
                <input style={inputStyle} type="password" value={newPwd2} onChange={e => setNewPwd2(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleChangePwd()} />
                <button style={btnStyle} onClick={handleChangePwd} disabled={busy}>{busy ? '提交中...' : '确认修改'}</button>
              </div>
            )}
          </div>
        )}

        <div style={{ textAlign: 'center', fontSize: 11, color: '#444', marginTop: 20 }}>
          {isLoggedIn() && tab !== 'password' && (
            <a href="/login?tab=password" style={{ color: '#555', textDecoration: 'none' }}>修改密码</a>
          )}
        </div>
      </div>
    </div>
  )
}

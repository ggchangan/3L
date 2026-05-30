import { useEffect, useState, useRef } from 'react'

interface SoundConfig {
  url: string
  name: string
  duration: number
}

/* ── WxPusher 微信推送配置组件 ── */
function WxPushConfig() {
  const [status, setStatus] = useState<any>(null)
  const [uidInput, setUidInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    fetch('/api/wxpush/status')
      .then(r => r.json())
      .then(d => {
        setStatus(d)
        if (d.uid) setUidInput(d.uid)
      })
      .catch(() => setStatus({ configured: false, has_token: false, has_uid: false }))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      const r = await fetch('/api/wxpush/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: uidInput.trim() }),
      })
      const d = await r.json()
      setStatus(d)
      setMsg(d.success ? '✅ 配置已保存' : '❌ ' + (d.error || '保存失败'))
    } catch (e: any) {
      setMsg('❌ ' + (e.message || '请求失败'))
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setMsg('')
    try {
      const r = await fetch('/api/wxpush/test')
      const d = await r.json()
      setMsg(d.success ? '✅ ' + d.message : '❌ ' + (d.error || '发送失败'))
    } catch (e: any) {
      setMsg('❌ ' + (e.message || '请求失败'))
    } finally {
      setTesting(false)
    }
  }

  return (
    <div style={{ marginTop: 16, padding: 16, background: '#0d1b2a', borderRadius: 12, fontSize: 12, color: '#ccc' }}>
      <div style={{ fontWeight: 600, color: '#4ecdc4', marginBottom: 8 }}>📱 微信通知配置（WxPusher）</div>
      <div style={{ marginBottom: 8, lineHeight: 1.8 }}>
        <span style={{ color: status?.has_token ? '#4ecdc4' : '#e94560' }}>
          {status?.has_token ? '✅' : '❌'} Token 已配
        </span>
        {' | '}
        <span style={{ color: status?.has_uid ? '#4ecdc4' : '#e94560' }}>
          {status?.has_uid ? '✅' : '❌'} UID 已配
        </span>
        {!status?.has_uid && (
          <span style={{ color: '#ffd700', marginLeft: 8, fontSize: 11 }}>
            * 请在 WxPusher 后台扫二维码关注应用后获取 UID
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <span style={{ whiteSpace: 'nowrap' }}>UID：</span>
        <input
          value={uidInput}
          onChange={e => setUidInput(e.target.value)}
          placeholder="UID_xxxx"
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid #333',
            background: '#1a1a2e', color: '#e0e0e0', fontSize: 12,
          }}
        />
        <button onClick={handleSave} disabled={saving}
          style={{
            background: '#4ecdc4', color: '#000', border: 'none', borderRadius: 6,
            padding: '6px 14px', fontSize: 12, cursor: 'pointer', opacity: saving ? 0.6 : 1,
          }}
        >{saving ? '保存中...' : '💾 保存'}</button>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={handleTest} disabled={testing || !status?.has_uid}
          style={{
            background: testing ? '#555' : '#2a2a4a', color: testing ? '#888' : '#4ecdc4',
            border: '1px solid #4ecdc4', borderRadius: 6,
            padding: '6px 14px', fontSize: 12, cursor: testing || !status?.has_uid ? 'not-allowed' : 'pointer',
          }}
        >{testing ? '发送中...' : '📤 发送测试'}</button>
        <span style={{ color: msg.includes('✅') ? '#4ecdc4' : msg.includes('❌') ? '#e94560' : '#888', fontSize: 11 }}>
          {msg}
        </span>
      </div>
      {!status?.has_uid && (
        <div style={{ marginTop: 10, padding: 10, background: '#1a1a2e', borderRadius: 8, fontSize: 11, color: '#888', lineHeight: 1.8 }}>
          <div style={{ fontWeight: 600, color: '#aaa', marginBottom: 4 }}>📋 首次配置步骤</div>
          <ol style={{ margin: 0, paddingLeft: 18 }}>
            <li>前往 <a href="https://wxpusher.zjiecode.com" target="_blank" style={{ color: '#4ecdc4' }}>wxpusher.zjiecode.com</a></li>
            <li>在「应用管理」中打开你的应用</li>
            <li>用微信扫「关注二维码」关注</li>
            <li>在「用户管理」中查看你的 UID</li>
            <li>把 UID 填到上面输入框点保存</li>
            <li>点「发送测试」验证能收到消息</li>
          </ol>
        </div>
      )}
    </div>
  )
}

const ALARM_META: Record<string, { icon: string; label: string; color: string }> = {
  stop:            { icon: '🔴', label: '止损报警', color: '#e94560' },
  stock:           { icon: '🟡', label: '个股异动', color: '#ffd700' },
  market:          { icon: '🟠', label: '大盘预警', color: '#ff6b35' },
  market_critical: { icon: '🔴', label: '系统风险', color: '#e94560' },
}

const AUDIO_UNLOCKED_KEY = '3l_audio_unlocked'
function markAudioUnlocked() {
  localStorage.setItem(AUDIO_UNLOCKED_KEY, '1')
}

export default function AlarmSounds() {
  const [configs, setConfigs] = useState<Record<string, SoundConfig>>({})
  const [playingType, setPlayingType] = useState<string | null>(null)
  const [uploading, setUploading] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pendingTypeRef = useRef<string | null>(null)

  useEffect(() => {
    fetch('/api/alarm-sounds')
      .then(r => r.json())
      .then(d => setConfigs(d.alarms || {}))
      .catch(() => {})
  }, [])

  const handlePlay = (type: string) => {
    markAudioUnlocked()
    setPlayingType(type)
    const audio = document.getElementById(`cfg-audio-${type}`) as HTMLAudioElement
    if (audio) {
      audio.currentTime = 0
      audio.play().then(() => {
        setTimeout(() => setPlayingType(null), (configs[type]?.duration || 20) * 1000 + 500)
      }).catch(() => setPlayingType(null))
    }
  }

  const handleStop = (type: string) => {
    const audio = document.getElementById(`cfg-audio-${type}`) as HTMLAudioElement
    if (audio) { audio.pause(); audio.currentTime = 0 }
    setPlayingType(null)
  }

  const handleFileSelect = (type: string) => {
    pendingTypeRef.current = type
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    const type = pendingTypeRef.current
    if (!file || !type) return

    const ext = file.name.toLowerCase().split('.').pop()
    if (!['mp3', 'wav', 'ogg'].includes(ext || '')) {
      alert('仅支持 MP3、WAV、OGG 格式')
      return
    }

    if (file.size > 20 * 1024 * 1024) {
      alert('文件超过 20MB 大小限制')
      return
    }

    setUploading(type)

    try {
      // 用 FileReader.readAsDataURL 直接获取 base64（去掉 data:...;base64, 前缀）
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
          const result = reader.result as string
          // result 是 "data:audio/mpeg;base64,XXXXX..."
          const comma = result.indexOf(',')
          resolve(result.substring(comma + 1))
        }
        reader.onerror = () => reject(new Error('读取文件失败'))
        reader.readAsDataURL(file)
      })

      const r = await fetch('/api/alarm-sounds/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, name: file.name, data: base64 }),
      })
      // 只读一次 body，手动解析 JSON
      const bodyText = await r.text()
      let result: any
      try {
        result = JSON.parse(bodyText)
      } catch {
        throw new Error(`服务器返回 ${r.status}: ${bodyText.substring(0, 200)}`)
      }
      if (result.success) {
        const r2 = await fetch('/api/alarm-sounds')
        const d2 = await r2.json()
        setConfigs(d2.alarms || {})
      } else {
        alert('上传失败: ' + (result.error || '未知错误'))
      }
    } catch (err: any) {
      alert('上传失败: ' + (err.message || '未知错误'))
    } finally {
      setUploading(null)
      pendingTypeRef.current = null
      // 清理 input 以便下次选同一文件
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div style={{ maxWidth: 600, margin: '20px auto', padding: '0 16px' }}>
      {/* 隐藏的文件选择器 */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".mp3,.wav,.ogg"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      <h1 style={{ fontSize: 18, marginBottom: 16 }}>🎵 报警音乐配置</h1>
      <p style={{ fontSize: 12, color: '#888', marginBottom: 20 }}>
        点击 ▶ 试听报警音乐。试听后，盯盘页的报警将自动播放音乐（无需再点击）。<br />
        点击「上传音乐」从电脑选择 MP3/WAV 文件替换报警音乐。
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Object.entries(ALARM_META).map(([type, meta]) => {
          const cfg = configs[type]
          return (
            <div key={type} style={{
              background: 'linear-gradient(135deg, #1a1a2e, #16213e)',
              border: `1px solid ${meta.color}44`,
              borderRadius: 12, padding: 16,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 18 }}>{meta.icon}</span>
                <span style={{ color: '#e0e0e0', fontSize: 14, fontWeight: 600 }}>{meta.label}</span>
                <span style={{ color: '#888', fontSize: 11, flex: 1 }}>{cfg?.name || '默认音效'}</span>

                <button
                  onClick={() => playingType === type ? handleStop(type) : handlePlay(type)}
                  style={{
                    background: playingType === type ? '#4ecdc4' : meta.color,
                    color: '#fff', border: 'none', borderRadius: 6,
                    padding: '4px 12px', fontSize: 12, cursor: 'pointer',
                  }}
                >
                  {playingType === type ? '⏹ 停止' : '▶ 试听'}
                </button>

                <button
                  onClick={() => handleFileSelect(type)}
                  disabled={uploading === type}
                  style={{
                    background: uploading === type ? '#555' : '#2a2a4a',
                    color: uploading === type ? '#888' : '#aaa',
                    border: 'none', borderRadius: 6,
                    padding: '4px 12px', fontSize: 12, cursor: uploading === type ? 'not-allowed' : 'pointer',
                  }}
                >
                  {uploading === type ? '⏳ 上传中...' : '📁 上传音乐'}
                </button>
              </div>

              <audio id={`cfg-audio-${type}`} preload="auto" src={cfg?.url} style={{ display: 'none' }} />

              <div style={{ fontSize: 10, color: '#555', marginTop: 4 }}>
                当前文件: {cfg?.url || '默认音效'} | 支持 MP3/WAV/OGG 最大20MB
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 24, padding: 16, background: '#0d1b2a', borderRadius: 12, fontSize: 12, color: '#888' }} id="wxpush-config-section">
        <div style={{ fontWeight: 600, color: '#aaa', marginBottom: 6 }}>💡 使用说明</div>
        <ul style={{ margin: 0, paddingLeft: 16, lineHeight: 1.8 }}>
          <li>点 ▶ 试听后，浏览器会记住允许本网站播放音频</li>
          <li>之后回到盯盘页，报警时将自动播放对应的音乐</li>
          <li>点「上传音乐」从电脑选 MP3/WAV 文件替换对应的报警音乐</li>
          <li>上传后自动保存，下次报警就播你选的文件</li>
        </ul>
      </div>

      {/* ── WxPusher 微信推送配置 ── */}
      <WxPushConfig />

      <div style={{ textAlign: 'center', marginTop: 20 }}>
        <a href="/monitor" style={{ color: '#4ecdc4', fontSize: 13 }}>← 返回盯盘</a>
      </div>
    </div>
  )
}

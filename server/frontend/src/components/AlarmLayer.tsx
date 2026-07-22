import { useEffect, useRef, useState, useCallback } from 'react'

interface ToastItem {
  msg: string
  type: string
  id: number
  ts: number
  alarmId?: string
}

interface SoundConfig {
  url: string
  name: string
  duration: number
}

const ALARM_ICONS: Record<string, string> = { buy: '🟢', stop: '🔴', warn: '🟡', abnormal: '🔔', info: 'ℹ️', market: '🟠', market_critical: '🔴', panic: '🔴' }
const ALARM_COLORS: Record<string, string> = { buy: '#22c55e', stop: '#e94560', warn: '#ffd700', abnormal: '#ff9800', info: '#2196f3', market: '#ff6b35', market_critical: '#e94560', panic: '#e94560' }

const MAX_VISIBLE_TOASTS = 5

// ── 报警类型 → 音乐配置 key 映射 ─────────────
const SOUND_KEY_MAP: Record<string, string> = {
  stop: 'stop',
  warn: 'stock',
  market: 'market',
  market_critical: 'market_critical',
  price: 'stop',
  deviation: 'stock',
  panic: 'market_critical',
}

// ── 优先级（数字越小越优先）────────────────
const PRIORITY: Record<string, number> = {
  market_critical: 0,
  stop: 1,
  market: 2,
  warn: 3,
  deviation: 3,
  info: 4,
}

// ── 音频播放 ────────────────────────────────
let _soundConfig: Record<string, SoundConfig> = {}
let _audioElements: Record<string, HTMLAudioElement> = {} // DOM 创建的 audio，不受 React JSX 影响

function createAudioElements() {
  for (const [type, config] of Object.entries(_soundConfig)) {
    if (_audioElements[type]) continue
    const audio = document.createElement('audio')
    audio.id = `alarm-audio-${type}`
    audio.preload = 'auto'
    audio.src = config.url
    audio.muted = true // 初始静音，等用户点开按钮
    document.body.appendChild(audio)
    _audioElements[type] = audio
  }
}

async function loadSoundConfig(signal: AbortSignal) {
  try {
    const r = await fetch('/api/alarm-sounds', { signal })
    const data = await r.json()
    if (signal.aborted) return
    _soundConfig = data.alarms || {}
    createAudioElements()
  } catch {}
}

// 播放队列
let _playQueue: string[] = []
let _isPlaying = false
let _currentType: string | null = null
let _soundEnabled = false

function enqueueByPriority(type: string) {
  const p = PRIORITY[type] ?? 99
  let i = 0
  for (; i < _playQueue.length; i++) {
    if ((PRIORITY[_playQueue[i]] ?? 99) > p) break
  }
  _playQueue.splice(i, 0, type)
}

function playNext() {
  if (_isPlaying || _playQueue.length === 0) return
  const type = _playQueue[0]
  const soundKey = SOUND_KEY_MAP[type] || type
  const audio = _audioElements[soundKey]
  if (!audio) {
    _playQueue.shift()
    playNext()
    return
  }
  _isPlaying = true
  _currentType = type
  audio.muted = false
  audio.volume = 1
  audio.currentTime = 0
  audio.onended = () => {
    _isPlaying = false
    _currentType = null
    _playQueue.shift()
    playNext()
  }
  audio.play().catch(() => {
    _isPlaying = false
    _currentType = null
    _playQueue.shift()
  })
}

function enqueueSound(type: string) {
  if (!_soundEnabled) return
  const soundKey = SOUND_KEY_MAP[type] || type
  if (!_audioElements[soundKey]) return
  if (_currentType === type) return
  if (_playQueue.includes(type)) return
  enqueueByPriority(type)
  if (!_isPlaying) playNext()
}

function stopCurrent() {
  if (_currentType) {
    const soundKey = SOUND_KEY_MAP[_currentType] || _currentType
    const audio = _audioElements[soundKey]
    if (audio) { audio.pause(); audio.currentTime = 0 }
  }
  _isPlaying = false
  _currentType = null
}

// ── Toast ───────────────────────────────────
let toastCb: ((toasts: ToastItem[]) => void) | null = null
let panelCb: ((alarms: any[]) => void) | null = null
let toastIdCounter = 0
let activeToasts: ToastItem[] = []

export function pushAlarm(msg: string, type: string = 'info', _duration: number = 5000, alarmId?: string) {
  enqueueSound(type)
  sendBrowserNotification(msg, type)
  const item: ToastItem = { msg, type, id: ++toastIdCounter, ts: Date.now(), alarmId }
  activeToasts = [item, ...activeToasts].slice(0, MAX_VISIBLE_TOASTS)
  toastCb?.(activeToasts)
}

export function setFullAlarmPanel(alarms: any[]) {
  panelCb?.(alarms)
}

export function dismissToast(toastId: number) {
  const removed = activeToasts.find(t => t.id === toastId)
  activeToasts = activeToasts.filter(t => t.id !== toastId)
  toastCb?.(activeToasts)
  if (removed && _currentType === removed.type) stopCurrent()
}

function sendBrowserNotification(msg: string, type: string = 'info') {
  if (!('Notification' in window)) return
  const icons: Record<string, string> = { stop: '🔴', market: '🟠', market_critical: '🔴', deviation: '🟡' }
  const icon = icons[type] || '⚠️'
  if (Notification.permission === 'granted') {
    new Notification(`${icon} 3L 报警`, { body: msg })
  }
}

// ── 组件 ────────────────────────────────────
export default function AlarmLayer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [panelAlarms, setPanelAlarms] = useState<any[]>([])
  const [historyExpanded, setHistoryExpanded] = useState(false)
  const [nowPlaying, setNowPlaying] = useState<string | null>(null)
  const [soundEnabled, setSoundEnabled] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    loadSoundConfig(controller.signal)
    return () => {
      controller.abort()
      stopCurrent()
      _playQueue = []
      for (const audio of Object.values(_audioElements)) {
        audio.pause()
        audio.remove()
      }
      _audioElements = {}
    }
  }, [])

  useEffect(() => { _soundEnabled = soundEnabled }, [soundEnabled])

  // 监控播放状态
  useEffect(() => {
    const t = setInterval(() => setNowPlaying(_currentType), 1000)
    return () => clearInterval(t)
  }, [])

  const handleToasts = useCallback((items: ToastItem[]) => setToasts([...items]), [])
  const handlePanel = useCallback((items: any[]) => setPanelAlarms(items), [])

  useEffect(() => {
    toastCb = handleToasts
    panelCb = handlePanel
    return () => {
      if (toastCb === handleToasts) toastCb = null
      if (panelCb === handlePanel) panelCb = null
    }
  }, [handleToasts, handlePanel])

  const isHandledAlarm = (a: any) => a.status === 'handled' || a.status === 'dismissed'

  const dismissAlarm = async (alarmId: string) => {
    setPanelAlarms(prev => prev.map(a => a.id === alarmId ? { ...a, status: 'handled' } : a))
    try {
      const response = await fetch('/api/alarms/dismiss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: alarmId }),
      })
      if (!response.ok) throw new Error('dismiss failed')
    } catch {
      setPanelAlarms(prev => prev.map(a => a.id === alarmId ? { ...a, status: 'active' } : a))
    }
  }

  const toggleSound = () => {
    if (soundEnabled) {
      stopCurrent()
      _playQueue = []
      setSoundEnabled(false)
      _soundEnabled = false
    } else {
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission()
      }
      // 取消静音所有用 DOM 创建的 audio 元素
      for (const audio of Object.values(_audioElements)) {
        audio.muted = false
      }
      setSoundEnabled(true)
      _soundEnabled = true
      if (_playQueue.length > 0 && !_isPlaying) playNext()
    }
  }

  const toastBg: Record<string, string> = {
    buy: 'linear-gradient(135deg, #064e3b, #065f46)',
    stop: 'linear-gradient(135deg, #450a0a, #7f1d1d)',
    warn: 'linear-gradient(135deg, #422006, #713f12)',
    abnormal: 'linear-gradient(135deg, #431407, #7c2d12)',
    info: 'linear-gradient(135deg, #0c1929, #1e3a5f)',
    market: 'linear-gradient(135deg, #2d1b00, #4a2800)',
    market_critical: 'linear-gradient(135deg, #450a0a, #7f1d1d)',
    panic: 'linear-gradient(135deg, #450a0a, #7f1d1d)',
  }

  const activePanelAlarms = panelAlarms.filter(a => !isHandledAlarm(a))
  const handledPanelAlarms = panelAlarms.filter(isHandledAlarm)

  const renderPanelAlarm = (a: any, i: number, history = false) => {
    let alarmType = 'info'
    if (a.type === 'price') alarmType = 'stop'
    else if (a.type === 'deviation') alarmType = 'warn'
    else if (a.type === 'market') alarmType = 'market'
    else if (a.type === 'market_critical') alarmType = 'market_critical'
    else if (a.type === 'panic') alarmType = 'panic'
    const c = ALARM_COLORS[alarmType] || '#888'
    const ic = ALARM_ICONS[alarmType] || 'ℹ️'
    const typeLabel = {price:'止损', deviation:'异动', market:'大盘', market_critical:'系统风险', panic:'恐慌'}[a.type] || ''
    const rawMsg = a.msg || (a.stock ? `${a.stock} ${typeLabel}` : `报警 #${i + 1}`)
    const msg = String(rawMsg).replace(/^\uFFFD+\s*/, '').replace(/^[🟢🔴🟡🔔ℹ️🟠]\s*/, '')
    const alarmDate = a.triggered_at || a.handled_at || a.created || ''
    return (
      <div key={a.id || `${history}-${i}`} className={`alarm-row${history ? ' alarm-row-history' : ''}`}
        style={{ borderLeftColor: history ? '#555' : c }}>
        <span>{ic}</span>
        <span className="alarm-message">{msg}</span>
        {alarmDate && <span className="alarm-date">{String(alarmDate).slice(0, 16)}</span>}
        {!history && a.id && (
          <button type="button" className="alarm-handle-button" onClick={() => dismissAlarm(a.id)}>处理</button>
        )}
      </div>
    )
  }

  return (
    <>
      {/* 声音开关按钮 */}
      <button type="button" aria-pressed={soundEnabled} className="alarm-sound-button" style={{
        position: 'fixed', bottom: 12, right: 12, zIndex: 99999,
        background: 'rgba(0,0,0,0.7)', color: soundEnabled ? '#4ecdc4' : '#aaa', fontSize: 11,
        padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
        border: soundEnabled ? 'none' : '1px solid #4ecdc4',
        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
      }} onClick={toggleSound}>
        {soundEnabled
          ? (nowPlaying ? `🔊 ${_soundConfig[SOUND_KEY_MAP[nowPlaying] || nowPlaying]?.name}` : '🔊 报警声音已开启')
          : '🔇 点此开启报警声音'}
      </button>

      {/* Toast 弹窗 */}
      {toasts.length > 0 && (
        <div style={{
          position: 'fixed', top: 12, left: '50%', transform: 'translateX(-50%)',
          zIndex: 99999, maxWidth: 440, width: '92%',
          display: 'flex', flexDirection: 'column', gap: 6, pointerEvents: 'none',
        }}>
          {toasts.map((t, idx) => {
            const bg = toastBg[t.type] || 'linear-gradient(135deg, #1a1a2e, #16213e)'
            const color = ALARM_COLORS[t.type] || '#888'
            return (
              <div key={t.id} style={{
                pointerEvents: 'auto',
                padding: '12px 16px', borderRadius: 10, background: bg,
                border: `1.5px solid ${color}`,
                boxShadow: `0 4px 16px rgba(0,0,0,0.5)`,
                display: 'flex', alignItems: 'center', gap: 8,
                animation: `alarmSlideIn 0.25s ease-out ${idx * 0.08}s both`,
              }}>
                <span style={{ fontSize: 20, lineHeight: '18px' }}>{ALARM_ICONS[t.type] || 'ℹ️'}</span>
                <span style={{ color: '#fff', fontSize: 13.5, fontWeight: 600, flex: 1 }}>{t.msg}</span>
                <button type="button" aria-label="关闭报警提示" className="toast-close" onClick={() => dismissToast(t.id)}>×</button>
              </div>
            )
          })}
        </div>
      )}

      {/* 报警层面板 */}
      <div className="layer alarm-layer">
        <div className="layer-title">
          <span className="badge-layer">④</span> 🔔 报警层
          <button type="button" className="text-button" style={{ marginLeft: 'auto' }}
                onClick={() => window.location.href = '/alarm-sounds'}>
            🎵 配置音乐
          </button>
          <span className="badge" style={{ background: activePanelAlarms.length > 0 ? '#e94560' : '#555' }}>{activePanelAlarms.length}</span>
        </div>
        {activePanelAlarms.length === 0
          ? <div className="empty">当前没有未处理报警</div>
          : activePanelAlarms.map((a, i) => renderPanelAlarm(a, i))}
        {handledPanelAlarms.length > 0 && (
          <div className="alarm-history">
            <button type="button" className="history-toggle" aria-expanded={historyExpanded}
              onClick={() => setHistoryExpanded(v => !v)}>
              历史记录 {handledPanelAlarms.length} 条 {historyExpanded ? '收起' : '展开'}
            </button>
            {historyExpanded && handledPanelAlarms.map((a, i) => renderPanelAlarm(a, i, true))}
          </div>
        )}
      </div>
    </>
  )
}

import { useState } from 'react'

interface Alarm {
  msg: string
  type: string
  ts: number
}

const ALARM_ICONS: Record<string, string> = { buy: '🟢', stop: '🔴', warn: '🟡', abnormal: '🔔', info: 'ℹ️' }
const ALARM_COLORS: Record<string, string> = { buy: '#22c55e', stop: '#e94560', warn: '#ffd700', abnormal: '#ff9800', info: '#2196f3' }

const MAX_ALARMS = 20

/** 全局报警队列，供其他组件调用 */
let globalPushAlarm: ((msg: string, type: string) => void) | null = null

/** 发送浏览器通知 */
function sendBrowserNotification(msg: string) {
  if (!('Notification' in window)) return
  if (Notification.permission === 'granted') {
    new Notification('⚠️ 3L 报警', { body: msg })
  } else if (Notification.permission === 'default') {
    Notification.requestPermission()
  }
}

/** 播放提示音 */
function playAlertSound() {
  try {
    // 用 AudioContext 生成短促提示音，无需外部文件
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880  // A5
    osc.type = 'square'
    gain.gain.value = 0.15
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3)
    osc.start()
    osc.stop(ctx.currentTime + 0.3)
  } catch {}
}

export function pushAlarm(msg: string, type: string = 'info') {
  globalPushAlarm?.(msg, type)
  sendBrowserNotification(msg)
  playAlertSound()
}

export default function AlarmLayer() {
  const [alarms, setAlarms] = useState<Alarm[]>([])

  globalPushAlarm = (msg: string, type: string) => {
    setAlarms(prev => {
      const next = [{ msg, type, ts: Date.now() }, ...prev]
      return next.slice(0, MAX_ALARMS)
    })
  }

  return (
    <div className="layer alarm-layer">
      <div className="layer-title">
        <span className="badge-layer">④</span> 🔔 报警层
        <span className="badge" style={{ background: alarms.length > 0 ? '#e94560' : '#555' }}>{alarms.length}</span>
      </div>
      {alarms.length === 0 ? (
        <div className="empty">暂无报警</div>
      ) : (
        alarms.map((a, i) => {
          const c = ALARM_COLORS[a.type] || '#888'
          const ic = ALARM_ICONS[a.type] || 'ℹ️'
          return (
            <div
              key={`${a.ts}-${i}`}
              style={{
                display: 'flex', gap: 8, alignItems: 'flex-start', padding: '6px 10px',
                marginBottom: 4, borderRadius: 6, background: 'rgba(255,255,255,0.02)',
                borderLeft: `3px solid ${c}`, fontSize: 12,
              }}
            >
              <span>{ic}</span>
              <span style={{ color: '#e0e0e0' }}>{a.msg}</span>
            </div>
          )
        })
      )}
    </div>
  )
}

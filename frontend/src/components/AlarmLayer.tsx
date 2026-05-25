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

export function pushAlarm(msg: string, type: string = 'info') {
  globalPushAlarm?.(msg, type)
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

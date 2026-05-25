import { useEffect, useState } from 'react'

interface MonitorData {
  // TODO: Phase 1 迁移时补充类型
  market?: Record<string, unknown>
  stocks?: unknown[]
}

export default function Monitor() {
  const [data, setData] = useState<MonitorData>({})

  useEffect(() => {
    // 占位：Phase 1 迁移时接入真实 API
    setData({})
  }, [])

  return (
    <div>
      <h1>📡 3L 盘中盯盘</h1>
      <p style={{ color: '#888' }}>React 版建设中… (Phase 1 迁移)</p>
      <pre style={{ color: '#666', fontSize: 12 }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}

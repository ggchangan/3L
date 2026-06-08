import { useEffect, useRef, useState } from 'react'
import './Monitor.css'
import NavBar, { BottomNav } from '../components/NavBar'
import RuleLayer from '../components/RuleLayer'
import PlanLayer from '../components/PlanLayer'
import MarketQuote from '../components/MarketQuote'
import SectorMonitor from '../components/SectorMonitor'
import LeaderMonitor from '../components/LeaderMonitor'
import BuySignalsArea from '../components/BuySignalsArea'
import StopLossArea from '../components/StopLossArea'
import AlarmLayer, { pushAlarm, setFullAlarmPanel } from '../components/AlarmLayer'

export default function Monitor() {
  const [updateTime, setUpdateTime] = useState('等待数据...')
  const [collapseInfo, setCollapseInfo] = useState(false)
  const [collapseSectors, setCollapseSectors] = useState(true)
  const [collapseBuySignals, setCollapseBuySignals] = useState(true)

  useEffect(() => {
    const tick = () => {
      setUpdateTime(
        new Date().toLocaleTimeString('zh-CN', { hour12: false })
      )
    }
    tick()
    const timer = setInterval(tick, 30000)
    return () => clearInterval(timer)
  }, [])

  // 报警轮询：每30秒检查是否有新触发报警
  // 后端有独立线程检测，前端只读展示结果
  const shownRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const r = await fetch('/api/alarms/list-all')
        const data = await r.json()
        const alarms: any[] = data.alarms || []

        // 同步全部报警到报警层面板（含已处理的）
        setFullAlarmPanel(alarms)

        // 找新触发的（已触发、待处理、且还没展示过的）
        const newTriggered = alarms.filter((a: any) => {
          const id = a.id || `${a.stock_code}_${a.type}`
          const isActive = a.status === 'active'
          const hasTriggered = !!a.triggered_at  // 只有实际触发的才弹 toast
          return isActive && hasTriggered && !shownRef.current.has(id)
        })
        if (newTriggered.length === 0) return

        // 逐个弹窗，间隔1.5秒
        ;(async () => {
          for (const a of newTriggered) {
            await new Promise(r => setTimeout(r, 1500))
            const id = a.id || `${a.stock_code}_${a.type}`
            shownRef.current.add(id)
            // 报警类型映射
            let alarmType = 'info'
            let typeLabel = ''
            if (a.type === 'price') { alarmType = 'stop'; typeLabel = '止损' }
            else if (a.type === 'deviation') { alarmType = 'warn'; typeLabel = '异动' }
            else if (a.type === 'market') { alarmType = 'market'; typeLabel = '大盘' }
            else if (a.type === 'market_critical') { alarmType = 'market_critical'; typeLabel = '系统风险' }
            else if (a.type === 'panic') { alarmType = 'market_critical'; typeLabel = '恐慌' }
            // 优先用后端返回的消息，否则构造详细消息
            const msg = a.msg || (a.stock ? `${a.stock} ${typeLabel}`
                          : a.index_name ? `${a.index_name} ${typeLabel}`
                          : `${typeLabel}报警触发`)
            pushAlarm(msg, alarmType, 12000, a.id)
          }
        })()
      } catch {}
    }
    checkAlerts()
    const timer = setInterval(checkAlerts, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <>
      <NavBar />
      <div className="header">
        <h1>📡 3L 盘中盯盘</h1>
        <div className="update-badge" id="updateBadge">{updateTime}</div>
      </div>

      <div className="monitor-layout">
        {/* ① 规则层 */}
        <RuleLayer />

        {/* ② 计划层 */}
        <PlanLayer />

        {/* ②.5 外围关联（已移到宏观页面） */}
        <div className="layer" style={{ padding: '8px 16px', borderBottom: '1px solid #2a2a4e' }}>
          <a href="/macro.html" style={{ color: '#2196f3', fontSize: 12, textDecoration: 'none' }}>
            🌍 外围关联 → 查看宏观环境
          </a>
        </div>

        {/* ③ 信息层 */}
        <div className="layer info-layer">
          <div className="layer-title" style={{ cursor: 'pointer' }} onClick={() => setCollapseInfo(v => !v)}>
            <span className="badge-layer">③</span> 📊 实时信息
            <span className="collapse-indicator">{collapseInfo ? '▶' : '▼'}</span>
          </div>

          {!collapseInfo && (<>
          {/* 大盘观测 */}
          <div className="info-block">
            <MarketQuote />
          </div>

          {/* 板块监测 */}  
          <div className="info-block">
            <div className="block-title" style={{ cursor: 'pointer' }} onClick={() => setCollapseSectors(v => !v)}>
              📊 板块监测 <span className="badge">10分钟刷新</span>
              <span className="collapse-indicator ib-toggle">{collapseSectors ? '▼' : '▶'}</span>
            </div>
            {collapseSectors && <div className="ib-body">
              <SectorMonitor />
            </div>}
          </div>

          {/* 龙头观测 */}
          <div className="info-block">
            <LeaderMonitor />
          </div>

          {/* 盘中机会 */}
          <div className="info-block">
            <div className="block-title" style={{ cursor: 'pointer' }} onClick={e => {
              const body = (e.currentTarget.parentElement?.querySelector('.ib-body') as HTMLElement)
              if (body) {
                body.style.display = body.style.display === 'none' ? 'block' : 'none'
                const toggle = e.currentTarget.querySelector('.ib-toggle')
                if (toggle) toggle.textContent = body.style.display === 'none' ? '▶' : '▼'
              }
            }}>
              🎯 盘中机会 <span className="badge">每1小时扫描</span>
              <span className="collapse-indicator ib-toggle">▼</span>
            </div>
            <div className="ib-body">
              <BuySignalsArea />
            </div>
          </div>

          {/* 止损预警 */}
          <div className="info-block">
            <StopLossArea />
          </div>
          </>)}
        </div>

        {/* ④ 报警层 */}
        <AlarmLayer />
      </div>

      <BottomNav />
    </>
  )
}

import { useEffect, useState } from 'react'
import './Monitor.css'
import RuleLayer from '../components/RuleLayer'
import PlanLayer from '../components/PlanLayer'
import ExternalLayer from '../components/ExternalLayer'
import MarketQuote from '../components/MarketQuote'
import SectorMonitor from '../components/SectorMonitor'
import LeaderMonitor from '../components/LeaderMonitor'
import BuySignalsArea from '../components/BuySignalsArea'
import StopLossArea from '../components/StopLossArea'
import AlarmLayer from '../components/AlarmLayer'

export default function Monitor() {
  const [updateTime, setUpdateTime] = useState('等待数据...')
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

  return (
    <>
      <div style={{ marginTop: 10 }} id="nav-top"></div>
      <div className="header">
        <h1>📡 3L 盘中盯盘</h1>
        <div className="update-badge" id="updateBadge">{updateTime}</div>
      </div>

      <div className="monitor-layout">
        {/* ① 规则层 */}
        <RuleLayer />

        {/* ② 计划层 */}
        <PlanLayer />

        {/* ②.5 外围关联 */}
        <ExternalLayer />

        {/* ③ 信息层 */}
        <div className="layer info-layer">
          <div className="layer-title">
            <span className="badge-layer">③</span> 📊 实时信息
          </div>

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
        </div>

        {/* ④ 报警层 */}
        <AlarmLayer />
      </div>

      <div id="nav-bottom" style={{ textAlign: 'center', marginTop: 24, paddingTop: 14, borderTop: '1px solid #2a2a4a' }}></div>
    </>
  )
}

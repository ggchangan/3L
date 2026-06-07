/** 换算阶段图标 */
import { useState } from 'react'
const STAGE_ICONS: Record<string, string> = {
  '上行': '↑', '加速': '🚀', '缩量整理': '🔄', '滞涨': '⚠️',
  '转弱': '📉', '下行': '↓', '加速跌': '📉', '转强': '📈',
  '区间底部': '🟢', '区间中段': '➡️', '区间顶部': '🔴',
}
const STAGE_COLORS: Record<string, string> = {
  '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700', '滞涨': '#ff6b6b',
  '转弱': '#ff6b6b', '下行': '#666', '加速跌': '#e94560', '转强': '#4ecdc4',
  '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560',
}
const STRUCT_ICONS: Record<string, string> = { '上涨趋势': '📈', '区间震荡': '➡️', '下降趋势': '📉' }

import type { BuySignalItem } from '../lib/types'

interface StockCardProps {
  s: BuySignalItem
  idx: number
  chartPrefix?: string
  mode?: 'review' | 'monitor'
  opportunityMap?: Record<string, string>
}

export default function StockCard({ s, idx, chartPrefix = '', mode, opportunityMap }: StockCardProps) {
  const [showChart, setShowChart] = useState(false)
  const cls = s.signal === 'sell' ? 'danger' : s.signal === 'buy' ? 'warn' : 'hold'
  const signalText = s.signal === 'hold' ? '✅持有' : s.signal === 'buy' ? '⚡买入' : s.signal === 'sell' ? '❌卖出' : '--'
  // 操作文字优先用卡片统一推导的 action_signal，次选 action_type，最后回退 signalText
  const displayAction = s.action_signal || s.action_type || signalText

  const isTrend = s.trading_system === 'trend'
  const systemIcon = isTrend ? '🔥' : '📘'
  const systemText = isTrend ? '趋势交易' : '3L交易'

  const icon = STAGE_ICONS[s.stage] || '•'
  const stageColor = STAGE_COLORS[s.stage] || '#888'
  const structIcon = STRUCT_ICONS[s.structure] || ''

  const isBuy = s.signal === 'buy'
  const chartId = `${chartPrefix}chart_${idx}`
  const modeParam = mode ? `&mode=${mode}` : ''
  const chartUrl = `/api/stock-chart?code=${s.code}${modeParam}`
  const [chartEverShown, setChartEverShown] = useState(false)

  // 止损
  let slContent: React.ReactNode = null
  if (s.stop_loss !== undefined && s.stop_loss !== null && s.stop_loss_pct !== undefined && s.stop_loss_pct !== null) {
    const sl = Number(s.stop_loss)
    const pct = Number(s.stop_loss_pct)
    const slColor = pct > 8 ? '#e94560' : pct > 5 ? '#ffd700' : '#4ecdc4'
    slContent = <div className="field"><span className="l">止损:</span> <span className="v" style={{ color: slColor, fontSize: 11 }}>⬇ {sl.toFixed(2)} (约{pct.toFixed(1)}%)</span></div>
  }

  // 买点/区域
  let bpContent: React.ReactNode = null
  if (isTrend) {
    const bias = s.trend_bias !== undefined && s.trend_bias !== '' ? Number(s.trend_bias) : null
    if (bias !== null) {
      let zoneLabel = ''
      let zoneColor = '#888'
      if (bias < 0 || bias <= 2) { zoneLabel = '乖离率买入区'; zoneColor = '#4ecdc4' }
      else if (bias <= 8) { zoneLabel = '持有区'; zoneColor = '#ffd700' }
      else { zoneLabel = '警戒区'; zoneColor = '#e94560' }
      bpContent = <div className="field"><span className="l">区域:</span> <span className="v" style={{ color: zoneColor }}>📊 {zoneLabel} BIAS={bias.toFixed(2)}%</span></div>
    }
  } else if (s.buy_point) {
    bpContent = <div className="field"><span className="l">买点:</span> <span className="v">{s.buy_point}</span></div>
  }

  // 板块对比标识（个股 vs 板块 5日涨幅）
  const vsSector = (s as any).vs_sector_5d
  const sectorChg5d = (s as any).sector_chg_5d
  let vsSectorContent = null
  if (vsSector !== undefined && vsSector !== null) {
    const isWeak = vsSector < -3
    vsSectorContent = (
      <div className="field" style={{ marginTop: 2 }}>
        <span className="l">板块对比:</span>
        <span className="v" style={{ color: isWeak ? '#ff9800' : '#888', fontSize: 11 }}>
          {isWeak ? '⚠️ ' : ''}跑赢板块 {vsSector >= 0 ? '+' : ''}{vsSector.toFixed(1)}%
          {isWeak ? ' 偏弱' : ''}
        </span>
      </div>
    )
  }

  // 结论
  let conclusion = `阶段${s.stage}，${s.structure}`
  let conclusionColor = '#aaa'
  if (isBuy) {
    const slText = (s.stop_loss && s.stop_loss_pct)
      ? `，建议止损${Number(s.stop_loss).toFixed(2)}（约${Number(s.stop_loss_pct).toFixed(1)}%）`
      : ''
    if (isTrend) {
      const bias = s.trend_bias !== undefined && s.trend_bias !== '' ? Number(s.trend_bias) : null
      if (bias !== null && (bias < 0 || bias <= 2)) {
        conclusion = `BIAS5=${bias.toFixed(2)}%，乖离率买入区${slText}`
      } else {
        conclusion = `${s.buy_point || '买点信号'}，${s.stage}阶段${slText}`
      }
    } else {
      conclusion = `触发${s.buy_point}，${s.stage}阶段确认，可执行买入计划${slText}`
    }
    conclusionColor = '#4ecdc4'
  } else if (isTrend && s.trend_bias != null && s.trend_bias !== '') {
    const bias = Number(s.trend_bias)
    if (bias < 0) { conclusion = `BIAS5=${bias.toFixed(2)}%，价格在EMA5下方，乖离率买入区，属于趋势交易乖离率买点`; conclusionColor = '#4ecdc4' }
    else if (bias <= 2) { conclusion = `BIAS5=${bias.toFixed(2)}%，价格靠近EMA5，乖离率买入区，可考虑逢低吸纳`; conclusionColor = '#4ecdc4' }
    else if (bias <= 8) { conclusion = `BIAS5=${bias.toFixed(2)}%，价格在EMA5上方，持有区，趋势健康继续持有`; conclusionColor = '#ffd700' }
    else { conclusion = `⚠️ BIAS5=${bias.toFixed(2)}%，价格远离EMA5，警戒区，关注回调风险`; conclusionColor = '#e94560' }
  } else if (s.stage === '缩量整理') {
    const volDesc = s.vol_analysis || ''
    conclusion = `量能${volDesc}卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待放量突破`
  } else if (s.stage === '上行') { conclusion = '斜率正常，EMA10持续向上，上行趋势健康，继续持有不动' }
  else if (s.stage === '加速') { conclusion = 'EMA10斜率加速变陡，拉升阶段，关注放量滞涨等左侧止盈信号' }
  else if (s.stage === '滞涨') { conclusion = `EMA10走平涨不动${s.vol_analysis ? '，量能'+s.vol_analysis+'未有效萎缩' : ''}，警惕回调，考虑减仓` }
  else if (s.stage === '转弱') { conclusion = 'EMA10已拐头向下，趋势转弱，关注关键支撑位是否破位' }
  else if (s.stage === '区间底部') { conclusion = '价格在支撑位附近，区间底部企稳，可考虑加仓博反弹' }
  else if (s.stage === '区间顶部') { conclusion = '价格接近压力位，区间顶部受阻，注意减仓回避' }
  else if (s.stage === '区间中段') { conclusion = '区间中部无明确方向，等待价格靠近支撑或压力再做决定' }

  const changeVal = s.change || 0
  const changeColor = changeVal >= 0 ? '#ff4444' : '#44aa44'

  return (
    <div className="stock-item">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="name">{structIcon} {s.name}</span>
          <span className="code">{s.code}</span>
          {s.profit_model1 && <span className="tag" style={{ background: '#e94560', fontSize: 10, padding: '1px 6px', borderRadius: 4, marginLeft: 4 }}>🏆 盈利1</span>}
          {s.trend_stock && <span className="tag" style={{ background: '#2196f3', fontSize: 10, padding: '1px 6px', borderRadius: 4, marginLeft: 4 }}>📈 趋势股</span>}
          {isBuy && <span style={{ background: '#e94560', color: '#fff', fontSize: 11, fontWeight: 'bold', padding: '2px 8px', borderRadius: 4, marginLeft: 6 }}>🎯 买点</span>}
        </div>
        <span style={{ fontSize: 13, color: changeColor }}>
          {s.price !== undefined && s.price !== null ? s.price.toFixed(2) : '--'} {changeVal >= 0 ? '+' : ''}{changeVal}%
        </span>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <div className="field"><span className="l">方法:</span> <span className="v" title={s.trading_reason || ''}>{systemIcon}{systemText}</span></div>
        <div className="field"><span className="l">操作:</span> <span className={`v ${cls}`} style={{ fontWeight: 'bold' }}>{displayAction}</span></div>
        <div className="field"><span className="l">结构:</span> <span className="v">{structIcon} {s.structure || '--'}</span></div>
        <div className="field"><span className="l">阶段:</span> <span className="v" style={{ color: stageColor, fontWeight: 'bold' }}>{icon} {s.stage || '--'}</span></div>
        {bpContent}
        {slContent}
        {vsSectorContent}
        <div className="field">
          <span className="l">板块:</span>
          <span className="v" style={{ color: '#aaa', fontSize: 11 }}>{s.sector || '--'}</span>
          {s.sector_chg != null ? <span style={{ color: s.sector_chg >= 0 ? '#ff4444' : '#44aa44', fontSize: 11, marginLeft: 4 }}>{s.sector_chg >= 0 ? '+' : ''}{s.sector_chg.toFixed(2)}%</span> : null}
          {s.direction ? <><span style={{ color: '#555', margin: '0 4px' }}>|</span><span className="l">方向:</span> <span className="v" style={{ color: '#4ecdc4', fontSize: 11 }}>{s.direction}</span></> : null}
        </div>
        {/* 机会类型标注 */}
        {(() => {
          const secName = s.sector || s.direction || ''
          const opp = opportunityMap && secName ? opportunityMap[secName] : (s as any).opportunity
          if (!opp || opp === '--') return null
          const oppColors: Record<string, string> = {
            '主线回调': '#e94560', '次线机会': '#ffd700', '波谷观察': '#4ecdc4',
            '趋势延续': '#44aa44', '见顶风险': '#ff6b00', '回调中': '#888',
          }
          const color = oppColors[opp] || '#888'
          return (
            <div className="field">
              <span className="l">方向机会:</span>
              <span className="v" style={{ color, fontSize: 11, fontWeight: 600 }}>{opp}</span>
            </div>
          )
        })()}
        {s.mainline_level ? (
          <div className="field">
            <span className="l">定位:</span>
            <span className="v" style={{ color: s.mainline_level === '主线' ? '#e94560' : s.mainline_level === '次级主线' ? '#ffd700' : '#666', fontSize: 11 }}>{s.mainline_level}</span>
          </div>
        ) : null}
        <div className="field">
          <span className="l" style={{ cursor: 'pointer', color: '#4ecdc4' }} onClick={() => { setChartEverShown(true); setShowChart(v => !v); }}>📊</span>
        </div>
      </div>
      <div style={{ marginTop: 2, fontSize: 11, color: conclusionColor, padding: '2px 0' }}>💡 {conclusion}</div>

      {/* 融合判定信号显示 */}
      {s.triggered_signals && s.triggered_signals.length > 0 && (
        <div style={{ marginTop: 4, padding: '4px 6px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, border: '1px solid #2a2a3a' }}>
          <div style={{ fontSize: 10, color: '#888', marginBottom: 3 }}>📡 关键信号</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(s.triggered_signals as Array<{name:string;confidence:number;direction:string}>).slice(0,4).map((sig, i) => {
              const dirColor = sig.direction === 'bullish' ? '#4ecdc4' : sig.direction === 'bearish' ? '#e94560' : '#ffd700'
              const dirIcon = sig.direction === 'bullish' ? '🟢' : sig.direction === 'bearish' ? '🔴' : '🟡'
              return (
                <span key={i} style={{ fontSize: 10, background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 4, color: dirColor }}>
                  {dirIcon} {sig.name} {sig.confidence.toFixed(0)}分
                </span>
              )
            })}
            {s.fusion_type && (
              <span style={{ fontSize: 10, background: 'rgba(88,166,255,0.1)', padding: '2px 6px', borderRadius: 4, color: '#58a6ff' }}>
                {(() => {
                  const fusionLabels: Record<string,string> = {
                    'strong_buy': '🟢强买', 'signal_buy': '🟢买入', 'conflict_bearish': '⚠️警惕',
                    'signal_sell': '🔴卖出', 'conflict_bullish': '⚠️等确认', 'buy_point_only': '⏳买点',
                    'bearish_watch': '👀偏空', 'bullish_wait': '⏳等待', 'balance': '⚖️平衡',
                  }
                  return fusionLabels[s.fusion_type!] || s.fusion_type
                })()}
              </span>
            )}
          </div>
        </div>
      )}
      {(chartEverShown || showChart) && (
        <div id={chartId} className="chart-container" style={{ display: showChart ? 'block' : 'none', marginTop: 6 }}>
          <object data={chartUrl} type="image/svg+xml" style={{ width: '100%', maxWidth: 700, borderRadius: 8 }} />
        </div>
      )}
    </div>
  )
}

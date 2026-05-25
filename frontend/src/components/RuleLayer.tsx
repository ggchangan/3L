/** ① 规则层 — 今日纪律 */
export default function RuleLayer() {
  return (
    <div className="layer rule-layer">
      <div className="layer-title">
        <span className="badge-layer">①</span> ⚠️ 今日纪律
      </div>
      <div className="warnings">
        <div className="warn-item" id="dailyRule">
          <div className="num">🔴</div>
          <div className="text">按计划执行，达到条件才操作</div>
        </div>
        <div className="warn-item">
          <span className="dot">🟡</span>
          <span className="t">不看分时图，只看日K线</span>
        </div>
        <div className="warn-item">
          <span className="dot">🟡</span>
          <span className="t">不做T+0，盘中不临时起意</span>
        </div>
      </div>
    </div>
  )
}

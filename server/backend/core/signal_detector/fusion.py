"""
融合判定引擎 — 关键点 × 关键信号 → 操作建议

《量价原理》5.7节："只在关键点和关键信号交易"

流程：
  ① 运行全部9个信号检测器，收集触发结果
  ② 读取当前关键点状态（结构/阶段/EMA位置/BIAS/前高前低）
  ③ 按以下规则交叉判定：

    关键点方向 ↗    关键信号方向 ↗    → 🟢 买点确认
    关键点方向 ↗    关键信号方向 ↘    → ⚠️ 警惕假信号
    关键点方向 ↘    关键信号方向 ↗    → ⚠️ 等待确认
    关键点方向 ↘    关键信号方向 ↘    → 🔴 卖点确认
    无关键信号触发                    → ⏳ 平衡状态（等待）
"""

from typing import List, Dict, Optional, Any

from backend.core.signal_detector import (
    detect_upward_breakout,
    detect_downward_breakout,
    detect_upward_continuation,
    detect_downward_continuation,
    detect_range_continuation,
    detect_upward_reversal,
    detect_downward_reversal,
    detect_demand_exhaustion,
    detect_supply_exhaustion,
    SIGNAL_NAMES,
)

# ── 信号方向映射 ──
SIGNAL_DIRECTION = {
    'upward_breakout': 'bullish',       # 向上突破 → 看多
    'upward_continuation': 'bullish',   # 上涨中继 → 看多
    'upward_reversal': 'bullish',       # 向上反转 → 看多
    'supply_exhaustion': 'bullish',     # 供应衰竭 → 看多（抄底信号）
    'downward_breakout': 'bearish',     # 向下突破 → 看空
    'downward_reversal': 'bearish',     # 向下反转 → 看空
    'demand_exhaustion': 'bearish',     # 需求衰竭 → 看空
    'downward_continuation': 'bearish', # 下跌中继 → 看空
    'range_continuation': 'neutral',    # 区间震荡中继 → 中性
}

DETECTORS = {
    'upward_breakout': detect_upward_breakout,
    'downward_breakout': detect_downward_breakout,
    'upward_continuation': detect_upward_continuation,
    'downward_continuation': detect_downward_continuation,
    'range_continuation': detect_range_continuation,
    'upward_reversal': detect_upward_reversal,
    'downward_reversal': detect_downward_reversal,
    'demand_exhaustion': detect_demand_exhaustion,
    'supply_exhaustion': detect_supply_exhaustion,
}

# ── 关键点方向判定 ──

def _keypoint_direction(structure: str, stage: str,
                        ema_arrangement: str, bias5: float,
                        is_mainline: bool) -> str:
    """
    基于关键点状态判断当前方向偏向。
    返回 'bullish' / 'bearish' / 'neutral'
    """
    # 看空信号
    if structure == '下降趋势':
        return 'bearish'
    if stage in ('加速', '滞涨', '转弱', '放量滞涨', '缩量滞涨'):
        return 'bearish'
    if bias5 > 12:  # 严重超买
        return 'bearish'
    if structure == '区间震荡' and stage in ('区间顶部',):
        return 'bearish'

    # 看多信号
    if stage in ('缩量整理', '上行'):
        return 'bullish'
    if bias5 < -8:  # 严重超卖
        return 'bullish'
    if structure == '区间震荡' and stage in ('区间底部',):
        return 'bullish'

    # 趋势辅助判断
    if ema_arrangement in ('多头排列', '多头'):
        return 'bullish'

    return 'neutral'


def _get_triggered_signals(klines: List[Dict], idx: int,
                           main_line_names: List[str],
                           sector: str) -> List[Dict]:
    """运行全部9个信号检测器，返回所有触发的信号"""
    results = []
    for key, detector in DETECTORS.items():
        try:
            sig = detector(klines, idx)
        except Exception as e:
            continue
        if sig.get('triggered'):
            name = SIGNAL_NAMES.get(key, key)
            dir_ = SIGNAL_DIRECTION.get(key, 'neutral')
            results.append({
                'key': key,
                'name': name,
                'direction': dir_,
                'confidence': sig.get('confidence', 0),
                'scores': sig.get('scores', {}),
                'detail': sig.get('detail', ''),
            })
    return results


def _run_fusion(klines: List[Dict], idx: int, structure: str,
                stage: str, ema_arrangement: str, bias5: float,
                main_line_names: List[str], sector: str,
                existing_signal: str, existing_buy_point: str,
                confidence_threshold: int = 60) -> Dict:
    """
    融合判定主逻辑。

    Args:
        existing_signal: 当前卡片的 signal ('buy'/'hold'/'sell')
        existing_buy_point: 当前卡片的 buy_point (盈利模式1/2)

    Returns:
        融合判定结果 dict
    """
    # 1. 跑所有信号
    triggered = _get_triggered_signals(klines, idx, main_line_names, sector)

    # 过滤低置信度
    triggered = [t for t in triggered if t['confidence'] >= confidence_threshold]

    # 2. 关键点方向
    kp_dir = _keypoint_direction(structure, stage, ema_arrangement,
                                 bias5, sector in main_line_names)

    # 3. 如果有已有的 buy_point，视为强关键点信号
    buy_point_active = bool(existing_buy_point) and existing_signal == 'buy'

    # 4. 融合判定
    bullish_signals = [t for t in triggered if t['direction'] == 'bullish']
    bearish_signals = [t for t in triggered if t['direction'] == 'bearish']
    neutral_signals = [t for t in triggered if t['direction'] == 'neutral']

    best_bullish = max(bullish_signals, key=lambda x: x['confidence']) if bullish_signals else None
    best_bearish = max(bearish_signals, key=lambda x: x['confidence']) if bearish_signals else None

    result = {
        'triggered_signals': triggered,
        'keypoint_direction': kp_dir,
        'signal': 'hold',
        'signal_text': '',
        'confidence': 0,
        'fusion_type': '',
        'reason': '',
    }

    # 规则1: 关键点看多 + 看多信号 + 买点已确认 → 🟢 买入
    if buy_point_active and bullish_signals:
        result['signal'] = 'buy'
        result['signal_text'] = f'{existing_buy_point}+{best_bullish["name"]}({best_bullish["confidence"]}分)'
        result['confidence'] = min(100, 70 + best_bullish['confidence'] // 5)
        result['fusion_type'] = 'strong_buy'
        result['reason'] = f'关键点看多({kp_dir})+买点确认({existing_buy_point})+{best_bullish["name"]}信号确认'
        return result

    # 规则2: 关键点看多 + 看多信号 → 🟢 潜在买点
    if kp_dir == 'bullish' and best_bullish:
        result['signal'] = 'buy'
        result['signal_text'] = best_bullish['name']
        result['confidence'] = min(80, 50 + best_bullish['confidence'] // 4)
        result['fusion_type'] = 'signal_buy'
        result['reason'] = f'关键点看多({kp_dir})+{best_bullish["name"]}({best_bullish["confidence"]}分)→倾向买入'
        return result

    # 规则2b: 关键点看多 + 看空信号 → ⚠️ 矛盾，警惕
    if kp_dir == 'bullish' and best_bearish:
        result['signal'] = 'hold'
        result['signal_text'] = f'⚠️ {best_bearish["name"]}'
        result['confidence'] = min(60, 40 + best_bearish['confidence'] // 5)
        result['fusion_type'] = 'conflict_bearish'
        result['reason'] = f'关键点偏多({kp_dir})但出现看空信号{best_bearish["name"]}({best_bearish["confidence"]}分)，需警惕'
        return result

    # 规则3: 关键点看空 + 看空信号 → 🔴 卖出
    if kp_dir == 'bearish' and best_bearish:
        result['signal'] = 'sell'
        result['signal_text'] = best_bearish['name']
        result['confidence'] = min(80, 50 + best_bearish['confidence'] // 4)
        result['fusion_type'] = 'signal_sell'
        result['reason'] = f'关键点偏空({kp_dir})+{best_bearish["name"]}({best_bearish["confidence"]}分)→倾向卖出'
        return result

    # 规则3b: 关键点看空 + 看多信号 → ⚠️ 矛盾，等确认
    if kp_dir == 'bearish' and best_bullish:
        result['signal'] = 'hold'
        result['signal_text'] = f'⏳ {best_bullish["name"]}待确认'
        result['confidence'] = min(50, 30 + best_bullish['confidence'] // 6)
        result['fusion_type'] = 'conflict_bullish'
        result['reason'] = f'关键点偏空({kp_dir})但出现看多信号{best_bullish["name"]}({best_bullish["confidence"]}分)，等确认再入场'
        return result

    # 规则4: 已有盈利模式买点→维持买点（即使无信号确认）
    if buy_point_active:
        result['signal'] = 'buy'
        result['signal_text'] = existing_buy_point
        result['confidence'] = 60
        result['fusion_type'] = 'buy_point_only'
        result['reason'] = f'{existing_buy_point}触发，但关键信号未确认，需谨慎'
        return result

    # 规则5: 只看空关键点 + 无看空信号 → ⏳ 持有但警惕
    if kp_dir == 'bearish' and not best_bearish:
        result['signal'] = 'hold'
        result['signal_text'] = '结构偏空·等待信号'
        result['confidence'] = 40
        result['fusion_type'] = 'bearish_watch'
        result['reason'] = '关键点偏空但无信号确认，暂持有观察'
        return result

    # 规则6: 关键点看多 + 无看多信号 → ⏳ 等待
    if kp_dir == 'bullish' and not best_bullish:
        result['signal'] = 'hold'
        result['signal_text'] = '关键点位等待信号'
        result['confidence'] = 30
        result['fusion_type'] = 'bullish_wait'
        result['reason'] = '关键点偏多但无信号触发，等确认再入场'
        return result

    # 规则7: 只有信号无关键点 → ❌ 忽略
    if triggered and kp_dir == 'neutral':
        # 取置信度最高的
        best_signal = max(triggered, key=lambda x: x['confidence'])
        result['signal'] = 'hold'
        result['signal_text'] = '信号在非关键位置'
        result['confidence'] = 20
        result['fusion_type'] = 'ignore_signal'
        result['reason'] = f'{best_signal["name"]}({best_signal["confidence"]}分)但关键点中性，大概率假信号，忽略'
        return result

    # 规则8: 无信号 → ⏳ 平衡状态
    result['signal'] = 'hold'
    result['signal_text'] = '平衡'
    result['confidence'] = 0
    result['fusion_type'] = 'balance'
    result['reason'] = '无关键信号触发，正常持有'
    return result


def fusion_judge(klines: List[Dict], idx: int,
                 main_line_names: List[str], sector: str,
                 existing_signal: str = 'hold', existing_buy_point: str = '',
                 structure: str = '', stage: str = '',
                 ema_arrangement: str = '', bias5: float = 0,
                 confidence_threshold: int = 60) -> Dict:
    """
    对外接口：融合判定。

    Args:
        klines: 日K线数据
        idx: 当前索引
        main_line_names: 主线板块列表
        sector: 所属行业
        existing_signal: get_stock_card已有的signal
        existing_buy_point: get_stock_card已有的buy_point
        structure, stage, ema_arrangement, bias5: 关键点信息

    Returns:
        {
            'signal': 'buy'/'sell'/'hold',
            'signal_text': str,
            'confidence': 0-100,
            'fusion_type': str,
            'reason': str,
            'triggered_signals': [{'key', 'name', 'direction', 'confidence', ...}],
            'keypoint_direction': str,
        }
    """
    return _run_fusion(
        klines, idx, structure, stage, ema_arrangement, bias5,
        main_line_names, sector, existing_signal, existing_buy_point,
        confidence_threshold
    )

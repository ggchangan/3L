"""
信号检测器通用工具函数
"""
from typing import List, Tuple, Optional, Dict, Any


def calc_ma(klines: List[Dict], field: str = 'close', period: int = 20) -> float:
    """移动平均"""
    if len(klines) < period:
        return 0.0
    values = [k[field] for k in klines[-period:]]
    return sum(values) / period


def calc_volume_ratio(klines: List[Dict], idx: int = -1, period: int = 20) -> float:
    """当前成交量 / 过去period日均量（不含当日）"""
    if len(klines) < period + 1:
        return 0.0
    current_vol = klines[idx]['volume']
    avg_vol = sum(k['volume'] for k in klines[idx - period:idx]) / period
    if avg_vol == 0:
        return 0.0
    return current_vol / avg_vol


def calc_candle_body_ratio(klines: List[Dict], idx: int = -1) -> float:
    """实体占振幅比例，正值=阳线，负值=阴线"""
    k = klines[idx]
    body = k['close'] - k['open']
    amp = k['high'] - k['low']
    if amp == 0:
        return 0.0
    return body / amp


def is_big_candle(klines: List[Dict], idx: int = -1, threshold: float = 0.5) -> bool:
    """是否大实体K线（实体占振幅比例超过threshold）"""
    return abs(calc_candle_body_ratio(klines, idx)) >= threshold


def close_in_upper_third(klines: List[Dict], idx: int = -1) -> bool:
    """收盘价位于当日振幅的上1/3区间"""
    k = klines[idx]
    amp = k['high'] - k['low']
    if amp == 0:
        return False
    return (k['close'] - k['low']) / amp > 0.66


def close_in_lower_third(klines: List[Dict], idx: int = -1) -> bool:
    """收盘价位于当日振幅的下1/3区间"""
    k = klines[idx]
    amp = k['high'] - k['low']
    if amp == 0:
        return False
    return (k['close'] - k['low']) / amp < 0.33


def detect_range_trade(klines: List[Dict], lookback: int = 30) -> Tuple[bool, float, float, float]:
    """
    判断最近lookback天是否为区间震荡。
    返回 (is_range, range_high, range_low, range_mid)
    """
    if len(klines) < lookback:
        return False, 0, 0, 0

    window = klines[-lookback:]
    highs = [k['high'] for k in window]
    lows = [k['low'] for k in window]
    closes = [k['close'] for k in window]

    rh = max(highs)
    rl = min(lows)
    mid = (rh + rl) / 2
    amplitude = (rh - rl) / mid if mid > 0 else 999

    # 区间振幅不超过28%（趋势中短期整理振幅可能较大）
    if amplitude > 0.28:
        return False, rh, rl, mid

    # 检查是否无明显单边趋势：最近10日收盘价变化幅度 < 15%
    recent_closes = closes[-10:]
    recent_change = (recent_closes[-1] - recent_closes[0]) / (recent_closes[0] or 1)
    if abs(recent_change) > 0.15:
        return False, rh, rl, mid

    return True, rh, rl, mid


def detect_trend(klines: List[Dict], lookback: int = 30) -> str:
    """
    判断趋势方向。
    通过EMA10斜率 + 高低点创新程度综合判定。
    返回 'up' | 'down' | 'range'
    """
    if len(klines) < lookback:
        return 'range'

    window = klines[-lookback:]
    # EMA10
    ema10 = calc_ema([k['close'] for k in window], period=10)
    # 斜率：最近5日EMA变化
    if len(ema10) < 5:
        return 'range'
    ema_slope = (ema10[-1] - ema10[-5]) / (ema10[-5] or 1)

    # 高点新高比例
    highs = [k['high'] for k in window]
    lows = [k['low'] for k in window]
    recent_highs = highs[-5:]
    earlier_highs = highs[:-5]
    new_high_count = sum(1 for h in recent_highs if h > max(highs[:-5] or [0]))

    recent_lows = lows[-5:]
    new_low_count = sum(1 for l in recent_lows if l < min(lows[:-5] or [99999]))

    if ema_slope > 0.02 and new_high_count >= 3:
        return 'up'
    elif ema_slope < -0.02 and new_low_count >= 3:
        return 'down'
    else:
        return 'range'


def calc_ema(values: List[float], period: int = 10) -> List[float]:
    """EMA计算"""
    if len(values) < period:
        return values[:]
    multiplier = 2 / (period + 1)
    ema = [sum(values[:period]) / period]
    for v in values[period:]:
        ema.append((v - ema[-1]) * multiplier + ema[-1])
    return ema


def volume_trend(klines: List[Dict], window: int = 10) -> float:
    """
    最近window天成交量的线性回归斜率（归一化）。
    负值表示缩量趋势，正值表示放量趋势。
    """
    if len(klines) < window:
        return 0.0
    vols = [k['volume'] for k in klines[-window:]]
    avg = sum(vols) / window
    if avg == 0:
        return 0.0
    x_vals = list(range(window))
    n = window
    xy = sum(x * v for x, v in zip(x_vals, vols))
    x_mean = (n - 1) / 2
    xx = sum((x - x_mean) ** 2 for x in x_vals)
    if xx == 0:
        return 0.0
    slope = (xy - n * x_mean * (sum(vols) / n)) / xx
    return slope / avg  # 归一化


def calc_avg_range(klines: List[Dict], window: int = 10) -> float:
    """最近window天的平均振幅（相对收盘价）"""
    if len(klines) < window:
        return 0.0
    ranges = []
    for k in klines[-window:]:
        amp = (k['high'] - k['low']) / (k['close'] or 1)
        ranges.append(amp)
    return sum(ranges) / window


SignalResult = Dict[str, Any]
"""信号检测结果：
{
    'triggered': bool,       # 是否触发
    'confidence': float,     # 0-100 置信度
    'signal_name': str,      # 信号中文名
    'signal_key': str,       # 信号英文key
    'detail': str,           # 触发原因的简要描述
    'scores': Dict[str, float],  # 各规则得分明细
}
"""


def make_result(triggered: bool, confidence: float, signal_name: str,
                signal_key: str, detail: str = '',
                scores: Optional[Dict[str, float]] = None) -> SignalResult:
    return {
        'triggered': triggered,
        'confidence': confidence,
        'signal_name': signal_name,
        'signal_key': signal_key,
        'detail': detail,
        'scores': scores or {},
    }

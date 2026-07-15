"""ATR (Average True Range) 计算函数

用于非3L买点的持仓股止损计算。
ATR(14) 衡量股票近期的平均波动幅度，
2×ATR 低于买入价作为止损参考。

公式：
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = EMA 平滑后的 True Range
"""


def calc_atr(klines, period=14):
    """计算 ATR（平均真实波幅）

    Args:
        klines: K线列表，升序排列（旧→新），
                每根K线须含 high, low, close（或 open, close 作为close的备选）
        period: 周期（默认14）

    Returns:
        float: ATR 值（与价格同单位），数据不足时返回 0
    """
    if len(klines) < period + 1:
        return 0

    trs = []
    for i in range(1, len(klines)):
        high = klines[i].get('high', 0)
        low = klines[i].get('low', 0)
        close = klines[i].get('close', 0)
        prev_close = klines[i - 1].get('close', 0)

        hl = high - low
        hc = abs(high - prev_close)
        lc = abs(low - prev_close)
        trs.append(max(hl, hc, lc))

    if len(trs) < period:
        return 0

    # 前 period 根取算术平均值
    atr = sum(trs[:period]) / period
    # 后续用 EMA 平滑
    for v in trs[period:]:
        atr = (atr * (period - 1) + v) / period

    return atr


def calc_stop_loss_atr(cost_price, atr, cur_price, multiplier=2.0):
    """基于 ATR 计算止损价和止损百分比

    Args:
        cost_price: 买入价
        atr: ATR 值
        cur_price: 当前价（用于计算止损百分比）
        multiplier: ATR 倍数（默认2.0）

    Returns:
        (stop_loss_price, stop_loss_pct) 或 (None, None)
    """
    if not atr or atr <= 0:
        return None, None
    if not cur_price or cur_price <= 0:
        return None, None

    sl = round(cost_price - multiplier * atr, 2)
    sl_pct = round((cur_price - sl) / cur_price * 100, 2) if cur_price > 0 else None
    return sl, sl_pct

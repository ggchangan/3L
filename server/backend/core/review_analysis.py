"""
review_analysis.py — 复盘数据分析模块

从 generate_review_data.py 的③区段提取的纯函数。
接受数据为参数，不做文件I/O。可测试。
"""

import sys

from backend.core.logger import get_logger

log = get_logger(__name__)


def _get_actual_date(code, stocks, date_str):
    """用该股K线实际最新日期"""
    actual = date_str
    for sec_name, sec_stocks in stocks.items():
        if code in sec_stocks:
            kls = sec_stocks[code]
            if kls:
                last_d = kls[-1]['date']
                actual = last_d[:4] + '-' + last_d[4:6] + '-' + last_d[6:8]
            break
    return actual


def generate_holdings_review(holdings, stocks, buy_signals,
                              timing_signals_holdings, bs_by_code,
                              date_str, mainlines, trend_mainlines=None):
    """为每只持仓生成复盘结论

    Args:
        holdings: 原始持仓列表 [{'code', 'name', ...}]
        stocks: {方向: {code: [klines]}}
        buy_signals: 买点信号列表
        timing_signals_holdings: get_buy_sell_signals 返回的 holdings 列表
        bs_by_code: {code: signal_dict}
        date_str: 'YYYY-MM-DD'
        mainlines: {'lines': [...], 'secondary': [...]}
        trend_mainlines: 主线名称列表，None时从mainlines取

    Returns:
        [{'code', 'name', 'structure', 'stage', 'signal', ...}]
    """
    from backend.services.stock_card_service import get_stock_card

    if trend_mainlines is None:
        trend_mainlines = [l['name'] for l in (
            mainlines.get('lines', []) + mainlines.get('secondary', [])
        )]

    holdings_data = {h.get('code', ''): h for h in holdings}
    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}

    result = []
    for h in timing_signals_holdings:
        code = h.get('code', '')
        d = holdings_data.get(code, {})
        actual_date = _get_actual_date(code, stocks, date_str)

        # 全部从 StockCardService 取，不碰扫描缓存
        kls_for_card = None
        for sec, ss in stocks.items():
            if code in ss:
                kls_for_card = ss[code]
                break

        try:
            card = get_stock_card(
                code=code,
                date_str=actual_date,
                market_position='波中',
                main_lines=mainlines,
                direction=d.get('direction', ''),
                klines=kls_for_card,
            )
        except Exception:
            log.warning('个股卡片生成失败（持仓分析）: %s', d.get('code', '?'))
            card = None

        if not card:
            continue

        # 手动止损（唯一不从卡片取的东西）
        stop_loss = card['stop_loss']
        stop_loss_pct = card['stop_loss_pct']
        manual_sl = d.get('stop_loss_price')
        if manual_sl is not None:
            stop_loss = float(manual_sl)
            stop_loss_pct = round((card['price'] - stop_loss) / card['price'] * 100, 2) if card['price'] and card['price'] > 0 else None

        result.append({
            'code': card['code'],
            'name': card['name'],
            'sector': card['sector'],
            'direction': card.get('direction', ''),
            'structure': card['structure'],
            'stage': card['stage'],
            'price': card['price'],
            'change': card['change'],
            'ema': card['ema'],
            'vol_analysis': card['vol_analysis'],
            'signal': card['signal'],
            'signal_text': card.get('signal_text', ''),
            'buy_point': card['buy_point'],
            'profit_model1': card['profit_model1'],
            'trend_stock': card['trend_stock'],
            'trading_system': card['trading_system'],
            'trading_reason': card.get('trading_reason', ''),
            'trend_buy_type': card.get('trend_buy_type', ''),
            'trend_bias': card.get('trend_bias', ''),
            'mainline_level': card.get('mainline_level', ''),
            'stop_loss': stop_loss,
            'stop_loss_pct': stop_loss_pct,
            # 融合判定字段
            'triggered_signals': card.get('triggered_signals', []),
            'fusion_type': card.get('fusion_type', ''),
            'fusion_reason': card.get('fusion_reason', ''),
            'wave_position': card.get('wave_position', ''),
            # 操作建议（由卡片统一推导，外部不重复计算）
            'action_type': card.get('action_type', '持有'),
            'action_signal': card.get('action_signal', ''),
            'action_priority': card.get('action_priority', '中'),
            'action_reason': card.get('action_reason', ''),
        })

    result.sort(key=lambda x: struct_priority.get(x['structure'], 3))
    return result


def generate_buy_signals_review(buy_signals, stocks, stock_cache,
                                 date_str, mainlines, trend_mainlines=None,
                                 direction_map=None):
    """生成买点信号复盘

    Args:
        buy_signals: 买点信号列表
        stocks: {方向: {code: [klines]}}
        stock_cache: get_buy_sell_signals 返回的 cache
        date_str: 'YYYY-MM-DD'
        mainlines: {'lines': [...], 'secondary': [...]}
        trend_mainlines: 主线名称列表
        direction_map: {code: direction} 来自 watchlist 的方向映射

    Returns:
        [{'code', 'name', 'buy_point', 'score', ...}]
    """
    from backend.services.stock_card_service import get_stock_card

    if direction_map is None:
        direction_map = {}

    if trend_mainlines is None:
        trend_mainlines = [l["name"] for l in (
            mainlines.get("lines", []) + mainlines.get("secondary", [])
        )]

    result = []
    for s in buy_signals:
        code = s.get("code", "")
        actual_date = _get_actual_date(code, stocks, date_str)

        # 方向优先从 watchlist 取（用户手动设定），回退到空让卡片自己算
        direction = direction_map.get(code, '')

        # 全部从 StockCardService 取
        kls_for_card = None
        for sec, ss in stocks.items():
            if code in ss:
                kls_for_card = ss[code]
                break

        try:
            card = get_stock_card(
                code=code,
                date_str=actual_date,
                market_position="波中",
                main_lines=mainlines,
                direction=direction,
                klines=kls_for_card,
            )
        except Exception:
            log.warning('个股卡片生成失败（趋势候选）: %s', code)
            card = None

        if not card:
            continue

        # 信号只看最新K线 — 用 get_stock_card 确认
        if card.get("signal") != "buy":
            continue

        result.append({
            "code": card['code'],
            "name": card['name'],
            "sector": card['sector'],
            "direction": direction or card.get('direction', ''),
            "buy_point": card['buy_point'],
            "price": card['price'],
            "change": card['change'],
            "score": card.get('score', 0),
            "profit_model1": card['profit_model1'],
            "trend_stock": card['trend_stock'],
            "trading_system": card['trading_system'],
            "trading_reason": card.get('trading_reason', ''),
            "trend_buy_type": card.get('trend_buy_type', ''),
            "trend_bias": card.get('trend_bias', ''),
            "mainline_level": card.get('mainline_level', ''),
            "stop_loss": card['stop_loss'],
            "stop_loss_pct": card['stop_loss_pct'],
            "structure": card['structure'],
            "stage": card['stage'],
            "signal": card['signal'],
            "ema": card['ema'],
            "vol_analysis": card['vol_analysis'],
            "flags": card.get('flags', ''),
            "triggered_signals": card.get('triggered_signals', []),
            "fusion_type": card.get('fusion_type', ''),
            "fusion_reason": card.get('fusion_reason', ''),
            "wave_position": card.get('wave_position', ''),
            # 操作建议（由卡片统一推导，外部不重复计算）
            "action_type": card.get('action_type', '持有'),
            "action_signal": card.get('action_signal', ''),
            "action_priority": card.get('action_priority', '中'),
            "action_reason": card.get('action_reason', ''),
        })

    # 按分数降序
    result.sort(key=lambda x: x.get('score', 0), reverse=True)
    return result

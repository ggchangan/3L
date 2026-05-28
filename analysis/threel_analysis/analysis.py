"""个股分析服务 — 3l-analysis 独立版"""
import os, json
from threel_core.data_layer import get_all_stocks, get_watchlist, resolve_stock
from threel_core.buy_point_detection import (
    detect_buy_point, detect_huicai_buy_point, find_idx, _find_support_levels,
)
from threel_core.trend_trading import detect_trend_buy

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
BT_RESULTS_PATH = os.path.join(DATA_DIR, 'private', 'buy_signal_backtest_results.json')


def search_and_analyze(query, stocks=None, wl=None):
    """搜索并分析一只股票（返回 dict）"""
    if stocks is None:
        stocks = get_all_stocks()
    if wl is None:
        wl = get_watchlist()
    wl_codes = set(s['code'] for s in wl)

    matched_code, matched_direction, matched_name = resolve_stock(query, stocks)
    if not matched_code:
        return {'error': f'未找到股票: {query}'}

    return _analyze(matched_code, matched_direction, matched_name, stocks, wl_codes)


def _analyze(code, direction, name, stocks, wl_codes):
    from threel_analysis.card import get_stock_card
    from threel_core.data_layer import get_all_stocks as _get_all
    from threel_core.buy_point_detection import (
        detect_buy_point, detect_huicai_buy_point, find_idx, _find_support_levels,
    )
    from threel_core.trend_trading import detect_trend_buy
    from threel_core.ema_utils import ema_list

    kls = stocks[direction][code]
    if not kls or len(kls) < 30:
        return {'error': f'{name} 数据不足30条'}

    today_str = kls[-1]['date']
    today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}'
    is_watchlist = code in wl_codes

    # 通过 StockCard 获取核心数据
    card = get_stock_card(
        code=code,
        date_str=today_fmt,
        market_position='波中',
        main_lines=[],
        direction=direction,
        klines=kls,
    )
    if 'error' in card:
        return card

    # 构建结果
    result = {
        'code': code,
        'name': card.get('name', name),
        'direction': direction,
        'is_watchlist': is_watchlist,
        'price': card.get('price'),
        'change': card.get('change'),
        'date': card.get('date', today_fmt),
        'structure': card.get('structure', '--'),
        'stage': card.get('stage', '--'),
        'ema5': card.get('ema5'),
        'ema10': card.get('ema10'),
        'ema20': card.get('ema20'),
        'ema30': card.get('ema30'),
        'deviation_pct': card.get('deviation_pct', 0),
        'vol_ratio': card.get('vol_ratio', 0),
        'trend_stock': card.get('trend_stock', False),
        'trading_system': card.get('trading_system', '3l'),
        'trading_reason': card.get('trading_reason', ''),
        'signal': card.get('signal', 'hold'),
        'stop_loss': card.get('stop_loss'),
        'stop_loss_pct': card.get('stop_loss_pct'),
        'mainline_level': card.get('mainline_level', ''),
        'trend_bias': card.get('trend_bias'),
        'sector': card.get('sector', ''),
        'conclusion': card.get('conclusion', ''),
    }

    # SVG图表路径（不存在，独立版没有缓存图表）
    result['has_chart'] = False

    # 买点详情
    sub_stocks = {direction: {code: kls}}
    bt = detect_buy_point(code, today_str, sub_stocks)
    result['buy_point'] = bt.get('buy_type', '') if bt else ''
    result['buy_score'] = bt.get('score', 0) if bt else 0
    result['buy_detail'] = bt.get('detail', {}) if bt else None

    # 回踩买点
    hc = detect_huicai_buy_point(code, today_str, sub_stocks)
    result['huicai_detail'] = hc.get('detail', {}) if hc else None

    # 趋势股买点
    _trend_buy = detect_trend_buy(code, today_str, _get_all())
    result['trend_buy'] = _trend_buy
    result['trend_buy_type'] = card.get('trend_buy_type', '')

    # 止损/盈亏比/成功率
    _calc_risk_reward(result, code, kls, today_fmt)

    return result


def _calc_risk_reward(result, code, kls, today_fmt):
    """计算止损位、盈亏比、成功率"""
    _last_idx = find_idx(today_fmt, kls)
    _bt_cache = None
    if os.path.exists(BT_RESULTS_PATH):
        try:
            with open(BT_RESULTS_PATH) as f:
                _bt_cache = json.load(f)
        except Exception:
            pass

    if _last_idx >= 10:
        _support = _find_support_levels(kls, _last_idx)
        if _support is not None:
            cur_close = kls[-1]['close']
            _sl = round(_support * 0.98, 2)
            result['stop_loss'] = _sl
            result['stop_loss_pct'] = round((cur_close - _sl) / cur_close * 100, 2)

            _highs = [k['high'] for k in kls[:_last_idx + 1]]
            _resistance = None
            for _i in range(_last_idx, max(0, _last_idx - 30), -1):
                if _highs[_i] > cur_close * 1.02:
                    _resistance = _highs[_i]
                    break
            if _resistance and result.get('stop_loss'):
                _risk = cur_close - result['stop_loss']
                if _risk > 0:
                    result['risk_reward_ratio'] = round((_resistance - cur_close) / _risk, 2)

        if _bt_cache and code in _bt_cache:
            bt_info = _bt_cache[code]
            total = bt_info.get('total', 0)
            wins = bt_info.get('wins', 0)
            if total > 0:
                result['success_rate'] = round(wins / total * 100, 1)

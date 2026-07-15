"""
个股分析服务 — 股票搜索、技术分析、系统判定
"""
import json, os
from backend.core.config import REVIEW_CHARTS_DIR, BT_RESULTS_PATH
from backend.data_access.data_layer import get_all_stocks, get_watchlist, resolve_stock, search_stock_full_market
from backend.core.buy_point_detection import (
    detect_buy_point,
    detect_huicai_buy_point, find_idx,
    _find_support_levels,
)
from backend.core.trend_trading import detect_trend_buy
from backend.core.scan_buy_signals import get_full_mainlines


def search_and_analyze(query, stocks=None, wl=None):
    """搜索并分析一只股票

    支持按需拉取：如果股票不在数据层，尝试通过 akshare 拉取60天K线。
    stocks/wl 可选参数，用于测试注入；生产不传走缓存
    """
    if stocks is None:
        stocks = get_all_stocks()
    if wl is None:
        wl = get_watchlist()
    wl_codes = set(s['code'] for s in wl)

    q = query.strip()

    # 1. 正常搜索（在已有数据中）
    matched_code, matched_direction, matched_name = resolve_stock(q, stocks)
    if not matched_code:
        # 2. 未缓存 → 尝试按需拉取
        result = _try_on_demand_fetch(q, stocks)
        if result:
            matched_code, matched_direction, matched_name = result
        else:
            # 尝试全市场搜索，给用户更友好的提示
            market = search_stock_full_market(q, max_results=1)
            if market:
                return {'error': f'{market[0]["name"]}({market[0]["code"]}) 暂无足够数据'}
            return {'error': f'未找到股票: {q}'}

    return _analyze(matched_code, matched_direction, matched_name, stocks, wl_codes)


def _try_on_demand_fetch(query, stocks):
    """尝试按需拉取未缓存的股票数据

    Returns:
        (code, direction, name) or None
    """
    from backend.core.on_demand_stock import get_or_fetch_stock_data

    market = search_stock_full_market(query, max_results=1)
    if not market:
        return None

    code = market[0]['code']
    name = market[0]['name']

    klines, direction, _ = get_or_fetch_stock_data(code)
    if klines is None or len(klines) < 30:
        return None

    # 注入到 stocks dict（_analyze 需要 stocks[direction][code]）
    if direction not in stocks:
        stocks[direction] = {}
    stocks[direction][code] = klines

    return code, direction, name


def _analyze(code, direction, name, stocks, wl_codes):
    """执行完整的个股分析 — 基于 StockCardService 统一数据"""
    from backend.services.stock_card_service import get_stock_card
    from backend.data_access.data_layer import get_all_stocks as _get_all
    from backend.core.buy_point_detection import (
        detect_buy_point, check_trend_stock, check_profit_model1,
        detect_huicai_buy_point, find_idx, _find_support_levels,
    )
    from backend.core.trend_trading import detect_trend_buy
    from backend.core.scan_buy_signals import get_full_mainlines
    from backend.core.ema_utils import ema_list

    kls = stocks[direction][code]
    if not kls or len(kls) < 30:
        return {'error': f'{name} 数据不足30条'}

    today_str = kls[-1]['date']
    today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}'
    is_watchlist = code in wl_codes

    # 通过 StockCardService 获取核心数据（含行业+概念主线）
    _mainlines = get_full_mainlines()
    try:
        card = get_stock_card(
            code=code,
            date_str=today_fmt,
            market_position='波中',
            main_lines=_mainlines,
            direction=direction,
            klines=kls,
        )
    except Exception as e:
        return {'error': f'{name} 分析失败: {e}'}

    # 构建基础结果（卡片字段直接映射）
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
        'profit_model1': card.get('profit_model1', False),
        'trading_system': card.get('trading_system', '3l'),
        'trading_reason': card.get('trading_reason', ''),
        'signal': card.get('signal', 'hold'),
        'stop_loss': card.get('stop_loss'),
        'stop_loss_pct': card.get('stop_loss_pct'),
        'mainline_level': card.get('mainline_level', ''),
        'trend_bias': card.get('trend_bias'),
        'sector': card.get('sector', ''),
        'sector_chg': card.get('sector_chg'),
        'conclusion': card.get('conclusion', ''),
    }

    # 补充分析特有字段
    # SVG图表路径
    svg_abs = os.path.join(REVIEW_CHARTS_DIR, f'{code}.svg')
    result['has_chart'] = os.path.exists(svg_abs)

    # 买点详情（需再次调用 detect_buy_point 获取 detail）
    sub_stocks = {direction: {code: kls}}
    bt = detect_buy_point(code, today_fmt, sub_stocks)
    result['buy_point'] = bt.get('buy_type', '') if bt else ''
    result['buy_score'] = bt.get('score', 0) if bt else 0
    result['buy_detail'] = bt.get('detail', {}) if bt else None

    # 回踩买点
    hc = detect_huicai_buy_point(code, today_fmt, sub_stocks)
    result['huicai_detail'] = hc.get('detail', {}) if hc else None

    # 趋势股买点
    _trend_buy = detect_trend_buy(code, today_fmt, _get_all())
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

            # 盈亏比：找最近压力位
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

        # 成功率
        if _bt_cache and code in _bt_cache:
            bt_info = _bt_cache[code]
            total = bt_info.get('total', 0)
            wins = bt_info.get('wins', 0)
            if total > 0:
                result['success_rate'] = round(wins / total * 100, 1)

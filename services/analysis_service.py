"""
个股分析服务 — 股票搜索、技术分析、系统判定
"""
import json, os
from config import REVIEW_CHARTS_DIR, REVIEW_ARCHIVE_DIR, BT_RESULTS_PATH
from scripts.data_layer import get_all_stocks, get_watchlist, resolve_stock
from scripts.buy_point_detection import (
    detect_buy_point, check_trend_stock, check_profit_model1,
    detect_huicai_buy_point, find_idx, _ema_list,
    _find_support_levels,
)
from ema_utils import get_structure, get_stage, get_mainline_level
from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
from scripts.scan_buy_signals import get_main_lines


def search_and_analyze(query, stocks=None, wl=None):
    """搜索并分析一只股票
    
    返回 dict，含 structure/stage/signal 等所有分析字段
    如果搜索不到返回 {'error': '...'}
    stocks/wl 可选参数，用于测试注入；生产不传走缓存
    """
    if stocks is None:
        stocks = get_all_stocks()
    if wl is None:
        wl = get_watchlist()
    wl_codes = set(s['code'] for s in wl)

    # 搜索匹配
    matched_code, matched_direction, matched_name = resolve_stock(query, stocks)
    if not matched_code:
        return {'error': f'未找到股票: {query}'}

    return _analyze(matched_code, matched_direction, matched_name, stocks, wl_codes)


def _analyze(code, direction, name, stocks, wl_codes):
    """执行完整的个股分析"""
    from scripts.data_layer import get_all_stocks as _get_all
    kls = stocks[direction][code]
    if not kls or len(kls) < 30:
        return {'error': f'{name} 数据不足30条'}

    today_str = kls[-1]['date']
    today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}'
    sub_stocks = {direction: {code: kls}}

    # 核心分析
    bt = detect_buy_point(code, today_fmt, sub_stocks)
    trend = bool(check_trend_stock(code, today_fmt, sub_stocks))
    hc = detect_huicai_buy_point(code, today_fmt, sub_stocks)
    pm1 = check_profit_model1(code, today_fmt, sub_stocks)
    _main_lines = get_main_lines()
    _sys = decide_system_with_detail(code, today_fmt, _get_all(), _main_lines)
    _trend_buy = detect_trend_buy(code, today_fmt, _get_all())

    # 结构/阶段
    closes = [k['close'] for k in kls]
    structure = get_structure(closes)
    highs = [k['high'] for k in kls]
    lows = [k['low'] for k in kls]
    vols = [k.get('volume', k.get('vol', 0)) for k in kls]
    stage = get_stage(closes, structure, highs, lows, volumes=vols)

    # EMA
    ema5 = _ema_list(closes, 5)
    ema10 = _ema_list(closes, 10)
    ema20 = _ema_list(closes, 20)
    ema30 = _ema_list(closes, 30)

    cur_close = kls[-1]['close']
    cur_ema5 = ema5[-1] if ema5[-1] else 0
    deviation = (cur_close - cur_ema5) / cur_ema5 * 100 if cur_ema5 > 0 else 0
    is_watchlist = code in wl_codes

    # SVG图表路径
    svg_abs = os.path.join(REVIEW_CHARTS_DIR, f'{code}.svg')
    has_chart = os.path.exists(svg_abs)

    # 量比
    vol_ratio = 0
    if len(kls) >= 5:
        recent_vols = [k.get('volume', k.get('vol', 0)) for k in kls[-5:]]
        vma5 = sum(recent_vols) / 5 if all(v > 0 for v in recent_vols) else 0
        cur_vol = kls[-1].get('volume', kls[-1].get('vol', 0))
        vol_ratio = round(cur_vol / vma5, 2) if vma5 > 0 else 0

    result = {
        'code': code, 'name': name, 'direction': direction,
        'is_watchlist': is_watchlist,
        'price': round(cur_close, 2),
        'change': round((cur_close - kls[-2]['close']) / kls[-2]['close'] * 100, 2) if len(kls) >= 2 else 0,
        'date': today_fmt, 'structure': structure, 'stage': stage,
        'ema5': round(cur_ema5, 2) if cur_ema5 else None,
        'ema10': round(ema10[-1], 2) if ema10[-1] else None,
        'ema20': round(ema20[-1], 2) if ema20[-1] else None,
        'ema30': round(ema30[-1], 2) if ema30[-1] else None,
        'deviation_pct': round(deviation, 2), 'vol_ratio': vol_ratio,
        'trend_stock': trend,
        'profit_model1': bool(pm1 and pm1['match']) if pm1 else False,
        'trading_system': _sys['system'], 'trading_reason': _sys['reason'],
        'trend_buy': _trend_buy,
        'buy_point': bt.get('buy_type', '') if bt else '',
        'buy_score': bt.get('score', 0) if bt else 0,
        'buy_detail': bt.get('detail', {}) if bt else None,
        'huicai_detail': hc.get('detail', {}) if hc else None,
        'has_chart': has_chart,
        'signal': 'buy' if bt else ('hold' if structure == '上涨趋势' else 'warn'),
        'stop_loss': None, 'stop_loss_pct': None,
        'risk_reward_ratio': None, 'success_rate': None,
        'mainline_level': '',
    }

    # 主线分类
    result['mainline_level'] = _get_mainline_level(
        direction, REVIEW_ARCHIVE_DIR)

    # 止损位+盈亏比
    _calc_risk_reward(result, code, kls, today_fmt)

    return result


def _get_mainline_level(sector, archive_dir):
    """从复盘存档获取主线等级"""
    main_lines_list = []
    sub_main_list = []
    if os.path.isdir(archive_dir):
        archives = sorted([f for f in os.listdir(archive_dir) if f.endswith('.json')])
        if archives:
            try:
                with open(os.path.join(archive_dir, archives[-1])) as f:
                    rd = json.load(f)
                main_lines_list = [l['name'] for l in rd.get('mainline', {}).get('lines', [])]
                sub_main_list = [l['name'] for l in rd.get('mainline', {}).get('secondary', [])]
            except Exception:
                pass
    return get_mainline_level(sector, main_lines_list, sub_main_list)


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

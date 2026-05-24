"""
趋势服务 — 趋势候选扫描、跟踪管理、自选股批量分析
"""
import json
import os

import config


def get_trend_candidates():
    """趋势候选扫描 — 扫描主线候选标的，结合复盘存档中的次级主线

    返回 scan_trend_candidates() 的原始结果 dict。
    """
    from scripts.scan_buy_signals import get_main_lines
    from scripts.trend_candidates import scan_trend_candidates
    from scripts.data_layer import REVIEW_ARCHIVE_DIR

    main_lines = get_main_lines() or []

    # 读取复盘存档获取次级主线
    sub_main_names = []
    try:
        archives = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
        if archives:
            with open(os.path.join(REVIEW_ARCHIVE_DIR, archives[-1])) as f:
                rd = json.load(f)
            sub_main_names = [l['name'] for l in rd.get('mainline', {}).get('secondary', [])]
    except Exception:
        pass

    result = scan_trend_candidates(main_lines, sub_main_names)
    return result


def get_trend_tracked():
    """已跟踪趋势交易列表 — 直接从配置文件读取，不经过主线筛选"""
    from scripts.trend_candidates import get_tracked_stocks
    return get_tracked_stocks()


def toggle_trend_stock(code, enable=True):
    """切换趋势候选个股的跟踪状态（加入/移除手动列表）

    Parameters
    ----------
    code : str
        股票代码
    enable : bool
        True=加入跟踪，False=移除跟踪

    Returns
    -------
    dict
        操作结果
    """
    from scripts.trend_candidates import toggle_trend_stock as _toggle
    return _toggle(code, enable)


def get_watchlist_analysis(stocks=None, wl=None):
    """自选股批量分析 — 对自选股列表逐只计算结构/阶段/偏倚/系统/信号

    返回 {'stocks': [...], 'count': N}，每个股票条目包含：
      price, change, structure, stage, sector, trading_system,
      trend_bias, signal, trend_stock, profit_model1

    如果缺少 K 线 SVG 图表则自动生成。

    stocks/wl 可选参数，用于测试注入；生产不传走缓存。
    """
    from scripts.data_layer import get_all_stocks, get_watchlist, INDUSTRY_MAP_PATH, _load_json
    from scripts.ema_utils import get_structure, get_stage
    from scripts.buy_point_detection import check_trend_stock, check_profit_model1, _ema_list
    from scripts.trend_trading import decide_system_with_detail
    from scripts.scan_buy_signals import get_main_lines

    if stocks is None:
        stocks = get_all_stocks()
    if wl is None:
        wl = get_watchlist()
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    _main_lines = get_main_lines()

    results = []
    for s in wl:
        code = s['code']

        # 在所有方向中查找 K 线数据
        kls = None
        for sec, codes in stocks.items():
            if code in codes:
                kls = codes[code]
                break

        if not kls or len(kls) < 30:
            results.append({
                **s,
                'price': None,
                'change': None,
                'structure': '数据不足',
                'stage': '',
                'sector': imap.get(code, {}).get('ths_industry', ''),
                'trading_system': '3l',
                'trend_bias': None,
                'signal': 'hold',
                'trend_stock': False,
                'profit_model1': False,
            })
            continue

        closes = [k['close'] for k in kls]
        highs = [k['high'] for k in kls]
        lows = [k['low'] for k in kls]
        vols = [k.get('volume', k.get('vol', 0)) for k in kls]
        cur_close = kls[-1]['close']
        change = round((cur_close - kls[-2]['close']) / kls[-2]['close'] * 100, 2) if len(kls) >= 2 else 0

        structure = get_structure(closes)
        stage = get_stage(closes, structure, highs, lows, volumes=vols)
        sector = imap.get(code, {}).get('ths_industry', '')

        ema5 = _ema_list(closes, 5)
        cur_ema5 = ema5[-1] if ema5 and ema5[-1] else 0
        trend_bias = round((cur_close - cur_ema5) / cur_ema5 * 100, 2) if cur_ema5 > 0 else 0

        today_str = kls[-1]['date']
        today_fmt = today_str[:4] + '-' + today_str[4:6] + '-' + today_str[6:8]

        _sys = decide_system_with_detail(code, today_fmt, stocks, _main_lines)
        _trading_system = _sys['system']
        _trend_stock = bool(check_trend_stock(code, today_fmt, stocks))
        _pm1 = check_profit_model1(code, today_fmt, stocks)
        _profit_model1 = bool(_pm1 and _pm1.get('match', False)) if _pm1 else False

        # 生成 K 线 SVG 图（若缺失）
        svg_abs = config.review_chart_svg(code)
        if not os.path.exists(svg_abs):
            try:
                from scripts.scan_buy_signals import gen_svg
                from scripts.buy_point_detection import _find_support_levels, find_idx

                kps = []
                idx = find_idx(today_fmt, kls)
                if idx >= 10:
                    support = _find_support_levels(kls, idx)
                    if isinstance(support, (int, float)):
                        kps = [{'label': '突', 'y': support}]
                name = s.get('name', code)
                gen_svg(name, code, kls, [], svg_abs)
            except Exception:
                pass

        # signal：简单推断
        signal = 'hold'
        if structure == '上涨趋势' and stage in ('上行', '缩量整理'):
            signal = 'hold'
        elif structure == '上涨趋势' and stage in ('加速',):
            signal = 'buy'
        elif structure == '下降趋势' or stage in ('转弱', '滞涨', '下行'):
            signal = 'sell'
        elif structure == '区间震荡' and stage == '区间底部':
            signal = 'buy'

        results.append({
            **s,
            'price': round(cur_close, 2),
            'change': change,
            'structure': structure,
            'stage': stage,
            'sector': sector,
            'trading_system': _trading_system,
            'trend_bias': trend_bias,
            'signal': signal,
            'trend_stock': _trend_stock,
            'profit_model1': _profit_model1,
        })

    return {'stocks': results, 'count': len(results)}

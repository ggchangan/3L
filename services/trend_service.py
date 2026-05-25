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


def search_watchlist_for_trend(query):
    """从自选股搜索可加入趋势候选的股票

    从自选股列表中搜索匹配代码或名称的股票，
    同时标注是否已在趋势候选列表中。

    Parameters
    ----------
    query : str
        搜索关键词（股票代码或名称）

    Returns
    -------
    dict
        {'results': [{'code', 'name', 'direction', 'in_trend'}, ...]}
    """
    from scripts.trend_candidates import _load_manual_trend
    import config

    # 读取自选股
    wl_path = config.WATCHLIST_PATH
    try:
        with open(wl_path) as f:
            import json
            wl = json.load(f).get('stocks', [])
    except Exception:
        return {'results': []}

    manual = _load_manual_trend()
    q = query.strip().lower()
    if not q or len(q) < 1:
        return {'results': []}

    results = []
    for s in wl:
        code = s.get('code', '')
        name = s.get('name', '')
        if q in code.lower() or q in name.lower():
            results.append({
                'code': code,
                'name': name,
                'direction': s.get('direction', ''),
                'in_trend': code in manual,
            })

    # 按代码匹配优先、名称匹配次之排序
    results.sort(key=lambda x: (0 if x['code'].startswith(q) else 1, x['code']))
    return {'results': results[:20]}


def get_watchlist_analysis(stocks=None, wl=None):
    """自选股批量分析 — 对自选股列表逐只计算结构/阶段/偏倚/系统/信号

    返回 {'stocks': [...], 'count': N}，每个股票条目包含：
      price, change, structure, stage, sector, trading_system,
      trend_bias, signal, trend_stock, profit_model1

    如果缺少 K 线 SVG 图表则自动生成。

    stocks/wl 可选参数，用于测试注入；生产不传走缓存。
    """
    from scripts.data_layer import get_all_stocks, get_watchlist, INDUSTRY_MAP_PATH, _load_json
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

        today_str = kls[-1]['date']
        today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}'

        # 通过 StockCardService 统一获取卡片数据
        try:
            from services.stock_card_service import get_stock_card
            card = get_stock_card(
                code=code,
                date_str=today_fmt,
                market_position='波中',
                main_lines=list(_main_lines) if _main_lines else [],
                klines=kls,
            )
        except Exception as e:
            results.append({
                **s,
                'price': round(kls[-1]['close'], 2),
                'change': round((kls[-1]['close'] - kls[-2]['close']) / kls[-2]['close'] * 100, 2) if len(kls) >= 2 else 0,
                'structure': '--',
                'stage': '--',
                'sector': imap.get(code, {}).get('ths_industry', ''),
                'trading_system': '3l',
                'trend_bias': None,
                'signal': 'hold',
                'trend_stock': False,
                'profit_model1': False,
            })
            continue

        # 生成 K 线 SVG 图（若缺失）
        svg_abs = config.review_chart_svg(code)
        if not os.path.exists(svg_abs):
            try:
                from scripts.scan_buy_signals import gen_svg
                from scripts.buy_point_detection import _find_support_levels, find_idx

                kps = []
                idx_ = find_idx(today_fmt, kls)
                if idx_ >= 10:
                    support = _find_support_levels(kls, idx_)
                    if isinstance(support, (int, float)):
                        kps = [{'label': '突', 'y': support}]
                name = s.get('name', code)
                gen_svg(name, code, kls, [], svg_abs)
            except Exception:
                pass

        results.append({
            **s,
            'price': card.get('price'),
            'change': card.get('change'),
            'structure': card.get('structure', '--'),
            'stage': card.get('stage', '--'),
            'sector': card.get('sector', ''),
            'trading_system': card.get('trading_system', '3l'),
            'trend_bias': card.get('trend_bias', None) or card.get('deviation_pct'),
            'signal': card.get('signal', 'hold'),
            'trend_stock': card.get('trend_stock', False),
            'profit_model1': card.get('profit_model1', False),
        })

    return {'stocks': results, 'count': len(results)}

"""
趋势服务 — 趋势候选扫描、跟踪管理
"""
import json
import os

from backend import config


def get_trend_candidates():
    """趋势候选扫描 — 从主线缓存读取主线+次级主线，扫描全市场候选标的"""
    from backend.core.scan_buy_signals import get_main_lines, get_sub_main_lines
    from backend.core.trend_candidates import scan_trend_candidates

    main_lines = get_main_lines() or []
    sub_main_names = get_sub_main_lines() or []

    result = scan_trend_candidates(main_lines, sub_main_names)
    return result


def get_trend_tracked():
    """已跟踪趋势交易列表 — 直接从配置文件读取，不经过主线筛选"""
    from backend.core.trend_candidates import get_tracked_stocks
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
    from backend.core.trend_candidates import toggle_trend_stock as _toggle
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
    from backend.core.trend_candidates import _load_manual_trend
    from backend import config

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

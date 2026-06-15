"""大盘市场数据路由"""
from . import parse_query, get_server
from backend.services.market_service import get_momentum_data
from backend.services.stock_chart_service import generate_index_chart
from backend.core.logger import get_logger

log = get_logger('api.market')


def _handle_market(h, path):
    """实时计算大盘周期数据（读本地K线）
    支持 ?code=000001 参数指定指数，默认中证全指(000985)
    """
    from backend.data_access.data_layer import get_index_klines, INDEX_CODE
    from backend.services.review_compute_service import judge_peak_valley, fetch_market_quote
    try:
        params = parse_query(path)
        code = (params.get('code') or [INDEX_CODE])[0]
        index_klines = get_index_klines(code)
        if isinstance(index_klines, list):
            index_klines = [k for k in index_klines if k.get('date', '') <= '99999999']
        today_quote = fetch_market_quote()
        market_cycle = judge_peak_valley(index_klines)
        if index_klines:
            last = index_klines[-1]
            prev = index_klines[-2] if len(index_klines) >= 2 else None
            market_cycle['price'] = f"{last['close']:.2f}"
            if prev:
                chg_pct = (last['close'] - prev['close']) / prev['close'] * 100
                market_cycle['change'] = round(chg_pct, 2)
            else:
                market_cycle['change'] = 0
            market_cycle['data_date'] = last.get('date', '')
        h.send_json(market_cycle)
    except Exception as e:
        log.error(f'实时计算大盘数据失败: {e}')
        h.send_json({'price': '--', 'position': '波中', 'score': 0})


def _handle_mainlines(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA.get('mainlines', {}))


def _handle_stocks(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA.get('stocks', {}))


def _handle_momentum(h, path):
    """返回动量数据"""
    h.send_json(get_momentum_data())


def _handle_review_full(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA)


def _handle_index_chart(h, path):
    """返回指数K线SVG
    ?code=000001 — 指数代码，默认000985（中证全指）
    ?mode=monitor → 总是最新数据（含实时）
    ?mode=review → 按时间控制（18:00前不包含今天）
    """
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(path).query)
    mode = (qs.get('mode') or ['review'])[0]
    code = (qs.get('code') or ['000985'])[0]
    svg_path, err = generate_index_chart(mode=mode, code=code)
    if err:
        h.send_json({'error': err})
        return
    h._serve_file(svg_path, 'image/svg+xml')


def register_routes(routes):
    routes.exact('/api/market', func=_handle_market)
    routes.exact('/api/mainlines', func=_handle_mainlines)
    routes.exact('/api/stocks', func=_handle_stocks)
    routes.exact('/api/momentum', func=_handle_momentum)
    routes.exact('/api/review', func=_handle_review_full)
    routes.exact('/api/index-chart', func=_handle_index_chart)
    return routes

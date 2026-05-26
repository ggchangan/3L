"""大盘市场数据路由"""
from . import parse_query, get_server
from services.market_service import get_momentum_data
from services.stock_chart_service import generate_index_chart
from services.logger import get_logger

log = get_logger('api.market')


def _handle_market(h, path):
    """实时计算大盘周期数据（不读存档）"""
    from services.review_compute_service import fetch_index_klines, judge_peak_valley, fetch_market_quote
    try:
        index_klines = fetch_index_klines(120)
        if not index_klines:
            index_klines = fetch_index_klines(120)
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
    """返回中证全指K线SVG（含实时叠加）"""
    svg_path, err = generate_index_chart()
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

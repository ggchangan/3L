"""个股分析/回测/图表路由"""
from . import parse_query
from services.analysis_service import search_and_analyze
from services.backtest_service import run_backtest
from services.stock_chart_service import generate_stock_chart, generate_trend_stock_chart


def _handle_stock_analysis(h, path):
    q = parse_query(path).get('q', [''])[0].strip()
    if not q:
        h.send_json({'error': '请输入股票代码或名称'})
        return
    h.send_json(search_and_analyze(q))


def _handle_stock_backtest(h, path):
    params = parse_query(path)
    code = params.get('code', [''])[0].strip()
    days = int(params.get('days', ['60'])[0])
    market_position = params.get('market_position', ['波中'])[0].strip()
    main_lines_raw = params.get('main_lines', [''])[0].strip()
    if not code:
        h.send_json({'error': '请输入股票代码或名称'})
        return
    main_lines = set(m.strip() for m in main_lines_raw.split(',') if m.strip()) if main_lines_raw else {'半导体'}
    h.send_json(run_backtest(code, days, market_position=market_position, main_lines=main_lines))


def _get_stock_trading_system(code):
    """从 manual_trend_stocks.json 查交易系统类型"""
    raw_code = str(code).strip()
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if raw_code.startswith(pfx):
            raw_code = raw_code[len(pfx):]
            break
    raw_code = raw_code[-6:] if len(raw_code) >= 6 else raw_code
    try:
        from config import MANUAL_TREND_PATH
        import json
        with open(MANUAL_TREND_PATH, 'r', encoding='utf-8') as f:
            manual = json.load(f)
        if raw_code in manual:
            return 'trend'
    except Exception:
        pass
    return '3l'


def _handle_stock_chart(h, path):
    params = parse_query(path)
    code = params.get('code', [None])[0]
    if not code:
        h.send_json({'error': 'missing code param'})
        return
    if code in ('undefined', 'null', 'None', ''):
        h.send_json({'error': f'invalid code: {code}'})
        return
    # 后端自决交易系统类型，不依赖前端传 sys 参数
    trading_system = _get_stock_trading_system(code)
    if trading_system == 'trend':
        svg_str, err = generate_trend_stock_chart(code)
        if err:
            h.send_json({'error': err})
            return
    else:
        svg_str, err = generate_stock_chart(code)
        if err:
            h.send_json({'error': err})
            return
    body = svg_str.encode('utf-8')
    h.send_response(200)
    h.send_header('Content-Type', 'image/svg+xml')
    h.send_header('Content-Length', str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def register_routes(routes):
    routes.exact('/api/stock-analysis', func=_handle_stock_analysis)
    routes.exact('/api/stock-backtest', func=_handle_stock_backtest)
    routes.exact('/api/stock-chart', func=_handle_stock_chart)
    return routes

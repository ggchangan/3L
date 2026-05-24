"""个股分析/回测路由"""
from . import parse_query
from services.analysis_service import search_and_analyze
from services.backtest_service import run_backtest


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
    if not code:
        h.send_json({'error': '请输入股票代码或名称'})
        return
    h.send_json(run_backtest(code, days))


def register_routes(routes):
    routes.exact('/api/stock-analysis', func=_handle_stock_analysis)
    routes.exact('/api/stock-backtest', func=_handle_stock_backtest)
    return routes

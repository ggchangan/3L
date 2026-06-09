"""个股分析/回测/图表路由"""
from backend.core.logger import get_logger
from . import parse_query

log = get_logger(__name__)
from backend.services.analysis_service import search_and_analyze
from backend.services.backtest_service import run_backtest
from backend.services.stock_chart_service import generate_stock_chart, generate_trend_stock_chart
from backend.services.diagnosis_service import compute_diagnosis


def _handle_stock_analysis(h, path):
    q = parse_query(path).get('q', [''])[0].strip()
    if not q:
        h.send_json({'error': '请输入股票代码或名称'})
        return
    result = search_and_analyze(q)
    if isinstance(result, dict) and 'error' not in result:
        try:
            diag = compute_diagnosis(result.get('code', ''), result.get('name', ''), result)
            result['diagnosis'] = diag
        except Exception as e:
            log.error("stock diagnosis error: %s", e, exc_info=True)
            result['diagnosis'] = {'error': str(e)}
    h.send_json(result)


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
        from backend.config import MANUAL_TREND_PATH
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
    # 图表模式：monitor=含实时，其他=不实时（只用日K线）
    mode = (params.get('mode') or ['review'])[0]
    # 后端自决交易系统类型，不依赖前端传 sys 参数
    trading_system = _get_stock_trading_system(code)
    if trading_system == 'trend':
        svg_str, err = generate_trend_stock_chart(code, mode=mode)
        if err:
            h.send_json({'error': err})
            return
    else:
        # 检测信号（用于SVG图上标注）
        triggered = _detect_chart_signals(code)
        svg_str, err = generate_stock_chart(code, mode=mode, triggered_signals=triggered)
        if err:
            h.send_json({'error': err})
            return
    body = svg_str.encode('utf-8')
    h.send_response(200)
    h.send_header('Content-Type', 'image/svg+xml')
    h.send_header('Content-Length', str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _detect_chart_signals(code):
    """对个股检测信号，返回触发信号列表用于SVG标注"""
    try:
        from backend.core.signal_detector import (
            detect_upward_breakout, detect_upward_continuation, detect_upward_reversal,
            detect_supply_exhaustion, detect_downward_breakout, detect_downward_reversal,
            detect_demand_exhaustion, detect_downward_continuation, detect_range_continuation,
        )
        from backend.services.stock_chart_service import get_all_stocks, get_stock_klines
        raw_code = str(code).strip()
        for pfx in ['SH', 'SZ', 'sh', 'sz']:
            if raw_code.startswith(pfx):
                raw_code = raw_code[len(pfx):]
                break
        raw_code = raw_code[-6:] if len(raw_code) >= 6 else raw_code
        stocks = get_all_stocks()
        klines = get_stock_klines(raw_code, stocks=stocks)
        if not klines or len(klines) < 20:
            return []
        idx = len(klines) - 1
        detectors = [
            ('向上突破', detect_upward_breakout, 'bullish'),
            ('上涨中继', detect_upward_continuation, 'bullish'),
            ('向上反转', detect_upward_reversal, 'bullish'),
            ('供应衰竭', detect_supply_exhaustion, 'bullish'),
            ('向下突破', detect_downward_breakout, 'bearish'),
            ('向下反转', detect_downward_reversal, 'bearish'),
            ('需求衰竭', detect_demand_exhaustion, 'bearish'),
            ('下跌中继', detect_downward_continuation, 'bearish'),
            ('区间震荡', detect_range_continuation, 'neutral'),
        ]
        signals = []
        for name, detector, direction in detectors:
            try:
                result = detector(klines, idx)
                if result.get('triggered'):
                    signals.append({
                        'key': name,
                        'name': name,
                        'direction': direction,
                        'confidence': result.get('confidence', 60),
                    })
            except Exception:
                pass
        return signals
    except Exception:
        return []


def register_routes(routes):
    routes.exact('/api/stock-analysis', func=_handle_stock_analysis)
    routes.exact('/api/stock-backtest', func=_handle_stock_backtest)
    routes.exact('/api/stock-chart', func=_handle_stock_chart)
    return routes

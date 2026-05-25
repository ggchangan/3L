"""持仓/交易记录路由"""
import json
from services.holdings_service import get_holdings_with_prices, get_trades, save_holdings


def _handle_holdings(h, path):
    """GET /api/holdings — 返回持仓（含实时行情）"""
    h.send_json(get_holdings_with_prices())


def _handle_trades(h, path):
    """GET /api/trades — 返回交易记录"""
    h.send_json(get_trades())


def _handle_save(h, path, body):
    """POST /api/holdings/save — 保存持仓全量数据"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        h.send_json({'success': False, 'error': f'JSON解析失败: {e}'})
        return

    result = save_holdings(data)
    h.send_json(result)


def register_routes(routes):
    routes.exact('/api/holdings', func=_handle_holdings)
    routes.exact('/api/trades', func=_handle_trades)
    return routes

"""持仓/交易记录路由"""
import json
from backend.core.exceptions import APIError
from backend.services.holdings_service import (
    get_holdings_with_prices,
    get_stop_loss_recommendation,
    get_trades,
    save_holdings,
)


def _handle_holdings(h, path):
    """GET /api/holdings — 返回持仓（含实时行情）"""
    h.send_json(get_holdings_with_prices())


def _handle_recommended_stop(h, path, body):
    """POST /api/holdings/recommended-stop — 获取推荐止损价

    Body: {"code": "002371", "buy_date": "2026-07-01",
           "buy_price": 100, "current_stop": 92}
    只返回建议，不修改已保存的手工止损。
    """
    try:
        data = json.loads(body)
        code = data.get('code', '').strip()
        if not code:
            h.send_json({'success': False, 'error': '缺少 code'})
            return
        h.send_json(get_stop_loss_recommendation(
            code=code,
            buy_date=data.get('buy_date'),
            buy_price=data.get('buy_price'),
            current_stop=data.get('current_stop'),
            entry_signal_type=data.get('entry_signal_type'),
            entry_signal_date=data.get('entry_signal_date'),
            entry_anchor_price=data.get('entry_anchor_price'),
            original_stop_loss_price=data.get('original_stop_loss_price'),
        ))
    except Exception as e:
        raise APIError(f"持仓操作异常: {e}") from e


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
    routes.exact('/api/holdings/recommended-stop', func=_handle_recommended_stop)
    routes.exact('/api/trades', func=_handle_trades)
    return routes

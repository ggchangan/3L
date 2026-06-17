"""持仓/交易记录路由"""
import json
from backend.core.exceptions import APIError
from backend.services.holdings_service import get_holdings_with_prices, get_trades, save_holdings


def _handle_holdings(h, path):
    """GET /api/holdings — 返回持仓（含实时行情）"""
    h.send_json(get_holdings_with_prices())


def _handle_recommended_stop(h, path, body):
    """POST /api/holdings/recommended-stop — 获取推荐止损价

    Body: {"code": "002371"}
    从 get_stock_card() 读取推荐止损价返回（优先使用 holdings_service 的缓存）。
    """
    try:
        data = json.loads(body)
        code = data.get('code', '').strip()
        if not code:
            h.send_json({'success': False, 'error': '缺少 code'})
            return
        # 优先从持仓卡片缓存取
        from backend.services.holdings_service import _get_cached_card
        card = _get_cached_card(code)
        if card is None:
            from backend.services.stock_card_service import get_stock_card
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            card = get_stock_card(code, today)
        stop_loss = card.get('stop_loss')
        if stop_loss and stop_loss > 0:
            h.send_json({
                'success': True,
                'stop_loss': round(stop_loss, 2),
                'stop_loss_pct': card.get('stop_loss_pct'),
                'price': card.get('price'),
            })
        else:
            h.send_json({'success': False, 'error': '无法获取推荐止损', 'price': card.get('price')})
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

"""热点个股追踪路由 — 同花顺热股Top100 + 3L分析"""
import requests
import json
from datetime import datetime
from . import parse_query, get_server


# 同花顺热点API配置
_THS_HOT_API = 'http://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock'
_THS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.10jqka.com.cn/',
    'Accept': 'application/json, text/plain, */*',
}

# 交易所映射
_MARKET_MAP = {
    17: '.SS',   # 上交所
    33: '.SZ',   # 深交所
}


def _fetch_hot_stocks(stock_type='a', list_type='normal', limit=100):
    """从同花顺获取热门个股列表"""
    params = {
        'stock_type': stock_type,
        'type': 'day',
        'list_type': list_type,
    }
    try:
        r = requests.get(_THS_HOT_API, headers=_THS_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            return None, f'同花顺API返回 {r.status_code}'
        data = r.json()
        if data.get('status_code') != 0:
            return None, data.get('status_msg', '未知错误')
        stock_list = data.get('data', {}).get('stock_list', [])
        return stock_list[:limit], None
    except Exception as e:
        return None, str(e)


def _code_with_market(code, market):
    """根据交易所返回带后缀的代码"""
    suffix = _MARKET_MAP.get(market, '')
    return code + suffix


def _handle_hot_stocks(h, path):
    """GET /api/hot-stocks — 返回热点个股 + 3L分析"""
    params = parse_query(path)
    limit = int(params.get('limit', ['100'])[0])
    stock_type = params.get('stock_type', ['a'])[0]

    # 1. 获取热股列表
    stock_list, err = _fetch_hot_stocks(stock_type=stock_type, limit=limit)
    if err:
        h.send_json({'error': f'获取热股失败: {err}', 'stocks': [], 'total': 0})
        return

    # 2. 获取每只热股的3L分析
    from backend.services.stock_card_service import get_stock_card
    today = datetime.now().strftime('%Y%m%d')

    results = []
    for item in stock_list:
        code = item.get('code', '')
        name = item.get('name', '')
        market = item.get('market', 0)
        hot_rank = item.get('order', 0)
        hot_value = item.get('rate', '0')
        try:
            hot_value_int = int(hot_value) if hot_value else 0
        except (ValueError, TypeError):
            hot_value_int = 0
        change_raw = item.get('rise_and_fall', 0)
        change = round(change_raw, 2) if change_raw else None
        tags = item.get('tag', {}) or {}
        concept_tags = tags.get('concept_tag', [])
        popularity_tag = tags.get('popularity_tag', '')

        # 调用3L卡片分析
        try:
            card = get_stock_card(code.strip(), today)
            if card:
                # 合并热股特有字段
                card['hot_rank'] = hot_rank
                card['hot_value'] = hot_value_int
                card['concept_tags'] = concept_tags
                card['popularity_tag'] = popularity_tag
                # 用同花顺实时涨跌幅覆盖（比行情快）
                if change is not None:
                    card['change'] = change
                results.append(card)
                continue
        except Exception:
            pass

        # 卡片分析失败 — 返回基础信息
        results.append({
            'code': code,
            'name': name,
            'hot_rank': hot_rank,
            'hot_value': hot_value_int,
            'change': change or 0,
            'price': None,
            'sector': '',
            'structure': '--',
            'stage': '--',
            'signal': 'hold',
            'trading_system': '3l',
            'buy_point': '',
            'stop_loss': None,
            'stop_loss_pct': None,
            'mainline_level': '',
            'concept_tags': concept_tags,
            'popularity_tag': popularity_tag,
            'triggered_signals': [],
            'fusion_type': '',
            'conclusion': '数据不足',
        })

    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    h.send_json({
        'stocks': results,
        'scan_time': scan_time,
        'total': len(results),
    })


def register_routes(routes):
    routes.exact('/api/hot-stocks', func=_handle_hot_stocks)
    return routes

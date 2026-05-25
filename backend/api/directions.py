"""方向管理 API 路由"""
import json
import os
import requests
from services.direction_service import (
    get_all, get_active, get_all_ordered, add, remove, set_active, get_suggestions,
    reorder,
)

INDUSTRY_MAP_PATH = os.environ.get('INDUSTRY_MAP_PATH',
    os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'stock_industry_map.json'))


def _load_industry_map():
    if not os.path.isfile(INDUSTRY_MAP_PATH):
        return {}
    with open(INDUSTRY_MAP_PATH) as f:
        return json.load(f)


def _get_stock_names():
    """从 all_stocks.json 加载股票名称"""
    sp = os.environ.get('ALL_STOCKS_PATH',
        os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'all_stocks_60d.json'))
    if not os.path.isfile(sp):
        return {}
    with open(sp) as f:
        data = json.load(f)
    names = {}
    stocks = data.get('stocks', data) if isinstance(data, dict) else data
    for sec, codes in (stocks.items() if isinstance(stocks, dict) else []):
        for code, kls in codes.items():
            if kls and isinstance(kls, list) and len(kls) > 0:
                names[code] = kls[0].get('name', '')
    return names


def _batch_realtime(codes):
    """批量获取实时行情（腾讯API），返回 {code: {price, change, change_pct}}"""
    results = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        qstr = ','.join(
            ('sh' + c if c.startswith(('6','9')) else 'sz' + c) for c in batch
        )
        try:
            r = requests.get(f'https://qt.gtimg.cn/q={qstr}',
                headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                timeout=5)
            text = r.text
            try:
                text = text.decode('gbk')
            except:
                pass
            for line in text.strip().split(';'):
                if not line.strip():
                    continue
                parts = line.split('~')
                if len(parts) >= 34:
                    code = parts[2] if len(parts) > 2 else ''
                    price = float(parts[3]) if parts[3] else 0
                    prev_close = float(parts[4]) if parts[4] else price
                    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                    change = round(price - prev_close, 2) if prev_close else 0
                    results[code] = {'price': price, 'change': change, 'change_pct': change_pct}
        except:
            pass
    return results


def _load_board_constituents():
    """加载板块成分股缓存"""
    path = '/home/ubuntu/data/3l/board_constituents.json'
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f)
        return data.get('boards', {})
    return {}


def _load_all_a_stocks():
    """加载全量A股股票列表 {code: name}"""
    path = os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'all_a_stocks.json')
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _handle_search_stocks(h, path):
    """搜索股票 — GET /api/directions/stocks?q=关键词"""
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(path).query)
    q = (qs.get('q', [''])[0]).strip().lower()
    if not q:
        h.send_json({'stocks': []})
        return

    imap = _load_industry_map()
    names = _load_all_a_stocks()  # 5317只全量A股
    boards = _load_board_constituents()

    matched = []
    seen = set()

    # 1. 搜索全量A股：匹配 code / name
    for code, name in names.items():
        if code in seen:
            continue
        if q in code.lower() or q in name.lower():
            seen.add(code)
            info = imap.get(code, {})
            matched.append({'code': code, 'name': name,
                'direction': info.get('direction', ''),
                'industry': info.get('ths_industry', '')})

    # 2. 搜索同花顺板块成分股映射
    for board_name, stocks in boards.items():
        if q in board_name.lower():
            for s in stocks:
                if s['code'] not in seen:
                    seen.add(s['code'])
                    code = s['code']
                    info = imap.get(code, {})
                    direction = info.get('direction', '')
                    industry = info.get('ths_industry', '')
                    matched.append({'code': code, 'name': names.get(code, ''), 'direction': direction, 'industry': industry})

    if not matched:
        # 3. 兜底：检查缓存中的同花顺行业/概念板块名
        board_cache_path = '/home/ubuntu/data/3l/board_names_cache.json'
        if os.path.isfile(board_cache_path):
            try:
                with open(board_cache_path) as f:
                    bc = json.load(f)
                # 行业板块
                for name in bc.get('industry', []):
                    if q in name.lower():
                        h.send_json({
                            'stocks': [], 'total': 0,
                            'board_info': {'name': name, 'type': 'industry',
                                'note': '该板块无成分股数据，建议按个股名称/代码搜索'}
                        })
                        return
                # 概念板块
                for name in bc.get('concept', []):
                    if q in name.lower():
                        h.send_json({
                            'stocks': [], 'total': 0,
                            'board_info': {'name': name, 'type': 'concept',
                                'note': '该板块无成分股数据，建议按个股名称/代码搜索'}
                        })
                        return
            except:
                pass

    if not matched:
        h.send_json({'stocks': [], 'total': 0})
        return

    codes = [m['code'] for m in matched]
    quotes = _batch_realtime(codes)

    stocks = []
    for m in matched:
        qq = quotes.get(m['code'], {})
        stocks.append({
            'code': m['code'],
            'name': m['name'],
            'direction': m['direction'],
            'industry': m['industry'],
            'price': qq.get('price', 0),
            'change': qq.get('change', 0),
            'change_pct': qq.get('change_pct', 0),
        })

    stocks.sort(key=lambda s: s['change_pct'], reverse=True)
    h.send_json({'stocks': stocks[:30], 'total': len(matched)})


def _handle_get_all(h, path):
    h.send_json({
        'directions': get_all(),
        'active': get_active(),
        'all': get_all_ordered(),
        'suggestions': get_suggestions(),
    })


def _handle_add(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        if name in ('全部', '其他'):
            h.send_json({'success': False, 'error': '不能添加系统保留方向'})
            return
        exist = get_all()
        if name in exist:
            h.send_json({'success': False, 'error': f'方向"{name}"已存在'})
            return
        r = add(name)
        h.send_json(r)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_remove(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        if name == '其他':
            h.send_json({'success': False, 'error': '不能删除"其他"方向'})
            return
        # 1. 从 directions.json 删除该方向
        from services.direction_service import remove as _remove_dir
        r = _remove_dir(name)
        if not r.get('success'):
            h.send_json(r)
            return
        # 2. 从 watchlist 删除该方向的所有股票
        removed = 0
        wl_path = '/home/ubuntu/data/3l/watchlist.json'
        if os.path.isfile(wl_path):
            with open(wl_path, 'r', encoding='utf-8') as f:
                wl = json.load(f)
            before = len(wl.get('stocks', []))
            wl['stocks'] = [s for s in wl.get('stocks', []) if s.get('direction') != name]
            removed = before - len(wl['stocks'])
            if removed > 0:
                from services.watchlist_service import save_watchlist
                save_watchlist(wl)
                from scripts.cache_layer import cache
                cache.invalidate('watchlist')
        h.send_json({'success': True, 'removed_stocks': removed})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_set_active(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        active = data.get('active', True)
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        r = set_active(name, active)
        h.send_json(r)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_reorder(h, path, body):
    try:
        data = json.loads(body)
        names = data.get('names', [])
        if not names or len(names) < 2:
            h.send_json({'success': False, 'error': '至少需要2个方向'})
            return
        r = reorder(names)
        h.send_json(r)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def register_routes(routes):
    routes.exact('/api/directions/get', func=_handle_get_all)
    routes.exact('/api/directions/stocks', func=_handle_search_stocks)
    return routes

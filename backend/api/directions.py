"""方向管理 API 路由"""
import json
import os
import requests
from services.direction_service import (
    get_all, get_active, add, remove, set_active, get_suggestions,
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


def _handle_search_stocks(h, path):
    """搜索股票 — GET /api/directions/stocks?q=关键词"""
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(path).query)
    q = (qs.get('q', [''])[0]).strip().lower()
    if not q:
        h.send_json({'stocks': []})
        return

    imap = _load_industry_map()
    names = _get_stock_names()

    matched = []
    seen = set()
    for code, info in imap.items():
        if code in seen:
            continue
        direction = info.get('direction', '')
        industry = info.get('ths_industry', '')
        name = names.get(code, '')
        # 匹配 code / direction / industry / name
        if q in code.lower() or q in direction.lower() or q in industry.lower() or q in name.lower():
            seen.add(code)
            matched.append({
                'code': code,
                'name': name,
                'direction': direction,
                'industry': industry,
            })
            if len(matched) >= 100:
                break

    if not matched:
        h.send_json({'stocks': []})
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
        r = remove(name)
        h.send_json(r)
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


def register_routes(routes):
    routes.exact('/api/directions/get', func=_handle_get_all)
    routes.exact('/api/directions/stocks', func=_handle_search_stocks)
    return routes

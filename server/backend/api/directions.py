"""方向管理 API 路由 — V2 分层 + 概念绑定"""
import json
import os
import sys
import requests
from urllib.parse import urlparse, parse_qs
from backend.core.logger import get_logger
from backend.core.exceptions import APIError
from backend.core.config import DATA_DIR

log = get_logger(__name__)
from backend.services.direction_service import (
    get_all, get_active, get_all_ordered, add, remove, set_active, get_suggestions,
    reorder,
    # V2 新接口
    get_categories, get_sub_directions,
    add_category, remove_category, set_category_enabled, reorder_categories,
    rename_category,
    add_sub_direction, remove_sub_direction, set_sub_direction_enabled,
    reorder_sub_directions, move_sub_direction, rename_sub_direction,
    bind_concept, unbind_concept, get_bound_concepts,
    search_concepts, parse_direction, format_direction,
    migrate_v1_to_v2,
)

INDUSTRY_MAP_PATH = os.environ.get('INDUSTRY_MAP_PATH',
    os.path.join(DATA_DIR, 'stock_industry_map.json'))


def _load_industry_map():
    if not os.path.isfile(INDUSTRY_MAP_PATH):
        return {}
    with open(INDUSTRY_MAP_PATH) as f:
        return json.load(f)


def _get_stock_names():
    """从 all_stocks.json 加载股票名称"""
    sp = os.environ.get('ALL_STOCKS_PATH',
        os.path.join(DATA_DIR, 'all_stocks_60d.json'))
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
    path = os.path.join(DATA_DIR, 'board_constituents.json')
    if os.path.isfile(path):
        with open(path) as f:
            data = json.load(f)
        return data.get('boards', {})
    return {}


def _load_all_a_stocks():
    """加载全量A股股票列表 {code: name}，缺失时自动从 all_stock_codes.json 生成"""
    path = os.path.join(DATA_DIR, 'all_a_stocks.json')
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    # 从 all_stock_codes.json 自动生成
    src = os.path.join(DATA_DIR, 'all_stock_codes.json')
    if os.path.isfile(src):
        try:
            data = json.load(open(src))
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            print(f'[directions] ⚡ 自动生成 all_a_stocks.json ({len(data)}只)', flush=True)
            return data
        except Exception:
            pass
    return {}


def _fetch_concept_stocks(name):
    """获取概念板块成分股（缓存优先，按需抓取）"""
    board_constituents_path = os.path.join(DATA_DIR, 'board_constituents.json')
    if os.path.isfile(board_constituents_path):
        try:
            with open(board_constituents_path) as f:
                bc_data = json.load(f)
            boards = bc_data.get('boards', bc_data)
            if name in boards:
                entry = boards[name]
                if isinstance(entry, dict) and 'stocks' in entry and entry['stocks']:
                    return entry['stocks']
                elif isinstance(entry, list) and entry:
                    return entry
        except:
            pass
    import requests as _req
    _h = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
    _base = 'https://push2test.eastmoney.com/api/qt/clist/get'
    try:
        _all_params = {
            'pn': '1', 'pz': '500', 'po': '1', 'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2', 'invt': '2', 'fid': 'f3',
            'fs': 'm:90 t:3 f:!50',
            'fields': 'f12,f14',
        }
        r = _req.get(_base, params=_all_params, headers=_h, timeout=10)
        r.raise_for_status()
        all_data = r.json()
        board_code = None
        for item in all_data.get('data', {}).get('diff', []):
            if item.get('f14') == name:
                board_code = item.get('f12')
                break
        if not board_code:
            return []
        _stk_params = {
            'pn': '1', 'pz': '200', 'po': '1', 'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2', 'invt': '2', 'fid': 'f3',
            'fs': f'b:{board_code} f:!50',
            'fields': 'f12,f14',
        }
        r2 = _req.get(_base, params=_stk_params, headers=_h, timeout=10)
        r2.raise_for_status()
        stk_data = r2.json()
        stks = []
        for item in stk_data.get('data', {}).get('diff', []):
            code = str(item.get('f12', ''))
            if code.startswith('BK'):
                continue
            stks.append({'code': code, 'name': item.get('f14', ''), 'industry': ''})
        if stks:
            try:
                with open(board_constituents_path) as f:
                    all_boards = json.load(f)
                all_boards.setdefault('boards', {})[name] = {'type': 'concept', 'stocks': stks}
                json.dump(all_boards, open(board_constituents_path, 'w'), ensure_ascii=False, indent=2)
            except:
                pass
        return stks
    except Exception as e:
        import logging
        logging.getLogger('server').error(f'概念板块抓取失败 [{name}]: {e}')
        return []


def _handle_search_stocks(h, path):
    """搜索股票 — GET /api/directions/stocks?q=关键词"""
    qs = parse_qs(urlparse(path).query)
    q = (qs.get('q', [''])[0]).strip().lower()
    if not q:
        h.send_json({'stocks': []})
        return

    imap = _load_industry_map()
    names = _load_all_a_stocks()
    boards = _load_board_constituents()

    matched = []
    seen = set()

    board_cache_path = os.path.join(DATA_DIR, 'board_names_cache.json')
    if os.path.isfile(board_cache_path):
        try:
            with open(board_cache_path) as f:
                bc = json.load(f)
            for name in bc.get('industry', []):
                if q in name.lower():
                    break
            for name in bc.get('concept', []):
                if q in name.lower():
                    stocks_data = _fetch_concept_stocks(name)
                    if stocks_data:
                        codes = [s['code'] for s in stocks_data]
                        quotes = _batch_realtime(codes)
                        matched = []
                        for s in stocks_data:
                            qq = quotes.get(s['code'], {})
                            info = imap.get(s['code'], {})
                            matched.append({
                                'code': s['code'], 'name': s['name'],
                                'direction': info.get('direction', ''),
                                'industry': info.get('ths_industry', s.get('industry', '')),
                                'price': qq.get('price', 0), 'change': qq.get('change', 0),
                                'change_pct': qq.get('change_pct', 0),
                            })
                        matched.sort(key=lambda x: x['change_pct'], reverse=True)
                        h.send_json({'stocks': matched[:30], 'total': len(matched)})
                        return
        except:
            pass

    for code, name in names.items():
        if code in seen:
            continue
        if q in code.lower() or q in name.lower():
            seen.add(code)
            info = imap.get(code, {})
            matched.append({'code': code, 'name': name,
                'direction': info.get('direction', ''),
                'industry': info.get('ths_industry', '')})

    if not matched or len(matched) < 20:
        pinyin_path = os.path.join(DATA_DIR, 'pinyin_initials.json')
        if not os.path.isfile(pinyin_path):
            # 缺失时从 names 自动生成拼音首字母映射
            try:
                from pypinyin import pinyin as _py, Style as _Style
                if names:
                    py_map = {}
                    for c, n in names.items():
                        py_map[c] = ''.join(p[0][0].upper() for p in _py(n, style=_Style.FIRST_LETTER))
                    with open(pinyin_path, 'w', encoding='utf-8') as _f:
                        json.dump(py_map, _f, ensure_ascii=False, separators=(',', ':'))
                    print(f'[directions] ⚡ 自动生成 pinyin_initials.json ({len(py_map)}只)', flush=True)
            except Exception:
                pass
        if os.path.isfile(pinyin_path):
            try:
                pinyin_map = json.load(open(pinyin_path))
                for code, initials in pinyin_map.items():
                    if code not in seen and q in initials.lower():
                        seen.add(code)
                        name = names.get(code, '')
                        info = imap.get(code, {})
                        matched.append({'code': code, 'name': name,
                            'direction': info.get('direction', ''),
                            'industry': info.get('ths_industry', '')})
            except:
                pass

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
        board_cache_path = os.path.join(DATA_DIR, 'board_names_cache.json')
        if os.path.isfile(board_cache_path):
            try:
                with open(board_cache_path) as f:
                    bc = json.load(f)
                for name in bc.get('industry', []):
                    if q in name.lower():
                        h.send_json({
                            'stocks': [], 'total': 0,
                            'board_info': {'name': name, 'type': 'industry',
                                'note': '该行业板块无成分股数据，建议按个股名称/代码搜索'}
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


# ═══════════════════════════════════════════════════════════
# GET /api/directions/get — 完整状态快照
# ═══════════════════════════════════════════════════════════

def _handle_get(h, path):
    """返回 categories（数组格式）, sub_directions（含 concepts 数组）, active, version"""
    cat_dict = get_categories()
    sub_dirs = get_sub_directions()
    # 将 dict {name: {order, enabled}} 转为前端需要的数组格式 [{name, order, enabled, sub_count}]
    categories_arr = []
    for name, info in sorted(cat_dict.items(), key=lambda x: x[1].get('order', 0)):
        sub_count = sum(1 for sd in sub_dirs.values() if sd.get('category') == name)
        categories_arr.append({
            'name': name,
            'enabled': info.get('enabled', True),
            'sub_count': sub_count,
            'order': info.get('order', 0),
        })
    # 给每个 sub_direction 补上 concepts 数组（前端需要）
    for key, sd in sub_dirs.items():
        codes = sd.get('concept_codes', [])
        names = sd.get('concept_names', [])
        sd['concepts'] = [
            {'code': codes[i], 'name': names[i]} if i < len(names) else {'code': codes[i], 'name': codes[i]}
            for i in range(len(codes))
        ]
    h.send_json({
        'categories': categories_arr,
        'sub_directions': sub_dirs,
        'active': get_active(),
        'version': 2,
    })


# ═══════════════════════════════════════════════════════════
# CATEGORY 端点
# ═══════════════════════════════════════════════════════════

def _handle_category_add(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '分类名称不能为空'})
            return
        r = add_category(name)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_category_remove(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '分类名称不能为空'})
            return
        r = remove_category(name)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_category_toggle(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        enabled = data.get('enabled', True)
        if not name:
            h.send_json({'success': False, 'error': '分类名称不能为空'})
            return
        r = set_category_enabled(name, enabled)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_category_reorder(h, path, body):
    try:
        data = json.loads(body)
        names = data.get('names', [])
        if not names:
            h.send_json({'success': False, 'error': '分类列表不能为空'})
            return
        r = reorder_categories(names)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_category_rename(h, path, body):
    """POST /api/directions/category/rename — 重命名大类"""
    try:
        data = json.loads(body)
        old_name = data.get('old_name', '').strip()
        new_name = data.get('new_name', '').strip()
        if not old_name:
            h.send_json({'success': False, 'error': '原名称不能为空'})
            return
        if not new_name:
            h.send_json({'success': False, 'error': '新名称不能为空'})
            return
        r = rename_category(old_name, new_name)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# SUB_DIRECTION 端点
# ═══════════════════════════════════════════════════════════

def _handle_sub_add(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        category = data.get('category', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '细分方向名称不能为空'})
            return
        if not category:
            h.send_json({'success': False, 'error': '所属分类不能为空'})
            return
        # order 参数暂不支持，服务端自动计算
        r = add_sub_direction(category, name)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_sub_remove(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '细分方向名称不能为空'})
            return
        # name 为完整名称 "科技.半导体"，解析出分类和子方向名
        cat, sub = parse_direction(name)
        if not cat:
            h.send_json({'success': False, 'error': '名称格式错误，需要完整路径如"科技.半导体"'})
            return
        r = remove_sub_direction(cat, sub)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_sub_toggle(h, path, body):
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        enabled = data.get('enabled', True)
        if not name:
            h.send_json({'success': False, 'error': '细分方向名称不能为空'})
            return
        cat, sub = parse_direction(name)
        if not cat:
            h.send_json({'success': False, 'error': '名称格式错误，需要完整路径如"科技.半导体"'})
            return
        r = set_sub_direction_enabled(cat, sub, enabled)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_sub_reorder(h, path, body):
    try:
        data = json.loads(body)
        names = data.get('names', [])
        if not names:
            h.send_json({'success': False, 'error': '细分方向列表不能为空'})
            return
        # 从第一个完整名称提取分类
        cat, _ = parse_direction(names[0])
        if not cat:
            h.send_json({'success': False, 'error': '名称格式错误，需要完整路径如"科技.半导体"'})
            return
        r = reorder_sub_directions(cat, names)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_sub_move(h, path, body):
    """POST /api/directions/sub/move — 将细分方向移动到另一个大类"""
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        new_category = data.get('new_category', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '细分方向完整名称不能为空'})
            return
        if not new_category:
            h.send_json({'success': False, 'error': '目标分类名称不能为空'})
            return
        cat, sub = parse_direction(name)
        if not cat:
            cat = '未分类'
        r = move_sub_direction(cat, sub, new_category)
        if r.get('success'):
            h.send_json({'success': True, 'old_key': name, 'new_key': r['new_key']})
        else:
            h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_sub_rename(h, path, body):
    """POST /api/directions/sub/rename — 重命名细分方向"""
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        new_name = data.get('new_name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '原名称不能为空'})
            return
        if not new_name:
            h.send_json({'success': False, 'error': '新名称不能为空'})
            return
        cat, sub = parse_direction(name)
        if not cat:
            cat = '未分类'
        r = rename_sub_direction(cat, sub, new_name)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# 概念绑定端点
# ═══════════════════════════════════════════════════════════

def _handle_bind(h, path, body):
    try:
        data = json.loads(body)
        sub_dir = data.get('sub_dir', '').strip()
        concept_code = data.get('concept_code', '').strip()
        if not sub_dir:
            h.send_json({'success': False, 'error': 'sub_dir 不能为空'})
            return
        if not concept_code:
            h.send_json({'success': False, 'error': 'concept_code 不能为空'})
            return
        cat, sub = parse_direction(sub_dir)
        if not cat:
            h.send_json({'success': False, 'error': 'sub_dir 格式错误，需要完整路径如"科技.半导体"'})
            return
        r = bind_concept(cat, sub, concept_code)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


def _handle_unbind(h, path, body):
    try:
        data = json.loads(body)
        sub_dir = data.get('sub_dir', '').strip()
        concept_code = data.get('concept_code', '').strip()
        if not sub_dir:
            h.send_json({'success': False, 'error': 'sub_dir 不能为空'})
            return
        if not concept_code:
            h.send_json({'success': False, 'error': 'concept_code 不能为空'})
            return
        cat, sub = parse_direction(sub_dir)
        if not cat:
            h.send_json({'success': False, 'error': 'sub_dir 格式错误，需要完整路径如"科技.半导体"'})
            return
        r = unbind_concept(cat, sub, concept_code)
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# GET /api/directions/concepts/search?q=xxx
# ═══════════════════════════════════════════════════════════

def _handle_concepts_search(h, path):
    try:
        qs = parse_qs(urlparse(path).query)
        q = qs.get('q', [''])[0].strip()
        results = search_concepts(q)
        # 转成 [{code, name}] 格式（stock_count 来自 push2 不准确，不返回）
        items = []
        for code, info in results.items():
            if isinstance(info, dict):
                items.append({'code': code, 'name': info.get('name', code)})
            else:
                items.append({'code': code, 'name': info})
        h.send_json({'results': items})
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# POST /api/directions/migrate — V1→V2 迁移
# ═══════════════════════════════════════════════════════════

def _handle_migrate(h, path, body):
    try:
        r = migrate_v1_to_v2()
        h.send_json(r)
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# 旧接口兼容处理（已重写为调用 V2 服务）
# ═══════════════════════════════════════════════════════════

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
        raise APIError(f"方向管理操作异常: {e}") from e


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
        if not r.get('success'):
            h.send_json(r)
            return
        # 从 watchlist 删除该方向的所有股票
        removed = 0
        wl_path = os.path.join(DATA_DIR, 'watchlist.json')
        if os.path.isfile(wl_path):
            with open(wl_path, 'r', encoding='utf-8') as f:
                wl = json.load(f)
            before = len(wl.get('stocks', []))
            wl['stocks'] = [s for s in wl.get('stocks', []) if s.get('direction') != name]
            removed = before - len(wl['stocks'])
            if removed > 0:
                from backend.services.watchlist_service import save_watchlist
                save_watchlist(wl)
                from backend.data_access.cache_layer import cache
                cache.invalidate('watchlist')
        h.send_json({'success': True, 'removed_stocks': removed})
    except Exception as e:
        raise APIError(f"方向管理操作异常: {e}") from e


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
        raise APIError(f"方向管理操作异常: {e}") from e


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
        raise APIError(f"方向管理操作异常: {e}") from e


# ═══════════════════════════════════════════════════════════
# 路由注册
# ═══════════════════════════════════════════════════════════

def register_routes(routes):
    # GET 路由（通过 RouteRegistry）
    routes.exact('/api/directions/get', func=_handle_get)
    routes.exact('/api/directions/stocks', func=_handle_search_stocks)
    routes.exact('/api/directions/concepts/search', func=_handle_concepts_search)
    return routes

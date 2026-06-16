"""
趋势候选扫描 — 从主线/次级主线 THS 行业扫描全市场候选股票
返回 signalStockCard 兼容的完整个股分析数据
同时生成 trend_ 趋势交易SVG图表

性能优化：只拉目标行业的股票K线，不走全量 get_all_stocks()
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.core.logger import get_logger
from backend.data_access.data_layer import _load_json
from backend.core.ema_utils import ema_list, get_structure, get_stage
from backend.core.gen_trend_chart import gen_trend_svg
from backend.core.trend_trading import _load_manual_trend
from backend.core import config

INDUSTRY_MAP_PATH = config.INDUSTRY_MAP_PATH
MANUAL_TREND_PATH = config.MANUAL_TREND_PATH
WATCHLIST_PATH = config.WATCHLIST_PATH
REVIEW_CHARTS_DIR = config.REVIEW_CHARTS_DIR

log = get_logger(__name__)


def _ensure_suffix(code):
    """6位纯数字代码 → 含后缀代码（用于MySQL查询）"""
    if '.' in code:
        return code
    if code.startswith('6'):
        return f'{code}.SH'
    return f'{code}.SZ'


# 进程级缓存（热点追踪页面频繁刷新时避免重复DB查询）
_batch_klines_cache = {'data': {}, 'ts': 0}
_BATCH_CACHE_TTL = 30


def _batch_fetch_klines(codes_list):
    """批量从DB拉取K线数据（含前复权），返回 {code: [升序排列的K线]}

    使用 threel_core/db.py（单连接批量查询），比 TushareDB 快10倍+。
    带30s进程级缓存。
    """
    if not codes_list:
        return {}
    now = time.time()
    if now - _batch_klines_cache['ts'] < _BATCH_CACHE_TTL:
        cached = _batch_klines_cache['data']
        if all(c in cached for c in codes_list):
            return {c: cached.get(c, []) for c in codes_list}
    from threel_core.db import query_stock_klines
    lookup = [_ensure_suffix(c) for c in codes_list]
    ts_code_map = {_ensure_suffix(c): c for c in codes_list}
    raw = query_stock_klines(lookup, limit=60)
    # 转换回纯数字代码
    klines_map = {}
    for ts, kls in raw.items():
        code = ts_code_map.get(ts, ts)
        klines_map[code] = kls
    # 补充股票名称
    from backend.data_access.data_layer import get_stock_names_from_db
    names = get_stock_names_from_db(codes_list)
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    result = {}
    for code in codes_list:
        kls = klines_map.get(code, [])
        if kls:
            name = names.get(code, '')
            if not name:
                info = imap.get(code, {})
                name = info.get('name', '') if isinstance(info, dict) else ''
            if name:
                for k in kls:
                    k['name'] = name
            result[code] = sorted(kls, key=lambda x: x['date'])  # 确保升序（防御 _apply_qfq_batch 不一致）
    # 写缓存
    _batch_klines_cache['data'] = result
    _batch_klines_cache['ts'] = time.time()
    return result


def scan_trend_candidates(main_line_names, sub_main_names):
    """扫描主线+次级主线，返回完整个股分析数据"""
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    manual = _load_manual_trend()

    # 收集目标行业的所有股票代码（避免拉全量自选股K线）
    target_names = set(main_line_names + sub_main_names)
    target_codes = []
    for code, info in imap.items():
        ths = info.get('ths_industry', '') if isinstance(info, dict) else ''
        if ths in target_names:
            target_codes.append(code)

    # 只拉目标股票的K线，不走 get_all_stocks()
    all_s = _batch_fetch_klines(target_codes)

    result = {
        'main_lines': _scan_industries(main_line_names, imap, all_s, manual),
        'sub_main_lines': _scan_industries(sub_main_names, imap, all_s, manual),
    }
    total = sum(len(g['candidates']) for g in result['main_lines']) + \
            sum(len(g['candidates']) for g in result['sub_main_lines'])
    result['count'] = total
    return result


def _scan_industries(industry_names, imap, all_s, manual):
    """扫描一组THS行业，返回 [{industry, candidates}]"""
    groups = {}
    for code, info in imap.items():
        ths = info.get('ths_industry', '')
        if ths in industry_names:
            groups.setdefault(ths, []).append((code, info))

    out = []
    for ind in industry_names:
        stocks = groups.get(ind, [])
        if not stocks:
            continue
        candidates = []
        for code, info in stocks:
            kls = all_s.get(code, [])
            if not kls or len(kls) < 30:
                continue

            closes = [k['close'] for k in kls]
            structure = get_structure(closes)
            if structure != '上涨趋势':
                continue

            ema5 = ema_list(closes, 5)
            ema5_vals = [v for v in ema5 if v is not None]
            if len(ema5_vals) < 6:
                continue

            slope = round((ema5_vals[-1] - ema5_vals[-6]) / ema5_vals[-6] * 100, 2)
            if slope <= 3.0:
                continue

            name = kls[0].get('name', code) if kls else code
            direction = info.get('direction', '')
            cur_close = closes[-1]
            ema5_last = ema5[-1] if ema5[-1] else cur_close
            cur_b5 = round((cur_close - ema5_last) / ema5_last * 100, 2)
            change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0

            highs = [k['high'] for k in kls]
            lows = [k['low'] for k in kls]
            vols = [k.get('volume', k.get('vol', 0)) for k in kls]
            stage = get_stage(closes, structure, highs, lows, volumes=vols)

            signal = 'hold'
            try:
                from backend.services.stock_card_service import get_stock_card
                _today = kls[-1]['date']
                _today_fmt = f'{_today[:4]}-{_today[4:6]}-{_today[6:8]}'
                _card = get_stock_card(code, _today_fmt, klines=kls)
                signal = _card.get('signal', 'hold')
            except Exception:
                log.warning('个股信号获取失败（趋势候选扫描）: %s', code)
                pass

            in_manual = code in manual
            trading_system = 'trend' if in_manual else '3l'

            _gen_chart(name, code, kls, cur_b5)

            candidates.append({
                'name': name,
                'code': code,
                'price': cur_close,
                'change': change_pct,
                'signal': signal,
                'structure': structure,
                'stage': stage,
                'sector': ind,
                'direction': direction,
                'trading_system': trading_system,
                'trading_reason': '手动指定趋势交易' if in_manual else '3L体系',
                'trend_bias': cur_b5,
                'ema5_slope': slope,
                'in_manual': in_manual,
            })

        candidates.sort(key=lambda x: x.get('ema5_slope', 0), reverse=True)
        out.append({'industry': ind, 'candidates': candidates})

    return out


def _gen_chart(name, code, klines, bias5):
    """生成趋势交易SVG（如不存在）"""
    out_path = os.path.join(REVIEW_CHARTS_DIR, f'trend_{code}.svg')
    if not os.path.exists(out_path):
        try:
            gen_trend_svg(name, code, klines, out_path, trend_bias=bias5)
        except Exception as e:
            print(f'[trend_candidates] SVG生成失败 {code}: {e}')


def toggle_trend_stock(code, enable):
    manual = set(_load_manual_trend())
    changed = False
    if enable and code not in manual:
        manual.add(code)
        changed = True
        _ensure_in_watchlist(code)
        _set_watchlist_trading_system(code, 'trend')
    elif not enable and code in manual:
        manual.discard(code)
        changed = True
        _set_watchlist_trading_system(code, '3l')
    if changed:
        config.atomic_json_dump(sorted(manual), MANUAL_TREND_PATH)
    return {'success': True, 'in_manual': code in manual}


def _set_watchlist_trading_system(code, system):
    try:
        wl = _load_json(WATCHLIST_PATH, {'stocks': []})
        for s in wl.get('stocks', []):
            if s['code'] == code:
                s['trading_system'] = system
                if system == 'trend':
                    s['trend_stock'] = True
                else:
                    s.pop('trend_stock', None)
                with open(WATCHLIST_PATH, 'w') as f:
                    json.dump(wl, f, ensure_ascii=False, indent=2)
                return
    except Exception:
        log.warning('趋势标记写入失败（自选股）')
        pass


def _ensure_in_watchlist(code):
    try:
        wl = _load_json(WATCHLIST_PATH, {'stocks': []})
        existing = {s['code'] for s in wl.get('stocks', [])}
        if code in existing:
            return
        imap = _load_json(INDUSTRY_MAP_PATH, {})
        info = imap.get(code, {})
        name = info.get('name', '')
        if not name:
            from backend.data_access.data_layer import get_stock_names_from_db
            names = get_stock_names_from_db([code])
            name = names.get(code, code)
        wl['stocks'].append({
            'code': code,
            'name': name or code,
            'direction': info.get('direction', ''),
            'industry': info.get('ths_industry', ''),
        })
        with open(WATCHLIST_PATH, 'w') as f:
            json.dump(wl, f, ensure_ascii=False, indent=2)
    except Exception:
        log.warning('自选股自动添加失败: %s', code)
        pass


def get_tracked_stocks():
    """返回已手动标记趋势交易的股票完整分析数据（不经过主线筛选）"""
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    manual = _load_manual_trend()

    codes_list = sorted(manual)
    if not codes_list:
        return {'count': 0, 'candidates': []}

    all_s = _batch_fetch_klines(codes_list)

    candidates = []
    for code in codes_list:
        info = imap.get(code, {})
        kls = all_s.get(code, [])
        if not kls or len(kls) < 30:
            candidates.append({
                'name': info.get('code', code) if isinstance(info, dict) else code, 'code': code,
                'price': 0, 'change': 0, 'signal': 'hold',
                'structure': '--', 'stage': '--',
                'sector': info.get('ths_industry', '') if isinstance(info, dict) else '',
                'direction': info.get('direction', '') if isinstance(info, dict) else '',
                'trading_system': 'trend',
                'trading_reason': '手动指定趋势交易',
                'trend_bias': 0,
                'ema5_slope': 0,
                'in_manual': True,
            })
            continue

        closes = [k['close'] for k in kls]
        structure = get_structure(closes)
        ema5 = ema_list(closes, 5)
        ema5_vals = [v for v in ema5 if v is not None]
        ema5_last = ema5[-1] if ema5[-1] else closes[-1]
        cur_b5 = round((closes[-1] - ema5_last) / ema5_last * 100, 2)
        change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0
        slope = round((ema5_vals[-1] - ema5_vals[-6]) / ema5_vals[-6] * 100, 2) if len(ema5_vals) >= 6 else 0

        highs = [k['high'] for k in kls]
        lows = [k['low'] for k in kls]
        vols = [k.get('volume', k.get('vol', 0)) for k in kls]
        stage = get_stage(closes, structure, highs, lows, volumes=vols)

        name = kls[0].get('name', code) if kls else code

        signal = 'hold'
        try:
            from backend.services.stock_card_service import get_stock_card
            _today = kls[-1]['date']
            _today_fmt = f'{_today[:4]}-{_today[4:6]}-{_today[6:8]}'
            _card = get_stock_card(code, _today_fmt, klines=kls)
            signal = _card.get('signal', 'hold')
        except Exception:
            log.warning('个股信号获取失败（跟踪趋势）: %s', code)
            pass

        _gen_chart(name, code, kls, cur_b5)

        candidates.append({
            'name': name, 'code': code,
            'price': closes[-1], 'change': change_pct,
            'signal': signal, 'structure': structure, 'stage': stage,
            'sector': info.get('ths_industry', '') if isinstance(info, dict) else '',
            'direction': info.get('direction', '') if isinstance(info, dict) else '',
            'trading_system': 'trend',
            'trading_reason': '手动指定趋势交易',
            'trend_bias': cur_b5,
            'ema5_slope': slope,
            'in_manual': True,
        })

    return {'count': len(candidates), 'candidates': candidates}

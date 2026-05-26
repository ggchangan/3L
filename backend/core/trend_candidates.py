"""
趋势候选扫描 — 从主线/次级主线 THS 行业扫描全市场候选股票
返回 signalStockCard 兼容的完整个股分析数据
同时生成 trend_ 趋势交易SVG图表
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.config import DATA_DIR
from backend.core.data_layer import _load_json
from backend.core.ema_utils import ema_list, get_structure, get_stage
from backend.core.gen_trend_chart import gen_trend_svg
from backend.core.trend_trading import _load_manual_trend
from backend import config

DATA_DIR = config.DATA_DIR
INDUSTRY_MAP_PATH = config.INDUSTRY_MAP_PATH
ALL_STOCKS_PATH = config.ALL_STOCKS_PATH
MANUAL_TREND_PATH = config.MANUAL_TREND_PATH
WATCHLIST_PATH = config.WATCHLIST_PATH
REVIEW_CHARTS_DIR = config.REVIEW_CHARTS_DIR


def scan_trend_candidates(main_line_names, sub_main_names):
    """扫描主线+次级主线，返回完整个股分析数据"""
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    all_s = _load_json(ALL_STOCKS_PATH, {}).get('stocks', {})
    manual = _load_manual_trend()

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
            kls = _find_klines(code, all_s)
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

            # 阶段
            highs = [k['high'] for k in kls]
            lows = [k['low'] for k in kls]
            vols = [k.get('volume', k.get('vol', 0)) for k in kls]
            stage = get_stage(closes, structure, highs, lows, volumes=vols)

            # 信号（使用统一的 bias5 区域判定，与复盘页 get_bias5_zone 一致）
            signal = 'hold'
            try:
                from backend.core.trend_trading import get_bias5_zone
                _idx = len(klines) - 1
                _zone, _ = get_bias5_zone(klines, _idx)
                if _zone == '买入':
                    signal = 'buy'
                elif _zone == '卖出':
                    signal = 'sell'
            except Exception:
                pass

            in_manual = code in manual
            trading_system = 'trend' if in_manual else '3l'

            # 生成趋势SVG图表
            _gen_chart(name, code, kls, cur_b5)

            candidates.append({
                # signalStockCard 基础字段
                'name': name,
                'code': code,
                'price': cur_close,
                'change': change_pct,
                'signal': signal,
                'structure': structure,
                'stage': stage,
                'sector': ind,            # 同花顺行业板块名
                'direction': direction,    # 用户的8大方向
                'trading_system': trading_system,
                'trading_reason': '手动指定趋势交易' if in_manual else '3L体系',
                'trend_bias': cur_b5,
                # 额外字段
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


def _find_klines(code, all_s):
    for sec, codes in all_s.items():
        if code in codes:
            return codes[code]
    return []
def toggle_trend_stock(code, enable):
    manual = set(_load_manual_trend())
    changed = False
    if enable and code not in manual:
        manual.add(code)
        changed = True
        # 标记为趋势股时，自动加入自选股（如不在）
        _ensure_in_watchlist(code)
        # 同步更新 watchlist 里的 trading_system 字段
        _set_watchlist_trading_system(code, 'trend')
    elif not enable and code in manual:
        manual.discard(code)
        changed = True
        # 取消趋势时恢复 watchlist 里的 trading_system 字段
        _set_watchlist_trading_system(code, '3l')
    if changed:
        with open(MANUAL_TREND_PATH, 'w') as f:
            json.dump(sorted(manual), f)
    return {'success': True, 'in_manual': code in manual}


def _set_watchlist_trading_system(code, system):
    """同步 watchlist 中个股的 trading_system 字段"""
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
        pass


def _ensure_in_watchlist(code):
    """确保股票在自选股列表中，不在则自动添加"""
    try:
        wl = _load_json(WATCHLIST_PATH, {'stocks': []})
        existing = {s['code'] for s in wl.get('stocks', [])}
        if code in existing:
            return  # 已在自选股中
        # 查行业映射获取名称/方向/行业
        imap = _load_json(INDUSTRY_MAP_PATH, {})
        info = imap.get(code, {})
        name = info.get('name', '')
        if not name:
            # 从K线数据取
            all_s = _load_json(ALL_STOCKS_PATH, {}).get('stocks', {})
            for sec, ss in all_s.items():
                if code in ss and ss[code]:
                    name = ss[code][0].get('name', code)
                    break
        wl['stocks'].append({
            'code': code,
            'name': name or code,
            'direction': info.get('direction', ''),
            'industry': info.get('ths_industry', ''),
        })
        with open(WATCHLIST_PATH, 'w') as f:
            json.dump(wl, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_tracked_stocks():
    """返回已手动标记趋势交易的股票完整分析数据（不经过主线筛选）"""
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    all_s = _load_json(ALL_STOCKS_PATH, {}).get('stocks', {})
    manual = _load_manual_trend()

    candidates = []
    for code in sorted(manual):
        info = imap.get(code, {})
        kls = _find_klines(code, all_s)
        if not kls or len(kls) < 30:
            # 数据不足仍返回基本信息
            candidates.append({
                'name': info.get('code', code), 'code': code,
                'price': 0, 'change': 0, 'signal': 'hold',
                'structure': '--', 'stage': '--',
                'sector': info.get('ths_industry', ''),
                'direction': info.get('direction', ''),
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

        # 信号（使用统一的趋势交易信号判定，与复盘页一致）
        signal = 'hold'
        try:
            from backend.core.trend_trading import check_trend_type, get_bias5_zone, get_bias10_zone
            _idx = len(klines) - 1
            _tt = check_trend_type(klines, _idx)
            if _tt.get('trend_type'):
                if _tt.get('trend_5d'):
                    _zone, _ = get_bias5_zone(klines, _idx)
                else:
                    _zone, _ = get_bias10_zone(klines, _idx)
                if _zone == '买入':
                    signal = 'buy'
                elif _zone == '卖出':
                    signal = 'sell'
        except Exception:
            pass

        # 更新SVG
        _gen_chart(name, code, kls, cur_b5)

        candidates.append({
            'name': name, 'code': code,
            'price': closes[-1], 'change': change_pct,
            'signal': signal, 'structure': structure, 'stage': stage,
            'sector': info.get('ths_industry', ''),
            'direction': info.get('direction', ''),
            'trading_system': 'trend',
            'trading_reason': '手动指定趋势交易',
            'trend_bias': cur_b5,
            'ema5_slope': slope,
            'in_manual': True,
        })

    # 无行业分组，统一返回
    return {'count': len(candidates), 'candidates': candidates}

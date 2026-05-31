"""概念板块波谷追踪 API 路由"""
import json, os, sys, statistics
from datetime import datetime

from backend.services.concept_wave_service import judge_concept_wave
from backend.core.data_layer import (
    get_sector_daily, get_concept_list, get_stock_concept_map,
    get_watchlist,
)


def _today_str():
    return datetime.now().strftime('%Y-%m-%d')


def _now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _make_response(handler, path):
    """
    GET /api/concept-wave — 返回概念板块波谷追踪数据

    Query 参数:
      sort_by: vl_score / name / change_5d (默认 vl_score)
      group_by: stage / none (默认 stage)
      date: YYYY-MM-DD (可选，回溯历史)
    """
    # 解析查询参数
    qs = {}
    if '?' in path:
        parts = path.split('?', 1)[1].split('&')
        for p in parts:
            if '=' in p:
                k, v = p.split('=', 1)
                qs[k] = v

    sort_by = qs.get('sort_by', 'vl_score')
    group_by = qs.get('group_by', 'stage')
    target_date = qs.get('date', _today_str())

    # 读取数据
    sector_data = get_sector_daily()
    concepts_kline = sector_data.get('concepts', {})

    if not concepts_kline:
        # 回退到 Mock 数据
        mock_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'mock', 'concept-wave.json'
        )
        real = os.path.realpath(mock_path)
        if os.path.isfile(real):
            with open(real) as f:
                handler.send_json(json.load(f))
            return
        handler.send_json({'success': False, 'error': '暂无概念板块数据'})
        return

    concept_list = get_concept_list()
    stock_concept_map = get_stock_concept_map()
    watchlist = get_watchlist()
    watchlist_codes = set(s.get('code', '') for s in watchlist)

    # 筛选：只处理有K线且存在追踪列表中的概念（取自选股涉及的概念）
    results = []
    for code, cinfo in concept_list.items():
        name = cinfo.get('name', '')
        klines = concepts_kline.get(name)
        if not klines or len(klines) < 20:
            continue

        score = judge_concept_wave(klines)

        # 关联自选股
        related_stocks = []
        related_codes = []
        for scode, sinfo in stock_concept_map.items():
            if code in sinfo.get('concept_codes', []) and scode in watchlist_codes:
                related_stocks.append(sinfo.get('name', scode))
                related_codes.append(scode)

        # 近5日涨跌
        if len(klines) >= 5:
            close_now = klines[-1]['close']
            close_5d_ago = klines[-5]['close']
            change_5d = (close_now - close_5d_ago) / close_5d_ago * 100
        else:
            change_5d = 0

        # vs 中证全指（暂用概念自身走势近似）
        vs_market_5d = 0
        vs_market_20d = 0

        # 走势数据（归一化到50±25范围）
        if len(klines) >= 30:
            wave_seg = klines[-30:]
        elif len(klines) >= 10:
            wave_seg = klines
        else:
            wave_seg = klines
        base = wave_seg[0]['close'] if wave_seg else 1
        wave_data = []
        for wk in wave_seg:
            normalized = (wk['close'] / base) * 100 if base > 0 else 50
            wave_data.append({
                'date': wk.get('date', ''),
                'normalized': round(normalized, 2),
                'change_pct': round((wk['close'] - wave_seg[0]['close']) / wave_seg[0]['close'] * 100, 2) if wave_seg else 0,
                'volume_ratio': wk.get('volume', 0) / 1,
            })

        results.append({
            'code': code,
            'name': name,
            'stage': score['stage'],
            'vl_score': score['vl_score'],
            'pk_score': score['pk_score'],
            'bias20': score['bias20'],
            'bias5': score['bias5'],
            'change_5d': round(change_5d, 2),
            'change_1d': score.get('change_pct', 0),
            'volume_ratio': score['volume_ratio'],
            'volume_signal': score['volume_signal'],
            'entry_window': score['entry_window'],
            'ema10_slope': score['ema10_slope'],
            'two_sigma': score['two_sigma'],
            'mainline_rank': None,
            'mainline_badge': None,
            'vs_market_5d': round(vs_market_5d, 2),
            'vs_market_20d': round(vs_market_20d, 2),
            'historical_gain': None,
            'last_peak_date': None,
            'last_trough_date': None,
            'cycle_days': None,
            'cycle_count': 0,
            'related_stocks': related_stocks[:3],
            'related_count': len(related_stocks),
            'related_codes': related_codes[:3],
            'stock_count': cinfo.get('stock_count', 0),
            'wave_data': wave_data,
            'annotations': [],
        })

    # 排序
    if sort_by == 'vl_score':
        results.sort(key=lambda r: -r['vl_score'])
    elif sort_by == 'name':
        results.sort(key=lambda r: r['name'])
    elif sort_by == 'change_5d':
        results.sort(key=lambda r: r['change_5d'])

    # 分组
    grouped = {'valley': [], 'mid': [], 'declining': []}
    for r in results:
        if r['stage'] == '波谷':
            grouped['valley'].append(r)
        elif r['stage'] == '波中':
            grouped['mid'].append(r)
        else:
            grouped['declining'].append(r)

    # 统计
    s = {
        'total': len(results),
        'valley': len(grouped['valley']),
        'mid': len(grouped['mid']),
        'declining': len(grouped['declining']),
        'alerts_count': sum(1 for r in results if r['vl_score'] >= 3),
        'new_this_week': 0,
    }

    # 告警
    alerts = [
        {'code': r['code'], 'name': r['name'], 'vl_score': r['vl_score'],
         'reason': f'BIAS20={r["bias20"]}%, 量比={r["volume_ratio"]}', 'date': _today_str()}
        for r in results if r['vl_score'] >= 3
    ][:10]

    response = {
        'success': True,
        'date': _today_str(),
        'data_timestamp': _now_str(),
        'stats': s,
        'grouped': grouped if group_by == 'stage' else {},
        'list': results if group_by == 'none' else [],
        'alerts': alerts,
        'new_hot': [],
    }

    handler.send_json(response)


def register_routes(routes):
    routes.exact('/api/concept-wave', func=_make_response)
    return routes

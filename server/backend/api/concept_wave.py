"""概念板块波谷追踪 API 路由"""
import json, os, sys, statistics
from datetime import datetime

from backend.core.logger import get_logger
log = get_logger(__name__)

from backend.services.concept_wave_service import judge_concept_wave, compute_chart_annotations
from backend.core.data_layer import (
    get_sector_daily, get_concept_list, get_stock_concept_map,
    get_watchlist, get_index_klines,
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

        # ★ 核心筛选：自选股关联>=6只才视为重点关注的概念
        if len(related_stocks) < 6:
            continue

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
            'related_stocks': related_stocks,
            'related_count': len(related_stocks),
            'related_codes': related_codes,
            'stock_count': cinfo.get('stock_count', 0),
            'wave_data': wave_data,
            'klines': klines[-60:],
            'chart_annotations': compute_chart_annotations(klines[-60:]),
            'annotations': [],
            'reasoning_chain': _build_reasoning_chain(name, score, related_codes),
        })

    # 排序
    if sort_by == 'vl_score':
        results.sort(key=lambda r: -r['vl_score'])
    elif sort_by == 'name':
        results.sort(key=lambda r: r['name'])
    elif sort_by == 'change_5d':
        results.sort(key=lambda r: r['change_5d'])

    # 分组（5阶段）
    grouped = {'valley': [], 'peak': [], 'rise': [], 'decline': [], 'mid': []}
    for r in results:
        stage = r['stage']
        if stage == '波谷':
            grouped['valley'].append(r)
        elif stage == '波峰':
            grouped['peak'].append(r)
        elif stage == '上涨':
            grouped['rise'].append(r)
        elif stage == '下跌':
            grouped['decline'].append(r)
        else:
            grouped['mid'].append(r)

    # 统计
    s = {
        'total': len(results),
        'valley': len(grouped['valley']),
        'peak': len(grouped['peak']),
        'rise': len(grouped['rise']),
        'decline': len(grouped['decline']),
        'mid': len(grouped['mid']),
        'alerts_count': sum(1 for r in results if r['vl_score'] >= 3),
        'new_this_week': 0,
    }

    # 未追踪股票（所在概念自选股<6只，未纳入波谷追踪）
    untracked_stocks = []
    untracked_concepts = []
    for code, cinfo in concept_list.items():
        name = cinfo.get('name', '')
        klines = concepts_kline.get(name)
        if not klines or len(klines) < 20:
            continue
        related_stocks = []
        for scode, sinfo in stock_concept_map.items():
            if code in sinfo.get('concept_codes', []) and scode in watchlist_codes:
                related_stocks.append(sinfo.get('name', scode))
        if 1 <= len(related_stocks) <= 5:
            untracked_concepts.append({'name': name, 'stock_count': len(related_stocks), 'stocks': related_stocks})
            for sname in related_stocks:
                if sname not in untracked_stocks:
                    untracked_stocks.append(sname)
    untracked_concepts.sort(key=lambda x: -x['stock_count'])

    # 告警
    alerts = [
        {'code': r['code'], 'name': r['name'], 'vl_score': r['vl_score'],
         'reason': f'BIAS20={r["bias20"]}%, 量比={r["volume_ratio"]}', 'date': _today_str()}
        for r in results if r['vl_score'] >= 3
    ][:10]

    # 获取中证全指K线（用于对比线）
    index_klines = get_index_klines() or []

    response = {
        'success': True,
        'date': _today_str(),
        'data_timestamp': _now_str(),
        'stats': s,
        'grouped': grouped if group_by == 'stage' else {},
        'list': results if group_by == 'none' else [],
        'alerts': alerts,
        'new_hot': [],
        'index_klines': index_klines[-60:] if len(index_klines) >= 60 else index_klines,
        'untracked_stocks': untracked_stocks,
        'untracked_concepts': untracked_concepts[:20],
    }

    handler.send_json(response)


def _build_reasoning_chain(name, score, related_codes):
    """构建推理链数据"""
    from backend.services.review_compute_service import judge_peak_valley
    from backend.core.data_layer import get_index_klines

    chain = {'market': {}, 'concept_analysis': {}, 'stock_signals': []}
    try:
        index_klines = get_index_klines()
        if isinstance(index_klines, list):
            mc = judge_peak_valley(index_klines)
            chain['market'] = {
                'position': mc.get('position', '波中'),
                'position_pct': mc.get('position_pct', '半仓'),
                'volume_level': '中等',
                'volume_amount': '--',
                'top_mainlines': [],
            }
    except Exception:
        log.warning('概念波趋势链构建失败')
        chain['market'] = {'position': '波中', 'position_pct': '半仓', 'volume_level': '--', 'volume_amount': '--', 'top_mainlines': []}

    # 主线TOP3（从服务器内存数据读）
    try:
        from . import get_server
        _srv = get_server()
        ml = _srv.REVIEW_DATA.get('mainlines', {}).get('mainlines', {})
        # mainlines 可能是 {name: rank} 字典或 [{name, rank}] 列表
        if isinstance(ml, dict):
            sorted_ml = sorted(ml.items(), key=lambda x: x[1])[:3]
            chain['market']['top_mainlines'] = [
                {'name': name, 'rank': rank, 'days': 1}
                for name, rank in sorted_ml
            ]
        elif isinstance(ml, list):
            chain['market']['top_mainlines'] = [
                {'name': l.get('name', l) if isinstance(l, dict) else l, 'rank': rank, 'days': 1}
                for rank, l in enumerate(ml[:3])
            ]
    except Exception:
        log.warning("概念波主线TOP3构建失败")
        pass

    # 概念分析理由
    vl, pk = score.get('vl_score', 0), score.get('pk_score', 0)
    b20 = score.get('bias20', 0)
    vr = score.get('volume_ratio', 1)
    es = score.get('ema10_slope', 0)
    stage = score.get('stage', '波中')
    parts = []
    if b20 < -5:
        parts.append(f'BIAS20={b20:.1f}%（深度负值）')
    if vr < 0.7:
        parts.append(f'量比={vr:.2f}（{"极度" if vr < 0.5 else ""}缩量）')
    if es > -0.3:
        parts.append('EMA10走平/拐头')
    if stage == '波谷':
        chain['concept_analysis']['reason'] = ' → '.join(parts) + ' → 波谷确认' if parts else '波段底部确认'
    elif stage == '波峰':
        chain['concept_analysis']['reason'] = '价格高位+放量滞涨 → 警惕见顶'
    elif stage == '上涨':
        chain['concept_analysis']['reason'] = '趋势向上+量能配合 → 趋势延续'
    elif stage == '下跌':
        chain['concept_analysis']['reason'] = '价格下行+缩量 → 筑底过程'
    else:
        chain['concept_analysis']['reason'] = '趋势不明 → 继续观察'

    # 个股信号（检查关联自选股是否有买点）
    try:
        from backend.services.stock_card_service import get_stock_card
        for code in related_codes[:5]:
            card = get_stock_card(code, datetime.now().strftime('%Y%m%d'))
            if card and card.get('signal') in ('buy',):
                chain['stock_signals'].append({
                    'code': code,
                    'name': card.get('name', ''),
                    'signal': 'buy',
                    'buy_type': card.get('buy_point', ''),
                    'reason': card.get('signal_text', ''),
                })
    except Exception:
        log.warning("概念波扫描评分失败")
        pass

    return chain


def register_routes(routes):
    routes.exact('/api/concept-wave', func=_make_response)
    return routes

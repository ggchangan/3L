"""
涨幅榜服务 — 计算全市场指定区间涨幅排名 + 板块饼图
"""
import json, os, re
from backend.config import DATA_DIR, WWW_DIR
from backend.core.data_layer import get_all_stocks
from backend.core.ema_utils import get_structure, get_stage

INDUSTRY_MAP_PATH = os.path.join(DATA_DIR, 'stock_industry_map.json')


def get_top_gainers(start, end, limit=50, stocks=None):
    """
    获取全市场指定区间涨幅排名靠前的股票。

    Args:
        start: 起始日期 YYYYMMDD
        end: 截止日期 YYYYMMDD
        limit: 返回条数上限，默认50
        stocks: 可选参数，用于测试注入；生产不传走缓存。

    Returns:
        dict: {
            'stocks': [...],    # 涨幅靠前的股票列表
            'pie': [...],       # 板块饼图数据
            'total': int,       # 有完整数据的股票总数
            'limit': int,       # 请求的limit
            'start': str,       # 起始日期
            'end': str,         # 截止日期
            'days': int,        # 区间天数
        }
    """
    _start = start.replace('-', '')
    _end = end.replace('-', '')

    if stocks is None:
        stocks = get_all_stocks()
    _stocks = stocks
    _imap = json.load(open(INDUSTRY_MAP_PATH, 'r', encoding='utf-8'))

    _results = []
    for _sec, _ss in _stocks.items():
        for _code, _kls in _ss.items():
            if len(_kls) < 2:
                continue

            # 找起始和截止索引
            _start_idx = -1
            _end_idx = -1
            for i, _k in enumerate(_kls):
                _kd = str(_k['date']).replace('-', '')
                if _kd == _start:
                    _start_idx = i
                if _kd == _end:
                    _end_idx = i

            if _start_idx < 0 or _end_idx < 0 or _end_idx <= _start_idx:
                continue

            _k_start = _kls[_start_idx]
            _k_end = _kls[_end_idx]
            _days = _end_idx - _start_idx
            _gain = round((_k_end['close'] - _k_start['close']) / _k_start['close'] * 100, 2)

            # 基本信息
            _name = _kls[0].get('name', _code)
            _prev_close = _kls[_end_idx - 1]['close'] if _end_idx > 0 else _k_end['open']
            _change = round((_k_end['close'] - _prev_close) / _prev_close * 100, 2) if _prev_close else 0

            # 行业
            _ind_info = _imap.get(_code, {})
            if isinstance(_ind_info, dict):
                _sector = _ind_info.get('ths_industry', '')
                _direction = _ind_info.get('direction', '')
            else:
                _sector = ''
                _direction = _sec

            # 结构/阶段（基于截止日）
            _closes = [x['close'] for x in _kls[:_end_idx + 1]]
            _highs = [x['high'] for x in _kls[:_end_idx + 1]]
            _lows = [x['low'] for x in _kls[:_end_idx + 1]]
            _vols = [x.get('volume', x.get('vol', 0)) for x in _kls[:_end_idx + 1]]
            _structure = get_structure(_closes) if len(_closes) >= 30 else ''
            _stage = get_stage(_closes, _structure, _highs, _lows, volumes=_vols) if _structure else ''

            _results.append({
                'code': _code,
                'name': _name,
                'price': _k_end['close'],
                'change': _change,
                'gain': _gain,
                'days': _days,
                'structure': _structure,
                'stage': _stage,
                'sector': _sector,
                'direction': _direction or _sec,
            })

    # 按区间涨幅降序
    _results.sort(key=lambda x: -x['gain'])
    _top = _results[:limit]

    # 饼图数据：按板块统计
    _pie = {}
    for _s in _top:
        _sec_name = _s['sector'] or '其他'
        _pie[_sec_name] = _pie.get(_sec_name, 0) + 1

    _pie_data = [
        {'name': k, 'count': v, 'pct': round(v / len(_top) * 100, 1)}
        for k, v in sorted(_pie.items(), key=lambda x: -x[1])
    ]

    return {
        'stocks': _top,
        'pie': _pie_data,
        'total': len(_results),
        'limit': limit,
        'start': _start,
        'end': _end,
        'days': _days if _results else 0,
    }

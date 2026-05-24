"""
涨幅榜服务 — 计算全市场30日涨幅排名 + 板块饼图
"""
import json, os, re
from config import DATA_DIR, WWW_DIR
from scripts.data_layer import get_all_stocks
from scripts.ema_utils import get_structure, get_stage

INDUSTRY_MAP_PATH = os.path.join(DATA_DIR, 'stock_industry_map.json')


def get_top_gainers(date_str, limit=50, stocks=None):
    """
    获取全市场30日涨幅排名靠前的股票。

    Args:
        date_str: 日期字符串，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
        limit: 返回条数上限，默认50
        stocks: 可选参数，用于测试注入；生产不传走缓存。

    Returns:
        dict: {
            'stocks': [...],    # 涨幅靠前的股票列表
            'pie': [...],       # 板块饼图数据
            'total': int,       # 有完整数据的股票总数
            'limit': int,       # 请求的limit
            'date': str,        # 实际使用的日期
        }
    """
    _date_str = date_str.replace('-', '')

    if stocks is None:
        stocks = get_all_stocks()
    _stocks = stocks
    _imap = json.load(open(INDUSTRY_MAP_PATH, 'r', encoding='utf-8'))

    _results = []
    for _sec, _ss in _stocks.items():
        for _code, _kls in _ss.items():
            if len(_kls) < 35:
                continue

            # 找日期对应的索引
            _idx = -1
            _date_clean = _date_str
            for i, _k in enumerate(_kls):
                _kd = str(_k['date']).replace('-', '')
                if _kd == _date_clean:
                    _idx = i
                    break
            if _idx < 0:
                continue

            # 找30天前的索引
            _start = _idx - 29
            if _start < 0:
                continue

            _k = _kls[_idx]
            _k0 = _kls[_start]
            _gain = round((_k['close'] - _k0['close']) / _k0['close'] * 100, 2)

            # 基本信息
            _name = _kls[0].get('name', _code)
            _prev_close = _kls[_idx - 1]['close'] if _idx > 0 else _k['open']
            _change = round((_k['close'] - _prev_close) / _prev_close * 100, 2) if _prev_close else 0

            # 行业
            _ind_info = _imap.get(_code, {})
            if isinstance(_ind_info, dict):
                _sector = _ind_info.get('ths_industry', '')
                _direction = _ind_info.get('direction', '')
            else:
                _sector = ''
                _direction = _sec

            # 结构/阶段
            _closes = [x['close'] for x in _kls[:_idx + 1]]
            _highs = [x['high'] for x in _kls[:_idx + 1]]
            _lows = [x['low'] for x in _kls[:_idx + 1]]
            _vols = [x.get('volume', x.get('vol', 0)) for x in _kls[:_idx + 1]]
            _structure = get_structure(_closes) if len(_closes) >= 30 else ''
            _stage = get_stage(_closes, _structure, _highs, _lows, volumes=_vols) if _structure else ''
            _ema = ''
            if len(_closes) >= 30:
                try:
                    from scripts.ema_utils import get_ema_arrangement
                    _ema = get_ema_arrangement(_closes)
                except ImportError:
                    pass

            _results.append({
                'code': _code,
                'name': _name,
                'price': _k['close'],
                'change': _change,
                'gain_30d': _gain,
                'structure': _structure,
                'stage': _stage,
                'ema_arrangement': _ema or '',
                'sector': _sector,
                'direction': _direction or _sec,
                'date': _date_str or '',
            })

    # 按30日涨幅降序
    _results.sort(key=lambda x: -x['gain_30d'])
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
        'date': _date_str or '—',
    }

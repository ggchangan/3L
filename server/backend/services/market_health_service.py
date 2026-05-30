"""盯盘页 — 市场健康数据API

聚合结构/阶段/量能/主线/异常事件数据，一次返回全部。
数据来源均为现有本地文件+腾讯实时API，不新增外部依赖。
"""
import json
import os
import statistics
from datetime import datetime

from backend.config import DATA_DIR


def _load_index_data():
    """读 index_sh_data.json，返回 {closes, highs, lows, vols, last_close}"""
    path = os.path.join(DATA_DIR, 'index_sh_data.json')
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        return None
    klines = d.get('klines', [])
    if not klines or len(klines) < 30:
        return None
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    vols = [k.get('volume', 0) for k in klines]
    return {
        'closes': closes, 'highs': highs, 'lows': lows, 'vols': vols,
        'last_close': closes[-1], 'klines_count': len(klines),
    }


def _judge_structure(closes):
    """EMA10极值法判定结构"""
    n = 15
    seg = closes[-n:]
    max_pos = max(range(n), key=lambda i: seg[i])
    min_pos = min(range(n), key=lambda i: seg[i])
    fq, lq = n // 4, n - 1 - n // 4
    if max_pos >= lq and min_pos <= fq:
        return '上涨趋势'
    elif min_pos >= lq and max_pos <= fq:
        return '下降趋势'
    return '区间震荡'


def _judge_stage(closes):
    """乖离率变化法判定阶段"""
    if len(closes) < 10:
        return ''
    bias5_list = []
    for i in range(5, len(closes)):
        m5 = statistics.mean(closes[i - 5:i])
        bias5_list.append((closes[i] - m5) / m5 * 100)
    if len(bias5_list) < 4:
        return ''
    chg = bias5_list[-1] - bias5_list[-4]
    if chg > 1:
        return '上行'
    elif chg < -1:
        return '下行'
    return '整理'


def _calc_peak_valley(closes, highs, lows):
    """简化波峰波谷评分（基于当前BIAS20偏离程度）"""
    if len(closes) < 20:
        return 0, 0, '波中'
    ma20 = statistics.mean(closes[-20:])
    bias20 = (closes[-1] - ma20) / ma20 * 100

    pk, vl = 0, 0
    if bias20 > 6:
        pk += 2
    elif bias20 > 4:
        pk += 1
    if closes[-1] > statistics.mean(closes[-10:]):
        pk += 1
    if bias20 < -6:
        vl += 2
    elif bias20 < -4:
        vl += 1
    if closes[-1] < statistics.mean(closes[-10:]):
        vl += 1

    if pk >= 4:
        pos = '偏波峰'
    elif pk >= 3:
        pos = '波中偏上'
    elif vl >= 4:
        pos = '偏波谷'
    elif vl >= 3:
        pos = '波中偏下'
    else:
        pos = '波中'
    return pk, vl, pos


def _calc_volume_stats(index_data):
    """计算量能分析数据"""
    vols = index_data['vols']
    if len(vols) < 5:
        return {}
    latest_vol = vols[-1]
    avg5 = statistics.mean(vols[-5:]) if len(vols) >= 5 else latest_vol
    avg20 = statistics.mean(vols[-20:]) if len(vols) >= 20 else latest_vol
    vs_5d = (latest_vol - avg5) / avg5 * 100 if avg5 > 0 else 0
    vs_20d = (latest_vol - avg20) / avg20 * 100 if avg20 > 0 else 0
    return {
        'latest_volume': latest_vol,
        'avg5_volume': round(avg5, 0),
        'avg20_volume': round(avg20, 0),
        'vs_5day_pct': round(vs_5d, 1),
        'vs_20day_pct': round(vs_20d, 1),
    }


def _load_mainline():
    """读主线数据"""
    result = {'top3': [], 'gap_pct': 0}
    # 尝试读 mainline_history
    mh_path = os.path.join(DATA_DIR, 'mainline_history.json')
    if os.path.isfile(mh_path):
        try:
            with open(mh_path) as f:
                mh = json.load(f)
            dates = sorted(mh.keys(), reverse=True)
            if dates:
                today = mh[dates[0]]
                top10 = today.get('top10', today if isinstance(today, list) else [])
                for i, name in enumerate(top10[:3]):
                    days = today.get(f'{name}_days', 1) if isinstance(today, dict) else 1
                    result['top3'].append({'name': name, 'days': days})
                if len(top10) >= 5:
                    # 估算涨幅差（从sector_daily读取TOP1 vs TOP5）
                    result['gap_pct'] = 1.2  # 占位
        except Exception:
            pass
    return result


def _load_volume_curve():
    """复用现有的成交额曲线数据"""
    try:
        from backend.services.trading_calendar import get_today_volume
        curve = get_today_volume()
        if curve:
            return curve
    except Exception:
        pass
    return []


def get_market_health():
    """聚合市场健康数据"""
    idx = _load_index_data()
    if not idx:
        return {'error': '无指数数据', 'structure': '—', 'stage': '—'}

    closes = idx['closes']
    highs = idx['highs']
    lows = idx['lows']

    structure = _judge_structure(closes)
    stage = _judge_stage(closes)
    pk_score, vl_score, pos = _calc_peak_valley(closes, highs, lows)

    # BIAS20
    ma20 = statistics.mean(closes[-20:])
    bias20 = round((closes[-1] - ma20) / ma20 * 100, 2)

    # 仓位建议
    if pk_score >= 4:
        position_advice = '五成'
    elif pk_score >= 3:
        position_advice = '六至七成'
    elif vl_score >= 4:
        position_advice = '五至八成'
    elif vl_score >= 3:
        position_advice = '五至七成'
    else:
        position_advice = '七至八成'

    vol_stats = _calc_volume_stats(idx)
    mainline = _load_mainline()

    return {
        'structure': structure,
        'stage': stage,
        'pk_score': pk_score,
        'vl_score': vl_score,
        'position': pos,
        'position_advice': position_advice,
        'bias20': bias20,
        'last_close': idx['last_close'],
        'volume': vol_stats,
        'mainline': mainline,
        'updated': datetime.now().strftime('%H:%M'),
    }

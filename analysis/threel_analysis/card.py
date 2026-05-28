"""StockCardService — 统一个股卡片数据服务（3l-analysis 独立版）
使用 threel_core 进行核心计算，不依赖 3l-server。

用法:
    card = get_stock_card(code='002916', date_str='2026-05-28', ...)
"""

import os, json
from datetime import datetime

from threel_core.data_layer import get_stock_klines, get_industry_map, get_all_stocks
from threel_core.ema_utils import (
    ema_list, get_ema_arrangement, get_structure, get_stage,
    get_mainline_level,
)
from threel_core.buy_point_detection import detect_buy_point, calc_stop_loss
from threel_core.trend_trading import detect_trend_buy, decide_system_with_detail

# ── 数据目录 ──
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
MANUAL_TREND_PATH = os.path.join(DATA_DIR, 'private', 'manual_trend_stocks.json')
ALL_A_STOCKS_PATH = os.path.join(DATA_DIR, 'all_a_stocks.json')

# 全量A股名称映射
_ALL_A_STOCKS = {}
if os.path.isfile(ALL_A_STOCKS_PATH):
    try:
        with open(ALL_A_STOCKS_PATH) as _f:
            _ALL_A_STOCKS = json.load(_f)
    except Exception:
        pass


def _load_manual_trend():
    """加载手动趋势股列表"""
    try:
        with open(MANUAL_TREND_PATH) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _find_idx(klines, date_str):
    date_clean = date_str.replace('-', '')
    for i, k in enumerate(klines):
        if str(k.get('date', '')).replace('-', '') == date_clean:
            return i
    return len(klines) - 1


def _analyze_structure(klines, idx):
    if idx < 0 or idx >= len(klines):
        return {'structure': '--', 'stage': '--', 'ema': '--'}
    closes = [k['close'] for k in klines[:idx + 1]]
    highs = [k['high'] for k in klines[:idx + 1]]
    lows = [k['low'] for k in klines[:idx + 1]]
    volumes = [k['volume'] for k in klines[:idx + 1]]
    structure = get_structure(closes)
    stage = get_stage(closes, structure=structure, highs=highs, lows=lows, volumes=volumes)
    ema = get_ema_arrangement(closes)
    return {
        'structure': structure or '--',
        'stage': stage or '--',
        'ema': ema or '--',
    }


def _decide_trading_system(code):
    manual = _load_manual_trend()
    raw = code.strip()
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if raw.startswith(pfx):
            raw = raw[len(pfx):]
            break
    raw = raw[-6:] if len(raw) >= 6 else raw
    return 'trend' if raw in manual else '3l'


def get_stock_card(code, date_str, market_position='波中', main_lines=None,
                   direction=None, klines=None):
    """统一个股卡片数据（与 3l-server 的 get_stock_card 接口兼容）"""
    if main_lines is None:
        main_lines = []

    # 获取K线
    if klines is None:
        klines = get_stock_klines(code, direction)
    if not klines or len(klines) < 30:
        return {'error': f'{code} 数据不足30条'}

    idx = _find_idx(klines, date_str)
    today = klines[idx] if idx < len(klines) else klines[-1]
    today_str = today.get('date', '').replace('-', '')

    # 基本字段
    close = today.get('close', 0)
    pre_close = today.get('pre_close', 0)
    change_pct = round((close - pre_close) / pre_close * 100, 2) if pre_close else 0

    # EMA
    closes = [k['close'] for k in klines[:idx + 1]]
    if len(closes) >= 30:
        ema5 = round(ema_list(closes, 5)[-1], 2) if len(closes) >= 5 else None
        ema10 = round(ema_list(closes, 10)[-1], 2) if len(closes) >= 10 else None
        ema20 = round(ema_list(closes, 20)[-1], 2) if len(closes) >= 20 else None
        ema30 = round(ema_list(closes, 30)[-1], 2) if len(closes) >= 30 else None
    else:
        ema5 = ema10 = ema20 = ema30 = None

    # 乖离率
    bias = round((close - ema5) / ema5 * 100, 2) if ema5 and ema5 else 0

    # 结构/阶段/均线排列
    sa = _analyze_structure(klines, idx)
    structure, stage, ema_arr = sa['structure'], sa['stage'], sa['ema']

    # 量比（相对于前5日）
    vol5 = sum(k['volume'] for k in klines[max(0, idx - 4):idx + 1]) / max(1, min(5, idx + 1))
    vol_prev = sum(k['volume'] for k in klines[max(0, idx - 9):idx - 4]) / max(1, min(5, idx - 3))
    vol_ratio = round(vol5 / vol_prev, 2) if vol_prev else 1.0

    # 交易系统判定
    trading_system = _decide_trading_system(code)
    trend_stock = trading_system == 'trend'

    # 趋势交易详情
    _all_stocks = get_all_stocks()
    trend_detail = decide_system_with_detail(code=code, date_str=date_str, data=_all_stocks)
    trading_reason = trend_detail.get('reason', '') if trend_detail else ''
    trend_bias = None

    # 止损（3L用）
    stop_loss_data = calc_stop_loss(klines, idx)
    if isinstance(stop_loss_data, tuple):
        stop_loss = stop_loss_data[0]
        stop_loss_pct = stop_loss_data[1]
    else:
        stop_loss = stop_loss_data.get('stop_loss') if isinstance(stop_loss_data, dict) else None
        stop_loss_pct = stop_loss_data.get('stop_loss_pct') if isinstance(stop_loss_data, dict) else None

    # 板块
    ind_map = get_industry_map()
    sector_data = ind_map.get(code, {}) if ind_map else {}
    sector = sector_data.get('industry', '') if isinstance(sector_data, dict) else ''

    # 主线等级
    ml = get_mainline_level(code, closes, structure, main_lines) if main_lines else ''

    # 信号
    signal = 'hold'
    conclusion = ''
    if structure == '上升':
        signal = 'up'

    # 买点检测（简要）
    sub_stocks = {}
    if direction:
        sub_stocks[direction] = {code: klines}
    bp = detect_buy_point(code, today_str, sub_stocks) if direction else None

    # 名称
    name = _ALL_A_STOCKS.get(code, code)

    return {
        'code': code,
        'name': name,
        'price': close,
        'change': change_pct,
        'date': date_str,
        'structure': structure,
        'stage': stage,
        'ema': ema_arr,
        'ema5': ema5,
        'ema10': ema10,
        'ema20': ema20,
        'ema30': ema30,
        'deviation_pct': bias,
        'vol_ratio': vol_ratio,
        'trend_stock': trend_stock,
        'trading_system': trading_system,
        'trading_reason': trading_reason,
        'signal': signal,
        'stop_loss': stop_loss,
        'stop_loss_pct': stop_loss_pct,
        'mainline_level': ml,
        'trend_bias': trend_bias,
        'sector': sector,
        'conclusion': conclusion,
        'buy_point': bp.get('buy_type', '') if bp else '',
        'buy_score': bp.get('score', 0) if bp else 0,
        'buy_detail': bp.get('detail', {}) if bp else None,
        'has_chart': False,
    }

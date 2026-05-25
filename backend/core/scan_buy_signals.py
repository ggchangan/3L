#!/usr/bin/env python3
"""
盘中买点扫描 - 每1小时运行一次
使用 buy_point_detection.py（统一算法），但用腾讯实时行情替代缓存数据
扫描完成后自动更新买点股票的SVG图表（含当天数据）
"""
import json, os, sys
from datetime import datetime

# 导入统一算法和数据获取函数
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.core.buy_point_detection import detect_buy_point, get_realtime_kline
from backend.core.trend_trading import detect_trend_buy
from backend.core.data_layer import ALL_STOCKS_PATH, WATCHLIST_PATH, REVIEW_CHARTS_DIR, REVIEW_ARCHIVE_DIR

# 自选股数据
STOCKS_FILE = ALL_STOCKS_PATH
# 方向过滤：扫描全部
FOCUS_DIRECTIONS = []
# SVG输出目录
SVG_OUT_DIR = REVIEW_CHARTS_DIR


# ── EMA ──
def _ema(data, period):
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r


# ── 关键点识别（与 batch_gen_charts.py 一致） ──
def find_keypoints(data):
    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    n = len(data)
    kps = []
    ema20_vals = _ema(closes, 20)
    for i in range(5, n):
        if highs[i] == max(highs[max(0,i-10):i+1]):
            kps.append({'idx': i, 'type': 1, 'label': '前高', 'y': highs[i]})
        if lows[i] == min(lows[max(0,i-10):i+1]):
            kps.append({'idx': i, 'type': 1, 'label': '前低', 'y': lows[i]})
        if i >= 10:
            vw = volumes[i-10:i]
            if max(vw) > 0:
                if volumes[i] >= max(vw) * 1.5:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
                elif volumes[i] <= min(vw) * 0.3:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
        if i >= 10:
            ph = max(highs[i-10:i])
            if closes[i] > ph and closes[i] > opens[i]:
                kps.append({'idx': i, 'type': 2, 'label': '突', 'y': highs[i], 'support_price': ph})
        if i >= 1 and closes[i] > opens[i] and closes[i-1] < opens[i-1] and closes[i] > opens[i-1] and opens[i] < closes[i-1]:
            kps.append({'idx': i, 'type': 2, 'label': '反', 'y': lows[i]})
        if ema20_vals[i] and closes[i] >= ema20_vals[i]*0.98 and closes[i] <= ema20_vals[i]*1.02:
            va = sum(volumes[i-5:i]) / 5 if i >= 5 else 0
            if va > 0 and volumes[i] < va * 0.8:
                kps.append({'idx': i, 'type': 2, 'label': '中', 'y': lows[i]})
    return kps


# ── 生成SVG ──
def gen_svg(name, code, klines, kps, output_path):
    W, H = 750, 480
    pl, pr, pt, pb = 60, 25, 32, 65
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    opens = [k['open'] for k in klines]
    volumes = [k['volume'] for k in klines]
    mx, mn = max(highs), min(lows)
    rg = mx - mn if mx != mn else 1
    n = len(klines)
    cw = (W - pl - pr) / n
    bv = H - pb
    px = lambda i: pl + i * cw + cw / 2
    py = lambda v: pt + (mx - v) / rg * (H - pt - pb)
    ema5 = _ema(closes, 5)
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    vm = max(volumes) if max(volumes) > 0 else 1
    sv = []
    sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
    sv.append(f'<text x="{W/2}" y="22" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#ffffff" font-weight="bold">{name}({code}) 关键点图</text>')
    sv.append(f'<text x="{W/2}" y="31" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#888888">最新: {closes[-1]:.2f}</text>')
    for i in range(5):
        yv = mx - i * rg / 4
        yp = py(yv)
        sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
        sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="8" fill="#666666">{yv:.1f}</text>')
    sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.55, 1)
        vh = volumes[i] / vm * 40
        is_up = closes[i] >= opens[i]
        vc = '#ff4444' if is_up else '#44aa44'
        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh, 0.5)}" fill="{vc}" opacity="0.35"/>')
    for ev, clr in [(ema5, '#ffd700'), (ema10, '#ff6b6b'), (ema20, '#4ecdc4')]:
        pts = []
        for i in range(n):
            if ev[i] is not None:
                pts.append(f'{px(i)},{py(ev[i])}')
        if pts:
            sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="1" opacity="0.7"/>')
    for i in range(n):
        x = px(i)
        w = max(cw * 0.45, 1)
        hi, lo, op, cl = highs[i], lows[i], opens[i], closes[i]
        yh, yl = py(hi), py(lo)
        yo, yc = py(op), py(cl)
        is_up = cl >= op
        clr = '#ff4444' if is_up else '#44aa44'
        sv.append(f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" stroke="{clr}" stroke-width="0.5" opacity="0.6"/>')
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(f'<rect x="{x-w/2}" y="{bt}" width="{w}" height="{max(bb-bt, 0.5)}" fill="{clr}" opacity="0.8"/>')
    sz = 4
    for kp in kps:
        xp = px(kp['idx'])
        yp = py(kp['y'])
        clr = '#ff9800' if kp['type'] == 1 else '#2196f3'
        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{clr}" opacity="0.85"/>')
        sv.append(f'<text x="{xp}" y="{yp-sz-2}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="{clr}">{kp["label"]}</text>')
    for i in range(0, n, 5):
        xd = px(i)
        ds = str(klines[i]['date']).replace('-', '')
        mm, dd = ds[4:6], ds[6:8]
        sv.append(f'<text x="{xd}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{xd},{bv+14})">{mm}/{dd}</text>')
    last_ds = str(klines[-1]['date']).replace('-', '')
    sv.append(f'<text x="{px(n-1)}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{px(n-1)},{bv+14})">{last_ds[4:6]}/{last_ds[6:8]}</text>')
    # 买点标记（最新K线下方画大箭头）
    sv.append(f'<polygon points="{px(n-1)-8},{py(closes[-1])+8} {px(n-1)+8},{py(closes[-1])+8} {px(n-1)},{py(closes[-1])+18}" fill="#e94560" opacity="0.9"/>')
    sv.append(f'<text x="{px(n-1)}" y="{py(closes[-1])+26}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#e94560" font-weight="bold">买点</text>')
    # 止损线
    try:
        from backend.core.buy_point_detection import calc_stop_loss
        _sl, _sl_pct = calc_stop_loss(klines, n-1)
        if _sl and _sl > 0:
            _sl_y = py(_sl)
            sv.append(f'<line x1="{pl}" y1="{_sl_y}" x2="{W-pr}" y2="{_sl_y}" stroke="#ff9800" stroke-width="1" stroke-dasharray="6,3" opacity="0.7"/>')
            sv.append(f'<text x="{W-pr-4}" y="{_sl_y-3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#ff9800">止损 {_sl:.2f} ({_sl_pct:.1f}%)</text>')
    except Exception:
        pass
    ly2 = bv + 9
    for idx2, (clr2, lbl) in enumerate([('#ff9800','第1类'),('#2196f3','第2类'),('#ffd700','EMA5'),('#ff6b6b','EMA10'),('#4ecdc4','EMA20')]):
        lx = 60 + idx2 * 130
        sv.append(f'<rect x="{lx}" y="{ly2}" width="8" height="8" fill="{clr2}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+11}" y="{ly2+7}" font-family="sans-serif" font-size="9" fill="#888888">{lbl}</text>')
    sv.append('</svg>')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(sv))

# 自选股名单
WATCHLIST_FILE = WATCHLIST_PATH
# 方向过滤：扫描全部
FOCUS_DIRECTIONS = []
# SVG输出目录
SVG_OUT_DIR = REVIEW_CHARTS_DIR


def load_stock_list():
    "从 watchlist.json 读取自选股名单（只读已启用方向）"
    if not os.path.isfile(WATCHLIST_FILE):
        print(f"❌ watchlist.json 不存在", file=sys.stderr)
        return []
    with open(WATCHLIST_FILE) as f:
        data = json.load(f)
    stocks = data.get('stocks', [])
    # 方向过滤：只返回已启用方向的自选股
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from services.direction_service import get_active
    active = get_active()
    stocks = [s for s in stocks if s.get('direction', '其他') in active]
    return stocks


def get_market_position():
    try:
        archive_dir = REVIEW_ARCHIVE_DIR
        if os.path.isdir(archive_dir):
            archives = sorted([f for f in os.listdir(archive_dir) if f.endswith('.json')])
            if archives:
                with open(os.path.join(archive_dir, archives[-1])) as f:
                    rd = json.load(f)
                return rd.get('market', {}).get('position', '波中')
    except:
        pass
    return '波中'


def get_main_lines():
    try:
        archive_dir = REVIEW_ARCHIVE_DIR
        if os.path.isdir(archive_dir):
            archives = sorted([f for f in os.listdir(archive_dir) if f.endswith('.json')])
            if archives:
                with open(os.path.join(archive_dir, archives[-1])) as f:
                    rd = json.load(f)
                return [l['name'] for l in rd.get('mainline', {}).get('lines', [])]
    except:
        pass
    return []


# ── 盘中预估全天成交量 ──
def _estimate_full_day_volume(current_vol, now=None):
    """预估全天成交量（股），A股：09:30-11:30(120min)+13:00-15:00(120min)=240min"""
    if now is None:
        now = datetime.now()
    total_min = 240  # A股全天交易240分钟
    h, m = now.hour, now.minute
    if h < 9 or (h == 9 and m < 30):
        return current_vol  # 还没开盘
    if h < 12:
        elapsed = (h - 9) * 60 + m - 30  # 上午 09:30-11:30
    elif h < 13:
        elapsed = 120  # 午休 11:30-13:00，上午已满
    else:
        elapsed = 120 + (h - 13) * 60 + m  # 下午 13:00-15:00
    elapsed = max(1, min(elapsed, total_min))
    return int(current_vol * total_min / elapsed)


def main():
    stocks = load_stock_list()
    print(f"加载自选股: {len(stocks)}只", file=sys.stderr)
    
    market_position = get_market_position()
    main_lines = get_main_lines()
    print(f"大盘位置: {market_position}, 主线: {main_lines}", file=sys.stderr)
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    signals = []
    svg_ok = 0
    now = datetime.now()
    is_trading_hours = (9 <= now.hour < 15)  # 盘中
    
    for s in stocks:
        code = s['code']
        direction = s['direction']
        name = s['name']
        
        # 获取实时K线数据（缓存59天+今日实时）
        klines = get_realtime_kline(code, direction)
        if len(klines) < 30:
            continue
        
        # 盘中：用预估全天成交量替代今日真实成交量
        vol_estimated = False
        if is_trading_hours:
            last_k = klines[-1]
            today_str_short = last_k.get('date', '').replace('-', '')
            if today_str_short == now.strftime('%Y%m%d'):
                actual_vol = last_k.get('volume', 0)
                if actual_vol > 0:
                    est_vol = _estimate_full_day_volume(actual_vol, now)
                    if est_vol != actual_vol:
                        print(f"  {code} {name}: 预估量 {actual_vol}→{est_vol} (股)", file=sys.stderr)
                        last_k['volume'] = est_vol
                        vol_estimated = True
        
        all_stocks = {direction: {code: klines}}
        bt = detect_buy_point(code, today_str, all_stocks,
                              market_position=market_position,
                              main_lines=main_lines)
        
        if bt:
            # 不再限制买点类型：突破/中继/回踩都输出
            # 量能文本
            vr = bt.get('vol_ratio', 0)
            if vr < 0.7:
                vol_text = f'缩量{vr:.0%}'
            elif vr > 1.5:
                vol_text = f'放量{vr:.0%}'
            else:
                vol_text = f'量能正常{vr:.0%}'
            
            gain_val = round(bt.get('gain', 0), 2)
            signal = {
                'code': code,
                'name': name,
                'direction': direction,
                'price': bt.get('close', klines[-1]['close']),
                'change': gain_val,
                'change_pct': gain_val,
                'signal': 'buy',
                'buy_type': bt.get('buy_type', ''),
                'buy_point': bt.get('buy_type', ''),
                'structure': bt.get('structure', ''),
                'stage': bt.get('stage', ''),
                'vol_ratio': vr,
                'vol_analysis': vol_text,
                'score': bt.get('score', 0),
                'detail': bt.get('detail', {}),
                'ema_arrangement': bt.get('ema_arrangement', ''),
            }
            signals.append(signal)
            
            # SVG不预生成，由前端点📊时按需调用 /api/stock-chart 生成
        
        # 趋势买点检测
        try:
            _all_stocks_full = {}
            # 加载全量数据用于趋势判定
            if os.path.isfile(STOCKS_FILE):
                with open(STOCKS_FILE) as _f:
                    _ad = json.load(_f)
                _all_stocks_full = _ad.get('stocks', _ad)
            _tb = detect_trend_buy(code, today_str, _all_stocks_full, main_lines)
            if _tb:
                _tb_gain = round(_tb.get('gain', 0), 2)
                signals.append({
                    'code': code,
                    'name': name,
                    'direction': direction,
                    'price': _tb.get('price', klines[-1]['close']),
                    'change': _tb_gain,
                    'change_pct': _tb_gain,
                    'signal': 'buy',
                    'buy_type': _tb['buy_type'],
                    'buy_point': _tb['buy_type'],
                    'structure': _tb.get('bias5_zone', ''),
                    'stage': _tb.get('buy_type', ''),
                    'vol_ratio': 0,
                    'vol_analysis': f"BIAS5={_tb.get('bias5',0)}%",
                    'score': 5,
                    'detail': {'reason': _tb.get('reason', '')},
                    'trend_bias': _tb.get('bias5', 0),
                    'trend_buy_reason': _tb.get('reason', ''),
                    'trading_system': 'trend',
                })
        except Exception as e:
            print(f"  趋势买点失败 {code}: {e}", file=sys.stderr)
    
    signals.sort(key=lambda x: (0 if x.get('buy_type') == '突破买点' else 1, -(x.get('score', 0))))
    
    result = {
        'signals': signals,
        'count': len(signals),
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'focused_directions': FOCUS_DIRECTIONS if FOCUS_DIRECTIONS else 'all',
        'stocks_scanned': len(stocks),
        'market_position': market_position,
        'main_lines': main_lines,
        'svg_generated': svg_ok,
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

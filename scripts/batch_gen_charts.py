#!/usr/bin/env python3
"""批量生成个股3L关键点K线图（SVG）
从 all_stocks_60d.json 读取数据，根据买点信号+持仓股列表生成图表
存入 review_charts/{code}.svg
"""
import json, os, sys, math
from collections import OrderedDict
from datetime import datetime

# 从 config 读取路径（支持环境变量覆盖）
import config

WWW_DIR = config.WWW_DIR
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
DATA_PATH = os.path.join(DATA_DIR, 'all_stocks_60d.json')
SCAN_PATH = os.path.join(DATA_DIR, 'latest_scan_result.json')
HOLDINGS_PATH = os.path.join(WWW_DIR, 'private', 'holdings.json')
OUT_DIR = config.CHARTS_DIR

# ── EMA 计算 ──
def ema(data, period):
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r

# ── 关键点识别 ──
def find_keypoints(data):
    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    n = len(data)
    kps = []
    ema20_vals = ema(closes, 20)

    for i in range(5, n):
        if highs[i] == max(highs[max(0,i-10):i+1]):
            kps.append({'idx': i, 'type': 1, 'label': '前高', 'y': highs[i]})
        if lows[i] == min(lows[max(0,i-10):i+1]):
            kps.append({'idx': i, 'type': 1, 'label': '前低', 'y': lows[i]})
        if i >= 10:
            vol_window = volumes[i-10:i]
            if max(vol_window) > 0:
                if volumes[i] >= max(vol_window) * 1.5:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
                elif volumes[i] <= min(vol_window) * 0.3:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
        if i >= 10:
            prev_high = max(highs[i-10:i])
            if closes[i] > prev_high and closes[i] > opens[i]:
                kps.append({'idx': i, 'type': 2, 'label': '突', 'y': highs[i], 'support_price': prev_high})
        if i >= 1 and closes[i] > opens[i] and closes[i-1] < opens[i-1] and closes[i] > opens[i-1] and opens[i] < closes[i-1]:
            kps.append({'idx': i, 'type': 2, 'label': '反', 'y': lows[i]})
        if ema20_vals[i] and closes[i] >= ema20_vals[i] * 0.98 and closes[i] <= ema20_vals[i] * 1.02:
            vol_avg = sum(volumes[i-5:i]) / 5 if i >= 5 else 0
            if vol_avg > 0 and volumes[i] < vol_avg * 0.8:
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

    ema5 = ema(closes, 5)
    ema10 = ema(closes, 10)
    ema20 = ema(closes, 20)
    vm = max(volumes) if max(volumes) > 0 else 1

    sv = []
    sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
    sv.append(f'<text x="{W/2}" y="22" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#ffffff" font-weight="bold">{name}({code}) 关键点图</text>')
    sv.append(f'<text x="{W/2}" y="31" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#888888">最新: {closes[-1]:.2f}</text>')

    for i in range(5):
        y_val = mx - i * rg / 4
        yp = py(y_val)
        sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
        sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="8" fill="#666666">{y_val:.1f}</text>')
    sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')

    # ── 判断最后一根K线是否需要盘中虚线标记 ──
    # 只有今天且此刻在交易时段内（9:30-15:00）才画盘中标记
    today_str = datetime.now().strftime('%Y-%m-%d')
    last_date = klines[-1].get('date', '')
    now_hour = datetime.now().hour
    now_min = datetime.now().minute
    is_trading_hours = (now_hour > 9 or (now_hour == 9 and now_min >= 30)) and now_hour < 15
    is_intraday = last_date == today_str and is_trading_hours

    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.55, 1)
        vh = volumes[i] / vm * 40
        is_up = closes[i] >= opens[i]
        vc = '#ff4444' if is_up else '#44aa44'
        is_last = (i == n - 1) and is_intraday
        vdash = ' stroke-dasharray="3,2"' if is_last else ''
        vopa = '0.25' if is_last else '0.35'
        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh, 0.5)}" fill="{vc}" opacity="{vopa}"{vdash}/>')

    for ema_vals, color in [(ema5, '#ffd700'), (ema10, '#ff6b6b'), (ema20, '#4ecdc4')]:
        pts = []
        for i in range(n):
            if ema_vals[i] is not None:
                pts.append(f'{px(i)},{py(ema_vals[i])}')
        if pts:
            sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1" opacity="0.7"/>')

    for i in range(n):
        x = px(i)
        w = max(cw * 0.45, 1)
        hi, lo, op, cl = highs[i], lows[i], opens[i], closes[i]
        yh, yl = py(hi), py(lo)
        yo, yc = py(op), py(cl)
        is_up = cl >= op
        color = '#ff4444' if is_up else '#44aa44'
        is_last = (i == n - 1) and is_intraday
        dash = ' stroke-dasharray="4,3"' if is_last else ''
        opa = '0.3' if is_last else '0.6'
        bopa = '0.4' if is_last else '0.8'
        sv.append(f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" stroke="{color}" stroke-width="0.5" opacity="{opa}"{dash}/>')
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(f'<rect x="{x-w/2}" y="{bt}" width="{w}" height="{max(bb-bt, 0.5)}" fill="{color}" opacity="{bopa}"{dash} rx="1"/>')
    # 盘中标记
    if is_intraday:
        lx = px(n - 1)
        sv.append(f'<text x="{lx + 20}" y="{py(closes[-1]) - 6}" font-family="sans-serif" font-size="9" fill="#ffd700" opacity="0.8">🕐 盘中</text>')

    # ── 判断结构（直接用ema_utils，与复盘页一致） ──
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'trading', 'ema10-trend-judgment', 'scripts'))
    from ema_utils import get_structure
    structure = get_structure(closes)
    import sys as _sys
    _sys.modules.pop('ema_utils', None)  # clean import

    # ── 区间震荡 → 画支撑/压力线（同板块图逻辑） ──
    if structure == '区间震荡':
        cur_close = closes[-1]
        # 支撑线 = 最近的突破点下方（用突破前的10日高，不是突破日最高价）
        bk_pts = sorted([kp for kp in kps if kp['label'] == '突' and kp['support_price'] < cur_close],
                        key=lambda x: x['support_price'], reverse=True)
        # 压力线 = 近15日最高价
        nd15 = min(15, n)
        hi_15 = max(highs[-nd15:])
        hi_lo_20 = min(lows[-min(20, n):])

        support_y = bk_pts[0]['support_price'] if bk_pts else hi_lo_20
        # 过滤：支撑位必须距离当前价至少1.5%，否则用下一档或回退
        if bk_pts and cur_close > 0 and (cur_close - support_y) / cur_close < 0.015:
            deeper = [kp for kp in bk_pts if (cur_close - kp['support_price']) / cur_close >= 0.015]
            support_y = deeper[0]['support_price'] if deeper else hi_lo_20
        resist_y = hi_15

        if support_y and resist_y and support_y < resist_y:
            sy = py(support_y)
            ry = py(resist_y)
            # 支撑线 - 绿色虚线
            sv.append(f'<line x1="{pl}" y1="{sy}" x2="{W-pr}" y2="{sy}" stroke="#4caf50" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>')
            sv.append(f'<text x="{pl+4}" y="{sy-4}" font-family="sans-serif" font-size="9" fill="#4caf50" font-weight="bold">支撑 {support_y:.1f}</text>')
            # 压力线 - 红色虚线
            sv.append(f'<line x1="{pl}" y1="{ry}" x2="{W-pr}" y2="{ry}" stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>')
            sv.append(f'<text x="{pl+4}" y="{ry-4}" font-family="sans-serif" font-size="9" fill="#f44336" font-weight="bold">压力 {resist_y:.1f}</text>')

    sz = 4
    for kp in kps:
        i = kp['idx']
        xp = px(i)
        yp = py(kp['y'])
        color = '#ff9800' if kp['type'] == 1 else '#2196f3'
        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{color}" opacity="0.85"/>')
        sv.append(f'<text x="{xp}" y="{yp-sz-2}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="{color}">{kp["label"]}</text>')

    for i in range(0, n, 5):
        xd = px(i)
        ds = str(klines[i]['date'])
        mm, dd = ds[4:6], ds[6:8]
        sv.append(f'<text x="{xd}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{xd},{bv+14})">{mm}/{dd}</text>')
    last_ds = str(klines[-1]['date'])
    sv.append(f'<text x="{px(n-1)}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{px(n-1)},{bv+14})">{last_ds[4:6]}/{last_ds[6:8]}</text>')

    ly2 = bv + 9
    legend_items = [
        ('#ff9800', '第1类'), ('#2196f3', '第2类'),
        ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20'),
    ]
    for idx, (lcolor, llabel) in enumerate(legend_items):
        lx = 60 + idx * 130
        sv.append(f'<rect x="{lx}" y="{ly2}" width="8" height="8" fill="{lcolor}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+11}" y="{ly2+7}" font-family="sans-serif" font-size="9" fill="#888888">{llabel}</text>')

    sv.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    content = '\n'.join(sv)
    with open(output_path, 'w') as f:
        f.write(content)
    return len(content)


def main():
    print("📂 读取数据...")
    if not os.path.exists(DATA_PATH):
        print(f"❌ {DATA_PATH} 不存在")
        return
    with open(DATA_PATH) as f:
        data = json.load(f)
    stocks = data.get('stocks', {})

    all_codes = {}
    for sec, sec_stocks in stocks.items():
        for code, klines in sec_stocks.items():
            name = klines[0].get('name', code) if klines else code
            all_codes[code] = {'name': name, 'sector': sec, 'klines': klines}

    need_codes = {}
    if os.path.exists(SCAN_PATH):
        with open(SCAN_PATH) as f:
            scan = json.load(f)
        for r in scan.get('results', []):
            code = r['code']
            if code in all_codes:
                need_codes[code] = '买点信号'
    if os.path.exists(HOLDINGS_PATH):
        with open(HOLDINGS_PATH) as f:
            hdata = json.load(f)
        for h in hdata.get('holdings', []):
            code = h.get('code', '')
            if code and code in all_codes:
                need_codes[code] = '持仓股'

    if not need_codes:
        print("⚠️ 没有需要生成图表的股票")
        return

    print(f"需要生成图表: {len(need_codes)} 只")
    ok, fail = 0, 0
    for code, reason in need_codes.items():
        info = all_codes[code]
        klines = info['klines']
        if len(klines) < 20:
            print(f"  ⚠ {info['name']}({code}) 数据不足")
            fail += 1
            continue
        try:
            kps = find_keypoints(klines)
            out = os.path.join(OUT_DIR, f'{code}.svg')
            size = gen_svg(info['name'], code, klines, kps, out)
            print(f"  ✅ {info['name']}({code}) → {len(kps)}个关键点, {size}B")
            # 同时生成趋势交易图
            try:
                sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
                import importlib
                gen_trend_svg = importlib.import_module('gen_trend_chart').gen_trend_svg
                tout = os.path.join(OUT_DIR, f'trend_{code}.svg')
                tsize = gen_trend_svg(info['name'], code, klines, tout)
                print(f"     趋势图 {tsize}B")
            except Exception:
                pass
            ok += 1
        except Exception as e:
            print(f"  ❌ {code}: {e}")
            fail += 1
    print(f"\n✅ {ok} 成功, {fail} 失败")

if __name__ == '__main__':
    main()

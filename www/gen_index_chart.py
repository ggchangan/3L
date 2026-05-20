#!/usr/bin/env python3
"""生成中证全指(000985)关键点K线图 - 使用正确的数据源"""
import json, os, math
import akshare as ak

def get_kline():
    df = ak.stock_zh_index_daily_tx(symbol='sh000985')
    # Take last 60 trading days
    df = df.tail(60).reset_index(drop=True)
    data = []
    for _, row in df.iterrows():
        data.append({
            'day': row['date'],
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['amount']) / 1e4,  # scale amount for volume bars
        })
    return data

def ema(data, period):
    result = [None] * len(data)
    multiplier = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            result[i] = data[i]
        elif result[i-1] is not None:
            result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
    return result

def find_keypoints(data):
    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    n = len(data)
    kps = []
    
    for i in range(5, n):
        if highs[i] == max(highs[max(0,i-10):i+1]) and i > 0:
            kps.append({'idx': i, 'type': 1, 'label': '前高', 'y': highs[i]})
        if lows[i] == min(lows[max(0,i-10):i+1]) and i > 0:
            kps.append({'idx': i, 'type': 1, 'label': '前低', 'y': lows[i]})
        if i >= 10:
            vol_window = volumes[i-10:i]
            if len(vol_window) > 0 and max(vol_window) > 0:
                if volumes[i] >= max(vol_window) * 1.5:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
                elif volumes[i] <= min(vol_window) * 0.5 and volumes[i] > 0:
                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
            prev_high = max(highs[i-10:i])
            if closes[i] > prev_high and closes[i] > opens[i]:
                kps.append({'idx': i, 'type': 2, 'label': '突', 'y': highs[i]})
            if i >= 1 and closes[i] > opens[i] and closes[i-1] < opens[i-1] and closes[i] > opens[i-1] and opens[i] < closes[i-1]:
                kps.append({'idx': i, 'type': 2, 'label': '反', 'y': lows[i]})
            ema20_val = ema(closes, 20)[i]
            if ema20_val and closes[i] >= ema20_val * 0.98 and closes[i] <= ema20_val * 1.02:
                vol_avg = sum(volumes[i-5:i]) / 5 if i >= 5 else 0
                if vol_avg > 0 and volumes[i] < vol_avg * 0.8:
                    kps.append({'idx': i, 'type': 2, 'label': '中', 'y': lows[i]})
    return kps

def gen_svg(data, kps, output_path):
    W, H = 1000, 550
    pl, pr, pt, pb = 70, 30, 36, 70
    
    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    
    mx, mn = max(highs), min(lows)
    rg = mx - mn if mx != mn else 1
    n = len(data)
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
    sv.append(f'<text x="{W/2}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#ffffff" font-weight="bold">中证全指(000985) 关键点图</text>')
    sv.append(f'<text x="{W/2}" y="34" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#888888">最新: {data[-1]["close"]:.2f} ({data[-1]["day"]})</text>')
    
    for i in range(6):
        y_val = mx - i * rg / 5
        yp = py(y_val)
        sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
        sv.append(f'<text x="{pl-5}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#666666">{y_val:.0f}</text>')
    
    sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
    
    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.6, 1)
        vh = volumes[i] / vm * 50
        is_up = closes[i] >= opens[i]
        vc = '#ff4444' if is_up else '#44aa44'
        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh, 0.5)}" fill="{vc}" opacity="0.35"/>')
    
    for ema_vals, color in [(ema5, '#ffd700'), (ema10, '#ff6b6b'), (ema20, '#4ecdc4')]:
        pts = []
        for i in range(n):
            if ema_vals[i] is not None:
                pts.append(f'{px(i)},{py(ema_vals[i])}')
        if pts:
            sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1" opacity="0.7"/>')
    
    for i in range(n):
        x = px(i)
        w = max(cw * 0.5, 1)
        hi, lo, op, cl = highs[i], lows[i], opens[i], closes[i]
        yh, yl = py(hi), py(lo)
        yo, yc = py(op), py(cl)
        is_up = cl >= op
        color = '#ff4444' if is_up else '#44aa44'
        sv.append(f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" stroke="{color}" stroke-width="0.5" opacity="0.6"/>')
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(f'<rect x="{x-w/2}" y="{bt}" width="{w}" height="{max(bb-bt, 0.5)}" fill="{color}" opacity="0.8"/>')
    
    sz = 5
    for kp in kps:
        i = kp['idx']
        xp = px(i)
        yp = py(kp['y'])
        color = '#ff9800' if kp['type'] == 1 else '#2196f3'
        txt_color = color
        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{color}" opacity="0.85"/>')
        sv.append(f'<text x="{xp}" y="{yp-sz-3}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="{txt_color}">{kp["label"]}</text>')
    
    for i in range(0, n, 5):
        xd = px(i)
        date_str = str(data[i]['day'])
        mm, dd = date_str[5:7], date_str[8:10]
        sv.append(f'<text x="{xd}" y="{bv+16}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#666666" transform="rotate(-45,{xd},{bv+16})">{mm}/{dd}</text>')
    ld = str(data[-1]['day'])
    sv.append(f'<text x="{px(n-1)}" y="{bv+16}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#666666" transform="rotate(-45,{px(n-1)},{bv+16})">{ld[5:7]}/{ld[8:10]}</text>')
    
    ly2 = bv + 10
    legend_items = [
        ('#ff9800', '第1类参考点'), ('#2196f3', '第2类供需改变'),
        ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20'),
    ]
    for idx, (color, label) in enumerate(legend_items):
        lx = 80 + idx * 160
        sv.append(f'<rect x="{lx}" y="{ly2}" width="10" height="10" fill="{color}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+14}" y="{ly2+9}" font-family="sans-serif" font-size="11" fill="#888888">{label}</text>')
    
    sv.append('</svg>')
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    content = '\n'.join(sv)
    with open(output_path, 'w') as f:
        f.write(content)
    print(f"Chart saved: {output_path} ({len(content)} chars)")
    print(f"Latest: {data[-1]['close']:.2f} on {data[-1]['day']}")

if __name__ == '__main__':
    data = get_kline()
    kps = find_keypoints(data)
    print(f"Found {len(kps)} keypoints")
    gen_svg(data, kps, '/home/ubuntu/www/review_charts/sz000985.svg')
    
    # Also update the label in review.html
    # The current label shows "中证全指 000985" which is fine but let's also update the real-time value display in the page

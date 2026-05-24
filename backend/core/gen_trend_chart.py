#!/usr/bin/env python3
"""生成趋势交易专用K线图（SVG）
含乖离率BIAS5指示 + 买入区标记 + 趋势分析
存为 review_charts/trend_{code}.svg

与batch_gen_charts.py的关键点图不同：
- 标题改为"趋势交易分析图"
- 不标7种关键点，改标乖离率买点区
- 增加BIAS5曲线指示
- 显示当前趋势判定结论
- 明确标注买入区/持有区/警戒区范围
"""
import json, os, sys, math
from datetime import date

import config

DATA_PATH = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = config.CHARTS_DIR


def ema(data, period):
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r


def gen_trend_svg(name, code, klines, output_path, trend_bias=None):
    """生成趋势交易K线图

    trend_bias: 当前BIAS5值（用于标注），若不提供则自动计算
    """
    W, H = 750, 540  # 增高一点给更多标注空间
    pl, pr, pt, pb = 60, 25, 32, 65

    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    opens_ = [k['open'] for k in klines]
    volumes = [k['volume'] for k in klines]

    mx, mn = max(highs), min(lows)
    rg = mx - mn if mx != mn else 1
    n = len(klines)
    cw = (W - pl - pr) / n
    bv = H - pb
    # BIAS5图的高度
    bias_h = 55
    kline_bottom = bv - bias_h - 5  # K线区域底部

    px = lambda i: pl + i * cw + cw / 2
    py = lambda v: pt + (mx - v) / rg * (kline_bottom - pt)

    ema5 = ema(closes, 5)
    ema10 = ema(closes, 10)
    ema20 = ema(closes, 20)

    # BIAS5计算
    bias5_vals = []
    for i in range(n):
        if ema5[i] and ema5[i] > 0:
            bias5_vals.append((closes[i] - ema5[i]) / ema5[i] * 100)
        else:
            bias5_vals.append(None)

    current_bias = bias5_vals[-1] if bias5_vals[-1] is not None else 0
    if trend_bias is not None:
        current_bias = trend_bias

    vm = max(volumes) if max(volumes) > 0 else 1

    sv = []
    sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
    sv.append(f'<text x="{W/2}" y="22" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#ffffff" font-weight="bold">{name}({code}) 趋势交易分析图</text>')

    # 顶部状态栏：只显示BIAS5值和区域（完整风险提示在个股卡片）
    if current_bias < 0:
        bias_color = '#4ecdc4'
    elif current_bias <= 2:
        bias_color = '#4ecdc4'
    elif current_bias <= 8:
        bias_color = '#ffd700'
    else:
        bias_color = '#e94560'

    sv.append(f'<text x="{pl}" y="31" font-family="sans-serif" font-size="10" fill="#888888">最新: {closes[-1]:.2f}</text>')
    # BIAS5值在下方副图曲线旁显示，顶部只以颜色示意区域

    # ── K线区域：三个区间的价格参考线 ──
    last_ema5 = ema5[-1] if ema5[-1] else closes[-1]
    # 买入区上限 = EMA5 * (1 + 2%)
    buy_zone_top = last_ema5 * 1.02
    # 警戒区下限 = EMA5 * (1 + 8%)
    warn_zone_bottom = last_ema5 * 1.08

    # 只在合理范围内画参考线
    if mn <= buy_zone_top <= mx:
        byy = py(buy_zone_top)
        sv.append(f'<line x1="{pl}" y1="{byy}" x2="{W-pr}" y2="{byy}" stroke="#4ecdc4" stroke-width="0.5" stroke-dasharray="4,3" opacity="0.4"/>')
        sv.append(f'<text x="{pl+2}" y="{byy-2}" font-family="sans-serif" font-size="7" fill="#4ecdc4" opacity="0.6">买入↑2%</text>')

    if mn <= warn_zone_bottom <= mx:
        wyy = py(warn_zone_bottom)
        sv.append(f'<line x1="{pl}" y1="{wyy}" x2="{W-pr}" y2="{wyy}" stroke="#e94560" stroke-width="0.5" stroke-dasharray="4,3" opacity="0.4"/>')
        sv.append(f'<text x="{pl+2}" y="{wyy-2}" font-family="sans-serif" font-size="7" fill="#e94560" opacity="0.6">警戒↑8%</text>')

    # 在K线区域左右两侧画垂直色带指示当前区域
    if buy_zone_top >= mn:
        buy_zone_rect_h = kline_bottom - pt - py(buy_zone_top)
        if buy_zone_rect_h > 5:
            sv.append(f'<rect x="{pl}" y="{py(buy_zone_top)}" width="3" height="{buy_zone_rect_h}" fill="#4ecdc4" opacity="0.3" rx="1"/>')
    if warn_zone_bottom <= mx:
        warn_rect_y = py(warn_zone_bottom) if mn <= warn_zone_bottom <= mx else pt
        warn_rect_h = (kline_bottom - pt) - py(min(warn_zone_bottom, mx))
        sv.append(f'<rect x="{pl}" y="{warn_rect_y}" width="3" height="{warn_rect_h}" fill="#e94560" opacity="0.3" rx="1"/>')
    # 持有区色带在买入和警戒之间
    mid_rect_y = py(buy_zone_top) if mn <= buy_zone_top <= mx else kline_bottom
    mid_rect_end = py(warn_zone_bottom) if mn <= warn_zone_bottom <= mx else pt
    mid_rect_h = mid_rect_y - mid_rect_end
    if mid_rect_h > 5:
        sv.append(f'<rect x="{pl}" y="{mid_rect_end}" width="3" height="{mid_rect_h}" fill="#ffd700" opacity="0.2" rx="1"/>')

    # 网格线
    for i in range(5):
        y_val = mx - i * rg / 4
        yp = py(y_val)
        sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
        sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="8" fill="#666666">{y_val:.1f}</text>')

    # ── 判断盘中 ──
    today_str = date.today().strftime('%Y-%m-%d')
    is_intraday = klines[-1].get('date', '') == today_str

    # 成交量柱
    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.55, 1)
        vh = volumes[i] / vm * 35
        is_up = closes[i] >= opens_[i]
        vc = '#ff4444' if is_up else '#44aa44'
        is_last = (i == n - 1) and is_intraday
        vdash = ' stroke-dasharray="3,2"' if is_last else ''
        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh, 0.5)}" fill="{vc}" opacity="{"0.25" if is_last else "0.35"}"{vdash}/>')

    # EMA均线
    for ema_vals, color in [(ema5, '#ffd700'), (ema10, '#ff6b6b'), (ema20, '#4ecdc4')]:
        pts = []
        for i in range(n):
            if ema_vals[i] is not None:
                pts.append(f'{px(i)},{py(ema_vals[i])}')
        if pts:
            sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1" opacity="0.7"/>')

    # K线绘制
    for i in range(n):
        x = px(i)
        w = max(cw * 0.45, 1)
        hi, lo, op, cl = highs[i], lows[i], opens_[i], closes[i]
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
        sv.append(f'<text x="{px(n-1) + 20}" y="{py(closes[-1]) - 6}" font-family="sans-serif" font-size="9" fill="#ffd700" opacity="0.8">🕐 盘中</text>')

    # ── 买点标记（类似3L关键点图风格） ──
    # 策略：找BIAS5从>2%下降到<2%的位置（进入买入区），或者从负值回升到正值
    # 只标记前5次最近的
    buy_signal_indices = []
    for i in range(5, n):
        if bias5_vals[i] is None or bias5_vals[i-1] is None:
            continue
        # 条件：昨天BIAS5 >= 2%，今天 < 2%（下穿买入区边界）
        # 或：昨天BIAS5 <= 0，今天 > 0（从负乖离回升）
        if (bias5_vals[i-1] >= 2 and bias5_vals[i] < 2) or \
           (bias5_vals[i-1] <= 0 and bias5_vals[i] > 0 and bias5_vals[i] < 2):
            buy_signal_indices.append(i)

    # 取最多5个最近的
    buy_signals_to_draw = buy_signal_indices[-5:]

    # 警戒区标记：找BIAS5从<8%上穿>8%
    warn_signal_indices = []
    for i in range(5, n):
        if bias5_vals[i] is None or bias5_vals[i-1] is None:
            continue
        if bias5_vals[i-1] < 8 and bias5_vals[i] >= 8:
            warn_signal_indices.append(i)
    warn_signals_to_draw = warn_signal_indices[-3:]

    # 画买点标记（B1, B2, ...）
    buy_cnt = 0
    for idx in buy_signals_to_draw:
        buy_cnt += 1
        xp = px(idx)
        label_y = py(lows[idx]) - 28 - buy_cnt * 15  # 错开放
        # 从K线底部向上引虚线
        sv.append(f'<line x1="{xp}" y1="{py(lows[idx])}" x2="{xp}" y2="{label_y+8}" stroke="#4ecdc4" stroke-width="0.8" stroke-dasharray="2,2" opacity="0.7"/>')
        # 标签背景
        label_text = f'B{buy_cnt}乖离买入'
        sv.append(f'<rect x="{xp-36}" y="{label_y-1}" width="72" height="16" fill="#4ecdc4" opacity="0.85" rx="3"/>')
        sv.append(f'<text x="{xp}" y="{label_y+11}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#000000" font-weight="bold">{label_text}</text>')
        # 在K线下方画绿色三角
        sv.append(f'<polygon points="{xp},{py(lows[idx])+6} {xp-4},{py(lows[idx])} {xp+4},{py(lows[idx])}" fill="#4ecdc4" opacity="0.9"/>')

    # 画警戒区标记
    warn_cnt = 0
    for idx in warn_signals_to_draw:
        warn_cnt += 1
        xp = px(idx)
        label_y = py(highs[idx]) + 12 + warn_cnt * 15  # 在K线上方
        sv.append(f'<line x1="{xp}" y1="{py(highs[idx])}" x2="{xp}" y2="{label_y-8}" stroke="#e94560" stroke-width="0.8" stroke-dasharray="2,2" opacity="0.7"/>')
        label_text = f'W{warn_cnt}警戒⚠️'
        sv.append(f'<rect x="{xp-34}" y="{label_y-1}" width="68" height="16" fill="#e94560" opacity="0.85" rx="3"/>')
        sv.append(f'<text x="{xp}" y="{label_y+11}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#ffffff" font-weight="bold">{label_text}</text>')
        # 在K线上方画红色小三角
        sv.append(f'<polygon points="{xp},{py(highs[idx])-6} {xp-4},{py(highs[idx])} {xp+4},{py(highs[idx])}" fill="#e94560" opacity="0.9"/>')

    # ── 结论文字（顶部状态栏已显示警戒区，此处不再重复） ──
    # 只在非警戒区时才显示一行简洁提示（买入区/持有区简短引导）
    if current_bias <= 8:
        if current_bias < 0:
            buy_zone_text = f'✅ BIAS5={current_bias:.2f}%，乖离率买入区，可逢低吸纳'
        elif current_bias <= 2:
            buy_zone_text = f'✅ BIAS5={current_bias:.2f}%，乖离率买入区，趋势健康可持股'
        else:
            buy_zone_text = f'📊 BIAS5={current_bias:.2f}%，持有区，趋势健康'
        sv.append(f'<text x="{W/2}" y="{kline_bottom+20}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#aaaaaa">{buy_zone_text}</text>')

    # ── BIAS5 副图（小曲线） ──
    bias_top = kline_bottom + 30
    bias_y_range = max(15, max([abs(v) for v in bias5_vals if v is not None]) * 1.2)
    bias_mid = bias_top + bias_h / 2
    bias_py = lambda v: bias_mid - (v / bias_y_range) * (bias_h / 2 - 4)

    # 背景
    sv.append(f'<rect x="{pl}" y="{bias_top-2}" width="{W-pl-pr}" height="{bias_h}" fill="#111122" opacity="0.5" rx="2"/>')

    # 三个区的颜色填充（提高透明度到0.2）
    buy_zone_y = bias_py(2)  # 2%线的Y坐标
    safe_zone_y = bias_py(8)  # 8%线的Y坐标
    # 警戒区（8%以上）：红色
    sv.append(f'<rect x="{pl}" y="{bias_top-2}" width="{W-pl-pr}" height="{safe_zone_y - (bias_top-2)}" fill="#e94560" opacity="0.18" rx="2"/>')
    # 持有区（2%-8%）：黄色
    sv.append(f'<rect x="{pl}" y="{safe_zone_y}" width="{W-pl-pr}" height="{buy_zone_y - safe_zone_y}" fill="#ffd700" opacity="0.12"/>')
    # 买入区（<2%包括负值）：绿色
    sv.append(f'<rect x="{pl}" y="{buy_zone_y}" width="{W-pl-pr}" height="{bias_mid + bias_h/2 - buy_zone_y}" fill="#4ecdc4" opacity="0.14"/>')

    # 在各区右侧加文字标签（关键改进）
    label_x = W - pr - 55
    # 警戒区标签
    warn_label_y = (bias_top - 2 + safe_zone_y) / 2
    sv.append(f'<text x="{label_x}" y="{warn_label_y+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#e94560" font-weight="bold">⚠️ 警戒区</text>')
    # 持有区标签
    hold_label_y = (safe_zone_y + buy_zone_y) / 2
    sv.append(f'<text x="{label_x}" y="{hold_label_y+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#ffd700">持有区</text>')
    # 买入区标签
    buy_label_y = (buy_zone_y + bias_mid + bias_h / 2) / 2
    sv.append(f'<text x="{label_x}" y="{buy_label_y+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#4ecdc4">买入区</text>')

    # 参考线 at 0%, 2%, 8%
    for val, lcolor in [(0, '#888888'), (2, '#4ecdc4'), (8, '#e94560')]:
        yy = bias_py(val)
        sv.append(f'<line x1="{pl}" y1="{yy}" x2="{W-pr}" y2="{yy}" stroke="{lcolor}" stroke-width="0.5" stroke-dasharray="3,2" opacity="0.5"/>')
        sv.append(f'<text x="{pl-4}" y="{yy+3}" text-anchor="end" font-family="sans-serif" font-size="7" fill="{lcolor}">{val}%</text>')
    sv.append(f'<text x="{pl}" y="{bias_top}" font-family="sans-serif" font-size="8" fill="#888888">BIAS5</text>')

    # BIAS5线
    pts_bias = []
    for i in range(n):
        if bias5_vals[i] is not None:
            pts_bias.append(f'{px(i)},{bias_py(bias5_vals[i])}')
    if pts_bias:
        sv.append(f'<polyline points="{" ".join(pts_bias)}" fill="none" stroke="#4ecdc4" stroke-width="1.5" opacity="0.9"/>')

    # BIAS5当前值高亮
    last_bias_y = bias_py(current_bias)
    sv.append(f'<circle cx="{px(n-1)}" cy="{last_bias_y}" r="3" fill="#4ecdc4" opacity="1"/>')
    sv.append(f'<text x="{px(n-1)+5}" y="{last_bias_y+3}" font-family="sans-serif" font-size="9" fill="#4ecdc4" font-weight="bold">BIAS5={current_bias:.1f}%</text>')

    # 日期标签
    for i in range(0, n, 5):
        xd = px(i)
        ds = str(klines[i]['date'])
        mm, dd = ds[4:6], ds[6:8]
        sv.append(f'<text x="{xd}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{xd},{bv+14})">{mm}/{dd}</text>')
    last_ds = str(klines[-1]['date'])
    sv.append(f'<text x="{px(n-1)}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-45,{px(n-1)},{bv+14})">{last_ds[4:6]}/{last_ds[6:8]}</text>')

    # 图例 — 趋势专属
    ly2 = bv + 9
    legend_items = [
        ('#4ecdc4', '买入区(BIAS&lt;2%)'), ('#ffd700', '持有区(2-8%)'), ('#e94560', '警戒区(&gt;8%)'),
        ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20'),
        ('#4ecdc4', 'B乖离买入'), ('#e94560', 'W警戒⚠️'),
    ]
    # 两行布局（每行4个）
    for idx, (lcolor, llabel) in enumerate(legend_items[:4]):
        lx = 60 + idx * 170
        sv.append(f'<rect x="{lx}" y="{ly2}" width="8" height="8" fill="{lcolor}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+11}" y="{ly2+7}" font-family="sans-serif" font-size="9" fill="#888888">{llabel}</text>')
    for idx, (lcolor, llabel) in enumerate(legend_items[4:]):
        lx = 60 + idx * 170
        sv.append(f'<rect x="{lx}" y="{ly2+13}" width="8" height="8" fill="{lcolor}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+11}" y="{ly2+20}" font-family="sans-serif" font-size="9" fill="#888888">{llabel}</text>')

    sv.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    content = '\n'.join(sv)
    with open(output_path, 'w') as f:
        f.write(content)
    return len(content)


def main():
    """批量生成所有趋势股的图表"""
    print("📂 读取数据...")
    if not os.path.exists(DATA_PATH):
        print(f"❌ {DATA_PATH} 不存在")
        return
    with open(DATA_PATH) as f:
        data = json.load(f)
    stocks = data.get('stocks', {})

    all_codes = []
    for sec, sec_stocks in stocks.items():
        for code, klines in sec_stocks.items():
            name = klines[0].get('name', code) if klines else code
            all_codes.append((code, name, sec, klines))

    print(f"共 {len(all_codes)} 只股票")
    ok, fail = 0, 0
    for code, name, sec, klines in all_codes:
        if len(klines) < 20:
            continue
        try:
            out = os.path.join(OUT_DIR, f'trend_{code}.svg')
            size = gen_trend_svg(name, code, klines, out)
            print(f"  ✅ {name}({code}) → {size}B")
            ok += 1
        except Exception as e:
            print(f"  ❌ {code}: {e}")
            fail += 1
    print(f"\n✅ {ok} 成功, {fail} 失败")


if __name__ == '__main__':
    main()

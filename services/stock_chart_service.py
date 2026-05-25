"""
股票 K 线 SVG 图表服务 — 60 日 K 线 + 今日实时虚线蜡烛 + 成交量预估

用法:
    svg_str, err = generate_stock_chart('688428')
    if svg_str:
        # save or serve SVG
    else:
        print(err)
"""

import json
import math
import os
from datetime import datetime

import requests

from backend.core.data_layer import get_all_stocks, ensure_stock_data, get_stock_klines


def _fetch_realtime_quote(code):
    """从腾讯接口获取实时行情，返回 dict 或 None"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
    qcode = f'{prefix}{code[-6:]}'
    try:
        r = requests.get(
            f'https://qt.gtimg.cn/q={qcode}',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.qq.com',
            },
            timeout=5,
        )
        text = r.text
        try:
            text = text.decode('gbk')
        except (UnicodeDecodeError, AttributeError):
            pass
        # 腾讯返回格式: v_qcode="...~name~code~price~..."
        fields = text.split('"')[1].split('~') if '"' in text else []
        if len(fields) >= 40:
            def _f(idx, default=0):
                try:
                    return float(fields[idx]) if fields[idx] else default
                except (ValueError, IndexError):
                    return default

            def _fi(idx, default=0):
                v = fields[idx] if idx < len(fields) else ''
                try:
                    return int(v) if v.strip().isdigit() else default
                except (ValueError, IndexError):
                    return default

            return {
                'open': _f(5),
                'close': _f(3),          # 当前价
                'high': _f(33),
                'low': _f(34),
                'volume_hand': _fi(6),   # 手
                'prev_close': _f(4),
                'change_pct': _f(32),
                'amount': _f(37),
                'name': fields[1] if len(fields) > 1 else '',
            }
    except Exception:
        pass
    return None


def _ema(values, period):
    """指数移动平均"""
    result = [None] * len(values)
    if not values:
        return result
    k = 2.0 / (period + 1)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = (values[i] - result[i - 1]) * k + result[i - 1]
    return result


def _find_breakthrough_points(closes, highs, lows, volumes):
    """识别关键点：突破（突）、前高前低、放量"""
    n = len(closes)
    kps = []
    for i in range(5, n):
        # 前高
        if highs[i] == max(highs[max(0, i - 10):i + 1]) and i > 0:
            kps.append({'idx': i, 'label': '前高', 'y': highs[i]})
        # 前低
        if lows[i] == min(lows[max(0, i - 10):i + 1]) and i > 0:
            kps.append({'idx': i, 'label': '前低', 'y': lows[i]})
        # 放量 / 缩量
        if i >= 10:
            vw = volumes[i - 10:i]
            if vw and max(vw) > 0:
                if volumes[i] >= max(vw) * 1.5:
                    kps.append({'idx': i, 'label': '量', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})
                elif volumes[i] <= min(vw) * 0.5 and volumes[i] > 0:
                    kps.append({'idx': i, 'label': '量', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})
        # 突破
        if i >= 10:
            ph = max(highs[i - 10:i])
            if closes[i] > ph and closes[i] > highs[i] - (highs[i] - lows[i]) * 0.3:
                kps.append({'idx': i, 'label': '突', 'y': highs[i]})
    return kps


def _format_volume(v):
    """格式化成交量显示"""
    if v >= 1e8:
        return f'{v / 1e8:.1f}亿'
    if v >= 1e4:
        return f'{v / 1e4:.0f}万'
    return f'{v:.0f}'


def generate_stock_chart(code):
    """
    生成个股 K 线 SVG（60 日 K 线 + 今日实时虚线蜡烛 + 成交量预估）

    Args:
        code: 股票代码（如 688428、sh688428、SZ000001 等）

    Returns:
        (svg_string, error_or_none)
            - svg_string: 完整 SVG XML 字符串（成功时）
            - error_or_none: None（成功）或错误消息（失败时）
    """
    # ── 0. 标准化 code ──────────────────────────────────────
    raw_code = str(code).strip()
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if raw_code.startswith(pfx):
            raw_code = raw_code[len(pfx):]
            break
    raw_code = raw_code[-6:] if len(raw_code) >= 6 else raw_code

    # ── 1. 获取 60 日 K 线数据 ──────────────────────────────
    stocks = get_all_stocks()
    klines = get_stock_klines(raw_code, stocks=stocks)

    if not klines or len(klines) < 10:
        # 尝试拉取
        ok, msg = ensure_stock_data(raw_code)
        if not ok:
            return None, f'获取数据失败: {msg}'
        stocks = get_all_stocks()
        klines = get_stock_klines(raw_code, stocks=stocks)

    if not klines or len(klines) < 10:
        return None, f'数据不足: {len(klines) if klines else 0} 根K线'

    # 股票名称
    name = klines[0].get('name', raw_code) if klines else raw_code

    # ── 2. 获取实时行情 ─────────────────────────────────────
    rt = _fetch_realtime_quote(raw_code)
    now = datetime.now()

    # ── 3. 准备绘图数据（取最近 60 根）────────────────────
    data_60 = klines[-60:]
    n = len(data_60)

    closes  = [float(k['close']) for k in data_60]
    highs   = [float(k['high']) for k in data_60]
    lows    = [float(k['low']) for k in data_60]
    opens_p = [float(k['open']) for k in data_60]
    volumes = [int(k.get('volume', 0)) for k in data_60]

    # 判断今天数据是否已有（如果最后一天的日期就是今天，说明已收盘）
    last_date = str(data_60[-1].get('date', '')).replace('-', '')
    today_str = now.strftime('%Y%m%d')
    has_today = rt and rt['close'] > 0 and last_date != today_str

    # 汇总最高最低
    all_highs = list(highs)
    all_lows = list(lows)
    if has_today:
        all_highs.append(rt['high'])
        all_lows.append(rt['low'])

    mx = max(all_highs[-60:])
    mn = min(all_lows[-60:])
    rg = mx - mn if mx != mn else 1

    total_bars = n + (1 if has_today else 0)

    # ── 4. SVG 画布参数 ────────────────────────────────────
    W, H = 800, 400
    pl, pr, pt, pb = 60, 20, 30, 55
    cw = (W - pl - pr) / total_bars
    bv = H - pb          # 底部 y
    vol_chart_h = 45     # 成交量区域高度
    candle_top = pt      # K 线区域顶部
    candle_bot = bv - vol_chart_h  # K 线区域底部（成交量上方）

    def px(i):
        """第 i 根 bar 的 x 中心坐标"""
        return pl + i * cw + cw / 2

    def py_price(v):
        """价格 v → y 坐标（K 线区域）"""
        return candle_top + (mx - v) / rg * (candle_bot - candle_top)

    def py_vol(v, max_v):
        """成交量 v → y 坐标（成交量区域，从底部往上画）"""
        if max_v <= 0:
            return bv
        return bv - (v / max_v) * vol_chart_h

    # EMA
    e5  = _ema(closes, 5)
    e10 = _ema(closes, 10)
    e20 = _ema(closes, 20)

    # 关键点
    kps = _find_breakthrough_points(closes, highs, lows, volumes)

    # 支撑线（最近的突破点且低于现价）
    cur_close = closes[-1] if closes else 0
    bk_pts = sorted(
        [kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close],
        key=lambda x: x['y'], reverse=True
    )

    # 压力线（15 日内最高）
    nd15 = min(15, len(closes))
    hi_15 = max(highs[-nd15:]) if nd15 > 0 else mx

    # 今日虚线蜡烛的 label
    today_label = ''
    if has_today:
        pct = rt.get('change_pct', 0)
        sign = '+' if pct >= 0 else ''
        today_label = f'今日 {sign}{pct:.2f}%'

    # ── 5. 组装 SVG ────────────────────────────────────────
    sv = []

    # 5a. 根元素 & 背景
    sv.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
    )
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')

    # 5b. 标题
    title_text = f'{name}({raw_code}) K线图'
    if today_label:
        title_text += f'  |  {today_label}'
    sv.append(
        f'<text x="{W / 2}" y="20" text-anchor="middle" '
        f'font-family="sans-serif" font-size="14" fill="#ffffff" '
        f'font-weight="bold">{title_text}</text>'
    )

    # 5c. 网格线（价格）
    for i in range(6):
        yv = mx - i * rg / 5
        yp = py_price(yv)
        sv.append(
            f'<line x1="{pl}" y1="{yp}" x2="{W - pr}" y2="{yp}" '
            f'stroke="#2a2a4e" stroke-width="0.5"/>'
        )
        sv.append(
            f'<text x="{pl - 5}" y="{yp + 3}" text-anchor="end" '
            f'font-family="sans-serif" font-size="8" fill="#666666">{yv:.2f}</text>'
        )

    # 5d. 成交量/价格分隔线
    sv.append(
        f'<line x1="{pl}" y1="{candle_bot}" x2="{W - pr}" y2="{candle_bot}" '
        f'stroke="#2a2a4e" stroke-width="0.5"/>'
    )
    sv.append(
        f'<line x1="{pl}" y1="{bv}" x2="{W - pr}" y2="{bv}" '
        f'stroke="#2a2a4e" stroke-width="0.5"/>'
    )

    # 5e. 历史成交量柱
    vm = max(volumes) if max(volumes) > 0 else 1
    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.6, 1)
        vh = py_vol(volumes[i], vm)
        is_up = closes[i] >= opens_p[i]
        vc = '#ff4444' if is_up else '#44aa44'
        sv.append(
            f'<rect x="{x}" y="{vh}" width="{w}" '
            f'height="{max(bv - vh, 0.5)}" fill="{vc}" opacity="0.3"/>'
        )

    # 5f. EMA 线
    for ev, clr, lbl in [(e5, '#ffd700', 'EMA5'), (e10, '#ff6b6b', 'EMA10'), (e20, '#4ecdc4', 'EMA20')]:
        pts = []
        for i in range(n):
            if ev[i] is not None:
                pts.append(f'{px(i)},{py_price(ev[i]):.2f}')
        if pts:
            sv.append(
                f'<polyline points="{" ".join(pts)}" fill="none" '
                f'stroke="{clr}" stroke-width="0.8" opacity="0.7"/>'
            )

    # 5g. 历史 K 线蜡烛
    for i in range(n):
        x = px(i)
        w = max(cw * 0.5, 1)
        hi, lo = highs[i], lows[i]
        op, cl = opens_p[i], closes[i]
        yh = py_price(hi)
        yl = py_price(lo)
        yo = py_price(op)
        yc = py_price(cl)
        is_up = cl >= op
        clr = '#ff4444' if is_up else '#44aa44'

        # 影线
        sv.append(
            f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
            f'stroke="{clr}" stroke-width="0.5" opacity="0.6"/>'
        )
        # 实体
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(
            f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
            f'height="{max(bb - bt, 0.5)}" fill="{clr}" opacity="0.85"/>'
        )

    # 5h. 关键点标记
    sz = 4
    for kp in kps:
        if kp['idx'] < n - 60:
            continue
        ai = kp['idx'] - (n - 60) if n > 60 else kp['idx']
        if ai < 0:
            continue
        xp = px(ai)
        yp = py_price(kp['y'])
        clr_map = {'突': '#2196f3', '量': '#ff9800', '前高': '#ff9800', '前低': '#4caf50'}
        clr = clr_map.get(kp['label'], '#ff9800')
        sv.append(
            f'<rect x="{xp - sz}" y="{yp - sz}" width="{sz * 2}" '
            f'height="{sz * 2}" fill="{clr}" opacity="0.85" rx="1"/>'
        )
        sv.append(
            f'<text x="{xp}" y="{yp - sz - 2}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="8" fill="{clr}">{kp["label"]}</text>'
        )

    # 5i. 支撑线
    if bk_pts:
        sy = py_price(bk_pts[0]['y'])
        sv.append(
            f'<line x1="{pl}" y1="{sy}" x2="{W - pr}" y2="{sy}" '
            f'stroke="#4caf50" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        )
        sv.append(
            f'<text x="{pl + 4}" y="{sy - 4}" font-family="sans-serif" '
            f'font-size="9" fill="#4caf50" font-weight="bold">'
            f'支撑 {bk_pts[0]["y"]:.2f}</text>'
        )

    # 5j. 压力线
    if hi_15:
        ry = py_price(hi_15)
        sv.append(
            f'<line x1="{pl}" y1="{ry}" x2="{W - pr}" y2="{ry}" '
            f'stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        )
        sv.append(
            f'<text x="{pl + 4}" y="{ry - 4}" font-family="sans-serif" '
            f'font-size="9" fill="#f44336" font-weight="bold">'
            f'压力 {hi_15:.2f}</text>'
        )

    # 5k. 今日实时虚线蜡烛
    if has_today:
        idx_today = n  # 最后一根之后的索引
        x = px(idx_today)
        w = max(cw * 0.5, 1)

        r_open  = rt['open']
        r_close = rt['close']
        r_high  = rt['high']
        r_low   = rt['low']
        r_vol   = int(rt.get('volume_hand', 0)) * 100  # 手转股
        r_prev  = rt.get('prev_close', r_close)

        # 防止实时数据异常
        if r_high < r_low or r_high <= 0:
            r_high = max(r_open, r_close, r_low) + 0.01
        if r_low <= 0 or r_low > r_high:
            r_low = min(r_open, r_close, r_high) - 0.01

        yh = py_price(r_high)
        yl = py_price(r_low)
        yo = py_price(r_open)
        yc = py_price(r_close)
        is_up = r_close >= r_open
        clr = '#ff4444' if is_up else '#44aa44'

        # 虚线影线
        sv.append(
            f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
            f'stroke="{clr}" stroke-width="0.5" opacity="0.4" stroke-dasharray="4,3"/>'
        )
        # 虚线实体
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(
            f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
            f'height="{max(bb - bt, 0.5)}" fill="none" '
            f'stroke="{clr}" stroke-width="1.2" stroke-dasharray="4,3" opacity="0.7"/>'
        )

        # 成交量虚线柱（预估：用实时成交量/收盘估算今日总量）
        # 预估全日成交量 = 实时成交量 / 当前时间占比（假设 09:30~15:00 = 330分钟）
        r_vol_est = r_vol
        try:
            hh = now.hour
            mm = now.minute
            total_min = 330  # 09:30 ~ 15:00
            elapsed_min = max(0, min(total_min,
                (hh - 9) * 60 + mm - 30 if hh >= 9 else 0
            ))
            if elapsed_min > 0:
                r_vol_est = int(r_vol * total_min / elapsed_min)
        except Exception:
            pass

        vh_rt = py_vol(r_vol_est, vm)
        # 成交量虚线柱
        sv.append(
            f'<rect x="{x - cw * 0.35}" y="{vh_rt}" width="{max(cw * 0.6, 1)}" '
            f'height="{max(bv - vh_rt, 0.5)}" fill="{clr}" opacity="0.25" '
            f'stroke="{clr}" stroke-width="0.6" stroke-dasharray="3,2"/>'
        )

        # 今日标记文字框
        pct_color = '#ff4444' if rt['change_pct'] >= 0 else '#44aa44'
        sign = '+' if rt['change_pct'] >= 0 else ''
        sv.append(
            f'<rect x="{x - 30}" y="{pt - 2}" width="80" height="16" '
            f'rx="3" fill="#1a1a2e" stroke="{pct_color}" stroke-width="0.6"/>'
        )
        sv.append(
            f'<text x="{x}" y="{pt + 11}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="10" fill="{pct_color}" '
            f'font-weight="bold">实时 {sign}{rt["change_pct"]:.2f}%</text>'
        )

    # 5l. 日期标签
    for i in range(0, n, max(1, n // 10)):
        dt = str(data_60[i].get('date', ''))
        xd = px(i)
        sv.append(
            f'<text x="{xd}" y="{bv + 14}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="8" fill="#666666" '
            f'transform="rotate(-40,{xd},{bv + 14})">'
            f'{dt[4:6]}/{dt[6:8] if len(dt) >= 8 else dt[4:6]}</text>'
        )
    # 最后一根日期
    ldt = str(data_60[-1].get('date', ''))
    sv.append(
        f'<text x="{px(n - 1)}" y="{bv + 14}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="8" fill="#666666" '
        f'transform="rotate(-40,{px(n - 1)},{bv + 14})">'
        f'{ldt[4:6]}/{ldt[6:8] if len(ldt) >= 8 else ldt[4:6]}</text>'
    )

    # 今日日期标签（如果有时）
    if has_today:
        xd = px(n)
        sv.append(
            f'<text x="{xd}" y="{bv + 14}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="8" fill="#ff9800" '
            f'transform="rotate(-40,{xd},{bv + 14})">实时</text>'
        )

    # 5m. 底部信息栏
    timestamp = now.strftime('%Y-%m-%d %H:%M')
    data_date = last_date
    info_text = f'数据截至: {timestamp}  |  最新K线: {data_date}'
    if has_today:
        vol_text = _format_volume(int(rt.get('volume_hand', 0)) * 100)
        info_text += f'  |  实时量: {vol_text}'
        if rt['amount'] > 0:
            amt_text = _format_volume(rt['amount'])
            info_text += f'  |  额: {amt_text}'

    sv.append(
        f'<text x="{W / 2}" y="{H - 4}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="9" fill="#555555">{info_text}</text>'
    )

    # 5n. 图例
    ly2 = bv + 28
    legend_items = [
        ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20'),
        ('#2196f3', '突破'), ('#ff9800', '前高/量'), ('#4caf50', '前低'),
    ]
    if has_today:
        legend_items.append(('#ffffff', '今日(虚线)'))
    for idx, (clr2, lbl) in enumerate(legend_items):
        lx = 50 + idx * 100
        sv.append(
            f'<rect x="{lx}" y="{ly2}" width="8" height="8" '
            f'fill="{clr2}" opacity="0.8" rx="1"/>'
        )
        sv.append(
            f'<text x="{lx + 11}" y="{ly2 + 7}" font-family="sans-serif" '
            f'font-size="9" fill="#888888">{lbl}</text>'
        )

    sv.append('</svg>')

    return '\n'.join(sv), None

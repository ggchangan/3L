"""
市场服务 — 板块数据、动量、行业地图、板块K线图
"""
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta

from config import WWW_DIR, DATA_DIR, CACHE_DIR, INDUSTRY_MAP_PATH, REVIEW_CHARTS_DIR
import config  # for config.atomic_json_dump

# 板块缓存目录（位于 WWW_DIR/data/cache，区别于 config.CACHE_DIR）
_BOARD_CACHE_DIR = os.path.join(WWW_DIR, 'data', 'cache')


# =====================================================
# 通用工具
# =====================================================

def _cache_dir():
    os.makedirs(_BOARD_CACHE_DIR, exist_ok=True)
    return _BOARD_CACHE_DIR


def _fetch_with_timeout(fetcher, timeout=30):
    """在后台线程中执行 fetcher()，超时返回 None；fetcher 应写入 result/err 列表。"""
    result = []
    err = [None]

    def _run():
        try:
            r = fetcher()
            result.append(r)
        except Exception as e:
            err[0] = str(e)

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=timeout)

    if err[0]:
        return {'error': err[0]}
    if not result:
        return {'error': 'timeout or no data'}
    return result[0]


# =====================================================
# 1. 行业板块概要（akshare，10 分钟缓存）
# =====================================================

def get_industry_boards():
    """获取行业板块概要数据，10 分钟 TTL 缓存。"""
    cache_dir = _cache_dir()
    today = datetime.now().strftime('%Y-%m-%d')
    cache_file = os.path.join(cache_dir, f'industry_boards_{today}.json')

    # 检查缓存（10 分钟 TTL）
    if os.path.isfile(cache_file):
        mtime = os.path.getmtime(cache_file)
        if (datetime.now().timestamp() - mtime) < 600:
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                pass  # 缓存损坏，重新拉取

    # 拉取新数据
    def fetch():
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        return df.fillna('').to_dict('records')

    data = _fetch_with_timeout(fetch, timeout=30)
    if isinstance(data, dict) and 'error' in data:
        return data

    result_data = {'data': data, 'count': len(data)}
    config.atomic_json_dump(result_data, cache_file)
    return result_data


# =====================================================
# 2. 概念板块概要（akshare，无缓存）
# =====================================================

def get_concept_boards():
    """获取概念板块概要数据。"""
    def fetch():
        import akshare as ak
        df = ak.stock_board_concept_summary_ths()
        return df.fillna('').to_dict('records')

    data = _fetch_with_timeout(fetch, timeout=30)
    if isinstance(data, dict) and 'error' in data:
        return data

    return {'data': data, 'count': len(data)}


# =====================================================
# 3. 行业分类映射
# =====================================================

def get_industry_map():
    """返回行业分类映射数据（industry-map.json）。"""
    if os.path.isfile(INDUSTRY_MAP_PATH):
        with open(INDUSTRY_MAP_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'error': 'no data'}


# =====================================================
# 4. 最强动量数据（涨停+创新高，subprocess 方式）
# =====================================================

def get_momentum_data():
    """获取动量数据，每日缓存一次。调用 fetch_momentum.py 子进程获取数据。"""
    cache_dir = _cache_dir()
    today_str = datetime.now().strftime('%Y-%m-%d')
    cache_file = os.path.join(cache_dir, f'momentum_{today_str}.json')

    # 检查今日缓存
    if os.path.isfile(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 无缓存，拉取新数据
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(WWW_DIR, 'fetch_momentum.py')],
            capture_output=True, text=True, timeout=90
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            config.atomic_json_dump(data, cache_file)
            return data
        else:
            return {'error': r.stderr[-300:]}
    except Exception as e:
        return {'error': str(e)}


# =====================================================
# 5. 板块 K 线关键点 SVG 图
# =====================================================

def get_sector_chart(name):
    """生成板块 60 日 K 线关键点 SVG 图。

    返回 (svg_path, error_or_none):
        - svg_path: SVG 文件绝对路径（成功时）
        - error_or_none: None（成功）或错误消息字符串（失败时）
    """
    if not name:
        return None, 'missing name param'

    svg_file = os.path.join(REVIEW_CHARTS_DIR, f'sector_{name}.svg')

    # 检查缓存（1 小时 TTL）
    if os.path.isfile(svg_file) and (datetime.now().timestamp() - os.path.getmtime(svg_file)) <= 3600:
        return svg_file, None

    # 生成板块关键点图
    try:
        import akshare as ak

        # 获取 60 日 K 线
        now = datetime.now()
        start_d = now - timedelta(days=90)
        start_date = start_d.strftime('%Y%m%d')
        end_date = now.strftime('%Y%m%d')
        df = ak.stock_board_industry_index_ths(
            symbol=name, start_date=start_date, end_date=end_date
        )

        if df is None or len(df) < 10:
            return None, 'insufficient data'

        # 解析数据
        data = []
        for _, row in df.iterrows():
            data.append({
                'day': str(row['日期']),
                'open': float(row['开盘价']),
                'high': float(row['最高价']),
                'low': float(row['最低价']),
                'close': float(row['收盘价']),
                'volume': float(row['成交量']),
            })

        # -------- 关键点识别 --------
        closes = [k['close'] for k in data]
        highs = [k['high'] for k in data]
        lows = [k['low'] for k in data]
        opens = [k['open'] for k in data]
        volumes = [k['volume'] for k in data]
        n = len(data)

        kps = []
        for i in range(5, n):
            if highs[i] == max(highs[max(0, i - 10):i + 1]) and i > 0:
                kps.append({'idx': i, 'type': 1, 'label': '前高', 'y': highs[i]})
            if lows[i] == min(lows[max(0, i - 10):i + 1]) and i > 0:
                kps.append({'idx': i, 'type': 1, 'label': '前低', 'y': lows[i]})
            if i >= 10:
                vw = volumes[i - 10:i]
                if len(vw) > 0 and max(vw) > 0:
                    if volumes[i] >= max(vw) * 1.5:
                        kps.append({
                            'idx': i, 'type': 1, 'label': '量',
                            'y': highs[i] + (highs[i] - lows[i]) * 0.5
                        })
                    elif volumes[i] <= min(vw) * 0.5 and volumes[i] > 0:
                        kps.append({
                            'idx': i, 'type': 1, 'label': '量',
                            'y': highs[i] + (highs[i] - lows[i]) * 0.5
                        })
            if i >= 10:
                ph = max(highs[i - 10:i])
                if closes[i] > ph and closes[i] > opens[i]:
                    kps.append({'idx': i, 'type': 2, 'label': '突', 'y': highs[i]})
                if (i >= 1 and closes[i] > opens[i]
                        and closes[i - 1] < opens[i - 1]
                        and closes[i] > opens[i - 1]
                        and opens[i] < closes[i - 1]):
                    kps.append({'idx': i, 'type': 2, 'label': '反', 'y': lows[i]})

        # -------- SVG 生成 --------
        W, H = 800, 400
        pl, pr, pt, pb = 60, 20, 30, 55
        mx, mn = max(highs[-60:]), min(lows[-60:])
        rg = mx - mn if mx != mn else 1
        nd = min(n, 60)
        data_60 = data[-nd:]
        cw = (W - pl - pr) / nd
        bv = H - pb

        def px(i):
            return pl + i * cw + cw / 2

        def py(v):
            return pt + (mx - v) / rg * (H - pt - pb)

        c60 = [k['close'] for k in data_60]
        h60 = [k['high'] for k in data_60]
        l60 = [k['low'] for k in data_60]
        o60 = [k['open'] for k in data_60]
        v60 = [k['volume'] for k in data_60]
        vm = max(v60) if max(v60) > 0 else 1

        cur_close = c60[-1]
        bk_pts_chart = sorted(
            [kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close and kp['idx'] >= n - nd],
            key=lambda x: x['y'], reverse=True
        )
        nd15 = min(15, len(c60))
        hi_15 = max(h60[-nd15:])

        def ema(d, p):
            r = [None] * len(d)
            m = 2 / (p + 1)
            for i in range(len(d)):
                if i == 0:
                    r[i] = d[i]
                elif r[i - 1] is not None:
                    r[i] = (d[i] - r[i - 1]) * m + r[i - 1]
            return r

        e5 = ema(c60, 5)
        e10 = ema(c60, 10)
        e20 = ema(c60, 20)

        sv = []
        sv.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">'
        )
        sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
        sv.append(
            f'<text x="{W / 2}" y="20" text-anchor="middle" '
            f'font-family="sans-serif" font-size="14" fill="#ffffff" '
            f'font-weight="bold">{name} 关键点图</text>'
        )

        # 网格线
        for i in range(6):
            yv = mx - i * rg / 5
            yp = py(yv)
            sv.append(
                f'<line x1="{pl}" y1="{yp}" x2="{W - pr}" y2="{yp}" '
                f'stroke="#2a2a4e" stroke-width="0.5"/>'
            )
            sv.append(
                f'<text x="{pl - 5}" y="{yp + 3}" text-anchor="end" '
                f'font-family="sans-serif" font-size="8" fill="#666666">{yv:.1f}</text>'
            )
        sv.append(
            f'<line x1="{pl}" y1="{bv}" x2="{W - pr}" y2="{bv}" '
            f'stroke="#2a2a4e" stroke-width="0.5"/>'
        )

        # 成交量柱
        for i in range(nd):
            x = px(i) - cw * 0.35
            w = max(cw * 0.6, 1)
            vh = v60[i] / vm * 40
            is_up = c60[i] >= o60[i]
            vc = '#ff4444' if is_up else '#44aa44'
            sv.append(
                f'<rect x="{x}" y="{bv - vh}" width="{w}" '
                f'height="{max(vh, 0.5)}" fill="{vc}" opacity="0.3"/>'
            )

        # EMA 线
        for ev, clr in [(e5, '#ffd700'), (e10, '#ff6b6b'), (e20, '#4ecdc4')]:
            pts = []
            for i in range(nd):
                if ev[i] is not None:
                    pts.append(f'{px(i)},{py(ev[i])}')
            if pts:
                sv.append(
                    f'<polyline points="{" ".join(pts)}" fill="none" '
                    f'stroke="{clr}" stroke-width="0.8" opacity="0.7"/>'
                )

        # K 线
        for i in range(nd):
            x = px(i)
            w = max(cw * 0.5, 1)
            hi, lo, op, cl = h60[i], l60[i], o60[i], c60[i]
            yh, yl = py(hi), py(lo)
            yo, yc = py(op), py(cl)
            is_up = cl >= op
            clr = '#ff4444' if is_up else '#44aa44'
            sv.append(
                f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
                f'stroke="{clr}" stroke-width="0.5" opacity="0.6"/>'
            )
            bt, bb = min(yo, yc), max(yo, yc)
            sv.append(
                f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
                f'height="{max(bb - bt, 0.5)}" fill="{clr}" opacity="0.8"/>'
            )

        # 关键点标记
        sz = 4
        for kp in kps:
            if kp['idx'] < n - nd:
                continue
            ai = kp['idx'] - (n - nd)
            xp = px(ai)
            yp = py(kp['y'])
            clr = '#ff9800' if kp['type'] == 1 else '#2196f3'
            sv.append(
                f'<rect x="{xp - sz}" y="{yp - sz}" width="{sz * 2}" '
                f'height="{sz * 2}" fill="{clr}" opacity="0.85"/>'
            )
            sv.append(
                f'<text x="{xp}" y="{yp - sz - 2}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="8" fill="{clr}">{kp["label"]}</text>'
            )

        # 支撑线
        if bk_pts_chart:
            sy = py(bk_pts_chart[0]['y'])
            sv.append(
                f'<line x1="{pl}" y1="{sy}" x2="{W - pr}" y2="{sy}" '
                f'stroke="#4caf50" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
            )
            sv.append(
                f'<text x="{pl + 4}" y="{sy - 4}" font-family="sans-serif" '
                f'font-size="9" fill="#4caf50" font-weight="bold">'
                f'支撑 {bk_pts_chart[0]["y"]:.0f}</text>'
            )

        # 压力线
        if hi_15:
            ry = py(hi_15)
            sv.append(
                f'<line x1="{pl}" y1="{ry}" x2="{W - pr}" y2="{ry}" '
                f'stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
            )
            sv.append(
                f'<text x="{pl + 4}" y="{ry - 4}" font-family="sans-serif" '
                f'font-size="9" fill="#f44336" font-weight="bold">'
                f'压力 {hi_15:.0f}</text>'
            )

        # 日期标签
        for i in range(0, nd, 6):
            dt = data_60[i]['day']
            xd = px(i)
            sv.append(
                f'<text x="{xd}" y="{bv + 14}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="8" fill="#666666" '
                f'transform="rotate(-40,{xd},{bv + 14})">{dt[5:7]}/{dt[8:10]}</text>'
            )
        ldi = data_60[-1]['day']
        sv.append(
            f'<text x="{px(nd - 1)}" y="{bv + 14}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="8" fill="#666666" '
            f'transform="rotate(-40,{px(nd - 1)},{bv + 14})">{ldi[5:7]}/{ldi[8:10]}</text>'
        )

        # 图例
        ly2 = bv + 8
        for idx2, (clr2, lbl) in enumerate([
            ('#ff9800', '第1类'), ('#2196f3', '第2类'),
            ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20')
        ]):
            lx = 50 + idx2 * 130
            sv.append(
                f'<rect x="{lx}" y="{ly2}" width="8" height="8" '
                f'fill="{clr2}" opacity="0.8" rx="1"/>'
            )
            sv.append(
                f'<text x="{lx + 11}" y="{ly2 + 7}" font-family="sans-serif" '
                f'font-size="10" fill="#888888">{lbl}</text>'
            )

        sv.append('</svg>')

        os.makedirs(os.path.dirname(svg_file), exist_ok=True)
        with open(svg_file, 'w') as f:
            f.write('\n'.join(sv))

        # === 保存 60 日 K 线数据 JSON ===
        kline_cache = os.path.join(REVIEW_CHARTS_DIR, f'sector_{name}_kline.json')
        kline_data = {
            'closes': [round(x, 2) for x in c60],
            'highs': [round(x, 2) for x in h60],
            'lows': [round(x, 2) for x in l60],
            'volumes': [round(x, 2) for x in v60],
            'key_points': [
                {'idx': k['idx'] - (n - nd), 'type': k['type'],
                 'label': k['label'], 'y': k['y']}
                for k in kps if k['idx'] >= n - nd
            ],
            'high_60': round(max(h60), 2),
            'low_60': round(min(l60), 2),
            'close_now': round(c60[-1], 2),
        }
        try:
            config.atomic_json_dump(kline_data, kline_cache)
        except Exception:
            pass

        # === 形态法判断结构 ===
        c15 = c60[-15:] if len(c60) >= 15 else c60
        e15 = ema(c15, 10)
        up = sum(1 for i in range(1, len(e15)) if e15[i] > e15[i - 1])
        dn = sum(1 for i in range(1, len(e15)) if e15[i] < e15[i - 1])
        r = up / (up + dn) if (up + dn) > 0 else 0.5

        if r >= 0.7:
            structure = '📈 上涨趋势'
        elif r <= 0.3:
            structure = '📉 下降趋势'
        else:
            structure = '➡ 区间震荡'

        # 线性回归检测加速/滞涨
        def reg_slope_y(y_list):
            n_ = len(y_list)
            xs = list(range(n_))
            mx_ = sum(xs) / n_
            my_ = sum(y_list) / n_
            num = sum((xs[i] - mx_) * (y_list[i] - my_) for i in range(n_))
            den = sum((xs[i] - mx_) ** 2 for i in range(n_))
            return num / den if den else 0

        half = len(e15) // 2
        s1 = reg_slope_y(e15[:half])
        s2 = reg_slope_y(e15[half:])

        if structure == '📈 上涨趋势':
            if s1 > 0 and s2 > 0:
                ratio = s2 / s1 if s1 != 0 else 999
                if ratio > 1.8:
                    phase = '🚀 加速'
                elif ratio < 0.4:
                    phase = '⚠️ 滞涨'
                else:
                    phase = '↑ 上行'
            elif s1 > 0 and s2 <= 0:
                phase = '🔻 转跌'
            elif s1 <= 0 and s2 > 0:
                phase = '🟢 转涨'
            else:
                phase = ''
        elif structure == '📉 下降趋势':
            if s1 <= 0 and s2 <= 0:
                ratio = s2 / s1 if s1 != 0 else 0
                if ratio > 1.8:
                    phase = '📉 加速跌'
                else:
                    phase = '↓ 下行'
            elif s1 <= 0 and s2 > 0:
                phase = '🟢 转涨'
            else:
                phase = ''
        else:  # 区间震荡
            if os.path.isfile(kline_cache):
                try:
                    with open(kline_cache) as f:
                        kd = json.load(f)
                    c60_r = kd.get('closes', [])
                    h60_r = kd.get('highs', [])
                    l60_r = kd.get('lows', [])
                    kps_r = kd.get('key_points', [])
                    cur = c60_r[-1] if c60_r else 0

                    bk_pts = sorted(
                        [kp for kp in kps_r if kp['label'] == '突' and kp['y'] < cur],
                        key=lambda x: x['y'], reverse=True
                    )
                    nd15_r = min(15, len(c60_r))
                    hi_15_r = max(h60_r[-nd15_r:]) if len(h60_r) >= nd15_r else None

                    n20 = min(20, len(c60_r))
                    hi_fallback = max(h60_r[-n20:]) if len(h60_r) >= n20 else (max(h60_r) if h60_r else 0)
                    lo_fallback = min(l60_r[-n20:]) if len(l60_r) >= n20 else (min(l60_r) if l60_r else 0)

                    hi_r = hi_15_r if hi_15_r else hi_fallback
                    lo_r = bk_pts[0]['y'] if bk_pts else lo_fallback

                    if hi_r and lo_r and hi_r != lo_r:
                        pct = (cur - lo_r) / (hi_r - lo_r) * 100
                        if pct < 30:
                            phase = '区间底部'
                        elif pct > 70:
                            phase = '区间顶部'
                        else:
                            phase = '区间中段'
                    else:
                        phase = ''
                except Exception:
                    phase = ''
            else:
                phase = ''

        # 写入结构缓存
        struct_cache = os.path.join(CACHE_DIR, 'sector_structure.json')
        struct_data = {}
        if os.path.isfile(struct_cache):
            try:
                with open(struct_cache) as f:
                    struct_data = json.load(f)
            except Exception:
                pass
        struct_data[name] = {
            'structure': structure,
            'phase': phase,
            'updated': str(datetime.now())
        }
        try:
            config.atomic_json_dump(struct_data, struct_cache)
        except Exception:
            pass

    except Exception as e:
        return None, str(e)

    return svg_file, None

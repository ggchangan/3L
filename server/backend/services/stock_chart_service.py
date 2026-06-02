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
from datetime import datetime, timedelta

import requests
import akshare as ak

from backend.core.data_layer import get_all_stocks, get_stock_klines

# 中证全指K线图输出目录
REVIEW_CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'public', 'charts')


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


def _find_breakthrough_points(closes, highs, lows, volumes, structure=None, stage=None,
                              opens=None, detect_reversal=False):
    """识别关键点：突破（突）、前高前低、放量信号

    统一函数，个股/板块/大盘共用。如有差异需求通过参数分支处理。

    关键点类型一览（静态层，基于量价数据实时计算）：

    【供需格局转换点】—— 代表供应/需求主导权切换：
      - 前高：局部波峰，比前后各5根K线的最高都高 → 需求衰竭，供应开始主导
      - 前低：局部波谷，比前后各5根K线的最低都低 → 供应衰竭，需求开始主导
      - 突：区间震荡突破（结构=区间震荡+突破前12日最高+收盘偏高+EMA20以上）→ 需求突破供应区
      - 反：阴转阳反转形态 → 短期供需逆转（仅大盘/板块）

    【量能辅助标注】—— 描述当日成交量行为，不构成供需转换：
      - 放↑：放量上涨（≥1.5倍10日均量，涨幅>2%）
      - 放↓：放量下跌（≥1.5倍10日均量，跌幅>2%）
      - 缩：缩量（接近10日最低量50%）
      - ↯：放量滞涨（stage=放量滞涨+量>1.2倍）

    动态信号层（由 signal_detector 独立检测，通过 triggered_signals 参数传入，
    在SVG右上角以图例框展示）：向上突破/上涨中继/向上反转/供应衰竭/
    向下突破/向下反转/需求衰竭/下跌中继/区间震荡中继

    2026-06-02 修复：
    - 前高/前低/突破/反转各自独立去重（互不干扰）
    - 去重阈值 >= 3（允许3根K线间隔）
    - "突" 仅在结构为 区间震荡 时标记（上升趋势不叫突破）
    - 板块图/大盘图也必须传入 structure

    Args:
        detect_reversal: 是否检测'反'(反转)标记（大盘/板块需要，个股不需要）
    """
    n = len(closes)
    kps = []

    # 每种类型独立去重列表
    _last = {'前高': -99, '前低': -99, '突': -99, '反': -99}

    # EMA20 用于突破点位置校验
    e20 = _ema(closes, 20) if len(closes) >= 20 else [None] * n
    opens_arr = opens or closes

    for i in range(10, n):
        # ── 前高（波峰检测：比前后各5根高才算真前高） ──
        if i >= 5 and i < n - 5:
            if highs[i] > max(highs[i - 5:i]) and highs[i] >= max(highs[i + 1:i + 6]):
                if i - _last.get('前高', -99) >= 3:
                    kps.append({'idx': i, 'label': '前高', 'y': highs[i]})
                    _last['前高'] = i
        elif i >= n - 5:
            # 末尾5根：退回到后向窗口
            if highs[i] == max(highs[max(0, i - 10):i + 1]):
                if i - _last.get('前高', -99) >= 3:
                    kps.append({'idx': i, 'label': '前高', 'y': highs[i]})
                    _last['前高'] = i

        # ── 前低（波谷检测：比前后各5根低才算真前低） ──
        if i >= 5 and i < n - 5:
            if lows[i] < min(lows[i - 5:i]) and lows[i] <= min(lows[i + 1:i + 6]):
                if i - _last.get('前低', -99) >= 3:
                    kps.append({'idx': i, 'label': '前低', 'y': lows[i]})
                    _last['前低'] = i
        elif i >= n - 5:
            # 末尾5根：退回到后向窗口
            if lows[i] == min(lows[max(0, i - 10):i + 1]):
                if i - _last.get('前低', -99) >= 3:
                    kps.append({'idx': i, 'label': '前低', 'y': lows[i]})
                    _last['前低'] = i

        # ── 量能信号 ──
        if i >= 15:
            vw10 = volumes[i - 10:i]
            vw20 = volumes[i - 15:i]
            if vw10 and max(vw10) > 0 and vw20 and max(vw20) > 0:
                vol_10max = max(vw10)
                vol_10avg = sum(vw10) / len(vw10)
                vol_15avg = sum(vw20[-10:]) / 10
                cur_v = volumes[i]
                cur_gain = (closes[i] - closes[i - 1]) / closes[i - 1] * 100

                # 放量滞涨（结合stage）
                if stage == '放量滞涨' and cur_v > vol_10avg * 1.2:
                    kps.append({'idx': i, 'label': '↯', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})
                # 放量涨
                elif cur_v >= vol_10max * 1.5 and cur_gain > 2:
                    kps.append({'idx': i, 'label': '放↑', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})
                # 放量跌
                elif cur_v >= vol_10max * 1.5 and cur_gain < -2:
                    kps.append({'idx': i, 'label': '放↓', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})
                # 缩量（接近10日最低量50%）
                elif cur_v <= min(vw10) * 0.5 and cur_v > 0:
                    kps.append({'idx': i, 'label': '缩', 'y': highs[i] + (highs[i] - lows[i]) * 0.5})

        # ── 突破 — 仅区间震荡的真突破（上升趋势/下跌反弹不标"突"） ──
        if structure == '区间震荡' and i >= 15:
            ph = max(highs[i - 12:i])
            # 突破前12日最高 + 收盘在偏高位置 + EMA20上行过滤
            if (closes[i] > ph and
                closes[i] > closes[i - 1] and
                closes[i] > highs[i] - (highs[i] - lows[i]) * 0.3):
                if e20[i] and closes[i] > e20[i]:
                    if i - _last.get('突', -99) >= 3:
                        kps.append({'idx': i, 'label': '突', 'y': highs[i]})
                        _last['突'] = i

        # ── 反转（仅大盘/板块使用） ──
        if detect_reversal and i >= 1:
            if (closes[i] > opens_arr[i] and closes[i - 1] < opens_arr[i - 1]
                    and closes[i] > opens_arr[i - 1] and opens_arr[i] < closes[i - 1]):
                if i - _last.get('反', -99) >= 3:
                    kps.append({'idx': i, 'label': '反', 'y': lows[i]})
                    _last['反'] = i

    return kps


def _format_volume(v):
    """格式化成交量显示"""
    if v >= 1e8:
        return f'{v / 1e8:.1f}亿'
    if v >= 1e4:
        return f'{v / 1e4:.0f}万'
    return f'{v:.0f}'


def _resolve_today_candle_state(now_hour, now_min, quote, last_date_str, today_str):
    """
    决定今日蜡烛的渲染状态（三态）

    Args:
        now_hour: 当前小时 (0-23)
        now_min: 当前分钟 (0-59)
        quote: 腾讯实时行情 dict 或 None
        last_date_str: 最后一条K线的日期 (YYYYMMDD)
        today_str: 今日日期 (YYYYMMDD)

    Returns:
        dict:
            - type: 'none' | 'trading' | 'settled'
            - is_dashed: bool（仅 trading/settled）
            - label_prefix: '实时' | '涨跌'
            - date_label: '实时' | '今日'
            - vol_prefix: '实时量' | '量'
            - legend_label: '今日(虚线)' | '今日(实心)'
            - estimate_volume: bool
    """
    has_today = quote and quote.get('close', 0) > 0 and last_date_str != today_str
    if has_today:
        # 今日K线仅限交易日 9:30 后才显示（避免凌晨/周末用前一日收盘数据冒充今日）
        now_total_min = now_hour * 60 + now_min
        today_dt = datetime.strptime(today_str, '%Y%m%d')
        is_weekday = today_dt.weekday() < 5
        if not is_weekday or now_total_min < 9 * 60 + 30:
            has_today = False
    if not has_today:
        return {'type': 'none'}

    now_total_min = now_hour * 60 + now_min
    is_trading = (9 * 60 + 30) <= now_total_min < (15 * 60)  # 9:30 ≤ now < 15:00

    if is_trading:
        return {
            'type': 'trading',
            'is_dashed': True,
            'label_prefix': '实时',
            'date_label': '实时',
            'vol_prefix': '实时量',
            'legend_label': '今日(虚线)',
            'estimate_volume': True,
        }
    else:
        return {
            'type': 'settled',
            'is_dashed': False,
            'label_prefix': '涨跌',
            'date_label': '今日',
            'vol_prefix': '量',
            'legend_label': '今日(实心)',
            'estimate_volume': False,
        }


def generate_stock_chart(code, mode='review', triggered_signals=None):
    """
    生成个股 K 线 SVG（60 日 K 线）
    mode=monitor: 含今日实时虚线蜡烛，不缓存；
    其他mode: 仅日K线，不含实时数据，按18:00规则缓存。

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

    now = datetime.now()
    today_str = now.strftime('%Y%m%d')
    is_weekday = now.weekday() < 5

    # ── 1. 获取 60 日 K 线数据 ──────────────────────────────
    stocks = get_all_stocks()
    klines = get_stock_klines(raw_code, stocks=stocks)

    if not klines or len(klines) < 10:
        return None, f'数据不足: {len(klines) if klines else 0} 根K线（等待17:00数据更新）'

        # ── 缓存检查（用最后K线日期作缓存键） ──
    cache_file = None
    if mode != 'monitor':
        last_date = str(klines[-1].get('date', '')).replace('-', '')
        cache_file = os.path.join(
            REVIEW_CHARTS_DIR,
            f'zzqz_stock_chart_{raw_code}_{last_date}.svg'
        )
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return f.read(), None
            except Exception:
                pass

    # 股票名称（从K线取）
    name = ''
    for k in klines:
        if k.get('name'):
            name = k['name']
            break
    name = name or raw_code

    # ── 2. 获取实时行情（仅 monitor 模式） ──────────────────
    rt = None
    if mode == 'monitor':
        rt = _fetch_realtime_quote(raw_code)

    # ── 3. 准备绘图数据（取最近 60 根）────────────────────
    data_60 = klines[-60:]
    n = len(data_60)

    # monitor模式才叠加今日蜡烛
    if mode == 'monitor':
        closes  = [float(k['close']) for k in data_60]
        highs   = [float(k['high']) for k in data_60]
        lows    = [float(k['low']) for k in data_60]
        opens_p = [float(k['open']) for k in data_60]
        volumes = [int(k.get('volume', 0)) for k in data_60]

        last_date = str(data_60[-1].get('date', '')).replace('-', '')
        st = _resolve_today_candle_state(now.hour, now.minute, rt, last_date, today_str)
        has_today = st['type'] != 'none'

        all_highs = list(highs)
        all_lows = list(lows)
        if has_today:
            all_highs.append(rt['high'])
            all_lows.append(rt['low'])
        mx = max(all_highs[-60:])
        mn = min(all_lows[-60:])
        rg = mx - mn if mx != mn else 1
        total_bars = n + (1 if has_today else 0)

        # Today label
        if has_today:
            pct = rt.get('change_pct', 0)
            sign = '+' if pct >= 0 else ''
        else:
            pct = 0
            sign = ''
        today_label = f'{st["label_prefix"]} {sign}{pct:.2f}%' if has_today else ''
    else:
        closes  = [float(k['close']) for k in data_60]
        highs   = [float(k['high']) for k in data_60]
        lows    = [float(k['low']) for k in data_60]
        opens_p = [float(k['open']) for k in data_60]
        volumes = [int(k.get('volume', 0)) for k in data_60]
        has_today = False
        mx = max(highs[-60:])
        mn = min(lows[-60:])
        rg = mx - mn if mx != mn else 1
        total_bars = n
        today_label = ''
        last_date = str(data_60[-1].get('date', '')).replace('-', '')
        date_label = ''
        info_vol_prefix = ''

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

    # 判断结构+阶段
    from backend.core.ema_utils import get_structure, get_stage
    try:
        stock_structure = get_structure(closes)
    except Exception:
        stock_structure = '上涨趋势'
    try:
        stock_stage = get_stage(closes, structure=stock_structure, highs=highs, lows=lows,
                                volumes=volumes, opens_p=opens_p)
    except Exception:
        stock_stage = ''

    # 关键点（传入结构+阶段用于量价信号标注）
    kps = _find_breakthrough_points(closes, highs, lows, volumes,
                                    structure=stock_structure, stage=stock_stage)

    # ── 5. 当前买卖点 — 显示 get_stock_card() 的信号 ──
    try:
        from backend.services.stock_card_service import get_stock_card
        card = get_stock_card(raw_code, last_date, klines=stocks) if last_date else None
        if card:
            sig = card.get('signal', '')
            last_pos = n - 1
            if sig == 'buy':
                kps.append({'idx': last_pos, 'label': '买', 'y': lows[last_pos], 'type': 1})
            elif sig == 'sell':
                kps.append({'idx': last_pos, 'label': '卖', 'y': highs[last_pos], 'type': 1})
    except Exception:
        pass

    # 支撑/压力线 — 综合支撑候选，取最近的一档
    # 2026-06-02 v3: 支撑=前低+前高(角色互换)+突(突破)，均低于现价取最高
    #               压力=前高+前低(角色互换)+突，均高于现价取最低
    cur_close = closes[-1] if closes else 0
    bk_pts = []
    hi_15 = None
    nd20 = min(20, len(closes))

    # 支撑候选：所有低于现价的关键点，取最高的（最接近现价）
    support_candidates = [kp for kp in kps
                          if kp['label'] in ('前低', '前高', '突')
                          and kp['idx'] >= len(closes) - nd20
                          and kp['y'] < cur_close]
    if support_candidates:
        best = max(support_candidates, key=lambda x: x['y'])
        support_y = best['y']
    else:
        support_y = min(lows[-nd20:]) if nd20 > 0 else 0

    # 压力候选：所有高于现价的关键点（全量数据），取最低的（最接近现价）
    resistance_candidates = [kp for kp in kps
                             if kp['label'] in ('前高', '前低', '突')
                             and kp['y'] > cur_close]
    if resistance_candidates:
        best = min(resistance_candidates, key=lambda x: x['y'])
        resistance_y = best['y']
    else:
        resistance_y = None
        # 无高于现价的关键点 → 不画压力线（已突破所有历史压力）

    if stock_structure == '区间震荡':
        bk_pts = [{'y': support_y, 'label': '支撑'}]
        hi_15 = resistance_y

    # ── 5. 组装 SVG ────────────────────────────────────────
    sv = []

    # 5a. 根元素 & 背景
    sv.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
    )
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')

    # 5b. 标题（含结构+阶段标签）
    stage_label = ''
    if stock_structure:
        stage_label = ' [' + stock_structure
        if stock_stage:
            stage_label += '·' + stock_stage
        stage_label += ']'
    title_text = name + '(' + raw_code + ') K线图' + stage_label
    if today_label:
        title_text += '  |  ' + today_label
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
        clr_map = {'突': '#2196f3', '前高': '#ff9800', '前低': '#4caf50', '放↑': '#ff5722', '放↓': '#9c27b0', '缩': '#607d8b', '↯': '#ff9800', '买': '#00e676', '卖': '#e94560'}
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

    # 5j2. 上涨趋势EMA支撑线
    if stock_structure == '上涨趋势' and e10 and len(e10) > 5:
        e10v = e10[-1]
        if e10v:
            ey = py_price(e10v)
            sv.append(
                f'<line x1="{pl}" y1="{ey}" x2="{W - pr}" y2="{ey}" '
                f'stroke="#2196f3" stroke-width="1.0" stroke-dasharray="3,3" opacity="0.5"/>'
            )
            sv.append(
                f'<text x="{W - pr - 4}" y="{ey - 4}" font-family="sans-serif" '
                f'font-size="8" fill="#2196f3">'
                f'EMA10 {e10v:.2f}</text>'
            )

    # 5k. 今日蜡烛（盘中虚线+实时标记，收盘实心+今日标记）
    if has_today:
        idx_today = n  # 最后一根之后的索引
        x = px(idx_today)
        w = max(cw * 0.5, 1)

        candle_style = ' stroke-dasharray="4,3"' if st['is_dashed'] else ''
        vol_style = ' stroke-dasharray="3,2"' if st['is_dashed'] else ''
        vol_fill = 'opacity="0.25"' if st['is_dashed'] else 'opacity="0.3"'
        label_prefix = st['label_prefix']
        date_label = st['date_label']
        info_vol_prefix = st['vol_prefix']

        r_open  = rt['open']
        r_close = rt['close']
        r_high  = rt['high']
        r_low   = rt['low']
        r_vol   = int(rt.get('volume_hand', 0)) * 100  # æè½¬è¡
        r_prev  = rt.get('prev_close', r_close)

        # é²æ­¢å®æ¶æ°æ®å¼å¸¸
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

        # å½±çº¿
        sv.append(
            f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
            f'stroke="{clr}" stroke-width="0.5" opacity="0.4"{candle_style}/>'
        )
        # å®ä½ï¼æ¶çå®å¿å¡«åï¼çä¸­èçº¿è¾¹æ¡ï¼
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(
            f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
            f'height="{max(bb - bt, 0.5)}" '
            f'fill="{clr if not st["is_dashed"] else "none"}" '
            f'stroke="{clr}" stroke-width="1.2"{candle_style} opacity="0.7"/>'
        )

        # æäº¤éæ±ï¼æ¶çå®å¿ï¼çä¸­èçº¿ï¼
        r_vol_est = r_vol
        try:
            hh = now.hour
            mm = now.minute
            # 盘中才预估全天量，收盘后用实际量
            if st['estimate_volume']:
                total_min = 240  # Aè¡å¨å¤©äº¤æ 240åé
                if hh < 12:
                    elapsed_min = (hh - 9) * 60 + mm - 30 if hh >= 9 else 0
                elif hh < 13:
                    elapsed_min = 120  # åä¼
                else:
                    elapsed_min = 120 + (hh - 13) * 60 + mm
                elapsed_min = max(1, min(elapsed_min, total_min))
                r_vol_est = int(r_vol * total_min / elapsed_min)
        except Exception:
            pass

        vh_rt = py_vol(r_vol_est, vm)
        sv.append(
            f'<rect x="{x - cw * 0.35}" y="{vh_rt}" width="{max(cw * 0.6, 1)}" '
            f'height="{max(bv - vh_rt, 0.5)}" fill="{clr}" {vol_fill} '
            f'stroke="{clr}" stroke-width="0.6"{vol_style}/>'
        )

        # æ è®°æå­æ¡
        pct_color = '#ff4444' if rt['change_pct'] >= 0 else '#44aa44'
        sign = '+' if rt['change_pct'] >= 0 else ''
        sv.append(
            f'<rect x="{x - 30}" y="{pt - 2}" width="80" height="16" '
            f'rx="3" fill="#1a1a2e" stroke="{pct_color}" stroke-width="0.6"/>'
        )
        sv.append(
            f'<text x="{x}" y="{pt + 11}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="10" fill="{pct_color}" '
            f'font-weight="bold">{label_prefix} {sign}{rt["change_pct"]:.2f}%</text>'
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
            f'transform="rotate(-40,{xd},{bv + 14})">{date_label}</text>'
        )

    # 5m. 底部信息栏
    timestamp = now.strftime('%Y-%m-%d %H:%M')
    data_date = last_date
    info_text = f'数据截至: {timestamp}  |  最新K线: {data_date}'
    if has_today:
        vol_text = _format_volume(int(rt.get('volume_hand', 0)) * 100)
        info_text += f'  |  {info_vol_prefix}: {vol_text}'
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
        ('#00e676', '买点'), ('#e94560', '卖点'),
    ]
    if has_today:
        legend_items.append(('#ffffff', st['legend_label']))
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


    # 5o. 信号标记（如果提供）
    if triggered_signals:
        sig_x = W - pr - 10
        sig_y = pt + 4
        sv.append(f'<rect x="{sig_x - 85}" y="{sig_y - 2}" width="90" height="{min(len(triggered_signals) * 18 + 4, 90)}" rx="4" fill="#0d1117" stroke="#30363d" stroke-width="0.5" opacity="0.9"/>')
        for si, sig in enumerate(triggered_signals[:5]):
            sy2 = sig_y + si * 18
            dc = sig.get('direction', 'neutral')
            dir_color = '#4ecdc4' if dc == 'bullish' else '#e94560' if dc == 'bearish' else '#ffd700'
            dir_icon = chr(9650) if dc == 'bullish' else chr(9660) if dc == 'bearish' else chr(9670)
            conf = sig.get('confidence', 0)
            nm = (sig.get('name', '') or sig.get('key', ''))[:8]
            sv.append(f'<text x="{sig_x}" y="{sy2 + 10}" text-anchor="end" font-family="monospace" font-size="8" fill="{dir_color}">{dir_icon} {nm} {conf:.0f}</text>')
    sv.append('</svg>')
    svg_content = '\n'.join(sv)

    # ── 5o. 写入缓存（review 模式） ──
    if mode != 'monitor':
        try:
            os.makedirs(REVIEW_CHARTS_DIR, exist_ok=True)
            with open(cache_file, 'w') as f:
                f.write(svg_content)
        except Exception:
            pass  # 缓存写失败不影响返回

    return svg_content, None


def _ema_index(values, period):
    """指数移动平均（用于中证全指）"""
    result = [None] * len(values)
    if not values:
        return result
    k = 2.0 / (period + 1)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = (values[i] - result[i - 1]) * k + result[i - 1]
    return result


def _find_index_keypoints(data):
    """中证全指关键点识别 — 委托统一函数"""
    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    # 计算结构（大盘关键点图也要基于结构判定）
    from backend.core.ema_utils import get_structure
    try:
        idx_structure = get_structure(closes)
    except Exception:
        idx_structure = '上涨趋势'
    kps = _find_breakthrough_points(closes, highs, lows, volumes,
                                    structure=idx_structure,
                                    opens=opens, detect_reversal=True)
    # 兼容旧字段格式（type字段用于SVG渲染）
    for kp in kps:
        kp['type'] = 1 if kp['label'] in ('前高', '前低', '量', '放↑', '放↓', '缩', '↯') else 2
    return kps


def generate_index_chart(mode='review'):
    """生成中证全指K线SVG
    mode=monitor: 总是最新数据（含实时）；mode=review: 18:00前不包含当天数据。
    缓存: 文件名带最后一个K线日期(zzqz_index_chart_YYYYMMDD.svg)。
    Returns: (svg_absolute_path, error_or_none)
    """
    today = datetime.now().date()
    now = datetime.now()
    today_str = now.strftime('%Y%m%d')
    is_weekday = now.weekday() < 5
    use_today = (mode == 'monitor') or (now.hour >= 18 and is_weekday)

    # ── 快速缓存检查（避免每次调 akshare） ──
    if mode == 'monitor':
        cache_file = os.path.join(REVIEW_CHARTS_DIR, 'zzqz_index_chart_monitor.svg')
        if os.path.isfile(cache_file):
            age = now.timestamp() - os.path.getmtime(cache_file)
            if age < 300:  # 5分钟缓存
                return cache_file, None
    else:
        from datetime import timedelta
        if use_today:
            cache_date = today_str
        else:
            if today.weekday() == 0:    # 周一→上周五
                cache_date = (today - timedelta(days=3)).strftime('%Y%m%d')
            elif today.weekday() == 6:   # 周日→上周五
                cache_date = (today - timedelta(days=2)).strftime('%Y%m%d')
            else:
                cache_date = (today - timedelta(days=1)).strftime('%Y%m%d')
        cache_file = os.path.join(REVIEW_CHARTS_DIR, f'zzqz_index_chart_{cache_date}.svg')
        if os.path.isfile(cache_file):
            return cache_file, None

    # ── Fetch 60-day kline data ──────────────────────────
    try:
        ak_data = ak.stock_zh_index_daily_tx(symbol='sh000985')
        ak_data = ak_data.tail(60).reset_index(drop=True)
    except Exception as e:
        # fallback: check any cached file
        for fname in sorted(os.listdir(REVIEW_CHARTS_DIR), reverse=True):
            if fname.startswith('zzqz_index_chart_') and fname.endswith('.svg'):
                fp = os.path.join(REVIEW_CHARTS_DIR, fname)
                if os.path.isfile(fp):
                    return fp, None
        return None, f'failed to fetch index data: {e}'

    data = []
    for _, row in ak_data.iterrows():
        data.append({
            'day': str(row['date']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['amount']) / 1e4,
        })

    # ── 确定缓存日期 ──
    if not use_today:
        # 过滤掉今天的K线（如有）
        data = [d for d in data if d['day'] != today.isoformat()]
        if not data:
            # 全被过滤了（数据只有今天），回退到全量
            data = [{'day': str(row['date']), 'open': float(row['open']),
                     'high': float(row['high']), 'low': float(row['low']),
                     'close': float(row['close']), 'volume': float(row['amount']) / 1e4}
                    for _, row in ak_data.iterrows()]

    last_date = str(data[-1]['day']).replace('-', '')

    # ── 缓存文件名：review=日期缓存，monitor=独立缓存（实时刷新） ──
    if mode == 'monitor':
        cache_file = os.path.join(REVIEW_CHARTS_DIR, 'zzqz_index_chart_monitor.svg')
        # monitor 缓存有效期5分钟
        if os.path.isfile(cache_file):
            age = now.timestamp() - os.path.getmtime(cache_file)
            if age < 300:  # 5分钟
                return cache_file, None
    else:
        cache_file = os.path.join(REVIEW_CHARTS_DIR, f'zzqz_index_chart_{last_date}.svg')
        if os.path.isfile(cache_file):
            return cache_file, None

    # ── 旧文件路径（仍保留兼容） ──
    svg_file = os.path.join(REVIEW_CHARTS_DIR, 'zzqz_v2.svg')
    svg_file2 = os.path.join(REVIEW_CHARTS_DIR, 'sz000985.svg')

    # ── Fetch real-time quote (only after 18:00) ──
    rt = None
    if use_today:
        try:
            r = requests.get(
                'https://qt.gtimg.cn/q=sh000985',
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
                rt = {
                    'open': _f(5), 'close': _f(3), 'high': _f(33), 'low': _f(34),
                    'volume_hand': _fi(6), 'prev_close': _f(4),
                    'change_pct': _f(32), 'amount': _f(37),
                    'name': fields[1] if len(fields) > 1 else '',
                }
        except Exception:
            pass

    last_date_str = str(data[-1]['day']).replace('-', '')
    st = _resolve_today_candle_state(now.hour, now.minute, rt, last_date_str, today_str) if use_today else {'type': 'none'}
    has_today = use_today and st['type'] != 'none'

    closes = [k['close'] for k in data]
    highs = [k['high'] for k in data]
    lows = [k['low'] for k in data]
    opens_p = [k['open'] for k in data]
    volumes = [k['volume'] for k in data]
    n = len(data)

    # y-axis range
    all_highs = list(highs)
    all_lows = list(lows)
    if has_today:
        all_highs.append(rt['high'])
        all_lows.append(rt['low'])

    mx = max(all_highs[-60:])
    mn = min(all_lows[-60:])
    rg = mx - mn if mx != mn else 1

    total_bars = n + (1 if has_today else 0)

    # ── SVG params (1000x550 as gen_index_chart.py) ──────
    W, H = 1000, 550
    pl, pr, pt, pb = 70, 30, 36, 70
    cw = (W - pl - pr) / total_bars
    bv = H - pb

    def px(i): return pl + i * cw + cw / 2
    def py(v): return pt + (mx - v) / rg * (H - pt - pb)

    # EMAs
    e5 = _ema_index(closes, 5)
    e10 = _ema_index(closes, 10)
    e20 = _ema_index(closes, 20)
    vm = max(volumes) if max(volumes) > 0 else 1

    # Keypoints
    kps = _find_index_keypoints(data)
    cur_close = closes[-1] if closes else 0
    bk_pts_chart = sorted(
        [kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close],
        key=lambda x: x['y'], reverse=True
    )
    nd15 = min(15, len(closes))
    hi_15 = max(highs[-nd15:]) if nd15 > 0 else mx

    # Today label
    if has_today:
        pct = rt.get('change_pct', 0)
        sign = '+' if pct >= 0 else ''
    else:
        pct = 0
        sign = ''
    today_label = f'{st["label_prefix"]} {sign}{pct:.2f}%' if has_today else ''

    # ── Build SVG ────────────────────────────────────────
    sv = []
    sv.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
    )
    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')

    # Title
    title_text = '中证全指(000985) K线图'
    if today_label:
        title_text += f'  |  {today_label}'
    sv.append(
        f'<text x="{W / 2}" y="24" text-anchor="middle" '
        f'font-family="sans-serif" font-size="18" fill="#ffffff" '
        f'font-weight="bold">{title_text}</text>'
    )

    # Grid lines
    for i in range(6):
        yv = mx - i * rg / 5
        yp = py(yv)
        sv.append(
            f'<line x1="{pl}" y1="{yp}" x2="{W - pr}" y2="{yp}" '
            f'stroke="#2a2a4e" stroke-width="0.5"/>'
        )
        sv.append(
            f'<text x="{pl - 5}" y="{yp + 3}" text-anchor="end" '
            f'font-family="sans-serif" font-size="9" fill="#666666">{yv:.0f}</text>'
        )
    sv.append(
        f'<line x1="{pl}" y1="{bv}" x2="{W - pr}" y2="{bv}" '
        f'stroke="#2a2a4e" stroke-width="0.5"/>'
    )

    # Historical volume bars
    for i in range(n):
        x = px(i) - cw * 0.35
        w = max(cw * 0.6, 1)
        vh = volumes[i] / vm * 50
        is_up = closes[i] >= opens_p[i]
        vc = '#ff4444' if is_up else '#44aa44'
        sv.append(
            f'<rect x="{x}" y="{bv - vh}" width="{w}" '
            f'height="{max(vh, 0.5)}" fill="{vc}" opacity="0.35"/>'
        )

    # EMA lines
    for ev, clr in [(e5, '#ffd700'), (e10, '#ff6b6b'), (e20, '#4ecdc4')]:
        pts = []
        for i in range(n):
            if ev[i] is not None:
                pts.append(f'{px(i)},{py(ev[i]):.2f}')
        if pts:
            sv.append(
                f'<polyline points="{" ".join(pts)}" fill="none" '
                f'stroke="{clr}" stroke-width="1" opacity="0.7"/>'
            )

    # Historical candles
    for i in range(n):
        x = px(i)
        w = max(cw * 0.5, 1)
        hi, lo = highs[i], lows[i]
        op, cl = opens_p[i], closes[i]
        yh = py(hi)
        yl = py(lo)
        yo = py(op)
        yc = py(cl)
        is_up = cl >= op
        clr = '#ff4444' if is_up else '#44aa44'
        sv.append(
            f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
            f'stroke="{clr}" stroke-width="0.5" opacity="0.6"/>'
        )
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(
            f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
            f'height="{max(bb - bt, 0.5)}" fill="{clr}" opacity="0.8" rx="1"/>'
        )

    # Keypoints
    sz = 5
    for kp in kps:
        i = kp['idx']
        xp = px(i)
        yp = py(kp['y'])
        clr = '#ff9800' if kp['type'] == 1 else '#2196f3'
        sv.append(
            f'<rect x="{xp - sz}" y="{yp - sz}" width="{sz * 2}" '
            f'height="{sz * 2}" fill="{clr}" opacity="0.85"/>'
        )
        sv.append(
            f'<text x="{xp}" y="{yp - sz - 3}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="9" fill="{clr}">{kp["label"]}</text>'
        )

    # Support line
    if bk_pts_chart:
        sy = py(bk_pts_chart[0]['y'])
        sv.append(
            f'<line x1="{pl}" y1="{sy}" x2="{W - pr}" y2="{sy}" '
            f'stroke="#4caf50" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        )
        sv.append(
            f'<text x="{pl + 4}" y="{sy - 4}" font-family="sans-serif" '
            f'font-size="10" fill="#4caf50" font-weight="bold">'
            f'支撑 {bk_pts_chart[0]["y"]:.0f}</text>'
        )

    # Resistance line
    if hi_15:
        ry = py(hi_15)
        sv.append(
            f'<line x1="{pl}" y1="{ry}" x2="{W - pr}" y2="{ry}" '
            f'stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        )
        sv.append(
            f'<text x="{pl + 4}" y="{ry - 4}" font-family="sans-serif" '
            f'font-size="10" fill="#f44336" font-weight="bold">'
            f'压力 {hi_15:.0f}</text>'
        )

    # Today's dashed candle (real-time overlay)
    if has_today:
        idx_today = n
        x = px(idx_today)
        w = max(cw * 0.5, 1)

        r_open = rt['open']
        r_close = rt['close']
        r_high = rt['high']
        r_low = rt['low']

        if r_high < r_low or r_high <= 0:
            r_high = max(r_open, r_close, r_low) + 0.01
        if r_low <= 0 or r_low > r_high:
            r_low = min(r_open, r_close, r_high) - 0.01

        yh = py(r_high)
        yl = py(r_low)
        yo = py(r_open)
        yc = py(r_close)
        is_up = r_close >= r_open
        clr = '#ff4444' if is_up else '#44aa44'

        candle_style = ' stroke-dasharray="4,3"' if st['is_dashed'] else ''
        vol_style = ' stroke-dasharray="3,2"' if st['is_dashed'] else ''

        # Candle wick
        sv.append(
            f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" '
            f'stroke="{clr}" stroke-width="0.5" opacity="0.4"{candle_style}/>'
        )
        # Candle body
        bt, bb = min(yo, yc), max(yo, yc)
        sv.append(
            f'<rect x="{x - w / 2}" y="{bt}" width="{w}" '
            f'height="{max(bb - bt, 0.5)}" '
            f'fill="{clr if not st["is_dashed"] else "none"}" '
            f'stroke="{clr}" stroke-width="1.2"{candle_style} opacity="0.7" rx="1"/>'
        )

        # Volume bar
        r_vol = rt.get('volume_hand', 0)
        vh_rt = (r_vol / 10000) / vm * 50
        vol_fill = 'opacity="0.25"' if st['is_dashed'] else 'opacity="0.3"'
        sv.append(
            f'<rect x="{x - cw * 0.35}" y="{bv - vh_rt}" width="{max(cw * 0.6, 1)}" '
            f'height="{max(vh_rt, 0.5)}" fill="{clr}" {vol_fill} '
            f'stroke="{clr}" stroke-width="0.6"{vol_style}/>'
        )

        # Real-time label
        pct_color = '#ff4444' if rt['change_pct'] >= 0 else '#44aa44'
        sign2 = '+' if rt['change_pct'] >= 0 else ''
        sv.append(
            f'<rect x="{x - 35}" y="{pt - 2}" width="90" height="18" '
            f'rx="3" fill="#1a1a2e" stroke="{pct_color}" stroke-width="0.6"/>'
        )
        sv.append(
            f'<text x="{x}" y="{pt + 12}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="11" fill="{pct_color}" '
            f'font-weight="bold">{st["label_prefix"]} {sign2}{rt["change_pct"]:.2f}%</text>'
        )

        # Text annotation near the candle
        label_x = x + 20
        label_y = yc - 6
        sv.append(
            f'<text x="{label_x}" y="{label_y}" font-family="sans-serif" '
            f'font-size="9" fill="#ffd700" opacity="0.8">{st["label_prefix"]} {sign2}{rt["change_pct"]:.2f}%</text>'
        )
        sv.append(
            f'<text x="{label_x}" y="{label_y + 11}" font-family="sans-serif" '
            f'font-size="8" fill="#888">开:{r_open:.0f} 高:{r_high:.0f} '
            f'低:{r_low:.0f} 现:{r_close:.0f}</text>'
        )

    # Date labels
    step = max(1, n // 8)
    for i in range(0, n, step):
        xd = px(i)
        d = str(data[i]['day'])
        mm, dd = d[5:7], d[8:10]
        sv.append(
            f'<text x="{xd}" y="{bv + 16}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="9" fill="#666666" '
            f'transform="rotate(-45,{xd},{bv + 16})">{mm}/{dd}</text>'
        )
    ldt = str(data[-1]['day'])
    sv.append(
        f'<text x="{px(n - 1)}" y="{bv + 16}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="9" fill="#666666" '
        f'transform="rotate(-45,{px(n - 1)},{bv + 16})">'
        f'{ldt[5:7]}/{ldt[8:10]}</text>'
    )
    if has_today:
        xd = px(n)
        sv.append(
            f'<text x="{xd}" y="{bv + 16}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="9" fill="#ff9800" '
            f'transform="rotate(-45,{xd},{bv + 16})">{st["date_label"]}</text>'
        )

    # Legend
    ly2 = bv + 10
    legend_items = [
        ('#ff9800', '第1类参考点'), ('#2196f3', '第2类供需改变'),
        ('#ffd700', 'EMA5'), ('#ff6b6b', 'EMA10'), ('#4ecdc4', 'EMA20'),
    ]
    if has_today:
        legend_items.append(('#ffffff', st['legend_label']))
    for idx, (clr2, lbl) in enumerate(legend_items):
        lx = 80 + idx * 160
        sv.append(
            f'<rect x="{lx}" y="{ly2}" width="10" height="10" '
            f'fill="{clr2}" opacity="0.8" rx="1"/>'
        )
        sv.append(
            f'<text x="{lx + 14}" y="{ly2 + 9}" font-family="sans-serif" '
            f'font-size="11" fill="#888888">{lbl}</text>'
        )

    # Data freshness label
    timestamp = now.strftime('%Y-%m-%d %H:%M')
    if has_today:
        sv.append(
            f'<text x="{W / 2}" y="{H - 8}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="9" fill="#555">'
            f'数据截至: {timestamp}  |  历史日K线: {data[-1]["day"]} (上一交易日收盘)  |  🟢 盘中更新</text>'
        )
    else:
        sv.append(
            f'<text x="{W / 2}" y="{H - 8}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="9" fill="#555">'
            f'数据截至: {data[-1]["day"]} (已收盘)</text>'
        )

    sv.append('</svg>')

    content = '\n'.join(sv)
    os.makedirs(os.path.dirname(svg_file), exist_ok=True)
    with open(svg_file, 'w') as f:
        f.write(content)
    with open(svg_file2, 'w') as f:
        f.write(content)
    with open(cache_file, 'w') as f:
        f.write(content)

    # 清理旧缓存文件（只保留最新3个，不清理 monitor 独立缓存）
    _all_chart_files = sorted([
        os.path.join(REVIEW_CHARTS_DIR, fn)
        for fn in os.listdir(REVIEW_CHARTS_DIR)
        if fn.startswith('zzqz_index_chart_') and fn != 'zzqz_index_chart_monitor.svg' and fn.endswith('.svg')
    ], key=os.path.getmtime)
    for _old_f in _all_chart_files[:-3]:
        try:
            os.remove(_old_f)
        except OSError:
            pass

    return cache_file, None


def generate_trend_stock_chart(code, mode='review'):
    """生成趋势交易 K 线 SVG（使用 gen_trend_chart 的绘制逻辑）
    mode=monitor: 含今日实时数据叠加到K线，不缓存；
    其他mode: 仅日K线，按18:00规则缓存。
    """
    raw_code = str(code).strip()
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if raw_code.startswith(pfx):
            raw_code = raw_code[len(pfx):]
            break
    raw_code = raw_code[-6:] if len(raw_code) >= 6 else raw_code

    # ── 缓存检查（review 模式：按 18:00 规则判定缓存有效） ──
    now = datetime.now()
    today_str = now.strftime('%Y%m%d')
    is_weekday = now.weekday() < 5
    if mode != 'monitor':
        if now.hour >= 18 and is_weekday:
            cache_date = today_str
        else:
            if now.weekday() == 0:
                cache_date = (now - timedelta(days=3)).strftime('%Y%m%d')
            elif now.weekday() == 6:
                cache_date = (now - timedelta(days=2)).strftime('%Y%m%d')
            else:
                cache_date = (now - timedelta(days=1)).strftime('%Y%m%d')
        cache_file = os.path.join(
            REVIEW_CHARTS_DIR,
            f'zzqz_trend_stock_chart_{raw_code}_{cache_date}.svg'
        )
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return f.read(), None
            except Exception:
                pass

    stocks = get_all_stocks()
    klines = get_stock_klines(raw_code, stocks=stocks)
    if not klines or len(klines) < 10:
        return None, f'数据不足: {len(klines) if klines else 0} 根K线'

    # ── 缓存检查（用最后K线日期作缓存键） ──
    cache_file = None
    if mode != 'monitor':
        last_date = str(klines[-1].get('date', '')).replace('-', '')
        cache_file = os.path.join(
            REVIEW_CHARTS_DIR,
            f'zzqz_trend_stock_chart_{raw_code}_{last_date}.svg'
        )
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return f.read(), None
            except Exception:
                pass

    name = klines[0].get('name', raw_code) if klines else raw_code

    # ── monitor 模式：获取实时行情，作为今日K线叠加 ──
    if mode == 'monitor':
        rt = _fetch_realtime_quote(raw_code)
        if rt and rt.get('close', 0) > 0:
            today_dt = datetime.strptime(today_str, '%Y%m%d')
            if today_dt.weekday() < 5:
                klines.append({
                    'date': today_str,
                    'open': float(rt.get('open', 0)),
                    'high': float(rt.get('high', 0)),
                    'low': float(rt.get('low', 0)),
                    'close': float(rt.get('close', 0)),
                    'volume': int(rt.get('volume_hand', 0)) * 100,
                    'name': name,
                })

    from backend.core.gen_trend_chart import gen_trend_svg
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmpf:
        out_path = tmpf.name

    gen_trend_svg(name, raw_code, klines, out_path, trend_bias=None)

    with open(out_path, 'r') as f:
        svg_str = f.read()
    os.unlink(out_path)

    # ── 写入缓存（review 模式） ──
    if mode != 'monitor':
        try:
            os.makedirs(REVIEW_CHARTS_DIR, exist_ok=True)
            with open(cache_file, 'w') as f:
                f.write(svg_str)
        except Exception:
            pass

    # monitor 模式：注入实时标注（今日虚线+实时量文字）
    if mode == 'monitor':
        now = datetime.now()
        now_total = now.hour * 60 + now.minute
        is_trading = (9 * 60 + 30) <= now_total < (15 * 60)
        if is_trading:
            label = '<text x="685" y="18" font-family="sans-serif" font-size="9" fill="#ffd700" opacity="0.8">📊 今日(虚线)</text>'
            svg_str = svg_str.replace('</svg>', label + '</svg>')

    return svg_str, None

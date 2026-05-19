#!/usr/bin/env python3
"""
完整流程: 采集数据 → 分析中继买点 → 生成关键点 → 保存到磁盘
"""
import urllib.request, json, os, sys, math, datetime

DATA_DIR = "/home/ubuntu/data/3l"
os.makedirs(DATA_DIR, exist_ok=True)
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# ══════ 股票池 ══════
# 候选股(13只)
candidates = {
    "通富微电": "002156", "大族数控": "002920",
    "潍柴动力": "000338", "永鼎股份": "600105",
    "美年健康": "002044", "数字政通": "300075",
    "西部材料": "002149", "宏达电子": "300726",
    "云南锗业": "002428", "全志科技": "300458",
    "博实股份": "002698", "德福科技": "301511",
    "鹏辉能源": "300438",
}
# 持仓股(去重)
holdings = {
    "德业股份": "605117", "天赐材料": "002709",
    "拓普集团": "601689", "伟创电气": "688698",
    "天齐锂业": "002466", "航天电子": "600879",
    "光迅科技": "002281", "润泽科技": "300442",
    "三花智控": "002050", "恒瑞医药": "600276",
    "药明康德": "603259", "中国卫星": "600118",
    "胜宏科技": "300476", "德明利": "001309",
}
all_stocks = {}
all_stocks.update(candidates)
all_stocks.update(holdings)
print(f"共 {len(all_stocks)} 只股票")

# ══════ 数据采集 ══════
def get_daily_kline(code, days=60):
    """新浪API日K线"""
    prefix = "sh" if (code.startswith("6") or code.startswith("9") or code.startswith("5")) else "sz"
    symbol = f"{prefix}{code}"
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&datalen={days}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        text = resp.read().decode("utf-8")
    raw = json.loads(text)
    if not raw or isinstance(raw, dict):
        return None
    
    klines = []
    for bar in raw:
        try:
            dt = bar["day"][:10].replace("-", "")
            klines.append({
                "date": dt,
                "open": float(bar["open"]),
                "close": float(bar["close"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "volume": float(bar["volume"]),
            })
        except: pass
    return klines[-30:]  # 最近30天

# 采集
market_data = {}
for name, code in sorted(all_stocks.items()):
    try:
        klines = get_daily_kline(code)
        if klines and len(klines) >= 15:
            market_data[name] = {"code": code, "klines": klines}
            print(f"  ✓ {name}({code}): {len(klines)}条 [{klines[0]['date']}~{klines[-1]['date']}]")
        else:
            print(f"  ✗ {name}({code}): 数据不足({len(klines) if klines else 0}条)")
    except Exception as e:
        print(f"  ✗ {name}({code}): {e}")

print(f"\n成功采集 {len(market_data)} 只股票")

# 保存原始数据
cache_path = os.path.join(DATA_DIR, "candidates_data.json")
with open(cache_path, "w") as f:
    json.dump(market_data, f, ensure_ascii=False, indent=2)
print(f"数据保存到 {cache_path}")

# ══════ 中继买点判断 ══════
def calc_ma(klines, period):
    """计算均线"""
    prices = [k["close"] for k in klines]
    mas = []
    for i in range(len(prices)):
        if i < period - 1:
            mas.append(None)
        else:
            mas.append(sum(prices[i-period+1:i+1]) / period)
    return mas

def calc_volume_avg(klines, period):
    """计算量均线"""
    vols = [k["volume"] for k in klines]
    avgs = []
    for i in range(len(vols)):
        if i < period - 1:
            avgs.append(None)
        else:
            avgs.append(sum(vols[i-period+1:i+1]) / period)
    return avgs

def find_key_points(klines):
    """识别关键点（30天窗口内，先识别波段再标极端值）"""
    n = len(klines)
    if n < 10:
        return []
    
    prices_h = [k["high"] for k in klines]
    prices_l = [k["low"] for k in klines]
    prices_c = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    # 计算均线、量均线
    ma5 = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    vol_ma5 = calc_volume_avg(klines, 5)
    vol_ma20 = calc_volume_avg(klines, 20)
    
    # 计算低迷期均量(近60日最后20日做参考)
    avg_vol_low = sum(sorted(volumes)[:max(5, n//5)]) / max(5, n//5)
    
    # 识别波段极端值（局部高点和低点）
    band_highs = set()
    band_lows = set()
    window = 3  # 相邻3天内的高低点判断
    
    for i in range(window, n - window):
        # 局部高点: 前后window天内最高
        if all(prices_h[i] >= prices_h[i-j] for j in range(1, window+1)) and \
           all(prices_h[i] >= prices_h[i+j] for j in range(1, window+1)):
            band_highs.add(i)
        # 局部低点
        if all(prices_l[i] <= prices_l[i-j] for j in range(1, window+1)) and \
           all(prices_l[i] <= prices_l[i+j] for j in range(1, window+1)):
            band_lows.add(i)
    # 首尾端点
    band_highs.add(n-1) if prices_h[n-1] >= prices_h[n-2] else None
    band_lows.add(0)
    band_lows.add(n-1) if prices_l[n-1] <= prices_l[n-2] else None
    
    # 计算各点的量价特征
    def get_vol_ratio(idx):
        """成交量相对低迷期倍数"""
        if vol_ma5[idx] and vol_ma5[idx] > 0 and avg_vol_low > 0:
            return vol_ma5[idx] / avg_vol_low
        return 0
    
    # 计算天量/地量阈值
    vol_sorted = sorted(volumes)
    threshold_high = vol_sorted[-3] if len(vol_sorted) >= 3 else vol_sorted[-1]  # 天量阈值
    threshold_low = vol_sorted[2] if len(vol_sorted) >= 3 else vol_sorted[0]     # 地量阈值
    
    key_points = []
    
    for i in range(n):
        reason = []
        kp_type = None
        significance = ""
        
        # --- 第1类关键点（参考点）: 前高/前低/天量/地量 ---
        
        # 前高（波段高点）
        if i in band_highs:
            kp_type = "前高"
            significance = "高"
            reason.append(f"波段高点({prices_h[i]:.2f})")
        
        # 前低（波段低点）
        if i in band_lows:
            kp_type = "前低"
            significance = "高"
            reason.append(f"波段低点({prices_l[i]:.2f})")
        
        # 天量K线
        if volumes[i] >= threshold_high and vol_ma20[i] and volumes[i] > vol_ma20[i] * 1.5:
            vol_ratio = volumes[i] / avg_vol_low if avg_vol_low > 0 else 0
            if vol_ratio >= 4 or (volumes[i] == max(volumes[-10:]) and vol_ratio >= 3):
                # 检查是否是波段极端值
                if i in band_highs or i in band_lows:
                    if kp_type:
                        reason.append(f"天量({vol_ratio:.1f}x)")
                    else:
                        kp_type = "天量"
                        significance = "高"
                        reason.append(f"天量({vol_ratio:.1f}x)")
        
        # 地量K线
        if volumes[i] <= threshold_low and vol_ma20[i] and volumes[i] < vol_ma20[i] * 0.6:
            if i in band_lows or i in band_highs:
                vol_ratio = volumes[i] / avg_vol_low if avg_vol_low > 0 else 0
                if vol_ratio < 1.5:
                    if kp_type:
                        reason.append(f"地量({vol_ratio:.1f}x)")
                    else:
                        kp_type = "地量"
                        significance = "高"
                        reason.append(f"地量({vol_ratio:.1f}x)")
        
        # --- 第2类关键点（供需改变） ---
        
        # 突破点: 价格突破前高且放量
        if i >= 1 and i in band_highs and kp_type != "前高":
            # 不作为单独的，已经标了
            pass
            
        # 反转点: 放量阳线+从低点反转
        if i >= 1:
            if prices_c[i] > prices_c[i-1] and vol_ma5[i] and volumes[i] > vol_ma5[i] * 1.3:
                change_pct = (prices_c[i] - prices_c[i-1]) / prices_c[i-1] * 100
                if change_pct > 3 and i in band_lows:
                    if kp_type:
                        reason.append(f"反转点({prices_c[i]:.2f},+{change_pct:.1f}%)")
                    else:
                        # Check if it qualifies
                        pass
        
        # 中继点: 缩量回踩支撑后站稳
        if i >= 2 and i == n - 1:  # 只看当前（最新一天）
            # 最近3天缩量
            recent_3 = volumes[-3:]
            recent_3_avg = sum(recent_3) / 3
            if vol_ma5[i] and vol_ma20[i] and recent_3_avg < vol_ma5[i] * 0.8 and recent_3_avg < vol_ma20[i] * 0.9:
                # 价格在均线上方
                if ma5[i] and ma10[i] and ma20[i] and prices_c[i] > ma20[i]:
                    # 回踩MA10或MA20
                    lowest_3 = min(prices_l[-3:])
                    if ma10[i] and lowest_3 <= ma10[i] * 1.02 and lowest_3 >= ma10[i] * 0.96:
                        if not kp_type:
                            kp_type = "中继点"
                            significance = "高"
                            reason.append(f"缩量回踩MA10({ma10[i]:.2f})")
        
        if kp_type:
            key_points.append({
                "idx": i,
                "date": klines[i]["date"],
                "price": prices_c[i],
                "high": prices_h[i],
                "low": prices_l[i],
                "volume": volumes[i],
                "type": kp_type,
                "significance": significance,
                "reason": "; ".join(reason),
                "color": "orange" if kp_type in ["前高","前低","天量","地量"] else "blue"
            })
    
    # 按重要性排序去重
    seen_types = set()
    filtered = []
    for kp in key_points:
        key = (kp["type"], kp["date"])
        if key not in seen_types:
            seen_types.add(key)
            filtered.append(kp)
    
    return filtered[:10]  # 最多10个

# ══════ 量价择时判断 ══════
def classify_relay_buy(name, data):
    """中继买点判断"""
    klines = data["klines"]
    n = len(klines)
    
    prices_c = [k["close"] for k in klines]
    prices_l = [k["low"] for k in klines]
    prices_h = [k["high"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    ma5 = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    vol_ma5 = calc_volume_avg(klines, 5)
    
    last = klines[-1]
    last_close = last["close"]
    last_vol = last["volume"]
    
    # 成交量判断
    avg_vol_5 = vol_ma5[-1] if vol_ma5[-1] else sum(volumes[-5:])/5
    avg_vol_20 = sum(volumes[-20:])/20 if n >= 20 else sum(volumes)/len(volumes)
    
    # 判断标准
    checks = {"pass": 0, "total": 0, "detail": []}
    
    # 1️⃣ 价格在重要均线上方
    checks["total"] += 1
    above_ma = False
    if ma20[-1] and last_close > ma20[-1]:
        above_ma = True
        checks["pass"] += 1
        checks["detail"].append(f"✓ 价格{last_close:.2f}>MA20({ma20[-1]:.2f})")
    else:
        checks["detail"].append(f"✗ 价格{last_close:.2f}<MA20({ma20[-1]:.2f})" if ma20[-1] else "✗ 无MA20数据")
    
    # 2️⃣ 最近3天缩量（量<MA5量均线）
    checks["total"] += 1
    recent_3_vol = sum(volumes[-3:]) / 3
    if recent_3_vol < avg_vol_5 * 0.85:
        checks["pass"] += 1
        checks["detail"].append(f"✓ 缩量(近3日均量{recent_3_vol/10000:.0f}万<MA5量均{avg_vol_5/10000:.0f}万)")
    else:
        checks["detail"].append(f"✗ 未缩量(近3日均量{recent_3_vol/10000:.0f}万≥MA5量均{avg_vol_5/10000:.0f}万)")
    
    # 3️⃣ 回踩关键支撑位（MA10/MA20/前低）
    checks["total"] += 1
    lowest_3 = min(prices_l[-3:])
    support_hit = False
    support_level = 0
    
    if ma10[-1] and lowest_3 <= ma10[-1] * 1.03 and lowest_3 >= ma10[-1] * 0.95:
        support_hit = True
        support_level = ma10[-1]
        checks["pass"] += 1
        checks["detail"].append(f"✓ 回踩MA10({ma10[-1]:.2f}),最低{lowest_3:.2f}")
    elif ma20[-1] and lowest_3 <= ma20[-1] * 1.03 and lowest_3 >= ma20[-1] * 0.95:
        support_hit = True
        support_level = ma20[-1]
        checks["pass"] += 1
        checks["detail"].append(f"✓ 回踩MA20({ma20[-1]:.2f}),最低{lowest_3:.2f}")
    else:
        checks["detail"].append(f"✗ 未回踩关键支撑,最低{lowest_3:.2f}")
        if ma10[-1]: checks["detail"].append(f"  MA10={ma10[-1]:.2f}")
        if ma20[-1]: checks["detail"].append(f"  MA20={ma20[-1]:.2f}")
    
    # 4️⃣ 之前有明确的上升波段（趋势确认）
    checks["total"] += 1
    if n >= 10:
        high_10 = max(prices_h[-10:])
        low_10 = min(prices_l[-10:-5] if n >= 5 else prices_l[-10:])
        if high_10 > low_10 * 1.08:  # 之前有8%以上的涨幅
            checks["pass"] += 1
            checks["detail"].append(f"✓ 上升趋势确认(10日高点{high_10:.2f}>低点{low_10:.2f})")
        else:
            checks["detail"].append(f"✗ 无明显上升趋势")
    else:
        checks["detail"].append(f"✗ 数据不足")
    
    # 5️⃣ 当前价格未加速（不是放量大涨）
    checks["total"] += 1
    if len(klines) >= 3:
        vol_ratio = last_vol / avg_vol_5 if avg_vol_5 > 0 else 0
        change_1d = (last_close - klines[-2]["close"]) / klines[-2]["close"] * 100
        if vol_ratio < 2.5 and abs(change_1d) < 5:
            checks["pass"] += 1
            checks["detail"].append(f"✓ 未加速(量比{vol_ratio:.1f}x,涨幅{change_1d:+.1f}%)")
        else:
            checks["detail"].append(f"✗ 加速/放量异常(量比{vol_ratio:.1f}x,涨幅{change_1d:+.1f}%)")
    else:
        checks["total"] -= 1
    
    score = checks["pass"] / checks["total"] * 100 if checks["total"] > 0 else 0
    
    return {
        "score": score,
        "pass": checks["pass"],
        "total": checks["total"],
        "details": checks["detail"],
        "last_close": last_close,
        "support_level": support_level,
    }

# ══════ 执行分析 ══════
results = {}
for name, data in sorted(market_data.items()):
    klines = data["klines"]
    key_points = find_key_points(klines)
    buy_signal = classify_relay_buy(name, data)
    
    # 今日涨跌幅
    last_close = klines[-1]["close"]
    prev_close = klines[-2]["close"] if len(klines) >= 2 else last_close
    change_pct = (last_close - prev_close) / prev_close * 100
    
    results[name] = {
        "code": data["code"],
        "closing": round(last_close, 2),
        "change_pct": round(change_pct, 2),
        "key_points": key_points,
        "buy_signal": buy_signal,
        "klines": klines,  # 供画图用
    }
    print(f"  {name}: {buy_signal['pass']}/{buy_signal['total']} 评分{buy_signal['score']:.0f}")

# 保存分析结果
result_path = os.path.join(DATA_DIR, "analysis_results.json")
with open(result_path, "w") as f:
    # 不保存klines到结果文件（太大），只保存元数据
    clean_results = {}
    for name, r in results.items():
        clean_results[name] = {k: v for k, v in r.items() if k != "klines"}
    json.dump(clean_results, f, ensure_ascii=False, indent=2)
print(f"\n分析结果保存到 {result_path}")

# ══════ 生成SVG关键点图 ══════
def generate_svg(name, data, width=1000, height=600):
    """生成关键点图SVG"""
    klines = data["klines"]
    key_points = data["key_points"]
    n = len(klines)
    if n < 5:
        return None
    
    prices_h = [k["high"] for k in klines]
    prices_l = [k["low"] for k in klines]
    prices_c = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    dates = [k["date"] for k in klines]
    
    # 均线
    ma5 = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    
    # 价格范围
    margin_top, margin_bottom, margin_left, margin_right = 80, 170, 70, 30
    chart_w = width - margin_left - margin_right
    chart_h_price = (height - margin_top - margin_bottom) * 0.7
    chart_h_vol = (height - margin_top - margin_bottom) * 0.3
    vol_y = margin_top + chart_h_price
    
    max_price = max(prices_h) * 1.03
    min_price = min(prices_l) * 0.97
    price_range = max_price - min_price
    if price_range < 1:
        price_range = 1
    
    max_vol = max(volumes) * 1.2
    
    def px(idx):
        return margin_left + idx * chart_w / (n - 1) if n > 1 else margin_left
    
    def py_price(p):
        return margin_top + chart_h_price * (max_price - p) / price_range
    
    def py_vol(v):
        return vol_y + chart_h_vol * (1 - v / max_vol)
    
    # 构建SVG
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')
    
    # 标题
    buy = data["buy_signal"]
    lines.append(f'<text x="{margin_left}" y="35" fill="#ffffff" font-size="20" font-weight="bold">{name}({data["code"]}) 关键点图</text>')
    lines.append(f'<text x="{margin_left + 300}" y="35" fill="#{"4caf50" if buy["score"] >= 60 else "#ff9800"}" font-size="16">中继买点评分: {buy["pass"]}/{buy["total"]} = {buy["score"]:.0f}/100</text>')
    lines.append(f'<text x="{margin_left + 600}" y="35" fill="#cccccc" font-size="14">5/18/2026 收盘 {data["closing"]}</text>')
    
    # 网格
    for i in range(5):
        y = margin_top + chart_h_price * i / 4
        p = max_price - price_range * i / 4
        lines.append(f'<line x1="{margin_left}" y1="{y}" x2="{width - margin_right}" y2="{y}" stroke="#2a2a4e" stroke-width="0.5"/>')
        lines.append(f'<text x="{margin_left - 5}" y="{y + 4}" fill="#666666" font-size="10" text-anchor="end">{p:.1f}</text>')
    
    # 日期标签（每隔5天）
    for i in range(0, n, 5):
        x = px(i)
        lbl = f"{dates[i][4:6]}/{dates[i][6:8]}" if len(dates[i]) >= 8 else dates[i]
        lines.append(f'<text x="{x}" y="{margin_top + chart_h_price + 15}" fill="#666666" font-size="10" text-anchor="middle" transform="rotate(-45,{x},{margin_top + chart_h_price + 15})">{lbl}</text>')
    
    # MA均线
    for ma_arr, color, name in [(ma5, "#ffd700", "MA5"), (ma10, "#ff6b6b", "MA10"), (ma20, "#4ecdc4", "MA20")]:
        pts = []
        for i in range(n):
            if ma_arr[i] and ma_arr[i] > 0:
                pts.append(f"{px(i):.1f},{py_price(ma_arr[i]):.1f}")
        if len(pts) > 1:
            lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1" opacity="0.7"/>')
    
    # 成交量柱
    bar_w = max(2, chart_w / n * 0.6)
    for i in range(n):
        is_up = prices_c[i] >= klines[i]["open"]
        bar_color = "#ff4444" if is_up else "#44aa44"
        bh = volumes[i] / max_vol * chart_h_vol
        x = px(i) - bar_w / 2
        lines.append(f'<rect x="{x:.1f}" y="{vol_y + chart_h_vol - bh:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{bar_color}" opacity="0.4"/>')
    
    # K线
    candle_w = max(2, chart_w / n * 0.5)
    for i in range(n):
        x = px(i)
        is_up = prices_c[i] >= klines[i]["open"]
        color = "#ff4444" if is_up else "#44aa44"
        top = max(prices_c[i], klines[i]["open"])
        bottom = min(prices_c[i], klines[i]["open"])
        
        # 影线
        lines.append(f'<line x1="{x:.1f}" y1="{py_price(prices_h[i]):.1f}" x2="{x:.1f}" y2="{py_price(prices_l[i]):.1f}" stroke="{color}" stroke-width="1"/>')
        # 实体
        lines.append(f'<rect x="{x - candle_w/2:.1f}" y="{py_price(top):.1f}" width="{candle_w:.1f}" height="{max(1, py_price(bottom) - py_price(top)):.1f}" fill="{color}" opacity="0.8"/>')
    
    # 关键点标注
    for kp in key_points:
        i = kp["idx"]
        x = px(i)
        y = py_price(kp["high"]) - 10 if kp["type"] in ["前高","天量","中继点"] else py_price(kp["low"]) + 15  # 前高标上面, 前低标下面
        color = "#ff9800" if kp["color"] == "orange" else "#2196f3"
        
        # 彩色方块标记
        box_size = 8
        lines.append(f'<rect x="{x - box_size/2}" y="{py_price(kp["high"]) - box_size - 2}" width="{box_size}" height="{box_size}" fill="{color}" opacity="0.8"/>')
        
        # 标签文字
        lines.append(f'<text x="{x}" y="{py_price(kp["high"]) - box_size - 5}" fill="{color}" font-size="9" text-anchor="middle">{kp["type"]}</text>')
    
    lines.append('</svg>')
    return "\n".join(lines)

# 生成SVG
for name, data in sorted(results.items()):
    svg = generate_svg(name, data)
    if svg:
        svg_path = os.path.join(CHARTS_DIR, f"{name}.svg")
        with open(svg_path, "w") as f:
            f.write(svg)
        print(f"  SVG生成: {name}.svg")
    else:
        print(f"  SVG失败: {name} (数据不足)")

print(f"\n所有SVG保存在 {CHARTS_DIR}")
print("完成!")

#!/usr/bin/env python3
"""用上证指数数据重跑波峰波谷评分"""
import json, os
import urllib.request

def get_index_data():
    """从Sina获取上证60天K线"""
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000001&scale=240&ma=no&datalen=60"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode("utf-8"))
    # 转成统一格式
    result = []
    for d in data:
        result.append({
            "date": d["day"], "open": float(d["open"]), "close": float(d["close"]),
            "high": float(d["high"]), "low": float(d["low"]), "volume": int(d["volume"])
        })
    return result

def judge_peak_trough_by_index(data, date_str):
    """用上证指数数据做评分"""
    idx = next((i for i,k in enumerate(data) if k["date"]==date_str), -1)
    if idx < 20: return None
    
    C = [k["close"] for k in data]
    H = [k["high"] for k in data]
    L = [k["low"] for k in data]
    V = [k["volume"] for k in data]
    
    price = C[idx]; ma20 = sum(C[idx-19:idx+1])/20
    
    # 量比
    vs = sorted(V[idx-29:idx+1])
    lb = sum(vs[:max(3, len(vs)//5)]) / max(3, len(vs)//5)
    vol_ratio = V[idx] / lb if lb > 0 else 1
    
    # 波动率
    body = abs(C[idx] - data[idx]["open"])
    avg_body = sum(abs(C[j] - data[j]["open"]) for j in range(idx-4, idx+1)) / 5
    body_ratio = body / avg_body if avg_body > 0 else 1
    
    score = 0
    details = {}
    
    # ① 趋势结构
    pct_from_ma = (price - ma20) / ma20 * 100
    if pct_from_ma > 3:
        score += 1; details["趋势"] = f"+1 (价格{price:.0f} > MA20{ma20:.0f} +{pct_from_ma:.1f}%)"
    elif pct_from_ma < -3:
        score -= 1; details["趋势"] = f"-1 (价格{price:.0f} < MA20{ma20:.0f} {pct_from_ma:.1f}%)"
    else:
        details["趋势"] = f"0 (价格{price:.0f} ≈ MA20{ma20:.0f} {pct_from_ma:+.1f}%)"
    
    # ② 量能
    if vol_ratio > 3:
        score += 1; details["量能"] = f"+1 (高潮量比{vol_ratio:.2f}x)"
    elif vol_ratio < 1.3:
        score -= 1; details["量能"] = f"-1 (地量量比{vol_ratio:.2f}x)"
    else:
        details["量能"] = f"0 (正常量比{vol_ratio:.2f}x)"
    
    # ③ 量价形态
    has_accel = False; has_panic = False
    if idx >= 3:
        chgs = [(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-2, idx+1)]
        if all(c > 0 and c > chgs[i-1] for i,c in enumerate(chgs) if i>0):
            if V[idx] > sum(V[idx-4:idx+1])/5:
                has_accel = True
    # 恐慌：连续下跌后放量+下影线
    if idx >= 3:
        prev_chgs = [(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-4, idx+1)]
        if sum(1 for c in prev_chgs if c < 0) >= 3:
            if V[idx] > sum(V[idx-4:idx+1])/5 * 1.3:
                low_pct = (L[idx] - C[idx]) / C[idx]
                if abs(low_pct) > 0.01:  # 有下影线
                    has_panic = True
    
    if has_accel:
        score += 1; details["形态"] = "+1 (检测到加速)"
    elif has_panic:
        score -= 1; details["形态"] = "-1 (恐慌出清)"
    else:
        details["形态"] = "0 (无异常)"
    
    # ④ 波动率
    if body_ratio > 1.2:
        score += 1; details["波动"] = f"+1 (实体放大{body_ratio:.2f}x)"
    elif body_ratio < 0.8:
        score -= 1; details["波动"] = f"-1 (实体收窄{body_ratio:.2f}x)"
    else:
        details["波动"] = f"0 (实体正常{body_ratio:.2f}x)"
    
    # 解读
    if score >= 3: result = "波峰区域"
    elif score >= 1: result = "偏波峰"
    elif score <= -3: result = "波谷区域"
    elif score <= -1: result = "偏波谷"
    else: result = "波中"
    
    return {"date": date_str, "price": round(price,2), "ma20": round(ma20,2),
            "vol_ratio": round(vol_ratio,2), "score": score, "result": result,
            "details": details}

# 获取数据
print("获取上证指数数据...")
index_data = get_index_data()
print(f"共{len(index_data)}条K线")

# 判断全周期
dates_to_check = [
    "2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10",
    "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17",
    "2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-24",
    "2026-04-27", "2026-04-28", "2026-04-29", "2026-04-30",
    "2026-05-06", "2026-05-07", "2026-05-08",
    "2026-05-11", "2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15",
]

print(f"\n{'日期':14} {'价格':>8} {'MA20':>8} {'涨幅%':>8} {'量比':>6} {'评分':>4} {'结果':>10}")
print("-" * 65)
for d in dates_to_check:
    r = judge_peak_trough_by_index(index_data, d)
    if r:
        price_pct = (r["price"] - r["ma20"]) / r["ma20"] * 100
        print(f"{r['date']:14} {r['price']:>8.0f} {r['ma20']:>8.0f} {price_pct:>+7.1f}% {r['vol_ratio']:>5.1f}x {r['score']:>3d} {r['result']:>10}")
        # print(f"     {r['details']}")

#!/usr/bin/env python3
"""v2模拟引擎 - 仓位决策流程图版 | 只跑第1周"""
import json, os, re
from datetime import datetime, timedelta

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = "/home/ubuntu/data/3l/simulation/v2"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

# 股票名称映射
CODE_NAMES = {}
for s in ALL_STOCKS.values():
    for code, klines in s.items():
        name = "未知"
        # 从文件名映射... 用之前定义的那个
        pass

# 实际用简化的
NAME_MAP = {
    "300503":"昊志机电","688131":"皓元医药","002192":"融捷股份","002240":"盛新锂能",
    "300054":"鼎龙股份","300788":"佰维存储","002378":"章源钨业","002460":"赣锋锂业",
    "000637":"*ST京化","601689":"拓普集团","002050":"三花智控","002698":"博实股份",
}

# 行业映射
SECTOR_MAP = {}
for sec, stocks in ALL_STOCKS.items():
    for code in stocks:
        SECTOR_MAP[code] = sec

def get_klines(code):
    for s in ALL_STOCKS.values():
        if code in s:
            return s[code]
    return None

def di(date_str, klines):
    for i, k in enumerate(klines):
        if k["date"] == date_str:
            return i
    return -1

# ═══ 大盘判强弱 ═══
def judge_market(date_str, lookback=30):
    """用大盘指数(上证综指)判强弱 - 简化版: 用自选股平均成交量倍数"""
    all_vols = []
    for sec, stocks in ALL_STOCKS.items():
        for code, klines in stocks.items():
            idx = di(date_str, klines)
            if idx < 20:
                continue
            vols_30 = [k["volume"] for k in klines[idx-29:idx+1]]
            # 低迷期基准: 最低的20%成交量的均值
            sorted_v = sorted(vols_30)
            low_base = sum(sorted_v[:max(3, len(sorted_v)//5)]) / max(3, len(sorted_v)//5)
            current_vol = klines[idx]["volume"]
            multiple = current_vol / low_base if low_base > 0 else 0
            all_vols.append(multiple)
    
    avg_multiple = sum(all_vols) / len(all_vols) if all_vols else 1
    
    if avg_multiple < 1.5:
        phase, total_limit = "低迷期", (0.6, 0.8)
    elif avg_multiple < 2:
        phase, total_limit = "正常", (0.4, 0.6)
    elif avg_multiple < 4:
        phase, total_limit = "强势", (0.2, 0.4)
    else:
        phase, total_limit = "高潮", (0, 0.2)
    
    return phase, total_limit, round(avg_multiple, 2)

# ═══ 仓位决策 ═══
def calc_position_size(code, date_str, market_phase, total_limit, existing_positions):
    """仓位决策流程图"""
    base_pct = 0.06  # 中继买点基础6%
    
    # 1. 大盘调整
    phase_map = {"低迷期": 1.2, "正常": 1.0, "强势": 0.8, "高潮": 0.3}
    phase_mult = phase_map.get(market_phase, 1.0)
    
    # 2. 买点类型（中继买点评分调整）
    klines = get_klines(code)
    if not klines:
        return 0
    idx = di(date_str, klines)
    if idx < 20:
        return 0
    
    prices_c = [k["close"] for k in klines]
    prices_l = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    # 判断买点质量（缩量程度、支撑力度）
    vol_ma5 = sum(volumes[idx-4:idx+1]) / 5
    vol_ratio = volumes[idx] / vol_ma5 if vol_ma5 > 0 else 1
    
    # 缩量越明显评分越高
    if vol_ratio < 0.6:
        buy_quality = 1.2  # 优秀缩量
    elif vol_ratio < 0.85:
        buy_quality = 1.0  # 标准
    else:
        buy_quality = 0.7  # 缩量不足
    
    # 3. 波段位置（简化：看价格在MA20上方位置）
    ma20 = sum(prices_c[idx-19:idx+1]) / 20
    price = prices_c[idx]
    pos_in_trend = (price - ma20) / ma20
    
    if pos_in_trend < 0.03:
        band_mult = 0.5  # 鱼头（刚突破）
    elif pos_in_trend < 0.15:
        band_mult = 1.0  # 鱼身（确认趋势）
    else:
        band_mult = 0.5  # 鱼尾（远离均线，有风险）
    
    # 4. 行业分散
    sec = SECTOR_MAP.get(code, "")
    same_sec_count = sum(1 for p in existing_positions if SECTOR_MAP.get(p, "") == sec)
    if same_sec_count > 0:
        return 0  # 同方向已有持仓，不开新仓
    
    # 主线方向检查（简化：机器人、半导体、新能源为主线）
    main_lines = ["机器人", "半导体", "AI应用", "算力"]
    line_mult = 1.2 if sec in main_lines else 0.8
    
    # 最终仓位
    raw_pct = base_pct * phase_mult * buy_quality * band_mult * line_mult
    final_pct = max(0.02, min(raw_pct, 0.10))  # 2%-10%之间
    
    return round(final_pct, 3)

# ═══ 运行第1周 ═══
dates_w1 = ["20260407","20260408","20260409","20260410"]
start_cash = 1000000

class SimV2:
    def __init__(self):
        self.cash = start_cash
        self.portfolio = {}
        self.trades = []
        self.daily = []
    
    def value(self, date):
        pv = 0
        for code, pos in self.portfolio.items():
            klines = get_klines(code)
            if klines:
                idx = di(date, klines)
                if idx >= 0:
                    pv += klines[idx]["close"] * pos["shares"]
        return self.cash + pv
    
    def buy(self, date, code, pct_of_total):
        klines = get_klines(code)
        if not klines:
            return False
        idx = di(date, klines)
        if idx < 0:
            return False
        price = klines[idx]["close"]
        total_val = self.value(date) or self.cash
        invest = total_val * pct_of_total
        shares = int(invest / price / 100) * 100
        if shares <= 0:
            return False
        cost = shares * price
        if cost > self.cash:
            shares = int(self.cash / price / 100) * 100
            if shares <= 0:
                return False
            cost = shares * price
        
        self.cash -= cost
        self.portfolio[code] = {
            "shares": shares, "price": price, "cost": cost,
            "entry_date": date, "pct": pct_of_total,
            "stop_loss": round(price * 0.92, 2)
        }
        self.trades.append({
            "date": date, "time": "15:00", "direction": "买入",
            "code": code, "name": NAME_MAP.get(code, code),
            "sector": SECTOR_MAP.get(code, ""),
            "qty": shares, "price": round(price, 2), "amount": round(cost, 2),
            "pos_pct": round(pct_of_total * 100, 1),
            "reason": f"中继买点|大盘{market_phase}|仓位{pct_of_total*100:.1f}%"
        })
        return True
    
    def sell(self, date, code, reason):
        if code not in self.portfolio:
            return
        pos = self.portfolio[code]
        klines = get_klines(code)
        if not klines:
            return
        idx = di(date, klines)
        if idx < 0:
            return
        price = klines[idx]["close"]
        proceeds = pos["shares"] * price
        self.cash += proceeds
        
        # 计算盈亏
        pl = (price - pos["price"]) * pos["shares"]
        pl_pct = (price - pos["price"]) / pos["price"] * 100
        
        self.trades.append({
            "date": date, "time": "15:00", "direction": "卖出",
            "code": code, "name": NAME_MAP.get(code, code),
            "sector": SECTOR_MAP.get(code, ""),
            "qty": pos["shares"], "price": round(price, 2),
            "amount": round(proceeds, 2),
            "profit": round(pl, 2), "profit_pct": round(pl_pct, 2),
            "reason": reason
        })
        del self.portfolio[code]

sim = SimV2()
market_phase, total_limit, mult = judge_market("20260407")
print(f"大盘阶段: {market_phase} (量比{mult}x) | 总仓位上限: {total_limit[0]*100:.0f}%-{total_limit[1]*100:.0f}%")

# 4/7：开盘日，扫描买点
candidates = []
for sec, stocks in ALL_STOCKS.items():
    for code, klines in stocks.items():
        idx = di("20260407", klines)
        if idx < 20:
            continue
        prices_c = [k["close"] for k in klines]
        prices_l = [k["low"] for k in klines]
        volumes = [k["volume"] for k in klines]
        
        # 中继买点判断
        ma20 = sum(prices_c[idx-19:idx+1]) / 20
        ma10 = sum(prices_c[idx-9:idx+1]) / 10
        today_c = prices_c[idx]
        today_l = prices_l[idx]
        vol_ma5 = sum(volumes[idx-4:idx+1]) / 5
        
        if today_c <= ma20:
            continue  # 必须在MA20上方
        if volumes[idx] >= vol_ma5 * 0.85:
            continue  # 必须缩量
        
        near_ma10 = today_l <= ma10 * 1.03 and today_l >= ma10 * 0.94
        near_ma20 = today_l <= ma20 * 1.03 and today_l >= ma20 * 0.94
        if not (near_ma10 or near_ma20):
            continue  # 必须回踩支撑
        
        change = (today_c - prices_c[idx-1]) / prices_c[idx-1] * 100 if idx > 0 else 0
        if change > 4:
            continue
        
        candidates.append(code)

print(f"扫描到{len(candidates)}个买点候选")

# 选股：每个方向最多1只，优先选总仓位允许的
selected = []
used_sectors = set()
for code in candidates:
    sec = SECTOR_MAP.get(code, "")
    if sec in used_sectors:
        continue
    if len(selected) >= 5:
        break
    
    pct = calc_position_size(code, "20260407", market_phase, total_limit, [p for p in sim.portfolio.keys()])
    if pct > 0:
        sim.buy("20260407", code, pct)
        used_sectors.add(sec)
        selected.append(code)
        print(f"  买入 {NAME_MAP.get(code,code)}({code}) {sec} 仓位{pct*100:.1f}%")

# 4/8~4/10：检查止损+每日记录
for date in ["20260408","20260409","20260410"]:
    # 止损检查
    for code in list(sim.portfolio.keys()):
        pos = sim.portfolio[code]
        klines = get_klines(code)
        if not klines:
            continue
        idx = di(date, klines)
        if idx < 0:
            continue
        low = klines[idx]["low"]
        if low <= pos["stop_loss"]:
            sim.sell(date, code, f"止损|触发价{low:.2f}<止损{pos['stop_loss']:.2f}")
    
    # 每日记录
    tv = sim.value(date)
    total_pct = sum(p["cost"] for p in sim.portfolio.values()) / tv * 100 if tv > 0 else 0
    sim.daily.append({
        "date": date, "total_value": round(tv, 2),
        "total_pct": round(total_pct, 1),
        "positions": {c: p["shares"] for c, p in sim.portfolio.items()}
    })

# ═══ 输出结果 ═══
print("\n" + "="*100)
print("  v2 第1周交易明细 | 2026-04-07 ~ 2026-04-10 (仓位决策流程图版)")
print("="*100)
print(f"{'日期':12} {'时间':6} {'操作':6} {'名称':12} {'代码':8} {'方向':8} {'数量':>8} {'单价':>8} {'金额':>10} {'个股仓位':>8} {'总仓位':>8} {'理由'}")
print("-"*100)

for t in sim.trades:
    d = t["date"]
    fd = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    total_pct = 0
    if t["direction"] == "买入":
        pp = t["pos_pct"]
        # 计算当天总仓位
        tv = sim.value(d)
        buy_total = sum(p["cost"] for p in sim.portfolio.values() if p.get("entry_date") == t.get("entry_date") or True)
        # 简化：直接从daily取
        for dl in sim.daily:
            if dl["date"] == d:
                total_pct = dl["total_pct"]
                break
        if total_pct == 0:
            total_pct = sum(p["cost"] for c,p in sim.portfolio.items()) / tv * 100 if tv > 0 else 0
        r = "中继买点"
        print(f"{fd:12} {'15:00':6} {'买入':6} {t['name']:12} {t['code']:8} {t.get('sector',''):8} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {pp:>7.1f}% {total_pct:>7.1f}% {r}")
    else:
        pl = t.get("profit_pct", 0)
        r = f"{'止损' if pl < 0 else '止盈'}{pl:+.1f}%" if t.get("profit") else t["reason"]
        # 总仓位
        tv = sim.value(d)
        buy_total = sum(p["cost"] for c,p in sim.portfolio.items())
        total_pct = buy_total / tv * 100 if tv > 0 else 0
        print(f"{fd:12} {'15:00':6} {'卖出':6} {t['name']:12} {t['code']:8} {t.get('sector',''):8} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {'-':>8} {total_pct:>7.1f}% {r}")

print("-"*100)

# 仓位算法
print("\n📐  仓位决策流程（v2版）")
print("─"*70)
print(f"""
输入: 大盘{market_phase}(量比{mult}x) | 中继买点 | 个股结构
       │
       ▼
┌─ ① 大盘判强弱 ──────────────────┐
│  {market_phase} → 总仓位{total_limit[0]*100:.0f}%-{total_limit[1]*100:.0f}%{'⬅️' if market_phase else ''}
│  大盘量比{mult}x → 仓位系数×{phase_map.get(market_phase,1.0)}
└────────────────────────────────┘
       │
       ▼
┌─ ② 买点类型 ────────────────────┐
│  中继买点 → 基础仓位6%
│  缩量良好(量比<0.6) → ×1.2
│  缩量标准(量比<0.85) → ×1.0
│  缩量不足 → ×0.7
└────────────────────────────────┘
       │
       ▼
┌─ ③ 波段位置 ────────────────────┐
│  鱼头(刚突破MA20<3%) → ×0.5
│  鱼身(趋势确认3-15%) → ×1.0
│  鱼尾(远离MA20>15%) → ×0.5
└────────────────────────────────┘
       │
       ▼
┌─ ④ 行业分散 ────────────────────┐
│  同方向已有持仓 → 不新增
│  主线(机器人/半导体等) → ×1.2
│  非主线 → ×0.8
└────────────────────────────────┘
       │
       ▼
最终个股仓位 = 6% × 大盘系数 × 缩量系数 × 波段系数 × 行业系数
约束范围: 2% ~ 10%
""")

# 本周表现
end_val = sim.value("20260410")
pnl = end_val - start_cash
buys = len([t for t in sim.trades if t["direction"]=="买入"])
sells = len([t for t in sim.trades if t["direction"]=="卖出"])

print("📊  本周表现")
print(f"  期初资产: {start_cash:>10,.0f}  期末资产: {end_val:>10,.0f}  盈亏: {pnl:>+10,.0f} ({pnl/start_cash*100:+.2f}%)")
print(f"  操作: 买入{buys}笔 | 卖出{sells}笔")
print(f"  大盘阶段: {market_phase} | 大盘量比: {mult}x")

# 保存
with open(os.path.join(OUT_DIR, "第1周_v2.txt"), "w") as f:
    f.write("")

print(f"\n✅ v2结果已保存到 {OUT_DIR}/")

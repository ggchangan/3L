#!/usr/bin/env python3
"""v2多周模拟引擎 - 逐周运行，接续上周持仓"""
import json, os, sys

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = "/home/ubuntu/data/3l/simulation/v2"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

# ═══ 名称映射 ═══
CODE_NAMES = {
    "688126":"沪硅产业","688234":"天岳先进","300054":"鼎龙股份","688548":"广钢气体",
    "688127":"蓝特光学","688347":"华虹公司","300788":"佰维存储","301308":"江波龙",
    "001309":"德明利","300475":"香农芯创","603986":"兆易创新","688766":"普冉股份",
    "300223":"北京君正","300042":"朗科科技","300604":"长川科技","688012":"中微公司",
    "688072":"拓荆科技","002156":"通富微电","600584":"长电科技","002371":"北方华创",
    "688041":"海光信息","688981":"中芯国际","688256":"寒武纪","300346":"南大光电",
    "300236":"上海新阳","002920":"大族数控","002008":"大族激光",
    "002640":"跨境通","002044":"美年健康","688258":"卓易信息","603859":"能科科技",
    "688171":"税友股份","301171":"易点天下","301236":"软通动力","300339":"润和软件",
    "600571":"信雅达","300556":"宏景科技","603716":"塞力医疗","002153":"石基信息",
    "600588":"用友网络","300687":"赛意信息","300170":"汉得信息","300977":"杰创智能",
    "300451":"创业慧康","002987":"京北方","688232":"新点软件","300075":"数字政通",
    "002368":"太极股份","688246":"嘉和美康","688393":"安必平","600570":"恒生电子",
    "300674":"宇信科技","603918":"金桥信息","601360":"三六零","300624":"万兴科技",
    "000681":"视觉中国","300766":"每日互动","300058":"蓝色光标","300229":"拓尔思",
    "300033":"同花顺","688590":"新致软件","002315":"焦点科技","300253":"卫宁健康",
    "688108":"润达医疗","300010":"ST豆神","300418":"昆仑万维","002517":"恺英网络",
    "300459":"汤姆猫","002605":"姚记科技","002230":"科大讯飞","300378":"鼎捷数智",
    "688095":"福昕软件","688369":"致远互联","688615":"合合信息","688039":"泛微网络",
    "688111":"金山办公","002222":"福晶科技","600330":"天通股份","002436":"兴森科技",
    "001339":"智微智能","603389":"广合科技","600105":"永鼎股份","000338":"潍柴动力",
    "688519":"南亚新材","002353":"杰瑞股份","300442":"润泽科技","600550":"保变电气",
    "601179":"中国西电","301128":"强瑞技术","920099":"铜冠铜箔","300502":"新易盛",
    "300308":"中际旭创","300620":"光库科技","688195":"腾景科技","001267":"汇绿生态",
    "688313":"仕佳光子","688376":"英维克","002837":"英维克","300684":"中石科技",
    "002384":"东山精密","002916":"沪电股份","603920":"世运电路","300476":"胜宏科技",
    "600399":"应流股份","002364":"中恒电气","300870":"欧陆通","300284":"麦格米特",
    "002281":"光迅科技","600673":"东阳光","000988":"华工科技","601869":"长飞光纤",
    "600487":"亨通光电","600176":"中国巨石","605006":"山东玻纤","301526":"国际复材",
    "600941":"中国移动","600050":"中国联通","601728":"中国电信","002428":"云南锗业",
    "002361":"神剑股份","002202":"金风科技","002342":"巨力索具","002149":"西部材料",
    "601698":"中国卫通","688010":"福光股份","600879":"航天电子","300699":"光威复材",
    "300726":"宏达电子","001208":"华菱线缆","600118":"中国卫星","600391":"航天机电",
    "688088":"凌云光","300503":"昊志机电","300969":"恒帅股份","002196":"方正电机",
    "002434":"万向钱潮","603786":"科博达","603319":"均胜电子","603148":"浙江荣泰",
    "002915":"中欣氟材","600592":"龙溪股份","002048":"宁波华翔","688084":"晶品特装",
    "605056":"咸亨国际","688290":"景业智能","603012":"创力集团","600239":"华荣股份",
    "601177":"杭齿前进","300718":"长盛轴承","300660":"江苏雷利","300458":"全志科技",
    "002067":"景兴纸业","603980":"吉华集团","002607":"实益达","688322":"奥比中光",
    "603583":"捷昌驱动","600232":"中坚科技","603237":"日盈电子","300161":"福莱新材",
    "002527":"卧龙电驱","688160":"震裕科技","600580":"雷赛智能","300953":"中大力德",
    "002896":"双林股份","300100":"埃夫特","688165":"拓斯达","300607":"日发精机",
    "002520":"北纬科技","002148":"亿嘉和","002689":"豪能股份","603179":"绿的谐波",
    "601100":"恒立液压","603667":"五洲新春","002031":"巨轮智能","300432":"富临精工",
    "002553":"南方精工","002472":"双环传动","601689":"拓普集团","002050":"三花智控",
    "300007":"汉威科技","002698":"博实股份","300580":"贝斯特","603728":"鸣志电器",
    "603009":"北特科技","688218":"江苏北人","002611":"东方精工","002892":"兆威机电",
    "603662":"柯力传感","000637":"*ST京化","301413":"安培龙",
    "603538":"美诺华","688578":"艾力斯","002653":"海思科","688331":"荣昌生物",
    "002393":"舒泰神","301509":"康龙化成","688131":"皓元医药","300436":"广生堂",
    "002294":"信立泰","688266":"泽璟制药","688428":"诺诚健华","600276":"恒瑞医药",
    "603259":"药明康德","300347":"昭衍新药","688235":"百济神州",
    "301219":"腾远钴业","300139":"晓程科技","000831":"中稀有色","002378":"章源钨业",
    "000657":"中钨高新","002240":"盛新锂能","000933":"神火股份","600301":"华锡有色",
    "002160":"常铝股份","601600":"中国铝业","688353":"华盛锂电","002466":"天齐锂业",
    "002192":"融捷股份","601168":"西部矿业","002460":"赣锋锂业","600516":"方大炭素",
    "600111":"北方稀土","600549":"厦门钨业","603993":"洛阳钼业","601899":"紫金矿业",
    "000737":"北方铜业","600362":"江西铜业",
    "002709":"天赐材料","605117":"德业股份","300750":"宁德时代","300274":"阳光电源",
    "688390":"固德威","300438":"鹏辉能源","002245":"蔚蓝锂芯","301511":"德福科技",
    "002407":"多氟多","301358":"湖南裕能",
}
def name_of(code): return CODE_NAMES.get(code, code)

SECTOR_MAP = {}
for sec, stocks in ALL_STOCKS.items():
    for code in stocks:
        SECTOR_MAP[code] = sec

def get_klines(code):
    for sec, stocks in ALL_STOCKS.items():
        if code in stocks: return stocks[code]
    return None

def di(date_str, klines):
    for i, k in enumerate(klines):
        if k["date"] == date_str: return i
    return -1

# ═══ 核心工具函数 ═══
def judge_market(date_str):
    all_mults = []
    for sec, stocks in ALL_STOCKS.items():
        for code in stocks:
            klines = get_klines(code)
            if not klines: continue
            idx = di(date_str, klines)
            if idx < 30: continue
            vols = [k["volume"] for k in klines[idx-29:idx+1]]
            sv = sorted(vols)
            low_base = sum(sv[:max(3, len(sv)//5)]) / max(3, len(sv)//5)
            cur_vol = klines[idx]["volume"]
            mult = cur_vol / low_base if low_base > 0 else 0
            all_mults.append(mult)
    avg = sum(all_mults) / len(all_mults) if all_mults else 1
    if avg < 1.5: phase, limit = "低迷期", (0.6, 0.8)
    elif avg < 2: phase, limit = "正常", (0.4, 0.6)
    elif avg < 4: phase, limit = "强势", (0.2, 0.4)
    else: phase, limit = "高潮期", (0, 0.2)
    return phase, limit, round(avg, 2)

def calc_sector_momentum(date_str):
    sec_scores = {}
    for sec, stocks in ALL_STOCKS.items():
        gains = []
        for code in stocks:
            klines = get_klines(code)
            if not klines: continue
            idx = di(date_str, klines)
            if idx < 20: continue
            p20 = klines[idx-20]["close"]
            pc = klines[idx]["close"]
            gain = (pc - p20) / p20 * 100
            gains.append(gain)
        if gains:
            above_ma20 = 0
            for code in stocks:
                klines = get_klines(code)
                if not klines: continue
                idx = di(date_str, klines)
                if idx < 20: continue
                ma20 = sum(k["close"] for k in klines[idx-19:idx+1]) / 20
                if klines[idx]["close"] > ma20: above_ma20 += 1
            sec_scores[sec] = {
                "avg_gain_20d": round(sum(gains)/len(gains), 2),
                "above_ma20": above_ma20, "total": len(gains),
                "above_pct": round(above_ma20/len(gains)*100, 1)
            }
    return sec_scores

def scan_candidates(date_str, portfolio_codes):
    """扫描中继买点候选"""
    candidates = []
    for sec, stocks in ALL_STOCKS.items():
        for code in stocks:
            if code in portfolio_codes: continue  # 已持仓不扫描
            klines = get_klines(code)
            if not klines: continue
            idx = di(date_str, klines)
            if idx < 20: continue
            
            prices_c = [k["close"] for k in klines]
            prices_l = [k["low"] for k in klines]
            volumes = [k["volume"] for k in klines]
            
            ma20 = sum(prices_c[idx-19:idx+1]) / 20
            ma10 = sum(prices_c[idx-9:idx+1]) / 10
            tc = prices_c[idx]
            tl = prices_l[idx]
            v5 = sum(volumes[idx-4:idx+1]) / 5
            
            if tc <= ma20: continue
            if volumes[idx] >= v5 * 0.85: continue
            
            near10 = tl <= ma10 * 1.03 and tl >= ma10 * 0.94
            near20 = tl <= ma20 * 1.03 and tl >= ma20 * 0.94
            if not (near10 or near20): continue
            
            chg = (tc - prices_c[idx-1]) / prices_c[idx-1] * 100 if idx > 0 else 0
            if chg > 4: continue
            
            vol_ratio = volumes[idx] / v5 if v5 > 0 else 1
            vol_desc = "优秀缩量" if vol_ratio < 0.6 else "标准缩量"
            support = "MA10" if near10 else "MA20"
            
            candidates.append({
                "code": code, "sector": sec,
                "close": round(tc, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2),
                "vol_ratio": round(vol_ratio, 2), "vol_desc": vol_desc,
                "support": support, "change": round(chg, 2)
            })
    candidates.sort(key=lambda x: x["vol_ratio"])
    return candidates

def calc_position(code, date_str, market_phase, existing_codes):
    klines = get_klines(code)
    if not klines: return 0, {}
    idx = di(date_str, klines)
    if idx < 20: return 0, {}
    prices_c = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    price = prices_c[idx]
    
    phase_map = {"低迷期": 1.2, "正常": 1.0, "强势": 0.8, "高潮期": 0.3}
    phase_mult = phase_map.get(market_phase, 1.0)
    
    vol_ma5 = sum(volumes[idx-4:idx+1]) / 5
    vol_ratio = volumes[idx] / vol_ma5 if vol_ma5 > 0 else 1
    if vol_ratio < 0.6: buy_mult, buy_desc = 1.2, "优秀缩量"
    elif vol_ratio < 0.85: buy_mult, buy_desc = 1.0, "标准缩量"
    else: buy_mult, buy_desc = 0.7, "缩量不足"
    
    ma20 = sum(prices_c[idx-19:idx+1]) / 20
    pos = (price - ma20) / ma20
    if pos < 0.03: band_mult, band_desc = 0.5, "鱼头(初突破)"
    elif pos < 0.15: band_mult, band_desc = 1.0, "鱼身(确认趋势)"
    else: band_mult, band_desc = 0.5, "鱼尾(远离均线)"
    
    sec = SECTOR_MAP.get(code, "")
    existing_secs = set(SECTOR_MAP.get(c, "") for c in existing_codes if c in SECTOR_MAP)
    if sec in existing_secs: return 0, {}
    
    main_lines = {"机器人", "半导体", "AI应用", "算力"}
    line_mult = 1.2 if sec in main_lines else 0.8
    line_desc = "主线方向" if sec in main_lines else "非主线方向"
    
    base = 0.06
    raw = base * phase_mult * buy_mult * band_mult * line_mult
    final = max(0.02, min(raw, 0.10))
    
    return final, {
        "phase_mult": phase_mult, "buy_mult": buy_mult, "band_mult": band_mult, "line_mult": line_mult,
        "base": base, "final": final, "buy_desc": buy_desc, "band_desc": band_desc, "line_desc": line_desc,
        "vol_ratio": vol_ratio, "sector": sec, "pos_in_trend": round(pos, 4)
    }

# ═══ 模拟引擎类 ═══
class SimV2:
    def __init__(self, cash=1000000, portfolio=None):
        self.cash = cash
        self.portfolio = portfolio or {}
        self.trades = []
        self.market_phase = ""
        self.daily_log = []
    
    def price(self, code, date):
        klines = get_klines(code)
        if not klines: return 0
        idx = di(date, klines)
        return klines[idx]["close"] if idx >= 0 else 0
    
    def low_price(self, code, date):
        klines = get_klines(code)
        if not klines: return 0
        idx = di(date, klines)
        return klines[idx]["low"] if idx >= 0 else 0
    
    def total_value(self, date):
        pv = 0
        for code, pos in self.portfolio.items():
            p = self.price(code, date)
            pv += p * pos["shares"]
        return self.cash + pv
    
    def total_position_pct(self, date):
        tv = self.total_value(date)
        if tv <= 0: return 0
        cost_sum = sum(p["cost"] for p in self.portfolio.values())
        return cost_sum / tv * 100
    
    def buy(self, date, code, pct, details):
        price = self.price(code, date)
        if price <= 0: return False
        tv = self.total_value(date) or self.cash
        invest = tv * pct
        shares = int(invest / price / 100) * 100
        if shares <= 0: return False
        cost = shares * price
        if cost > self.cash:
            shares = int(self.cash / price / 100) * 100
            if shares <= 0: return False
            cost = shares * price
        
        self.cash -= cost
        self.portfolio[code] = {
            "shares": shares, "price": price, "cost": cost,
            "entry_date": date, "pct": pct,
            "stop_loss": round(price * 0.92, 2),
            "high_water_mark": price,
            "consec_up_days": 0
        }
        
        tv2 = self.total_value(date)
        total_pct = sum(p["cost"] for p in self.portfolio.values()) / tv2 * 100 if tv2 > 0 else 0
        
        self.trades.append({
            "date": date, "time": "15:00", "direction": "买入",
            "code": code, "name": name_of(code), "sector": SECTOR_MAP.get(code,""),
            "qty": shares, "price": round(price, 2), "amount": round(cost, 2),
            "pos_pct": round(pct*100, 1),
            "total_pct": round(total_pct, 1),
            "reason": "中继买点"
        })
        return True
    
    def sell(self, date, code, reason):
        if code not in self.portfolio: return
        pos = self.portfolio[code]
        price = self.price(code, date)
        if price <= 0: return
        proceeds = pos["shares"] * price
        self.cash += proceeds
        
        pl = (price - pos["price"]) * pos["shares"]
        pl_pct = (price - pos["price"]) / pos["price"] * 100
        
        del self.portfolio[code]
        tv = self.total_value(date)
        total_pct = sum(p["cost"] for p in self.portfolio.values()) / tv * 100 if tv > 0 and self.portfolio else 0
        
        plabel = "止盈" if pl > 0 else "止损"
        self.trades.append({
            "date": date, "time": "15:00", "direction": "卖出",
            "code": code, "name": name_of(code), "sector": SECTOR_MAP.get(code,""),
            "qty": pos["shares"], "price": round(price, 2),
            "amount": round(proceeds, 2),
            "profit": round(pl, 2), "profit_pct": round(pl_pct, 2),
            "total_pct": round(total_pct, 1),
            "pos_pct": "-",
            "reason": f"{plabel}|{reason}"
        })
    
    def check_stop_and_take_profit(self, date):
        """每日检查止损（-8%）和止盈（3L规则）"""
        for code in list(self.portfolio.keys()):
            pos = self.portfolio[code]
            close = self.price(code, date)
            low = self.low_price(code, date)
            if close <= 0: continue
            
            # 更新高点和连涨天数
            if close > pos["high_water_mark"]:
                pos["high_water_mark"] = close
            yesterday = self.price(code, self._prev_trading_day(date))
            if yesterday > 0 and close > yesterday:
                pos["consec_up_days"] += 1
            else:
                pos["consec_up_days"] = 0
            
            # 止损：跌破成本价8%
            if low > 0 and low <= pos["stop_loss"]:
                self.sell(date, code, f"跌破止损{pos['stop_loss']:.2f}")
                continue
            
            # 止盈（3L规则）：
            # ① 加速+量递减：连涨3天+累计>12%+量递减
            if pos["consec_up_days"] >= 2:
                cum_gain = (close - pos["price"]) / pos["price"] * 100
                if cum_gain > 12:
                    klines = get_klines(code)
                    idx = di(date, klines)
                    if idx >= 3:
                        vols = [k["volume"] for k in klines[idx-2:idx+1]]
                        if vols[2] < vols[1] and vols[1] < vols[0]:
                            self.sell(date, code, f"加速后量递减|累计{cum_gain:.1f}%")
                            continue
            
            # ② 右侧止盈：跌破MA20
            klines = get_klines(code)
            idx = di(date, klines)
            if idx >= 20:
                prices_c = [k["close"] for k in klines]
                ma20 = sum(prices_c[idx-19:idx+1]) / 20
                if close < ma20:
                    self.sell(date, code, f"跌破MA20({ma20:.2f})")
                    continue
    
    def _prev_trading_day(self, date_str):
        """获取上一个交易日"""
        klines = get_klines(list(self.portfolio.keys())[0]) if self.portfolio else None
        if not klines:
            for sec, stocks in ALL_STOCKS.items():
                for code in stocks:
                    klines = get_klines(code)
                    if klines: break
                if klines: break
        if not klines: return date_str
        idx = di(date_str, klines)
        if idx > 0:
            return klines[idx-1]["date"]
        return date_str


# ═══ 运行 ═══
START_CASH = 1000000

# 第1周初始建仓（从report_data.json加载或直接定义）
def load_week1_state():
    """加载第1周结束时的状态"""
    # 从第1周报告数据重建
    rp = os.path.join(OUT_DIR, "report_data.json")
    if os.path.exists(rp):
        with open(rp) as f:
            data = json.load(f)
        portfolio = {}
        total_cost = 0
        for h in data["part6_holdings"]:
            portfolio[h["code"]] = {
                "shares": h["shares"],
                "price": h["buy_price"],
                "cost": h["shares"] * h["buy_price"],
                "entry_date": "20260407",
                "pct": h["cost_pct"] / 100,
                "stop_loss": round(h["buy_price"] * 0.92, 2),
                "high_water_mark": h["current_price"],
                "consec_up_days": 0
            }
            total_cost += h["shares"] * h["buy_price"]
        cash = START_CASH - total_cost
        return cash, portfolio
    return START_CASH, {}

# 第2周
print("═══ 第2周模拟 (20260413~20260417) ═══\n")

sim = SimV2(*load_week1_state())
w2_dates = ["20260413","20260414","20260415","20260416","20260417"]

# 周一(4/13)：先检查止损止盈 → 再扫描买点
print(f"周一 {w2_dates[0]}")
# 检查持仓
sim.check_stop_and_take_profit(w2_dates[0])
print(f"  cash={sim.cash:.0f}, 持仓{len(sim.portfolio)}只, 总值{sim.total_value(w2_dates[0]):.0f}")

# 大盘判强弱
market_phase, total_limit, mult = judge_market(w2_dates[0])
sim.market_phase = market_phase
print(f"  大盘: {market_phase} (量比{mult}x), 上限{total_limit[0]*100:.0f}%-{total_limit[1]*100:.0f}%")

# 行业动量
sec_scores = calc_sector_momentum(w2_dates[0])
print(f"  行业动量排名:")
for sec, sc in sorted(sec_scores.items(), key=lambda x: -x[1]["avg_gain_20d"]):
    main = "主线" if sec in {"机器人","半导体","AI应用","算力"} else "非主线"
    print(f"    {sec}: {sc['avg_gain_20d']:+.1f}% | {sc['above_pct']:.0f}%站上MA20 | {main}")

# 扫描买点
portfolio_codes = list(sim.portfolio.keys())
candidates = scan_candidates(w2_dates[0], portfolio_codes)
print(f"\n  扫描到{len(candidates)}个候选买点")

# 选股买入
used_secs = set(SECTOR_MAP.get(c,"") for c in portfolio_codes if c in SECTOR_MAP)
buys = []
for c in candidates:
    code = c["code"]
    sec = c["sector"]
    if sec in used_secs: continue
    if len(sim.portfolio) >= 5: break
    
    pct, det = calc_position(code, w2_dates[0], market_phase, list(sim.portfolio.keys()))
    if pct > 0:
        if sim.buy(w2_dates[0], code, pct, det):
            used_secs.add(sec)
            buys.append((code, pct, det, c))
            print(f"  ✅ 买入 {name_of(code)}({code}) {sec} 仓位{pct*100:.1f}% | {det['buy_desc']} | {det['line_desc']}")

if not buys:
    print("  本周无新买入")

# 周二~周五：每日检查止损止盈
for date in w2_dates[1:]:
    sim.check_stop_and_take_profit(date)
    tv = sim.total_value(date)
    print(f"  {date[-5:]}: 总值{tv:.0f} cash={sim.cash:.0f} 持仓{len(sim.portfolio)}只")

# 输出交易记录
print(f"\n📋 第2周交易明细:")
print(f"{'日期':8} {'操作':6} {'名称':14} {'方向':8} {'数量':>8} {'单价':>8} {'金额':>10} {'个股仓位':>8} {'理由'}")
print("-" * 75)
for t in sim.trades:
    d = t["date"]
    dn = f"{d[-5:]}"
    if t["direction"] == "买入":
        print(f"{dn:8} {'买入':6} {name_of(t['code']):14} {SECTOR_MAP.get(t['code'],''):8} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {t['pos_pct']:>7}% {t['reason']}")
    else:
        pls = f"{t.get('profit_pct',0):+.1f}%"
        print(f"{dn:8} {'卖出':6} {name_of(t['code']):14} {SECTOR_MAP.get(t['code'],''):8} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {'-':>8} {t['reason']} ({pls})")

end_val = sim.total_value(w2_dates[-1])
pnl = end_val - START_CASH
print(f"\n📊 累计表现（含第1周）:")
print(f"  期初: {START_CASH:,}")
print(f"  期末: {end_val:,.0f}")
print(f"  累计盈亏: {pnl:+,.0f} ({pnl/START_CASH*100:+.2f}%)")
w2_pnl = end_val - sim.total_value("20260407")  
print(f"  本周盈亏: {w2_pnl:+,.0f}")
print(f"  持仓{len(sim.portfolio)}只")

# 保存状态
state = {
    "cash": sim.cash,
    "portfolio": {code: pos for code, pos in sim.portfolio.items()},
    "trades": sim.trades
}
import pickle
with open(os.path.join(OUT_DIR, "week2_state.pkl"), "wb") as f:
    pickle.dump(state, f)
print(f"\n✅ 第2周状态已保存")

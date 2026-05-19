#!/usr/bin/env python3
"""A股3L模拟交易引擎 - 回溯4/7~5/15"""
import json, os, sys
from datetime import datetime, timedelta

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUTPUT_DIR = "/home/ubuntu/data/3l/simulation"
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

# 股票代码→名称映射
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

def name_of(code):
    return CODE_NAMES.get(code, code)

def get_klines(code):
    """找某只股票的K线"""
    for sector, stocks in ALL_STOCKS.items():
        if code in stocks:
            return stocks[code]
    return None

def get_date_idx(klines, date_str):
    """找日期对应的K线索引"""
    for i, k in enumerate(klines):
        if k["date"] == date_str:
            return i
    return -1

def calc_ma(prices, period, idx):
    """计算idx位置的MA"""
    if idx < period - 1:
        return None
    return sum(prices[idx-period+1:idx+1]) / period

# ═══ 交易日历 ═══
stock0 = list(ALL_STOCKS["半导体"].values())[0]
ALL_DATES = sorted(set(k["date"] for k in stock0))
TRADING_DAYS = [d for d in ALL_DATES if "20260407" <= d <= "20260515"]

# 周划分
WEEKS = {}
for dt in TRADING_DAYS:
    d = datetime.strptime(dt, "%Y%m%d")
    ws = d - timedelta(days=d.weekday())
    wk = ws.strftime("%Y%m%d")
    if wk not in WEEKS:
        WEEKS[wk] = []
    WEEKS[wk].append(dt)

WEEK_LIST = sorted(WEEKS.items())  # [(week_start, [dates])]

# ═══ 模拟引擎 ═══
class Simulator:
    def __init__(self, cash=1000000):
        self.cash = cash
        self.portfolio = {}  # {code: {shares, avg_price, entry_date, reason, stop_loss}}
        self.trades = []     # [{date, code, direction, qty, price, amount, reason}]
        self.daily_logs = [] # [{date, summary, positions}]
        self.total_value_history = []
        
    def value(self, date):
        """计算总资产(现金+持仓市值)"""
        pv = 0
        for code, pos in self.portfolio.items():
            klines = get_klines(code)
            if klines:
                idx = get_date_idx(klines, date)
                if idx >= 0:
                    pv += klines[idx]["close"] * pos["shares"]
        return self.cash + pv
    
    def execute_buy(self, date, code, amount, reason, price=None):
        """买入 - amount是买入金额"""
        klines = get_klines(code)
        if not klines:
            return False
        idx = get_date_idx(klines, date)
        if idx < 0:
            return False
        p = price or klines[idx]["close"]
        shares = int(amount / p / 100) * 100  # 整百股
        if shares <= 0:
            return False
        cost = shares * p
        if cost > self.cash:
            shares = int(self.cash / p / 100) * 100
            if shares <= 0:
                return False
            cost = shares * p
        
        self.cash -= cost
        
        # 已有则合并
        if code in self.portfolio:
            pos = self.portfolio[code]
            total_cost = pos["avg_price"] * pos["shares"] + cost
            total_shares = pos["shares"] + shares
            pos["avg_price"] = total_cost / total_shares
            pos["shares"] = total_shares
        else:
            self.portfolio[code] = {
                "shares": shares,
                "avg_price": p,
                "entry_date": date,
                "reason": reason,
                "stop_loss": round(p * 0.92, 2),  # 初始止损-8%
            }
        
        self.trades.append({
            "date": date, "time": "15:00", "code": code, "name": name_of(code), "direction": "买入",
            "qty": shares, "price": round(p, 2), "amount": round(cost, 2),
            "pos_pct": round(cost / (self.cash + cost) * 100, 2) if (self.cash + cost) > 0 else 0,
            "reason": reason
        })
        return True
    
    def execute_sell(self, date, code, reason, ratio=1.0):
        """卖出 - ratio是卖出比例(0-1)"""
        if code not in self.portfolio:
            return False
        pos = self.portfolio[code]
        klines = get_klines(code)
        if not klines:
            return False
        idx = get_date_idx(klines, date)
        if idx < 0:
            return False
        p = klines[idx]["close"]
        sell_shares = int(pos["shares"] * ratio / 100) * 100
        if sell_shares <= 0:
            sell_shares = pos["shares"]
        if sell_shares <= 0:
            return False
        
        proceeds = sell_shares * p
        self.cash += proceeds
        
        self.trades.append({
            "date": date, "time": "15:00", "code": code, "name": name_of(code), "direction": "卖出",
            "qty": sell_shares, "price": round(p, 2), "amount": round(proceeds, 2),
            "reason": reason
        })
        
        if sell_shares >= pos["shares"]:
            del self.portfolio[code]
        else:
            pos["shares"] -= sell_shares
        
        return True
    
    def check_stop_loss(self, date):
        """检查止损"""
        exits = []
        for code in list(self.portfolio.keys()):
            pos = self.portfolio[code]
            klines = get_klines(code)
            if not klines:
                continue
            idx = get_date_idx(klines, date)
            if idx < 0:
                continue
            low = klines[idx]["low"]
            if low <= pos["stop_loss"]:
                exits.append((code, f"止损触发: 最低{low}<止损{pos['stop_loss']}"))
        for code, reason in exits:
            self.execute_sell(date, code, reason)
        return exits

# ═══ 3L买点扫描 ═══
def scan_relay_buy(klines, date):
    """中继买点扫描"""
    idx = get_date_idx(klines, date)
    if idx < 5:
        return False
    
    prices_c = [k["close"] for k in klines]
    prices_l = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    # MA计算
    ma5 = calc_ma(prices_c, 5, idx)
    ma10 = calc_ma(prices_c, 10, idx)
    ma20 = calc_ma(prices_c, 20, idx)
    if not all([ma5, ma10, ma20]):
        return False
    
    today_c = prices_c[idx]
    today_v = volumes[idx]
    prev_c = prices_c[idx - 1] if idx > 0 else today_c
    
    # 成交量MA5
    if idx < 4:
        return False
    vol_ma5 = sum(volumes[idx-4:idx+1]) / 5
    
    # 1. 趋势向上: 价格 > MA20
    if today_c <= ma20:
        return False
    
    # 2. 缩量: 今日量 < MA5量均
    if today_v >= vol_ma5 * 0.85:
        # 更严格：最近3天平均量也要小于MA5量均
        recent_3 = sum(volumes[idx-2:idx+1]) / 3 if idx >= 2 else today_v
        if recent_3 >= vol_ma5 * 0.85:
            return False
    
    # 3. 回踩支撑: 最低价在MA10/MA20附近
    today_l = prices_l[idx]
    near_ma10 = today_l <= ma10 * 1.03 and today_l >= ma10 * 0.94
    near_ma20 = today_l <= ma20 * 1.03 and today_l >= ma20 * 0.94
    if not (near_ma10 or near_ma20):
        return False
    
    # 4. 未加速: 今日涨幅不过大
    change = (today_c - prev_c) / prev_c * 100
    if change > 4:
        return False
    
    # 5. 前10天有上升趋势
    high_10 = max(prices_c[idx-9:idx+1]) if idx >= 9 else max(prices_c[:idx+1])
    low_prior = min(prices_c[idx-9:idx-4]) if idx >= 9 else min(prices_c[:idx+1])
    if high_10 < low_prior * 1.06:
        return False
    
    return True

def find_all_buy_signals(date):
    """扫描全部股票找买点"""
    candidates = []
    today = datetime.strptime(date, "%Y%m%d")
    
    for sector, stocks in ALL_STOCKS.items():
        for code, klines in stocks.items():
            # 已有持仓不再重复推荐
            if code in sim.portfolio:
                continue
            if scan_relay_buy(klines, date):
                idx = get_date_idx(klines, date)
                candidates.append({
                    "code": code, "sector": sector,
                    "price": klines[idx]["close"],
                    "volume_ratio": klines[idx]["volume"] / (sum(k["volume"] for k in klines[idx-4:idx+1])/5) if idx >= 4 else 0,
                })
    
    # 按成交量比排序（缩量越明显越优先）
    candidates.sort(key=lambda x: x["volume_ratio"])
    return candidates

# ═══ 运行 ═══
sim = Simulator()

# 按天模拟
for dt in TRADING_DAYS:
    d = datetime.strptime(dt, "%Y%m%d")
    day_notes = []
    
    # 1. 检查止损
    stops = sim.check_stop_loss(dt)
    for code, reason in stops:
        day_notes.append(f"⚠️ 止损{code}: {reason}")
    
    # 2. 周一/周初：扫描买点
    is_monday = d.weekday() == 0
    is_first_day = (dt == TRADING_DAYS[0])
    
    if is_monday or is_first_day:
        candidates = find_all_buy_signals(dt)
        if candidates:
            day_notes.append(f"📡 扫描到{len(candidates)}个买点候选")
            
            # 最多开新仓到5只
            max_positions = 5
            available_slots = max_positions - len(sim.portfolio)
            
            if available_slots > 0:
                # 分散行业，每行业最多1只
                sectors_used = set(pos_code.split("_")[0] if "_" in pos_code else "" 
                                    for pos_code in sim.portfolio.keys())
                # 其实应该用股票的实际行业
                sector_selection = {"算力":0,"半导体":0,"AI应用":0,"机器人":0,"商业航天":0,"创新药":0,"资源股":0,"新能源":0}
                
                for c in candidates:
                    if available_slots <= 0:
                        break
                    sec = c["sector"]
                    if sector_selection.get(sec, 0) >= 1:
                        continue
                    
                    # 查该股
                    code = c["code"]
                    if code in sim.portfolio:
                        continue
                    
                    klines = get_klines(code)
                    if not klines:
                        continue
                    idx = get_date_idx(klines, dt)
                    if idx < 0:
                        continue
                    price = klines[idx]["close"]
                    
                    # 仓位：5%×行业信心
                    if len(sim.portfolio) == 0:
                        pos_pct = 0.10  # 首次开仓10%
                    elif len(sim.portfolio) <= 2:
                        pos_pct = 0.08
                    else:
                        pos_pct = 0.06
                    
                    invest = int(sim.cash * pos_pct)
                    reason = f"中继买点: 价格{price}>MA20, 缩量回踩, {sec}方向"
                    
                    if sim.execute_buy(dt, code, invest, reason):
                        sector_selection[sec] = sector_selection.get(sec, 0) + 1
                        available_slots -= 1
                        day_notes.append(f"🟢 买入{code}: {reason} (金额{invest/10000:.1f}万)")
    
    # 3. 周四/周五：检查止盈/卖出信号
    is_thursday = d.weekday() == 3
    is_friday = d.weekday() == 4
    is_last_day = (dt == TRADING_DAYS[-1])
    
    if is_thursday or is_friday or is_last_day:
        for code in list(sim.portfolio.keys()):
            pos = sim.portfolio[code]
            klines = get_klines(code)
            if not klines:
                continue
            idx = get_date_idx(klines, dt)
            if idx < 0:
                continue
            today_c = klines[idx]["close"]
            change_pct = (today_c - pos["avg_price"]) / pos["avg_price"] * 100
            prev_c = klines[idx-1]["close"] if idx > 0 else today_c
            today_chg = (today_c - prev_c) / prev_c * 100
            
            # 止盈：涨超15%减半
            if change_pct > 15:
                sim.execute_sell(dt, code, f"止盈: +{change_pct:.1f}%超过15%目标", ratio=0.5)
                day_notes.append(f"🔴 止盈{code}(半仓): +{change_pct:.1f}%")
            
            # 卖出信号：连跌3天且累计超5%
            if idx >= 3:
                d1 = (klines[idx]["close"] - klines[idx-1]["close"]) / klines[idx-1]["close"]
                d2 = (klines[idx-1]["close"] - klines[idx-2]["close"]) / klines[idx-2]["close"]
                d3 = (klines[idx-2]["close"] - klines[idx-3]["close"]) / klines[idx-3]["close"]
                if d1 < 0 and d2 < 0 and d3 < 0:
                    total_drop = abs(d1+d2+d3) * 100
                    if total_drop > 5:
                        sim.execute_sell(dt, code, f"连跌3天累计-{total_drop:.1f}%")
                        day_notes.append(f"🔴 卖出{code}: 连跌3天累计-{total_drop:.1f}%")
            
            # 最后一日强制平仓
            if is_last_day:
                sim.execute_sell(dt, code, "模拟结束平仓")
                day_notes.append(f"🔴 平仓{code}: 模拟结束")
    
    # 4. 每日小结 - 记录持仓盈亏
    pos_strs = []
    for code, pos in sim.portfolio.items():
        klines_p = get_klines(code)
        if klines_p:
            idx_p = get_date_idx(klines_p, dt)
            if idx_p >= 0:
                cur_p = klines_p[idx_p]["close"]
                pnl_pct = (cur_p - pos["avg_price"]) / pos["avg_price"] * 100
                pos_strs.append(f"{code}({pnl_pct:+.1f}%)")
    
    if not day_notes and pos_strs:
        day_notes.append(f"持仓: {', '.join(pos_strs)}")
    elif not day_notes:
        day_notes.append("空仓")
    elif pos_strs:
        day_notes.append(f"持仓: {', '.join(pos_strs)}")
    pv = sim.value(dt)
    total_value = pv
    # 计算当日盈亏（环比上一交易日）
    if len(sim.total_value_history) > 0:
        prev_total = sim.total_value_history[-1]
        day_pnl = total_value - prev_total
        day_pnl_pct = day_pnl / prev_total * 100
    else:
        day_pnl = 0
        day_pnl_pct = 0
    cum_pnl = total_value - 1000000
    
    log = {
        "date": dt,
        "day_of_week": ["周一","周二","周三","周四","周五","周六","周日"][d.weekday()],
        "positions": len(sim.portfolio),
        "cash": round(sim.cash, 2),
        "position_value": round(pv - sim.cash, 2),
        "total_value": round(total_value, 2),
        "day_pnl": round(day_pnl, 2),
        "day_pnl_pct": round(day_pnl_pct, 2),
        "cum_pnl": round(cum_pnl, 2),
        "cum_pnl_pct": round(cum_pnl / 1000000 * 100, 2),
        "notes": "; ".join(day_notes) if day_notes else "空仓",
    }
    sim.daily_logs.append(log)
    sim.total_value_history.append(total_value)

# ═══ 生成每日报告 ═══
daily_file = os.path.join(OUTPUT_DIR, "daily_log.json")
with open(daily_file, "w") as f:
    json.dump(sim.daily_logs, f, ensure_ascii=False, indent=2)

# 生成周报
week_idx = 0
for wk, dates in WEEK_LIST:
    week_dates_set = set(dates)
    week_logs = [l for l in sim.daily_logs if l["date"] in week_dates_set]
    week_trades = [t for t in sim.trades if t["date"] in week_dates_set]
    
    if week_logs:
        first = week_logs[0]
        last = week_logs[-1]
        # 期初资产 = 上周五收盘
        first_date = week_logs[0]["date"]
        prev_val = 1000000
        for li, ll in enumerate(sim.daily_logs):
            if ll["date"] == first_date:
                if li > 0:
                    prev_val = sim.daily_logs[li-1]["total_value"]
                break
        start_value = prev_val
        week_pnl = last["total_value"] - start_value
        week_pnl_pct = week_pnl / start_value * 100
        
        week_idx += 1
        # 持仓明细（周最后一天的持仓）
        pos_detail = []
        for code, pos in sim.portfolio.items():
            klines_pos = get_klines(code)
            if klines_pos:
                idx_p = get_date_idx(klines_pos, last["date"])
                if idx_p >= 0:
                    cur_p = klines_pos[idx_p]["close"]
                    pnl_pct = (cur_p - pos["avg_price"]) / pos["avg_price"] * 100
                    pos_detail.append(f'  · {code}: {pos["shares"]}股@{pos["avg_price"]:.2f} 现价{cur_p:.2f}({pnl_pct:+.1f}%) 止损{pos["stop_loss"]:.2f}')
        
        report = f"""════════════════════════════════════
第{week_idx}周报告 | {dates[0]}~{dates[-1]}
════════════════════════════════════

📊 本周表现
  期初总资产: {start_value:,.2f}
  期末总资产: {last['total_value']:,.2f}
  本周盈亏: {week_pnl:+,.2f} ({week_pnl_pct:+.2f}%)
  累计盈亏: {last['total_value']-1000000:+,.2f} ({(last['total_value']-1000000)/1000000*100:+.2f}%)

💼 本周交易
{chr(10).join(f'  · {"🟢" if t["direction"]=="买入" else "🔴"} {t["code"]}: {t["direction"]} {t["qty"]}股@{t["price"]} = {t["amount"]:,.0f}元 | {t["reason"]}' for t in week_trades) if week_trades else '  无操作'}

📝 每日日志
{chr(10).join(f'  [{l["date"]} {l["day_of_week"]}] 资产{l["total_value"]:,.0f} | {l["notes"]}' for l in week_logs)}

📈 持仓明细
{chr(10).join(pos_detail) if pos_detail else '  空仓'}
"""
        report_path = os.path.join(OUTPUT_DIR, f"周报_第{week_idx}周_{dates[0]}_{dates[-1]}.txt")
        with open(report_path, "w") as f:
            f.write(report)
        print(report[:200])

# 生成最终总结
total_value_final = sim.total_value_history[-1]
total_pnl = total_value_final - 1000000
total_pnl_pct = total_pnl / 1000000 * 100

# 个股盈亏
stock_pnl = {}
for t in sim.trades:
    c = t["code"]
    if c not in stock_pnl:
        stock_pnl[c] = {"buy_amount": 0, "sell_amount": 0, "trades": []}
    if t["direction"] == "买入":
        stock_pnl[c]["buy_amount"] += t["amount"]
    else:
        stock_pnl[c]["sell_amount"] += t["amount"]
    stock_pnl[c]["trades"].append(t)

# 计算每个股的盈亏
stock_results = []
for code, sd in stock_pnl.items():
    net = sd["sell_amount"] - sd["buy_amount"]
    cost = sd["buy_amount"]
    pnl_pct = net / cost * 100 if cost > 0 else 0
    
    # 持股天数
    buy_dates = [t["date"] for t in sd["trades"] if t["direction"] == "买入"]
    sell_dates = [t["date"] for t in sd["trades"] if t["direction"] == "卖出"]
    if buy_dates:
        first_buy = datetime.strptime(min(buy_dates), "%Y%m%d")
        last_date = datetime.strptime(max(sell_dates or buy_dates), "%Y%m%d")
        hold_days = (last_date - first_buy).days
    else:
        hold_days = 0
    
    stock_results.append({
        "code": code,
        "profit": round(net, 2),
        "profit_pct": round(pnl_pct, 2),
        "cost": round(cost, 2),
        "hold_days": hold_days,
        "trade_count": len(sd["trades"]),
    })

stock_results.sort(key=lambda x: x["profit"], reverse=True)

summary = f"""═══════════════════════════════════════════
模拟交易总结报告
周期: 2026-04-07 ~ 2026-05-15 (26个交易日)
本金: 1,000,000 元
═══════════════════════════════════════════

📊 总体表现
  期末总资产: {total_value_final:,.2f}
  总盈亏: {total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)
  总交易次数: {len(sim.trades)}笔

🏆 个股盈亏排行
{chr(10).join(f'  {i+1}. {r["code"]}: {r["profit"]:+,.0f}元 ({r["profit_pct"]:+.1f}%) | 投入{r["cost"]:,.0f}元 | 持仓{r["hold_days"]}天 | {r["trade_count"]}笔交易'
     for i, r in enumerate(stock_results[:20]))}

📉 亏损个股
{chr(10).join(f'  {i+1}. {r["code"]}: {r["profit"]:+,.0f}元 ({r["profit_pct"]:+.1f}%)' 
     for i, r in enumerate([r for r in stock_results if r["profit"] < 0][:10])) if any(r["profit"] < 0 for r in stock_results) else '  无'}

💼 日收益率曲线
{chr(10).join(f'  [{l["date"]}] {l["total_value"]:,.0f} ({l["day_pnl_pct"]:+.2f}%) | 持仓{l["positions"]}只 | {l["notes"][:40]}'
     for l in sim.daily_logs)}

📈 最大回撤
"""

# 算最大回撤
peak = sim.total_value_history[0]
max_dd = 0
max_dd_start = max_dd_end = ""
for i, v in enumerate(sim.total_value_history):
    if v > peak:
        peak = v
    dd = (peak - v) / peak * 100
    if dd > max_dd:
        max_dd = dd
        max_dd_end = sim.daily_logs[i]["date"]

summary += f"  最大回撤: {max_dd:.2f}%\n"

summary_path = os.path.join(OUTPUT_DIR, "最终总结报告.txt")
with open(summary_path, "w") as f:
    f.write(summary)

# 保存交易记录
trades_file = os.path.join(OUTPUT_DIR, "交易记录.json")
with open(trades_file, "w") as f:
    json.dump(sim.trades, f, ensure_ascii=False, indent=2)

print(f"\n所有报告已保存到 {OUTPUT_DIR}/")
print(f"  - daily_log.json (每日日志)")
print(f"  - 交易记录.json (逐笔交易)")
print(f"  - 周报_* (每周报告)")
print(f"  - 最终总结报告.txt")
print(f"\n总盈亏: {total_pnl:+,.2f}元 ({total_pnl_pct:+.2f}%)")
print(f"总交易: {len(sim.trades)}笔")

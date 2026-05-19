#!/usr/bin/env python3
"""v2引擎 - 3L仓位决策流程图版 | 只跑第1周 | 干净报告"""
import json, os, subprocess, re
from datetime import datetime

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = "/home/ubuntu/data/3l/simulation/v2"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

# ═══ 代码→名称映射（从原引擎复制）═══
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

# ═══ 行业映射 ═══
SECTOR_MAP = {}
for sec, stocks in ALL_STOCKS.items():
    for code in stocks:
        SECTOR_MAP[code] = sec

def get_klines(code):
    for sec, stocks in ALL_STOCKS.items():
        if code in stocks:
            return stocks[code]
    return None

def di(date_str, klines):
    for i, k in enumerate(klines):
        if k["date"] == date_str:
            return i
    return -1

# ═══ 主线方向 ═══
MAIN_LINES = {"机器人", "半导体", "AI应用", "算力"}

# ═══ ① 大盘判强弱 ═══
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
    if avg < 1.5:
        phase, total_limit = "低迷期", (0.6, 0.8)
    elif avg < 2:
        phase, total_limit = "正常", (0.4, 0.6)
    elif avg < 4:
        phase, total_limit = "强势", (0.2, 0.4)
    else:
        phase, total_limit = "高潮期", (0, 0.2)
    return phase, total_limit, round(avg, 2)

# ═══ ②~④ 仓位决策 ═══
def calc_position(code, date_str, market_phase, existing_codes):
    klines = get_klines(code)
    if not klines: return 0, {}
    idx = di(date_str, klines)
    if idx < 20: return 0, {}

    prices_c = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    price = prices_c[idx]

    # 大盘系数
    phase_map = {"低迷期": 1.2, "正常": 1.0, "强势": 0.8, "高潮期": 0.3}
    phase_mult = phase_map.get(market_phase, 1.0)

    # 买点类型(中继)：缩量质量
    vol_ma5 = sum(volumes[idx-4:idx+1]) / 5
    vol_ratio = volumes[idx] / vol_ma5 if vol_ma5 > 0 else 1
    if vol_ratio < 0.6:
        buy_mult = 1.2  # 优秀
        buy_desc = "优秀缩量"
    elif vol_ratio < 0.85:
        buy_mult = 1.0  # 标准
        buy_desc = "标准缩量"
    else:
        buy_mult = 0.7  # 不足
        buy_desc = "缩量不足"

    # 波段位置
    ma20 = sum(prices_c[idx-19:idx+1]) / 20
    pos = (price - ma20) / ma20
    if pos < 0.03:
        band_mult = 0.5
        band_desc = "鱼头(初突破)"
    elif pos < 0.15:
        band_mult = 1.0
        band_desc = "鱼身(确认趋势)"
    else:
        band_mult = 0.5
        band_desc = "鱼尾(远离均线)"

    # 行业分散
    sec = SECTOR_MAP.get(code, "")
    same_sec = [c for c in existing_codes if SECTOR_MAP.get(c, "") == sec]
    if same_sec:
        return 0, {}  # 同方向已有持仓

    line_mult = 1.2 if sec in MAIN_LINES else 0.8
    line_desc = "主线" if sec in MAIN_LINES else "非主线"

    # 计算
    base = 0.06
    raw = base * phase_mult * buy_mult * band_mult * line_mult
    final = max(0.02, min(raw, 0.10))

    details = {
        "phase_mult": phase_mult, "buy_mult": buy_mult,
        "band_mult": band_mult, "line_mult": line_mult,
        "base": base, "final": final,
        "buy_desc": buy_desc, "band_desc": band_desc, "line_desc": line_desc,
        "vol_ratio": round(vol_ratio, 2),
        "sector": sec
    }
    return final, details

# ═══ 交易引擎 ═══
class SimV2:
    def __init__(self):
        self.cash = 1_000_000
        self.portfolio = {}
        self.trades = []
        self.market_phase = ""
        self.phase_detail = {}

    def total_value(self, date):
        pv = sum(self._price(code, date) * pos["shares"] for code, pos in self.portfolio.items())
        return self.cash + pv

    def _price(self, code, date):
        klines = get_klines(code)
        if not klines: return 0
        idx = di(date, klines)
        return klines[idx]["close"] if idx >= 0 else 0

    def buy(self, date, code, pct, details):
        klines = get_klines(code)
        if not klines: return False
        idx = di(date, klines)
        if idx < 0: return False
        price = klines[idx]["close"]
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
            "stop_loss": round(price * 0.92, 2)
        }

        sec = SECTOR_MAP.get(code, "")
        # 计算买入时的总仓位
        tv2 = self.total_value(date)
        total_pct = sum(p["cost"] for p in self.portfolio.values()) / tv2 * 100 if tv2 > 0 else 0

        # 构建买入理由
        reason_parts = [
            f"中继买点|大盘{self.market_phase}",
            f"{details['buy_desc']}(量比{details['vol_ratio']})",
            f"{details['band_desc']}",
            f"{details['line_desc']}{details['line_mult']:.1f}x",
            f"仓位{pct*100:.1f}%"
        ]
        reason = " | ".join(reason_parts)

        self.trades.append({
            "date": date, "time": "15:00", "direction": "买入",
            "code": code, "name": name_of(code),
            "sector": sec,
            "qty": shares, "price": round(price, 2), "amount": round(cost, 2),
            "pos_pct": round(pct * 100, 1),
            "total_pct": round(total_pct, 1),
            "reason": reason
        })
        return True

    def sell(self, date, code, reason):
        if code not in self.portfolio: return
        pos = self.portfolio[code]
        price = self._price(code, date)
        if price == 0: return
        proceeds = pos["shares"] * price
        self.cash += proceeds

        pl = (price - pos["price"]) * pos["shares"]
        pl_pct = (price - pos["price"]) / pos["price"] * 100

        # 计算卖出后总仓位
        del self.portfolio[code]
        tv = self.total_value(date)
        total_pct = sum(p["cost"] for p in self.portfolio.values()) / tv * 100 if tv > 0 and self.portfolio else 0

        self.trades.append({
            "date": date, "time": "15:00", "direction": "卖出",
            "code": code, "name": name_of(code),
            "sector": SECTOR_MAP.get(code, ""),
            "qty": pos["shares"], "price": round(price, 2),
            "amount": round(proceeds, 2),
            "profit": round(pl, 2), "profit_pct": round(pl_pct, 2),
            "total_pct": round(total_pct, 1),
            "pos_pct": "-",
            "reason": reason
        })

# ═══ 运行 ═══
sim = SimV2()
w1_dates = ["20260407","20260408","20260409","20260410"]

# 大盘判强弱
market_phase, total_limit, mult = judge_market("20260407")
sim.market_phase = market_phase

# 4/7：选股买入
results = []
for sec, stocks in ALL_STOCKS.items():
    for code in stocks:
        klines = get_klines(code)
        if not klines: continue
        idx = di("20260407", klines)
        if idx < 20: continue
        prices_c = [k["close"] for k in klines]
        prices_l = [k["low"] for k in klines]
        volumes = [k["volume"] for k in klines]

        # 中继买点筛选
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

        pct, det = calc_position(code, "20260407", market_phase, [p for p in sim.portfolio.keys()])
        if pct > 0:
            results.append((code, pct, det))

# 按仓位降序，同方向只取1只（已在calc_position处理）
results.sort(key=lambda x: -x[1])

# 买入
used_secs = set()
buy_report = []
for code, pct, det in results:
    sec = SECTOR_MAP.get(code, "")
    if sec in used_secs: continue
    if len(sim.portfolio) >= 5: break
    sim.buy("20260407", code, pct, det)
    used_secs.add(sec)
    buy_report.append((code, pct, det))

# 4/8~4/10：每日检查
for date in w1_dates[1:]:
    for code in list(sim.portfolio.keys()):
        pos = sim.portfolio[code]
        low = 0
        klines = get_klines(code)
        if klines:
            idx = di(date, klines)
            if idx >= 0:
                low = klines[idx]["low"]
        if low > 0 and low <= pos["stop_loss"]:
            sim.sell(date, code, f"止损触发|低点{low:.2f}<止损{pos['stop_loss']:.2f}")

# ═══ 输出报告 ═══
start_cash = 1_000_000
end_val = sim.total_value("20260410")
pnl = end_val - start_cash

lines = []
def L(s):
    lines.append(s)
    print(s)

L("=" * 110)
L("  v2 第1周交易报告 | 2026-04-07 ~ 2026-04-10 | 3L仓位决策流程图版")
L("=" * 110)
L("")

# 大盘判强弱
L("📊  大盘判强弱")
L(f"  大盘阶段: {market_phase}  |  自选股平均量比: {mult}x")
L(f"  总仓位上限: {total_limit[0]*100:.0f}% ~ {total_limit[1]*100:.0f}%")
L("")

# 仓位决策流程图
L("📐  仓位决策流程")
L("  ┌─────────────────────────────────────────────┐")
L(f"  │ ① 大盘判强弱                                   │")
L(f"  │   {market_phase} (量比{mult}x) → 仓位系数 × {[v for k,v in [('低迷期',1.2),('正常',1.0),('强势',0.8),('高潮期',0.3)] if k==market_phase][0]} │")
L("  ├─────────────────────────────────────────────┤")
L("  │ ② 买点类型 (中继买点)                         │")
L("  │   基础仓位 6% × 缩量质量系数（优秀1.2/标准1.0/不足0.7）  │")
L("  ├─────────────────────────────────────────────┤")
L("  │ ③ 波段位置                                     │")
L("  │   鱼头×0.5 / 鱼身×1.0 / 鱼尾×0.5               │")
L("  ├─────────────────────────────────────────────┤")
L("  │ ④ 行业分散修正                                 │")
L("  │   主线方向×1.2 / 非主线×0.8 / 同方向不新增    │")
L("  └─────────────────────────────────────────────┘")
L(f"  最终个股仓位 = 6% × {[v for k,v in [('低迷期',1.2),('正常',1.0),('强势',0.8),('高潮期',0.3)] if k==market_phase][0]} × 缩量系数 × 波段系数 × 行业系数")
L("  约束范围: 2% ~ 10%")
L("")

# 买入明细
L("📋  本期买入")
L(f"  {'股票':12} {'代码':8} {'方向':10} {'仓位':>8} {'缩量':>8} {'波段':>12} {'行业':>10} {'仓位计算':>30}")
L("  " + "-" * 110)
for code, pct, det in buy_report:
    sec = det["sector"]
    calc_str = f"6%×{det['phase_mult']}×{det['buy_mult']}×{det['band_mult']}×{det['line_mult']}={pct*100:.1f}%"
    L(f"  {name_of(code):12} {code:8} {sec:10} {pct*100:>7.1f}% {det['buy_desc']:>8} {det['band_desc']:>12} {det['line_desc']:>10} {calc_str:>30}")
L("")

# 交易明细表
L("📋  逐笔交易明细")
L(f"  {'日期':12} {'时间':6} {'操作':6} {'名称':12} {'代码':8} {'方向':10} {'数量':>8} {'单价':>8} {'金额':>10} {'个股仓位':>8} {'总仓位':>8} {'理由'}")
L("  " + "-" * 130)
for t in sim.trades:
    d = t["date"]
    fd = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    name = t["name"]
    sec = t.get("sector", "")
    if t["direction"] == "买入":
        pp = f"{t['pos_pct']:.1f}%"
        tp = f"{t['total_pct']:.1f}%"
        r = "中继买点"
        L(f"  {fd:12} {'15:00':6} {'买入':6} {name:12} {t['code']:8} {sec:10} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {pp:>8} {tp:>8} {r}")
    else:
        pp = f"-"
        tp = f"{t['total_pct']:.1f}%"
        pl_pct = t.get("profit_pct", 0)
        pl_str = f"{'止损' if pl_pct < 0 else '止盈'}{pl_pct:+.1f}%" if t.get("profit") else t["reason"]
        L(f"  {fd:12} {'15:00':6} {'卖出':6} {name:12} {t['code']:8} {sec:10} {t['qty']:>8} {t['price']:>8.2f} {t['amount']:>10,.0f} {pp:>8} {tp:>8} {pl_str}")
L("")

# 本周表现
L("📊  本周表现")
L(f"  期初资产: {start_cash:>12,.0f}")
L(f"  期末资产: {end_val:>12,.0f}")
L(f"  本周盈亏: {pnl:>+12,.0f} ({pnl/start_cash*100:+.2f}%)")
buys = sum(1 for t in sim.trades if t["direction"] == "买入")
sells = sum(1 for t in sim.trades if t["direction"] == "卖出")
L(f"  操作: 买入{buys}笔 | 卖出{sells}笔")
L("")

# 期末持仓
L("📋  期末持仓")
if sim.portfolio:
    L(f"  {'股票':12} {'代码':8} {'方向':10} {'数量':>8} {'成本':>8} {'现价':>8} {'盈亏':>10} {'盈亏%':>8} {'仓位%':>8}")
    L("  " + "-" * 90)
    for code, pos in sim.portfolio.items():
        cur_p = sim._price(code, "20260410")
        pl_val = (cur_p - pos["price"]) * pos["shares"]
        pl_pct = (cur_p - pos["price"]) / pos["price"] * 100
        tv = sim.total_value("20260410")
        cur_pct = pos["cost"] / tv * 100 if tv > 0 else 0
        L(f"  {name_of(code):12} {code:8} {SECTOR_MAP.get(code,''):10} {pos['shares']:>8} {pos['price']:>8.2f} {cur_p:>8.2f} {pl_val:>+10,.0f} {pl_pct:>+7.2f}% {cur_pct:>7.1f}%")
else:
    L("  空仓")
L("")

# 仓位计算明细
L("📐  各股仓位计算明细")
L(f"  {'股票':12} {'方向':10} {'大盘系数':>8} {'缩量系数':>8} {'波段系数':>8} {'行业系数':>8} {'最终':>8}")
L("  " + "-" * 70)
for code, pct, det in buy_report:
    L(f"  {name_of(code):12} {det['sector']:10} {det['phase_mult']:>7.1f}x {det['buy_mult']:>7.1f}x {det['band_mult']:>7.1f}x {det['line_mult']:>7.1f}x {pct*100:>6.1f}%")
L("")

# 保存
with open(os.path.join(OUT_DIR, "第1周_v2报告.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\n✅ v2第1周报告已保存到 {OUT_DIR}/")

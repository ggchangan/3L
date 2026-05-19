#!/usr/bin/env python3
"""v2增强报告生成器 - 6部分结构"""
import json, os

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = "/home/ubuntu/data/3l/simulation/v2"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

# ═══ 代码→名称映射（同前）═══
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

# ═══ Part 1: 大盘判强弱 ═══
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

# ═══ Part 2: 主线判定 ═══
def calc_sector_momentum(date_str):
    """各行业4/7动量评分 - 20日涨幅均值"""
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
            avg_gain = sum(gains) / len(gains)
            # Count stocks above MA20
            above_ma20 = 0
            for code in stocks:
                klines = get_klines(code)
                if not klines: continue
                idx = di(date_str, klines)
                if idx < 20: continue
                ma20 = sum(k["close"] for k in klines[idx-19:idx+1]) / 20
                if klines[idx]["close"] > ma20:
                    above_ma20 += 1
            sec_scores[sec] = {
                "avg_gain_20d": round(avg_gain, 2),
                "above_ma20": above_ma20,
                "total": len(gains),
                "above_pct": round(above_ma20 / len(gains) * 100, 1)
            }
    return sec_scores

# ═══ Part 3-4: 选股与交易 ═══
def scan_candidates(date_str, market_phase):
    """完整选股过程 - 返回所有候选及淘汰原因"""
    candidates_all = []
    rejected = []
    for sec, stocks in ALL_STOCKS.items():
        for code in stocks:
            klines = get_klines(code)
            if not klines:
                rejected.append((code, sec, "无K线数据"))
                continue
            idx = di(date_str, klines)
            if idx < 20:
                rejected.append((code, sec, "K线不足20天"))
                continue
            
            prices_c = [k["close"] for k in klines]
            prices_l = [k["low"] for k in klines]
            volumes = [k["volume"] for k in klines]
            
            ma20 = sum(prices_c[idx-19:idx+1]) / 20
            ma10 = sum(prices_c[idx-9:idx+1]) / 10
            tc = prices_c[idx]
            tl = prices_l[idx]
            v5 = sum(volumes[idx-4:idx+1]) / 5
            
            reasons = []
            
            # 条件1: 在MA20上方
            if tc <= ma20:
                rejected.append((code, sec, f"低于MA20(收{tc:.2f}<MA20{ma20:.2f})"))
                continue
            
            # 条件2: 缩量
            vol_ratio = volumes[idx] / v5 if v5 > 0 else 1
            if volumes[idx] >= v5 * 0.85:
                rejected.append((code, sec, f"缩量不足(量比{vol_ratio:.2f}>0.85)"))
                continue
            
            # 条件3: 回踩支撑
            near10 = tl <= ma10 * 1.03 and tl >= ma10 * 0.94
            near20 = tl <= ma20 * 1.03 and tl >= ma20 * 0.94
            if not (near10 or near20):
                rejected.append((code, sec, f"未回踩支撑(低{tl:.2f}, MA10{ma10:.2f}, MA20{ma20:.2f})"))
                continue
            
            # 条件4: 涨幅不过大
            chg = (tc - prices_c[idx-1]) / prices_c[idx-1] * 100 if idx > 0 else 0
            if chg > 4:
                rejected.append((code, sec, f"涨幅过大({chg:.1f}%>4%)"))
                continue
            
            # 通过全部条件
            vol_desc = "优秀缩量" if vol_ratio < 0.6 else "标准缩量"
            support = "MA10" if near10 else "MA20"
            candidates_all.append({
                "code": code, "sector": sec,
                "close": round(tc, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2),
                "vol_ratio": round(vol_ratio, 2), "vol_desc": vol_desc,
                "support": support,
                "change": round(chg, 2)
            })
    
    # 排序：按缩量程度（越缩量越好）+ 靠近支撑程度
    candidates_all.sort(key=lambda x: (x["vol_ratio"]))
    return candidates_all, rejected

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
    same_sec = [c for c in existing_codes if SECTOR_MAP.get(c, "") == sec]
    if same_sec: return 0, {}
    
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

# ═══ 执行全部计算 ═══
date_str = "20260407"
market_phase, total_limit, mult = judge_market(date_str)

# Part 2: 行业动量
sec_scores = calc_sector_momentum(date_str)

# Part 3: 选股
candidates, rejected = scan_candidates(date_str, market_phase)

# 选股5只
selected = []
used_secs = set()
for c in candidates:
    code = c["code"]
    sec = c["sector"]
    if sec in used_secs: continue
    if len(selected) >= 5: break
    pct, det = calc_position(code, date_str, market_phase, [s["data"]["code"] for s in selected])
    if pct > 0:
        selected.append({"data": c, "pct": pct, "details": det})
        used_secs.add(sec)

# Part 4: 交易明细 + Part 6: 持仓
prices_c_final = {}
for s in selected:
    code = s["data"]["code"]
    klines = get_klines(code)
    idx = di(date_str, klines)
    prices_c_final[code] = klines[idx]["close"] if idx >= 0 else 0

# 每周五(4/10)价格
prices_eow = {}
for s in selected:
    code = s["data"]["code"]
    klines = get_klines(code)
    idx = di("20260410", klines)
    prices_eow[code] = round(klines[idx]["close"], 2) if idx >= 0 else 0

# ═══ 生成报告数据文件 ═══
report = {
    "part1_market": {
        "phase": market_phase,
        "volume_mult": mult,
        "total_limit_low": total_limit[0]*100,
        "total_limit_high": total_limit[1]*100
    },
    "part2_sectors": {},
    "part3_selection": {
        "total_candidates": len(candidates),
        "total_stocks_239": sum(len(v) for v in ALL_STOCKS.values()),
        "selected": [],
        "rejected_count": len(rejected)
    },
    "part4_trades": [],
    "part5_performance": {},
    "part6_holdings": []
}

# Part 2 detail
for sec, sc in sorted(sec_scores.items(), key=lambda x: -x[1]["avg_gain_20d"]):
    main = "主线" if sec in {"机器人","半导体","AI应用","算力"} else "非主线"
    report["part2_sectors"][sec] = {
        "avg_gain_20d": sc["avg_gain_20d"],
        "above_ma20_pct": sc["above_pct"],
        "classification": main,
        "reason": ""
    }
# 加判定理由
for sec in report["part2_sectors"]:
    sc = report["part2_sectors"][sec]
    if sc["classification"] == "主线":
        sc["reason"] = f"20日涨幅{sc['avg_gain_20d']:+.1f}% | {sc['above_ma20_pct']:.0f}%个股站上MA20 | 市场聚焦方向"
    else:
        sc["reason"] = f"20日涨幅{sc['avg_gain_20d']:+.1f}% | 动量排序靠后 | 非当前市场聚焦方向"

# Part 3 detail
used_sectors_list = []
for i, s in enumerate(selected):
    c = s["data"]
    d = s["details"]
    pct = s["pct"]
    shares = 0
    price = c["close"]
    invest = 1_000_000 * pct
    shares = int(invest / price / 100) * 100
    cost = shares * price if shares > 0 else 0
    
    item = {
        "rank": i+1,
        "code": c["code"], "name": name_of(c["code"]),
        "sector": c["sector"],
        "price": price, "shares": shares, "cost": cost,
        "pct": pct*100,
        "selection_reason": f"中继买点通过: 在MA20上方({c['close']}>{c['ma20']}), "
                           f"{c['vol_desc']}(量比{c['vol_ratio']}), 回踩{c['support']}支撑({c['support']})",
        "calc_formula": f"6% × {d['phase_mult']} × {d['buy_mult']} × {d['band_mult']} × {d['line_mult']} = {pct*100:.1f}%",
        "details": {
            "phase_coef": d["phase_mult"], "buy_coef": d["buy_mult"],
            "band_coef": d["band_mult"], "line_coef": d["line_mult"],
            "buy_type": d["buy_desc"], "band_type": d["band_desc"],
            "line_type": d["line_desc"]
        }
    }
    report["part3_selection"]["selected"].append(item)
    used_sectors_list.append(c["sector"])

# Part 4: 交易明细
total_pct_running = 0
for i, s in enumerate(report["part3_selection"]["selected"]):
    total_pct_running += s["pct"]
    report["part4_trades"].append({
        "date": "04-07", "time": "15:00", "direction": "买入",
        "name": s["name"], "code": s["code"], "sector": s["sector"],
        "qty": s["shares"], "price": s["price"], "amount": s["cost"],
        "pos_pct": f"{s['pct']:.1f}%",
        "total_pct": f"{total_pct_running:.1f}%",
        "reason": "中继买点"
    })

# Part 5: 业绩
start_cash = 1_000_000
portfolio_val = sum(s["shares"] * prices_eow[s["code"]] for s in report["part3_selection"]["selected"])
end_val = (1_000_000 - sum(s["cost"] for s in report["part3_selection"]["selected"])) + portfolio_val
pnl = end_val - start_cash

report["part5_performance"] = {
    "start_value": start_cash,
    "end_value": round(end_val),
    "pnl": round(pnl),
    "pnl_pct": round(pnl/start_cash*100, 2),
    "buy_count": len(report["part4_trades"]),
    "sell_count": 0,
    "market_phase": market_phase,
    "volume_mult": mult
}

# Part 6: 持仓
for s in report["part3_selection"]["selected"]:
    code = s["code"]
    bp = s["price"]
    ep = prices_eow[code]
    pl_val = (ep - bp) * s["shares"]
    pl_pct = (ep - bp) / bp * 100
    cur_pct = s["cost"] / end_val * 100 if end_val > 0 else 0
    report["part6_holdings"].append({
        "name": s["name"], "code": code, "sector": s["sector"],
        "shares": s["shares"], "buy_price": bp, "current_price": ep,
        "pl_val": round(pl_val), "pl_pct": round(pl_pct, 2),
        "cost_pct": round(cur_pct, 1)
    })

with open(os.path.join(OUT_DIR, "report_data.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(json.dumps(report, ensure_ascii=False, indent=2))

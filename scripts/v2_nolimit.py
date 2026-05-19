#!/usr/bin/env python3
"""v2第2周模拟 - 无5只上限，全部由仓位约束"""
import json, os, pickle

DATA_FILE = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT_DIR = "/home/ubuntu/data/3l/simulation/v2"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DATA_FILE) as f:
    raw = json.load(f)
ALL_STOCKS = raw["stocks"]

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
def name_of(c): return CODE_NAMES.get(c,c)

SECTOR_MAP = {}
for sec, stocks in ALL_STOCKS.items():
    for code in stocks:
        SECTOR_MAP[code] = sec

def klines_of(code):
    for sec, stocks in ALL_STOCKS.items():
        if code in stocks: return stocks[code]
    return None

def find_idx(date, klines):
    for i,k in enumerate(klines):
        if k["date"]==date: return i
    return -1

MAIN_LINES = {"机器人","半导体","AI应用","算力"}

def judge_market(date_str):
    mults = []
    for sec, stocks in ALL_STOCKS.items():
        for code in stocks:
            kls = klines_of(code)
            if not kls: continue
            idx = find_idx(date_str, kls)
            if idx < 30: continue
            vs = [k["volume"] for k in kls[idx-29:idx+1]]
            sv = sorted(vs)
            lb = sum(sv[:max(3,len(sv)//5)]) / max(3,len(sv)//5)
            cur = kls[idx]["volume"]
            r = cur/lb if lb>0 else 0
            mults.append(r)
    avg = sum(mults)/len(mults) if mults else 1
    if avg<1.5: p,lim="低迷期",(0.6,0.8)
    elif avg<2: p,lim="正常",(0.4,0.6)
    elif avg<4: p,lim="强势",(0.2,0.4)
    else: p,lim="高潮期",(0,0.2)
    return p, lim, round(avg,2)

def sector_momentum(date_str):
    sc = {}
    for sec, stocks in ALL_STOCKS.items():
        gains = []
        above = 0
        total = 0
        for code in stocks:
            kls = klines_of(code)
            if not kls: continue
            idx = find_idx(date_str, kls)
            if idx<20: continue
            p20 = kls[idx-20]["close"]
            pc = kls[idx]["close"]
            gains.append((pc-p20)/p20*100)
            ma20 = sum(k["close"] for k in kls[idx-19:idx+1])/20
            if pc>ma20: above+=1
            total+=1
        if gains:
            sc[sec] = {"avg": round(sum(gains)/len(gains),2), "above_pct": round(above/total*100,1)}
    return sc

def scan_buys(date_str, exclude_codes):
    cands = []
    for sec, stocks in ALL_STOCKS.items():
        for code in stocks:
            if code in exclude_codes: continue
            kls = klines_of(code)
            if not kls: continue
            idx = find_idx(date_str, kls)
            if idx<20: continue
            C = [k["close"] for k in kls]
            L = [k["low"] for k in kls]
            V = [k["volume"] for k in kls]
            ma20 = sum(C[idx-19:idx+1])/20
            ma10 = sum(C[idx-9:idx+1])/10
            tc, tl = C[idx], L[idx]
            v5 = sum(V[idx-4:idx+1])/5
            if tc<=ma20: continue
            if V[idx]>=v5*0.85: continue
            nr10 = tl<=ma10*1.03 and tl>=ma10*0.94
            nr20 = tl<=ma20*1.03 and tl>=ma20*0.94
            if not (nr10 or nr20): continue
            chg = (tc-C[idx-1])/C[idx-1]*100 if idx>0 else 0
            if chg>4: continue
            vr = V[idx]/v5 if v5>0 else 1
            cands.append({"code":code,"sector":sec,"close":round(tc,2),"ma10":round(ma10,2),
                         "ma20":round(ma20,2),"vol_ratio":round(vr,2),
                         "support":"MA10" if nr10 else "MA20","change":round(chg,2)})
    cands.sort(key=lambda x: x["vol_ratio"])
    return cands

def calc_pos(code, date_str, mkt_phase, existing_codes):
    kls = klines_of(code)
    if not kls: return 0,{}
    idx = find_idx(date_str, kls)
    if idx<20: return 0,{}
    C = [k["close"] for k in kls]
    V = [k["volume"] for k in kls]
    p = C[idx]
    phm = {"低迷期":1.2,"正常":1.0,"强势":0.8,"高潮期":0.3}
    pm = phm.get(mkt_phase,1.0)
    v5 = sum(V[idx-4:idx+1])/5
    vr = V[idx]/v5 if v5>0 else 1
    if vr<0.6: bm,bd=1.2,"优秀缩量"
    elif vr<0.85: bm,bd=1.0,"标准缩量"
    else: bm,bd=0.7,"缩量不足"
    ma20 = sum(C[idx-19:idx+1])/20
    pos = (p-ma20)/ma20
    if pos<0.03: bnm,bnd=0.5,"鱼头(初突破)"
    elif pos<0.15: bnm,bnd=1.0,"鱼身(确认趋势)"
    else: bnm,bnd=0.5,"鱼尾(远离均线)"
    sec = SECTOR_MAP.get(code,"")
    ex_secs = set(SECTOR_MAP.get(c,"") for c in existing_codes)
    if sec in ex_secs: return 0,{}
    lm = 1.2 if sec in MAIN_LINES else 0.8
    ld = "主线" if sec in MAIN_LINES else "非主线"
    raw = 0.06 * pm * bm * bnm * lm
    final = max(0.02, min(raw, 0.10))
    return final, {"pm":pm,"bm":bm,"bnm":bnm,"lm":lm,"base":0.06,"bd":bd,"bnd":bnd,"ld":ld,"vr":vr,"sec":sec,"pos_in_trend":round(pos,4)}

# ═══ 模拟类（无5只上限）═══
class Sim:
    def __init__(self):
        self.cash = 1000000
        self.portfolio = {}
        self.trades = []
        self.market_phase = ""
    def price(self, code, date):
        kls = klines_of(code)
        if not kls: return 0
        idx = find_idx(date, kls)
        return kls[idx]["close"] if idx>=0 else 0
    def low(self, code, date):
        kls = klines_of(code)
        if not kls: return 0
        idx = find_idx(date, kls)
        return kls[idx]["low"] if idx>=0 else 0
    def tv(self, date):
        pv = sum(self.price(c,p["entry_date"] if date=="20260407" else date)*p["shares"] for c,p in self.portfolio.items())
        return self.cash + pv
    def total_pct(self, date):
        v = self.tv(date)
        cs = sum(p["cost"] for p in self.portfolio.values())
        return cs/v*100 if v>0 else 0
    def buy(self, date, code, pct, det):
        p = self.price(code, date)
        if p<=0: return False
        v = self.tv(date) or self.cash
        invest = v * pct
        sh = int(invest/p/100)*100
        if sh<=0: return False
        cost = sh*p
        if cost>self.cash:
            sh = int(self.cash/p/100)*100
            if sh<=0: return False
            cost = sh*p
        self.cash -= cost
        self.portfolio[code] = {"shares":sh,"price":p,"cost":cost,"entry_date":date,"pct":pct,
                                "sl":round(p*0.92,2),"hwm":p,"cup":0}
        tp = self.total_pct(date)
        self.trades.append({"date":date,"time":"15:00","direction":"买入","code":code,
            "name":name_of(code),"sector":SECTOR_MAP.get(code,""),
            "qty":sh,"price":round(p,2),"amount":round(cost,2),
            "pos_pct":round(pct*100,1),"total_pct":round(tp,1),"reason":"中继买点"})
        return True
    def sell(self, date, code, reason):
        if code not in self.portfolio: return
        pos = self.portfolio[code]
        p = self.price(code,date)
        if p<=0: return
        proc = pos["shares"]*p
        self.cash += proc
        pl = (p-pos["price"])*pos["shares"]
        plp = (p-pos["price"])/pos["price"]*100
        del self.portfolio[code]
        tp = self.total_pct(date)
        lb = "止盈" if pl>0 else "止损"
        self.trades.append({"date":date,"time":"15:00","direction":"卖出","code":code,
            "name":name_of(code),"sector":SECTOR_MAP.get(code,""),
            "qty":pos["shares"],"price":round(p,2),"amount":round(proc,2),
            "profit":round(pl,2),"profit_pct":round(plp,2),
            "total_pct":round(tp,1),"pos_pct":"-","reason":f"{lb}|{reason}"})
    def check(self, date):
        for code in list(self.portfolio.keys()):
            pos = self.portfolio[code]
            p = self.price(code,date)
            l = self.low(code,date)
            if p<=0: continue
            if p>pos["hwm"]: pos["hwm"]=p
            yes = self.price(code, self.prev_day(date))
            if yes>0 and p>yes: pos["cup"]+=1
            else: pos["cup"]=0
            if l>0 and l<=pos["sl"]:
                self.sell(date,code,f"跌破止损{pos['sl']:.2f}")
                continue
            if pos["cup"]>=2:
                cg = (p-pos["price"])/pos["price"]*100
                if cg>12:
                    kls = klines_of(code)
                    idx = find_idx(date,kls)
                    if idx>=3:
                        vs = [k["volume"] for k in kls[idx-2:idx+1]]
                        if vs[2]<vs[1] and vs[1]<vs[0]:
                            self.sell(date,code,f"加速量递减|cg{cg:.1f}%")
                            continue
            kls = klines_of(code)
            idx = find_idx(date,kls)
            if idx>=20:
                ma20 = sum(k["close"] for k in kls[idx-19:idx+1])/20
                if p<ma20:
                    self.sell(date,code,f"跌破MA20({ma20:.2f})")
                    continue
    def prev_day(self, date_str):
        for sec,stocks in ALL_STOCKS.items():
            for code in stocks:
                kls = klines_of(code)
                if kls:
                    idx = find_idx(date_str,kls)
                    if idx>0: return kls[idx-1]["date"]
        return date_str

# ═══ 第1周建仓 ═══
print("═══ 第1周建仓 (20260407) ═══")
sim = Sim()
market_phase, total_limit, mult = judge_market("20260407")
sim.market_phase = market_phase
print(f"大盘: {market_phase} (量比{mult}x) 总仓位上限: {total_limit[0]*100:.0f}%-{total_limit[1]*100:.0f}%")

cands = scan_buys("20260407", [])
print(f"候选: {len(cands)}只")
used_secs = set()
buys = []
for c in cands:
    code = c["code"]
    sec = c["sector"]
    if sec in used_secs: continue
    # 检查总仓位上限
    tp = sim.total_pct("20260407")
    pct, det = calc_pos(code,"20260407",market_phase, list(sim.portfolio.keys()))
    if pct>0 and tp+pct*100 <= total_limit[1]*100:
        sim.buy("20260407",code,pct,det)
        used_secs.add(sec)
        buys.append((code, pct, det))
        print(f"  ✅ {name_of(code)}({code}) {sec} {pct*100:.1f}% | tp_now={sim.total_pct('20260407'):.1f}%")

print(f"建仓完成: {len(sim.portfolio)}只 | 总仓位{sim.total_pct('20260407'):.1f}%")
print(f"cash={sim.cash:.0f} tv={sim.tv('20260407'):.0f}")

# 第1周检查
for d in ["20260408","20260409","20260410"]:
    sim.check(d)
print(f"第1周末: {len(sim.portfolio)}只 | tv={sim.tv('20260410'):.0f} | pnl={sim.tv('20260410')-1000000:+,.0f}")

# ═══ 第2周 (20260413~20260417) ═══
print(f"\n═══ 第2周 (20260413~20260417) ═══")
market_phase2, total_limit2, mult2 = judge_market("20260413")
sim.market_phase = market_phase2
print(f"大盘: {market_phase2} (量比{mult2}x) 总仓位上限: {total_limit2[0]*100:.0f}%-{total_limit2[1]*100:.0f}%")

# 周一
print(f"\n周一 20260413:")
w1_end = sim.tv("20260410")
sim.check("20260413")
print(f"  检查后: {len(sim.portfolio)}只 | tv={sim.tv('20260413'):.0f} | 仓位{sim.total_pct('20260413'):.1f}%")

# 扫描买入
cands2 = scan_buys("20260413", list(sim.portfolio.keys()))
print(f"  候选: {len(cands2)}只")
existing_secs = set(SECTOR_MAP.get(c,"") for c in sim.portfolio.keys())
new_buys = []
for c in cands2:
    code = c["code"]
    sec = c["sector"]
    if sec in existing_secs: continue
    tp = sim.total_pct("20260413")
    pct, det = calc_pos(code,"20260413",market_phase2, list(sim.portfolio.keys()))
    if pct>0:
        remaining = total_limit2[1]*100 - tp
        if remaining >= pct*100:
            sim.buy("20260413",code,pct,det)
            existing_secs.add(sec)
            new_buys.append((code,pct,det))
            print(f"  ✅ {name_of(code)}({code}) {sec} {pct*100:.1f}% | tp_now={sim.total_pct('20260413'):.1f}%")

# 每日检查
for d in ["20260414","20260415","20260416","20260417"]:
    sim.check(d)
    print(f"  {d[-5:]}: {len(sim.portfolio)}只 tv={sim.tv(d):.0f} 仓位{sim.total_pct(d):.1f}%")

end = sim.tv("20260417")
print(f"\n📊 第2周结果:")
print(f"  期初(4/10): {w1_end:,.0f} → 期末(4/17): {end:,.0f}")
print(f"  本周P&L: {end-w1_end:+,.0f} ({(end-w1_end)/w1_end*100:+.2f}%)")
print(f"  累计P&L: {end-1000000:+,.0f} ({(end-1000000)/1000000*100:+.2f}%)")
print(f"  期末持仓: {len(sim.portfolio)}只 仓位{sim.total_pct('20260417'):.1f}%")

# 交易明细
print(f"\n📋 交易明细:")
for t in sim.trades:
    if t["direction"]=="买入":
        print(f"  {t['date'][-5:]} 买入 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | 个股{t['pos_pct']:>5}% 总{t['total_pct']:>5}%")
    else:
        print(f"  {t['date'][-5:]} 卖出 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | {t['reason']} ({t.get('profit_pct',0):+.2f}%)")

# 保存
state = {"cash":sim.cash,"portfolio":sim.portfolio,"trades":sim.trades,
         "w1_end":w1_end,"w2_end":end}
with open(os.path.join(OUT_DIR,"full_state.pkl"),"wb") as f:
    pickle.dump(state,f)
print(f"\n✅ 已保存")

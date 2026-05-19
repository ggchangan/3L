#!/usr/bin/env python3
"""v3.3 第2周 (20260413~20260417) — 从第1周状态继续"""
import json, os, pickle, urllib.request

DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT = "/home/ubuntu/data/3l/simulation/v3"
PKL = os.path.join(OUT, "w1_v33.pkl")

with open(DATA) as f:
    raw = json.load(f)
ALL = raw["stocks"]

# 股票名称映射
CN = {
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
    "002407":"多氟多","301358":"湖南裕能","300383":"光环新网",
}
def nm(c): return CN.get(c,c)

SM = {}
for sec, stocks in ALL.items():
    for c in stocks:
        SM[c] = sec
from judge_main_line import get_main_lines

KL = lambda c: next((stocks[c] for sec,stocks in ALL.items() if c in stocks), None)
DI = lambda d,kl: next((i for i,k in enumerate(kl) if k["date"]==d), -1)

# ═══ 函数 ═══
def get_index_data():
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000001&scale=240&ma=no&datalen=120"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode("utf-8"))
    result = []
    for d in data:
        result.append({"date": d["day"], "open": float(d["open"]), "close": float(d["close"]),
                       "high": float(d["high"]), "low": float(d["low"]), "volume": int(d["volume"])})
    return result

def judge_peak_trough(index_data, date_str):
    ds = date_str
    if len(date_str) == 8 and date_str.isdigit():
        ds = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    idx = next((i for i,k in enumerate(index_data) if k["date"]==ds), -1)
    if idx < 20: return 0, "波中", "正常交易", {"错误": "数据不足"}
    C = [k["close"] for k in index_data]
    H = [k["high"] for k in index_data]
    L = [k["low"] for k in index_data]
    V = [k["volume"] for k in index_data]
    price = C[idx]; ma20 = sum(C[idx-19:idx+1])/20
    vs = sorted(V[idx-29:idx+1])
    lb = sum(vs[:max(3, len(vs)//5)]) / max(3, len(vs)//5)
    vol_ratio = V[idx] / lb if lb > 0 else 1
    body = abs(C[idx] - index_data[idx]["open"])
    avg_body = sum(abs(C[j] - index_data[j]["open"]) for j in range(idx-4, idx+1)) / 5
    body_ratio = body / avg_body if avg_body > 0 else 1
    score = 0; details = {}
    pct_from_ma = (price - ma20) / ma20 * 100
    if pct_from_ma > 3: score += 1; details["趋势"] = f"+1"
    elif pct_from_ma < -3: score -= 1; details["趋势"] = f"-1"
    else: details["趋势"] = "0"
    if vol_ratio > 3: score += 1; details["量能"] = f"+1({vol_ratio:.1f}x)"
    elif vol_ratio < 1.3: score -= 1; details["量能"] = f"-1({vol_ratio:.1f}x)"
    else: details["量能"] = f"0({vol_ratio:.1f}x)"
    has_accel=False; has_panic=False
    if idx>=3:
        chgs=[(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-2,idx+1)]
        if len(chgs)==3 and all(chgs[j]>0 and chgs[j]>chgs[j-1] for j in range(1,3)):
            if V[idx]>sum(V[idx-4:idx+1])/5: has_accel=True
    if idx>=3:
        pc=[(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-4,idx+1)]
        if sum(1 for c in pc if c<0)>=3 and V[idx]>sum(V[idx-4:idx+1])/5*1.3:
            if abs((L[idx]-C[idx])/C[idx])>0.01: has_panic=True
    if has_accel: score+=1; details["形态"]="+1"
    elif has_panic: score-=1; details["形态"]="-1"
    else: details["形态"]="0"
    if body_ratio>1.2: score+=1; details["波动"]="+1"
    elif body_ratio<0.8: score-=1; details["波动"]="-1"
    else: details["波动"]="0"
    if score>=3: result="波峰区域"; strategy="控仓"
    elif score>=1: result="偏波峰"; strategy="偏防守"
    elif score<=-3: result="波谷区域"; strategy="重仓80%-100%"
    elif score<=-1: result="偏波谷"; strategy="偏进攻"
    else: result="波中"; strategy="正常交易"
    return score, result, strategy, details

def trend_of(code, d):
    kl = KL(code)
    if not kl: return "下降趋势"
    idx = DI(d, kl)
    if idx < 13: return "下降趋势"
    C = [k["close"] for k in kl]
    ma10_now = sum(C[idx-9:idx+1]) / 10
    ma10_prev = sum(C[idx-12:idx-2]) / 10
    diff = (ma10_now - ma10_prev) / ma10_prev if ma10_prev > 0 else 0
    if diff > 0.003: return "上升趋势"
    elif diff < -0.003: return "下降趋势"
    else: return "区间震荡"

def get_position(code, d, is_mainline, score):
    if score <= -1: base = 0.10
    else: base = 0.05
    tr = trend_of(code, d)
    if tr != "上升趋势": return base
    kl = KL(code); idx = DI(d, kl)
    if idx<5: return base
    V = [k["volume"] for k in kl]
    v5 = sum(V[idx-4:idx+1])/5
    vr = V[idx]/v5 if v5>0 else 1
    if is_mainline and tr=="上升趋势" and vr<0.7:
        return min(base*2, 0.20)
    return base

INDIVIDUAL_MAX = 0.20; SECTOR_MAX = 0.40

def scan(d, ex, main_lines=None):
    cs = []
    for sec, stocks in ALL.items():
        for c in stocks:
            if c in ex: continue
            kl = KL(c)
            if not kl: continue
            idx = DI(d,kl)
            if idx<20: continue
            C = [k["close"] for k in kl]; L = [k["low"] for k in kl]
            V = [k["volume"] for k in kl]
            ma20 = sum(C[idx-19:idx+1])/20; ma10 = sum(C[idx-9:idx+1])/10
            tc,tl = C[idx],L[idx]; v5 = sum(V[idx-4:idx+1])/5
            tr = trend_of(c, d)
            if tr == "下降趋势": continue
            if tc<=ma20: continue
            if V[idx]>=v5*0.85: continue
            n10,n20 = tl<=ma10*1.03 and tl>=ma10*0.94, tl<=ma20*1.03 and tl>=ma20*0.94
            if not (n10 or n20): continue
            chg = (tc-C[idx-1])/C[idx-1]*100 if idx>0 else 0
            if chg>4: continue
            vr = V[idx]/v5 if v5>0 else 1
            ml_set = set(main_lines) if main_lines else set()
            is_main = sec in ml_set; is_rising = tr=="上升趋势"
            priority = 4 if is_main and is_rising else 3 if is_main else 2 if is_rising else 1
            cs.append({"code":c,"sec":sec,"close":round(tc,2),"ma10":round(ma10,2),"ma20":round(ma20,2),
                       "vr":round(vr,2),"support":"MA10" if n10 else "MA20","chg":round(chg,2),
                       "trend":tr,"is_main":is_main,"priority":priority})
    cs.sort(key=lambda x: (-x["priority"], x["vr"]))
    return cs

class Sim:
    def __init__(self):
        self.cash = 1000000; self.pf = {}; self.trades = []
    def px(self,c,d):
        kl=KL(c); return kl[DI(d,kl)]["close"] if kl and DI(d,kl)>=0 else 0
    def low_px(self,c,d):
        kl=KL(c); return kl[DI(d,kl)]["low"] if kl and DI(d,kl)>=0 else 0
    def tv(self,d):
        return self.cash + sum(self.px(c,p.get("entry_date",""))*p["shares"] for c,p in self.pf.items())
    def tpct(self,d):
        v=self.tv(d); cs=sum(p["cost"] for p in self.pf.values()); return cs/v*100 if v>0 else 0
    def buy(self,d,c,pct,ed):
        kl=KL(c); idx=DI(d,kl)
        if idx<0: return False
        p=kl[idx]["close"]; v=self.tv(d) or self.cash; inv=v*pct
        sh=int(inv/p/100)*100
        if sh<=0: return False
        cost=sh*p
        if cost>self.cash:
            sh=int(self.cash/p/100)*100
            if sh<=0: return False
            cost=sh*p
        self.cash-=cost
        sp=ed["support"]; sp_val=ed["ma10"] if sp=="MA10" else ed["ma20"]
        sl=round(sp_val*0.97,2)
        self.pf[c]={"shares":sh,"price":p,"cost":cost,"entry_date":d,"pct":pct,
                     "sl":sl,"hwm":p,"entry_idx":idx,"left_sold":False}
        tp=self.tpct(d)
        self.trades.append({"date":d,"time":"15:00","direction":"买入","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":sh,"price":round(p,2),
            "amount":round(cost,2),"pos_pct":round(pct*100,1),"total_pct":round(tp,1),
            "reason":f"中继买点|{ed.get('trend','')}","stop_loss":sl})
        return True
    def sell_half(self,d,c,reason):
        if c not in self.pf: return
        pos=self.pf[c]; half=pos["shares"]//2
        if half<=0: return
        p=self.px(c,d)
        if p<=0: return
        proc=half*p; self.cash+=proc
        remaining=pos["shares"]-half; remaining_cost=pos["cost"]*(remaining/pos["shares"])
        pl=(p-pos["price"])*half; plpct=(p-pos["price"])/pos["price"]*100
        pos["shares"]=remaining; pos["cost"]=remaining_cost; pos["left_sold"]=True
        tp=self.tpct(d)
        self.trades.append({"date":d,"time":"15:00","direction":"卖半","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":half,"price":round(p,2),
            "amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plpct,2),
            "total_pct":round(tp,1),"pos_pct":"-","reason":f"左侧止盈减半|{reason}"})
    def sell_all(self,d,c,reason):
        if c not in self.pf: return
        pos=self.pf[c]; p=self.px(c,d)
        if p<=0: return
        proc=pos["shares"]*p; self.cash+=proc
        pl=(p-pos["price"])*pos["shares"]; plpct=(p-pos["price"])/pos["price"]*100
        del self.pf[c]; tp=self.tpct(d)
        lb="止盈" if pl>0 else "止损"
        self.trades.append({"date":d,"time":"15:00","direction":"卖出","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":pos["shares"],"price":round(p,2),
            "amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plpct,2),
            "total_pct":round(tp,1),"pos_pct":"-","reason":f"{lb}|{reason}"})
    def check(self,d):
        for c in list(self.pf.keys()):
            pos=self.pf[c]; p=self.px(c,d); l=self.low_px(c,d)
            if p<=0: continue
            kl=KL(c); idx=DI(d,kl)
            if idx<0: continue
            V=[k["volume"] for k in kl]; C=[k["close"] for k in kl]
            if p>pos["hwm"]: pos["hwm"]=p
            days_held=idx-pos["entry_idx"]
            if l>0 and l<=pos["sl"]:
                self.sell_all(d,c,f"跌破止损{pos['sl']:.2f}"); continue
            if not pos["left_sold"]:
                v_ma5=sum(V[max(0,idx-4):idx+1])/5 if idx>=4 else V[idx]
                if days_held>=2 and idx>=2 and v_ma5>0:
                    consec=0
                    for j in range(pos["entry_idx"]+1,idx+1):
                        if C[j]>C[j-1]: consec+=1; break
                    if consec>=3:
                        chgs=[(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-2,idx+1)]
                        if len(chgs)==3 and chgs[0]<chgs[1]<chgs[2] and V[idx]>v_ma5:
                            self.sell_half(d,c,f"加速|连{consec}阳"); continue
                if days_held>=2 and v_ma5>0 and V[idx]>v_ma5*1.5:
                    pc=[(C[j]-C[j-1])/C[j-1]*100 for j in range(pos["entry_idx"]+1,idx)]
                    if pc:
                        avg_pc=sum(pc)/len(pc); cc=(C[idx]-C[idx-1])/C[idx-1]*100 if idx>pos["entry_idx"] else 0
                        if avg_pc>0 and abs(cc)<avg_pc*0.5:
                            self.sell_half(d,c,f"放量滞涨|量{round(V[idx]/v_ma5,1)}x"); continue
                if days_held>=3 and idx>=3:
                    v3=[V[j] for j in range(idx-2,idx+1)]
                    if v3[0]>v3[1]>v3[2]:
                        eh=max(C[pos["entry_idx"]:idx+1])
                        if C[idx]>=eh*0.995:
                            self.sell_half(d,c,f"动力减弱|价高量缩"); continue
            ma20=sum(C[idx-19:idx+1])/20
            if p<ma20:
                pre="右侧止盈" if pos["left_sold"] else "反转"
                self.sell_all(d,c,f"{pre}|跌破MA20({ma20:.2f})"); continue

# ═══ 加载第1周状态 ═══
print("═══ v3.3 第2周 (20260413~20260417) ═══")
with open(PKL, "rb") as f:
    w1 = pickle.load(f)

sim = Sim()
sim.cash = w1["cash"]
sim.pf = w1["pf"]
sim.trades = w1["trades"]
# 从w1获取index_data或重新获取
idx_data = w1.get("index_data", get_index_data())
if not w1.get("index_data"):
    idx_data = get_index_data()

print(f"第1周结束: 现金{sim.cash:.0f} 持仓{len(sim.pf)}只 tv={w1['end']:.0f}")

# 第2周日期
week2_dates = ["20260413","20260414","20260415","20260416","20260417"]

for d in week2_dates:
    # 波峰波谷判断
    w2_score, w2_result, w2_strategy, w2_details = judge_peak_trough(idx_data, d)
    
    # 检查/止盈/止损
    before_cnt = len(sim.pf)
    sim.check(d)
    sold = before_cnt - len(sim.pf)
    
    # 波谷换股（偏波谷/波谷时卖出后补回）
    if w2_score <= -1 and (sold > 0 or sim.tpct(d) < 80.0):
        ml_d, _ = get_main_lines(d, ALL, top_n=3, min_score=15)
        new_cs = scan(d, list(sim.pf.keys()), ml_d)
        new_bought = 0
        for c in new_cs:
            code, sec = c["code"], c["sec"]
            if code in sim.pf: continue
            pct = get_position(code, d, c["is_main"], w2_score)
            cost_pct = 0
            for pc in sim.pf:
                if pc == code: cost_pct += sim.pf[pc]["cost"] / sim.tv(d)
            if cost_pct + pct > INDIVIDUAL_MAX: continue
            dir_total = 0
            for pc in sim.pf:
                if SM.get(pc,"") == sec: dir_total += sim.pf[pc]["cost"] / sim.tv(d)
            if dir_total + pct > SECTOR_MAX: continue
            if sim.buy(d, code, pct, c):
                new_bought += 1
                print(f"    🔄 换股买入 {nm(code)}({code}) {sec} {pct*100:.0f}%")
        if new_bought > 0:
            print(f"    → 换股{new_bought}只, 仓位{sim.tpct(d):.1f}%")
    
    tv = sim.tv(d)
    print(f"  {d[-5:]}: w2_score={w2_score}→{w2_result} {len(sim.pf)}只 仓位{sim.tpct(d):.1f}% tv={tv:.0f} pnl={tv-1000000:+.0f}")

end = sim.tv("20260417")
print(f"\n📊 第2周结束: 资产{end:,.0f} 累计{(end-1000000):+,.0f}({(end-1000000)/1000000*100:+.2f}%) | 仓位{sim.tpct('20260417'):.1f}%")
print(f"\n📋 交易明细:")
for t in sim.trades:
    if t["date"] >= "20260413":
        if t["direction"]=="买入":
            print(f"  {t['date'][-5:]} 买入 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | 个股{t['pos_pct']:>5}% 止损{t.get('stop_loss',0):.2f}")
        elif t["direction"]=="卖半":
            print(f"  {t['date'][-5:]} 卖半 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | ({t.get('profit_pct',0):+.2f}%) {t['reason']}")
        else:
            print(f"  {t['date'][-5:]} 卖出 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | ({t.get('profit_pct',0):+.2f}%) {t['reason']}")

pickle.dump({"cash":sim.cash,"pf":sim.pf,"trades":sim.trades,"end":end,
             "peak_trough":{"score":w2_score,"result":w2_result,"strategy":w2_strategy},
             "week_results": {"total_pnl": end-1000000, "total_pct": (end-1000000)/1000000*100,
                              "main_pct": None, "total_pos_pct": None},  # 占位，报告里算
             "index_data":idx_data},
            open(os.path.join(OUT,"w2_v33.pkl"),"wb"))
print(f"\n✅ 已保存到 {OUT}/w2_v33.pkl")

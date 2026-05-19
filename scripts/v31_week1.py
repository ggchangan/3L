#!/usr/bin/env python3
"""v3.1 - 左右结合法：左侧减半+右侧清仓+新买点继续买入"""
import json, os, pickle

DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT = "/home/ubuntu/data/3l/simulation/v3"
os.makedirs(OUT, exist_ok=True)
with open(DATA) as f:
    raw = json.load(f)
ALL = raw["stocks"]

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
    "002407":"多氟多","301358":"湖南裕能",
}
def nm(c): return CN.get(c,c)

SM = {}
for sec, stocks in ALL.items():
    for c in stocks: SM[c] = sec

KL = lambda c: next((stocks[c] for sec,stocks in ALL.items() if c in stocks), None)
DI = lambda d,kl: next((i for i,k in enumerate(kl) if k["date"]==d), -1)

ML = {"机器人","半导体","AI应用","算力"}

def jm(d):
    ms = []
    for sec,stocks in ALL.items():
        for c in stocks:
            kl = KL(c)
            if not kl: continue
            idx = DI(d,kl)
            if idx<30: continue
            vs = [k["volume"] for k in kl[idx-29:idx+1]]
            sv = sorted(vs)
            lb = sum(sv[:max(3,len(sv)//5)])/max(3,len(sv)//5)
            r = kl[idx]["volume"]/lb if lb>0 else 0
            ms.append(r)
    a = sum(ms)/len(ms) if ms else 1
    if a<1.5: p,lm="低迷期",(0.6,0.8)
    elif a<2: p,lm="正常",(0.4,0.6)
    elif a<4: p,lm="强势",(0.2,0.4)
    else: p,lm="高潮期",(0,0.2)
    return p,lm,round(a,2)

def calc_pos(c,d,ph,ex):
    kl = KL(c)
    if not kl: return 0,{}
    idx = DI(d,kl)
    if idx<20: return 0,{}
    C = [k["close"] for k in kl]
    V = [k["volume"] for k in kl]
    pm = {"低迷期":1.2,"正常":1.0,"强势":0.8,"高潮期":0.3}.get(ph,1.0)
    v5 = sum(V[idx-4:idx+1])/5
    vr = V[idx]/v5 if v5>0 else 1
    bm,bd = (1.2,"优秀缩量") if vr<0.6 else ((1.0,"标准缩量") if vr<0.85 else (0.7,"缩量不足"))
    ma20 = sum(C[idx-19:idx+1])/20
    pos = (C[idx]-ma20)/ma20
    bnm,bnd = (0.5,"鱼头(初突破)") if pos<0.03 else ((1.0,"鱼身(确认趋势)") if pos<0.15 else (0.5,"鱼尾(远离均线)"))
    sec = SM.get(c,"")
    exs = set(SM.get(x,"") for x in ex)
    if sec in exs: return 0,{}
    lm = 1.2 if sec in ML else 0.8
    raw = 0.06 * pm * bm * bnm * lm
    final = max(0.02, min(raw, 0.10))
    return final, {"pm":pm,"bm":bm,"bnm":bnm,"lm":lm,"bd":bd,"bnd":bnd,"vr":vr,"sec":sec}

def scan(d, ex):
    cs = []
    for sec,stocks in ALL.items():
        for c in stocks:
            if c in ex: continue
            kl = KL(c)
            if not kl: continue
            idx = DI(d,kl)
            if idx<20: continue
            C = [k["close"] for k in kl]
            L = [k["low"] for k in kl]
            V = [k["volume"] for k in kl]
            ma20 = sum(C[idx-19:idx+1])/20
            ma10 = sum(C[idx-9:idx+1])/10
            tc,tl = C[idx],L[idx]
            v5 = sum(V[idx-4:idx+1])/5
            if tc<=ma20: continue
            if V[idx]>=v5*0.85: continue
            n10,n20 = tl<=ma10*1.03 and tl>=ma10*0.94, tl<=ma20*1.03 and tl>=ma20*0.94
            if not (n10 or n20): continue
            chg = (tc-C[idx-1])/C[idx-1]*100 if idx>0 else 0
            if chg>4: continue
            vr = V[idx]/v5 if v5>0 else 1
            cs.append({"code":c,"sec":sec,"close":round(tc,2),"ma10":round(ma10,2),"ma20":round(ma20,2),
                       "vr":round(vr,2),"support":"MA10" if n10 else "MA20","chg":round(chg,2)})
    cs.sort(key=lambda x: x["vr"])
    return cs

class Sim:
    def __init__(self):
        self.cash = 1000000
        self.pf = {}  # {code: {shares,price,cost,entry_date,pct,sl, entry_ma10, entry_ma20, hwm, entry_day_data}}
        self.trades = []
        self.ph = ""
    
    def px(self,c,d):
        kl = KL(c)
        if not kl: return 0
        idx = DI(d,kl)
        return kl[idx]["close"] if idx>=0 else 0
    
    def low_px(self,c,d):
        kl = KL(c)
        if not kl: return 0
        idx = DI(d,kl)
        return kl[idx]["low"] if idx>=0 else 0
    
    def tv(self,d):
        return self.cash + sum(self.px(c,p.get("entry_date",""))*p["shares"] for c,p in self.pf.items())
    
    def tpct(self,d):
        v = self.tv(d)
        cs = sum(p["cost"] for p in self.pf.values())
        return cs/v*100 if v>0 else 0
    
    def buy(self,d,c,pct,det,ed):
        """买入"""
        kl = KL(c)
        if not kl: return False
        idx = DI(d,kl)
        if idx<0: return False
        p = kl[idx]["close"]
        v = self.tv(d) or self.cash
        inv = v*pct
        sh = int(inv/p/100)*100
        if sh<=0: return False
        cost = sh*p
        if cost>self.cash:
            sh = int(self.cash/p/100)*100
            if sh<=0: return False
            cost = sh*p
        self.cash -= cost
        # 止损线：买入当天回踩的支撑下方3%
        sp = ed["support"]
        sp_val = ed["ma10"] if sp=="MA10" else ed["ma20"]
        sl = round(sp_val * 0.97, 2)
        self.pf[c] = {"shares":sh,"price":p,"cost":cost,"entry_date":d,"pct":pct,
                      "sl":sl,"hwm":p,"entry_idx":idx,
                      "entry_ma10":ed["ma10"],"entry_ma20":ed["ma20"],
                      "support_sp":sp_val,"support_type":sp,
                      "left_sold":False}  # 左侧是否已卖一半
        tp = self.tpct(d)
        self.trades.append({"date":d,"time":"15:00","direction":"买入","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":sh,"price":round(p,2),
            "amount":round(cost,2),"pos_pct":round(pct*100,1),"total_pct":round(tp,1),
            "reason":"中继买点","stop_loss":sl})
        return True
    
    def sell_half(self,d,c,reason):
        """左侧止盈：卖一半"""
        if c not in self.pf: return
        pos = self.pf[c]
        half = pos["shares"] // 2
        if half <= 0: return
        p = self.px(c,d)
        if p<=0: return
        proc = half * p
        self.cash += proc
        # 更新持仓
        remaining = pos["shares"] - half
        remaining_cost = pos["cost"] * (remaining / pos["shares"])
        pl = (p-pos["price"])*half
        plpct = (p-pos["price"])/pos["price"]*100
        pos["shares"] = remaining
        pos["cost"] = remaining_cost
        pos["left_sold"] = True
        tp = self.tpct(d)
        self.trades.append({"date":d,"time":"15:00","direction":"卖半","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":half,"price":round(p,2),
            "amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plpct,2),
            "total_pct":round(tp,1),"pos_pct":"-","reason":f"左侧止盈减半|{reason}"})
    
    def sell_all(self,d,c,reason):
        """右侧止盈/止损：清仓"""
        if c not in self.pf: return
        pos = self.pf[c]
        p = self.px(c,d)
        if p<=0: return
        proc = pos["shares"]*p
        self.cash += proc
        pl = (p-pos["price"])*pos["shares"]
        plpct = (p-pos["price"])/pos["price"]*100
        del self.pf[c]
        tp = self.tpct(d)
        lb = "止盈" if pl>0 else "止损"
        self.trades.append({"date":d,"time":"15:00","direction":"卖出","code":c,
            "name":nm(c),"sector":SM.get(c,""),"qty":pos["shares"],"price":round(p,2),
            "amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plpct,2),
            "total_pct":round(tp,1),"pos_pct":"-","reason":f"{lb}|{reason}"})
    
    def check(self,d):
        """每日检查：止损→左侧止盈(卖半)→右侧止盈(清仓)"""
        for c in list(self.pf.keys()):
            pos = self.pf[c]
            p = self.px(c,d)
            l = self.low_px(c,d)
            if p<=0: continue
            kl = KL(c)
            idx = DI(d,kl)
            if idx<0: continue
            V = [k["volume"] for k in kl]
            C = [k["close"] for k in kl]
            
            # 更新最高价
            if p>pos["hwm"]: pos["hwm"]=p
            
            days_held = idx - pos["entry_idx"]
            
            # ═══ 止损 ═══
            if l>0 and l<=pos["sl"]:
                self.sell_all(d,c,f"跌破止损{pos['sl']:.2f}")
                continue
            
            # ═══ 左侧止盈（卖一半）——仅当左侧未卖过 ═══
            if not pos["left_sold"]:
                v_ma5 = sum(V[max(0,idx-4):idx+1])/5 if idx>=4 else V[idx]
                
                # ① 加速：放量大阳拉升
                if days_held>=2 and idx>=2 and v_ma5>0:
                    # 从entry_idx开始算连阳
                    consec = 0
                    for j in range(pos["entry_idx"]+1, idx+1):
                        if C[j]>C[j-1]: consec+=1
                        else: break
                    if consec>=3:
                        # 涨幅逐日扩大
                        chgs = [(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-2,idx+1)]
                        if len(chgs)==3 and chgs[0]<chgs[1]<chgs[2] and V[idx]>v_ma5:
                            self.sell_half(d,c,f"加速|连{consec}阳量{round(V[idx]/v_ma5,1)}x")
                            continue
                
                # ② 放量滞涨
                if days_held>=2 and v_ma5>0 and V[idx]>v_ma5*1.5:
                    # 前几日平均涨幅
                    prev_chgs = []
                    for j in range(pos["entry_idx"]+1, idx):
                        prev_chgs.append((C[j]-C[j-1])/C[j-1]*100)
                    if prev_chgs:
                        avg_prev = sum(prev_chgs)/len(prev_chgs)
                        curr_chg = (C[idx]-C[idx-1])/C[idx-1]*100 if idx>pos["entry_idx"] else 0
                        if avg_prev>0 and abs(curr_chg) < avg_prev*0.5:
                            self.sell_half(d,c,f"放量滞涨|量{round(V[idx]/v_ma5,1)}x涨{curr_chg:.1f}%")
                            continue
                
                # ③ 动力减弱（量价背离）
                if days_held>=3 and idx>=3:
                    # 仅使用entry_idx之后的volume数据
                    if days_held>=3:
                        entry_idx = pos["entry_idx"]
                        v_last3 = [V[j] for j in range(idx-2, idx+1)]  # 最近3日量
                        if v_last3[0]>v_last3[1]>v_last3[2]:  # 量递减
                            # 价创新高
                            entry_high = max(C[entry_idx:idx+1])
                            if C[idx] >= entry_high * 0.995:
                                self.sell_half(d,c,f"动力减弱|价高量缩{round(v_last3[2]/v_ma5,2)}x")
                                continue
            
            # ═══ 右侧止盈（清剩余）——左侧已卖过 或 直接反转 ═══
            # 条件：跌破MA20
            ma20 = sum(C[idx-19:idx+1])/20
            if p < ma20:
                # 如果左侧已卖过，这是右侧清仓
                if pos["left_sold"]:
                    self.sell_all(d,c,f"右侧止盈|跌破MA20({ma20:.2f})")
                else:
                    # 没卖过左侧直接反转的，也清仓
                    self.sell_all(d,c,f"反转|跌破MA20({ma20:.2f})")
                continue
    
    def run_week(self, week_dates, week_label):
        """跑一周"""
        mon = week_dates[0]
        # 周一先检查持仓
        self.check(mon)
        
        # 周一扫描买入
        old_tp = self.tpct(mon)
        cs = scan(mon, list(self.pf.keys()))
        ph,lim,_ = self.ph_info(mon)
        used_secs = set(SM.get(c,"") for c in self.pf.keys())
        added = 0
        for c in cs:
            code,sec = c["code"],c["sec"]
            if sec in used_secs: continue
            tp = self.tpct(mon)
            pct, det = calc_pos(code,mon,ph,list(self.pf.keys()))
            if pct>0 and tp+pct*100 <= lim[1]*100:
                self.buy(mon,code,pct,det,c)
                used_secs.add(sec)
                added += 1
        
        if added:
            print(f"  {mon[-5:]} 新增买入{added}只 | tp={self.tpct(mon):.1f}%")
        
        # 周二~周五每日检查
        for d in week_dates[1:]:
            if d == mon: continue
            self.check(d)
        
        end = self.tv(week_dates[-1])
        w_pnl = end - self.tv(self.prev_mon(week_dates[0]))
        return end, w_pnl
    
    def prev_mon(self,d):
        """上周一/建仓前基准"""
        return "20260407"
    
    def ph_info(self,d):
        return jm(d)


print("═══ v3.1 第1周 (20260407~20260410) ═══")
sim = Sim()
ph,lim,mult = jm("20260407")
sim.ph = ph
print(f"大盘: {ph} (量比{mult}x) 上限{lim[0]*100:.0f}%-{lim[1]*100:.0f}%")

# 建仓
cs = scan("20260407",[])
exs = set()
for c in cs:
    code,sec = c["code"],c["sec"]
    if sec in exs: continue
    tp = sim.tpct("20260407")
    pct, det = calc_pos(code,"20260407",ph, list(sim.pf.keys()))
    if pct>0 and tp+pct*100 <= lim[1]*100:
        sim.buy("20260407",code,pct,det,c)
        exs.add(sec)
        print(f"  {nm(code)}({code}) {sec} {pct*100:.1f}% | tp={sim.tpct('20260407'):.1f}%")

print(f"建仓{len(sim.pf)}只 | 总仓位{sim.tpct('20260407'):.1f}%")

# 每日检查
for d in ["20260408","20260409","20260410"]:
    sim.check(d)
    tv = sim.tv(d)
    print(f"  {d[-5:]}: {len(sim.pf)}只 tv={tv:.0f} pnl={tv-1000000:+.0f} 仓位{sim.tpct(d):.1f}%")

end = sim.tv("20260410")
print(f"\n📊 第1周结果:")
print(f"  期末资产: {end:,.0f}  盈亏: {end-1000000:+,.0f} ({(end-1000000)/1000000*100:+.2f}%)")
print(f"  期末持仓: {len(sim.pf)}只 仓位{sim.tpct('20260410'):.1f}%")

print(f"\n📋 交易明细:")
for t in sim.trades:
    if t["direction"]=="买入":
        print(f"  {t['date'][-5:]} 买入 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | 个股{t['pos_pct']:>5}% 总{t['total_pct']:>5}% 止损{t.get('stop_loss',0):.2f}")
    elif t["direction"]=="卖半":
        print(f"  {t['date'][-5:]} 卖半 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | {t['reason']} ({t.get('profit_pct',0):+.2f}%)")
    else:
        print(f"  {t['date'][-5:]} 卖出 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | {t['reason']} ({t.get('profit_pct',0):+.2f}%)")

print(f"\n  持仓详情:")
for c,pos in sim.pf.items():
    print(f"    {nm(c)}({c}): {pos['shares']}股 @{pos['price']} 止损{pos['sl']} 已左侧?{pos['left_sold']}")

# 保存
pickle.dump({"cash":sim.cash,"pf":sim.pf,"trades":sim.trades,"end":end}, open(os.path.join(OUT,"w1.pkl"),"wb"))
print(f"\n✅ 保存")

#!/usr/bin/env python3
"""v3.3 第4周 (20260427~20260430)"""
import json,os,pickle,urllib.request
D="/home/ubuntu/data/3l/all_stocks_60d.json"; O="/home/ubuntu/data/3l/simulation/v3"; P=os.path.join(O,"w3_v33.pkl")
with open(D) as f: r=json.load(f); A=r["stocks"]
C={"688126":"沪硅产业","688234":"天岳先进","300054":"鼎龙股份","688548":"广钢气体","688127":"蓝特光学","688347":"华虹公司","300788":"佰维存储","301308":"江波龙","001309":"德明利","300475":"香农芯创","603986":"兆易创新","688766":"普冉股份","300223":"北京君正","300042":"朗科科技","300604":"长川科技","688012":"中微公司","688072":"拓荆科技","002156":"通富微电","600584":"长电科技","002371":"北方华创","688041":"海光信息","688981":"中芯国际","688256":"寒武纪","300346":"南大光电","300236":"上海新阳","002920":"大族数控","002008":"大族激光","002640":"跨境通","002044":"美年健康","688258":"卓易信息","603859":"能科科技","688171":"税友股份","301171":"易点天下","301236":"软通动力","300339":"润和软件","600571":"信雅达","300556":"宏景科技","603716":"塞力医疗","002153":"石基信息","600588":"用友网络","300687":"赛意信息","300170":"汉得信息","300977":"杰创智能","300451":"创业慧康","002987":"京北方","688232":"新点软件","300075":"数字政通","002368":"太极股份","688246":"嘉和美康","688393":"安必平","600570":"恒生电子","300674":"宇信科技","603918":"金桥信息","601360":"三六零","300624":"万兴科技","000681":"视觉中国","300766":"每日互动","300058":"蓝色光标","300229":"拓尔思","300033":"同花顺","688590":"新致软件","002315":"焦点科技","300253":"卫宁健康","688108":"润达医疗","300010":"ST豆神","300418":"昆仑万维","002517":"恺英网络","300459":"汤姆猫","002605":"姚记科技","002230":"科大讯飞","300378":"鼎捷数智","688095":"福昕软件","688369":"致远互联","688615":"合合信息","688039":"泛微网络","688111":"金山办公","002222":"福晶科技","600330":"天通股份","002436":"兴森科技","001339":"智微智能","603389":"广合科技","600105":"永鼎股份","000338":"潍柴动力","688519":"南亚新材","002353":"杰瑞股份","300442":"润泽科技","600550":"保变电气","601179":"中国西电","301128":"强瑞技术","920099":"铜冠铜箔","300502":"新易盛","300308":"中际旭创","300620":"光库科技","688195":"腾景科技","001267":"汇绿生态","688313":"仕佳光子","688376":"英维克","002837":"英维克","300684":"中石科技","002384":"东山精密","002916":"沪电股份","603920":"世运电路","300476":"胜宏科技","600399":"应流股份","002364":"中恒电气","300870":"欧陆通","300284":"麦格米特","002281":"光迅科技","600673":"东阳光","000988":"华工科技","601869":"长飞光纤","600487":"亨通光电","600176":"中国巨石","605006":"山东玻纤","301526":"国际复材","600941":"中国移动","600050":"中国联通","601728":"中国电信","002428":"云南锗业","002361":"神剑股份","002202":"金风科技","002342":"巨力索具","002149":"西部材料","601698":"中国卫通","688010":"福光股份","600879":"航天电子","300699":"光威复材","300726":"宏达电子","001208":"华菱线缆","600118":"中国卫星","600391":"航天机电","688088":"凌云光","300503":"昊志机电","300969":"恒帅股份","002196":"方正电机","002434":"万向钱潮","603786":"科博达","603319":"均胜电子","603148":"浙江荣泰","002915":"中欣氟材","600592":"龙溪股份","002048":"宁波华翔","688084":"晶品特装","605056":"咸亨国际","688290":"景业智能","603012":"创力集团","600239":"华荣股份","601177":"杭齿前进","300718":"长盛轴承","300660":"江苏雷利","300458":"全志科技","002067":"景兴纸业","603980":"吉华集团","002607":"实益达","688322":"奥比中光","603583":"捷昌驱动","600232":"中坚科技","603237":"日盈电子","300161":"福莱新材","002527":"卧龙电驱","688160":"震裕科技","600580":"雷赛智能","300953":"中大力德","002896":"双林股份","300100":"埃夫特","688165":"拓斯达","300607":"日发精机","002520":"北纬科技","002148":"亿嘉和","002689":"豪能股份","603179":"绿的谐波","601100":"恒立液压","603667":"五洲新春","002031":"巨轮智能","300432":"富临精工","002553":"南方精工","002472":"双环传动","601689":"拓普集团","002050":"三花智控","300007":"汉威科技","002698":"博实股份","300580":"贝斯特","603728":"鸣志电器","603009":"北特科技","688218":"江苏北人","002611":"东方精工","002892":"兆威机电","603662":"柯力传感","000637":"*ST京化","301413":"安培龙","603538":"美诺华","688578":"艾力斯","002653":"海思科","688331":"荣昌生物","002393":"舒泰神","301509":"康龙化成","688131":"皓元医药","300436":"广生堂","002294":"信立泰","688266":"泽璟制药","688428":"诺诚健华","600276":"恒瑞医药","603259":"药明康德","300347":"昭衍新药","688235":"百济神州","301219":"腾远钴业","300139":"晓程科技","000831":"中稀有色","002378":"章源钨业","000657":"中钨高新","002240":"盛新锂能","000933":"神火股份","600301":"华锡有色","002160":"常铝股份","601600":"中国铝业","688353":"华盛锂电","002466":"天齐锂业","002192":"融捷股份","601168":"西部矿业","002460":"赣锋锂业","600516":"方大炭素","600111":"北方稀土","600549":"厦门钨业","603993":"洛阳钼业","601899":"紫金矿业","000737":"北方铜业","600362":"江西铜业","002709":"天赐材料","605117":"德业股份","300750":"宁德时代","300274":"阳光电源","688390":"固德威","300438":"鹏辉能源","002245":"蔚蓝锂芯","301511":"德福科技","002407":"多氟多","301358":"湖南裕能","300383":"光环新网"}
def nm(c): return C.get(c,c)
S={}
for sec,st in A.items():
    for c in st: S[c]=sec
M={"机器人","半导体","AI应用","算力"}
KL=lambda c:next((st[c] for sec,st in A.items() if c in st),None)
DI=lambda d,kl:next((i for i,k in enumerate(kl) if k["date"]==d),-1)

def gix():
    url="https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000001&scale=240&ma=no&datalen=120"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req) as r: data=json.loads(r.read().decode("utf-8"))
    return [{"date":d["day"],"open":float(d["open"]),"close":float(d["close"]),
             "high":float(d["high"]),"low":float(d["low"]),"volume":int(d["volume"])} for d in data]

def jpt(idx,ds):
    if len(ds)==8 and ds.isdigit(): ds=f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    i=next((j for j,k in enumerate(idx) if k["date"]==ds),-1)
    if i<20: return 0,"波中","",{}
    C=[k["close"] for k in idx]; H=[k["high"] for k in idx]; L=[k["low"] for k in idx]; V=[k["volume"] for k in idx]
    p=C[i]; m20=sum(C[i-19:i+1])/20
    vs=sorted(V[i-29:i+1]); lb=sum(vs[:max(3,len(vs)//5)])/max(3,len(vs)//5); vr=V[i]/lb if lb>0 else 1
    b=abs(C[i]-idx[i]["open"]); ab=sum(abs(C[j]-idx[j]["open"]) for j in range(i-4,i+1))/5; br=b/ab if ab>0 else 1
    sc=0
    pm=(p-m20)/m20*100
    if pm>3: sc+=1
    elif pm<-3: sc-=1
    if vr>3: sc+=1
    elif vr<1.3: sc-=1
    ha=False; hp=False
    if i>=3:
        cgs=[(C[j]-C[j-1])/C[j-1]*100 for j in range(i-2,i+1)]
        if len(cgs)==3 and all(cgs[j]>0 and cgs[j]>cgs[j-1] for j in range(1,3)):
            if V[i]>sum(V[i-4:i+1])/5: ha=True
    if i>=5:
        pc=[(C[j]-C[j-1])/C[j-1]*100 for j in range(i-4,i+1)]
        if sum(1 for c in pc if c<0)>=3 and V[i]>sum(V[i-4:i+1])/5*1.3:
            if abs((L[i]-C[i])/C[i])>0.01: hp=True
    if ha: sc+=1
    elif hp: sc-=1
    if br>1.2: sc+=1
    elif br<0.8: sc-=1
    r="波谷区域" if sc<=-3 else "偏波谷" if sc<=-1 else "波峰区域" if sc>=3 else "偏波峰" if sc>=1 else "波中"
    sg={"波谷区域":"重仓","偏波谷":"偏进攻","波中":"正常","偏波峰":"偏防守","波峰区域":"控仓"}.get(r,"")
    return sc,r,sg,{}

def trd(code,d):
    kl=KL(code)
    if not kl: return "下降趋势"
    i=DI(d,kl)
    if i<13: return "下降趋势"
    C=[k["close"] for k in kl]; mn=sum(C[i-9:i+1])/10; mp=sum(C[i-12:i-2])/10
    df=(mn-mp)/mp if mp>0 else 0
    return "上升趋势" if df>0.003 else "下降趋势" if df<-0.003 else "区间震荡"

def gpos(code,d,is_m,sc):
    b=0.10 if sc<=-1 else 0.05
    tr=trd(code,d)
    if tr!="上升趋势": return b
    kl=KL(code); i=DI(d,kl)
    if i<5: return b
    V=[k["volume"] for k in kl]; v5=sum(V[i-4:i+1])/5; vr=V[i]/v5 if v5>0 else 1
    return min(b*2,0.20) if is_m and tr=="上升趋势" and vr<0.7 else b
IV=0.20; ST=0.40

def scn(d,ex):
    cs=[]
    for sec,st in A.items():
        for c in st:
            if c in ex: continue
            kl=KL(c)
            if not kl: continue
            i=DI(d,kl)
            if i<20: continue
            C=[k["close"] for k in kl]; L=[k["low"] for k in kl]; V=[k["volume"] for k in kl]
            m20=sum(C[i-19:i+1])/20; m10=sum(C[i-9:i+1])/10
            tc=C[i]; tl=L[i]; v5=sum(V[i-4:i+1])/5
            tr=trd(c,d)
            if tr=="下降趋势": continue
            if tc<=m20 or V[i]>=v5*0.85: continue
            n10=tl<=m10*1.03 and tl>=m10*0.94; n20=tl<=m20*1.03 and tl>=m20*0.94
            if not (n10 or n20): continue
            chg=(tc-C[i-1])/C[i-1]*100 if i>0 else 0
            if chg>4: continue
            vr=V[i]/v5 if v5>0 else 1; is_m=sec in M; ir=tr=="上升趋势"
            pri=4 if is_m and ir else 3 if is_m else 2 if ir else 1
            cs.append({"code":c,"sec":sec,"close":round(tc,2),"ma10":round(m10,2),"ma20":round(m20,2),
                       "vr":round(vr,2),"support":"MA10" if n10 else "MA20","trend":tr,"is_main":is_m,"priority":pri})
    cs.sort(key=lambda x:(-x["priority"],x["vr"]))
    return cs

class Sim:
    def __init__(s): s.cash=1000000; s.pf={}; s.trds=[]
    def px(s,c,d):
        kl=KL(c); i=DI(d,kl); return kl[i]["close"] if kl and i>=0 else 0
    def lp(s,c,d):
        kl=KL(c); i=DI(d,kl); return kl[i]["low"] if kl and i>=0 else 0
    def tv(s,d): return s.cash+sum(s.px(c,p.get("entry_date",""))*p["shares"] for c,p in s.pf.items())
    def tp(s,d): v=s.tv(d); cs=sum(p["cost"] for p in s.pf.values()); return cs/v*100 if v>0 else 0
    def buy(s,d,c,p,ed):
        kl=KL(c); i=DI(d,kl)
        if i<0: return False
        px=kl[i]["close"]; v=s.tv(d) or s.cash; inv=v*p; sh=int(inv/px/100)*100
        if sh<=0: return False
        cost=sh*px
        if cost>s.cash: sh=int(s.cash/px/100)*100; cost=sh*px
        if sh<=0: return False
        s.cash-=cost; sv=ed["ma10"] if ed["support"]=="MA10" else ed["ma20"]; sl=round(sv*0.97,2)
        s.pf[c]={"shares":sh,"price":px,"cost":cost,"entry_date":d,"pct":p,"sl":sl,"hwm":px,"entry_idx":i,"left_sold":False}
        s.trds.append({"date":d,"time":"15:00","direction":"买入","code":c,"name":nm(c),"sector":S.get(c,""),
            "qty":sh,"price":round(px,2),"amount":round(cost,2),"pos_pct":round(p*100,1),"total_pct":round(s.tp(d),1),
            "reason":f"中继买点|{ed.get('trend','')}","stop_loss":sl})
        return True
    def sh(s,d,c,reason):
        if c not in s.pf: return
        pos=s.pf[c]; h=pos["shares"]//2
        if h<=0: return
        px=s.px(c,d)
        if px<=0: return
        proc=h*px; s.cash+=proc; rem=pos["shares"]-h; rc=pos["cost"]*(rem/pos["shares"])
        pl=(px-pos["price"])*h; plp=(px-pos["price"])/pos["price"]*100
        pos["shares"]=rem; pos["cost"]=rc; pos["left_sold"]=True
        s.trds.append({"date":d,"time":"15:00","direction":"卖半","code":c,"name":nm(c),"sector":S.get(c,""),
            "qty":h,"price":round(px,2),"amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plp,2),
            "total_pct":round(s.tp(d),1),"pos_pct":"-","reason":f"左侧止盈减半|{reason}"})
    def sa(s,d,c,reason):
        if c not in s.pf: return
        pos=s.pf[c]; px=s.px(c,d)
        if px<=0: return
        proc=pos["shares"]*px; s.cash+=proc
        pl=(px-pos["price"])*pos["shares"]; plp=(px-pos["price"])/pos["price"]*100
        del s.pf[c]; lb="止盈" if pl>0 else "止损"
        s.trds.append({"date":d,"time":"15:00","direction":"卖出","code":c,"name":nm(c),"sector":S.get(c,""),
            "qty":pos["shares"],"price":round(px,2),"amount":round(proc,2),"profit":round(pl,2),"profit_pct":round(plp,2),
            "total_pct":round(s.tp(d),1),"pos_pct":"-","reason":f"{lb}|{reason}"})
    def chk(s,d):
        for c in list(s.pf.keys()):
            pos=s.pf[c]; px=s.px(c,d); l=s.lp(c,d)
            if px<=0: continue
            kl=KL(c); i=DI(d,kl)
            if i<0: continue
            V=[k["volume"] for k in kl]; C=[k["close"] for k in kl]
            if px>pos["hwm"]: pos["hwm"]=px
            dh=i-pos["entry_idx"]
            if l>0 and l<=pos["sl"]: s.sa(d,c,f"跌破止损{pos['sl']:.2f}"); continue
            if not pos["left_sold"]:
                v5=sum(V[max(0,i-4):i+1])/5 if i>=4 else V[i]
                if dh>=2 and i>=2 and v5>0:
                    cc=0
                    for j in range(pos["entry_idx"]+1,i+1):
                        if C[j]>C[j-1]: cc+=1
                        else: break
                    if cc>=3:
                        cgs=[(C[j]-C[j-1])/C[j-1]*100 for j in range(i-2,i+1)]
                        if len(cgs)==3 and cgs[0]<cgs[1]<cgs[2] and V[i]>v5: s.sh(d,c,f"加速|连{cc}阳"); continue
                if dh>=2 and v5>0 and V[i]>v5*1.5:
                    pc=[(C[j]-C[j-1])/C[j-1]*100 for j in range(pos["entry_idx"]+1,i)]
                    if pc:
                        ap=sum(pc)/len(pc); cc=(C[i]-C[i-1])/C[i-1]*100 if i>pos["entry_idx"] else 0
                        if ap>0 and abs(cc)<ap*0.5: s.sh(d,c,f"放量滞涨|量{round(V[i]/v5,1)}x"); continue
                if dh>=3 and i>=3:
                    v3=[V[j] for j in range(i-2,i+1)]
                    if v3[0]>v3[1]>v3[2] and C[i]>=max(C[pos["entry_idx"]:i+1])*0.995: s.sh(d,c,f"动力减弱|价高量缩"); continue
            m20=sum(C[i-19:i+1])/20
            if px<m20: pre="右侧止盈" if pos["left_sold"] else "反转"; s.sa(d,c,f"{pre}|跌破MA20({m20:.2f})"); continue

print("═══ v3.3 第4周 (20260427~20260430) ═══")
with open(P,"rb") as f: pw=pickle.load(f)
s=Sim(); s.cash=pw["cash"]; s.pf=pw["pf"]; s.trds=pw["trades"]
ix=pw.get("index_data",gix())
if not pw.get("index_data"): ix=gix()
print(f"第3周结束: 现金{s.cash:.0f} 持仓{len(s.pf)}只 tv={pw['end']:.0f}")

d4=["20260427","20260428","20260429","20260430"]
for d in d4:
    sc,rn,sg,_=jpt(ix,d)
    bc=len(s.pf); s.chk(d); sold=bc-len(s.pf)
    if sc<=-1 and (sold>0 or s.tp(d)<80.0):
        ns=scn(d,list(s.pf.keys())); nb=0
        for c in ns:
            cd,se=c["code"],c["sec"]
            if cd in s.pf: continue
            p=gpos(cd,d,c["is_main"],sc)
            cp=sum(s.pf[pc]["cost"] for pc in s.pf if pc==cd)/(s.tv(d)or 1)
            if cp+p>IV: continue
            dt=sum(s.pf[pc]["cost"] for pc in s.pf if S.get(pc,"")==se)/(s.tv(d)or 1)
            if dt+p>ST: continue
            if s.buy(d,cd,p,c): nb+=1; print(f"    🔄 换股买入 {nm(cd)}({cd}) {se} {p*100:.0f}%")
        if nb>0: print(f"    → 换股{nb}只, 仓位{s.tp(d):.1f}%")
    print(f"  {d[-5:]}: sc={sc}→{rn} {len(s.pf)}只 仓位{s.tp(d):.1f}% tv={s.tv(d):.0f} pnl={s.tv(d)-1000000:+.0f}")

end=s.tv("20260430")
mc=sum(p["cost"] for c,p in s.pf.items() if S.get(c,"") in M)
nc=sum(p["cost"] for c,p in s.pf.items() if S.get(c,"") not in M)
mp=mc/end*100; tp=(mc+nc)/end*100
print(f"\n📊 第4周结束: 资产{end:,.0f} 累计{end-1000000:+,.0f}({(end-1000000)/1000000*100:+.2f}%) | 仓位{tp:.1f}% 主线{mp:.1f}%")
for t in s.trds:
    if t["date"]>="20260427":
        if t["direction"]=="买入": print(f"  {t['date'][-5:]} 买入 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | 个股{t['pos_pct']:>5}%")
        elif t["direction"]=="卖半": print(f"  {t['date'][-5:]} 卖半 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | ({t.get('profit_pct',0):+.2f}%)")
        else: print(f"  {t['date'][-5:]} 卖出 {t['name']:12} {t['sector']:8} {t['qty']:>5}股 {t['price']:>7.2f} | ({t.get('profit_pct',0):+.2f}%)")
pickle.dump({"cash":s.cash,"pf":s.pf,"trades":s.trds,"end":end,"peak_trough":{"score":sc,"result":rn},"index_data":ix,"sim4":True},open(os.path.join(O,"w4_v33.pkl"),"wb"))
print(f"\n✅")

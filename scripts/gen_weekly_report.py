#!/usr/bin/env python3
"""通用周报生成器 — 按第1周格式，不使用f-string避免嵌套问题"""
import json, os, pickle, sys, subprocess
from datetime import datetime
sys.path.insert(0, "/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts")
from judge_main_line import get_main_lines

WEEK = sys.argv[1] if len(sys.argv) > 1 else "4"
PKL = f"w{WEEK}_v33.pkl"; PREV = f"w{int(WEEK)-1}_v33.pkl" if int(WEEK)>1 else None
OUT = "/home/ubuntu/data/3l/simulation/v3"
CDIR = os.path.join(OUT, "charts"); os.makedirs(CDIR, exist_ok=True)
DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"

with open(os.path.join(OUT,PKL),"rb") as f: res = pickle.load(f)
prev = None
if PREV and os.path.exists(os.path.join(OUT,PREV)):
    with open(os.path.join(OUT,PREV),"rb") as f: prev = pickle.load(f)
with open(DATA) as f: raw = json.load(f); ALL = raw["stocks"]
KL=lambda c:next((st[c] for sec,st in ALL.items() if c in st),None)
DI=lambda d,kl:next((i for i,k in enumerate(kl) if k["date"]==d),-1)

CN = {
    "688126":"沪硅产业","688234":"天岳先进","300054":"鼎龙股份","688548":"广钢气体",
    "688127":"蓝特光学","688347":"华虹公司","300788":"佰维存储","301308":"江波龙",
    "001309":"德明利","300475":"香农芯创","603986":"兆易创新","688766":"普冉股份",
    "300223":"北京君正","300042":"朗科科技","300604":"长川科技","688012":"中微公司",
    "688072":"拓荆科技","002156":"通富微电","600584":"长电科技","002371":"北方华创",
    "688041":"海光信息","688981":"中芯国际","688256":"寒武纪","300346":"南大光电",
    "300236":"上海新阳","002920":"大族数控","002008":"大族激光",
    "002640":"跨境通","002044":"美年健康","688258":"卓易信息","603859":"能科科技",
    "688171":"税友股份","603171":"税友股份","301171":"易点天下","301236":"软通动力","300339":"润和软件",
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
SM={}
for sec,st in ALL.items():
    for c in st: SM[c]=sec

DATES={"1":"20260410","2":"20260417","3":"20260424","4":"20260430","5":"20260508","6":"20260515"}
ED=DATES.get(WEEK,f"202604{10+int(WEEK)*7}")
WEEK_LABEL="\u7b2c"+WEEK+"\u5468"

# 动态主线判定（方案B）
main_lines, ml_ranking = get_main_lines(ED, ALL)
ML=set(main_lines) if main_lines else set()
ML_LABEL=" · ".join(main_lines) if main_lines else "无主线"
# 找出非主线板块（持仓涉及的板块中不在ML的）
held_sectors=set(SM.get(c,"") for c in res["pf"])
ml_sectors=set(main_lines)
nl_sectors=held_sectors-ml_sectors
NL_LABEL=" · ".join(sorted(nl_sectors)) if nl_sectors else "—"

def idkp(code, ds, lb=40):
    kl=KL(code); idx=DI(ds,kl)
    if not kl or idx<20: return []
    st=max(0,idx-lb); p=[(k["date"],k["open"],k["close"],k["high"],k["low"],k["volume"]) for k in kl[st:idx+1]]
    C=[x[2] for x in p]; H=[x[3] for x in p]; L=[x[4] for x in p]; V=[x[5] for x in p]
    kp=[]; vm20=[sum(V[max(0,i-19):i+1])/20 for i in range(len(V))]
    vm5=[sum(V[max(0,i-4):i+1])/5 for i in range(len(V))]
    for i in range(5,len(p)):
        kl2=[]
        if i>=5 and i<=len(p)-3:
            if H[i]>max(H[i-5:i]) and H[i]>=max(H[i+1:min(i+4,len(H))]): kl2.append(("\u524d\u9ad8",round(H[i],2)))
            if L[i]<min(L[i-5:i]) and L[i]<=min(L[i+1:min(i+4,len(L))]): kl2.append(("\u524d\u4f4e",round(L[i],2)))
        if V[i]>vm20[i]*2.5 and vm20[i]>0: kl2.append(("\u5929\u91cf",round(H[i],2) if C[i]>p[i][1] else round(L[i],2)))
        if V[i]<vm20[i]*0.4 and vm20[i]>0: kl2.append(("\u5730\u91cf",round(C[i],2)))
        if i>=3:
            for j in range(i-1,max(i-15,0),-1):
                if H[j]<H[i] and V[i]>vm5[i]*1.5 and C[i]>p[i][1]: kl2.append(("\u7a81\u7834",round(H[i],2))); break
            if C[i]>p[i][1] and p[i-1][1]>C[i-1] and C[i]>p[i-1][1] and p[i][1]<C[i-1]: kl2.append(("\u53cd\u8f6c",round(C[i],2)))
            sh=min(p[i][1],C[i])-L[i]; bd=abs(C[i]-p[i][1])
            if sh>bd*2 and bd<(H[i]-L[i])*0.3 and V[i]>vm5[i]: kl2.append(("\u53cd\u8f6c",round(L[i],2)))
            su=H[i]-max(p[i][1],C[i])
            if su>bd*2 and bd<(H[i]-L[i])*0.3 and C[i]<p[i][1]: kl2.append(("\u53cd\u8f6c",round(H[i],2)))
            if V[i]<vm5[i]*0.85 and C[i]>C[i-1]: kl2.append(("\u4e2d\u7ee7",round(C[i],2)))
        for t,v in kl2: kp.append({"type":t,"price":v,"days_ago":(idx-st)-i})
    seen=set(); f=[]
    for x in reversed(kp):
        k=(x["type"],x["days_ago"])
        if k not in seen: seen.add(k); f.append(x)
    f.reverse(); return f

def gsvg(code,ds,kps,bp,bd,name,sell_trades):
    kl=KL(code); idx=DI(ds,kl)
    if not kl or idx<20: return ""
    st=max(0,idx-40); ch=kl[st:idx+1]; n=len(ch)
    mx=max(k["high"] for k in ch)*1.08; mn=min(k["low"] for k in ch)*0.92
    if mx==mn: mx+=1
    rg=mx-mn
    W,H,pl,pr,pt,pb=1000,550,70,30,36,70; cw=(W-pl-pr)/n
    px=lambda i:pl+i*cw+cw/2; py=lambda v:pt+(mx-v)/rg*(H-pt-pb)
    bv=H-pb
    # 计算EMA
    cls=[k["close"] for k in ch]
    def ema(data,p):
        r=[None]*len(data); m=2/(p+1)
        for i in range(len(data)):
            if i==0: r[i]=data[i]
            elif r[i-1] is not None: r[i]=(data[i]-r[i-1])*m+r[i-1]
        return r
    ema5=ema(cls,5); ema10=ema(cls,10); ema20=ema(cls,20)
    # 深色背景
    sv=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>',
        f'<text x="{W/2}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="bold" fill="#ffffff">{name}({code}) 关键点图</text>']
    # 价格网格
    for j in range(6):
        v=round(mx-j*rg/5,2); ly=py(v)
        sv.append(f'<line x1="{pl}" y1="{ly}" x2="{W-pr}" y2="{ly}" stroke="#2a2a4e" stroke-width="0.5"/>')
        sv.append(f'<text x="{pl-6}" y="{ly+3}" text-anchor="end" font-size="11" fill="#666666">{v}</text>')
    # 均线
    for ema_data,col in [(ema5,"#ffd700"),(ema10,"#ff6b6b"),(ema20,"#4ecdc4")]:
        pts=[]
        for i,v in enumerate(ema_data):
            if v is not None and v>0: pts.append(f"{px(i)},{py(v)}")
        if len(pts)>1: sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="1" opacity="0.7"/>')
    # K线和量能柱
    vols=[k["volume"] for k in ch]; vm=max(vols) if max(vols)>0 else 1
    for i,k in enumerate(ch):
        o,cv=k["open"],k["close"]; up=cv>=o; co="#ff4444" if up else "#44aa44"; x=pl+i*cw; w=max(cw*0.65,1)
        sv.append(f'<line x1="{px(i)}" y1="{py(k["high"])}" x2="{px(i)}" y2="{py(k["low"])}" stroke="{co}" stroke-width="1" opacity="0.8"/>')
        bt=py(max(o,cv)); bb=py(min(o,cv))
        sv.append(f'<rect x="{x}" y="{bt}" width="{w}" height="{max(bb-bt,1)}" fill="{co}" opacity="0.8"/>')
        vh=vols[i]/vm*50
        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{vh}" fill="{co}" opacity="0.35"/>')
    # 日期标签（5根/个）
    for i in range(0,n,5):
        dt=ch[i]["date"]; lb=f"{dt[4:6]}/{dt[6:8]}"
        sv.append(f'<text x="{px(i)}" y="{bv+35}" fill="#666666" font-size="10" text-anchor="middle" transform="rotate(-45,{px(i)},{bv+35})">{lb}</text>')
    sv.append(f'<text x="{px(n-1)}" y="{bv+35}" fill="#666666" font-size="10" text-anchor="middle" transform="rotate(-45,{px(n-1)},{bv+35})">{ch[-1]["date"][4:6]}/{ch[-1]["date"][6:8]}</text>')
    # 第1类关键点：橙色实心方块+文字
    cs1={"前高":"#ff9800","前低":"#ff9800","天量":"#ff9800","地量":"#ff9800"}
    ls1={"前高":"前高","前低":"前低","天量":"量","地量":"量"}
    for x in kps:
        if x["type"] not in cs1: continue
        da=x["days_ago"]
        if da>n-1 or da<0: continue
        ki=(idx-da)-st
        if ki<0 or ki>=n: continue
        xp=px(ki); yp=py(x["price"]); co=cs1[x["type"]]; lb=ls1[x["type"]]
        sz=5
        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{co}" opacity="0.85"/>')
        sv.append(f'<text x="{xp}" y="{yp-sz-3}" text-anchor="middle" font-size="10" font-weight="bold" fill="{co}">{lb}</text>')
    # 第2类关键点：蓝色实心方块+文字
    cs2={"突破":"#2196f3","反转":"#2196f3","中继":"#2196f3"}
    ls2={"突破":"突","反转":"反","中继":"中"}
    for x in kps:
        if x["type"] not in cs2: continue
        da=x["days_ago"]
        if da>n-1 or da<0: continue
        ki=(idx-da)-st
        if ki<0 or ki>=n: continue
        xp=px(ki); yp=py(x["price"]); co=cs2[x["type"]]; lb=ls2[x["type"]]
        sz=5
        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{co}" opacity="0.85"/>')
        sv.append(f'<text x="{xp}" y="{yp-sz-3}" text-anchor="middle" font-size="10" font-weight="bold" fill="{co}">{lb}</text>')
    # 买入点：虚线引到顶部
    bi=DI(bd,kl)-st
    if 0<=bi<n and bp>0:
        xb=px(bi); yb=py(bp); lab_y=pt
        sv.append(f'<line x1="{xb}" y1="{yb}" x2="{xb}" y2="{lab_y+18}" stroke="#4caf50" stroke-width="1" stroke-dasharray="4,3"/>')
        sv.append(f'<rect x="{xb-24}" y="{lab_y}" width="48" height="18" rx="4" fill="#2563eb" opacity="0.9"/>')
        sv.append(f'<text x="{xb}" y="{lab_y+13}" text-anchor="middle" font-size="11" font-weight="bold" fill="white">买入点</text>')
    # 卖半/卖出：虚线引到底部
    for st_ in sell_trades:
        sc_=st_["code"]; sd_=st_["date"]; sp_=st_["price"]; sdir_=st_["direction"]
        if sc_!=code: continue
        si_=DI(sd_,kl)
        if si_<0: continue
        sk_=si_-st
        if sk_<0 or sk_>=n: continue
        xs=px(sk_); ys=py(sp_); lab_y2=bv
        if sdir_=="卖半":
            sv.append(f'<line x1="{xs}" y1="{ys}" x2="{xs}" y2="{lab_y2-14}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>')
            sv.append(f'<rect x="{xs-20}" y="{lab_y2-18}" width="40" height="18" rx="4" fill="#f59e0b" opacity="0.9"/>')
            sv.append(f'<text x="{xs}" y="{lab_y2-5}" text-anchor="middle" font-size="11" font-weight="bold" fill="white">卖半</text>')
        elif sdir_=="卖出":
            sv.append(f'<line x1="{xs}" y1="{ys}" x2="{xs}" y2="{lab_y2-14}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,3"/>')
            sv.append(f'<rect x="{xs-20}" y="{lab_y2-18}" width="40" height="18" rx="4" fill="#ef4444" opacity="0.9"/>')
            sv.append(f'<text x="{xs}" y="{lab_y2-5}" text-anchor="middle" font-size="11" font-weight="bold" fill="white">卖出</text>')
    # 图例（6项）
    ly2=bv+10; lx=pl
    for lb,lc in [("第1类参考点","#ff9800"),("第2类供需改变","#2196f3"),("EMA5","#ffd700"),("EMA10","#ff6b6b"),("EMA20","#4ecdc4"),("买入点","#2563eb")]:
        sv.append(f'<rect x="{lx}" y="{ly2-6}" width="10" height="10" fill="{lc}" opacity="0.8" rx="1"/>')
        sv.append(f'<text x="{lx+14}" y="{ly2+3}" font-family="sans-serif" font-size="11" fill="#888888">{lb}</text>')
        lx+=130
    sv.append('</svg>'); return '\n'.join(sv)

# 数据准备
end=res["end"]; prev_end=prev["end"] if prev else 1000000
mc=sum(p["cost"] for c,p in res["pf"].items() if SM.get(c,"") in ML)
nc=sum(p["cost"] for c,p in res["pf"].items() if SM.get(c,"") not in ML)
mp=mc/end*100; tp=(mc+nc)/end*100; nmp=tp-mp
pt=res.get("peak_trough",{}); sc=pt.get("score",0); rn=pt.get("result",""); sg=pt.get("strategy","")

# Week trades
lp=prev["trades"][-1]["date"] if prev and prev["trades"] else ""
wt=[t for t in res["trades"] if t["date"]>lp] if lp else res["trades"]
bp={}
for c,pos in res["pf"].items():
    # 优先用本周买入价+日期，否则用持仓入库价+日期
    wk_buy=[t for t in wt if t["code"]==c and t["direction"]=="买入"]
    if wk_buy:
        bp[c]=wk_buy[-1]["price"]
        bp[c+"_date"]=wk_buy[-1]["date"]
    else:
        bp[c]=pos["price"]
        bp[c+"_date"]=pos.get("entry_date",ED)
# 补充当周买入当周卖出的股票（不在期末持仓中）
wc_buy_sell=set(c for t in wt if t["direction"]=="买入" for c in [t["code"]]) | set(res["pf"].keys())
# 遍历本周买入的股票，如果在bp中缺失则补充
for t in wt:
    if t["direction"]=="买入" and t["code"] not in bp:
        bp[t["code"]]=t["price"]
        bp[t["code"]+"_date"]=t["date"]
# 该周的卖出交易
sell_trades=[t for t in wt if t["direction"] in ("卖出","卖半")]
# 对本周卖出但本周未买入的股票（如上周买入本周卖出），从全量交易记录中找买入价
for st in sell_trades:
    c=st["code"]
    if c not in bp:
        for bt in res["trades"]:
            if bt["code"]==c and bt["direction"]=="买入":
                bp[c]=bt["price"]
                bp[c+"_date"]=bt["date"]
                break
wc=wc_buy_sell | set(c for st in sell_trades for c in [st["code"]])

# 从交易记录中获取股票名称（补充CN字典缺失的）
trade_names={}
for t in res["trades"]:
    if t["code"] not in trade_names and t.get("name","") and t["name"]!=t["code"]:
        trade_names[t["code"]]=t["name"]
if prev:
    for t in prev["trades"]:
        if t["code"] not in trade_names and t.get("name","") and t["name"]!=t["code"]:
            trade_names[t["code"]]=t["name"]

# ═══ 每日主线跟踪：逐日重建持仓+判定主线 ═══
sys.path.insert(0, "/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts")
from buy_point_detection import format_buy_signals
daily_ml_records = []
# 从该周交易记录 + 指数数据 获取所有交易日
daily_dates = sorted(set(t["date"] for t in wt))
# 补齐周内其他交易日：从最早交易日到ED之间
if res.get("index_data") and daily_dates:
    start = min(daily_dates)
    day_end = ED
    for d_entry in res["index_data"]:
        d_str = d_entry.get("day", "").replace("-", "")
        if not d_str or len(d_str) != 8: continue
        if start <= d_str <= day_end:
            daily_dates = sorted(set(daily_dates) | {d_str})

# 从期初状态开始逐日重建
pf_day = {}
cash_day = prev_end  # 周初现金（第1周=100万）

for day in daily_dates:
    day_trades_ = [t for t in wt if t["date"] == day and t["direction"] in ("买入","卖出","卖半")]
    day_sells = [t for t in day_trades_ if t["direction"] in ("卖出","卖半")]
    day_buys = [t for t in day_trades_ if t["direction"] == "买入"]
    # 先卖出再买入
    for t in day_sells:
        cash_day += t["amount"]
        if t["code"] in pf_day:
            if t["direction"] == "卖出":
                del pf_day[t["code"]]
            else:  # 卖半
                ex = pf_day[t["code"]]
                ratio = t["qty"] / ex["shares"]
                pf_day[t["code"]] = {"shares": ex["shares"] - t["qty"],
                                     "cost": ex["cost"] * (1 - ratio)}
                if pf_day[t["code"]]["shares"] <= 0:
                    del pf_day[t["code"]]
    for t in day_buys:
        cash_day -= t["amount"]
        ex = pf_day.get(t["code"], {"shares": 0, "cost": 0})
        pf_day[t["code"]] = {"shares": ex["shares"] + t["qty"],
                             "cost": ex["cost"] + t["amount"]}
    # 当日主线判定
    dml, drank = get_main_lines(day, ALL)
    dml_set = set(dml) if dml else set()
    ta = cash_day + sum(p["cost"] for c,p in pf_day.items())
    mc_ = sum(p["cost"] for c,p in pf_day.items() if SM.get(c,"") in dml_set)
    mp_ = mc_ / ta * 100 if ta > 0 else 0
    mains = [CN.get(c,trade_names.get(c,c)) for c in pf_day if SM.get(c,"") in dml_set]
    nonm = [CN.get(c,trade_names.get(c,c)) for c in pf_day if SM.get(c,"") not in dml_set]
    rk_lb = " · ".join(f"{s}({drank[s]['score']:.1f})" for s in dml) if dml else "无"
    all_rk = " | ".join(f"{s}{drank[s]['score']:.1f}" for s in sorted(drank,key=lambda x:-drank[x]['score'])[:8])
    # 当日买点信号
    bsig = format_buy_signals(day, ALL, dml)
    daily_ml_records.append({
        "date": day, "ml_label": rk_lb, "all_rank": all_rk,
        "mp": mp_, "check": "✅" if mp_ >= 60 else "⚠️",
        "mains": mains, "nonm": nonm,
        "mains_str": ", ".join(mains) if mains else "—",
        "nonm_str": ", ".join(nonm) if nonm else "—",
        "tupo_ml": [x["name"]+f"({x['flags']})" for x in bsig["tupo_main"][:3]],
        "tupo_ml_str": ", ".join(f"{CN.get(x['code'],trade_names.get(x['code'],x['code']))}({x['score']}/4{x['flags']})" for x in bsig["tupo_main"][:3]) if bsig["tupo_main"] else "—",
        "zj_ml_str": ", ".join(f"{CN.get(x['code'],trade_names.get(x['code'],x['code']))}({x['score']}/5{x['flags']})" for x in bsig["zhongji_main"][:3]) if bsig["zhongji_main"] else "—",
    })

print(f"{WEEK_LABEL} 生成K线图...")
# 从交易记录中获取股票名称（补充CN字典缺失的）
trade_names={}
for t in res["trades"]:
    if t["code"] not in trade_names and t.get("name","") and t["name"]!=t["code"]:
        trade_names[t["code"]]=t["name"]
if prev:
    for t in prev["trades"]:
        if t["code"] not in trade_names and t.get("name","") and t["name"]!=t["code"]:
            trade_names[t["code"]]=t["name"]
ch=""
for code in sorted(wc):
    nm=CN.get(code,code)
    if nm==code:
        nm=trade_names.get(code,code)
    # 如果名字还是code（ETF等未收录），从交易记录中取name
    if nm==code:
        for t in res["trades"]:
            if t["code"]==code and t.get("name","") and t["name"]!=code:
                nm=t["name"]; break
    kps=idkp(code,ED)
    buy=bp.get(code,0)
    bd=bp.get(code+"_date",ED)
    sv=gsvg(code,ED,kps,buy,bd,nm,sell_trades)
    if sv:
        with open(os.path.join(CDIR,f"w{WEEK}_{code}_{nm}.svg"),"w") as f: f.write(sv)
        ch+=f'<div style="margin:6px 0;border:1px solid #e5e7eb;border-radius:4px;padding:4px;">{sv}</div>\n'
        print(f"  {nm}({code})")

# 交易明细
tr=""
for t in wt:
    d=t["date"][-5:]
    if t["direction"]=="买入":
        tr+=f'<tr><td>{d}</td><td>买入</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'
        tr+=f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.2f}</td>'
        tr+=f'<td>{t["pos_pct"]}%</td><td>{t["total_pct"]}%</td>'
        tr+=f'<td class="left">中继买点|止损{t.get("stop_loss",0):.2f}</td></tr>'
    elif t["direction"]=="卖半":
        p=t.get("profit_pct",0); pc="pos" if p>=0 else "neg"
        tr+=f'<tr><td>{d}</td><td style="color:#d97706">卖半</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'
        tr+=f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.2f}</td>'
        tr+=f'<td>-</td><td>{t["total_pct"]}%</td>'
        tr+=f'<td class="left">左侧止盈|{t["reason"]} <span class="{pc}">({p:+.2f}%)</span></td></tr>'
    else:
        p=t.get("profit_pct",0); pc="pos" if p>=0 else "neg"
        lb="止盈" if p>0 else "止损"
        tr+=f'<tr><td>{d}</td><td style="color:{"#16a34a" if p>0 else "#dc2626"}">{lb}</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'
        tr+=f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.2f}</td>'
        tr+=f'<td>-</td><td>{t["total_pct"]}%</td>'
        tr+=f'<td class="left">{t["reason"]} <span class="{pc}">({p:+.2f}%)</span></td></tr>'

# 清仓
cr=""
for t in wt:
    if t["direction"] not in ("卖出","卖半"): continue
    nm=CN.get(t["code"],t["code"])
    bd2=""
    for bt in res["trades"]:
        if bt["code"]==t["code"] and bt["direction"]=="买入": bd2=bt["date"]; break
    dy="?"
    if bd2:
        try: dy=str((datetime.strptime(t["date"],"%Y%m%d")-datetime.strptime(bd2,"%Y%m%d")).days)
        except: pass
    pl=t.get("profit_pct",0); pc="pos" if pl>=0 else "neg"
    cr+=f'<tr><td class="left">{nm}</td><td>{t["sector"]}</td><td>{t["date"][-5:]}</td>'
    cr+=f'<td>{t["price"]:.2f}</td><td>{t["qty"]}</td><td>{t["amount"]:.2f}</td>'
    cr+=f'<td class="{pc}">{pl:+.2f}%</td><td class="{pc}">{t.get("profit",0):+.2f}</td>'
    cr+=f'<td>{dy}天</td><td class="left">{t["reason"]}</td></tr>'

# 持仓
hr=""
for code,pos in sorted(res["pf"].items(), key=lambda x:x[1]["cost"],reverse=True):
    nm=CN.get(code,code); sec=SM.get(code,""); ac=round(pos["cost"]/pos["shares"],2)
    cp=ac; k=KL(code)
    if k:
        i=DI(ED,k)
        if i>=0: cp=k[i]["close"]
    mk=cp*pos["shares"]; pl=mk-pos["cost"]; pp=round((cp-pos["price"])/pos["price"]*100,2); pc="pos" if pl>=0 else "neg"
    try: dy=(datetime.strptime(ED,"%Y%m%d")-datetime.strptime(pos["entry_date"],"%Y%m%d")).days
    except: dy="?"
    hr+=f'<tr><td class="left">{nm}</td><td>{sec}</td><td>{pos["shares"]}</td>'
    hr+=f'<td>{ac:.2f}</td><td>{cp:.2f}</td>'
    hr+=f'<td class="{pc}">{pl:+.2f}</td><td class="{pc}">{pp:+.2f}%</td>'
    hr+=f'<td>{dy}天</td><td>{pos["cost"]:.2f}</td><td>{pos["cost"]/end*100:.1f}%</td></tr>'

# 选股表
sr=""
for code,pos in sorted(res["pf"].items(),key=lambda x:x[1]["cost"],reverse=True):
    nm=CN.get(code,code); sec=SM.get(code,""); im=sec in ML; tag="tag-main" if im else "tag-nonmain"
    sr+=f'<tr><td class="left">{nm}</td><td>{sec}</td>'
    sr+=f'<td><span class="tag-hold">上升趋势</span></td>'
    sr+=f'<td class="pos">{pos["cost"]/end*100:.1f}%</td>'
    sr+=f'<td><span class="{tag}">{"主线" if im else "非主线"}</span></td></tr>'

# 主线非主线列表
mls=", ".join(CN.get(c,c) for c in res["pf"] if SM.get(c,"") in ML)
nls=", ".join(CN.get(c,c) for c in res["pf"] if SM.get(c,"") not in ML)
mc2=sum(1 for c in res["pf"] if SM.get(c,"") in ML)
nc2=sum(1 for c in res["pf"] if SM.get(c,"") not in ML)
wkp=end-prev_end; wkpp=wkp/prev_end*100; cump=end-1000000; cump_pct=cump/1000000*100

# ═══ 指数收益率 ═══
import urllib.request
def get_index_weekly(code, end_date, prev_end_date):
    """获取指数周收益率，传入的end_date和prev_end_date格式均为yyyymmdd"""
    url=f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale=240&ma=no&datalen=120"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data=json.loads(r.read().decode("utf-8"))
    # Sina返回的日期格式为"2026-04-10"，传入为"20260410"
    fmt_d=lambda s: f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s)==8 else s
    pe=fmt_d(prev_end_date); ee=fmt_d(end_date)
    sv=None; ev=None
    for d in data:
        if d["day"]==pe: sv=float(d["close"])
        if d["day"]==ee: ev=float(d["close"])
    if sv and ev:
        return (ev-sv)/sv*100
    return None

# 周结束日期的前一个交易日（该周起始日的收盘）
WEEK_START_MAP={
    "1":"20260403",
    "2":"20260410", "3":"20260417", "4":"20260424",
    "5":"20260508", "6":"20260515"
}
prev_ed=WEEK_START_MAP.get(WEEK,ED)
# 该周期货日期范围
from datetime import timedelta
prev_end_dt = datetime.strptime(prev_ed, "%Y%m%d")
end_dt = datetime.strptime(ED, "%Y%m%d")
week_start_dt = prev_end_dt + timedelta(days=1)
# 顺延到最近的交易日
week_trade_dates = sorted(set(t["date"] for t in wt if t["date"] > prev_ed)) if wt else []
if week_trade_dates:
    s = week_trade_dates[0]; e = week_trade_dates[-1]
    dr_full = f"{s[:4]}/{s[4:6]}/{s[6:8]} - {e[:4]}/{e[4:6]}/{e[6:8]}"
else:
    dr_full = f"{week_start_dt.year}/{week_start_dt.month:02d}/{week_start_dt.day:02d} - {end_dt.year}/{end_dt.month:02d}/{end_dt.day:02d}" 
idxs=[("sh000001","上证指数"),("sz399001","深证成指"),("sz399006","创业板指")]
idx_ret=[]
for code,iname in idxs:
    r_=get_index_weekly(code,ED,prev_ed)
    if r_ is not None:
        idx_ret.append((iname,r_))

# 跑赢/跑输判断
beat_str=""
if idx_ret:
    beats=[]
    for iname,ir in idx_ret:
        if wkpp>ir: beats.append(f"跑赢{iname}({ir:+.2f}%)")
        elif wkpp<ir: beats.append(f"跑输{iname}({ir:+.2f}%)")
        else: beats.append(f"持平{iname}")
    beat_str=",".join(beats)

# ═══ HTML ═══
html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head><meta charset="UTF-8">\n<style>\n'
html += '*{margin:0;padding:0;box-sizing:border-box}\n'
html += 'body{font-family:\'Noto Sans CJK SC\',\'WenQuanYi Zen Hei\',sans-serif;font-size:11px;color:#1a1a1a;padding:20px;line-height:1.7}\n'
html += '.report-header{text-align:center;margin-bottom:14px}\n'
html += '.report-title{font-size:20px;font-weight:bold;color:#2563eb}\n'
html += '.report-divider{border:none;border-top:2px solid #2563eb;opacity:0.4;margin:6px 0}\n'
html += '.part{margin-top:18px}\n'
html += '.part-header{font-size:15px;font-weight:bold;color:#1e40af;background:#eff6ff;padding:5px 10px;border-radius:4px;margin-bottom:8px;border-left:4px solid #2563eb}\n'
html += '.part-number{display:inline-block;background:#2563eb;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;margin-right:6px}\n'
html += 'table{width:100%;border-collapse:collapse;font-size:11px;margin:6px 0}\n'
html += 'th{background:#f3f4f6;padding:4px 5px;text-align:center;font-weight:bold;border-bottom:1.5px solid #d1d5db;white-space:nowrap}\n'
html += 'td{padding:3px 5px;border-bottom:1px solid #f0f0f0;text-align:center;white-space:nowrap}\n'
html += 'tr:last-child td{border-bottom:2px solid #d1d5db}\n'
html += 'td.left,th.left{text-align:left}\n'
html += '.pos{color:#16a34a;font-weight:bold}\n.neg{color:#dc2626;font-weight:bold}\n'
html += '.kpi-group{margin:6px 0}\n'
html += '.kpi-row{display:inline-block;margin:3px 12px 3px 0;background:#f9fafb;padding:4px 10px;border-radius:4px}\n'
html += '.kpi-label{font-size:10px;color:#888}\n.kpi-value{font-size:16px;font-weight:bold}\n'
html += '.highlight-box{background:#f0fdf4;border:1px solid #86efac}\n'
html += '.detail-box{background:#fafafa;border:1px solid #e5e7eb;border-radius:4px;padding:8px 12px;margin:6px 0;font-size:11px}\n'
html += '.tag-main{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#dbeafe;color:#1e40af}\n'
html += '.tag-nonmain{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#f3f4f6;color:#666}\n'
html += '.tag-hold{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#e0e7ff;color:#3730a3}\n'
html += '</style></head>\n<body>\n\n'

html += '<div class="report-header"><div class="report-title">v3.3 '+WEEK_LABEL+'交易报告</div>'
html += '<div class="report-subtitle">'+dr_full+' | 波谷换股+主线>60% | 上证指数波峰波谷</div><hr class="report-divider"></div>\n\n'

# Part 0
scc='#fef2f2' if sc<0 else '#f0fdf4'
scc2='#dc2626' if sc<0 else '#16a34a'
rcc='#dc2626' if rn in ('波谷区域','偏波谷') else '#1e40af'
html += '<div class="part">\n<div class="part-header"><span class="part-number">0</span> 大盘波峰波谷判断</div>\n'
html += '<div class="kpi-group">\n'
html += '<span class="kpi-row" style="background:'+scc+'"><span class="kpi-label">综合评分</span><br><span class="kpi-value" style="color:'+scc2+'">'+str(sc)+'分</span></span>\n'
html += '<span class="kpi-row"><span class="kpi-label">判断结果</span><br><span class="kpi-value" style="color:'+rcc+'">'+rn+'</span></span>\n'
html += '<span class="kpi-row highlight-box"><span class="kpi-label">仓位策略</span><br><span class="kpi-value" style="font-size:14px">'+sg+'</span></span>\n'
html += '</div>\n'
html += '<div class="detail-box"><b>数据源：</b>上证指数（sh000001）通过新浪API获取。<br>\n'
html += '<b>综合评分法v1：</b>4维度评分。-4~+4。≤-3=波谷区域重仓80-100%，≥+3=波峰区域控仓。<br>\n'
html += '<b>期末判断：</b>评分'+str(sc)+'→'+rn+'。</div>\n</div>\n\n'

# Part 1
html += '<div class="part">\n<div class="part-header"><span class="part-number">1</span> 大盘判强弱</div>\n'
html += '<div class="kpi-group">\n'
html += '<span class="kpi-row"><span class="kpi-label">大盘阶段</span><br><span class="kpi-value">低迷期</span></span>\n'
html += '<span class="kpi-row"><span class="kpi-label">期末仓位</span><br><span class="kpi-value">'+f'{tp:.1f}'+'%</span></span>\n'
html += '</div>\n'
html += '<div class="detail-box">大盘判强弱用于选择买点类型，不用于算仓位系数。<br>'
html += '仓位由波峰波谷决定（当前'+rn+'）。<br>'
mp_check="✅" if mp>=60 else "⚠️ 未达标"
html += '主线占比<b>'+f'{mp:.1f}'+'%</b> '+mp_check+' 超过60%规则。</div>\n</div>\n\n'

# Part 2 — 每日主线跟踪（含买点信号）
html += '<div class="part">\n<div class="part-header"><span class="part-number">2</span> 主线/非主线判定（逐日跟踪）</div>\n'
html += '<div class="detail-box"><b>方案B</b>：20日涨幅×0.6 + MA20覆盖率×0.4，每日收盘重算，评分≥15且取Top3。<br>'
html += '<b>仓位系数</b>：主线×1.2，非主线×0.8。<br>'
html += '<b>买点</b>：🟢突=突破买点(放量突破前高) 🔵中=中继买点(缩量回踩)</div>\n'
html += '<table><tr><th>日期</th><th>主线板块(评分)</th>'
html += '<th>主仓位</th><th>非仓位</th><th>达标</th>'
html += '<th>突破买点(主线)</th><th>中继买点(主线)</th></tr>\n'
for dr in daily_ml_records:
    chk_cls = "pos" if dr["check"] == "✅" else "neg"
    html += '<tr>'
    html += f'<td>{dr["date"][-5:]}</td>'
    html += f'<td class="left" style="font-size:10px">{dr["ml_label"]}</td>'
    html += f'<td class="pos">{dr["mp"]:.1f}%</td>'
    html += f'<td>{100-dr["mp"]:.1f}%</td>'
    html += f'<td class="{chk_cls}">{dr["check"]}</td>'
    html += f'<td class="left" style="font-size:10px">{dr["tupo_ml_str"]}</td>'
    html += f'<td class="left" style="font-size:10px">{dr["zj_ml_str"]}</td>'
    html += '</tr>\n'
html += '</table>\n</div>\n\n'

# Part 3
html += '<div class="part">\n<div class="part-header"><span class="part-number">3</span> 选股过程与仓位计算</div>\n'
html += '<div class="detail-box">'
html += '<b>选股条件：</b>非下降趋势(MA10斜率) + 收MA20上方 + 缩量<MA5×0.85 + 回踩MA10/MA20支撑 + 涨幅<4%<br>'
html += '<b>个股仓位：</b>偏波谷建仓10%/只，特别看好翻倍20%。个股上限20%，板块上限40%。<br>'
html += '<b>波谷换股：</b>卖出后当天扫描新买点补回，维持仓位80%+。<br>'
html += '<b>主线要求：</b>主线仓位>总仓位60%。</div>\n'
html += '<table><tr><th class="left">股票</th><th>方向</th><th>走势</th><th>仓位</th><th>类别</th></tr>\n'+sr+'</table>\n</div>\n\n'

# Part 4
html += '<div class="part">\n<div class="part-header"><span class="part-number">4</span> 交易明细</div>\n'
html += '<table><tr><th>日期</th><th>操作</th><th class="left">名称</th><th>方向</th><th>数量</th><th>单价</th><th>金额</th><th>个股%</th><th>总仓位</th><th class="left">理由</th></tr>\n'+tr+'</table>\n</div>\n\n'

# Part 5
html += '<div class="part">\n<div class="part-header"><span class="part-number">5</span> 个股关键点分析</div>\n'
html += '<div style="font-size:11px;color:#666;margin-bottom:8px">暗色背景K线图 橙色=第1类(前高/前低/天量/地量) 蓝色=第2类(突破/反转/中继) 金线=EMA5 红线=EMA10 青线=EMA20 标签=买卖点</div>\n'
html += ch+'\n</div>\n\n'

# Part 6
wkc='#16a34a' if wkp>=0 else '#dc2626'
cmc='#16a34a' if cump>=0 else '#dc2626'
html += '<div class="part">\n<div class="part-header"><span class="part-number">6</span> 本周表现</div>\n'
html += '<div class="kpi-group">\n'
html += '<span class="kpi-row"><span class="kpi-label">期初资产</span><br><span class="kpi-value">'+f'{prev_end:,.2f}'+'</span></span>\n'

# 指数对比表
html += '<h3 style="font-size:12px;color:#333;margin:8px 0 4px">指数对比</h3>\n'
html += '<table><tr><th>指标</th><th>本周收益率</th><th>vs组合差</th><th>比较</th></tr>\n'
html += '<tr><td class="left"><b>组合</b></td><td class="pos"><b>'+f'{wkpp:+.2f}'+'%</b></td><td>—</td><td>—</td></tr>\n'
for iname,ir in idx_ret:
    ic='pos' if ir>=0 else 'neg'
    diff=wkpp-ir
    dc='pos' if diff>=0 else 'neg'
    beat_icon=''
    beat_cls=''
    if wkpp>ir: beat_icon='\u25b2'; beat_cls='pos'
    elif wkpp<ir: beat_icon='\u25bc'; beat_cls='neg'
    else: beat_icon='\u25a0'; beat_cls=''
    html += '<tr><td class="left">'+iname+'</td><td class="'+ic+'">'+f'{ir:+.2f}'+'%</td>'
    html += '<td class="'+dc+'">'+f'{diff:+.2f}'+'%</td>'
    html += '<td class="'+beat_cls+'">'+beat_icon+' '+('跑赢' if wkpp>ir else '跑输' if wkpp<ir else '持平')+'</td></tr>\n'
html += '</table>\n'
html += '<div class="detail-box" style="margin-top:6px">'+beat_str+'</div>\n'
html += '</div>\n\n'

# Part 7
html += '<div class="part">\n<div class="part-header"><span class="part-number">7</span> 期末持仓 ('+ED[-5:]+')</div>\n'
html += '<table><tr><th class="left">名称</th><th>方向</th><th>持股</th><th>均价</th><th>现价</th><th>盈亏</th><th>盈亏%</th><th>持天</th><th>成本</th><th>仓位</th></tr>\n'+hr+'</table>\n'
html += '<div class="detail-box">总资产：'+f'{end:,.2f}'+' | 现金：'+f'{res["cash"]:,.2f}'+' | 市值：'+f'{end-res["cash"]:,.2f}'+' | 仓位：'+f'{tp:.1f}%<br>'
html += '主线'+f'{mp:.1f}%'+' \u2705 | 非主线'+f'{nmp:.1f}%'+'</div>\n'
html += '</div>\n\n'

# Part 8
html += '<div class="part">\n<div class="part-header"><span class="part-number">8</span> 清仓记录</div>\n'
html += '<table><tr><th class="left">名称</th><th>方向</th><th>清仓日</th><th>卖出价</th><th>数量</th><th>金额</th><th>盈亏%</th><th>盈亏</th><th>持天</th><th class="left">理由</th></tr>\n'+cr+'</table>\n'
html += '</div>\n\n'

# Footer
html += '<div style="text-align:center;font-size:10px;color:#999;margin-top:20px">v3.3 '+WEEK_LABEL+' | 累计'+f'{cump_pct:+.2f}%'+'</div>\n'
html += '</body>\n</html>'

# 保存
html_path = os.path.join(OUT, f"\u7b2c{WEEK}\u5468_v33.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"\u2705 HTML\u5df2\u751f\u6210")

# PDF
pdf_path = os.path.join(OUT, f"\u7b2c{WEEK}\u5468_v33.pdf")
try:
    from weasyprint import HTML as WHTML
    WHTML(string=html).write_pdf(pdf_path)
    print(f"\u2705 PDF\u5df2\u751f\u6210 ({os.path.getsize(pdf_path)//1024}KB)")
except Exception as e:
    print(f"weasyprint\u5931\u8d25: {e}")
    # \u5907\u7528: wkhtmltopdf
    with open(html_path, "r") as f:
        subprocess.run(["wkhtmltopdf", "--encoding", "utf-8", "--page-size", "A4", html_path, pdf_path], check=True)
        print(f"\u2705 PDF via wkhtmltopdf ({os.path.getsize(pdf_path)//1024}KB)")


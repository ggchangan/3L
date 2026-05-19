#!/usr/bin/env python3
"""生成个股K线关键点SVG图表"""
import json, os

DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT = "/home/ubuntu/data/3l/simulation/v3"
os.makedirs(os.path.join(OUT, "charts"), exist_ok=True)

with open(DATA) as f:
    raw = json.load(f)
ALL = raw["stocks"]

KL = lambda c: next((stocks[c] for sec,stocks in ALL.items() if c in stocks), None)
DI = lambda d,kl: next((i for i,k in enumerate(kl) if k["date"]==d), -1)

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
NM = lambda c: CN.get(c,c)

def identify_keypoints(code, date_str, lookback=40):
    kl = KL(code)
    if not kl: return []
    idx = DI(date_str, kl)
    if idx < 20: return []
    start = max(0, idx - lookback)
    prices = [(k["date"], k["open"], k["close"], k["high"], k["low"], k["volume"]) for k in kl[start:idx+1]]
    C = [p[2] for p in prices]; H = [p[3] for p in prices]
    L = [p[4] for p in prices]; V = [p[5] for p in prices]
    keypoints = []
    vol_ma20 = [sum(V[max(0,i-19):i+1])/20 for i in range(len(V))]
    vol_ma5 = [sum(V[max(0,i-4):i+1])/5 for i in range(len(V))]
    for i in range(5, len(prices)):
        kp_list = []
        if i >= 5 and i <= len(prices)-3:
            lh = max(H[i-5:i]); rh = max(H[i+1:min(i+4,len(H))])
            if H[i] > lh and H[i] >= rh:
                kp_list.append(("前高", round(H[i],2)))
            ll = min(L[i-5:i]); rl = min(L[i+1:min(i+4,len(L))])
            if L[i] < ll and L[i] <= rl:
                kp_list.append(("前低", round(L[i],2)))
        if V[i] > vol_ma20[i]*2.5 and vol_ma20[i]>0:
            is_up = C[i] > prices[i][1]
            kp_list.append(("天量", round(H[i],2) if is_up else round(L[i],2)))
        if V[i] < vol_ma20[i]*0.4 and vol_ma20[i]>0:
            kp_list.append(("地量", round(C[i],2)))
        if i >= 3:
            for j in range(i-1, max(i-15,0), -1):
                if H[j] < H[i] and V[i] > vol_ma5[i]*1.5 and C[i] > prices[i][1]:
                    kp_list.append(("突破", round(H[i],2)))
                    break
            if C[i] > prices[i][1] and prices[i-1][1] > C[i-1]:
                if C[i] > prices[i-1][1] and prices[i][1] < C[i-1]:
                    kp_list.append(("反转", round(C[i],2)))
            shadow = min(prices[i][1],C[i]) - L[i]
            body = abs(C[i]-prices[i][1])
            if shadow > body*2 and body < (H[i]-L[i])*0.3 and V[i] > vol_ma5[i]:
                kp_list.append(("反转", round(L[i],2)))
            shadow_u = H[i] - max(prices[i][1],C[i])
            if shadow_u > body*2 and body < (H[i]-L[i])*0.3 and C[i] < prices[i][1]:
                kp_list.append(("反转", round(H[i],2)))
            if V[i] < vol_ma5[i]*0.85 and C[i] > C[i-1]:
                kp_list.append(("中继", round(C[i],2)))
        for kp_type, price in kp_list:
            days = i - (idx - start)
            keypoints.append({"type":kp_type, "price":price, "days_ago":days})
    # 去重同类型最近
    seen=set(); filtered=[]
    for kp in reversed(keypoints):
        k=(kp["type"], kp["days_ago"])
        if k not in seen: seen.add(k); filtered.append(kp)
    filtered.reverse()
    return filtered

def gen_svg(code, date_str, kps, buy_price, buy_date, name):
    kl = KL(code)
    if not kl: return ""
    idx = DI(date_str, kl)
    if idx < 20: return ""
    start = max(0, idx-24)
    chunk = kl[start:idx+1]
    n = len(chunk)
    
    highs = [k["high"] for k in chunk]
    lows = [k["low"] for k in chunk]
    max_p = max(highs) * 1.08
    min_p = min(lows) * 0.92
    rng = max_p - min_p
    
    W, H = 660, 260
    padL, padR, padT, padB = 50, 20, 20, 30
    cw = (W - padL - padR) / n
    
    def px(i): return padL + i * cw + cw/2
    def py(v): return padT + (max_p - v) / rng * (H - padT - padB)
    
    parts = [f'<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>',
             f'<text x="{W/2}" y="14" text-anchor="middle" font-family="Noto Sans CJK SC,sans-serif" font-size="12" font-weight="bold" fill="#2563eb">{name}({code}) 关键点</text>']
    
    vols = [k["volume"] for k in chunk]
    vol_max = max(vols)
    for i, k in enumerate(chunk):
        o,c_val = k["open"],k["close"]
        is_up = c_val >= o
        color = "#16a34a" if is_up else "#dc2626"
        x = padL + i * cw
        w = cw * 0.7
        parts.append(f'<line x1="{px(i)}" y1="{py(k["high"])}" x2="{px(i)}" y2="{py(k["low"])}" stroke="{color}" stroke-width="1"/>')
        body_t = py(max(o,c_val)); body_b = py(min(o,c_val))
        parts.append(f'<rect x="{x}" y="{body_t}" width="{w}" height="{max(body_b-body_t,1)}" fill="{color}" opacity="0.85"/>')
        
        # 成交量柱
        vh = vols[i] / vol_max * 25
        parts.append(f'<rect x="{x}" y="{H-padB+5}" width="{w}" height="{vh}" fill="{color}" opacity="0.3"/>')
    
    # 刻度
    step = round(rng / 5, 2)
    for j in range(6):
        v = round(max_p - j*step, 2)
        ly = py(v)
        parts.append(f'<line x1="{padL-5}" y1="{ly}" x2="{padL}" y2="{ly}" stroke="#eee" stroke-width="0.5"/>')
        parts.append(f'<text x="{padL-8}" y="{ly+3}" text-anchor="end" font-size="8" fill="#999">{v}</text>')
    
    # 关键点
    colors = {"前高":"#e67e22","前低":"#e67e22","天量":"#e67e22","地量":"#e67e22",
              "突破":"#3498db","反转":"#3498db","中继":"#3498db"}
    labels = {"前高":"前高","前低":"前低","天量":"量","地量":"量","突破":"突","反转":"反","中继":"中"}
    for kp in kps:
        da = kp["days_ago"]
        if da > n-1 or da < 0: continue
        ki = (idx - da) - start
        if ki < 0 or ki >= n: continue
        xp = px(ki); yp = py(kp["price"])
        col = colors.get(kp["type"],"#666")
        lb = labels.get(kp["type"],kp["type"])
        parts.append(f'<circle cx="{xp}" cy="{yp}" r="4" fill="{col}" stroke="white" stroke-width="1.5"/>')
        parts.append(f'<text x="{xp}" y="{yp-8}" text-anchor="middle" font-size="7" font-weight="bold" fill="{col}">{lb}</text>')
    
    # 买入点
    bi = DI(buy_date, kl) - start
    if 0 <= bi < n:
        xb = px(bi); yb = py(buy_price)
        parts.append(f'<rect x="{xb-22}" y="{yb-20}" width="44" height="16" rx="3" fill="#2563eb" opacity="0.9"/>')
        parts.append(f'<text x="{xb}" y="{yb-9}" text-anchor="middle" font-size="9" font-weight="bold" fill="white">买入点</text>')
        parts.append(f'<line x1="{xb}" y1="{yb-2}" x2="{xb}" y2="{yb+25}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="4,3"/>')
    
    # 图例
    ly2 = H - 2
    items = [
        ("第1类(前高/前低/天量/地量)","#e67e22"),
        ("第2类(突破/反转/中继)","#3498db"),
        ("买入点","#2563eb")
    ]
    lx = padL
    for lb, lc in items:
        parts.append(f'<circle cx="{lx+5}" cy="{ly2-2}" r="3" fill="{lc}"/>')
        parts.append(f'<text x="{lx+12}" y="{ly2}" font-family="Noto Sans CJK SC,sans-serif" font-size="7" fill="#888">{lb}</text>')
        lx += 145
    parts.append('</svg>')
    return '\n'.join(parts)

stocks = [
    ("300503","昊志机电","机器人",52.31,"20260407"),
    ("300054","鼎龙股份","半导体",49.50,"20260407"),
    ("301128","强瑞技术","算力",147.19,"20260407"),
    ("688131","皓元医药","创新药",70.40,"20260407"),
    ("002192","融捷股份","资源股",71.28,"20260407"),
    ("603716","塞力医疗","AI应用",23.34,"20260407"),
    ("688010","福光股份","商业航天",30.05,"20260407"),
]
cdir = os.path.join(OUT,"charts")
for code,name,sector,bp,bd in stocks:
    kps = identify_keypoints(code,"20260407")
    svg = gen_svg(code,"20260407",kps,bp,bd,name)
    if svg:
        with open(os.path.join(cdir,f"{code}_{name}.svg"),"w") as f:
            f.write(svg)
        print(f"  {name}({code})")
print(f"\n✅ 图表已保存到 {cdir}/")

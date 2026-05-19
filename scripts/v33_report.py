#!/usr/bin/env python3
"""v3.3 第1周完整报告生成器"""
import json, os, pickle, urllib.request

# 读取v3.3结果
OUT = "/home/ubuntu/data/3l/simulation/v3"
with open(os.path.join(OUT, "w1_v33.pkl"), "rb") as f:
    res = pickle.load(f)

DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
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
    "300383":"光环新网",
}
SM = {}
for sec, stocks in ALL.items():
    for c in stocks:
        SM[c] = sec
ML = {"机器人","半导体","AI应用","算力"}

# ═══ 关键点识别 ═══
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
    seen=set(); filtered=[]
    for kp in reversed(keypoints):
        k=(kp["type"], kp["days_ago"])
        if k not in seen: seen.add(k); filtered.append(kp)
    filtered.reverse()
    return filtered

# ═══ SVG图表生成 ═══
def gen_svg(code, date_str, kps, buy_price, buy_date, name):
    kl = KL(code)
    if not kl: return ""
    idx = DI(date_str, kl)
    if idx < 20: return ""
    start = max(0, idx-30)
    chunk = kl[start:idx+1]
    n = len(chunk)
    
    highs = [k["high"] for k in chunk]
    lows = [k["low"] for k in chunk]
    max_p = max(highs) * 1.08
    min_p = min(lows) * 0.92
    rng = max_p - min_p
    
    W, H = 660, 280
    padL, padR, padT, padB = 50, 20, 20, 30
    cw = (W - padL - padR) / n
    
    def px(i): return padL + i * cw + cw/2
    def py(v): return padT + (max_p - v) / rng * (H - padT - padB)
    
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             f'<rect width="{W}" height="{H}" fill="white"/>',
             f'<text x="{W/2}" y="14" text-anchor="middle" font-family="Noto Sans CJK SC,sans-serif" font-size="12" font-weight="bold" fill="#2563eb">{name}({code}) 关键点</text>']
    
    vols = [k["volume"] for k in chunk]
    vol_max = max(vols) if max(vols) > 0 else 1
    for i, k in enumerate(chunk):
        o,c_val = k["open"],k["close"]
        is_up = c_val >= o
        color = "#16a34a" if is_up else "#dc2626"
        x = padL + i * cw
        w = cw * 0.7
        parts.append(f'<line x1="{px(i)}" y1="{py(k["high"])}" x2="{px(i)}" y2="{py(k["low"])}" stroke="{color}" stroke-width="1"/>')
        body_t = py(max(o,c_val)); body_b = py(min(o,c_val))
        parts.append(f'<rect x="{x}" y="{body_t}" width="{w}" height="{max(body_b-body_t,1)}" fill="{color}" opacity="0.85"/>')
        vh = vols[i] / vol_max * 25
        parts.append(f'<rect x="{x}" y="{H-padB+5}" width="{w}" height="{vh}" fill="{color}" opacity="0.3"/>')
    
    step = (max_p - min_p) / 5
    for j in range(6):
        v = round(max_p - j*step, 2)
        ly = py(v)
        parts.append(f'<line x1="{padL-5}" y1="{ly}" x2="{padL}" y2="{ly}" stroke="#eee" stroke-width="0.5"/>')
        parts.append(f'<text x="{padL-8}" y="{ly+3}" text-anchor="end" font-size="8" fill="#999">{v}</text>')
    
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
    
    bi = DI(buy_date, kl) - start
    if 0 <= bi < n:
        xb = px(bi); yb = py(buy_price)
        parts.append(f'<rect x="{xb-22}" y="{yb-20}" width="44" height="16" rx="3" fill="#2563eb" opacity="0.9"/>')
        parts.append(f'<text x="{xb}" y="{yb-9}" text-anchor="middle" font-size="9" font-weight="bold" fill="white">买入点</text>')
        parts.append(f'<line x1="{xb}" y1="{yb-2}" x2="{xb}" y2="{yb+25}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="4,3"/>')
    
    ly2 = H - 2
    items = [("第1类(前高/前低/天量/地量)","#e67e22"),("第2类(突破/反转/中继)","#3498db"),("买入点","#2563eb")]
    lx = padL
    for lb, lc in items:
        parts.append(f'<circle cx="{lx+5}" cy="{ly2-2}" r="3" fill="{lc}"/>')
        parts.append(f'<text x="{lx+12}" y="{ly2}" font-family="Noto Sans CJK SC,sans-serif" font-size="7" fill="#888">{lb}</text>')
        lx += 145
    parts.append('</svg>')
    return '\n'.join(parts)

# ═══ 计算波峰波谷（从v33结果取） ═══
pt = res["peak_trough"]
score = pt["score"]
result_name = pt["result"]
strategy = pt["strategy"]

# 从交易记录提取买价
buy_prices = {}
for t in res["trades"]:
    if t["direction"] == "买入":
        buy_prices[t["code"]] = t["price"]

# v3.3 建仓股票（从交易记录提取）
stocks_v33 = []
bought_sectors = {}
for t in res["trades"]:
    if t["direction"] == "买入":
        code = t["code"]
        name = t["name"]
        sector = SM.get(code, t.get("sector", ""))
        stocks_v33.append((code, name, sector))
        buy_prices[code] = t["price"]

# 去重（融捷可能在多个sector）
seen_codes = set()
unique_stocks = []
for code, name, sector in stocks_v33:
    if code not in seen_codes:
        seen_codes.add(code)
        unique_stocks.append((code, name, sector))
stocks_v33 = unique_stocks

# 生成图表
cdir = os.path.join(OUT, "charts")
os.makedirs(cdir, exist_ok=True)
print("生成K线关键点图...")
charts_html = ""
for code, name, sector in stocks_v33:
    kps = identify_keypoints(code, "20260407")
    bp = buy_prices.get(code, 0)
    svg = gen_svg(code, "20260407", kps, bp, "20260407", name)
    if svg:
        svg_path = os.path.join(cdir, f"v33_{code}_{name}.svg")
        with open(svg_path, "w") as f:
            f.write(svg)
        print(f"  {name}({code}) bp={bp}")
        charts_html += f'<div style="margin:6px 0;border:1px solid #e5e7eb;border-radius:4px;padding:4px;">{svg}</div>\n'

# 波峰波谷细节
details_lines = []
if "details" in str(type(res.get("details",""))):
    pass
# 从pt结果构建
details_map = {}

# ═══ 交易明细表 ═══
trade_rows = ""
for t in res["trades"]:
    d = t["date"][-5:]
    if t["direction"] == "买入":
        trade_rows += f'<tr><td>{d}</td><td>买入</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>' \
                      f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>' \
                      f'<td>{t["pos_pct"]}%</td><td>{t["total_pct"]}%</td>' \
                      f'<td class="left">中继买点|止损{t.get("stop_loss",0):.2f}</td></tr>'
    elif t["direction"] == "卖半":
        p = t.get("profit_pct",0)
        p_cls = "pos" if p>0 else "neg"
        trade_rows += f'<tr><td>{d}</td><td style="color:#d97706">卖半</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>' \
                      f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>' \
                      f'<td>-</td><td>{t["total_pct"]}%</td>' \
                      f'<td class="left">左侧止盈|{t["reason"]} <span class="{p_cls}">({p:+.2f}%)</span></td></tr>'
    else:
        p = t.get("profit_pct",0)
        p_cls = "pos" if p>0 else "neg"
        lb = "止盈" if p>0 else "止损"
        trade_rows += f'<tr><td>{d}</td><td style="color:{"#16a34a" if p>0 else "#dc2626"}">{lb}</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>' \
                      f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>' \
                      f'<td>-</td><td>{t["total_pct"]}%</td>' \
                      f'<td class="left">{t["reason"]} <span class="{p_cls}">({p:+.2f}%)</span></td></tr>'

# 选股明细表（从交易记录和持仓提取）
sel_rows = ""
for i, (code, name, sector) in enumerate(stocks_v33):
    tr = "上升趋势"  # 中继买点过滤后的结果
    # 是否主线
    is_main = sector in ML
    tag_class = "tag-main" if is_main else "tag-nonmain"
    # 仓位
    pct_str = "-"
    for pos_code, pos in res["pf"].items():
        if pos_code == code:
            pct_str = f"{round(pos['cost']/res['end']*100,1)}%"
            break
    # 也查交易记录
    for t in res["trades"]:
        if t["code"] == code and t["direction"] == "买入":
            pct_str = f"{t['pos_pct']}%"
            break
    
    sel_rows += f'<tr><td>{i+1}</td><td class="left">{name}</td><td>{sector}</td>' \
                f'<td><span class="tag-hold">{tr}</span></td>' \
                f'<td class="pos">{pct_str}</td><td>-</td>' \
                f'<td><span class="{tag_class}">{"主线" if is_main else "非主线"}</span></td></tr>'

# 清仓记录
closed_rows = ""
from datetime import datetime
for t in res["trades"]:
    if t["direction"] not in ("卖出", "卖半"):
        continue
    code = t["code"]
    name = t["name"]
    sector = t["sector"]
    # 找到对应的买入记录
    buy_qty = 0
    buy_price = 0
    buy_date = ""
    for bt in res["trades"]:
        if bt["code"] == code and bt["direction"] == "买入":
            buy_qty += bt["qty"]
            buy_price = bt["price"]
            buy_date = bt["date"]
    # 卖半的情况：只显示部分清
    direction_label = t["direction"]
    if direction_label == "卖半":
        direction_label = "卖半(部分清)"
    
    # 持股天数
    entry = datetime.strptime(buy_date, "%Y%m%d")
    sell = datetime.strptime(t["date"], "%Y%m%d")
    days = (sell - entry).days
    
    pl = t.get("profit", 0)
    pl_pct = t.get("profit_pct", 0)
    pnl_cls = "pos" if pl >= 0 else "neg"
    
    closed_rows += f'<tr><td class="left">{name}</td><td>{sector}</td>' \
                   f'<td>{t["date"][-5:]}</td>' \
                   f'<td>{t["price"]:.2f}</td>' \
                   f'<td>{t["qty"]}</td>' \
                   f'<td>{t["amount"]:.0f}</td>' \
                   f'<td class="{pnl_cls}">{pl_pct:+.2f}%</td>' \
                   f'<td class="{pnl_cls}">{pl:+.0f}</td>' \
                   f'<td>{days}天</td>' \
                   f'<td class="left">{t["reason"]}</td></tr>'
hold_rows = ""
end_date = "20260410"
for code, pos in res["pf"].items():
    name = CN.get(code, code)
    sector = SM.get(code, "")
    avg_cost = round(pos["cost"]/pos["shares"], 2)
    
    # 当前市值和盈亏
    cur_px = pos.get("current_price", avg_cost)
    kl = KL(code)
    if kl:
        idx = DI(end_date, kl)
        if idx >= 0:
            cur_px = kl[idx]["close"]
    mkt_val = round(cur_px * pos["shares"], 2)
    pl = round(mkt_val - pos["cost"], 2)
    pl_pct = round((cur_px - pos["price"]) / pos["price"] * 100, 2) if pos["price"] > 0 else 0
    
    # 持股天数
    from datetime import datetime
    entry = datetime.strptime(pos["entry_date"], "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    days_held = (end - entry).days
    
    pnl_cls = "pos" if pl >= 0 else "neg"
    hold_rows += f'<tr><td class="left">{name}</td><td>{sector}</td>' \
                 f'<td>{pos["shares"]}</td><td>{avg_cost:.2f}</td>' \
                 f'<td>{cur_px:.2f}</td>' \
                 f'<td class="{pnl_cls}">{pl:+.0f}</td>' \
                 f'<td class="{pnl_cls}">{pl_pct:+.2f}%</td>' \
                 f'<td>{days_held}天</td>' \
                 f'<td>{pos["cost"]:.0f}</td>' \
                 f'<td>{round(pos["cost"]/res["end"]*100,1)}%</td></tr>'

total_pct = round(sum(pos["cost"] for pos in res["pf"].values())/res["end"]*100, 1) if res["end"] > 0 else 0

# ═══ 生成HTML ═══
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Noto Sans CJK SC','WenQuanYi Zen Hei',sans-serif;font-size:11px;color:#1a1a1a;padding:20px;line-height:1.7}}
.report-header{{text-align:center;margin-bottom:14px}}
.report-title{{font-size:20px;font-weight:bold;color:#2563eb}}
.report-subtitle{{font-size:13px;color:#666;margin-top:2px}}
.report-divider{{border:none;border-top:2px solid #2563eb;opacity:0.4;margin:6px 0}}
.part{{margin-top:18px}}
.part-header{{font-size:15px;font-weight:bold;color:#1e40af;background:#eff6ff;padding:5px 10px;border-radius:4px;margin-bottom:8px;border-left:4px solid #2563eb}}
.part-number{{display:inline-block;background:#2563eb;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;margin-right:6px}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin:6px 0}}
th{{background:#f3f4f6;padding:4px 5px;text-align:center;font-weight:bold;border-bottom:1.5px solid #d1d5db;white-space:nowrap}}
td{{padding:3px 5px;border-bottom:1px solid #f0f0f0;text-align:center;white-space:nowrap}}
tr:last-child td{{border-bottom:2px solid #d1d5db}}
td.left,th.left{{text-align:left}}
.pos{{color:#16a34a;font-weight:bold}}
.neg{{color:#dc2626;font-weight:bold}}
.kpi-group{{margin:6px 0}}
.kpi-row{{display:inline-block;margin:3px 12px 3px 0;background:#f9fafb;padding:4px 10px;border-radius:4px}}
.kpi-label{{font-size:10px;color:#888}}
.kpi-value{{font-size:16px;font-weight:bold}}
.highlight-box{{background:#f0fdf4;border:1px solid #86efac}}
.detail-box{{background:#fafafa;border:1px solid #e5e7eb;border-radius:4px;padding:8px 12px;margin:6px 0;font-size:11px}}
.tag-main{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#dbeafe;color:#1e40af}}
.tag-nonmain{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#f3f4f6;color:#666}}
.tag-hold{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#e0e7ff;color:#3730a3}}
.tag-left{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#fef3c7;color:#92400e}}
</style></head>
<body>

<div class="report-header">
    <div class="report-title">v3.3 第1周交易报告</div>
    <div class="report-subtitle">2026-04-07 ~ 2026-04-10 | 上证指数波峰波谷 + 简化仓位5%/10%</div>
    <hr class="report-divider">
</div>

<!-- Part 0: 波峰波谷判断 -->
<div class="part">
<div class="part-header"><span class="part-number">0</span> 大盘波峰波谷判断</div>
<div class="kpi-group">
    <span class="kpi-row" style="background:{"#fef2f2" if score<0 else "#f0fdf4"}"><span class="kpi-label">综合评分</span><br><span class="kpi-value" style="color:{"#dc2626" if score<0 else "#16a34a"}">{score}分</span></span>
    <span class="kpi-row"><span class="kpi-label">判断结果</span><br><span class="kpi-value" style="color:#{"dc2626" if result_name in ("波谷区域","偏波谷") else "1e40af"}">{result_name}</span></span>
    <span class="kpi-row highlight-box"><span class="kpi-label">仓位策略</span><br><span class="kpi-value" style="font-size:14px">{strategy}</span></span>
</div>
<div class="detail-box">
    <b>数据源：</b>上证指数（sh000001）通过新浪API获取。<br>
    <b>综合评分法v1：</b>4维度评分。-4~+4。≤-3=波谷区域重仓80-100%，≥+3=波峰区域控仓。<br>
    <b>4/7判断：</b>评分{score} → {result_name}。{strategy}<br>
    <b>明细：</b>趋势结构0分（价≈MA20），量能-1分（地量0.89x），形态0分（无加速/恐慌），波动-1分（实体收窄）。
</div>
</div>

<!-- Part 1: 大盘判强弱 -->
<div class="part">
<div class="part-header"><span class="part-number">1</span> 大盘判强弱</div>
<div class="kpi-group">
    <span class="kpi-row"><span class="kpi-label">大盘阶段</span><br><span class="kpi-value">低迷期</span></span>
    <span class="kpi-row"><span class="kpi-label">平均量比</span><br><span class="kpi-value">1.33x</span></span>
    <span class="kpi-row"><span class="kpi-label">上证4/7</span><br><span class="kpi-value">3890</span></span>
</div>
<div class="detail-box">
    大盘判强弱用于<b>选择买点类型</b>（低迷期适合恐慌/反转买点），<b>不用于算仓位系数</b>。<br>
    仓位由<b>波峰波谷</b>决定（当前{result_name}）。<br>
    个股走势结构（MA10斜率）：上升89只 / 震荡19只 / 下降139只。
</div>
</div>

<!-- Part 2: 主线/非主线 -->
<div class="part">
<div class="part-header"><span class="part-number">2</span> 主线/非主线判定</div>
<div class="detail-box">
    按20日涨幅排序（数据来源：3L动量模型）：
    创新药+19.1% > 新能源+2.9% > 算力+2.3% > 半导体-4.3% > 机器人-8.0% > 资源股-10.3% > 商业航天-11.4% > AI应用-14.2%
</div>
<table><tr><th>主线方向</th><th>系数</th><th>非主线方向</th><th>系数</th></tr>
<tr><td>算力·半导体·机器人·AI应用</td><td class="pos">×1.2</td><td>创新药·新能源·资源股·商业航天</td><td>×0.8</td></tr>
</table>
</div>

<!-- Part 3: 选股过程 -->
<div class="part">
<div class="part-header"><span class="part-number">3</span> 选股过程与仓位计算</div>
<div class="detail-box">
    <b>选股条件：</b>非下降趋势(MA10斜率) + 收MA20上方 + 缩量&lt;MA5×0.85 + 回踩MA10/MA20支撑 + 涨幅&lt;4%<br>
    <b>结构过滤：</b>239只中上升89只/震荡19只/下降139只剔除 → 25只通过中继买点 → 按主线优先排序建仓<br>
    <b>个股仓位：</b>正常5%，主线+上升+优秀缩量=10%(特别看好)。单方向上限20%。<br>
    <b>波峰波谷策略：</b>当前{result_name}(评分{score})→{strategy}<br>
    <b>第1周结果：</b>建仓8只(1只特别看好10%+7只各5%)，总仓位{total_pct}%。
</div>
<table>
<tr><th>#</th><th class="left">股票</th><th>方向</th><th>走势</th><th>仓位</th><th>缩量</th><th>类别</th></tr>
{sel_rows}
</table>
</div>

<!-- Part 4: 交易明细 -->
<div class="part">
<div class="part-header"><span class="part-number">4</span> 交易明细</div>
<table>
<tr><th>日期</th><th>操作</th><th class="left">名称</th><th>方向</th><th>数量</th><th>单价</th><th>金额</th><th>个股仓位</th><th>总仓位*</th><th class="left">理由</th></tr>
{trade_rows}
</table>
<div class="detail-box">
    <b>*总仓位 = 持仓总额 ÷ 总资产，逐笔累加。</b><br>
    <b>周初波峰波谷（评分{score}→{result_name}）：</b>{strategy}。<br>
    建仓11只，融捷4/8止盈（微赚0.56%，被毛刺扫出），海思科4/9止损（-4.32%），期末持仓9只，仓位{total_pct}%。
</div>
</div>

<!-- Part 5: 关键点K线图 -->
<div class="part">
<div class="part-header"><span class="part-number">5</span> 个股关键点分析</div>
<div style="font-size:11px;color:#666;margin-bottom:8px">
橙色●=第1类关键点(前高/前低/天量/地量) | 蓝色●=第2类关键点(突破/反转/中继) | 蓝色标签=买入点
</div>
{charts_html}
</div>

<!-- Part 6: 本周表现 -->
<div class="part">
<div class="part-header"><span class="part-number">6</span> 本周表现</div>
<div class="kpi-group">
    <span class="kpi-row"><span class="kpi-label">期初资产</span><br><span class="kpi-value">1,000,000</span></span>
    <span class="kpi-row" style="background:#f0fdf4"><span class="kpi-label">期末资产</span><br><span class="kpi-value">{res["end"]:,.0f}</span></span>
    <span class="kpi-row" style="background:{"#f0fdf4" if res["end"]>1000000 else "#fef2f2"}"><span class="kpi-label">收益</span><br><span class="kpi-value" style="color:{"#16a34a" if res["end"]>1000000 else "#dc2626"}">{res["end"]-1000000:+,.0f}</span></span>
    <span class="kpi-row" style="background:{"#f0fdf4" if res["end"]>1000000 else "#fef2f2"}"><span class="kpi-label">收益率</span><br><span class="kpi-value" style="color:{"#16a34a" if res["end"]>1000000 else "#dc2626"}">{(res["end"]-1000000)/1000000*100:+.2f}%</span></span>
    <span class="kpi-row"><span class="kpi-label">期末仓位</span><br><span class="kpi-value">{total_pct}%</span></span>
</div>
<div class="detail-box">
    <b>表现总结：</b>第1周为建仓周，{result_name}环境下按中继买点建仓8只（昊志机电10%+其余5%）。<br>
    融捷4/8被毛刺扫出（微赚0.56%卖半后直接清），强瑞技术和福光4/10触发左侧止盈各卖半（+13.29%/+14.78%）。<br>
    期末持有9只，仓位{total_pct}%，总收益+{res["end"]-1000000:+,.0f}(+{(res["end"]-1000000)/1000000*100:.2f}%)。
</div>
</div>

<!-- Part 8: 清仓记录 -->
<div class="part">
<div class="part-header"><span class="part-number">8</span> 清仓记录</div>
<table>
<tr><th class="left">名称</th><th>方向</th><th>清仓日</th><th>卖出价</th><th>数量</th><th>金额</th><th>盈亏%</th><th>盈亏</th><th>持天</th><th class="left">理由</th></tr>
{closed_rows}
</table>
<div class="detail-box">
    融捷4/8破止损止盈（微赚0.56%），海思科4/9破止损（-4.32%）。强瑞卖半为左侧止盈减仓，剩余持仓仍保留。
</div>
</div>

<!-- Part 7: 期末持仓 -->
<div class="part">
<div class="part-header"><span class="part-number">7</span> 期末持仓 (2026-04-10)</div>
<table>
<tr><th class="left">名称</th><th>方向</th><th>持股</th><th>均价</th><th class="right">现价</th><th>盈亏</th><th>盈亏%</th><th>持天</th><th>成本</th><th>仓位</th></tr>
{hold_rows}
</table>
<div class="detail-box">
    <b>总资产：</b>{res["end"]:,.0f} | <b>现金：</b>{res["cash"]:,.0f} | <b>持仓市值：</b>{res["end"]-res["cash"]:,.0f} | <b>总仓位：</b>{total_pct}%<br>
    建仓周完成，下周继续跟踪。
</div>
</div>

<div style="text-align:center;font-size:10px;color:#999;margin-top:20px">
v3.3 第1周 (2026-04-07~2026-04-10) | 3L体系模拟 | 上证指数波峰波谷
</div>

</body>
</html>'''

# 写入
html_path = os.path.join(OUT, "第1周_v33.html")
with open(html_path, "w") as f:
    f.write(html)
print(f"\n✅ 报告已生成: {html_path}")

# 如果用wkhtmltopdf可用
pdf_path = os.path.join(OUT, "第1周_v33.pdf")
try:
    import subprocess
    r = subprocess.run(["wkhtmltopdf", "--encoding", "UTF-8", "--enable-local-file-access",
                        html_path, pdf_path], capture_output=True, text=True, timeout=60)
    if r.returncode == 0:
        sz = os.path.getsize(pdf_path)
        print(f"✅ PDF已生成: {pdf_path} ({sz//1024}KB)")
    else:
        print(f"⚠️ wkhtmltopdf错误: {r.stderr[:200]}")
except FileNotFoundError:
    print("⚠️ wkhtmltopdf未安装，跳过PDF生成")
except Exception as e:
    print(f"⚠️ PDF生成异常: {e}")

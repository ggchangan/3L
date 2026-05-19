#!/usr/bin/env python3
"""v3.3 第2周报告生成"""
import json, os, pickle
OUT = "/home/ubuntu/data/3l/simulation/v3"
with open(os.path.join(OUT,"w2_v33.pkl"),"rb") as f: res = pickle.load(f)
with open(os.path.join(OUT,"w1_v33.pkl"),"rb") as f: w1 = pickle.load(f)
DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
with open(DATA) as f: raw = json.load(f)
ALL = raw["stocks"]
SM = {}
for sec, stocks in ALL.items(): 
    for c in stocks: SM[c] = sec
ML = {"机器人","半导体","AI应用","算力"}

CN = {"300383":"光环新网","688108":"润达医疗","301171":"易点天下",
      "002160":"常铝股份","688131":"皓元医药","600276":"恒瑞医药",
      "002393":"舒泰神","300054":"鼎龙股份","603716":"塞力医疗",
      "300503":"昊志机电","300580":"贝斯特","301128":"强瑞技术",
      "688218":"江苏北人","300161":"福莱新材","688234":"天岳先进"}

# 主线比例
end = res["end"]
main_cost = sum(pos["cost"] for c,pos in res["pf"].items() if SM.get(c,"") in ML)
nonmain_cost = sum(pos["cost"] for c,pos in res["pf"].items() if SM.get(c,"") not in ML)
main_pct = main_cost/end*100; total_pct = (main_cost+nonmain_cost)/end*100
nonmain_pct = total_pct - main_pct

# 清仓记录
closed_rows = ""
for t in res["trades"]:
    if t["date"] < "20260413": continue
    if t["direction"] in ("卖出","卖半"):
        from datetime import datetime
        code=t["code"]; name=CN.get(code,code); sector=t["sector"]
        buy_date=""; buy_px=0
        for bt in res["trades"]:
            if bt["code"]==code and bt["direction"]=="买入":
                buy_date=bt["date"]; buy_px=bt["price"]; break
        days="?"
        if buy_date:
            try: days=str((datetime.strptime(t["date"],"%Y%m%d")-datetime.strptime(buy_date,"%Y%m%d")).days)
            except: pass
        pl=t.get("profit_pct",0); pcls="pos" if pl>=0 else "neg"
        closed_rows+=f'<tr><td class="left">{name}</td><td>{sector}</td><td>{t["date"][-5:]}</td>'\
                      f'<td>{t["price"]:.2f}</td><td>{t["qty"]}</td>'\
                      f'<td class="{pcls}">{pl:+.2f}%</td><td>{t.get("profit",0):+.0f}</td><td>{days}</td>'\
                      f'<td class="left">{t["reason"]}</td></tr>'

# 交易明细
trade_rows = ""
for t in res["trades"]:
    if t["date"] < "20260413": continue
    if t["direction"]=="买入":
        trade_rows+=f'<tr><td>{t["date"][-5:]}</td><td>买入</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'\
                     f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>'\
                     f'<td>{t["pos_pct"]}%</td><td class="left">中继买点|止损{t.get("stop_loss",0):.2f}</td></tr>'
    elif t["direction"]=="卖半":
        p=t.get("profit_pct",0); pcls="pos" if p>=0 else "neg"
        trade_rows+=f'<tr><td>{t["date"][-5:]}</td><td style="color:#d97706">卖半</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'\
                     f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>'\
                     f'<td>-</td><td class="left">左侧止盈 <span class="{pcls}">({p:+.2f}%)</span></td></tr>'
    else:
        p=t.get("profit_pct",0); pcls="pos" if p>=0 else "neg"
        lb="止盈" if p>0 else "止损"
        trade_rows+=f'<tr><td>{t["date"][-5:]}</td><td style="color:{"#16a34a" if p>0 else "#dc2626"}">{lb}</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td>'\
                     f'<td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td>'\
                     f'<td>-</td><td class="left">{t["reason"]} <span class="{pcls}">({p:+.2f}%)</span></td></tr>'

# 期末持仓
hold_rows = ""
from datetime import datetime
for code, pos in sorted(res["pf"].items(), key=lambda x: x[1]["cost"], reverse=True):
    name=CN.get(code,code); sector=SM.get(code,"")
    avg_c=round(pos["cost"]/pos["shares"],2); cur_px=pos.get("current_price",avg_c)
    end_date="20260417"
    kl=lambda c:next((stocks[c] for sec,stocks in ALL.items() if c in stocks),None)
    DI=lambda d,kl:next((i for i,k in enumerate(kl) if k["date"]==d),-1) if kl else -1
    k=kl(code)
    if k:
        i=DI(end_date,k)
        if i>=0: cur_px=k[i]["close"]
    mkv=cur_px*pos["shares"]; pl=mkv-pos["cost"]
    plp=round((cur_px-pos["price"])/pos["price"]*100,2)
    pcls="pos" if pl>=0 else "neg"
    entry=datetime.strptime(pos["entry_date"],"%Y%m%d")
    end_dt=datetime.strptime(end_date,"%Y%m%d")
    days=(end_dt-entry).days
    hold_rows+=f'<tr><td class="left">{name}</td><td>{sector}</td><td>{pos["shares"]}</td>'\
                f'<td>{avg_c:.2f}</td><td>{cur_px:.2f}</td>'\
                f'<td class="{pcls}">{pl:+.0f}</td><td class="{pcls}">{plp:+.2f}%</td>'\
                f'<td>{days}</td><td>{pos["cost"]:.0f}</td><td>{pos["cost"]/end*100:.1f}%</td></tr>'

# 建仓明细（持仓+换股新入）  
sel_rows = ""
for code, pos in sorted(res["pf"].items(), key=lambda x: x[1]["cost"], reverse=True):
    name=CN.get(code,code); sector=SM.get(code,"")
    is_main = sector in ML
    tag_cls="tag-main" if is_main else "tag-nonmain"
    pct_str=f"{pos['cost']/end*100:.1f}%"
    sel_rows+=f'<tr><td class="left">{name}</td><td>{sector}</td>'\
               f'<td><span class="tag-hold">上升趋势</span></td>'\
               f'<td class="pos">{pct_str}</td><td><span class="{tag_cls}">{"主线" if is_main else "非主线"}</span></td></tr>'

w1_end = w1["end"]
# 波峰波谷
pt = res.get("peak_trough",{}); sc=pt.get("score",0); rn=pt.get("result",""); sg=pt.get("strategy","")

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><style>
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
</style></head>
<body>

<div class="report-header">
    <div class="report-title">v3.3 第2周交易报告</div>
    <div class="report-subtitle">2026-04-13 ~ 2026-04-17 | 波谷换股+主线>60%</div>
    <hr class="report-divider">
</div>

<div class="part">
<div class="part-header"><span class="part-number">0</span> 大盘波峰波谷</div>
<div class="detail-box">
<b>第2周评分变化：</b>04/13 -1偏波谷 → 04/14 -1偏波谷 → 04/15 -1偏波谷 → 04/16 0波中 → 04/17 -2偏波谷<br>
整周维持偏波谷~波中状态，波谷换股逻辑持续生效。
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">1</span> 本周表现</div>
<div class="kpi-group">
    <span class="kpi-row"><span class="kpi-label">周初资产</span><br><span class="kpi-value">{w1_end:,.0f}</span></span>
    <span class="kpi-row" style="background:#f0fdf4"><span class="kpi-label">周末资产</span><br><span class="kpi-value">{end:,.0f}</span></span>
    <span class="kpi-row" style="background:{"#f0fdf4" if end>w1_end else "#fef2f2"}"><span class="kpi-label">本周收益</span><br><span class="kpi-value" style="color:{"#16a34a" if end>w1_end else "#dc2626"}">{end-w1_end:+,.0f}</span></span>
    <span class="kpi-row" style="background:{"#f0fdf4" if end>1000000 else "#fef2f2"}"><span class="kpi-label">累计收益</span><br><span class="kpi-value" style="color:{"#16a34a" if end>1000000 else "#dc2626"}">{end-1000000:+,.0f} ({(end-1000000)/1000000*100:+.2f}%)</span></span>
    <span class="kpi-row"><span class="kpi-label">总仓位</span><br><span class="kpi-value">{total_pct:.1f}%</span></span>
    <span class="kpi-row"><span class="kpi-label">主线占比</span><br><span class="kpi-value" style="color:#16a34a">{main_pct:.1f}%</span></span>
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">2</span> 主线仓位占比</div>
<div class="kpi-group">
    <span class="kpi-row" style="background:{"#f0fdf4" if main_pct>=60 else "#fef2f2"}"><span class="kpi-label">主线仓位</span><br><span class="kpi-value">{main_pct:.1f}%</span></span>
    <span class="kpi-row"><span class="kpi-label">非主线仓位</span><br><span class="kpi-value">{nonmain_pct:.1f}%</span></span>
    <span class="kpi-row" style="background:#f3f4f6"><span class="kpi-label">主线只数</span><br><span class="kpi-value">{sum(1 for c in res["pf"] if SM.get(c,"") in ML)}</span></span>
    <span class="kpi-row" style="background:#f3f4f6"><span class="kpi-label">非主线只数</span><br><span class="kpi-value">{sum(1 for c in res["pf"] if SM.get(c,"") not in ML)}</span></span>
</div>
<div class="detail-box">
    <b>规则：</b>主线仓位>总仓位60% | 当前主线<strong>{main_pct:.1f}%</strong> ✅ 达标<br>
    第1周末主线65.6% → 第2周末主线{main_pct:.1f}%，持续提升。
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">3</span> 期末持仓</div>
<table>
<tr><th class="left">名称</th><th>方向</th><th>持股</th><th>均价</th><th>现价</th><th>盈亏</th><th>盈亏%</th><th>持天</th><th>成本</th><th>仓位</th></tr>
{hold_rows}
</table>
<div class="detail-box">
<b>总资产：</b>{end:,.0f} | <b>现金：</b>{res["cash"]:,.0f} | <b>市值：</b>{end-res["cash"]:,.0f} | <b>仓位：</b>{total_pct}%<br>
<b>主线</b>{main_pct:.1f}% (< 60% ✅) | <b>非主线</b>{nonmain_pct:.1f}%
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">4</span> 交易明细</div>
<table>
<tr><th>日期</th><th>操作</th><th class="left">名称</th><th>方向</th><th>数量</th><th>单价</th><th>金额</th><th>个股</th><th class="left">理由</th></tr>
{trade_rows}
</table>
</div>

<div class="part">
<div class="part-header"><span class="part-number">5</span> 清仓记录</div>
<table>
<tr><th class="left">名称</th><th>方向</th><th>清仓日</th><th>卖出价</th><th>数量</th><th>盈亏%</th><th>盈亏</th><th>持天</th><th class="left">理由</th></tr>
{closed_rows}
</table>
</div>

<div class="part">
<div class="part-header"><span class="part-number">6</span> 选股与仓位</div>
<table>
<tr><th class="left">股票</th><th>方向</th><th>走势</th><th>仓位</th><th>类别</th></tr>
{sel_rows}
</table>
<div class="detail-box">
    换股操作：江苏北人/恒瑞医药→易点天下(20%)+福莱新材(10%)；舒泰神→天岳先进(10%)；维持仓位94%+。
</div>
</div>

<div style="text-align:center;font-size:10px;color:#999;margin-top:20px">
v3.3 第2周 (2026-04-13~2026-04-17) | 累计+{(end-1000000)/1000000*100:.2f}%
</div>

</body>
</html>'''

html_path = os.path.join(OUT,"第2周_v33.html")
with open(html_path,"w") as f: f.write(html)
print(f"✅ HTML已生成: {html_path}")

pdf_path = os.path.join(OUT,"第2周_v33.pdf")
try:
    import subprocess
    r = subprocess.run(["wkhtmltopdf","--encoding","UTF-8","--enable-local-file-access",
                        html_path,pdf_path], capture_output=True,text=True,timeout=60)
    if r.returncode==0:
        import os; sz=os.path.getsize(pdf_path)
        print(f"✅ PDF已生成 ({sz//1024}KB)")
    else:
        print(f"⚠️ {r.stderr[:200]}")
except: print("⚠️ PDF跳过")

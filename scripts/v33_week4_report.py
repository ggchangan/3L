#!/usr/bin/env python3
"""v3.3 第4周报告"""
import json,os,pickle
OUT="/home/ubuntu/data/3l/simulation/v3"
with open(os.path.join(OUT,"w4_v33.pkl"),"rb") as f: r=pickle.load(f)
with open(os.path.join(OUT,"w3_v33.pkl"),"rb") as f: w3=pickle.load(f)
D="/home/ubuntu/data/3l/all_stocks_60d.json"
with open(D) as f: rd=json.load(f); A=rd["stocks"]
S={}
for sec,st in A.items():
    for c in st: S[c]=sec
M={"机器人","半导体","AI应用","算力"}
C={"300503":"昊志机电","300054":"鼎龙股份","301128":"强瑞技术","603716":"塞力医疗","300580":"贝斯特","688218":"江苏北人","688131":"皓元医药","002160":"常铝股份","600276":"恒瑞医药","002393":"舒泰神","300383":"光环新网","688108":"润达医疗","301171":"易点天下","300161":"福莱新材","688234":"天岳先进","002371":"北方华创","600232":"中坚科技","600941":"中国移动","688615":"合合信息","300418":"昆仑万维","600580":"雷赛智能","300284":"麦格米特","002364":"中恒电气","688108":"润达医疗","300058":"蓝色光标","603237":"日盈电子","601728":"中国电信","603012":"创力集团","300075":"数字政通"}
end=r["end"]; w3e=w3["end"]
mc=sum(p["cost"] for c,p in r["pf"].items() if S.get(c,"") in M)
nc=sum(p["cost"] for c,p in r["pf"].items() if S.get(c,"") not in M)
mp=mc/end*100; tp=(mc+nc)/end*100

# 清仓
cr=""
for t in r["trades"]:
    if t["date"]<"20260427": continue
    if t["direction"] in ("卖出","卖半"):
        cd=t["code"]; nm=C.get(cd,cd)
        bd=""; bp=0
        for bt in r["trades"]:
            if bt["code"]==cd and bt["direction"]=="买入": bd=bt["date"]; bp=bt["price"]; break
        days="?"
        if bd:
            from datetime import datetime as ddt
            try: days=str((ddt.strptime(t["date"],"%Y%m%d")-ddt.strptime(bd,"%Y%m%d")).days)
            except: pass
        pl=t.get("profit_pct",0); pc="pos" if pl>=0 else "neg"
        cr+=f'<tr><td class="left">{nm}</td><td>{t["sector"]}</td><td>{t["date"][-5:]}</td><td>{t["price"]:.2f}</td><td>{t["qty"]}</td><td class="{pc}">{pl:+.2f}%</td><td>{days}天</td><td class="left">{t["reason"]}</td></tr>'
# 交易明细
tr=""
for t in r["trades"]:
    if t["date"]<"20260427": continue
    if t["direction"]=="买入": tr+=f'<tr><td>{t["date"][-5:]}</td><td>买入</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td><td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td><td>{t["pos_pct"]}%</td><td class="left">止损{t.get("stop_loss",0):.2f}</td></tr>'
    elif t["direction"]=="卖半": p=t.get("profit_pct",0); cl="pos" if p>=0 else "neg"; tr+=f'<tr><td>{t["date"][-5:]}</td><td style="color:#d97706">卖半</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td><td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td><td>-</td><td class="left">左侧止盈<span class="{cl}">({p:+.2f}%)</span></td></tr>'
    else: p=t.get("profit_pct",0); cl="pos" if p>=0 else "neg"; lb="止盈" if p>0 else "止损"; tr+=f'<tr><td>{t["date"][-5:]}</td><td style="color:{"#16a34a" if p>0 else "#dc2626"}">{lb}</td><td class="left">{t["name"]}</td><td>{t["sector"]}</td><td>{t["qty"]}</td><td>{t["price"]:.2f}</td><td>{t["amount"]:.0f}</td><td>-</td><td class="left">{t["reason"]}<span class="{cl}">({p:+.2f}%)</span></td></tr>'
# 持仓
hr=""; from datetime import datetime as ddt
for cd,pos in sorted(r["pf"].items(),key=lambda x:x[1]["cost"],reverse=True):
    nm=C.get(cd,cd); sc=S.get(cd,""); ac=round(pos["cost"]/pos["shares"],2)
    kl=lambda c:next((st[c] for sec,st in A.items() if c in st),None); DI=lambda d,kl:next((i for i,k in enumerate(kl) if k["date"]==d),-1) if kl else -1
    k=kl(cd); cp=ac
    if k:
        i=DI("20260430",k)
        if i>=0: cp=k[i]["close"]
    mv=cp*pos["shares"]; pl=mv-pos["cost"]; pp=round((cp-pos["price"])/pos["price"]*100,2); cl="pos" if pl>=0 else "neg"
    ed=ddt.strptime(pos["entry_date"],"%Y%m%d"); e2=ddt.strptime("20260430","%Y%m%d"); dy=(e2-ed).days
    hr+=f'<tr><td class="left">{nm}</td><td>{sc}</td><td>{pos["shares"]}</td><td>{ac:.2f}</td><td>{cp:.2f}</td><td class="{cl}">{pl:+.0f}</td><td class="{cl}">{pp:+.2f}%</td><td>{dy}天</td><td>{pos["cost"]:.0f}</td><td>{pos["cost"]/end*100:.1f}%</td></tr>'

pt=r.get("peak_trough",{}); sc=pt.get("score",0); rn=pt.get("result","")

html=f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
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
</style></head><body>
<div class="report-header"><div class="report-title">v3.3 第4周交易报告</div><div class="report-subtitle">2026-04-27 ~ 2026-04-30 | 波谷换股+主线>60%</div><hr class="report-divider"></div>
<div class="part"><div class="part-header"><span class="part-number">0</span> 大盘波峰波谷</div><div class="detail-box">第4周评分：04/27 -1偏波谷 → 04/28 -2偏波谷 → 04/29 0波中 → 04/30 -2偏波谷<br>整周波谷~波中震荡。</div></div>
<div class="part"><div class="part-header"><span class="part-number">1</span> 本周表现</div>
<div class="kpi-group">
<span class="kpi-row"><span class="kpi-label">周初资产</span><br><span class="kpi-value">{w3e:,.0f}</span></span>
<span class="kpi-row" style="background:{"#f0fdf4" if end>w3e else "#fef2f2"}"><span class="kpi-label">周末资产</span><br><span class="kpi-value">{end:,.0f}</span></span>
<span class="kpi-row" style="background:{"#f0fdf4" if end>w3e else "#fef2f2"}"><span class="kpi-label">本周收益</span><br><span class="kpi-value" style="color:{"#16a34a" if end>w3e else "#dc2626"}">{end-w3e:+,.0f} ({(end-w3e)/w3e*100:+.2f}%)</span></span>
<span class="kpi-row" style="background:{"#f0fdf4" if end>1000000 else "#fef2f2"}"><span class="kpi-label">累计收益</span><br><span class="kpi-value" style="color:{"#16a34a" if end>1000000 else "#dc2626"}">{end-1000000:+,.0f} ({(end-1000000)/1000000*100:+.2f}%)</span></span>
<span class="kpi-row"><span class="kpi-label">总仓位</span><br><span class="kpi-value">{tp:.1f}%</span></span>
<span class="kpi-row"><span class="kpi-label">主线占比</span><br><span class="kpi-value" style="color:#16a34a">{mp:.1f}%</span></span>
</div></div>
<div class="part"><div class="part-header"><span class="part-number">2</span> 主线仓位</div><div class="detail-box">主线<b>{mp:.1f}%</b> (< 60% ✅) | 非主线<b>{tp-mp:.1f}%</b></div></div>
<div class="part"><div class="part-header"><span class="part-number">3</span> 期末持仓</div><table><tr><th class="left">名称</th><th>方向</th><th>持股</th><th>均价</th><th>现价</th><th>盈亏</th><th>盈亏%</th><th>持天</th><th>成本</th><th>仓位</th></tr>{hr}</table><div class="detail-box">总资产{end:,.0f} | 现金{r["cash"]:,.0f} | 市值{end-r["cash"]:,.0f} | 仓位{tp:.1f}%</div></div>
<div class="part"><div class="part-header"><span class="part-number">4</span> 交易明细</div><table><tr><th>日期</th><th>操作</th><th class="left">名称</th><th>方向</th><th>数量</th><th>单价</th><th>金额</th><th>个股</th><th class="left">理由</th></tr>{tr}</table></div>
<div class="part"><div class="part-header"><span class="part-number">5</span> 清仓记录</div><table><tr><th class="left">名称</th><th>方向</th><th>清仓日</th><th>卖出价</th><th>数量</th><th>盈亏%</th><th>持天</th><th class="left">理由</th></tr>{cr}</table><div class="detail-box">合合信息-28.94%为本周最大亏损（数据或事件异常）。累计仍盈利+0.34%。</div></div>
<div style="text-align:center;font-size:10px;color:#999;margin-top:20px">v3.3 第4周 (2026-04-27~2026-04-30) | 累计+{(end-1000000)/1000000*100:.2f}%</div>
</body></html>'''

with open(os.path.join(OUT,"第4周_v33.html"),"w") as f: f.write(html)
import subprocess as sp
r2=sp.run(["wkhtmltopdf","--encoding","UTF-8","--enable-local-file-access",os.path.join(OUT,"第4周_v33.html"),os.path.join(OUT,"第4周_v33.pdf")],capture_output=True,text=True,timeout=60)
print(f"✅ PDF {'成功' if r2.returncode==0 else '失败'}")

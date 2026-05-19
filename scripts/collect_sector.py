#!/usr/bin/env python3
"""补采一个行业，参数: python3 collect_sector.py 商业航天 002361,002202,..."""
import urllib.request, json, os, time, sys

CACHE = "/home/ubuntu/data/3l/all_stocks_60d.json"

if os.path.exists(CACHE):
    with open(CACHE) as f:
        data = json.load(f)
else:
    data = {"last_updated":"2026-05-18","stocks":{}}

sector = sys.argv[1]
codes = sys.argv[2].split(",")

print(f"采集: {sector} ({len(codes)}只)")

if sector not in data["stocks"]:
    data["stocks"][sector] = {}

def fetch_kline(code, max_retry=5):
    prefix = "sh" if (code.startswith("6") or code.startswith("9") or code.startswith("5")) else "sz"
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&datalen=60"
    for a in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            if raw and not isinstance(raw, dict):
                return [{"date":b["day"][:10].replace("-",""),"open":float(b["open"]),"close":float(b["close"]),
                        "high":float(b["high"]),"low":float(b["low"]),"volume":float(b["volume"])} for b in raw]
        except: pass
        time.sleep(3 + a*2)
    return None

ok = 0
for code in codes:
    if code in data["stocks"].get(sector, {}):
        ok += 1
        continue
    klines = fetch_kline(code)
    if klines and len(klines) >= 20:
        data["stocks"][sector][code] = klines
        ok += 1
        print(f"  ✓ {code} ({len(klines)}条)")
    else:
        print(f"  ✗ {code}")
    time.sleep(0.35)

with open(CACHE, "w") as f:
    json.dump(data, f, ensure_ascii=False)

total = sum(len(v) for v in data["stocks"].values())
print(f"\n{sector}: {ok}/{len(codes)} → 累计{total}只")

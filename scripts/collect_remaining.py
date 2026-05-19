#!/usr/bin/env python3
"""分批补采，每完成一个行业就保存"""
import urllib.request, json, os, time, sys

DATA_DIR = "/home/ubuntu/data/3l"
CACHE = os.path.join(DATA_DIR, "all_stocks_60d.json")

# 已存数据
if os.path.exists(CACHE):
    with open(CACHE) as f:
        data = json.load(f)
else:
    data = {"last_updated":"2026-05-18","stocks":{}}

# 需要补的行业+股票
TODO = {
    "商业航天": ["002361","002202","002342","002149","601698","688010","600879","300699","300726","001208","600118","600391","562510"],
    "机器人": ["688088","300503","300969","002196","002434","603786","603319","603148","002915","600592","002048","688084","605056","688290","603012","600239","601177","300718","300660","002067","603980","002607","688322","603583","600232","603237","300161","002527","688160","600580","300953","002896","300100","688165","300607","002520","002148","002689","603179","688017","601100","603667","002031","300432","002553","002472","601689","002050","300007","002698","300580","603728","603009","688218","002611","002892","603662","000637","301413"],
    "创新药": ["603538","688578","002653","688331","002393","301509","688131","300436","002294","688266","688428","600276","603259","300347","688235"],
    "资源股": ["301219","300139","000831","002378","000657","002240","002428","000933","600301","002160","601600","688353","002466","002192","601168","002460","600516","600111","600549","603993","601899","000737","000831","600362"],
    "新能源": ["002709","605117","300750","300274","688390","300438","002245","301511","300953","002407","301358","002460","002466","002192","002240","688353","002915"],
}

def fetch_kline(code, max_retry=3):
    prefix = "sh" if (code.startswith("6") or code.startswith("9") or code.startswith("5")) else "sz"
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&datalen=60"
    for a in range(max_retry):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            if raw and not isinstance(raw, dict):
                klines = [{"date":b["day"][:10].replace("-",""),"open":float(b["open"]),"close":float(b["close"]),
                          "high":float(b["high"]),"low":float(b["low"]),"volume":float(b["volume"])} for b in raw]
                return klines
        except: pass
        time.sleep(3)
    return None

total_ok = sum(len(v) for v in data["stocks"].values())
print(f"已存: {total_ok}只")

for sector, codes in TODO.items():
    if sector in data["stocks"] and len(data["stocks"][sector]) >= len(codes) * 0.5:
        print(f"跳过{sector}: 已有{len(data['stocks'][sector])}只")
        continue
    data["stocks"][sector] = data["stocks"].get(sector, {})
    sector_ok = 0
    for code in codes:
        if code in data["stocks"][sector]:
            sector_ok += 1
            continue
        klines = fetch_kline(code)
        if klines and len(klines) >= 20:
            data["stocks"][sector][code] = klines
            sector_ok += 1
            sys.stdout.write(f"✓")
        else:
            sys.stdout.write(f"✗")
        sys.stdout.flush()
        time.sleep(0.4)  # 400ms间隔防限流
    # 每完成一个行业就保存
    with open(CACHE, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    total = sum(len(v) for v in data["stocks"].values())
    print(f"\n{sector}: {sector_ok}/{len(codes)}只 → 累计{total}只 | 已保存")

print(f"\n最终: {sum(len(v) for v in data['stocks'].values())}只")

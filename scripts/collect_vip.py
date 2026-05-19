#!/usr/bin/env python3
"""用VIP域名补采剩余股票"""
import json, os, time, urllib.request

CACHE = "/home/ubuntu/data/3l/all_stocks_60d.json"
with open(CACHE) as f:
    data = json.load(f)

# 算力缺的18只
SUANLI_MISSING = ["920099","688313","603920","002364","300284","002281","300442","000988","601869","600487","600176","605006","301526","600941","600050","601728","002428","002222"]
# 资源股24只
ZIYUAN = ["301219","300139","000831","002378","000657","002240","002428","000933","600301","002160","601600","688353","002466","002192","601168","002460","600516","600111","600549","603993","601899","000737","000831","600362"]
# 新能源20只
XINNENGYUAN = ["002709","605117","300750","300274","688390","300438","002245","301511","300953","002407","301358","002460","002466","002192","002240","688353","002915"]
# 机器人缺1只
JIQIREN_MISSING = ["603148"]

# 先算已有的，只取缺的
def get_missing(sector, codes, existing_data):
    existing = set(existing_data["stocks"].get(sector, {}).keys())
    return [c for c in codes if c not in existing]

suanli = get_missing("算力", SUANLI_MISSING, data)
ziyuan = get_missing("资源股", ZIYUAN, data)
xinneng = get_missing("新能源", XINNENGYUAN, data)
jiqiren = get_missing("机器人", JIQIREN_MISSING, data)

ALL_MISSING = suanli + ziyuan + xinneng + jiqiren
print(f"需补: 算力{suanli}+资源{ziyuan}+新能源{xinneng}+机器人{jiqiren}={len(ALL_MISSING)}只")

def fetch(code):
    prefix = "sh" if (code.startswith("6") or code.startswith("9") or code.startswith("5")) else "sz"
    url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&datalen=60"
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        if raw and not isinstance(raw, dict):
            return [{"date":b["day"][:10].replace("-",""),"open":float(b["open"]),"close":float(b["close"]),
                    "high":float(b["high"]),"low":float(b["low"]),"volume":float(b["volume"])} for b in raw]
    except: pass
    return None

# 按行业分组获取
groups = [
    ("算力", suanli),
    ("资源股", ziyuan),
    ("新能源", xinneng),
    ("机器人", jiqiren),
]

for sector, codes in groups:
    if not codes:
        print(f"{sector}: 已全")
        continue
    if sector not in data["stocks"]:
        data["stocks"][sector] = {}
    ok = 0
    for code in codes:
        klines = fetch(code)
        if klines and len(klines) >= 20:
            data["stocks"][sector][code] = klines
            ok += 1
            print(f"  ✓ {sector}/{code} ({len(klines)}条)")
        else:
            print(f"  ✗ {sector}/{code}")
        time.sleep(0.3)
    # 每行业保存
    with open(CACHE, "w") as f:
        json.dump(data, f, ensure_ascii=False)

total = sum(len(v) for v in data["stocks"].values())
print(f"\n完成! 累计{total}只")

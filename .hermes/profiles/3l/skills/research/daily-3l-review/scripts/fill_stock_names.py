#!/usr/bin/env python3
"""为 all_stocks_60d.json 中所有股票补上名称"""
import json, requests, time

DATA_PATH = "/home/ubuntu/data/3l/all_stocks_60d.json"

with open(DATA_PATH) as f:
    data = json.load(f)
stocks = data["stocks"]

def get_stock_name(code):
    """从腾讯API获取股票名称"""
    market = "sz" if code.startswith(("0", "3")) else "sh"
    try:
        r = requests.get(
            f"https://qt.gtimg.cn/q={market}{code}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        parts = r.text.split("~")
        if len(parts) > 1:
            return parts[1]
    except:
        pass
    return None

total = sum(len(v) for v in stocks.values())
fixed = 0
batch = 0
for sec_name, sec_stocks in stocks.items():
    for code, kls in sec_stocks.items():
        if not kls:
            continue
        if "name" in kls[0] and kls[0].get("name"):
            continue  # 已有名
        name = get_stock_name(code)
        if name:
            for k in kls:
                k["name"] = name
            fixed += 1
        batch += 1
        if batch % 20 == 0:
            time.sleep(0.3)  # 防封

with open(DATA_PATH, "w") as f:
    json.dump(data, f, ensure_ascii=False)

print(f"[补名] ✅ {fixed}/{total} 只补全名称")

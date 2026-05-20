     1|#!/usr/bin/env python3
     2|"""为 all_stocks_60d.json 中247只股票补上名称"""
     3|import json, requests, time
     4|
     5|DATA_PATH = "/home/ubuntu/data/3l/all_stocks_60d.json"
     6|
     7|with open(DATA_PATH) as f:
     8|    data = json.load(f)
     9|stocks = data["stocks"]
    10|
    11|# 收集所有股票代码
    12|codes = []
    13|for sec, sec_stocks in stocks.items():
    14|    for code in sec_stocks:
    15|        codes.append((sec, code))
    16|
    17|print(f"共 {len(codes)} 只股票，开始拉取名称...")
    18|
    19|# 腾讯API批量查（最多一次50只）
    20|def batch_get_names(code_batch):
    21|    """腾讯支持一次查多只，用逗号分隔"""
    22|    codes_str = ",".join(
    23|        f"sz{c}" if c.startswith(("0", "3")) else f"sh{c}"
    24|        for _, c in code_batch
    25|    )
    26|    try:
    27|        r = requests.get(
    28|            f"https://qt.gtimg.cn/q={codes_str}",
    29|            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com"},
    30|            timeout=10
    31|        )
    32|        result = {}
    33|        for line in r.text.strip().split(";"):
    34|            if not line.strip():
    35|                continue
    36|            # 解析格式：v_sh688766="1~普冉股份~688766~..."
    37|            if "~" not in line:
    38|                continue
    39|            parts = line.split("~")
    40|            if len(parts) >= 3:
    41|                code = parts[2]
    42|                name = parts[1]
    43|                result[code] = name
    44|        return result
    45|    except Exception as e:
    46|        print(f"  batch error: {e}")
    47|        return {}
    48|
    49|# 分批处理，每批20只（避免触发限流）
    50|BATCH_SIZE = 20
    51|total_updated = 0
    52|t0 = time.time()
    53|
    54|for i in range(0, len(codes), BATCH_SIZE):
    55|    batch = codes[i:i+BATCH_SIZE]
    56|    names = batch_get_names(batch)
    57|    
    58|    for sec, code in batch:
    59|        if code in names and code in stocks.get(sec, {}):
    60|            kls = stocks[sec][code]
    61|            if kls:
    62|                kls[0]["name"] = names[code]
    63|                total_updated += 1
    64|    
    65|    # 进度
    66|    pct = min(100, (i + BATCH_SIZE) / len(codes) * 100)
    67|    print(f"  {i+BATCH_SIZE}/{len(codes)} ({pct:.0f}%) ✓", end="\r")
    68|    
    69|    # 每批间隔0.2秒，避免限流
    70|    if i + BATCH_SIZE < len(codes):
    71|        time.sleep(0.2)
    72|
    73|t1 = time.time()
    74|print(f"\n✅ 完成: {total_updated}/{len(codes)} 只补上名称, 耗时 {t1-t0:.1f}s")
    75|
    76|# 保存
    77|with open(DATA_PATH, "w") as f:
    78|    json.dump(data, f, ensure_ascii=False)
    79|print(f"💾 已保存 → {DATA_PATH}")
    80|
    81|# 验证
    82|with open(DATA_PATH) as f:
    83|    data2 = json.load(f)
    84|stocks2 = data2["stocks"]
    85|for sec, sec_stocks in stocks2.items():
    86|    for code, kls in sec_stocks.items():
    87|        if kls and "name" in kls[0]:
    88|            pass
    89|        else:
    90|            print(f"⚠️  {sec}/{code} 缺名称")
    91|            break
    92|    else:
    93|        continue
    94|    break
    95|else:
    96|    print("✅ 全部股票名称检查通过")
    97|
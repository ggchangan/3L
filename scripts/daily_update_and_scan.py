#!/usr/bin/env python3
"""
每日数据更新 + 全量自选股买点扫描

Step 1: 从mootdx拉取最新交易日数据，更新 all_stocks_60d.json
Step 2: 对247只自选股运行买点检测（中继+突破）
Step 3: 输出扫描结果到 latest_scan_result.json

用法:
    python3 scripts/daily_update_and_scan.py              # 完整执行（更新+扫描）
    python3 scripts/daily_update_and_scan.py --scan-only  # 只扫描，不拉数据
    python3 scripts/daily_update_and_scan.py --update-only # 只更新缓存，不扫描
"""
import json
import os
import sys
import time
from collections import Counter
from mootdx.quotes import Quotes

# ── 路径（本地 scripts/，不再依赖 Hermes 技能）──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buy_point_detection import detect_buy_point

DATA_PATH = os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'all_stocks_60d.json')
CLUSTER_PATH = os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'sub_sector_clusters.json')
OUTPUT_PATH = os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'latest_scan_result.json')


def update_cache():
    """拉最新交易日数据更新缓存"""
    print("=" * 60)
    print("📂 读取缓存...")
    with open(DATA_PATH) as f:
        data = json.load(f)
    stocks = data["stocks"]
    cached_date = data.get("last_updated", "未知")

    first_stock = None
    for sec, sec_stocks in stocks.items():
        for code in sec_stocks:
            first_stock = code
            break
        if first_stock:
            break

    existing_dates = set()
    for sec, sec_stocks in stocks.items():
        for code, klines in sec_stocks.items():
            for k in klines:
                existing_dates.add(k["date"])
    cache_latest = max(existing_dates) if existing_dates else ""

    # mootdx最新
    client = Quotes.factory(market="std")
    sample = client.bars(symbol=first_stock, frequency=9, start=0, count=3)
    latest_mootdx = sample.iloc[-1]["datetime"][:10].replace("-", "")

    print(f"  缓存: {cached_date} (最新日 {cache_latest})")
    print(f"  mootdx最新: {latest_mootdx}")

    if latest_mootdx <= cache_latest:
        print("✅ 已最新，跳过")
        return data

    total = sum(len(v) for v in stocks.values())
    updated = 0
    t0 = time.time()
    for sec_idx, (sec_name, sec_stocks) in enumerate(stocks.items()):
        for code, klines in sec_stocks.items():
            try:
                bars = client.bars(symbol=code, frequency=9, start=0, count=800, fq=True)
                if bars is None or len(bars) == 0:
                    continue
                new_records = []
                for _, row in bars.iterrows():
                    d = row["datetime"][:10].replace("-", "")
                    if d > cache_latest:
                        new_records.append({
                            "date": d,
                            "open": round(float(row["open"]), 2),
                            "close": round(float(row["close"]), 2),
                            "high": round(float(row["high"]), 2),
                            "low": round(float(row["low"]), 2),
                            "volume": int(float(row["volume"]))
                        })
                if new_records:
                    seen = {k["date"] for k in klines}
                    for nr in new_records:
                        if nr["date"] not in seen:
                            klines.append(nr)
                    klines.sort(key=lambda x: x["date"])
                    while len(klines) > 60:
                        klines.pop(0)
                    updated += 1
            except Exception:
                pass

    t1 = time.time()
    data["last_updated"] = latest_mootdx
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"✅ 更新 {updated}/{total} 只, 耗时 {t1-t0:.1f}s")
    return data


def scan_buy_points(data):
    """全量自选股买点扫描"""
    stocks = data["stocks"]
    all_dates = set()
    for sec, sec_stocks in stocks.items():
        for code, klines in sec_stocks.items():
            for k in klines:
                all_dates.add(k["date"])
    last_date = max(all_dates) if all_dates else data.get("last_updated", "")

    try:
        with open(CLUSTER_PATH) as f:
            sub_sector_map = json.load(f).get("sub_sector_map", {})
    except Exception:
        sub_sector_map = {}

    results = []
    for sec_name, sec_stocks in stocks.items():
        for code in sec_stocks:
            result = detect_buy_point(code, last_date, stocks)
            bs, bt, fl = 0, "", ""
            if result and result['score'] >= 3:
                bs, bt = result['score'], result['buy_type']
                fl = result.get('flags', '')
            if bs > 0:
                close = None
                for sec2, sec_stocks2 in stocks.items():
                    if code in sec_stocks2:
                        for k in sec_stocks2[code]:
                            if k["date"] == last_date:
                                close = k["close"]
                                break
                results.append({
                    "code": code,
                    "sector": sec_name,
                    "score": round(bs, 1),
                    "buy_type": bt,
                    "flags": fl,
                    "close": close or 0,
                    "cluster": sub_sector_map.get(code, "unknown"),
                })

    results.sort(key=lambda x: -x["score"])

    # 输出
    print(f"\n{'=' * 60}")
    print(f"📊 {len(results)} 个买点信号\n")
    if results:
        from collections import Counter
        dc = Counter(r["sector"] for r in results)
        for sec, cnt in dc.most_common():
            print(f"  {sec}: {cnt}")
        print(f"\nTOP20:")
        print(f"{'方向':<8} {'代码':<8} {'类型':<10} {'评分':<6} {'收盘':<8}")
        print("-" * 40)
        for r in results[:20]:
            print(f"{r['sector']:<8} {r['code']:<8} {r['buy_type']:<10} {r['score']:<6} {r['close']:<8.2f}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump({"scan_date": last_date, "data_source": "mootdx",
                    "total_signals": len(results), "results": results},
                   f, ensure_ascii=False, indent=2)
    print(f"\n💾 → {OUTPUT_PATH}")
    return results


def main():
    args = set(sys.argv[1:])
    if "--update-only" in args:
        update_cache()
    elif "--scan-only" in args:
        with open(DATA_PATH) as f:
            scan_buy_points(json.load(f))
    else:
        scan_buy_points(update_cache())


if __name__ == "__main__":
    main()

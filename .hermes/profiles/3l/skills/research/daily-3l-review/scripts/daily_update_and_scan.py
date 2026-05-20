#!/usr/bin/env python3
"""
每日数据更新 + 全量自选股买点扫描

Step 1: 从mootdx拉取最新交易日数据，更新 all_stocks_60d.json
Step 2: 对自选股运行买点检测（中继+突破）
Step 3: 输出扫描结果到 latest_scan_result.json

用法:
    python3 daily_update_and_scan.py              # 完整执行（更新+扫描）
    python3 daily_update_and_scan.py --scan-only  # 只扫描，不拉数据
    python3 daily_update_and_scan.py --update-only # 只更新缓存，不扫描
"""
import json
import os
import sys
import time
from collections import Counter
from mootdx.quotes import Quotes

DATA_PATH = "/home/ubuntu/data/3l/all_stocks_60d.json"
CLUSTER_PATH = "/home/ubuntu/data/3l/sub_sector_clusters.json"
OUTPUT_PATH = "/home/ubuntu/data/3l/latest_scan_result.json"
BPD_PATH = "/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts"
sys.path.insert(0, BPD_PATH)
from buy_point_detection import check_zhongji, check_tupo


def update_cache():
    """Step 1: 拉取最新日数据更新缓存"""
    print("=" * 60)
    print("📂 读取缓存...")
    with open(DATA_PATH) as f:
        data = json.load(f)
    stocks = data["stocks"]
    cached_date = data.get("last_updated", "未知")
    total_stocks = sum(len(v) for v in stocks.values())
    print(f"  当前缓存最新: {cached_date}, 共 {total_stocks} 只")

    first_sector = list(stocks.values())[0]
    first_code = list(first_sector.keys())[0]
    existing_dates = sorted(set(k["date"] for k in first_sector[first_code]))
    cache_latest = existing_dates[-1]

    client = Quotes.factory(market="std")
    sample = client.bars(symbol=first_code, frequency=9, start=0, count=3)
    latest_mootdx = sample.iloc[-1]["datetime"][:10].replace("-", "")

    print(f"  mootdx最新数据日: {latest_mootdx}")
    print(f"  缓存最新日: {cache_latest}")

    if latest_mootdx <= cache_latest:
        print("✅ 缓存已是最新，无需更新")
        return data

    updated = 0
    failed = 0
    t0 = time.time()

    for sec_idx, (sec_name, sec_stocks) in enumerate(stocks.items()):
        print(f"\n  [{sec_idx + 1}/8] {sec_name} ({len(sec_stocks)}只)...", end=" ")
        sec_updated = 0
        for code, klines in sec_stocks.items():
            try:
                bars = client.bars(symbol=code, frequency=9, start=0, count=800, fq=True)
                if bars is None or len(bars) == 0:
                    continue
                new_entries = []
                for _, row in bars.iterrows():
                    d = row["datetime"][:10].replace("-", "")
                    # 拉所有比缓存新的日期，不限于一天
                    if d > cache_latest:
                        new_entries.append({
                            "date": d,
                            "open": round(float(row["open"]), 2),
                            "close": round(float(row["close"]), 2),
                            "high": round(float(row["high"]), 2),
                            "low": round(float(row["low"]), 2),
                            "volume": int(float(row["volume"]))
                        })
                if new_entries:
                    existing_dates_set = set(k["date"] for k in klines)
                    for entry in new_entries:
                        if entry["date"] not in existing_dates_set:
                            klines.append(entry)
                    klines.sort(key=lambda x: x["date"])
                    while len(klines) > 60:
                        klines.pop(0)
                    sec_updated += 1
            except Exception:
                failed += 1
        updated += sec_updated
        print(f"{sec_updated}只更新")

    t1 = time.time()
    print(f"\n✅ 更新完成: {updated}/{total_stocks} 只获取到新数据")
    if failed:
        print(f"⚠️  {failed} 只失败")
    print(f"⏱  耗时: {t1 - t0:.1f}s")

    data["last_updated"] = latest_mootdx
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"💾 已保存 → {DATA_PATH}")
    return data


def scan_buy_points(data):
    """Step 2: 全量自选股买点扫描"""
    stocks = data["stocks"]
    data_latest = data.get("last_updated", "未知")

    all_dates = set()
    for sec, sec_stocks in stocks.items():
        for code, klines in sec_stocks.items():
            for k in klines:
                all_dates.add(k["date"])
    last_date = sorted(all_dates)[-1]
    print(f"\n{'=' * 60}")
    print(f"🔍 扫描日期: {last_date} (缓存最新: {data_latest})")

    try:
        with open(CLUSTER_PATH) as f:
            cluster_data = json.load(f)
        sub_sector_map = cluster_data.get("sub_sector_map", {})
    except (FileNotFoundError, json.JSONDecodeError):
        sub_sector_map = {}

    def get_name(code):
        for sec, sec_stocks in stocks.items():
            if code in sec_stocks and sec_stocks[code]:
                return sec_stocks[code][0].get("name", code)
        return code

    def get_close(code, date_str):
        for sec, sec_stocks in stocks.items():
            if code in sec_stocks:
                for k in sec_stocks[code]:
                    if k["date"] == date_str:
                        return k["close"]
        return None

    results = []
    for sec_name, sec_stocks in stocks.items():
        for code in sec_stocks:
            zj = check_zhongji(code, last_date, stocks)
            tp = check_tupo(code, last_date, stocks)
            bs, bt, fl = 0, "", ""
            if zj and zj["pass"] >= 4:
                bs, bt, fl = zj["pass"], "中继买点", zj["flags"]
            if tp and tp["pass"] >= 3:
                if bs < tp["pass"] + 0.5:
                    bs, bt, fl = tp["pass"] + 0.5, "突破买点", tp["flags"]
            if bs > 0:
                results.append({
                    "code": code,
                    "name": get_name(code),
                    "sector": sec_name,
                    "score": round(bs, 1),
                    "buy_type": bt,
                    "flags": fl,
                    "close": get_close(code, last_date) or 0,
                    "cluster": sub_sector_map.get(code, "unknown"),
                })

    results.sort(key=lambda x: -x["score"])

    print(f"\n📊 共发现 {len(results)} 个买点信号\n")
    if results:
        dir_counter = Counter(r["sector"] for r in results)
        print(f"{'方向':<10} {'数量':<6}")
        print("-" * 20)
        for sec, cnt in dir_counter.most_common():
            print(f"{sec:<10} {cnt:<6}")
        print(f"\n📋 TOP20:")
        for r in results[:20]:
            print(f"  {r['name']:<10} {r['code']:<8} {r['buy_type']:<10} {r['score']:<4}")
    else:
        print("⚠️ 无买点信号")

    output = {
        "scan_date": last_date,
        "data_source": "mootdx",
        "cache_updated_to": data_latest,
        "total_signals": len(results),
        "results": results,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存 → {OUTPUT_PATH}")
    return results


def main():
    args = set(sys.argv[1:])
    if "--update-only" in args:
        update_cache()
    elif "--scan-only" in args:
        with open(DATA_PATH) as f:
            data = json.load(f)
        scan_buy_points(data)
    else:
        data = update_cache()
        scan_buy_points(data)


if __name__ == "__main__":
    main()

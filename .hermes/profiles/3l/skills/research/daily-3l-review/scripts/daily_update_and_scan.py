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
from buy_point_detection import detect_buy_point


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

    from buy_point_detection import detect_buy_point
    
    # 获取大盘位置（读取已有review数据或默认波中）
    market_position = ''
    for try_date in [last_date.replace('-', ''), last_date]:
        p = f'/home/ubuntu/data/3l/review_output/{try_date}/review.json'
        if os.path.isfile(p):
            try:
                with open(p) as _f:
                    _rd = json.load(_f)
                market_position = _rd.get('market', {}).get('position', '')
            except:
                pass
            break
    if not market_position:
        # 没有review数据时从K线估算
        try:
            idx_code = '000985'
            idx_closes = []
            for sec, sec_stocks in stocks.items():
                if idx_code in sec_stocks:
                    for k in sec_stocks[idx_code]:
                        idx_closes.append(k['close'])
                    break
            if len(idx_closes) >= 20:
                cur = idx_closes[-1]
                ma20 = sum(idx_closes[-20:]) / 20
                d = (cur - ma20) / ma20 * 100
                if d > 2: market_position = '波中偏上'
                elif d > -2: market_position = '波中'
                elif d > -5: market_position = '波中偏下'
                else: market_position = '波谷'
        except:
            pass
    if market_position:
        from buy_point_detection import _shrink_threshold
        print(f"  大盘位置: {market_position}  缩量阈值: <{_shrink_threshold(market_position):.0%}")
    
    results = []
    for sec_name, sec_stocks in stocks.items():
        for code in sec_stocks:
            try:
                bt = detect_buy_point(code, last_date, stocks, market_position=market_position)
                if bt:
                    results.append({
                        "code": code,
                        "name": get_name(code),
                        "sector": sec_name,
                        "score": bt['score'],
                        "buy_type": bt['buy_type'],
                        "flags": bt['buy_type'],
                        "close": bt['close'],
                        "gain": bt.get('gain', 0),
                        "cluster": sub_sector_map.get(code, "unknown"),
                    })
            except Exception:
                continue

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

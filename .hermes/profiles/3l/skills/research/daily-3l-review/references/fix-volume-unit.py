#!/usr/bin/env python3
"""
修复 all_stocks_60d.json 中最后若干日的volume单位问题。

根因：腾讯财经API返回volume单位为手（lot），mootdx返回股（shares）。
generate_review_data.py 从腾讯财经补拉最新K线时若未×100，会导致最新几日volume
仅为正常值的1%，进而影响买点检测中的"放量"条件判断。

检测逻辑：最后N天中，若某日volume < 前10日均量的20%，判定为手，×100修复。
"""
import json, os, sys

DATA_PATH = "/home/ubuntu/data/3l/all_stocks_60d.json"
CHECK_DAYS = 3       # 检查最后几天
WINDOW = 10          # 对比前N天的均量
THRESHOLD = 0.20     # 低于均量20%视为单位错误

def fix_volume(data_path=DATA_PATH, dry_run=False):
    with open(data_path) as f:
        data = json.load(f)

    stocks_data = data.get("stocks", data)  # 兼容两种结构
    fixed_count = 0
    fixed_codes = set()

    for sec_name, sec_stocks in stocks_data.items():
        if not isinstance(sec_stocks, dict):
            continue
        for code, klines in sec_stocks.items():
            if not isinstance(klines, list) or len(klines) < WINDOW + 2:
                continue
            for offset in range(-CHECK_DAYS, 0):
                idx = len(klines) + offset
                if idx < 0:
                    continue
                k = klines[idx]
                vols_before = [klines[i]["volume"] for i in range(max(0, idx - WINDOW), idx)
                               if isinstance(klines[i].get("volume"), (int, float)) and klines[i]["volume"] > 0]
                if not vols_before:
                    continue
                avg_before = sum(vols_before) / len(vols_before)
                cur_vol = k.get("volume", 0)
                if avg_before > 0 and isinstance(cur_vol, (int, float)) and cur_vol > 0 and cur_vol < avg_before * THRESHOLD:
                    if not dry_run:
                        k["volume"] = int(cur_vol * 100)
                    fixed_count += 1
                    fixed_codes.add(code)

    if not dry_run:
        with open(data_path, "w") as f:
            json.dump(data, f, ensure_ascii=False)

    return fixed_count, len(fixed_codes)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DATA_PATH
    dry = "--dry-run" in sys.argv

    n_records, n_codes = fix_volume(path, dry_run=dry)
    print(f"{'[DRY RUN] ' if dry else ''}修复 {n_records} 条记录, 涉及 {n_codes} 只股票")

    if n_records > 0:
        print("提示: 修复后请重新运行 buy_point_detection 扫描。")

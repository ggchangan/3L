import json, sys
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')
from buy_point_detection import scan_all_stocks

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)

results = scan_all_stocks('2026-05-21', raw, market_position='波中', main_lines={'半导体','算力','创新药','机器人','新能源','资源股','AI应用','商业航天'})

# Show full result dict for each
for r in results:
    sector = r.get('sector', '?')
    is_main = "主线" if sector in {'半导体','算力','创新药','机器人','新能源','资源股','AI应用','商业航天'} else "非主线"
    print(f"\n代码={r.get('code','?')} 名称={r.get('name','?')} 类型={r['buy_type']} 板块={sector}({is_main})")
    print(f"  评分={r.get('score')} 入场价={r.get('close')} 当日涨幅={r.get('gain','?')}%")
    detail = r.get('detail', r.get('details', {}))
    if detail:
        print(f"  明细: {json.dumps(detail, ensure_ascii=False, default=str)[:300]}")

# Summary
print("\n" + "="*60)
print("SUMMARY REPORT")
print("="*60)
print(f"Date: 2026-05-21")
print(f"Market Position: 波中")
print(f"Main Lines: 半导体,算力,创新药,机器人,新能源,资源股,AI应用,商业航天")
print(f"Total stocks scanned: {sum(len(v) for v in raw.values())}")
print(f"Total buy signals: {len(results)}")

breakdown = {}
total_score = 0
for r in results:
    bt = r['buy_type']
    breakdown[bt] = breakdown.get(bt, 0) + 1
    total_score += r.get('score', 0)

print(f"\nBuy Type Breakdown:")
for bt, count in sorted(breakdown.items()):
    print(f"  {bt}: {count}")

print(f"\nScore Summary:")
print(f"  Total score (sum): {total_score}")
print(f"  Avg score: {total_score/len(results):.1f}" if results else "  N/A")

# Main line vs non-main breakdown
main_count = sum(1 for r in results if r.get('sector') in {'半导体','算力','创新药','机器人','新能源','资源股','AI应用','商业航天'})
nonmain_count = len(results) - main_count
print(f"\nMain line stocks: {main_count}")
print(f"Non-main line: {nonmain_count}")

# Individual results
print(f"\nIndividual signals:")
for r in results:
    sector = r.get('sector', '?')
    is_main = "★" if sector in {'半导体','算力','创新药','机器人','新能源','资源股','AI应用','商业航天'} else " "
    print(f"  {is_main} {r.get('code','?')} {r.get('name','?'):8s} {r['buy_type']:8s} score={r.get('score',0):2d} 入场={r.get('close',0):>8.2f} gain={r.get('gain',0):>+5.2f}% 板块={sector}")

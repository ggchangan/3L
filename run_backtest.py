import json, sys, time
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')
from buy_point_detection import scan_all_stocks

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)

t0 = time.time()
results = scan_all_stocks('2026-05-21', raw, market_position='波中', main_lines={'半导体','算力','创新药','机器人','新能源','资源股','AI应用','商业航天'})
t1 = time.time()

print(f"Total buy signals: {len(results)}")
print(f"Scan time: {t1-t0:.2f}s")
breakdown = {}
for r in results:
    bt = r['buy_type']
    breakdown[bt] = breakdown.get(bt, 0) + 1
    print(f"  {r.get('code','?')} {r.get('name','?'):8s} {bt:8s} score={r.get('score',0)} 入场={r.get('close',0)}")

print("\n=== BREAKDOWN ===")
for bt, count in sorted(breakdown.items()):
    print(f"{bt}: {count}")

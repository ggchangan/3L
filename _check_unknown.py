"""检查未知板块股票"""
import json

DATA_DIR = '/home/ubuntu/data/3l'

with open(f'{DATA_DIR}/watchlist.json') as f:
    wl = json.load(f)
stocks = wl.get('stocks', wl) if isinstance(wl, dict) else wl

with open(f'{DATA_DIR}/stock_industry_map.json') as f:
    imap = json.load(f)

unknown = []
for s in stocks:
    code = s.get('code', '')[-6:]
    info = imap.get(code, {})
    industry = info.get('ths_industry', '') if isinstance(info, dict) else ''
    if not industry:
        unknown.append((code, s.get('name', code), '有' if code in imap else '无'))

print(f'未知板块: {len(unknown)}只')
for code, name, in_map in unknown:
    print(f'  {code} {name} (map:{in_map})')

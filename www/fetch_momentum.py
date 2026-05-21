#!/usr/bin/env python3
"""Generate momentum data (limit up + new highs) for the review page."""
import json, sys, os, datetime

sys.path.insert(0, '/home/ubuntu/scripts')

result = {'limit_up': [], 'new_highs': [], 'new_highs_total': 0}

# 加载自选股代码
codes_set = set()
data_file = '/home/ubuntu/data/3l/all_stocks_60d.json'
if os.path.exists(data_file):
    with open(data_file) as f:
        raw = json.load(f)
        for direction in raw.get('stocks', {}).values():
            for code in direction:
                codes_set.add(code)

# 加载行业映射
industry_map = {}
ind_file = '/home/ubuntu/data/3l/stock_industry_map.json'
if os.path.exists(ind_file):
    with open(ind_file) as f:
        raw_map = json.load(f)
        for code, info in raw_map.items():
            industry_map[code] = info.get('ths_industry', '')
            industry_map[code[2:]] = info.get('ths_industry', '')
    dir_map = {}
    for code, info in raw_map.items():
        dir_map[code] = info.get('direction', '')
        dir_map[code[2:]] = info.get('direction', '')

# === 涨停数据（东财涨停板池，含连板数+行业） ===
try:
    import akshare as ak
    df = ak.stock_zt_pool_em(date=datetime.datetime.now().strftime('%Y%m%d'))
    records = df.to_dict('records')
    for r in records:
        code = str(r['代码'])
        # 标准化股票代码到6位
        if len(code) > 6:
            code = code[-6:]
        r['在自选'] = code in codes_set
        # 连板数
        r['连板数'] = r.get('连板数', 1)
        # 行业
        r['行业'] = r.get('所属行业', '') or industry_map.get(code, '') or industry_map.get(code[2:], '')
        # 方向（自定义大主题，作为涨停原因参考）
        r['方向'] = dir_map.get(code, '') or dir_map.get(code[2:], '')
        r['股票代码'] = code
        r['股票简称'] = r['名称']
        r['涨跌幅'] = r.get('涨跌幅', 0)
        r['最新价'] = r.get('最新价', 0)
    result['limit_up'] = records[:100]
except Exception as e:
    result['limit_error'] = str(e)

# === 创新高数据 ===
try:
    import akshare as ak
    df2 = ak.stock_rank_cxg_ths()
    cxg_records = df2.to_dict('records')
    watchlist_new = []
    all_new = []
    for r in cxg_records:
        code = r['股票代码']
        ind = industry_map.get(code, '') or industry_map.get(code[2:], '')
        r2 = dict(r)
        if '前期高点日期' in r2 and not isinstance(r2['前期高点日期'], str):
            r2['前期高点日期'] = str(r2['前期高点日期'])
        r2['行业'] = ind
        if code in codes_set:
            watchlist_new.append(r2)
        all_new.append(r2)
    result['new_highs'] = watchlist_new
    result['new_highs_all'] = sorted(all_new, key=lambda x: x.get('涨跌幅', 0), reverse=True)
    result['new_highs_total'] = len(cxg_records)
except Exception as e:
    result['new_highs_error'] = str(e)

print(json.dumps(result, ensure_ascii=False))

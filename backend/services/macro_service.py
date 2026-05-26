"""
宏观数据服务 — 指数行情、汇率、CPI/PPI
"""
import json
import os
from datetime import datetime

import requests

from backend.config import CACHE_DIR


def get_macro_data():
    """
    获取宏观数据综合面板

    返回::
        {
            'indices': {名称: {price, prev_close, change_pct, name, code, high, low, time}, ...},
            'fx':      {币种: {price, change_pct, time, name}, ...},
            'cpi':     [{date, value, forecast, previous}, ...],
            'ppi':     [{date, value}, ...],
            'updated': 'YYYY-MM-DD HH:MM'
        }
    """
    os.environ['TQDM_DISABLE'] = '1'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com'
    }

    # ── 指数行情：腾讯 ───────────────────────────────────
    symbols = {
        'sh000001': '上证指数', 'sz399001': '深证成指',
        'sz399006': '创业板指', 'sh000300': '沪深300',
        'sh000985': '中证全指', 'us.INX': '标普500',
        'us.IXIC': '纳斯达克', 'us.DJI': '道琼斯',
        'sh000688': '科创50',
    }
    q_str = ','.join(symbols.keys())
    indices = {}
    try:
        r = requests.get(
            f'https://qt.gtimg.cn/q={q_str}',
            headers=headers,
            timeout=10
        )
        for line in r.text.strip().split(';'):
            if '="' not in line:
                continue
            key = line.split('=')[0].strip()
            parts = line.split('"')[1].split('~') if '"' in line else []
            if len(parts) < 10:
                continue
            tz = symbols.get(key, parts[1] if len(parts) > 1 else '')
            price = float(parts[3]) if parts[3] else 0
            prev = float(parts[4]) if parts[4] else price
            chg_pct = round((price - prev) / prev * 100, 2) if prev > 0 else 0
            indices[tz] = {
                'price': price, 'prev_close': prev,
                'change_pct': chg_pct, 'name': tz,
                'code': parts[2] if len(parts) > 2 else '',
                'high': float(parts[8]) if len(parts) > 8 and parts[8] else 0,
                'low': float(parts[9]) if len(parts) > 9 and parts[9] else 0,
                'time': parts[31] if len(parts) > 31 else '',
            }
    except Exception:
        pass

    # ── 汇率：新浪 ───────────────────────────────────────
    fx = {}
    try:
        rfx = requests.get(
            'https://hq.sinajs.cn/list=fx_susdcny,fx_seurcny,fx_sgbpcny,fx_sjpycny',
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://finance.sina.com.cn'
            },
            timeout=8
        )
        for fl in rfx.text.strip().split(';'):
            if '="' not in fl:
                continue
            fp = fl.split('"')[1].split(',') if '"' in fl else []
            if len(fp) < 4:
                continue
            fname = fp[9] if len(fp) > 9 else ''
            fprice = float(fp[3]) if len(fp) > 3 and fp[3] else 0
            fchg_amt = float(fp[12]) if len(fp) > 12 and fp[12] else 0
            fprev = fprice - fchg_amt if fchg_amt != 0 else fprice
            fchg = round((fprice - fprev) / fprev * 100, 4) if fprev > 0 else 0
            fx[fname or 'USD/CNY'] = {
                'price': fprice, 'change_pct': fchg,
                'time': fp[0] if fp[0] else '',
                'name': fname or '美元/人民币',
            }
    except Exception:
        pass

    # ── CPI（月频，带缓存） ─────────────────────────────
    cpi = None
    cpi_cache = os.path.join(CACHE_DIR, 'macro_cpi.json')
    cpi_today = datetime.now().strftime('%Y%m%d')
    if os.path.isfile(cpi_cache):
        try:
            cached = json.load(open(cpi_cache))
            if cached.get('date') == cpi_today:
                cpi = cached['data']
        except Exception:
            pass
    if cpi is None:
        try:
            import akshare as ak
            cpi_df = ak.macro_china_cpi_monthly()
            cpi_records = []
            for _, row in cpi_df.tail(12).iterrows():
                cpi_records.append({
                    'date': str(row.iloc[1]) if len(row) > 1 else '',
                    'value': float(row.iloc[2]) if len(row) > 2 and row.iloc[2] else None,
                    'forecast': float(row.iloc[3]) if len(row) > 3 and row.iloc[3] else None,
                    'previous': float(row.iloc[4]) if len(row) > 4 and row.iloc[4] else None,
                })
            cpi = cpi_records
            os.makedirs(os.path.dirname(cpi_cache), exist_ok=True)
            config.atomic_json_dump({'date': cpi_today, 'data': cpi}, cpi_cache)
        except Exception:
            cpi = []

    # ── PPI ──────────────────────────────────────────────
    ppi = []
    try:
        import akshare as ak
        ppi_df = ak.macro_china_ppi()
        ppi_records = []
        for _, row in ppi_df.head(12).iterrows():
            ppi_records.append({
                'date': str(row.iloc[0]) if len(row) > 0 else '',
                'value': float(row.iloc[2]) if len(row) > 2 and row.iloc[2] else None,
            })
        ppi = ppi_records
    except Exception:
        ppi = []

    return {
        'indices': indices,
        'fx': fx,
        'cpi': cpi or [],
        'ppi': ppi or [],
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

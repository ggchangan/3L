"""
宏观数据服务 — 指数行情、汇率、CPI/PPI
"""
import json
import os
from datetime import datetime

import requests

from backend.config import CACHE_DIR


# ── 美股代码对照表（与 external_mapping.json 的 23 只对齐） ──
_US_CODES = {
    'us.NVDA': '英伟达', 'us.AMD': '超威半导体', 'us.INTC': '英特尔',
    'us.AVGO': '博通', 'us.ARM': 'Arm Holdings', 'us.TSM': '台积电',
    'us.MU': '美光科技', 'us.WDC': '西部数据', 'us.SNDK': '闪迪', 'us.STX': '希捷科技',
    'us.AAOI': '应用光电', 'us.LITE': 'Lumentum', 'us.GLW': '康宁', 'us.COHR': 'Coherent Corp',
    'us.VRT': 'Vertiv', 'us.GEV': 'GE Vernova',
    'us.ASML': '阿斯麦', 'us.TER': '泰瑞达', 'us.AXTI': 'AXT Inc',
    'us.GOOGL': '谷歌', 'us.MSFT': '微软', 'us.ORCL': '甲骨文', 'us.META': 'Meta',
}


def get_alert_level(change_pct):
    """判定涨跌幅的的异动等级"""
    abs_chg = abs(change_pct)
    if abs_chg >= 5:
        return 'warning'
    elif abs_chg >= 3:
        return 'caution'
    return None


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
        # 外围更多指数
        'us.SOX': '费城半导体', 'us.RUT': '罗素2000',
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

    # ── 美股实时行情（新浪） ────────────────────────────
    us_stocks = {}
    us_codes = _US_CODES
    try:
        sina_keys = {k.replace('us.', 'gb_').lower(): v for k, v in us_codes.items()}
        r_us = requests.get(
            f'https://hq.sinajs.cn/list={",".join(sina_keys.keys())}',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn'},
            timeout=10
        )
        for line in r_us.text.strip().split(';'):
            if '="' not in line:
                continue
            parts = line.split('"')[1].split(',') if '"' in line else []
            if len(parts) < 10:
                continue
            key = line.split('=')[0].strip()
            name = sina_keys.get(key, parts[0] if len(parts) > 0 else '')
            try:
                price = float(parts[1]) if parts[1] else 0
                chg_pct = float(parts[2]) if parts[2] else 0
            except (ValueError, IndexError):
                continue
            us_stocks[name] = {
                'price': price, 'change_pct': chg_pct if abs(chg_pct) < 100 else 0,
                'name': name, 'code': key.replace('gb_', '').upper(),
                'time': parts[3] if len(parts) > 3 else '',
            }
    except Exception:
        pass

    # ── 外围供应链映射数据 ────────────────────────────
    external_mapping = {}
    ext_path = os.path.join(os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'public', 'external_mapping.json')
    if os.path.isfile(ext_path):
        try:
            external_mapping = json.load(open(ext_path, encoding='utf-8'))
        except Exception:
            pass

    # ── 异动检测 ────────────────────────────────────────────
    abnormal_alerts = []
    ext_cats = external_mapping.get('categories', []) if isinstance(external_mapping, dict) else []
    for cat in ext_cats:
        for s in cat.get('stocks', []):
            name = s.get('name', '')
            stock_data = us_stocks.get(name)
            if not stock_data:
                continue
            chg = stock_data.get('change_pct', 0)
            level = get_alert_level(chg)
            if level:
                abnormal_alerts.append({
                    'name': name,
                    'code': s.get('code', ''),
                    'change_pct': chg,
                    'level': level,
                    'impact': s.get('impact', ''),
                })

    return {
        'indices': indices,
        'fx': fx,
        'cpi': cpi or [],
        'ppi': ppi or [],
        'us_stocks': us_stocks,
        'external': external_mapping,
        'abnormal_alerts': abnormal_alerts,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

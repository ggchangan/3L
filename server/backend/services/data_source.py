#!/usr/bin/env python3
"""
抽象数据层 — 统一数据获取入口，内置故障切换+健康监测

用法：
    from backend.services.data_source import (
        get_sector_rankings, get_sector_klines, get_concept_map, get_data_source_status
    )
"""

import json, os, sys, time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.config import (
    SECTOR_DAILY_PATH,
    SOURCES_EM_SECTOR_DAILY,
    SOURCES_THS_SECTOR_DAILY,
    SOURCES_EM_CONCEPT_MAP,
    STOCK_CONCEPT_MAP_PATH,
)
from backend.services.source_health import (
    report_success, report_failure, is_source_available, get_all_health
)


def _last_trading_day():
    """返回最后一个交易日字符串 YYYYMMDD
    周末回退到周五，简单实现不考虑法定节假日
    """
    d = datetime.now()
    for _ in range(7):
        if d.weekday() < 5:  # Mon=0..Fri=4
            return d.strftime('%Y%m%d')
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')


class DataUnavailableError(Exception):
    def __init__(self, data_type):
        self.data_type = data_type
        super().__init__(f'数据源全部不可用: {data_type}')

def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _call_with_failover(data_type, args, chain, fallback=None):
    for source_name, fetch_fn in chain:
        if not is_source_available(source_name):
            continue
        try:
            data = fetch_fn(*args)
            if data is None:
                continue  # None 表示"没找到"→尝试下一个源
            report_success(source_name)
            return data
        except Exception as e:
            report_failure(source_name, str(e))
            print(f'[data_source] {data_type} -> {source_name} 失败: {e}')
            continue
    if fallback:
        return fallback
    print(f'[data_source] {data_type}: 所有数据源均不可用!')
    raise DataUnavailableError(data_type)

# --- EM仓获取函数 ---
def _fetch_em_sector_ranking(date_str):
    """从 push2test 实时获取板块排行（chg_1d 取自 f3 字段）
    
    直接调东财实时接口，不依赖静态文件。失败时回退读 EM 仓文件。
    返回 {last_updated, industries: {name: {date, change_pct, close, ...}},
           concepts: {...}}
    """
    today = _last_trading_day()
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/',
        }
        ut = 'bd1d9ddb04089700cf9c27f6f7426281'
        result = {'last_updated': today, 'industries': {}, 'concepts': {}}
        for sector_type, fs in [('industries', 'm:90+t:2'), ('concepts', 'm:90+t:3')]:
            params = {
                'pn': '1', 'pz': '2000', 'po': '1', 'np': '1',
                'ut': ut, 'fltt': '2', 'invt': '2',
                'fs': fs, 'fields': 'f2,f3,f14,f15,f16,f17,f18,f5',
            }
            r = requests.get(url, params=params, headers=headers, timeout=20)
            items = r.json().get('data', {}).get('diff', [])
            for item in items:
                name = (item.get('f14') or '').strip()
                # 归一化：去掉Ⅱ/Ⅲ/D等东财后缀
                clean = name.replace('Ⅱ', '').replace('Ⅲ', '').replace('D', '').strip()
                if not clean:
                    continue
                close = float(item.get('f2', 0) or 0)
                result[sector_type][clean] = {
                    'date': today,
                    'close': round(close, 2),
                    'change_pct': round(float(item.get('f3', 0) or 0), 2),
                    'open': round(float(item.get('f17', close) or close), 2),
                    'high': round(float(item.get('f15', close) or close), 2),
                    'low': round(float(item.get('f16', close) or close), 2),
                    'volume': int(float(item.get('f5', 0) or 0)),
                    'prev_close': round(float(item.get('f18', 0) or 0), 2),
                }
            print(f'[data_source] push2test live [{sector_type}]: {len(result[sector_type])}个板块')
        print(f'[data_source] push2test live 排行获取成功 (行业{len(result["industries"])}个, 概念{len(result["concepts"])}个)')
        return result
    except Exception as e:
        print(f'[data_source] push2test live 失败, 回退 EM文件: {e}')
        return _load_json(SOURCES_EM_SECTOR_DAILY)

def _fetch_em_concept_map():
    return _load_json(SOURCES_EM_CONCEPT_MAP)

# --- THS仓获取函数 ---
def _fetch_em_sector_klines(sector_name, sector_type):
    """从 EM 仓获取单日K线（只有今日数据）"""
    data = _load_json(SOURCES_EM_SECTOR_DAILY)
    key = 'industries' if sector_type == 'industry' else 'concepts'
    container = data.get(key, {})
    entry = container.get(sector_name)
    if entry and isinstance(entry, dict):
        return [{
            'date': entry.get('date', ''),
            'open': entry.get('open', 0),
            'close': entry.get('close', 0),
            'high': entry.get('high', 0),
            'low': entry.get('low', 0),
            'volume': entry.get('volume', 0),
            'change_pct': entry.get('change_pct', 0),
        }]
    return []

def _fetch_ths_sector_ranking(date_str):
    data = _load_json(SOURCES_THS_SECTOR_DAILY)
    result = {}
    for key in ['industries', 'concepts']:
        container = data.get(key, {})
        for name, klines in container.items():
            if klines and len(klines) >= 2:
                latest = klines[-1]
                prev = klines[-2]
                if latest['date'] == date_str or date_str == '':
                    prev_close = prev['close']
                    if prev_close > 0:
                        result[name] = {
                            'date': latest['date'],
                            'change_pct': round((latest['close'] - prev_close) / prev_close * 100, 2),
                            'close': latest['close'],
                        }
    return result

def _fetch_ths_sector_klines(sector_name, sector_type):
    data = _load_json(SOURCES_THS_SECTOR_DAILY)
    key = 'industries' if sector_type == 'industry' else 'concepts'
    result = data.get(key, {}).get(sector_name)
    if result is None:
        return None  # 没找到→尝试下一个源
    return result

# --- 旧 sector_daily.json 获取函数 ---
def _fetch_legacy_sector_ranking(date_str):
    data = _load_json(SECTOR_DAILY_PATH)
    return data if data else None

def _fetch_legacy_sector_klines(sector_name, sector_type):
    data = _load_json(SECTOR_DAILY_PATH)
    key = 'industries' if sector_type == 'industry' else 'concepts'
    result = data.get(key, {}).get(sector_name)
    if result is None:
        return None
    return result

# ====== 调用链定义 ======
DATA_SOURCE_CHAINS = {
    'sector_ranking': [
        ('em_sector', lambda date: _fetch_em_sector_ranking(date)),
        ('legacy_sector', lambda date: _fetch_legacy_sector_ranking(date)),
        ('ths_sector', lambda date: _fetch_ths_sector_ranking(date)),
    ],
    'sector_klines': [
        ('ths_sector', lambda name, type_: _fetch_ths_sector_klines(name, type_)),
        ('em_sector', lambda name, type_: _fetch_em_sector_klines(name, type_)),
        ('legacy_sector', lambda name, type_: _fetch_legacy_sector_klines(name, type_)),
    ],
    'concept_map': [
        ('em_sector', lambda: _fetch_em_concept_map()),
        ('legacy_sector', lambda: _load_json(STOCK_CONCEPT_MAP_PATH)),
    ],
}

# ====== 公开API ======
def get_sector_rankings(sector_type='industry', date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    chain = DATA_SOURCE_CHAINS['sector_ranking']
    result = _call_with_failover(f'sector_ranking_{sector_type}', (date_str,), chain)
    if isinstance(result, dict):
        if sector_type == 'industry':
            return result.get('industries', result) if 'industries' in result else result
        else:
            return result.get('concepts', {}) if 'concepts' in result else {}
    return result

def get_sector_klines(sector_name, sector_type='industry'):
    chain = DATA_SOURCE_CHAINS['sector_klines']
    return _call_with_failover(f'sector_klines_{sector_type}', (sector_name, sector_type), chain, fallback=[])

def get_concept_map():
    chain = DATA_SOURCE_CHAINS['concept_map']
    return _call_with_failover('concept_map', (), chain, fallback={})

# 合并数据内存缓存（TTL=1秒，避免同一批请求反复读6MB文件）
_MERGED_CACHE = {'data': None, 'ts': 0.0}

def get_merged_sector_data():
    """获取合并后的全量板块数据 {last_updated, industries, concepts}
    
    合并策略：EM仓(今日数据) + THS仓(历史K线) + legacy(向后兼容)
    以 legacy 的完整K线优先，EM仓补充今日数据，THS仓补充历史K线
    
    内置1秒内存缓存（非 key 级过期，数据不常变）
    """
    global _MERGED_CACHE
    now = time.time()
    if _MERGED_CACHE['data'] is not None and now - _MERGED_CACHE['ts'] < 1.0:
        return _MERGED_CACHE['data']
    # 1. 先读 legacy（最完整，包含历史K线）
    legacy = _load_json(SECTOR_DAILY_PATH)
    if legacy and 'industries' in legacy:
        result = {
            'last_updated': legacy.get('last_updated', ''),
            'industries': dict(legacy.get('industries', {})),
            'concepts': dict(legacy.get('concepts', {})),
        }
        report_success('legacy_sector')
    else:
        result = {
            'last_updated': '',
            'industries': {},
            'concepts': {},
        }
    
    # 2. THS仓补充历史K线（legacy没有的板块）
    ths = _load_json(SOURCES_THS_SECTOR_DAILY)
    if ths:
        for key in ['industries', 'concepts']:
            ths_container = ths.get(key, {})
            for name, klines in ths_container.items():
                if name not in result[key] and klines:
                    result[key][name] = klines
    
    # 3. EM仓补充今日数据（含change_pct）
    em = _load_json(SOURCES_EM_SECTOR_DAILY)
    if em:
        for key, em_key in [('industries', 'industries'), ('concepts', 'concepts')]:
            em_container = em.get(em_key, {})
            for name, entry in em_container.items():
                if isinstance(entry, dict) and entry.get('date'):
                    if name not in result[key] or not result[key][name]:
                        # 新板块，创建单日K线
                        result[key][name] = [{'date': entry['date'],
                            'open': entry.get('open', 0),
                            'close': entry.get('close', 0),
                            'high': entry.get('high', 0),
                            'low': entry.get('low', 0),
                            'volume': entry.get('volume', 0),
                            'change_pct': entry.get('change_pct', 0)}]
                    elif result[key][name] and result[key][name][-1]['date'] != entry.get('date'):
                        # 已有板块；已有change_pct在`_to_em_format`中已有，不需要追加
                        pass

    _MERGED_CACHE['data'] = result
    _MERGED_CACHE['ts'] = time.time()
    return result

def get_data_source_status():
    health = get_all_health()
    return {
        'sources': health.get('sources', {}),
        'transitions': health.get('transitions', [])[-20:],
        'summary': {
            'total': len(health.get('sources', {})),
            'up': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'UP'),
            'down': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'DOWN'),
            'degraded': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'DEGRADED'),
        }
    }


# ════════════════════════════════════════════════════════════
# 板块涨跌计算（从个股K线 → mootdx，不依赖 push2test f3）
# ════════════════════════════════════════════════════════════

def calc_sector_chg_from_stocks(sector_code: str, date_str: str = None) -> Optional[float]:
    """从个股K线计算板块涨跌幅
    
    获取板块成分股 → mootdx 拉个股日K线 → 等权平均涨跌幅
    不依赖 push2test f3 字段，周末也能拿到历史交易日数据。
    
    Args:
        sector_code: 东财板块代码，如 'BK1039'
        date_str: YYYYMMDD，默认最后一个交易日
    
    Returns:
        等权平均涨跌幅（%），失败返回 None
    """
    if date_str is None:
        date_str = _last_trading_day()
    
    # 1. 从push2test获取成分股代码
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        params = {'pn':'1','pz':'200','po':'0','np':'1',
                  'ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2',
                  'fs':f'b:{sector_code}','fields':'f12,f14'}
        headers = {'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        items = r.json().get('data',{}).get('diff',[])
        if not items:
            return None
        codes = [(it.get('f12',''),it.get('f14','')) for it in items if it.get('f12')]
    except Exception:
        return None
    
    # 2. 从mootdx获取个股K线，计算涨跌幅
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
    except Exception:
        return None
    
    if not date_str or len(date_str) != 8:
        return None
    
    # 前一个交易日
    prev_date = datetime.strptime(date_str, '%Y%m%d')
    for _ in range(7):
        prev_date -= timedelta(days=1)
        if prev_date.weekday() < 5:
            break
    prev_str = prev_date.strftime('%Y%m%d')
    
    changes = []
    for code, name in codes:
        if code.startswith(('9','8','4')):  # 北交所跳过
            continue
        try:
            market = 0 if not code.startswith('6') else 1
            klines = client.bars(symbol=code, category=4, offset=10)
            if klines is None or len(klines) < 2:
                continue
            close_target = close_prev = None
            for i in range(len(klines)-1, -1, -1):
                row = klines.iloc[i]
                ds = str(row.name)[:10].replace('-','')
                if ds == date_str:
                    close_target = row['close']
                elif ds == prev_str:
                    close_prev = row['close']
            if close_target and close_prev and close_prev > 0:
                chg = (close_target / close_prev - 1) * 100
                changes.append(chg)
        except Exception:
            continue
    
    if not changes:
        return None
    return sum(changes) / len(changes)


def get_sector_constituents(sector_code: str) -> List[tuple]:
    """获取板块成分股列表 [(code, name), ...]
    
    用于验证、展示成分股构成。
    """
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        params = {'pn':'1','pz':'200','po':'0','np':'1',
                  'ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2',
                  'fs':f'b:{sector_code}','fields':'f12,f14'}
        headers = {'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        items = r.json().get('data',{}).get('diff',[])
        return [(it.get('f12',''),it.get('f14','')) for it in items if it.get('f12')]
    except Exception:
        return []


# ════════════════════════════════════════════════════════════
# 数据源验证层 — 正确性/及时性/一致性
# ════════════════════════════════════════════════════════════

def verify_data_sources(verbose=True):
    """验证所有数据源的正确性、及时性、缓存一致性

    验证项：
      1. 实时源（push2test）：可调用、数量合理、change_pct 正常
      2. 文件源（EM/THS/legacy）：存在、有效JSON、数据新鲜度
      3. 一致性：实时 vs 文件 change_pct 基本一致

    返回 {"status": "pass"|"fail", "checks": [...], "now": date_str}
    """
    now = datetime.now().strftime('%Y%m%d')
    latest_trade_day = _last_trading_day()
    checks = []
    all_pass = True

    def _check(name, passed, detail):
        nonlocal all_pass
        if not passed:
            all_pass = False
        if verbose:
            tag = '✅' if passed else '❌'
            print(f'  {tag} {name}: {detail}')
        checks.append({'check': name, 'pass': passed, 'detail': detail})

    # ════ 1. 实时源验证（push2test）════
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
        ut = 'bd1d9ddb04089700cf9c27f6f7426281'

        # 行业
        ind_params = {'pn':'1','pz':'2000','po':'1','np':'1','ut':ut,'fltt':'2','invt':'2','fs':'m:90+t:2','fields':'f2,f3,f14'}
        r = requests.get(url, params=ind_params, headers=headers, timeout=15)
        ind_items = r.json().get('data', {}).get('diff', [])
        ind_cnt = len(ind_items)
        ind_ok = ind_cnt > 400 and r.status_code == 200
        _check('push2test行业数', ind_cnt > 400, f'返回{ind_cnt}个 (需>400)')

        # 概念
        con_params = {'pn':'1','pz':'2000','po':'1','np':'1','ut':ut,'fltt':'2','invt':'2','fs':'m:90+t:3','fields':'f2,f3,f14'}
        r2 = requests.get(url, params=con_params, headers=headers, timeout=15)
        con_items = r2.json().get('data', {}).get('diff', [])
        con_cnt = len(con_items)
        _check('push2test概念数', con_cnt > 300, f'返回{con_cnt}个 (需>300)')

        # change_pct 合理性：至少有些非零
        non_zero = sum(1 for it in ind_items for _ in [0] if abs(float(it.get('f3', 0) or 0)) > 0.01)
        _check('行业涨跌幅合理性', non_zero > 0 or _is_weekend(), f'{non_zero}/{ind_cnt}个非零')

        # 采样几个关键板块验证
        ind_data = {}
        for it in ind_items:
            name = (it.get('f14') or '').strip().replace('Ⅱ','').replace('Ⅲ','').replace('D','').strip()
            if name:
                ind_data[name] = float(it.get('f3', 0) or 0)
        for key_sector in ['银行', '半导体', '证券']:
            val = ind_data.get(key_sector)
            _check(f'关键板块[{key_sector}]存在且合理', val is not None and -15 < val < 15,
                   f'change_pct={val}')

    except Exception as e:
        _check('push2test HTTP调用', False, f'异常: {e}')

    # ════ 2. 文件源验证 ════
    for fname, fpath in [('EM仓', SOURCES_EM_SECTOR_DAILY), ('THS仓', SOURCES_THS_SECTOR_DAILY),
                         ('legacy', SECTOR_DAILY_PATH)]:
        if not os.path.isfile(fpath):
            _check(f'{fname}[{os.path.basename(fpath)}] 文件存在', False, '文件不存在')
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            has_ind = bool(data.get('industries'))
            has_con = bool(data.get('concepts'))
            _check(f'{fname}[{os.path.basename(fpath)}] JSON有效', True,
                   f'行业{len(data.get("industries",{}))}个, 概念{len(data.get("concepts",{}))}个')
        except Exception as e:
            _check(f'{fname}[{os.path.basename(fpath)}] JSON解析', False, str(e))
            continue

        # 新鲜度：应等于最后一个交易日
        last_up = data.get('last_updated', '') or data.get('_push2test_updated', '')
        fresh = last_up == latest_trade_day
        _check(f'{fname}[{os.path.basename(fpath)}] 新鲜度(最近交易日<{latest_trade_day}>)',
               fresh, f'last_updated={last_up}')

    # ════ 3. 一致性验证（实时 vs 文件）════
    try:
        em_file = _load_json(SOURCES_EM_SECTOR_DAILY)
        if em_file:
            em_inds = em_file.get('industries', {})
            matched = 0
            for name in list(ind_data.keys())[:30]:  # 前30个采样
                if name in em_inds and abs(em_inds[name].get('change_pct', 0) - ind_data.get(name, 0)) < 0.5:
                    matched += 1
            _check('实时vsEM仓 change_pct 一致性(采样前30)',
                   matched >= 20, f'{matched}/30采样偏差<0.5%')
    except Exception as e:
        _check('一致性验证', False, f'异常: {e}')

    # ════ 汇总 ════
    if verbose:
        print(f'\n{"="*40}')
        print(f'  数据源验证：{"✅ 全部通过" if all_pass else "❌ 存在问题"}')
        print(f'  {sum(1 for c in checks if c["pass"])}/{len(checks)} 项通过')
    return {'status': 'pass' if all_pass else 'fail', 'checks': checks, 'now': now}


def _is_weekend():
    """非交易日无需验证涨跌幅"""
    return datetime.now().weekday() >= 5

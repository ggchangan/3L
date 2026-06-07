#!/usr/bin/env python3
"""
抽象数据层 — 统一数据获取入口，内置故障切换+健康监测

用法：
    from backend.services.data_source import (
        get_sector_rankings, get_sector_klines, get_concept_map, get_data_source_status
    )
"""

import json, os, sys
from datetime import datetime

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

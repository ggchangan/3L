#!/usr/bin/env python3
"""
数据源迁移脚本 — 将 sector_daily.json 拆分为 EM 和 legacy 双仓

用法:
    cd /home/ubuntu/3l-server/server
    python3 scripts/migrate_sector_sources.py
    
输出:
    1. data/sources/em/sector_daily.json — EM仓（push2test今日数据）
    2. data/sources/ths/sector_daily.json — THS仓（历史K线）
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    DATA_DIR, SECTOR_DAILY_PATH,
    SOURCES_EM_SECTOR_DAILY, SOURCES_THS_SECTOR_DAILY,
)


def main():
    if not os.path.isfile(SECTOR_DAILY_PATH):
        print('❌ sector_daily.json 不存在，跳过迁移')
        return
    
    print(f'📖 读取 sector_daily.json ({os.path.getsize(SECTOR_DAILY_PATH)} bytes)...')
    with open(SECTOR_DAILY_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    
    last_updated = raw.get('last_updated', '')
    industries = raw.get('industries', {})
    concepts = raw.get('concepts', {})
    
    print(f'   最后更新: {last_updated}')
    print(f'   行业板块: {len(industries)} 个')
    print(f'   概念板块: {len(concepts)} 个')
    
    # --- 创建 EM 仓（今日数据，含 change_pct） ---
    def _to_em_format(items):
        result = {}
        for name, klines in items.items():
            if not klines:
                continue
            latest = klines[-1]
            prev_close = klines[-2]['close'] if len(klines) >= 2 else latest.get('close', 0)
            change_pct = latest.get('change_pct')
            if change_pct is None and prev_close > 0:
                change_pct = round((latest.get('close', 0) - prev_close) / prev_close * 100, 2)
            
            result[name] = {
                'date': latest.get('date', ''),
                'change_pct': change_pct or 0,
                'close': latest.get('close', 0),
                'prev_close': prev_close,
                'open': latest.get('open', 0),
                'high': latest.get('high', 0),
                'low': latest.get('low', 0),
                'volume': latest.get('volume', 0),
            }
        return result
    
    em_data = {
        'last_updated': last_updated,
        'industries': _to_em_format(industries),
        'concepts': _to_em_format(concepts),
        'source': 'push2test.eastmoney.com',
        'description': '东方财富push2test API — 板块当日行情'
    }
    
    os.makedirs(os.path.dirname(SOURCES_EM_SECTOR_DAILY), exist_ok=True)
    with open(SOURCES_EM_SECTOR_DAILY, 'w', encoding='utf-8') as f:
        json.dump(em_data, f, ensure_ascii=False, indent=2)
    print(f'✅ EM 仓写入: {SOURCES_EM_SECTOR_DAILY}')
    print(f'   行业 {len(em_data["industries"])} 个, 概念 {len(em_data["concepts"])} 个')
    
    # --- 创建 THS 仓（保留完整历史K线） ---
    ths_data = {
        'last_updated': last_updated,
        'version': 'ths-board-kline-v1',
        'industries': {},
        'concepts': {},
        'source': 'akshare(同花顺) — 板块历史K线',
        'description': '保留完整的原始K线序列，供需要历史趋势的模块使用'
    }
    
    for name, klines in industries.items():
        if klines and len(klines) >= 2:
            ths_data['industries'][name] = klines
    for name, klines in concepts.items():
        if klines and len(klines) >= 2:
            ths_data['concepts'][name] = klines
    
    os.makedirs(os.path.dirname(SOURCES_THS_SECTOR_DAILY), exist_ok=True)
    with open(SOURCES_THS_SECTOR_DAILY, 'w', encoding='utf-8') as f:
        json.dump(ths_data, f, ensure_ascii=False, indent=2)
    print(f'✅ THS 仓写入: {SOURCES_THS_SECTOR_DAILY}')
    print(f'   行业 {len(ths_data["industries"])} 个, 概念 {len(ths_data["concepts"])} 个')
    
    # --- 创建 EM 概念映射（从现有 stock_concept.json） ---
    concept_map_path = os.path.join(DATA_DIR, 'map', 'stock_concept.json')
    if os.path.isfile(concept_map_path):
        os.makedirs(os.path.dirname(SOURCES_EM_CONCEPT_MAP), exist_ok=True)
        with open(concept_map_path, 'r', encoding='utf-8') as f:
            concept_data = json.load(f)
        with open(SOURCES_EM_CONCEPT_MAP, 'w', encoding='utf-8') as f:
            json.dump(concept_data, f, ensure_ascii=False, indent=2)
        print(f'✅ EM 概念映射写入: {SOURCES_EM_CONCEPT_MAP} ({len(concept_data)} 条)')
    
    # --- 初始化 source_health.json ---
    from backend.config import SOURCE_HEALTH_PATH
    health_path = SOURCE_HEALTH_PATH
    if not os.path.isfile(health_path):
        initial_health = {
            'sources': {
                'em_sector': {'status': 'UP', 'last_ok': '', 'last_fail': '', 'fail_count': 0, 'total_calls': 0, 'success_rate_pct': 100.0, 'last_error': ''},
                'legacy_sector': {'status': 'UP', 'last_ok': '', 'last_fail': '', 'fail_count': 0, 'total_calls': 0, 'success_rate_pct': 100.0, 'last_error': ''},
                'ths_sector': {'status': 'UP', 'last_ok': '', 'last_fail': '', 'fail_count': 0, 'total_calls': 0, 'success_rate_pct': 100.0, 'last_error': ''},
            },
            'transitions': []
        }
        os.makedirs(os.path.dirname(health_path), exist_ok=True)
        with open(health_path, 'w', encoding='utf-8') as f:
            json.dump(initial_health, f, ensure_ascii=False, indent=2)
        print(f'✅ 健康状态文件初始化: {health_path}')
    
    # --- 打印迁移结果 ---
    print(f'\n{"="*60}')
    print(f'🎉 迁移完成！')
    print(f'{"="*60}')
    print(f'   备份: /home/ubuntu/data/3l/backups/data-source-refactor-*/')
    print(f'   旧文件: {SECTOR_DAILY_PATH}（保持不变）')
    print(f'   EM仓:   {SOURCES_EM_SECTOR_DAILY}')
    print(f'   THS仓:  {SOURCES_THS_SECTOR_DAILY}')
    print(f'   健康:   {health_path}')
    print(f'')
    print(f'   后续步骤: 逐个模块切换到 data_source 抽象层接口')


if __name__ == '__main__':
    main()

"""
构建 同花顺行业板块 → 成分股 映射文件

数据源：MySQL 数据库 ths_index + ths_member 表
输出: data/3l/board_constituents.json
     {board_name: [code, ...], last_updated: 'YYYY-MM-DD'}

与 stock_industry_map.json（个股→GICS行业名）是两套体系，互不依赖。
专供复盘页面的板块领涨股计算使用。
"""
import os, json, time, sys
from backend.data_access.tushare_db import TushareDB
from backend.core.config import DATA_DIR

OUTPUT_PATH = os.path.join(DATA_DIR, 'board_constituents.json')


def build_mapping():
    try:
        db = TushareDB()
    except Exception as e:
        print(f'[ERROR] MySQL 连接失败: {e}', file=sys.stderr)
        sys.exit(1)

    # 1. 获取所有行业板块（type='I'）
    rows = db.query_many('ths_index', where='type=%s', params=('I',))
    board_count = len(rows)
    print(f'THS行业板块(类型I)总数: {board_count}')

    # 查询所有 ths_member 记录按 ts_code 分组
    member_rows = db.query_many('ths_member')
    board_to_codes = {}
    for m in member_rows:
        ts_code = m['ts_code']
        con_code = m['con_code']
        board_to_codes.setdefault(ts_code, []).append(con_code.upper().strip())

    result = {}
    matched = 0
    for row in rows:
        name = row['name']
        ts_code = row['ts_code']
        codes = board_to_codes.get(ts_code, [])
        if codes:
            matched += 1
        result[name] = codes

    # 2. 写入
    output = {
        'boards': result,
        'count': len(result),
        'boards_with_stocks': matched,
        'total_stocks': sum(len(v) for v in result.values()),
        'last_updated': time.strftime('%Y-%m-%d'),
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'完成: {output["count"]}个板块, 含＞0只: {matched}, 总股票条目: {output["total_stocks"]}')
    print(f'输出: {OUTPUT_PATH}')
    print(f'上次更新: {output["last_updated"]}')


if __name__ == '__main__':
    build_mapping()

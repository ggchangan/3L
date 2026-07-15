#!/usr/bin/env python3
"""一次性迁移脚本: config/holdings.json → holdings 表 (user_id=1)"""
import os, sys, json
_script_dir = os.path.dirname(os.path.abspath(__file__))
_server_root = os.path.join(_script_dir, '..', 'server')
for p in [_server_root, os.path.join(_script_dir, '..')]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ['DATA_DIR'] = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')

from backend.data_access.data_layer import save_holdings

CONFIG_HOLDINGS = os.path.join(os.environ['DATA_DIR'], 'config', 'holdings.json')

def main():
    if not os.path.isfile(CONFIG_HOLDINGS):
        print(f"❌ 配置文件不存在: {CONFIG_HOLDINGS}")
        return 1

    with open(CONFIG_HOLDINGS) as f:
        data = json.load(f)

    raw_holdings = data.get('holdings', [])
    if not raw_holdings:
        print("❌ 配置文件中无持仓数据")
        return 1

    # 映射到 DB 字段
    holdings_list = []
    for h in raw_holdings:
        item = {
            'code': h.get('code', ''),
            'name': h.get('name', ''),
            'direction': h.get('direction', ''),
            'target_ratio': h.get('ratio', h.get('target_ratio', 0)),
            'cost_price': h.get('price', h.get('cost_price')),
            'stop_loss_price': h.get('stop_loss_price'),
            'sector': h.get('sector', ''),
        }
        holdings_list.append(item)

    print(f"📋 读取 {len(holdings_list)} 条持仓")
    for h in holdings_list:
        print(f"  {h['code']} {h['name']} | {h['direction']} | {h['target_ratio']}%")

    ok = save_holdings(1, holdings_list)
    if ok:
        print(f"✅ 已写入 holdings 表 (user_id=1)，共 {len(holdings_list)} 条")
    else:
        print(f"❌ 写入失败，已回退 JSON")
        return 1

    # 验证
    from backend.data_access.data_layer import get_holdings
    result = get_holdings(1)
    print(f"✅ 验证: 读取到 {len(result)} 条")
    return 0

if __name__ == '__main__':
    sys.exit(main())

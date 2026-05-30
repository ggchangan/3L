# 手动补齐持仓止损报警

> 适用场景：在持仓页面新增/修改股票后，止损报警未自动同步时

---

## 方式一：重启服务（最简单）

新增持仓后，系统每30秒自动同步。如果等了1分钟还没生效：

```bash
sudo systemctl restart 3l-server
```

重启后系统会重新运行 `_sync_holdings_to_alarms()`，自动为所有带止损价的持仓创建报警。

## 方式二：手动触发同步

```bash
cd /home/ubuntu/3l-server/server
python3 -c "
import json
from backend.services.check_alerts import _sync_holdings_to_alarms
_sync_holdings_to_alarms()
print('同步完成')
"
```

## 方式三：直接编辑 alarms.json

如果前两种方式不生效，可手动操作：

```bash
cd /home/ubuntu/3l-server/server
python3 << 'PYEOF'
import json, os
from datetime import datetime

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
alarms_path = os.path.join(DATA_DIR, 'private', 'alarms.json')
holdings_path = os.path.join(DATA_DIR, 'private', 'holdings.json')

# 读持仓
holdings = json.load(open(holdings_path, encoding='utf-8')).get('holdings', [])
# 读现有报警
alarms_data = json.load(open(alarms_path, encoding='utf-8'))
alarms = alarms_data.get('alarms', [])
existing_codes = {a['stock_code'] for a in alarms if a['type'] == 'price' and a['status'] == 'active'}

# 补齐缺失
for h in holdings:
    code = h.get('code', '')
    if not code or code in existing_codes:
        continue
    sl = h.get('stop_loss_price') or h.get('stop_loss')
    if not sl:
        continue
    alarms.append({
        'id': f"alarm_{code}_{int(datetime.now().timestamp())}",
        'stock': f"{h.get('name','')}({code})",
        'stock_code': code,
        'type': 'price',
        'enabled': True,
        'stop_loss': sl,
        'stop_loss_pct': h.get('stop_loss_pct'),
        'condition': '',
        'created': datetime.now().isoformat(),
        'status': 'active',
        'source': 'holdings_auto',
        'expires_days': 7,
    })
    print(f'补齐: {h.get(\"name\")}({code}) 止损 {sl}')

alarms_data['alarms'] = alarms
json.dump(alarms_data, open(alarms_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'\n完成，共 {len(alarms)} 条报警')
PYEOF
```

## 验证

```bash
# 查看活跃的价格报警
python3 -c "
import json
d = json.load(open('/home/ubuntu/data/3l/private/alarms.json', encoding='utf-8'))
for a in d.get('alarms', []):
    if a['type'] == 'price' and a['status'] == 'active':
        print(f'{a[\"stock\"]} | 止损:{a.get(\"stop_loss\",\"?\")}')
"
```

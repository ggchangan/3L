#!/bin/bash
cd /home/ubuntu/3l-server/server
TQDM_DISABLE=1 /home/ubuntu/3l-server/.venv/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
from backend.services.data_source import verify_data_sources
r = verify_data_sources(verbose=False)
checks = r.get('checks', [])
pass_count = sum(1 for c in checks if c['pass'])
fail_count = sum(1 for c in checks if not c['pass'])
total = len(checks)
status = '✅' if r.get('status') == 'pass' else '❌'
print(f'{status} 数据源验证: {pass_count}/{total}, 失败{fail_count}')
if fail_count > 0:
    for c in checks:
        if not c['pass']:
            print(f'  ❌ {c[\"check\"]}: {c[\"detail\"]}')
"

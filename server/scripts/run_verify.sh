#!/bin/bash
cd /home/ubuntu/3l-server/server
TQDM_DISABLE=1 /home/ubuntu/3l-server/.venv/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
from backend.services.data_source import verify_data_sources
r = verify_data_sources(verbose=False)
total = r['pass_count'] + r['fail_count'] + r['warn_count']
print(f'数据源验证: {r[\"pass_count\"]}/{total}, 失败{r[\"fail_count\"]}, 警告{r[\"warn_count\"]}')
if r['fail_count'] > 0:
    print('❌ 有失败项，请检查日志')
"

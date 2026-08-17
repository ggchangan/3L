#!/bin/bash
# 晚间板块正式数据更新（Tushare ths_daily 15000分）
# 20:00 主跑；22:00 条件补齐（20:00 未齐时）
# 复用 --isolated-stage sectors-backfill（子进程隔离 + 覆盖门禁 + 最近未确认交易日回补）
set -u

STAGE=sectors-backfill
LOG=/home/ubuntu/3l-server/logs/sector-evening.log
MARK=/tmp/3l-sector-confirmed-$(date +%Y%m%d)
PHASE=${1:-main}   # main=20:00 主跑(成功打标记)  catchup=22:00 补齐(已确认则跳过)

cd /home/ubuntu/3l-server/server

run_sectors() {
    TQDM_DISABLE=1 /usr/bin/flock -n /tmp/3l-sector-evening.lock \
        /home/ubuntu/3l-server/.venv/bin/python3 -m backend.core.update_stock_data \
        --isolated-stage "$STAGE" >> "$LOG" 2>&1
}

if [ "$PHASE" = "catchup" ] && [ -f "$MARK" ]; then
    echo "[$(date '+%F %T')] 20:00 已确认 $(date +%Y%m%d) 板块数据，22:00 跳过补齐" >> "$LOG"
    exit 0
fi

echo "[$(date '+%F %T')] 晚间板块更新($PHASE) 开始" >> "$LOG"
if run_sectors; then
    echo "[$(date '+%F %T')] 板块正式数据已确认 $(date +%Y%m%d)" >> "$LOG"
    touch "$MARK"
    exit 0
else
    rc=$?
    echo "[$(date '+%F %T')] 板块更新未通过覆盖门禁（数据未齐），退出码 $rc" >> "$LOG"
    exit "$rc"
fi

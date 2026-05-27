#!/bin/bash
# 3L交易系统 — Docker 容器入口点
#
# 功能：
# 1. 启动 cron 守护进程（用于定时数据更新）
# 2. 启动 web server
set -e

# 检查必填环境变量
if [ -z "$AUTH_USER" ] || [ -z "$AUTH_PASS" ]; then
    echo "ERROR: AUTH_USER 和 AUTH_PASS 必须通过 -e 传入" >&2
    exit 1
fi

# ==== 首次启动：种子数据 ====
# 预置参考数据（如果挂载目录里没有）
if [ ! -f /data/all_a_stocks.json ]; then
    echo "Seeding reference data files..."
    cp /app/all_a_stocks.json /data/all_a_stocks.json 2>/dev/null || true
    cp /app/pinyin_initials.json /data/pinyin_initials.json 2>/dev/null || true
fi

# 创建空配置文件（如果不存在）
mkdir -p /data/private /data/cache /data/charts
[ -f /data/private/watchlist.json ] || echo '[]' > /data/private/watchlist.json
[ -f /data/private/holdings.json ] || echo '{"update_date":"","holdings":[]}' > /data/private/holdings.json
[ -f /data/private/trades.json ] || echo '[]' > /data/private/trades.json
[ -f /data/private/journal_entries.json ] || echo '[]' > /data/private/journal_entries.json
[ -f /data/private/manual_trend_stocks.json ] || echo '[]' > /data/private/manual_trend_stocks.json
[ -f /data/directions.json ] || echo '{"directions":[],"update_date":""}' > /data/directions.json

echo "Data directory ready."
# ==== 种子数据结束 ====

# 启动 cron（定时数据更新）
echo "Starting cron daemon for scheduled data updates..."
service cron start

# 启动 web server
echo "Starting 3L server on port ${PORT}..."
exec python3 server.py --host 0.0.0.0

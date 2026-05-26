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

# 启动 cron（定时数据更新）
echo "Starting cron daemon for scheduled data updates..."
service cron start

# 启动 web server
echo "Starting 3L server on port ${PORT}..."
exec python3 server.py --host 0.0.0.0

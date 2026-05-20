#!/bin/bash
# 重启 3L Web 服务（server.py）
# 用途：一键杀掉旧进程 + 启动新进程 + 健康检查
# 用法：bash /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/restart_server.sh

PORT=8080
WWW_DIR="/home/ubuntu/www"
LOG_FILE="/tmp/www_server.log"
PID_FILE="${WWW_DIR}/server.pid"

echo "🔄 重启 3L Web 服务 (port ${PORT})..."

# 1. 杀掉旧进程
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  杀掉旧进程 PID=$OLD_PID..."
        kill "$OLD_PID" 2>/dev/null
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# 2. 也杀掉其他server.py进程
OLD_PIDS=$(pgrep -f "python3.*server.py" 2>/dev/null)
if [ -n "$OLD_PIDS" ]; then
    echo "  清理残留进程: $OLD_PIDS"
    kill $OLD_PIDS 2>/dev/null
    sleep 1
fi

# 3. 启动新进程
cd "$WWW_DIR" || { echo "❌ 目录不存在: $WWW_DIR"; exit 1; }
nohup python3 server.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"
echo "  新进程 PID=$NEW_PID"

# 4. 等待启动
sleep 2

# 5. 健康检查
if ss -tlnp | grep -q ":$PORT "; then
    echo "✅ 服务启动成功 (port $PORT)"
    echo "   日志: $LOG_FILE"
    echo "   页面: http://localhost:$PORT/review.html"
else
    echo "⚠️  端口 $PORT 未监听，可能启动失败"
    echo "   查看日志: tail -20 $LOG_FILE"
fi

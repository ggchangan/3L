#!/bin/bash
# 3L交易系统 — 一键部署脚本（Docker版）
# 用法: bash deploy.sh [密码]
# 或者: AUTH_PASS=你的密码 bash deploy.sh
#
# 如果未提供密码，脚本会提示输入
# 首次部署约需 5-10 分钟（含数据初始化拉取）
# 支持: docker compose / docker-compose / 直接 docker run 三种方式

set -euo pipefail

IMAGE="ccr.ccs.tencentyun.com/ygys30ds/lll:latest"
DATA_DIR="${HOME}/3l-server/data"
LOG_DIR="${HOME}/3l-server/logs"

echo "=============================================="
echo "  3L 交易系统 — 一键部署"
echo "=============================================="

# ==== 1. 获取密码 ====
if [ $# -ge 1 ]; then
    AUTH_PASS="$1"
else
    unset AUTH_PASS
    while true; do
        read -s -p "请输入登录密码: " AUTH_PASS
        echo
        read -s -p "请再次输入密码确认: " AUTH_CONFIRM
        echo
        if [ "${AUTH_PASS}" != "${AUTH_CONFIRM}" ]; then
            echo "错误：两次输入的密码不一致，请重新输入" >&2
        elif [ -z "${AUTH_PASS}" ]; then
            echo "错误：密码不能为空" >&2
        else
            break
        fi
    done
fi

# ==== 2. 获取 WxPusher 配置（微信报警） ====
echo ""
echo "=> 微信报警配置（WxPusher）"
echo "   注册地址: https://wxpusher.zjiecode.com"
echo "   留空可跳过，之后在前端 /alarm-sounds 页面配置"
echo ""
read -p "WXPUSHER_TOKEN (AT_xxx，留空跳过): " WX_TOKEN
read -p "WXPUSHER_UID (UID_xxx，留空跳过): " WX_UID

# ==== 3. 选择访问端口 ====
echo ""
read -p "访问端口 (默认 80): " PORT
PORT="${PORT:-80}"

# ==== 4. 打开防火墙 ====
echo ""
echo "=> 检查防火墙..."
if command -v ufw &>/dev/null; then
    if sudo ufw status | grep -q "Status: active"; then
        if ! sudo ufw status | grep -q "${PORT}"; then
            echo "   开放端口 ${PORT}/tcp..."
            sudo ufw allow "${PORT}/tcp"
        else
            echo "   端口 ${PORT} 已开放"
        fi
    fi
fi

# ==== 5. MySQL 数据库安装（Docker数据源需要） ====
echo ""
echo "=> 检查 MySQL..."
if ! command -v mysql &>/dev/null; then
    echo "   正在安装 MySQL 8.0..."
    sudo apt-get install -y -qq mysql-server python3-pymysql
    sudo systemctl start mysql
    sudo systemctl enable mysql
    echo "   MySQL 安装完成"
fi

if ! sudo mysql -e "SELECT 1" &>/dev/null; then
    echo "   启动 MySQL..."
    sudo systemctl start mysql
fi

# 建库建用户（幂等）
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS tushare CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'tushare'@'localhost' IDENTIFIED WITH mysql_native_password BY 'tushare_pass';
CREATE USER IF NOT EXISTS 'tushare'@'%' IDENTIFIED WITH mysql_native_password BY 'tushare_pass';
GRANT ALL PRIVILEGES ON tushare.* TO 'tushare'@'localhost';
GRANT ALL PRIVILEGES ON tushare.* TO 'tushare'@'%';
FLUSH PRIVILEGES;
" 2>/dev/null
echo "   MySQL 数据库就绪"

# 从 SQLite 迁移到 MySQL（如果 SQLite 文件存在）
SQLITE_FILE="${DATA_DIR}/tushare.db"
if [ -f "${SQLITE_FILE}" ]; then
    echo "   发现旧 SQLite 数据库，迁移到 MySQL..."
    sudo docker exec 3l-server python3 -m backend.services.migrate_to_mysql 2>/dev/null || \
    echo "   迁移跳过（容器未运行，后续可手动执行）"
fi

# ==== 6. 检查 Docker ====
echo ""
echo "=> 检查 Docker..."
if ! command -v docker &>/dev/null; then
    echo "=> 正在安装 Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "Docker 安装完成"
fi

# ==== 7. 准备数据目录 ====
echo ""
echo "=> 创建数据目录..."
mkdir -p "${DATA_DIR}"/{private,cache,charts,config,computed,public}
mkdir -p "${LOG_DIR}"

# ==== 8. 拉取镜像 ====
echo ""
echo "=> 登录镜像仓库..."
echo "   (账号: 100048956351)"
sudo docker login ccr.ccs.tencentyun.com -u 100048956351 -p ygys30ds

echo "=> 拉取镜像..."
sudo docker pull ${IMAGE}

# ==== 9. 停止旧容器 ====
echo ""
echo "=> 停止旧容器..."
sudo docker stop 3l-server 2>/dev/null || true
sudo docker rm 3l-server 2>/dev/null || true

# ==== 10. 构建环境变量 ====
ENV_OPTS=""
ENV_OPTS="${ENV_OPTS} -e AUTH_USER=admin"
ENV_OPTS="${ENV_OPTS} -e AUTH_PASS=${AUTH_PASS}"
ENV_OPTS="${ENV_OPTS} -e PORT=8080"
ENV_OPTS="${ENV_OPTS} -e DATA_DIR=/data"
ENV_OPTS="${ENV_OPTS} -e LOG_DIR=/app/logs"
ENV_OPTS="${ENV_OPTS} -e LOG_LEVEL=INFO"
# MySQL 连接配置（容器用 host.docker.internal 连宿主机 MySQL）
ENV_OPTS="${ENV_OPTS} -e MYSQL_HOST=host.docker.internal"
ENV_OPTS="${ENV_OPTS} -e MYSQL_PORT=3306"
ENV_OPTS="${ENV_OPTS} -e MYSQL_USER=tushare"
ENV_OPTS="${ENV_OPTS} -e MYSQL_PASSWORD=tushare_pass"
ENV_OPTS="${ENV_OPTS} -e MYSQL_DATABASE=tushare"
if [ -n "${WX_TOKEN:-}" ]; then
    ENV_OPTS="${ENV_OPTS} -e WXPUSHER_TOKEN=${WX_TOKEN}"
fi
if [ -n "${WX_UID:-}" ]; then
    ENV_OPTS="${ENV_OPTS} -e WXPUSHER_UID=${WX_UID}"
fi

# ==== 11. 启动容器 ====
echo ""
echo "=> 启动服务..."

PORT_MAP="${PORT}:8080"
COMPOSE_FILE="${HOME}/3l-server/docker-compose.yml"

if docker compose version &>/dev/null; then
    USE_COMPOSE="docker compose"
    cat > "${COMPOSE_FILE}" <<EOF
services:
  server:
    image: ${IMAGE}
    container_name: 3l-server
    ports:
      - "${PORT_MAP}"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ${DATA_DIR}:/data
      - ${LOG_DIR}:/app/logs
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=${AUTH_PASS}
      - PORT=8080
      - LOG_DIR=/app/logs
      - LOG_LEVEL=INFO
      - MYSQL_HOST=host.docker.internal
      - MYSQL_PORT=3306
      - MYSQL_USER=tushare
      - MYSQL_PASSWORD=tushare_pass
      - MYSQL_DATABASE=tushare
EOF
    echo "   使用 docker compose 启动 (宿主机端口 ${PORT})"
    cd "$(dirname "${COMPOSE_FILE}")"
    sudo ${USE_COMPOSE} up -d

elif command -v docker-compose &>/dev/null; then
    USE_COMPOSE="docker-compose"
    cat > "${COMPOSE_FILE}" <<EOF
version: '3.8'
services:
  server:
    image: ${IMAGE}
    container_name: 3l-server
    ports:
      - "${PORT_MAP}"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ${DATA_DIR}:/data
      - ${LOG_DIR}:/app/logs
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=${AUTH_PASS}
      - PORT=8080
      - LOG_DIR=/app/logs
      - LOG_LEVEL=INFO
      - MYSQL_HOST=host.docker.internal
      - MYSQL_PORT=3306
      - MYSQL_USER=tushare
      - MYSQL_PASSWORD=tushare_pass
      - MYSQL_DATABASE=tushare
EOF
    echo "   使用 docker-compose 启动 (宿主机端口 ${PORT})"
    cd "$(dirname "${COMPOSE_FILE}")"
    sudo ${USE_COMPOSE} up -d

else
    echo "   使用 docker run 直接启动 (宿主机端口 ${PORT})"
    sudo docker run -d --restart unless-stopped \
      --name 3l-server \
      -p "${PORT_MAP}" \
      --add-host host.docker.internal:host-gateway \
      -v "${DATA_DIR}:/data" \
      -v "${LOG_DIR}:/app/logs" \
      ${ENV_OPTS} \
      ${IMAGE}
fi

# ==== 12. 等待服务就绪 ====
echo "=> 等待服务就绪..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:${PORT}/ 2>/dev/null | grep -q 200; then
        echo "   ✅ 服务已就绪 ($((i * 2))s)"
        break
    fi
    sleep 2
done

echo ""
echo "=> 检查容器状态..."
if sudo docker ps --format '{{.Names}} {{.Status}}' | grep -q "3l-server"; then
    sudo docker ps --format '{{.Names}} {{.Status}}' | grep "3l-server"
else
    echo "   ⚠️ 容器可能未正常运行，查看日志: sudo docker logs 3l-server"
fi

# ==== 13. 数据初始化 ====
echo ""
if [ -f "${DATA_DIR}/all_stocks_60d.json" ]; then
    echo "   已有数据文件，跳过初始化。如需强制更新:"
    echo "   sudo docker exec 3l-server python3 -m backend.core.update_stock_data"
else
    echo "=> 首次数据初始化（拉取 A股 K线数据，约 3-5 分钟）..."
    echo "   请耐心等待，不要中断..."
    if sudo docker exec 3l-server python3 -m backend.core.update_stock_data; then
        echo "   ✅ 数据初始化完成"
    else
        echo "   ⚠️ 数据拉取未完全成功"
        echo "   可稍后手动执行: sudo docker exec 3l-server python3 -m backend.core.update_stock_data"
    fi
fi

# ==== 完成 ====
IP_ADDR=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
ACCESS_URL="http://${IP_ADDR}"
if [ "${PORT}" != "80" ]; then
    ACCESS_URL="http://${IP_ADDR}:${PORT}"
fi
echo ""
echo "=============================================="
echo "  ✅ 部署完成！"
echo "=============================================="
echo ""
echo "  访问地址: ${ACCESS_URL}"
echo "  登录账号: admin"
echo "  密码:     (你设置的)"
echo ""
if [ -n "${WX_TOKEN:-}" ] && [ -n "${WX_UID:-}" ]; then
    echo "  微信报警: ✅ 已配置"
else
    echo "  微信报警: ⏭️ 未配置"
    echo "  配置方式: 打开前端 /alarm-sounds 页面"
fi
echo ""
echo "  数据更新: 每个交易日 17:00 自动更新"
echo "  手动更新: sudo docker exec 3l-server python3 -m backend.core.update_stock_data"
echo ""
echo "  查看日志: sudo docker logs -f 3l-server"
echo "  重启服务: sudo docker restart 3l-server"
echo "  MySQL 连接: mysql -h 127.0.0.1 -u tushare -p'tushare_pass' tushare"
echo ""
echo "=============================================="

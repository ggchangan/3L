#!/bin/bash
# 3L交易系统 — 一键部署脚本
# 用法: bash deploy.sh [密码]
# 或者: AUTH_PASS=你的密码 bash deploy.sh
#
# 如果未提供密码，脚本会提示输入

set -euo pipefail

IMAGE="ccr.ccs.tencentyun.com/ygys30ds/lll:latest"
DATA_DIR="${HOME}/3l-server/data"
LOG_DIR="${HOME}/3l-server/logs"
COMPOSE_FILE="${HOME}/3l-server/docker-compose.yml"

echo "=============================================="
echo "  3L 交易系统 — 一键部署"
echo "=============================================="

# ==== 1. 获取密码 ====
if [ $# -ge 1 ]; then
    AUTH_PASS="$1"
elif [ -z "${AUTH_PASS:-}" ]; then
    read -s -p "请输入登录密码: " AUTH_PASS
    echo
fi

if [ -z "${AUTH_PASS:-}" ]; then
    echo "错误：密码不能为空" >&2
    exit 1
fi

# ==== 2. 检查 Docker ====
if ! command -v docker &>/dev/null; then
    echo "=> 正在安装 Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "Docker 安装完成"
fi

# 检查 docker compose（新版 docker 自带）
if ! docker compose version &>/dev/null; then
    if ! command -v docker-compose &>/dev/null; then
        echo "错误：需要 docker compose 或 docker-compose" >&2
        exit 1
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# ==== 3. 准备数据目录 ====
echo "=> 创建数据目录..."
mkdir -p "${DATA_DIR}"
mkdir -p "${LOG_DIR}"

# ==== 4. 生成 docker-compose.yml ====
echo "=> 生成配置..."
cat > "${COMPOSE_FILE}" <<EOF
version: '3.8'

services:
  server:
    image: ${IMAGE}
    container_name: 3l-server
    ports:
      - "8080:8080"
    volumes:
      - ${DATA_DIR}:/data
      - ${LOG_DIR}:/app/logs
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=${AUTH_PASS}
      - PORT=8080
      - LOG_LEVEL=INFO
      - LOG_DIR=/app/logs
    restart: unless-stopped
EOF

echo "   数据目录: ${DATA_DIR}"
echo "   配置:      ${COMPOSE_FILE}"

# ==== 5. 拉取镜像 ====
echo "=> 拉取镜像..."
sudo docker pull ${IMAGE}

# ==== 6. 启动 ====
echo "=> 启动服务..."
cd "$(dirname "${COMPOSE_FILE}")"
sudo ${COMPOSE_CMD} down 2>/dev/null || true
sudo ${COMPOSE_CMD} up -d

echo ""
echo "=============================================="
echo "  ✅ 部署完成！"
echo "=============================================="
echo "  访问地址: http://$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):8080"
echo "  登录账号: admin"
echo "  密码:     (你设置的)"
echo ""
echo "  首次使用请手动触发数据更新："
echo "  sudo docker exec 3l-server python3 -m backend.core.update_stock_data"
echo "  之后每个交易日 17:00 自动更新。"
echo "=============================================="

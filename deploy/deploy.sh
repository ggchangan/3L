#!/bin/bash
# 3L交易系统 — 一键部署脚本（Docker版）
# 用法: bash deploy.sh [密码]
# 或者: AUTH_PASS=你的密码 bash deploy.sh
#
# 如果未提供密码，脚本会提示输入
# 首次部署约需 5-10 分钟（含数据初始化拉取）

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

# ==== 2. 获取 WxPusher 配置（微信报警） ====
echo ""
echo "=> 微信报警配置（WxPusher）"
echo "   注册地址: https://wxpusher.zjiecode.com"
echo "   创建应用 → 获取 APP_TOKEN → 用户管理获取 UID"
echo "   留空可跳过，之后在前端 /alarm-sounds 页面配置"
echo ""
read -p "WXPUSHER_TOKEN (AT_xxx，留空跳过): " WX_TOKEN
read -p "WXPUSHER_UID (UID_xxx，留空跳过): " WX_UID

# ==== 3. 检查 Docker ====
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

# ==== 4. 准备数据目录 ====
echo ""
echo "=> 创建数据目录..."
mkdir -p "${DATA_DIR}"/{private,cache,charts}
mkdir -p "${LOG_DIR}"

# ==== 5. 生成 docker-compose.yml ====
echo ""
echo "=> 生成配置..."

# 构建 environment 块
ENV_LINES="      - AUTH_USER=admin"
ENV_LINES+="\n      - AUTH_PASS=${AUTH_PASS}"
ENV_LINES+="\n      - PORT=8080"
ENV_LINES+="\n      - LOG_LEVEL=INFO"
ENV_LINES+="\n      - LOG_DIR=/app/logs"
if [ -n "${WX_TOKEN}" ]; then
    ENV_LINES+="\n      - WXPUSHER_TOKEN=${WX_TOKEN}"
fi
if [ -n "${WX_UID}" ]; then
    ENV_LINES+="\n      - WXPUSHER_UID=${WX_UID}"
fi

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
$(echo -e "${ENV_LINES}" | sed 's/^/      /')
    restart: unless-stopped
EOF

echo "   数据目录: ${DATA_DIR}"
echo "   配置:      ${COMPOSE_FILE}"

# ==== 6. 拉取镜像 ====
echo ""
echo "=> 拉取镜像..."
sudo docker pull ${IMAGE}

# ==== 7. 启动服务 ====
echo ""
echo "=> 启动服务..."
cd "$(dirname "${COMPOSE_FILE}")"
sudo ${COMPOSE_CMD} down 2>/dev/null || true
sudo ${COMPOSE_CMD} up -d

# 等待启动就绪
echo "=> 等待服务就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8080/api/health 2>/dev/null | grep -q '"ok"\|"healthy"\|"running"'; then
        echo "   服务已就绪"
        break
    fi
    sleep 2
done

# ==== 8. 首次数据初始化（拉取 K线数据） ====
echo ""
echo "=> 首次数据初始化（拉取 A股 K线数据，约 3-5 分钟）..."
echo "   包含: 个股60天 / 中证全指200天 / 行业板块90天"
echo "   请耐心等待，不要中断..."
if sudo docker exec 3l-server python3 -m backend.core.update_stock_data; then
    echo "   ✅ 数据初始化完成"
else
    echo "   ⚠️ 数据拉取未完全成功"
    echo "   可稍后手动执行: sudo docker exec 3l-server python3 -m backend.core.update_stock_data"
fi

# ==== 完成 ====
IP_ADDR=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo "=============================================="
echo "  ✅ 部署完成！"
echo "=============================================="
echo ""
echo "  访问地址: http://${IP_ADDR}:8080"
echo "  登录账号: admin"
echo "  密码:     (你设置的)"
echo ""
if [ -n "${WX_TOKEN}" ] && [ -n "${WX_UID}" ]; then
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
echo "  升级服务: sudo docker pull ${IMAGE} && sudo docker compose -f ${COMPOSE_FILE} up -d"
echo ""
echo "=============================================="

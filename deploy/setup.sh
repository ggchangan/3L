#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# 3L 交易系统 — 一键部署脚本
# 用法: bash deploy/setup.sh /目标目录
# 示例: bash deploy/setup.sh /home/ubuntu/3l-server
# ═══════════════════════════════════════════════════════════════

INSTALL_DIR="${1:-/home/ubuntu/3l-server}"
DATA_DIR="${DATA_DIR:-/home/ubuntu/data/3l}"
SERVER_IP="${SERVER_IP:-$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"

echo "════════════════════════════════════════════"
echo "  3L 交易系统 — 一键部署"
echo "════════════════════════════════════════════"
echo ""
echo "安装目录: ${INSTALL_DIR}"
echo "数据目录: ${DATA_DIR}"
echo "服务器IP: ${SERVER_IP}"
echo ""

# ── 1. 检查系统 ────────────────────────────────
echo "📋 [1/8] 检查系统环境..."
OS="$(uname -s)"
if [ "$OS" != "Linux" ]; then
    echo "❌ 仅支持 Linux"
    exit 1
fi

# 检测包管理器
if command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
else
    echo "❌ 不支持的包管理器（仅支持 apt/yum）"
    exit 1
fi
echo "  包管理器: ${PKG_MANAGER}"

# ── 2. 安装系统依赖 ───────────────────────────
echo "📦 [2/8] 安装系统依赖..."
if [ "$PKG_MANAGER" = "apt" ]; then
    sudo apt update -qq
    sudo apt install -y -qq python3 python3-venv nginx wkhtmltopdf librsvg2-bin curl
elif [ "$PKG_MANAGER" = "yum" ]; then
    sudo yum install -y python3 python3-venv nginx wkhtmltopdf librsvg2 curl
fi
echo "  ✅ 系统依赖安装完成"

# ── 3. 创建目录结构 ───────────────────────────
echo "📁 [3/8] 创建目录结构..."
sudo mkdir -p "${DATA_DIR}"/{private,cache,key_points,knowledge_base,simulation}
sudo mkdir -p "${DATA_DIR}/private/review_archive"
sudo mkdir -p "${INSTALL_DIR}"/{review_charts,charts,files,logs,data/cache}
echo "  ✅ 目录已创建"

# ── 4. 复制项目文件 ───────────────────────────
echo "📂 [4/8] 复制项目文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ "$PROJECT_DIR" != "$INSTALL_DIR" ]; then
    echo "  从 ${PROJECT_DIR} 复制到 ${INSTALL_DIR}..."
    rsync -a --exclude='.venv' --exclude='.env' --exclude='__pycache__' \
          --exclude='*.pyc' --exclude='.git' --exclude='node_modules' \
          "${PROJECT_DIR}/" "${INSTALL_DIR}/"
fi
echo "  ✅ 文件已就绪"

# ── 5. 创建 .env 配置文件 ─────────────────────
echo "🔐 [5/8] 创建 .env 配置文件..."
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    # 生成随机密码
    ADMIN_PASS=$(openssl rand -base64 12 2>/dev/null || echo "change_me_$(date +%s)")

    # 询问微信报警配置
    echo ""
    echo "  微信报警配置（WxPusher，可跳过）："
    echo "    注册: https://wxpusher.zjiecode.com"
    echo "    创建应用 → 获取 APP_TOKEN → 用户管理获取 UID"
    read -p "  WXPUSHER_TOKEN (AT_xxx，留空跳过): " WX_TOKEN
    read -p "  WXPUSHER_UID (UID_xxx，留空跳过): " WX_UID

    cat > "${INSTALL_DIR}/.env" << EOF
# 3L 交易系统配置
WWW_DIR=${INSTALL_DIR}
DATA_DIR=${DATA_DIR}
PORT=8080
SERVER_HOST=127.0.0.1
LOG_LEVEL=INFO
LOG_DIR=${INSTALL_DIR}/logs
AUTH_USER=admin
AUTH_PASS=${ADMIN_PASS}
$(if [ -n "${WX_TOKEN}" ]; then echo "WXPUSHER_TOKEN=${WX_TOKEN}"; fi)
$(if [ -n "${WX_UID}" ]; then echo "WXPUSHER_UID=${WX_UID}"; fi)
EOF
    echo "  ✅ .env 已创建（密码: ${ADMIN_PASS}）"
    echo "  ⚠️  请保存密码并修改 AUTH_PASS"
else
    echo "  ⏭️  .env 已存在，跳过"
fi

# ── 6. Python 虚拟环境 ────────────────────────
echo "🐍 [6/8] 设置 Python 虚拟环境..."
if [ ! -d "${INSTALL_DIR}/.venv" ]; then
    cd "${INSTALL_DIR}"
    python3 -m venv .venv
    .venv/bin/pip install --quiet -r requirements.txt
    echo "  ✅ 虚拟环境已创建"
else
    echo "  ⏭️  .venv 已存在，跳过"
fi

# ── 7. SSL 证书 + Nginx ───────────────────────
echo "🔒 [7/8] 配置 SSL 和 Nginx..."
SSL_DIR="/etc/nginx/ssl"
sudo mkdir -p "${SSL_DIR}"

if [ ! -f "${SSL_DIR}/3l.key" ]; then
    sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${SSL_DIR}/3l.key" \
        -out "${SSL_DIR}/3l.crt" \
        -subj "/CN=${SERVER_IP}" 2>/dev/null
    sudo chmod 600 "${SSL_DIR}/3l.key"
    echo "  ✅ 自签名证书已生成（CN=${SERVER_IP}）"
else
    echo "  ⏭️  证书已存在，跳过"
fi

# 配置 nginx
sudo cp "${INSTALL_DIR}/deploy/nginx-3l.conf" /etc/nginx/sites-available/3l
sudo ln -sf /etc/nginx/sites-available/3l /etc/nginx/sites-enabled/ 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx
echo "  ✅ Nginx 已配置"

# ── 8. Systemd 服务 ───────────────────────────
echo "⚙️ [8/8] 配置 Systemd 服务..."
# 替换用户为运行者
RUN_USER="${SUDO_USER:-$(whoami)}"
sed "s/User=www-data/User=${RUN_USER}/" "${INSTALL_DIR}/deploy/3l-server.service" | \
    sed "s|/home/ubuntu/3l-server|${INSTALL_DIR}|g" > /tmp/3l-server.service
sudo cp /tmp/3l-server.service /etc/systemd/system/3l-server.service
sudo systemctl daemon-reload
sudo systemctl enable 3l-server.service
sudo systemctl restart 3l-server.service

# 等待就绪
sleep 2
HEALTH=$(curl -s http://127.0.0.1:8080/api/health 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")

echo ""
echo "════════════════════════════════════════════"
echo "  服务已就绪（API: ${HEALTH}）"
echo "════════════════════════════════════════════"

# ── 9. 安装定时任务 ────────────────────────────
echo "⏰ 安装 crontab 定时任务..."
crontab "${INSTALL_DIR}/deploy/crontab" 2>/dev/null && \
    echo "  ✅ crontab 已安装（查看: crontab -l）" || \
    echo "  ⚠️ crontab 安装失败，请手动执行: crontab deploy/crontab"
echo ""

# ── 10. 首次数据初始化 ─────────────────────────
echo ""
echo "📊 [10/10] 首次数据初始化（拉取 A股 K线数据，约 3-5 分钟）..."
echo "  包含: 个股60天 / 中证全指200天 / 行业板块90天"
echo "  请耐心等待，不要中断..."
cd "${INSTALL_DIR}" && cd server && python3 -m backend.core.update_stock_data 2>&1 && \
    echo "  ✅ 数据初始化完成" || \
    echo "  ⚠️ 数据拉取未完全成功，可稍后手动执行"
echo ""
echo "  管理地址: https://${SERVER_IP}"
echo "  API健康:  http://127.0.0.1:8080/api/health"
echo "  服务状态: ${HEALTH}"
echo ""
if [ -f "${INSTALL_DIR}/.env" ]; then
    echo "  🔑 用户: admin"
    grep AUTH_PASS "${INSTALL_DIR}/.env" | head -1
fi
echo ""
echo "  常用命令:"
echo "    sudo systemctl restart 3l-server   重启服务"
echo "    sudo journalctl -u 3l-server -f    查看日志"
echo "    cd ${INSTALL_DIR} && bash deploy/backup.sh  手动备份"
echo ""

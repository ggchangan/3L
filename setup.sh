#!/usr/bin/env bash
set -euo pipefail

# 3L 交易系统 — 一键部署脚本
# 用法: bash setup.sh            # 完整安装
#       bash setup.sh --venv     # 只建虚拟环境
#       bash setup.sh --check    # 只检查系统依赖

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/.venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# ──────────────────────────────────────────────
# 检查系统依赖
# ──────────────────────────────────────────────
check_system_deps() {
    echo ""
    echo "═══ 检查系统依赖 ═══"
    local ok=true

    if command -v python3 &>/dev/null; then
        pyver=$(python3 --version 2>&1)
        info "Python: $pyver"
    else
        err "python3 未安装"
        ok=false
    fi

    if command -v wkhtmltopdf &>/dev/null; then
        info "wkhtmltopdf: $(wkhtmltopdf --version 2>&1 | head -1)"
    else
        warn "wkhtmltopdf 未安装 (用于 PDF 生成, 可选)"
    fi

    if command -v rsvg-convert &>/dev/null; then
        info "rsvg-convert: $(rsvg-convert --version 2>&1)"
    else
        warn "rsvg-convert 未安装 (用于SVG转PNG, 可选但推荐)"
    fi

    if [ "$ok" = false ]; then
        err "请先安装缺失的依赖"
        return 1
    fi
    return 0
}

# ──────────────────────────────────────────────
# 创建虚拟环境 + 安装依赖
# ──────────────────────────────────────────────
setup_venv() {
    echo ""
    echo "═══ 创建虚拟环境 ═══"

    if [ -d "$VENV_DIR" ]; then
        warn "虚拟环境已存在: $VENV_DIR"
        read -r -p "是否重建? [y/N] " rebuild
        if [[ "$rebuild" =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            info "跳过虚拟环境创建"
            return 0
        fi
    fi

    python3 -m venv "$VENV_DIR"
    info "虚拟环境创建完成: $VENV_DIR"

    # 激活并安装依赖
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip -q

    if [ -f "$APP_DIR/requirements.txt" ]; then
        pip install -r "$APP_DIR/requirements.txt"
        info "生产依赖安装完成"
    fi

    if [ -f "$APP_DIR/requirements-dev.txt" ]; then
        pip install -r "$APP_DIR/requirements-dev.txt"
        info "开发依赖安装完成"
    fi

    deactivate
}

# ──────────────────────────────────────────────
# 创建 .env (如果不存在)
# ──────────────────────────────────────────────
setup_env() {
    echo ""
    echo "═══ 配置环境变量 ═══"
    if [ -f "$APP_DIR/.env" ]; then
        info ".env 已存在, 跳过"
    else
        cat > "$APP_DIR/.env" << 'ENVEOF'
# 3L 交易系统 — 环境配置
# 复制此文件为 .env 并按需修改

# 项目路径
WWW_DIR=/home/ubuntu/3l-server
DATA_DIR=/home/ubuntu/data/3l

# 服务端口
PORT=8080

# 日志
LOG_LEVEL=INFO
LOG_DIR=/var/log/3l

# GitHub 远程 (用于 git push)
GIT_REMOTE=origin
ENVEOF
        info ".env 创建完成 ($APP_DIR/.env)"
        warn "请检查 .env 中的路径是否正确"
    fi
}

# ──────────────────────────────────────────────
# 安装 systemd 服务
# ──────────────────────────────────────────────
install_systemd() {
    echo ""
    echo "═══ 安装 systemd 服务 ═══"
    local service_name="3l-server.service"
    local service_path="/etc/systemd/system/$service_name"

    if [ -f "$service_path" ]; then
        warn "服务已存在: $service_path"
        read -r -p "是否覆盖? [y/N] " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            info "跳过 systemd 服务安装"
            return 0
        fi
    fi

    sudo tee "$service_path" > /dev/null << SERVICEEOF
[Unit]
Description=3L TradingView Web Server (Port 8080)
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$APP_DIR
Environment=PYTHONPATH=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python $APP_DIR/server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

    sudo systemctl daemon-reload
    info "systemd 服务安装完成: $service_name"
    warn "启动: sudo systemctl start $service_name"
    warn "启用开机自启: sudo systemctl enable $service_name"
    warn "查看日志: journalctl -u $service_name -f"
}

# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
main() {
    echo ""
    echo "╔═══════════════════════════════════╗"
    echo "║    3L 交易系统 — 一键部署          ║"
    echo "╚═══════════════════════════════════╝"

    case "${1:-all}" in
        --check)
            check_system_deps
            ;;
        --venv)
            check_system_deps
            setup_venv
            ;;
        --env)
            setup_env
            ;;
        --systemd)
            install_systemd
            ;;
        all|*)
            check_system_deps
            setup_venv
            setup_env
            install_systemd
            info "部署完成!"
            echo ""
            echo "启动: sudo systemctl start 3l-server"
            echo "停止: sudo systemctl stop 3l-server"
            echo "日志: journalctl -u 3l-server -f"
            echo ""
            ;;
    esac
}

main "$@"

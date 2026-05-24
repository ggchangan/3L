#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════
# 3L 交易系统 — 部署脚本
# 用法: ./deploy/deploy.sh [版本标签]
# 示例: ./deploy/deploy.sh v0.81
# ═══════════════════════════════════════════════

APP_DIR="/home/ubuntu/3l-server"
TAG="${1:-"v$(date +%Y%m%d.%H%M)"}"

cd "${APP_DIR}"

# 1. 备份当前状态
echo "[deploy] 创建部署前备份..."
bash deploy/backup.sh

# 2. 检查 git 是否有未提交更改
if [ -n "$(git status --porcelain)" ]; then
    echo "[deploy] ⚠️  有未提交的更改，先提交..."
    git add -A
    git commit -m "auto-commit before deploy ${TAG}" || true
fi

# 3. 拉取最新代码
echo "[deploy] 拉取最新代码..."
git fetch --tags
git pull --ff-only || {
    echo "[deploy] ❌ git pull 失败，可能有冲突"
    exit 1
}

# 4. 创建版本标签
echo "[deploy] 打标签: ${TAG}"
git tag -f "${TAG}"
git push origin "${TAG}" 2>/dev/null || true

# 5. 重启服务
echo "[deploy] 重启服务..."
sudo systemctl restart 3l-server.service

# 6. 等待就绪并验证
sleep 2
HEALTH=$(curl -s http://127.0.0.1:8080/api/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")

if [ "${HEALTH}" = "ok" ]; then
    echo "[deploy] ✅ 部署成功 (${TAG})"
else
    echo "[deploy] ⚠️  服务状态: ${HEALTH}"
fi

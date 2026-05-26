# 3L交易系统 — Docker 部署指南

> 更新时间：2026-05-27

---

## 前置条件

- 云服务器（建议 Ubuntu 22.04+，2GB 内存）
- 开放端口 8080（防火墙/安全组）

---

## 方式A：一键部署（推荐）

适合不想看细节的同学，两条命令搞定：

```bash
# 1. 下载脚本
curl -O https://raw.githubusercontent.com/ggchangan/3L/feature/deploy-docker/deploy/deploy.sh

# 2. 运行（AUTH_PASS 替换为你的登录密码）
AUTH_PASS=你的密码 bash deploy.sh
```

脚本会自动完成：装 Docker → 创建数据目录 → 拉镜像 → 生成配置 → 启动服务。

---

## 方式B：详细部署步骤

适合想了解每一步在做什么的同学。

### 1️⃣ 安装 Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
```

### 2️⃣ 拉取镜像

```bash
sudo docker pull ccr.ccs.tencentyun.com/ygys30ds/lll:latest
```

### 3️⃣ 创建数据目录

```bash
mkdir -p ~/3l-server/data
mkdir -p ~/3l-server/logs
```

**数据目录无需手动准备文件。** 容器首次启动会自动创建初始配置（空的 watchlist/holdings 等），17:00 定时任务会下载全量行情数据。

启动后目录结构会自动变为：

```
~/3l-server/data/
├── all_a_stocks.json          ← 预置（股票代码→名称映射）
├── pinyin_initials.json       ← 预置（拼音首字母搜索）
├── all_stocks_60d.json        ← 17:00 自动生成
├── index_sh_data.json         ← 17:00 自动生成
├── sector_daily.json          ← 17:00 自动生成
├── board_constituents.json    ← 17:00 自动生成
├── directions.json            ← 空配置（首次启动自动创建）
├── private/                   ← 用户数据
│   ├── watchlist.json         ← 首次空数组，用户自行添加
│   ├── holdings.json          ← 持仓
│   ├── trades.json            ← 交易记录
│   ├── workbench/             ← 工作台数据（自动生成）
│   └── journal_entries.json   ← 工作日志
├── cache/                     ← 运行时缓存（自动生成）
└── charts/                    ← K线图缓存（自动生成）
```

> **提示：** 如果想从你的数据迁移（拷贝自选股等），把对应的 JSON 文件放到 `~/3l-server/data/private/` 目录下再启动容器。

### 4️⃣ 启动服务

**推荐 — 用 docker-compose：**

```bash
cd ~/3l-server
curl -O https://raw.githubusercontent.com/ggchangan/3L/feature/deploy-docker/deploy/docker-compose.yml
AUTH_PASS=你的密码 sudo docker compose up -d
```

**或者 — 用 docker run：**

```bash
sudo docker run -d \
  --name 3l-server \
  -p 8080:8080 \
  -v ~/3l-server/data:/data \
  -v ~/3l-server/logs:/app/logs \
  -e AUTH_USER=admin \
  -e AUTH_PASS=你的密码 \
  --restart unless-stopped \
  ccr.ccs.tencentyun.com/ygys30ds/lll:latest
```

### 5️⃣ 验证

浏览器访问 `http://<服务器IP>:8080/`，用你设置的账号密码登录。

能正常看到页面即部署成功。首次使用建议手动触发一次数据更新：

```bash
sudo docker exec 3l-server python3 -m backend.core.update_stock_data
```

之后每个交易日 17:00 自动更新。

---

## 日常维护

| 操作 | docker-compose 方式 | docker run 方式 |
|:----|:-------------------|:--------------|
| 查看状态 | `sudo docker compose ps` | `sudo docker ps` |
| 查看日志 | `sudo docker compose logs -f` | `sudo docker logs -f 3l-server` |
| 重启 | `sudo docker compose restart` | `sudo docker restart 3l-server` |
| 升级 | `sudo docker compose pull && sudo docker compose up -d` | 停旧容器，重新 run |
| 停掉 | `sudo docker compose down` | `sudo docker stop 3l-server` |

### 数据更新

交易日 17:00 自动更新。如需手动触发：

```bash
sudo docker exec 3l-server python3 -m backend.core.update_stock_data
```

### 备份

数据都在 `~/3l-server/data/` 下，直接备份这个目录：

```bash
tar czf 3l-data-backup-$(date +%Y%m%d).tar.gz ~/3l-server/data/
```

---

## 常见问题

**Q：页面能打开但没有股票数据？**
→ 检查数据目录挂载是否正确。容器的 `/data` 要对应到你的 `~/3l-server/data/`。

**Q：忘记密码了？**
→ 停掉容器，修改 `AUTH_PASS` 环境变量，重新启动。

**Q：怎么看实时日志？**
→ `sudo docker logs -f 3l-server`

**Q：8080 端口被占用了怎么办？**
→ 把 `-p 8080:8080` 改成 `-p 你想要的端口:8080`

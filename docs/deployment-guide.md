# 3L交易系统 — Docker 部署指南

> 给同学或朋友的 5 步部署文档
> 更新时间：2026-05-27

---

## 前置条件

- 一台云服务器（建议 Ubuntu 22.04+，2GB 内存）
- 开放端口 8080（防火墙/安全组）
- 安装 Docker（见第1步）

---

## 第1步：安装 Docker

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y docker.io

# 启动 Docker 并设置开机自启
sudo systemctl enable docker
sudo systemctl start docker
```

---

## 第2步：获取镜像（二选一）

### 方式A：从镜像仓库拉取（推荐）

```bash
sudo docker pull ccr.ccs.tencentyun.com/ygys30ds/lll:latest
```

### 方式B：从文件加载（离线传输）

我这边会把镜像导出为 `3l-server.tar.gz` 发给你。你收到后：

```bash
# 解压
gunzip 3l-server.tar.gz

# 加载到 Docker
sudo docker load -i 3l-server.tar
```

---

## 第3步：准备数据目录

```bash
mkdir -p ~/3l-server/data
mkdir -p ~/3l-server/logs
```

把数据包解压到 `~/3l-server/data/`，目录结构应该是：
```
~/3l-server/data/
├── stock_data/         个股K线数据
├── index_data/         指数数据
├── sector_data/        板块数据
├── private/            私有数据（复盘存档、工作台等）
├── knowledge_base/     知识库
├── all_stocks_60d.json 全量股票数据
├── watchlist.json      自选股列表
└── ...
```

---

## 第4步：运行

方式A — 用 docker run（简单）：

```bash
sudo docker run -d \
  --name 3l-server \
  -p 8080:8080 \
  -v ~/3l-server/data:/data \
  -v ~/3l-server/logs:/app/logs \
  -e AUTH_USER=admin \
  -e AUTH_PASS=你的密码 \
  --restart unless-stopped \
  3l-server:latest
```

方式B — 用 docker-compose（推荐，容易管理）：

先创建 `~/3l-server/docker-compose.yml`：

```yaml
version: '3.8'

services:
  server:
    image: 3l-server:latest
    container_name: 3l-server
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./logs:/app/logs
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=你的密码
    restart: unless-stopped
```

然后启动：

```bash
cd ~/3l-server
sudo docker compose up -d
```

---

## 第5步：验证

浏览器访问 `http://<服务器IP>:8080/`，用你设置的账号密码登录。

能正常看到页面和股票数据即部署成功。

---

## 日常维护

| 操作 | docker run 方式 | docker-compose 方式 |
|:----|:--------------|:-------------------|
| 查看状态 | `sudo docker ps` | `sudo docker compose ps` |
| 查看日志 | `sudo docker logs 3l-server` | `sudo docker compose logs -f` |
| 重启 | `sudo docker restart 3l-server` | `sudo docker compose restart` |
| 升级 | 停掉旧容器，新版本 run | `sudo docker compose pull && sudo docker compose up -d` |
| 停掉 | `sudo docker stop 3l-server` | `sudo docker compose down` |

### 数据更新

系统内置定时任务，**每个交易日 17:00 自动更新行情数据**，无需手动操作。

如果某天数据没更新，可以手动触发：

```bash
sudo docker exec 3l-server python3 -m backend.core.update_stock_data
```

### 备份

数据都在 `~/3l-server/data/` 目录下，直接备份这个目录就行：

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

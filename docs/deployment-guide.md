# 3L交易系统 — Docker 部署指南

> 给同学或朋友的 4 步部署文档
> 更新时间：2026-05-27

---

## 前置条件

- 一台云服务器（建议 Ubuntu 22.04+，2GB 内存）
- 开放端口 8080（防火墙/安全组）
- 安装 Docker（见第1步）

---

## 第1步：装 Docker + 拉取镜像

如果目标机器还没装 Docker，一键脚本会自动安装。直接跑：

```bash
# 下载一键部署脚本
curl -O https://raw.githubusercontent.com/ggchangan/3L/feature/deploy-docker/deploy/deploy.sh

# 运行（会提示输入密码）
bash deploy.sh

# 或者直接传密码（避免交互）
AUTH_PASS=你的密码 bash deploy.sh
```

脚本会帮你完成所有步骤：装 Docker → 创建数据目录 → 拉镜像 → 生成配置 → 启动。

如果用 docker-compose 手动部署：

```bash
# 先装 Docker
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

# 拉取镜像
sudo docker pull ccr.ccs.tencentyun.com/ygys30ds/lll:latest
```

然后创建目录和 docker-compose.yml 按第3~4步。

---

## 第2步：准备数据目录

创建数据目录（挂载到容器 `/data`）：

```bash
mkdir -p ~/3l-server/data
mkdir -p ~/3l-server/logs
```

**数据目录无需手动准备任何文件。** 容器的入口脚本会自动创建初始配置（空的 watchlist/holdings 等），17:00 定时任务会下载全量行情数据。

启动后的目录结构会自动变为：

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

> **提示：** 如果同学想从你的数据迁移（比如从你这里拷贝自选股），可以直接把对应的 JSON 文件放到 `~/3l-server/data/private/` 目录下再启动容器。

---

## 第3步：运行

**推荐方式** — 使用项目自带的 docker-compose.yml：

```bash
cd ~/3l-server
# 如果之前用了 deploy.sh，compose 文件已经生成好了
# 如果手动部署，先下载仓库里的 docker-compose.yml：
curl -O https://raw.githubusercontent.com/ggchangan/3L/feature/deploy-docker/deploy/docker-compose.yml

# 通过环境变量传入密码启动
AUTH_PASS=你的密码 sudo docker compose up -d
```

或者用 `docker run`（更简单，适合不熟悉 compose 的同学）：

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

---

## 第4步：验证

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

# 3L交易系统 — Docker 部署指南

> 更新时间：2026-05-30
> 适用版本：v0.5.1+

---

## 前置条件

- 云服务器（建议 Ubuntu 22.04+，2GB 内存）
- 开放端口 8080（防火墙/安全组）
- 可选：注册 [WxPusher](https://wxpusher.zjiecode.com) 用于微信报警推送

---

## 方式A：一键部署（推荐）

适合不想看细节的同学，两条命令搞定：

```bash
# 1. 下载脚本
curl -O https://raw.githubusercontent.com/ggchangan/3L/master/deploy/deploy.sh

# 2. 运行（按提示输入密码和微信配置）
bash deploy.sh
```

脚本会自动完成：装 Docker → 配置报警 → 拉镜像 → 生成配置 → 启动服务 → 拉取首次数据。

---

## 方式B：详细部署步骤

### 1️⃣ 安装 Docker

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl enable docker && sudo systemctl start docker
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

### 4️⃣ 启动服务

```bash
# 生成 docker-compose.yml
cat > ~/3l-server/docker-compose.yml << 'EOF'
version: '3.8'

services:
  server:
    image: ccr.ccs.tencentyun.com/ygys30ds/lll:latest
    container_name: 3l-server
    ports:
      - "8080:8080"
    volumes:
      - ~/3l-server/data:/data
      - ~/3l-server/logs:/app/logs
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=你的密码
      - PORT=8080
      - LOG_LEVEL=INFO
      - LOG_DIR=/app/logs
      # 微信报警（可选，也可在前端 /alarm-sounds 页面配置）
      # - WXPUSHER_TOKEN=AT_xxxx
      # - WXPUSHER_UID=UID_xxxx
    restart: unless-stopped
EOF

sudo docker compose -f ~/3l-server/docker-compose.yml up -d
```

### 5️⃣ 首次数据初始化

启动后首次需要手动拉取 K线数据：

```bash
sudo docker exec 3l-server python3 -m backend.core.update_stock_data
```

> ⏱ 约 3-5 分钟，包含：个股60天K线 / 中证全指200天 / 行业板块90天
>
> 之后每个交易日 17:00 自动更新。

### 6️⃣ 验证

浏览器访问 `http://<服务器IP>:8080/`，用设置的账号密码登录。

---

## 微信报警配置（WxPusher）

两种方式：

**方式一：部署时配置**（在 `deploy.sh` 交互式输入）

**方式二：前端配置**

1. 登录系统
2. 打开 `/alarm-sounds` 页面
3. 在「微信通知配置」区域输入 Token 和 UID
4. 点「保存」→ 点「发送测试」

WxPusher 注册说明：
- 访问 [https://wxpusher.zjiecode.com](https://wxpusher.zjiecode.com)
- 微信扫码登录
- 创建「应用」→ 获取 `APP_TOKEN`（格式 `AT_xxxx`）
- 「用户管理」→ 获取你的 `UID`（格式 `UID_xxxx`）

---

## 日常维护

| 操作 | 命令 |
|:----|:-----|
| 查看状态 | `sudo docker ps` |
| 查看日志 | `sudo docker logs -f 3l-server` |
| 重启 | `sudo docker restart 3l-server` |
| 数据更新 | `sudo docker exec 3l-server python3 -m backend.core.update_stock_data` |
| 升级服务 | `sudo docker pull ccr.ccs.tencentyun.com/ygys30ds/lll:latest && sudo docker compose -f ~/3l-server/docker-compose.yml up -d` |
| 备份数据 | `tar czf 3l-data-backup-$(date +%Y%m%d).tar.gz ~/3l-server/data/` |
| 停掉服务 | `sudo docker compose -f ~/3l-server/docker-compose.yml down` |

---

## 常见问题

**Q：页面能打开但没有股票数据？**
→ 检查数据目录是否挂载正确。需要首次执行 `update_stock_data`。

**Q：忘记密码了？**
→ 编辑 `~/3l-server/docker-compose.yml` 修改 `AUTH_PASS`，然后重启。

**Q：怎么看实时日志？**
→ `sudo docker logs -f 3l-server`

**Q：8080 端口被占了？**
→ 把 `"8080:8080"` 改成 `"你想要的端口:8080"`

**Q：微信报警没收到？**
→ 检查 Token 和 UID 是否正确，或在前端 `/alarm-sounds` 页面点「发送测试」。

# Docker 打包部署方案

> 目的：给同学部署时不暴露源码，只在服务器上跑 Docker 镜像
> 状态：💤 待讨论

---

## 1. 为什么用 Docker

| 方案 | 源码暴露 | 依赖管理 | 更新方式 | 推荐 |
|:----|:--------|:--------|:--------|:----:|
| 直接 scp 源码 | ❌ 全裸 | 手动装环境 | 手动覆盖 | ✗ |
| 编译成 Linux 可执行文件 | ⚠️ 理论上可逆向 | ✅ 单文件 | 重新编译 | △ |
| **Docker** | ✅ 只有镜像 | ✅ 环境打包 | `docker pull` | **✓** |

## 2. 基本思路

```
3l-server/ (你的开发机)
├── Dockerfile          ← 还没写
├── requirements.txt
├── server.py
├── frontend/dist/      ← 前端构建产物
└── ...

→ docker build -t 3l-server .
→ docker push <仓库>/3l-server:latest

同学服务器：
→ docker pull <仓库>/3l-server:latest
→ docker run -d -p 8080:8080 \
    -v /path/to/data:/home/ubuntu/data \
    -v /path/to/config:/home/ubuntu/3l-server/config \
    --name 3l-server \
    <仓库>/3l-server:latest
```

## 3. 需要注意的点

- **数据目录挂载**：行情数据、缓存、数据库不能打包在镜像里，要挂载宿主机的 volume
- **配置分离**：密钥、端口、环境变量通过 `-e` 或 `.env` 传入，不写死在镜像
- **数据更新**：他那边没有 cron，需要在 Docker 内或宿主机写定时任务跑 update_stock_data.py
- **镜像大小**：依赖多，镜像可能比较大，考虑 alpine 基础镜像或多阶段构建

## 4. 待讨论

- [ ] 镜像放哪？Docker Hub（国内可能慢）还是阿里云/腾讯云容器镜像服务？
- [ ] 他服务器上要不要装 python/node？还是全依赖都在镜像里？
- [ ] 数据更新怎么搞——容器内 crond 还是外置 systemd timer？
- [ ] 多用户隔离？他一个人用一个容器就行，还是需要支持多人同时用？

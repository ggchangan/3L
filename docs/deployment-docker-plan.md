# Docker 打包部署方案

> 目的：给同学部署时不暴露源码，只在服务器上跑 Docker 镜像
> 状态：✅ 已实现（D-01 ~ D-07 已完成，待推送仓库和同学部署）

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

---

## 5. 可执行计划

### Phase 1 — 基础 Docker 化（在你自己的机器上先跑通）

| # | 任务 | 预估 | 前置 |
|:-:|:----|:----:|:----:|
| D-01 | 写 Dockerfile：Python 基础镜像 + 后端依赖 + 前端构建产物 | 1h | — |
| D-02 | 写 .dockerignore：排除 venv/、node_modules/、__pycache__/、.git/ | 0.2h | D-01 |
| D-03 | `docker build -t 3l-server:dev .` 构建成功 | 0.3h | D-01,D-02 |
| D-04 | `docker run` 启动容器，验证后端 API 可访问 | 0.5h | D-03 |
| D-05 | 验证容器内前端页面正常加载（JS/CSS/API调用） | 0.3h | D-04 |
| D-06 | 配置数据目录挂载：`-v /path/to/data:/home/ubuntu/data` | 0.3h | D-05 |
| D-07 | 配置 config 挂载：密钥/端口/env 分离 | 0.5h | D-05 |
| D-08 | 容器内数据更新：写一个 container-cron.sh，运行时自动跑 update 任务 | 0.5h | D-06 |

**验证标准：** ✅ 你在自己机器上 `docker run` 后打开浏览器能正常使用，数据更新正常

### Phase 2 — 镜像分发

| # | 任务 | 预估 | 前置 |
|:-:|:----|:----:|:----:|
| D-09 | 注册阿里云/腾讯云容器镜像服务（选一个） | 0.3h | — |
| D-10 | 本地 `docker tag` + `docker push` 推到镜像仓库 | 0.3h | D-08,D-09 |
| D-11 | 写一份部署文档：同学那边一键执行的命令 | 0.5h | D-10 |

**验证标准：** ✅ 你能从另一台机器 `docker pull` 下来跑通

### Phase 3 — 同学部署

| # | 任务 | 预估 | 前置 |
|:-:|:----|:----:|:----:|
| D-12 | 同学服务器装 Docker | 0.2h | — |
| D-13 | 按部署文档一步步执行，你在旁协助 | 1h | D-11,D-12 |
| D-14 | 验收：同学能正常访问和使用 | 0.5h | D-13 |

### 排期建议

```
第一周：D-01 ~ D-05（把容器跑起来）
第二周：D-06 ~ D-11（配置完善 + 镜像分发）
第三周：D-12 ~ D-14（同学部署）
```

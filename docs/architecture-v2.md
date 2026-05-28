# 3L交易系统 — 架构设计 v2

> 版本: v2.0 | 最后更新: 2026-05-29

---

## 一、仓库结构总览

### 1.1 GitHub 仓库

| 仓库 | 说明 | 服务端目录 |
|:-----|:-----|:----------|
| `ggchangan/3L` | 主仓库（monorepo） | `/home/ubuntu/3l-server/` |
| `ggchangan/3L-miniprogram` | 微信小程序 | `/home/ubuntu/3l-miniprogram/` |

### 1.2 主仓库目录结构

```
3l-server/                    ← 顶层 monorepo (GitHub: ggchangan/3L)
├── server/                   ← 3l-server 主 Web 服务 (systemd, :8080)
│   ├── server.py             ← HTTP 入口（路由注册）
│   ├── backend/
│   │   ├── config.py         ← 集中配置（路径、环境变量、数据目录）
│   │   ├── api/              ← API 路由处理
│   │   │   ├── trend.py      ─ 趋势候选
│   │   │   ├── stock.py      ─ 个股分析
│   │   │   ├── watchlist.py  ─ 自选股
│   │   │   └── system.py     ─ 系统状态
│   │   ├── services/         ← 业务逻辑层
│   │   │   ├── review_service.py  ─ 复盘数据
│   │   │   ├── market_service.py  ─ 大盘/板块/动量
│   │   │   ├── trend_service.py   ─ 趋势交易
│   │   │   └── alarm_service.py   ─ 告警
│   │   ├── core/             ← 主服务特有的核心逻辑
│   │   │   └── trend_candidates.py
│   │   ├── cli/              ← CLI 脚本入口
│   │   └── tests/            ← 后端单元测试
│   ├── frontend/             ← React SPA 前端 (Vite + TypeScript)
│   │   ├── src/pages/        ← 各页面 TSX 组件
│   │   ├── src/components/   ← 共享组件 (StockCard, NavBar)
│   │   └── src/__tests__/    ← 前端组件测试
│   ├── scripts/              ← 运维/工具脚本
│   └── tests/                ← 前端 e2e / 回归报告
│
├── core/                     ← 3l-core 核心逻辑共享包
│   ├── pyproject.toml        ← pip 安装包定义
│   └── threel_core/          ← 共享库代码（pip 包）
│       ├── data_layer.py        ─ 数据层（读 JSON 文件）
│       ├── cache_layer.py       ─ 缓存层
│       ├── buy_point_detection.py  ─ 买点判定
│       ├── trend_trading.py     ─ 趋势交易
│       ├── ema_utils.py         ─ EMA 计算
│       └── __init__.py          ─ 统一导出
│
├── analysis/                 ← 3l-analysis 独立个股分析服务 (Docker, :9090)
│   ├── Dockerfile            ← 容器构建
│   ├── frontend/index.html   ← 独立前端页面（纯 HTML+JS）
│   ├── threel_analysis/      ← 分析服务代码
│   │   ├── card.py           ─ 个股卡片数据
│   │   ├── analysis.py       ─ 分析业务逻辑
│   │   └── server.py         ─ HTTP 服务入口
│   └── .venv/                ← 独立虚拟环境
│
├── data/                     ← 数据目录（软链或挂载）
├── private/                  ← 私有配置（自选股、趋势股等）
├── docs/                     ← 文档
└── tests/                    ← 回归测试 / 截图基线
```

---

## 二、服务组件

### 2.1 3l-server（主服务）

- **进程管理**: systemd (`3l-server.service`)
- **端口**: 8080
- **技术栈**: Python 3.12 http.server + React 19 SPA
- **职责**: 所有主要页面（复盘/盯盘/自选股/趋势候选/个股分析/持仓/工作台）
- **前端**: 单页应用（SPA），各页面按需加载

### 2.2 3l-analysis（独立个股分析服务）

- **进程管理**: Docker (`3l-analysis:latest`)
- **端口**: 9090
- **技术栈**: Python 3.12 http.server + 纯 HTML/JS 前端
- **职责**: 独立的个股分析页面和 API
- **部署**: Docker 容器，数据目录以只读卷挂载

### 2.3 3l-core（共享逻辑库）

- **安装方式**: pip 安装（`pip install core/`），或通过 `PYTHONPATH` 引用
- **版本**: threel-core 0.1.0
- **职责**: 所有服务共享的核心业务逻辑（数据读取、买点判定、趋势交易、EMA 计算）
- **设计原则**: 纯函数、无状态、仅依赖 `requests`

---

## 三、数据流

```
前端页面 (React/HTML)
    │  fetch(/api/...)
    ▼
Nginx (43.136.177.133:443)
    │
    ├── /api/stock-analysis       ───→ Docker(:9090) ──→ 3l-analysis 服务
    ├── /stock-analysis           ───→ Docker(:9090) ──→ 3l-analysis 前端
    └── / (所有其他路由)          ───→ systemd(:8080) ──→ 3l-server 主服务
                                            │
                                     ┌──────┴──────┐
                                     │              │
                            backend/services/    backend/core/
                            (业务逻辑层)        (主服务逻辑)
                                     │
                            core/threel_core/
                            (共享逻辑包 ── 读 JSON 数据)
                                     │
                            /home/ubuntu/data/3l/
                            (数据文件: all_stocks_60d.json 等)
```

### Nginx 路由规则

| 路径 | 目标 | 说明 |
|:-----|:-----|:-----|
| `/stock-analysis` | 127.0.0.1:9090 | 独立个股分析页面 |
| `/api/stock-analysis` | 127.0.0.1:9090 | 个股分析 API |
| `/` | 127.0.0.1:8080 | 主 SPA 所有页面 |

---

## 四、核心架构决策

### 4.1 转发层模式

核心逻辑抽取为 `3l-core` 后，原位置保留转发文件：

```python
# server/backend/core/__init__.py
from threel_core import *   # 旧路径自动转发到新包
```

这样旧代码无需修改 import 语句，新旧共享同一份代码。

### 4.2 数据层设计

- **单一写入口**: 所有数据写操作经 `config.atomic_json_dump()`，保证原子写入
- **缓存策略**: 内存缓存（TTL 10s）+ 文件缓存，小文件直接读
- **路径管理**: 所有路径通过 `DATA_DIR` 环境变量配置，模块级常量统一读取

### 4.3 前端架构

- **框架**: React 19 + TypeScript + Vite
- **SSR**: Node.js 22 服务端渲染，消除白屏时间
- **CSS**: 每页独立 CSS 文件，暗色主题，类名前缀 `.section` / `.info-card` / `.action-btn`
- **组件**: `StockCard` 是唯一个股展示组件，所有上层只做遍历+组装

### 4.4 数据更新管线

- **定时任务**: 17:00 cron 更新所有基础数据（个股 K 线/中证全指/板块 K 线/主线数据）
- **复盘页面**: 只读本地文件，零网络请求
- **增量更新**: 支持非交易日跳过，数据新鲜度检查见回归测试

---

## 五、关键技术指标

| 指标 | 当前值 |
|:-----|:-------|
| 后端测试 | 20 项（CRITICAL） |
| 前端测试 | 95 项（CRITICAL） |
| 个股分析 API 响应 | < 100ms（命中缓存） |
| 前端构建时间 | ~3.5s |
| 数据文件大小 | ~5MB (all_stocks_60d.json) |
| CSS 加载 | ~5-7ms（直读文件，无 modulepreload 竞争） |

---

## 六、部署运维

### 6.1 服务生命周期

```bash
# 主服务
sudo systemctl status 3l-server.service   # 查看状态
sudo systemctl restart 3l-server.service  # 重启
sudo journalctl -u 3l-server -n 50        # 查看日志

# 独立分析服务
sudo docker ps --filter name=3l-analysis  # 查看状态
sudo docker restart 3l-analysis           # 重启
sudo docker logs 3l-analysis --tail 50    # 查看日志
```

### 6.2 前端部署

```bash
cd 3l-server/server/frontend
npm run build                              # 构建 React SPA
sudo systemctl restart 3l-server.service   # 重启主服务
```

### 6.3 Docker 镜像更新

```bash
cd /home/ubuntu/3l-server
sudo docker build -t 3l-analysis:latest -f analysis/Dockerfile .
sudo docker stop 3l-analysis && sudo docker rm 3l-analysis
sudo docker run -d --name 3l-analysis -p 9090:9090 \
  -v /home/ubuntu/data/3l:/data/3l \
  -e DATA_DIR=/data/3l \
  --restart unless-stopped \
  3l-analysis:latest
```

# 3L 交易系统

基于简放 **3L体系**（动量主线 / 最优买点 / 波段操作）的 A 股交易辅助系统。

## 功能

| 功能 | 路由 | 说明 |
|------|------|------|
| **盘中监控** | `/monitor` | 实时行情、量价对比、板块排行、止损提醒、计划报警 |
| **每日复盘** | `/review` | 大盘结构、主线分析、持仓回顾、买点信号 |
| **自选股管理** | `/watchlist` | 增删改方向分组，趋势/3L 双模式 |
| **趋势候选** | `/trend_candidates` | 自动候选 + 手动趋势股管理 |
| **个股分析** | `/stock_analysis` / `/stock-analysis` | 3L 量价分析、K线图、诊断评分、买卖信号 |
| **持仓管理** | `/holdings` | 持仓股追踪 |
| **工作台** | `/workbench` | 每日工作流、计划生成 |
| **逻辑追踪** | `/logic-tracking` | 聚焦分层、前置预判、逻辑关联 |
| **模拟交易** | `/simulation` | 3L 体系模拟交易引擎 |

## 快速开始

### 前置依赖

- Python 3.12+
- Node.js 22+（前端构建）
- Docker（可选，独立分析服务）

### 开发环境

```bash
# 1. 进入 server 目录
cd server

# 2. 创建虚拟环境 + 安装依赖
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 中的 DATA_DIR 等路径

# 4. 构建前端
cd frontend && npm install && npm run build && cd ..

# 5. 启动
.venv/bin/python server.py
```

浏览器打开 `http://localhost:8080`。

### systemd 服务

```bash
sudo cp deploy/3l-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 3l-server
journalctl -u 3l-server -f   # 查看日志
```

## 项目结构（Monorepo）

```
3l-server/                     ← GitHub: ggchangan/3L
├── server/                    ← 主 Web 服务 (systemd, :8080)
│   ├── server.py              ← HTTP 入口
│   ├── backend/               ← Python 后端
│   │   ├── config.py          ← 集中配置
│   │   ├── api/               ← API 路由处理
│   │   ├── services/          ← 业务逻辑层
│   │   ├── core/              ← 主服务特有逻辑
│   │   └── cli/               ← CLI 脚本入口
│   ├── frontend/              ← React SPA 前端 (Vite + TypeScript)
│   ├── scripts/               ← 运维/工具脚本
│   └── tests/                 ← 测试与报告
├── core/                      ← 3l-core 共享逻辑包 (pip)
│   └── threel_core/           ← 数据层、买点判定、趋势交易、EMA 计算
├── analysis/                  ← 独立个股分析服务 (Docker, :9090)
│   ├── Dockerfile
│   ├── frontend/index.html    ← 独立前端页面
│   └── threel_analysis/       ← 分析服务代码
├── docs/                      ← 文档
└── deploy/                    ← 部署脚本 / systemd 配置
```

## 服务架构

```
用户 → Nginx (443)
  ├── /stock-analysis → Docker(:9090) → 独立个股分析
  └── /               → systemd(:8080) → 主 SPA
```

## 数据更新

每天 17:00 通过 cron 自动执行：
1. 拉取全量个股 K 线数据
2. 更新中证全指
3. 更新行业/概念板块 K 线
4. 主线数据计算 + 动量数据

详见 `docs/usage-guide.md`。

## 测试

```bash
# 全回归（CRITICAL + WARNING）
cd server && python3 scripts/run_full_regression.py

# 仅后端
python3 -m pytest backend/tests/ -v

# 仅前端
cd frontend && npx vitest run
```

## 技术栈

- **后端**: Python 3.12 (http.server) + akshare
- **前端**: React 19 + TypeScript + Vite (SSR: Node 22)
- **共享库**: threel-core (pip 包)
- **容器**: Docker（个股分析独立服务）
- **反向代理**: Nginx + 自签名 SSL
- **数据**: JSON 文件（日频更新）

## 文档

- `docs/architecture-v2.md` — 架构设计
- `docs/usage-guide.md` — 使用指南
- `docs/stock-card-logic-design.md` — 个股卡片逻辑设计
- `docs/stock-diagnosis-design.md` — 个股诊断系统设计
- `docs/on-demand-stock-analysis-design.md` — 按需数据拉取设计
- `docs/product-design-v1.md` — 产品设计文档

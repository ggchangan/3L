# 3L 交易系统

基于简放 **3L体系**（动量主线 / 最优买点 / 波段操作）的 A 股交易辅助系统。

## 功能

| 功能 | 说明 |
|------|------|
| **盘中监控** (`monitor.html`) | 实时行情、量价对比、板块排行、止损提醒 |
| **每日复盘** (`review.html`) | 大盘结构、主线分析、持仓回顾、买点信号 |
| **自选股管理** (`watchlist.html`) | 增删改方向，趋势/3L 双模式 |
| **趋势候选** (`trend.html`) | 趋势股筛选、方向分类、信号卡片 |
| **模拟交易** (`simulation.html`) | 3L 体系模拟交易引擎 |
| **个股分析** | 点击代码可查看 K 线图、关键点、买卖信号 |
| **回测** | 买点检测回测、交易明细导出 |
| **知识库** (`kb.html`) | 交易技巧、行业跟踪文档管理 |

## 快速开始

### 前置依赖

- Python 3.12+
- wkhtmltopdf（PDF 生成，可选）
- rsvg-convert（SVG 转 PNG，可选）

### 一键部署

```bash
bash setup.sh
```

或手动：

```bash
# 1. 创建虚拟环境 + 安装依赖
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 修改路径

# 3. 启动
.venv/bin/python server.py
```

### 启动后

浏览器打开 `http://localhost:8080`

### systemd 服务

```bash
sudo cp 3l-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 3l-server
journalctl -u 3l-server -f   # 查看日志
```

## 测试

```bash
make test          # 全测试（不含API）
make test-all      # 全测试（含API）
make test-api      # API 测试（需服务运行中）
```

## 项目结构

```
www/
├── server.py              # HTTP 服务入口
├── config.py              # 集中配置
├── services/              # 业务逻辑层
│   ├── market_service.py
│   ├── monitor_service.py
│   ├── watchlist_service.py
│   ├── review_service.py
│   ├── analysis_service.py
│   ├── backtest_service.py
│   ├── trend_service.py
│   ├── holdings_service.py
│   ├── knowledge_service.py
│   ├── macro_service.py
│   └── top_gainers_service.py
├── scripts/               # 数据采集/分析脚本
├── private/               # 持仓/交易/复盘存档
├── tests/                 # 测试
├── js/ css/               # 前端资源
├── *.html                 # 页面
├── requirements.txt       # 生产依赖
├── requirements-dev.txt   # 开发依赖
├── Makefile               # 构建命令
├── setup.sh               # 一键部署
└── .env.example           # 环境变量模板
```

## 配置

见 `.env.example`，关键项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WWW_DIR` | `/home/ubuntu/www` | 项目根目录 |
| `DATA_DIR` | `/home/ubuntu/data/3l` | 数据存储目录 |
| `PORT` | `8080` | HTTP 服务端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_DIR` | `/var/log/3l` | 日志目录 |

## 技术栈

- Python 3.12 (http.server)
- akshare（A 股数据）
- 前端：原生 HTML/CSS/JS
- 图表：SVG → rsvg-convert / wkhtmltopdf

## License

MIT

# 3L交易系统 — 使用指南

> 版本: v2.1 | 最后更新: 2026-05-29

---

## 一、页面总览

| 页面 | 路由 | 功能 |
|:-----|:-----|:------|
| 🏠 首页 | `/` | 大盘情绪 + 主线结构 + 快速入口 |
| 📊 复盘 | `/review` | 每日复盘，市场结构/主线/个股信号 |
| 👁️ 盯盘 | `/monitor` | 盘中实时监控，四层模型 |
| 📋 自选股 | `/watchlist` | 自选股管理，方向分组，交易系统 |
| 🎯 趋势候选 | `/trend_candidates` | 自动候选 + 手动管理趋势交易股 |
| 📈 个股分析 | `/stock_analysis` | 3L 量价分析（主 SPA） |
| 📈 个股分析 | `/stock-analysis` | 3L 量价分析（独立页面） |
| 📦 持仓 | `/holdings` | 持仓股管理 |
| 💼 工作台 | `/workbench` | 每日工作流 |
| 🔬 逻辑追踪 | `/logic-tracking` | 逻辑追踪系统 |
| 🛠️ 技能 | `/skills` | 系统技能管理 |

---

## 二、数据更新

### 2.1 自动更新（cron）

每天 17:00 自动执行数据更新管线：

| 阶段 | 内容 | 执行方式 |
|:-----|:-----|:---------|
| 1 | 拉取全量个股 K 线数据 | `scripts/fetch_all_stocks.py` |
| 2 | 更新中证全指 | 内置定时器 |
| 3 | 更新行业/概念板块 K 线 | `scripts/refresh_sectors.py` |
| 4 | 主线数据计算 + 动量数据 | `generate_review_data.py` + `fetch_momentum.py` |

cron 路径：`/home/ubuntu/3l-server/server`，使用项目自带 venv。

### 2.2 手动触发

```bash
# 方式一：通过系统状态 API
curl -X POST http://localhost:8080/api/system/update

# 方式二：直接跑脚本
cd /home/ubuntu/3l-server/server
../.venv/bin/python scripts/fetch_all_stocks.py 2>&1
```

---

## 三、趋势候选管理

### 3.1 自动候选

系统根据主线+次主线行业自动识别趋势候选股票，显示在「自动候选」Tab 中。按行业分组，支持翻页。

### 3.2 手动管理

- **搜索加入**: 在搜索框输入代码/名称/拼音首字母，从自选股中搜索并加入趋势跟踪
- **打勾切换**: 候选列表右侧复选框，可直接加入/移除趋势跟踪
- **配置文件**: `private/manual_trend_stocks.json`

### 3.3 查看趋势股

切换「已跟踪」Tab，查看所有已加入趋势跟踪的股票及其状态。

---

## 四、个股分析

### 4.1 主 SPA 页面 (`/stock_analysis`)

SPA 内的个股分析，含导航栏，支持输入代码回车分析。分析结果使用 `StockCard` 组件展示，包含结构/阶段/均线/信号/买点等。

### 4.2 独立页面 (`/stock-analysis`)

轻量级独立页面，不含导航栏，适合外部引用或嵌入。支持 URL 参数 `?q=300750` 直接分析。

### 4.3 按需数据拉取

搜索不在 cron 数据中的股票时（非自选股/非主线板块成分股），系统自动从数据源拉取 60 天 K 线：

- **数据源优先级**：akshare（HTTP）→ mootdx（通达信回退）
- **缓存**：独立文件 `stock_on_demand_cache.json`，TTL=1 天，最多 30 只
- **行业映射**：自动通过 `stock_industry_map.json` 查行业→方向
- **不影响 cron**：不污染 `all_stocks_60d.json`，cron 17:00 不碰此缓存

适用场景：发现某只不在自选股的股票想快速分析，直接搜代码即可。

### 4.4 个股诊断系统

分析结果新增诊断评分区块，展示三维度评定：

| 维度 | 满分 | 说明 |
|:-----|:----:|:-----|
| 📊 趋势面 | 40 | 结构/阶段/信号/主线/买点/乖离率 |
| 💰 财务面 | 40 | ROE/净利润增长/营收增长/负债率 |
| 🛡️ 风险面 | 20 | 净利润下滑/高负债/流动性/趋势风险 |
| 总分等级 | 100 | A(≥85)/B(70-84)/C(55-69)/D(<55) |

财务数据通过 akshare 拉取，1 小时内存缓存。若 akshare 不可用，财务面降级为 0 分。

### 4.5 API 接口

```bash
GET /api/stock-analysis?q=<代码或名称>
```

返回字段：

| 字段 | 说明 |
|:-----|:------|
| `code`, `name` | 股票代码、名称 |
| `structure` | 结构：上升趋势/下降趋势/震荡 |
| `stage` | 阶段：上行/转强/调整/筑底 |
| `ema5`, `ema10`, `ema20`, `ema30` | 各周期均线值 |
| `deviation_pct` | 乖离率 (BIAS5) |
| `vol_ratio` | 量比 |
| `signal` | 信号：buy/hold/sell |
| `trading_system` | 交易系统：3l/trend |
| `buy_point` | 买点类型 |
| `buy_score` | 买点评分 (0-100) |
| `stop_loss` | 止损位 |
| `stop_loss_pct` | 止损百分比 |
| `risk_reward_ratio` | 盈亏比 |
| `mainline_level` | 主线级别 |
| `sector` | 所属板块 |
| `diagnosis` | 诊断对象（v3.4.0+） |
| `diagnosis.total_score` | 总分 (0-100) |
| `diagnosis.grade` | 等级 A/B/C/D |
| `diagnosis.detail.financial` | 财务评分（含 ROE/增长/负债数据） |
| `diagnosis.detail.trend` | 趋势评分 |
| `diagnosis.detail.risk` | 风险评分（含风险项列表） |
| `diagnosis.cost_ms` | 诊断计算耗时 ms |

---

## 五、自选股管理

### 5.1 方向分组

自选股支持方向分组，可在「方向管理」中创建/编辑/删除分组。

### 5.2 搜索添加

输入代码/名称/拼音首字母搜索个股，点击加入自选股，选择方向分组。

### 5.3 批量操作

- 批量设置方向
- 批量移除
- 排序（支持按涨幅降序）

---

## 六、复盘阅读

### 6.1 页面结构

- **市场概况**: 大盘结构 + 阶段判定 + 波峰波谷
- **主线结构**: 主线/次主线/非主线三梯队
- **个股信号**: 持仓股 + 启用自选股的买点信号和卡片数据
- **历史复盘**: 选择历史日期查看

### 6.2 数据加载

复盘页面只读本地文件，无网络请求。数据由 17:00 cron 预生成。

---

## 七、回归测试

### 7.1 运行全回归

```bash
cd /home/ubuntu/3l-server/server
python3 scripts/run_full_regression.py
```

### 7.2 测试分级

| 等级 | 含义 | 不通过影响 |
|:-----|:-----|:-----------|
| CRITICAL | 必须通过 | 阻塞构建 |
| WARNING | 报告但不阻塞 | 风格漂移、设计覆盖率下降 |
| INFO | 仅日志 | 视觉回归结果 |

### 7.3 查看报告

```bash
# 最新报告
cat /home/ubuntu/3l-server/server/tests/reports/latest.md

# 历史报告
ls /home/ubuntu/3l-server/server/tests/reports/
```

---

## 八、常见操作

### 修改前端后部署

```bash
cd /home/ubuntu/3l-server/server
python3 frontend/build.py   # 构建 React SPA
sudo systemctl restart 3l-server.service
```

### 修改分析服务后部署

```bash
cd /home/ubuntu/3l-server
sudo docker build -t 3l-analysis:latest -f analysis/Dockerfile .
sudo docker restart 3l-analysis
```

### 查看服务日志

```bash
sudo journalctl -u 3l-server -n 100 -f     # 主服务实时日志
sudo docker logs 3l-analysis --tail 50 -f  # 分析服务实时日志
```

### 数据目录结构

```bash
/home/ubuntu/data/3l/
├── all_stocks_60d.json          ← 全量个股 60 日 K 线（cron 更新）
├── all_a_stocks.json            ← 全 A 股代码/名称映射（用于搜索）
├── stock_industry_map.json      ← 个股行业映射
├── stock_on_demand_cache.json   ← 按需拉取缓存（独立于 cron）
├── all_sections.json            ← 板块概要
├── watchlist.json               ← 自选股
└── private/                     ← 私有配置
    ├── manual_trend_stocks.json  ← 手动趋势股
    ├── review_data.json          ← 复盘缓存
    └── review_archive/           ← 历史复盘
```

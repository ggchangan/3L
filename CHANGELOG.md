# Changelog

## [v3.5.2] — 2026-05-30

### 修复：Docker 部署前端 404 问题

**根因：** Docker 镜像缺少前端构建产物 + FE_DIR 路径不兼容 Docker 布局。
`COPY server/ .` 将 `frontend/dist/` 放到 `/app/frontend/dist/`，但代码硬编码找 `/app/server/frontend/dist/`。

**改动：**
- **`server/server.py`** — FE_DIR 改为多候选路径探测（原生开发 / Docker 布局）
- **`server/Dockerfile`** — 改为多阶段构建：Stage 1 node:20 编译前端 → Stage 2 python 运行，前端产物编入镜像
- **`server/.dockerignore`** — 移除 `frontend/src/` 等排除规则（多阶段构建的 build stage 需要）
- **`deploy/deploy.sh`** — 密码输入加两次确认循环；支持端口选择(80/8080)；自动开 ufw 防火墙

### 🔧 部署验证
- `GET /` → 200（返回 react SPA）
- SPA 路由 `/monitor` → 200
- 静态资源 JS/CSS → 200
- API `/api/market-health` → 200
- Docker 健康检查通过

## [v3.5.1] — 2026-05-30

### 修复：数据管线 cron 反复失败（第3次根治）

**根因：** `update_stock_data.py` 在 `server/backend/core/` 下，sys.path 用
4 层 dirname 指向项目根目录，但 `backend` 包在 `server/` 子目录下。
cron 始终找不到 `backend` 模块，数据停留在旧日期。

**改动：**
- **`update_stock_data.py`** — sys.path 改为 3 层 dirname 指向 `server/`，加注释注明
- **5 个 logic service 文件** — 同一类 sys.path 问题修复（logic_high_scanner / feed / zt / verify / p1）
- **crontab** — cd 目录从项目根改为 `server/`（匹配 `-m backend.core.update_stock_data`）
- **`docs/usage-guide.md`** — 数据更新章节全面重写：准确 cron 配置、手动执行指南、新鲜度检查、失效排查步骤、已知坑
- **`data-pipeline` skill** — 新增"cron 反复失败"陷阱文档

**手动修复（已执行）：** 数据已手动更新到 2026-05-29（周五），全部三项数据（个股/指数/板块）最新。

## [v3.5.0] — 2026-05-29

### 重构：微信推送去 Hermes 依赖，改用 WxPusher 直推

**报警消息不再依赖 Hermes agent / cron job，后端检测到触发时直接通过 WxPusher API 推送微信。**

#### 改动

- **新模块 `wxpush_sender.py`**：WxPusher HTTP API 对接，`send_alert()` / `send_alert_batch()` 直推微信
- **`check_alerts.py` 重构**：删除 `_format_wechat_msg()` / `WECHAT_PUSH_PATH`，`_push_wechat()` 直接用 `send_alert_batch()` 发微信
- **`.env` 新增**：`WXPUSHER_TOKEN=AT_SazEHFvo4fy6EYk1rCDCx31bWhzB12MP`, `WXPUSHER_UID=UID_LPkG96qVOpg2teQgnqbeG7SpzdHM`
- **新 API**：`GET /api/wxpush/status`、`POST /api/wxpush/config`、`GET /api/wxpush/test`
- **前端配置页**：报警音乐配置页新增「微信通知配置」区块，支持在线配置 UID + 发送测试
- **Hermes cron job 已删除**：`92952344f75f`（报警微信投递，每3分钟）
- **测试已更新**：`test_format_wechat_msg_contains_all_alarms` → `test_send_alert_batch_handles_triggered`
- 64 项全回归通过

#### 架构变化

```
之前: 检测触发 → 写文件 → hermes cron run → 微信
现在: 检测触发 → requests.post(WxPusher) → 微信（零依赖）
```

## [v3.4.0] — 2026-05-29

### 新增：按需个股数据拉取 + 三维度诊断系统

**按需拉取未缓存股票 K 线数据，个股分析页面现在可以搜索任意 A 股。新增趋势/财务/风险三维度评分引擎。**

#### 功能

- **按需个股数据拉取**：搜索未在 cron 数据中的股票时，自动通过 akshare（HTTP）或 mootdx（通达信）拉取 60 天 K 线
  - 独立缓存 `stock_on_demand_cache.json`，TTL=1 天，最多保留 30 只
  - 不污染主数据文件 `all_stocks_60d.json`，cron 不碰
  - 自动按 `stock_industry_map.json` 映射行业方向
- **三维度诊断系统**：个股分析结果新增 `diagnosis` 字段
  - **财务面**(40分)：ROE、净利润增长率、营收增长率、资产负债率
  - **趋势面**(40分)：结构/阶段/信号/主线/买点/乖离率
  - **风险面**(20分)：净利润下滑、高负债、流动性差、趋势评分低
  - 总分 A(≥85)/B(70-84)/C(55-69)/D(<55) 四级评定（akshare 财务数据 1h 缓存）
- **主 SPA + 独立页面同步展示诊断**：评分条 + 4 列卡片（趋势/财务/风险/消息） + 优势/注意文字

#### 文档

- `docs/on-demand-stock-analysis-design.md` — 按需数据拉取设计文档 v0.1
- `docs/stock-diagnosis-design.md` — 诊断系统设计文档 v0.1

#### 测试

- `test_on_demand_stock.py` 20 项全通过（缓存管理/akshare拉取/方向映射/过期清理）
- `test_diagnosis_service.py` 20 项全通过（评分/分级/异常降级）
- 全回归 40+ 项新增测试全部通过

#### 修复

- 独立分析页 `/stock-analysis` 路径在 Docker 容器中 404 — 增加 rewrite 映射到内部 `/stock_analysis`
- API 路由 `/api/stock-analysis` 改走主服务(:8080)以使用最新诊断+按需功能
- analysis/server.py 增加 `/stock-analysis` 和 `/stock-analysis.html` 路径识别

---

## [v3.3.0] — 2026-05-29

### 重构：Monorepo 结构重组（extract-core）

**将原本扁平的仓库重组为 server/core/analysis 三层 monorepo，核心逻辑抽为共享包，新增独立个股分析服务。**

#### 仓库结构

- **server/** Web 主服务（原代码移入）
- **core/** 3l-core 共享逻辑包（data_layer / cache_layer / buy_point_detection / trend_trading / ema_utils）
  - 转发层模式：旧 `backend/core/__init__.py` 自动转发到 `threel_core`
- **analysis/** 独立个股分析 Docker 服务（:9090）

#### 新增

- **独立个股分析页面** `/stock-analysis`：轻量级纯 HTML 页面，不含导航栏，可 `?q=300750` 直达
- **Docker 部署**：3l-analysis 容器，数据卷只读挂载
- **Nginx 路由**：`/stock-analysis` + `/api/stock-analysis` → :9090
- **架构设计文档** `docs/architecture-v2.md`
- **使用指南** `docs/usage-guide.md`

#### 修复

- 个股分析页面初始状态去 spinner 误导
- `fetch_momentum.py` 路径修正（market_service + review_service）
- 复盘页买点信号丢失（路径重构导致 import 失败）

#### 样式

- 趋势候选搜索框统一个股分析渐变面板样式
- 趋势候选面板扩展包裹搜索+Tab+卡片+分页整个区域

#### 功能

- 个股分析两个页面支持拼音首字母自动补全搜索
- 独立页面搜索框居中 + 增加 K 线图 + 完整交易系统信息

#### 测试

- 前端 95 项 + 后端 20 项 CRITICAL 全部通过
- 全回归脚本 `scripts/run_full_regression.py`

---

## [v3.2.0] — 2026-05-28

### 改进：PlanLayer 报警拆分为两区块

**持仓止损 + 计划报警分开展示，持仓止损自动读持仓数据，计划报警过滤重复。**

- **🔴 持仓止损**（新增区块）：从复盘持仓数据实时读取止损价，自动展示
  - 每只带止损的持仓股自动显示：止损价、偏离百分比、现价
  - 不依赖 alarms.json，持仓有止损就显示
- **🟡 计划报警**（原报警清单改进）：从 alarms.json 读取，过滤掉已在持仓止损展示的价格报警
  - 偏差报警、时间报警、非持仓股的止损报警保留
  - 避免同一只股的价格报警重复出现
- **技术改动**：PlanLayer 新增 `fetchReviewToday()` 并行加载持仓数据，过滤逻辑纯前端
- **可折叠**：今日计划、实时信息两个区块标题可点击折叠/展开，减少滚动

## [v3.1.0] — 2026-05-28

### 新增：独立持久化报警系统

**报警现在独立存储，不再跟随每日计划文件过期。**

- **alarm_service.py**：新增 `data/private/alarms.json` 持久化报警存储
  - `save_alarm()` / `remove_alarm()` / `mark_alarm_triggered()` / `get_active_alarms()`
  - `sync_alarms_from_plan()` — 工作台保存时自动同步
  - 报警状态：active → triggered / disabled / expired
  - 默认有效期7天，触发了自动标记
- **check_alerts.py**：改从 `alarms.json` 读取报警配置，不再依赖每日日志文件
  - 价格报警、偏差报警统一检查
  - 触发的自动标记状态为 triggered，5分钟内不重复弹
  - 核心股自动偏差报警（direction_service）保持并行
- **alarms API**：`GET /api/alarms/list` 返回生效报警、`POST /api/alarms/remove` 删除
- **workbench API**：保存日志后自动调用 `sync_alarms_from_plan()` 同步到 alarms.json
- **PlanLayer（盯盘）**：新增 🔔 报警清单区块，显示所有生效中报警（类型、股票、止损/阈值）
- **测试**：新增 `test_alarm_service.py` 11个 + 重构 `test_check_alerts.py` 9个
- 全回归：665 passed / 2 skipped / 1 xfailed

### 修复：盘中买点扫描只有趋势信号，3L买点全漏

**根因：** `get_stock_card()` 传入实时K线（含预估全天成交量），但3L买点检测 `detect_buy_point()` 内部从 `get_all_stocks()` 读取了数据层的旧K线，旧K线没有预估成交量，量比算不对，所有3L买点（突破/中继/涨停回踩）全部漏掉。

- **stock_card_service.py**：外部传 `klines` 参数时，覆盖 `all_stocks` 字典中对应股票的K线，`detect_buy_point` 现在用实时K线检测
- **restore scan_buy_signals.py shim**：`scripts/` 目录清理时被误删，恢复指向 `backend.core.scan_buy_signals` 的shim
- **测试**：新增 `test_external_klines_overrides_all_stocks_for_detect_buy_point`
- 修复后扫描结果：1个趋势信号 → **11个信号（突破买点×8 + 中继买点×3 + 趋势×1）**

---

## [v3.0.1] — 2026-05-28

### 修复：板块数据管线 + 主线持续天数跟踪

- **板块akshare加日期参数**：`_fetch_sector_klines_akshare()` 和 `refresh_sectors.py` 传 `start_date`/`end_date`，否则akshare默认只返回到2024年数据
- **板块只拉90天存60天**：不再从2020年起拉全量，改为90天前到今天，存60条
- **cron只拉原始数据**：删除阶段4（主线计算），主线计算改由页面首次加载时按需完成
- **主线轮动/持续天数**：新增 `mainline_history.json` 每日记录top10，`track_mainline_persistence()` 逐日回溯计算连续在榜天数
- **关注买点字段修复**：`generate_trading_plan()` 缺传 `change`/`name`/`is_main`/`profit_model1`/`trend_stock`，导致Plan区只显示"%"标签
- **排序修正**：个股操作按优先级高→中→低；关注买点按主线级>趋势状态>涨幅降序

### 测试

- 新增 `tests/test_sector_update.py` 9个测试（列名兼容性、日期参数验证、MAX_K裁剪）
- 全回归 645 passed / 2 skipped / 1 xfailed

---

## [v3.0.0] — 2026-05-24

### 重构：运维部署 + 独立化（Phase 0）

- `requirements.txt` / `requirements-dev.txt`：完整依赖清单
- `.env.example`：环境变量模板，config.py 改为从 `.env` 读取
- `setup.sh`：一键部署脚本（创建 venv、安装依赖、配置 systemd）
- `Makefile`：统一构建命令（`make install/run/test/lint`）
- `3l-server.service`：systemd 服务文件，指向本地 venv
- `.gitignore` 忽略 `.env` / `.venv` / `.hermes`
- `README.md` / `CHANGELOG.md`：项目文档

### 修复

- `test_services.py` 12 个失败测试（mock 路径/参数顺序/异常捕获）
- 新增 10 个 service 层测试（holdings/knowledge/watchlist）

### 依赖变化

- 新增 `fpdf2==2.8.7`（之前可能只依赖 Hermes 环境）
- `PYTHONPATH` 不再需要指向 Hermes site-packages

---

## [v2.0.0] — 2026-05-23

### 重构：架构优化（Phase 1 + 2）

- server.py import 提顶：35 个内联 import 移到模块顶部
- 所有 API URL 统一为相对路径
- CSS 抽取独立文件，版本号管理
- archive 清理，旧占位文件移除
- 数据安全：私有数据不暴露到前端

### 修复

- 修复 3 个 API 测试（sectors, industry-boards, buy-signals）
- 全回归 196 passed / 2 skipped
- 新增 68 个 stock_card 单元测试

---

## [v1.0.0] — 2026-04

初始版本：3L 交易系统基础功能上线。

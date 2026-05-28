# Changelog

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

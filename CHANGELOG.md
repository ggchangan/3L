# Changelog

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

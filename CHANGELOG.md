# Changelog

## [v3.9.1] — 2026-06-07

### 修复：行业板块数据源切回同花顺 THS

**问题：** 之前将行业数据源从同花顺 THS 切换到 push2test，但同花顺行业数据一直稳定好用，不应被替换。

**改动：**
- `update_sectors()`: 行业（industries）切回同花顺 `stock_board_industry_summary_ths()`，概念（concepts）保留 push2test（同花顺无批量概念接口）
- `data_source.py`: 新增 `_fetch_ths_live_sector_ranking()`，加入数据源链首位
- 补数据：周日非交易日用 THS 写入周五准确数据到 `_push2test.industries`

**数据优势（THS vs push2test）：**
| 字段 | THS（新） | push2test（旧） |
|:-----|:---------|:---------------|
| 涨跌幅% | ✅ 90个行业 | ✅ 含概念 |
| 上涨/下跌家数 | ✅ 新增 | ❌ |
| 领涨股 | ✅ 新增 | ❌ |
| 净流入 | ✅ 新增 | ❌ |
| 名字后缀 | 无（电子化学品） | 有（电子化学品Ⅱ） |

**分层验证：** L1~L3 全部通过（23/23），详见 `docs/data-source-verification/design.md`

## [v3.9.0] — 2026-06-04

### 新增：方向分层系统补充功能 — 重命名/移动/拼音搜索/自动同步

基于 direction-hierarchy 分支，补全方向分层系统的必要交互功能：

**方向管理新功能：**
- `rename_category(old_name, new_name)` — 重命名大类，自动更新所有 sub_directions key 和 watchlist 引用
- `rename_sub_direction(category, old_name, new_name)` — 重命名细分方向，自动更新 watchlist
- `move_sub_direction(category, sub_name, new_category)` — 将细分方向移动到另一个大类，自动更新 watchlist
- `_update_watchlist_on_key_change(old_key, new_key)` — 内部辅助函数，同时兼容 `directions` 数组（新格式）和 `direction` 字符串（旧格式）
- `set_sub_direction_enabled` 新增 V1 key 回退兼容（当 V2 格式 key 找不到时，尝试用 V1 无前缀格式查找）

**搜索增强：**
- `search_concepts(q)` 返回格式改为 `{code: {name, stock_count}}` 字典（之前是 `{code: name}`）
- 新增拼音首字母模糊匹配（pypinyin 库），如输入 `"xpgn"` 可匹配 `"芯片概念"`
- 支持代码精确匹配

**新增 API 端点：**
- `POST /api/directions/category/rename` — `{old_name, new_name}` 重命名大类
- `POST /api/directions/sub/rename` — `{name, new_name}` 重命名细分方向
- `POST /api/directions/sub/move` — `{name, new_category}` 移动细分方向

**路由注册：**
- `server/server.py` 中新增 3 条 POST 路由注册，映射到 `backend.api.directions` 的对应 handler

**单元测试：**
- `test_direction_service.py` — 从 53 个→69 个测试（+16）：重命名空名/重复/已存在、移动细分方向、watchlist 同步、拼音搜索、`_update_watchlist_on_key_change` 双格式兼容
- `test_direction_api.py` — 从 26 个→39 个测试（+13）：`_handle_category_rename`、`_handle_sub_rename`、`_handle_sub_move` 及各种错误情况
- 全部 108 个测试通过

**设计文档更新：**
- `docs/direction-hierarchy/design.md` — 更新 4.1 架构图（新增 rename/move/reorder_categories）、4.3 API 表（新增 5 个端点）、6.3 文件清单、6.4 变更日志

### 修复
- 修复 `test_search_concepts_returns_results` — `search_concepts` 返回格式已变为 `{code: {name, stock_count}}` 字典
- 修复测试 fixture 中 `DATA_DIR` 和 `CONCEPT_LIST_PATH` 未指向临时目录的问题，确保 `_update_watchlist_on_key_change` 和 `search_concepts` 在测试中使用正确路径

---

## [v3.8.1] — 2026-06-01

### 新增：P3 关键点×关键信号融合判定引擎（后端完成）

实现《量价原理》5.7节的完整融合框架：

**融合引擎：** `server/backend/core/signal_detector/fusion.py`
- 8条判定规则覆盖所有组合场景
- 9个信号检测器自动运行，取置信度最高者
- 关键点方向判定（结构/阶段/EMA/BIAS → bullish/bearish/neutral）

**8条融合规则：**

| 规则 | 关键点方向 | 信号方向 | 结果 |
|:----|:---------:|:--------:|:----|
| strong_buy | 看多 | 看多 + 已有买点 | 🟢 强买入 |
| signal_buy | 看多 | 看多 | 🟢 买入 |
| conflict_bearish | 看多 | 看空 | ⚠️ 警惕 |
| signal_sell | 看空 | 看空 | 🔴 卖出 |
| conflict_bullish | 看空 | 看多 | ⚠️ 等确认 |
| buy_point_only | 看多 | 无信号 | ⏳ 谨慎持有 |
| ignore_signal | 中性 | 有信号 | ❌ 假信号忽略 |
| balance | - | 无信号 | ⏳ 正常持有 |

**集成范围：**
- `get_stock_card()`: 新增 triggered_signals/fusion_type/fusion_reason 字段
- `_build_conclusion()`: 融合判定优先于静态结论
- `holdings_service`: 持仓数据传递融合字段

## [v3.8.0] — 2026-06-01

### 新增：中继信号补全 + 全量9信号回测

基于《量价原理》5.6节，补全最后2个中继信号，实现全部9大量价信号检测：

**新增信号：**
- **下跌中继**（`downward_continuation`）：下降趋势中缩量反弹至压力位，成交量不能持续+价格回到均线附近
- **区间震荡中继**（`range_continuation`）：顶部放量滞涨+底部放量滞跌，价格无法突破震荡区间

**全量9信号回测结果：**

| 信号 | 触发 | 5日方向 | 均盈亏 | 评价 |
|:----|:---:|:------:|:-----:|:----|
| **向上突破** | 123次 | 68.2%涨 | +4.51% | ✅ 好 |
| **上涨中继** | 650次 | 61.0%涨 | +3.59% | ✅ 好 |
| **向上反转** | 27次 | 57.1%涨 | +3.79% | ✅ 好 |
| 向下突破 | 13次 | 40.0%跌 | +1.25% | ⚠️ 偏弱 |
| 向下反转 | 42次 | 41.7%跌 | -0.71% | ⚠️ 方向待优化 |
| 需求衰竭 | 805次 | 54.6%涨 | +1.23% | ⚠️ 非主线+高分可用 |
| 供应衰竭 | 10次 | 20.0%涨 | -0.98% | ❌ 样本不足 |
| 下跌中继 | 59次 | 35.9%跌 | +0.01% | ⚠️ 方向偏 |
| 区间震荡中继 | 196次 | 50.0%涨 | +0.32% | ⚠️ 随机 |

**关键发现：**
- 上涨趋势信号（向上突破/上涨中继/向上反转）表现稳定，5日胜率57-68%
- 下降趋势信号（向下突破/向下反转）方向偏弱，因60天窗口内强势股回调后仍能涨回
- 需求衰竭在非主线板块有效（52.1%跌），高分信号(90+)独立有效（69.2%跌）
- 向下反转在非主线+上涨趋势中30.0%跌，勉强可用

**设计文档更新：**
- `docs/signal-detector/design.md` — 新增5.7节关键点×关键信号辩证关系

**单元测试：**
- `tests/test_signal_detectors.py` — 16个测试全部通过
- `tests/test_new_continuation.py` — 新增下跌中继+区间震荡中继测试

**文件清单：**
- `server/backend/core/signal_detector/downward_continuation.py` — 新实现
- `server/backend/core/signal_detector/range_continuation.py` — 新实现
- `server/backend/core/signal_detector/__init__.py` — 注册2个新信号

## [v3.7.0] — 2026-06-01

### 新增：六大关键信号检测系统（P1完成）

基于《量价原理》5.6节原文规则，实现全部6大量价信号的程序化检测：

**新信号实现：**
- **向下突破**（`downward_breakout`）：区间震荡中跌破前低+放量+大阴线
- **向下反转**（`downward_reversal`）：上涨趋势中不再创新高+放量长阴/阴包阳+跌破EMA5
- **需求衰竭**（`demand_exhaustion`）：两种形态——加速(连续大阳线+斜率陡峭+BIAS20>8%) 和 缩量滞涨(成交量跟不上+价格停滞+平顶)
- **供应衰竭**（`supply_exhaustion`）：下降趋势中缓跌后急跌+放量大跌+恐慌抛售

**回测框架升级：**
- 改造 `backtest.py` v2，支持按结构分层回测（主线板块/非主线 + 趋势方向）
- 结构分层结果写入设计文档

**关键回测结论：**
- 需求衰竭在非主线板块上52.1%概率跌，90分以上69.2%概率跌
- 主线板块上需求衰竭是假信号（60.5%继续涨）
- 供应衰竭样本不足，需200天以上窗口

**单元测试：**
- `tests/test_signal_detectors.py`，16个测试全部通过
- 覆盖7个信号检测器的基本逻辑验证

**文件清单：**
- `server/backend/core/signal_detector/downward_breakout.py` — 新实现
- `server/backend/core/signal_detector/downward_reversal.py` — 新实现
- `server/backend/core/signal_detector/demand_exhaustion.py` — 重写（原文规则）
- `server/backend/core/signal_detector/supply_exhaustion.py` — 重写（原文规则）
- `server/backend/core/signal_detector/backtest.py` — 升级v2（分层回测）
- `docs/signal-detector/design.md` — 更新（结构分层+回测结果）
- `tests/test_signal_detectors.py` — 新增

## [v3.6.0] — 2026-05-31

### 重构：操作计划追踪 v2 — 数据源改为复盘 trading_plan + SQLite 存储

**背景：** 旧版从工作台（workbench）提取计划，数据经过人工筛选，无法追踪系统本身判断质量。

**v2 方案：**
- **数据源**：复盘 `compute_review_real_time()` 的 `trading_plan.holdings_action` + `trading_plan.buy_priority`，不再依赖 workbench 文件
- **存储**：JSON 文件 → SQLite（`plan_tracking.db`），零外部依赖，SQL 直接 GROUP BY 做多维统计
- **归类维度**：买点类型、结构·阶段、是否主线、来源(持仓/关注)、操作方向
- **自动建议**：新增主线 vs 非主线对比建议

**改动：**
- **`docs/plan-tracking-design.md`** — 更新为 v2 设计文档（含 PDF）
- **`server/backend/services/plan_tracking_service.py`** — 重写：SQLite 存储、review trading_plan 数据源、多维统计
- **`server/backend/api/plan_tracking.py`** — 适配新数据模型（date+code 标识取代 plan_date+type+stock）
- **`server/backend/tests/test_plan_tracking.py`** — 29 个新测试
- **`server/frontend/src/pages/PlanTracking.tsx`** — 适配新字段（source/buy_point/structure/is_main）

### 修复：大盘报警 dismiss 逻辑

- `check_index_alerts()` 中跳过 status=handled 的报警条目，大盘报警与个股报警保持一致的 dismiss/reenable 逻辑

## [v3.5.2] — 2026-05-30

### 修复：Docker 目录结构对齐原生开发（根治所有路径问题）

**根因：** `COPY server/ .` 将 `server/` 展平到 `/app/` 下，所有 `os.path.join(WWW_DIR, 'server', ...)` 路径全错。
之前打了 FE_DIR、scan_buy_signals 等多候选路径补丁，治标不治本。

**根治方案：** `COPY server/ /app/server/` 保持目录结构一致。
回退所有 Docker 路径补丁。保留的必须修复见下方。

**改动：**
- **`server/Dockerfile`** — COPY 目标改为 `/app/server/`，WORKDIR 改为 `/app/server`，cron cd 路径同步更新
- **`server/docker-entrypoint.sh`** — 入口脚本路径对齐；`directions.json` 初始格式改为正确格式
- **`server/.dockerignore`** — 恢复前端源码排除（镜像瘦身）
- **`deploy/deploy.sh`** — 密码输入加两次确认循环；支持端口选择(80/8080)；自动开 ufw 防火墙；每次交互运行强制弹密码输入（不依赖环境变量遗留值）；已有数据跳过初始化
- **`server/backend/core/monitor_data.py`** — review_archive 目录不存在时自动创建
- **`server/backend/services/monitor_service.py`** — 扫描脚本路径兼容 Docker 布局
- **`server/backend/core/update_stock_data.py`** — 在 import akshare 前设置 TQDM_DISABLE，消除脏进度条
- **`server/backend/core/update_stock_data.py`** — 新增 `update_industry_map()`，用 push2test.eastmoney.com `f100` 字段全量拉取4680只A股申万二级行业映射，每日全量替换
- **`server/backend/core/data_layer.py`** — 新增 `save_industry_map()` 配合行业映射写入
- **`server/backend/services/check_alerts.py`** — 大盘指数报警增加 dismiss 检查，用户标记"已处理"后不再重复推送（与个股报警逻辑一致）
- **`docs/deployment-guide.md`** — 修正部署文档：明确部署后需手动添加自选股+持仓股再拉数据，
  删除"首次数据初始化自动完成"的误导描述
- **`server/backend/services/direction_service.py`** — _load 兼容旧格式 directions.json，修复 KeyError: 'all' 导致新建方向失败

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

---

## [v3.8.2] — 2026-06-01

### 新增：参数固化 + 卖点体系 + 大盘过滤

**参数固化：** `server/backend/core/signal_detector/signal_config.json`
- 各信号阈值集中管理（confidence_pass / direction / enabled）
- 融合引擎参数（keypoint_bias_thresholds / buy_point_scale）
- 大盘过滤参数（acceleration_bias_threshold / bear_market_stage）

**卖点体系：** `server/backend/core/signal_detector/sell_point_detection.py`
- 规则1：向下突破（置信度≥60，最强烈）
- 规则2：向下反转（置信度≥65，上涨趋势末端）
- 规则3：需求衰竭（置信度≥75，波峰预警）
- 规则4：结构卖出（下降趋势/转弱/滞涨）
- 规则5：BIAS5>15%乖离卖出
- 集成到 `get_stock_card()`，置信度高于信号时覆盖

**大盘过滤：** `server/backend/core/signal_detector/market_filter.py`
- 加速阶段（波峰/pk≥4/BIAS>12%）→ 减仓至5成
- 阴跌阶段（下降趋势/vl≥4/BIAS<-8%）→ 休息至3成
- 其他阶段 → 正常交易（8成）

**前端集成：**
- `StockCard.tsx`: 信号徽章显示（方向色+置信度+融合类型标签）
- `TradingPlan.tsx`: 交易计划信号+融合类型展示
- `types.ts`: 信号类型定义

### 新增：SVG关键点图信号标注

- `stock_chart_service.py`: `generate_stock_chart()` 新增 `triggered_signals` 参数
- SVG右上角添加暗色信号徽章（▲/▼/◆方向图标+信号名+置信度）
- `stock.py`: `_handle_stock_chart` 自动检测信号传入图表

### 新增：信号系统单元测试

- `server/backend/tests/test_signal_fusion.py`，44个用例
- 覆盖9大检测器调用验证 / 8条融合规则 / 大盘过滤三态 / 卖点五规则

---

初始版本：3L 交易系统基础功能上线。

# Tushare 数据源迁移 + 目录结构重构设计方案

**版本:** v2.0（重构版）
**日期:** 2026-06-14
**状态:** 🔧 重构中（目录结构 + 架构合规修复）

> 本文档是数据源迁移和项目结构重构的统一设计文档。
> 记录了从 JSON 存储到 Tushare + MySQL 的迁移过程，以及标准 Python 后端项目结构的重构。

---

## 1. 数据架构总览

### 1.1 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    业务层 (services/)                     │
│  stock_card_service.py, analysis_service.py,             │
│  review_service.py, monitor_service.py ...                │
│         │  只能调 data_layer（唯一入口）                    │
│         ▼                                                  │
├─────────────────────────────────────────────────────────┤
│                  数据访问层 (data_access/)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  data_layer   │  │ data_source  │  │ tushare_db   │   │
│  │  (屏蔽层) ──► │  (获取层) ──► │  (DB驱动)     │   │
│  │  唯一入口      │  │  多源故障切换  │  │  MySQL连接    │   │
│  │               │  │  JSON回退    │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│         │                                                │
│         ▼                                                  │
├─────────────────────────────────────────────────────────┤
│                  基础设施 (core/)                          │
│  config.py, exceptions.py, logger.py                     │
├─────────────────────────────────────────────────────────┤
│                  数据模型 (models/)                        │
│  data_models.py (合约/Schema定义)                        │
└─────────────────────────────────────────────────────────┘
```

### 1.2 依赖方向（严格单向）

```
api/ → services/ → data_access/data_layer
                  → data_access/data_source
                  → data_access/tushare_db
                  → data_access/cache_layer
                  → models/
                  → core/ (config, exceptions)
```

**核心规则：**
- `services/` 和 `api/` **只能 import `data_layer`**，禁止直接调 `data_source` / `tushare_db` / `cache_layer`
- `data_layer` 是唯一入口，内部调用 `data_source` / `tushare_db` / `cache_layer`
- `core/` 不依赖其他层
- `models/` 不依赖其他层

### 1.3 双账号策略

| 账号 | 积分 | 用途 | 代理 |
|------|------|------|------|
| 15000 | 高权限 | 一次性回填历史全量 | `https://tu.brze.top` |
| 2000 | 标准 | 日常增量更新 | 直连（无代理） |

---

## 2. 目录结构

### 2.1 最终目标结构

```
server/backend/
├── core/                          ← 基础设施
│   ├── __init__.py
│   ├── config.py                  ← 配置（从 backend/ 移入）
│   ├── exceptions.py              ← 异常定义
│   └── logger.py                  ← 日志
│
├── models/                        ← 数据模型/合约
│   ├── __init__.py
│   └── data_models.py             ← 从 core/ 移入
│
├── data_access/                   ← 数据访问层（唯一数据入口）
│   ├── __init__.py
│   ├── data_layer.py              ← 屏蔽层（统一入口，业务代码只能调这个）
│   ├── data_source.py             ← 获取层（多源故障切换，从 services/ 移入）
│   ├── tushare_db.py              ← MySQL驱动（从 services/ 移入）
│   └── cache_layer.py             ← 缓存（从 core/ 移入）
│
├── services/                      ← 业务服务
│   ├── __init__.py
│   ├── analysis_service.py
│   ├── stock_card_service.py
│   ├── review_service.py
│   ├── monitor_service.py
│   ├── watchlist_service.py
│   ├── macro_service.py
│   └── ...（保留所有纯业务服务）
│
├── api/                           ← 路由（HTTP端点）
│   ├── __init__.py
│   └── ...（按模块拆分）
│
└── scripts/                       ← 一次性脚本
    ├── fill_history.py            ← 从 services/ 移入
    ├── migrate_to_mysql.py        ← 从 services/ 移入
    └── ...
```

### 2.2 当前 vs 目标

| 文件 | 当前位置 | 目标位置 | 状态 |
|------|---------|---------|------|
| `data_source.py` | `services/` | `data_access/` | ⏳ 待移 |
| `tushare_db.py` | `services/` | `data_access/` | ⏳ 待移 |
| `cache_layer.py` | `core/` | `data_access/` | ⏳ 待移 |
| `data_models.py` | `core/` | `models/` | ⏳ 待移 |
| `config.py` | `backend/` | `core/` | ⏳ 待移 |
| `fill_history.py` | `services/` | `scripts/` | ⏳ 待移 |
| `migrate_to_mysql.py` | `services/` | `scripts/` | ⏳ 待移 |
| 重复 `data_layer.py` | `core/threel_core/` | 删掉（合并） | ⏳ 待删 |

### 2.3 数据层内部关系

```
data_layer.py（屏蔽层 — 业务代码的唯一入口）
  │
  ├── 调用 data_source.py 获取K线/板块/指数数据
  │     └── data_source.py 内部：
  │           ├── TushareDB（MySQL，主数据源）
  │           ├── 同花顺 THS akshare（ths_daily 回退）
  │           ├── 东财 push2test（板块快照回退）
  │           └── JSON（极少数回退场景）
  │
  ├── 调用 tushare_db.py 读写 MySQL
  │     └── TushareDB 类：建表/CRUD/查询/复权
  │
  └── 调用 cache_layer.py 做内存+文件缓存
```

---

## 3. 数据存储现状

### 3.1 已迁移到 MySQL（JSON 已删除）

| 原JSON文件 | 替代 | 状态 |
|-----------|------|------|
| `all_stocks_60d.json` | `stock_daily` 表 (318万行) | ✅ DB优先，JSON已删 |
| `index_sh_data.json` | `index_daily` 表 (2360行) | ✅ DB优先，JSON已删 |
| `map/` (4文件) | `ths_index` + `ths_member` 表 | ✅ 已备份清理 |
| `sources/` (3文件) | `ths_daily` 表 (84万行) | ✅ 已备份清理 |
| 根目录散落JSON | 各对应表 | ✅ 已备份清理 |

### 3.2 仍走 JSON 的数据（合理保留）

| 文件 | 路径 | 说明 |
|------|------|------|
| `watchlist.json` | `config/` | 自选股配置 |
| `holdings.json` | `config/` | 持仓数据 |
| `trades.json` | `config/` | 交易记录 |
| `mainlines_cache.json` | `config/` | 主线缓存 |
| `industry_map.json` | `computed/` | 行业映射 |
| `concept_list.json` | `map/`（已备） | 概念列表 |
| `scan_result.json` | `computed/` | 扫描结果 |

### 3.3 待迁移（板块数据）

`SECTOR_DAILY_PATH` 仍走 JSON 生成/读取，但文件由 `update_stock_data.py` 运行时自动生成。`ths_daily` 表已回填84万行历史数据，但尚未对接为读取源。

---

## 4. 当前架构违规范

### 4.1 data_layer 直接访问 TushareDB ❌

违反规则的代码在 `data_layer.py`：

```python
# ❌ 当前（data_layer 直接 import TushareDB）
from backend.services.tushare_db import TushareDB

def get_all_stocks_db():
    db = TushareDB()  # 绕过 data_source
    ...

def get_index_data():
    db = TushareDB()  # 绕过 data_source
    ...

def save_all_stocks(stocks):
    db = TushareDB()  # 绕过 data_source
    ...

def save_index_data(data):
    db = TushareDB()  # 绕过 data_source
    ...
```

应该改为：

```python
# ✅ 正确（data_layer 调 data_source）
def get_all_stocks():
    return data_source.get_all_stocks_from_db()

def get_all_stocks_db():
    return data_source.get_all_stocks_from_db()

def get_index_data():
    return data_source.get_index_data_from_db()

def save_all_stocks(stocks):
    data_source.save_stock_klines_to_db(stocks)

def save_index_data(data):
    data_source.save_index_klines_to_db(data)
```

### 4.2 data_source.py 放错位置 ❌

`data_source.py` 在 `services/` 目录下，但它不是业务服务，而是数据获取层。应放入 `data_access/`。

### 4.3 其他位置问题 ❌

- `tushare_db.py` 在 `services/` → 应放 `data_access/`
- `cache_layer.py` 在 `core/` → 应放 `data_access/`
- `config.py` 在 `backend/` → 应放 `core/`
- `data_models.py` 在 `core/` → 应放 `models/`
- `fill_history.py` / `migrate_to_mysql.py` 在 `services/` → 应放 `scripts/`
- 重复的 `data_layer.py` 在 `core/threel_core/` → 应删除

---

## 5. 重构计划（TDD 驱动）

### Phase R1: data_source 新增接口（TDD）

**Goal:** data_source.py 增加 `get_all_stocks_from_db()` / `get_index_data_from_db()` / `save_stock_klines_to_db()` / `save_index_klines_to_db()` 四个函数。

| 步骤 | 内容 | 测试 |
|------|------|------|
| R1.1 | 编写测试：测试 data_source 新接口返回格式 | 🔴 RED |
| R1.2 | 实现 data_source 新接口（从 data_layer 搬逻辑） | 🟢 GREEN |
| R1.3 | 重构 data_layer 调 data_source 而非直接调 TushareDB | 🔵 REFACTOR |
| R1.4 | 全量测试验证 | ✅ |

### Phase R2: 目录结构调整（TDD）

**Goal:** 将文件移到正确位置，更新所有 import

| 步骤 | 内容 | 测试 |
|------|------|------|
| R2.1 | 编写测试：新路径的 import 可正常工作 | 🔴 RED |
| R2.2 | 移动文件 + 更新所有 import 路径 | 🟢 GREEN |
| R2.3 | 删除重复 `data_layer.py` | 🔵 REFACTOR |
| R2.4 | 全量测试验证 | ✅ |

### Phase R3: 后续清理

| 步骤 | 内容 |
|------|------|
| R3.1 | 删除 `core/threel_core/data_layer.py`（重复） |
| R3.2 | 更新所有脚本/测试的 import 路径 |
| R3.3 | 验证服务器启动正常 |
| R3.4 | 更新设计文档 |

---

## 6. MySQL 数据库 Schema

### 6.1 表清单（9张表，~1070万行）

| 表名 | Tushare API | 行数 | 说明 |
|------|------------|------|------|
| `stock_daily` | `daily` | 318万 | 个股日线（前复权+不复权） |
| `daily_basic` | `daily_basic` | 318万 | PE/PB/市值/换手率 |
| `index_daily` | `index_daily` | 2360 | 4指数日线 |
| `ths_daily` | `ths_daily` | 84万 | 板块日线 |
| `ths_index` | `ths_index` | 1725 | 板块列表 |
| `ths_member` | `ths_member` | 28万 | 板块成分股 |
| `stock_basic` | `stock_basic` | 5522 | A股基本信息 |
| `adj_factor` | `adj_factor` | 320万 | 复权因子 |
| `trade_cal` | `trade_cal` | 896 | 交易日历 |

### 6.2 复权方案

使用 Tushare 复权因子计算前复权价：
```
前复权价 = 原始价 × latest_adj / adj_factor[t]
```

默认返回前复权价格（`adj='qfq'`），与旧 JSON 前复权价格 0.00% 差异验证通过。

---

## 7. MySQL 连接配置

| 配置 | 值 |
|------|-----|
| 主机 | `43.136.177.133` |
| 端口 | `3306` |
| 数据库 | `tushare` |
| 用户 | `tushare` |
| 密码 | 环境变量 `MYSQL_PASSWORD` |

配置在 `.env` 和 `config.py` 中。

---

## 8. 实施进度

### ✅ Phase 1-4: 基础架构（已完成）

- [x] TushareDB MySQL 驱动（PyMySQL）
- [x] 9张表建表 + CRUD + 复权计算
- [x] data_source.py Tushare 路由
- [x] 代理验证（15000分走代理）
- [x] 全量回填（~1070万行）
- [x] 目录结构调整（config/computed/cache/public 分拆）
- [x] JSON 备份清理

### ✅ Phase 5: data_layer 切 MySQL（已完成）

- [x] `get_all_stocks()` 优先读 DB
- [x] `get_index_data()` 优先读 DB
- [x] JSON 回退完全移除
- [x] 残留 JSON 引用清理

### ⏳ Phase R1-R2: 架构合规修复（当前任务）

- [ ] R1: data_source 新增接口
- [ ] R2: 目录结构调整
- [ ] R3: 清理收尾

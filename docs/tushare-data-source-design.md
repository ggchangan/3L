# Tushare 数据源迁移设计方案 v0.3 — 数据库+双账号策略

**版本:** v0.3 (草案)
**日期:** 2026-06-14
**状态:** 📝 方案讨论中

> **积分说明：** Tushare Pro 的积分是**权限等级**，不是单次调用消耗。
> - API接口有最低积分要求（如某接口需要2000分以上才能调用）
> - 调用API不消耗积分，有频率限制（200次/分钟）
> - 高积分账号解锁更多高级接口
> - 2000分账号日常已可使用 `daily` / `daily_basic` / `ths_daily` / `index_daily` 等核心接口

## 1. 数据架构总览

### 1.1 核心理念

```
┌─────────────────────────────────────────────────────┐
│                   Tushare Pro                         │
│  ┌─────────────────────┐  ┌──────────────────────┐   │
│  │  15000积分账号 (高权限)│  │  2000积分账号 (标准)   │   │
│  │  → 一次性回填全部历史  │  │  → 每日增量更新       │   │
│  │  → 解锁所有高级接口    │  │  → 日常查询(够用)     │   │
│  └─────────┬───────────┘  └──────────┬───────────┘   │
└────────────┼──────────────────────────┼──────────────┘
             │                          │
             ▼                          ▼
        ┌────────────────────────────────────┐
        │         SQLite 数据库               │
        │  (db/tushare.db)                    │
        │  表: stock_daily, daily_basic,      │
        │       index_daily, ths_daily, ...   │
        │  一次补齐，每日追加                  │
        └──────┬─────────────────────────────┘
               │
               ▼
        ┌──────────────────┐
        │   data_layer.py   │  ← 业务代码不变
        │  (新增DB读取路径)  │     只改内部实现
        └──────────────────┘
```

### 1.2 为什么选 SQLite

| 考量 | SQLite | PostgreSQL | JSON文件 |
|------|--------|-----------|---------|
| 服务器 | 无(文件级) | 需安装配置 | 无 |
| 时间序列查询 | ✅ `WHERE date BETWEEN` | ✅ | ❌ 全量加载过滤 |
| 历史数据量适配 | ✅ 单文件TB级 | ✅ | ❌ 越大越慢 |
| 并发读写 | ⚠️ WAL模式可读+写 | ✅ | ❌ 原子写但无查询 |
| 迁移成本 | 低(文件替换) | 高 | — |
| 备份 | 单文件cp | pg_dump | cp |

SQLite 用 WAL 模式允许同时读写（cron写+服务读），零运维成本。

---

## 2. 数据库 Schema 设计

### 2.1 表清单（5张核心表 + 3张辅助表）

```sql
-- ═══════════════════════════════════════
-- 1. 个股日线行情 (核心表)
-- 对应 Tushare: daily
-- 行数估算: ~5000只 × 250天/年 = ~125万行/年
-- ═══════════════════════════════════════
CREATE TABLE stock_daily (
    ts_code     TEXT NOT NULL,  -- '000001.SZ'
    trade_date  TEXT NOT NULL,  -- '20260613'
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    pre_close   REAL,
    change      REAL,           -- 涨跌额
    pct_chg     REAL,           -- 涨跌幅% (Tushare已算好)
    vol         REAL,           -- 成交量(股)
    amount      REAL,           -- 成交额(元)
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 2. 每日指标 (PE/PB/市值/换手率)
-- 对应 Tushare: daily_basic
-- ═══════════════════════════════════════
CREATE TABLE daily_basic (
    ts_code         TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    close           REAL,
    turnover_rate   REAL,       -- 换手率%
    turnover_rate_f REAL,       -- 自由流通换手率%
    volume_ratio    REAL,       -- 量比
    pe              REAL,       -- 动态市盈率
    pe_ttm          REAL,       -- 滚动市盈率
    pb              REAL,       -- 市净率
    ps              REAL,       -- 市销率
    pcf             REAL,       -- 市现率
    total_mv        REAL,       -- 总市值(万元)
    circ_mv         REAL,       -- 流通市值(万元)
    total_share     REAL,       -- 总股本(万股)
    float_share     REAL,       -- 流通股本(万股)
    free_share      REAL,       -- 自由流通股本(万股)
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 3. 指数日线行情
-- 对应 Tushare: index_daily
-- ═══════════════════════════════════════
CREATE TABLE index_daily (
    ts_code     TEXT NOT NULL,  -- '000985.SH'
    trade_date  TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    pre_close   REAL,
    change      REAL,
    pct_chg     REAL,
    vol         REAL,
    amount      REAL,
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 4. 同花顺板块日线 (行业+概念)
-- 对应 Tushare: ths_daily
-- ═══════════════════════════════════════
CREATE TABLE ths_daily (
    ts_code     TEXT NOT NULL,  -- '881121.TI' / '884112.TI'
    trade_date  TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    pre_close   REAL,
    change      REAL,
    pct_chg     REAL,
    vol         REAL,
    amount      REAL,
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 5. 同花顺板块列表
-- 对应 Tushare: ths_index
-- ═══════════════════════════════════════
CREATE TABLE ths_index (
    ts_code     TEXT PRIMARY KEY,   -- '881121.TI'
    name        TEXT NOT NULL,      -- '电子' / '人工智能'
    count       INTEGER,           -- 成分股数量
    list_date   TEXT,              -- 上市日期
    type        TEXT               -- 'I'(行业) / 'N'(概念)
);

-- ═══════════════════════════════════════
-- 6. 板块成分股
-- 对应 Tushare: ths_member
-- ═══════════════════════════════════════
CREATE TABLE ths_member (
    ts_code     TEXT NOT NULL,      -- 板块ts_code '881121.TI'
    con_code    TEXT NOT NULL,      -- 成分股ts_code '600519.SH'
    con_name    TEXT,              -- 成分股名称
    weight      REAL,              -- 权重
    PRIMARY KEY (ts_code, con_code)
);

-- ═══════════════════════════════════════
-- 7. A股基本信息
-- 对应 Tushare: stock_basic
-- ═══════════════════════════════════════
CREATE TABLE stock_basic (
    ts_code         TEXT PRIMARY KEY,
    symbol          TEXT,           -- 6位代码
    name            TEXT,
    area            TEXT,           -- 地域
    industry        TEXT,           -- 申万行业
    market          TEXT,           -- '主板'/'创业板'/'科创板'
    list_date       TEXT,           -- 上市日期
    delist_date     TEXT,           -- 退市日期
    is_hs           TEXT            -- 是否沪深港通
);

-- ═══════════════════════════════════════
-- 8. 复权因子
-- 对应 Tushare: adj_factor
-- ═══════════════════════════════════════
CREATE TABLE adj_factor (
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    adj_factor  REAL,            -- 后复权因子
    PRIMARY KEY (ts_code, trade_date)
);
```

### 2.2 索引设计

```sql
-- 个股查询加速
CREATE INDEX idx_stock_daily_ts_code ON stock_daily(ts_code);
CREATE INDEX idx_stock_daily_date ON stock_daily(trade_date);
CREATE INDEX idx_daily_basic_ts_code ON daily_basic(ts_code);
CREATE INDEX idx_adj_factor_ts_code ON adj_factor(ts_code);

-- 板块查询加速
CREATE INDEX idx_ths_daily_ts_code ON ths_daily(ts_code);
CREATE INDEX idx_ths_member_con_code ON ths_member(con_code);  -- 按成分股查所属板块
CREATE INDEX idx_ths_index_type ON ths_index(type);            -- 按行业/概念筛选

-- 指数查询加速
CREATE INDEX idx_index_daily_ts_code ON index_daily(ts_code);
```

### 2.3 交易日历表（可选）

```sql
CREATE TABLE trade_cal (
    exchange    TEXT NOT NULL,      -- 'SSE'
    cal_date    TEXT NOT NULL,      -- '20260613'
    is_open     INTEGER,            -- 0闭市/1开市
    pretrade_date TEXT,             -- 前一交易日
    PRIMARY KEY (exchange, cal_date)
);
```

---

## 3. 数据拉取计划

### 3.1 Tushare 接口调用总表

| API | 说明 | 最低积分 | 回填方式 | 增量方式(账号) | 写入表 |
|-----|------|---------|---------|---------------|-------|
| `stock_basic` | A股列表+行业 | 免费 | 1次全量,5000+只 | 月/15000或2000 | `stock_basic` |
| `trade_cal` | 交易日历 | 免费 | 1次全量,10年 | 年/15000或2000 | `trade_cal` |
| `ths_index` | 同花顺板块列表 | 免费 | 1次全量(行业+概念) | 月/15000或2000 | `ths_index` |
| `ths_member` | 板块成分股 | 免费 | ~500板块逐次 | 月/15000或2000 | `ths_member` |
| `daily` | 个股日线 | 2000 | 全量5000只×2年 | 每日/2000 | `stock_daily` |
| `daily_basic` | 每日指标(PE/PB) | 2000 | 全量5000只×2年 | 每日/2000 | `daily_basic` |
| `adj_factor` | 复权因子 | 2000 | 全量5000只×2年 | 每日/2000 | `adj_factor` |
| `index_daily` | 指数日线 | 免费 | 4个指数×2年 | 每日/2000 | `index_daily` |
| `ths_daily` | 板块日线 | **6000** | ~500板块×2年 | 每日/**15000** | `ths_daily` |

> ⚠️ `ths_daily` 需要6000积分，2000账号调不了。每日增量用15000账号跑（仅10次调用/天，量极小）。

### 3.2 一次性回填（15000积分账号）

按依赖顺序依次执行，每张表完成后打印进度。

```
┌─────────────────────────────────────────────────────────┐
│  回填顺序（从上到下，并行无依赖的可以并发）                │
│                                                          │
│  Step 1: stock_basic + trade_cal + ths_index (3个免费)   │
│              │  (可并发, 互不依赖)                        │
│  Step 2: ths_member (依赖 ths_index 的板块ts_code)         │
│              │                                            │
│  Step 3: index_daily + adj_factor (可并发)                │
│              │                                            │
│  Step 4: ths_daily (依赖 ths_index 的板块ts_code)          │
│              │                                            │
│  Step 5: stock_daily (分批, 500只/批, 每批1次调用)         │
│              │                                            │
│  Step 6: daily_basic (分批, 500只/批, 每批1次调用)         │
└─────────────────────────────────────────────────────────┘
```

#### Step 1 — stock_basic（免费，1次调用）

```python
pro = ts.pro_api(token_high)
df = pro.stock_basic(
    fields='ts_code,symbol,name,area,industry,market,list_date,delist_date,is_hs'
)
# → stock_basic 表，全量~5300只A股
```

**Tushare 返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | str | 股票代码(600519.SH) |
| symbol | str | 6位代码 |
| name | str | 股票名称 |
| area | str | 地域 |
| industry | str | 申万行业 |
| market | str | 主板/创业板/科创板 |
| list_date | str | 上市日期 |
| delist_date | str | 退市日期 |
| is_hs | str | 沪深港通标 |

#### Step 1 — trade_cal（免费，1次调用）

```python
df = pro.trade_cal(exchange='SSE', start_date='20200101', end_date='20271231',
                   fields='exchange,cal_date,is_open,pretrade_date')
# → trade_cal 表
```

#### Step 1 — ths_index（免费，2次调用）

```python
df_i = pro.ths_index(type='I')  # 行业板块, ~90个
df_n = pro.ths_index(type='N')  # 概念板块, ~400个
# → ths_index 表
```

**Tushare 返回字段：**
| 字段 | 说明 |
|------|------|
| ts_code | 板块代码(881121.TI) |
| name | 板块名(电子) |
| count | 成分股数量 |
| list_date | 上市日 |
| type | I=行业, N=概念 |

#### Step 2 — ths_member（免费，~490次调用）

```python
# 遍历 ths_index 的每个板块，逐次拉取
for _, row in ths_index.iterrows():
    df = pro.ths_member(ts_code=row['ts_code'],
                        fields='ts_code,con_code,con_name,weight')
    # → ths_member 表
```

**Tushare 返回字段：**
| 字段 | 说明 |
|------|------|
| ts_code | 板块代码 |
| con_code | 成分股代码 |
| con_name | 成分股名称 |
| weight | 权重% |

**限流：** 每次间隔≥0.4秒。490次 ≈ 3.5分钟。

#### Step 3 — index_daily（免费，4次调用）

```python
for code in ['000001.SH', '000688.SH', '000985.SH', '399006.SZ']:
    df = pro.index_daily(ts_code=code, start_date='20240101', end_date=today,
                         fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount')
    # → index_daily 表
```

**Tushare 返回字段：** 与 stock_daily 结构相同。

#### Step 3 — adj_factor（2000积分，分批调用）

```python
# 同 stock_daily 分批逻辑，500只/批
for batch in chunks(all_codes, 500):
    df = pro.adj_factor(ts_code=','.join(batch),
                        start_date='20240101', end_date=today,
                        fields='ts_code,trade_date,adj_factor')
    # → adj_factor 表
```

#### Step 4 — ths_daily（免费，分批调用）

```python
# 遍历 ths_index 中的 ~490个板块，按50个/批拉取
ths_codes = ths_index['ts_code'].tolist()
for batch in chunks(ths_codes, 50):
    df = pro.ths_daily(ts_code=','.join(batch),
                       start_date='20240101', end_date=today,
                       fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount')
    # → ths_daily 表
```

**注意：** `ths_daily` 的 ts_code 参数不能传过多代码，实测50个/批较安全。~490板块 ÷ 50 = 10批。

#### Step 5 — stock_daily（2000积分，分批，500只/批）

```python
codes = stock_basic['ts_code'].tolist()  # ~5300只
for batch in chunks(codes, 500):
    df = pro.daily(ts_code=','.join(batch),
                   start_date='20240101', end_date=today,
                   fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount')
    # → stock_daily 表
```

**Tushare 返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | str | 股票代码 |
| trade_date | str | 交易日期(20260613) |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| pre_close | float | 昨收价 |
| change | float | 涨跌额 |
| pct_chg | float | 涨跌幅% |
| vol | float | 成交量(股) |
| amount | float | 成交额(元) |

#### Step 6 — daily_basic（2000积分，分批，500只/批）

```python
for batch in chunks(codes, 500):
    df = pro.daily_basic(ts_code=','.join(batch),
                         start_date='20240101', end_date=today,
                         fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,pcf,total_mv,circ_mv,total_share,float_share,free_share')
    # → daily_basic 表
```

**Tushare 返回字段：**
| 字段 | 说明 |
|------|------|
| ts_code | 股票代码 |
| trade_date | 交易日期 |
| close | 收盘价 |
| turnover_rate | 换手率% |
| turnover_rate_f | 自由流通换手率% |
| volume_ratio | 量比 |
| pe | 动态市盈率 |
| pe_ttm | 滚动市盈率 |
| pb | 市净率 |
| ps | 市销率 |
| pcf | 市现率 |
| total_mv | 总市值(万元) |
| circ_mv | 流通市值(万元) |
| total_share | 总股本(万股) |
| float_share | 流通股本(万股) |
| free_share | 自由流通股本(万股) |

### 3.3 每日增量（混合账号）

```python
def daily_incremental_update(pro_low, pro_high, db, trade_date):
    """每日增量更新
    pro_low:  2000积分账号（调用 daily / daily_basic / adj_factor / index_daily）
    pro_high: 15000积分账号（仅调用 ths_daily，需要6000积分权限）
    """
    # 1. 自选股列表
    watchlist_codes = get_watchlist_codes()
    ts_codes = [code_to_ts(c) for c in watchlist_codes]
    ts_codes_str = ','.join(ts_codes)
    
    # ---------- 2000账号 ----------
    # 2. 个股日线（仅自选股）
    df = pro_low.daily(ts_code=ts_codes_str, start_date=trade_date, end_date=trade_date)
    db.upsert_many('stock_daily', df)
    
    # 3. 每日指标
    df = pro_low.daily_basic(ts_code=ts_codes_str, start_date=trade_date, end_date=trade_date)
    db.upsert_many('daily_basic', df)
    
    # 4. 复权因子
    df = pro_low.adj_factor(ts_code=ts_codes_str, start_date=trade_date, end_date=trade_date)
    db.upsert_many('adj_factor', df)
    
    # 5. 指数（免费）
    for code in ['000001.SH', '000688.SH', '000985.SH', '399006.SZ']:
        df = pro_low.index_daily(ts_code=code, start_date=trade_date, end_date=trade_date)
        db.upsert_many('index_daily', df)
    
    # ---------- 15000账号（ths_daily 需要6000积分）----------
    # 6. 板块日线（全量板块）
    ths_codes = db.get_all_ths_codes()
    for batch in chunks(ths_codes, 50):
        df = pro_high.ths_daily(ts_code=','.join(batch), start_date=trade_date, end_date=trade_date)
        db.upsert_many('ths_daily', df)
```

**各API每日调用次数：**
| API | 调用次数 | 使用账号 | 说明 |
|-----|---------|---------|------|
| `daily` | 1次 | 2000 | 50只自选股一次传 |
| `daily_basic` | 1次 | 2000 | 同上 |
| `adj_factor` | 1次 | 2000 | 同上 |
| `index_daily` | 4次 | 2000 | 4个指数各1次 |
| `ths_daily` | 10次 | **15000** | ~490板块÷50/批，需6000积分 |
| **合计** | **17次** | 双账号 | 远低于200次/分钟限流 |

### 3.4 表结构一览（全部9张表）

| 表名 | Tushare API | PRIMARY KEY | 行数预估(2年) | 核心字段 |
|------|------------|-------------|-------------|---------|
| `stock_daily` | `daily` | (ts_code, trade_date) | 250万 | open,close,high,low,vol,amount,pct_chg |
| `daily_basic` | `daily_basic` | (ts_code, trade_date) | 250万 | pe_ttm,pb,total_mv,circ_mv,turnover_rate |
| `index_daily` | `index_daily` | (ts_code, trade_date) | 2000 | open,close,high,low,vol,pct_chg |
| `ths_daily` | `ths_daily` | (ts_code, trade_date) | 25万 | open,close,high,low,vol,pct_chg |
| `ths_index` | `ths_index` | (ts_code) | 490 | name,count,type |
| `ths_member` | `ths_member` | (ts_code, con_code) | 5万 | con_name,weight |
| `stock_basic` | `stock_basic` | (ts_code) | 5300 | name,industry,market |
| `adj_factor` | `adj_factor` | (ts_code, trade_date) | 250万 | adj_factor |
| `trade_cal` | `trade_cal` | (exchange, cal_date) | 2000 | is_open |

完整的 CREATE TABLE SQL 见 **§2.1**。

## 4. 数据存储架构重整

趁这次改成表格存储，把整个数据目录重新设计一遍。

### 4.1 新目录结构

```
data/
├── tushare.db              # 【新增】SQLite 主库 — 全量原始数据
│
├── config/                 # 【新增】用户配置（可读可改的JSON）
│   ├── watchlist.json      # 自选股 ← 从根目录移入
│   ├── holdings.json       # 持仓 ← 从 private/ 移入
│   ├── trades.json         # 交易记录 ← 从 private/ 移入
│   ├── alarms.json         # 报警配置 ← 从 private/ 移入
│   ├── plan_tracking.json  # 计划跟踪 ← 从 private/ 移入
│   ├── manual_trend.json   # 手动趋势股 ← 从 private/ 移入
│   ├── directions.json     # 方向配置 ← 从根目录移入
│   ├── watched_industries.json  # 关注的行业 ← 从根目录移入
│   └── journals.json       # 日志 ← 从 private/ 移入
│
├── computed/               # 【新增】计算结果（可删除，可重算）
│   ├── scan_result.json    # 最新扫描结果 ← 从根目录移入
│   ├── industry_leaders.json   # 领涨股 ← 从根目录移入
│   ├── candidates_data.json    # 候选股 ← 从根目录移入
│   ├── analysis_results.json   # 分析结果 ← 从根目录移入
│   ├── mainlines_cache.json    # 主线缓存 ← 从根目录移入
│   ├── mainline_history.json   # 主线历史 ← 从根目录移入
│   ├── logic_tracking.json     # 逻辑追踪 ← 从根目录移入
│   ├── sub_sector_clusters.json # 子行业聚类 ← 从根目录移入
│   ├── profit_quality.json     # 盈利质量 ← 从根目录移入
│   └── key_points/             # 关键点 ← 从根目录移入
│
├── cache/                  # 运行时缓存（按TTL自动清理）
│   ├── buy_signals/        # 扫描结果（按日期分）
│   ├── volume_snapshots/   # 成交量快照
│   ├── industry_boards/    # 行业板块
│   └── backtest/           # 回测缓存
│
├── charts/                 # SVG图表（不变）
├── public/                 # 前端公开数据（不变）
├── simulation/             # 模拟交易（不变）
├── knowledge_base/         # 知识库（不变）
│
# 前端静态数据（在 WWW_DIR 下，不在 data/ 下）
# WWW_DIR/data/public/pinyin.json    ← 拼音首字母，/pub/pinyin.json 直接服务
# WWW_DIR/data/public/...             ← 其他前端用JSON
│
├── private/                # 【废弃】所有文件移到 config/ 或 computed/
│
├── map/                    # 【废弃】移到 tushare.db
├── sources/                # 【废弃】移到 tushare.db
├── all_stocks_60d.json     # 【废弃】移到 tushare.db
├── sector_daily.json       # 【废弃】移到 tushare.db
├── index_sh_data.json      # 【废弃】移到 tushare.db
├── stock_industry_map.json # 【废弃】移到 tushare.db
└── ...（其他根目录散落的原始数据文件）
```

### 4.2 全量文件迁移清单（逐个文件列全）

#### 🔴 01 — 删除（被 DB 替代）

| 文件 | 大小 | 替代方 | 说明 |
|------|------|--------|------|
| `all_stocks_60d.json` | 2.1M | `stock_daily` 表 | 个股K线 |
| `all_stocks_60d.json.bak*` | 2.5M | — | 备份，清掉 |
| `sector_daily.json` | 15M | `ths_daily` + `ths_index` 表 | 板块K线 |
| `sector_daily.*.bak*` | ~30M | — | 各种备份，清掉 |
| `index_sh_data.json` | 85K | `index_daily` 表 | 指数K线 |
| `index_sh_data.json.bak` | 22K | — | 备份，清掉 |
| `stock_industry_map.json` | 373K | `stock_basic.industry` | 行业归属 |
| `all_stock_codes.json` | 149K | `stock_basic` 表 | 全量A股代码 |
| `all_a_stocks.json` | 133K | `stock_basic` 表 | 全量A股名 |
| `board_constituents.json` | 178K | `ths_member` 表 | 板块成分股 |
| `board_names_cache.json` | 37K | `ths_index` 表 | 板块中文名↔代码 |
| `financial_data_cache.json` | 128K | → 删除，从 `daily_basic` 按需查 | 财务缓存不再需要 |
| `stock_on_demand_cache.json` | 4K | → 删除，DB有全量 | 按需缓存废弃 |
| `sources/` (3个文件) | 1.9M | `ths_daily` + `ths_index` 表 | EM/THS数据源 |
| `map/` (4个文件) | 1.6M | `ths_index` + `ths_member` 表 | 概念列表+成分股 |
| `private/trading_days_cache.json` | 121K | `trade_cal` 表 | 交易日历 |
| `sector_daily.ths.backup*` | 2.5M | — | 备份，清掉 |
| **合计删除** | **~57MB** | | 含各种bak |

#### 🟡 02 — 移入 config/（用户配置）

| 当前位置 | 新位置 | 大小 | 说明 |
|---------|--------|------|------|
| `watchlist.json` | `config/watchlist.json` | 42K | 自选股 |
| `private/holdings.json` | `config/holdings.json` | 8.3K | 持仓 |
| `private/trades.json` | `config/trades.json` | 1.1K | 交易记录 |
| `private/alarms.json` | `config/alarms.json` | 17K | 报警配置 |
| `private/plan_tracking.json` | `config/plan_tracking.json` | 6.0K | 计划跟踪 |
| `private/plan_tracking.db` | `config/plan_tracking.db` | 344K | 计划跟踪SQLite |
| `private/manual_trend_stocks.json` | `config/manual_trend.json` | 180B | 手动趋势股 |
| `private/journal_entries.json` | `config/journals.json` | 496B | 日志 |
| `private/watchlist.json` | → 合并到 config/watchlist.json | 3B | 冗余，清掉 |
| `directions.json` | `config/directions.json` | 6.4K | 方向配置 |
| `watched_industries.json` | `config/watched_industries.json` | 18B | 关注的行业 |
| **合计移入 config/** | | **~425K** | |

#### 🟡 03 — 移入 public/（前端静态数据）

| 当前位置 | 新位置 | 大小 | 说明 |
|---------|--------|------|------|
| `pinyin_initials.json` | `WWW_DIR/data/public/pinyin.json` | 108K | 拼音首字母，前端搜索用 |
| `public/external_mapping.json` | `WWW_DIR/data/public/`（已有） | 12K | 不变 |
| `public/index_data.json` | `WWW_DIR/data/public/`（已有） | 109K | 不变 |
| `public/panic_history.json` | `WWW_DIR/data/public/`（已有） | 2.1K | 不变 |
| `public/sounds/alarm_sounds.json` | `WWW_DIR/data/public/`（已有） | 554B | 不变 |

#### 🟡 04 — 移入 computed/（计算结果）

| 当前位置 | 新位置 | 大小 | 说明 |
|---------|--------|------|------|
| `latest_scan_result.json` | `computed/scan_result.json` | 13K | 最新扫描 |
| `industry_leaders.json` | `computed/industry_leaders.json` | 102K | 领涨股（可改为按需计算） |
| `candidates_data.json` | `computed/candidates_data.json` | 133K | 候选股 |
| `analysis_results.json` | `computed/analysis_results.json` | 56K | 分析结果 |
| `mainline_history.json` | `computed/mainline_history.json` | 2.9K | 主线历史 |
| `logic_tracking.json` | `computed/logic_tracking.json` | 5.2K | 逻辑追踪 |
| `sub_sector_clusters.json` | `computed/sub_sector_clusters.json` | 43K | 子行业聚类 |
| `profit_quality_results.json` | `computed/profit_quality.json` | 615B | 盈利质量 |
| `private/mainlines_cache.json` | `computed/mainlines_cache.json` | 537B | 主线缓存 |
| `key_points/` (10个文件) | `computed/key_points/` | 44K | 关键点 |
| `private/workbench/` (7个文件) | `computed/workbench/` | 2.2K | 工作台 |
| `source_health.json` | `computed/source_health.json` | 1.1K | 数据源健康状态 |
| **合计移入 computed/** | | **~400K** | |

#### 🟢 05 — 保留不动

| 路径 | 大小 | 说明 |
|------|------|------|
| `cache/buy_signals_*.json` (30+个) | 3.5M | 扫描结果缓存，按日期 |
| `cache/volume_snapshots_*.json` (20+个) | 750K | 成交量快照，按日期 |
| `cache/industry_boards_*.json` (20+个) | 480K | 行业板块缓存，按日期 |
| `cache/market_leaders_*.json` | 8K | 市场领涨缓存 |
| `cache/market_leaders_daily/*` (300+个) | 300K | 个股每日领涨数据 |
| `cache/backtest_*.json` (3个) | 1.3M | 回测缓存 |
| `cache/manual_scan_*.json` | 135B | 手动扫描缓存 |
| `cache/macro_cpi.json` | 915B | CPI数据 |
| `cache/sector_structure.json` | 357B | 板块结构 |
| `cache/watchlist_analysis_cache.json` | 142K | 自选分析缓存 |
| **cache/ 合计** | **~6.5M** | 运行时缓存，按TTL清理 |
| `charts/*.png` (30+个) | 1.1M | SVG/PNG图表 |
| `simulation/` | 19M | 模拟交易（v2/v3/pdf/报告） |
| `knowledge_base/` | 11M | 知识库文档 |
| `public/charts/` | (charts已有) | 前端图表不碰 |

#### 🟣 06 — 需确认/清理的

| 文件 | 大小 | 处理方式 |
|------|------|---------|
| `fill_stock_names.py` | 2.7K | 脚本，移到 scripts/ |
| `update_cache_and_scan.py` | 9.3K | 脚本，移到 scripts/ |
| `stock_knowledge_base.md` | 6.8K | 文档，移到 knowledge_base/ |
| `中继买点精选报告_*.pdf` | 1.4M | 移入 simulation/ 或删掉 |
| `盈利模式1_*.txt` | 3.9K | 移入 knowledge_base/ 或删掉 |
| `private/review_archive/` | 324K | 复盘存档，移到 computed/review/ |
| `private/review_data.json.bak` | 324K | 备份，清掉 |
| `private/.wechat_*` | 159K | 微信偏移量/去重缓存，保留原处 |
| `private/alarm_music_design.md` | 2.5K | 文档，移到 knowledge_base/ |

### 4.3 各文件用途与结构示例

#### tushare.db — SQLite 主库

**用途：** 全量原始行情数据的唯一存储。所有业务代码通过 data_layer → data_source → TushareDB 读取，不直接操作文件。

**包含8张表，详见 §2.1（Schema 定义）：**
- `stock_daily` — 个股日线（含涨跌幅）
- `daily_basic` — 每日指标（PE/PB/市值/换手率）
- `index_daily` — 指数日线
- `ths_daily` — 同花顺板块日线
- `ths_index` — 同花顺板块列表
- `ths_member` — 板块成分股
- `stock_basic` — A股基本信息
- `adj_factor` — 复权因子
- `trade_cal` — 交易日历

---

#### config/watchlist.json — 自选股

**用途：** 用户关注的股票列表，包含代码、名称、方向分类、行业归属。由页面自助添加/删除。

```json
{
  "stocks": [
    {"code": "000062", "name": "深圳华强", "direction": "算力硬件.算力", "industry": "其他电子"},
    {"code": "300308", "name": "中际旭创", "direction": "算力硬件.光模块", "industry": "通信设备"}
  ],
  "count": 296
}
```

#### config/holdings.json — 持仓

**用途：** 当前持仓记录（不含历史已清仓）。直接影响复盘页视图、止损检查、收益计算。

```json
{
  "update_date": "2026-06-14",
  "holdings": [
    {"code": "300308", "name": "中际旭创", "ratio": "0.15", "cost": 128.50, "price": 142.30, "pct": 10.74}
  ],
  "cash_ratio": 0.35
}
```

#### config/trades.json — 交易记录

**用途：** 买卖历史记录，供复盘查看交易流水。

```json
{
  "trades": [
    {"date": "2026-05-21", "type": "卖出", "name": "大族数控", "code": "301200",
     "ratio": "1/3", "reason": "减仓", "note": "卖出1/3仓位，15.76%→10.51%"}
  ]
}
```

#### config/alarms.json — 报警

**用途：** 价格/涨跌幅/成交量条件报警配置，由 alarm_service 读取检查。

```json
{
  "alarms": [
    {"id": "alarm_002409_xxx", "stock": "雅克科技(002409)", "stock_code": "002409",
     "type": "price", "enabled": true,
     "stop_loss": 91.38, "stop_loss_pct": -25.43, "condition": ""}
  ]
}
```

#### config/plan_tracking.json — 计划跟踪

**用途：** 记录预设的买卖计划（买点条件、止损价、追踪执行情况）。

```json
{
  "plans": [
    {"plan_date": "2026-05-26", "type": "buy", "stock": "广钢气体", "code": "688548",
     "condition": "中继买点", "condition_category": "中继买点", "stop_loss": null}
  ],
  "summary": {}
}
```

#### config/manual_trend.json — 手动趋势股

**用途：** 用户手动指定的趋势交易股票列表（独立于3L体系的辅助决策）。

```json
["300308", "002916", "688017"]
```

#### config/directions.json — 方向配置

**用途：** 方向分类体系（如"算力硬件.光模块"），包含子方向和核心推荐。

```json
{
  "version": "3.0",
  "categories": ["算力硬件", "半导体", "AI应用"],
  "sub_directions": {"算力硬件": ["光模块", "PCB", "算力"]},
  "core": ["AI应用"],
  "suggestions": {}
}
```

#### config/watched_industries.json — 关注的行业

**用途：** 用户在页面上标记关注的行业板块列表。

```json
{"industries": ["电子化学品", "半导体", "通信设备"]}
```

#### config/journals.json — 日志

**用途：** 交易心理/操作思考记录。

```json
{
  "entries": [
    {"date": "2026-05-21", "stock": "大族数控",
     "reason": "上升趋势，突破买点...", "stop_loss": "220",
     "point": "回踩买点", "emotion": "冷静"}
  ]
}
```

---

#### computed/scan_result.json — 扫描结果

**用途：** 最新一批买点扫描的完整结果（按方向分组展示）。由 scan_buy_signals.py 或 manual_scan 生成。

```json
{
  "scan_date": "2026-06-14 15:00",
  "data_source": "mootdx",
  "total_signals": 23,
  "results": {
    "算力硬件": [
      {"code": "300308", "name": "中际旭创", "score": 85, "buy_type": "突破买点",
       "price": 142.30, "change_pct": 3.2}
    ]
  }
}
```

#### computed/industry_leaders.json — 领涨股

**用途：** 各行业板块的领涨股（涨幅最高）。用于监控页面展示板块龙头。

```json
{
  "count": 86,
  "by_industry": {
    "半导体": [{"code": "688041", "name": "海光信息", "change_pct": 5.2}]
  },
  "all_stocks": [...]
}
```

#### computed/candidates_data.json — 候选股

**用途：** 候选股的完整K线数据（含多只股票的日线），用于指标计算和回测。

```json
{
  "三花智控": {
    "code": "002050",
    "klines": [
      {"date": "20260401", "open": 43.34, "close": 43.59, "high": 44.0, "low": 43.05, "volume": 77985760}
    ]
  }
}
```

#### computed/analysis_results.json — 分析结果

**用途：** 对候选股的逐只技术面分析结果（关键点、买卖信号、波浪结构等）。

```json
{
  "三花智控": {
    "code": "002050", "closing": 52.92, "change_pct": 1.65,
    "key_points": [
      {"idx": 0, "date": "20260401", "price": 43.59, "type": "前低", "significance": "强"}
    ],
    "buy_signal": {"type": "突破买点", "date": "20260415", "price": 46.20}
  }
}
```

#### computed/mainlines_cache.json — 主线缓存

**用途：** 每日复盘时写入一次的主线判定结果（含行业主线和概念主线）。供趋势候选模块读取。

```json
{
  "lines": ["电子化学品", "半导体", "AI应用"],
  "secondary": ["元件", "非金属材料"],
  "concept_mainline": ["人形机器人", "AI智能体"]
}
```

#### computed/mainline_history.json — 主线历史

**用途：** 每日主线TOP10的归档历史，用于回溯主线演变。

```json
{
  "2026-05-26": {"top10": ["电子化学品", "元件", "非金属材料", "煤炭开采加工", ...]},
  "2026-05-27": {"top10": [...]}
}
```

#### computed/logic_tracking.json — 逻辑追踪

**用途：** AI自动跟踪的信息源归类结果（聚焦分层+前置预判）。

```json
{
  "tags": {"AI应用": {...}, "半导体": {...}},
  "entries": [],
  "forecasts": [],
  "updated_at": "2026-06-14"
}
```

#### computed/sub_sector_clusters.json — 子行业聚类

**用途：** 将同行业个股进一步细分为子集群（用于精细化的板块对比）。

```json
{
  "sub_sector_map": {"688126": "半导体_c0", "688234": "半导体_c1"},
  "clusters": {"半导体": {"c0": {"name": "设备", "stocks": [...]}}}
}
```

#### computed/profit_quality.json — 盈利质量

**用途：** 盈利质量检查结果（ROE/毛利率/现金流等因子过滤）。

```json
{
  "scan_date": "2026-06-14",
  "total": 50, "pass_count": 23, "fail_count": 27
}
```

#### computed/source_health.json — 数据源健康

**用途：** 各数据源的健康状态（UP/DOWN/DEGRADED）和故障转移记录。

```json
{
  "sources": {
    "tushare": {"status": "UP", "last_success": "2026-06-14 07:00"},
    "tencent": {"status": "UP", "last_success": "2026-06-14 07:00"}
  },
  "transitions": [...]
}
```

#### computed/key_points/ — 关键点

**用途：** 按个股存储的关键点标记（支撑/阻力/突破位），每只股票一个文件。

```json
// computed/key_points/中际旭创_300308.json
{"code": "300308", "name": "中际旭创", "points": [
  {"date": "20260401", "price": 42.50, "type": "支撑", "strength": "强"}
]}
```

#### computed/workbench/ — 工作台

**用途：** 每日工作台记录（思考/重点方向/待办事项），按日期分文件。

```json
// computed/workbench/2026-06-14.json
{"date": "2026-06-14", "focus": ["AI应用"], "todos": ["检查xxx买点"]}
```

---

#### public/pinyin.json — 拼音首字母

**用途：** 前端股票搜索时按拼音首字母快速定位。原 `pinyin_initials.json` 移植，`/pub/pinyin.json` 直接服务。

```json
{
  "000001": "PAH", "000002": "WKA", "000004": "GNKJ",
  "000005": "ZXYS", "000006": "SZY"
}
```

#### public/external_mapping.json — 外部数据映射

**用途：** 前端展示外部链接时的代码→名称映射。

#### public/index_data.json — 指数展示数据

**用途：** 前端大盘走势图所需的指数数据（由后端定时生成）。

#### public/panic_history.json — 恐慌历史

**用途：** 历史恐慌事件记录，前端恐慌图展示。

#### public/sounds/alarm_sounds.json — 报警音效

**用途：** 前端报警触发时的音效配置（用户自定义上传）。

---

#### cache/ — 运行时缓存

**用途：** 各模块运行时产生的缓存文件，按TTL自动清理。无需手动维护。

| 缓存文件 | 用途 | 清理策略 |
|---------|------|---------|
| `buy_signals_YYYY-MM-DD_HHMM.json` | 15分钟扫描的买点信号结果 | 保留最近30天 |
| `volume_snapshots_YYYY-MM-DD.json` | 成交额分布快照 | 保留最近30天 |
| `industry_boards_YYYY-MM-DD.json` | 行业板块日数据 | 保留最近30天 |
| `market_leaders_daily/` | 个股每日领涨排名 | 保留最近30天 |
| `backtest_*.json` | 回测缓存结果 | 手动清理 |
| `watchlist_analysis_cache.json` | 自选股分析缓存 | 自动失效(TTL) |

所有cache文件格式由各自写入模块决定，无统一Schema约束。

### 4.4 计算方式优化

有了 Tushare DB 全量数据后，一些计算结果可以从"定时缓存"改为"按需计算"：

| 当前文件 | 当前方式 | 新方式 |
|---------|---------|--------|
| `financial_data_cache.json` (128K) | 定时拉取财务数据缓存 | **删除** → 从 `daily_basic` 表按需查询 |
| `industry_leaders.json` (104K) | 定时计算领涨股 | 改为按需计算（计算量小，从 stock_basic + stock_daily 聚合即可） |
| `candidates_data.json` (136K) | 定时计算候选股 | 保持不变（扫描结果是耗时计算，适合缓存） |
| `sub_sector_clusters.json` (44K) | 定时计算子行业 | 改为按需计算（从 ths_index + ths_member 聚合） |
| `mainlines_cache.json` (4K) | 复盘时写入一次 | 保持（每日计算一次，供趋势候选模块读取） |

### 4.5 文件路径更新

`config.py` 中的路径常量全部对应更新：

```python
# config.py 新旧对照

# 旧                              → 新
ALL_STOCKS_PATH                   → 删除（DB替代）
SECTOR_DAILY_PATH                 → 删除（DB替代）  
INDEX_DATA_PATH                   → 删除（DB替代）
INDUSTRY_MAP_PATH                 → 删除（DB替代）
ALL_CODES_PATH                    → 删除（DB替代）
CONCEPT_LIST_PATH                 → 删除（DB替代）
STOCK_CONCEPT_MAP_PATH            → 删除（DB替代）
CONCEPT_NAME_MAPPING_PATH         → 删除（DB替代）
FINANCIAL_CACHE_PATH              → 删除（按需计算）
ON_DEMAND_CACHE_PATH              → 删除（不再需要）
SOURCES_EM_SECTOR_DAILY           → 删除（DB替代）
SOURCES_THS_SECTOR_DAILY          → 删除（DB替代）
SOURCES_EM_CONCEPT_MAP            → 删除（DB替代）

WATCHLIST_PATH                    → CONFIG_DIR / 'watchlist.json'
HOLDINGS_PATH                     → CONFIG_DIR / 'holdings.json'
TRADES_PATH                       → CONFIG_DIR / 'trades.json'
PINYIN_PATH                       → CONFIG_DIR / 'pinyin.json'
DIRECTIONS_PATH                   → CONFIG_DIR / 'directions.json'

LATEST_SCAN_PATH                  → COMPUTED_DIR / 'scan_result.json'
INDUSTRY_LEADERS_PATH             → COMPUTED_DIR / 'industry_leaders.json'
MAINLINES_CACHE_PATH              → COMPUTED_DIR / 'mainlines_cache.json'
KEY_POINTS_DIR                    → COMPUTED_DIR / 'key_points'
```

新的顶层路径常量：

```python
# 新增
TUSHARE_DB_PATH   = os.path.join(DATA_DIR, 'tushare.db')
CONFIG_DIR        = os.path.join(DATA_DIR, 'config')
COMPUTED_DIR      = os.path.join(DATA_DIR, 'computed')
CACHE_DIR         = os.path.join(DATA_DIR, 'cache')    # 已有，不变
```

## 5. 双账号策略

### 5.1 账号分工

| 阶段 | 使用账号 | 工作内容 | 需解锁的接口 |
|------|---------|---------|------------|
| **一次性回填** | 15000积分账号 | 全量回填2年历史数据。高积分解锁全部接口，包括 ths_daily（需6000分）。 | `daily`, `daily_basic`, `adj_factor`, `index_daily`, `ths_daily`, `ths_index`, `ths_member`, `stock_basic`, `trade_cal` |
| **每日增量** | 2000 + 15000 | 2000账号调日常接口（daily/daily_basic/index_daily等），ths_daily 切15000账号跑（仅10次调用/天）。 | 2000: `daily`, `daily_basic`, `index_daily` … 15000: `ths_daily` |

### 5.2 回填策略（15000积分账号 → 一次性）

**步骤:** 全量数据回填，分批执行确保不超200次/分钟限制。

```
回填顺序:
1. stock_basic        → 1次调用，5000+只A股
2. ths_index          → 1次调用，获取全部板块列表
3. ths_member         → ~500次调用，获取各板块成分股
4. stock_daily        → 分批回填(500只/批)，每批1次
5. daily_basic        → 分批回填(500只/批)，每批1次
6. index_daily        → 4次调用（上证/科创/全指/创业板）
7. ths_daily          → 分批回填(~500个板块)
8. adj_factor         → 分批回填(500只/批)
9. trade_cal          → 1次调用

回填脚本: scripts/backfill_tushare.py
每次回填后打印进度+预估剩余调用次数。
```

**限流策略：**
```python
# Tushare Pro 限制: 200次/分钟
# 安全策略: 150次/分钟 (留50次余量)
# 每批调用后 sleep(60/150) ≈ 0.4秒
BATCH_INTERVAL = 0.4  # 秒
BATCH_SIZE = 200      # 最大每批股票数
```

**历史深度：** 回填最近 **2年**（2024-01 ~ 2026，约500个交易日）的日线数据。覆盖完整牛熊周期，足够EMA分析、波谷判定、买点回测使用。后续增量更新自动累积。

### 5.3 每日增量（2000积分账号 → 日常）

```python
# 每日cron运行:
# 1. 获取最新交易日 trade_cal
# 2. 检查各表最大日期
# 3. 增量拉取当日数据
# 4. 写入数据库

def daily_update():
    # 获取最新交易日
    latest = get_latest_trade_day()  # '20260613'
   
    # 各表增量追加
    for table, api in [
        ('stock_daily', 'daily'),        # 自选股+持仓股
        ('daily_basic', 'daily_basic'),
        ('index_daily', 'index_daily'),  # 4个指数
        ('ths_daily', 'ths_daily'),      # 所有板块
        ('adj_factor', 'adj_factor'),    # 自选股+持仓股
    ]:
        data = api(ts_code_list, trade_date=latest)
        db.insert(table, data)
```

**2000积分/天的日常调用量：**
```
stock_daily:   50只 × 1次 = 1次
daily_basic:   50只 × 1次 = 1次
ths_daily:    ~500板块 × 1次 = 1次
index_daily:   4指数 × 1次 = 1次
ths_member:    ~50板块 × 1次(按需)
adj_factor:   50只 × 1次 = 1次(按需)
trade_cal:     1次

所有接口调用不消耗积分，受限于200次/分钟频率。
自选股~50只的日常更新完全够用 ✅
```

**注意:** 板块K线(ths_daily)、指数(index_daily)、成分股(ths_member)等接口无需额外权限门槛，2000积分账号即可调用。日常调用完全在200次/分钟频率限制内。

---

## 6. 与现有系统集成

### 6.1 数据流变化

```
当前:
  update_stock_data.py → mootdx → JSON(all_stocks_60d.json)
  refresh_sectors.py → akshare/push2test → JSON(sector_daily.json)

改为:
  一次性: backfill_tushare.py → 15000积分账号 → SQLite DB (历史全量)
  每日:   daily_update_tushare.py → 2000积分账号 → SQLite DB (增量)
  
  查询:   data_layer.py → SQLite DB → 返回现有合约(Kline等)
```

### 6.2 data_layer.py 改造

现有 `data_layer.py` 的功能接口**完全保留不动**，只在底层增加 SQLite 读取路径：

```python
# data_layer.py 新增内部模块
from backend.services.tushare_db import TushareDB

_db = TushareDB()  # SQLite 连接

def get_stock_klines(code, direction=None, stocks=None):
    """保持现有接口不变，内部增加DB读取路径"""
    # 1. 先尝试从 DB 读取（历史全量）
    rows = _db.query_stock_daily(code, limit=60)
    if rows and len(rows) >= 30:
        return rows
    
    # 2. DB无数据→回退旧JSON路径（过渡期）
    return _legacy_get_stock_klines(code, direction, stocks)
```

**过渡期双写策略：**
```
Phase 1: 回填DB + 双写DB和JSON → 业务代码无感知
Phase 2: DB验证OK后，业务代码默认读DB
Phase 3: 确认稳定后，删除JSON路径
```

### 6.3 板块数据改造

当前板块K线和快照存储在 `sector_daily.json` 中，迁移后：

```
当前:
  get_sector_klines('电子', 'industry') → sector_daily.json

改为:
  get_sector_klines('电子', 'industry') → 
    1. ths_index表查 '电子' 的 ts_code ('881121.TI')
    2. ths_daily表查 K线
    3. 返回 [{date, open, close, high, low, volume}]
```

需要维护**板块名称 ↔ ts_code** 的映射（`ths_index` 表已包含）。

---

## 7. 实施步骤

### Phase 0: 基建（0.5天）
- [ ] 安装 Tushare
- [ ] 创建 `TushareDB` 类（SQLite连接+建表+CRUD）
- [ ] 创建双token管理
- [ ] 写入现有 config.py（新增 DB_PATH, TUSHARE_TOKEN_HIGH, TUSHARE_TOKEN_LOW）

### Phase 1: 一次性回填（1-2天，15000积分账号）
- [ ] 回填 `stock_basic`（全量A股列表+行业归属）
- [ ] 回填 `ths_index` + `ths_member`（板块列表+成分股）
- [ ] 回填 `stock_daily`（分批，500只/批）
- [ ] 回填 `daily_basic`（PE/PB/市值历史）
- [ ] 回填 `index_daily`（4个指数）
- [ ] 回填 `ths_daily`（所有板块）
- [ ] 回填 `adj_factor`（复权因子）
- [ ] 回填 `trade_cal`（交易日历）

### Phase 2: 数据验证（1天）
- [ ] A/B对比: DB vs JSON (stock_daily, sector_daily)
- [ ] A/B对比: DB vs 腾讯财经 (PE/PB/市值)
- [ ] A/B对比: DB vs 同花顺THS (板块K线)
- [ ] 全量交叉验证脚本

### Phase 3: 代码改造（2-3天）
- [ ] data_layer.py 增加SQLite读取路径
- [ ] update_stock_data.py 改用 daily_update_tushare.py
- [ ] refresh_sectors.py 改用DB
- [ ] 双写过渡（DB+JSON并行）
- [ ] 删除旧JSON路径（验证后）

### Phase 4: 日常cron切换（0.5天）
- [ ] 配置 daily_update_tushare.py 为cron
- [ ] 停掉旧的 mootdx + akshare 更新流程
- [ ] 监控 + 告警

---

## 8. 风险与注意事项

### 8.1 板块代码映射（已识别）

当前系统用中文板块名称作为key，Tushare 用 `ts_code`（如 `881121.TI`）。

**方案：** `ths_index` 表同时存储 `name`（中文名）和 `ts_code`，提供双向查询：
```python
# 中文名 → ts_code
ts_code = db.get_ths_code_by_name('人工智能')

# 覆盖当前 get_sector_klines('人工智能', 'concept') 的调用
```

### 8.2 前复权价格差异

Tushare 前复权 vs 当前 mootdx 手动矫正：
- Tushare：统一用 `adj='qfq'` 参数获取前复权数据
- 当前：mootdx bars 原始数据 + xdxr 手动矫正

**方案：** 回填时存储**不复权价格** + 单独的 `adj_factor` 表，应用层统一使用 Tushare 复权因子计算前复权。这样日后调整复权方式无需重新拉取。

但最简方案：直接用 `adj='qfq'` 参数获取前复权数据存储到 `stock_daily`。

**验证：** A/B对比脚本比较DB复权价格与当前mootdx价格差异阈值（价差<1%即通过）。

### 8.3 当前JSON文件的过渡期

已有用户持仓/自选股的判断逻辑依赖 `all_stocks_60d.json` 中的K线数据。

**方案：** 过渡期 JSON 和 DB 双写，`data_layer` 优先读 DB，DB 无数据时回退 JSON。过渡期结束后删除 JSON 路径。

### 8.4 各接口权限门槛

Tushare 积分是权限等级，每个接口有最低积分要求。以下是我们需要的接口及其门槛：

| 接口名 | 最低积分 | 15000账号 | 2000账号 |
|--------|---------|-----------|---------|
| `stock_basic` | 免费 | ✅ | ✅ |
| `trade_cal` | 免费 | ✅ | ✅ |
| `index_daily` | 免费 | ✅ | ✅ |
| `ths_daily` | **6000** | ✅ | ❌ |
| `ths_index` | 免费 | ✅ | ✅ |
| `ths_member` | 免费 | ✅ | ✅ |
| `daily` | 2000 | ✅ | ✅ |
| `daily_basic` | 2000 | ✅ | ✅ |
| `adj_factor` | 2000 | ✅ | ✅ |

**结论：** 2000积分账号可调用大部分接口，但 `ths_daily` 需要6000分，需用15000账号。
日常增量中，2000账号跑 daily/daily_basic/index_daily，ths_daily 切15000账号。

### 8.5 数据库备份

SQLite 单文件，每天cron `cp tushare.db backup/tushare_$(date +%Y%m%d).db` 即可。

---

## 9. 与现有数据源的关系

| 数据类型 | 迁移后主源 | 保留源 | 何时用保留源 |
|---------|-----------|-------|------------|
| 个股K线 | Tushare daily (DB) | mootdx | DB不可用时 |
| 实时行情(价格) | Tushare daily最新 | 腾讯财经 | 盘中使用(DB只有日线) |
| PE/PB/市值 | Tushare daily_basic | 腾讯财经 | DB不可用 |
| 指数K线 | Tushare index_daily | mootdx | DB不可用时 |
| 板块K线 | Tushare ths_daily | JSON备份 | DB不可用时 |
| 板块快照 | Tushare ths_daily最新 | JSON | DB不可用时 |
| 概念归属 | Tushare ths_member | JSON | DB不可用时 |
| 涨跌停价 | — | 腾讯财经 | 保留(盘中) |
| 题材归因 | — | 同花顺热点 | 保留(独家) |
| 五档盘口 | — | mootdx | 保留(盘中实时) |
| 资金流向/龙虎榜 | — | 东财 | 保留(Tushare无) |

---

## 10. 代码结构

```
server/backend/
├── services/
│   ├── data_source.py          # 现有 → 新增Tushare数据源链
│   ├── tushare_db.py           # 【新增】SQLite ORM封装
│   │
├── core/
│   ├── data_layer.py           # 现有 → 新增DB读取路径
│   ├── update_stock_data.py    # 现有 → 保留(可选)
│   │
├── scripts/
│   ├── daily_update_tushare.py # 【新增】每日增量更新cron脚本
│   └── backfill_tushare.py     # 【新增】一次性回填脚本(15000账号)

data/
└── tushare.db                  # SQLite数据库文件
```

### tushare_db.py 核心设计

```python
"""
Tushare SQLite 数据库封装层
- 建表(初始化)
- 批量写入(upsert)
- 查询封装(get_stock_daily, get_daily_basic, ...)
- 双token管理
"""

import sqlite3
import tushare as ts

class TushareDB:
    def __init__(self, db_path, token_high, token_low):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")  # 支持读写并发
        self.token_high = token_high  # 15000积分账号
        self.token_low = token_low    # 2000积分账号
        self._init_tables()
    
    def _init_tables(self):
        """建表SQL（CREATE TABLE IF NOT EXISTS）"""
    
    def upsert_many(self, table, df):
        """批量upsert：DataFrame → INSERT OR REPLACE"""
    
    def get_stock_daily(self, ts_code, start_date=None, limit=60):
        """查询个股日线"""
    
    def get_daily_basic(self, ts_code, trade_date=None):
        """查询每日指标"""
    
    def get_ths_code_by_name(self, name):
        """中文板块名 → ts_code"""
    
    def get_ths_name_by_code(self, ts_code):
        """ts_code → 中文板块名"""
    
    def get_sector_klines(self, sector_name, sector_type, limit=120):
        """获取板块K线"""
    
    def get_index_klines(self, ts_code, limit=500):
        """获取指数K线"""
```

### backfill_tushare.py 核心逻辑

```python
"""
一次性回填脚本 — 使用15000积分账号
从Tushare拉取全量历史数据写入SQLite
"""

def backfill_all():
    db = TushareDB(token=token_high)
    pro = ts.pro_api(token_high)
    
    # 1. stock_basic - 免费
    df = pro.stock_basic()
    db.upsert_many('stock_basic', df)
    
    # 2. ths_index - 免费
    df_i = pro.ths_index(type='I')  # 行业
    df_n = pro.ths_index(type='N')  # 概念
    db.upsert_many('ths_index', pd.concat([df_i, df_n]))
    
    # 3. ths_member - 免费
    for _, row in ths_index.iterrows():
        df = pro.ths_member(ts_code=row['ts_code'])
        db.upsert_many('ths_member', df)
    
    # 4. stock_daily - 分批，每次最多500只
    codes = get_all_ts_codes()
    for batch in chunks(codes, 500):
        df = pro.daily(ts_code=','.join(batch), 
                       start_date='20240101', 
                       end_date=today)
        db.upsert_many('stock_daily', df)
    
    # 5. index_daily - 免费
    for index_code in ['000985.SH', '000001.SH', '000688.SH', '399006.SZ']:
        df = pro.index_daily(ts_code=index_code, start_date='20240101')
        db.upsert_many('index_daily', df)
    
    # ... 后续表类似
```

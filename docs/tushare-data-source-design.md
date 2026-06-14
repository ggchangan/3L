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

## 3. 双账号策略

### 3.1 账号分工

| 阶段 | 使用账号 | 工作内容 | 需解锁的接口 |
|------|---------|---------|------------|
| **一次性回填** | 15000积分账号 | 全量回填6年以上历史数据。高积分解锁全部接口，部分接口有最低积分门槛（如 `adj_factor` 等）。 | `daily`, `daily_basic`, `adj_factor`, `index_daily`, `ths_daily`, `ths_index`, `ths_member`, `stock_basic`, `trade_cal` |
| **每日增量** | 2000积分账号 | 每日追加最新数据+日常查询。2000积分已可调用核心接口 `daily` / `daily_basic` / `ths_daily` 等。 | `daily`, `daily_basic`, `index_daily`, `ths_daily`, `ths_index`, `stock_basic`, `trade_cal` |

### 3.2 回填策略（15000积分账号 → 一次性）

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

### 3.3 每日增量（2000积分账号 → 日常）

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

## 4. 与现有系统集成

### 4.1 数据流变化

```
当前:
  update_stock_data.py → mootdx → JSON(all_stocks_60d.json)
  refresh_sectors.py → akshare/push2test → JSON(sector_daily.json)

改为:
  一次性: backfill_tushare.py → 15000积分账号 → SQLite DB (历史全量)
  每日:   daily_update_tushare.py → 2000积分账号 → SQLite DB (增量)
  
  查询:   data_layer.py → SQLite DB → 返回现有合约(Kline等)
```

### 4.2 data_layer.py 改造

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

### 4.3 板块数据改造

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

## 5. 实施步骤

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

## 6. 风险与注意事项

### 6.1 板块代码映射（已识别）

当前系统用中文板块名称作为key，Tushare 用 `ts_code`（如 `881121.TI`）。

**方案：** `ths_index` 表同时存储 `name`（中文名）和 `ts_code`，提供双向查询：
```python
# 中文名 → ts_code
ts_code = db.get_ths_code_by_name('人工智能')

# 覆盖当前 get_sector_klines('人工智能', 'concept') 的调用
```

### 6.2 前复权价格差异

Tushare 前复权 vs 当前 mootdx 手动矫正：
- Tushare：统一用 `adj='qfq'` 参数获取前复权数据
- 当前：mootdx bars 原始数据 + xdxr 手动矫正

**方案：** 回填时存储**不复权价格** + 单独的 `adj_factor` 表，应用层统一使用 Tushare 复权因子计算前复权。这样日后调整复权方式无需重新拉取。

但最简方案：直接用 `adj='qfq'` 参数获取前复权数据存储到 `stock_daily`。

**验证：** A/B对比脚本比较DB复权价格与当前mootdx价格差异阈值（价差<1%即通过）。

### 6.3 当前JSON文件的过渡期

已有用户持仓/自选股的判断逻辑依赖 `all_stocks_60d.json` 中的K线数据。

**方案：** 过渡期 JSON 和 DB 双写，`data_layer` 优先读 DB，DB 无数据时回退 JSON。过渡期结束后删除 JSON 路径。

### 6.4 各接口权限门槛

Tushare 积分是权限等级，每个接口有最低积分要求。以下是我们需要的接口及其门槛：

| 接口名 | 最低积分 | 15000账号 | 2000账号 |
|--------|---------|-----------|---------|
| `stock_basic` | 免费 | ✅ | ✅ |
| `trade_cal` | 免费 | ✅ | ✅ |
| `index_daily` | 免费 | ✅ | ✅ |
| `ths_daily` | 免费 | ✅ | ✅ |
| `ths_index` | 免费 | ✅ | ✅ |
| `ths_member` | 免费 | ✅ | ✅ |
| `daily` | 2000 | ✅ | ✅ |
| `daily_basic` | 2000 | ✅ | ✅ |
| `adj_factor` | 2000 | ✅ | ✅ |

**结论：** 2000积分账号即可调用我们需要的全部接口。
15000积分账号的优势在于**一次性回填**时更高的调用频率容忍度，以及日后可能需要的**高级接口**（如资金流向、财务数据等）。

### 6.5 数据库备份

SQLite 单文件，每天cron `cp tushare.db backup/tushare_$(date +%Y%m%d).db` 即可。

---

## 7. 与现有数据源的关系

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

## 8. 代码结构

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

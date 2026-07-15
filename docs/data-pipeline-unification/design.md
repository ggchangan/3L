# 数据管线统一 — 设计文档 v1

> **日期:** 2026-06-16
> **状态:** 设计阶段

## 1. 背景与问题

### 现状

当前 `update_stock_data.py`（06:00 cron）的管线是**多数据源拼凑**，不是统一的 Tushare + MySQL 管线：

| 数据 | 当前数据源 | 存储目标 | 问题 |
|------|-----------|---------|------|
| **个股K线** | 读 `stock_daily` DB | 缓存（另一个DB表） | 没人写新数据进 `stock_daily`，`fill_history.py --daily` 是唯一的写入入口但**没配 cron** |
| **指数K线** | akshare → 腾讯HTTP | JSON缓存文件（`index_data.json`） | 不走 `index_daily` DB表。DB表有数据但不用 |
| **板块K线** | akshare THS | `ths_daily` DB ✅ | 正确，保留 |
| **板块快照** | akshare THS summary | JSON | **06:00跑必挂**（非交易时段HTML表格返回空），14项验证失败 |
| **行业映射** | push2test HTTP `f100` | `stock_industry_map.json` | 外部HTTP依赖。`ths_member`+`ths_index` DB已有同花顺行业数据 |
| **概念映射** | push2test HTTP `f103` | `concept_list.json` + `stock_concept_map.json` | 同上。`ths_member`+`ths_index` DB已有成分股数据 |

### 痛点

1. **个股K线断流**：`stock_daily` 表只进不出，新交易日的数据没人往里写。过几天数据就停更了
2. **指数走JSON，不走DB**：`index_daily` DB表里有2360行历史数据但日常更新用 akshare 写到 JSON
3. **行业/概念走外部HTTP**：push2test 依赖网络，无必要（DB已有同花顺 `ths_index`+`ths_member`）
4. **板块快照06:00必挂**：同花顺 `stock_board_industry_summary_ths()` 非交易时段返回空HTML

### 目标

一个 cron（06:00交易日），全部数据走 **Tushare 2000分 → MySQL DB → 缓存重建** 的完整链路，消除外部 HTTP 依赖（push2test/akshare板块快照）。

## 2. 设计思想

### 2.1 核心理念

**DB 是唯一权威源。** Tushare 负责灌数据进 DB，`update_stock_data.py` 负责从 DB 读数据做缓存重建和业务计算。不再依赖中间 HTTP API 做数据获取。

### 2.2 方案选择

| 候选方案 | 优点 | 缺点 | 结论 |
|:--------|:----|:----|:----:|
| **A：合到 `update_stock_data.py` 里** | 一个cron管完，简单 | 改动较大（重写3个函数） | ✅ |
| B：加 `fill_history.py --daily` cron | 不改现有代码 | 两个脚本，逻辑分散，容易遗忘 | ❌ |

### 2.3 数据源变更总览

| 阶段 | 旧数据源 | 新数据源 | 理由 |
|:----:|---------|---------|------|
| 个股K线增量 | ❌ 不存在 | Tushare `api.daily`(2000分) | 日常增量唯一合法路径 |
| 指数K线增量 | akshare → 腾讯HTTP | Tushare `api.index_daily`(2000分) | 统一走Tushare，消除akshare依赖 |
| 行业映射 | push2test `f100` | `ths_member` + `ths_index(type=I)` **DB** | 消除HTTP依赖，DB已有 |
| 概念映射 | push2test `f103` | `ths_member` + `ths_index(type=N)` **DB** | 消除HTTP依赖，DB已有 |
| 板块快照 | akshare THS summary | **删除** | 06:00跑必挂，无用 |

### 2.4 命名体系变更（重要）

`industry_map.json` 当前使用 **申万二级行业**（128个，如`玻璃玻纤`、`通信设备`）。

`ths_index` type=I 使用 **同花顺行业分类**（1080个，更细粒度，有Ⅲ/Ⅳ后缀）。

→ **切换到同花顺行业体系**。行业名如`电子化学品Ⅲ`、`玻璃制造`、`玻纤制造`、`通信线缆及配套`。

**影响面：** 16+个Python文件，275+处 `ths_industry` 引用。但行业名只用作展示和分组，不参与逻辑计算，所以不影响正确性。所有消费者（stock_card、review、watchlist等）只是按行业名做字符串比较和展示。

### 2.5 这个功能不做什么

- **不改板块K线**：akshare THS 写入 `ths_daily` DB 保持不变（Tushare `ths_daily` 需15000分，2000分做不了）
- **不改测试**：现有测试 mock 了行业映射，不受命名变更影响
- **不做 daily_basic 增量**：Tushare 2000分可调但当前系统不用 `daily_basic` 表的数据，先不加
- **不改 `adj_factor`**：除权除息非日常事件，当前前复权算法用 `_apply_qfq_batch` 读 `adj_factor` 表已有数据

## 3. 数据模型

### 3.1 `stock_industry_map.json` 格式不变

```json
// 行业名变了（从申万二级→同花顺行业），但格式不变
{
  "000001": {"code": "000001", "name": "平安银行", "ths_industry": "银行"},
  "600519": {"code": "600519", "name": "贵州茅台", "ths_industry": "白酒Ⅲ"},
  ...
}
```

### 3.2 `concept_list.json` + `stock_concept_map.json` 格式不变

概念本身就是同花顺体系（与 `ths_index` type=N 一致），名称为精确对应。

### 3.3 增量数据写入表

| DB表 | 写入方式 | 数据源 |
|------|---------|--------|
| `stock_daily` | `db.upsert_many('stock_daily', df)` | Tushare `api.daily(trade_date=昨天)` |
| `index_daily` | `db.upsert_many('index_daily', df)` | Tushare `api.index_daily(ts_code=XXX, start_date=昨天, end_date=昨天)` |

### 3.4 行业映射 DB 查询

```sql
-- stock → industry（同花顺行业）
SELECT m.con_code, i.name 
FROM ths_member m 
JOIN ths_index i ON m.ts_code = i.ts_code 
WHERE i.type = 'I'

-- stock → concept（同花顺概念）
SELECT m.con_code, i.name 
FROM ths_member m 
JOIN ths_index i ON m.ts_code = i.ts_code 
WHERE i.type = 'N'
```

## 4. 系统设计

### 4.1 架构总览（before/after）

**Before（当前）：**

```
cron 06:00 → update_stock_data.py
  ├── 行业映射    push2test HTTP ───────────────────────→ stock_industry_map.json
  ├── 概念映射    push2test HTTP ───────────────────────→ concept_list.json + stock_concept_map.json
  ├── 个股更新    stock_daily DB（只读，无人写新数据）──→ 缓存
  ├── 指数更新    akshare 腾讯HTTP ─────────────────────→ index_data.json（JSON缓存，不走DB）
  ├── 板块K线     akshare THS ─────────────────────────→ ths_daily DB ✅
  └── 板块快照    akshare THS summary ─────────────────→ JSON（06:00必挂❌）
```

**After（统一后）：**

```
cron 06:00 → update_stock_data.py
  ├── [NEW] Tushare增量 ── api.daily + api.index_daily ──→ stock_daily + index_daily DB
  ├── [RWR] 行业映射     ths_member + ths_index(I) DB ──→ stock_industry_map.json
  ├── [RWR] 概念映射     ths_member + ths_index(N) DB ──→ concept_list.json + stock_concept_map.json
  ├── [KEEP]个股更新     stock_daily DB（已有新数据）───→ 缓存
  ├── [RWR] 指数更新     index_daily DB ────────────────→ 缓存（代替JSON）
  ├── [KEEP]板块K线      akshare THS ──────────────────→ ths_daily DB ✅
  └── [DEL] 板块快照     删除
```

备注：`[NEW]`=新增 `[RWR]`=重写 `[KEEP]`=保留 `[DEL]`=删除

### 4.2 核心逻辑

#### Tushare 增量拉取（新增）

```python
def fetch_tushare_daily_incremental():
    """拉取最新交易日数据到 stock_daily + index_daily"""
    # 1. 确定最新交易日
    trade_date = get_last_completed_trading_day()  # 已存在的函数
    
    # 2. 检查是否已有数据（防重复拉取）
    if has_data_for_date('stock_daily', trade_date):
        log(f'stock_daily 已有 {trade_date} 数据，跳过')
    else:
        df = api.daily(trade_date=trade_date)
        db.upsert_many('stock_daily', df)
        time.sleep(0.6)
    
    # 3. 指数
    if has_data_for_date('index_daily', trade_date):
        log(f'index_daily 已有 {trade_date} 数据，跳过')
    else:
        for ts_code in INDEX_CODES.keys():
            df = api.index_daily(ts_code=ts_code, start_date=trade_date, end_date=trade_date)
            if df is not None and not df.empty:
                db.upsert_many('index_daily', df)
            time.sleep(0.6)
```

#### 行业映射从 DB 构建（重写）

```python
def update_industry_map():
    """从 ths_member + ths_index 重建 stock_industry_map.json"""
    query = """
        SELECT m.con_code, m.con_name, i.name 
        FROM ths_member m 
        JOIN ths_index i ON m.ts_code = i.ts_code 
        WHERE i.type = 'I'
    """
    rows = db.query(query)
    result = {}
    for row in rows:
        code = row['con_code'].replace('.SZ', '').replace('.SH', '')
        name = row['con_name']
        industry = row['name']
        result[code] = {'code': code, 'name': name, 'ths_industry': industry}
    save_industry_map(result)
```

#### 概念映射从 DB 构建（重写）

```python
def update_concept_maps():
    """从 ths_member + ths_index 重建概念映射"""
    # ... 类似方式从 DB 构建 concept_list.json + stock_concept_map.json
```

#### 指数更新改读 DB（重写）

```python
def update_index():
    """从 index_daily DB 表重建缓存"""
    data = data_source.get_index_data_from_db(INDEX_CODES.keys())
    # 转换为需要的格式，保存
    save_index_data(data)
```

### 4.3 API 设计

**无变化。** 所有 API 通过 `data_layer` 读数据，后端数据源变更对前端透明。

### 4.4 影响范围

| 数据类型 | 消费者文件数 | 风险 |
|---------|:----------:|:----:|
| `industry_map`（行业名变更） | 16+文件，275+引用 | **中** — 行业名只做展示和分组，不影响逻辑。但行业排名页面显示的名称会变 |
| 概念映射（来源变更） | 10+文件 | **低** — 概念名不变（本身就是同花顺体系），只是数据来源从 push2test 改为 DB |
| 指数（JSON→DB） | 5+文件 | **低** — `data_layer` 已有 DB 读取路径，改 `update_index()` 读取端即可 |

## 5. 执行计划

详见：[数据管线统一 — 执行计划](plan.md)

## 6. 附录

### 6.1 Tushare 2000分调用量估算

| API | 每次增量调用次数 | 耗时 |
|-----|:--------------:|:----:|
| `api.daily(trade_date=昨日)` | 1次 | ~5s（含0.6s间隔） |
| `api.index_daily(ts_code=4个指数)` | 4次 | ~4s（含0.6s间隔） |
| **合计** | **5次** | **~10s** |

2000分 | 200次/分钟限制，5次完全无压力。

### 6.2 同花顺行业 vs 申万行业差异

| 申万二级举例 | 同花顺对应 | 
|:-----------|:----------|
| `玻璃玻纤` | `玻璃制造`、`玻纤制造`（拆成2个） |
| `电子化学品` | `电子化学品`、`电子化学品Ⅲ`（多一个子分类） |
| `通信设备` | `通信线缆及配套`、`通信网络设备及器件`、`通信终端及配件`（拆成多个） |

这会影响：行业排名页面的行业名显示、复盘页面的行业分组。但数值计算结果不受影响。

### 6.3 文件清单

**修改：**
- `server/backend/core/update_stock_data.py` — 主要改动（新增Tushare增量+重写行业/概念/指数+删除快照）
- `server/backend/data_access/data_layer.py` — 可能需新增 `fetch_index_data_from_db()` 等包装

**新增：**
- `docs/data-pipeline-unification/design.md` — 本设计文档
- `docs/data-pipeline-unification/plan.md` — 执行计划

### 6.4 开放问题

1. `ths_member` 中的 `con_code` 带 `.SZ`/`.SH` 后缀，需要 strip。当前 `industry_map.json` 用的是纯6位代码。对齐处理。
2. `ths_member` 中一只股票可能属于多个同花顺行业（如某个股票既是`银行`又是`银行Ⅲ`），去重策略取最长/最短？
3. 板块快照删除后，`get_sector_push2test()` 和相关 API 端点返回空数据，是否影响前端展示？（前端宏观页面依赖板块快照做当日排行）

### 6.5 变更记录

| 版本 | 日期 | 变更内容 |
|:----|:----|:--------|
| v1 | 2026-06-16 | 初稿 |

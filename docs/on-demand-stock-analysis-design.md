# 按需个股数据拉取 — 设计文档

> 版本: v0.2 | 日期: 2026-05-29 | 分支: feature/stock-analysis-enhance | 状态: ✅ 已实现

---

## 一、背景

个股分析页面（主 SPA + 独立页）目前只能分析 **cron 已拉取过 K 线数据的股票**（自选股 + 主线板块成分股）。用户搜索其他 A 股时，即使能从 `all_a_stocks.json` 搜到代码和名字，也会因为缺少 K 线数据而报"数据不足30条"。

需要设计一种机制：用户搜索未缓存的股票时，**按需拉取数据并分析**。

## 二、设计原则

1. **不影响现有管线** — cron 17:00 的拉取逻辑不变，不污染 `all_stocks_60d.json`
2. **独立缓存** — 新增 `stock_on_demand_cache.json`，cron 不碰
3. **自清洁** — TTL=1天，最多保留30只，不会无限膨胀
4. **快速** — 首次0.2s，同一天重复搜索立即命中

## 三、数据流

```
用户搜索"300894 火星人"
  ↓
① resolve_stock(stocks) — 在 all_stocks_60d.json 找不到
  ↓
② search_stock_full_market(query) — 在 all_a_stocks.json 找到 code+name
  ↓
③ try_on_demand_fetch(code)
  ├─ stock_on_demand_cache.json 有今天的缓存吗？
  │   ├─ 有 → 直接返回 (klines, direction)，0ms
  │   └─ 没有 → akshare 拉60天K线（~0.2s）
  │       ├─ 格式转换（akshare列名→内部格式）
  │       ├─ stock_industry_map.json 查行业→方向
  │       └─ 写入 cache
  ↓
④ inject 到 stocks dict（`stocks[direction][code] = klines`）
  ↓
⑤ _analyze() 正常执行（结构/阶段/信号/买点/诊断）
```

## 四、文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `server/backend/core/on_demand_stock.py` | 按需拉取 + 缓存管理 + 方向映射 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `server/backend/config.py` | 添加 `ON_DEMAND_CACHE_PATH` |
| `server/backend/services/analysis_service.py` | `search_and_analyze()` 中 resolve_stock 失败后调用 on-demand |

### 新增数据文件

| 文件 | 说明 |
|------|------|
| `{DATA_DIR}/stock_on_demand_cache.json` | 按需拉取的缓存，独立于主数据 |

## 五、核心逻辑

### 5.1 `on_demand_stock.py`

```python
ON_DEMAND_CACHE_PATH = os.path.join(DATA_DIR, 'stock_on_demand_cache.json')
MAX_CACHED_STOCKS = 30
CACHE_TTL_DAYS = 1

def get_or_fetch_stock_data(code) -> (klines, direction, name) | None
 ① 检查 all_stocks_60d.json → 已有则直接返回（不计入cache）
 ② 检查 stock_on_demand_cache.json → 今天缓存命中则返回
 ③ akshare 拉单股60天K线 → 格式转换
 ④ stock_industry_map.json 查行业 → SECTOR_TO_INDUSTRY_MAP 映射方向
 ⑤ 写入缓存（TTL=当天）
 ⑥ 返回 (klines, direction, name)

def _fetch_stock_klines_akshare(code) -> [klines] | None
  - ak.stock_zh_a_hist(symbol=code, period='daily', start_date='90天前', end_date='今天', adjust='qfq')
  - 列名转换：'日期'→'date', '开盘'→'open', '收盘'→'close', '最高'→'high', '最低'→'low', '成交量'→'volume'
  - 保留最近60条
  - 不附加name字段（与mootdx格式一致，name由上层resolve_stock提供）

def _get_stock_direction(code) -> str
  - stock_industry_map.json 查 ths_industry
  - SECTOR_TO_INDUSTRY_MAP 映射到方向
  - 找不到映射 → '其他'
```

### 5.2 缓存格式

```json
{
  "cached_at": "20260529",
  "stocks": {
    "300894": {
      "direction": "其他",
      "klines": [
        {"date": "20260302", "open": 11.40, "close": 11.22, "high": 11.55, "low": 11.15, "volume": 51159},
        ...
      ]
    }
  }
}
```

### 5.3 注入点（analysis_service.py）

```python
def search_and_analyze(query, stocks=None, wl=None):
    stocks = stocks or get_all_stocks()
    wl = wl or get_watchlist()
    wl_codes = set(s['code'] for s in wl)

    q = query.strip()

    # ① 正常搜索
    code, direction, name = resolve_stock(q, stocks)
    if not code:
        # ② 按需拉取
        result = _try_on_demand_fetch(q, stocks)
        if result:
            code, direction, name = result
        else:
            market = search_stock_full_market(q, max_results=1)
            if market:
                return {'error': f'{market[0]["name"]}({market[0]["code"]}) 暂无数据'}
            return {'error': f'未找到股票: {q}'}

    return _analyze(code, direction, name, stocks, wl_codes)

def _try_on_demand_fetch(query, stocks):
    """按需拉取未缓存的股票数据。返回 (code, direction, name) 或 None"""
    from backend.core.on_demand_stock import get_or_fetch_stock_data
    from backend.core.data_layer import search_stock_full_market

    market = search_stock_full_market(query, max_results=1)
    if not market:
        return None

    code = market[0]['code']
    klines, direction, _ = get_or_fetch_stock_data(code)
    if not klines or len(klines) < 30:
        return None

    if direction not in stocks:
        stocks[direction] = {}
    stocks[direction][code] = klines

    return code, direction, market[0]['name']
```

## 六、边界情况

| 场景 | 行为 |
|------|------|
| akshare 拉取失败（网络/限流） | 不写入缓存，返回原错误提示 |
| stock_industry_map.json 无此股 | direction='其他' |
| K线不足30条 | 不缓存，返回"暂无数据" |
| 同一天搜索30+只不同股 | 缓存保留最近30只，旧的自动淘汰 |
| 跨天搜索同一只股 | 缓存过期，重新拉取（需要新数据） |
| 用户后来把这只股加入自选 | 下次 cron 会正常拉取，不再依赖按需缓存 |

## 七、测试要点

1. `test_fetch_klines_akshare` — mock akshare 返回60行数据，验证格式转换
2. `test_cache_hit` — 写入缓存后，第二次搜索直接命中
3. `test_cache_expiry` — 第二天再搜，缓存未命中，触发拉取
4. `test_direction_mapping` — 已知行业映射成功 vs 未知行业回退'其他'
5. `test_inject_and_analyze` — 注入 stocks dict 后，_analyze 正常返回
6. `test_klines_no_name_field` — K线记录不含name字段（与mootdx格式一致）

## 八、非目标

- ❌ cron 不追踪按需缓存中的股票
- ❌ 不自动把搜索过的股加入自选股
- ❌ 不做批量扫描（只针对单只搜索）
- ❌ 财务诊断的 akshare 拉取已有，不改动

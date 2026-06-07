# 数据源验证 — 设计文档 v2

> **核心思想：分层验证。** 数据分了层，验证也分层。
> 每层只验证自己这层的职责，不越级。

```
数据源层 → 数据服务层 → 业务逻辑层 → API层 → 前端展示层
  验证        验证          验证        验证       验证
  原始数据    服务逻辑      计算结果    API响应    页面渲染
```

## 0. 当前问题

### 一次典型的事故（2026-06-05）

```
cron 17:00 跑 update_sectors()
  → 调 push2test 成功，日志说"行业90只更新"  ✅（日志正确）
  → 但没有任何代码把这90条数据存到文件    ❌（旧代码没写 _push2test）
  → 复盘页 chg_1d 用旧的K线算：+5.63%   ❌（用户看到的是6月4日旧数据）
```

**每层都在做什么：**
- 数据源层：push2test 确实返回了数据 ✅
- 数据服务层：`load_sector_daily_uncached()` 正确读文件 ✅
- 业务逻辑层：`get_mainline_data()` 用K线算chg_1d ✅
- API层：返回了正确的JSON结构 ✅
- 前端：页面正常渲染 ✅

**每层看起来都对了，但数据是错的。** 因为**数据管线本身断了**（没写入），而验证只检查了各层的形式正确性，没检查"数据是否流到了下一层"。

### 分层验证要解决的问题

| 问题 | 表现 | 根因 |
|:----|:----|:-----|
| 数据没落盘 | 日志说更新了，文件没变 | 旧代码没写 `_push2test` |
| 日期标记错误 | 周日的数据标成当日 | 用 `datetime.now()` 而非最后一个交易日 |
| 没有端到端验证 | 每层自检都过，但最终页面数据错误 | 各层独立验证，没走完整链路 |

## 1. 分层架构

### 数据分层（现有）

```
┌─────────────────────────────────────────────┐
│  前端展示层（复盘页/盯盘页/个股分析页）        │
├─────────────────────────────────────────────┤
│  API层（review_service / stock_card_service） │
├─────────────────────────────────────────────┤
│  业务逻辑层（get_mainline_data / 主线判定等） │
├─────────────────────────────────────────────┤
│  数据服务层（data_source.py 抽象层）          │
│    get_sector_rankings  → 故障切换链         │
│    get_sector_klines    → 多源合并           │
│    get_merged_sector_data → 缓存管理         │
├─────────────────────────────────────────────┤
│  数据源层（原始数据文件 + API）               │
│    push2test(eastmoney) / EM仓 / THS仓       │
│    legacy sector_daily.json                  │
└─────────────────────────────────────────────┘
```

### 验证分层（对应设计）

```
┌─────────────────────────────┐
│  L5 前端展示验证              │  页面渲染正确性
├─────────────────────────────┤
│  L4 API验证                  │  API响应结构 + 示例值
├─────────────────────────────┤
│  L3 业务逻辑验证              │  计算逻辑正确性
├─────────────────────────────┤
│  L2 数据服务验证              │  服务层逻辑正确性
├─────────────────────────────┤
│  L1 数据源验证                │  原始数据正确性
└─────────────────────────────┘
```

## 2. 各层验证设计

### L1 — 数据源验证（原始数据）

**职责：** 验证原始数据本身是正确的——文件可读、格式正确、值自洽、日期新鲜。

**不需要知道：** 数据结构如何被使用、业务逻辑是什么。

| 验证项 | 方法 | 预期 | 失败后果 |
|:------|:----|:-----|:--------|
| push2test 可达 | HTTP GET → 200 | 成功 | L1 失败 |
| 行业数量 | 返回 diff 数组 | > 400 | DEGRADED |
| 概念数量 | 同上 | > 300 | DEGRADED |
| f3 自洽性 | f3 vs (f2-f18)/f18*100 | 全部偏差 < 0.02% | DEGRADED |
| 数据日期 | `last_updated` 或 `_push2test_updated` | == 最后一个交易日 | L1 失败 |
| EM仓 JSON | `json.load()` | 无异常 | L1 失败 |
| THS仓 JSON | 同上 | 无异常 | L1 失败 |
| Legacy JSON | 同上 | 无异常 | L1 失败 |
| K线日期序 | klines 按 date 升序 | 全部有序 | WARN |
| 关键行业存在性 | 银行/半导体/证券在三个源都存在 | 均存在 | WARN |

**交易日算法：**
```python
def _last_trading_day():
    \"\"\"返回最后一个交易日 YYYYMMDD（周末回退到周五，不计节假日）\"\"\"
    d = datetime.now()
    for _ in range(7):
        if d.weekday() < 5:
            return d.strftime('%Y%m%d')
        d -= timedelta(days=1)
```

### L2 — 数据服务验证（抽象层逻辑）

**职责：** 验证 `data_source.py` 的服务函数逻辑正确——故障切换、多源合并、缓存管理。

**不需要知道：** 业务逻辑怎么用这些数据。

| 验证项 | 方法 | 预期 |
|:------|:----|:-----|
| `get_sector_rankings('industry')` | 调用，检查返回值 | 返回 dict，有 400+ key |
| `get_sector_rankings('concept')` | 同上 | 返回 dict，有 300+ key |
| 返回值含 `change_pct` | 采样 key | 每个都有 |
| `get_sector_klines(name)` | 对已知行业调用 | 返回 list，最后日期是交易日 |
| `get_merged_sector_data()` | 调用 | 含 industries + concepts |
| 故障切换 | 关掉 EM 源（临时）再调 | 自动切到 legacy/THS |
| 缓存一致性 | 连续调2次 `get_merged_sector_data()` | 返回相同数据 |
| EM仓 vs live 一致性 | EM仓 change_pct vs push2test live f3 | 偏差 < 0.5%（同源数据） |

### L3 — 业务逻辑验证

**职责：** 验证业务计算逻辑正确——主线判定、行业排行、chg_1d/chg_20d 计算。

**不需要知道：** 数据从哪个源来、前端怎么展示。

| 验证项 | 方法 | 预期 |
|:------|:----|:-----|
| `get_mainline_data()` 结构 | 调用 | 含 lines/secondary/all_ranked |
| chg_1d 值 | 对比已知行业的预期值 | 与 `_push2test` 或实时源一致 |
| chg_20d 值 | 对比K线计算 | (klines[-1]/klines[-20]-1)*100 |
| 主线排序 | 按 chg_20d 降序 | 前5 = 主线 |
| 概念主线同理 | `get_concept_mainline_data()` | 结构与行业主线一致 |

### L4 — API验证

**职责：** 验证 API 端点返回正确结构、正确值。

**不需要知道：** 前端怎么展示这些值。

| 验证项 | 方法 | 预期 |
|:------|:----|:-----|
| `GET /api/review` | HTTP 调用 | 200 + JSON |
| 返回结构 | 含 lines/secondary/industries | schema 完整 |
| 行业排行 | `GET /api/review` 中 industries | 含 chg_1d/chg_20d |
| 关键行业值 | 电子化学品/半导体/银行 | change_pct 非零（交易日） |

### L5 — 前端展示验证（可选）

**职责：** 验证页面渲染正确。

| 验证项 | 方法 | 预期 |
|:------|:----|:-----|
| 关键数字显示 | 浏览器截图分析 | 与 API 返回值一致 |

## 3. 验证实现

### 3.1 架构

每个验证层是一个独立的函数，可单独调用：

```
verify_l1()  → 返回 L1Report
verify_l2()  → 返回 L2Report  (可能需要 L1 先过)
verify_l3()  → 返回 L3Report  (可能需要 L2 先过)
verify_all() → 运行 L1→L2→L3 并汇总
```

### 3.2 L1 — 数据源验证（已有 + 补全）

已有函数 `verify_data_sources()` 在 `data_source.py`，已实现：
- push2test 可达性 ✅
- 行业/概念数量 ✅
- f3 自洽性 ✅
- 文件 JSON 有效性 ✅
- 数据日期（`_last_trading_day`）✅

需补全：
- K线日期有序性
- 关键行业存在性
- 非交易日跳过

### 3.3 L2 — 数据服务验证（新建）

新建函数 `verify_data_service()` 在 `tests/test_data_service.py`：

```python
def verify_data_service():
    checks = []
    # get_sector_rankings
    r = get_sector_rankings('industry')
    checks.append(('industry count', len(r) > 400, len(r)))
    
    # get_sector_klines for a known sector
    k = get_sector_klines('银行', 'industry')
    checks.append(('银行 klines', len(k) >= 2, len(k)))
    
    # get_merged_sector_data
    m = get_merged_sector_data()
    checks.append(('merged industries', len(m.get('industries',{})) > 400, ...))
    
    # 故障切换（模拟EM源失败）
    # cache一致性
    return checks
```

### 3.4 L3 — 业务逻辑验证（新建）

新建函数 `verify_business_logic()` 在 `tests/test_business_logic.py`：

```python
def verify_business_logic(date_str=None):
    if date_str is None:
        date_str = _last_trading_day()
    checks = []
    
    # get_mainline_data 结构
    ml = get_mainline_data(date_str)
    checks.append(('has lines', len(ml.get('lines',[])) > 0, ...))
    checks.append(('has secondary', len(ml.get('secondary',[])) > 0, ...))
    
    # chg_1d 合理性（交易日不应当全为0）
    non_zero = sum(1 for l in ml.get('all_ranked',[]) if abs(l.get('chg_1d',0)) > 0.01)
    checks.append(('chg_1d non-zero', non_zero > 0, non_zero))
    
    return checks
```

### 3.5 验证报告格式

```python
{
    "date": "20260605",
    "last_trade_day": "20260605",
    "layers": {
        "l1_source": {"status": "pass", "checks": [...]},
        "l2_service": {"status": "pass", "checks": [...]},
        "l3_business": {"status": "pass", "checks": [...]},
    },
    "summary": {
        "total": 25,
        "pass": 23,
        "fail": 1,
        "warn": 1
    },
    "status": "degraded"  # pass / degraded / fail
}
```

### 3.6 状态映射

| 状态 | 条件 |
|:----|:-----|
| pass | 所有层全部通过 |
| degraded | L1 通过，L2/L3 有失败 |
| fail | L1 有失败（原始数据不可用） |

## 4. 执行计划

详见：[数据源验证 — 执行计划](plan.md)

### 简要任务分解

| # | 任务 | 文件 | 状态 |
|:-:|:----|:----|:----:|
| 1 | L1 完善（K线日期序、关键行业存在性） | `data_source.py` | ⏳ |
| 2 | L2 新建（服务层验证） | `tests/test_data_service.py` | ⏳ |
| 3 | L3 新建（业务逻辑验证） | `tests/test_business_logic.py` | ⏳ |
| 4 | 集成到 cron + 报警 | cron job | ⏳ |
| 5 | 一次性回测验证（跑过去30天数据确认管线正常） | 脚本 | ⏳ |

## 5. 开放问题

1. **L4/L5 是否需要独立验证函数？** L4 可以并入 L3（调用 API 实质是验证业务逻辑），L5 需要浏览器自动化测试，成本较高。建议 L4 作为 L3 的延伸。
2. **一次性回测：** 需要跑过去30天每天的数据，确认管线在每段时期都正常工作。这可以作为一个独立的数据完整性检查脚本，但实施前需要确认数据保留策略。

# 数据层三层架构设计文档

> 版本：v1 — 2026-06-07
> 解决的核心问题：数据源切换无验证、业务代码绕过抽象层直接读文件、数据格式无合约

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    业务层（services/）                    │
│  review_compute_service / review_service / stock_card   │
│  market_service / strong_trend / concept_wave / ...     │
│  ── 只调 data_layer，不知道文件/API/数据源的存在         │
└──────────────────────┬──────────────────────────────────┘
                       │ 只读
┌──────────────────────▼──────────────────────────────────┐
│              data_layer.py（屏蔽层/合约层）               │
│                                                         │
│  对外接口：                                              │
│  get_sector_daily()        → {last_updated, industries} │
│  get_sector_push2test()    → SectorPush2Test（类型化）   │
│  get_sector_klines(name)   → [Kline]                    │
│  save_sector_daily(data)   → 原子写入 + 缓存失效         │
│  verify_data_sources()     → 数据源验证报告               │
│                                                         │
│  ── 内部可调 data_source，对外屏蔽所有实现细节            │
└──────────────────────┬──────────────────────────────────┘
                       │ 内部调用
┌──────────────────────▼──────────────────────────────────┐
│             data_source.py（数据获取层）                  │
│                                                         │
│  职责：多数据源获取、故障切换、缓存、文件IO              │
│  源链：THS live → EM仓 → legacy文件 → THS K-line       │
│  行业数据：stock_board_industry_summary_ths()           │
│  概念数据：push2test.eastmoney.com（同花顺无批量接口）  │
│                                                         │
│  ── 如果数据源变化，只改这一层                            │
└─────────────────────────────────────────────────────────┘
```

## 2. 设计原则

### 原则1：业务层只认 data_layer

**错误做法（之前）：**
```python
# services/review_compute_service.py
from backend.core.data_layer import load_sector_daily_uncached  # ❌ 绕过了合约
_sd = load_sector_daily_uncached()
push2test_data = _sd.get('_push2test', {})
```

**正确做法（现在）：**
```python
# services/review_compute_service.py
from backend.core.data_layer import get_sector_push2test  # ✅ 通过合约
push2test_data = get_sector_push2test()
# 返回 SectorPush2Test 类型化对象，字段有保证
```

### 原则2：data_layer 是唯一的屏蔽层

只有 `data_layer.py` 可以导入 `data_source`。其他任何文件（包括 `update_stock_data.py`）都不应该直接调 `data_source`。

```
✅ data_layer.py → data_source（内部调用，合理）
❌ update_stock_data.py → data_source（应走 data_layer.verify_data_sources）
❌ services/* → data_source（应走 data_layer）
```

### 原则3：数据模型由业务需求驱动

先定义业务需要什么字段（`data_models.py`），再实现获取逻辑（`data_source.py`）。

```python
# data_models.py — 定义合约
@dataclass
class ThsIndustrySnapshot:
    change_pct: float         # 涨跌幅%（必填）
    up_count: Optional[int]   # 上涨家数（THS特有）
    down_count: Optional[int] # 下跌家数（THS特有）
    leader: Optional[str]     # 领涨股（THS特有）
    leader_chg: Optional[float] # 领涨股涨跌幅（THS特有）
    net_flow: Optional[float] # 净流入（THS特有）
    ...
```

### 原则4：数据源切换要有验证

不能因为"更快"就换数据源。每次切换必须：
1. 确认旧数据源是否真的不可用
2. 交叉验证新旧数据源的同一字段值
3. 走 L1~L4 分层验证
4. 更新测试

### 原则5：临时验证脚本 → 永久测试

任何手动跑的 `python3 -c` 验证脚本，完成后必须转为 pytest 测试。
```
手动验证 → tests/test_data_source_integration.py（L1~L3 全链路）
手动验证 → tests/test_data_verify_l4_api.py（L4 API 验证）
```

## 3. 模型合约定义

### 3.1 行业涨跌幅快照（来自同花顺THS）

```python
@dataclass
class ThsIndustrySnapshot:
    date: str              # YYYYMMDD
    change_pct: float      # 涨跌幅%
    up_count: Optional[int]     # 上涨家数
    down_count: Optional[int]   # 下跌家数
    leader: Optional[str]       # 领涨股名称
    leader_chg: Optional[float] # 领涨股涨跌幅%
    net_flow: Optional[float]   # 净流入（亿元）
    volume: Optional[float]     # 总成交量（万手）
    amount: Optional[float]     # 总成交额（亿元）
```

### 3.2 概念涨跌幅快照（来自 push2test）

```python
@dataclass
class Push2TestConceptSnapshot:
    date: str              # YYYYMMDD
    change_pct: float      # 涨跌幅%
    # 不含上涨家数/领涨股/净流入（push2test没有这些字段）
```

### 3.3 K线数据

```python
@dataclass
class Kline:
    date: str              # YYYYMMDD
    open: float            # 开盘价
    close: float           # 收盘价
    high: float            # 最高价
    low: float             # 最低价
    volume: int            # 成交量（股）
```

## 4. 文件结构

```
server/backend/
├── core/
│   ├── data_layer.py      ← 屏蔽层（业务代码只调这里）
│   ├── data_models.py     ← 合约定义（dataclass）
│   └── update_stock_data.py ← 数据更新脚本（调 data_layer）
├── services/
│   ├── data_source.py     ← 数据获取层（data_layer 内部调用）
│   ├── review_compute_service.py  ← 调 data_layer ✅
│   ├── review_service.py          ← 调 data_layer ✅
│   └── ...（其他 service）         ← 全部调 data_layer ✅
└── api/
    └── data_source_health.py  ← 诊断端点（允许直接调 data_source）

docs/
└── data-layer-architecture.md  ← 本文档

tests/
├── test_data_source_integration.py  ← L1~L3 验证（可调 data_source）
├── test_data_verify_l4_api.py       ← L4 API 验证（调 data_layer）
└── test_sector_update.py            ← 板块更新测试（调 update_stock_data）
```

## 5. 数据源验证方案

### L1 — 数据源层验证

检查原始数据是否正确。在 `test_data_source_integration.py` 中。

| 检查项 | 方法 |
|:-------|:-----|
| THS行业数≥80 | `_fetch_today_industries_from_ths()` |
| 电子化学品chg合理 | `get('电子化学品', {}).get('change_pct')` |
| 上涨/下跌家数存在 | `up_count` / `down_count` |
| 领涨股非空 | `leader` |
| 半导体/电机等核心行业存在 | `'半导体' in data` |
| push2test概念命中 | `_fetch_today_sectors_from_push2test()` |

### L2 — 数据服务层验证

检查文件写入和数据层函数正确性。在 `test_data_source_integration.py` 中。

| 检查项 | 方法 |
|:-------|:-----|
| _push2test字段存在 | `load_sector_daily_uncached()['_push2test']` |
| 行业数≥80 | `p2['industries']` 长度 |
| 电子化学品chg=-0.7% | `p2['industries']['电子化学品']['change_pct']` |
| THS历史K线保留 | `industries` 有K线数据 |

### L3 — 业务逻辑层验证

检查主线计算正确性。在 `test_data_source_integration.py` 中。

| 检查项 | 方法 |
|:-------|:-----|
| lines非空 | `get_mainline_data('20260605')['lines']` |
| 电子化学品在lines中 | `'电子化学品' in names` |
| chg_1d=-0.7% | `line['chg_1d']` |
| chg_20d>0 | `line['chg_20d']` |
| 有stage | `line['stage']` |
| lines按chg_20d降序 | 遍历检查 |
| L1→L2→L3数据一致 | `source_chg ≈ sd_chg ≈ ml_chg` |

### L4 — API层验证

检查 `/api/review/today` 端点。在 `test_data_verify_l4_api.py` 中。

**陷阱：** `lines` 不在顶层，在 `mainline.lines` 下。
```python
# ❌ 错误
count = len(data.get('lines', []))

# ✅ 正确
lines = data['mainline']['lines']
count = len(lines)
```

## 6. 关键决策记录

| 日期 | 决策 | 原因 |
|:----|:-----|:-----|
| 2026-06-07 | 行业数据源切回同花顺THS | 同花顺行业数据一直稳定，之前因概念问题连行业也换了 |
| 2026-06-07 | 概念保留push2test | 同花顺无批量概念板块涨跌幅接口 |
| 2026-06-07 | data_layer加get_sector_push2test() | 业务代码不直接读sector_daily.json的_push2test字段 |
| 2026-06-07 | data_layer加get_sector_klines() | 屏蔽data_source的多源故障切换细节 |
| 2026-06-07 | data_layer加verify_data_sources() | update_stock_data.py不直接调data_source |
| 2026-06-07 | data_models改用ThsIndustrySnapshot | THS数据比push2test字段更丰富（上涨家数/领涨股等） |
| 2026-06-07 | 分层验证L1~L4 | 每层独立验证，不越级，发现数据层问题时快速定位 |
| 2026-06-07 | 临时验证→永久测试 | 所有手动验证转为pytest测试，可重复执行 |

## 7. 常见陷阱（避免重走弯路）

### 陷阱1：业务代码绕过 data_layer

```python
# ❌ 错误 — 2026-06-07 确实存在
from backend.core.data_layer import load_sector_daily_uncached
sd = load_sector_daily_uncached()
push2test = sd.get('_push2test', {})

# ✅ 正确
from backend.core.data_layer import get_sector_push2test
data = get_sector_push2test()
```

**后果：** 如果 sector_daily.json 的格式或路径变化，读 `_push2test` 会炸。而 `data_layer` 可以统一处理。

### 陷阱2：数据源切换不做验证

```python
# ❌ 错误 — 2026-06-06 发生
# push2test 更快（1.9s）→ 直接替换 THS → 没验证就上线

# ✅ 正确流程
# 1. 确认旧源（THS）是否真的不可用（验证后发现THS一直稳定）
# 2. 交叉验证两个源的同一板块涨跌幅偏差
# 3. 如果替换，走L1~L4分层验证
# 4. 更新测试
```

**后果：** 行业数据不准，复盘页显示错误。

### 陷阱3：L4验证读错字段路径

```python
# ❌ 错误 — 2026-06-07 发生
data = requests.get('/api/review/today').json()
lines = data.get('lines', [])  # ← 顶层没有lines！
# 返回0行 → 错误结论"API返回0"

# ✅ 正确
lines = data['mainline']['lines']
```

**后果：** 误判API有问题，浪费时间排查。

### 陷阱4：dataclass定义未与业务字段对齐

```python
# ❌ 错误 — 第一版data_models.py
class ChangePctSnapshot:
    change_pct: float
    close: float       # ← 没用过
    prev_close: float  # ← 没用过
    # 缺 up_count / down_count / leader（业务层真实在用）

# ✅ 正确 — 按业务需求定义
class ThsIndustrySnapshot:
    change_pct: float
    up_count: Optional[int]   # 业务层在用
    leader: Optional[str]     # 业务层在用
```

**后果：** 模型定义与业务脱节，无法做格式校验。

## 8. 全量测试覆盖

```bash
# 运行全部数据层测试
python3 -m pytest \
  tests/test_data_source_integration.py \
  tests/test_data_verify_l4_api.py \
  tests/test_sector_update.py \
  tests/test_data_layer.py \
  -v
```

| 测试文件 | 层 | 测试数 |
|:---------|:---|:------:|
| `test_data_source_integration.py` | L1~L3 | 36 |
| `test_data_verify_l4_api.py` | L4 | 17 |
| `test_sector_update.py` | 更新逻辑 | 10 |
| `test_data_layer.py` | 通用 | 已有 |
| **合计** | **L1~L4全链路** | **63+** |

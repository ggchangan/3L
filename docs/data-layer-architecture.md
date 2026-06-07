# 数据层三层架构设计文档

> 版本：v2 — 2026-06-07（新增L0数据覆盖度验证）
> 解决的核心问题：数据源切换无验证、业务代码绕过抽象层直接读文件、数据格式无合约、验证覆盖度不足（概念侧0覆盖）

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

### L0 — 数据覆盖度验证（2026-06-07 新增）

> **为什么要有L0：** L1~L4都假设数据已正确写入后再验证API/业务逻辑。但如果数据写入端就是错的（如概念K线停更、快照只有5条），L1~L4全都不会报错——因为它们不扫数据体内的日期。
>
> L0 不验证任何业务逻辑，只验证一件事：**data_layer 能返回的数据是否完整、新鲜、自洽。**

#### 设计思想

按 **四种数据类型**（行业K线 / 概念K线 / 行业快照 / 概念快照）分别检查三个维度：

| 维度 | 做什么 | 为什么 |
|:----|:-------|:-------|
| **结构完整性** | 全量扫描K线日期分布，禁止周末/未来日期；计数检查 | 最轻量，一次I/O，O(N)扫描，秒级完成 |
| **时效脉冲** | 按比例采样（行业10%，概念10%），关键概念必检 | 不扫全量，但足够发现"大部分数据停了"的问题 |
| **交叉验算** | K线计算chg vs 快照change_pct；多数据源比对 | 不同口径互相印证 |

**覆盖度标准：**

| 数据类型 | 数量 | 结构 | 脉冲 | 验算 | 关键必检 |
|:--------|:---:|:----|:----|:----|:---------|
| 行业K线 | 530 | ❌ 周末日期 / ❌ 多日期 ≠ last_updated | 采样53个，最新日期∈[T-1, T] | 和THS实时、push2test比对 | 电子化学品、半导体 |
| 概念K线 | 421 | ❌ 周末日期 / ❌ 多日期 ≠ last_updated | 采样42个，最新日期∈[T-1, T] | K线chg vs 快照change_pct | 培育钻石、华为概念 |
| 行业快照 | 90 | 计数≥80 | 90个全量检查chg非零率 | 和THS实时逐条比对 | 全部(90) |
| 概念快照 | 数百 | 计数≥200 | 采样5%，非零占比≥20% | K线chg vs 快照 | 培育钻石 |

**T = 最后一个交易日**（周末回退到周五，不计节假日）。

#### 验证逻辑

```python
def verify_data_coverage():
    """data_layer 数据覆盖度验证"""

    # ── 1. 结构完整性 ──
    # 对所有K线数据（行业530个+概念421个），扫描最后一条K线的日期：
    #   1a. 所有日期必须为交易日（周一到周五）
    #   1b. 所有日期必须 ∈ [last_trading_day-1, last_trading_day]
    #       （允许跨度1是由于不同板块更新先后差一天）
    #   1c. 超出此范围的板块数 > 50%（如288个停在6月1号）→ FAIL
    #
    # 对 _push2test 快照：
    #   1d. 行业快照数 ≥ 80
    #   1e. 概念快照数 ≥ 200
    #   1f. 概念快照 change_pct 非零占比 ≥ 20%

    # ── 2. 时效脉冲（采样验证）──
    # 行业K线：采样10%（~53个），按板块列表均匀挑选
    #        + 关键行业必检（电子化学品、半导体、银行、证券）
    # 概念K线：采样10%（~42个），按板块列表均匀挑选
    #        + 关键概念必检（培育钻石、华为概念）
    # 每一条：最新K线日期 ∈ [T-1, T]
    # 关键概念不存在于K线中 → WARN（数据还没拉，不是过期）

    # ── 3. 交叉验算 ──
    # 取采样中概念/行业的最后两条K线（prev_close, latest_close）
    # chg = (latest_close - prev_close) / prev_close * 100
    # 与 _push2test 快照的 change_pct 比对
    # 差异 < 0.5% → 一致（通过）
    # 差异 ≥ 0.5% → WARN（可能存在数据源不一致）
    # 无法比对（快照中没有此概念）→ WARN（快照覆盖率不足，不报FAIL）
    #
    # 多数据源比对（能做就做，不做不强求）：
    # 行业K线 chg vs THS实时 chg vs _push2test chg
    # 概念K线 chg vs 概念成分股加权 chg（选key概念，如缺失则跳过）
```

#### 与传统 L1~L4 的关系

```
L0（覆盖度） → 数据体扫描：所有K线日期、快照计数、chg非零率
                   ↓
L1（数据源层） → 原始API正确性（THS可调用、push2test可调）
                   ↓
L2（服务层） → 文件写入、data_layer函数
                   ↓
L3（业务层） → 主线计算逻辑
                   ↓
L4（API层） → 对外API端点
```

L0 如果FAIL，说明**数据写入就有问题**，L1~L4都基于这个数据的计算必然也不对。应该先修L0，再查上层。

#### 2026-06-07 实际验证结果

实时运行 `verify_data_coverage()` 对当前数据的诊断：

**1. 结构完整性：**
```python
# K线日期扫描 — 概念（421个）
20260601: 288个概念  ← 过期（上周一数据，含培育钻石）
20260602:   6个概念
20260603:  14个概念
20260604:   3个概念
20260606: 110个概念  ← 非交易日（周六），日期非法！

# K线日期扫描 — 行业（530个）
20260604:  31个行业
20260605:   3个行业
20260606: 496个行业  ← 非交易日（周六），日期非法！

# _push2test 快照
概念数: 5  ← 不达标（需≥200）
非零占比: 0/5=0%  ← 不达标（需≥20%）
关键概念「培育钻石」存在? 否 ← 不达标
```

**2. 时效脉冲：** 培育钻石K线最新日期=20260601，距T(20260605)差4天 → FAIL

**3. 交叉验算：**
- 培育钻石K线chg=-1.41%，_push2test中无此概念 → WARN（覆盖率不足）
- 电子化学品K线最后日期=20260606？或=20260605？需检查实际分布

**结论：** 当前数据有4个问题：
1. 行业/概念K线存在日期=20260606（周六）的非法数据
2. 概念K线288个过期到6月1号
3. _push2test概念快照只有5个，覆盖率为0
4. 培育钻石查不到

#### 检查流程优先级

```
verify_data_coverage() 的检查顺序：
  1. 先读 sector_daily.json 做结构扫描（成本最低，发现问题后直接WARN/FAIL）
  2. 如果结构扫描通过，做时效脉冲（有网络开销，采样）
  3. 如果时效脉冲通过，做交叉验算（有计算开销，选关键项）
```

这样避免：数据体已经碎了，还去查上层的一致性和交叉验算——浪费时间。

#### 特殊处理

- **非交易日**：如果今天是非交易日，T=上一个交易日，K线日期检查按T算
- **数据量不足**：概念K线数<50 → 跳过时效脉冲（数据还没拉够），但结构检查仍做（计数、日期）
- **周末日期**：日期 > T 且为周末 → 非交易日污染，直接FAIL（不应该在非交易日打标的）
- **关键概念不存在于K线**：不影响数据完整性，WARN即可（新概念还没拉）

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
| 2026-06-07 | **新增L0覆盖度验证** | 旧验证按数据源组织，概念侧0覆盖。新增按数据类型组织，行业K线/概念K线/行业快照/概念快照各3维检查（结构/脉冲/验算） |

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

### 陷阱5：验证覆盖度按数据源组织，不按数据类型组织

**2026-06-07 踩坑记录：** `verify_data_sources()` 的29项检查中，概念侧的覆盖度为0。

```
✅ THS live行业 → 检查了
✅ push2test行业实时API → 检查了
✅ push2test概念实时API → 只检查了API可调通（486个），没检查写入后的数据
✅ data_layer行业合约 → 检查了
❌ data_layer概念合约 → 完全没检查
❌ 概念K线最新日期 → 完全没检查
❌ _push2test概念快照计数/非零率 → 完全没检查
```

**根因：** 验证是按"数据源"（THS/push2test/文件）来设计的，不是按"数据类型"（行业/概念）。概念被当作"依附在push2test上的次要数据"处理了。

**正确的组织方式：** 每种数据类型（行业K线、概念K线、行业快照、概念快照）都要有 presence + freshness + format + value 四个维度的覆盖。

**验证手段：**
```python
def verify_coverage():
    for data_type in ['industry_kline', 'concept_kline', 'industry_snapshot', 'concept_snapshot']:
        presence(data_type)   # 存在、数量达标
        freshness(data_type)  # 最新日期合理
        format(data_type)     # 字段完整、类型正确
        value(data_type)      # 非零占比合理
```

**后果：** 概念数据损坏（K线停在6月1号、快照只有5个全0%）但验证29/29全通过。用户从同花顺看到的-3.3% 和系统返回的查不到/查到的数据对不上，浪费排查时间。

## 8. 全量测试覆盖

```bash
# 运行全部数据层测试
python3 -m pytest \
  tests/test_data_coverage_l0.py \
  tests/test_data_source_integration.py \
  tests/test_data_verify_l4_api.py \
  tests/test_sector_update.py \
  tests/test_data_layer.py \
  -v
```

| 测试文件 | 层 | 说明 |
|:---------|:---|:-----|
| `test_data_coverage_l0.py` | L0 | 数据覆盖度验证（结构完整性+时效脉冲+交叉验算） |
| `test_data_source_integration.py` | L1~L3 | 数据源+服务层+业务逻辑层 |
| `test_data_verify_l4_api.py` | L4 | API层 |
| `test_sector_update.py` | 更新逻辑 | 板块更新脚本 |
| `test_data_layer.py` | 通用 | data_layer通用函数 |
| **合计** | **L0~L4全链路** | **新增L0覆盖度验证** |

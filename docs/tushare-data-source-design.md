# Tushare 数据源迁移设计方案

**版本:** v0.1 (草案)
**日期:** 2026-06-14
**状态:** 📝 方案讨论中

## 1. 背景与目标

当前 3L 系统使用 **4 个数据源** 分散获取数据：
| 数据源 | 用途 | 协议 | 问题 |
|--------|------|------|------|
| mootdx (通达信TCP) | 个股K线、指数K线、财务快照、F10 | TCP 7709 | 海外不稳定，精度差 |
| 腾讯财经API | 实时行情(PE/PB/市值/换手率/涨跌停) | HTTP | 不封IP但字段有限 |
| 东财 push2test | 板块涨跌幅、概念列表、概念成分股 | HTTP | 有封IP风险，需限流 |
| 同花顺THS (akshare) | 行业/概念板块K线、概念快照、名称映射 | HTTP | akshare有版本兼容问题 |

**目标：** 引入 Tushare Pro 作为统一数据源，替换上述分散数据源，降低维护成本，提高数据一致性。

> Tushare Pro 是收费数据源（500元/年起），需注册获取 token。
> 社区版 Tushare (tushare) 接口有限，Pro 版 (tusharepro) 才有完整数据。

---

## 2. 3L系统所需数据类型全量清单

按业务用途分组，列出当前使用的数据源和Tushare对应接口：

### 2.1 个股数据

| 数据类型 | 当前数据源 | 当前存储 | Tushare接口 | 是否可替换 |
|---------|-----------|---------|-------------|-----------|
| 个股日K线(60天) | mootdx tcp | `all_stocks_60d.json` | `daily` + `adj_factor` | ✅ |
| 个股实时行情(价格) | 腾讯财经API | 实时获取 | `daily`最新日线 | ✅ |
| PE / PB / 总市值 | 腾讯财经API | 实时获取 | `daily_basic` | ✅ |
| 换手率 / 量比 | 腾讯财经API | 实时获取 | `daily_basic` | ✅ |
| 涨跌停价 | 腾讯财经API | 实时获取 | ❌ Tushare无此字段 | ❌ 需保留腾讯 |
| 涨停原因/题材归因 | 同花顺热点 | 实时获取 | ❌ Tushare无此数据 | ❌ 保留同花顺 |
| 个股涨跌幅 | mootdx | 计算 | `daily` pct_chg | ✅ |
| 个股概念归属 | 东财 push2test | `stock_concept.json` | `ths_member` (同花顺概念) | ✅ |
| 行业归属 | mootdx/东财 | `stock_industry_map.json` | `stock_basic` + `ths_member` | ✅ |
| 财务快照(季报) | mootdx | 不持久化 | `fina_indicator` / `income` | ✅ |
| 除权除息事件 | mootdx xdxr() | 前复权矫正用 | `adj_factor` 直接返回 | ✅ |

### 2.2 指数数据

| 数据类型 | 当前数据源 | 当前存储 | Tushare接口 | 是否可替换 |
|---------|-----------|---------|-------------|-----------|
| 中证全指(000985)日K线 | mootdx | `index_sh_data.json` | `index_daily` | ✅ |
| 上证指数(000001)日K线 | mootdx | `index_sh_data.json` | `index_daily` | ✅ |
| 科创50(000688)日K线 | mootdx | `index_sh_data.json` | `index_daily` | ✅ |
| 创业板指(399006)日K线 | mootdx | `index_sh_data.json` | `index_daily` | ✅ |

### 2.3 行业/概念板块数据

| 数据类型 | 当前数据源 | 当前存储 | Tushare接口 | 是否可替换 |
|---------|-----------|---------|-------------|-----------|
| 行业板块日K线 | 同花顺THS (akshare) | `sector_daily.json` | `ths_daily` (同花顺行业) | ✅ |
| 概念板块日K线 | 同花顺THS (akshare) | `sector_daily.json` | `ths_daily` (同花顺概念) | ✅ |
| 行业板块今日涨跌幅快照 | 同花顺THS (akshare) | `_push2test`字段 | `ths_daily` 最新 + `ths_index` | ✅ |
| 概念板块今日涨跌幅快照 | 同花顺THS (akshare) | `_push2test`字段 | `ths_daily` 最新 + `ths_index` | ✅ |
| 行业列表 | 东财 push2test | 运行时获取 | `ths_index` (同花顺行业) | ✅ |
| 概念列表 | 东财 push2test | `concept_list.json` | `ths_index` (同花顺概念) | ✅ |
| 概念→系统名称映射 | 同花顺THS | `concept_name_mapping.json` | `ths_index` 直接同名 | ✅ |
| 行业板块成分股 | 东财 push2test | 运行时获取 | `ths_member` | ✅ |
| 概念板块成分股 | 东财 push2test | 运行时获取 | `ths_member` | ✅ |
| 行业上涨/下跌家数 | 同花顺THS | `push2test` | ❌ 需从成分股涨跌计算 | ⚠️ 需计算 |
| 板块领涨股 | 同花顺THS | `_push2test` | ❌ 需从成分股涨跌排序 | ⚠️ 需计算 |

### 2.4 辅助数据

| 数据类型 | 当前数据源 | 当前存储 | Tushare接口 | 是否可替换 |
|---------|-----------|---------|-------------|-----------|
| 交易日历 | akshare `tool_trade_date_hist_sina` | 内存缓存 | `trade_cal` | ✅ |
| 全量A股代码列表 | mootdx/akshare | `all_stock_codes.json` | `stock_basic` | ✅ |

### 2.5 无法被Tushare替代的数据（保留现有数据源）

| 数据类型 | 原因 | 保留方案 |
|---------|------|---------|
| 个股涨跌停价(limit_up/down) | Tushare无此字段 | 保留腾讯财经API |
| 同花顺热点(强势股+题材归因) | 独家数据,Tushare无替代 | 保留同花顺热点接口 |
| 实时五档盘口/逐笔成交 | Tushare无实时盘口 | 保留mootdx(仅实时场景) |
| 东财研报/PDF | Tushare无研报 | 保留东财reportapi |

---

## 3. Tushare 数据替换映射表

### 3.1 关键 Tushare API 接口

| Tushare接口 | 说明 | 频率限制(Pro) | 费用点 |
|------------|------|--------------|--------|
| `daily` | 个股日线行情(含涨跌幅) | 200次/分钟 | 200积分/次(基础） |
| `daily_basic` | 每日指标(PE/PB/市值/换手率) | 200次/分钟 | 200积分/次 |
| `adj_factor` | 复权因子 | 200次/分钟 | 免费 |
| `index_daily` | 指数日线行情 | 200次/分钟 | 免费 |
| `ths_daily` | 同花顺板块日线行情 | 200次/分钟 | 免费 |
| `ths_index` | 同花顺板块列表 | 200次/分钟 | 免费 |
| `ths_member` | 同花顺板块成分股 | 200次/分钟 | 免费 |
| `stock_basic` | 股票基本信息（含行业） | 200次/分钟 | 免费 |
| `trade_cal` | 交易日历 | 不限 | 免费 |

### 3.2 替换策略

#### A. 个股K线（当前 mootdx → Tushare daily + adj_factor）

```
当前:
  mootdx.bars(code, count=800) → [{date, open, close, high, low, volume}]
  + mootdx.xdxr(code) → 前复权矫正

替换为:
  pro.daily(ts_code, start_date, end_date) → [{trade_date, open, close, high, low, vol, pct_chg}]
  + pro.adj_factor(ts_code, trade_date) → 复权因子
  OR pro.daily(ts_code, adj='qfq') → 直接返回前复权数据
  
  ts_code 格式: '000001.SZ' / '600519.SH'
```

**注意点:**
- Tushare 的 ts_code 是 `股票代码.市场` 格式（如 `688017.SH`）
- `adj='qfq'` 参数可以直接返回前复权数据，无需手动矫正
- `daily` 接口每次最多返回 5000 条，足够60天及历史K线

#### B. 实时行情（当前腾讯财经 → Tushare daily_basic）

```
当前:
  tencent_quote([code]) → {code: {price, pe_ttm, pb, mcap, turnover, limit_up, ...}}

替换为:
  pro.daily_basic(ts_code, trade_date=trade_cal) → {pe_ttm, pb, total_mv, circ_mv, turnover_rate, ...}
  + pro.daily(ts_code, trade_date) → {close, pct_chg} 获取最新收盘价
  
  注: daily_basic 只能获取历史交易日数据，盘中实时价无法获取
  → 盘中使用场景还需腾讯财经或mootdx
```

#### C. 指数K线（当前 mootdx → Tushare index_daily）

```
当前:
  mootdx.bars('000001', category=4, count=500) → [{date, open, close, high, low, volume}]

替换为:
  pro.index_daily(ts_code='000001.SH', start_date, end_date) → [{trade_date, open, close, high, low, vol}]
  
  指数 ts_code: '000001.SH'(上证), '000688.SH'(科创50), '000985.SH'(中证全指), '399006.SZ'(创业板指)
```

#### D. 行业/概念板块K线（当前 akshare THS → Tushare ths_daily）

```
当前:
  ak.stock_board_industry_index_ths(symbol='电子') → K线
  ak.stock_board_concept_index_ths(symbol='人工智能') → K线

替换为:
  先查ths_index获取板块代码:
  pro.ths_index(name='电子', ts_code='881111.TI') → 返回ts_code
  
  再查K线:
  pro.ths_daily(ts_code='881111.TI', start_date, end_date) → [{trade_date, open, close, high, low, vol, pct_chg}]
  
  同花顺行业板块 ts_code 前缀: '881' (行业) / '897' (概念)
  Tushare 板块代码格式: '881111.TI' (Tushare Industry)
```

**⚠️ 需要确认的问题:**
- Tushare `ths_daily` 的板块代码与系统中使用的名称如何映射
- 当前系统用中文板块名作为key，Tushare用 `ts_code`（如 `881121.TI`）

#### E. 板块快照（当前 THS_concept_info + push2test → Tushare ths_daily 最新日线）

```
当前:
  ak.stock_board_concept_info_ths(symbol='人工智能') → {板块涨幅, 涨跌家数, 资金净流入}
  或 push2test → {f3涨跌幅, f104上涨家数, ...}

替换为:
  pro.ths_daily(ts_code='881111.TI') 取最新记录 → {pct_chg}
  + ths_member + daily_basic 计算上涨家数
  或 用 ths_daily 的 pct_chg 替代（但缺少上涨家数等字段）
```

#### F. 概念列表（当前 东财 push2test → Tushare ths_index）

```
当前:
  push2test fs='m:90+t:3' → 东财概念板块列表

替换为:
  pro.ths_index() → 同花顺概念板块列表（含名称、代码）
  
  同花顺概念板块有专门的分类体系，与东财概念不完全一致
  需评估名称映射的影响
```

#### G. 成分股查询（当前 东财 push2test → Tushare ths_member）

```
当前:
  push2test fs='b:BK1039' → 东财板块成分股

替换为:
  pro.ths_member(ts_code='881111.TI') → [{ts_code, name, weight}]
```

#### H. 交易日历（当前 akshare → Tushare trade_cal）

```
当前:
  ak.tool_trade_date_hist_sina() → set of trade dates

替换为:
  pro.trade_cal(exchange='SSE', start_date, end_date) → [{cal_date, is_open}]
```

---

## 4. 架构变化

### 4.1 当前架构

```
┌─────────────┐  ┌──────────────┐  ┌───────────┐
│  business    │  │  data_layer   │  │ data_     │
│  code        │→ │  (统一入口)   │→ │ source.py │→→ mootdx / 腾讯 / 东财 / THS
│  (services)  │  │  +缓存        │  │ (抽象层+  │
└─────────────┘  └──────────────┘  │ 故障切换) │
                                    └───────────┘
```

### 4.2 迁移后架构

```
┌─────────────┐  ┌──────────────┐  ┌───────────────┐
│  business    │  │  data_layer   │  │  data_source   │
│  code        │→ │  (统一入口)   │→ │  .py           │→→ Tushare Pro (主)
│  (services)  │  │  +缓存        │  │  (抽象层+      │→→ 腾讯 (涨跌停价,备源)
└─────────────┘  └──────────────┘  │  故障切换)      │→→ 同花顺热点 (保留)
                                    └───────────────┘
```

**核心原则：** 不改动 data_layer 和 data_models 对外合约，只改 data_source.py 内部实现。
现有业务代码完全不受影响。

### 4.3 故障切换链（需新增 Tushare 数据源）

```python
# 现有: [('mootdx', fetch_mootdx), ('tencent', fetch_tencent), ...]
# 改为: [('tushare', fetch_tushare), ('tencent', fetch_tencent_fallback), ...]

DATA_SOURCE_CHAINS = {
    'stock_klines': [
        ('tushare_daily', fetch_tushare_stock_klines),     # 主源
        ('mootdx_fallback', fetch_mootdx_stock_klines),    # 备源
    ],
    'sector_ranking': [
        ('tushare_sector', fetch_tushare_sector_ranking),  # 主源
        ('push2test_fallback', fetch_push2test_ranking),   # 备源
    ],
    'sector_klines': [
        ('tushare_ths', fetch_tushare_sector_klines),      # 主源
        ('legacy_file', fetch_legacy_sector_klines),       # 备源
    ],
    'concept_map': [
        ('tushare_ths_index', fetch_tushare_concept_map),  # 主源
        ('em_fallback', fetch_em_concept_map),             # 备源
    ],
}
```

---

## 5. 逐个数据迁移清单

### § 必须改的（数据源切换）

| # | 功能 | 当前数据源 | Tushare替换 | 修改文件 | 影响范围 |
|---|------|-----------|-------------|---------|---------|
| 1 | 个股日K线 | mootdx | `daily` + `adj_factor` | `update_stock_data.py` | 全部个股分析 |
| 2 | 指数日K线 | mootdx | `index_daily` | `update_stock_data.py` + `data_source.py` | 大盘走势图 |
| 3 | 行业/概念板块K线 | akshare THS | `ths_daily` | `data_source.py` | 板块走势图, 波谷判定 |
| 4 | 概念列表 | 东财 push2test | `ths_index` | `refresh_sectors.py` | 概念板块 |
| 5 | 概念成分股 | 东财 push2test | `ths_member` | `refresh_sectors.py` | 个股概念归属 |
| 6 | 交易日历 | akshare | `trade_cal` | `data_source.py` | 交易时段判断 |
| 7 | 股票列表 | akshare/mootdx | `stock_basic` | `update_stock_data.py` | 全量A股 |
| 8 | 板块涨跌幅快照 | THS + push2test | `ths_daily` pct_chg | `data_source.py` | 主线判定 |
| 9 | PE/PB/市值/换手率 | 腾讯财经 | `daily_basic` | `data_source.py` | 个股卡片 |
| 10 | 行业归属 | mootdx | `stock_basic` industry | `update_stock_data.py` | 行业分类 |

### § 不动或保留的

| # | 功能 | 当前数据源 | 处理方式 |
|---|------|-----------|---------|
| 1 | 涨跌停价 | 腾讯财经 | 保留腾讯（Tushare无此字段） |
| 2 | 同花顺热点(题材归因) | 同花顺热点 | 保留（Tushare无替代） |
| 3 | 实时五档盘口/逐笔成交 | mootdx | 保留mootdx（仅盘中实时场景） |
| 4 | 东财研报PDF | 东财reportapi | 保留（Tushare无研报） |
| 5 | 资金流向(分钟/日级) | 东财push2 | 保留（Tushare无此数据） |
| 6 | 龙虎榜/解禁/融资融券 | 东财datacenter | 保留（Tushare可能有但需评估） |

---

## 6. 需要确认的问题

### 6.1 Tushare 板块代码 vs 系统板块名称

当前系统用 **中文板块名称** 作为key（如 `'电子化学品'`, `'人工智能'`）：
- `sector_daily.json`中 industries/concepts 的key是中文名
- `concept_list.json` 中概念名称是中文
- `stock_concept.json` 中`concepts`字段是中文名列表

Tushare `ths_daily` 需要的参数是 **`ts_code`**（如 `'881121.TI'`, `'884112.TI'`）。

**问题：** 系统中尚无 `板块中文名 ↔ Tushare ts_code` 的映射表。

**方案A：** 通过 `ths_index(type='I'/'N')` 获取全量列表，生成映射表 `ths_name_mapping.json`
- 优点：一次获取，持久化使用
- 缺点：需要额外维护一张映射表

**方案B：** 用中文名直接查 Tushare（Tushare不支持中文名查ths_daily）
- 不可行，Tushare ts_code 是数字编码

### 6.2 Tushare 日K线 vs mootdx 精度差异

当前 mootdx 返回的K线：
```python
{'date': '20260613', 'open': 224.10, 'close': 229.62, 'high': 229.62, 'low': 214.10, 'volume': 800000000}
```

Tushare daily 返回的K线（前复权）：
```python
{'trade_date': '20260613', 'open': 22.41, 'close': 22.96, 'high': 22.96, 'low': 21.41, 'vol': 8000000}
```

**注意：** Tushare 的 vol 单位是 **股**（手×100），mootdx 也是股。但 Tushare 前复权会缩放价格（送转股后价格除以送转比例）。

**可能的影响：**
- 价格数值差异：Tushare前复权价格可能比mootdx小（如果送转较多）
- 现有代码中基于价格计算的指标（突破位、关键点、买点信号）可能受到影响
- 建议先A/B对比测试验证

### 6.3 上涨家数/下跌家数/领涨股字段

当前同花顺THS提供 `上涨家数` / `下跌家数` / `领涨股` 等字段。
Tushare `ths_daily` 只提供板块指数K线，不提供这些衍生统计字段。

**方案：** 通过 `ths_member` 获取成分股 → 用 `daily_basic` 查各股涨跌 → 统计上涨/下跌家数 → 排序得领涨股。

### 6.4 费用估算

| 接口 | 每次调用 | 日调用量估算 | 日积分消耗 |
|------|---------|------------|-----------|
| `daily` (个股) | 200积分 | ~50只×2次 | 20,000 |
| `daily_basic` | 200积分 | ~50只 | 10,000 |
| `ths_daily` (板块) | 200积分 | ~500个 | 100,000 |
| `ths_member` | 免费 | ~50个 | 0 |
| `ths_index` | 免费 | 1次/天 | 0 |
| `stock_basic` | 免费 | 1次/周 | 0 |
| `index_daily` | 免费 | 4只 | 0 |
| `adj_factor` | 免费 | ~50只 | 0 |
| `trade_cal` | 免费 | 1次/天 | 0 |
| **合计** | | | **~130,000/天** |

Tushare Pro 基础套餐通常包含 **200万积分/月**（约 ¥500/年）。
日消耗13万 → 月约400万积分 → 可能需升级套餐。

**优化方案：**
- 板块K线(ths_daily)改为增量拉取：只拉最新1天，减少调用
- 使用股票列表缓存（低频更新）
- 批量查询代替逐只查询

---

## 7. 实施步骤（讨论阶段）

### Phase 1: 基础设施（1-2天）
1. 安装 tusharepro: `pip install tushare`
2. 配置 Tushare token
3. 实现 `TushareDataSource` 类，封装所有Tushare接口调用
4. 实现 `tushare_get()` 统一限流+重试（参考现有 `em_get()` 模式）

### Phase 2: 核心数据迁移（2-3天）
1. 个股K线: `daily` + `adj_factor` → 替换 mootdx
2. 指数K线: `index_daily` → 替换 mootdx
3. 板块K线: `ths_daily` → 替换 akshare THS
4. 概念列表+成分股: `ths_index` + `ths_member` → 替换东财

### Phase 3: 衍生字段迁移（1-2天）
1. PE/PB/市值: `daily_basic` → 替换腾讯财经
2. 上涨家数计算: 成分股+stats → 替换同花顺快照
3. 交易日历: `trade_cal` → 替换 akshare

### Phase 4: 验证与切换（2天）
1. A/B对比测试：新旧数据源同口径对比
2. 全量数据校验（同花顺 vs Tushare）
3. 灰度切换：配置 `TUSHARE_ENABLED=True/False`

---

## 8. 风险和注意事项

1. **Tushare 依赖网络** — 需确保海外服务器可访问 Tushare API（当前mootdx海外不稳定 — 但Tushare是HTTP，走国内代理更稳定）
2. **前复权价格差异** — 需与现有mootdx前复权结果交叉验证
3. **概念分类体系差异** — 同花顺概念 vs 东财概念不完全一致，切换Tushare后概念名称体系变化需要处理
4. **板块代码映射** — 需建立 `系统板块名 ↔ Tushare ts_code` 的双向映射
5. **限流控制** — Tushare Pro 200次/分钟，批量拉取需限流
6. **费用** — 月均400万积分可能超基础套餐，需评估升级成本

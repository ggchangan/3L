# 原始数据层 — 数据模型 v1

> 定义每个数据源拉什么数据、存成什么格式、怎么更新。
> 这是所有上层逻辑的基础，必须先打扎实。

## 数据源总览

| 编号 | 源 | 用途 | 实时/历史 | 更新频率 | 状态 |
|:---:|:---|:----|:---------|:--------|:----:|
| S1 | push2test.eastmoney.com | 板块排行 f3 | 实时 | 交易日17:00/21:00 | ✅ 主源 |
| S2 | push2test.eastmoney.com | 个股概念映射 f103 | 实时 | 交易日17:00 | ✅ |
| S3 | push2test.eastmoney.com | 行业映射 f100 | 实时 | 交易日17:00 | ✅ |
| S4 | mootdx TCP | 个股K线 | 历史(日线) | 交易日17:00 | ✅ |
| S5 | push2test.eastmoney.com | 指数行情 | 实时 | 交易日17:00 | ✅ |
| S6 | 腾讯 qt.gtimg.cn | 指数实时行情 | 实时 | 盘中 | ✅ 辅助 |
| S7 | THS 历史快照 | 板块历史K线 | 历史(静态) | 一次迁移 | 📦 归档 |
| S8 | Tencent/sina | (备选) | — | — | 🔒 被墙 |

## 文件存储结构

```
data/
├── sector_daily.json          ← 主力板块文件（THS K线 + _push2test）
├── stock_industry_map.json     ← 个股→行业映射
├── stock_concept_map.json      ← 个股→概念映射
├── concept_list.json           ← 概念板块列表
├── all_stock_codes.json        ← 全量A股代码
├── index_sh_data.json          ← 主要指数K线
└── sources/                    ← 数据源仓库（抽象层用）
    ├── em/
    │   ├── sector_daily.json   ← EM仓板指快照
    │   └── concept_map.json    ← EM仓概念映射
    └── ths/
        └── sector_daily.json   ← THS仓历史块照
```

---

## 模型1：板块日K线（核心）

```json
{
  "last_updated": "20260605",
  "industries": {
    "<行业名>": [
      {"date": "20260601", "open": 100.0, "close": 102.0, "high": 103.0, "low": 99.0, "volume": 1000000},
      ...
    ]
  },
  "concepts": {
    "<概念名>": [ ... ]
  },
  "_push2test": {
    "industries": {
      "<行业名>": {
        "date": "20260605",
        "change_pct": 2.34,
        "close": 100.0,
        "open": 99.0,
        "high": 101.0,
        "low": 98.0,
        "volume": 1000000,
        "prev_close": 97.71
      }
    },
    "concepts": { ... }
  },
  "_push2test_updated": "20260605"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| `last_updated` | string YYYYMMDD | 最后更新日期（=最近一次cron成功的交易日） |
| `industries` | dict of arrays | 行业板块K线数组，key=行业名（无后缀） |
| `concepts` | dict of arrays | 概念板块K线数组 |
| `_push2test` | dict | push2test最新快照（当日涨跌幅用change_pct，不从K线算） |
| `_push2test_updated` | string | push2test数据日期 |

### K线数组元素

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| `date` | string YYYYMMDD | 交易日 |
| `open` | float | 开盘价 |
| `close` | float | 收盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `volume` | int | 成交量 |

### `_push2test` 字段

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| `date` | string YYYYMMDD | 数据日期（=最后一个交易日） |
| `change_pct` | float | 当日涨跌幅%（直接取自 push2test f3，不从K线算） |
| `close` | float | 收盘价 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `volume` | int | 成交量 |
| `prev_close` | float | 前收盘价 |

### 更新逻辑（update_sectors）

```
1. 交易日(Mon-Fri)才执行，非交易日跳过
2. 调 push2test 拉全量行业/概念
   → 行业: fs='m:90+t:2', fields=f2, f3, f12, f14, f15, f16, f17, f18, f5
   → 概念: fs='m:90+t:3', fields同上
3. 名称归一化：去掉 Ⅱ/Ⅲ/D 后缀
4. 写入 _push2test 字段
5. 同步写入 EM仓 sources/em/sector_daily.json（供抽象层使用）
6. 不修改 THS K线数组（历史K线不变，只更新 _push2test 快照）
```

---

## 模型2：EM仓板指快照

```json
{
  "last_updated": "20260605",
  "industries": {
    "<行业名>": {
      "date": "20260605",
      "change_pct": 2.34,
      "close": 100.0,
      "open": 99.0,
      "high": 101.0,
      "low": 98.0,
      "volume": 1000000,
      "prev_close": 97.71
    }
  },
  "concepts": { ... }
}
```

**说明：** EM仓是 **`update_sectors()` 的副产品**，在保存 `_push2test` 后同步写入。
用途：供 `get_sector_rankings()` 在 push2test live 不可用时做文件回退。

---

## 模型3：THS仓板指历史K线

```json
{
  "last_updated": "20260606",
  "industries": {
    "<行业名>": [
      {"date": "...", "open": ..., "close": ..., ...}
    ]
  },
  "concepts": { ... }
}
```

**说明：** THS仓是**一次迁移的历史快照**，不再增量更新。34个行业(申万一级)，311个概念。
用途：供 chg_20d 计算（需要20+根K线历史），以及 `get_sector_klines()` 回退。

---

## 模型4：个股→行业映射

```json
{
  "600001": {"code": "600001", "name": "XX股份", "ths_industry": "银行"},
  "600002": {"code": "600002", "name": "XX股份", "ths_industry": "半导体"},
  ...
}
```

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| key | string | 股票代码 |
| `code` | string | 股票代码 |
| `name` | string | 股票名称 |
| `ths_industry` | string | 申万二级行业名 |

**更新逻辑：** `update_industry_map()` 交易日17:00运行
```
push2test: fs='m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23', fields=f12,f14,f100
→ f100 = 申万二级行业名
→ 写入 stock_industry_map.json
```

---

## 模型5：个股→概念映射

```json
{
  "600001": {
    "code": "600001",
    "name": "XX股份",
    "concept_codes": ["BK001", "BK002"],
    "concept_names": ["人工智能", "芯片"]
  }
}
```

| 字段 | 类型 | 说明 |
|:----|:----|:-----|
| key | string | 股票代码 |
| `code` | string | 股票代码 |
| `name` | string | 股票名称 |
| `concept_codes` | array[string] | 概念板块代码列表 |
| `concept_names` | array[string] | 概念板块名称列表 |

**更新逻辑：** `update_concept_maps()` 交易日17:00运行
```
push2test: 逐股拉 f103 字段（概念板块代码）
→ 与 concept_list.json 对照匹配名称
→ 写入 concept_map 和 concept_list
```

---

## 模型6：指数K线

```json
{
  "last_updated": "20260605",
  "indices": {
    "000001": [
      {"date": "20260601", "open": 3200.0, "close": 3210.0, "high": 3220.0, "low": 3190.0, "volume": 100000000},
      ...
    ]
  }
}
```

**存储位置：** `index_sh_data.json`

**更新逻辑：** `update_index()` 交易日17:00/21:00运行
```
mootdx TCP → 上证指数/科创50/中证全指 日K线
→ 增量追加新交易日数据
→ 写入 index_sh_data.json
```

---

## 模型7：全量A股代码表

```json
{
  "600001": "XX股份",
  "600002": "YY股份",
  ...
}
```

**说明：** code→name 映射，磁盘搜索用。启动时自动生成（如不存在则从 akshare 拉取）。

---

## 数据流总图

```
                       ┌──────────────────┐
                       │  S6 腾讯实时指数   │
                       │  (盘中辅助)       │
                       └────────┬─────────┘
                                │
┌─────────────┐    ┌────────────▼─────────┐    ┌──────────────────────┐
│ S1 push2test│───▶│  update_sectors()    │───▶│  sector_daily.json   │
│ 板块排行f3   │    │  交易日17:00/21:00    │    │  └─ industries(K线)  │
└─────────────┘    │                      │    │  └─ concepts(K线)    │
                   │  1. 拉全量行业+概念    │    │  └─ _push2test(快照) │
┌─────────────┐    │  2. 名称归一化        │    └──────────┬───────────┘
│ S2 push2test│───▶│  3. 写入 _push2test   │               │
│ 概念映射f103 │    │  4. 同步EM仓          │               │
└─────────────┘    └──────────────────────┘               │
                                                          ▼
┌─────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ S3 push2test│───▶│ update_industry_map()│───▶│ stock_industry_map   │
│ 行业映射f100 │    │  交易日17:00          │    │  .json              │
└─────────────┘    └──────────────────────┘    └──────────────────────┘

┌─────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ S4 mootdx   │───▶│  update_stocks()     │───▶│  all_stocks.json     │
│ 个股日K线    │    │  交易日17:00          │    │                      │
└─────────────┘    └──────────────────────┘    └──────────────────────┘

┌─────────────┐    ┌──────────────────────┐
│ S5 push2test│───▶│  update_index()      │───▶ index_sh_data.json
│ 指数行情    │    │  交易日17:00          │
└─────────────┘    └──────────────────────┘
```

## 当前数据质量状态（截至2026-06-07）

| 模型 | 数据量 | 截止日期 | 状态 |
|:----|:------|:--------|:----:|
| 板块K线(industries) | 530个行业 | 20260604（最后K线） | ⚠️ 6月5日K线缺失 |
| 板块K线(concepts) | 421个概念 | 20260604 | ⚠️ 同上 |
| `_push2test` 行业 | 456条 | — | ❌ 已清空（周日手动run后清除，等周一重建） |
| EM仓行业 | 530条 | 20260607 | ❌ 日期错标（已同步清理） |
| THS仓行业 | 34条 | 20260604 | 📦 静态归档 |
| 个股→行业映射 | 5208只 | 20260605 | ✅ |
| 个股→概念映射 | 4594只 | 20260605 | ✅ 匹配率92% |
| 指数K线 | 上证+科创+中证 | 20260605 | ✅ |
| 全量代码表 | ~5200只 | — | ✅ 已有 |

## 已知问题

1. **`_push2test` 6月5日数据丢失** — 旧cron代码没写 `_push2test` 字段，无法恢复
2. **EM仓日期错标** — 迁移时 `last_updated` 设成了迁移日期而非数据实际日期
3. **行业名不统一** — 东财带 Ⅱ/Ⅲ 后缀，THS/legacy 无后缀（已在 `_fetch_today_sectors_from_push2test` 归一化）

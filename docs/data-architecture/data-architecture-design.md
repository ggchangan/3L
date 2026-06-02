# 3L 交易系统 — 数据架构设计文档

> 版本: 1.0 | 日期: 2026-06-02 | 状态: ✅ 定稿

---

## 核心原则

### 1. 两层架构

```
┌─────────────────────────────────────────────────────────────┐
│                   服务层 (Services)                          │
│  stock_card_service · review_compute · monitor_service       │
│  concept_wave_service · signal_detector                     │
│  只做数据加工/计算，不直接拉外部数据源                       │
│  输入: data_layer 读本地文件 → 输出: 加工后的结构化数据       │
├─────────────────────────────────────────────────────────────┤
│                   数据层 (Data Layer)                        │
│  data_layer.py (读接口) · update_stock_data.py (写入口)      │
│  只做: 从外部数据源拉原始数据 → 存本地 JSON 文件              │
│  不做: 任何业务逻辑/加工/计算                                │
├─────────────────────────────────────────────────────────────┤
│             外部数据源 (External Data Sources)               │
│  东方财富 push2test · 同花顺 sector_daily · mootdx(通达信)   │
│  腾讯财经 · 巨潮 cninfo · 新浪 finance                       │
└─────────────────────────────────────────────────────────────┘
```

### 2. 单一写入口

**所有数据写入必须经过 `update_stock_data.py` 的 main() 流程。**
其他模块（服务层、API 路由）只读不写，不得在业务逻辑中塞写入逻辑。

### 3. 数据源不混合

每类数据有且只有一个「主数据源」，同一个数据源内保持一致性。

---

## 数据源全景

### 已验证的 7 个数据源

| 数据源 | 协议 | 封 IP 风险 | 可用状态 | 用途 |
|:------|:------|:----------|:--------|:-----|
| **东方财富 push2test** | HTTP | 低 | ✅ 稳定 | 个股→概念归属 (f103)、个股基本面 |
| **东方财富 change_em** | HTTP | 低 | ✅ 稳定 | 概念板块实时排行 |
| **东方财富 datacenter** | HTTP | 中（已限流） | ✅ 稳定 | 龙虎榜、解禁、两融、大宗交易 |
| **同花顺 sector_index** | HTTP | 低 | ✅ 稳定 | 行业/概念板块 K 线 (sector_daily.json) |
| **mootdx (通达信 TCP)** | TCP 7709 | 不封 IP | ✅ 稳定 | 个股 K 线、五档盘口、财务快照、F10 |
| **腾讯财经** | HTTP GBK | 不封 IP | ✅ 稳定 | 实时价、PE/PB/市值、指数、ETF |
| **巨潮 cninfo** | HTTP | 低 | ✅ 稳定 | 公告全文 |
| **新浪财报** | HTTP | 低 | ✅ 稳定 | 三表(资产负债表/利润表/现金流量表) |

### 已失效/不使用

| 数据源 | 原因 | 替代 |
|:------|:-----|:----|
| 同花顺概念页面 scraping | Nginx 403 封 IP | 东方财富 f103 + 名称映射 |
| 东方财富 concept_name_em | 连接被断 | 同花顺缓存 (concept_list.json) |
| 东方财富 concept_cons_em | 连接被断 | 同上 |
| 东方财富 concept_hist_em | 连接被断 | 同花顺 sector_index |
| 百度概念板块归属 | 403 封 IP | 东方财富 f103 |
| 新浪概念分类 | JSON 解析失败 | 东方财富 f103 |
| 通达信 block.dat | 只有100个指数板块，无完整概念 | 东方财富 f103 |

---

## 数据层文件结构

```
server/backend/
├── config.py                  # 所有文件路径/常量
├── core/
│   ├── data_layer.py          # 读接口：统一的读入口，所有模块通过这里读数据
│   ├── update_stock_data.py   # 写入口：主数据更新管道
│   └── cache_layer.py         # 缓存层：TTL 缓存 + 失效策略
├── services/
│   ├── stock_card_service.py  # 个股卡片服务（加工）
│   ├── review_compute_service.py
│   ├── monitor_service.py     # 盯盘服务
│   ├── concept_wave_service.py
│   └── signal_detector_service.py
└── api/
    ├── concept_wave.py
    ├── monitor_api.py
    └── ...
```

### config.py — 路径注册中心

所有数据文件路径集中定义，模块间通过 `config.XXX` 引用，不硬编码。

```python
# config.py 关键路径
DATA_DIR      = '/home/ubuntu/data/3l'           # 数据根目录
ALL_STOCKS_PATH      = DATA_DIR + '/all_stocks_60d.json'
WATCHLIST_PATH       = DATA_DIR + '/watchlist.json'
INDUSTRY_MAP_PATH    = DATA_DIR + '/stock_industry_map.json'
SECTOR_DAILY_PATH    = DATA_DIR + '/sector_daily.json'
CONCEPT_LIST_PATH    = DATA_DIR + '/map/concept_list.json'
STOCK_CONCEPT_MAP_PATH = DATA_DIR + '/map/stock_concept.json'
CACHE_DIR            = DATA_DIR + '/cache/'
KEY_POINTS_DIR       = DATA_DIR + '/key_points/'
```

### data_layer.py — 统一读接口

提供 `get_xxx()` 函数，所有服务层模块通过这里读取数据。
内部走 TTL 缓存（`cache_layer.py`），避免重复读盘。

```python
# 核心读接口
get_all_stocks()         → {方向: {code: [klines]}}
get_watchlist()          → [{code, name, direction, industry}]
get_sector_daily()       → {industries: {...}, concepts: {...}}
get_concept_list()       → {code: {name, stock_count, stocks}}
get_stock_concept_map()  → {stock_code: {code, name, concept_codes, concept_names}}
get_index_klines()       → [{date, open, close, high, low}]
```

### update_stock_data.py — 单一写入口

主数据更新管道，按阶段依次执行：

```python
def main():
    # 阶段 0: 基建
    update_industry_map()       # 个股→行业映射 (东方财富 push2)
    update_concept_maps()       # 个股→概念映射 (东方财富 f103 + 名称映射)
    
    # 阶段 1: 个股 K 线
    update_stocks()             # 个股 60d K线 (mootdx TCP)
    
    # 阶段 2: 板块 K 线
    update_sectors()            # 行业/概念板块 K线 (同花顺 sector_index)
    
    # 阶段 3: 扫描/分析
    scan_stock_cards()          # 个股卡片计算 (基于本地数据)
    ...
```

---

## 各数据流详细设计

### 1. 行情数据 (个股 K 线)

| 项目 | 说明 |
|:----|:-----|
| **数据源** | mootdx (通达信 TCP 7709) |
| **文件名** | `all_stocks_60d.json` |
| **更新频率** | 每日盘后增量更新 |
| **写入函数** | `update_stock_data.update_stocks()` |
| **读接口** | `data_layer.get_all_stocks()` |
| **结构** | `{方向: {code: [{date, open, close, high, low, volume, ma5, ma10, ma20, ...}]}}` |

### 2. 行业映射

| 项目 | 说明 |
|:----|:-----|
| **数据源** | 东方财富 push2test (f100=申万二级行业名) |
| **文件名** | `stock_industry_map.json` |
| **更新频率** | 每日（行业归属很少变） |
| **写入函数** | `update_stock_data.update_industry_map()` |
| **读接口** | `data_layer.get_industry_map()` |
| **结构** | `{code: {code, name, industry, industry_code}}` |

### 3. 概念板块 — 成分股映射 ⭐ (本次修复核心)

| 项目 | 说明 |
|:----|:-----|
| **概念名** | 同花顺 akshare (缓存至 `map/concept_list.json`，362个) |
| **成分股归属** | 东方财富 push2test f103 |
| **名称匹配** | 映射表 (EM 名 → THS 名)，见 §名称映射规则 |
| **文件名** | `map/concept_list.json` + `map/stock_concept.json` |
| **更新频率** | 概念成分股变化慢，每周/按需 |
| **写入函数** | `update_stock_data.update_concept_maps()` |
| **读接口** | `data_layer.get_concept_list()` + `data_layer.get_stock_concept_map()` |

#### 名称映射规则

```python
def match_em_to_ths(em_name, ths_pool):
    """东方财富 f103 概念名 → 同花顺概念名"""
    # 1. 手动映射表（处理无法自动匹配的）
    if em_name in MANUAL:
        return MANUAL[em_name]
    
    # 2. 精确匹配
    if em_name in ths_pool: return em_name
    
    # 3. "概念"后缀差异
    if em_name.endswith('概念'): ...
    else: check em_name + '概念'
    
    # 4. 括号内容清理后匹配
    # 5. 子串包含匹配
    # 6. 核心词匹配（去掉括号和"概念"后缀）
```

#### 手动映射表

| 东方财富名 | 同花顺名 |
|:----------|:---------|
| CPO概念 | 共封装光学(CPO) |
| 东数西算 | 东数西算(算力) |
| 算力概念 | 东数西算(算力) |
| 国产芯片 | 芯片概念 |
| 光通信模块 | 光纤概念 |
| 车联网(路云) | 车联网(车路协同) |
| 数据中心 | 数据中心(AIDC) |
| 新能源汽车 | 新能源车 |
| 国企改革 | 央国企改革 |

### 4. 概念板块 K 线

| 项目 | 说明 |
|:----|:-----|
| **数据源** | 同花顺 `stock_board_concept_index_ths()` |
| **文件名** | `sector_daily.json` → `concepts` 字段 |
| **更新频率** | 每日增量 |
| **写入函数** | `update_stock_data.update_sectors()` |
| **读接口** | `data_layer.get_sector_daily()` |
| **结构** | `{concepts: {概念名: [{date, open, close, high, low, volume, amount}]}}` |

### 5. 概念板块实时排行

| 项目 | 说明 |
|:----|:-----|
| **数据源** | 东方财富 `stock_board_change_em()` / `change_em()` |
| **文件名** | 无（实时数据，不进磁盘） |
| **调用方** | `monitor_data.py` → 盯盘页面 |
| **特点** | 实时 HTTP 请求，0.28s 返回 999 个板块涨跌幅 |
| **去重** | 服务端用 dict 去重（"被动元件"等重复名） |

### 6. 自选股/持仓

| 项目 | 说明 |
|:----|:-----|
| **文件名** | `watchlist.json` + `holdings.json` |
| **更新方式** | 页面操作写入 |
| **读接口** | `data_layer.get_watchlist()` + `data_layer.get_holdings()` |

---

## 数据层不可违反的铁律

### 1. 单一写入口

```python
# ✅ 正确：通过 update_stock_data 写入
from backend.core import update_stock_data
update_stock_data.main()

# ❌ 错误：在服务层/API 路由中写数据文件
open('data/xxx.json', 'w').write(...)
```

### 2. 服务层不直接拉数据源

```python
# ✅ 正确：通过 data_layer 读本地数据
from backend.core.data_layer import get_stock_concept_map
concept_map = get_stock_concept_map()

# ❌ 错误：在服务层直接请求外部 API
import requests
r = requests.get('https://push2test.eastmoney.com/...')
```

### 3. 数据加工在服务层

```python
# data_layer.py 只做 → 读取原始数据
def get_stock_concept_map():
    return cache.get('stock_concept_map', 
                     lambda: _load_json(STOCK_CONCEPT_MAP_PATH, {}))

# monitor_service.py 做 → 加工/过滤
def get_tracked_concepts():
    concept_map = get_stock_concept_map()
    watchlist = get_watchlist()
    # 过滤出关联≥6只自选股的概念
    ...
```

### 4. NaN 序列化禁止

```python
# Python json.dumps 默认 allow_nan=True，会把 float('nan') 序列化为非法 JSON
# 全局修复在 server.py 的 send_json() 中递归 _clean() 替换 NaN→null
# 所有服务层输出必须经过 send_json()
```

---

## 数据更新流程

```
每日/按需执行: python3 -m backend.core.update_stock_data
  │
  ├── update_industry_map()      # 东方财富 push2 → stock_industry_map.json
  ├── update_concept_maps()      # 东方财富 f103 → map/concept_list.json + stock_concept.json
  ├── update_stocks()            # mootdx TCP → all_stocks_60d.json  
  ├── update_sectors()           # 同花顺 → sector_daily.json
  ├── scan_stock_cards()         # 基于本地数据 → latest_scan_result.json
  └── 其他...
```

---

## 未解决/待做

| 问题 | 状态 | 计划 |
|:----|:-----|:----|
| 同花顺概念名列表更新 | ⚠️ 当前用缓存 | 同花顺解封后恢复 akshare 调用 |
| 手工创建自定义概念 | 📋 待实现 | 添加 `watched_concepts.json`，用户自定义 |
| 通达信 block.dat 解码 | 📋 低优 | 可作为 mootdx 概念成分股的补充 |

# 3L 核心逻辑共享包 — 架构设计方案

> 版本: v1.0 | 最后更新: 2026-05-28
> 分支: feature/extract-core
> 状态: 进行中（ema_utils.py 已迁移）

---

## 1. 背景与动机

### 问题

个股买卖点检测页面（StockAnalysis.tsx）的后端逻辑与 3l-server 主项目深度耦合：

```
3l-server/
  backend/
    core/
      ema_utils.py              ← 纯逻辑
      trend_trading.py           ← 纯逻辑
      buy_point_detection.py     ← 纯逻辑
      data_layer.py              ← 数据访问
      cache_layer.py             ← 缓存
    services/
      analysis_service.py         ← API处理器（含HTTP代码）
      stock_chart_service.py      ← SVG图表生成
      stock_card_service.py       ← 卡片组装
    config.py                     ← 路径常量
```

如果想要把个股买点检测独立成一个新项目（3l-analysis），要么：

1. **拷贝代码** — 两份逻辑不同步，改一个忘了另一个
2. **共享源码** — 软链或路径依赖，部署麻烦
3. **抽共享包** — pip install 标准做法

### 目标

- 核心计算逻辑（EMA、趋势判定、买点判定、数据层）**单源维护**
- 3l-server 和 3l-analysis **各自独立部署**
- 迁移过程中 **不影响线上功能**
- 逐步迁移，**移一个测一个**

---

## 2. 备选方案比较

### 方案A: 抽共享 pip 包（推荐 ✅）

```
/home/ubuntu/
  3l-core/                        # 新仓库
    pyproject.toml
    threel_core/
      __init__.py
      ema_utils.py                # EMA/结构/阶段
      trend_trading.py            # 趋势判定
      buy_point_detection.py      # 买点判定
      data_layer.py               # 数据访问
      cache_layer.py              # 缓存
      config.py                   # 路径常量

  3l-server/                      # 现有项目（pip install -e 3l-core）
    backend/core/ema_utils.py     # 转发层（7行）
    backend/core/trend_trading.py  # 转发层（待迁移）
    backend/core/buy_point_detection.py  # 转发层（待迁移）
    ...其他文件不变

  3l-analysis/                    # 新项目（pip install 3l-core）
    server.py
    frontend/
```

**原理**：

```
threel_core  ←── pip install -e ──→  3l-server (转发层)
    ↑                                    ↑
    └── pip install ──→  3l-analysis     用户无感知
```

- 3l-server 通过**转发层**（`from threel_core.xxx import *`）保持旧 import 路径可用
- 所有旧代码一行不改，测试照跑
- 新项目直接 `from threel_core.xxx import yyy`

| 维度 | 评价 |
|:-----|:------|
| 单源维护 | ✅ 核心逻辑只在 3l-core，两边共享 |
| 独立部署 | ✅ 3l-server 和 3l-analysis 各自独立 |
| 迁移风险 | ✅ 转发层模式，逐步迁移，每一步全回归验证 |
| 学习成本 | ⚠️ 需要理解 pip install -e 和转发层模式 |
| 维护成本 | ✅ 低 — 改核心逻辑两边自动生效 |

### 方案B: 微服务拆分

```
3l-analysis 作为独立的 HTTP 微服务
  只暴露 3 个接口:
    GET /api/stock-analysis?q=300750
    GET /api/stock-chart?code=300750
    GET /api/buy-signals?codes=...

3l-server 通过 HTTP 调用 3l-analysis
```

| 维度 | 评价 |
|:-----|:------|
| 独立部署 | ✅ 完全隔离 |
| 代码共享 | ❌ 核心逻辑还是要在两边各有一份（或另抽包）|
| 延迟 | ❌ 多一层 HTTP 调用，个股分析变慢 |
| 运维 | ❌ 多一个服务要监控、配负载均衡 |
| 迁移复杂度 | ❌ 接口版本管理、超时、熔断都要处理 |

### 方案C: 纯部署拆分（代码不动）

```
3l-analysis = 3l-server 的精简版
  删掉不需要的页面和路由
  核心代码在原路径，用软链指向 3l-server/backend/
```

| 维度 | 评价 |
|:-----|:------|
| 实现速度 | ✅ 最快，复制删改就行 |
| 代码共享 | ❌ 两份副本，改核心逻辑要两边改 |
| 部署 | ⚠️ 依赖 3l-server 的路径结构 |
| 长期维护 | ❌ 容易打架 — 改了 3l-server 忘了同步 3l-analysis |

---

## 3. 方案选型

### 选择方案A（抽共享 pip 包）

**理由**：

1. **真正的单源维护** — 核心逻辑只在一个地方，两边 `pip install` 即可
2. **标准做法** — Python 生态的标准包管理模式，不是 hack
3. **可逐步迁移** — 转发层模式让每一步都可独立验证
4. **零风险** — 旧 import 路径不变，全回归兜底
5. **新项目直接受益** — `3l-analysis` 建起来就是干净的 `from threel_core import`

### 不选方案B的理由

个股分析是计算密集型，多一层 HTTP 延迟（每次分析多 50-200ms）体验差。且最终还是需要一个共享包来避免代码重复——方案B实际上是"方案A + 额外 HTTP 层"。

### 不选方案C的理由

两份代码不是长期方案。用户明确要求"整个改动能让那个页面受益"，方案C做不到——改了 3l-core 的逻辑，另一个项目还得手动同步。

---

## 4. 实现方案

### 4.1 架构

```
┌─────────────────────────────┐
│        threel_core          │  ← pip 包
│                             │
│  ema_utils.py               │  →  EMA计算、结构、阶段
│  trend_trading.py           │  →  平滑趋势、交易系统判定
│  buy_point_detection.py     │  →  买点检测核心
│  data_layer.py              │  →  数据访问（读JSON）
│  cache_layer.py             │  →  内存缓存TTL
│  config.py                  │  →  路径配置
└──────────┬──────────────────┘
           │
    pip install -e
           │
    ┌──────┴──────────────┬──────────────┐
    ▼                     ▼              ▼
┌──────────────┐   ┌──────────────┐  ┌──────────────┐
│  3l-server   │   │ 3l-analysis  │  │  (未来项目)  │
│              │   │              │  │              │
│ 转发层(7行)  │   │ 直接import   │  │ 直接import   │
│ from threel  │   │ from threel  │  │ from threel  │
└──────────────┘   └──────────────┘  └──────────────┘
```

### 4.2 迁移模式：转发层

每个从 `backend/core/` 迁移到 `threel_core/` 的文件，在**原地保留一个转发层**：

```python
# 原始文件: backend/core/ema_utils.py  (196行)
# 迁移后:   threel_core/ema_utils.py  (196行)
#            backend/core/ema_utils.py  (7行 转发层)

from threel_core.ema_utils import (
    ema_list,
    get_ema_arrangement,
    get_structure,
    get_stage,
    _reg_slope,
    get_mainline_level,
)
```

**转发层的作用**：
- 所有旧代码的 `from backend.core.ema_utils import get_structure` **继续可用**
- 不修改任何调用方代码
- 新项目可以直接 `from threel_core.ema_utils import get_structure`

### 4.3 安装方式

```bash
# 3l-server 的 venv 里安装（已执行）
cd /home/ubuntu/3l-server
.venv/bin/pip install -e /home/ubuntu/3l-core/

# 未来 3l-analysis 的 venv 里安装
cd /home/ubuntu/3l-analysis
python3 -m venv .venv
.venv/bin/pip install -e /home/ubuntu/3l-core/
```

`-e`（editable）模式意味着 3l-core 的代码修改立即生效，无需重新安装。

### 4.4 迁移顺序

| 步骤 | 文件 | 状态 | 依赖 | 说明 |
|:----:|:-----|:----:|:----|:-----|
| 1 | `ema_utils.py` | ✅ 已完成 | 无 | 纯计算，零依赖，最适合第一个 |
| 2 | `trend_trading.py` | ⏳ 待做 | ema_utils | 趋势判定逻辑 |
| 3 | `buy_point_detection.py` | ⏳ 待做 | trend_trading, ema_utils | 买点核心 |
| 4 | `cache_layer.py` | ⏳ 待做 | 无 | 内存缓存 |
| 5 | `data_layer.py` | ⏳ 待做 | cache_layer, config | 数据访问（去除更新脚本代码）|
| 6 | `config.py` | ⏳ 待做 | 无 | 精简版路径常量 |

每步完成后运行 `make regression` 全回归验证。

### 4.5 关键决策记录

| 决策 | 选择 | 原因 |
|:-----|:------|:------|
| 包名 | `threel-core` / `threel_core` | Python 包名规范（下划线），PyPI 名（横线）|
| 安装模式 | `pip install -e` | 开发期即时生效，部署时改为 `pip install` |
| 转发层 vs 改 import | 转发层 | 零改动旧代码，可逐步迁移 |
| 包位置 | `/home/ubuntu/3l-core/` | 和 3l-server 同级，独立仓库 |
| 测试策略 | 全回归 + 每个迁移步骤单独验证 | 确保每一步都不破坏现有功能 |

---

## 5. 当前状态 (2026-05-28)

### 已完成

- [x] 创建 `/home/ubuntu/3l-core/` 目录结构
- [x] 创建 `pyproject.toml` 构建配置
- [x] 创建 `threel_core/__init__.py` 包入口
- [x] 迁移 `ema_utils.py` → `threel_core/ema_utils.py`
- [x] `backend/core/ema_utils.py` 改为转发层（7行）
- [x] 迁移 `trend_trading.py` → `threel_core/trend_trading.py`
- [x] `backend/core/trend_trading.py` 改为转发层（15个函数）
- [x] 迁移 `cache_layer.py` → `threel_core/cache_layer.py`
- [x] 迁移 `buy_point_detection.py` → `threel_core/buy_point_detection.py`
- [x] 创建 `threel_core/data_layer.py` 精简版（共享子集）
- [x] `pip install -e` 安装到 3l-server 的 venv
- [x] 全回归 6/6 通过（89前端 + 649后端 + 4项检查）
- [x] 创建 `3l-analysis` 项目脚手架，验证独立可运行

### 待完成

- [ ] 迁移 `config.py`（精简版路径常量）
- [ ] `3l-analysis` 添加 server.py + 前端页面

### 验证方式

每次迁移完一个文件：

```bash
# 1. 验证新路径
.venv/bin/python -c "from threel_core.xxx import yyy; ..."

# 2. 验证旧路径（转发层）
.venv/bin/python -c "from backend.core.xxx import yyy; ..."

# 3. 全回归
make regression
```

---

## 6. 目录结构（最终目标）

```
/home/ubuntu/
  3l-core/                          # 共享逻辑包
    pyproject.toml
    threel_core/
      __init__.py
      ema_utils.py                  # EMA计算、结构、阶段
      trend_trading.py              # 平滑趋势、交易系统判定
      buy_point_detection.py        # 买点核心判定
      data_layer.py                 # 统一数据入口
      cache_layer.py                # 内存缓存
      config.py                     # 路径配置

  3l-server/                        # 主项目（现有）
    backend/
      core/
        ema_utils.py                # 转发层（7行）
        trend_trading.py            # 转发层（待迁移）
        buy_point_detection.py      # 转发层（待迁移）
        data_layer.py               # 转发层（待迁移）
        cache_layer.py              # 转发层（待迁移）
        ...                         # 其他文件（无变化）
      services/
        analysis_service.py         # 个股分析API
        stock_chart_service.py      # SVG图表
        stock_card_service.py       # 卡片组装
        ...
    frontend/
      src/pages/StockAnalysis.tsx   # 个股分析页面（不动）
      ...

  3l-analysis/                      # 新项目（待创建）
    pyproject.toml
    server.py                       # 轻量服务器（只挂个股分析相关路由）
    frontend/
      index.html
      ...
```

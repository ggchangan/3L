# 3L 交易系统 — 架构设计

> 最后更新: 2026-05-24
> 本文件记录系统核心架构决策，供后续讨论和演进参考。

## 一、系统架构总览

```
用户浏览器
    ↓ HTTPS (443)
nginx (SSL 终结 + /private/ 拦截)
    ↓ HTTP (127.0.0.1:8080)
server.py (薄路由层, ~500行)
    ├─ services/        ← 业务逻辑层
    ├─ scripts/         ← 核心算法 + 数据层
    └─ config.py        ← 集中配置
```

## 二、数据分层缓存设计

### 三层缓存策略

```
┌──────────────────────────────────────┐
│  Layer 1: 文件级持久缓存             │
│  (SVG/PDF/PNG)                       │
│  特征：内容哈希寻址，磁盘持久化       │
│  用途：K线SVG、回测图表、PDF报告      │
│  粒度：每只股票每张图独立             │
└────────────┬─────────────────────────┘
┌────────────▼─────────────────────────┐
│  Layer 2: 计算结果缓存 (Memory)      │
│  (function + input_hash → result)    │
│  特征：输入不变 → 输出不重算         │
│  用途：买点判定、结构分析、EMA计算    │
│  粒度：单只股票单次分析结果           │
└────────────┬─────────────────────────┘
┌────────────▼─────────────────────────┐
│  Layer 3: 数据缓存 (Memory)          │
│  (data_key → data)                   │
│  特征：TTL+主动失效，线程安全         │
│  用途：60天K线全量(2.5MB)、自选股、   │
│        行业映射                       │
│  粒度：全量数据整体缓存               │
└──────────────────────────────────────┘
```

### Layer 3 — 内存数据缓存（当前实现）

**解决的问题：** `all_stocks_60d.json`（2.5MB）被 15+ 个调用点各自独立读取，每次 HTTP 请求都读一次磁盘。

**方案：** `TTLCache` 类 + 单例

```python
class TTLCache:
    """线程安全、TTL 自动过期、支持主动失效和 Mock"""
    get(key, loader, ttl=30)     # 懒加载
    invalidate(key)              # 主动失效
    set_mock(key, data)          # 测试注入
```

| 数据 | TTL | 理由 |
|:----|:----|:------|
| all_stocks_60d | 30s | 突发请求命中缓存，手动刷新等30s或invalidate |
| watchlist | 10s | 边改边切页面，快速反映编辑 |
| industry_map | 60s | 几乎不变 |

**设计选择：**
- 不用 `@lru_cache` → 没有TTL、不能主动失效
- 单例（module-level）→ 天然单例，不需要容器
- `threading.Lock` → 不会递归，不需要 RLock
- loader 回调函数 → 灵活（可读JSON、调API）

### Layer 2 — 计算结果缓存（待实现）

**解决的问题：** 盯盘页面 30s 刷新一次，如果数据没变（非交易时段、或只有一根K线更新），买点判定、结构分析的计算结果是完全一样的。

**方案：** 内容寻址缓存

```python
def detect_buy_point_cached(code, klines):
    h = hash(tuple(k['close'] for k in klines[-10:]))
    key = f'buy_point_{code}_{h}'
    
    cached = computed_cache.get(key)
    if cached is not None:
        return cached
    
    result = detect_buy_point(code, klines)
    computed_cache.set(key, result)
    return result
```

**何时值得做：** 当一次 HTTP 请求中涉及 10+ 次买点/结构重复计算时（如趋势候选页面展开时加载多只股票）。

### Layer 1 — 文件级持久缓存（待实现）

**解决的问题：** 一张 SVG 图在数据没变时反复生成。

**方案：** 输入哈希 → 唯一文件名

```python
h = md5(f"{code}_{last_close}_{keypoint_hash}")
cache_path = f"/tmp/svg_cache/{h}.svg"
```

**注意：** SVG 图本身只有几 KB，不如全量方案简单。只有当图表生成成为性能瓶颈时才考虑。

## 三、数据流

### 核心数据

| 数据 | 大小 | 来源 | 更新频率 | 消费方 |
|:----|:----|:------|:---------|:-------|
| all_stocks_60d.json | 2.5MB | akshare 爬虫 | 每日1次（盘后） | 所有API端点 |
| watchlist.json | ~10KB | 用户编辑 | 手动 | 自选股/趋势/监控 |
| holdings.json | ~5KB | 用户编辑 | 手动 | 成果页/复盘 |
| trades.json | ~5KB | 用户编辑 | 手动 | 成果页/复盘 |
| industry_map.json | ~50KB | 固定数据 | 几乎不变 | 行业映射 |

### 60天数据的特殊性

**核心观察：** 过去60天的K线数据，相邻两天有 59/60（~98%）是重叠的。当前方案每次全量加载，实际只有最后1天的新数据有意义。（5/24数据 → 5/25数据：前59天完全相同，只新增第60天）

### 数据库问题（未采纳）

曾考虑引入 SQLite，理由：
- 增量更新（只插入新K线，不重写全量）
- SQL 查询单只股票60天，不需要加载全量
- ACID 写入保证

未采纳理由：
- K线是时序数据，关系模型表达不好
- 需要迁移所有现有关联代码
- 部署多一个数据迁移步骤
- 单用户场景 JSON 够用

**如果需要未来重新讨论：** 观察点 —— 当需要查询单只股票超过60天历史 或 做跨股票统计分析 时。

## 四、测试策略

### 分层测试

| 层 | 框架 | 依赖 | 重点 |
|:---|:-----|:-----|:-----|
| 核心算法 | pytest | 硬编码数据 | 买点/EMA/结构判定 |
| 数据层 | pytest | 真实JSON | 加载/搜索/缓存 |
| 服务层 | pytest | mock数据 | 业务逻辑（inject stocks参数） |
| 路由层 | pytest | mock服务 | server.py路由表 |
| 前端E2E | Playwright | 真实服务 | 页面加载/JS报错/关键元素 |

### service 层的可测试性模式

函数签名注入：

```python
# ✅ 生产：不传参数走缓存
result = get_stock_analysis('300750.SZ')

# ✅ 测试：传 mock 数据
result = get_stock_analysis('300750.SZ', stocks=mock_stocks)
```

## 五、部署架构

详见 `deploy/setup.sh` 和 `deploy/` 目录，此处简述：

```
用户浏览器 → [HTTPS:443] → nginx → [HTTP:127.0.0.1:8080] → server.py → .venv
                                                             ↓
                                                        systemd (自恢复)
```

- **系统依赖：** Python3, nginx, wkhtmltopdf, rsvg-convert
- **部署方式：** `bash deploy/setup.sh`（全自动）
- **服务管理：** `sudo systemctl <action> 3l-server`
- **备份：** 每日凌晨3点 `deploy/backup.sh`，保留14天
- **更新/回滚：** `deploy/deploy.sh` / `deploy/rollback.sh`

## 六、重要设计原则

1. **函数签名不破坏兼容性** — 加参数用 `stocks=None` 缺省值，已有调用处不修改
2. **每次请求不重复读 2.5MB** — 内存缓存层解决
3. **不为例数据做过度拟合** — 通用规则>单案例优化
4. **新提取函数必须加单元测试** — 不需提醒
5. **入口脚本不在 `services/` 下** — generate_review_data.py 等项目入口放项目根目录，不混入services

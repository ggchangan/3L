# ATR止损与买入日期 — 执行计划

## 总览

| 阶段 | 状态 | 预估 |
|:----|:----:|:----:|
| Phase 1: 数据层 — ATL计算 + buy_date | ⏳ | 1h |
| Phase 2: 服务层 — holdings_service + calc_stop_loss | ⏳ | 1h |
| Phase 3: API层 — holdings API + stock-chart API | ⏳ | 0.5h |
| Phase 4: 前端 — Holdings.tsx 买入日期 + 止损线 | ⏳ | 1.5h |
| Phase 5: 验证 + 清理 | ⏳ | 0.5h |

## Phase 1: 数据层

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | 新增 `core/threel_core/atr.py` — calc_atr() + 测试 | `core/threel_core/atr.py` | 15m | ⏳ |
| 2 | holdings_repo.py SELECT/INSERT 加 buy_date 列 | `holdings_repo.py` | 10m | ⏳ |
| 3 | MySQL ALTER TABLE 加 buy_date 字段 | 终端执行 | 5m | ⏳ |

## Phase 2: 服务层

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 4 | holdings_service.py get_holdings() 加 buy_date 映射 | `holdings_service.py` | 10m | ⏳ |
| 5 | holdings_service.py save_holdings() 加 buy_date | `holdings_service.py` | 10m | ⏳ |
| 6 | calc_stop_loss 加 ATR 模式 | `buy_point_detection.py` | 15m | ⏳ |

## Phase 3: API层

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 7 | holdings API 返回/接收 buy_date | `api/holdings.py` | 10m | ⏳ |
| 8 | stock-chart API 接受 ?stop_loss= 参数 | `api/stock.py` | 10m | ⏳ |
| 9 | stock_chart_service.py 画止损线 | `stock_chart_service.py` | 20m | ⏳ |

## Phase 4: 前端

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 10 | types.ts 加 buy_date 类型 | `types.ts` | 5m | ⏳ |
| 11 | Holdings.tsx 编辑弹窗加买入日期输入框 | `Holdings.tsx` | 30m | ⏳ |
| 12 | Holdings.tsx 修复仓位比例可编辑 | `Holdings.tsx` | 10m | ⏳ |
| 13 | StockCard.tsx 传 stop_loss 到图表URL | `StockCard.tsx` | 10m | ⏳ |

## Phase 5: 验证

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 14 | 运行全部测试 | — | 10m | ⏳ |
| 15 | 构建前端 + 重启服务验证 | — | 10m | ⏳ |

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-17 | 初稿 |

# 复盘页机会分类 — 执行计划

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----:|:----:|:----:|
| 一：后端数据改造 | ✅ | 1.5h | 20min |
| 二：前端组件重构 | ✅ | 2h | 30min |
| 三：PLAN接入 | ✅ | 0.5h | 10min |
| 四：测试+构建+部署 | ✅ | 0.5h | 10min |

---

## 阶段一：后端数据改造

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | `classify_opportunity()` 函数 + `get_mainline_data` 加 stage/opportunity | `review_compute_service.py` | 30min | 10min | ✅ |
| 2 | `get_concept_mainline_data()` 加 stage/opportunity | `review_compute_service.py` | 20min | 5min | ✅ |
| 3 | `review_service.py` 构建 opportunity_map + 传递 | `review_service.py` | 10min | 5min | ✅ |
| 4 | `generate_trading_plan()` 按机会类型排序 buy_priority | `review_compute_service.py` | 20min | 10min | ✅ |

## 阶段二：前端组件重构

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 5 | TS types 扩展（LineItem, opportunity_map, sector/opportunity 字段） | `types.ts` | 5min | 3min | ✅ |
| 6 | `MainlineSection.tsx` 按机会类型分组渲染 + 折叠 | `MainlineSection.tsx` | 1.5h | 20min | ✅ |
| 7 | `StockCard.tsx` 机会类型标注行 | `StockCard.tsx` | 10min | 5min | ✅ |
| 8 | `HoldingsReview` + `BuySignalsReview` 传递 opportunityMap | 2 files | 10min | 5min | ✅ |

## 阶段三：PLAN接入

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 9 | `TradingPlan.tsx` 机会类型分组展示 | `TradingPlan.tsx` | 30min | 10min | ✅ |

## 阶段四：测试+构建+部署

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 10 | 后端测试（classify_opportunity 单元测试 + API 验证） | — | 10min | 5min | ✅ |
| 11 | npm build + 重启 | — | 10min | 5min | ✅ |

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-01 | 初稿 |
| 2026-06-01 | 全部完成，已部署 |

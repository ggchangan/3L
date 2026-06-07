# 个股卡片数据合约 — 执行计划

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----|:----:|:----:|
| 阶段1：准备+测试 | ⏳ | 30min | — |
| 阶段2：后端实现 | ⏳ | 30min | — |
| 阶段3：前端实现 | ⏳ | 20min | — |
| 阶段4：验证+提交 | ⏳ | 20min | — |

## 阶段1：准备+测试

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1.1 | 新增 StockCardData dataclass | `data_models.py` | 10min | — | ⏳ |
| 1.2 | 写合约测试：验证 StockCardData 字段完整性 | `tests/test_stock_card_contract.py` | 15min | — | ⏳ |
| 1.3 | 回退 review_compute_service 的未提交改动 | — | 5min | — | ⏳ |

## 阶段2：后端实现

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 2.1 | get_stock_card() 新增 action_type 计算函数 | `stock_card_service.py` | 15min | — | ⏳ |
| 2.2 | get_stock_card() 新增 action_signal/action_priority/action_reason 计算 | `stock_card_service.py` | 10min | — | ⏳ |
| 2.3 | generate_holdings_review() 透传新字段 | `review_analysis.py` | 5min | — | ⏳ |
| 2.4 | generate_buy_signals_review() 透传新字段 | `review_analysis.py` | 5min | — | ⏳ |
| 2.5 | 删掉 _make_item_action()，从 review 读 action_type | `review_compute_service.py` | 10min | — | ⏳ |
| 2.6 | 运行后端测试，确认通过 | — | 5min | — | ⏳ |

## 阶段3：前端实现

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 3.1 | BuySignalItem 接口新增 4 字段类型 | `types.ts` | 5min | — | ⏳ |
| 3.2 | StockCard 组件"操作"改用 action_signal | `StockCard.tsx` | 10min | — | ⏳ |
| 3.3 | 前端构建验证 | `build.py` | 10min | — | ⏳ |

## 阶段4：验证+提交

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 4.1 | 全量测试运行 | — | 10min | — | ⏳ |
| 4.2 | git add + commit + push | — | 5min | — | ⏳ |
| 4.3 | 验证部署 | — | 5min | — | ⏳ |

## 阻塞项

无

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-07 | 初稿 |

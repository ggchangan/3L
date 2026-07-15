# 数据管线统一 — 执行计划

> **对应设计文档:** [data-pipeline-unification/design.md](design.md)
> **创建日期:** 2026-06-16
> **状态:** ⏳ 待执行

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----:|:----:|:----:|
| Phase 1: Tushare 增量拉取 | ⏳ | 1h | — |
| Phase 2: 行业映射改读 DB | ⏳ | 2h | — |
| Phase 3: 概念映射改读 DB | ⏳ | 2h | — |
| Phase 4: 指数更新改读 DB | ⏳ | 1h | — |
| Phase 5: 删除板块快照 | ⏳ | 0.5h | — |
| Phase 6: 测试+验证 | ⏳ | 2h | — |

## Phase 1: Tushare 增量拉取（预估 1h）

在 `update_stock_data.py` main() 开头新增 Tushare 增量拉取。

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1.1 | 新增 `_fetch_tushare_daily_incremental()` — 拉 `api.daily` 写 `stock_daily` | `update_stock_data.py` | 20min | — | ⏳ |
| 1.2 | 同时拉 `api.index_daily` 写 `index_daily` | `update_stock_data.py` | 20min | — | ⏳ |
| 1.3 | 已有数据日期跳过逻辑 | `update_stock_data.py` | 10min | — | ⏳ |
| 1.4 | 非交易日跳过 | `update_stock_data.py` | 10min | — | ⏳ |

**阻塞项：** 无

---

## Phase 2: 行业映射改读 DB（预估 2h）

重写 `update_industry_map()`，改用 `ths_member` + `ths_index` DB 查询。

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 2.1 | 分析 `ths_member.con_code` 后缀（.SZ/.SH）处理 | `update_stock_data.py` | 15min | — | ⏳ |
| 2.2 | 重写 `update_industry_map()` — DB 查询 → 组装 → `save_industry_map()` | `update_stock_data.py` | 45min | — | ⏳ |
| 2.3 | 验证行业名变更影响（前端页面展示） | 手动检查 | 30min | — | ⏳ |
| 2.4 | 修复受影响的前端/API（如有） | 各文件 | 30min | — | ⏳ |

**阻塞项：** 行业名变更涉及16+文件，需确认是否全部自动适配（字符串传递不涉及业务逻辑则不需改）

---

## Phase 3: 概念映射改读 DB（预估 2h）

重写 `update_concept_maps()`，改用 DB 查询。

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 3.1 | 分析 DB 查询 → 生成 `concept_list.json` 格式 | `update_stock_data.py` | 30min | — | ⏳ |
| 3.2 | 分析 DB 查询 → 生成 `stock_concept_map.json` 格式 | `update_stock_data.py` | 30min | — | ⏳ |
| 3.3 | 实现并替换 `update_concept_maps()` | `update_stock_data.py` | 45min | — | ⏳ |
| 3.4 | 删除 `_fetch_board_names_from_push2test` + `_fetch_today_sectors_from_push2test`（概念部分） | `update_stock_data.py` | 15min | — | ⏳ |

**阻塞项：** 概念名为同花顺体系，和当前一致，无命名差异问题。

---

## Phase 4: 指数更新改读 DB（预估 1h）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 4.1 | 确认 `data_layer.get_index_data()` 已能从 `index_daily` DB 读到数据 | `data_layer.py` | 10min | — | ⏳ |
| 4.2 | 重写 `update_index()` — 改为调 `data_layer.get_index_data()` 而不是 akshare | `update_stock_data.py` | 30min | — | ⏳ |
| 4.3 | 清理 akshare 相关代码（`fetch_index_klines_from_akshare` 引用） | `update_stock_data.py` | 20min | — | ⏳ |

**阻塞项：** 验证 `get_index_data()` 返回格式与 `update_index()` 的 JSON 缓存格式一致

---

## Phase 5: 删除板块快照（预估 0.5h）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 5.1 | 删除 `_fetch_today_industries_from_ths()` | `update_stock_data.py` | 5min | — | ⏳ |
| 5.2 | 删除 `get_concept_snapshots()` 调用 | `update_stock_data.py` | 5min | — | ⏳ |
| 5.3 | 删除 `get_sector_push2test` 相关验证/告警 | `update_stock_data.py` | 10min | — | ⏳ |
| 5.4 | 清理 `verify_data_sources` 中依赖 push2test 的检查项 | `data_source.py` | 10min | — | ⏳ |

**阻塞项：** `get_sector_push2test()` 是否被前端页面直接调用？需确认后决定是否保留空的快照 API。

---

## Phase 6: 测试+验证（预估 2h）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 6.1 | 更新 mock 测试（`test_data_layer.py` 等） | 测试文件 | 30min | — | ⏳ |
| 6.2 | 手动跑一次完整 `update_stock_data.py` 验证 | — | 30min | — | ⏳ |
| 6.3 | 验证 API 响应正常（review、market 等） | — | 30min | — | ⏳ |
| 6.4 | 全量 pytest 通过 | — | 30min | — | ⏳ |

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-16 | 初版 |

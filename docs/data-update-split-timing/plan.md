# 数据更新时序拆分 — 执行计划

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----|:----:|:----:|
| 设计文档 | ✅ 完成 | 1h | 1h |
| Phase1: 管线拆分 | ⏳ | 1.5h | — |
| Phase2: crontab 调整 | ⏳ | 0.5h | — |
| Phase3: 验证测试 | ⏳ | 1h | — |
| Phase4: 部署上线 | ⏳ | 0.5h | — |

## Phase1：管线拆分

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | main() 拆为 main_phase1() + main_phase2() | `update_stock_data.py` | 30min | — | ⏳ |
| 2 | phase1 跳过 update_sectors() | `update_stock_data.py` | 5min | — | ⏳ |
| 3 | 新增 `--phase1` / `--phase2` 命令行参数 | `update_stock_data.py` | 15min | — | ⏳ |
| 4 | 验证 `python -m backend.core.update_stock_data --phase1` 不阻塞 | 终端 | 10min | — | ⏳ |
| 5 | 验证 `python -m backend.core.update_stock_data --phase2` 只更新板块 | 终端 | 10min | — | ⏳ |
| 6 | 完整管线回归（phase1 + phase2 顺序执行 = 原06:00行为一致） | 终端 | 20min | — | ⏳ |

## Phase2：crontab 调整

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | deploy/crontab 改 18:00 phase1 + 06:00 phase2 | `deploy/crontab` | 5min | — | ⏳ |
| 2 | 安装新 crontab | 终端 | 2min | — | ⏳ |
| 3 | 验证 crontab -l 正确 | 终端 | 2min | — | ⏳ |

## Phase3：验证测试

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 跑 `test_data_layer_db_functions.py` 无回归 | 终端 | 5min | — | ⏳ |
| 2 | 跑 `test_review_service.py`（如有） | 终端 | 5min | — | ⏳ |
| 3 | 验证 after phase1: all_stocks_60d.json 已更新 | 终端 | 3min | — | ⏳ |
| 4 | 验证 after phase2: sector_daily.json last_updated 已更新 | 终端 | 3min | — | ⏳ |
| 5 | 前端验证：复盘页面在 phase1 后能否正常打开 | 浏览器 | 10min | — | ⏳ |

## Phase4：部署上线

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 提交代码 + 推送 | 终端 | 5min | — | ⏳ |
| 2 | 发PR链接 | — | — | — | ⏳ |
| 3 | 用户确认/合并 | — | — | — | ⏳ |
| 4 | checkout master + 重启服务 | 终端 | 5min | — | ⏳ |

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-07-02 | 初版 |

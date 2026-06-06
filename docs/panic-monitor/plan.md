# 恐慌监测 & 策略推送 — 执行计划

## 总览

| 阶段 | 内容 | 状态 | 预估 | 实际 |
|:----|:-----|:----:|:----:|:----:|
| 1 | 回测：历史数据找最优恐慌阈值 | ⏳ | 1h | — |
| 2 | TDD：恐慌判定函数+历史存储（后端） | ⏳ | 1.5h | — |
| 3 | TDD：策略生成+API集成 | ⏳ | 1h | — |
| 4 | 前端：恐慌区块渲染+展开逻辑 | ⏳ | 1.5h | — |
| 5 | 微信推送 cron | ⏳ | 1h | — |
| 6 | 构建+部署+验证 | ⏳ | 0.5h | — |

---

## 阶段一：回测 — 历史数据找最优恐慌阈值

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 回测脚本：遍历阈值组合，统计触发次数+后续涨跌幅 | `scripts/panic_backtest.py` | 30min | — | ⏳ |
| 2 | 分析结果：确定caution/warning两级阈值 | — | 15min | — | ⏳ |
| 3 | 验证最优阈值在最近3个月的稳定性 | — | 15min | — | ⏳ |

**输出：** 确定的阈值数据和评估报告

---

## 阶段二：TDD — 恐慌判定函数+历史存储

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：`detect_panic()` 正常/边缘/空数据三种场景 | `tests/test_panic_monitor.py` | 15min | — | ⏳ |
| 2 | 测试：`save_panic_record()` 文件写入+去重 | `tests/test_panic_monitor.py` | 10min | — | ⏳ |
| 3 | 测试：`get_panic_history()` 返回历史 | `tests/test_panic_monitor.py` | 5min | — | ⏳ |
| 4 | 实现：`panic_monitor_service.py` 完整逻辑 | `services/panic_monitor_service.py` | 30min | — | ⏳ |
| 5 | 验证：全回归测试 | `pytest tests/` | 10min | — | ⏳ |

---

## 阶段三：TDD — 策略生成+API集成

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：`generate_strategy()` 返回正确的策略卡片 | `tests/test_panic_monitor.py` | 10min | — | ⏳ |
| 2 | 测试：`/api/macro` 返回 panic_monitor 字段 | `tests/test_api.py` | 10min | — | ⏳ |
| 3 | 实现：`generate_strategy()` + 策略内容硬编码（基于PDF） | `panic_monitor_service.py` | 10min | — | ⏳ |
| 4 | 修改：`macro_service.get_macro_data()` 注入 panic_monitor | `macro_service.py` | 10min | — | ⏳ |
| 5 | 验证：全回归+curl手动检查API格式 | `pytest tests/` + curl | 10min | — | ⏳ |

---

## 阶段四：前端 — 恐慌区块渲染+展开逻辑

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：恐慌区块在mock数据下的渲染 | `frontend/src/__tests__/Macro.test.tsx` | 15min | — | ⏳ |
| 2 | 实现：恐慌区块组件（等级标签+触发原因+策略卡片+历史） | `Macro.tsx` | 30min | — | ⏳ |
| 3 | 实现：恐慌区块折叠展开动画 | `Macro.css` | 15min | — | ⏳ |
| 4 | 构建验证：`npm run build` + 页面加载测试 | — | 10min | — | ⏳ |

---

## 阶段五：微信推送 cron

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：推送去重逻辑 | `tests/test_panic_pusher.py` | 10min | — | ⏳ |
| 2 | 实现：`panic_pusher.py` — 调用macro API+构建推送消息 | `cron/panic_pusher.py` | 20min | — | ⏳ |
| 3 | 注册cron：交易时段5分钟检测 | `cronjob` | 10min | — | ⏳ |
| 4 | 验证：模拟推送消息到微信 | — | 10min | — | ⏳ |

---

## 阶段六：构建+部署+验证

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | git提交+推送+PR | — | 10min | — | ⏳ |
| 2 | docker build + deploy | — | 10min | — | ⏳ |
| 3 | 上线验证：页面加载+API+历史记录 | — | 10min | — | ⏳ |
| 4 | 通知用户完成 | — | — | — | ⏳ |

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-06 | 初版 |

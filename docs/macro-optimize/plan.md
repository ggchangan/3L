# 外围美股映射优化 — 执行计划

## 总览

| 阶段 | 状态 | 预估 |
|:----|:----|:----:|
| 后端：补全美股+异动检测 | ✅ | 1h |
| 后端：分析API | ✅ | 1h |
| 前端：异动标记+汇总区+分析弹窗 | ✅ | 3h |
| 修复：POST路由注册bug | ✅ | 0.5h |
| 构建+部署 | ✅ | 0.5h |

## 阶段一：后端 — 补全美股+异动检测 ✅

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：补齐23只美股行情拉取 | `tests/test_macro_service.py` | 20min | 15min | ✅ |
| 2 | 测试：异动等级判定(±3%/±5%) | `tests/test_macro_service.py` | 20min | 10min | ✅ |
| 3 | 测试：异动检测与主数据集成 | `tests/test_macro_service.py` | 20min | 10min | ✅ |
| 4 | 实现：补齐美股代码列表 | `macro_service.py` | 15min | 10min | ✅ |
| 5 | 实现：异动判定函数+abnormal_alerts | `macro_service.py` | 30min | 20min | ✅ |
| 6 | 验证：跑测试+手动curl验 | — | 15min | 5min | ✅ |

## 阶段二：后端 — 分析API ✅

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 测试：分析API返回格式 | `tests/test_macro_analysis.py` | 15min | 10min | ✅ |
| 2 | 测试：异常股票新闻搜索 | `tests/test_macro_analysis.py` | 15min | 10min | ✅ |
| 3 | 测试：无异常/无效股票处理 | `tests/test_macro_analysis.py` | 15min | 10min | ✅ |
| 4 | 实现：macro_analysis_service | `services/macro_analysis_service.py` | 30min | 20min | ✅ |
| 5 | 实现：API handler+路由注册 | `api/macro_analysis.py` + `server.py` | 15min | 10min | ✅ |
| 6 | 验证：跑测试+curl验 | — | 15min | 5min | ✅ |

## 阶段三：前端改造 ✅

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 美股卡片加异动标签样式+汇总区+弹窗样式 | `Macro.css` | 15min | 10min | ✅ |
| 2 | 异动汇总区块+卡片标红+分析弹窗 + 修复POST路由bug | `Macro.tsx` + `server.py` | 60min | 20min | ✅ |
| 3 | 构建验证 | — | 15min | 5min | ✅ |

## 阶段四：部署 ✅

| # | 任务 | 预估 | 状态 |
|:-:|:----|:----:|:----:|
| 1 | 提交+推送 | 5min | ✅ |
| 2 | 部署+验证 | 5min | ✅ |

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-05 | 初稿 |

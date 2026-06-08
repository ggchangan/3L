# 统一异常处理与日志模块 — 执行计划 v1

## 总览

| 阶段 | 状态 | 预估 |
|:----|:----|:----:|
| 阶段一：基础框架（core/logger + core/exceptions） | ⏳ | 1h |
| 阶段二：全局拦截 + 统一错误响应 | ⏳ | 1h |
| 阶段三：测试用例 | ⏳ | 1h |
| 阶段四：部署验证 | ⏳ | 0.5h |

## 阶段一：基础框架

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | 创建 `core/logger.py`（从 `services/logger.py` 迁移 + 增加 error 日志独立文件） | `server/backend/core/logger.py` | 15m | ⏳ |
| 2 | 创建 `core/exceptions.py`（分层异常：ThreeLError / DataError / APIError / ConfigError / DataSourceError） | `server/backend/core/exceptions.py` | 10m | ⏳ |
| 3 | 更新 6 个 import 路径（server.py / wsgi.py / data_layer.py / market.py / monitor_service.py / watchlist_service.py） | 6 files | 10m | ⏳ |
| 4 | 删除 `services/logger.py` | `server/backend/services/logger.py` | 2m | ⏳ |

**验证：** 重启服务，确认日志文件 `3l-server.log` 和 `3l-server.error.log` 正常生成

## 阶段二：全局拦截 + 统一错误响应

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | `do_GET()` 添加 try-except 包裹，分类捕获 APIError / DataError / Exception | `server/server.py` | 15m | ⏳ |
| 2 | `do_POST()` 添加 try-except 包裹，同上 | `server/server.py` | 10m | ⏳ |
| 3 | 改造核心 API handler（stock.py / monitor.py / watchlist.py 等），改为显式 raise 分层异常 | ~5 files | 20m | ⏳ |

**验证：** 模拟异常请求，确认返回统一错误结构 `{success, error, error_type}`

## 阶段三：测试用例

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | 分层异常测试：`test_threeL_error_auto_logs` / `test_data_error_inheritance` / `test_api_error_response` / `test_data_source_error_chain` | `tests/test_core_exceptions.py` | 20m | ⏳ |
| 2 | 日志功能测试：`test_log_file_created` / `test_console_output_format` / `test_error_log_separate_file` / `test_rotating_file_handler` | `tests/test_core_logger.py` | 20m | ⏳ |
| 3 | 全局异常拦截测试：mock 一个抛出 APIError 的 handler，验证返回 `{success: false, error_type: "APIError"}` | `tests/test_core_exceptions.py` | 15m | ⏳ |

**验证：** `python3 -m pytest backend/tests/test_core_exceptions.py backend/tests/test_core_logger.py -v`

## 阶段四：部署验证

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | 启动服务，检查日志文件是否正常生成 | — | 5m | ⏳ |
| 2 | 模拟错误请求，检查控制台输出格式 | — | 5m | ⏳ |
| 3 | 前端页面交互测试（随机打开 3-5 个页面，确认功能正常） | — | 10m | ⏳ |
| 4 | 提交 + 推送 + PR 链接 | — | 5m | ⏳ |

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-09 | 初稿 |

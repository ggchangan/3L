# 强势趋势追踪 — 执行计划

> **关联文档：** [design.md](design.md)
> **分支：** `feat/strong-trend-screener`

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----|:----:|:----:|
| 一、设计文档 | ⏳ 进行中 | 1h | — |
| 二、后端实现 + TDD | ⏳ | 2h | — |
| 三、API集成测试 | ⏳ | 1h | — |
| 四、前端 TDD + 实现 | ⏳ | 2h | — |
| 五、构建 + 部署 | ⏳ | 0.5h | — |
| 六、PR + 通知 | ⏳ | 0.5h | — |

## 阶段一：设计文档 ✅

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 产品讨论确认方向 | — | 0.5h | 0.3h | ✅ |
| 2 | 编写设计文档 | `docs/strong-trend-screener/design.md` | 0.5h | — | ✅ |
| 3 | 编写执行计划 | `docs/strong-trend-screener/plan.md` | 0.2h | — | ✅ |

## 阶段二：后端实现 + TDD

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | TDD: 编写后端测试（RED） | `server/backend/tests/test_strong_trend.py` | 0.3h | — | ⏳ |
| 2 | 实现 strong_trend_service.py | `server/backend/services/strong_trend_service.py` | 1.0h | — | ⏳ |
| 3 | 实现 API 端点 | `server/backend/api/strong_trend.py` | 0.3h | — | ⏳ |
| 4 | 注册路由到 server.py | `server/server.py` | 0.1h | — | ⏳ |
| 5 | 运行测试 — 通过（GREEN） | — | 0.2h | — | ⏳ |

## 阶段三：API 集成验证

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | curl 验证 API 返回结构 | — | 0.2h | — | ⏳ |
| 2 | 手动检查数据质量（找漏/误） | — | 0.5h | — | ⏳ |
| 3 | 调整阈值/权重 | 各文件 | 0.3h | — | ⏳ |

## 阶段四：前端 TDD + 实现

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | TDD: 编写前端测试（RED） | `server/frontend/src/__tests__/strong_trend.test.tsx` | 0.3h | — | ⏳ |
| 2 | 实现 StrongTrendCandidates 页面 | `server/frontend/src/pages/StrongTrendCandidates.tsx` | 1.0h | — | ⏳ |
| 3 | 添加到 App.tsx 路由 | `server/frontend/src/App.tsx` | 0.1h | — | ⏳ |
| 4 | 添加到 NavBar | `server/frontend/src/components/NavBar.tsx` | 0.1h | — | ⏳ |
| 5 | 全量测试 | `npm test` | 0.3h | — | ⏳ |

## 阶段五：构建 + 部署

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 构建前端 | `npm run build` | 0.3h | — | ⏳ |
| 2 | 重启服务验证 | `sudo systemctl restart 3l-server` | 0.1h | — | ⏳ |
| 3 | 浏览器验证页面 | — | 0.1h | — | ⏳ |

## 阶段六：PR + 通知

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 提交并推送分支 | — | 0.1h | — | ⏳ |
| 2 | 创建 PR | — | 0.1h | — | ⏳ |
| 3 | 通知用户 | 微信发送PR链接 | 0.1h | — | ⏳ |

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-03 | 创建执行计划 |

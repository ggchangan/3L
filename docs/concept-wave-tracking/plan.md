# 概念板块波谷追踪 — 执行计划

> 本文件跟踪项目执行进度，独立于设计文档。设计文档回答"做什么/为什么"，
> 本文件回答"做到哪了/下一步做什么"。

**分支：** `feature/concept-wave-tracking`
**设计文档：** [design.md](design.md)
**原型预览：** [打开原型](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ggchangan/3L/feature/concept-wave-tracking/docs/concept-wave-tracking/sketch/index.html)

---

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----|:----:|:----:|
| 一：数据基建 | ⏳ 待开始 | 3.5h | — |
| 二：波谷评分 | ⏳ 待开始 | 3.5h | — |
| 三：API + Mock | ⏳ 待开始 | 2h | — |
| 四：前端页面 | ⏳ 待开始 | 2.5h | — |

---

## 阶段一：数据基建（P0）

**目标：** 概念板块映射数据 + K线数据 + SQLite存储就绪

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | `update_concept_maps()` 从push2test f103拉取个股→概念映射，全量覆盖 | `update_stock_data.py` | 1h | — | ⏳ |
| 2 | `update_concept_klines()` 拉概念板块K线（核心池50~80个） | `update_stock_data.py` | 1.5h | — | ⏳ |
| 3 | SQLite `concept_wave.db` 表结构 + `_init_db()` | `concept_wave_service.py` | 0.5h | — | ⏳ |
| 4 | data_layer 新增概念板块读取函数 | `data_layer.py` | 0.5h | — | ⏳ |

**阻塞项：** 无

---

## 阶段二：波谷评分逻辑（P0）

**目标：** 概念板块波谷评分（V5移植适配）可运行

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 5 | `judge_concept_wave()` 波谷评分函数（4条件: BIAS20/量缩/EMA10斜率/2σ跌幅） | `concept_wave_service.py` | 1.5h | — | ⏳ |
| 6 | 波谷信号检测 + 告警生成（vl_score≥3） | `concept_wave_service.py` | 1h | — | ⏳ |
| 7 | 单元测试 | `test_concept_wave.py` | 1h | — | ⏳ |

**阻塞项：** 依赖阶段一完成

---

## 阶段三：API + Mock数据（P1）

**目标：** 后端API就绪 + Mock JSON可供前端独立开发

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 8 | 后端API handler `/api/concept-wave/*` | `api/concept_wave.py` | 0.5h | — | ⏳ |
| 9 | 生成 `mock/concept-wave-mock.json`（按设计文档Schema） | 新建 | 0.5h | — | ⏳ |
| 10 | 注册路由到 server.py + do_POST | `server.py` | 0.5h | — | ⏳ |
| 11 | WxPusher 微信推送集成（强信号通知） | `concept_wave_service.py` | 0.5h | — | ⏳ |

**阻塞项：** 依赖阶段二完成  
**Mock数据用途：** 前端可并行开发，字段结构100%对齐API Schema

---

## 阶段四：前端页面（P1）

**目标：** 概念板块波谷追踪页面可交互运行

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 12 | 前端页面 `ConceptWaveTracking.tsx`（折叠卡片+堆叠走势） | `frontend/src/pages/` | 1.5h | — | ⏳ |
| 13 | CSS 样式 | `ConceptWaveTracking.css` | 0.5h | — | ⏳ |
| 14 | 页面路由注册（spa_routes + html_redirects） | `server.py` | 0.5h | — | ⏳ |

**阻塞项：** 无（可用Mock数据独立开发）

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-05-31 | 创建执行计划，从设计文档分离 |

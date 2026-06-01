# 概念板块波谷追踪 — 执行计划

> 本文件跟踪项目执行进度，独立于设计文档。设计文档回答"做什么/为什么"，
> 本文件回答"做到哪了/下一步做什么"。

**分支：** `feature/concept-wave-tracking`
**设计文档：** [design.md](design.md)
**原型预览：** [打开原型](https://htmlpreview.github.io/?https://raw.githubusercontent.com/ggchangan/3L/feature/concept-wave-tracking/docs/concept-wave-tracking/sketch/index.html)

---

## 开发策略

每个阶段独立可测互不阻塞，都用Mock/合成数据开发验证，最后再连接真实数据。

```
阶段一（前端） ← Mock数据 → 独立可验证
阶段二（API）  ← Mock数据 → 独立可验证
阶段三（评分） ← 合成用例 → 独立可验证（含回测报告→review→调参）
阶段四（基建） ← 真实接口 → 独立可验证
```

---

## 总览

| 阶段 | 内容 | 依赖 | 状态 |
|:----|:-----|:----|:----:|
| 一 | 前端页面 `ConceptWaveTracking.tsx` | 设计文档API Schema（已定稿） | ✅ |
| 五 | API层 handler + 连接真实数据 | 无（实时评分） | ✅ |
| 六 | 概念映射管线（update_concept_maps） | 无（akshare+push2test） | ✅ |
| 七 | 连接真实数据 → 前端渲染 | sector_daily.json | ✅ |

---

## 阶段一：前端页面（P0）

**目标：** 前端页面可交互运行（数据来自Mock JSON）

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | `ConceptWaveTracking.tsx` 主页面（折叠卡片+堆叠走势+统计卡+告警+扫描） | `frontend/src/pages/` | 1.5h | 1.5h | ✅ |
| 2 | `ConceptWaveTracking.css` 样式（暗色主题，对齐现有设计系统） | `frontend/src/pages/` | 0.5h | 0.3h | ✅ |
| 3 | Mock JSON（按设计文档API Schema生成） | `server/frontend/src/mock/` | 0.5h | 0.2h | ✅ |
| 4 | 页面路由注册（spa_routes + App.tsx） | `server.py` + `App.tsx` | 0.5h | 0.2h | ✅ |

**验证方式：** 浏览器打开页面，Mock数据渲染正确、展开折叠交互正常

---

## 阶段二：API层（P0）

**目标：** 后端API路由就绪（先返回静态Mock数据）

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 5 | `concept_wave.py` handler（GET/POST路由） | `backend/api/concept_wave.py` | 0.5h | ⏳ |
| 6 | 注册路由到 server.py（GET routes + do_POST） | `server.py` | 0.5h | ⏳ |
| 7 | 前端切到真实API路径，回归测试 | 前端 | 0.5h | ⏳ |

**验证方式：** `curl /api/concept-wave` 返回JSON结构=设计文档Schema

---

## 阶段三：波谷评分 + 回测（P1）

**目标：** V5移植到概念板块，跑回测报告review后调参

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 8 | `judge_concept_wave()` 开发（V5移植：BIAS20/量缩/EMA斜率/2σ跌幅） | `concept_wave_service.py` | 1.5h | ⏳ |
| 9 | `backtest_report()` 输出历史vl_score≥3 + 后续5日涨跌 | `concept_wave_service.py` | 1h | ⏳ |
| 10 | 单元测试（合成用例） | `test_concept_wave.py` | 1h | ⏳ |
| 11 | **输出回测报告 → 用户review → 调参 → 锁定** | — | 1h | ⏳ |

**验证方式：** 单元测试覆盖已知case；回测报告显示准确率

---

## 阶段四：数据基建管线（P1）

**目标：** 按评分逻辑需要的字段和天数，拉取真实数据

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 12 | `update_concept_maps()` （push2test f103个股→概念映射） | `update_stock_data.py` | 1h | ⏳ |
| 13 | `update_concept_klines()` （拉概念板块K线） | `update_stock_data.py` | 1.5h | ⏳ |
| 14 | 连接data_layer + 评分逻辑跑真实数据 | — | 0.5h | ⏳ |

**验证方式：** 真实数据跑评分，与Mock数据结果一致

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-05-31 | 创建执行计划，从设计文档分离 |
| 2026-05-31 | 重构为四阶段：前端→API→评分+回测→基建，各阶段独立可测 |

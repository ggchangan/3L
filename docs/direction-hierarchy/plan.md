# 方向分层 + 概念绑定 — 执行计划

## 总览

| 阶段 | 状态 | 预估 | 实际 |
|:----|:----:|:----:|:----:|
| 阶段一：前端Mock | ⏳ | 7h | — |
| 阶段二：后端 | ⏳ | 4h | — |
| 阶段三：集成 | ⏳ | 2h | — |
| 阶段四：回归测试 | ⏳ | 2h | — |
| 阶段五：部署 | ⏳ | 2h | — |
| 阶段六：检查+修复 | ⏳ | 2h | — |

---

## 阶段一：前端Mock（3个子阶段并行）

**原则：** 不与后端绑定。前端自己生成Mock JSON，API Schema 100% 对齐 design doc。

### 1-a 方向管理面板（Watchlist.tsx）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 方向面板改为可展开的两层树结构（大类→细分） | `Watchlist.tsx` | 1.5h | — | ⏳ |
| 2 | 大类的添加/删除/启用/禁用 UI | `Watchlist.tsx` | 0.5h | — | ⏳ |
| 3 | 细分方向的添加/删除/启用/禁用 UI | `Watchlist.tsx` | 0.5h | — | ⏳ |
| 4 | 个股添加/编辑时的方向选择器改为多选Tags | `Watchlist.tsx` | 1h | — | ⏳ |
| 5 | 适配新的API响应格式（Mock JSON先固定） | `Watchlist.tsx` | 0.5h | — | ⏳ |
| 6 | 相关CSS | `Watchlist.css` | 0.5h | — | ⏳ |

### 1-b 概念绑定弹窗（新建组件）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 新建 ConceptBindingModal 组件 | `components/ConceptBindingModal.tsx` | 1h | — | ⏳ |
| 2 | 搜索同花顺概念 + 多选 + 自选股数展示 | `components/ConceptBindingModal.tsx` | 1h | — | ⏳ |
| 3 | 在方向面板中接入绑定弹窗 | `Watchlist.tsx` | 0.5h | — | ⏳ |
| 4 | 弹窗相关CSS | `Watchlist.css` | 0.5h | — | ⏳ |

### 1-c 概念波谷分组视图（ConceptWaveTracking.tsx）

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 概念波谷页面新增方向Tab（每个大类一个Tab） | `ConceptWaveTracking.tsx` | 1h | — | ⏳ |
| 2 | 按grouped_by_direction渲染分组视图 | `ConceptWaveTracking.tsx` | 1h | — | ⏳ |
| 3 | 卡片标题改为细分方向名+关联概念名 | `ConceptWaveTracking.tsx` | 0.5h | — | ⏳ |
| 4 | 相关CSS | `ConceptWaveTracking.css` | 0.5h | — | ⏳ |

---

## 阶段二：后端

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 设计新 directions.json 数据结构（JSON schema） | `direction_service.py` | 0.5h | — | ⏳ |
| 2 | 实现 CATEGORY CRUD | `direction_service.py` | 0.5h | — | ⏳ |
| 3 | 实现 SUB_DIRECTION CRUD | `direction_service.py` | 0.5h | — | ⏳ |
| 4 | 实现 CONCEPT BINDING（bind/unbind/search_concepts） | `direction_service.py` | 0.5h | — | ⏳ |
| 5 | 实现 parse_direction / format_direction 工具函数 | `direction_service.py` | 0.5h | — | ⏳ |
| 6 | 实现 migrate_v1_to_v2 数据迁移 | `direction_service.py` | 0.5h | — | ⏳ |
| 7 | 兼容旧接口 get_active() / get_all_ordered() | `direction_service.py` | 0.5h | — | ⏳ |
| 8 | 新增大类CRUD / 细分CRUD / 概念绑定API端点 | `api/directions.py` | 1h | — | ⏳ |
| 9 | 新增数据迁移 API端点 | `api/directions.py` | 0.5h | — | ⏳ |
| 10 | 概念波谷 API 新增 group_by=direction | `api/concept_wave.py` | 1h | — | ⏳ |
| 11 | 注册新路由到 server.py | `server.py` | 0.5h | — | ⏳ |

**阻塞项：** 无（与阶段一可并行）

---

## 阶段三：集成

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 前端Mock数据切到真实API | 前端各文件 | 0.5h | — | ⏳ |
| 2 | 运行 v1→v2 数据迁移（19个平方向 → 层级格式） | 数据操作 | 0.5h | — | ⏳ |
| 3 | watchlist.json direction→directions 字段迁移 | 数据操作 | 0.5h | — | ⏳ |
| 4 | 前端构建 + 部署到测试环境 | `build.py` | 0.5h | — | ⏳ |

**阻塞项：** 依赖阶段一+二完成

---

## 阶段四：回归测试

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 验证自选股方向显示正确（翻两三只看） | 检查 | 0.5h | — | ⏳ |
| 2 | 验证概念波谷分组视图（每个大类的数据正确） | 检查 | 0.5h | — | ⏳ |
| 3 | 验证买点扫描结果（看扫描出的3只票方向是否正确） | 检查 | 0.5h | — | ⏳ |
| 4 | 验证持仓页方向分组正常 | 检查 | 0.5h | — | ⏳ |

**阻塞项：** 依赖阶段三完成

---

## 阶段五：部署

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | deploy.sh 检查（是否要改部署结构） | `deploy.sh` | 0.5h | — | ⏳ |
| 2 | 提交所有改动 + PR | git | 0.5h | — | ⏳ |
| 3 | 部署到服务器 | `deploy.sh` | 0.5h | — | ⏳ |
| 4 | 部署后验证页面可用 | 检查 | 0.5h | — | ⏳ |

**阻塞项：** 依赖阶段四通过

---

## 阶段六：检查+修复

| # | 任务 | 文件 | 预估 | 实际 | 状态 |
|:-:|:----|:----|:----:|:----:|:----:|
| 1 | 上线后观察是否有报错/展示异常 | 检查 | 1h | — | ⏳ |
| 2 | 根据问题讨论 + 修复 | 待定 | 1h | — | ⏳ |

**阻塞项：** 依赖阶段五完成

---

## 变更记录

| 日期 | 变更 |
|:----|:-----|
| 2026-06-04 | 初稿 |
| 2026-06-04 | 改为前端Mock→后端→集成→回归→部署→检查修复的顺序 |

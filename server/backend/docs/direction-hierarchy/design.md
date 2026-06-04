# 方向分层 + 概念绑定 — 设计文档 v1.0

> **状态：** ✅ 已实现并合入 `feat/direction-hierarchy` 分支（2026-06-04）

## 0. 总览

方向管理系统从 V1 的"平坦列表"升级为 V2 的"大类→细分方向"两层结构，同时支持将同花顺概念板块绑定到细分方向。

**核心布局：**
- 左侧方向面板：大类为可折叠组标题，下方列出细分方向（带启用开关）
- 概念绑定弹窗：搜索概念 → 选中 → 绑定到细分方向
- 概念板块追踪页：新增"按方向分组"Tab

## 1. 背景与问题

### 现状

V1 方向管理将所有方向放在一个平坦列表中，用 `all`/`active` 两个数组管理。

```json
{"all": ["半导体", "算力", "创新药", "AI"], "active": ["半导体", "算力"]}
```

### 痛点

| 问题 | 影响 |
|:----|:-----|
| 没有分类，20+方向一排到底 | 找方向困难、维护成本高 |
| 自选股方向字段混存旧格式 `direction` 和新格式 `directions` | 前端读取需兼容两种格式 |
| 概念板块绑定无后台管理 | 手动在代码里配置概念代码，无 UI 支持 |

### 目标

方向管理支持"大类→细分方向"两层结构 + 概念绑定（UI + API + 数据持久化），且完全向后兼容 V1 格式。

## 2. 设计思想

### 2.1 核心理念

- **方向即标签**：一只股票可以有多个方向，方向是大类+细分方向的两级标签
- **概念即数据源**：概念板块是方向的数据底座——绑定了概念后，该概念的成分股自动关联到方向下
- **向后兼容高于一切**：现存 V1 格式的 `directions.json` 和 `watchlist.json` 必须无缝升级

### 2.2 方案选择

| 候选 | 优点 | 缺点 | 结论 |
|:----|:-----|:-----|:----:|
| **用 `.` 分隔符** 结构如 `"科技.半导体"` | 无需新增存储字段，文件格式简单。兼容 flat list 查询 | 解析需拆分 key | ✅ 选定了 |
| 独立的嵌套 JSON 如 `{"categories": {"科技": {"半导体": ...}}}` | 语义清晰 | 更改 key 需递归更新 watchlist，迁移复杂 | ❌ |
| 数据库存储 | 查询方便 | 引入额外依赖 | ❌ |

**为什么选 `.` 分隔符方案：**
1. V1 已有 flat key list，`科技.半导体` 作为 key 天然兼容 `get_all()` 返回值
2. `watchlist.json` 中方向字段已用字符串存储，改变 key 格式影响最小
3. 搜索/启用/禁用等查操作只需 `parse_direction()` 按 `.` 分割

### 2.3 设计原则

1. **V1 格式读时自动升级** — 旧 `{all: [...], active: [...], suggestions: {...}, core: {...}}` 在 `_load()` 时自动转为 V2
2. **变更同步** — 大类改名/细分方向移动时，自动同步 `watchlist.json` 中的引用
3. **概念即方向的数据** — 方向关联概念，概念成分股是从数据源拉取的副产品，方向本身不存股票列表

### 2.4 屏幕内外

- **做什么：**
  - 大类/细分方向的 CRUD（添加、删除、重命名、启用/禁用、排序、移动）
  - 概念板块搜索与绑定/解绑
  - 方向面板以树结构展示（折叠分类组）
  - 概念板块追踪页按方向分组
  - 自选股支持多方向选择
  - V1 → V2 无缝迁移

- **不做什么：**
  - 不从方向绑定数据自动生成自选股（选股是独立行为）
  - 不做自动扫描建议方向（现有 suggestions 机制已够用）
  - 不存股票列表到方向下（只在运行时按概念拉取）
  - 不做方向间股票交叉分析

## 3. 数据模型

### 3.1 文件格式 (directions.json)

```json
{
  "version": 2,
  "categories": {
    "科技": {"order": 0, "enabled": true},
    "医药": {"order": 1, "enabled": true},
    "新能源": {"order": 2, "enabled": true}
  },
  "sub_directions": {
    "科技.半导体": {
      "category": "科技", "enabled": true, "order": 0,
      "concept_codes": ["301085", "307940"],
      "concept_names": ["芯片概念", "存储芯片"]
    },
    "科技.AI": {
      "category": "科技", "enabled": true, "order": 1,
      "concept_codes": [],
      "concept_names": []
    },
    "医药.创新药": {
      "category": "医药", "enabled": true, "order": 0,
      "concept_codes": ["306168"],
      "concept_names": ["创新药"]
    }
  },
  "suggestions": {"industry": [...], "concept": [...], "custom": [...]},
  "core": {"002371": {"name": "北方华创", "deviation": 6}}
}
```

**V1 → V2 迁移规则：**
1. `all` → 全部归入"未分类"大类
2. `active` → 对应细分方向的 enabled 状态
3. 新增 `categories` / `sub_directions` 结构
4. 新增 `version` 字段标记为 2

### 3.2 JSON Key 约束

- 大类名不可包含 `.` 字符
- 细分方向完整 key = `{大类名}.{细分方向名}` 或（无大类时）`{细分方向名}`
- sub_directions 对象以完整 key 为键

### 3.3 数据流

```
用户操作(API) → direction_service.py → directions.json
  ↑                              ↓
  └──── watchlist.json ◄─────────┘(rename/move 时同步)
```

## 4. 系统设计

### 4.1 架构总览

```
api/directions.py          — 路由层：12个 API 端点
services/direction_service.py — 服务层：40+个公开函数
tests/test_direction_service.py — 服务层测试：69个
tests/test_direction_api.py     — API层测试：39个
```

**后端依赖：** 无新增依赖，共用 `backend.config.DATA_DIR`

### 4.2 核心算法/逻辑

**parse_direction(full_name) → (category, sub_name)**
- `"科技.半导体"` → `("科技", "半导体")`
- `"半导体"` → `("", "半导体")`

**format_direction(category, sub_name) → full_name**
- `("科技", "半导体")` → `"科技.半导体"`
- `("", "半导体")` → `"半导体"`

**rename_category(old_name, new_name):**
1. 重命名 categories 中的 key
2. 更新所有 sub_directions 中 category = old_name 的条目
3. 同步更新 watchlist.json 中的 key 引用

**move_sub_direction(category, sub_name, new_category):**
1. 在原分类中删除条目
2. 在新分类中插入条目（自动计算 order）
3. 同步更新 watchlist.json 中的 key 引用

### 4.3 API 设计

#### GET /api/directions/get

完整状态快照，前端方向面板使用。

**响应：**
```json
{
  "categories": [
    {"name": "科技", "enabled": true, "sub_count": 3, "order": 0}
  ],
  "sub_directions": {
    "科技.半导体": {
      "category": "科技", "enabled": true, "order": 0,
      "concept_codes": ["301085"],
      "concept_names": ["芯片概念"],
      "concepts": [{"code": "301085", "name": "芯片概念"}]
    }
  },
  "active": ["科技.半导体"],
  "version": 2
}
```

#### POST 端点

| 端点 | 请求体 | 说明 |
|:----|:-------|:-----|
| `/api/directions/category/add` | `{name}` | 添加大类 |
| `/api/directions/category/remove` | `{name}` | 删除大类（含子方向） |
| `/api/directions/category/toggle` | `{name, enabled}` | 启用/禁用大类 |
| `/api/directions/category/reorder` | `{names}` | 重排大类顺序 |
| `/api/directions/category/rename` | `{old_name, new_name}` | 重命名大类 |
| `/api/directions/sub/add` | `{name, category}` | 添加细分方向 |
| `/api/directions/sub/remove` | `{name}` | 删除细分方向（完整key） |
| `/api/directions/sub/toggle` | `{name, enabled}` | 启用/禁用细分方向 |
| `/api/directions/sub/reorder` | `{names}` | 重排细分方向顺序 |
| `/api/directions/sub/rename` | `{name, new_name}` | 重命名细分方向 |
| `/api/directions/sub/move` | `{name, new_category}` | 移动细分方向到其他大类 |
| `/api/directions/bind` | `{sub_dir, concept_code}` | 绑定概念到细分方向 |
| `/api/directions/unbind` | `{sub_dir, concept_code}` | 解绑概念 |
| `/api/directions/migrate` | — | 显式触发 V1→V2 迁移 |

**响应格式（POST 端点统一）：**
```json
{"success": true}
// 或
{"success": false, "error": "错误原因"}
```

#### GET /api/directions/concepts/search?q=xxx

概念搜索，支持中文模糊匹配 + 拼音首字母匹配。

**响应：**
```json
{"results": [{"code": "301085", "name": "芯片概念"}]}
```

### 4.4 前端设计

#### 方向面板（左侧边栏）

V1 → V2 的变化：
- 大类显示为可折叠组标题（`▶ 科技 [3]`）
- 点击组标题展开/收起该分类下的细分方向
- 细分方向显示条目（`半导芯片` `存储芯片` 带启用开关）
- 底部有添加大类/添加细分方向的按钮

#### 概念绑定弹窗

- 搜索框输入概念名 → 下拉展示匹配结果
- 点击结果项 → 绑定到当前细分方向
- 已绑定的概念显示在细分方向下，右侧有解绑按钮

#### 概念板块追踪页

新增"方向分组"Tab，按方向聚合展示概念板块走势数据。

## 5. 执行计划（已实现）

| # | 任务 | 文件 | 状态 |
|:-:|:----|:----|:----:|
| 1 | V2 数据模型 + 迁移逻辑 | `direction_service.py` | ✅ |
| 2 | 大类/细分方向 CRUD 操作 | `direction_service.py` | ✅ |
| 3 | 概念绑定/解绑/搜索 | `direction_service.py` | ✅ |
| 4 | 兼容接口保持 V1 签名 | `direction_service.py` | ✅ |
| 5 | API 路由（12+端点） | `api/directions.py` | ✅ |
| 6 | 左侧方向面板树结构 | `DirectionPanel.vue` | ✅ |
| 7 | 概念绑定弹窗 | `ConceptBindingModal.vue` | ✅ |
| 8 | 概念波段追踪方向分组Tab | `ConceptWaveTracking.vue` | ✅ |
| 9 | 自选股多方向选择 | `WatchlistItem.vue` | ✅ |
| 10 | 服务层测试（69个） | `test_direction_service.py` | ✅ |
| 11 | API层测试（39个） | `test_direction_api.py` | ✅ |
| 12 | 设计文档（本章） | `docs/direction-hierarchy/design.md` | ✅ |

## 6. 附录

### 6.1 替代方案

**嵌套 JSON 格式：** 被否决。key 变更时 watchlist 同步成本高。

### 6.2 向后兼容策略

1. V1 → V2 自动升级：`_load()` 检测 `version !== 2` 时自动调用 `_migrate_v1_to_v2_inplace()`
2. V1 兼容函数：`add(name)` / `remove(name)` / `set_active(name, active)` 保持签名不变
3. 旧 watchlist 格式支持：`get_stock_directions()` 同时支持 `direction`（字符串）和 `directions`（数组）
4. 旧 sub_direction key 兼容：`set_sub_direction_enabled()` / `rename_sub_direction()` / `move_sub_direction()` 在找不到 `"科技.半导体"` 时会尝试直接用 `"半导体"` 查找

### 6.3 文件清单

```
新增：
  server/backend/api/directions.py                   — API 路由
  server/backend/docs/direction-hierarchy/design.md   — 本设计文档

修改：
  server/backend/services/direction_service.py       — V2 核心逻辑
  server/backend/tests/test_direction_service.py     — 69 个服务层测试
  server/backend/tests/test_direction_api.py         — 39 个 API 层测试
  server/frontend/src/components/DirectionPanel.vue  — 方向面板树结构
  server/frontend/src/components/ConceptBindingModal.vue — 概念绑定弹窗
  server/frontend/src/components/ConceptWaveTracking.vue — 方向分组Tab
  server/frontend/src/components/WatchlistItem.vue   — 多方向选择
  server/frontend/src/App.vue (或 index.css)         — 方向面板样式
```

### 6.4 变更日志

| 版本 | 日期 | 变更内容 |
|:----|:----|:--------|
| v1.0 | 2026-06-04 | 初稿（功能已实现后回补） |

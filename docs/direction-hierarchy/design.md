# 方向分层 + 概念绑定 — 设计文档 v1

## 0. 前端原型总览

> 📸 **先看图，再看字。** 本章是原型截图占位。

```
原型待截图：
  - 自选股管理页面：方向管理面板改为两层树结构
  - 概念波谷追踪页面：按大类分组的"科技"/"医药"/"新能源" Tab
```

**核心布局一句话：** 自选股管理右侧的方向面板从平的列表改为可展开的两层树（大类→细分），每个细分方向可绑定多个同花顺概念板块；概念波谷追踪页面新增按大类分组视图，组内展示细分方向的波峰波谷轮动。

---

## 1. 背景与问题

### 现状

当前的方向（direction）系统是**平的一层**：

```
先进封装 | MLCC | PCB概念 | 半导体 | 算力 | 资源股 | 机器人
AI应用 | 创新药 | 商业航天 | 新能源 | 培育钻石 | 光纤概念
CPO | 存储 | AIPC | 消费电子 | 半导体设备
```

共 19 个方向，每个自选股只能选一个。概念波谷追踪（concept_wave）有 375 个同花顺概念板块的波峰波谷评分，但目前独立于方向系统展示。

### 痛点/断层

| 问题 | 影响 |
|:----|:-----|
| **方向平的，看不出层次** | 半导体/算力/机器人都是平级，实际上它们同属"科技"大类 |
| **当前市场在科技内部轮动** | 科技→科技，不是科技→医药，平的视图看不出来谁在轮换 |
| **概念波谷数据独立** | 概念波谷追踪页面有精细的波峰波谷数据，但跟方向系统完全割裂 |
| **没有分组轮动视图** | 看不出"科技类哪些细分到波谷、哪些刚到波峰" |

### 目标

把方向改为**两层结构**（大类→细分方向），细分方向可绑定同花顺概念板块，实现概念波谷追踪按大类分组展示轮动。

---

## 2. 设计思想

### 2.1 核心理念

> **方向不是标签，是分组器。**

方向系统的核心价值不是给个股打标签（那个对交易决策没有什么用），而是把概念板块按用户关注的大类分组，让概念波峰波谷数据能按**组**查看——一眼看出"科技内部谁到波谷可以进、谁到波峰该回避"。

### 2.2 方案选择

#### 个股归属方案

| 候选方案 | 优点 | 缺点 | 结论 |
|:--------|:----|:----|:----:|
| **A: 个股可多选细分方向** | 贴近现实（一只票跨多个概念板块），数据多对多 | `watchlist.json` direction字段从字符串变数组，需迁移 | ✅ |
| B: 个股只选一个方向 | 改动最小 | 大族激光既是PCB又是机器人，只能二选一，丢失信息 | ❌ |
| C: 个股自动从概念反推方向 | 自动化 | 一票挂N个概念，其中一半是噪声，不可控 | ❌ |

**结论：** 选方案A。个股在添加/编辑时，可从多个细分方向中勾选。`watchlist.json` 中 `direction` 字段改为 `directions`（字符串数组），后端兼容两种格式，前端改成多选Tags选择器。

**理由（数据支撑）：** 大族激光同时属于 PCB概念、机器人概念、5G、华为概念、光纤概念、芯片概念……如果当前方向系统有"科技.PCB概念"和"科技.机器人"两个方向，大族激光应能同时归属两者。一只票跨多个概念板块是A股常态，多选方向更贴近现实。

#### 方向→概念绑定方案

| 候选方案 | 优点 | 缺点 | 结论 |
|:--------|:----|:----|:----:|
| **A: 手动绑定概念板块** | 精准可控，只绑定关注的概念 | 需要用户手动设置一次 | ✅ |
| B: 自动从自选股涉及的概念反推 | 零配置 | 混入不关注的概念 | ❌ |

**结论：** 选方案A。每个细分方向手动绑定多个同花顺概念板块，一次性设置后长期有效。

### 2.3 设计原则

1. **个股管理不复杂化** — 个股仍然选一个方向，下拉框多了一级选择而已
2. **概念绑定做一次** — 建好方向后绑概念，后续几乎不改
3. **概念波谷页面是最终消费者** — 方向分层+概念绑定的所有努力，最终体现在概念波谷页面按大类看轮动

### 2.4 屏幕内外

**这个功能做：**
- 方向从平的改成两层（大类→细分方向）
- 个股可多选细分方向
- 细分方向可绑定多个同花顺概念板块
- 概念波谷追踪页面新增按大类分组的视图
- 自选股管理页面的方向面板改为两层结构+多选Tags编辑器

**这个功能不做：**
- ❌ 自动概念推荐（手动绑定即可）
- ❌ 方向迁移工具（旧数据的个股方向保留字符串字段，兼容读取）

---

## 3. 数据模型

### 3.1 directions.json（新增格式）

```json
{
  "categories": {
    "科技": {
      "order": 0,
      "enabled": true
    },
    "医药": {
      "order": 1,
      "enabled": true
    },
    "新能源": {
      "order": 2,
      "enabled": true
    }
  },
  "sub_directions": {
    "科技.半导体": {
      "category": "科技",
      "enabled": true,
      "order": 0,
      "concept_codes": ["301085", "307940", "308725", "309049", "308384"],
      "concept_names": ["芯片概念", "存储芯片", "半导体", "先进封装", "MLCC"]
    },
    "科技.算力": {
      "category": "科技",
      "enabled": true,
      "order": 1,
      "concept_codes": ["301459", "308828", "308642"],
      "concept_names": ["华为概念", "人工智能", "东数西算(算力)"]
    },
    "科技.机器人": {
      "category": "科技",
      "enabled": true,
      "order": 2,
      "concept_codes": ["300816", "309119", "309000"],
      "concept_names": ["机器人概念", "人形机器人", "特斯拉概念"]
    },
    "医药.创新药": {
      "category": "医药",
      "enabled": true,
      "order": 0,
      "concept_codes": ["308014", "301505"],
      "concept_names": ["阿尔茨海默概念", "创新药"]
    }
  },
  "version": 2,
  "migrated_from_v1": false
}
```

### 3.2 watchlist.json（个股 direction → directions 数组）

```json
{
  "stocks": [
    {
      "code": "688981",
      "name": "中芯国际",
      "directions": ["科技.半导体", "科技.算力"],
      "industry": "集成电路设计"
    },
    {
      "code": "300308",
      "name": "中际旭创",
      "directions": ["科技.算力"],
      "industry": "光模块"
    },
    {
      "code": "002008",
      "name": "大族激光",
      "directions": ["科技.PCB概念", "科技.机器人", "科技.光纤概念"],
      "industry": "激光"
    }
  ]
}
```

**变化：** 字段名从 `direction`（字符串）→ `directions`（字符串数组）。后端兼容旧格式（读取时如果取到字符串，自动转单元素数组）。

### 3.3 数据流

```
┌─────────────────────────┐
│  自选股管理页面          │  ← 建大类/建细分/绑概念
│  Watchlist.tsx           │
├─────────────────────────┤
│  direction_service.py    │  ← CRUD 操作
│  directions.json         │
├─────────────────────────┤
│  parse_direction(name)   │  ← 解析 "科技.半导体" → {category, sub_dir}
│    name.split('.', 1)    │
├─────────────────────────┤
│  概念波谷 API            │  ← 按大类分组
│  /api/concept-wave       │
├─────────────────────────┤
│  概念波谷页面             │  ← 展示：大类Tab → 细分方向的波峰波谷
│  ConceptWaveTracking.tsx │
└─────────────────────────┘
```

---

## 4. 系统设计

### 4.1 架构总览

```
direction_service.py          ← 核心服务（新增/重写）
├── Category CRUD             ← 新增
│   ├── add_category(name, order?)
│   ├── remove_category(name)
│   ├── set_category_enabled(name, bool)
│   └── get_categories() → [{name, enabled, sub_count}]
├── SubDirection CRUD         ← 新增
│   ├── add_sub_direction(name, category, order?)
│   ├── remove_sub_direction(name)
│   ├── set_sub_direction_enabled(name, bool)  ← 相当于原来的 set_active
│   └── get_sub_directions(category?) → [{name, category, enabled, concepts}]
├── Concept Binding           ← 新增
│   ├── bind_concept(sub_dir, concept_code)
│   ├── unbind_concept(sub_dir, concept_code)
│   ├── search_concepts(q) → [{code, name, stock_count}]
│   └── get_bound_concepts(sub_dir) → [{code, name}]
├── Legacy Support            ← 兼容旧数据
│   ├── get_active()          ← 返回已启用的细分方向名列表（兼容旧调用方）
│   ├── get_all_ordered()     ← 返回有序的所有细分方向名列表
│   └── migrate_v1_to_v2()   ← 将平的 directions.json 转为层级格式
└── Utils
    ├── parse_direction(name) → (category, sub_dir)  ← "科技.半导体" → ("科技", "半导体")
    └── format_direction(category, sub_dir) → "科技.半导体"
```

### 4.2 解析工具函数

```python
def parse_direction(full_name: str) -> tuple:
    """解析 "科技.半导体" → ("科技", "半导体")"""
    parts = full_name.split('.', 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return ('其他', full_name)

def format_direction(category: str, sub_dir: str) -> str:
    """("科技", "半导体") → "科技.半导体" """
    return f"{category}.{sub_dir}"
```

**关键设计决策：** 所有后端服务只加一层 `parse_direction()` 解析，不需要重构过滤/分组逻辑。

### 4.3 API 设计

API 路由全在 `api/directions.py`（同一文件），新增/修改端点：

| 端点 | 方法 | 用途 |
|:-----|:-----|:-----|
| `/api/directions/get` | GET | 返回完整方向数据（大类+细分+启用状态+概念绑定） |
| `/api/directions/category/add` | POST | 添加大类 `{name, order?}` |
| `/api/directions/category/remove` | POST | 删除大类 `{name}` |
| `/api/directions/category/toggle` | POST | 启用/禁用大类 `{name, enabled}` |
| `/api/directions/sub/add` | POST | 添加细分方向 `{name, category, order?}` |
| `/api/directions/sub/remove` | POST | 删除细分方向 `{name}` (该方向股票归入"其他") |
| `/api/directions/sub/toggle` | POST | 启用/禁用细分方向 `{name, enabled}` |
| `/api/directions/bind` | POST | 绑定概念 `{sub_dir, concept_code}` |
| `/api/directions/unbind` | POST | 解绑概念 `{sub_dir, concept_code}` |
| `/api/directions/concepts/search` | GET | 搜索可选概念 `?q=半导` |
| `/api/directions/migrate` | POST | v1→v2数据迁移（仅执行一次） |

**GET `/api/directions/get` 响应格式：**

```json
{
  "categories": [
    {"name": "科技", "enabled": true, "sub_count": 5, "order": 0},
    {"name": "医药", "enabled": true, "sub_count": 2, "order": 1}
  ],
  "sub_directions": {
    "科技.半导体": {
      "category": "科技",
      "enabled": true,
      "concepts": [
        {"code": "301085", "name": "芯片概念"},
        {"code": "307940", "name": "存储芯片"}
      ]
    }
  },
  "active": ["科技.半导体", "科技.算力", "医药.创新药"],
  "version": 2
}
```

#### 概念波谷 API 扩展

**GET `/api/concept-wave?group_by=direction`**

在现有 `/api/concept-wave` 端点新增 `group_by=direction` 参数，按大类分组返回：

```json
{
  "grouped_by_direction": {
    "科技": {
      "valley": [{"name": "半导体设备", "vl_score": 4, ...}],
      "mid": [{"name": "算力", "vl_score": 2, ...}],
      "peak": [{"name": "CPO", "pk_score": 4, ...}]
    },
    "医药": {
      "valley": [{"name": "创新药", "vl_score": 3, ...}]
    }
  }
}
```

### 4.4 前端设计

#### 4.4.1 自选股管理 — 方向面板

```
┌───────────────────────────────────────┐
│ 🎯 方向管理 ▾                          │
├───────────────────────────────────────┤
│ 添加方向                               │
│ [请输入方向名] [科技.半导体] [添加]      │
├───────────────────────────────────────┤
│ 📁 科技 (5个细分)       [全部启用/禁用] │
│   ├─ ☑ 半导体          [⚙绑定概念] [✕]│
│   ├─ ☑ 算力            [⚙绑定概念] [✕]│
│   ├─ ☑ 机器人          [⚙绑定概念] [✕]│
│   ├─ ☑ CPO             [⚙绑定概念] [✕]│
│   └─ ☐ 存储            [⚙绑定概念] [✕]│
│                                        │
│ 📁 医药 (1个细分)       [全部启用/禁用] │
│   └─ ☑ 创新药          [⚙绑定概念] [✕]│
│                                        │
│ 📁 新能源 (0个细分)     [添加细分方向]   │
├───────────────────────────────────────┤
│ 添加大类 [+ 新建大类]                   │
└───────────────────────────────────────┘
```

**交互说明：**
- 大类可展开/折叠，显示其下的细分方向
- 大类右侧显示细分方向数
- 每个细分方向行有：复选框（启用/禁用）、名称、齿轮按钮（打开概念绑定弹窗）、删除按钮
- 细分方向拖拽排序（按大类内部排序）
- 大类的启用/禁用 = 批量启用/禁用其下所有细分方向

#### 4.4.2 概念绑定弹窗

```
┌───────────────────────────────────────┐
│ 🎯 绑定概念 — 科技.半导体               │
├───────────────────────────────────────┤
│ [搜索同花顺概念板块...]                  │
├───────────────────────────────────────┤
│ ✅ 芯片概念 (47只自选股涉及)             │
│ ✅ 存储芯片 (25只自选股涉及)             │
│ ✅ 半导体 (18只自选股涉及)               │
│ ✅ 先进封装 (6只自选股涉及)              │
│ ✅ MLCC (10只自选股涉及)                │
│ ☐ EDA概念 (2只自选股涉及)              │
│ ☐ 光刻机 (1只自选股涉及)               │
├───────────────────────────────────────┤
│ [已选5个概念]       [保存]              │
└───────────────────────────────────────┘
```

**交互说明：**
- 搜索框实时过滤同花顺概念（375个概念）
- 每个概念行显示名称 + 关联的自选股数（可直观看到哪些概念跟自选股相关度高）
- 多选，已选的概念排在前面
- 底部显示已选数量 + 保存按钮

#### 4.4.3 概念波谷页面 — 按方向分组视图

```
📊 概念板块波谷追踪

[全部] [科技] [医药] [新能源] [其他方向]

─────────────────────────────────

📁 科技 (共15个概念, 5个在波谷)

┌─ 半导体（芯片概念/存储芯片/先进封装/MLCC）──────────────┐
│  vl:3 pk:1  BIAS20 -8.2%  量比 0.65   状态 🟢 波谷      │
│  近5日: -3.1%  近20日: -12.5%                           │
│  关联: 中芯国际/北方华创/中微公司/长电科技...             │
└────────────────────────────────────────────────────────┘

┌─ 算力（华为概念/人工智能/东数西算）──────────────────────┐
│  vl:1 pk:2  BIAS20 +3.1%  量比 1.05   状态 🔴 波峰-ish  │
│  近5日: +2.8%  近20日: +8.2%                            │
└────────────────────────────────────────────────────────┘

📁 医药 (共3个概念, 1个在波谷)

┌─ 创新药（创新药/阿尔茨海默概念）────────────────────────┐
│  vl:4 pk:0  BIAS20 -9.5%  量比 0.58   状态 🟢 波谷      │
│  近5日: -4.2%  近20日: -15.1%                           │
└────────────────────────────────────────────────────────┘
```

**交互说明：**
- Tab 行：原有5个阶段Tab保留，新增每个大类作为Tab
- 选中某个大类Tab后，只显示该大类绑定的概念，并按波谷/波中/波峰分组
- 每组显示大类的汇总信息（共N个概念，X个在波谷）
- 每个概念卡片与现有布局一致（vl_score、pk_score、BIAS20、量比、状态）
- 卡片顶部用细分方向名作为标题（带关联的概念名作为副标题）

#### 4.4.4 个股添加/编辑方向（多选Tags）

自选股每张卡片的操作栏中，方向选择器从单选下拉改为多选Tags：

```
┌──────────────────────────────────┐
│  大族激光(002008)                │
│  ┌─[科技·PCB概念 ✕] [科技·机器人 ✕] 科技·光纤概念  ─┐│
│  │  输入添加方向...              ││
│  └────────────────────────────────┘│
│  [趋势交易] [✕ 删除]              │
└──────────────────────────────────┘
```

**交互说明：**
- 已有方向显示为Tags（带✕可删除）
- 点击输入框，弹出所有已启用的细分方向列表（格式：`大类·细分名`）
- 点击选中/取消，新建的Tag显示在列表头部
- 输入框可输入文字过滤候选列表
- 选完后自动保存（或点击空白区域保存）
- 搜索添加个股时，可勾选多个方向

---

## 5. 执行计划

详见：[方向分层 + 概念绑定 — 执行计划](plan.md)

---

## 6. 附录

### 6.1 替代方案

**方案X：自动从概念反推方向**
直接分析自选股涉及的同花顺概念，自动归类到大类。但一票挂N个概念（中芯国际挂8个概念），里面混杂"沪深300""MSCI中国"等噪声，自动归类不可控。**否决。**

### 6.2 开放问题

1. **旧数据迁移：`direction` 字符串 → `directions` 数组。** 已有自选股JSON里 `direction: "半导体"`，迁移时转为 `directions: ["其他.半导体"]`（因为旧方向没有大类归属）。后端读取时若取到`direction`字符串，自动转数组。
2. **前端多选Tags组件** — 用现有React轮子（如react-select/tagsinput）还是手写？建议手写一个简单版，不额外引包。
3. **概念绑定弹窗中，搜索候选列表用同花顺全部375个概念，还是只显示自选股涉及的那165个？** 倾向全部375个，因为用户可能想绑定一个还没在自选股中出现的新概念方向。但搜索时可以优先展示自选股涉及的概念。
4. **大类Tab在概念波谷页面怎么排？** 按用户在大类管理中设置的顺序排列。

### 6.3 文件清单

```
修改：
  server/backend/services/direction_service.py     # 重写：层级CRUD + 概念绑定
  server/backend/api/directions.py                  # 大改：新增层级API端点
  server/backend/api/concept_wave.py                # 中改：新增group_by=direction
  server/frontend/src/pages/Watchlist.tsx           # 大改：方向面板两层树+概念绑定弹窗
  server/frontend/src/pages/ConceptWaveTracking.tsx # 中改：新增方向分组视图
  server/frontend/src/pages/Watchlist.css           # 小改：新UI样式

新增：
  server/frontend/src/components/ConceptBindingModal.tsx  # 概念绑定弹窗组件

无需改动（仅加一层 parse_direction 解析的函数调用，并兼容 direction→directions）：
  server/backend/services/review_service.py        # directions[0]或方向列表遍历
  server/backend/core/scan_buy_signals.py          # 遍历 directions 数组判断活跃
  server/backend/services/holdings_service.py      # directions 数组读写
  server/backend/services/review_compute_service.py # directions 数组读取
  server/backend/core/review_analysis.py           # directions 字段名兼容
  server/backend/core/data_layer.py                # get_watchlist_by_direction 遍历数组
  server/backend/core/trend_candidates.py          # directions 字段名兼容
  server/frontend/src/pages/Holdings.tsx           # 遍历 directions 数组分组
  server/frontend/src/pages/Review.tsx             # 遍历 directions 数组分组
```

### 6.4 变更日志

| 版本 | 日期 | 变更内容 |
|:----|:----|:--------|
| v1 | 2026-06-04 | 初稿 |

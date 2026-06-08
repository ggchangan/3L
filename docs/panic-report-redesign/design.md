# 恐慌报告PDF — 从 get_panic_monitor() 统一输出 + 宏观页下载 设计 v2

## 0. 前端原型总览

宏观环境监控页已有完整的恐慌监测区块（触发原因、三种路径、市场环境、主线方向、底部突起新板块、个股分析），
需要在恐慌区块底部加一个"📥 下载恐慌应对报告（PDF）"按钮。

点击按钮 → 后端调用 get_panic_monitor() 生成PDF → 浏览器自动下载。

## 1. 背景与问题

**现状：**
- `get_panic_monitor()` 已返回完整数据（恐慌等级/策略/主线/底部突起/个股分析/历史）
- macro 页面已展示该数据的全部内容（触发原因、路径、市场环境、主线、底部突起、持仓分析、历史）
- PDF报告目前是手动写的 `generate_panic_report.py`，没走 `get_panic_monitor()`

**断层：**
1. PDF数据源不一致 — 手动写的 PDF 跟页面展示的不一样
2. PDF缺失 emerging_sectors（6/5电机/减速器等新板块）、holdings_analysis（个股卡片）、mainline_sectors（主线）
3. 页面没有"下载报告"入口，用户只能看不能导出

**数据源说明：**
- 行业板块今日数据 → **同花顺 THS**（`ak.stock_board_industry_summary_ths()`，90个行业）
- 概念板块今日数据 → **同花顺 THS**（`ak.stock_board_concept_info_ths()`）
- 存在 `sector_daily.json` 的 `_push2test` 字段（字段名是历史遗留，数据已是同花顺）
- 旧版 `industries`/`concepts` 字段（akshare旧格式带每日K线）已不准确，`_get_rising_from_bottom()` 读的是旧字段，导致底部突起方向数据为空

**目标：**
1. 统一数据源：PDF 从 `get_panic_monitor()` 生成，跟宏观页展示的数据一致
2. 页面加下载按钮：用户点击即可下载当前恐慌应对报告的PDF
3. 修复 `_get_rising_from_bottom()`：从旧K线格式改为读 `_push2test`（同花顺今日数据）

## 2. 设计思想

### 2.1 核心理念

**同一份数据，三种输出形式：**
```
get_panic_monitor()
    ├─→ macro_service → JSON → 宏观页面展示
    ├─→ check_alerts → 实时推送文本
    └─→ panic_report_service → PDF → 页面下载
```
三种输出形式共享同一个数据入口，保证信息一致性。

### 2.2 方案选择

| 候选方案 | 优点 | 缺点 | 结论 |
|:--------|:----|:----|:----:|
| 手动写PDF | 灵活 | 数据源不一致，易遗漏 | ❌ |
| Python脚本离线生成 | 可自动化 | 不能在页面下载 | ❌ |
| **后端API + 页面按钮** | **统一数据源+页面入口** | 需要新增一个API端点 | ✅ |

### 2.3 屏幕内外

- **做什么：**
  - 重写 `scripts/generate_panic_report.py` 调用 `get_panic_monitor()`
  - 新增 `POST /api/panic-report-pdf` 端点
  - 宏观页恐慌区块加"📥 下载PDF"按钮
  - 修复 `_get_rising_from_bottom()`：从旧K线格式改为读 `_push2test`（同花顺今日数据）+ 同时查 industries 和 concepts
  - PDF内容 = 恐慌等级 + 市场环境 + 主线方向 + 底部突起新板块（含减速器/电机等） + 三种路径 + 整体策略 + 个股分析
- **不做什么：**
  - ❌ 不改 `get_panic_monitor()` 的返回结构
  - ❌ 不改 macro_service 或 check_alerts
  - ❌ PDF不取代页面展示，只是导出

## 3. 数据模型

### 3.1 底部突起方向检测（修复版）

**现状：** `_get_rising_from_bottom()` 读旧 `concepts` K线格式，缺少22条记录的新概念（如减速器）被跳过，且不查 industries（电机在行业）。

**修复方案：** 改为读 `_push2test`（同花顺今日数据）：

```python
def _get_rising_from_bottom_v2():
    """从_push2test中找底部突起方向
    逻辑：当日涨>1.5% → 今日突然走强
    
    v2改动：
    - 数据源从旧K线格式改为_push2test（同花顺今日数据）
    - 同时检查 concepts + industries
    - 不需要22条K线历史，直接用当日涨跌幅判断
    """
```

注意：push2test（同花顺数据）只有今日单日数据，没有20日历史。所以判断维度从"1日涨幅>1.5% 且 20日涨幅<3%"简化为"1日涨幅>1.5%"。如果后续需要20日维度，需另建历史库。

### 3.2 PDF内容结构

```
恐慌应对报告PDF
├── 标题 + 时间
├── 恐慌等级（level/warning/caution + triggers）
├── 市场环境（structure/stage/position_advice/bias20）
├── 主线方向（mainline_sectors 彩色标签）
├── 底部突起新板块（emerging_sectors 表格）
│   └── (如：电机、减速器、煤炭概念等近日突然走强)
├── 三种路径（paths 卡片式）
├── 核心原则（overall_summary）
└── 个股分析（holdings_analysis 逐只）
    └── 代码/名称/现价/涨跌/结构/阶段/止损/建议
```

### 3.3 数据流

```
用户点击"下载PDF"按钮
    ↓
POST /api/panic-report-pdf (前端fetch)
    ↓
panic_report_service.generate_panic_report_pdf()
    ├─→ get_panic_monitor()  ← 统一数据源（含已修复的_v2底部突起检测）
    └─→ get_sector_daily()   ← 补充概念汇总表（从_push2test读）
    ↓
format_markdown() → pandoc + wkhtmltopdf → panic_report_20260607.pdf
    ↓
返回 { download_url: '/download/panic_report_20260607.pdf' }
    ↓
前端 window.open(download_url) → 浏览器下载
```

## 4. 系统设计

### 4.1 API设计

**`POST /api/panic-report-pdf`**

请求：无参数

响应：
```json
{
  "filename": "panic_report_20260607.pdf",
  "download_url": "/download/panic_report_20260607.pdf",
  "size_kb": 147.8
}
```

### 4.2 新增/修改文件

| 文件 | 用途 |
|:----|:-----|
| `scripts/generate_panic_report.py` | 重写，调用 get_panic_monitor() 生成报告MD |
| `server/backend/services/panic_report_service.py` | **新增** PDF生成服务 |
| `server/backend/services/panic_monitor_service.py` | 修改 `_get_rising_from_bottom()` → v2（读_push2test，含 industries+concepts） |
| `server/backend/api/macro.py` | 新增 `_handle_panic_report_pdf()` 路由处理 |
| `server/server.py` | POST路由表新增 `/api/panic-report-pdf` |
| `server/frontend/src/pages/Macro.tsx` | 恐慌区块底部加下载按钮 |
| `server/frontend/src/pages/Macro.css` | 下载按钮样式 |

### 4.3 前端设计

**按钮位置：** 恐慌区块底部，历史记录之后

```
┌──────────────────────────────────┐
│ ...个股分析...                    │
│ ...历史记录...                    │
│                                  │
│       [📥 下载恐慌应对报告（PDF）]  │
└──────────────────────────────────┘
```

点击 → 调API → 下载PDF

## 5. 执行计划

| # | 任务 | 文件 | 预估 | 状态 |
|:-:|:----|:----|:----:|:----:|
| 1 | 测试先行：写 `_get_rising_from_bottom_v2` 单元测试 | `test_panic_monitor.py` | 10m | ⏳ |
| 2 | 修复 `_get_rising_from_bottom()` v2: 读_push2test + 查industries+concepts | `panic_monitor_service.py` | 10m | ⏳ |
| 3 | 运行测试验证底部突起方向（电机/减速器应出现） | `pytest test_panic_monitor.py` | 3m | ⏳ |
| 4 | 创建 `panic_report_service.py` PDF生成服务 | `panic_report_service.py` | 15m | ⏳ |
| 5 | 修改 `macro.py` + `server.py` 添加API路由 | `macro.py`, `server.py` | 5m | ⏳ |
| 6 | 重写 `generate_panic_report.py` 调用 `get_panic_monitor()` | `generate_panic_report.py` | 10m | ⏳ |
| 7 | 前端：Macro.tsx加下载按钮 + Macro.css样式 | `Macro.tsx`, `Macro.css` | 8m | ⏳ |
| 8 | 前端构建 + 重启服务 + 全量验证 | — | 5m | ⏳ |
| 9 | 检查修复：底部突起方向显示（减速器/电机） + PDF下载 | 页面检查 | 5m | ⏳ |
| 10 | 提交推送 + PR | — | 3m | ⏳ |

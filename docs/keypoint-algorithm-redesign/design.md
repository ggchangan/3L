# 3L 关键点与买卖点算法重设计

## 背景

复盘页出现过「区间顶部 / 放量下跌 / 减仓」同时又显示「中继买点」的冲突。
典型样本是圣邦股份 `300661` 在 `2026-08-18`：

- `2026-08-17` 成交量 `148,669`
- `2026-08-18` 成交量 `227,188`，较前一日放大约 `1.53` 倍
- 当日跌幅约 `-5.13%`
- 结构判定为 `区间震荡`
- 阶段判定为 `区间顶部`
- 技术融合却保留了 `中继买点`

这说明问题不只在展示层，也不只是给中继检测器补一条门禁；更上游的
「关键点 → 量价行为 → 买卖点」算法边界需要重新设计。

本文档先约束算法定义，不直接改实现。

## 原文定义摘录与理解边界

### 1. 关键点包括三类特征

《量价原理》5.5 关键点(1) 说明，关键点具备如下特征：

1. 图表上容易观察到的位置，例如前高、前低；
2. 不寻常的量价行为，例如成交量明显放大或萎缩、长阳线、长阴线、十字星；
3. 供需格局转换时出现的突破点、转折点、中继点。

工程理解：

- 「前高、前低、天量/地量 K 线高低点」是明显参考点，提供锚定位置。
- 「放量、缩量、长阳、长阴、十字星」是量价行为证据。
- 「突破点、反转点、中继点」是供需格局改变或延续的位置。
- 三者同属关键点体系，但不是简单父子关系。

需要避免的错误理解：

- 不能说供需转换点必须由锚定点派生；
- 也不能把锚定点直接当买卖点；
- 更不能把单独的技术信号直接写成买点。

### 2. 明显参考点

原文强调，明显参考点包括：

- 前高；
- 前低；
- 天量 K 线的高点/低点；
- 地量 K 线的高点/低点。

这些点之所以有效，是因为有限注意力和锚定效应。股价运行到前高、前低、
天量/地量成本聚集区附近时，市场参与者更容易形成支撑、压力、停顿或方向
选择。

工程定义：

```text
reference_keypoint =
  prior_high |
  prior_low |
  climax_volume_high |
  climax_volume_low |
  dry_volume_high |
  dry_volume_low
```

明显参考点只回答：

```text
当前价格是否到了容易发生供需博弈的位置？
```

它不直接回答：

```text
应该买还是卖？
```

### 3. 供需格局点

《量价原理》5.5 关键点(2) 说明：

- 原有供需格局被打破的位置，就是关键点；
- 供需格局被打破的位置，会出现突破点、反转点、中继点；
- 突破点是趋势形成点；
- 中继点是趋势延续点；
- 反转点是趋势逆转点。

工程定义：

```text
supply_demand_keypoint =
  breakout_point |
  breakdown_point |
  reversal_point |
  continuation_point
```

其中：

- `breakout_point`：区间或压力被需求放量突破，供需平衡转向供不应求；
- `breakdown_point`：区间或支撑被供应放量跌破，供需平衡转向供过于求；
- `reversal_point`：原趋势被反向力量改变，常伴随放量反包、长影线、吞没线；
- `continuation_point`：无法改变原有趋势的量价行为出现的位置。

### 4. 上涨中继点与中继买点

原文对上涨中继的核心定义：

```text
发生位置：上涨趋势中。
量价行为：缩量回踩。
供需含义：卖方意愿不强，不破坏原有上升趋势的构成条件。
交易含义：上升趋势中的低风险补偿性买点。
```

所以工程上必须严格区分：

```text
上涨中继点 ≠ 均线多头 + 距离高点回撤
上涨中继点 = 上涨趋势中，回踩行为不足以破坏原供不应求格局
```

上涨中继买点必须同时满足：

1. 大结构是上涨趋势；
2. 当前处于趋势内回踩，而不是区间顶部压力、加速末端或放量转弱；
3. 回踩阶段缩量，且缩量应能体现供应不足；
4. 回踩没有破坏趋势关键支撑，例如趋势线、EMA10/EMA20、前突破位或最近有效支撑；
5. 当日量价行为不能显示供应显著进入。

## 现有程序偏差

### 1. 关键点识别不统一

当前至少存在三套相关逻辑：

- `server/backend/services/stock_chart_service.py`
  - `_find_breakthrough_points()`：用于关键点图；
  - 标记前高、前低、突、反、放量、缩量；
- `core/threel_core/buy_point_detection.py`
  - `_find_support_levels()`、`_find_resistance_levels()`：买点检测内部自行找支撑阻力；
  - `detect_buy_point()`：自己根据结构、阶段、量比判断买点；
- `core/threel_core/ema_utils.py`
  - `get_structure()`、`get_stage()`：股票卡片和买点算法共用结构/阶段。

问题：

```text
图上关键点、买点检测关键点、股票卡片结构阶段不是同一个算法源头。
```

结果就是：图表、后端字段、复盘展示可能同时给出互相矛盾的解释。

### 2. 中继检测把「技术形态」误当「关键点」

`server/backend/core/signal_detector/upward_continuation.py` 当前更像一个技术评分器：

- 检查趋势；
- 计算近期高点到当前的回撤；
- 计算最近 5 日均量 / 前一段上涨期均量；
- 检查 EMA10/EMA20；
- 给出置信度。

这没有先回答：

```text
今天是否形成 3L 意义上的中继点？
```

而是先回答：

```text
形态像不像上涨趋势中的回踩？
```

这会导致圣邦股份这类样本误触发：当天相对昨日是放量下跌，但最近 5 日均量
接近前段均量，于是算法仍给出 `量0.98倍` 的中继信号。

### 3. 成交量口径不符合“当天量价行为”的展示语义

圣邦股份 `2026-08-18`：

```text
昨日量：148,669
今日量：227,188
今日/昨日：1.53
```

但检测器展示：

```text
量0.98倍
```

原因是它实际计算的是：

```text
最近5日均量 / 前上涨段均量
```

这个指标可以作为背景，但不能替代当日量价行为。3L 的关键点判断必须关注
关键位置当天或当段的量价结果。

### 4. 买点字段被被拒绝的技术信号污染

`stock_card_service.py` 中存在逻辑：

```python
if technical_signal == 'buy' and detected_buy_point and not buy_point:
    buy_point = detected_buy_point
```

即使融合结果是 `keypoint_rejected_bullish`，`buy_point` 仍可能被填入。

这违背字段契约：

```text
buy_point 应该只表示通过关键点语义后的有效买点；
被关键点拒绝的技术信号只能留在 technical_signal / triggered_signals。
```

## 目标算法流程

### 总流程

```text
输入 K 线
  ↓
1. 识别结构：上涨趋势 / 区间震荡 / 下降趋势
  ↓
2. 识别关键点体系
   2.1 明显参考点：前高 / 前低 / 天量高低点 / 地量高低点
   2.2 当前价格与参考点关系：接近支撑 / 接近压力 / 脱离关键区
   2.3 供需格局点：突破 / 跌破 / 反转 / 中继 / 无供需点
  ↓
3. 识别当前关键位置/走势中的量价行为
   放量上涨 / 放量下跌 / 缩量回踩 / 缩量反弹 / 放量滞涨 / 天量滞跌
  ↓
4. 生成买卖点候选
   突破买点 / 中继买点 / 反转买点 / 恐慌买点 / 卖点 / 无有效买卖点
  ↓
5. 复盘层叠加大盘、行业主线、个股方向、止损，决定是否可执行
```

### 关键点输出契约

新增统一结构：

```json
{
  "structure": "上涨趋势",
  "stage": "缩量整理",
  "reference_points": [
    {
      "type": "prior_high",
      "date": "20260814",
      "price": 123.8,
      "role": "resistance",
      "distance_pct": -5.56
    }
  ],
  "current_zone": {
    "type": "near_resistance | near_support | mid_range | trend_pullback | extended",
    "anchor_type": "prior_high",
    "anchor_price": 123.8,
    "distance_pct": -5.56
  },
  "volume_price_action": {
    "type": "volume_down",
    "day_volume_ratio": 1.53,
    "ma5_volume_ratio": 1.24,
    "price_change_pct": -5.13
  },
  "supply_demand_keypoint": {
    "type": "continuation | breakout | breakdown | reversal | failed_breakout | none",
    "direction": "bullish | bearish | neutral",
    "confidence": 0,
    "reason": "区间顶部放量下跌，供应进入，不构成上涨中继"
  }
}
```

### 买卖点输出契约

买卖点只能消费统一关键点结果：

```json
{
  "trade_signal": "buy | sell | hold",
  "buy_point": "",
  "sell_point": "区间顶部受阻",
  "technical_signal": "rejected_bullish_continuation",
  "reason": "上涨中继要求上涨趋势中的缩量回踩；当前为区间顶部放量下跌"
}
```

规则：

- `buy_point` 只允许保存有效买点；
- 被拒绝的看多技术事实只能进入 `technical_signal` / `rejected_signals`；
- `triggered_signals` 必须标明 `keypoint_allowed=false` 时，不得反向污染 `buy_point`；
- 前端展示买点时只读取 `buy_point`，展示“疑似/被拒绝信号”时读取 `rejected_signals`。

## 上涨中继点伪算法

```python
def detect_bullish_continuation_keypoint(klines, idx, context):
    if context.structure != '上涨趋势':
        return rejected('上涨中继只发生在上涨趋势中')

    if context.stage in ('加速', '滞涨', '转弱'):
        return rejected('加速/滞涨/转弱不是中继点')

    if context.current_zone.type not in ('trend_pullback', 'near_support'):
        return rejected('当前不在趋势回踩或关键支撑附近')

    vpa = context.volume_price_action
    if vpa.type not in ('shrink_pullback', 'narrow_shrink'):
        return rejected('上涨中继要求缩量回踩，当前量价行为不匹配')

    if context.trend_support_broken:
        return rejected('回踩已破坏原上涨趋势')

    return confirmed(
        type='continuation',
        direction='bullish',
        reason='上涨趋势中缩量回踩，供应不足，原供不应求格局未被破坏',
    )
```

这里的重点是：

```text
不是给“像回踩”的形态打高分，而是先证明“这里是中继点”。
```

## 圣邦股份样本应输出

`300661` 在 `2026-08-18` 应输出：

```json
{
  "structure": "区间震荡",
  "stage": "区间顶部",
  "current_zone": {
    "type": "near_resistance",
    "anchor_type": "prior_high",
    "anchor_price": 123.8
  },
  "volume_price_action": {
    "type": "volume_down",
    "day_volume_ratio": 1.53,
    "price_change_pct": -5.13
  },
  "supply_demand_keypoint": {
    "type": "failed_breakout",
    "direction": "bearish",
    "reason": "区间顶部附近放量下跌，供应进入，突破失败倾向"
  },
  "trade_signal": "sell",
  "buy_point": "",
  "sell_point": "区间顶部受阻"
}
```

## 改造步骤

### P0：统一关键点上下文，不改交易策略参数

1. 新增 `backend/core/keypoint_detection.py` 或迁移到 `threel_core`：
   - `detect_reference_keypoints()`
   - `detect_volume_price_action()`
   - `detect_supply_demand_keypoint()`
   - `build_keypoint_context()`
2. 股票卡片、复盘信号、关键点图共用同一个 `keypoint_context`。
3. 修复 `buy_point` 字段污染：
   - `keypoint_rejected_bullish` 不能写入 `buy_point`。

#### P0 实现决策

P0 不直接重写全部买卖点检测器，原因是当前系统里结构、阶段、技术信号、
复盘缓存和前端展示已经有较多调用链。如果一次性重写，容易把“定义问题”
和“工程迁移问题”混在一起，回归时难以定位。

本阶段采用如下策略：

```text
保留现有结构/阶段判断
  ↓
新增统一 keypoint_context
  ↓
股票卡片先输出统一上下文
  ↓
禁止被关键点拒绝的看多技术信号污染正式 buy_point
  ↓
后续上涨中继、突破、反转、恐慌买点逐个迁移到 keypoint_context
```

具体复用与重写边界：

- 复用 `get_structure()` / `get_stage()`：P0 先沿用现有结构、阶段口径；
- 新增 `backend/core/keypoint_context.py`：统一输出明显参考点、当前关键区域、
  当日量价行为、供需格局点；
- 不复用各检测器内部私有的支撑/压力口径作为统一来源；
- 不在 P0 重写 `upward_continuation.py`，但先阻止它在被融合层拒绝后继续写入
  正式 `buy_point`；
- `buy_point` 字段只表达“通过关键点语义后的有效买点”，疑似或被拒绝信号
  只能留在 `technical_signal` / `triggered_signals` / `fusion_reason`。

P0 的回归验收样本：

- 圣邦股份 `300661` / `2026-08-18`：
  - 区间震荡；
  - 区间顶部；
  - 今日/昨日成交量约 `1.53`；
  - 放量下跌；
  - 供需格局点应为 `failed_breakout`；
  - 不允许输出正式 `中继买点`。
- 人工上涨趋势缩量回踩样本：
  - 上涨趋势；
  - 回踩 EMA/支撑附近；
  - 今日相对昨日和 5 日均量同步缩量；
  - 可识别为 `continuation`。

### P0.1：纯关键点识别器

这一阶段只做“图上哪些点本身值得标记”，不做买点、不做卖点、不解释位置含义。

#### 原文依据

3L 原文里，前高、前低、天量 K 线高低点、地量 K 线高低点属于容易被参与者
观察和锚定的明显参考点。它们提供支撑/压力/成本聚集参考，但不直接等于
突破、反转、中继或恐慌。

因此 P0.1 的输出只包含：

```text
price_high       局部前高
price_low        局部前低
volume_peak      局部量峰
volume_trough    局部量谷
```

每个点都必须带确认状态：

```text
confirmed  右侧 K 线数量足够，已经确认
candidate  最新右侧 K 线不足，只能称为候选点
```

#### 旧实现审计与取舍

现有代码里有可借鉴部分，也有必须拆分的部分。

可借鉴：

- `stock_chart_service._find_breakthrough_points()` 中前高/前低使用“左右各 5 根”
  的局部波峰/波谷思想，符合明显参考点的基本定义；
- `buy_point_detection._find_resistance_levels()` 使用局部波峰找阻力，方向正确；
- `buy_point_detection._is_extreme_shrink()` 使用分位数识别地量，比简单均量倍数
  更接近“相对异常量”；
- `range-oscillation-support-resistance/design.md` 中对区间支撑/压力做过回测，
  可作为后续“关键点到位置含义”的验证参考。

需要重写或拆分：

- `_find_breakthrough_points()` 在末尾 5 根 K 线缺少右侧确认时，仍会退化成
  后向窗口并标为“前高/前低”，这会把最新高点误当成确认关键点；
- 旧图表函数同时输出前高/前低、放量/缩量、突破/反转，静态锚点和供需转换点
  混在一起，不利于回归；
- 旧量能标注是“放↑/放↓/缩”的行为标签，不是“局部量峰/局部量谷”；
- 买点检测器内部各自计算支撑、压力、缩量和突破，导致图表、卡片和复盘可能
  使用不同关键点来源；
- 中继/突破买点中存在技术评分逻辑，不能直接当作 3L 关键点识别器。

结论：

```text
局部极值思想保留；
分位数思想保留；
末端确认逻辑、量峰量谷识别、输出契约需要重写；
供需转换点必须从纯关键点识别器之上另起一层，不能混在 P0.1。
```

#### 三类对象参数

定义保持一致，参数按对象类型微调：

| 对象 | 示例 | 价格窗口 | 量能窗口 | 量峰强度 | 量谷强度 |
|---|---|---:|---:|---|---|
| 大盘 market | 科创50、中证全指 | 左右 5 根 | 左右 5 根 | MA20×1.25 或 60日分位≥85% | MA20×0.75 或 60日分位≤20% |
| 板块 sector | CPO、元件、存储 | 左右 4 根 | 左右 4 根 | MA20×1.35 或 60日分位≥85% | MA20×0.70 或 60日分位≤18% |
| 个股 stock | 中国巨石、太辰光、普冉股份 | 左右 3 根 | 左右 3 根 | MA20×1.50 或 60日分位≥90% | MA20×0.65 或 60日分位≤15% |

这里的差异来自工程经验假设：

- 大盘噪音相对少，关键点应该更稳、更少；
- 板块轮动更快，需要略敏感；
- 个股噪音最大，价格窗口可以更短，但量能异常强度必须更高。

这些参数必须通过样本图和回归样本继续校准，不能视为最终值。

#### P0.1 输出契约

```json
{
  "version": "pure-keypoint-v1",
  "asset_type": "market",
  "date": "20260818",
  "profile": {
    "price_left": 5,
    "price_right": 5,
    "volume_left": 5,
    "volume_right": 5
  },
  "points": [
    {
      "idx": 30,
      "date": "20260701",
      "type": "price_high",
      "label": "局部前高",
      "status": "confirmed",
      "role": "resistance",
      "price": 2255.25
    },
    {
      "idx": 64,
      "date": "20260818",
      "type": "price_high",
      "label": "候选前高",
      "status": "candidate",
      "role": "resistance",
      "price": 1798.78
    },
    {
      "idx": 21,
      "date": "20260618",
      "type": "volume_peak",
      "label": "局部量峰",
      "status": "confirmed",
      "volume": 21000000,
      "metrics": {
        "volume_ma_ratio": 1.42,
        "volume_percentile": 88.0
      }
    }
  ]
}
```

#### 回归策略

三类对象都要有回归样本：

```text
market_keypoint_cases.json   科创50、中证全指
sector_keypoint_cases.json   CPO、元件、存储
stock_keypoint_cases.json    中国巨石、太辰光、普冉股份
```

第一批不追求完整标注全市场，只固化人眼讨论后确认的 `must_include` 和
`must_exclude`：

```json
{
  "target": "科创50",
  "asset_type": "market",
  "date_range": ["20260519", "20260818"],
  "must_include": [
    {"date": "20260701", "type": "price_high"},
    {"date": "20260803", "type": "price_low"}
  ],
  "must_exclude": [
    {"date": "20260818", "type": "price_high", "status": "confirmed"}
  ]
}
```

验收指标：

```text
召回：人眼确认的重要点是否被识别；
误报：算法标出来但明显没有意义的点是否过多；
状态：confirmed / candidate 是否区分正确；
稳定性：大盘、板块、个股是否需要不同参数。
```

#### 第一版人工确认基准集

2026-08-20 已将第一批人工校准图固化为回归基准：

```text
fixture: server/backend/tests/fixtures/pure_keypoint_benchmark_v1.json
test:    server/backend/tests/test_pure_keypoint_detector.py::test_user_confirmed_pure_keypoint_benchmark_v1
```

样本范围：

| 类型 | 样本 | 用途 |
|---|---|---|
| 大盘 | 科创50、中证全指 | 验证指数级前高/前低/量峰/量谷的稳健性 |
| 板块 | CPO、元件、存储 | 验证板块轮动更快时的关键点敏感度 |
| 个股 | 中国巨石、太辰光、普冉股份 | 验证个股噪音更高时的关键点过滤 |

该基准只锁定 P0.1 的“纯关键点”：

- 日期；
- 类型：`price_high / price_low / volume_peak / volume_trough`；
- 状态：`confirmed / candidate`；
- 对应价格或成交量。

它不锁定成交量分位数、均量比等解释性指标，避免小数级辅助指标变化导致
无意义的测试失败。后续如果人工确认新增样本，应追加到同一 fixture 或新
建 v2 fixture，并在文档中记录确认日期和样本来源。

#### 形成中关键点状态机

当天复盘最重要的是“正在形成的关键点”。这类点不能因为右侧确认不足而被
忽略，也不能被当成已确认历史锚点。

状态定义：

```text
candidate    形成中，右侧 K 线不足；
confirmed    右侧窗口完整，仍保持局部极值；
superseded   后续出现更极端高点/低点/量峰/量谷，候选点自然顺延；
invalidated  后续走势使该候选点失去关键点意义。
```

P0.1 只落地 `candidate / confirmed` 两种状态：

```text
右侧窗口完整 → confirmed
右侧窗口不足 → candidate
```

`superseded / invalidated` 需要跨日状态追踪，不在纯函数里持久化。但纯函数
必须天然支持“顺延”：

```text
T 日出现候选量峰；
T+1 继续更大成交量；
再次滚动计算时，T 日不能升级为 confirmed，T+1 成为新的 candidate。
```

这保证当天复盘可以看到关键变化，同时避免把形成中的点误当成历史确认点。

#### 人工验证图

新增脚本：

```bash
PYTHONPATH=server:core python server/scripts/render_pure_keypoint_validation.py
```

本地没有 MySQL 或真实行情库不可达时，使用离线 fixture 回归模式：

```bash
PYTHONPATH=server:core python server/scripts/render_pure_keypoint_validation.py --fixture
```

默认生成 8 个标的的总览图：

```text
大盘：科创50、中证全指
板块：CPO、元件、存储
个股：中国巨石、太辰光、普冉股份
```

图上只展示：

```text
前高、前低、局部量峰、局部量谷；
半透明标记表示 candidate，实心/高亮标记表示 confirmed。
```

### P1：重写上涨中继算法

1. 上涨中继只消费 `keypoint_context`；
2. 要求结构为上涨趋势；
3. 要求当前区域为趋势回踩或关键支撑；
4. 要求量价行为为缩量回踩或窄幅缩量；
5. 要求趋势支撑未破；
6. 输出中必须解释：
   - 回踩到哪个关键点/支撑；
   - 当日量能相对昨日和均量的变化；
   - 为什么供应不足；
   - 为什么原上涨趋势没有被破坏。

### P2：回归样本库

建立人工可审查样本，而不是只看准确率：

- 圣邦股份 `2026-08-18`：区顶放量下跌，不是中继买点；
- 选择 5～10 个明确上涨趋势缩量回踩样本：应识别为中继点；
- 选择 5～10 个区间顶部放量受阻样本：应识别为卖点/压力；
- 选择 5～10 个区间底部缩量/滞跌样本：应识别为支撑/反转候选；
- 选择 5～10 个下降趋势缩量阴跌样本：不得识别为买点。

### P3：前端展示同步

前端展示分三行：

```text
关键点：区间顶部压力 / 前高附近 / 突破失败
量价行为：放量下跌，今日量/昨日量 1.53
买卖点：无有效买点；减仓/观察压力
```

不要再把 `technical_signal` 直接展示为 `buy_point`。

## 开放问题

1. 趋势线支撑是否先用 EMA10/EMA20 + 前突破位近似，还是要做真正趋势线？
2. 天量/地量 K 线高低点的回看周期先用 60 日、120 日还是动态窗口？
3. 中继点是否允许发生在“区间震荡中的上涨中继平台”？原文提到区间震荡也有中继信号，但和“上涨趋势中的中继买点”需要区分。
4. 强势市场中不容易回踩时，是否允许“突破后窄幅整理”作为中继点？如果允许，需要单独定义，不应和缩量回踩混用。

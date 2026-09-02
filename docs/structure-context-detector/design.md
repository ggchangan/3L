# 3L 结构上下文识别器设计

> 状态：P0 设计文档，先不接生产。
> 目标：在关键点、波段、供需事件都已有旁路实现后，补上最关键的一层：
> **用 3L 原文口径统一判断结构、阶段、波段位置和主跌风险**，为后续买卖点重构提供稳定前置上下文。

## 1. 背景

最近几轮重构已经拆出了几层旁路能力：

```text
P0.1 纯关键点
  前高 / 前低 / 局部量峰 / 局部量谷

P0.2 供需关键点
  突破 / 跌破 / 突破失败 / 跌破失败 / 中继 / 反转 / 恐慌 / 高潮

P0.3 多日供需转换区
  下降→上升、上升→下降的候选转换窗口

P0.4 结构化供需事件
  把 P0.2 点规范成 SupplyDemandEvent，并保持 is_trade_decision=false

P0.5 结构/阶段/位置口径统一
  修复“区间中段但接近支撑/压力”的自相矛盾
```

这些层解决了很多局部混乱，但仍缺一个统一的上游问题：

```text
当前到底处于什么 3L 结构？
当前是在这个结构里的什么阶段？
当前交易波段是上涨、下降、反弹、回调还是横向？
这里是波谷左侧、波谷确认、波中、波峰左侧，还是主跌发展段？
```

如果这一层不稳定，后续就会反复出现：

- 区间顶部被展示成中继买点；
- 下降趋势缩量被误读成低吸；
- 主跌段反弹被误读成反转；
- 恐慌/高潮没有绑定结构位置；
- 买卖点文案和 K 线图、个股卡片、复盘页互相打架。

所以本阶段要先设计一个独立旁路：

```text
detect_3l_structure_context()
```

它不直接输出买卖点，只输出 3L 结构上下文。

## 2. 3L 原文依据

### 2.1 趋势是第一把尺子

知识库依据：

- `training_camp/01_如何识别趋势.md`
- `trading_system/大盘定性.md`
- `trading_system/走势结构与阶段.md`

核心定义：

```text
上升趋势：高点越来越高，低点也越来越高。
下降趋势：高点越来越低，低点也越来越低。
区间震荡：供需相对均衡，等待方向选择。
```

工程含义：

- 趋势不应只靠 EMA 斜率确认；
- EMA 可以辅助，但不能替代“高低点序列”；
- 趋势必须保留级别概念：一个大结构里可以有多个小波段。

### 2.2 看盘顺序必须固定

知识库依据：

- `trading_system/走势结构与阶段.md`
- `training_camp/14_强弱结构判断及买卖点匹配.md`
- `trading_system/四种买点.md`

3L 顺序：

```text
先看市场强弱
  ↓
再看走势结构
  ↓
再看结构阶段
  ↓
最后看量价行为 / 买卖点
```

工程边界：

- 结构层不是买卖点；
- 阶段层不是买卖点；
- 供需事件也不是买卖点；
- 买卖点必须由市场环境、主线/方向、板块环境、个股结构、供需事件共同派生。

### 2.3 波段是最终交易视角

知识库依据：

- `training_camp/11_波段盈利框架及波段峰谷特征.md`
- `training_camp/13_波段交易程序及要点.md`
- `training_camp/18_仓位控制.md`

核心定义：

```text
波谷：下降段的结束，同时也是上升段的起始。
波峰：上升段的结束，同时也是下降段的起始。
波中：波谷和波峰之间的中间段。
```

交易含义：

```text
波谷重仓，波峰控仓。
上升趋势的波段容错率最高。
区间震荡的波段次之。
下降趋势的波段容错率最低，除非恐慌或清晰反转。
```

工程含义：

- 结构识别器必须输出当前交易波段；
- 不能只输出 `上涨趋势 / 区间震荡 / 下降趋势` 三个粗标签；
- 必须区分：
  - 上涨趋势中的下降波段/回调；
  - 下降趋势中的上涨波段/反弹；
  - 区间震荡中的上行/下行摆动；
  - 主跌风险中的弱反弹。

### 2.4 主跌风险是大盘/仓位的核心

知识库依据：

- `training_camp/18_仓位控制.md`
- `trading_system/大盘定性.md`
- `training_camp/07_不同市场背景下的策略选择.md`

核心定义：

```text
仓位控制的核心不是躲掉所有调整，而是尽量回避主跌段。
只要大盘不处于主跌段，就不要被大盘小波动影响，
而应专注自己的方向和个股买卖点。
```

主跌段高发位置：

1. 明显加速后；
2. 一波清晰上升段后的需求不足、放量滞涨、缩量滞涨或供应涌现；
3. 下降趋势的形成/发展段，恐慌后除外。

工程含义：

- `market_environment` 不能只显示强势/弱势；
- 必须同级显示 `major_decline_risk`；
- 主跌风险不等于普通下跌，也不等于一天大跌；
- 恐慌后反而可能从“主跌风险”转为“供应衰竭候选”。

### 2.5 相同量价行为在不同结构中含义不同

知识库依据：

- `liangjia_yuanli/量价原理_提取摘要.md`
- `training_camp/14_强弱结构判断及买卖点匹配.md`

关键规则：

```text
上涨趋势中的价跌量缩：供应萎缩，可能是中继。
下降趋势中的价跌量缩：需求不足，不是抄底理由。

下降趋势末端的天量滞跌：供应快速释放，可能是恐慌/供应衰竭。
上涨趋势高位的放量长阴：需求占优格局被破坏，不是恐慌低吸。

区间顶部无法突破：卖点/风险。
区间底部无法跌破：买点候选/支撑。
区间中部：胜负未明，不宜强行解释。
```

这要求结构上下文必须在供需事件之前稳定输出。

## 3. 设计目标

### 3.1 输出统一上下文，不输出交易动作

`detect_3l_structure_context()` 只回答：

```text
现在处于什么结构？
当前波段是什么？
处于波谷/波中/波峰/主跌风险的哪个位置？
这些判断的证据是什么？
哪些判断还只是候选？
```

不回答：

```text
是否买入？
是否卖出？
买多少？
止损在哪里？
```

### 3.2 同时服务大盘、板块、个股

同一套输出契约适用于：

- 大盘：科创50、中证全指等；
- 板块：CPO、元件、存储等；
- 个股：中国巨石、太辰光、普冉股份、圣邦股份等。

但阈值需要按对象分层：

| 对象 | 特点 | 阈值倾向 |
|---|---|---|
| 大盘 | 流动性最好，噪音较低，恐慌/高潮更可信 | 反转阈值较低，量价异常要求稳定 |
| 板块 | 轮动快，但不易被单一资金操纵 | 反转阈值中等，重视主线/覆盖度 |
| 个股 | 波动大，可能受事件/资金操纵 | 反转阈值较高，需更强证据 |

### 3.3 保持旁路，先验证再接生产

本阶段只设计：

```text
文档
  ↓
纯函数
  ↓
fixture 回归
  ↓
真实数据验证图
  ↓
人工校验
```

在人工样本稳定前，不替换生产 `get_structure()` / `get_stage()`。

## 4. 输出契约

建议输出：

```json
{
  "version": "3l-structure-context-v1",
  "status": "ok",
  "asset_type": "market|sector|stock",
  "date": "20260901",

  "market_structure": {
    "structure": "上涨趋势|区间震荡|下降趋势|未识别",
    "stage": "形成|发展|加速|逆转|恐慌|下行|反弹|区间顶部|区间底部|区间中段",
    "supply_demand_regime": "demand_dominant|supply_dominant|balance|unknown",
    "confidence": 0,
    "evidence": []
  },

  "wave_context": {
    "primary_wave": {
      "direction": "up|down|flat",
      "start_idx": 0,
      "start_date": "20260612",
      "extreme_idx": 0,
      "extreme_date": "20260709",
      "change_pct": 0,
      "duration": 0,
      "status": "confirmed|candidate"
    },
    "trading_wave": {
      "direction": "up|down|flat",
      "label": "上涨波段|下降波段|横向整理",
      "state": "上涨趋势中的回调|下降趋势中的反弹|区间震荡中的上行波段"
    },
    "pivots": []
  },

  "wave_position": {
    "position": "valley_left|valley_confirmed|rising_middle|peak_left|peak_confirmed|falling_middle|range_middle|unknown",
    "label": "波谷左侧|波谷确认|上升波中|波峰左侧|波峰确认|下降波中|区间中段|未识别",
    "confidence": 0,
    "evidence": []
  },

  "major_decline_risk": {
    "level": "none|watch|high",
    "reason": "",
    "evidence": []
  },

  "position_context": {
    "zone_type": "near_support|near_resistance|mid_range|trend_pullback|trend_body|downtrend|extended|unknown",
    "range_position_pct": null,
    "anchor": null
  },

  "warnings": [],
  "is_trade_decision": false
}
```

## 5. 算法设计

### 5.1 输入

```text
K 线序列：
  date, open, high, low, close, volume

对象类型：
  market / sector / stock

可选上游结果：
  pure_keypoints
  wave_structure_result
  supply_demand_events
```

### 5.2 第一步：识别波段 pivots

优先复用当前旁路：

- `server/backend/core/wave_structure_detector.py`
- 动态 ZigZag；
- `market / sector / stock` 不同阈值；
- confirmed pivot 与 candidate trading wave 分开。

后续需要补强：

1. 高低点序列校验：
   - 最近两个高点、低点是否抬高；
   - 最近两个高点、低点是否降低；
2. 波段质量：
   - 涨跌幅是否足够；
   - 持续时间是否足够；
   - 是否只是单日长影噪音；
3. 当前最后一天 candidate 处理：
   - 最后一根可以标为 candidate；
   - 不允许最后一天直接把历史 confirmed 结构完全推翻；
   - 但必须暴露“正在转向”的风险/机会。

伪算法：

```text
pivots = detect_wave_pivots(rows, dynamic_threshold)
active_wave = build_active_wave(last_confirmed_pivot, rows)
candidate_wave = detect_candidate_counter_wave(active_wave, recent_extreme, close)
trading_wave = candidate_wave or active_wave
```

### 5.3 第二步：由高低点序列判定结构

核心不能只看 EMA，要引入 3L 原文的高低点定义。

```text
if 最近两个有效高点抬高 and 最近两个有效低点抬高:
    structure = 上涨趋势
    regime = demand_dominant

elif 最近两个有效高点降低 and 最近两个有效低点降低:
    structure = 下降趋势
    regime = supply_dominant

else:
    structure = 区间震荡
    regime = balance
```

但实际必须允许“形成中”：

```text
只有一个高低点序列确认：
  - 低点抬高但高点未突破：上涨形成中 / 区间偏强
  - 高点降低但低点未跌破：下降形成中 / 区间偏弱
```

### 5.4 第三步：识别结构阶段

#### 上涨趋势阶段

```text
形成：
  刚从区间/下降中突破或反转；
  最近一组高低点开始抬高；
  需求进入但涨幅尚未过大。

发展：
  高低点持续抬高；
  上涨波中红肥绿瘦或温和放量；
  回踩不破关键支撑。

加速：
  上涨斜率明显变陡；
  成交量明显放大；
  连续长阳或乖离过大；
  需求可能被透支。

逆转：
  加速后放量滞涨、缩量滞涨、放量反转阴线；
  或关键低点被有效跌破；
  供应开始压倒需求。
```

#### 下降趋势阶段

```text
形成：
  上升段后跌破关键支撑；
  高低点开始降低；
  供应进入。

发展：
  高低点持续降低；
  下降波中绿肥红瘦；
  反弹无量，需求不足。

恐慌：
  缓跌后急跌；
  天量阴线、锤头线或小实体；
  放量但价格不再有效下跌；
  必须发生在下降末端或区间底部附近。

逆转：
  供应衰竭后，需求出现；
  放量阳线、放量锤头线、放量十字星；
  收在相对高位；
  反转原下降/调整走势。
```

#### 区间震荡阶段

区间震荡原文说“大多数时候市场处于区间震荡中”，且“不存在阶段概念”，工程上只给位置：

```text
区间顶部：接近压力，上沿无法突破偏风险；
区间底部：接近支撑，下沿无法跌破偏机会；
区间中段：胜负未明，默认观察。
```

### 5.5 第四步：识别波段位置

波段位置用于交易节奏，不直接等于买卖点。

```text
valley_left 波谷左侧：
  明显下降段之后；
  出现供应衰竭迹象；
  但需求尚未明确确认。

valley_confirmed 波谷确认：
  下降段结束后；
  出现需求进入或跌破失败/反转；
  trading_wave 开始转上。

rising_middle 上升波中：
  需求占优延续；
  未出现明显需求透支。

peak_left 波峰左侧：
  明显上升段之后；
  出现加速、高潮、放量滞涨、缩量滞涨；
  但尚未确认下跌波。

peak_confirmed 波峰确认：
  上升段结束；
  出现放量反转、突破失败、关键低点跌破；
  trading_wave 开始转下。

falling_middle 下降波中：
  供应占优延续；
  没有供应衰竭或需求进入证据。
```

### 5.6 第五步：识别主跌风险

主跌风险只在市场/板块/个股各自上下文中表达，不直接等于“大盘必须空仓”。

```text
high:
  下降趋势形成/发展；
  或上升段加速后出现需求衰竭/供应进入；
  或关键支撑跌破且无需求承接。

watch:
  上升段后出现滞涨、转弱、缩量上涨、反弹无量；
  或区间顶部突破失败；
  或交易波段已转下但主结构尚未确认。

none:
  上升趋势形成/发展；
  或区间底部承接；
  或下降末端恐慌/供应衰竭后等待需求确认。
```

特别注意：

```text
恐慌发生在下降末端或区间底部时，不应继续机械标成主跌 high；
它应转为 valley_left / supply_exhaustion_candidate。
```

## 6. 与现有代码关系

### 6.1 可复用

| 现有模块 | 可复用点 |
|---|---|
| `pure_keypoint_detector.py` | 前高/前低/局部量峰/量谷 |
| `wave_structure_detector.py` | 动态 ZigZag、confirmed/candidate trading wave |
| `structure_position_context.py` | 区间位置、趋势回踩位置 |
| `supply_demand_keypoint_detector.py` | 当前供需点候选 |
| `supply_demand_event_detector.py` | 结构化供需事件语义 |

### 6.2 不应复用为最终结构核心

| 现有模块 | 原因 |
|---|---|
| `get_structure()` | EMA 确认型，容易滞后，不能单独代表 3L 高低点趋势 |
| `get_stage()` | 对区间位置可参考，但趋势阶段语义过粗 |
| 旧买点 detector | 仍有历史兼容逻辑，不能反向污染结构层 |

### 6.3 兼容策略

短期：

```text
旧 get_structure/get_stage 继续服务生产页面；
新 detect_3l_structure_context 旁路验证；
复盘页先只展示旁路结果，不用于买卖点。
```

中期：

```text
供需事件优先消费新结构上下文；
买点层只消费 supply_demand_event + structure_context；
旧 signal_detector 逐步降级为技术参考。
```

长期：

```text
review / monitor / stock_analysis / holdings 全部共享同一结构上下文和买卖点合同。
```

## 7. 验证计划

### 7.1 第一批样本

继续沿用用户已经人工看过的样本：

| 类型 | 样本 |
|---|---|
| 大盘 | 科创50、中证全指 |
| 板块 | CPO、元件、存储芯片 |
| 个股 | 中国巨石、太辰光、普冉股份、圣邦股份、绿的谐波、美年健康、永鼎股份、胜宏科技、中际旭创 |

### 7.2 需要人工校验的问题

每张图不再问“是不是买点”，而是问：

1. 这一段是否是明显上涨波段？
2. 这一段是否是明显下降波段？
3. 当前是波谷左侧、波谷确认、波中、波峰左侧、波峰确认，还是下降波中？
4. 主跌风险是否应该是 `none / watch / high`？
5. 结构标签是否和人眼一致？

### 7.3 回归固化

人工确认后，把样本固化为：

```text
server/backend/tests/fixtures/structure_context_benchmark_v1.json
```

测试只锁定关键窗口，不锁死每一天：

```json
{
  "sample": "科创50",
  "windows": [
    {
      "start": "20260612",
      "end": "20260630",
      "expected_trading_wave": "up",
      "expected_position": "rising_middle"
    },
    {
      "start": "20260710",
      "end": "20260803",
      "expected_trading_wave": "down",
      "expected_major_decline_risk": "high"
    }
  ]
}
```

## 8. 首版实现计划

### PR 1：设计文档

本 PR。

### PR 2：旁路纯函数

新增：

```text
server/backend/core/structure_context_detector.py
server/backend/tests/test_structure_context_detector.py
```

先复用：

- `judge_wave_structure()`
- `detect_pure_keypoints()`
- `detect_structure_position_context()`
- `detect_supply_demand_events()`

输出 `3l-structure-context-v1`。

### PR 3：验证图

新增：

```text
server/scripts/render_structure_context_validation.py
```

图中展示：

- K 线；
- 主交易波段色带；
- 波谷/波峰候选；
- 主跌风险背景；
- 结构/阶段/波段位置标题；
- 所有判断证据。

### PR 4：人工校验样本固化

把用户确认过的窗口写入 benchmark fixture。

### PR 5：复盘页旁路展示

只展示结构上下文，不接买卖点。

例如：

```text
市场环境：弱势市场
主跌风险：high
波段位置：波谷左侧
结构阶段：下降趋势 · 恐慌候选
```

每个字段提供 information：

- 判断依据；
- 关键数值；
- 哪些证据支持；
- 哪些证据冲突。

## 9. 明确不做

本阶段不做：

- 不改生产买卖点；
- 不改仓位建议；
- 不把 `wave_position=valley_left` 自动解释成买点；
- 不把 `major_decline_risk=high` 自动解释成全部卖出；
- 不解决真正 L1 主线算法；
- 不改前端交互。

## 10. 成功标准

设计层成功：

- 文档能解释用户之前提出的所有核心冲突；
- 定义上能区分关键点、波段、结构、供需事件、买卖点；
- 明确了主跌风险与恐慌/供应衰竭不是同一个东西。

实现层成功：

- 真实图上，科创50 2026-06 中旬到 6 月底应被识别为上升波段；
- 2026-07 中旬到 8 月初的下跌段不应被单日反弹轻易打断；
- 普冉股份 2026-07 初应能暴露下降交易波段；
- 圣邦股份区间顶部/放量转弱不能成为中继买点前置；
- 绿的谐波下降趋势里的缩量反弹应解释为下跌中继/需求不足，而不是看多低吸。


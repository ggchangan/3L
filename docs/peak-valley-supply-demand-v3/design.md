# 3L 峰谷与供需格局判定 V3

> 状态：V3 已实现并完成首轮历史回归；按“解释性判定上线、禁止单独驱动买入”方式接入
> 目标：先把《3L交易体系》《量价原理》的自然语言转换成可解释、可回归、无未来数据的证据算法，再替换大盘现有 BIAS20 四项评分。

## 1. 为什么不能继续直接加分

现有 `judge_peak_valley()` 将“位置低、跌速变化、量价形态、短期方向”各记一分，并在 `BIAS20 < -8%` 时把波谷分强制提高到 3。它能做低位预警，但存在三个根本问题：

1. **位置不等于供需变化**：严重超跌只能说明价格离均值远，不能说明供应已经出清；
2. **证据有因果顺序**：恐慌是供应集中释放，放量滞跌才是供应被吸收，向上反转才是需求占优，三者不能等权相加；
3. **同一量价行为依赖结构**：上升趋势回踩缩量是供应减弱，下降趋势缩量阴跌却通常是需求不足。

工程中已有 `structure_wave.py`，它解决了“先分结构”问题，但仍直接把形态计分，并将峰谷压缩成五档。本版保留结构分流，新增可独立验证的供需证据层和有序状态机。

## 2. 知识库约束

算法必须满足以下不可被回测参数推翻的语义约束：

- 低点是某一级别的供应衰竭点，或供应占优转为需求占优的转折点；
- 下降趋势中的缩量不能单独视为供应衰竭，因为无需求也能持续阴跌；
- 恐慌性抛售是供应释放，不等于当日已经见底；需要观察供应是否被吸收、价格是否停止下跌；
- 放量滞跌表示很大的供应已经不能继续推动价格下跌，是底部证据；
- 向上反转表示需求开始占优，是比“位置低”更高级别的确认；
- 上升趋势波谷、区间底部波谷、下降趋势波谷使用不同路径；
- 波峰采用对称逻辑：需求透支/衰竭 → 供应吸收需求 → 供应开始占优；
- 大盘用于排除主跌风险。峰谷阶段影响交易节奏，但不能替代主线、板块环境和个股买点。

## 3. 两层算法

### 3.1 第一层：供需证据引擎

证据引擎不直接输出“波谷”，只输出可解释证据，每项为 `0~100`：

#### 位置与背景（Context，不作为确认）

- `low_location`：价格在近期区间的位置、BIAS20、距20/60日高点回撤；
- `high_location`：与低位位置对称；
- `decline_context`：下降持续时间、10/20日跌幅、MA20/MA60方向；
- `advance_context`：与下降背景对称；
- `support_context`：EMA10/MA20、前低或区间底部是否构成支撑；
- `resistance_context`：与支撑对称。

位置证据只允许进入“左侧观察”，不能单独进入“偏波谷/偏波峰”。

#### 供应侧证据

- `panic_release`：持续下跌后出现异常阴量、大实体或大振幅，表示供应集中释放；
- `supply_exhaustion`：下跌推进效率下降、价格不再有效创新低、振幅收窄；缩量只能作为组成证据；
- `absorption`：成交量/振幅很大但向下价格结果很小，或触及新低后收回，表示需求吸收供应；
- `supply_entry`：高位放量下跌、长上影、跌破短期关键点，表示供应开始占优。

#### 需求侧证据

- `buying_climax`：持续上涨后异常放量和斜率加速，表示需求集中消耗；
- `demand_exhaustion`：上涨推进效率下降、放量/缩量滞涨、价格不再有效创新高；
- `distribution`：成交量很大但向上价格结果很小，表示供应吸收需求；
- `demand_entry`：收盘位于日内高位、放量阳线/向上反转、站回短期关键点，表示需求开始占优。

### 3.2 第二层：峰谷状态机

波谷状态：

```text
NONE
  └─ 低位 + 下跌背景 ───────────────→ LEFT（波谷左侧）
LEFT
  └─ 恐慌/衰竭/吸收至少一项 ───────→ FORMING（波谷形成中）
FORMING
  └─ 供应侧证据 + 初步需求进入 ─────→ BIASED（偏波谷）
BIASED
  └─ 向上反转/收复关键点并延续 ─────→ CONFIRMED（波谷确认）
```

波峰完全对称：

```text
高位上涨背景 → PEAK_LEFT
高潮/需求衰竭/派发 → PEAK_FORMING
需求侧衰竭 + 供应进入 → PEAK_BIASED
向下反转/跌破关键点 → PEAK_CONFIRMED
```

状态不是“仓位目标”。它表示供需演化到了哪一步。

## 4. 基础特征

所有计算只使用当前及之前的K线，输入按日期升序归一化。

```python
return_1d = close[-1] / close[-2] - 1
return_3d = close[-1] / close[-4] - 1
return_10d = close[-1] / close[-11] - 1
return_20d = close[-1] / close[-21] - 1

atr14 = mean(true_range[-14:])
range_atr = true_range[-1] / atr14
volume_ratio20 = volume[-1] / mean(volume[-21:-1])
volume_percentile120 = percentile_rank(volume[-1], volume[-120:])
close_location = (close[-1] - low[-1]) / (high[-1] - low[-1])

bias20 = (close[-1] - ma20[-1]) / ma20[-1]
range_position60 = (close[-1] - low60) / (high60 - low60)
new_low_progress = max(0, (prior_low20 - low[-1]) / atr14)
new_high_progress = max(0, (high[-1] - prior_high20) / atr14)

down_effort = volume_ratio20 * max(0, -return_1d)
down_result = new_low_progress + max(0, -return_1d) / atr_pct
down_efficiency = down_result / max(down_effort, epsilon)

up_effort/up_result/up_efficiency = symmetric(...)
```

阈值优先使用 ATR、历史分位数等自适应量纲，不直接假设所有指数都适用相同的固定涨跌幅。

## 5. 证据算法

### 5.1 低位与高位

```python
low_location = weighted_score(
    range_position60 <= 0.20,
    bias20 / atr_pct 显著为负,
    drawdown20 / atr_pct 显著,
)

high_location = symmetric(low_location)
```

极端 BIAS 只提高 `low_location/high_location`，不得直接提高峰谷状态。

### 5.2 恐慌释放

```python
panic_release requires decline_context

effort = max(volume_ratio20, volume_percentile120, range_atr)
selling_result = 大阴线 or 向下跳空 or 明显创新低

panic_release = score(effort, selling_result)
```

恐慌当日如果收盘仍在最低区域、继续有效创新低，只表示供应释放；不能直接判波谷。

### 5.3 供应衰竭

```python
supply_exhaustion requires decline_context or pullback_context

slowdown = 近3日向下推进 < 前一阶段向下推进
no_progress = 新低幅度很小 or 连续2~3日不再创新低
range_contract = 近3日振幅 / 前10日振幅下降
volume_contract = 近3日量 / 前10日量下降

supply_exhaustion = score(slowdown, no_progress, range_contract, volume_contract)
```

硬约束：

```python
if structure == DOWN and demand_entry < threshold:
    volume_contract 只能作为辅助，不能让状态超过 FORMING
```

### 5.4 吸收/放量滞跌

```python
high_effort = volume_ratio20高 or volume_percentile120高
poor_down_result = down_efficiency显著低于过去20日
recovery = 收盘离开最低区域 or 触新低后收回

absorption = score(high_effort, poor_down_result, recovery)
```

这项直接实现“很大的供应已经不能继续推动价格下跌”。

### 5.5 需求进入

```python
bullish_result = 阳线实体/收盘位置/向上突破
effort_support = 上涨放量，或供应已衰竭后的温和需求
reclaim = 收复MA5、前一日高点或短期下降趋势线
follow_through = 最近2~3日向上推进且低点不再降低

demand_entry = score(bullish_result, effort_support, reclaim, follow_through)
```

峰部的 `buying_climax / demand_exhaustion / distribution / supply_entry` 使用完全对称的价格结果与成交量努力关系。

## 6. 按结构组合状态

### 上升趋势波谷

```python
LEFT:
  回踩发生，但趋势关键点尚未确认支撑

FORMING:
  support_context >= 50
  and supply_exhaustion >= 50

BIASED:
  support_context >= 60
  and supply_exhaustion >= 60
  and demand_entry >= 40

CONFIRMED:
  BIASED and demand_entry >= 70
```

### 区间震荡波谷

```python
LEFT:
  low_location >= 60 and 靠近区间底部

FORMING:
  LEFT and max(supply_exhaustion, absorption, panic_release) >= 60

BIASED:
  FORMING and demand_entry >= 50

CONFIRMED:
  BIASED and demand_entry >= 70 and 离开区间最低区域
```

### 下降趋势波谷

```python
LEFT:
  decline_context >= 60 and low_location >= 60

FORMING:
  LEFT and max(panic_release, supply_exhaustion, absorption) >= 60

BIASED:
  FORMING
  and max(panic_release, supply_exhaustion) >= 60
  and (
    (absorption >= 50 and demand_entry >= 55)
    or (supply_exhaustion >= 60 and demand_entry >= 65 and 需求连续推进)
  )

CONFIRMED:
  BIASED and demand_entry >= 75 and 收复短期关键点
```

第二条路径对应知识库所说的“向上反转是需求进入”：并非每次反转前都有标准放量滞跌，
但必须同时出现供应衰竭、较强需求和连续向上推进，不能用单根阳线代替。

因此，下降趋势中“严重超跌 + 缩量”最多停留在 `LEFT/FORMING`，不能成为偏波谷。

波峰按镜像规则组合，但保留知识库中的非对称事实：下降不需要量、向下突破可以缩量，因此供应进入的量能要求低于需求进入。

## 7. 输出契约

```json
{
  "position": "波中偏下",
  "wave_side": "valley",
  "wave_phase": "left",
  "wave_label": "波谷左侧",
  "structure": "下降趋势",
  "supply_demand_state": "供应仍占优",
  "evidence": {
    "low_location": 82,
    "panic_release": 20,
    "supply_exhaustion": 35,
    "absorption": 10,
    "demand_entry": 5
  },
  "hard_gates": ["下降趋势尚无吸收或需求进入"],
  "explanation": [
    "价格已进入低位区域",
    "向下推进仍在继续",
    "尚未观察到放量滞跌或需求反转"
  ],
  "algorithm_version": "supply_demand_v3"
}
```

兼容映射：

| 状态 | 旧五档位置 |
|---|---|
| `VALLEY_LEFT / VALLEY_FORMING` | 波中偏下 |
| `VALLEY_BIASED / VALLEY_CONFIRMED` | 偏波谷 |
| `PEAK_LEFT / PEAK_FORMING` | 波中偏上 |
| `PEAK_BIASED / PEAK_CONFIRMED` | 偏波峰 |
| 其他 | 波中 |

## 8. 回归测试设计

### 8.1 数据

- 中证全指、上证指数、创业板指、科创50；
- 使用数据库中全部可用日线；
- 每次滚动只向算法提供当日及以前数据；
- 最少预热80个交易日。

### 8.2 事件去重

连续多日停留在同一状态只记一次事件。状态升级可记新事件；状态未变化使用5日冷却，避免把同一个底部重复统计成多个样本。

### 8.3 指标

- 1/3/5/10/20日前向收益；
- 5/10/20日最大有利波动 MFE；
- 5/10/20日最大不利波动 MAE；
- 波谷后上涨胜率、波峰后下跌胜率；
- 从 LEFT 到 BIASED/CONFIRMED 的平均提前天数；
- 按指数、结构、阶段、年份分层；
- 触发次数与连续重复率；
- 旧 `judge_peak_valley()` 同期 A/B 对比。

LEFT 不是买入信号，不能只用胜率评价；主要评价它是否能提前覆盖后续 BIASED/CONFIRMED，同时保持可接受的误报持续时间。

### 8.4 防止过拟合

- 前60%历史用于诊断和参数调整，后40%只做最终验证；
- 不以单一“5日胜率”优化；
- 参数调整必须能对应明确的供需语义；
- 四个指数分别报告，不用样本量大的指数掩盖其他指数；
- 报告所有事件数，低样本结果不下结论。

### 8.5 上线门槛

1. 下降趋势缩量阴跌不得输出 `偏波谷/波谷确认`；
2. 极端 BIAS 无供需证据时只能输出 `波谷左侧`；
3. 恐慌但收盘低位、仍高效创新低时不得直接确认波谷；
4. 新算法的 `BIASED/CONFIRMED` 在验证集上的 MAE 必须优于旧“偏波谷”，且不能只靠减少到极少样本实现；
5. 波峰、波谷证据和硬门禁必须在 API 中可解释；
6. 单元测试、历史回归、生产当前四指数快照全部通过后才切换。

第4项在当前数据库样本内尚不能得到充分统计验证，因此本次接入不允许
`BIASED/CONFIRMED` 单独触发买入或目标仓位扩张；它只改变波段位置和交易节奏说明，
实际新增仓位仍必须同时满足主线/强动量方向和个股有效买点。详见同目录回归报告。

## 9. 伪算法

```python
def judge_peak_valley_v3(klines, structure=None):
    bars = normalize_and_validate(klines)
    if len(bars) < 80:
        return unknown_result("数据不足")

    features = compute_adaptive_features(bars)
    structure = structure or classify_structure(features)

    context = score_context(features, structure)
    supply = {
        "panic_release": score_panic_release(features, context),
        "supply_exhaustion": score_supply_exhaustion(features, context),
        "absorption": score_absorption(features, context),
        "supply_entry": score_supply_entry(features, context),
    }
    demand = {
        "buying_climax": score_buying_climax(features, context),
        "demand_exhaustion": score_demand_exhaustion(features, context),
        "distribution": score_distribution(features, context),
        "demand_entry": score_demand_entry(features, context),
    }

    valley_phase, valley_gates = combine_valley_state(
        structure, context, supply, demand
    )
    peak_phase, peak_gates = combine_peak_state(
        structure, context, supply, demand
    )

    side, phase = resolve_competing_states(
        valley_phase, peak_phase, context, supply, demand
    )
    return explain_and_map_legacy_position(
        side, phase, structure, context, supply, demand,
        valley_gates + peak_gates,
    )
```

## 10. 实施顺序

1. 新增纯函数模块，不修改现有生产调用；
2. 用合成K线锁定知识库硬约束；
3. 建立历史事件回归并与旧算法对比；
4. 根据诊断修正算法，记录每次修改原因和验证集结果；
5. 以双算字段接入 API，验证当前四指数；
6. 最终切换 `judge_peak_valley()`，保留旧算法一个版本周期作为回滚路径。

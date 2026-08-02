# L1 动量主线识别设计

## 1. 背景与边界

当前复盘的方向榜按“板块自身 20 日涨幅”排序，并把前 5、6–10 名作为两档候选。它可作为短期强度线索，但不符合 3L 知识库的 L1 动量主线定义，因此对外统一称为“20日板块强度候选”。

正式 L1 模型必须从全市场强势个股出发，再聚合到同花顺行业/概念；不能直接用板块自身涨幅替代。

## 2. 知识库口径

1. 计算全市场个股 20 日涨幅并取前列个股。基准为前 700 名，随市场容量扩张动态调整。
2. 剔除上市不足 20 日的次新股。
3. 按知识库口径剔除机构认可度不足的干扰项：基金持仓低于 2% **或**北向持仓低于 0.5% 均应剔除，即保留项必须同时满足两项门槛。若持仓数据缺失，必须标记数据不完整，不能静默跳过过滤。
4. 知识库原文按东财二级行业聚合：
   - 动量股数量 `momentum_stock_count`
   - 板块覆盖率 `coverage = momentum_stock_count / constituent_count`
   - 动量分值 `momentum_score = momentum_stock_count * coverage`
5. 原始口径中 `momentum_score > 1` 才具备板块效应；`momentum_score > 7` 是高潮风险提示，不是强度继续加分。
6. 用一年新高数量/重合度、趋势与持续在榜天数交叉验证。
7. 比较相邻交易日，识别新进、增强、持续、衰退、退出与主线切换。

### 3L 项目的工程口径偏差

本项目的数据源分层目标是优先统一使用 Tushare 提供的 THS 数据，因此正式实现计划采用 THS 行业，并将概念作为独立榜单。这与知识库原始的“东财二级行业”不是同一分类体系。`>1` 与 `>7` 阈值不能直接宣称等价，必须在 THS 成分口径上重新回放、校准并记录差异；校准完成前只能输出实验性 L1 结果。

## 3. 数据输入与质量门槛

| 输入 | 首选来源 | 最低要求 | 缺失处理 |
| --- | --- | --- | --- |
| 个股日线与复权价 | Tushare/THS 统一通道 | 至少 20 个有效交易日 | 个股不进入样本并计入缺失率 |
| 上市日期 | Tushare 基础资料 | 全市场覆盖 | 无法确认时排除并告警 |
| THS 行业/概念成分 | Tushare THS | 成分及板块总数同一交易日口径 | 板块不出正式结论 |
| 基金/北向持仓 | 可配置数据源 | 目标日可用的最近一期 | 输出 `partial`，不得伪装完整 L1 |
| 52 周新高 | 统一个股日线 | 至少 250 个交易日 | 只取消新高验证，不影响基础分，但降级置信度 |
| 历史 L1 快照 | 本系统每日快照 | 至少前一交易日 | 不输出轮动状态 |

所有输入必须携带 `as_of_date`、来源与覆盖率。计算只允许使用目标日当时已经可获得的数据，防止未来数据穿越。

## 4. 算法伪代码

```text
eligible = 全市场股票
eligible = eligible.filter(上市天数 >= 20)
eligible = eligible.filter(20日行情完整)

top_n = max(700, round(len(eligible) * dynamic_top_ratio))
momentum_pool = eligible.sort_by(20日涨幅 desc).take(top_n)

if 机构持仓覆盖达到门槛:
    momentum_pool = momentum_pool.filter(基金持仓 >= 2% and 北向持仓 >= 0.5%)
else:
    data_status = partial

for board in THS板块:  # 工程偏差口径，阈值须重新校准
    members = board.目标日有效成分
    hits = members ∩ momentum_pool
    count = len(hits)
    coverage = count / len(members)
    score = count * coverage
    high52_count = count(成员在目标日创52周新高)
    high52_overlap = count(hits ∩ 52周新高股)

    if score <= 1: status = not_confirmed
    if 1 < score <= 7: status = confirmed
    if score > 7: status = climax_warning

    compare previous snapshots:
        rotation_state = new | strengthening | persistent | declining | exited
```

同一只股票可能属于多个概念，概念榜必须明确多重归属；行业榜采用目标日权威行业映射，避免统计口径漂移。

## 5. 输出契约

正式 L1 接口至少返回：

- `model_type = l1_momentum_mainline`
- `is_l1_model = true`
- `momentum_stock_count`
- `constituent_count`
- `coverage`
- `momentum_score`
- `consecutive_days`
- `new_high_count` 与 `new_high_overlap`
- `status`：未确认、主线确认、高潮预警
- `rotation_state`：新进、增强、持续、衰退、退出、切换
- `data_status`、各输入覆盖率及 `as_of_date`

代理榜继续返回 `model_type = sector_return_20d_proxy`、`is_l1_model = false`，二者不得共用“主线确认”的展示文案。

## 6. 页面展示

方向卡按“动量分值”排序，但同时展示数量和覆盖率，避免大板块天然占优或小板块因少数个股被夸大。高潮预警使用风险色，不再继续提高推荐等级。

页面需展示：动量股数量、板块覆盖率、动量分值、连续在榜天数、一年新高验证、加速/高潮状态、新进/衰退/切换状态。板块量价阶段仍是独立环境维度，不能替代个股买点。

## 7. 实施与验证

1. 先做数据可用性审计，特别确认机构持仓、历史成分和 250 日行情覆盖。
2. 建立按交易日可重放的 L1 快照计算，不接入交易计划。
3. 选取多个强势、弱势和震荡区间做无未来数据回归，人工抽查主线形成、高潮和切换事件。
4. 与当前 20 日板块强度代理榜并行影子运行，记录差异及原因。
5. 达到覆盖率和稳定性门槛后，页面切换为正式 L1；交易计划仍需单独验证市场环境、方向优先级与个股买点的组合规则。

## 8. 验收原则

- 不以板块自身 20 日涨幅冒充 L1。
- 分值大于 1 才能标记板块效应，分值大于 7 必须提示高潮。
- 数据不完整时明确降级，不补零、不沿用旧结论伪装当日结果。
- 回归结果必须同时报告样本日期、覆盖率、事件识别结果和典型误判，不能只给一个脱离市场阶段的总准确率。

# 3L 参数治理

运行时参数统一定义在 `core/threel_core/parameters.py`。每次修改数值必须：

1. 升级 `PARAMETER_VERSION`；
2. 保留知识库来源，区分“体系原则”和“工程阈值”；
3. 使用 `backtest_service.run_backtest` 在相同股票池、日期区间上对比新旧版本；
4. 将回测结果快照登记到 `backtest_basis.result_snapshot` 后再用于生产。

`GET /api/system/parameters` 可查看线上实际生效的版本、参数、知识来源和回测状态。回测接口的结果包含 `parameter_version`，交易决策包含相同字段，便于复现。

当前知识库未检索到 BIAS、EMA 斜率和固定止损百分比的原文数值，因此清单明确把这些数值标记为工程参数；知识库只作为趋势、量价、关键点和风险控制的原则来源，避免把实现经验误写成 3L 原文规则。

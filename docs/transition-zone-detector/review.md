# P0.3 多日供需转换区间自审记录

## Review 1：接口与边界

- 结论：通过。
- 检查点：
  - 新增 `supply_demand_transition_zone_detector.py`，没有修改生产复盘页、买卖点模块或数据更新流程；
  - 输出包含 `is_trade_decision=false`，语义上只表示供需转换区间；
  - 支持外部传入 `wave_states` 和 `supply_demand_results`，方便后续复用和测试。
- 发现问题：
  - 初版把一日假切换也画到图上，容易制造噪声。
- 处理：
  - 增加 `include_failed=false` 默认过滤失败切换；
  - 保留 `include_failed=true` 作为研究/调试入口。

## Review 2：真实样本回归

- 结论：可进入人工校验，但不宜接生产。
- 检查样本：
  - 大盘：科创50、中证全指；
  - 板块：元件、CPO、存储芯片；
  - 个股：中国巨石、太辰光、普冉股份、圣邦股份、美年健康。
- 发现问题：
  - 股票前复权数据在验证脚本中没有强制升序，导致横轴反向；
  - 图中文字过密，影响人工观察 K 线。
- 处理：
  - `_normalize_rows()` 强制按日期升序；
  - 图上只给核心区间和最新区间打文字标签，关注区间保留半透明框。

## Review 3：3L 语义

- 结论：当前版本符合“先识别波段切换窗口”的 P0.3 目标，但仍是骨架版。
- 符合点：
  - 下降段→上升段、上升段→下降段被当作核心对象；
  - 区间允许多日，不把供需转换压缩成单根 K；
  - 最新切换可以标记为 `forming`，避免提前确认；
  - P0.2 单日供需格局点只作为证据，不替代波段切换。
- 尚未解决：
  - 还没有把“前高/前低/箱体上下沿/结构级突破失败”纳入区间边界；
  - 科创50 2026-06-12~2026-06-15 的人工锚点，当前算法更早在 2026-06-09 标记切换，说明下一步需要让“波段切换确认日”和“供需转换完成区间”分离；
  - 个股区间数量仍偏多，后续需要结合趋势级别和关键锚点继续降噪。

## 回归命令

```bash
PYTHONPATH=server:core pytest -q \
  server/backend/tests/test_wave_structure_detector.py \
  server/backend/tests/test_supply_demand_keypoint_detector.py \
  server/backend/tests/test_supply_demand_transition_zone_detector.py \
  server/backend/tests/test_transition_zone_validation_script.py \
  server/backend/tests/test_keypoint_validation_script.py
```

结果：`30 passed`。

## 验证图

- 本地：`data/validation/transition_zone_p03/overview.png`
- 服务器：`/home/ubuntu/data/3l/validation/transition_zone_p03/overview.png`

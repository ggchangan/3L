# 3L 止损算法回测报告

- 代码版本：`0e985a2300fd543019a748d5c1d5bfe58bbd5f71`
- 数据范围：20240401 ～ 20260410
- 股票池：946/1000（历史日线构造，固定哈希抽样=1000）
- 信号：原始 58508，20日冷却后 14823，近期删失 0，停牌删失 33
- 数据跳过：{"price_discontinuity": 54}
- 检测上下文：波中市场、假设属于主线；每个信号日强制截断 K 线，无未来数据。

## 校准集

| 候选 | 样本 | 覆盖率 | 初始风险 | 20日止损 | 假止损 | 平均收益 | CVaR5 | 最大亏损 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cost_2atr | 12908 | 100.00% | 8.32% | 44.27% | 28.94% | 1.33% | -15.52% | -32.74% |
| production_baseline | 12908 | 100.00% | 5.69% | 59.55% | 47.36% | 0.96% | -13.69% | -33.42% |
| structure_atr_0.0 | 12908 | 96.05% | 2.35% | 84.66% | 72.81% | 0.28% | -10.13% | -28.59% |
| structure_atr_0.1 | 12908 | 99.79% | 2.56% | 83.01% | 70.62% | 0.39% | -10.35% | -28.92% |
| structure_atr_0.2 | 12908 | 99.96% | 2.88% | 80.72% | 67.66% | 0.47% | -10.71% | -29.24% |
| structure_atr_0.3 | 12908 | 100.00% | 3.24% | 77.86% | 64.37% | 0.59% | -11.17% | -29.56% |

## 时间外验证集

| 候选 | 样本 | 覆盖率 | 初始风险 | 20日止损 | 假止损 | 平均收益 | CVaR5 | 最大亏损 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cost_2atr | 1909 | 100.00% | 8.27% | 53.06% | 23.69% | -0.66% | -14.66% | -35.24% |
| production_baseline | 1909 | 100.00% | 5.37% | 68.04% | 40.33% | -0.57% | -12.27% | -23.82% |
| structure_atr_0.0 | 1909 | 96.70% | 2.10% | 88.79% | 70.03% | -0.29% | -7.45% | -19.96% |
| structure_atr_0.1 | 1909 | 99.90% | 2.33% | 87.49% | 66.71% | -0.30% | -7.89% | -19.96% |
| structure_atr_0.2 | 1909 | 100.00% | 2.65% | 86.17% | 63.83% | -0.44% | -8.48% | -21.36% |
| structure_atr_0.3 | 1909 | 100.00% | 3.02% | 83.45% | 60.21% | -0.36% | -8.89% | -21.36% |

## 自动验收结论

```json
{
  "structure_atr_0.0": {
    "all": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2836,
      "false_stop_improvement_pp": -29.7031
    },
    "突破买点": {
      "accepted": false,
      "reasons": [
        "平均收益/假止损率未达到改善门槛",
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.0893,
      "false_stop_improvement_pp": -39.1122
    },
    "中继买点": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.3495,
      "false_stop_improvement_pp": -28.3627
    }
  },
  "structure_atr_0.1": {
    "all": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2737,
      "false_stop_improvement_pp": -26.3849
    },
    "突破买点": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2581,
      "false_stop_improvement_pp": -37.4913
    },
    "中继买点": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2791,
      "false_stop_improvement_pp": -24.2317
    }
  },
  "structure_atr_0.2": {
    "all": {
      "accepted": false,
      "reasons": [
        "平均收益/假止损率未达到改善门槛",
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.1342,
      "false_stop_improvement_pp": -23.5074
    },
    "突破买点": {
      "accepted": false,
      "reasons": [
        "平均收益/假止损率未达到改善门槛",
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.1782,
      "false_stop_improvement_pp": -36.3312
    },
    "中继买点": {
      "accepted": false,
      "reasons": [
        "平均收益/假止损率未达到改善门槛",
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.1186,
      "false_stop_improvement_pp": -20.7713
    }
  },
  "structure_atr_0.3": {
    "all": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2082,
      "false_stop_improvement_pp": -19.8816
    },
    "突破买点": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.2005,
      "false_stop_improvement_pp": -34.586
    },
    "中继买点": {
      "accepted": false,
      "reasons": [
        "假止损率恶化>2pp"
      ],
      "mean_return_improvement_pp": 0.211,
      "false_stop_improvement_pp": -16.5549
    }
  }
}
```

> 本报告使用结果代理指标，不宣称人工标注意义上的“止损准确率”。

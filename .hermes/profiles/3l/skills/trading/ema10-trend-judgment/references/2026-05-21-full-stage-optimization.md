# get_stage() 全量调优日志（2026-05-21）

## 改动一览

| 时间 | 改动 | 触发案例 |
|------|------|---------|
| C方案 | ratio>1.8时检测近5日阴线>3%，重算s1 | 伟创电气V反 |
| 缩量整理 | ratio<0.4时引入volumes参数，量缩80%+价在EMA10上→缩量整理 | 国际复材 |
| vol字段修复 | `k.get('volume', k.get('vol', 0))` | all_stocks_60d.json用volume名 |

## 当前判定树

```
s1>0, s2>0
  ├─ ratio>1.8 → 检测急跌 → adjust ratio → 加速/上行
  ├─ ratio<0.4 → 量缩80%+价在EMA10上 → 缩量整理
  │              否则 → 滞涨
  └─ 0.4~1.8 → 上行
s1>0, s2<0 → 转弱
s1<0, s2>0 → 转强
s1<0, s2<0 → 下行(ratio≤1.8) / 加速跌(>1.8)
```

## 参数说明

`get_stage(closes, structure, highs, lows, support_level=None, resistance_level=None, volumes=None)`

- volumes: 成交量列表（int），长度≥13才触发量能判断
- ratio<0.4分支中，volumes全为0或长度不足时自动fallback为"滞涨"
- 量比=末3日均量/前10日均量

# 数据管线设计

## 范围界定

**数据范围 = 自选股（watchlist.json）**

所有跟踪的股票范围由 watchlist 唯一界定，与方向无关。方向只是分组标签，不影响数据拉取。

## 更新线（唯一写入口）

```
update_stock_data.py（17:00 cron）
    │
    ① 读 watchlist.json → 拿到所有股票代码
        │（这是唯一的范围界定，加自选就有了，删自选就没了）
        │
    ② 对每个代码：
        ├─ 已有记录 → 从 mootdx 追加最新日K线
        └─ 新股票   → 从 mootdx 拉60天全量数据
        │
    ③ 原子写入 all_stocks_60d.json
        （先写 tmp 文件，os.rename 覆盖，避免脏读）
```

## 使用线（只读，不写）

所有其他模块通过 `data_layer.py` 提供的只读函数读取数据：
- `get_all_stocks()` — 获取所有股票K线（缓存30秒）
- `get_stock_klines(code)` — 获取单只股票K线

## 约束

1. 只有 `update_stock_data.py` 可以写入 `all_stocks_60d.json`
2. `data_layer.ensure_stock_data()` 改为只读，不写文件
3. `fill_stock_names.py` 补名逻辑合并入更新脚本
4. 删除自选股不清除数据（留作历史），但不更新

## 新加自选股但无数据的情况

17:00 前加入 watchlist → 当天更新后有数据
17:00 后加入 watchlist → 次日更新后有数据
个股卡片上如有需要可加标识："⏳ 明日复盘后显示完整数据"

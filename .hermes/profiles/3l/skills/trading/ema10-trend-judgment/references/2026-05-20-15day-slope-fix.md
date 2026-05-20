# 2026-05-20: 15日EMA10斜率修正 + 缓存陷阱

## 问题复现

电池板块显示"📉 下降趋势"但用户直觉判断应为上涨。

## 调试路径

1. 检查板块缓存文件 `sector_hist_chgs.json` → 确认电池有17条close数据 ✅
2. 单独运行斜率计算 → e10[-1]=23367, e10[-6]=23670 → 斜率 -1.28% → 下降趋势 ❌
3. **发现根本原因**: slope算的是 `e10[-1] vs e10[-6]`（只跨5天），不是15日视角
4. 改用 `e10[-1] vs e10[0]`（跨15天）→ 斜率 +1.84% → 上涨趋势 ✅
5. 修复 `monitor_data.py` 中的代码
6. 重启服务后API仍然返回旧数据 → 发现二层缓存

## 缓存陷阱

```python
# ❌ 危险模式: server.py 缓存了整个含结构/阶段的结果
cache_file = f'sectors_{今天日期}.json'
if os.path.isfile(cache_file):
    self._serve_file(cache_file)  # 返回旧版代码算的残值！
    return
sectors = get_top_sectors_with_5d()
with open(cache_file, 'w') as f:
    json.dump(sectors, f)  # 下次改代码还会坑
```

**教训**: 结构/阶段是**计算产物**，不应缓存到静态文件。只有原始K线数据（`sector_hist_chgs.json`）可以缓存。每次API请求都应从原始数据重新计算结构和阶段。

## 修复方案

- server.py: 去掉 `/api/monitor/sectors` 的缓存层（删除24行代码），每次都 `get_top_sectors_with_5d()` 重新计算
- monitor_data.py: 斜率对比改为 `e10[-1] vs e10[0]`（15日完整跨度）
- 同时需删除旧的 `sectors_YYYY-MM-DD.json` 缓存文件

# 3L交易系统 — 架构重构方案

## 总原则
1. **每一步只改结构，不改功能** — 重构不引入新逻辑、不改规则
2. **每一步都有验证屏障** — 改前跑全回归 → 改后跑全回归 → diff 必须零差异
3. **允许局部回滚** — 每个阶段独立可撤

---

## 阶段一：配置集中 + 路由规范化
**目标：** 消除硬编码路径，把 do_GET 的 if/elif 换成注册式路由

### 具体操作
1. 创建 `config.py`，把 `server.py`、`generate_review_data.py`、`scripts/` 中散落的路径集中
2. `server.py` 的 `do_GET` 换为路由表：`ROUTES = {'/api/market': handle_market, ...}`
3. `do_POST` 同理

### 正确性保障
- ✅ 全回归第1步（pytest 197项）通过
- ✅ 全回归第3步（前端E2E 8页面）通过
- ✅ 手动 curl 对比每个 API 的 JSON 输出和改前完全一致

### 风险
无——纯机械抽取，无逻辑变更。

---

## 阶段二：抽取 Service 层
**目标：** 把 server.py 中的业务逻辑下沉到 `services/` 目录

### 具体操作
1. 建 `services/` 目录：
   - `services/market_service.py` — 大盘数据、波峰波谷判定
   - `services/review_service.py` — 复盘数据生成（从 generate_review_data.py 抽入）
   - `services/analysis_service.py` — 个股分析
   - `services/watchlist_service.py` — 自选股管理
2. `server.py` 的 Handler 只做：路由 → 参数解析 → 调 Service → 返回 JSON

### 正确性保障
- ✅ 全回归通过（同上）
- ✅ `generate_review_data.py` 从 1384 行瘦身，但行为不变
- ✅ 子进程调 `generate_review_data.py` 的命令行入口保留兼容

### 注意事项
- `generate_review_data.py` 既是库也是 CLI 脚本，重构后保留 CLI 入口（`if __name__ == '__main__'`）
- 现有 cron job 通过 subprocess 调 `generate_review_data.py`，需要保持兼容

---

## 阶段三：回测脚本清理
**目标：** 16个回测脚本 → 保留3个版本 + 1个框架

### 现状
```
backtest_buy_signals.py       ← 最老的
bias_backtest.py              ← 迭代版
bias_entry_backtest.py        ← 迭代版
bias_v2_backtest.py           ← 迭代版
bias_v3_backtest.py           ← 迭代版
bias_v4_backtest.py           ← 迭代版
bias_v5_backtest.py           ← 迭代版（接近当前逻辑）
direction_backtest.py         ← 方向回测
final_backtest.py             ← 最终版
guangxun_backtest.py          ← 单股
trend_bias_backtest_v2.py     ← 趋势回测
trend_definition_backtest.py  ← 定义验证
trend_system_backtest.py      ← 趋势系统
trend_system_backtest_v2.py   ← 趋势系统 v2
backtest_strategy_selector.py ← 策略选择器
gen_backtest_data.py          ← 数据生成
```

### 具体操作
1. 归档旧脚本到 `archive/scripts/`（不删除，可追溯）
2. 保留：
   - `scripts/final_backtest.py` — 3L体系全量回测
   - `scripts/trend_system_backtest_v2.py` — 趋势交易回测
   - `scripts/gen_backtest_data.py` — 数据加载（被上述引用）
3. 其余一律标记为归档

### 正确性保障
- ✅ 保留的两个回测脚本输出与重构前完全一致
- ✅ 归档的删了也不会影响 server / generate_review_data / cron

---

## 阶段四：内联 JS 抽离
**目标：** 页面的 JS 逻辑从 HTML 中分离到独立文件

### 现状
每个 `.html` 文件在 `<script>` 标签中内联了几百行 JS，只有 `nav.js` 和 `stock_card.js` 是共享的。

### 具体操作
1. 建 `js/pages/` 目录
2. 每页抽一个 `.js` 文件，例如：
   - `js/pages/review.js` — 复盘页逻辑
   - `js/pages/monitor.js` — 盯盘页逻辑
   - `js/pages/watchlist.js` — 自选股逻辑
3. HTML 中通过 `<script src="/js/pages/review.js">` 加载

### 正确性保障
- ✅ 全回归第3步（Playwright E2E 截图 + JS报错）通过
- ✅ 增加 `test_stock_card.mjs` 类似的纯函数测试
- ✅ visual diff：截图与重构前像素级对比

---

## 阶段五（可选）：Vue/React 渐进式引入
如果后续页面逻辑越来越复杂，考虑引入轻量框架。当前 vanilla JS 够用，不建议在此阶段做。

---

## 执行顺序建议

```
阶段一  配置集中+路由     → 1天     ← 先搞这个，收益高、风险低
   ↓
阶段二  Service 层抽取    → 2-3天   ← 核心解耦
   ↓
阶段三  回测脚本清理      → 半天    ← 打扫卫生
   ↓
阶段四  JS 抽离          → 1-2天   ← 最后搞前端
```

每个阶段之间发 PR review。

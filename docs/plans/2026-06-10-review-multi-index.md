# 复盘页面多指数支持 — 实施计划

> **分支:** `feat/review-multi-index`
> **目标:** 复盘页大盘区域 Tab化，4指数（中证全指/上证/创业板/科创50）周期判定 + 对比表 + 结论

---

## 改动总览

### 涉及文件

| 层 | 文件 | 改动 |
|:---|:-----|:-----|
| 数据 | `core/data_layer.py` | INDEX_CODES 加 399006 |
| 数据 | `core/update_stock_data.py` | `update_index()` 支持 sz 前缀 |
| 后端 | `services/stock_chart_service.py` | `generate_index_chart()` 参数化 |
| 后端 | `api/market.py` | `_handle_market` 支持 code 参数 |
| 前端 | `components/MarketCycle.tsx` | 重写为 Tab + 对比表 |
| 前端 | `pages/Review.tsx` | 替换 MarketCycle 区域 |
| 前端 | `components/Review.css` | 新增样式 |
| 前端 | `lib/api.ts` | 新增 `fetchIndexData(code)` |
| 测试 | `backend/tests/test_market_api.py` | 新增多指数 API 测试 |
| 测试 | `backend/tests/test_market_cycle.py` | 新增多指数周期判定测试 |
| 文档 | `CHANGELOG.md` | 新增版本记录 |
| 文档 | `docs/plans/2026-06-10-review-multi-index.md` | 本计划文件 |

### 架构原则

1. **数据层改动最小化** — 仅加创业板指数代码+sz前缀，不改现有数据格式
2. **评审复用逻辑** — `judge_peak_valley()` 已函数化，传入任何K线数据即可
3. **前端层次清晰** — MarketCycle 组件内部负责 Tab 切换 + 各Tab内容 + 对比表
4. **API向下兼容** — `/api/market` 无参数时默认返回中证全指

---

## Task 1: 数据层 — 加创业板指到 INDEX_CODES

**Objective:** 数据定义支持创业板指，更新脚本能拉取sz399006数据

**Files:**
- Modify: `server/backend/core/data_layer.py` (INDEX_CODES)
- Modify: `server/backend/core/update_stock_data.py` (sz前缀处理)

**Step 1: 加 INDEX_CODES**

`data_layer.py` 中 `INDEX_CODES` 加上 `'399006': '创业板指'`

**Step 2: update_index() 支持 sz 前缀**

`update_stock_data.py` 中 `update_index()` 的 `ak.stock_zh_index_daily_tx(symbol=f'sh{code}')` 需要判断: 如果 code 以 '399' 或 '300' 开头 → `sz{code}`，否则 `sh{code}`

**Step 3: 手动验证**

运行 `python3 -c "from backend.core.update_stock_data import update_index; update_index(None)"`
或者直接跑 `python3 server/backend/core/update_stock_data.py`

**Step 4: 提交**
```bash
git add server/backend/core/data_layer.py server/backend/core/update_stock_data.py
git commit -m "feat(data): 加创业板指399006到多指数数据管线"
```

---

## Task 2: 后端 API — 多指数市场数据接口

**Objective:** `/api/market?code=000001` 返回指定指数的周期判定结果

**Files:**
- Modify: `server/backend/api/market.py`
- Test: `server/backend/tests/test_market_api.py`

**Step 1: 写失败测试**

```python
# test_market_api.py
def test_handle_market_with_code_returns_index_data():
    """传 code 参数应返回对应指数的周期判定结果"""
```

**Step 2: 实现在 _handle_market**

从 `parse_query(path)` 提取 `code` 参数，传给 `get_index_klines(code)`：
- 无参数 → 默认 000985（中证全指）
- 有参数 → 查询对应指数K线
- 未知code → 返回 400

**Step 3: 提交**
```bash
git add server/backend/api/market.py server/backend/tests/test_market_api.py
git commit -m "feat(api): /api/market 支持 code 参数查询任意指数"
```

---

## Task 3: 后端 — 关键点图参数化

**Objective:** `generate_index_chart()` 支持任意指数代码

**Files:**
- Modify: `server/backend/services/stock_chart_service.py`

**Step 1: 修改函数签名**

`generate_index_chart(mode='review', code='000985')` — 根据 code 确定指数名称和symbol

需要建立符号映射:
```
000985 → sh000985 (中证全指)
000001 → sh000001 (上证指数)
399006 → sz399006 (创业板指)
000688 → sh000688 (科创50)
```

**Step 2: 缓存文件名参数化**

缓存文件从 `zzqz_index_chart_*.svg` 改为 `index_chart_{code}_*.svg`

**Step 3: 更新 API 路由**

`/api/index-chart?code=000001&mode=review` 在 `_handle_index_chart` 中传递 code 参数

**Step 4: 提交**
```bash
git add server/backend/services/stock_chart_service.py server/backend/api/market.py
git commit -m "feat(chart): generate_index_chart 参数化支持多指数"
```

---

## Task 4: 前端 API 层 — 新增 fetchIndexData

**Objective:** 前端 lib/api.ts 新增按code获取指数数据的方法

**Files:**
- Modify: `server/frontend/src/lib/api.ts`

**Step 1: 写类型和函数**

```typescript
// types.ts — MarketData 已存在，无需新增
export function fetchIndexData(code: string): Promise<MarketData> {
  return fetch(`/api/market?code=${code}`).then(r => r.json())
}
```

**Step 2: 提交**
```bash
git add server/frontend/src/lib/api.ts
git commit -m "feat(api): 前端新增 fetchIndexData(code) 方法"
```

---

## Task 5: 前端市场API接口 — 获取多指市场数据

**Objective:** 后端 `/api/market/batch` 或前端并行调用，获取4指数数据

**决策:** 前端并行调用4次 `/api/market?code=XXX`，简单直接。不另写批量接口（YAGNI）。

**Files:**
- Modify: `server/frontend/src/lib/api.ts`

**Step 1: 新增 fetchAllIndexData**

```typescript
export const INDEX_CODES = ['000985', '000001', '399006', '000688']
export const INDEX_NAMES = {
  '000985': '中证全指',
  '000001': '上证指数',
  '399006': '创业板指',
  '000688': '科创50',
}

export function fetchAllIndexData(): Promise<Record<string, MarketData>> {
  return Promise.all(
    INDEX_CODES.map(code =>
      fetchIndexData(code).then(data => ({ code, data }))
    )
  ).then(results => {
    const map: Record<string, any> = {}
    results.forEach(r => { map[r.code] = r.data })
    return map
  })
}
```

**Step 2: 提交**
```bash
git add server/frontend/src/lib/api.ts
git commit -m "feat(api): 前端 fetchAllIndexData 并行加载4指数"
```

---

## Task 6: 前端 MarketCycle 组件 — Tab 重写

**Objective:** 大盘区域改为 Tab 切换 + 对比表

**Files:**
- Rewrite: `server/frontend/src/components/MarketCycle.tsx`
- Modify: `server/frontend/src/pages/Review.tsx`
- Modify: `server/frontend/src/components/Review.css`

**组件结构：**

```
MarketCycle (根容器)
├── TabBar: 4个Tab按钮（中证全指/上证/创业板/科创50）
├── TabContent (当前激活的Tab):
│   ├── InfoGrid (4格: 价格+涨跌 / 周期位置+评分 / 建议仓位 / 策略)
│   ├── [📊评分明细] 展开/收起
│   ├── [📈关键点图] 懒加载
│   └── (资金流向图 × 删除)
└── IndexComparison:
    ├── 对比表（4指数×5列: 涨跌/位置/BIAS20/峰分/谷分）
    └── 对比结论（自动生成文本）
```

**Tab 切换逻辑：**
- 加载时并行获取4指数数据
- Tab切换只切换显示，不重新请求（数据已全量加载）
- 每个Tab的评分明细/关键点图展开状态独立保存（用 Map<code, state>）
- 删除资金流向图相关代码（showFlow state + img标签）

**对比结论算法：**
```typescript
function generateConclusion(indexes: Record<string, MarketData>): string {
  // 1. 找出涨跌幅最高/最低
  // 2. 统计各指数周期位置分布
  // 3. 判断是否分化：位置不同→分化，位置相同→共振
  // 4. 合成一句话结论
}
```

**样式（Review.css）：**
- Tab 样式：横向平铺，激活态高亮（绿色下划线或背景）
- 对比表样式：深色表格，涨跌幅红涨绿跌
- 结论文本样式：带适当留白，结论突出

**Step 1: 先写前端测试**

写一个基本渲染测试（使用 vitest 或现有测试框架）

**Step 2: 重写 MarketCycle.tsx**

**Step 3: 更新 Review.tsx**

将 `MarketCycle />` 替换为新版本。Review.tsx 本身改动很小——只需要确认数据传递方式变了。

**Step 4: 提交**
```bash
git add server/frontend/src/components/MarketCycle.tsx server/frontend/src/pages/Review.tsx server/frontend/src/components/Review.css
git commit -m "feat(ui): 大盘区域Tab化 + 多指对比表 + 结论"
```

---

## Task 7: 验证

**Step 1: 构建前端**
```bash
cd server/frontend && npm run build
```

**Step 2: 重启服务**
```bash
sudo systemctl restart 3l-server
```

**Step 3: 浏览器验证**
- 打开 `/review` 页面
- 点击各 Tab 切换，确认数据正确
- 查看评分明细展开/收起
- 查看关键点图懒加载
- 查看对比表数据是否正确
- 查看对比结论文本

**Step 4: 提交**
```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG — 复盘页多指数支持"
```

**Step 5: 推送 + PR链接**
```bash
git push -u origin HEAD
```

---

## API 数据格式参考

### /api/market?code=000001 返回值
```json
{
  "price": "3350.42",
  "change": 0.85,
  "score": 2,
  "position": "波中",
  "position_pct": "七至八成",
  "strategy": "正常交易，积极选股",
  "build_per_stock_pct": "5%",
  "pk_score": 1,
  "vl_score": 0,
  "bias20": 1.2,
  "bias20_chg_3d": -0.3,
  "data_date": "20260609"
}
```

---

## 验收清单

- [ ] 4个Tab切换正常，数据正确
- [ ] 各指数评分明细可独立展开/收起
- [ ] 关键点图懒加载，不同指数显示不同图表
- [ ] 对比表显示4指数关键指标
- [ ] 对比结论有实际指导意义
- [ ] 已删除资金流向图
- [ ] 后端 API 向下兼容（无code参数=中证全指）
- [ ] 创业板指数据正常拉取和存储
- [ ] 前端构建成功

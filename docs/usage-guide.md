# 3L交易系统 — 使用指南

> 版本: v3.0 | 最后更新: 2026-05-29

---

## 一、页面总览

| 页面 | 路由 | 功能 |
|:-----|:-----|:------|
| 🏠 首页 | `/` | 大盘情绪 + 主线结构 + 快速入口 |
| 📊 复盘 | `/review` | 每日复盘，市场结构/主线/个股信号 |
| 👁️ 盯盘 | `/monitor` | 盘中实时监控，四层模型 |
| 📋 自选股 | `/watchlist` | 自选股管理，方向分组，交易系统 |
| 🎯 趋势候选 | `/trend_candidates` | 自动候选 + 手动管理趋势交易股 |
| 📈 个股分析 | `/stock_analysis` | 3L 量价分析（主 SPA） |
| 📈 个股分析 | `/stock-analysis` | 3L 量价分析（独立页面） |
| 📦 持仓 | `/holdings` | 持仓股管理 |
| 💼 工作台 | `/workbench` | 每日工作流 |
| 🔬 逻辑追踪 | `/logic-tracking` | 逻辑追踪系统 |
| 🛠️ 技能 | `/skills` | 系统技能管理 |

---

## 二、数据更新

### 2.1 自动更新（cron）

每天 17:00（交易日周一至周五）自动执行数据更新管线：

| 阶段 | 内容 | 执行方式（都在 update_stock_data.py 内） |
|:-----|:-----|:---------|
| 1 | 个股 K 线 | mootdx → `data_layer.save_all_stocks()` |
| 2 | 中证全指 + 上证 + 科创50 | mootdx → `data_layer.save_index_data()` |
| 3 | 同花顺行业/概念板块 K 线 | akshare → `data_layer.save_sector_daily()` |

**cron 只拉原始数据，不做计算。** 所有计算（主线排名、个股卡片、复盘分析）由页面首次加载时按需完成。

**cron 配置：**
```cron
0 17 * * 1-5 cd /home/ubuntu/3l-server/server && TQDM_DISABLE=1 \
  /home/ubuntu/3l-server/.venv/bin/python3 \
  -m backend.core.update_stock_data >> /home/ubuntu/3l-server/logs/update.log 2>&1
```

关键路径：
- 工作目录：`/home/ubuntu/3l-server/server`（必须，因为 `backend` 包在此目录下）
- Python：项目自带 venv（`/home/ubuntu/3l-server/.venv/bin/python3`）
- 日志：`/home/ubuntu/3l-server/logs/update.log`

### 2.2 手动触发（cron 失败时用）

当 cron 失效、数据停留在旧日期时，手动执行：

```bash
# 方式一：完整管线（推荐）
cd /home/ubuntu/3l-server/server
TQDM_DISABLE=1 /home/ubuntu/3l-server/.venv/bin/python3 -m backend.core.update_stock_data

# 方式二：仅更新板块（如果个股/指数已最新但板块旧）
cd /home/ubuntu/3l-server/server
TQDM_DISABLE=1 /home/ubuntu/3l-server/.venv/bin/python3 -c "
from backend.core.update_stock_data import update_sectors
update_sectors()
"

# 方式三：仅更新指数
cd /home/ubuntu/3l-server/server
TQDM_DISABLE=1 /home/ubuntu/3l-server/.venv/bin/python3 -c "
from backend.core.update_stock_data import update_index
from mootdx.quotes import Quotes
client = Quotes.factory(market='std')
update_index(client)
"
```

### 2.3 数据新鲜度检查

```bash
# 查看各数据文件的最新日期
python3 -c "
import json, os
files = {
    'all_stocks_60d.json': '个股K线',
    'sector_daily.json': '板块日K',
    'index_sh_data.json': '中证全指',
}
for f, label in files.items():
    p = f'/home/ubuntu/data/3l/{f}'
    if os.path.isfile(p):
        d = json.load(open(p))
        print(f'{label}: {d.get(\"last_updated\",\"?\")}')
"

# 查看 cron 日志
tail -50 /home/ubuntu/3l-server/logs/update.log
```

### 2.4 cron 失效排查步骤

当数据过期时，按顺序排查：

1. **检查 cron 日志**
   ```bash
   tail -50 /home/ubuntu/3l-server/logs/update.log
   ```

2. **检查 crontab 配置**
   ```bash
   crontab -l
   ```

3. **模拟 cron 环境测试**
   ```bash
   PATH=/usr/bin:/bin HOME=/home/ubuntu \
     /home/ubuntu/3l-server/.venv/bin/python3 \
     -c "from backend.config import DATA_DIR; print('OK:', DATA_DIR)"
   ```

4. **验证 mootdx 连接**
   ```bash
   PATH=/usr/bin:/bin HOME=/home/ubuntu \
     /home/ubuntu/3l-server/.venv/bin/python3 -c "
   from backend.core.update_stock_data import _ensure_mootdx_config, _create_mootdx_client
   _ensure_mootdx_config()
   c = _create_mootdx_client()
   print('mootdx OK:', c.server)
   "
   ```

5. **如果全部失败，走手动触发（见 2.2）**

### 2.5 已知坑：目录/路径问题

**cron 反复失败历史（2026-05-30 修复）：** `update_stock_data.py` 在 `server/backend/core/` 下，
sys.path 的 `dirname` 层数必须与文件位置匹配。如果将来文件挪位置，必须同步更新
`sys.path.insert(0, ...)` 中的 `dirname` 层数。

**审计方法：**
```bash
grep -rn 'sys.path.insert.*dirname.*__file__' server/ --include='*.py'
```
逐文件确认：文件位置 → sys.path 目标目录，层数是否正确。

---

## 三、趋势候选管理

### 3.1 自动候选

系统根据主线+次主线行业自动识别趋势候选股票，显示在「自动候选」Tab 中。按行业分组，支持翻页。

### 3.2 手动管理

- **搜索加入**: 在搜索框输入代码/名称/拼音首字母，从自选股中搜索并加入趋势跟踪
- **打勾切换**: 候选列表右侧复选框，可直接加入/移除趋势跟踪
- **配置文件**: `private/manual_trend_stocks.json`

### 3.3 查看趋势股

切换「已跟踪」Tab，查看所有已加入趋势跟踪的股票及其状态。

---

## 四、个股分析

### 4.1 主 SPA 页面 (`/stock_analysis`)

SPA 内的个股分析，含导航栏，支持输入代码回车分析。分析结果使用 `StockCard` 组件展示，包含结构/阶段/均线/信号/买点等。

### 4.2 独立页面 (`/stock-analysis`)

轻量级独立页面，不含导航栏，适合外部引用或嵌入。支持 URL 参数 `?q=300750` 直接分析。

### 4.3 按需数据拉取

搜索不在 cron 数据中的股票时（非自选股/非主线板块成分股），系统自动从数据源拉取 60 天 K 线：

- **数据源优先级**：akshare（HTTP）→ mootdx（通达信回退）
- **缓存**：独立文件 `stock_on_demand_cache.json`，TTL=1 天，最多 30 只
- **行业映射**：自动通过 `stock_industry_map.json` 查行业→方向
- **不影响 cron**：不污染 `all_stocks_60d.json`，cron 17:00 不碰此缓存

适用场景：发现某只不在自选股的股票想快速分析，直接搜代码即可。

### 4.4 个股诊断系统

分析结果新增诊断评分区块，展示三维度评定：

| 维度 | 满分 | 说明 |
|:-----|:----:|:-----|
| 📊 趋势面 | 40 | 结构/阶段/信号/主线/买点/乖离率 |
| 💰 财务面 | 40 | ROE/净利润增长/营收增长/负债率 |
| 🛡️ 风险面 | 20 | 净利润下滑/高负债/流动性/趋势风险 |
| 总分等级 | 100 | A(≥85)/B(70-84)/C(55-69)/D(<55) |

财务数据通过 akshare 拉取，1 小时内存缓存。若 akshare 不可用，财务面降级为 0 分。

### 4.5 API 接口

```bash
GET /api/stock-analysis?q=<代码或名称>
```

返回字段：

| 字段 | 说明 |
|:-----|:------|
| `code`, `name` | 股票代码、名称 |
| `structure` | 结构：上升趋势/下降趋势/震荡 |
| `stage` | 阶段：上行/转强/调整/筑底 |
| `ema5`, `ema10`, `ema20`, `ema30` | 各周期均线值 |
| `deviation_pct` | 乖离率 (BIAS5) |
| `vol_ratio` | 量比 |
| `signal` | 信号：buy/hold/sell |
| `trading_system` | 交易系统：3l/trend |
| `buy_point` | 买点类型 |
| `buy_score` | 买点评分 (0-100) |
| `stop_loss` | 止损位 |
| `stop_loss_pct` | 止损百分比 |
| `risk_reward_ratio` | 盈亏比 |
| `mainline_level` | 主线级别 |
| `sector` | 所属板块 |
| `diagnosis` | 诊断对象（v3.4.0+） |
| `diagnosis.total_score` | 总分 (0-100) |
| `diagnosis.grade` | 等级 A/B/C/D |
| `diagnosis.detail.financial` | 财务评分（含 ROE/增长/负债数据） |
| `diagnosis.detail.trend` | 趋势评分 |
| `diagnosis.detail.risk` | 风险评分（含风险项列表） |
| `diagnosis.cost_ms` | 诊断计算耗时 ms |

---

## 九、报警与微信通知

### 9.1 报警类型

| 等级 | 触发条件 | 说明 |
|:-----|:---------|:------|
| 🔴 止损 | 持仓跌破止损价 | 自动绑定持仓止损价 |
| 🟡 异动 | 核心股涨跌 > 阈值 | 方向管理中配置的核心股 |
| 🟠 大盘预警 | 指数跌 > 3% 或跌破 EMA | 上证/科创50/中证全指 |
| 🔴 系统风险 | 跌 > 3% 且跌破 EMA | 双重确认的风险信号 |

### 9.2 微信通知配置（WxPusher）

系统使用 **WxPusher** 推送到微信，**不依赖 Hermes agent / cron job**。
后端检测到报警触发时直接通过 HTTP API 发送。

**首次配置步骤：**

1. 访问 [wxpusher.zjiecode.com](https://wxpusher.zjiecode.com) 注册
2. 创建一个应用 → 获取 `APP_TOKEN`
3. 将 `APP_TOKEN` 写入 `server/.env`：`WXPUSHER_TOKEN=AT_xxx`
4. 用微信扫应用二维码关注
5. 在用户管理中找到你的 `UID`
6. 打开系统报警音乐配置页 `/alarm-sounds`
7. 在「微信通知配置」区域填写 UID → 保存 → 点「发送测试」验证
8. 验证成功后，所有报警触发时自动推送到你的微信

### 9.3 API 接口

```bash
GET  /api/wxpush/status    # 查看配置状态
POST /api/wxpush/config    # 配置 UID/Token
GET  /api/wxpush/test      # 发送测试消息到微信
```

### 9.4 报警音乐配置

报警音乐配置页 `/alarm-sounds` 支持：

- ▶ 试听各报警类型音乐
- 📁 上传自定义 MP3/WAV 文件替换
- 四种报警独立配置：止损 / 个股异动 / 大盘预警 / 系统风险

---

## 五、自选股管理

### 5.1 方向分组

自选股支持方向分组，可在「方向管理」中创建/编辑/删除分组。

### 5.2 搜索添加

输入代码/名称/拼音首字母搜索个股，点击加入自选股，选择方向分组。

### 5.3 批量操作

- 批量设置方向
- 批量移除
- 排序（支持按涨幅降序）

---

## 六、复盘阅读

### 6.1 页面结构

- **市场概况**: 大盘结构 + 阶段判定 + 波峰波谷
- **主线结构**: 主线/次主线/非主线三梯队
- **个股信号**: 持仓股 + 启用自选股的买点信号和卡片数据
- **历史复盘**: 选择历史日期查看

### 6.2 数据加载

复盘页面只读本地文件，无网络请求。数据由 17:00 cron 预生成。

---

## 七、回归测试

### 7.1 运行全回归

```bash
cd /home/ubuntu/3l-server/server
python3 scripts/run_full_regression.py
```

### 7.2 测试分级

| 等级 | 含义 | 不通过影响 |
|:-----|:-----|:-----------|
| CRITICAL | 必须通过 | 阻塞构建 |
| WARNING | 报告但不阻塞 | 风格漂移、设计覆盖率下降 |
| INFO | 仅日志 | 视觉回归结果 |

### 7.3 查看报告

```bash
# 最新报告
cat /home/ubuntu/3l-server/server/tests/reports/latest.md

# 历史报告
ls /home/ubuntu/3l-server/server/tests/reports/
```

---

## 八、常见操作

### 修改前端后部署

```bash
cd /home/ubuntu/3l-server/server
python3 frontend/build.py   # 构建 React SPA
sudo systemctl restart 3l-server.service
```

### 修改分析服务后部署

```bash
cd /home/ubuntu/3l-server
sudo docker build -t 3l-analysis:latest -f analysis/Dockerfile .
sudo docker restart 3l-analysis
```

### 查看服务日志

```bash
sudo journalctl -u 3l-server -n 100 -f     # 主服务实时日志
sudo docker logs 3l-analysis --tail 50 -f  # 分析服务实时日志
```

### 数据目录结构

```bash
/home/ubuntu/data/3l/
├── all_stocks_60d.json          ← 全量个股 60 日 K 线（cron 更新）
├── all_a_stocks.json            ← 全 A 股代码/名称映射（用于搜索）
├── stock_industry_map.json      ← 个股行业映射
├── stock_on_demand_cache.json   ← 按需拉取缓存（独立于 cron）
├── sector_daily.json            ← 同花顺行业+概念板块日 K 线（cron 更新）
├── index_sh_data.json           ← 中证全指+上证+科创50 K 线（cron 更新）
├── all_sections.json            ← 板块概要
├── watchlist.json               ← 自选股
├── directions.json              ← 方向配置
├── .cache/                      ← 计算缓存（主线排名等）
└── private/                     ← 私有配置
    ├── alarms.json               ← 报警数据
    ├── manual_trend_stocks.json  ← 手动趋势股
    ├── holdings.json             ← 持仓数据
    ├── trades.json               ← 交易记录
    ├── review_data.json          ← 复盘缓存
    └── review_archive/           ← 历史复盘
```

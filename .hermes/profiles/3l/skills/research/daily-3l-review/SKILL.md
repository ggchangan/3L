---
name: daily-3l-review
description: >-
  每日复盘页面（review.html）完整规范 — 6区(大盘/动量/逻辑/持仓/买点/交易计划) + 后端生成器 `generate_review_data.py` + 完整执行流程
---

# 3L 每日复盘页面

## 核心原则

### 🚨 复盘页面扩展第一原则：复用现有模式，不重写（2026-05-21 用户明确要求）

**新功能先看代码库已有实现，按相同风格扩展，不重写。** 用户会对重新发明轮子感到明确不满（"总是喜欢重新写"）。

**具体做法：**
1. **找模板** — 写复盘相关图表脚本先看 `gen_index_chart.py` 的写法（腾讯接口 `stock_zh_index_daily_tx`）
2. **数据源优先用已验证的** — 腾讯接口 > 东方财富接口。腾讯稳定，东方财富连接不稳定
3. **增量修改，不全盘重写** — 用 `git show HEAD:file > /tmp/backup.py` 备份后做 patch
4. **新功能集成到 Step 4** — 所有复盘新功能都放 `generate_review_data.py` 内部，不在 `generate_daily_review.sh` 里加新 Step

**教训（资金流向图四次迭代）：** 曾先后用了行业板块数据、全市场净流入、中证全指成交额、最终才正确。根本原因是每次都在重写而不是参考已有脚本（`gen_index_chart.py` 一直正确使用 `stock_zh_index_daily_tx`）。

## 核心原则

### 复盘页面只展示已完成交易日

**复盘是回顾已收盘的交易日，不是盘中实时工具。** 复盘数据由每日18:00的cron job生成，只有cron生成的数据才算数。

**⛔ 不允许犯的错误（2026-05-21 踩坑）：**
- 交易时段（09:30~15:00）手动运行 `generate_review_data.py` → 生成当天不完整的复盘数据
- 手动生成的当天存档 → 页面显示"今日复盘 ✓" → 但数据是错的（大盘/量价不完整）
- 最终需要删掉当天存档来恢复

**✅ 正确做法：**
- 页面永远从 `/api/review/dates` 取最新存档日期展示
- 18:00 cron跑完后自然就有今天的数据
- 手动跑 `generate_review_data.py` 只应在收盘后，且不加日期参数时自动用当天日期
- **怀疑数据有问题时**：检查 `review_archive/{date}.json` 是否是cron生成的，不是就删掉

## 6区结构

| # | 标题 | 数据源（今日页面） | 数据源（历史页面） |
|:-:|------|---------|---------|
| STEP 1 | 大盘周期判定 | 存档 `market` | 同左 |
| STEP 2 | 最强动量（4 tab） | 实时API `/api/momentum` | 存档 `momentum` + `industry_boards_archive` |
| STEP 3 | 最强逻辑 | 实时API `/api/industry-map` | 存档 `industry_map_archive` |
| STEP 4 | 持仓个股复盘 | 存档 `holdings_review` | 同左 |
| STEP 5 | 自选股买点信号 | 存档 `buy_signals_review` | 同左 |
| PLAN | 每日交易计划 | `trading_plan` | 同左 |

## 完整执行流程（必须按顺序）

### Step 0: 清理旧存档

```bash
rm -f /home/ubuntu/www/private/review_data.json
rm -f "/home/ubuntu/www/private/review_archive/{DATE}.json"
```

### Step 1: 更新缓存 + 扫买点

```bash
python3 /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/daily_update_and_scan.py
```

输出：`all_stocks_60d.json` + `latest_scan_result.json`

**数据源：** mootdx，已统一使用 **前复权（`fq=True`）**。`client.bars(symbol=code, frequency=9, start=0, count=800, fq=True)`

**坑：** 要从缓存最新日一直拉到mootdx最新日，不只拉一天。

**⚡ 2026-05-21 统一前复权：** `daily_update_and_scan.py` 的 `client.bars()` 已加 `fq=True` 参数获取前复权数据。如新建拉取脚本，必须同步加 `fq=True`，否则不复权数据与已存的前复权关键点/支撑线不一致。

### Step 2: 补全股票名称

```bash
python3 /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/fill_stock_names.py
```

通过腾讯API每批20只获取247只以上股票名称，写入每只首条K线的 `"name"` 字段。

### Step 3: 重绘关键点图表

```bash
# 中证全指
python3 /home/ubuntu/www/gen_index_chart.py
cp /home/ubuntu/www/review_charts/sz000985.svg /home/ubuntu/www/review_charts/zzqz_v2.svg

# 个股（买点信号+持仓股+领涨股）
# 区间震荡的股票会自动画绿色支撑线+红色压力线
python3 /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/batch_gen_charts.py
```

**⚡ SVG自动生成已整合：** `daily_update_and_scan.py` 的 `scan_buy_points()` 在扫描完成后自动调用 `batch_gen_charts.py`。`generate_review_data.py` 在保存复盘后也自动调用。日常运行 Step 1 或 Step 4 即可连带生成SVG，无需手动 Step 3。

### ⚠️ 复盘日期应使用上一个完整交易日（2026-05-21 发现）

`generate_review_data.py` 默认使用 `datetime.now().strftime('%Y-%m-%d')` 作为复盘日期。**如果在交易时段运行（09:30~15:00），这会生成当天的错误复盘——当天交易未结束，大盘/量价数据不完整。**

```bash
# ❌ 交易时段运行 → 生成今天的不完整数据
cd /home/ubuntu/www && python3 generate_review_data.py

# ✅ 交易时段运行 → 显式指定上个完整交易日
cd /home/ubuntu/www && python3 generate_review_data.py 2026-05-20

# ✅ 收盘后运行 → 用当天日期
cd /home/ubuntu/www && python3 generate_review_data.py
```

**脚本参数：** `sys.argv[1]` 是日期字符串（如 `2026-05-20`），**不是** `--date` 标志。错误调用 `--date 2026-05-20` 会导致 `date_arg = "--date"`，生成日期错误的复盘。

```bash
cd /home/ubuntu/www && python3 generate_review_data.py {date}
```

**坑：** 上述顺序不可颠倒。get_buy_sell_signals 必须在 buy_signals 重扫之后执行（已修复为自动顺序）。

### 一键脚本（cron job）

见 `/home/ubuntu/.hermes/profiles/3l/scripts/generate_daily_review.sh`

**⚠️ 图表归档已内置在 Step 4 中：** 图表归档（`zzqz_v2.svg`→`archive/{date}/zzqz_v2.svg`、`fund_flow_chart.png`→`archive/{date}/fund_flow_chart.png`）实现在 `generate_review_data.py` 的最后阶段（见下方《图表归档》章节，**目录隔离方案，不用后缀**）。**不要单独写一个归档步骤到 cron 脚本里**——Step 3 画图 → Step 4 自动归档，全流程一体化。

**原则：cron job 处理全量端到端流程，手动操作只用于调试。** 手动跑 `generate_review_data.py` 时也会触发归档和每日成果PDF生成，因此手动测试时不需要额外步骤。

## 关键坑（Pitfalls）

### ⚠️ 持仓不加分页（2026-05-21 用户明确）

STEP 4 持仓个股复盘**只有11只左右，不需要分页**。前端已移除所有分页逻辑（`pgStockPage` / `renderStockPage` / `perPage`），直接 `stocks.map(signalStockCard)` 全部展开。底部只显示"共N只持仓"。

### ⚠️ SVG图表自动生成+扫描后自动同步复盘（2026-05-21 整合+扩展）

`daily_update_and_scan.py` 的 `scan_buy_points()` 在保存扫描结果后自动：
1. 调用 `batch_gen_charts.py` 生成SVG图
2. **调用 `generate_review_data.py` 同步复盘存档**（如果已有存档）

```python
# daily_update_and_scan.py scan_buy_points() 末尾
if os.path.isfile(review_archive_path):
    subprocess.run([sys.executable, gen_script, today_str])
```

这样改数据→扫描→复盘不再脱节，不用手动记着再跑一遍 generate_review_data.py。

### ⚠️ `/api/review/generate` 路由不可达（2026-05-21 发现）

`server.py` 中 `/api/review/generate` 生成API 定义在 line 221，但被 line 155 的 `/api/review/` 通用匹配先拦截：

```python
# line 155 — 先匹配，拦截所有 /api/review/ 后的路径
if path.startswith('/api/review/') and len(path) > 12:
    date_str = path[12:]  # 'generate' → 查 generate.json → 404
    ...

# line 221 — 永远执行不到的代码
if path == '/api/review/generate':
    ...
```

**修复方法：** 将 `/api/review/generate` 的 `if` 判断移到 line 155 的 catch-all `if path.startswith('/api/review/')` **之前**。`generate` 端点必须优先匹配，因为 `generate` 不是合法的存档日期格式。

**临时绕过：** 直接命令行运行 `cd /home/ubuntu/www && python3 generate_review_data.py {date}`。

### ⚠️ server.py 被SYN flood/连接风暴打死（无自动恢复）

`server.py` 使用 `ThreadingHTTPServer`（每个请求一个线程）。2026-05-20 19:04 内核日志显示：
```
TCP: request_sock_TCP: Possible SYN flooding on port 0.0.0.0:8080. Sending cookies.
```
大量连接涌入导致线程爆炸/内存耗尽 → 进程静默退出。**没有任何自动恢复机制。**

**排查步骤（页面挂了先做这个）：**
1. `ss -tlnp | grep 8080` — 看端口是否在监听
2. `ps aux | grep server.py | grep -v grep` — 看进程是否存活
3. `dmesg -T | grep -i '8080\|SYN\|flood'` — 查内核是否检测到洪水
4. 重启：`kill $(cat /home/ubuntu/www/server.pid 2>/dev/null) 2>/dev/null; cd /home/ubuntu/www && python3 server.py &`

**快速重启脚本：** `scripts/restart_server.sh` — 一键杀掉旧进程+启动新进程+验证

**建议加固方案：** gunicorn（worker进程池+连接限流）或添加 systemd 自动重启。

### 4只持仓股不在缓存
大族数控(301200)、宏发股份(600885)、伟创电气(688698)、深圳华强(000062) 最初不在8个方向的自选股池中。必须从mootdx拉取60天K线加入对应方向。

### SVG图表防缓存
`review.html` 中 `<object data="/review_charts/{code}.svg">` 会被浏览器强缓存。必须加时间戳：`?t=${Date.now()}`。三个位置：持仓股(line 634)、买点信号(line 675)、领涨股JS(line 513)。

### 涨幅字段名
`holdings_review` 生成时 `change = h.get('change', 0)` ✅ 不要写成 `h.get('zj_gain', 0)` ❌。buy_signals 存的是 `change` 字段。

### mootdx 前复权数据

`daily_update_and_scan.py` 拉取mootdx数据时使用 **`fq=True`** 参数获取前复权数据：

```python
bars = client.bars(symbol=code, frequency=9, start=0, count=800, fq=True)
```

**注意：** `market-scan-workflow` skill 下的同名脚本也需同步修改。

### 区间震荡股票阶段用关键点支撑重算

`generate_review_data.py` 生成 `holdings_review` 时，对 `structure='区间震荡'` 的股票执行额外步骤：

1. 从 all_stocks_60d.json 取完整K线
2. 找所有"突"关键点的 `support_price`（突破前10日最高价）
3. 从高到低排列，取第一个距当前价≥1.5%的作为支撑
4. 全部支撑被过滤才回退到20日最低
5. 用（支撑, 15日最高）计算位置百分比，重写 stage
6. 再传入 `judge_signal()` 判断信号

参考实现见 `generate_review_data.py` 第644-667行（2026-05-21版本）。

### signal 统一由 judge_signal 判定（2026-05-21）

`holdings_review` 中 `signal` 字段（buy/hold/sell）由后端 `generate_review_data.py` 调用 `judge_signal(structure, stage, buy_point)` 统一生成。

```python
# generate_review_data.py 核心改动
code_sig, _, _ = judge_signal(structure=structure, stage=stage, buy_point=h['action'])
buy_point = h['action'].split()[0] if code_sig == 'buy' and h['action'] else ''
holdings_review.append({
    'signal': code_sig,       # buy / hold / sell
    'buy_point': buy_point,   # 仅code_sig=='buy'时填充
    ...
})
```

**关键点：**
- `signal_text` 已废弃（2026-05-21 用户确认删除），前端仅用 `signal` 代码渲染 `✅持有`/`⚡买入`/`❌卖出`
- 买点仅在 `signal='buy'` 时保留（`h['action'].split()[0]` 取类型名，不带flags）
- 卖出>买入>持有优先级由 judge_signal 保证

前端渲染（无 signal_text 依赖）：
```javascript
const signalText = s.signal === 'hold' ? '✅持有' : s.signal === 'buy' ? '⚡买入' : s.signal === 'sell' ? '❌卖出' : '--';
```

### ⚠️ latest_scan_result.json vs scan_buy_signals.py 两套扫描结果不同步（2026-05-21 发现→修复）

复盘页面的买点数据来自 `latest_scan_result.json`（`daily_update_and_scan.py` 通过 `buy_point_detection.py` 生成的），而小时级缓存（`data/cache/buy_signals_*.json`）来自 `scan_buy_signals.py`。

**2026-05-21 修复：** `scan_buy_signals.py` 已改为调用 `buy_point_detection.detect_buy_point()`（同复盘页面统一算法），不再使用自己的机械条件。`data/cache/buy_signals_*.json` 目前与 `latest_scan_result.json` 使用同一判定逻辑，仅数据源不同（实时腾讯API vs 缓存mootdx）。

```python
# latest_scan_result.json — 3层阈值框架（review页面用的）
daily_update_and_scan.py
  → buy_point_detection.detect_buy_point(market_position=波中偏上, main_lines=['半导体',...])
  → 缩量阈值 = 基准确(大盘) × 板块系数(主线×1.05/非主线×0.80)
  → 永鼎(通信设备=非主线) → 基准84% × 0.80 = 67%
  → 若量比68% > 67% → 不通过 ❌

# data/cache/buy_signals_*.json — 简单机械条件（小时扫描用）
scan_buy_signals.py
  → check_zhongji_buy(): MA20回踩 + MA5>MA10 + 缩量<1.2倍 + 涨幅<5%
  → 永鼎(缩量OK) → 中继买点 ✅
```

**排查思路：** 用户说"之前是买点现在没了"，先确认用户说的是复盘页面还是实时扫描结果，再看用的是哪套系统。复盘页面始终用 `latest_scan_result.json`，实时问询用 cache 中的 buy_signals。

**修复方法：** 重新运行 `daily_update_and_scan.py`（会重算 `latest_scan_result.json`）。如果主线判别已修改（如本次会话），必须重跑才能让复盘页面反映新逻辑。

`generate_review_data.py` 加载 buy_signals 的优先级：

1. **优先**从 `latest_scan_result.json` 读取（已应用最新阈值+市场位置）
2. 回退到 `existing` 存档的 `buy_signals` 字段

```python
# generate_review_data.py — 每日扫描结果优先
latest_scan_path = '/home/ubuntu/data/3l/latest_scan_result.json'
if os.path.isfile(latest_scan_path):
    with open(latest_scan_path) as _f:
        _scan = json.load(_f)
    _scan_results = _scan.get('results', [])
    if _scan_results:
        buy_signals = [...]  # 格式转换
```

**市场位置传入链路（2026-05-21 新增）：**
当触发 fallback 扫描路径（`format_buy_signals()`）时，`market_cycle.get('position')` 作为 `market_position` 参数传入，使扫描阈值与当前大盘环境匹配。

**坑：** 早期版本仅从 existing 存档加载 buy_signals，若存档有数据则跳过重新扫描。导致 `daily_update_and_scan.py` 的阈值或数据更新无法反映到复盘页。**读 `latest_scan_result.json` 修复了这个问题。**

#### 每日复盘完整刷新流程（主线判定变更后必须执行）

⚠️ 自动同步：从 2026-05-21 起，daily_update_and_scan.py 的 scan_buy_points() 在扫描完成后自动调用 generate_review_data.py 更新复盘存档。所以日常只需：

```bash
python3 .../daily-3l-review/scripts/daily_update_and_scan.py
```

复盘数据会自动更新，无需手动再跑 generate_review_data.py。

**但是（重复犯错陷阱）：** 修改了以下数据后，扫描+复盘不会自动更新，必须手动重跑：
- all_stocks_60d.json volume 手动修正
- watchlist.json 自选股增减
- 主线判定逻辑变更
- buy_point_detection.py 算法改动

**手动刷新（当自动同步没触发或数据不一致时）：**
```bash
# 1. 重跑扫描（用最新主线判定）
python3 /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/daily_update_and_scan.py --scan-only
# 2. 重新生成复盘
cd /home/ubuntu/www && python3 generate_review_data.py {date}
# 3. 重启服务
kill $(cat /home/ubuntu/www/server.pid 2>/dev/null)
cd /home/ubuntu/www && python3 server.py
```

**daily_update_and_scan.py 独立扫描时的市场位置获取（2026-05-21）：**
- 优先读取已有 review 存档的 `market.position`。**注意路径：** 存档在 `private/review_archive/2026-05-21.json`（YYYY-MM-DD格式），不是 `review_output/{date}/review.json`。`daily_update_and_scan.py` 已修复为两路径都尝试，YYYYMMDD转YYYY-MM-DD。\n- 无存档时从 000985 中证全指K线估算（收盘价/MA20偏离）\n- 估算失败时默认波中（80%阈值，非主线0.80系数下=64%）\n- 输出：控制台打印 `大盘位置: 波中偏上 缩量阈值: <89%  主线板块: 半导体, ...`

### 股票名称缺失

### 股票名称缺失
`all_stocks_60d.json` 首条必须含 `name` 字段，否则 `format_buy_signals` 回退为代码。

### ⚠️ batch_gen_charts.py 支撑线算法

`batch_gen_charts.py` 生成的个股SVG中，区间震荡股票会画绿色支撑线+红色压力线。

**支撑线算法：** 取最近且位于当前价下方的"突"关键点，用其 `support_price`（前10日最高价，即被突破的阻力位），**而非** `y`（突破日最高价）。距当前价不足1.5%的支撑位会被过滤，取下一档或20日最低。

**实例（深圳华强 2026-05-20）：**
- 突破日最高34.34 → ❌ 支撑34.34（距收盘0.07）
- 前10日最高33.10 → ✅ 支撑33.10（距收盘3.8%）

**⚡ 数据源复权影响：** `all_stocks_60d.json` 数据来自 mootdx（不复权），支撑线价格基于此。腾讯（前复权）的历史价格可能有0.5-1元偏差。详见 `a-stock-data-sources` 的 `references/mootdx-vs-tencent-fuquan.md`。

详见 `a-stock-kline-keypoint-chart` skill 的支撑线章节。
**不要**在 `batch_gen_charts.py` 内自己写结构判断算法（方向比法/涨天数比法）。
必须从 `ema10-trend-judgment/scripts/ema_utils.py` import `get_structure`，与复盘页和盯盘页使用完全一致的**极值位置法**。

错误历史：2026-05-21 我用了方向比法（EMA10涨/跌计数，ratio=0.39判定为区间震荡），但 ema_utils 的极值位置法判定为上涨趋势。两种算法给出了不同结果，被用户当场发现。

正确写法：
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'trading', 'ema10-trend-judgment', 'scripts'))
from ema_utils import get_structure
structure = get_structure(closes)
```

### ⚠️ all_stocks_60d.json vol 字段名（2026-05-21 踩坑）

`all_stocks_60d.json` 的K线数据用 `volume` 字段存成交量，而不是 `vol`。但 `get_buy_sell_signals()` 中曾误写为：
```python
vols_60 = [k.get('vol', 0) for k in _kls]  # ❌ 永远为0
```
导致量能分析全为0，`vol_prev10 > 0` 条件不满足，国际复材量缩到65%却无法判为"缩量整理"。

**修复：** `k.get('volume', k.get('vol', 0))` 双字段兼容。

### ⚠️ mainline_data 结构变更（2026-05-21）

`get_mainline_data()` 返回的结构从：
```python
{'lines': [{'name': '半导体', 'score': 27.1, 'change': 2.71, 'leader': '...'}]}
```
改为三梯队：
```python
{
  'lines': [{'name': '电子化学品', 'chg_20d': 37.57}, ...],      # 前5主线
  'secondary': [{'name': '消费电子', 'chg_20d': 9.38}, ...],     # 6~10次级
  'industries': [...],                                            # 今日排行（展示用）
  'all_ranked': [...]                                              # 全排序
}
```

**影响：** 
- `line['score']` 不再存在 → 使用 `line['chg_20d']`
- `classify_stocks_by_mainline()` 返回 `{'mainline':[], 'secondary':[], 'non_mainline':[]}`
- 持仓/候选中的通信设备行业股票自动归入 `secondary`
- 前端 logic_classify 区块需适配三分类渲染

### ⚠️ daily_update_and_scan.py 必须同步读取 secondary 主线（2026-05-21 踩坑）

`daily_update_and_scan.py` 从 review 存档读取 `main_lines_list` 时，**只读了 `lines`（前5），没读 `secondary`（6~10）**。导致通信设备等次级主线板块的股票（如永鼎股份）在扫描时被当作非主线，使用严阈值被过滤掉。

**修复（对应代码第159行）：**
```python
# ❌ 错误 — 只读前5主线
main_lines_list = [l['name'] for l in _rd.get('mainline', {}).get('lines', [])]

# ✅ 正确 — 主线+次级主线全传
main_lines_primary = [l['name'] for l in _rd.get('mainline', {}).get('lines', [])]
main_lines_secondary = [l['name'] for l in _rd.get('mainline', {}).get('secondary', [])]
main_lines_list = main_lines_primary + main_lines_secondary
```

**影响：** 主线判定逻辑变更后（如单日法→20日涨幅三梯队），必须：
1. 重新生成复盘数据（`generate_review_data.py`）
2. 重新运行扫描（`daily_update_and_scan.py`）
3. 再生成复盘数据（刷新 `buy_signals`）
否则旧的扫描结果不会自动反映新主线。`latest_scan_result.json` 在扫描时绑定了当时的 `main_lines` 和 `market_position`。

`holdings_review` 中不再包含 `signal_text` 字段。前端 `signalStockCard()` 操作字段仅通过 `s.signal` 代码（buy/hold/sell）渲染简短符号：`✅持有` / `⚡买入` / `❌卖出`，无冗余描述文字。结论文字独立于操作信号，由前端按 stage 生成详细的量价分析结论。

### ⚠️ 买点字段仅信号为buy时显示

`holdings_review` 的 `buy_point` 字段在 `generate_review_data.py` 中统一由 `judge_signal()` 控制：仅当 `code_sig == 'buy'` 时才保留买点类型（突破买点/中继买点），否则为空字符串。前端 `signalStockCard()` 根据 `s.buy_point` 非空才渲染买点字段，因此诊断卡上买点只出现于买入信号股票。

**前后端联动：**
```python
# generate_review_data.py
code_sig, signal_text, _ = judge_signal(structure, stage, h['action'])
buy_point = h['action'] if code_sig == 'buy' else ''   # 仅buy时保留
```
```javascript
// review.html signalStockCard()
${s.buy_point ? `<div class="field"><span class="l">买点:</span> <span class="v">${s.buy_point}</span></div>` : ''}
```

### ⚠️ UI改版第一原则：不得减少已有信息（2026-05-21 用户明确要求）

改复盘页面诊断卡时，第一次只保留了阶段+EMA+量能+结论，移除了买点和操作信号。**用户要求恢复全部原有字段。** 最终诊断卡展示7个字段：买点+操作+结构+阶段+EMA+量能+结论，并新增了结论文字。

**原则：新增字段是补充，不能替代已有字段。** 任何UI改版，必须先列出所有已有字段，确保全部保留，再考虑怎么加新内容。

### ⚠️ 重写 generate_review_data.py 需保留 fetch_* 函数

`generate_review_data.py` 包含 `fetch_index_klines()` 和 `fetch_market_quote()` 两个非业务函数，在 main 流程中调用。当整个文件被重写（如用 `skill_manage(write_file)` 全文覆盖）时，这两个函数必须保留，否则 generate_daily_review() 会报 `NameError`。

**保险做法：** 从 git 版本做 patch 增量修改，而非手写全文覆盖。
```bash
cd /home/ubuntu/www
git show HEAD:./generate_review_data.py > /tmp/gen_orig.py
# 在 /tmp/gen_orig.py 上做 patch，确认无误后 cp 回
```

`generate_review_data.py` 第581行从腾讯财经补拉K线时，volume字段单位是**手**(lot)：
```python
'volume': int(float(latest_k[5]) * 100),  # 腾讯财经×100转股
```
**永远不要删掉`* 100`。** 这个bug在2026-05-21又犯了一次，导致德业股份在突破日量比=0.03（正常应为1.3+），买点条件②放量永远不满足。

### ⚠️ mootdx volume 单位：手→股（2026-05-21 两轮踩坑）

`daily_update_and_scan.py` 从 mootdx 拉取 volume 时，原始数据为 **手（手）**，1手=100股。保存到 `all_stocks_60d.json` 时必须 ×100 转为 **股**。

```python
# ✅ 正确：mootdx返回手, 缓存存股
"volume": int(float(row["volume"]) * 100)
```

**2026-05-21 两轮踩坑：**

- **第1轮**：忘记 ×100，5/21新数据的 volume 全部为正常值的 1/100 → vol_analysis 中的量比错乱
- **第2轮**：局部 ×100 只修复 5/21 日行，但部分持仓股（伟创电气/大族数控/多氟多等6只）的老数据之前也是未×100的原始值，造成量比爆炸（如 5603% 放量）

**最终修复方案（2026-05-21）：**

对比 mootdx 原始 volume 与缓存存量 volume，统一全部 ×100：

```python
# 对每只股票，判断存量数据单位：
# 若 cache_5_20 / mootdx_5_20 ≈ 100 → 存量已是股 → 5/21也得×100
# 若 cache_5_20 / mootdx_5_20 ≈ 1   → 存量是手 → 全部×100
```

结果：245/251 只存量已是股（×100），仅 6 只需要补 ×100。`daily_update_and_scan.py` 的 `"volume": int(float(row["volume"]) * 100)` 已固化。

修复脚本：`references/fix-volume-unit.py` — 检测缓存中最后2天volume < 前10日均量20%的异常数据，自动×100修复。

### ⚠️ cron脚本路径错误（2026-05-21 发现）

`~/.hermes/profiles/3l/scripts/generate_daily_review.sh` 的 Step 1 路径曾误写为：
```bash
# ❌ 错误 — 路径不存在，cron静默跳过数据更新
python3 .../a-stock-daily-scan/scripts/daily_update_and_scan.py
# ✅ 正确路径
python3 .../daily-3l-review/scripts/daily_update_and_scan.py
```

**排查：** 复盘页面数据不对、量价异常时，先跑 cron 脚本看 Step 1 是否有 `No such file` 错误。
**修复：** `a-stock-daily-scan` → `daily-3l-review`

### ⚠️ 动量数据缓存全天锁死（2026-05-21 发现+修复）

`/api/momentum` 服务端（server.py）使用 **每日首次请求后全天缓存** 策略。如果首次请求在盘中（如09:30），全天的涨停/新高数据就被锁死在盘中状态。`generate_review_data.py` 归档时读取的是同一份缓存。

**后果：** 收盘后生成的复盘 → 涨停/新高数目是盘中的旧数据。

**⚠️ 碎片化修复陷阱（2026-05-21 教训）：**
- ❌ 仅删除缓存不够 → 复盘内部 `fetch_momentum.py` 若失败直接丢失动量数据
- ✅ 正确做法：**清缓存 → 先显式拉取新鲜数据存入缓存 → 再跑复盘**

**已修复：** `generate_daily_review.sh` Step 4 改为先清缓存→显式拉取→验证成功→再跑复盘。`generate_review_data.py` 内部保留fallback但一般不会触发。

**手动修复方法（收盘后复盘数据不对时）：**
```bash
rm -f /home/ubuntu/www/data/cache/momentum_$(date +%Y-%m-%d).json
cd /home/ubuntu/www && python3 fetch_momentum.py > /home/ubuntu/www/data/cache/momentum_$(date +%Y-%m-%d).json
rm -f /home/ubuntu/www/private/review_archive/$(date +%Y-%m-%d).json
cd /home/ubuntu/www && python3 generate_review_data.py $(date +%Y-%m-%d)
```

### ⚠️ fill_stock_names.py 文件行号污染（2026-05-21 发现）

`fill_stock_names.py` 文件内容带入了 `1|     1|#!/usr/bin/env python3` 行号前缀，导致 IndentationError 无法运行。

**根因：** 使用 `read_file(offset=N)` 分页读取后，用 `write_file` 写入时未去掉行号。
**检测：** 运行 Step 2 时报 `IndentationError: unexpected indent`。
**修复：** 重写文件（去掉行号前缀）或 `head -1 | grep '^\s'` 检查首字符是否空白。

### 中证全指数据源
- **正确：** `sh000985`（中证全指，~6500）
- **错误：** `sz000985`（大庆华科，~18）

## 交易计划标准（2026-05-21 升级为3L体系版）

### 后端生成 `generate_trading_plan()`

位于 `generate_review_data.py`，使用 `holdings_review` + `buy_signals_review` 生成4个区块。

**个股操作9种映射规则：**

| signal/stage | 操作建议 | 优先级 |
|:-----------:|:--------:|:-----:|
| `sell` | 卖出 | 高 |
| `buy` | 执行{买点} | 高 |
| 加速 | 持有·关注止盈 | 中 |
| 缩量整理 | 持有·可加仓 | 中 |
| 上行 | 持有不动 | 低 |
| 滞涨 | 警惕·考虑减仓 | 高 |
| 转弱 | 关注·可换股 | 高 |
| 区间底部 | 支撑位·可加仓 | 中 |
| 区间顶部 | 压力位·注意减仓 | 高 |
| 区间中段 | 等待方向 | 低 |

**买点6级优先级：** 主线突破+盈利1 > 主线突破 > 主线中继+盈利1 > 主线中继 > 非主线突破 > 非主线中继。同级按涨幅降序，取TOP10。

### 前端渲染 `updateTradingPlanUI()`

操作项带左色条（红=高优/黄=中/灰=低），买点区显示`主线`标签+`🏆`盈利1徽章。

### 脚本路径

| 脚本 | 路径 |
|------|------|
| 更新缓存+扫买点 | `daily-3l-review/scripts/daily_update_and_scan.py` |
| 补全股票名 | `daily-3l-review/scripts/fill_stock_names.py` |
| 重启Web服务 | `daily-3l-review/scripts/restart_server.sh` |
| 中证全指关键点图 | `/home/ubuntu/www/gen_index_chart.py` |
| 全市场资金流向图 | `/home/ubuntu/www/gen_fund_flow_chart.py` |
| 批量个股图 | `daily-3l-review/scripts/batch_gen_charts.py` |
| 复盘生成器 | `/home/ubuntu/www/generate_review_data.py` | — 含Step 5自动生成每日成果PDF |
| cron脚本 | `~/.hermes/profiles/3l/scripts/generate_daily_review.sh` |

## 存档系统

- 目录：`/home/ubuntu/www/private/review_archive/`
- API: `/api/review/{date}` GET, `/api/review/dates` GET

### 历史复盘列表（2026-05-21 重写）

**原则：历史列表排除当前展示日期，不排除"今天"。**

```
当前展示 2026-05-20 → 历史列表排除 05-20 → 显示 05-19（1条）
查看历史 ?date=2026-05-19 → 历史列表排除 05-19 → 显示 05-20（1条）
```

**实现：** `loadHistoryList(currentDisplayDate)` 接收当前展示的日期参数，`checkUrlParam()` 传入 `dateParam`，`loadLatestReview()` 传入 `latest`。

```javascript
function loadHistoryList(currentDisplayDate) {
    const curDate = currentDisplayDate || ...;
    const dates = allDates.filter(d => d !== curDate);  // 排除当前，不是排除"今天"
}
```

**错误历史：** 原来写死 `filter(d => d !== today)`（排除"今天"）。当查看历史页面（如 05-19）时，05-19 自己还在历史列表里（因为它不是"今天"），而 05-20 反而不在列表里（被"今天"排除条件误伤）。

#### 日加载逻辑（2026-05-21 重写 → 2026-05 18点降级）

**铁律：复盘页面只展示已完成交易日（已收盘）的数据。** 如果在18:00之前访问页面，即使当天有了存档（比如有人盘中手误跑了生成脚本），也必须**自动降级到上一个交易日**。

**最终实现（review.html `loadLatestReview()`）：**
```javascript
const today = `${y}-${m}-${d}`;
const nowHour = new Date().getHours();
let latest = dates[0];
// 如果最新日期是今天，但还没到18:00（cron未运行），自动降级到上一个交易日
if (latest === today && nowHour < 18 && dates.length > 1) {
    latest = dates[1];
}
const isToday = latest === today;
```

**行为：**
```
收盘前（<18:00）→ 即使dates[0]=今天 → 降级到dates[1]=昨天 → "每日复盘（收盘后自动更新）"
收盘后（≥18:00）→ cron刚跑完 → dates[0]=今天 → 正常显示 → "今日复盘 ✓"
```

**⛔ 重复犯错的教训（2026-05-21 已发生两次）：**
- 第一次写好了降级逻辑，后来改 `loadLatestReview()` 时**把时间判断删掉了**，直接取 `dates[0]`
- 用户发现后质问：这个逻辑上次不是说过了吗？怎么又改了
- **根因：** SKILL.md 只记录了原则（永远展示最新已有数据的日期），没有记录18:00前降级的具体实现
- **防止再犯：修改 review.html 的 loadLatestReview() 时，必须保留18:00前的降级逻辑。** 这是用户明确要求的行为，不是可选的优化。
- **Skill文档不等于代码实现：** 2026-05-21 降级规则写入skill文档后，review.html实际代码一直没改——规则存在skill纯文字里但前端从不执行。改完skill必须立即确认实际代码已更新并git commit验证。

服务端：`server.py` 的 `/api/review/dates` 加了 `re.match(r'^\d{4}-\d{2}-\d{2}\.json$')` 正则过滤，排除 `--date.json` 等非法文件名（2026-05-21 发现 `--date.json` 因 parse 错误写入的脏数据混入日期列表）。

### ⚠️ 资金流向图 vs 成交额（2026-05-21 踩坑）
**资金流向（主力净流入/净流出）≠ 成交额。** 初版错误地用了成交额/成交量替代，被用户纠正。
- 上图：全市场主力净流入（亿元），数据源 `akshare.stock_market_fund_flow()` 主力净流入-净额
- 下图：中证全指涨跌幅，数据源 `akshare.stock_zh_index_daily_tx(symbol='sh000985')`
- 标题统一为"中证全指资金流向"
- 颜色：红涨绿跌（正值红色`#e94560`，负值绿色`#4CAF50`）

**三次迭代教训：** 资金流向图曾先后用了行业板块数据、成交额数据，都被用户纠正。终版统一使用中证全指数据源，与关键点图一致。**同图同源。**

### ⚠️ 新功能集成原则：复用现有模式，不重写（2026-05-21 用户明确）

用户要求：**按已有的写法写，不要重新发明轮子。** 新功能应先查看代码库中类似功能的实现模式，再按相同风格扩展。

**错误做法（本会话踩坑）：**
- 资金流向图先后尝试了3种不同数据源，每次都是全部重写
- 应该一开始就参考 `gen_index_chart.py` 的写法（`stock_zh_index_daily_tx` 腾讯接口）

**正确做法：**
1. 先看现有脚本怎么写的（`gen_index_chart.py` 就是好模板）
2. 数据源优先用代码库已验证的（腾讯接口 > 东方财富接口）
3. 增量修改，不是全盘重写

同时：**新功能集成到 `generate_review_data.py`，不加 cron 步骤。**
当前已集成到 Step 4 的功能：`batch_gen_charts.py`、`gen_fund_flow_chart.py`、图表归档。

### ⚠️ toggleIndexChart() 的 `!display` 假阳性（2026-05-21 踩坑）
```javascript
// ❌ 错误 — 当 display=''（显示状态）时，!'' 为 true，视为隐藏
const isHidden = chart.style.display === 'none' || !chart.style.display;
// ✅ 正确 — 只判断是否为 'none'
const isHidden = chart.style.display === 'none';
```
`chart.style.display` 初始为 `'none'`（HTML inline style），展开后被设为 `''`（空字符串）。`!''` 返回 `true`，导致已展开的图表第二次点击无法收起。

### ⚠️ TQDM_DISABLE 必须在 import akshare 之前（2026-05-21）
`os.environ['TQDM_DISABLE'] = '1'` 如果在 `import akshare` 之后设置，不生效。进度条会污染日志输出。
```python
import os
os.environ['TQDM_DISABLE'] = '1'  # ✅ 在这里
import akshare as ak
```

### ⚠️ A股图表颜色铁律（2026-05-21 踩坑）
红涨绿跌。资金流向图、K线图等所有图表统一。
```python
# ✅ 正确：负值绿色，正值红色
colors = ['#4CAF50' if v < 0 else '#e94560' for v in values]
```

**方案：目录隔离，不改文件名。** 不使用后缀区分，而是把每天的图表拷贝到 `review_charts/archive/{date}/` 子目录：

```
review_charts/zzqz_v2.svg                        ← 最新（每天覆盖）
review_charts/archive/2026-05-19/zzqz_v2.svg     ← 历史归档（名称不变）
review_charts/archive/2026-05-19/fund_flow_chart.png
review_charts/archive/2026-05-20/zzqz_v2.svg
review_charts/archive/2026-05-20/fund_flow_chart.png
```

**⚠️ 不能用 `/private/` 目录：** 这个目录下的静态文件需要 Basic Auth，但 `<img>` 和 `<object>` 标签加载图片时**浏览器不会自动发送 auth header**，导致显示 401。归档图表必须放在**公共目录**（`review_charts/archive/` 或 `charts/archive/`）下。

**后端（`generate_review_data.py`）：**
```python
chart_archive_dir = os.path.join(WWW_DIR, 'review_charts', 'archive', date_str)
os.makedirs(chart_archive_dir, exist_ok=True)
shutil.copy2('/home/ubuntu/www/review_charts/zzqz_v2.svg',
              os.path.join(chart_archive_dir, 'zzqz_v2.svg'))
shutil.copy2('/home/ubuntu/www/charts/fund_flow_chart.png',
              os.path.join(chart_archive_dir, 'fund_flow_chart.png'))
review['charts'] = {
    'index_chart': f'/review_charts/archive/{date_str}/zzqz_v2.svg',
    'fund_flow': f'/review_charts/archive/{date_str}/fund_flow_chart.png',
}
save_json(os.path.join(ARCHIVE_DIR, f'{date_str}.json'), review)
```

**前端：** `loadReviewData()` 检测 `data.charts`，有则替换图表src：
```javascript
if (data.charts) {
    document.getElementById('indexChartObj').data = data.charts.index_chart;
    document.getElementById('fundFlowImg').src = data.charts.fund_flow;
} else {
    // 今日页面回退到默认路径
    document.getElementById('indexChartObj').data = '/review_charts/zzqz_v2.svg';
    document.getElementById('fundFlowImg').src = '/charts/fund_flow_chart.png';
}
```

**⚠️ 资金流向图 vs 成交额（2026-05-21 踩坑）：** 资金流向（主力净流入/净流出）≠ 成交额。初版错误地用了成交额/成交量替代，被用户纠正。终版使用 `stock_market_fund_flow()` 的 `主力净流入-净额`。
- 上图：全市场主力净流入（亿元），数据源 `akshare.stock_market_fund_flow()` 主力净流入-净额
- 下图：中证全指涨跌幅，数据源 `akshare.stock_zh_index_daily_tx(symbol='sh000985')`
- 标题统一为"中证全指资金流向"
- 颜色：红涨绿跌（正值红色`#e94560`，负值绿色`#4CAF50`）
- 图表由 `gen_fund_flow_chart.py` 生成，`generate_review_data.py` 传入 `date_str` 参数确保数据截止到复盘日期。归档时复制到 `archive/{date}/` 目录。

**同步坑：** `gen_fund_flow_chart.py` 的数据源必须稳定。曾用 `stock_zh_index_daily_em()`（东方财富）因连接不稳定切换回 `stock_zh_index_daily_tx()`（腾讯）。优先用腾讯接口。`TQDM_DISABLE=1` 必须写在 `import akshare` 之前才能关掉进度条。`get_zzqz_data()` 和 `get_fund_flow()` 函数名在 `gen_fund_flow_chart.py` 内已定义，不要在脚本外重复引用。

**三次迭代教训：** 资金流向图曾先后用了行业板块数据（stock_board_industry_summary_ths）和全市场净流入数据（stock_market_fund_flow），都被用户纠正。终版统一使用中证全指自身数据源，与关键点图一致。

**⚠️ A股图表颜色铁律（2026-05-21 踩坑）：** 红涨绿跌。资金流向图：红色=净流入(涨)，绿色=净流出(跌)。代码写法：
```python
# ✅ 正确
colors = ['#4CAF50' if v < 0 else '#e94560' for v in values]
# ❌ 错误（初版犯了此错）
# colors = ['#e94560' if v < 0 else '#4CAF50' for v in values]
```

**资金流向图结构：** 双面板暗色背景。上图=中证全指每日成交额柱状图（红涨绿跌，涨日红色，跌日绿色），下图=中证全指涨跌幅折线。**数据源统一使用 `akshare.stock_zh_index_daily_em(symbol='sh000985')`**，与中证全指关键点图（gen_index_chart.py）数据源一致。不要用行业板块数据（`stock_board_industry_summary_ths`）或全市场汇总（`stock_market_fund_flow`）。

**数据源切换历史（2026-05-21 四次迭代）：**\n1. ❌ 初版用了 `stock_board_industry_summary_ths()`（行业板块）→ 用户纠正"资金流向是中证全指"\n2. ❌ 二版改为 `stock_market_fund_flow()`（全市场主力净流入）→ 但面板2用了上证指数，数据源不统一\n3. ❌ 三版改为 `stock_zh_index_daily_tx('sh000985')` 成交额→ 用户纠正"成交额不是资金流向"\n4. ✅ 终版：上图 `stock_market_fund_flow()` 主力净流入, 下图 `stock_zh_index_daily_tx('sh000985')` 涨跌幅，统一标"中证全指"

**✅ 铁律：** 同图同源。资金流向图和中证全指关键点图都用 sh000985 一个数据源。不混用上证/深证/行业数据。

### toggleIndexChart() 的 `!display` 假阳性（2026-05-21 踩坑）

```javascript
// ❌ 错误 — 当 display=''（显示状态）时，!'' 为 true，视为隐藏
const isHidden = chart.style.display === 'none' || !chart.style.display;

// ✅ 正确 — 只判断是否为 'none'
const isHidden = chart.style.display === 'none';
```

`chart.style.display` 初始为 `'none'`（HTML inline style），展开后被设为 `''`（空字符串）。`!''` 返回 `true`，导致**已展开的图表点第二次无法收起**。`toggleChart()` 和 `toggleEl()` 都只用 `=== 'none'` 判断。

### fund_flow_chart.png 数据源：全市场主力净流入 + 中证全指涨跌幅\n\n`gen_fund_flow_chart.py` 使用两个数据源（逻辑统一于「中证全指」标签下）：\n\n**上图：** 全市场每日主力净流入/净流出柱状图（亿元）\n- `akshare.stock_market_fund_flow()` → `主力净流入-净额` / 1e8\n\n**下图：** 中证全指涨跌幅折线\n- `akshare.stock_zh_index_daily_tx(symbol='sh000985')` → `change_pct`\n\n**铁律：** 资金流向 ≠ 成交额。不要用成交量/成交额替代资金流向。`stock_zh_index_daily_tx()` 的 `amount` 字段是成交额，不是资金流向。\n\n**同步坑：** 优先用腾讯接口（`stock_zh_index_daily_tx`），东方财富接口（`stock_zh_index_daily_em`）连接不稳定。`TQDM_DISABLE=1` 必须写在 `import akshare` 之前才能生效。`get_zzqz_data()` 中最后调用 `stock_zh_index_daily_tx()` 内部会拉取最新15条数据，进度条已被 TQDM_DISABLE 关闭。

### ✅ 新功能集成原则：复用现有模式，不重写（2026-05-21 用户明确）\n\n用户有明确偏好：**按已有的写法写，不要重新发明轮子。** 新功能应先查看代码库中类似功能的实现模式，再按相同风格扩展。\n\n**错误做法（本会话踩坑）：**\n- 资金流向图先后尝试了3种不同数据源（行业板块→全市场净流入→成交额→终版混合），每次都是全部重写\n- 应该一开始就参考 `gen_index_chart.py` 的写法（`stock_zh_index_daily_tx` 腾讯接口）\n\n**正确做法：**\n1. 先看现有脚本怎么写的（`gen_index_chart.py` 就是好模板）\n2. 数据源优先用代码库已验证的（腾讯接口 > 东方财富接口）\n3. 增量修改，不是全盘重写\n\n同时：**新功能集成到 `generate_review_data.py`，不加 cron 步骤。** 所有复盘相关的新生成逻辑（图表生成、数据归档等）都应整合到 `generate_review_data.py` 内部，不在 `generate_daily_review.sh` 里加新 Step。cron 脚本只编排 4 个固定 Step，新功能在 Step 4 内部完成。

当前已集成到 Step 4 的功能：
- 批量个股关键点图（`batch_gen_charts.py`）
- 全市场资金流向图（`gen_fund_flow_chart.py`）
- 图表归档（`zzqz_v2.svg` + `fund_flow_chart.png` → `review_charts/archive/{date}/`）

**Step 5 新增（2026-05-21）：每日成果PDF自动生成**
`generate_daily_achievements_pdf(date_str)` 在复盘生成最后阶段调用：
- 生成 `每日成果_YYYYMMDD.pdf` 到 `/home/ubuntu/www/files/`
- 从复盘JSON提取大盘周期+主线数量填入PDF概要
- 已存在则跳过不覆盖（保护手写内容）
- HTML→wkhtmltopdf→PDF，临时HTML自动清理
- 下次cron运行时自动触发，无需额外脚本步骤

**问题：** 查看历史复盘时，②最强动量和③最强逻辑加载的是**当天**的实时数据，不是历史当天的数据。

**修复：** 后端 `generate_review_data.py` 在生成复盘时额外保存3个字段到存档JSON：
- `momentum` — 涨停/新高数据（来自 `fetch_momentum.py` 或其缓存）
- `industry_map_archive` — 行业分类地图（按 `ths_industry` 分组后的 `stock_industry_map.json`）
- `industry_boards_archive` — 同花顺90个行业当日涨跌幅/净流入/领涨股（来自 `akshare.stock_board_industry_summary_ths()`），供历史页板块排行展示

前端 `loadReviewData()` 检测存档中是否有这些字段：
```javascript
if (data.momentum) {
    updateMomentumFromArchive(data.momentum, data.industry_boards_archive);
} else {
    loadMomentum();  // 实时拉取（今日页面）
}
if (data.industry_map_archive) {
    updateLogicFromArchive(data.industry_map_archive);
} else {
    loadLogicMap();
}
```

**历史板块排行：** 从 `industry_boards_archive` 取出数据，按涨跌幅降序取TOP10渲染到 `#mainLineBodyArchive` 表格中。无领涨股图表链接（只有名称文字）。

**注意：** 历史动量和行业地图仅保存在 `review_archive/{date}.json` 中，不写入 `review_data.json`（仅今日数据）。

### 持仓按结构优先排序（2026-05-21）

`generate_review_data.py` 生成 `holdings_review` 后，执行排序：

```python
struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}
holdings_review.sort(key=lambda x: struct_priority.get(x['structure'], 3))
```

上升趋势在前→区间震荡→下降趋势最后。`--`/未知归到末尾（优先级3）。

### 持股card设计（2026-05-21 诊断卡终版）

**④区 `signalStockCard()` 终版布局：**
```
┌────────────────────────────────────────────────────────────────────┐
│ 📈 国际复材 301526                          18.78 +0.43%         │
├────────────────────────────────────────────────────────────────────┤
│ 操作:✅持有  结构:📈上涨趋势  阶段:🔄缩量整理  📊               │  ← 4字段，买点仅buy时出现
├────────────────────────────────────────────────────────────────────┤
│ 💡 量能缩量65%卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待   │
│    放量突破                                                        │
│ [chart: 点击📊展开SVG]                                            │
└────────────────────────────────────────────────────────────────────┘
```

**字段布局（从左到右）：** 操作 → 结构 → 阶段 → 买点(仅buy时) → 📊
- **操作：** 仅 `✅持有` / `⚡买入` / `❌卖出`，由 `judge_signal()` 统一判定，无 `signal_text`
- **结构/阶段：** 来自 `ema_utils`
- **买点：** 仅当 `signal='buy'` 时显示 `突破买点` / `中继买点`（不带flags ✓✗✓✓）
- **结论行：** 独立于操作信号，前端按stage+vol_analysis生成详细分析

**原则（2026-05-21 用户修正）：** 新增字段是补充，不能替代已有字段。任何UI改版，先列出所有已有字段确保全部保留。

### ⑤区 自选股买点信号 — 方向Tab+分页（2026-05-21 重写）

`updateBuySignalsUI()` 渲染 `buy_signals_review`，与第④部分**使用同一 `signalStockCard()` 函数**，判定逻辑完全一致。

**分组字段 `sector` = 用户方向（非同花顺行业）：**
`buy_signals_review` 中的 `sector` 字段存储的是**用户8大方向**（半导体/算力/创新药/机器人/新能源/资源股/AI应用/商业航天），而非同花顺行业分类。数据来源：`all_stocks_60d.json` 的顶层 key 即为用户方向名。Tab 按 `s.sector` 分组，算力Tab下显示华工科技/永鼎股份/中际旭创/东山精密/中国移动（同花顺行业为自动化设备/通信设备/元件/通信服务，分散在不同行业但都属于算力方向）。

**判定逻辑（2026-05-21 重构：完全基于系统B—EMA10趋势分析 + 3层阈值）：**
```
buy_signals[] ← 来自 latest_scan_result.json（每日扫描结果，含market_position+main_lines参数）
  → stock_cache[code] 获取 structure/stage/ema/vol_analysis（系统B分析结果）
  → 区间震荡 → 关键点支撑重算stage
  → judge_signal(structure, stage, buy_point) → signal (仅buy展示)
```

**中继买点判定（2026-05-21 3层阈值框架）：**
- 第1层 大盘定基准：market_position → 缩量基准(85%/80%/75%/70%)
- 第2层 板块调系数：main_lines → 主线×1.05 / 非主线×0.80
- 第3层 个股定类型：上涨趋势+缩量 → 中继买点 / 区底+缩量 → 中继买点
- 缩量阈值 = 基准(大盘) × 板块系数，放量阈值 = 基准 ÷ 板块系数
- 函数：`_shrink_threshold(market_position, is_main_line)` / `_surge_threshold(...)`
- 扫描链路：`daily_update_and_scan` → 从review.json读market_position+main_lines_list → `detect_buy_point(market_position=, main_lines=)`

**突破买点判定：**
- 上涨趋势 + 放量突破前10日高 → 需求强劲突破平台
- 区间顶部 + 放量突破前10日高 → 区顶放量突破
- 放量阈值同样受大盘+板块动态调整

**未通过条件不展示买点：** 中微公司(上涨趋势但量能正常104%)→ 无买点 ✅，沪硅产业(区间震荡不在底部)→ 无买点 ✅

**UI结构：**\n- **方向Tab** — 用 `<span onclick="">` 替代 `<a href="javascript:;">`，避免浏览器显示 `javascript;` 文本（2026-05-21 用户反馈后修复）\n  - 坑：`<a href="javascript:;" onclick="...">` 在某些浏览器/环境下点击后状态栏或页面文本中出现 `javascript;` 字样\n  - 修复：改为 `<span style="cursor:pointer;display:inline-block;" onclick="...">`\n- **Tab状态** — `if (!window._buyTab)` 初始化一次**而非**每次都 `window._buyTab = {...}` 重置。踩坑日志：误写成重置 → 用户切Tab后被拉回第一个 → 以为切Tab出错了\n- **每Tab分页** — >10只自动分页，每页10只\n- **排序** — 按结构优先级（上涨趋势→区间震荡→下降趋势），后端已排好\n- **卡片格式** — 同第④部分 `signalStockCard()`：操作/结构/阶段/买点(仅buy)/📊/结论+盈利1标签

**技术实现：**
1. `get_buy_sell_signals()` 返回三个值：`(signals, stock_cache, bs_by_code)`
   - `stock_cache: {code: {close, change, date, ema, structure, stage, vol_analysis}}` — 全量自选股缓存
2. `buy_signals_review` 构建时遍历 `buy_signals`，从 `stock_cache` 取结构/阶段/EMA/量能
3. 区间震荡股票用同样二次支撑重算（代码复制自holdings流程，但可优化复用）
4. 前端 `window._buyTab` 全局对象管理Tab状态（`activeSector` + 各Tab `pages`）

**前端JS核心：**
```javascript
// review.html updateBuySignalsUI()
const groups = {};
signals.forEach(s => { const sec = s.sector||'其他'; ... groups[sec].push(s); });
// Tab构建：筛选→分页→signalStockCard渲染
const pageData = groups[tab.activeSector].slice(start, end);
html += pageData.map((s, i) => signalStockCard(s, ...)).join('');
```

### ⚠️ 第⑤部分只展示买入信号（2026-05-21 用户纠正）

`buy_signals_review` 从全量自选股扫描结果生成，但 `generate_review_data.py` 中初始版本**未按 signal 过滤**，将 `judge_signal()` 判为 sell/hold 的股票也加入了列表，用户看到卖出建议出现在"自选股买点信号"区。

**修复：** 在遍历 `buy_signals` 时，对 `code_sig != 'buy'` 的股票执行 `continue`，不加入 `buy_signals_review`。

```python
# generate_review_data.py 遍历 buy_signals 时
code_sig, _, _ = judge_signal(structure=structure, stage=stage, buy_point=s.get('buy_point', ''))
if code_sig != 'buy':
    continue   # ← 必须过滤，第⑤部分只展示买入信号
buy_point_display = s.get('buy_point', '')
```

**原则：** 第⑤部分标题是"自选股**买点**信号"，只应展示 `signal='buy'` 的股票。

### ⚠️ signalStockCard() 跨区复用 — 变量作用域陷阱（2026-05-21 踩坑）

`signalStockCard()` 被 `updateStocksUI()`（第④部分）和 `updateBuySignalsUI()`（第⑤部分）共同调用。`secColors` 定义在 `updateBuySignalsUI()` 函数作用域内，**不在 `signalStockCard()` 的作用域链中**。如果在 `signalStockCard()` 中引用 `secColors`：

```javascript
// ❌ 错误 — secColors 在 signalStockCard 的闭包中未定义
function signalStockCard(s, idx) {
    const color = secColors[s.sector];  // ReferenceError!
}
```

后果：`updateStocksUI()` 调用 `signalStockCard()` 时，`secColors` 未定义 → ReferenceError → 抛出异常 → 被 `loadReviewData.fetch().catch()` 吞掉 → **三个section（持仓/买点/交易计划）全部静默为空**。用户看到的是"暂无数据"，完全无 JS 错误提示。

**避免方法：**
1. **不要**在 `signalStockCard()` 中引用外部函数作用域的变量
2. 如果需要方向颜色：在 `updateBuySignalsUI()` 渲染Tab时已经展示，卡片内无需重复
3. 如果必须跨区共享变量，提升到 `window` 全局或 IIFE 闭包

### ⚠️ signalStockCard() 跨区复用导致图表ID冲突（2026-05-21 用户反馈）

第④部分和第⑤部分都使用同一 `signalStockCard()` 渲染卡片，其中图表toggle的DOM ID固定为 `hchart_{idx}`。当两部分在页面同时存在时，`getElementById('hchart_1')` 永远返回第④部分的元素，第⑤部分点击📊无效。

**修复：** 第⑤部分渲染后对HTML做字符串替换，将 `hchart_` → `bchart_`：

```javascript
// review.html updateBuySignalsUI()
html += pageData.map((s, i) => {
    const card = signalStockCard(s, start + i + 1);
    return card.replace(/id="hchart_/g, 'id="bchart_')
               .replace(/toggleChart\('hchart_/g, "toggleChart('bchart_");
}).join('');
```

**原则：** 复用包含DOM ID的UI组件时，不同区域必须用ID前缀区分。Section 4 = `hchart_`，Section 5 = `bchart_`。

**方向颜色映射（JS `secColors`，仅在 `updateBuySignalsUI()` 函数作用域内定义，不可被 `signalStockCard()` 引用）：**
- 半导体: #e94560 · 算力: #2196f3 · 创新药: #4CAF50
- 机器人: #9C27B0 · 新能源: #FF9800 · 资源股: #8B4513
- AI应用: #00BCD4 · 商业航天: #FF5722

### profit_model1 + trend_stock 标签（2026-05-21 新增）

...

## 关联知识库

3L交易体系训练营18期资料（简放）已提取为markdown，存放在：
`/home/ubuntu/data/3l/knowledge_base/training_camp/`
索引见：`/home/ubuntu/data/3l/knowledge_base/INDEX.md`

可搜索各期内容辅助复盘分析和策略理解。

**第④部分 持仓卡片：** `signalStockCard()` 中在名称后加两个标签（蓝底 `📈 趋势股` + 红底 `🏆 盈利1`）：

```javascript
${s.profit_model1 ? '<span class="tag" style="background:#e94560;font-size:10px;padding:1px 6px;border-radius:4px;margin-left:4px;">🏆 盈利1</span>' : ''}
${s.trend_stock ? '<span class="tag" style="background:#2196f3;font-size:10px;padding:1px 6px;border-radius:4px;margin-left:4px;">📈 趋势股</span>' : ''}
```

**第⑤部分 买点信号卡：** 同样由 `signalStockCard()` 统一渲染。

**交易计划 买点优先级：** 使用缩写标签（仅emoji，节省空间）：

```javascript
const pm1 = s.profit_model1 ? '<span class="tag" style="background:#e94560;">🏆</span>' : '';
const trend = s.trend_stock ? '<span class="tag" style="background:#2196f3;">📈</span>' : '';
html += ` ${tag} ${pm1} ${trend}`;
```

两个标签独立展示，互不排斥。一票可以同时亮盈利模式1+趋势股。

#### 数据链路

profit_model1 和 trend_stock 走同一套数据管道：

```
buy_signals[] 
  → check_profit_model1_on_signals()    ← 添加 profit_model1 字段
  → check_trend_stock_on_signals()       ← 添加 trend_stock 字段
  → bs_by_code[code]                     ← 通过 code 查找
    → holdings_review[]                  ← 含 profit_model1 + trend_stock
    → buy_signals_review[]               ← 含 profit_model1 + trend_stock
    → trading_plan.buy_priority[]        ← 含 profit_model1 + trend_stock
```

两个 `on_signals` 函数位于 `buy_point_detection.py`（公共函数，不是 `generate_review_data.py` 的私有函数）。`generate_review_data.py` 通过 `from scripts.buy_point_detection import check_profit_model1_on_signals, check_trend_stock_on_signals` 导入。

#### 数据字段

- `buy_signals[n].profit_model1` — bool，盈利模式1是否满足
- `buy_signals[n].trend_stock` — bool，趋势股6条件是否满足
- `holdings_review[n].profit_model1` — 同上，从 bs_by_code 查找
- `holdings_review[n].trend_stock` — 同上
- `buy_signals_review[n].profit_model1` — 同上
- `buy_signals_review[n].trend_stock` — 同上
- `trading_plan.buy_priority[n].profit_model1` — 同上
- `trading_plan.buy_priority[n].trend_stock` — 同上

**数据链路：**
```
all_stocks_60d.json
  → get_buy_sell_signals()  ← cache中算vol_analysis
    → (signals['holdings'], stock_cache, bs_by_code)  ← 三返回值（2026-05-21 新增stock_cache+bs_by_code）
      → holdings_review[]   ← 含profit_model1(从bs_by_code查)
      → buy_signals_review[] ← 含structure/stage/signal(从stock_cache查)
```

**阶段颜色映射（前端JS `stageColors`）：**
- 上行 / 区间底部 / 转强 → `#4ecdc4` 青色（积极）
- 缩量整理 / 区间中段 → `#ffd700` 金色（中性等待）
- 滞涨 / 转弱 / 区间顶部 → `#ff6b6b` 橙红（警惕）
- 加速 / 加速跌 → `#e94560` 红色（极端）

**结论文字（前端JS硬编码，`signalStockCard()` 中根据 stage + vol_analysis 生成）：**
- 缩量整理 → `量能{volDesc}卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待放量突破`
- 上行 → `斜率正常，EMA10持续向上，上行趋势健康，继续持有不动`
- 加速 → `EMA10斜率加速变陡，拉升阶段，关注放量滞涨等左侧止盈信号`
- 滞涨 → `EMA10走平涨不动{volDesc ? '，量能'+volDesc+'未有效萎缩' : ''}，警惕回调，考虑减仓`
- 转弱 → `EMA10已拐头向下，趋势转弱，关注关键支撑位是否破位`
- 区间底部 → `价格在支撑位附近，区间底部企稳，可考虑加仓博反弹`
- 区间顶部 → `价格接近压力位，区间顶部受阻，注意减仓回避`
- 区间中段 → `区间中部无明确方向，等待价格靠近支撑或压力再做决定`

**设计原则：** 每句话引用具体数据（量能百分比、EMA10位置）、隐含操作方向、负面状态给出后续观察路径。详见 `references/2026-05-21-conclusion-text-mapping.md`。

**操作决策区（⑤区 自选股买点信号 — 2026-05-21 重写）：** 方向Tab分组+分页，同 `signalStockCard()` 渲染，判定逻辑与第④部分一致。
- 📋 持仓操作建议 — 根据stage映射操作图标和文字
  - 🔄 持有·可加仓（缩量整理）
  - ✅ 持有（上行/正常）
  - ⏳ 持有·关注止盈（加速）
  - ⚠️ 警惕·考虑减仓（滞涨）
  - ⚡ 关注·可换股（转弱）
  - 🟢 支撑位·可加仓（区间底部）
  - 🔴 压力位·注意减仓（区间顶部）
  - ❌ 卖出（卖出信号）
- 🎯 买点信号 — 从 `data.buy_signals_review` 渲染

**数据字段变动（2026-05-21）：**
- `holdings_review` 新增: `ema`, `vol_analysis`, `profit_model1`
- `buy_signals_review` 新增: `structure`, `stage`, `signal`, `ema`, `vol_analysis`, `profit_model1`（与holdings同判定逻辑）
- `get_buy_sell_signals()` 返回三参数: `(signals, stock_cache, bs_by_code)`

**数据链路（2026-05-21 三路返回架构）：**
```
all_stocks_60d.json
  → get_buy_sell_signals()  ← 内建 cache（structure/stage/ema/vol_analysis）
    → (signals['holdings'], stock_cache, bs_by_code)
      → holdings_review[]   ← 从 stock_cache 取structure/stage, 从 bs_by_code 取profit_model1
      → buy_signals_review[] ← 从 stock_cache 取structure/stage/ema/vol_analysis, 从 bs_by_code 取profit_model1
        → judge_signal(structure, stage, buy_point) → signal
        → 前端 signalStockCard() 统一渲染第④+⑤部分
```

### 参数说明

```python
# get_stage() 签名（2026-05-21 新增volumes参数）
def get_stage(closes, structure=None, highs=None, lows=None,
              support_level=None, resistance_level=None, volumes=None):
    ...
    # 当ratio<0.4时：
    #   量缩80%+价在EMA10上 → "缩量整理"
    #   其他               → "滞涨"
```

### 区间震荡stage的支撑计算（2026-05-21）

`generate_review_data.py` 在生成 `holdings_review` 时，对 `structure='区间震荡'` 的股票：

1. 从 `all_stocks_60d.json` 缓存读全部K线
2. 遍历60天K线找所有"突"关键点，`support_price` = 突破前10日最高价
3. 从高到低排列，取第一个距当前价≥1.5%的作为有效支撑
4. 全过滤掉则回退20日最低
5. 用支撑和15日最高(压力)重算 stage

**同步坑：** `generate_review_data.py` 的支撑选择逻辑必须与 `batch_gen_charts.py` 一致（`bk_pts` 过滤+下一档回退）。改一处时必须改另一处。

**错误历史（2026-05-21）：** 初版用了 `if filtered: support=None; support or min(lows[-20:])` 导致深圳华强跳到了29.58（20日最低），正确行为是取下一档33.10。

### 持仓个股卡片 signal 字段（统一由 judge_signal 判定 — 已废弃 signal_text）

**signal 统一判定：** 由后端 `generate_review_data.py` 调用 `judge_signal(structure, stage, buy_point)` 统一生成 `signal` 字段（buy/hold/sell）。前端读取 `s.signal` 渲染为简短符号 `✅持有` / `⚡买入` / `❌卖出`。

**signal_text 已废弃：** 不再使用。前端操作字段直接基于 signal 代码渲染，无冗余描述。

**买点显隐由 signal 控制：** `buy_point` 字段仅当 `signal='buy'` 时才保留，避免与操作建议冲突。

后端 `judge_signal()` 判定规则（详见 `stock-action-judgment` skill）：

| 条件 | signal_code | signal_text | CSS |
|------|:----------:|-------------|:---:|
| `structure` = 下降趋势 | `sell` | ❌ 卖出 · 下降趋势（回避模板①） | `danger` |
| 区间震荡 + 区间顶部 | `sell` | ❌ 卖出 · 区间顶部向下突破风险（回避模板②） | `danger` |
| 上涨趋势 + 加速 | `sell` | ❌ 卖出 · 加速后兑现压力（回避模板③） | `danger` |
| `buy_point` 含"突破/中继买点" | `buy` | ⚡ 买入 · 符合买点条件 | `warn` |
| 其余 | `hold` | ✅ 持有 · 符合持股模板 | `hold` |

优先级：卖出 > 买入 > 持有。**同时满足卖出和买入条件时，卖出优先。**

前端 fallback（当 `signal_text` 为空时）：
```javascript
const cls = s.signal === 'sell' ? 'danger' : s.signal === 'buy' ? 'warn' : 'hold';
const signalText = s.signal_text || (s.signal === 'hold' ? '✅ 持有' : s.signal === 'buy' ? '⚡ 买入' : s.signal === 'sell' ? '❌ 卖出' : '--');
```

**操作信号（操作: ✅持有/⚡买入/❌卖出）** 与买点、结构、阶段在同一行展示，不占单独行。基于 `judge_signal()` 后端生成。
- 持股模板（6.6节）→ ✅ 持有：没触发止损止盈、上升趋势无加速、非下降趋势、关键点附近、供需格局好、无异常量价
- 回避模板（6.7节）→ ❌ 卖出：趋势性下跌、震荡向下突破、加速后
- 买点条件 → ⚡ 买入：有突破/中继买点信号

**注意：** `stop_loss` 字段已在卡片第二行去掉（2026-05-21），保留三个字段：买点/结构/阶段。

### 关联 reference 文件

| 文件 | 说明 |
|------|------|
| `references/volume-unit-diagnosis.md` | Volume单位手↔股诊断步骤 + 已知不一致存量清单 |
| `references/server-crash-diagnosis.md` | server.py SYN flood 崩溃的诊断+加固方案 |
| `references/support-fallback-logic.md` | 区间震荡画stage时支撑过滤+下一档回退的详细说明 |
| `references/2026-05-21-diagnosis-operation-redesign.md` | ④⑤区重构（诊断卡+操作决策）+ vol字段名修复记录 |
| `references/2026-05-21-full-optimization-summary.md` | 操作建议全链路调优5轮记录 |
| `references/2026-05-21-conclusion-text-mapping.md` | 结论文字映射表（signalStockCard 前端逻辑） |
| `references/2026-05-21-session-chart-fixes.md` | 复盘页面修复会话记录：toggle、资金流向图颜色/日期/数据源、全量新高、TQDM_DISABLE |
| `references/2026-05-21-systemb-detection-rewrite.md` | 05-21 买点检测系统A→系统B重构 + 动态阈值 |
| `references/historical-data-preservation.md` | 历史复盘数据保存模式：哪些数据需存档、前后端实现方案、排查指南 |
| `references/repeat-offender-patterns.md` | 重复犯错模式：改数据忘同步/文档≠代码/局部修复陷阱 |

## 单元测试（2026-05-21）

`www/tests/` 目录包含pytest测试框架，覆盖数据层完整性和买点检测正确性。

**运行：** `cd /home/ubuntu/www && python -m pytest tests/ -v`

**32个测试用例：** 路径完整性(17) + 数据结构(9) + 趋势股正反验证 + 回踩买点 + 自选股过滤 + 接口完整性。

详见 `market-scan-workflow` skill 的 `references/unit-test-framework.md`。

## 个股独立分析页面（2026-05-21 新增）

**`/stock_analysis.html`** — 独立的个股买点检测页面，输入股票代码或名称即可查看完整3L量价分析。

### 后端API

`/api/stock-analysis?q=688126` 或 `?q=绿的谐波`

返回JSON结构：
```json
{
  "code": "688126", "name": "沪硅产业", "direction": "半导体",
  "is_watchlist": true, "price": 25.68, "change": 1.23, "date": "2026-05-21",
  "structure": "上涨趋势", "stage": "上行",
  "ema5": 25.10, "ema10": 24.50, "ema20": 23.80, "ema30": 23.20,
  "deviation_pct": 2.31, "vol_ratio": 0.85,
  "trend_stock": true, "profit_model1": false,
  "buy_point": "回踩买点", "buy_score": 5,
  "buy_detail": {"reason": "...", "ema5": 25.10, "deviation_pct": 0.85},
  "huicai_detail": null,
  "has_chart": true,
  "signal": "buy"
}
```

### 搜索逻辑

1. 精确匹配code → 2. 模糊匹配code → 3. 模糊匹配name
- 支持纯数字代码、带前缀代码、中英文名称

### 前端

暗色风格，与复盘页面一致：
- 信号标签（buy/hold/warn）→ 顶部高亮
- 基本信息（名称/代码/方向/价格/涨跌幅）
- 标签行（自选股/非自选、📈趋势股、🏆盈利1、结构）
- 信息网格（阶段、量比、偏离EMA5、EMA排列）
- EMA均线可视化（彩色小圆点+数值）
- 买点详情（可展开）
- K线SVG图表（可展开）

### ⚠️ API URL约定：使用硬编码服务器IP，不用相对URL（2026-05-21 用户纠正）

创建新独立HTML页面时，`fetch()` 调用后端API必须使用**完整URL + 服务器公网IP**：

```javascript
// ✅ 正确 — 用户明确要求
const res = await fetch(`http://43.136.177.133:8080/api/stock-analysis?q=${q}`);

// ❌ 错误 — 浏览器本地打开页面时失效
const res = await fetch(`/api/stock-analysis?q=${q}`);
```

**原因：** 用户可能通过 `file:///` 直接打开HTML，或从不同机器/浏览器访问时本地相对URL不可达。硬编码IP确保无论从哪个设备、以何种方式打开页面都能正常工作。

**注意：** IP变更时需同步更新所有HTML文件中的URL。

### 测试验证

覆盖三种响应：有买点（沪硅产业）、趋势股无买点（绿的谐波+5.10%）、搜索不到（错误提示）。

## 关联 skill

- `main-line-judgment` — buy_point_detection 模块来源
- `market-peak-trough` — 大盘周期判定
- `trading/daily-3l-monitor` — 盘中实时盯盘
- `a-stock-data-sources` — 数据源详情
- `trading/ema10-trend-judgment` — 结构/阶段判断（`scripts/ema_utils.py`）
- `trading/a-stock-kline-keypoint-chart` — 关键点K线图规范（支撑/压力线定义源）

## 数据架构（2026-05-21 统一数据层）

### 原则

- 所有股票数据统一放在 `/home/ubuntu/data/3l/` 下
- `~/.hermes/profiles/3l/data/` 不存放任何股票系统数据（仅hermes自身配置）
- **所有文件路径只在一个地方定义**：`/home/ubuntu/www/scripts/data_layer.py`
- 所有脚本通过 `from scripts.data_layer import ...` 访问数据，不支持直接写路径

### 已接入 data_layer 的脚本

| 脚本 | 替代的硬编码路径 |
|------|----------------|
| `scripts/buy_point_detection.py` | `ALL_STOCKS_PATH`, `get_industry_map()`, `PROFIT_QUALITY_PATH` |
| `generate_review_data.py` | `ALL_STOCKS_PATH`, `LATEST_SCAN_PATH`, `INDUSTRY_MAP_PATH`, `REVIEW_ARCHIVE_DIR`, `WWW_DIR` |
| `server.py` | `INDUSTRY_MAP_PATH`, `INDUSTRY_LEADERS_PATH` |
| `scripts/scan_buy_signals.py` | `ALL_STOCKS_PATH`, `WATCHLIST_PATH`, `REVIEW_CHARTS_DIR`, `REVIEW_ARCHIVE_DIR` |
| `scripts/monitor_data.py` | `CACHE_DIR`, `INDUSTRY_LEADERS_PATH`, `REVIEW_CHARTS_DIR`, `REVIEW_ARCHIVE_DIR` |
| `fetch_momentum.py` | `ALL_STOCKS_PATH`, `INDUSTRY_MAP_PATH`, `SCRIPTS_DIR` |
| `scripts/gen_weekly_report.py` | `ALL_STOCKS_PATH`, `OUTPUT_DIR`, `SCRIPTS_DIR` |
| `scripts/judge_main_line.py` | `ALL_STOCKS_PATH` |

### 自选股过滤（2026-05-21 新增）

**方案：** 扫描全量数据（`all_stocks_60d.json`），用 `watchlist.json` 过滤结果。

**实现位置：** `buy_point_detection.py` 的 `scan_all_stocks()` 新增 `watchlist_codes` 参数。

```python
def scan_all_stocks(date_str, all_stocks, market_position='', main_lines=None, watchlist_codes=None):
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            if watchlist_codes and code not in watchlist_codes:
                continue
            ...
```

**调用链路：**
- `generate_review_data.py` fallback扫描 → `format_buy_signals(watchlist_codes=wl_codes)` → `scan_all_stocks(watchlist_codes=wl_codes)`
- `scan_buy_signals.py` 已从 `load_stock_list()` 读取 `watchlist.json` → 按自选股列表逐一扫描（天然过滤）
- `gen_weekly_report.py` 历史扫描→未传 watchlist_codes（保持全量，周报可能需要）

**⚠️ 坑：** 如果不传 `watchlist_codes`，`scan_all_stocks()` 扫 `all_stocks_60d.json` 全部247+只。步科股份（688160）不在用户自选股但出现在扫描结果中 → 需要过滤。

### 公共函数归一化（2026-05-21）

以下函数从 `generate_review_data.py` 迁移到 `buy_point_detection.py` 作为公共函数：

- `find_latest_date_in_data()` — 找all_stocks中最新K线日期
- `check_profit_model1_on_signals()` — 批量标记盈利模式1
- `check_trend_stock_on_signals()` — 批量标记趋势股
- `check_trend_stock()` — 单只趋势股判定

**所有导入路径指向 `/home/ubuntu/www/scripts/buy_point_detection.py`，不再有旧skill路径的副本。**

旧路径（已删除）：
- `/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts/buy_point_detection.py`
- `~/.hermes/profiles/3l/data/market_data.json`

### load_market_data_for_profit_check() 简化

从 `market_data.json` 的14行转换逻辑简化为2行：

```python
def load_market_data_for_profit_check():
    return get_all_stocks()  # 与扫描同源，确保最新
```

原 `market_data.json` 格式（SH/SZ前缀、日期带横线、30天、最新→最旧）已废弃。现在统一使用 `all_stocks_60d.json` 格式（裸代码、日期无横线、60天、最旧→最新）。

### profit_model1 + trend_stock 标签（2026-05-21 新增）

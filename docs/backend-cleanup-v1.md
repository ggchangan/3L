# 3L交易系统 — 后端目录结构整理

## 现状

React SPA 迁移完成后，前端已全部收敛到 `frontend/`。但后端代码仍然散落各处：

### 问题一：根目录文件泛滥

```
3l-server/
├── server.py                 ← Flask/HTTP 入口
├── wsgi.py                   ← WSGI 入口
├── config.py                 ← 全局配置
├── manage.py                 ← 管理命令
├── daily_update.py           ← 每日数据更新
├── generate_review_data.py   ← 复盘生成
├── fetch_momentum.py         ← 动量数据抓取
├── gen_fund_flow_chart.py    ← 资金流向图
├── gen_index_chart.py        ← 指数图表
├── package.json              ← 前端依赖（根目录残留）
├── package-lock.json         ← 同上
├── 3l-server.service         ← systemd 配置（deploy/ 已有一份）
├── setup.sh                  ← 部署脚本（deploy/ 已有一份）
├── docker-compose.yml        ← 部署配置（应放 deploy/）
└── ARCHITECTURE_REFACTOR.md  ← 文档（应放 docs/）
```

### 问题二：services/ 在根目录

```
services/         ← 属于 backend 但放在根目录
backend/
  ├── api/        ← 看！这里是 backend 内部
  └── core/       ← 废弃代码（见下）
```

### 问题三：scripts/ 与 backend/core/ 双写冲突

| 目录 | 行数 | 被引用数 | 状态 |
|---|---|---|---|
| **`scripts/`** | ~13,000 | **25 处引用**（services/、tests/、backend/api/） | ✅ 活跃在用 |
| **`backend/core/`** | ~13,000 | **0 处引用**（废弃） | ☠️ 无人调用 |

`backend/core/` 是之前的重构尝试但半途而废，所有业务代码依然走 `from scripts.xxx import ...`。

## 目标结构

```
3l-server/
├── backend/                     ← 所有 Python 代码
│   ├── __init__.py
│   ├── server.py                ← server.py 移入
│   ├── wsgi.py                  ← wsgi.py 移入
│   ├── config.py                ← config.py 移入
│   ├── manage.py                ← manage.py 移入
│   ├── api/                     ← 已有，不变
│   ├── core/                    ← scripts/ 移入（覆盖当前废弃的 backend/core/）
│   ├── services/                ← services/ 移入
│   └── cli/                     ← 命令行入口
│       ├── __init__.py
│       ├── daily_update.py      ← daily_update.py 移入
│       ├── generate_review.py   ← generate_review_data.py 移入（重命名）
│       ├── fetch_momentum.py    ← fetch_momentum.py 移入
│       ├── gen_charts.py        ← 合并 gen_fund_flow_chart.py + gen_index_chart.py
│       └── gen_charts_old.py    ← 可选，保留原始脚本备查
├── frontend/                    ← 已有，不变
├── deploy/                      ← 部署配置（已有，补充移入）
│   ├── 3l-server.service        ← 已有
│   ├── docker-compose.yml       ← 从根目录移入
│   └── setup.sh                 ← 已有
├── tests/                       ← 已有，不变
├── docs/                        ← 文档（统一放这里）
│   ├── backend-cleanup-v1.md    ← 本文档
│   └── ...其他已有文档
├── data/                        ← 数据（不变）
├── private/                     ← 私有数据（不变）
├── scripts/                     ← ⚠️ 删除（已迁移到 backend/core/）
├── archive/                     ← 存档（不变）
├── charts/                      ← 生成图表（建议移入 data/public/charts/）
├── files/                       ← 用户下载文件（不变，业务用途）
├── requirements.txt             ← 保留根目录
├── README.md
└── .gitignore
```

## 文件迁移映射（逐文件）

### 核心文件

| 当前路径 | 目标路径 | 影响涉及文件数 |
|---|---|---|
| `server.py` | `backend/server.py` | ~12 处引用（manage.py, 3l-server.service, deploy scripts） |
| `wsgi.py` | `backend/wsgi.py` | ~2 处引用 |
| `config.py` | `backend/config.py` | ~40 处引用（几乎每个 .py 都 import config） |
| `manage.py` | `backend/manage.py` | ~1 处引用（自身） |

### scripts/ 迁移

| 当前路径 | 目标路径 | 说明 |
|---|---|---|
| `scripts/` 全目录 17 个 .py | `backend/core/` | 覆盖现有废弃 `backend/core/` |
| `scripts/gen_dml_chart.py` | `backend/core/gen_dml_chart.py` | 保留 |
| `scripts/gen_dml_trades.py` | `backend/core/gen_dml_trades.py` | 保留 |
| `scripts/build_board_mapping.py` | `backend/core/build_board_mapping.py` | 保留 |
| `scripts/build_board_names_cache.py` | `backend/core/build_board_names_cache.py` | 保留 |
| `scripts/update_stock_data.py` | `backend/core/update_stock_data.py` | 保留 |

### services/ 迁移

| 当前路径 | 目标路径 | 说明 |
|---|---|---|
| `services/` 全目录 17 个 .py | `backend/services/` | 直接移动 |

### 根目录脚本

| 当前路径 | 目标路径 | 说明 |
|---|---|---|
| `daily_update.py` | `backend/cli/daily_update.py` | cron 直接调用，需更新调用路径 |
| `generate_review_data.py` | `backend/cli/generate_review.py` | 重命名去掉 \_data，更清晰 |
| `fetch_momentum.py` | `backend/cli/fetch_momentum.py` | 直接移动 |
| `gen_fund_flow_chart.py` | `backend/cli/gen_charts.py` | 合并到统一图表生成脚本 |
| `gen_index_chart.py` | `backend/cli/gen_charts.py` | 同上，合并 |

### 根目录杂项

| 当前路径 | 目标路径 | 说明 |
|---|---|---|
| `package.json` | **删除** | 已在 `frontend/package.json`，根目录重复 |
| `package-lock.json` | **删除** | 同上 |
| `3l-server.service` | **删除** | 已在 `deploy/` |
| `setup.sh` | **删除** | 已在 `deploy/` |
| `docker-compose.yml` | `deploy/docker-compose.yml` | 移入部署目录 |
| `ARCHITECTURE_REFACTOR.md` | `docs/architecture-refactor.md` | 移入文档目录 |

### 废弃代码清理

| 路径 | 操作 | 原因 |
|---|---|---|
| `backend/core/`（现有内容） | **删除** | 被 `scripts/` 版本完全替代，0 引用 |
| `scripts/`（迁移完成后） | **删除** | 所有内容已移至 `backend/core/` |

## Import 改写映射

这是最核心的工作——所有 `from xxx import yyy` 路径需要批量更新。

### 1. config.py 的 import 路径变化

**所有** `.py` 文件都有 `import config` 或类似引用。

改写方式：
```
# 旧
import config
from config import SERVER_PORT

# 新
from backend import config
from backend.config import SERVER_PORT
```

涉及文件：~40 个。

### 2. scripts.* → backend.core.*

```
# 旧
from scripts.data_layer import _load_json
from scripts.ema_utils import ema_list
from scripts.scan_buy_signals import get_main_lines

# 新
from backend.core.data_layer import _load_json
from backend.core.ema_utils import ema_list
from backend.core.scan_buy_signals import get_main_lines
```

涉及文件：~25 处引用（services/ ×12, tests/ ×12, backend/api/ ×1）。

### 3. services.* → backend.services.*

```
# 旧
from services.logger import get_logger
from services.trend_service import get_trend_candidates
from services.review_service import get_review_data

# 新
from backend.services.logger import get_logger
from backend.services.trend_service import get_trend_candidates
from backend.services.review_service import get_review_data
```

涉及文件：~30 处引用（server.py, backend/api/ ×12, tests/ ×15, generate_review_data.py 等）。

### 4. tests/ 中的引用

tests/ 全部以 `cd /home/ubuntu/3l-server && python -m pytest` 运行，import 路径与生产代码一致。所以 tests/ 的 import 改写与前三条同步即可。

tests/ 中还有一些 `sys.path.insert(0, ...)` 需要更新：
```
# 旧
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# 新（如果改后不需要了）
# 依赖正确的包结构，可能不再需要 sys.path hack
```

### 5. 系统级引用（nginx, systemd, cron）

```
# 3l-server.service / cron job
# 旧
ExecStart=/home/ubuntu/3l-server/.venv/bin/python /home/ubuntu/3l-server/server.py
# 或
ExecStart=/home/ubuntu/3l-server/.venv/bin/python -m server
# 新
ExecStart=/home/ubuntu/3l-server/.venv/bin/python -m backend.server

# 旧 cron
0 17 * * * cd /home/ubuntu/3l-server && .venv/bin/python daily_update.py
# 新
0 17 * * * cd /home/ubuntu/3l-server && .venv/bin/python -m backend.cli.daily_update

# 旧 cron（复盘生成）
0 18 * * * cd /home/ubuntu/3l-server && .venv/bin/python generate_review_data.py
# 新
0 18 * * * cd /home/ubuntu/3l-server && .venv/bin/python -m backend.cli.generate_review
```

## 执行计划（分阶段，每个阶段可独立 PR）

### 阶段一：目录就位 + config 迁移

**风险：中** — config.py 被几乎每个文件引用，改 import 路径影响面大。

**操作：**
1. 创建 `backend/__init__.py`（已有，空）
2. 复制 `config.py` → `backend/config.py`（先复制不删原文件）
3. 全局搜索 `import config`，改为 `from backend import config`
   - 策略：在 `backend/__init__.py` 中加 `import config` 暴露，让 `from backend import config` 兼容
   - 或者直接全改 `from backend.config import XXX`
4. 创建 `backend/cli/` + `__init__.py`
5. 创建 `backend/services/` + `__init__.py`
6. 复制 `services/` → `backend/services/`（先复制）
7. 复制 `scripts/` → `backend/core/`（覆盖现有的废弃版本）

**验证：** 全回归通过（~197 tests + 手动 curl API）

### 阶段二：import 路径全部切换到 backend.*

**风险：大** — 多处批量替换，需要逐文件确认。

**操作：**
1. 全项目 `from scripts.xxx` → `from backend.core.xxx`
2. 全项目 `from services.xxx` → `from backend.services.xxx`
3. 全项目 `import config` → `from backend import config`
4. 删除旧的 `scripts/`、`services/`、`config.py`

**验证：** 全回归通过 + server 正常启动 + curl 验证各 API

### 阶段三：根目录脚本迁移

**风险：小** — 脚本独立，不影响运行中 API。

**操作：**
1. `server.py` → `backend/server.py`，更新 `3l-server.service` 和 `manage.py`
2. `wsgi.py` → `backend/wsgi.py`
3. `daily_update.py` → `backend/cli/daily_update.py`，更新 cron
4. `generate_review_data.py` → `backend/cli/generate_review.py`，更新 cron
5. `fetch_momentum.py` → `backend/cli/fetch_momentum.py`，更新 cron
6. 合并两个 gen_chart 脚本到 `backend/cli/gen_charts.py`

**验证：** 手动跑 cron 脚本确认 + curl API

### 阶段四：根目录杂物清理

**风险：无** — 纯删除/移动文件。

**操作：**
1. 删根目录 `package.json`、`package-lock.json`
2. 删根目录 `3l-server.service`（已在 deploy/）
3. 删根目录 `setup.sh`（已在 deploy/）
4. 移 `docker-compose.yml` → `deploy/`
5. 移 `ARCHITECTURE_REFACTOR.md` → `docs/`
6. 删废弃 `backend/core/`（如阶段一已覆盖则跳过）

**验证：** 服务正常启动，无报错

### 阶段五：废弃代码清理 + 收尾

**风险：无** — 已确认无人使用的代码。

**操作：**
1. 清理 `scripts/` 中未迁入 `backend/core/` 的剩余脚本
2. 更新 `.gitignore` 中过时的路径
3. 更新 `README.md` 目录结构说明
4. 全回归最终验证

## 已知风险与应对

| 风险 | 应对 |
|---|---|
| `config.py` 被 ~40 个文件 import | 阶段一先复制不删除，阶段二切换后全回归再删 |
| cron/nginx/systemd 调用路径需要手动更新 | 逐条确认修改，每天跑一次 cron 验证 |
| `backend/core/` 废弃代码误删 | `git diff` 确认 scripts/ 覆盖后内容一致再删 |
| `manage.py` 中的 server 管理命令 | 重构后需要更新调用的 Python 模块路径 |
| `generate_review_data.py` 被 tests/ 多个测试引用 | 更新 tests/ 中的 import 或创建兼容别名 |

## 本文档的归宿

- 设计文档统一放 `docs/` 目录
- 格式统一用 `.md`（版本控制友好，diff 可读）
- 命名约定：`<domain>-<purpose>-v1.md`
- 同类文档：`product-design-v1.md`（产品设计）、`architecture.md`（架构总览）

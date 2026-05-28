# 3L 交易系统 — 测试自动化架构设计

> 版本: v1.0 | 最后更新: 2026-05-28
> 对应代码: 回归运行器 `scripts/run_full_regression.py`

---

## 1. 动机与目标

### 为什么需要这个体系

3L 交易系统经过多轮迭代，已有 89 项前端测试 + 649 项后端测试。但测试是**分散**的：

- `make test` 只跑后端
- `npm test` 只跑前端
- 设计文档写了新功能 → 代码有没有实现？**手动查**
- 新增一个搜索框 → 和已有页面的风格一致吗？**凭眼睛看**
- 页面结构改了 → 布局有没有跑偏？**没人知道**

### 目标

1. **一键全回归** — 一条命令覆盖所有测试，结果统一报告
2. **发现 ≥90% 问题** — 代码错误、设计遗漏、风格漂移、结构变化，都能自动捕获
3. **分层堵截** — 不同等级的问题在不同阶段暴露，CRITICAL 阻塞构建，WARNING 报告但不阻塞
4. **可追溯** — 每轮回归结果入 git，能看出"这次和上次比什么变了"
5. **自动集成到构建** — `python3 frontend/build.py` 自动跑回归，不过不让部署

---

## 2. 备选方案比较

在设计阶段，评估了 5 种测试类型，对比 4 种候选方案（实际后来扩展为 5 种）：

### 方案 A: 纯后端合约测试

| 维度 | 评价 |
|:-----|:-----|
| 原理 | 用 pytest 直接请求每个 JSON API，验证返回结构、字段类型、数值范围 |
| 覆盖范围 | API 层（约 30 个端点） |
| 发现能力 | API 结构变化、路由丢失、字段缺失 |
| 盲区 | 前端渲染、CSS 样式、UI 布局、设计遗漏 |
| 速度 | ~2s |
| 维护成本 | 低 — API 稳定后极少改动 |

### 方案 B: 前端渲染测试 (vitest + jsdom)

| 维度 | 评价 |
|:-----|:-----|
| 原理 | 用 vitest + jsdom 渲染 React 组件，断言 DOM 结构和内容 |
| 覆盖范围 | 组件层（13 个测试文件，89 项测试） |
| 发现能力 | 组件崩溃、数据缺失时的降级显示、条件渲染逻辑 |
| 盲区 | 真实浏览器行为、CSS 渲染、布局偏移、API 联通性 |
| 速度 | ~20s |
| 维护成本 | 中 — 组件重构时需要更新测试 |

### 方案 C: 设计-代码交叉检查

| 维度 | 评价 |
|:-----|:-----|
| 原理 | 解析设计文档的功能需求列表，扫描代码文件是否有对应关键字实现 |
| 覆盖范围 | 功能需求 vs 代码实现的可追溯性 |
| 发现能力 | 设计写了但代码没实现、部分实现、实现不完整 |
| 盲区 | 实现质量（有代码但不一定正确）、数据准确度 |
| 速度 | ~0.1s |
| 维护成本 | 低 — 只需更新 REQUIREMENTS 列表和 SCAN_FILES |

### 方案 D: 视觉回归 (Playwright 截图)

| 维度 | 评价 |
|:-----|:-----|
| 原理 | 用 Playwright 启动真实浏览器，截图关键页面，和基线截图做像素对比 |
| 覆盖范围 | 真实渲染（含 CSS、布局、字体） |
| 发现能力 | 布局偏移、元素缺失、样式崩坏、字体/颜色变化 |
| 盲区 | 数据准确性、交互逻辑、动态内容 |
| 速度 | ~8s |
| 维护成本 | 高 — 每次有意布局变化需更新基线截图 |

### 方案 E: UI 风格一致性审计

| 维度 | 评价 |
|:-----|:-----|
| 原理 | 静态分析所有 .tsx 文件，提取 className、inline style、颜色值、字号、间距，检测离散程度 |
| 覆盖范围 | 前端所有组件的样式模式 |
| 发现能力 | 搜索框未用共享类、inline style 泛滥、低频颜色值、字号/圆角/间距不一致 |
| 盲区 | 运行时样式、CSS 变量、动态 className |
| 速度 | ~0.1s |
| 维护成本 | 低 — 只需更新 SHARED_CLASSES 列表 |

---

## 3. 方案选型理由

### 最终选择: 全部 5 种并行

**不选 A 放弃 B/C/D/E 的理由** — 每种测试覆盖的盲区是另一种的强项，互相补充。

| 场景 | 能发现的测试 |
|:-----|:-----------|
| 后端改了个字段名 | 合约测试 ✅ |
| 前端改了组件结构 | 渲染测试 ✅ + 视觉回归 ✅ |
| 新加了个搜索框但用了不同的样式 | UI 审计 ✅ |
| 设计文档写了新功能但代码忘了实现 | 交叉检查 ✅ |
| CSS 改了个颜色导致按钮看不见 | 视觉回归 ✅ |

### 分级策略

每种测试不是同等重要的，按影响分三级：

```
CRITICAL → 必须通过，否则构建失败
  ├── 前端 vitest（组件崩溃 = 页面不可用）
  └── 后端 pytest（逻辑错误 = 数据错误）

WARNING → 报告但不阻塞构建
  ├── 设计交叉检查（设计遗漏，但不影响线上）
  ├── UI 风格审计（风格漂移，不影响功能）
  └── API 合约测试（结构变化，可能兼容）

INFO → 仅日志
  └── 视觉回归（基线对比，人工判断）
```

这个分级让 CI/CD 流程既安全又灵活：
- **重大错误**（CRITICAL）→ 直接卡住，别想上线
- **风格/设计问题**（WARNING）→ 告诉你但不拦你
- **视觉变化**（INFO）→ 生成报告你自己看

---

## 4. 执行方式

### 4.1 一键回归

```bash
# 标准模式（运行全部，有失败也继续跑完）
make regression

# CI 模式（只跑 CRITICAL，失败立即退出码 1）
make regression-ci

# 只看报告（不重新跑）
python3 scripts/run_full_regression.py --report
```

### 4.2 独立工具

```bash
make audit-ui           # UI 风格审计
make check-design       # 设计-代码交叉检查
make visual-regression  # 视觉回归（生成/更新基线）
```

### 4.3 构建集成

`python3 frontend/build.py` 自动集成：

```
① 运行全回归（CRITICAL 必须过） ← 新增
② npm run build
③ 注入 modulepreload
④ 部署到 systemctl restarts
```

CRITICAL 失败了直接退出，不会构建/部署损坏版本。

### 4.4 CI/CD 流程

```
[开发者推送分支]
    ↓
手动创建 PR / 合并 → 由用户操作
    ↓
[合并到 master]
    ↓
下次构建自动触发全回归
    ↓
CRITICAL ❌ → 构建终止，开发者修复
CRITICAL ✅ → 构建部署成功
    ↓
WARNING ⚠️ → 报告存档，不阻塞上线
```

---

## 5. 技术实现细节

### 5.1 回归运行器 (run_full_regression.py)

```
TESTS = [
  { id: 'frontend-vitest',    tier: CRITICAL, cmd: 'npx vitest run' },
  { id: 'backend-pytest-unit', tier: CRITICAL, cmd: 'pytest tests/' },
  { id: 'design-cross-check',  tier: WARNING,  cmd: 'python check_design_vs_code.py' },
  { id: 'ui-consistency',      tier: WARNING,  cmd: 'python audit_ui_consistency.py' },
  { id: 'backend-api-contract',tier: WARNING,  cmd: 'pytest tests/test_api.py' },
]
```

- 每个测试独立子进程，互不影响
- 结果统一汇总为 Markdown 报告
- 报告保存到 `tests/reports/regression_{timestamp}.md`
- 最新报告覆盖 `tests/reports/latest.md`（入 git 追踪）

### 5.2 设计交叉检查原理

```
设计文档需求列表       代码文件扫描
  ├── P0需求（必须实现）   →  monitor_service.py
  ├── P1需求（应该实现）   →  LeaderMonitor.tsx
  └── P2需求（可选）      →  api.ts / types.ts / server.py
```

每个需求关联多个"关键字"，只要代码中任何一个关键字出现就算"部分匹配"。
通过率 = (完全通过 + 部分通过×0.5) / 总数。

### 5.3 UI 审计原理

静态分析 5 个维度：

| 维度 | 检测方法 | 阈值 |
|:-----|:---------|:-----|
| 输入框风格 | 扫描 `<input>` 的 className 是否含 `search-input` | 必须≥1 |
| inline style | 统计 `style={{...}}` 出现次数 | >3 处 = 偏高 |
| 颜色值离散度 | 提取所有 `color/backgroundColor/borderColor` | <3 次 = 低频色 |
| 字号离散度 | 提取所有 `fontSize` | <2 次 = 异常 |
| 间距离散度 | 提取所有 `padding/margin/gap` | <2 次 = 异常 |

### 5.4 视觉回归原理

Playwright 启动 Chromium（无头模式）→ 导航到 monitor 页面 → 展开龙头观测区域 → 截图 → 对比基线。

当前基线 2 张：

| 截图 | 类型 | 覆盖区域 |
|:-----|:-----|:---------|
| leader-dashboard-full.png | 视口 | 全部页面 |
| leader-dashboard-watched.png | 元素 | 关注的行业表格 |

---

## 6. 检测能力矩阵

| 问题类型 | 前段渲染测试 | 后端单元测试 | 设计交叉检查 | UI 审计 | 视觉回归 | API 合约 |
|:---------|:----------:|:----------:|:----------:|:------:|:--------:|:--------:|
| 语法/编译错误 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 组件崩溃 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 空数据降级显示 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 逻辑错误 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 路由缺失 | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| API 字段变更 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 设计遗漏 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 搜索框风格不一致 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| inline style 泛滥 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 颜色/字号跑偏 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 布局偏移 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| CSS 崩坏 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 数据准确性 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 交互逻辑 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **空白区**（需人工判断）：数据对错、交互体验、动画效果、商业逻辑合理性。

---

## 7. 报告示例

### 生成的报告

```
# 3L 全回归测试报告

> 时间: 2026-05-28 17:30:00 | 模式: standard

## 总览

| 等级 | 通过 | 失败 | 总计 |
|:---|:---:|:---:|:---:|
| 🔴 **CRITICAL** | 2 | 0 | 2 |
| 🟡 **WARNING** | 3 | 0 | 3 |

## 详细结果

| # | 测试 | 等级 | 结果 | 耗时 | 摘要 |
|:---:|:---|:---:|:---:|:---:|:---:|
| 1 | 前端组件渲染测试 | 🔴CRITICAL | ✅ | 19s | 89 passed |
| 2 | 后端单元测试 | 🔴CRITICAL | ✅ | 49s | 649 passed |
| 3 | 设计文档交叉检查 | 🟡WARNING | ✅ | 0.1s | 覆盖率100% |
| 4 | UI风格一致性审计 | 🟡WARNING | ✅ | 0.1s | exit code: 0 |
| 5 | 后端API合约测试 | 🟡WARNING | ✅ | 2s | 3 passed |
```

### 入 git 追踪

每次回归运行，`tests/reports/latest.md` 被覆盖。
`git diff tests/reports/latest.md` 一眼看出本轮和上轮的变化。

---

## 8. 当前状态 (2026-05-28)

| 测试类型 | 文件/用例数 | 等级 | 最近结果 | 备注 |
|:---------|:----------:|:----:|:--------:|:-----|
| 前端 vitest | 13 文件 / 89 测试 | CRITICAL | ✅ | 组件层覆盖 |
| 后端 pytest | 649 测试（2跳过/1xfail）| CRITICAL | ✅ | 逻辑层覆盖 |
| 设计交叉检查 | 20 项需求 | WARNING | ✅ 100% | 龙头观测重构 |
| UI 风格审计 | 22 个 .tsx 文件 | WARNING | ✅ | 检测6个不一致页面 |
| API 合约测试 | 3 项 | WARNING | ✅ | leader-dashboard |
| 视觉回归 | 2 张截图 | INFO | ✅ | 基线就绪 |

### 文件结构

```
tests/
  test_api.py                    # API 合约测试（需服务运行）
  visual_regression.mjs          # 视觉回归（Playwright）
  frontend_e2e.mjs               # 前端 E2E（预留）
  reports/
    .gitkeep                     # 报告目录占位
    latest.md                    # ← 最新报告（入 git 追踪）
    regression_20260528_*.md     # 历史报告（不入 git）
  screenshots/
    baseline/                    # 基线截图（入 git）
    current/                     # 当前截图（不入 git）
scripts/
  run_full_regression.py         # 回归运行器
  audit_ui_consistency.py        # UI 风格审计
  check_design_vs_code.py        # 设计-代码交叉检查
```

---

## 9. 未来扩展

### P0 — 短期

- [ ] **前端 E2E 测试** — `tests/frontend_e2e.mjs` 已创建骨架，填充真实交互用例（搜索股票→加入自选→验证页面变化）

### P1 — 中期

- [ ] **性能基准测试** — 记录关键 API 响应时间、前端构建大小、页面加载速度，超过阈值报警
- [ ] **自动更新基线截图** — 当 WARNING/INFO 测试全部通过时，自动用当前截图替换基线

### P2 — 长期

- [ ] **差分报告** — 对比两次回归结果，自动高亮新增/消失的失败项
- [ ] **覆盖率追踪** — 前端 Istanbul + 后端 coverage.py，追踪代码覆盖率变化趋势

---

## 10. 常见问题

### Q: UI 审计报了"低频色"怎么办？

低频色不一定是问题。比如龙头异动的红色/绿色标记用 1-2 次很正常。
**判断标准**：如果这颜色是全局通用的（如 `#ff4444` 代表红色），应该抽到 CSS 变量；
如果是个性化标记色（如 `#ff8800` 代表特定板块），保留 inline style 没问题。

**处理方式**：先看具体颜色值，确认是否应该归入 CSS 变量，如果不是就标记为"允许"。
审计脚本现在只是报告，不阻塞，不会因为误报卡住构建。

### Q: 设计交叉检查报"缺失"怎么办？

检查两步：
1. 是真的没实现？→ 实现它
2. 实现了但关键字没匹配到？→ 更新 `scripts/check_design_vs_code.py` 的 REQUIREMENTS 列表，增加匹配关键字

### Q: 视觉回归截图一直失败？

最常见原因：
- 服务没运行（先 `sudo systemctl start 3l-server`）
- Playwright 浏览器依赖缺失（`npx playwright install chromium`）
- 页面结构变了导致选择器失效（更新 `visual_regression.mjs` 的 SHOTS 配置）

---

## 附录 A: Makefile 命令参考

| 命令 | 作用 | 耗时 |
|:-----|:-----|:----:|
| `make regression` | 全回归（5 项测试）| ~80s |
| `make regression-ci` | CI 模式（CRITICAL 只跑 2 项）| ~70s |
| `make audit-ui` | UI 风格审计 | ~0.1s |
| `make check-design` | 设计交叉检查 | ~0.1s |
| `make visual-regression` | 视觉回归截图 | ~8s |
| `make test` | 后端测试（旧命令）| ~50s |
| `make build` | 回归 + 构建 + 部署 | ~90s |

## 附录 B: 快速修复指南

| 问题 | 修复步骤 |
|:-----|:---------|
| 前端测试挂了 | `cd frontend && npx vitest --reporter=verbose` 看具体哪个用例 |
| 后端测试挂了 | `.venv/bin/python -m pytest tests/ -v --tb=long` 看详细堆栈 |
| UI 审计报错 | 先确认新代码是否该用共享类，是则加 className，否则更新审计阈值 |
| 基线要更新 | `node tests/visual_regression.mjs --update` |

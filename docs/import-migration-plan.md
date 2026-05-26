# Import 路径迁移计划

## 目标
将 25 个测试文件中的 150+ 处 `services.xxx`/`scripts.xxx` 引用统一为 `backend.services.xxx`/`backend.core.xxx`，然后删除旧目录。

## 当前状态
- ✅ `backend/` 内全部已清理（无旧 import）
- ❌ 测试文件仍有旧引用

## 执行步骤

### 步骤一：from services./scripts. → backend.services./backend.core.
- `from services.` → `from backend.services.`（约 25 个文件）
- `from scripts.` → `from backend.core.`（约 14 个文件）

### 步骤二：import services.xxx as mod → from backend.services import xxx as mod
- test_direction_service.py（2处）
- test_workbench_service.py（3处）

### 步骤三：patch('services.xxx') → patch('backend.services.xxx')
- 106 处普通 patch（跨模块的 config 引用除外）
- 用 sed 全局替换

### 步骤四：patch('services.xxx.config.yyy') → patch('backend.config.yyy')
- 3 处特殊处理（config 不是 services 的子模块）

### 步骤五：conftest.py
- 2 处 `from scripts.data_layer import ...`

### 步骤六：验证
- 全回归 29 failed + 1 xfailed = baseline

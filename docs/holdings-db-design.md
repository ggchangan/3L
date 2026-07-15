# 持仓数据库设计

## 背景
持仓数据从 JSON 文件迁移到 MySQL，预留多用户支持。

## 表设计

### 1. users（用户表）

```sql
CREATE TABLE users (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  username    VARCHAR(50) NOT NULL UNIQUE,
  display_name VARCHAR(100) DEFAULT '',
  is_active   TINYINT(1) DEFAULT 1,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2. holdings（持仓表）

```sql
CREATE TABLE holdings (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL,
  code            VARCHAR(10) NOT NULL COMMENT '6位股票代码',
  name            VARCHAR(50) NOT NULL COMMENT '股票名称',
  direction       VARCHAR(100) NOT NULL DEFAULT '' COMMENT '方向，如 算力硬件.CPO',
  target_ratio    DECIMAL(5,2) DEFAULT 0 COMMENT '目标仓位比例%',
  cost_price      DECIMAL(10,2) DEFAULT NULL COMMENT '成本价',
  stop_loss_price DECIMAL(10,2) DEFAULT NULL COMMENT '止损价',
  sector          VARCHAR(50) DEFAULT '' COMMENT '行业',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '软删除',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_code (user_id, code),
  FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 设计原则

1. **只存用户输入的静态字段** — `change`, `structure`, `stage`, `signal`, `fusion_type`, `triggered_signals` 等由系统实时计算，不落库
2. **软删除** — `is_active` 字段，不真正删除记录
3. **唯一约束** — 同一用户下不允许重复持仓同一股票（`(user_id, code)` 唯一）
4. **默认用户** — 初始化时插入 id=1 的用户 `default`

## 数据流

```
用户修改持仓 → api/write DB → holdings 表
复盘计算     → api/read DB → 结合行情实时算 dynamic 字段 → 返回给前端
```

## 迁移

1. 建表
2. 插入默认用户
3. 从 config/holdings.json 读取数据，写入 holdings 表（user_id=1）
4. 更新 review_service.py 从 DB 读持仓（替换 JSON 路径）

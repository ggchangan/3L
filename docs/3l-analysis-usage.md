# 3L-analysis 个股分析独立服务 — 使用手册

> 版本: v1.1 | 最后更新: 2026-05-29

---

## 一、服务概述

3L-analysis 是一个独立的个股分析服务，基于 3L 交易体系（动量主线/最强逻辑/量价行为）对 A 股进行技术面分析。支持按股票代码、名称、拼音搜索，返回结构、阶段、均线排列、买点信号、交易系统判定等数据。

### 架构

```
用户
  ├── Web 浏览器 → https://43.136.177.133/stock_analysis
  │     └── Nginx → Docker容器(3l-analysis:9090) → 数据目录
  │
  └── 微信小程序 → 后端API(同一地址)
        └── config.js 中配置 API_BASE
```

- **Web 前端**：暗色主题搜索页面，输入股票代码调 API 展示结果
- **API 后端**：Python HTTP 服务，运行在 Docker 容器中
- **小程序前端**：独立的微信小程序项目，调用同一套 API

---

## 二、访问方式

### 2.1 Web 页面

**地址：** `https://43.136.177.133/stock_analysis`

直接在浏览器打开即可使用。搜索框输入股票代码、名称或拼音首字母，回车或点"分析"按钮。

**示例：**
- `300750` → 宁德时代
- `002916` → 深南电路  
- `宁德` → 模糊搜索
- `300` → 按代码前缀搜索

### 2.2 API 接口

```
GET https://43.136.177.133/api/stock-analysis?q=<股票代码或名称>
```

**请求示例：**
```bash
curl -sk 'https://43.136.177.133/api/stock-analysis?q=300750'
```

**返回字段说明：**

| 字段 | 说明 | 示例 |
|:-----|:-----|:-----|
| `code` | 股票代码 | `300750` |
| `name` | 股票名称 | `宁德时代` |
| `structure` | 结构判定 | `上升趋势` / `下降趋势` / `震荡` |
| `stage` | 阶段判定 | `上行` / `转强` / `调整` |
| `ema` | 均线排列 | `多头` / `空头` / `交叉` |
| `trading_system` | 交易系统 | `3l` / `trend` |
| `trend_stock` | 是否为趋势股 | `true` / `false` |
| `buy_point` | 买点信号 | `涨停回踩` / `趋势回踩` / `空` |
| `buy_score` | 买点评分 | `0-100` |
| `deviation_pct` | 乖离率(BIAS5) | `2.35` |
| `vol_ratio` | 量比 | `1.28` |
| `stop_loss` | 止损位 | `395.91` |
| `stop_loss_pct` | 止损百分比 | `4.76` |
| `risk_reward_ratio` | 盈亏比 | `0.67` |
| `sector` | 所属板块 | `新能源` |

---

## 三、部署架构

### 3.1 服务组件

| 组件 | 技术栈 | 运行方式 |
|:-----|:-------|:---------|
| HTTP服务器 | Python 3.12 (http.server) | Docker 容器 |
| 反向代理 | Nginx 1.24 | 宿主机直接运行 |
| SSL证书 | 自签名 | Nginx 配置 |
| 数据存储 | JSON 文件 | 宿主机目录挂载 |

### 3.2 容器信息

```bash
# 查看容器状态
docker ps --filter name=3l-analysis

# 查看日志
docker logs 3l-analysis

# 重启容器
docker restart 3l-analysis

# 重建镜像（代码更新后）
cd /home/ubuntu
docker build -t 3l-analysis:latest -f 3l-analysis/Dockerfile .
docker stop 3l-analysis && docker rm 3l-analysis
docker run -d --name 3l-analysis -p 9090:9090 \
  -v /home/ubuntu/data/3l:/data/3l \
  -e DATA_DIR=/data/3l \
  --restart unless-stopped \
  3l-analysis:latest
```

### 3.3 Nginx 路由规则

```
/stock_analysis            → 前端页面（转发到 :9090）
/api/stock-analysis        → API 接口（转发到 :9090）
/                          → 3l-server 主服务（转发到 :8080）
```

---

## 四、配置域名（可选）

当前服务通过 IP + 自签名 SSL 访问。如需绑定域名：

1. **DNS 解析**：将域名 A 记录指向 `43.136.177.133`
2. **获取 SSL 证书**（推荐 Let's Encrypt）：
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d 你的域名
   ```
3. **更新 Nginx**：`/etc/nginx/sites-enabled/3l` 中的 `server_name`
4. **更新小程序**：`/home/ubuntu/3l-miniprogram/config.js` 中的 `API_BASE`
5. **重载 Nginx**：`sudo nginx -t && sudo systemctl reload nginx`

---

## 五、微信小程序发布指南

### 5.1 前提条件

- 一个已认证的微信小程序 AppID（个人或企业）
- 微信开发者工具（Windows/Mac，[下载地址](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)）
- 一个已备案的域名（生产环境必须，开发时可跳过）

### 5.2 开发调试

1. **打开小程序项目**
   - 启动微信开发者工具
   - 点击「导入项目」
   - 选择目录：你的电脑上存放 `/home/ubuntu/3l-miniprogram` 的本地路径
   - 填入你的 AppID
   - 点击「导入」

2. **配置不校验域名（开发用）**
   - 开发者工具右上角 → 详情 → 本地设置
   - 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」
   - 这样开发环境可以通过 IP 地址访问 API

3. **测试功能**
   - 在模拟器中输入股票代码（如 300750）
   - 点击「分析」按钮
   - 验证搜索结果和卡片展示正常

### 5.3 生产环境发布步骤

```
第1步：准备域名
  ├── 确保域名已 ICP 备案（必须，否则微信审核不通过）
  ├── DNS 解析指向 43.136.177.133
  └── 配置 Let's Encrypt SSL 证书（见第四章）
  
第2步：更新小程序配置
  ├── 修改 config.js：
  │     const API_BASE = 'https://你的域名/api'
  └── 确保 HTTPS 可访问

第3步：配置小程序后台
  ├── 登录 mp.weixin.qq.com
  ├── 开发 → 开发管理 → 服务器域名
  └── 在 request 合法域名中添加：https://你的域名

第4步：上传代码
  ├── 微信开发者工具 → 工具栏 → 上传
  ├── 填写版本号（如 1.0.0）
  └── 填写项目备注

第5步：提交审核
  ├── 登录小程序管理后台
  ├── 管理 → 版本管理 → 开发版本
  ├── 找到刚上传的版本 → 提交审核
  └── 填写审核说明（注意：金融类审核较严）

第6步：发布
  ├── 审核通过后（通常1-3个工作日）
  ├── 管理后台 → 版本管理 → 审核通过版本
  └── 点击「发布」
```

### 5.4 注意事项

- **金融类审核**：小程序涉及个股分析，可能被归类为金融证券类。建议：
  - 提交审核时说明是「个人学习研究工具，不构成投资建议」
  - 如被拒绝，可尝试走「工具」分类而非「金融」分类
  - 如果只是自用/小范围，可以用「体验版 + 白名单」方式不公开发布

- **体验版（不发布）**：
  - 开发者工具上传后，在管理后台将版本设为「体验版」
  - 添加体验者微信号（最多 100 人）
  - 体验者扫码即可使用，无需审核

- **小程序文件结构**：
  ```
  3l-miniprogram/
  ├── app.js               # 全局 JS
  ├── app.json             # 全局配置（页面、窗口样式）
  ├── app.wxss             # 全局样式
  ├── config.js            # API 地址配置（唯一需要改的地方）
  ├── sitemap.json         # 搜索索引
  └── pages/index/
      ├── index.js         # 页面逻辑
      ├── index.wxml       # 页面结构
      ├── index.wxss       # 页面样式
      └── index.json       # 页面配置
  ```

---

## 六、常见问题

### Q: 搜索不到股票？
A: 数据只包含 3L 系统跟踪的行业板块股票（约200+只），不在跟踪列表内的股票搜不到。后续可扩展全量 A 股搜索。

### Q: 小程序编译报错？
A: 确认微信开发者工具版本为最新稳定版，导入项目时选择正确的 AppID。

### Q: 如何更新后端代码？
A: 修改 `3l-analysis/` 或 `3l-core/` 后，按 3.2 节步骤重建 Docker 镜像即可。

### Q: API 返回慢？
A: 首次请求会加载数据文件（约 5MB JSON），后续请求命中内存缓存，通常 < 200ms。

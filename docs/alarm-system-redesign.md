# 报警系统实现文档 v3.5

> 更新 2026-05-30：已完成全部实现，新增前端复选框处理/频次分级/全量展示

## 架构总览

```
后端独立线程（server.py 启动时，daemon=True, 30s 间隔）
  ├─ _sync_holdings_to_alarms() → 持仓止损自动同步
  ├─ 读 alarms.json → 腾讯行情 → 判断价格/偏差条件
  ├─ 触发 → 写入 alarms.json (triggered_at)
  └─ 有触发 → WxPusher 直推微信（不依赖 Hermes）

前端 30s 轮询
  ├─ /api/alarms/list-all → 全量报警（含已处理）同步到底部面板
  └─ status=active 的新报警 → 逐个弹 toast + 播音乐
```

## 报警频次分级

| 类型 | 推送频次 | 后端去重机制 |
|------|---------|------------|
| 🔴 大盘预警 (market/critical) | **每3分钟** | `_check_index_dedup` 内存缓存，3分钟窗口 |
| 🔴 跌破止损 (price/stop) | **每30秒** | `_has_recently_triggered` 检查 triggered_at，半分钟窗口 |
| 🟡 异动偏离 (deviation) | **每30分钟** | `_check_deviation_dedup` 内存缓存，30分钟窗口 |

## 微信推送（WxPusher）

三种类型各发一条独立消息，不合并：

```
🔴 大盘预警 (N条)
• 科创50 今日大跌4.2%！超过3%预警线！

🔴 跌破止损 (N只)
• 华工科技(000988) 止损163.88 现价160.20（-2.24%）

🟡 异动偏离 (N只)
• 北方华创 6.8%
```

配置在 `.env`：`WXPUSHER_TOKEN` + `WXPUSHER_UID`，可在 `/alarm-sounds` 页在线配置。

## 前端报警面板

- **顶部 toast 弹窗**：新触发报警弹出，仅 × 关闭，不承载处理功能
- **底部报警层面板**：全量报警列表（含已处理/未触发/未处理）
  - status=active（待处理）：正常显示 + 复选框未勾选 ☐
  - status=handled（已处理）：灰色背景 + 文字划线 + 复选框已勾选 ✅
  - 点击复选框：勾选→dismiss API / 取消勾选→reenable API
  - 刷新页面不丢失已处理记录

## 报警音乐

- `<audio>` 元素通过 DOM API 创建（`document.createElement('audio')`），完全绕过 React JSX 渲染
- 初始静音，用户点右下角按钮开启后取消静音
- 多个报警按优先级排队播放
- 声音文件放在 `public/assets/sounds/`，Vite 构建时自动拷贝到 `dist/`
- 可在 `/alarm-sounds` 页面上传替换音乐文件

## 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/alarms/list` | GET | 返回 status=active 的报警 |
| `/api/alarms/list-all` | GET | 返回全部报警（含 handled） |
| `/api/alarms/dismiss` | POST | 标记已处理（status=handled） |
| `/api/alarms/reenable` | POST | 重新启用（status=active） |
| `/api/alarms/remove` | POST | 删除报警 |
| `/api/alarm-sounds` | GET | 返回音乐配置 |
| `/api/wxpush/status` | GET | 返回 WxPusher 配置状态 |
| `/api/wxpush/config` | POST | 更新 WxPusher Token/UID |
| `/api/wxpush/test` | GET | 发送测试消息到微信 |

## 关键文件

| 文件 | 职责 |
|------|------|
| `server.py` | 启动时调用 `start_alert_checker(30)` |
| `check_alerts.py` | 报警检测 + 频次控制 + 微信推送分发 |
| `alarm_service.py` | alarms.json 读写 + dismiss/reenable 持久化 |
| `wxpush_sender.py` | WxPusher HTTP API 封装 |
| `Monitor.tsx` | 30s 轮询 `/api/alarms/list-all` 推 toast + 面板 |
| `AlarmLayer.tsx` | toast 弹窗 + 底部报警层面板 + 声音播放 |

## 已知限制（时间回放功能，暂缓）

时间回溯回放（Time-machine Replay）的设计草案在 `index-monitor-alarm-music-design.md §9` 中已有方案，但尚未实现，后续再做。

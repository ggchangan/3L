"""
报警检查服务 — 价格报警 + 偏差报警

从 alarm_service（alarms.json）读取持久化报警配置，检查条件是否触发。
核心股偏差报警由 direction_service 提供，与用户手动报警并行。
"""
import json
import os
import re
import requests
from datetime import date, datetime, timedelta

from backend.config import DATA_DIR
from backend.services.alarm_service import (
    get_active_alarms,
    mark_alarm_triggered,
)

# ── 内部接口 ──────────────────────────────────────────


def _parse_stock_code(stock_str: str) -> str:
    """从 '北方华创(002371)' 中解析出 002371"""
    if not stock_str:
        return None
    m = re.search(r'\((\d{6})\)', stock_str)
    return m.group(1) if m else None


def _get_core_stocks() -> dict:
    """从 direction_service 读取核心股列表 {code: {name, deviation}}"""
    from backend.services.direction_service import get_core_stocks
    return get_core_stocks()


def _norm_code(code: str) -> str:
    """为腾讯行情接口添加交易所前缀"""
    c = code.strip().upper().replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
    if c.startswith('6') or c.startswith('9'):
        return f'sh{c}'
    return f'sz{c}'


def _get_realtime_data(code: str) -> tuple:
    """通过腾讯行情接口获取实时数据

    Returns:
        (price, change_pct) 或 (0, 0)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com'
    }
    qcode = _norm_code(code)
    try:
        r = requests.get(
            f'https://qt.gtimg.cn/q={qcode}',
            headers=headers,
            timeout=5
        )
        line = r.text.strip()
        fields = line.split('"')[1].split('~') if '"' in line else []
        if len(fields) > 3:
            price = float(fields[3]) if fields[3] else 0
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
            return (price, change_pct)
        return (0, 0)
    except Exception:
        return (0, 0)


def _has_recently_triggered(alarm: dict, minutes: int = 0.5) -> bool:
    """检查报警是否在最近 minutes 分钟内已触发过"""
    triggered_at = alarm.get('triggered_at')
    if not triggered_at:
        return False
    try:
        t = datetime.fromisoformat(triggered_at)
        return (datetime.now() - t).total_seconds() < minutes * 60
    except Exception:
        return False


def _auto_dismiss_price_alarm(alarm: dict):
    """价格回升到止损价上方 → 自动标记为已解除"""
    from backend.services.alarm_service import dismiss_alarm
    alarm_id = alarm.get('id', '')
    if alarm_id:
        dismiss_alarm(alarm_id)


def _calc_ema(closes: list, period: int) -> float:
    """计算EMA值，返回最新一天的EMA"""
    if len(closes) < period:
        return None
    multiplier = 2.0 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema
    return round(ema, 2)


def _try_refresh_index_data():
    """检查指数数据是否过时，从 index_sh_data.json 增量同步中证全指
    
    在报警检查前调用，确保EMAs基于最新收盘数据计算。
    不含网络请求，不会卡住。
    """
    _sync_index_from_sh()


def _auto_dismiss_index_alarm(code: str):
    """指数恢复（价格回到EMA上方）→ 自动清除报警，永久沉默"""
    from backend.services.alarm_service import _load, _save
    data = _load()
    changed = False
    for a in data.get('alarms', []):
        if a.get('stock_code') == code and a.get('type') in ('market', 'market_critical') and a.get('status') != 'handled':
            a['status'] = 'handled'
            a['dismissed_at'] = datetime.now().isoformat()
            changed = True
    if changed:
        _save(data)


def _is_non_trading_day() -> bool:
    """判断当前是否为非交易日（复用 data_models.is_trading_day）"""
    from backend.core.data_models import is_trading_day
    today_str = datetime.now().strftime('%Y-%m-%d')
    return not is_trading_day(today_str)


# ── 外部接口 ──────────────────────────────────────────


# ── 指数监测 ──────────────────────────────────────────

# 指数代码 → 腾讯行情 qcode 映射
INDEX_CODES = {
    '000001': ('sh000001', '上证指数'),
    '000688': ('sh000688', '科创50'),
    '000985': ('sh000985', '中证全指'),
}

# 指数报警去重缓存：{(code, condition): triggered_timestamp}
_index_alert_cache: dict = {}

INDEX_DATA_PATH = os.path.join(
    os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'index_sh_data.json'
)


def _read_index_data() -> dict:
    """读取 index_sh_data.json（统一指数数据文件）

    格式: {last_updated, indices: {code: {name, klines}}}
    Returns:
        完整指数数据 dict，失败返回 {}
    """
    if not os.path.isfile(INDEX_DATA_PATH):
        return {}
    try:
        with open(INDEX_DATA_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_index_realtime(qcode: str) -> tuple:
    """获取指数实时行情，返回 (price, change_pct)

    与个股接口相同，但 qcode 直接传 sh000688 格式
    """
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'}
    try:
        r = requests.get(f'https://qt.gtimg.cn/q={qcode}', headers=headers, timeout=5)
        line = r.text.strip()
        fields = line.split('"')[1].split('~') if '"' in line else []
        if len(fields) > 3:
            price = float(fields[3]) if fields[3] else 0
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
            return (price, change_pct)
        return (0, 0)
    except Exception:
        return (0, 0)


def _check_index_dedup(code: str, condition: str, alarm_type: str) -> bool:
    """检查指数报警是否在频次限制内已触发过

    按类型使用不同去重窗口：
      - market/market_critical: 3 分钟
    """
    window_minutes = 3  # 大盘预警每3分钟可重报一次
    key = (code, condition)
    now = datetime.now().timestamp()
    last_ts = _index_alert_cache.get(key)
    if last_ts and (now - last_ts) < window_minutes * 60:
        return True  # 窗口期内已触发，跳过
    _index_alert_cache[key] = now
    # 清理过期缓存
    expired = [k for k, v in _index_alert_cache.items() if (now - v) > window_minutes * 60]
    for k in expired:
        _index_alert_cache.pop(k, None)
    return False


def _is_index_dismissed(code: str) -> bool:
    """检查指数报警是否已被标记为已处理（handle=永久沉默）"""
    alarms_path = os.path.join(
        os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'private', 'alarms.json'
    )
    try:
        with open(alarms_path) as f:
            data = json.load(f)
        for a in data.get('alarms', []):
            if a.get('stock_code') == code and a.get('status') == 'handled':
                return True
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass
    return False


def check_index_alerts() -> list:
    """检查三只指数的报警条件

    条件:
      - 日涨跌 > 3% → type=market
      - 跌破 EMA10 → type=market (短期破位)
      - 跌破 EMA20 → type=market (中期破位)
      - 跌>3% + 破EMA10/20 → type=market_critical (双重确认)

    Returns:
      triggered list (同 check_all_alerts 格式)
    """
    from backend.services.alarm_service import save_alarm
    index_data = _read_index_data()
    indices = index_data.get('indices', {})
    now_ts = datetime.now().timestamp()
    triggered = []

    for code, (qcode, name) in INDEX_CODES.items():
        info = indices.get(code)
        if not info:
            continue

        klines = info.get('klines', [])
        if len(klines) < 20:
            continue

        # 实时从K线计算EMA10和EMA20
        closes = [k['close'] for k in klines]
        ema10 = _calc_ema(closes, 10)
        ema20 = _calc_ema(closes, 20)
        if ema10 is None or ema20 is None:
            continue

        # 检查用户是否已标记该指数为已处理（跟个股报警逻辑一致）
        if _is_index_dismissed(code):
            continue

        # 拉实时价（腾讯 API 直接返回涨跌幅）
        price, change_pct = _get_index_realtime(qcode)
        if price <= 0:
            continue

        is_big_drop = change_pct < -3
        is_break_10 = price < ema10
        is_break_20 = price < ema20

        # 自动清除：价格回到EMA10/EMA20上方 → 消除旧的跌破报警
        if not is_break_10 and not is_break_20:
            _auto_dismiss_index_alarm(code)

        if is_big_drop and (is_break_10 or is_break_20):
            level = 'EMA10' if is_break_10 else 'EMA20'
            if not _check_index_dedup(code, 'critical', 'market_critical'):
                alarm_type = 'market_critical'
                msg = f'{name} 跌{abs(change_pct):.1f}% 且跌破{level}({ema10 if is_break_10 else ema20:.0f})，风险警告！'
                triggered.append({
                    'type': alarm_type, 'stock': name, 'code': code,
                    'current_price': price, 'daily_change': round(change_pct, 2),
                    'ema_break': level, 'msg': msg, 'ts': now_ts,
                })
                _save_index_alarm(code, name, alarm_type, msg)
        elif is_big_drop:
            if not _check_index_dedup(code, 'drop', 'market'):
                alarm_type = 'market'
                msg = f'{name} 今日大跌{abs(change_pct):.1f}%！超过3%预警线！'
                triggered.append({
                    'type': alarm_type, 'stock': name, 'code': code,
                    'current_price': price, 'daily_change': round(change_pct, 2),
                    'msg': msg, 'ts': now_ts,
                })
                _save_index_alarm(code, name, alarm_type, msg)
        elif is_break_10:
            if not _check_index_dedup(code, 'break10', 'market'):
                alarm_type = 'market'
                msg = f'{name} 跌破EMA10({ema10:.0f})短期支撑，现价{price}！'
                triggered.append({
                    'type': alarm_type, 'stock': name, 'code': code,
                    'current_price': price, 'ema10': ema10, 'msg': msg, 'ts': now_ts,
                })
                _save_index_alarm(code, name, alarm_type, msg)
        elif is_break_20:
            if not _check_index_dedup(code, 'break20', 'market'):
                alarm_type = 'market'
                msg = f'{name} 跌破EMA20({ema20:.0f})中期支撑，现价{price}！'
                triggered.append({
                    'type': alarm_type, 'stock': name, 'code': code,
                    'current_price': price, 'ema20': ema20, 'msg': msg, 'ts': now_ts,
                })
                _save_index_alarm(code, name, alarm_type, msg)

    return triggered


def _save_index_alarm(code: str, name: str, alarm_type: str, msg: str):
    """将指数报警写入 alarms.json，供前端 /api/alarms/list 读取"""
    from backend.services.alarm_service import save_alarm, mark_alarm_triggered
    result = save_alarm({
        'stock': f'{name}({code})',
        'stock_code': code,
        'type': alarm_type,  # market 或 market_critical
        'enabled': False,
        'condition': '',
        'source': 'index_monitor',
    })
    if result.get('id'):
        # 直接更新 triggered_at 并附带 msg
        import json, os
        alarms_path = os.path.join(
            os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'), 'private', 'alarms.json'
        )
        try:
            with open(alarms_path) as f:
                data = json.load(f)
            for a in data['alarms']:
                if a.get('id') == result['id']:
                    a['triggered_at'] = datetime.now().isoformat()
                    a['msg'] = msg  # 附带消息文本
                    a['status'] = 'active'  # 保持 active 让 list 接口返回
                    break
            with open(alarms_path, 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _sync_holdings_to_alarms():
    """将持仓止损自动同步到 alarms.json

    读取 holdings.json，将带 stop_loss_price 的持仓自动创建 price 报警。
    如果该股已有手动报警（source != holdings_auto），保留手动配置。
    """

    try:
        holdings_path = os.path.join(DATA_DIR, 'private', 'holdings.json')
        if not os.path.exists(holdings_path):
            return
        with open(holdings_path) as f:
            hdata = json.load(f)
        items = hdata.get('holdings', []) if isinstance(hdata, dict) else hdata
        if not isinstance(items, list):
            return

        from backend.services.alarm_service import save_alarm, get_active_alarms
        existing = get_active_alarms()
        manual_keys = {
            (a['stock_code'], a['type'])
            for a in existing if a.get('source') != 'holdings_auto'
        }

        for item in items:
            code = item.get('code', '')
            name = item.get('name', '')
            stop_loss = item.get('stop_loss_price') or item.get('stop_loss')
            if not code or not stop_loss:
                continue
            if (code, 'price') in manual_keys:
                continue  # 手动报警优先
            save_alarm({
                'stock': f'{name}({code})',
                'stock_code': code,
                'type': 'price',
                'enabled': True,
                'stop_loss': stop_loss,
                'stop_loss_pct': item.get('stop_loss_pct'),
                'condition': '',
                'source': 'holdings_auto',
            })
    except Exception:
        pass  # 同步失败不影响报警检查


# 偏离报警去重缓存（30分钟）
_deviation_cache: dict = {}


def _check_deviation_dedup(code: str) -> bool:
    """检查偏离报警是否在30分钟内已触发过"""
    window_minutes = 30
    now = datetime.now().timestamp()
    last_ts = _deviation_cache.get(code)
    if last_ts and (now - last_ts) < window_minutes * 60:
        return True
    _deviation_cache[code] = now
    # 清理过期
    expired = [k for k, v in _deviation_cache.items() if (now - v) > window_minutes * 60]
    for k in expired:
        _deviation_cache.pop(k, None)
    return False


def check_all_alerts() -> dict:
    """检查所有报警（价格+偏差）

    从 alarm_service 读取 active 报警 + 核心股自动偏差，
    合并检查后返回触发结果。

    Returns:
        {'triggered': [{type, stock, code, msg, ts}], 'count': N}
    """
    # 非交易日跳过报警检查（周五处理的报警，周六不重复报）
    if _is_non_trading_day():
        return {'triggered': [], 'count': 0}

    now_ts = datetime.now().timestamp()

    # ① 自动同步持仓止损到 alarms.json
    _sync_holdings_to_alarms()

    # ② 从 alarms.json 读取用户手动设置的报警
    user_alarms = get_active_alarms()

    # ③ 核心股自动偏差
    core_stocks = _get_core_stocks()

    triggered = []

    # 检查用户报警
    for alarm in user_alarms:
        code = alarm.get('stock_code', '')
        if not code:
            code = _parse_stock_code(alarm.get('stock', ''))
        if not code:
            continue

        alarm_type = alarm.get('type', '')
        stock_str = alarm.get('stock', '')

        # 刚触发过的跳过（默认0.5分钟），用户未标记处理就一直报
        if _has_recently_triggered(alarm):
            continue

        if alarm_type == 'price':
            stop_loss = alarm.get('stop_loss')
            if not stop_loss:
                continue
            price, _ = _get_realtime_data(code)
            if price <= 0:
                continue

            # 自动清除：价格回到止损价上方 → 报警已解除
            if price > stop_loss and alarm.get('triggered_at'):
                _auto_dismiss_price_alarm(alarm)
                continue

            if price <= stop_loss:
                loss_pct = round((price - stop_loss) / stop_loss * 100, 2)
                triggered.append({
                    'type': 'price',
                    'id': alarm.get('id', ''),  # 报警 ID，前端"已处理"用
                    'stock': stock_str,
                    'code': code,
                    'current_price': price,
                    'stop_loss': stop_loss,
                    'loss_pct': loss_pct,
                    'msg': f'{stock_str} 跌破止损 {stop_loss}，现价 {price}（{loss_pct}%）',
                    'ts': now_ts,
                })
                mark_alarm_triggered(alarm['id'])

        elif alarm_type == 'deviation':
            try:
                threshold = float(alarm.get('condition', 6))
            except (ValueError, TypeError):
                threshold = 6
            _, change_pct = _get_realtime_data(code)
            if change_pct == 0:
                continue
            if abs(change_pct) > threshold:
                direction = '上涨' if change_pct > 0 else '下跌'
                triggered.append({
                    'type': 'deviation',
                    'stock': stock_str,
                    'code': code,
                    'change_pct': change_pct,
                    'threshold': threshold,
                    'msg': f'{stock_str} {direction} {abs(change_pct)}%，超过偏差阈值{threshold}%',
                    'ts': now_ts,
                })
                mark_alarm_triggered(alarm['id'])

    # ③ 核心股自动偏差（独立于用户报警）
    for code, info in core_stocks.items():
        name = info.get('name', code)
        max_dev = abs(info.get('deviation', 6))

        # 检查这个核心股是否已经有用户报警触发了，避免重复
        already_triggered = any(
            t['code'] == code for t in triggered
        )
        if already_triggered:
            continue

        _, change_pct = _get_realtime_data(code)
        if change_pct == 0:
            continue

        if abs(change_pct) > max_dev:
            if _check_deviation_dedup(code):
                continue
            direction = '上涨' if change_pct > 0 else '下跌'
            triggered.append({
                'type': 'deviation',
                'stock': name,
                'code': code,
                'change_pct': change_pct,
                'threshold': max_dev,
                'msg': f'{name} {direction} {abs(change_pct)}%，超过偏差阈值{max_dev}%（核心股自动）',
                'ts': now_ts,
            })

    # ④ 指数监测（大盘/破位报警）
    index_triggered = check_index_alerts()
    triggered.extend(index_triggered)

    # ⑤ 恐慌监测（A股恐慌检测+推送）
    from backend.services.panic_monitor_service import check_panic_alerts_via_realtime
    panic_triggered = check_panic_alerts_via_realtime()
    triggered.extend(panic_triggered)

    return {'triggered': triggered, 'count': len(triggered)}


# ── WxPusher 微信推送（直接发送，不依赖 Hermes）───

from backend.services.wxpush_sender import send_alert


def _push_wechat(triggered: list):
    """按类型分组推送微信，每类一条独立消息"""
    if not triggered:
        return
    import logging
    logger = logging.getLogger(__name__)

    # 按类型分组
    market_alarms = [t for t in triggered if t.get('type') in ('market', 'market_critical')]
    price_alarms = [t for t in triggered if t.get('type') in ('price', 'stop')]
    deviation_alarms = [t for t in triggered if t.get('type') in ('deviation', 'warn', 'stock')]
    panic_alarms = [t for t in triggered if t.get('type') == 'panic']

    try:
        if market_alarms:
            items = '\n'.join(f'• {t.get("msg", t.get("stock", ""))}' for t in market_alarms)
            send_alert(f'🔴 大盘预警 ({len(market_alarms)}条)', items, alarm_type='market')

        if price_alarms:
            items = '\n'.join(
                f'• {t.get("stock", t.get("code", ""))} 止损{t.get("stop_loss", "?")} 现价{t.get("current_price", "?")}（{t.get("loss_pct", "")}%）'
                for t in price_alarms
            )
            send_alert(f'🔴 跌破止损 ({len(price_alarms)}只)', items, alarm_type='price')

        if deviation_alarms:
            items = '\n'.join(
                f'• {t.get("stock", t.get("code", ""))} {t.get("change_pct", "")}%'
                for t in deviation_alarms
            )
            send_alert(f'🟡 异动偏离 ({len(deviation_alarms)}只)', items, alarm_type='deviation')

        if panic_alarms:
            for t in panic_alarms:
                send_alert(f'🔴 A股恐慌', t.get('msg', ''), alarm_type='panic')
    except Exception:
        logger.exception('微信推送失败')


# ── 后端独立检测线程 ─────────────────────────────────


def start_alert_checker(interval: int = 30) -> 'threading.Thread':
    """启动后端独立报警检测线程

    在 server.py 启动时调用，每 interval 秒自动检查一次报警条件。
    不依赖前端轮询触发。

    Args:
        interval: 检测间隔（秒），默认 30

    Returns:
        threading.Thread 对象（daemon=True）
    """
    import threading

    def _loop():
        while True:
            try:
                result = check_all_alerts()
                if result['count'] > 0:
                    _push_wechat(result['triggered'])
            except Exception:
                pass
            import time
            time.sleep(interval)

    thread = threading.Thread(target=_loop, daemon=True, name='alert-checker')
    thread.start()
    return thread

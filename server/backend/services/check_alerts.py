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


def _get_realtime_data(code: str) -> tuple:
    """通过腾讯行情接口获取实时数据

    Returns:
        (price, change_pct) 或 (0, 0)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com'
    }
    try:
        r = requests.get(
            f'https://qt.gtimg.cn/q={code}',
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


def _has_recently_triggered(alarm: dict, minutes: int = 5) -> bool:
    """检查报警是否在最近 minutes 分钟内已触发过"""
    triggered_at = alarm.get('triggered_at')
    if not triggered_at:
        return False
    try:
        t = datetime.fromisoformat(triggered_at)
        return (datetime.now() - t).total_seconds() < minutes * 60
    except Exception:
        return False


# ── 外部接口 ──────────────────────────────────────────


def check_all_alerts() -> dict:
    """检查所有报警（价格+偏差）

    从 alarm_service 读取 active 报警 + 核心股自动偏差，
    合并检查后返回触发结果。

    Returns:
        {'triggered': [{type, stock, code, msg, ts}], 'count': N}
    """
    now_ts = datetime.now().timestamp()

    # ① 从 alarms.json 读取用户手动设置的报警
    user_alarms = get_active_alarms()

    # ② 核心股自动偏差
    core_stocks = _get_core_stocks()

    triggered = []

    # 检查用户报警
    for alarm in user_alarms:
        code = alarm.get('stock_code', '')
        if not code:
            code = _parse_stock_code(alarm.get('stock', ''))
        if not code:
            continue

        # 刚触发过的（5分钟内），跳过避免重复弹
        if _has_recently_triggered(alarm):
            continue

        alarm_type = alarm.get('type', '')
        stock_str = alarm.get('stock', '')

        if alarm_type == 'price':
            stop_loss = alarm.get('stop_loss')
            if not stop_loss:
                continue
            price, _ = _get_realtime_data(code)
            if price <= 0:
                continue
            if price <= stop_loss:
                loss_pct = round((price - stop_loss) / stop_loss * 100, 2)
                triggered.append({
                    'type': 'price',
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

    return {'triggered': triggered, 'count': len(triggered)}

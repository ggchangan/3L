"""
报警检查服务 — 价格报警

从工作台日志读取今日计划中的报警配置，检查条件是否触发。
"""
import json
import os
import re
import requests
from datetime import date, datetime

from backend.config import DATA_DIR

WORKBENCH_DIR = os.path.join(DATA_DIR, 'private', 'workbench')

# ── 内部接口（可 mock）──────────────────────────────────


def _load_workbench_plan(date_str: str = None) -> dict:
    """读取指定日期的工作台日志，返回 plan 部分"""
    dt = date_str or date.today().isoformat()
    fp = os.path.join(WORKBENCH_DIR, f'{dt}.json')
    if not os.path.isfile(fp):
        return {'buy': [], 'sell': [], 'watch': []}
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('plan', {'buy': [], 'sell': [], 'watch': []})


def _parse_stock_code(stock_str: str) -> str:
    """从 '北方华创(002371)' 中解析出 002371"""
    if not stock_str:
        return None
    m = re.search(r'\((\d{6})\)', stock_str)
    return m.group(1) if m else None


def _get_realtime_price(code: str) -> float:
    """通过腾讯行情接口获取实时股价"""
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
        return float(fields[3]) if len(fields) > 3 else 0
    except Exception:
        return 0


# ── 外部接口 ──────────────────────────────────────────


def check_price_alerts(date_str: str = None) -> dict:
    """检查今日计划中的价格报警

    Args:
        date_str: 工作台日志日期（默认今天），通常是昨天 -> 今天检查

    Returns:
        {'triggered': [{stock, code, current_price, stop_loss, loss_pct, ts}], 'count': N}
    """
    plan = _load_workbench_plan(date_str)
    triggered = []
    now_ts = datetime.now().timestamp()

    for category in ('buy', 'sell', 'watch'):
        for item in plan.get(category, []):
            alert = item.get('alert')
            if not alert or not alert.get('enabled'):
                continue
            if alert.get('type') != 'price':
                continue

            stop_loss = item.get('stop_loss')
            if not stop_loss:
                continue

            stock_str = item.get('stock', '')
            code = _parse_stock_code(stock_str)
            if not code:
                continue

            current_price = _get_realtime_price(code)
            if current_price <= 0:
                continue

            if current_price <= stop_loss:
                loss_pct = round((current_price - stop_loss) / stop_loss * 100, 2)
                triggered.append({
                    'stock': stock_str,
                    'code': code,
                    'current_price': current_price,
                    'stop_loss': stop_loss,
                    'loss_pct': loss_pct,
                    'ts': now_ts,
                })

    return {'triggered': triggered, 'count': len(triggered)}

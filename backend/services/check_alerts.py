"""
报警检查服务 — 价格报警 + 偏差报警

从工作台日志读取今日计划中的报警配置，以及核心股列表，
检查条件是否触发。
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
            # 涨跌幅在 fields[32]（腾讯行情格式）
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
            return (price, change_pct)
        return (0, 0)
    except Exception:
        return (0, 0)


# ── 外部接口 ──────────────────────────────────────────


def check_all_alerts(date_str: str = None, merge_dates: list = None) -> dict:
    """检查所有报警（价格+偏差）

    从核心股列表自动检查偏差报警 + 从工作台计划检查价格/偏差报警。
    支持 merge_dates 合并多天计划。

    Args:
        date_str: 单日工作台日志日期
        merge_dates: 多日日期列表，合并后统一检查

    Returns:
        {'triggered': [{type, stock, code, msg, ts}], 'count': N}
    """
    core_stocks = _get_core_stocks()
    now_ts = datetime.now().timestamp()

    # 合并多天计划
    plan = _load_workbench_plan(date_str)
    if merge_dates:
        plan = {'buy': [], 'sell': [], 'watch': []}
        seen = set()
        for d in merge_dates:
            p = _load_workbench_plan(d)
            for cat in ('buy', 'sell', 'watch'):
                for item in p.get(cat, []):
                    # 按 stock 去重，后加载的覆盖先加载的
                    stock = item.get('stock', '')
                    key = f'{cat}:{stock}'
                    if key not in seen:
                        seen.add(key)
                        plan[cat].append(item)
                    else:
                        # 替换同名项
                        for j, existing in enumerate(plan[cat]):
                            if existing.get('stock') == stock:
                                plan[cat][j] = item
                                break

    triggered = []
    triggered += _check_price_alerts(plan, now_ts)
    triggered += _check_deviation_alerts(plan, core_stocks, now_ts)

    return {'triggered': triggered, 'count': len(triggered)}


def check_price_alerts(date_str: str = None) -> dict:
    """仅检查价格报警（向后兼容）"""
    plan = _load_workbench_plan(date_str)
    now_ts = datetime.now().timestamp()
    return {'triggered': _check_price_alerts(plan, now_ts), 'count': 0}


def _check_price_alerts(plan: dict, now_ts: float) -> list:
    """检查计划项中的价格报警"""
    triggered = []
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
    return triggered


def _check_deviation_alerts(plan: dict, core_stocks: dict, now_ts: float) -> list:
    """检查偏差报警（核心股自动 + 计划项手动）"""
    triggered = []

    # 需要检查的集合：{code: {name, max_deviation}}
    check_set = {}

    # ① 核心股自动
    for code, info in core_stocks.items():
        check_set[code] = {
            'name': info.get('name', code),
            'max_dev': abs(info.get('deviation', 6)),
        }

    # ② 计划项手动
    for category in ('buy', 'sell', 'watch'):
        for item in plan.get(category, []):
            alert = item.get('alert')
            if not alert or not alert.get('enabled'):
                continue
            if alert.get('type') != 'deviation':
                continue
            # 偏差阈值从 alert.condition 取（数字字符串）
            try:
                threshold = float(alert.get('condition', 6))
            except (ValueError, TypeError):
                threshold = 6

            stock_str = item.get('stock', '')
            code = _parse_stock_code(stock_str)
            if not code or code in check_set:
                continue

            check_set[code] = {
                'name': stock_str,
                'max_dev': threshold,
            }

    if not check_set:
        return []

    for code, info in check_set.items():
        _, change_pct = _get_realtime_data(code)
        if change_pct == 0:
            continue

        if abs(change_pct) > info['max_dev']:
            direction = '上涨' if change_pct > 0 else '下跌'
            triggered.append({
                'type': 'deviation',
                'stock': info['name'],
                'code': code,
                'change_pct': change_pct,
                'threshold': info['max_dev'],
                'msg': f'{info["name"]} {direction} {abs(change_pct)}%，超过偏差阈值{info["max_dev"]}%',
                'ts': now_ts,
            })

    return triggered

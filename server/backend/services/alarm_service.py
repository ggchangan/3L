"""
报警持久化存储服务 — alarms.json

报警与每日计划解耦，独立持久化。
- 工作台保存时通过 sync_alarms_from_plan() 同步
- check_alerts 从 get_active_alarms() 读取
- 不过期，直到触发/手动删除/禁用
"""
import json
import os
import re
import time
from datetime import date, datetime, timedelta

from backend.config import DATA_DIR

ALARMS_DIR = os.path.join(DATA_DIR, 'private')
ALARMS_PATH = os.path.join(ALARMS_DIR, 'alarms.json')
os.makedirs(ALARMS_DIR, exist_ok=True)


def _load() -> dict:
    """读取 alarms.json，不存在返回空结构"""
    if not os.path.isfile(ALARMS_PATH):
        return {'alarms': []}
    try:
        with open(ALARMS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {'alarms': []}


def _save(data: dict):
    """写入 alarms.json"""
    with open(ALARMS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _generate_id(stock_code: str) -> str:
    """生成唯一报警 ID"""
    ts = int(time.time() * 1000)
    return f'alarm_{stock_code}_{ts}'


def _parse_stock_code(stock_str: str) -> str:
    """从 '北方华创(002371)' 解析出 002371"""
    if not stock_str:
        return None
    m = re.search(r'\((\d{6})\)', stock_str)
    return m.group(1) if m else None


def get_alarms() -> list:
    """返回全部报警（含已触发/过期）"""
    return _load().get('alarms', [])


def get_active_alarms() -> list:
    """返回当前生效的报警（status=active）"""
    return [a for a in get_alarms() if a.get('status') == 'active']


def save_alarm(alarm: dict) -> dict:
    """添加或更新一条报警

    按 (stock_code, type) 匹配，存在则更新，不存在则新增。
    """
    data = _load()
    alarms = data['alarms']
    stock_code = alarm.get('stock_code', '')
    alarm_type = alarm.get('type', '')

    # 查找已有
    found = None
    for a in alarms:
        if a.get('stock_code') == stock_code and a.get('type') == alarm_type:
            found = a
            break

    if found:
        # 更新字段（不含 status — status 由 dismissed_at 决定）
        for k in ('stock', 'type', 'enabled', 'stop_loss', 'stop_loss_pct', 'condition', 'source'):
            if k in alarm:
                found[k] = alarm[k]
        # 状态由 dismissed_at 驱动，不看 caller 传了什么
        dismissed_at = found.get('dismissed_at')
        if dismissed_at:
            try:
                d = datetime.fromisoformat(dismissed_at).date()
                source = found.get('source', '')
                if d < date.today() and source in ('holdings_auto', 'manual'):
                    # 新交易日 → 持仓止损/手动报警重新生效
                    found['status'] = 'active'
                    found.pop('silenced_until', None)
                elif d >= date.today():
                    # 同一天 dismiss → 强制 handled（修复旧代码误重置）
                    found['status'] = 'handled'
            except (ValueError, TypeError):
                pass
        found['updated'] = datetime.now().isoformat()
        _save(data)
        return {'success': True, 'id': found['id'], 'action': 'updated'}
    else:
        # 新增
        new_alarm = {
            'id': _generate_id(stock_code),
            'stock': alarm.get('stock', ''),
            'stock_code': stock_code,
            'type': alarm_type,
            'enabled': alarm.get('enabled', True),
            'stop_loss': alarm.get('stop_loss'),
            'stop_loss_pct': alarm.get('stop_loss_pct'),
            'condition': alarm.get('condition', ''),
            'source': alarm.get('source', 'manual'),
            'created': datetime.now().isoformat(),
            'status': 'active',
            'expires_days': 7,
        }
        alarms.append(new_alarm)
        _save(data)
        return {'success': True, 'id': new_alarm['id'], 'action': 'created'}


def remove_alarm(alarm_id: str) -> dict:
    """按 ID 删除报警"""
    data = _load()
    alarms = data['alarms']
    before = len(alarms)
    data['alarms'] = [a for a in alarms if a.get('id') != alarm_id]
    if len(data['alarms']) < before:
        _save(data)
        return {'success': True}
    return {'success': False}


def mark_alarm_triggered(alarm_id: str) -> dict:
    """标记报警为已触发（仅更新触发时间，不改状态，保持活跃可继续检查）"""
    data = _load()
    for a in data['alarms']:
        if a.get('id') == alarm_id:
            a['triggered_at'] = datetime.now().isoformat()
            a['status'] = 'active'  # 保持 active，让 get_active_alarms 继续返回
            _save(data)
            return {'success': True}
    return {'success': False}


def dismiss_alarm(alarm_id: str) -> dict:
    """标记报警为「已处理」— 不再触发推送，手动重新启用前保持沉默

    设置 status=handled + silenced_until=明日15:00（市场收盘）
    """
    data = _load()
    for a in data['alarms']:
        if a.get('id') == alarm_id:
            a['status'] = 'handled'
            a['dismissed_at'] = datetime.now().isoformat()
            # 沉默到明日收盘（避免收盘后触发）
            tomorrow = date.today() + timedelta(days=1)
            a['silenced_until'] = f'{tomorrow.strftime("%Y%m%d")}150000'
            _save(data)
            return {'success': True, 'id': alarm_id, 'status': 'handled'}
    return {'success': False, 'error': '报警不存在'}


def reenable_alarm(alarm_id: str) -> dict:
    """重新启用已处理的报警"""
    data = _load()
    for a in data['alarms']:
        if a.get('id') == alarm_id:
            a['status'] = 'active'
            a.pop('silenced_until', None)
            a.pop('dismissed_at', None)
            _save(data)
            return {'success': True, 'id': alarm_id, 'status': 'active'}
    return {'success': False, 'error': '报警不存在'}


def sync_alarms_from_plan(plan: dict) -> dict:
    """从计划项同步报警

    遍历 buy/sell/watch 中的每一项：
    - 有 alert 且 enabled → 同步到 alarms.json（新增或更新）
    - 无 alert 或 disabled → 从 alarms.json 移除对应的报警

    Returns:
        {'synced': N, 'removed': M}
    """
    # 收集当前计划项中的 (stock_code, type) 集合
    current_keys = set()
    for category in ('buy', 'sell', 'watch'):
        for item in plan.get(category, []):
            stock_str = item.get('stock', '')
            code = _parse_stock_code(stock_str)
            if not code:
                continue

            alert = item.get('alert')
            has_explicit_alert = alert and alert.get('enabled')
            has_stop_loss = item.get('stop_loss') is not None

            if has_explicit_alert:
                # 有显式报警 → 按用户配置
                alarm_type = alert.get('type', 'price')
                current_keys.add((code, alarm_type))
                alarm = {
                    'stock': stock_str,
                    'stock_code': code,
                    'type': alarm_type,
                    'enabled': True,
                    'stop_loss': item.get('stop_loss'),
                    'stop_loss_pct': item.get('stop_loss_pct'),
                    'condition': alert.get('condition', ''),
                }
                save_alarm(alarm)
            elif has_stop_loss:
                # 有止损价但没有显式报警 → 自动创建价格报警
                alarm_type = 'price'
                current_keys.add((code, alarm_type))
                alarm = {
                    'stock': stock_str,
                    'stock_code': code,
                    'type': 'price',
                    'enabled': True,
                    'stop_loss': item.get('stop_loss'),
                    'stop_loss_pct': item.get('stop_loss_pct'),
                    'condition': '',
                }
                save_alarm(alarm)

    # 移除已失效的报警：扫描 alarms.json 中所有 active 的报警，
    # 如果不在 current_keys 中则移除（但保留 source=holdings_auto 的）
    data = _load()
    removed = 0
    remaining = []
    for a in data['alarms']:
        key = (a.get('stock_code', ''), a.get('type', ''))
        if a.get('source') == 'holdings_auto':
            remaining.append(a)  # 持仓自动报警不被计划同步删除
        elif a.get('status') == 'active' and key not in current_keys:
            removed += 1
            continue  # 丢弃
        else:
            remaining.append(a)
    data['alarms'] = remaining
    _save(data)

    return {'synced': len(current_keys), 'removed': removed}


def cross_day_reactivate():
    """全局跨日重置：扫描所有 handled 报警，如果 dismiss 日期是昨天或更早 → 恢复 active

    适用于 holdings_auto / manual / plan 源的报警。单独运行，与调用 save_alarm 解耦。
    """
    data = _load()
    changed = 0
    today = date.today()
    for a in data['alarms']:
        if a.get('status') != 'handled':
            continue
        dismissed_at = a.get('dismissed_at')
        if not dismissed_at:
            continue
        try:
            d = datetime.fromisoformat(dismissed_at).date()
        except (ValueError, TypeError):
            continue
        source = a.get('source', '')
        if d < today and source in ('holdings_auto', 'manual'):
            a['status'] = 'active'
            a.pop('silenced_until', None)
            changed += 1
        elif d >= today:
            # 确保同天 dismiss 的不被旧代码误重置
            a['status'] = 'handled'
            changed += 1
    if changed:
        _save(data)
    return changed

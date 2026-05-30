#!/usr/bin/env python3
"""推送新触发的报警到微信 — 供 cron 使用

每2分钟由 cron 调用一次。
有新的触发报警则 stdout 输出消息（cron 自动投递到微信），
无新报警则静默（不输出）。
"""
import json
import os
import sys
from datetime import datetime, timezone

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
ALARMS_PATH = os.path.join(DATA_DIR, 'private', 'alarms.json')
STATE_FILE = os.path.join(DATA_DIR, 'private', '.last_wechat_push')


def get_last_push_time() -> float:
    try:
        with open(STATE_FILE) as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def save_last_push_time(ts: float):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        f.write(str(ts))


def parse_iso(s: str) -> float:
    """解析 ISO 时间戳为 epoch seconds"""
    try:
        dt = datetime.fromisoformat(s)
        return dt.timestamp()
    except Exception:
        return 0.0


def main():
    last_push = get_last_push_time()
    now = datetime.now().timestamp()

    try:
        with open(ALARMS_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # silent

    # 找触发时间 > last_push 的 active 报警
    new_alarms = []
    for a in data.get('alarms', []):
        if a.get('status') != 'active':
            continue
        triggered_at = a.get('triggered_at')
        if not triggered_at:
            continue
        ts = parse_iso(triggered_at)
        if ts > last_push:
            new_alarms.append(a)

    if not new_alarms:
        return  # silent

    # 按类型分组
    price_alarms = [a for a in new_alarms if a.get('type') == 'price']
    deviation_alarms = [a for a in new_alarms if a.get('type') == 'deviation']

    lines = []
    if price_alarms:
        lines.append(f'🔴 跌破止损（{len(price_alarms)}只）:')
        for a in price_alarms:
            stock = a.get('stock', a.get('stock_code', ''))
            sl = a.get('stop_loss', '?')
            lines.append(f'  {stock} 止损{sl}')

    if deviation_alarms:
        lines.append(f'🟡 异动偏离（{len(deviation_alarms)}只）:')
        for a in deviation_alarms:
            stock = a.get('stock', a.get('stock_code', ''))
            cond = a.get('condition', 6)
            lines.append(f'  {stock} 偏离{cond}%')

    if lines:
        print(f'⚠️ 3L 报警推送 ({datetime.now().strftime("%H:%M")})')
        for line in lines:
            print(line)

    save_last_push_time(now)


if __name__ == '__main__':
    main()

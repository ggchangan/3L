"""
WxPusher 微信推送模块 — 完全替代 Hermes 依赖

用法：
  from backend.services.wxpush_sender import send_alert
  send_alert("⚠️ 大盘预警", "📉 科创50跌超3%", alarm_type="market_critical")

配置：
  .env:
    WXPUSHER_TOKEN=AT_xxxx           # 必填
    WXPUSHER_UID=UID_xxxx            # 接收者的用户ID（从 WxPusher 后台获取）
"""
import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

# 从 .env 读取
WXPUSHER_TOKEN = os.environ.get('WXPUSHER_TOKEN', '')
WXPUSHER_UID = os.environ.get('WXPUSHER_UID', '')

API_SEND = 'https://wxpusher.zjiecode.com/api/send/message'
API_QRCODE = 'https://wxpusher.zjiecode.com/api/fun/create/qrcode'


def is_configured() -> dict:
    """检查 WxPusher 是否配好，返回状态信息供前端展示"""
    return {
        'configured': bool(WXPUSHER_TOKEN and WXPUSHER_UID),
        'has_token': bool(WXPUSHER_TOKEN),
        'has_uid': bool(WXPUSHER_UID),
        'uid': WXPUSHER_UID,
    }


def update_config(token: str = None, uid: str = None) -> bool:
    """更新 .env 中的 WxPusher 配置

    写入 ~/3l-server/.env
    """
    env_path = os.path.join(
        os.environ.get('WWW_DIR', '/home/ubuntu/3l-server'), '.env'
    )
    if not os.path.isfile(env_path):
        logger.error(f'.env not found at {env_path}')
        return False

    import re

    with open(env_path, 'r') as f:
        content = f.read()

    changed = False
    if token:
        if 'WXPUSHER_TOKEN=' in content:
            content = re.sub(
                r'WXPUSHER_TOKEN=.*',
                f'WXPUSHER_TOKEN={token}',
                content,
            )
        else:
            content += f'\nWXPUSHER_TOKEN={token}\n'
        changed = True
        global WXPUSHER_TOKEN
        WXPUSHER_TOKEN = token

    if uid:
        if 'WXPUSHER_UID=' in content:
            content = re.sub(
                r'WXPUSHER_UID=.*',
                f'WXPUSHER_UID={uid}',
                content,
            )
        else:
            content += f'\nWXPUSHER_UID={uid}\n'
        changed = True
        global WXPUSHER_UID
        WXPUSHER_UID = uid

    if changed:
        with open(env_path, 'w') as f:
            f.write(content)
        os.environ['WXPUSHER_TOKEN'] = WXPUSHER_TOKEN
        os.environ['WXPUSHER_UID'] = WXPUSHER_UID
        logger.info('WxPusher 配置已更新')
        return True
    return True


def send_alert(title: str, body: str = '', alarm_type: str = '') -> bool:
    """发送报警消息到微信

    Args:
        title: 消息标题（如"⚠️ 大盘预警"）
        body: 消息正文（支持 markdown）
        alarm_type: 报警类型，用于去重标记

    Returns:
        True 表示发送成功
    """
    if not WXPUSHER_TOKEN:
        logger.warning('WxPusher 未配置 WXPUSHER_TOKEN，无法发送')
        return False

    if not WXPUSHER_UID:
        logger.warning('WxPusher 未配置 WXPUSHER_UID，无法发送')
        return False

    # 组装 content（markdown 格式）
    if body:
        content = f'# {title}\n\n{body}'
    else:
        content = title

    payload = {
        'appToken': WXPUSHER_TOKEN,
        'content': content,
        'contentType': 3,  # 3=markdown
        'uids': [WXPUSHER_UID],
        'summary': title,  # 微信通知摘要
    }

    try:
        resp = requests.post(API_SEND, json=payload, timeout=10)
        data = resp.json()
        if data.get('code') == 1000:
            logger.info(f'微信报警已发送: {title}')
            return True
        else:
            logger.error(f'WxPusher API 错误: {data}')
            return False
    except requests.RequestException as e:
        logger.error(f'WxPusher 请求失败: {e}')
        return False


def send_alert_batch(triggered: list) -> bool:
    """将多只股票的报警合并为一条微信消息发送

    替代原来的 _push_wechat() 和 _format_wechat_msg()
    """
    if not triggered:
        return True

    from datetime import datetime
    now = datetime.now().strftime('%H:%M')

    # 按类型分组
    price_alarms = [t for t in triggered if t.get('type') in ('price', 'stop')]
    deviation_alarms = [t for t in triggered if t.get('type') in ('deviation', 'warn', 'stock')]
    market_alarms = [t for t in triggered if t.get('type') in ('market', 'market_critical')]

    parts = []
    # 大盘预警放最前面
    if market_alarms:
        items = '\n'.join(f'• {t.get("msg", t.get("stock", ""))}' for t in market_alarms)
        parts.append(f'## 🔴 大盘预警\n{items}')

    if price_alarms:
        items = '\n'.join(
            f'• {t.get("stock", t.get("code", ""))} 止损{t.get("stop_loss", "?")} 现价{t.get("current_price", "?")}（{t.get("loss_pct", "")}%）'
            for t in price_alarms
        )
        parts.append(f'## 🔴 跌破止损（{len(price_alarms)}只）\n{items}')

    if deviation_alarms:
        items = '\n'.join(
            f'• {t.get("stock", t.get("code", ""))} {t.get("change_pct", "")}%'
            for t in deviation_alarms
        )
        parts.append(f'## 🟡 异动偏离（{len(deviation_alarms)}只）\n{items}')

    title = f'⚠️ 3L 报警 ({now}) — {len(triggered)}条'
    body = '\n\n---\n\n'.join(parts)
    return send_alert(title, body)

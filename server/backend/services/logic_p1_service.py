"""
逻辑追踪 P1 组合服务

包含：自动升降级建议、最强逻辑股池生成、聚焦推送
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _get_store():
    from backend.core.logic_tracking_store import LogicTrackingStore
    return LogicTrackingStore()


# ═══════════════════════════════════════════════════
# 自动升降级建议
# ═══════════════════════════════════════════════════

def compute_tier_suggestions():
    """计算所有标签的升降级建议

    Returns: [{
        tag_id, tag_name, current_tier, suggested_tier,
        reason, event_count, verify_rate
    }, ...]
    """
    store = _get_store()
    tags = store.get_tags()
    suggestions = []

    for tag in tags:
        tier = tag.get('tier', 'watch')
        event_count = tag.get('event_count', 0) or 0
        verify_rate = tag.get('verify_rate', 0) or 0

        # 检查最近的entry，看30天内有没有新事件
        entries = store.get_entries(tag_id=tag['id'])
        recent_entries = [e for e in entries if e.get('fed_at', '')[:10] >= (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')]
        recent_events = len(recent_entries)
        recent_verified = [e for e in recent_entries if e.get('verify', {}).get('score') == 'confirmed']
        recent_verify_rate = len(recent_verified) / max(recent_events, 1)

        suggestion = None
        reason = ''

        if tier == 'watch' and event_count >= 3 and verify_rate >= 0.6:
            suggestion = 'core'
            reason = f'累计{event_count}个事件且印证率{int(verify_rate*100)}%≥60%'
        elif tier == 'core' and recent_events == 0 and event_count > 0:
            suggestion = 'watch'
            reason = f'30天无新事件'
        elif tier == 'core' and recent_events >= 3 and recent_verify_rate <= 0.3:
            suggestion = 'watch'
            reason = f'最近{recent_events}个事件印证率{int(recent_verify_rate*100)}%≤30%'

        if suggestion:
            suggestions.append({
                'tag_id': tag['id'],
                'tag_name': tag.get('name', ''),
                'current_tier': tier,
                'suggested_tier': suggestion,
                'reason': reason,
                'event_count': event_count,
                'verify_rate': verify_rate,
            })

    return suggestions


# ═══════════════════════════════════════════════════
# 最强逻辑股池
# ═══════════════════════════════════════════════════

def generate_top_pool():
    """从聚焦+核心逻辑提取个股，组装最强逻辑股池

    Returns: [{
        code, name, logic_tags: [{tag_name, tier}],
        event_count, verify_rate, recent_return,
        buy_signal: str or None,
    }, ...]
    """
    store = _get_store()
    tags = store.get_tags()
    active_tags = [t for t in tags if t.get('tier') in ('focused', 'core')]

    pool = {}
    for tag in active_tags:
        tier = tag.get('tier')
        for stock_code in tag.get('related_stocks', []):
            if stock_code not in pool:
                pool[stock_code] = {
                    'code': stock_code,
                    'name': _get_stock_name(stock_code),
                    'logic_tags': [],
                    'event_count': 0,
                    'verify_rate': 0,
                }
            pool[stock_code]['logic_tags'].append({
                'tag_name': tag.get('name', ''),
                'tier': tier,
            })
            pool[stock_code]['event_count'] += tag.get('event_count', 0)
            pool[stock_code]['verify_rate'] = max(
                pool[stock_code]['verify_rate'],
                tag.get('verify_rate', 0) or 0
            )

    # Get buy signals for all pool stocks
    for code, info in pool.items():
        info['buy_signal'] = _get_buy_signal(code)

    return sorted(pool.values(), key=lambda x: x['verify_rate'], reverse=True)


# ═══════════════════════════════════════════════════
# 聚焦推送 → 报警池
# ═══════════════════════════════════════════════════

def push_focused_alarms():
    """检查聚焦逻辑的关联个股异常，写入报警池

    Returns: [alarm_message, ...]
    """
    store = _get_store()
    tags = store.get_tags()
    focused = [t for t in tags if t.get('tier') == 'focused']
    alarms = []

    for tag in focused:
        for code in tag.get('related_stocks', []):
            card = _get_stock_card(code)
            if card and card.get('stage') in ('sell', 'risk', 'danger'):
                alarms.append({
                    'type': 'logic_alert',
                    'message': f'{tag["name"]}→{card.get("name", code)}阶段{card.get("stage", "")}',
                    'code': code,
                    'tag': tag['name'],
                    'time': datetime.now().strftime('%H:%M'),
                })

    # Write alarms to existing alarm pool file
    if alarms:
        _write_alarms(alarms)

    return alarms


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _get_stock_name(code):
    name_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'all_a_stocks.json')
    if os.path.isfile(name_path):
        with open(name_path) as f:
            names = json.load(f)
        return names.get(code, code)
    return code


def _get_buy_signal(code):
    try:
        from backend.services.stock_card_service import get_stock_card
        card = get_stock_card(code, datetime.now().strftime('%Y%m%d'))
        if card and card.get('buy_point_detected'):
            return card.get('buy_point_type', '买点')
        # Check trend buy point
        if card and card.get('trend_buy_signal'):
            return '趋势买点'
    except Exception:
        pass
    return None


def _get_stock_card(code):
    try:
        from backend.services.stock_card_service import get_stock_card
        return get_stock_card(code, datetime.now().strftime('%Y%m%d'))
    except Exception:
        return None


def _write_alarms(alarms):
    alarm_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache', 'logic_alarms.json')
    os.makedirs(os.path.dirname(alarm_path), exist_ok=True)
    existing = []
    if os.path.isfile(alarm_path):
        try:
            with open(alarm_path) as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.extend(alarms)
    # Keep last 50
    existing = existing[-50:]
    with open(alarm_path, 'w') as f:
        json.dump(existing, f, ensure_ascii=False)

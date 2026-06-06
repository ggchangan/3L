"""
恐慌监测服务 — 实时检测A股恐慌，提供应对策略
"""
import json
import os
from datetime import datetime

from backend.config import DATA_DIR, atomic_json_dump

from backend import config

# ── 恐慌阈值（基于历史回测：上证指数最近6个月） ──
# 回测结论（2026-06-06，94个交易日）：
#   上证 ≥2.0%: 2次/6月 (5.2次/年)，1日后+1.54%(100%胜率)
#   上证 ≥3.0%: 1次/6月 (2.6次/年)，3日后+1.99%
#   科创50波动极大，单独用会误报，联合下跌家数使用
INDEX_THRESHOLDS = {
    '上证指数': {'caution': 1.8, 'warning': 3.0},
    '深证成指': {'caution': 2.5, 'warning': 4.0},
    '创业板指': {'caution': 2.5, 'warning': 4.5},
    '科创50':   {'caution': 3.0, 'warning': 5.0},
    '中证全指': {'caution': 2.0, 'warning': 3.5},
}

DECLINE_COUNT_CAUTION = 3500   # 全市场下跌家数 > 3500 → 注意
DECLINE_COUNT_WARNING = 4000   # 下跌家数 > 4000 → 预警

MAX_HISTORY = 20
HISTORY_PATH = os.path.join(DATA_DIR, 'public', 'panic_history.json')


def detect_panic(indices, decline_count=0, total=5100):
    """
    检测恐慌等级

    参数:
        indices:    {指数名: {change_pct: float, ...}}
        decline_count: 全市场下跌家数
        total:         全市场股票总数

    返回:
        {
            'level': 'warning' | 'caution' | None,
            'triggered_at': 'HH:MM' or None,
            'triggers': [{'index': ..., 'change_pct': ..., 'threshold': ...}, ...]
        }
    """
    triggers = []
    
    # 维度1：指数跌幅
    for name, info in indices.items():
        chg = info.get('change_pct', 0)
        thresholds = INDEX_THRESHOLDS.get(name)
        if not thresholds:
            continue
        
        if chg <= -thresholds['warning']:
            triggers.append({
                'index': name,
                'change_pct': round(chg, 2),
                'threshold': thresholds['warning'],
                'level': 'warning',
            })
        elif chg <= -thresholds['caution']:
            triggers.append({
                'index': name,
                'change_pct': round(chg, 2),
                'threshold': thresholds['caution'],
                'level': 'caution',
            })
    
    # 维度2：下跌家数
    decline_ratio = decline_count / total if total > 0 else 0
    
    # 只在下雪家数高时才触发，防止正常震荡
    if decline_count > DECLINE_COUNT_WARNING:
        triggers.append({
            'index': f'下跌家数 {decline_count}/{total} ({decline_ratio*100:.0f}%)',
            'change_pct': 0,
            'threshold': DECLINE_COUNT_WARNING,
            'level': 'warning',
            'is_decline_count': True,
        })
    elif decline_count > DECLINE_COUNT_CAUTION:
        triggers.append({
            'index': f'下跌家数 {decline_count}/{total} ({decline_ratio*100:.0f}%)',
            'change_pct': 0,
            'threshold': DECLINE_COUNT_CAUTION,
            'level': 'caution',
            'is_decline_count': True,
        })
    
    if not triggers:
        return {
            'level': None,
            'triggered_at': None,
            'triggers': [],
        }
    
    # 取最高等级
    max_level = 'warning' if any(t['level'] == 'warning' for t in triggers) else 'caution'
    
    return {
        'level': max_level,
        'triggered_at': datetime.now().strftime('%H:%M'),
        'triggers': triggers,
    }


def generate_strategy(level, indices_data):
    """
    根据恐慌等级生成应对策略

    参数:
        level: 'warning' | 'caution' | None
        indices_data: {指数名: 涨跌幅}

    返回:
        策略字典（含路径+原则）
    """
    if not level:
        return {}
    
    # 基于3L体系 + 用户PDF内容的策略
    strategy = {
        'caution': {
            'paths': [
                {'name': '低开恐慌→日内V反', 'probability': 50,
                 'action': '持有，不急着卖，等午后确认'},
                {'name': '低开震荡→持续走弱', 'probability': 30,
                 'action': '减仓弱势股，执行止损'},
                {'name': '小幅低开→快速修复', 'probability': 20,
                 'action': '持有不动'},
            ],
            'principle': '恐慌急跌时不要卖 — 等第一个5-15分钟走完看后续确认。V反→持有，持续弱→减仓，快速修复→不动。',
        },
        'warning': {
            'paths': [
                {'name': '低开恐慌→日内V反', 'probability': 50,
                 'action': '持有，不急跌卖，等午后确认'},
                {'name': '低开震荡→持续走弱', 'probability': 35,
                 'action': '减仓弱势股，执行止损'},
                {'name': '小幅低开→快速修复', 'probability': 15,
                 'action': '持有不动'},
            ],
            'principle': '恐慌急跌时不要卖 — 等第一个5-15分钟走完看后续确认。V反→持有，持续弱→减仓，快速修复→不动。',
        },
    }
    
    return strategy.get(level, {})


def save_panic_record(record, path_override=None):
    """
    持久化恐慌记录（去重：同一天同一级别不重复记录）

    参数:
        record: {'date', 'time', 'level', 'trigger', ...}
        path_override: 可选测试路径
    """
    history_path = path_override or HISTORY_PATH
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    
    # 读取现有历史
    history = []
    if os.path.isfile(history_path):
        try:
            with open(history_path, encoding='utf-8') as f:
                data = json.load(f)
                history = data if isinstance(data, list) else data.get('records', [])
        except (json.JSONDecodeError, Exception):
            history = []
    
    # 去重：同一天同一级别不重复记录
    date = record.get('date', '')
    level = record.get('level', '')
    if any(h.get('date') == date and h.get('level') == level for h in history):
        return False  # 已存在，不重复
    
    # 追加到开头
    history.insert(0, record)
    
    # 限制数量
    if len(history) > MAX_HISTORY:
        history = history[:MAX_HISTORY]
    
    atomic_json_dump(history, history_path)
    return True


def get_panic_history(path_override=None):
    """
    读取恐慌历史记录

    参数:
        path_override: 可选测试路径

    返回:
        [{'date', 'time', 'level', 'trigger', ...}, ...]
    """
    history_path = path_override or HISTORY_PATH
    if not os.path.isfile(history_path):
        return []
    try:
        with open(history_path, encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get('records', [])
    except (json.JSONDecodeError, Exception):
        return []


def get_panic_monitor(indices_dict, decline_count=0, total=5100):
    """
    综合函数：检测恐慌+生成策略+读取历史
    供 macro_service.py 调用

    参数:
        indices_dict: {指数名: {change_pct, ...}}
        decline_count: 全市场下跌家数

    返回:
        {'level', 'triggered_at', 'triggers', 'strategy', 'history'}
    """
    # 检测恐慌
    panic = detect_panic(indices_dict, decline_count, total)
    
    # 如果触发了恐慌，保存记录
    if panic['level']:
        trigger_desc = '; '.join(
            f"{t['index']} {t['change_pct']:.2f}%" if not t.get('is_decline_count')
            else t['index']
            for t in panic['triggers'][:3]
        )
        record = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M'),
            'level': panic['level'],
            'trigger': trigger_desc,
            'indices': {k: v.get('change_pct') for k, v in indices_dict.items()},
        }
        save_panic_record(record)
    
    # 生成策略
    strategy = generate_strategy(panic['level'], indices_dict)

    # 增强策略：加入市场环境+主线方向+整体策略
    if panic['level']:
        try:
            from backend.services.market_health_service import get_market_health
            mh = get_market_health()
            if isinstance(mh, dict) and 'error' not in mh:
                strategy['market_overview'] = {
                    'structure': mh.get('structure', '—'),
                    'stage': mh.get('stage', '—'),
                    'position_advice': mh.get('position_advice', '—'),
                    'bias20': mh.get('bias20', 0),
                }
                ml = mh.get('mainline', {})
                if ml:
                    top_sectors = []
                    if isinstance(ml, dict):
                        for k in ['top_industries', 'top_sectors', 'strong_sectors', 'leaders']:
                            v = ml.get(k, [])
                            if isinstance(v, list):
                                top_sectors.extend(v[:5])
                            elif isinstance(v, str):
                                top_sectors.append(v)
                    strategy['mainline_sectors'] = top_sectors[:8] if top_sectors else []
        except Exception:
            pass

        # 整体策略总结
        strategy['overall_summary'] = {
            'principle': '恐慌急跌时不要卖 — 等第一个5-15分钟走完看后续确认。V反→持有，持续弱→减仓，快速修复→不动。',
            'key_points': [
                '上涨趋势的标的 → 恐慌是关注点，不是卖点',
                '区间底部的标的 → 已经最低区域，向下空间有限',
                '接近止损的标的 → 到了就走，不犹豫',
                '突破被大盘拖回的标的 → 等两天看突破效力还在不在',
            ],
            'conclusion': '降低止损的核心，不完全在于止损点的设置，而在于耐心等待一个好买点',
        }

    # 读取历史
    history = get_panic_history()
    
    return {
        'level': panic['level'],
        'triggered_at': panic['triggered_at'],
        'triggers': panic['triggers'],
        'strategy': strategy,
        'history': history,
    }


def check_panic_alerts_via_realtime(indices_api_codes: dict = None) -> list:
    """从腾讯API拉取实时指数数据，检测恐慌，返回 WxPusher 推送格式列表

    供 check_alerts.py 的 check_all_alerts() 调用。
    使用与 check_alerts.py 相同的腾讯API拉取模式。
    """
    import logging
    logger = logging.getLogger(__name__)
    now_ts = datetime.now().timestamp()
    triggered = []

    if indices_api_codes is None:
        indices_api_codes = {
            'sh000001': '上证指数', 'sz399001': '深证成指',
            'sz399006': '创业板指', 'sh000688': '科创50',
            'sh000985': '中证全指', 'us.INX': '标普500',
        }

    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'}
    q_str = ','.join(indices_api_codes.keys())
    try:
        import requests
        r = requests.get(f'https://qt.gtimg.cn/q={q_str}', headers=headers, timeout=10)
    except Exception:
        logger.warning('恐慌检测：腾讯API请求失败')
        return triggered

    indices = {}
    for line in r.text.strip().split(';'):
        if '="' not in line:
            continue
        key = line.split('=')[0].strip()
        parts = line.split('"')[1].split('~') if '"' in line else []
        if len(parts) < 10:
            continue
        name = indices_api_codes.get(key, parts[1] if len(parts) > 1 else '')
        price = float(parts[3]) if parts[3] else 0
        prev = float(parts[4]) if parts[4] else price
        chg = round((price - prev) / prev * 100, 2) if prev > 0 else 0
        indices[name] = {'change_pct': chg, 'price': price}

    if not indices:
        return triggered

    # 检查今天是否已经推送过同级别恐慌
    last_panic_level = None
    today = datetime.now().strftime('%Y-%m-%d')
    if os.path.isfile(HISTORY_PATH):
        try:
            with open(HISTORY_PATH) as f:
                data = json.load(f)
            records = data if isinstance(data, list) else data.get('records', [])
            for rec in records:
                if rec.get('date') == today:
                    last_panic_level = rec.get('level')
                    break
        except Exception:
            pass

    # 检测恐慌
    panic = detect_panic(indices, decline_count=0, total=5100)

    if panic['level'] and panic['level'] != last_panic_level:
        trigger_desc = '; '.join(
            f"{t['index']} {t['change_pct']:.2f}%" if not t.get('is_decline_count') else t['index']
            for t in panic['triggers'][:3]
        )
        msg = (
            f"🔴 A股恐慌{'预警' if panic['level'] == 'warning' else '注意'}\n"
            f"触发: {trigger_desc}\n"
            f"时间: {today} {panic['triggered_at']}\n\n"
            f"📋 应对策略：\n"
            f"① 低开→V反(50%)：持有，不急跌卖\n"
            f"② 低开→走弱(35%)：减仓弱势股\n"
            f"③ 低开→修复(15%)：持有不动\n"
        )
        triggered.append({
            'type': 'panic',
            'stock': 'A股恐慌',
            'msg': msg,
            'ts': now_ts,
            'level': panic['level'],
        })

        # 持久化记录（用于去重+历史展示）
        save_panic_record({
            'date': today,
            'time': panic['triggered_at'],
            'level': panic['level'],
            'trigger': trigger_desc,
            'indices': {k: v.get('change_pct') for k, v in indices.items()},
        })
        logger.info(f"恐慌检测推送: {panic['level']} — {trigger_desc}")

    return triggered

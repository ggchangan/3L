"""
盯盘监控服务 — 量价、买点信号、止损、板块龙头数据
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import requests

from config import CACHE_DIR, INDUSTRY_LEADERS_PATH, WWW_DIR, atomic_json_dump
from services.logger import get_logger

log = get_logger(__name__)

# ── 行业龙头模块级缓存 ──────────────────────────────────
_leaders_cache_data = None
_leaders_cache_time = 0


def get_volume_comparison():
    """量价对比 — 今日/昨日/5日均量"""
    from scripts.monitor_data import get_volume_comparison
    return get_volume_comparison()


def get_buy_signals():
    """买点信号扫描（1小时缓存）"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(
        CACHE_DIR,
        f'buy_signals_{datetime.now().strftime("%Y-%m-%d_%H")}.json'
    )
    # 1小时内已有缓存，且数据有效（至少2条信号且有完整字段），直接读取返回
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            sigs = data.get('signals', [])
            # 校验：有效数据至少1条，且第1条有 name 字段（区分脏数据如 [{"code":"300750"}]）
            if len(sigs) >= 1 and sigs[0].get('name') is not None:
                log.info('买点信号缓存命中 (%d条)', len(sigs))
                return data
            elif data.get('error'):
                # 错误字典直接返回
                log.info('买点信号缓存命中（错误）')
                return data
            else:
                log.warning('买点信号缓存无效（仅%d条或缺少字段），重新扫描', len(sigs))
        except Exception:
            log.warning('买点信号缓存读取失败，重新扫描')
    # 超过1小时重新扫描
    scan_file = os.path.join(WWW_DIR, 'scripts', 'scan_buy_signals.py')
    log.info('买点信号缓存过期，启动扫描...')
    try:
        r = subprocess.run(
            [sys.executable, scan_file],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            atomic_json_dump(data, cache_file)
            log.info('买点信号扫描完成 (%d条)', len(data.get('signals', [])))
            return data
        else:
            log.warning('买点信号扫描失败 (code=%d): %s', r.returncode, r.stderr[-200:])
            return {'error': r.stderr[-300:], 'signals': []}
    except Exception as e:
        log.error('买点信号扫描异常: %s', e)
        return {'error': str(e), 'signals': []}


def get_stop_loss_triggered():
    """检查持仓个股是否触发止损"""
    from backend.core.monitor_data import get_existing_holdings
    holdings = get_existing_holdings()
    triggered = []
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com'
    }
    for h in holdings:
        code = h.get('code', '')
        sl = h.get('stop_loss', '')
        if not code or not sl:
            continue
        try:
            sl_price = float(sl.replace('元', '').strip())
        except Exception:
            continue
        # 取实时行情
        try:
            r = requests.get(
                f'https://qt.gtimg.cn/q={code}',
                headers=headers,
                timeout=5
            )
            line = r.text.strip()
            fields = line.split('"')[1].split('~') if '"' in line else []
            cur_price = float(fields[3]) if len(fields) > 3 else 0
        except Exception:
            continue
        if cur_price > 0 and cur_price <= sl_price:
            triggered.append({
                'code': code,
                'name': h.get('name', code),
                'current_price': cur_price,
                'stop_loss': sl_price,
                'loss_pct': round((cur_price - sl_price) / sl_price * 100, 2),
                'reason': h.get('buy_reason', ''),
            })
    return {'triggered': triggered, 'count': len(triggered)}


def get_top_sectors():
    """获取行业板块排行榜（含5日趋势）"""
    from scripts.monitor_data import get_top_sectors_with_5d
    return get_top_sectors_with_5d()


def get_industry_leaders():
    """行业龙头数据 — 读取本地JSON并用实时行情更新chg/price

    模块级短缓存（2分钟），避免高频重复请求。
    """
    global _leaders_cache_data, _leaders_cache_time
    now_ts = time.time()
    if _leaders_cache_data and (now_ts - _leaders_cache_time) < 120:
        return _leaders_cache_data

    from scripts.monitor_data import _batch_tencent_quotes, _norm_code

    try:
        with open(INDUSTRY_LEADERS_PATH, 'r') as f:
            leaders = json.load(f)
    except Exception:
        return {'count': 0, 'by_industry': {}, 'error': '数据文件未找到'}

    # 收集所有股票代码（去重）
    code_set = set()
    for ind, stocks in leaders.get('by_industry', {}).items():
        for s in stocks:
            qcode = _norm_code(s['code'])
            code_set.add(qcode)
    codes_list = sorted(code_set)

    # 批量获取实时行情
    quotes = _batch_tencent_quotes(codes_list)

    # 用实时数据更新每个股票的chg和price
    for ind, stocks in leaders.get('by_industry', {}).items():
        for s in stocks:
            qcode = _norm_code(s['code'])
            q = quotes.get(qcode)
            if q and q['price'] > 0:
                chg = q['change_pct']
                s['chg'] = f"{'+' if chg >= 0 else ''}{chg:.2f}%"
                s['price'] = str(q['price'])

    _leaders_cache_data = leaders
    _leaders_cache_time = now_ts
    return leaders


def get_market_leaders():
    """市场龙头动态扫描"""
    from scripts.monitor_data import get_market_leaders
    return get_market_leaders()

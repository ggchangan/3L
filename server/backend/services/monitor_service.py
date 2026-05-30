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

from backend.config import CACHE_DIR, INDUSTRY_LEADERS_PATH, WWW_DIR, atomic_json_dump
from backend.services.logger import get_logger

log = get_logger(__name__)

# ── 行业龙头模块级缓存 ──────────────────────────────────
_leaders_cache_data = None
_leaders_cache_time = 0


def get_volume_comparison():
    """量价对比 — 今日/昨日/5日均量"""
    from backend.core.monitor_data import get_volume_comparison
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
    # 扫描脚本路径（兼容原生开发 / Docker 布局）
    scan_file_candidates = [
        os.path.join(WWW_DIR, 'server', 'scripts', 'scan_buy_signals.py'),  # 原生开发
        os.path.join(WWW_DIR, 'scripts', 'scan_buy_signals.py'),            # Docker COPY
    ]
    scan_file = WWW_DIR
    for c in scan_file_candidates:
        if os.path.isfile(c):
            scan_file = c
            break
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
        sl = h.get('stop_loss_price') or h.get('stop_loss', '')
        if not code or not sl:
            continue
        try:
            sl_price = float(sl.replace('元', '').strip())
        except Exception:
            continue
        # 取实时行情（加交易所前缀）
        qcode = f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}"
        try:
            r = requests.get(
                f'https://qt.gtimg.cn/q={qcode}',
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
    from backend.core.monitor_data import get_top_sectors_with_5d
    return get_top_sectors_with_5d()


def get_industry_leaders():
    """行业龙头数据 — 读取本地JSON并用实时行情更新chg/price

    模块级短缓存（2分钟），避免高频重复请求。
    """
    global _leaders_cache_data, _leaders_cache_time
    now_ts = time.time()
    if _leaders_cache_data and (now_ts - _leaders_cache_time) < 120:
        return _leaders_cache_data

    from backend.core.monitor_data import _batch_tencent_quotes, _norm_code

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


def get_leader_dashboard():
    '''
    龙头观测新面板 — 两区数据
    上区：关注的行业（持仓sector+涨幅前3+手动）
    下区：龙头异动（领涨领跌+龙头切换）
    '''
    from backend.config import (
        WATCHED_INDUSTRIES_PATH, INDUSTRY_LEADERS_PATH,
        CACHE_DIR, HOLDINGS_PATH
    )
    from backend.core.monitor_data import (
        _batch_tencent_quotes, _norm_code,
        get_top_sectors_with_5d
    )
    import os

    now_ts = time.time()

    # 1. 读取行业龙头数据
    try:
        with open(INDUSTRY_LEADERS_PATH, 'r') as f:
            leaders = json.load(f)
    except Exception:
        return {'watched': [], 'anomalies': {}, 'error': '行业龙头数据未找到'}

    by_industry = leaders.get('by_industry', {})

    # 2. 构建代码→行业反向映射
    code_to_industry = {}  # bare_code → industry_name
    for ind, stocks in by_industry.items():
        for s in stocks:
            bare = s['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
            code_to_industry[bare] = ind

    # 3. 批量获取实时行情
    qcodes = set()
    for ind, stocks in by_industry.items():
        for s in stocks:
            qcodes.add(_norm_code(s['code']))
    quotes = _batch_tencent_quotes(sorted(qcodes))

    # 把行情数据合并到龙头数据结构中
    leader_real = {}  # bare_code → {chg, price, volume, turnover_rate, name}
    for ind, stocks in by_industry.items():
        for s in stocks:
            bare = s['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
            qc = _norm_code(s['code'])
            q = quotes.get(qc)
            if q and q['price'] > 0:
                leader_real[bare] = {
                    'name': q['name'],
                    'chg': q['change_pct'],
                    'price': q['price'],
                    'volume': q.get('volume', 0),
                    'turnover_rate': q.get('turnover_rate', 0),
                    'mcap': s.get('mcap', 0),
                }
            else:
                leader_real[bare] = {
                    'name': s.get('name', ''),
                    'chg': 0,
                    'price': 0,
                    'volume': 0,
                    'turnover_rate': 0,
                    'mcap': s.get('mcap', 0),
                }

    # 4. 获取关注行业来源

    # 持仓sector → industry_leaders行业名 映射表（处理命名不一致）
    SECTOR_TO_INDUSTRY_MAP = {
        '元件': '被动元件',
        '电池': '锂电池',
        '建筑材料': '其他建材',
        '自动化设备': '工控设备',
        '电网设备': '输变电设备',
        '半导体': '半导体设备',
        '消费电子': '消费电子',
        '计算机': '其他计算机设备',
        '医药': '化学制剂',
        '通信': '通信网络设备及器件',
        '有色': '有色金属',
        '钢铁': '钢铁',
        '军工': '军工',
        '房地产': '房地产',
    }

    # 4a. 持仓行业
    watched_from_holdings = set()
    try:
        with open(HOLDINGS_PATH, 'r') as f:
            hd = json.load(f)
        for h in hd.get('holdings', []):
            sec = h.get('sector', '').strip()
            if not sec:
                continue
            # 先查映射表
            mapped = SECTOR_TO_INDUSTRY_MAP.get(sec)
            if mapped and mapped in by_industry:
                watched_from_holdings.add(mapped)
                continue
            # 再精确匹配
            if sec in by_industry:
                watched_from_holdings.add(sec)
                continue
            # 最后模糊匹配
            matched = False
            for ind in by_industry:
                if sec in ind or ind in sec or sec == ind:
                    watched_from_holdings.add(ind)
                    matched = True
                    break
            if not matched:
                log.info('持仓行业"%s"未匹配到industry_leaders中的行业', sec)
    except Exception:
        pass

    # 4b. 今日涨幅前3行业
    watched_from_top3 = set()
    try:
        sector_data = get_top_sectors_with_5d()
        top5 = sector_data.get('today_top5', [])
        for s in top5[:3]:
            name = s.get('name', '')
            if name and name in by_industry:
                watched_from_top3.add(name)
    except Exception:
        pass

    # 4c. 手动关注的行业
    watched_from_manual = set()
    try:
        if os.path.isfile(WATCHED_INDUSTRIES_PATH):
            with open(WATCHED_INDUSTRIES_PATH, 'r') as f:
                mw = json.load(f)
            for w in mw.get('industries', []):
                if isinstance(w, str):
                    watched_from_manual.add(w)
    except Exception:
        pass

    # 合并去重
    watched_industries = watched_from_holdings | watched_from_top3 | watched_from_manual

    # 5. 构建关注行业数据（带标记）
    watched_items = []
    for ind in watched_industries:
        if ind not in by_industry:
            continue
        stocks_in_ind = by_industry[ind]
        if not stocks_in_ind:
            continue

        # leader = 第一只（市值最大）
        leader = stocks_in_ind[0]
        leader_bare = leader['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
        lr = leader_real.get(leader_bare, {})
        chg = lr.get('chg', 0)

        # 计算标记
        marks = []
        if chg > 3:
            marks.append('🚀突破')
        if chg < -3:
            marks.append('⚠️领跌')
        tr = lr.get('turnover_rate', 0)
        if tr > 8:
            marks.append('📊放量')

        # 龙头切换检测：比较#1 vs #2/#3
        switching_info = None
        if len(stocks_in_ind) >= 2:
            runner_up = stocks_in_ind[1]
            ru_bare = runner_up['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
            ru_lr = leader_real.get(ru_bare, {})
            ru_chg = ru_lr.get('chg', 0)
            diff = ru_chg - chg
            if diff > 3:
                marks.append('🔄挑战')
                switching_info = {
                    'runner_up_name': runner_up.get('name', ''),
                    'runner_up_chg': round(ru_chg, 2),
                    'leader_chg': round(chg, 2),
                    'diff': round(diff, 2),
                }

        # 板块背离检测
        divergence = None
        try:
            # 从最近缓存的板块数据找该行业的板块指数涨跌幅
            # 先简单实现：与 #2 比较（如果#2大幅偏离#1方向）
            if not switching_info and len(stocks_in_ind) >= 2:
                runner_up = stocks_in_ind[1]
                ru_bare = runner_up['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
                ru_lr = leader_real.get(ru_bare, {})
                ru_chg = ru_lr.get('chg', 0)
                if abs(chg - ru_chg) > 3:
                    marks.append('⚡背离')
                    divergence = {
                        'leader_chg': round(chg, 2),
                        'sector_avg_chg': round((chg + ru_chg) / 2, 2),
                    }
        except Exception:
            pass

        watched_items.append({
            'industry': ind,
            'leader_name': leader.get('name', ''),
            'leader_code': leader.get('code', ''),
            'chg': round(chg, 2),
            'price': lr.get('price', 0),
            'mcap': lr.get('mcap', 0),
            'marks': marks,
            'switching': switching_info,
            'divergence': divergence,
            'source_tags': [],
        })

    # 标记来源
    for item in watched_items:
        ind = item['industry']
        tags = []
        if ind in watched_from_holdings:
            tags.append('持仓')
        if ind in watched_from_top3:
            tags.append('热榜')
        if ind in watched_from_manual:
            tags.append('关注')
        item['source_tags'] = tags

    # 按持仓 > 涨幅 > 手动排序
    def _sort_key(item):
        ind = item['industry']
        if ind in watched_from_holdings:
            return (0, -item['chg'])
        if ind in watched_from_top3:
            return (1, -item['chg'])
        return (2, -item['chg'])
    watched_items.sort(key=_sort_key)

    # 6. 构建异动数据

    # 6a. 领涨领跌 — 所有龙头按涨跌幅排序
    all_leaders_with_chg = []
    for ind, stocks in by_industry.items():
        if not stocks:
            continue
        leader = stocks[0]
        bare = leader['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
        lr = leader_real.get(bare, {})
        chg = lr.get('chg', 0)
        all_leaders_with_chg.append({
            'industry': ind,
            'name': leader.get('name', ''),
            'code': leader.get('code', ''),
            'chg': round(chg, 2),
            'price': lr.get('price', 0),
            'turnover_rate': lr.get('turnover_rate', 0),
        })

    sorted_asc = sorted(all_leaders_with_chg, key=lambda x: x['chg'])
    sorted_desc = sorted(all_leaders_with_chg, key=lambda x: x['chg'], reverse=True)

    anomalies = {}

    # 领涨TOP5
    surge = [x for x in sorted_desc if x['chg'] > 3][:5]
    anomalies['surge'] = surge

    # 领跌TOP5
    plunge = [x for x in sorted_asc if x['chg'] < -3][:5]
    anomalies['plunge'] = plunge

    # 6b. 龙头切换检测 — 所有行业中#2/#3超越#1
    switch_events = []
    for ind, stocks in by_industry.items():
        if len(stocks) < 2:
            continue
        leader = stocks[0]
        l_bare = leader['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
        l_chg = leader_real.get(l_bare, {}).get('chg', 0)

        for runner in stocks[1:]:
            r_bare = runner['code'].replace('SH', '').replace('SZ', '').replace('sh', '').replace('sz', '')
            r_chg = leader_real.get(r_bare, {}).get('chg', 0)
            diff = r_chg - l_chg
            if diff > 3:
                direction = '逆势涨' if l_chg < 0 else '跟涨更强'
                switch_events.append({
                    'industry': ind,
                    'leader_name': leader.get('name', ''),
                    'leader_chg': round(l_chg, 2),
                    'challenger_name': runner.get('name', ''),
                    'challenger_chg': round(r_chg, 2),
                    'diff': round(diff, 2),
                    'direction': direction,
                })
                break  # 只取第一个超越者

    switch_events.sort(key=lambda x: x['diff'], reverse=True)
    anomalies['switching'] = switch_events[:5]

    return {
        'watched': watched_items,
        'anomalies': anomalies,
    }


def add_watched_industry(industry_name):
    '''手动添加关注行业'''
    from backend.config import WATCHED_INDUSTRIES_PATH
    import os
    industries = []
    if os.path.isfile(WATCHED_INDUSTRIES_PATH):
        try:
            with open(WATCHED_INDUSTRIES_PATH, 'r') as f:
                d = json.load(f)
            industries = d.get('industries', [])
        except:
            industries = []
    if industry_name not in industries:
        industries.append(industry_name)
    with open(WATCHED_INDUSTRIES_PATH, 'w') as f:
        json.dump({'industries': industries}, f, ensure_ascii=False)
    return True


def remove_watched_industry(industry_name):
    '''移除手动关注行业'''
    from backend.config import WATCHED_INDUSTRIES_PATH
    import os
    if not os.path.isfile(WATCHED_INDUSTRIES_PATH):
        return False
    try:
        with open(WATCHED_INDUSTRIES_PATH, 'r') as f:
            d = json.load(f)
        industries = d.get('industries', [])
        if industry_name in industries:
            industries.remove(industry_name)
        with open(WATCHED_INDUSTRIES_PATH, 'w') as f:
            json.dump({'industries': industries}, f, ensure_ascii=False)
        return True
    except:
        return False


def get_market_leaders():
    """市场龙头动态扫描"""
    from backend.core.monitor_data import get_market_leaders
    return get_market_leaders()

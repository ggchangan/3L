"""
review_compute_service.py — 复盘计算层
大盘周期判定、动量主线计算、量价择时分析、交易计划生成
所有函数接收数据为参数，不直接依赖文件 I/O（可测试）
"""
import json, os, sys, math, threading
from contextlib import contextmanager
from datetime import datetime

from backend.core import config
from backend.core.config import DATA_DIR, WWW_DIR, MAINLINES_CACHE_PATH

ALL_STOCKS_PATH = os.path.join(DATA_DIR, 'all_stocks_60d.json')

MAINLINE_FULL_CACHE = os.path.join(DATA_DIR, '.cache', 'mainline_full.json')
MAINLINE_HISTORY_PATH = os.path.join(DATA_DIR, 'mainline_history.json')
MAINLINE_CALIBRATION_PATH = os.path.join(DATA_DIR, 'computed', 'mainline_calibration.json')
_MAINLINE_STATE_LOCK = threading.RLock()


@contextmanager
def _mainline_state_lock():
    """跨线程/进程串行化主线历史与校准记录的完整读改写事务。"""
    import fcntl

    lock_path = os.path.join(DATA_DIR, '.cache', 'mainline_state.lock')
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with _MAINLINE_STATE_LOCK:
        with open(lock_path, 'a+', encoding='utf-8') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def to_yyyymmdd(d):
    """统一日期格式为 YYYY-MM-DD"""
    if not d:
        return ''
    d = d.strip().replace('/', '-')
    if len(d) == 10 and d[4] == '-':
        return d
    return d


def is_trading_day(date_str):
    """判断给定日期是否为A股交易日（委托 data_models.is_trading_day）"""
    from backend.models.data_models import is_trading_day as _is_trading_day
    return _is_trading_day(date_str)


def _append_estimated_sector_kline(klines, snapshot, target_date, change_pct):
    """把目标日收盘快照追加为临时 K 线，供当日阶段与量价判断使用。"""
    if not klines or not snapshot:
        return klines

    def _number(value, default=None):
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    previous_close = _number(klines[-1].get('close'))
    if previous_close is None or previous_close <= 0:
        return klines

    close = _number(snapshot.get('close'))
    if close is None or close <= 0:
        close = previous_close * (1 + float(change_pct) / 100)

    open_price = _number(snapshot.get('open'), close)
    if open_price is None or open_price <= 0:
        open_price = close
    high = _number(snapshot.get('high'), max(open_price, close))
    low = _number(snapshot.get('low'), min(open_price, close))
    high = max(high or close, open_price, close)
    low = min(low or close, open_price, close)

    volume = _number(snapshot.get('volume'))
    if volume is None or volume <= 0:
        recent_volumes = [
            _number(row.get('volume'))
            for row in klines[-20:]
        ]
        recent_volumes = [value for value in recent_volumes if value and value > 0]
        volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0

    return [*klines, {
        'date': target_date,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }]


# ═══════════════════════════════════════════════════════════════
# 数据获取（外部 API / akshare）
# ═══════════════════════════════════════════════════════════════

def fetch_market_quote():
    """获取中证全指实时行情（经统一实时行情路由）。"""
    from backend.data_access.realtime_quotes import get_realtime_quote

    quote = get_realtime_quote('sh000985')
    if not quote:
        return None
    return {
        'price': quote['price'],
        'change': round(quote['change_pct'], 2),
        'name': quote.get('name') or '中证全指',
        'source': quote.get('source'),
        'realtime': True,
    }


def fetch_index_klines(days=60):
    """从 Tushare/MySQL 确认数据获取中证全指K线。"""
    from backend.data_access.data_layer import get_index_klines

    records = get_index_klines('000985')[:days]
    result = []
    for record in records:
        item = dict(record)
        date = str(item.get('date', ''))
        if len(date) == 8 and date.isdigit():
            item['date'] = f'{date[:4]}-{date[4:6]}-{date[6:]}'
        result.append(item)
    return result


def get_industry_rankings():
    """获取同花顺行业板块排行（当日实时）"""
    import akshare as ak
    try:
        df = ak.stock_board_industry_summary_ths()
        df = df.sort_values('涨跌幅', ascending=False)
        result = []
        for _, row in df.head(15).iterrows():
            result.append({
                'name': row['板块'],
                'change': row['涨跌幅'],
                'net_inflow': row['净流入'],
                'up_count': row['上涨家数'],
                'down_count': row['下跌家数'],
                'leader': row['领涨股'],
                'leader_change': row['领涨股-涨跌幅'],
            })
        return result
    except Exception as e:
        print(f"[WARN] 获取行业排行失败: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# ① 大盘周期判定（V5）
# ═══════════════════════════════════════════════════════════════

def judge_peak_valley(klines):
    """
    三维度大盘波峰波谷判定
    基于乖离率趋势转折 + 乖离率位置 + 量价信号
    返回 5档：偏波峰/波中偏上/波中/波中偏下/偏波谷
    """
    if len(klines) < 70:
        return _fallback_cycle(klines)

    import pandas as pd
    import numpy as np

    df = pd.DataFrame(klines)
    for ma in [5, 10, 20, 60]:
        df[f'MA{ma}'] = df['close'].rolling(ma).mean()
        df[f'bias_{ma}'] = (df['close'] - df[f'MA{ma}']) / df[f'MA{ma}'] * 100
    df['bias20_chg_3d'] = df['bias_20'].diff(3)
    df['bias20_chg_5d'] = df['bias_20'].diff(5)
    df['vol_ma20'] = df['volume'].rolling(20).mean()

    i = len(df) - 1
    r = df.iloc[i]
    if pd.isna(r['bias_20']) or pd.isna(r['bias20_chg_5d']):
        return _fallback_cycle(klines)

    bias20 = r['bias_20']
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    bias_early = r['bias_20'] - df.iloc[i - 10]['bias_20'] if i >= 10 else 0

    # 量价信号
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    ls_pct = (min(r['open'], r['close']) - r['low']) / r['open'] * 100
    us_pct = (r['high'] - max(r['open'], r['close'])) / r['open'] * 100
    gain = (r['close'] - r['open']) / r['open'] * 100

    last5 = df.iloc[max(0, i - 4):i + 1]

    # 波峰信号
    peak_sig = 0
    if vol_ratio > 1.3 and body_pct < 0.8:
        peak_sig += 1
    if us_pct > 1.5 and gain < 0:
        peak_sig += 1
    if len(last5) >= 5:
        gains = [(last5.iloc[j]['close'] - last5.iloc[j - 1]['close']) / last5.iloc[j - 1]['close'] * 100
                 for j in range(1, len(last5))]
        avg_g = np.mean([g for g in gains if not np.isnan(g)] or [0])
        tg = (r['close'] - last5.iloc[-2]['close']) / last5.iloc[-2]['close'] * 100
        if avg_g > 0.5 and tg < avg_g * 0.3:
            peak_sig += 1
        yang = sum(1 for j in range(1, len(last5)) if last5.iloc[j]['close'] > last5.iloc[j - 1]['close'])
        if yang >= 3 and vol_ratio > 1.5 and body_pct < 0.6:
            peak_sig += 1

    # 波谷信号
    valley_sig = 0
    if gain < -1.5 and vol_ratio > 1.3 and ls_pct > body_pct * 1.5 and ls_pct > 0.5:
        valley_sig += 1
    if ls_pct > 1.0 and body_pct < ls_pct:
        valley_sig += 1
    if len(last5) >= 4:
        down = sum(1 for j in range(1, len(last5)) if last5.iloc[j]['close'] < last5.iloc[j - 1]['close'])
        if down >= 4 and vol_ratio < 0.8:
            valley_sig += 1
        p4 = all(last5.iloc[j]['close'] < last5.iloc[j - 1]['close'] for j in range(1, 4))
        if p4 and body_pct < 0.8 and gain > 0:
            valley_sig += 1

    # 趋势转折
    peak_turn = bias_early > 0.5 and bias_chg_5d < 0.3
    valley_turn = bias_early < -0.8 and bias_chg_5d > -0.3

    pk_score = 0
    pk_conds = [peak_turn, bias20 > 1.5, peak_sig >= 1, bias_chg_3d < 0]
    for c in pk_conds:
        if c:
            pk_score += 1
    if bias20 > 8:
        pk_score = max(pk_score, 3)

    vl_score = 0
    vl_conds = [valley_turn, bias20 < -1.5, valley_sig >= 1, bias_chg_3d > 0]
    for c in vl_conds:
        if c:
            vl_score += 1
    if bias20 < -8:
        vl_score = max(vl_score, 3)

    # 5档判定
    if pk_score >= 4:
        position = '偏波峰'
        pct = '五成'
        strategy = '控制仓位，收紧止盈'
        bps = 5
    elif pk_score >= 3:
        position = '波中偏上'
        pct = '六至七成'
        strategy = '正常交易，注意减仓信号'
        bps = 5
    elif vl_score >= 4:
        position = '偏波谷'
        pct = '五至八成'
        strategy = '积极寻找买点，止损换股补回'
        bps = 10
    elif vl_score >= 3:
        position = '波中偏下'
        pct = '五至七成'
        strategy = '谨慎选股，收紧止损'
        bps = 5
    else:
        position = '波中'
        pct = '七至八成'
        strategy = '正常交易，积极选股'
        bps = 5

    score = pk_score - vl_score

    chg_10d = (klines[-1]['close'] - klines[-11]['close']) / klines[-11]['close'] * 100 if len(klines) >= 11 else 0
    ma20_val = float(df['MA20'].iloc[-1]) if not pd.isna(df['MA20'].iloc[-1]) else 0
    ma60_val = float(df['MA60'].iloc[-1]) if not pd.isna(df['MA60'].iloc[-1]) else 0

    return {
        'score': round(score, 1),
        'position': position,
        'pk_score': pk_score,
        'vl_score': vl_score,
        'bias20': round(bias20, 2),
        'bias20_chg_3d': round(bias_chg_3d, 2),
        'ma20': round(ma20_val, 2),
        'ma60': round(ma60_val, 2),
        'vol_ratio': round(vol_ratio, 2),
        'chg_10d': round(chg_10d, 2),
        'chg_10d_raw': round(chg_10d, 2),
        'strategy': strategy,
        'position_pct': pct,
        'build_per_stock_pct': bps,
        'peak_sig': peak_sig,
        'valley_sig': valley_sig,
        'ma_score': 0, 'vol_score': 0, 'trend_score': 0, 'amp_score': 0,
    }


def _fallback_cycle(klines):
    """数据不足时的兜底方案"""
    if len(klines) < 10:
        return {'score': 0, 'position': '波中', 'strategy': '正常交易',
                'position_pct': '七至八成', 'build_per_stock_pct': 5}
    chg = (klines[-1]['close'] - klines[-6]['close']) / klines[-6]['close'] * 100
    if chg > 5:
        return {'score': 0.5, 'position': '波中偏上', 'strategy': '正常交易，注意减仓信号',
                'position_pct': '六至七成', 'build_per_stock_pct': 5}
    elif chg < -5:
        return {'score': -0.5, 'position': '波中偏下', 'strategy': '谨慎选股，收紧止损',
                'position_pct': '五至七成', 'build_per_stock_pct': 5}
    else:
        return {'score': 0, 'position': '波中', 'strategy': '正常交易',
                'position_pct': '七至八成', 'build_per_stock_pct': 5}


# ═══════════════════════════════════════════════════════════════
# ② 机会分类
# ═══════════════════════════════════════════════════════════════

def classify_opportunity(is_mainline, is_secondary, stage, vl_score):
    """根据主线状态和5阶段判定机会类型"""
    if is_mainline:
        if stage == '波谷':
            return '主线回调'
        elif stage == '波峰':
            return '见顶风险'
        elif stage in ('上涨', '波中'):
            return '趋势延续'
        elif stage == '下跌':
            return '回调中'
        return '主线观察'
    if is_secondary:
        if stage == '波谷':
            return '次线机会'
        elif stage == '波峰':
            return '见顶风险'
        elif stage in ('上涨', '波中'):
            return '趋势延续'
        elif stage == '下跌':
            return '回调中'
        return '次级观察'
    # 非榜板块：只有波谷+高评分才算波谷观察
    if stage == '波谷' and (vl_score or 0) >= 3:
        return '波谷观察'
    return '--'


# ═══════════════════════════════════════════════════════════════
# ② 动量主线
# ═══════════════════════════════════════════════════════════════

def _record_mainline_calibration(date_str, ranked, is_estimated, coverage=0.0):
    """保存收盘预估 Top10，正式板块日线到齐后记录排名差异。"""
    try:
        with _mainline_state_lock():
            records = {}
            if os.path.isfile(MAINLINE_CALIBRATION_PATH):
                with open(MAINLINE_CALIBRATION_PATH, encoding='utf-8') as f:
                    records = json.load(f)
            top10 = [item['name'] for item in ranked[:10]]
            if is_estimated:
                previous = records.get(date_str, {})
                # 正式校准一旦完成，迟到的收盘任务不能把状态降回 pending。
                if previous.get('status') == 'completed':
                    return previous
                record = {
                    'status': 'pending',
                    'date': date_str,
                    'estimated_top10': top10,
                    'estimate_coverage': round(float(coverage or 0), 4),
                    'estimated_at': datetime.now().isoformat(timespec='seconds'),
                }
                records[date_str] = record
            else:
                previous = records.get(date_str, {})
                estimated_top10 = previous.get('estimated_top10', [])
                if not estimated_top10:
                    return None
                estimated_rank = {name: i + 1 for i, name in enumerate(estimated_top10)}
                confirmed_rank = {name: i + 1 for i, name in enumerate(top10)}
                common = [name for name in top10 if name in estimated_rank]
                record = {
                    **previous,
                    'status': 'completed',
                    'confirmed_top10': top10,
                    'entered': [name for name in top10 if name not in estimated_rank],
                    'exited': [name for name in estimated_top10 if name not in confirmed_rank],
                    'rank_changes': [
                        {
                            'name': name,
                            'estimated_rank': estimated_rank[name],
                            'confirmed_rank': confirmed_rank[name],
                            'change': estimated_rank[name] - confirmed_rank[name],
                        }
                        for name in common
                    ],
                    'top5_overlap': len(set(estimated_top10[:5]) & set(top10[:5])),
                    'top10_overlap': len(common),
                    'calibrated_at': datetime.now().isoformat(timespec='seconds'),
                }
                records[date_str] = record
            config.atomic_json_dump(records, MAINLINE_CALIBRATION_PATH, indent=2)
            return record
    except Exception as exc:
        print(f'[3L复盘] ⚠️ 主线校准记录失败: {exc}')
        return None


def get_mainline_data(date_str):
    """三梯队：前5=主线，6~10=次级主线，其余=非主线（当天文件缓存）"""
    # 检查当天缓存（数据源已经是 DB，不再检查文件 mtime）
    if os.path.isfile(MAINLINE_FULL_CACHE):
        try:
            with open(MAINLINE_FULL_CACHE) as _f:
                cached = json.load(_f)
            if cached.get('date') == date_str:
                print(f"[3L复盘] 主线数据读缓存 {date_str}")
                return cached
        except Exception:
            pass

    target_date = str(date_str).replace('-', '')
    from backend.data_access.data_layer import (
        get_sector_close_snapshot, get_sector_daily, get_sector_daily_snapshot,
        get_ths_daily_update_confirmation,
    )
    sector_state = get_sector_daily()
    sector_date = str(
        sector_state.get('industry_last_updated')
        or sector_state.get('last_updated', '')
    ).replace('-', '')
    effective_sector_date = min(sector_date, target_date) if sector_date else target_date
    confirmation = get_ths_daily_update_confirmation()
    active_industries = set(confirmation.get('industry_names', []))

    close_snapshot = get_sector_close_snapshot()
    snapshot_date = str(close_snapshot.get('date', '')).replace('-', '')
    industry_coverage = close_snapshot.get('coverage', {}).get('industry', {})
    estimate_active = (
        bool(sector_date)
        and sector_date < target_date
        and snapshot_date == target_date
        and industry_coverage.get('ready') is True
    )
    ranking_status = (
        'estimated' if estimate_active
        else 'confirmed' if sector_date and effective_sector_date >= target_date
        else 'stale'
    )
    daily_snapshot = get_sector_daily_snapshot()
    confirmed_snapshots = daily_snapshot.industries if hasattr(daily_snapshot, 'industries') else {}
    estimate_snapshots = close_snapshot.get('industries', {}) if estimate_active else {}

    # 从 DB（ths_daily）获取行业K线数据
    from backend.data_access.data_layer import get_ths_industry_klines
    industries_data = get_ths_industry_klines(ths_type='I')
    if not industries_data:
        return {'lines': [], 'secondary': [], 'industries': get_industry_rankings(), 'all_ranked': []}

    # 导入概念波谷判定（复用至行业板块）
    from backend.services.concept_wave_service import judge_concept_wave as _judge_wave

    scores = []
    for name, klines in industries_data.items():
        try:
            if active_industries and name not in active_industries:
                continue
            klines = [
                row for row in klines
                if str(row.get('date', '')).replace('-', '') <= effective_sector_date
            ]
            if not klines or str(klines[-1].get('date', '')).replace('-', '') != effective_sector_date:
                continue
            estimate_snap = estimate_snapshots.get(name)
            # 当日预估榜必须使用同一时点的数据；未命中收盘快照的行业不参与排名。
            if estimate_active and estimate_snap is None:
                continue
            confirmed_snap = confirmed_snapshots.get(name) if not estimate_active else None
            if confirmed_snap is not None and str(confirmed_snap.date).replace('-', '') != effective_sector_date:
                confirmed_snap = None
            if estimate_snap is not None:
                chg_1d = estimate_snap.get('change_pct')
            else:
                chg_1d = confirmed_snap.change_pct if confirmed_snap is not None else None
            if chg_1d is None:
                # 从K线计算（兜底）
                if len(klines) >= 2:
                    chg_1d = (klines[-1]['close'] / klines[-2]['close'] - 1) * 100
                else:
                    chg_1d = 0
            else:
                chg_1d = float(chg_1d)
            estimate_applied = estimate_snap is not None and len(klines) >= 19
            if estimate_applied:
                analysis_klines = _append_estimated_sector_kline(
                    klines, estimate_snap, target_date, chg_1d,
                )
                chg_20d = (
                    float(analysis_klines[-1]['close'])
                    / float(analysis_klines[-20]['close']) - 1
                ) * 100
            elif len(klines) >= 20:
                analysis_klines = klines
                chg_20d = (klines[-1]['close'] / klines[-20]['close'] - 1) * 100
            else:
                analysis_klines = klines
                chg_20d = 0  # 历史不足，不参与20日排名
            # 预估榜也必须使用目标日临时 K 线判断阶段，不能沿用上一日结论。
            wave = _judge_wave(analysis_klines)
            stage = wave.get('stage', '--')
            vl_score = wave.get('vl_score', 0)
            volume_ratio = wave.get('volume_ratio', 0)
            scores.append({
                'name': name,
                'chg_20d': round(chg_20d, 2),
                'chg_1d': round(chg_1d, 2),
                'stage': stage,
                'vl_score': vl_score,
                'volume_ratio': volume_ratio,
                'estimate_applied': estimate_applied,
            })
        except Exception:
            continue

    scores.sort(key=lambda x: x['chg_20d'], reverse=True)
    daily_rankings = get_industry_rankings()

    # 为每条数据标注主线状态 + 机会类型
    for i, item in enumerate(scores):
        item['is_mainline'] = i < 5
        item['is_secondary'] = 5 <= i < 10
        item['opportunity'] = classify_opportunity(
            item['is_mainline'], item['is_secondary'],
            item.get('stage', '--'), item.get('vl_score', 0),
        )

    main_lines = scores[:5]
    secondary_lines = scores[5:10]

    result = {
        'date': date_str,
        'ranking_status': ranking_status,
        'ranking_date': target_date if estimate_active else effective_sector_date,
        'base_date': effective_sector_date,
        'estimate_coverage': round(float(industry_coverage.get('ratio', 0)), 4) if estimate_active else None,
        'estimate_coverage_detail': {
            'covered': industry_coverage.get('covered'),
            'expected': industry_coverage.get('expected'),
            'ready': industry_coverage.get('ready'),
        } if estimate_active else {},
        'lines': main_lines,
        'secondary': secondary_lines,
        'industries': daily_rankings,
        'all_ranked': scores,
        'persistence': track_mainline_persistence(date_str, main_lines, prefix=''),
    }
    result['calibration'] = (
        _record_mainline_calibration(
            date_str, scores, estimate_active, industry_coverage.get('ratio', 0)
        )
        if ranking_status in ('estimated', 'confirmed') else None
    )

    # 写入缓存
    os.makedirs(os.path.dirname(MAINLINE_FULL_CACHE), exist_ok=True)
    with open(MAINLINE_FULL_CACHE, 'w') as _f:
        json.dump(result, _f)
    print(f"[3L复盘] 主线数据已缓存 {date_str}")

    # 只有正式板块日线才进入持续性历史；预估/过期排名由缓存和校准记录承载。
    if ranking_status == 'confirmed':
        try:
            with _mainline_state_lock():
                top10_names = [l['name'] for l in (main_lines + secondary_lines)]
                history = {}
                if os.path.isfile(MAINLINE_HISTORY_PATH):
                    with open(MAINLINE_HISTORY_PATH) as _fh:
                        history = json.load(_fh)
                # 只保留当天及之前的历史（防止future覆盖）
                history = {k: v for k, v in history.items() if k <= date_str}
                history[date_str] = {'top10': top10_names}
                config.atomic_json_dump(history, MAINLINE_HISTORY_PATH, indent=2)
        except Exception as e:
            print(f"[3L复盘] ⚠️ 历史记录保存失败: {e}")

    return result


def get_concept_mainline_data(date_str):
    """概念主线排名 — 与 get_mainline_data 相同逻辑，但用概念板块数据"""
    from backend.data_access.data_layer import (
        get_sector_close_snapshot, get_sector_daily, get_ths_industry_klines,
        get_tracked_concept_names,
    )
    from backend.services.concept_wave_service import judge_concept_wave as _judge_wave
    target_date = str(date_str).replace('-', '')
    concepts_data = get_ths_industry_klines(ths_type='N')
    tracked_concepts = get_tracked_concept_names(
        min_related_stocks=6,
        reference_date=target_date,
    )
    sector_state = get_sector_daily()
    sector_date = str(
        sector_state.get('concept_data_date')
        or sector_state.get('concept_last_updated')
        or sector_state.get('last_updated', '')
    ).replace('-', '')
    concept_confirmed_date = str(
        sector_state.get('concept_last_updated')
        or sector_state.get('last_updated', '')
    ).replace('-', '')
    concept_official_status = sector_state.get('concept_status', 'confirmed')
    official_coverage = sector_state.get('concept_coverage')
    official_coverage_detail = sector_state.get('concept_coverage_detail') or {}
    if not concepts_data or not tracked_concepts or not sector_date:
        return {'lines': [], 'secondary': [], 'all_ranked': [], 'persistence': []}

    # 从 THS 日快照获取已确认涨跌幅（同 get_mainline_data 一致）
    from backend.data_access.data_layer import get_sector_daily_snapshot
    daily_snapshot = get_sector_daily_snapshot()
    confirmed_concepts = daily_snapshot.concepts if hasattr(daily_snapshot, 'concepts') else {}
    close_snapshot = get_sector_close_snapshot()
    concept_coverage = close_snapshot.get('coverage', {}).get('concept', {})
    estimate_active = (
        sector_date < target_date
        and str(close_snapshot.get('date', '')).replace('-', '') == target_date
        and concept_coverage.get('ready') is True
    )
    estimate_snapshots = close_snapshot.get('concepts', {}) if estimate_active else {}

    scores = []
    for name, klines in concepts_data.items():
        try:
            if name not in tracked_concepts:
                continue
            klines = [
                row for row in klines
                if str(row.get('date', '')).replace('-', '') <= sector_date
            ]
            if not klines or str(klines[-1].get('date', '')).replace('-', '') != sector_date:
                continue
            if len(klines) < 20:
                continue
            # chg_1d：优先 THS 日快照，次选K线计算
            estimate_snap = estimate_snapshots.get(name)
            # 与行业榜一致，预估状态下只允许收盘快照覆盖的概念参与排名。
            if estimate_active and estimate_snap is None:
                continue
            snap = confirmed_concepts.get(name) if not estimate_active else None
            if snap is not None and str(snap.date).replace('-', '') != sector_date:
                snap = None
            if estimate_snap is not None:
                chg_1d = float(estimate_snap.get('change_pct', 0))
            elif snap is not None:
                chg_1d = float(snap.change_pct)
            elif len(klines) >= 2:
                chg_1d = (klines[-1]['close'] / klines[-2]['close'] - 1) * 100
            else:
                chg_1d = 0
            estimate_applied = estimate_snap is not None and len(klines) >= 19
            if estimate_applied:
                analysis_klines = _append_estimated_sector_kline(
                    klines, estimate_snap, target_date, chg_1d,
                )
                chg_20d = (
                    float(analysis_klines[-1]['close'])
                    / float(analysis_klines[-20]['close']) - 1
                ) * 100
            else:
                analysis_klines = klines
                chg_20d = (klines[-1]['close'] / klines[-20]['close'] - 1) * 100
            # 概念榜与行业榜使用相同的目标日临时 K 线口径。
            wave = _judge_wave(analysis_klines)
            stage = wave.get('stage', '--')
            vl_score = wave.get('vl_score', 0)
            volume_ratio = wave.get('volume_ratio', 0)
            scores.append({
                'name': name,
                'chg_20d': round(chg_20d, 2),
                'chg_1d': round(chg_1d, 2),
                'stage': stage,
                'vl_score': vl_score,
                'volume_ratio': volume_ratio,
                'estimate_applied': estimate_applied,
            })
        except Exception:
            continue

    scores.sort(key=lambda x: x['chg_20d'], reverse=True)

    # 为每条数据标注主线状态 + 机会类型
    for i, item in enumerate(scores):
        item['is_mainline'] = i < 5
        item['is_secondary'] = 5 <= i < 10
        item['opportunity'] = classify_opportunity(
            item['is_mainline'], item['is_secondary'],
            item.get('stage', '--'), item.get('vl_score', 0),
        )

    main_lines = scores[:5]
    secondary_lines = scores[5:10]

    if estimate_active:
        ranking_status = 'estimated'
    elif sector_date >= target_date and concept_official_status == 'partial':
        ranking_status = 'partial'
    elif concept_confirmed_date >= target_date:
        ranking_status = 'confirmed'
    else:
        ranking_status = 'stale'

    # 写入历史（共享同一份 mainline_history.json，标记 concept_ 前缀）
    if ranking_status == 'confirmed':
        try:
            with _mainline_state_lock():
                top10_names = [l['name'] for l in (main_lines + secondary_lines)]
                history = {}
                if os.path.isfile(MAINLINE_HISTORY_PATH):
                    with open(MAINLINE_HISTORY_PATH) as _fh:
                        history = json.load(_fh)
                key = f'concept_{date_str}'
                history = {k: v for k, v in history.items() if k.split('_')[-1] <= date_str}
                history[key] = {'top10': top10_names}
                config.atomic_json_dump(history, MAINLINE_HISTORY_PATH, indent=2)
        except Exception as e:
            print(f"[3L复盘] ⚠️ 概念历史记录保存失败: {e}")

    # 持续性
    persistence = track_mainline_persistence(date_str, main_lines, prefix='concept_')

    return {
        'date': date_str,
        'ranking_status': ranking_status,
        'ranking_date': target_date if estimate_active else sector_date,
        'confirmed_date': concept_confirmed_date,
        'base_date': (
            sector_date if estimate_active
            else concept_confirmed_date or sector_date
        ),
        'estimate_coverage': (
            round(float(concept_coverage.get('ratio', 0)), 4)
            if estimate_active else None
        ),
        'estimate_coverage_detail': {
            'covered': concept_coverage.get('covered'),
            'expected': concept_coverage.get('expected'),
            'ready': concept_coverage.get('ready'),
        } if estimate_active else {},
        'coverage': (
            round(float(official_coverage or 0), 4)
            if ranking_status == 'partial' else None
        ),
        'coverage_detail': (
            official_coverage_detail if ranking_status == 'partial' else {}
        ),
        'lines': main_lines,
        'secondary': secondary_lines,
        'all_ranked': scores,
        'persistence': persistence,
        'type': 'concept',
    }


def track_mainline_persistence(date_str, current_lines, prefix=''):
    """主线持续性跟踪 — 从历史记录追溯连续在榜天数"""
    if not current_lines:
        return []

    try:
        history = {}
        if os.path.isfile(MAINLINE_HISTORY_PATH):
            with open(MAINLINE_HISTORY_PATH) as _fh:
                history = json.load(_fh)
    except Exception:
        return [{'name': l['name'], 'days': 1, 'status': '持续'} for l in current_lines]

    # 获取所有历史日期，从最近到最远
    past_dates = sorted([d for d in history.keys() if d.startswith(prefix) and d < prefix + date_str], reverse=True)
    result = []

    for line in current_lines:
        name = line['name']
        days = 1  # 当天算1天
        # 逐日往前追溯
        for d in past_dates:
            top10 = history[d].get('top10', [])
            if name in top10:
                days += 1
            else:
                break
        status = '新进' if days == 1 else '持续'
        result.append({'name': name, 'days': days, 'status': status})

    return result


# ═══════════════════════════════════════════════════════════════
# ③ 量价择时分析
# ═══════════════════════════════════════════════════════════════

def get_buy_sell_signals(holdings, buy_signals, date_str=None, all_stocks_data=None):
    """量价择时分析 — 从全量扫描结果中提取持仓股买点

    如果 all_stocks_data (dict of {方向: {code: [klines]}}) 未提供，
    则从 ALL_STOCKS_PATH 自动读取。
    """
    signals = {'holdings': [], 'signals': buy_signals}
    bs_by_code = {s.get('code', ''): s for s in buy_signals}

    # 加载全量股票 K 线数据
    if all_stocks_data is None:
        try:
            with open(ALL_STOCKS_PATH) as f:
                _data = json.load(f)
            all_stocks_data = _data.get('stocks', {})
        except Exception:
            all_stocks_data = {}

    cache = {}
    try:
        sys.path.insert(0, os.path.join(config.WWW_DIR, 'scripts'))
        from ema_utils import get_ema_arrangement, get_structure, get_stage

        _date_clean = date_str.replace('-', '') if date_str else None
        for _sec, _ss in all_stocks_data.items():
            for _code, _kls in _ss.items():
                if _kls and len(_kls) >= 2:
                    if _date_clean:
                        _end_idx = len(_kls)
                        for _i, _k in enumerate(_kls):
                            if str(_k.get('date', '')).replace('-', '') > _date_clean:
                                _end_idx = _i
                                break
                        _use_kls = _kls[:_end_idx]
                    else:
                        _use_kls = _kls
                    if len(_use_kls) < 2:
                        continue
                    last = _use_kls[-1]
                    prev = _use_kls[-2]
                    chg = round((last['close'] - prev['close']) / prev['close'] * 100, 2) if prev['close'] else 0
                    closes_60 = [k['close'] for k in _use_kls]
                    highs_60 = [k['high'] for k in _use_kls]
                    lows_60 = [k['low'] for k in _use_kls]
                    vols_60 = [k.get('volume', k.get('vol', 0)) for k in _use_kls]
                    _structure = get_structure(closes_60)
                    _stage = get_stage(closes_60, _structure, highs_60, lows_60, volumes=vols_60)
                    _vol_analysis = '--'
                    if len(vols_60) >= 13 and all(v > 0 for v in vols_60[-13:]):
                        _vl3 = sum(vols_60[-3:]) / 3
                        _vp10 = sum(vols_60[-13:-3]) / 10
                        _vr = _vl3 / _vp10 if _vp10 > 0 else 1
                        if _vr < 0.8:
                            _vol_analysis = f'缩量{_vr:.0%}'
                        elif _vr > 1.5:
                            _vol_analysis = f'放量{_vr:.0%}'
                        else:
                            _vol_analysis = f'量能正常{_vr:.0%}'
                    cache[_code] = {
                        'close': last['close'], 'change': chg, 'date': last['date'],
                        'ema': get_ema_arrangement(closes_60),
                        'structure': _structure,
                        'stage': _stage,
                        'vol_analysis': _vol_analysis,
                    }
    except Exception:
        pass

    for h in holdings:
        code = h.get('code', '')
        name = h.get('name', '?')
        bs = bs_by_code.get(code)
        close_price = bs.get('price', 0) if bs else 0
        if not bs or close_price == 0:
            close_price = cache.get(code, {}).get('close', 0)
        chg_val = bs.get('change', 0) if bs else 0
        if not bs:
            chg_val = cache.get(code, {}).get('change', 0)
        action = f"{bs.get('buy_point', '')} {bs.get('flags', '')}" if bs else '持有观察'
        signals['holdings'].append({
            'name': name, 'code': code,
            'action': action.strip(),
            'close': close_price,
            'zhongji': bs.get('flags', '') if bs else '',
            'tupo': '',
            'change': chg_val,
            'structure': cache.get(code, {}).get('structure', '--'),
            'stage': cache.get(code, {}).get('stage', '--'),
            'ema': cache.get(code, {}).get('ema', '--'),
            'vol_analysis': cache.get(code, {}).get('vol_analysis', '--'),
        })
    return signals, cache, bs_by_code


# ═══════════════════════════════════════════════════════════════
# ④ 每日交易计划
# ═══════════════════════════════════════════════════════════════

def generate_trading_plan(market_cycle, mainline_data, signals_data, existing_holdings,
                          holdings_review=None, buy_signals_review=None,
                          opportunity_map=None):
    """综合前4项生成次日交易计划"""
    from backend.core.signal_detector.market_filter import get_market_filter
    mf = get_market_filter(market_cycle)
    mf_filter = mf.get('filter', 'normal')
    opportunity_map = opportunity_map or {}

    # 大盘过滤覆盖策略
    if mf_filter == 'reduce':
        _strategy = '减仓控风险'
        _position = mf.get('max_position', '5成')
    elif mf_filter == 'rest':
        _strategy = '休息不动'
        _position = mf.get('max_position', '3成')
    else:
        _strategy = market_cycle.get('strategy', '正常交易')
        _position = market_cycle.get('position_pct', '半仓')

    plan = {
        'overall_strategy': _strategy,
        'position_level': _position,
        'market_filter': mf,
        'build_per_stock_pct': f"{market_cycle.get('build_per_stock_pct', 5)}%/只",
        'main_lines': [],
        'position_detail': '',
        'holdings_action': [],
        'buy_priority': [],
        'risk_items': [],
    }

    for line in (mainline_data.get('lines', [])[:3]):
        plan['main_lines'].append(f"{line['name']}({line['chg_20d']}%)")

    pos = market_cycle.get('position', '波中')
    plan['position_detail'] = {
        '偏波峰': '偏波峰仓位五成，建仓5%/只。大盘偏高位，控制总仓位，收紧止盈线',
        '波中偏上': '波中偏上仓位六至七成，建仓5%/只。正常交易，注意减仓信号',
        '波中': '波中仓位七至八成，建仓5%/只。正常交易，积极选股',
        '波中偏下': '波中偏下仓位五至七成，建仓5%/只。谨慎选股，收紧止损',
        '偏波谷': '偏波谷仓位五至八成，建仓10%/只。积极寻找买点，止损后换股补回',
    }.get(pos, '正常仓位管理')

    # 大盘过滤覆盖 position_detail
    if mf_filter == 'reduce':
        plan['position_detail'] = f'{mf.get("reason", "")}。{plan["position_detail"]}'
        plan['risk_items'].append(f'大盘减速阶段：{mf.get("reason", "")}')
    elif mf_filter == 'rest':
        plan['position_detail'] = f'{mf.get("reason", "")}。{plan["position_detail"]}'
        plan['risk_items'].append(f'大盘休整阶段：{mf.get("reason", "")}')

    # 大盘周期标签（注入原因链）
    market_tag = f'大盘{pos}'

    if holdings_review:
        for h in holdings_review:
            name = f"{h['name']}({h['code']})"
            sig = h.get('signal', 'hold')
            stage = h.get('stage', '')
            struct = h.get('structure', '')
            # 查询所属板块的机会类型
            sec_name = h.get('industry') or h.get('sector', '')
            sec_opp = '--'
            sec_opp_reason = ''
            if opportunity_map and sec_name:
                sec_opp = opportunity_map.get(sec_name, '--')
            if sec_opp == '--':
                if not sec_name:
                    sec_opp_reason = '暂无行业数据'
                elif sec_name not in opportunity_map:
                    sec_opp_reason = '无板块数据'
                else:
                    sec_opp_reason = '暂无信号'
            # 构建推理链：大盘→板块→个股
            chain_parts = [market_tag]
            if sec_name and sec_opp and sec_opp != '--':
                chain_parts.append(f'{sec_name}·{sec_opp}')
            elif sec_name and sec_opp_reason:
                chain_parts.append(f'{sec_name}·{sec_opp_reason}')
            elif sec_name:
                chain_parts.append(f'{sec_name}')
            chain = '→'.join(chain_parts)
            # 基础字段
            base = {
                'stock': name,
                'stop_loss': h.get('stop_loss'),
                'stop_loss_pct': h.get('stop_loss_pct'),
                'change': h.get('change'),
                'industry': sec_name,
                'sector': sec_name,
                'opportunity': sec_opp,
                'opp_reason': sec_opp_reason,
                'mainline_level': h.get('mainline_level', ''),
                'is_main': h.get('mainline_level', '') in ('主线', '次级主线'),
                'profit_model1': h.get('profit_model1', False),
                'trend_stock': h.get('trend_stock', False),
                'triggered_signals': h.get('triggered_signals', []),
                'fusion_type': h.get('fusion_type', ''),
                'fusion_reason': h.get('fusion_reason', ''),
            }

            # ── 操作建议（已由 get_stock_card 统一推导，这里直接读取）──
            at = h.get('action_type', '持有')
            sig_txt = h.get('action_signal', '')
            reason = h.get('action_reason', '')
            pri = h.get('action_priority', '中')
            plan['holdings_action'].append({
                'name': name,  # "名称(代码)" 格式
                **base, 'action_type': at, 'signal': sig_txt,
                'action': at,
                'reason': f'{chain}→{reason}', 'priority': pri,
            })

    if buy_signals_review:
        for bs in buy_signals_review:
            # 通过 sector 名称在 opportunity_map 中查找该股票所属方向的机会类型
            sec_name = bs.get('industry') or bs.get('sector', '')
            direction = bs.get('direction', '')
            bs_opp = '--'
            opp_reason = ''
            if opportunity_map and sec_name:
                bs_opp = opportunity_map.get(sec_name, '--')
            if not bs_opp or bs_opp == '--':
                if not sec_name:
                    opp_reason = '暂无行业映射'
                elif sec_name not in opportunity_map:
                    ranking_status = mainline_data.get('ranking_status', 'stale')
                    if ranking_status == 'estimated':
                        opp_reason = f'{sec_name}·当日板块快照未覆盖'
                    elif ranking_status == 'stale':
                        opp_reason = f'{sec_name}·板块排名待补齐'
                    else:
                        opp_reason = f'{sec_name}·无板块数据'
                else:
                    opp_reason = f'{sec_name}·暂无信号'
            # 操作建议（已由 get_stock_card 统一推导，这里直接读取）
            at = bs.get('action_type', '买入')
            sig_txt = bs.get('action_signal', '')
            pri = bs.get('action_priority', '高')
            sector_unavailable = not sec_name or sec_name not in opportunity_map
            # 板块已覆盖时，机会类型只影响排序和仓位判断，不改变“买入”操作。
            # 只有板块数据完全未覆盖，才将操作降级为“待确认”。
            decision_status = 'executable'
            if sector_unavailable:
                # 3L 的板块层没有闭环时只保留个股技术信号，不生成正式买入指令。
                at = '待确认'
                pri = '低'
                decision_status = 'blocked'
            plan['buy_priority'].append({
                'name': f"{bs.get('name', '')}({bs.get('code', '')})",
                'code': bs.get('code', ''),
                'action_type': at,
                'signal': sig_txt,
                'buy_point': bs.get('buy_point', '') or bs.get('flags', '') or '买点信号',
                'change': bs.get('change'),
                'mainline_level': bs.get('mainline_level', ''),
                'is_main': bs.get('mainline_level', '') in ('主线', '次级主线'),
                'profit_model1': bs.get('profit_model1', False),
                'trend_stock': bs.get('trend_stock', False),
                'structure': bs.get('structure', ''),
                'stage': bs.get('stage', ''),
                'stop_loss': bs.get('stop_loss'),
                'stop_loss_pct': bs.get('stop_loss_pct'),
                'industry': sec_name,
                'sector': sec_name,
                'direction': direction,
                'opportunity': bs_opp,
                'opp_reason': opp_reason,
                'decision_status': decision_status,
                'data_quality': 'sector_unavailable' if sector_unavailable else 'ready',
                'reason': f'{market_tag}→{sec_name}·{bs_opp}→{bs.get("structure", "--")}·{bs.get("stage", "--")}' if bs_opp and bs_opp != '--' else f'{market_tag}→{opp_reason}' if opp_reason else '',
                'priority': pri,
                'triggered_signals': bs.get('triggered_signals', []),
                'fusion_type': bs.get('fusion_type', ''),
                'fusion_reason': bs.get('fusion_reason', ''),
            })

    # 排序：个股操作 高→低
    PRIORITY_ORDER = {'高': 0, '中': 1, '低': 2}
    plan['holdings_action'].sort(key=lambda x: PRIORITY_ORDER.get(x.get('priority', '中'), 2))

    # 排序：关注买点 机会类型优先级 > 主线级 > 趋势状态
    OPP_ORDER = {
        '主线回调': 0, '次线机会': 1, '潜在主线': 2,
        '趋势延续': 3, '回调中': 4, '见顶风险': 5, '--': 6,
    }
    MAINLINE_ORDER = {'主线': 0, '次级主线': 1}
    STRUCTURE_ORDER = {'上涨趋势': 0, '区间震荡': 1, '区间中段': 1, '区间底部': 1, '区间顶部': 2, '下降趋势': 3}
    plan['buy_priority'].sort(key=lambda x: (
        OPP_ORDER.get(x.get('opportunity', '--'), 5),
        MAINLINE_ORDER.get(x.get('mainline_level', ''), 2),
        STRUCTURE_ORDER.get(x.get('structure', ''), 4),
        -(x.get('change', 0) or 0),
    ))

    pk_score = market_cycle.get('pk_score', 0)
    vl_score = market_cycle.get('vl_score', 0)
    bias20 = market_cycle.get('bias20', 0)
    if pk_score >= 4:
        plan['risk_items'].append(f'大盘偏波峰（pk_score={pk_score}），控制仓位')
    if bias20 > 5:
        plan['risk_items'].append(f'乖离率偏高（BIAS20={bias20:.1f}%），警惕回调')
    if vl_score >= 3:
        plan['risk_items'].append(f'大盘偏波谷（vl_score={vl_score}），积极寻找机会')

    return plan


def apply_trading_plan_actions(buy_signals_review, trading_plan):
    """把交易计划的数据门禁同步回买点卡片，避免同一股票出现两种操作结论。"""
    plan_by_code = {
        str(item.get('code', '')).split('.')[0]: item
        for item in trading_plan.get('buy_priority', [])
        if item.get('code')
    }
    for signal in buy_signals_review or []:
        item = plan_by_code.get(str(signal.get('code', '')).split('.')[0])
        if not item:
            continue
        signal['decision_status'] = item.get('decision_status', 'executable')
        signal['data_quality'] = item.get('data_quality', 'ready')
        signal['action_type'] = item.get('action_type', signal.get('action_type', '买入'))
        if item.get('decision_status') == 'blocked':
            signal['action_reason'] = item.get('opp_reason') or item.get('reason') or '板块数据待补齐'
    return buy_signals_review


# ═══════════════════════════════════════════════════════════════
# 辅助函数（供外部调用）
# ═══════════════════════════════════════════════════════════════

def load_market_data_for_profit_check():
    """加载市场数据（用于业绩排雷对照）"""
    return {}

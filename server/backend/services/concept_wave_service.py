"""概念板块波谷追踪 — 服务层（V5评分 + 回测）"""
import json, os, math, statistics

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')


def _calc_ema(values, period):
    """计算EMA"""
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema[-1]


def _calc_sma(values, period):
    """简单移动平均"""
    if len(values) < period:
        return None
    return statistics.mean(values[-period:])


def _calc_std(values):
    """样本标准差"""
    if len(values) < 2:
        return 0
    m = statistics.mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def make_synthetic_klines(closes, vols=None):
    """从收盘价序列生成合成K线（测试用）"""
    if vols is None:
        vols = [1e8] * len(closes)
    klines = []
    for i, c in enumerate(closes):
        spread = c * 0.01
        klines.append({
            'open': float(c - spread * 0.5),
            'high': float(c + spread * 0.8),
            'low': float(c - spread * 0.8),
            'close': float(c),
            'volume': float(vols[i]),
            'date': f'2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}',
        })
    return klines


def judge_concept_wave(klines):
    """
    概念板块 V5 波谷评分（单向评分：只评估偏波谷程度）
    
    输入: klines = [{date, open, high, low, close, volume}, ...]
    需要至少60根K线，不足则退化评分
    
    返回 dict:
      vl_score: 0~5 波谷评分
      pk_score: 0~5 波峰评分（仅参考）
      stage: '波谷'/'波中'/'下跌'
      bias20: float BIAS20值
      volume_ratio: float 量比（当日成交量/20日均量）
      details: {各个条件判定结果}
    """
    if not klines or len(klines) < 20:
        return {
            'vl_score': 0, 'pk_score': 0, 'stage': '下跌',
            'bias20': 0, 'bias5': 0, 'bias10': 0,
            'volume_ratio': 0, 'volume_signal': None,
            'ema10_slope': 0, 'two_sigma': 0,
            'details': {'reason': '数据不足'},
        }

    closes = [k['close'] for k in klines]
    volumes = [k.get('volume', 0) for k in klines]
    
    # 计算各项指标
    n = len(closes)
    i = n - 1  # 当前索引
    
    # ---- BIAS系列 ----
    ma5 = _calc_sma(closes, 5)
    ma10 = _calc_sma(closes, 10)
    ma20 = _calc_sma(closes, 20)
    
    bias5 = (closes[-1] - ma5) / ma5 * 100 if ma5 and ma5 > 0 else 0
    bias10 = (closes[-1] - ma10) / ma10 * 100 if ma10 and ma10 > 0 else 0
    bias20 = (closes[-1] - ma20) / ma20 * 100 if ma20 and ma20 > 0 else 0
    
    # ---- EMA10斜率 ----
    ema10_vals = []
    for j in range(n):
        ema10_vals.append(_calc_ema(closes[:j + 1], 10) or closes[j])
    
    if len(ema10_vals) >= 5:
        slope_now = (ema10_vals[-1] - ema10_vals[-3]) / ema10_vals[-3] * 100 if ema10_vals[-3] > 0 else 0
        slope_prev = (ema10_vals[-3] - ema10_vals[-6]) / ema10_vals[-6] * 100 if ema10_vals[-6] > 0 else 0
    else:
        slope_now = 0
        slope_prev = 0
    ema10_slope = slope_now
    
    # ---- 量比 ----
    if len(volumes) >= 20:
        vol_ma20 = statistics.mean(volumes[-20:])
        volume_ratio = volumes[-1] / vol_ma20 if vol_ma20 > 0 else 1
    else:
        vol_ma20 = statistics.mean(volumes)
        volume_ratio = volumes[-1] / vol_ma20 if vol_ma20 > 0 else 1
    
    # ---- 缩量趋势（近5日量均 vs 近20日量均） ----
    if len(volumes) >= 5:
        vol_5d_avg = statistics.mean(volumes[-5:])
    else:
        vol_5d_avg = volumes[-1]
    vol_shrink_ratio = vol_5d_avg / vol_ma20 if vol_ma20 > 0 else 1
    
    # ---- 量价信号 ----
    gain = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
    volume_signal = None
    if volume_ratio < 0.7 and vol_shrink_ratio < 0.8:
        volume_signal = 'shrink'
    elif volume_ratio > 1.5 and gain > 2:
        volume_signal = 'surge'
    elif volume_ratio > 2.0 and abs(gain) < 0.5:
        volume_signal = 'overheat'
    
    # ---- 2σ偏差 ----
    if len(closes) >= 20:
        recent20 = closes[-20:]
        mean20 = statistics.mean(recent20)
        std20 = _calc_std(recent20)
        z_score = (closes[-1] - mean20) / std20 if std20 > 0 else 0
        two_sigma = z_score
    else:
        two_sigma = 0
    
    # ---- V5 波谷评分 ----
    vl_score = 0
    pk_score = 0
    
    # 条件1: BIAS20 <-5%（价格远离20日线）
    if bias20 < -5:
        vl_score += 1
    if bias20 < -8:
        vl_score += 1  # 更极端再加1分
    
    # 条件2: 量缩（连续下跌后供应枯竭）
    if volume_ratio < 0.7:
        vl_score += 1
    if volume_ratio < 0.5:
        vl_score += 1
    
    # 条件3: EMA10斜率从负转平（下跌趋缓）
    if slope_now > -0.3 and slope_prev < -0.3:
        vl_score += 1
    if slope_now > 0 and slope_prev <= 0:
        vl_score += 1
    
    # 条件4: 2σ极端跌幅
    if z_score < -1.5:
        vl_score += 1
    if z_score < -2.0:
        vl_score += 1
    
    # 自动升级：BIAS20 < -10% → 必定波谷
    if bias20 < -10:
        vl_score = max(vl_score, 3)
    
    # 波峰评分（反向参考）
    if bias20 > 5:
        pk_score += 1
    if bias20 > 8:
        pk_score += 1
    if volume_ratio > 1.5 and gain < 0.5:
        pk_score += 1
    if slope_now < -0.3 and slope_prev > 0.3:
        pk_score += 1
    if z_score > 1.5:
        pk_score += 1
    
    # 阶段判定
    if vl_score >= 3:
        stage = '波谷'
    elif vl_score >= 1 or pk_score >= 3:
        stage = '波中'
    else:
        stage = '下跌'
    
    # 切入窗口：vl_score>=3 + BIAS20在-5%~-8% + 持续缩量
    entry_window = (vl_score >= 3 and
                    -8 <= bias20 <= -5 and
                    volume_signal == 'shrink')
    
    return {
        'vl_score': min(vl_score, 5),
        'pk_score': min(pk_score, 5),
        'stage': stage,
        'bias20': round(bias20, 2),
        'bias5': round(bias5, 2),
        'bias10': round(bias10, 2),
        'volume_ratio': round(volume_ratio, 2),
        'volume_signal': volume_signal,
        'ema10_slope': round(ema10_slope, 4),
        'two_sigma': round(two_sigma, 2),
        'entry_window': entry_window,
        'close': closes[-1],
        'change_pct': round(gain, 2),
        'details': {
            'bias20_cond': bias20 < -5,
            'bias20_extreme': bias20 < -8,
            'volume_shrink': volume_ratio < 0.7,
            'volume_extreme': volume_ratio < 0.5,
            'slope_flatten': slope_now > -0.3 and slope_prev < -0.3,
            'slope_turn_up': slope_now > 0 and slope_prev <= 0,
            'z_score_low': z_score < -1.5,
            'z_score_extreme': z_score < -2.0,
            'vol_5d_shrink_ratio': round(vol_shrink_ratio, 2),
        },
    }


def backtest_report(klines_history):
    """
    回测报告：遍历历史K线，找出vl_score>=3的日期，计算后续5日涨跌
    
    输入: klines_history — 完整的K线历史 [{date, close, ...}, ...]
    返回: [
        {
            'date': str,
            'vl_score': int,
            'bias20': float,
            'next_1d': float,   # 后续1日涨跌幅%
            'next_5d': float,   # 后续5日涨跌幅%
            'max_5d': float,    # 后续5日最大涨幅（相对回测日收盘）
            'hit_positive': bool,  # 后续5日是否正收益
        },
        ...
    ]
    """
    if len(klines_history) < 80:
        return {'error': '数据不足80根K线', 'signals': 0, 'hits': 0, 'results': []}
    
    results = []
    # 跳过最后20根K线（用作后续5日验证空间）
    for i in range(60, len(klines_history) - 5):
        segment = klines_history[:i + 1]
        v = judge_concept_wave(segment)
        
        if v['vl_score'] >= 3:
            date = klines_history[i]['date']
            close_now = klines_history[i]['close']
            
            # 后续1日、5日涨跌
            next_close_1d = klines_history[i + 1]['close']
            next_close_5d = klines_history[i + 5]['close']
            
            chg_1d = (next_close_1d - close_now) / close_now * 100
            chg_5d = (next_close_5d - close_now) / close_now * 100
            
            # 后续5日最大涨幅
            max_close = max(k['close'] for k in klines_history[i + 1:i + 6])
            max_5d = (max_close - close_now) / close_now * 100
            
            results.append({
                'date': date,
                'vl_score': v['vl_score'],
                'bias20': v['bias20'],
                'next_1d': round(chg_1d, 2),
                'next_5d': round(chg_5d, 2),
                'max_5d': round(max_5d, 2),
                'hit_positive': chg_5d > 0,
            })
    
    if not results:
        return {'error': '未发现vl_score>=3信号', 'signals': 0, 'hits': 0, 'results': []}
    
    signals = len(results)
    hits = sum(1 for r in results if r['hit_positive'])
    avg_5d = statistics.mean([r['next_5d'] for r in results]) if results else 0
    avg_max = statistics.mean([r['max_5d'] for r in results]) if results else 0
    
    return {
        'signals': signals,
        'hits': hits,
        'accuracy': round(hits / signals * 100, 1) if signals > 0 else 0,
        'avg_5d_return': round(avg_5d, 2),
        'avg_max_return': round(avg_max, 2),
        'results': results,
    }

"""
自选股诊断服务 — 多维分析：趋势面 + 财务面 + 风险提示
"""
import time
import logging as log

CACHE = {}
CACHE_TTL = 3600  # 1小时缓存

# ── 财务面（akshare）──

def _get_financial(code):
    """获取财务数据，带缓存"""
    now = time.time()
    cached = CACHE.get(f'fin_{code}')
    if cached and now - cached['ts'] < CACHE_TTL:
        return cached['data']

    try:
        import akshare as ak
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year='2025')
        if df.empty:
            return None
        row = df.tail(1).iloc[-1]
        data = {
            'roe': _float(row.get('净资产收益率(%)')),
            'eps': _float(row.get('摊薄每股收益(元)')),
            'revenue_growth': _float(row.get('主营业务收入增长率(%)')),
            'profit_growth': _float(row.get('净利润增长率(%)')),
            'debt_ratio': _float(row.get('资产负债率(%)')),
            'current_ratio': _float(row.get('流动比率')),
            'quick_ratio': _float(row.get('速动比率')),
            'net_margin': _float(row.get('销售净利率(%)')),
            'total_asset_growth': _float(row.get('总资产增长率(%)')),
            'date': str(row.get('日期', ''))[:10],
        }
        CACHE[f'fin_{code}'] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        log.warning(f'[诊断] 财务数据获取失败 {code}: {e}')
        return None


# ── 评分引擎 ──

def _score_financial(fin):
    """财务面评分 0~40"""
    if not fin:
        return 0, []
    remarks = []
    score = 20  # 基础分

    # ROE
    roe = fin.get('roe')
    if roe is not None:
        if roe > 20: score += 10; remarks.append(f'ROE {roe:.1f}% 优秀')
        elif roe > 10: score += 5; remarks.append(f'ROE {roe:.1f}% 良好')
        elif roe > 0: remarks.append(f'ROE {roe:.1f}% 偏低')
        else: score -= 10; remarks.append(f'ROE {roe:.1f}% 亏损')

    # 净利润增长
    pg = fin.get('profit_growth')
    if pg is not None:
        if pg > 30: score += 8; remarks.append(f'净利润增长 {pg:.1f}% 高速')
        elif pg > 10: score += 4; remarks.append(f'净利润增长 {pg:.1f}% 稳健')
        elif pg > 0: remarks.append(f'净利润增长 {pg:.1f}% 微增')
        else: score -= 8; remarks.append(f'净利润增长 {pg:.1f}% 下滑 ⚠️')

    # 营收增长
    rg = fin.get('revenue_growth')
    if rg is not None:
        if rg > 20: score += 5; remarks.append(f'营收增长 {rg:.1f}% 高速')
        elif rg > 5: score += 2; remarks.append(f'营收增长 {rg:.1f}% 稳健')
        elif rg > 0: pass
        else: score -= 5; remarks.append(f'营收下滑 {rg:.1f}% ⚠️')

    # 资产负债率
    dr = fin.get('debt_ratio')
    if dr is not None:
        if dr > 70: score -= 5; remarks.append(f'资产负债率 {dr:.1f}% 偏高 ⚠️')
        elif dr > 50: score -= 2; remarks.append(f'资产负债率 {dr:.1f}% 适中')
        else: score += 3; remarks.append(f'资产负债率 {dr:.1f}% 健康')

    return max(0, min(40, score)), remarks


def _score_trend(card):
    """趋势面评分 0~40"""
    if not card:
        return 0, []
    remarks = []
    score = 15

    structure = (card.get('structure') or '').strip()
    stage = (card.get('stage') or '').strip()
    signal = (card.get('signal') or 'hold')
    mainline = (card.get('mainline_level') or '').strip()
    buy_point = (card.get('buy_point') or '').strip()
    deviation = card.get('deviation_pct') or 0

    # 结构
    if '上升' in structure:
        score += 8; remarks.append('上升趋势 +8')
    elif '震荡' in structure:
        score += 2; remarks.append('震荡盘整 +2')
    elif '下降' in structure:
        score -= 5; remarks.append('下降趋势 -5')

    # 阶段
    if stage in ('上行', '转强', '加速'):
        score += 5; remarks.append(f'阶段{stage} +5')
    elif stage in ('调整', '缩量整理'):
        score += 1
    elif stage in ('转弱', '下行', '加速跌'):
        score -= 5; remarks.append(f'阶段{stage} -5')

    # 信号
    if signal == 'buy':
        score += 5; remarks.append('买入信号 +5')
    elif signal == 'sell':
        score -= 5; remarks.append('卖出信号 -5')

    # 主线
    if mainline and '非主线' not in mainline:
        score += 5; remarks.append(f'{mainline} +5')

    # 买点
    if buy_point:
        score += 5; remarks.append(f'买点:{buy_point} +5')

    # 乖离率
    if deviation:
        if abs(deviation) > 10:
            score -= 3; remarks.append(f'乖离率{deviation:.1f}% 偏离过大 -3')

    return max(0, min(40, score)), remarks


def _score_risks(fin, trend_score):
    """风险评估 0~20（扣分制，得分越高越安全）"""
    score = 20
    risks = []
    if not fin:
        return 15, ['缺少财务数据'], '中风险'

    # 盈利风险
    pg = fin.get('profit_growth')
    if pg is not None and pg < -20:
        score -= 8; risks.append(f'净利润大幅下滑 {pg:.1f}%')
    elif pg is not None and pg < 0:
        score -= 4; risks.append(f'净利润负增长 {pg:.1f}%')

    # 负债风险
    dr = fin.get('debt_ratio')
    if dr is not None and dr > 80:
        score -= 5; risks.append(f'高负债率 {dr:.1f}%')
    elif dr is not None and dr > 60:
        score -= 2

    # 流动性风险
    cr = fin.get('current_ratio')
    if cr is not None and cr < 1:
        score -= 3; risks.append(f'流动比率 {cr:.2f} < 1')
    qr = fin.get('quick_ratio')
    if qr is not None and qr < 0.5:
        score -= 2; risks.append(f'速动比率 {qr:.2f} < 0.5')

    # 趋势风险（来自趋势评分低）
    if trend_score < 10:
        score -= 5; risks.append('趋势面评分极低')
        risk_level = '高风险'
    elif trend_score < 20:
        score -= 2; risks.append('趋势面偏弱')
        risk_level = '中风险'
    else:
        risk_level = '低风险'

    return max(0, min(20, score)), risks, risk_level


def _grade(total):
    if total >= 85: return 'A'
    if total >= 70: return 'B'
    if total >= 55: return 'C'
    return 'D'


def compute_diagnosis(code, name, card):
    """对一只股票做完整诊断"""
    t0 = time.time()

    # 1. 财务面
    fin = _get_financial(code)
    fin_score, fin_remarks = _score_financial(fin)

    # 2. 趋势面
    trend_score, trend_remarks = _score_trend(card)

    # 3. 风险
    risk_score, risks, risk_level = _score_risks(fin, trend_score)

    total = fin_score + trend_score + risk_score

    diagnosis = {
        'code': code,
        'name': name,
        'total_score': total,
        'grade': _grade(total),
        'detail': {
            'financial': {
                'score': fin_score,
                'data': fin,
                'remarks': fin_remarks,
            },
            'trend': {
                'score': trend_score,
                'remarks': trend_remarks,
            },
            'risk': {
                'score': risk_score,
                'level': risk_level,
                'items': risks,
            },
        },
        'cost_ms': int((time.time() - t0) * 1000),
    }
    return diagnosis


def _float(v):
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return None

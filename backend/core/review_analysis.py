"""
review_analysis.py — 复盘数据分析模块

从 generate_review_data.py 的③区段提取的纯函数。
接受数据为参数，不做文件I/O。可测试。
"""

import sys

from backend.core.data_layer import get_industry_map


def _recalc_stage_for_range(structure, stage, code, stocks):
    """区间震荡：用关键点支撑位重算stage
    
    从 generate_review_data.py 836-875行提取。
    """
    if structure != '区间震荡' or not stocks:
        return stage
    try:
        kls = None
        for sec, ss in stocks.items():
            if code in ss and ss[code] and len(ss[code]) >= 15:
                kls = ss[code]
                break
        if not kls:
            return stage
        
        highs = [k['high'] for k in kls]
        lows = [k['low'] for k in kls]
        closes = [k['close'] for k in kls]
        opens = [k['open'] for k in kls]
        
        all_supports = sorted([
            max(highs[i-10:i])
            for i in range(10, len(kls))
            if closes[i] > max(highs[i-10:i]) and closes[i] > opens[i]
            and max(highs[i-10:i]) < closes[-1]
        ], reverse=True)
        
        resistance = max(highs[-15:])
        support = None
        for s in all_supports:
            if (closes[-1] - s) / closes[-1] >= 0.015:
                support = s
                break
        support = support or min(lows[-20:])
        
        if resistance > support:
            pct = (closes[-1] - support) / (resistance - support) * 100
            if pct < 30:
                return '区间底部'
            elif pct > 70:
                return '区间顶部'
            else:
                return '区间中段'
    except Exception:
        pass
    return stage


def _get_actual_date(code, stocks, date_str):
    """用该股K线实际最新日期"""
    actual = date_str
    for sec_name, sec_stocks in stocks.items():
        if code in sec_stocks:
            kls = sec_stocks[code]
            if kls:
                last_d = kls[-1]['date']
                actual = last_d[:4] + '-' + last_d[4:6] + '-' + last_d[6:8]
            break
    return actual


def generate_holdings_review(holdings, stocks, buy_signals,
                              timing_signals_holdings, bs_by_code,
                              date_str, mainlines, trend_mainlines=None):
    """为每只持仓生成复盘结论
    
    Args:
        holdings: 原始持仓列表 [{'code', 'name', ...}]
        stocks: {方向: {code: [klines]}}
        buy_signals: 买点信号列表
        timing_signals_holdings: get_buy_sell_signals 返回的 holdings 列表
        bs_by_code: {code: signal_dict}
        date_str: 'YYYY-MM-DD'
        mainlines: {'lines': [...], 'secondary': [...]}
        trend_mainlines: 主线名称列表，None时从mainlines取
    
    Returns:
        [{'code', 'name', 'structure', 'stage', 'signal', ...}]
    """
    from backend.core.judge_signal import judge_signal
    from services.stock_card_service import get_stock_card

    if trend_mainlines is None:
        trend_mainlines = [l['name'] for l in (
            mainlines.get('lines', []) + mainlines.get('secondary', [])
        )]

    holdings_data = {h.get('code', ''): h for h in holdings}
    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}
    
    result = []
    for h in timing_signals_holdings:
        code = h.get('code', '')
        d = holdings_data.get(code, {})
        structure = h.get('structure', '')
        stage = h.get('stage', '--')

        # 区间震荡：重算stage
        stage = _recalc_stage_for_range(structure, stage, code, stocks)

        # 信号判定
        try:
            code_sig, signal_text, _ = judge_signal(
                structure=structure, stage=stage, buy_point=h['action'],
            )
        except Exception:
            code_sig = '无信号'
            signal_text = ''

        buy_point = h['action'].split()[0] if code_sig == 'buy' and h['action'] else ''
        bs_lookup = bs_by_code.get(code, {})
        pm1 = bs_lookup.get('profit_model1', False)
        trend = bs_lookup.get('trend_stock', False)

        actual_date = _get_actual_date(code, stocks, date_str)

        # 通过 StockCardService 获取统一计算
        kls_for_card = None
        for sec, ss in stocks.items():
            if code in ss:
                kls_for_card = ss[code]
                break

        try:
            card = get_stock_card(
                code=code,
                date_str=actual_date,
                market_position='波中',
                main_lines=mainlines,
                direction=d.get('direction', ''),
                klines=kls_for_card,
            )
            card_price = card['price']
            card_change = card['change']
            card_buy_point = card['buy_point']
            trading_system = card['trading_system']
            trading_reason = card['trading_reason']
            trend_buy_type = card.get('trend_buy_type', '')
            trend_bias = card.get('trend_bias', '')
            real_sector = card['sector']
            mainline_level = card['mainline_level']
            sl = card['stop_loss']
            sl_pct = card['stop_loss_pct']
        except Exception:
            card_price = h.get('close', 0)
            card_change = h.get('change', 0)
            card_buy_point = ''
            trading_system = '3l'
            trading_reason = '判定失败'
            trend_buy_type = ''
            trend_bias = ''
            real_sector = bs_lookup.get('sector', d.get('direction', ''))
            mainline_level = ''
            sl = None
            sl_pct = None

        # 买点优先用卡片数据（比扫描缓存更新更准确）
        if code_sig == 'buy' and card_buy_point:
            buy_point = card_buy_point

        # 手动止损优先于自动生成止损
        manual_sl = d.get('stop_loss_price')
        if manual_sl is not None:
            sl = float(manual_sl)
            sl_pct = round((card_price - sl) / card_price * 100, 2) if card_price and card_price > 0 else None

        result.append({
            'code': code,
            'name': h.get('name', d.get('name', code)),
            'sector': real_sector,
            'direction': d.get('direction', ''),
            'structure': structure,
            'stage': stage,
            'price': card_price,
            'change': card_change,
            'ema': h.get('ema', '--'),
            'vol_analysis': h.get('vol_analysis', '--'),
            'signal': code_sig,
            'signal_text': signal_text,
            'buy_point': buy_point,
            'profit_model1': pm1,
            'trend_stock': trend,
            'trading_system': trading_system,
            'trading_reason': trading_reason,
            'trend_buy_type': trend_buy_type,
            'trend_bias': trend_bias,
            'mainline_level': mainline_level,
            'stop_loss': sl,
            'stop_loss_pct': sl_pct,
        })

    result.sort(key=lambda x: struct_priority.get(x['structure'], 3))
    return result


def generate_buy_signals_review(buy_signals, stocks, stock_cache,
                                 date_str, mainlines, trend_mainlines=None):
    """生成买点信号复盘
    
    Args:
        buy_signals: 买点信号列表
        stocks: {方向: {code: [klines]}}
        stock_cache: get_buy_sell_signals 返回的 cache
        date_str: 'YYYY-MM-DD'
        mainlines: {'lines': [...], 'secondary': [...]}
        trend_mainlines: 主线名称列表
    
    Returns:
        [{'code', 'name', 'buy_point', 'score', ...}]
    """
    from backend.core.judge_signal import judge_signal
    from services.stock_card_service import get_stock_card

    if trend_mainlines is None:
        trend_mainlines = [l["name"] for l in (
            mainlines.get("lines", []) + mainlines.get("secondary", [])
        )]

    result = []
    for s in buy_signals:
        code = s.get("code", "")
        sc_info = stock_cache.get(code, {})
        structure = sc_info.get("structure", "上涨趋势")
        stage = sc_info.get("stage", "--")

        # 区间震荡：重算stage
        stage = _recalc_stage_for_range(structure, stage, code, stocks)

        buy_point_display = s.get("buy_point", "")
        actual_date = _get_actual_date(code, stocks, date_str)

        # 通过 StockCardService 获取统一计算
        kls_for_card = None
        for sec, ss in stocks.items():
            if code in ss:
                kls_for_card = ss[code]
                break

        try:
            card = get_stock_card(
                code=code,
                date_str=actual_date,
                market_position="波中",
                main_lines=mainlines,
                direction=s.get("sector", ""),
                klines=kls_for_card,
            )
            card_price = card["price"]
            card_change = card["change"]
            card_buy_point = card["buy_point"]
            card_signal = card.get("signal", "hold")
            trading_system = card["trading_system"]
            trading_reason = card["trading_reason"]
            trend_buy_type = card.get("trend_buy_type", "")
            trend_bias = card.get("trend_bias", "")
            real_sector = card["sector"]
            mainline_level = card["mainline_level"]
            sl = card["stop_loss"]
            sl_pct = card["stop_loss_pct"]
        except Exception:
            card_price = s.get("price", 0)
            card_change = s.get("change", 0)
            card_buy_point = ""
            card_signal = "hold"
            trading_system = "3l"
            trading_reason = "判定失败"
            trend_buy_type = ""
            trend_bias = ""
            sector = s.get("sector", "")
            real_sector = sector
            mainline_level = ""
            sl = None
            sl_pct = None

        # 信号只看最新K线（用卡片的判定结果）
        if card_signal != "buy":
            continue

        direction = s.get("direction", s.get("sector", ""))
        # 买点优先用卡片数据
        if card_buy_point:
            buy_point_display = card_buy_point

        result.append({
            "name": s.get("name", "?"),
            "code": code,
            "sector": real_sector or direction,
            "direction": direction,
            "buy_point": buy_point_display,
            "price": card_price,
            "change": card_change,
            "score": s.get("score", 0),
            "profit_model1": s.get("profit_model1", False),
            "trend_stock": s.get("trend_stock", False),
            "trading_system": trading_system,
            "trading_reason": trading_reason,
            "trend_buy_type": trend_buy_type,
            "trend_bias": trend_bias,
            "mainline_level": mainline_level,
            "stop_loss": sl,
            "stop_loss_pct": sl_pct,
            "structure": structure,
            "stage": stage,
            "signal": card_signal,
            "ema": sc_info.get("ema", "--"),
            "vol_analysis": sc_info.get("vol_analysis", "--"),
            "flags": s.get("flags", ""),
        })

    # 按分数降序
    result.sort(key=lambda x: x.get('score', 0), reverse=True)
    return result

"""
review_analysis.py — 复盘数据分析模块

从 generate_review_data.py 的③区段提取的纯函数。
接受数据为参数，不做文件I/O。可测试。
"""

import sys
import math

from backend.core.logger import get_logger

log = get_logger(__name__)


def _finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def build_holdings_risk_exposure(holdings, holdings_review):
    """按真实持仓记录计算组合风险暴露，不用建议仓位代替实际仓位。

    当前持仓模型只记录仓位百分比，不记录股数/市值，因此口径明确为
    “按记录仓位”；系统不伪造盘中市值权重。
    """
    raw_by_code = {
        str(item.get('code', '')).split('.')[0]: item
        for item in (holdings or []) if item.get('code')
    }
    review_by_code = {
        str(item.get('code', '')).split('.')[0]: item
        for item in (holdings_review or []) if item.get('code')
    }
    ordered_codes = list(raw_by_code)
    ordered_codes.extend(code for code in review_by_code if code not in raw_by_code)
    items = []
    direction_position = {}
    missing_ratio = []
    missing_price = []
    missing_stop = []
    breached = []
    total_position = 0.0
    covered_position = 0.0
    breached_position = 0.0
    unassessable_position = 0.0
    downside_to_stops = 0.0
    missing_cost = []
    stop_warnings = []

    for code in ordered_codes:
        review = review_by_code.get(code, {})
        raw = raw_by_code.get(code, {})
        ratio = _finite_number(raw.get('target_ratio', raw.get('ratio')))
        ratio = ratio if ratio is not None and 0 <= ratio <= 100 else None
        price = _finite_number(review.get('price'))
        cost = _finite_number(raw.get('cost_price', raw.get('buy_price')))
        stop = _finite_number(review.get('stop_loss'))
        if stop is None:
            stop = _finite_number(raw.get('stop_loss_price'))
        stop_source = review.get('stop_loss_source') or (
            'manual' if _finite_number(raw.get('stop_loss_price')) not in (None, 0) else 'unknown'
        )
        direction = (
            review.get('direction') or review.get('industry') or review.get('sector')
            or raw.get('direction') or raw.get('sector') or '未分类'
        )

        if ratio is None:
            missing_ratio.append(code)
        else:
            total_position += ratio
            direction_position[direction] = direction_position.get(direction, 0.0) + ratio
        if price is None or price <= 0:
            missing_price.append(code)
        if cost is None or cost <= 0:
            missing_cost.append(code)

        stop_valid = stop is not None and stop > 0
        price_valid = price is not None and price > 0
        stop_breached = bool(stop_valid and price_valid and price <= stop)
        stop_assessable = bool(stop_valid and price_valid)
        stop_warning = str(review.get('stop_loss_warning') or '')
        if stop_warning:
            stop_warnings.append({'code': code, 'name': review.get('name') or raw.get('name', ''), 'message': stop_warning})
        downside_pct = None
        risk_contribution = None
        if not stop_valid:
            missing_stop.append(code)
        elif ratio is not None and not stop_assessable:
            unassessable_position += ratio
        elif ratio is not None:
            if stop_breached:
                breached_position += ratio
            else:
                covered_position += ratio
        if stop_valid and price is not None and price > 0:
            downside_pct = round(max(0.0, (price - stop) / price * 100), 2)
            if ratio is not None:
                risk_contribution = round(ratio * downside_pct / 100, 3)
                downside_to_stops += risk_contribution
        if stop_breached:
            breached.append(code)

        unrealized_pct = None
        if cost is not None and cost > 0 and price is not None and price > 0:
            unrealized_pct = round((price - cost) / cost * 100, 2)

        items.append({
            'code': code,
            'name': review.get('name') or raw.get('name', ''),
            'direction': direction,
            'position_pct': round(ratio, 2) if ratio is not None else None,
            'cost_price': round(cost, 3) if cost is not None else None,
            'current_price': round(price, 3) if price is not None else None,
            'stop_loss': round(stop, 3) if stop is not None else None,
            'stop_loss_source': stop_source,
            'stop_loss_warning': stop_warning,
            'downside_to_stop_pct': downside_pct,
            'portfolio_risk_pct': risk_contribution,
            'unrealized_pnl_pct': unrealized_pct,
            'stop_status': (
                'breached' if stop_breached
                else 'covered' if stop_assessable
                else 'unassessable' if stop_valid
                else 'missing'
            ),
        })

    ranked_directions = sorted(
        ({'name': name, 'position_pct': round(value, 2)} for name, value in direction_position.items()),
        key=lambda item: item['position_pct'], reverse=True,
    )
    largest_item = max(
        (item for item in items if item['position_pct'] is not None),
        key=lambda item: item['position_pct'], default=None,
    )
    missing = []
    if missing_ratio:
        missing.append(f'{len(missing_ratio)}只缺少仓位比例')
    if missing_price:
        missing.append(f'{len(missing_price)}只缺少当日价格')
    if missing_cost:
        missing.append(f'{len(missing_cost)}只缺少持仓成本')
    if missing_stop:
        missing.append(f'{len(missing_stop)}只缺少有效止损')
    if stop_warnings:
        missing.append(f'{len(stop_warnings)}只手动止损无效，已回退系统建议')
    invalid_total = total_position > 100.0001
    if invalid_total:
        missing.append(f'记录仓位合计异常（{total_position:.2f}% > 100%）')
    status = 'confirmed' if not missing else 'partial'
    return {
        'status': status,
        'basis': '按用户记录仓位比例与当日收盘价计算；未记录股数/市值时不伪造盘中权重',
        'total_position_pct': round(total_position, 2),
        'cash_pct': (
            round(100 - total_position, 2)
            if not missing_ratio and not invalid_total else None
        ),
        'stop_covered_position_pct': round(covered_position, 2),
        'breached_position_pct': round(breached_position, 2),
        'unassessable_position_pct': round(unassessable_position, 2),
        'uncovered_position_pct': round(max(
            0.0, total_position - covered_position - breached_position - unassessable_position,
        ), 2),
        'portfolio_downside_to_stops_pct': round(downside_to_stops, 3),
        'largest_position': ({
            'code': largest_item['code'], 'name': largest_item['name'],
            'position_pct': largest_item['position_pct'],
        } if largest_item else None),
        'direction_concentration': ranked_directions,
        'breached_stop_codes': breached,
        'stop_warnings': stop_warnings,
        'missing': missing,
        'items': items,
    }


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
    from backend.services.stock_card_service import get_stock_card

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
        actual_date = _get_actual_date(code, stocks, date_str)

        # 全部从 StockCardService 取，不碰扫描缓存
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
        except Exception:
            log.warning('个股卡片生成失败（持仓分析）: %s', d.get('code', '?'))
            card = None

        if not card:
            continue

        # 手动止损（唯一不从卡片取的东西）
        stop_loss = card['stop_loss']
        stop_loss_pct = card['stop_loss_pct']
        manual_raw = d.get('stop_loss_price')
        manual_sl = _finite_number(manual_raw)
        manual_valid = manual_sl is not None and manual_sl > 0
        invalid_manual = manual_raw is not None and manual_raw != '' and not manual_valid
        if manual_valid:
            stop_loss = manual_sl
            stop_loss_pct = round((card['price'] - stop_loss) / card['price'] * 100, 2) if card['price'] and card['price'] > 0 else None
        decision = dict(card.get('decision', {}))
        decision.update({'stop_loss': stop_loss, 'stop_loss_pct': stop_loss_pct})

        result.append({
            'code': card['code'],
            'name': card['name'],
            'industry': card.get('industry', card['sector']),
            'sector': card['sector'],
            'direction': card.get('direction', ''),
            'structure': card['structure'],
            'stage': card['stage'],
            'price': card['price'],
            'change': card['change'],
            'ema': card['ema'],
            'vol_analysis': card['vol_analysis'],
            'signal': card['signal'],
            'signal_text': card.get('signal_text', ''),
            'buy_point': card['buy_point'],
            'profit_model1': card['profit_model1'],
            'trend_stock': card['trend_stock'],
            'trading_system': card['trading_system'],
            'trading_reason': card.get('trading_reason', ''),
            'trend_buy_type': card.get('trend_buy_type', ''),
            'trend_bias': card.get('trend_bias', ''),
            'mainline_level': card.get('mainline_level', ''),
            'matched_mainline_direction': card.get('matched_mainline_direction', ''),
            'stop_loss': stop_loss,
            'stop_loss_pct': stop_loss_pct,
            'position_pct': _finite_number(d.get('target_ratio', d.get('ratio'))),
            'cost_price': _finite_number(d.get('cost_price', d.get('buy_price'))),
            'stop_loss_source': 'manual' if manual_valid else 'system',
            'stop_loss_warning': '手动止损无效，已回退系统建议' if invalid_manual else '',
            'decision': decision,
            # 融合判定字段
            'triggered_signals': card.get('triggered_signals', []),
            'fusion_type': card.get('fusion_type', ''),
            'fusion_reason': card.get('fusion_reason', ''),
            'wave_position': card.get('wave_position', ''),
            'structure_context': card.get('structure_context'),
            'structure_context_status': card.get('structure_context_status', ''),
            'major_decline_risk': card.get('major_decline_risk', {}),
            'structure_wave_position': card.get('structure_wave_position', {}),
            'legacy_structure': card.get('legacy_structure', {}),
            # 操作建议（由卡片统一推导，外部不重复计算）
            'action_type': card.get('action_type', '持有'),
            'action_signal': card.get('action_signal', ''),
            'action_priority': card.get('action_priority', '中'),
            'action_reason': card.get('action_reason', ''),
        })

    result.sort(key=lambda x: struct_priority.get(x['structure'], 3))
    return result


def generate_buy_signals_review(buy_signals, stocks, stock_cache,
                                 date_str, mainlines, trend_mainlines=None,
                                 direction_map=None):
    """生成买点信号复盘

    Args:
        buy_signals: 买点信号列表
        stocks: {方向: {code: [klines]}}
        stock_cache: get_buy_sell_signals 返回的 cache
        date_str: 'YYYY-MM-DD'
        mainlines: {'lines': [...], 'secondary': [...]}
        trend_mainlines: 主线名称列表
        direction_map: {code: direction} 来自 watchlist 的方向映射

    Returns:
        [{'code', 'name', 'buy_point', 'score', ...}]
    """
    from backend.services.stock_card_service import get_stock_card

    if direction_map is None:
        direction_map = {}

    if trend_mainlines is None:
        trend_mainlines = [l["name"] for l in (
            mainlines.get("lines", []) + mainlines.get("secondary", [])
        )]

    result = []
    for s in buy_signals:
        code = s.get("code", "")
        actual_date = _get_actual_date(code, stocks, date_str)

        # 方向优先从 watchlist 取（用户手动设定），回退到空让卡片自己算
        direction = direction_map.get(code, '')

        # 扫描已产出完整卡片数据 → 直接格式化（无重复调 get_stock_card）
        if s.get('stop_loss') is not None or s.get('structure'):
            card_data = dict(s)
            if direction:
                card_data['direction'] = direction
            card = card_data
        else:
            # 补充扫描（盈利模式1/趋势股）没有完整卡片数据，调一次
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
                    direction=direction,
                    klines=kls_for_card,
                )
            except Exception:
                log.warning('个股卡片生成失败（趋势候选）: %s', code)
                card = None

        if not card:
            continue

        # 信号只看最新K线 — 用 get_stock_card 确认
        if card.get("technical_signal", card.get("signal")) != "buy":
            continue

        result.append({
            "code": card['code'],
            "name": card['name'],
            "industry": card.get('industry', card['sector']),
            "sector": card['sector'],
            "direction": direction or card.get('direction', ''),
            "buy_point": card['buy_point'],
            "date": card.get('date', actual_date),
            "price": card['price'],
            "change": card['change'],
            "score": card.get('score', 0),
            "profit_model1": card['profit_model1'],
            "trend_stock": card['trend_stock'],
            "trading_system": card['trading_system'],
            "trading_reason": card.get('trading_reason', ''),
            "trend_buy_type": card.get('trend_buy_type', ''),
            "trend_bias": card.get('trend_bias', ''),
            "mainline_level": card.get('mainline_level', ''),
            "matched_mainline_direction": card.get('matched_mainline_direction', ''),
            "stop_loss": card['stop_loss'],
            "stop_loss_pct": card['stop_loss_pct'],
            "decision": card.get('decision', {}),
            "structure": card['structure'],
            "stage": card['stage'],
            "signal": "buy",
            "execution_signal": card.get('execution_signal', card.get('signal', 'hold')),
            "technical_signal": card.get('technical_signal', card.get('signal', 'buy')),
            "technical_confidence": card.get('technical_confidence', card.get('score', 0)),
            "technical_reason": card.get('technical_reason', ''),
            "ema": card['ema'],
            "vol_analysis": card['vol_analysis'],
            "flags": card.get('flags', ''),
            "triggered_signals": card.get('triggered_signals', []),
            "fusion_type": card.get('fusion_type', ''),
            "fusion_reason": card.get('fusion_reason', ''),
            "wave_position": card.get('wave_position', ''),
            "structure_context": card.get('structure_context'),
            "structure_context_status": card.get('structure_context_status', ''),
            "major_decline_risk": card.get('major_decline_risk', {}),
            "structure_wave_position": card.get('structure_wave_position', {}),
            "legacy_structure": card.get('legacy_structure', {}),
            # 操作建议（由卡片统一推导，外部不重复计算）
            "action_type": card.get('action_type', '持有'),
            "action_signal": card.get('action_signal', ''),
            "action_priority": card.get('action_priority', '中'),
            "action_reason": card.get('action_reason', ''),
        })

    # 按分数降序
    result.sort(key=lambda x: x.get('score', 0), reverse=True)
    return result

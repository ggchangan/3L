"""个股回测服务 — 封装回测逻辑供 API 及其他模块调用"""

import config
from scripts.data_layer import get_all_stocks, resolve_stock
from scripts.buy_point_detection import (
    detect_buy_point, find_idx, _volume_ratio,
    gen_trade_chart_svg, compute_trade_stats, simulate_trade,
)
from scripts.ema_utils import get_structure, get_stage, ema_list
from scripts.trend_trading import decide_system_with_detail, simulate_trend_trade



def run_backtest(code_q, days=60, stocks=None):
    """对指定股票代码/名称执行回测，返回结果字典。
    
    stocks 可选参数，用于测试注入；生产不传走缓存。
    """

    # 搜索股票（精确code → 模糊code → 模糊名称 → 全市场）
    if stocks is None:
        stocks = get_all_stocks()
    matched_code, matched_direction, matched_name = resolve_stock(code_q, stocks)

    if not matched_code:
        return {'error': f'未找到股票: {code_q}'}

    resolved_code = matched_code
    stock_name = matched_name
    stock_direction = matched_direction
    kls = stocks[matched_direction][matched_code]
    sub = {stock_direction: {resolved_code: kls}}

    # ----- 确定当前系统 -----
    _last_d = str(kls[-1]['date']).replace('-', '')
    _today_fmt = f"{_last_d[:4]}-{_last_d[4:6]}-{_last_d[6:8]}"
    _bt_sys = decide_system_with_detail(resolved_code, _today_fmt, stocks)
    _bt_system = _bt_sys['system']

    # ----- 回测 -----
    signals = []
    start_idx = max(30, len(kls) - days)
    cum = 1.0

    # ── 3L 回测 ──
    if _bt_system == '3l':
        i = start_idx
        while i < len(kls):
            d = str(kls[i]['date']).replace('-', '')
            df = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            bt = detect_buy_point(
                resolved_code, df, sub,
                market_position='波中', main_lines={'半导体'},
            )
            if bt:
                entry = bt['close']
                buy_type = bt['buy_type']
                trade = simulate_trade(kls, i, entry, buy_type, max_days=60)
                if trade and trade['exit_idx'] is not None:
                    ei = trade['exit_idx']
                    exit_price = trade['exit_price']
                    gain = round((exit_price - entry) / entry * 100, 2)
                    cum *= (1 + gain / 100)
                    sig_date = bt.get('date', df)
                    exit_date_raw = str(kls[ei]['date']).replace('-', '')
                    sig_exit_date = (
                        f"{exit_date_raw[:4]}-{exit_date_raw[4:6]}-{exit_date_raw[6:8]}"
                        if ei != i else None
                    )
                    signals.append({
                        'n': len(signals) + 1,
                        'date': sig_date,
                        'type': buy_type,
                        'entry': entry,
                        'exit': exit_price if ei != i else None,
                        'exit_date': sig_exit_date,
                        'gain': gain,
                        'cum_gain': round((cum - 1) * 100, 2),
                        'days': trade['hold_days'],
                        'exit_reason': trade['exit_reason'],
                        'stop_triggered': trade['stop_triggered'],
                        'buy_back_price': trade.get('buy_back_price'),
                        'max_gain': trade.get('max_gain'),
                        'max_loss': trade.get('max_loss'),
                        'trading_system': '3l',
                    })
                    i = max(i + 1, ei + 1)
                    continue
            i += 1

    # ── 趋势回测 ──
    closes = [k['close'] for k in kls]
    ema5 = ema_list(closes, 5)
    trend_cum = 1.0
    trend_signals = []

    if _bt_system == 'trend':
        i = start_idx
        while i < len(kls) - 1:
            cur_close = kls[i]['close']
            if ema5[i] and ema5[i] > 0:
                bias5 = (cur_close - ema5[i]) / ema5[i] * 100
                if bias5 < 2:
                    trade = simulate_trend_trade(kls, i)
                    if trade:
                        hold_days = trade['hold_days']
                        exit_idx = min(i + hold_days, len(kls) - 1)
                        exit_price = kls[exit_idx]['close']
                        entry_date_raw = str(kls[i]['date']).replace('-', '')
                        entry_date = (
                            f"{entry_date_raw[:4]}-{entry_date_raw[4:6]}-{entry_date_raw[6:8]}"
                        )
                        gain = trade['ret']
                        trend_cum *= (1 + gain / 100)
                        if exit_idx != i and exit_idx > i:
                            exit_date_raw = str(kls[exit_idx]['date']).replace('-', '')
                            exit_date = (
                                f"{exit_date_raw[:4]}-{exit_date_raw[4:6]}-{exit_date_raw[6:8]}"
                            )
                            actual_days = exit_idx - i
                            raw_reason = trade.get('exit_reason', '--')
                            exit_reason = (
                                '数据结束'
                                if (raw_reason == '持满60天' and actual_days < 50)
                                else raw_reason
                            )
                            skip_to = exit_idx
                        else:
                            exit_date = None
                            exit_price = None
                            actual_days = 0
                            gain = 0
                            exit_reason = '待退出'
                            skip_to = i + 1
                        trend_signals.append({
                            'n': 0,
                            'date': entry_date,
                            'type': 'BIAS5乖离率买入',
                            'entry': cur_close,
                            'exit': exit_price,
                            'exit_date': exit_date,
                            'gain': gain,
                            'cum_gain': round((trend_cum - 1) * 100, 2),
                            'days': actual_days,
                            'exit_reason': exit_reason,
                            'stop_triggered': trade.get('exit_reason', '') in ('止损', '跟踪止盈'),
                            'trading_system': 'trend',
                        })
                        i = max(i + 1, skip_to)
                        continue
            i += 1

    # ── 合并信号，按日期排序 ──
    for s in trend_signals:
        s['n'] = len(signals) + 1
        signals.append(s)
    all_signals = sorted(signals, key=lambda x: x['date'])
    for idx, s in enumerate(all_signals):
        s['n'] = idx + 1

    # ── 合并统计 ──
    combined_stats = (
        compute_trade_stats(all_signals)
        if all_signals
        else {
            'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
            'avg_win': 0, 'avg_loss': 0, 'cumulative_return': 0,
        }
    )

    # ── 生成图表 SVG ──
    chart_abs = config.backtest_chart_svg(resolved_code)
    has_chart = gen_trade_chart_svg(kls, all_signals, stock_name, resolved_code, chart_abs)

    return {
        'code': resolved_code,
        'name': stock_name,
        'direction': stock_direction,
        'signals': all_signals,
        'chart_svg': f'/review_charts/bt_{resolved_code}.svg',
        'has_chart': has_chart,
        **combined_stats,
    }

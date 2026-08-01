"""
持仓/交易服务 — 持仓、交易数据读写
"""
import json, math, os, requests, tempfile
from backend.core.logger import get_logger
log = get_logger(__name__)
from datetime import date, datetime
from backend.core.config import HOLDINGS_PATH, TRADES_PATH

# ── 个股持仓卡片缓存（个股粒度，K线不变不重算）──
import time as _time
_CARD_CACHE = {}       # {code: card_data}
_CARD_CACHE_EXPIRY = {}  # {code: expiry_timestamp}
_CARD_CACHE_TTL = 300   # 5分钟


def _get_cached_cards(codes):
    """批量读取缓存，返回 {已缓存code: card}，缺失的code另行计算"""
    now = _time.time()
    result = {}
    for code in codes:
        if code in _CARD_CACHE and now < _CARD_CACHE_EXPIRY.get(code, 0):
            result[code] = _CARD_CACHE[code]
    return result


def _set_cached_cards(cards):
    """批量写入缓存"""
    expiry = _time.time() + _CARD_CACHE_TTL
    for code, card in cards.items():
        _CARD_CACHE[code] = card
        _CARD_CACHE_EXPIRY[code] = expiry


def _invalidate_card_cache(code):
    """个股卡片缓存失效"""
    _CARD_CACHE.pop(code, None)
    _CARD_CACHE_EXPIRY.pop(code, None)


def _get_cached_card(code):
    """获取单只个股卡片缓存，未命中返回 None"""
    now = _time.time()
    if code in _CARD_CACHE and now < _CARD_CACHE_EXPIRY.get(code, 0):
        return _CARD_CACHE[code]
    return None


def _kline_date(kline):
    return str(kline.get('date', '')).replace('-', '')


def get_stop_loss_recommendation(code, buy_date=None, buy_price=None, current_stop=None):
    """计算持仓止损建议，但不修改用户保存的手工止损。

    初始止损使用买入日之前可见的 K 线和买入价；保护止损使用最新价格结构。
    已有止损只允许上移，不能被建议值下调。
    """
    from backend.data_access.data_layer import get_stock_klines
    from backend.core.buy_point_detection import calc_stop_loss

    klines = get_stock_klines(code)
    if not klines or len(klines) < 11:
        return {'success': False, 'error': 'K线数据不足，无法计算止损建议'}

    current_idx = len(klines) - 1
    current_price = float(klines[current_idx]['close'])
    try:
        existing = float(current_stop) if current_stop not in (None, '') else None
        cost = float(buy_price) if buy_price not in (None, '') else None
    except (TypeError, ValueError):
        return {'success': False, 'error': '买入价或当前止损不是有效数字'}
    if any(value is not None and not math.isfinite(value) for value in (existing, cost)):
        return {'success': False, 'error': '买入价或当前止损不是有效数字'}
    if existing is not None and existing <= 0:
        return {'success': False, 'error': '当前止损必须大于0'}
    if cost is not None and cost <= 0:
        return {'success': False, 'error': '买入价必须大于0'}

    initial_stop = None
    raw_buy_date_text = str(buy_date or '')
    normalized_buy_date = raw_buy_date_text.replace('-', '')
    parsed_buy_date = None
    if normalized_buy_date:
        try:
            parsed_buy_date = datetime.strptime(raw_buy_date_text, '%Y-%m-%d').date()
        except ValueError:
            return {'success': False, 'error': '买入日期格式应为 YYYY-MM-DD'}
        if parsed_buy_date.isoformat() != raw_buy_date_text:
            return {'success': False, 'error': '买入日期格式应为 YYYY-MM-DD'}
        if parsed_buy_date > date.today():
            return {'success': False, 'error': '买入日期不能晚于今天'}
    buy_date_used = None
    if normalized_buy_date and cost and cost > 0:
        eligible = [i for i, k in enumerate(klines) if _kline_date(k) <= normalized_buy_date]
        if not eligible:
            return {'success': False, 'error': '买入日期早于现有K线范围'}
        buy_idx = eligible[-1]
        buy_date_used = _kline_date(klines[buy_idx])
        buy_date_used = f'{buy_date_used[:4]}-{buy_date_used[4:6]}-{buy_date_used[6:]}'
        initial_stop, _ = calc_stop_loss(
            klines, buy_idx, close_price=cost, cost_price=cost,
            buy_date=normalized_buy_date,
        )
        if initial_stop is not None:
            initial_stop = round(float(initial_stop), 2)

    protective_stop, _ = calc_stop_loss(klines, current_idx, close_price=current_price)
    if protective_stop is not None:
        protective_stop = round(float(protective_stop), 2)
        if protective_stop >= current_price:
            protective_stop = None

    if existing is not None and existing >= current_price:
        recommendation = existing
        recommendation_type = 'stop_reached'
        reason = '现价已到达或跌破手工止损，应先执行风险处置，不应继续放宽止损'
    elif existing is not None:
        if protective_stop is not None and protective_stop > existing:
            recommendation = protective_stop
            recommendation_type = 'raise_protective_stop'
            reason = '最新价格结构已抬高，建议上移保护止损；不会自动覆盖手工值'
        else:
            recommendation = existing
            recommendation_type = 'keep_current_stop'
            reason = '当前结构尚未支持上移止损，建议维持现有手工止损'
    elif initial_stop is not None:
        if initial_stop >= current_price:
            recommendation = initial_stop
            recommendation_type = 'stop_reached'
            reason = '现价已到达或跌破按建仓结构计算的初始止损，应先执行风险处置'
        elif protective_stop is not None and protective_stop > initial_stop:
            recommendation = protective_stop
            recommendation_type = 'protective_stop'
            reason = '持仓结构已较建仓时抬高，建议采用更高的当前结构保护位'
        else:
            recommendation = initial_stop
            recommendation_type = 'initial_risk_stop'
            reason = '根据买入日期、买入价及当时可见K线计算初始风险止损'
    elif protective_stop is not None:
        recommendation = protective_stop
        recommendation_type = 'structure_stop'
        reason = '缺少完整买入信息，按最新价格结构计算参考止损'
    else:
        return {'success': False, 'error': '当前数据无法形成有效止损建议'}

    return {
        'success': True,
        'stop_loss': round(float(recommendation), 2),
        'recommendation_type': recommendation_type,
        'reason': reason,
        'price': round(current_price, 2),
        'initial_stop': initial_stop,
        'buy_date_used': buy_date_used,
        'protective_stop': protective_stop,
        'current_stop': existing,
        'can_raise': recommendation_type == 'raise_protective_stop',
        'stop_loss_pct': round((float(recommendation) - current_price) / current_price * 100, 2),
    }

# ── 公共函数 ────────────────────────────────────────


def get_holdings():
    """获取持仓数据（从 MySQL DB 读取，回退 JSON）

    Returns:
      dict: {"holdings": [{code, name, direction, ratio, price, stop_loss_price, sector, ...}], "cash_ratio": float}
    """
    try:
        from backend.data_access.data_layer import get_holdings as _dl_holdings
        rows = _dl_holdings(user_id=1)
        if rows:
            holdings = []
            total_ratio = 0
            for r in rows:
                ratio = r.get('target_ratio', 0)
                total_ratio += ratio
                holdings.append({
                    'code': r.get('code', ''),
                    'name': r.get('name', ''),
                    'direction': r.get('direction', ''),
                    'ratio': ratio,
                    'buy_price': float(r['cost_price']) if r.get('cost_price') is not None else None,
                    'stop_loss_price': r.get('stop_loss_price'),
                    'sector': r.get('sector', ''),
                    'buy_date': r.get('buy_date', ''),
                })
            cash_ratio = round(max(0, 100 - total_ratio), 2)
            return {'holdings': holdings, 'cash_ratio': cash_ratio}
    except Exception:
        log.warning('get_holdings DB读取失败，回退JSON')
    # 回退：JSON
    if os.path.isfile(HOLDINGS_PATH):
        with open(HOLDINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'holdings': []}


def get_trades():
    """获取交易记录"""
    if os.path.isfile(TRADES_PATH):
        with open(TRADES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'trades': []}


def get_holdings_with_prices():
    """获取持仓数据（含实时行情 + 板块/结构/阶段分析）

    返回格式同 get_holdings()，但每个持仓额外包含:
      - price: 当前价（float | None）
      - change: 涨跌幅%（float | None）
      - stop_loss_pct: 止损跌幅%（float | None，从 stop_loss_price 和 price 计算）
      - sector: 同花顺行业板块（str）
      - structure: K线结构（str，如'上涨趋势'/'区间震荡'）
      - stage: 阶段（str，如'上行'/'加速'/'缩量整理'）
    """
    data = get_holdings()
    holdings = data.get('holdings', [])
    cash_ratio = data.get('cash_ratio', 0)

    if not holdings:
        return {'holdings': [], 'cash_ratio': cash_ratio or 100}

    # 批量获取实时行情
    codes = [h['code'] for h in holdings if h.get('code')]
    prices = {}
    if codes:
        try:
            from backend.data_access.realtime_quotes import get_realtime_quotes
            prices = {
                code: {'price': quote['price'], 'change': quote['change_pct']}
                for code, quote in get_realtime_quotes(codes).items()
            }
        except Exception:
            prices = {}

    # 叠加行情字段
    enriched = []
    # 加载自选股方向映射（方向管理优先于holdings.json的静态方向）
    wl_dirs = {}
    try:
        from backend.services.watchlist_service import get_watchlist
        wl = get_watchlist()
        for s in wl.get('stocks', []):
            if s.get('direction'):
                wl_dirs[s['code']] = s['direction']
    except Exception:
        log.warning('holdings: silent skip')
        pass
    # 板块/结构/阶段 — 通过 StockCardService 统一获取（缓存+并行加速）
    card_results = _get_cached_cards(codes)
    uncached = [c for c in codes if c not in card_results]
    if uncached:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from backend.services.stock_card_service import get_stock_card
            date_str = datetime.now().strftime('%Y%m%d')
            card_futures = {}
            with ThreadPoolExecutor(max_workers=10) as executor:
                for code in uncached:
                    fut = executor.submit(get_stock_card, code=code, date_str=date_str)
                    card_futures[fut] = code
                for fut in as_completed(card_futures):
                    code = card_futures[fut]
                    try:
                        card_results[code] = fut.result()
                    except Exception:
                        card_results[code] = {}
            _set_cached_cards(card_results)
        except Exception:
            pass

    for h in holdings:
        item = dict(h)
        code = h.get('code', '')
        price_info = prices.get(code, {})
        item['price'] = price_info.get('price')  # 实时行情价
        item['change'] = price_info.get('change')
        # 保留买入价格（cost_price）不覆盖
        if 'buy_price' not in item or item['buy_price'] is None:
            item['buy_price'] = None

        # 计算止损跌幅（用实时价）
        stop_price = h.get('stop_loss_price')
        current_price = item['price']
        if stop_price is not None and current_price is not None and current_price > 0:
            item['stop_loss_pct'] = round((stop_price - current_price) / current_price * 100, 2)
        else:
            item['stop_loss_pct'] = None

        # 方向：方向管理优先于holdings.json静态数据
        if code in wl_dirs:
            item['direction'] = wl_dirs[code]

        # 板块/结构/阶段 — 从并行计算的结果中取
        card = card_results.get(code, {})
        item['sector'] = card.get('sector', '') or ''
        item['structure'] = card.get('structure', '--')
        item['stage'] = card.get('stage', '--')
        item['signal'] = card.get('signal', '--')
        item['buy_point'] = card.get('buy_point', '')
        item['fusion_type'] = card.get('fusion_type', '')
        item['fusion_reason'] = card.get('fusion_reason', '')
        item['triggered_signals'] = card.get('triggered_signals', [])
        item['wave_position'] = card.get('wave_position', '')

        enriched.append(item)

    return {'holdings': enriched, 'cash_ratio': cash_ratio, 'update_date': data.get('update_date')}


def save_holdings(data):
    """保存持仓数据

    参数:
      data: dict，包含 holdings（list）和 cash_ratio（number）
    返回:
      dict: {"success": bool, "count": int, "error": str?}
    """
    # ── 校验 ──
    holdings = data.get('holdings', [])
    if not isinstance(holdings, list):
        return {'success': False, 'error': 'holdings 必须为列表'}

    for idx, holding in enumerate(holdings, start=1):
        if not isinstance(holding, dict):
            return {'success': False, 'error': f'第 {idx} 条持仓格式无效'}
        for field, label in (
            ('buy_price', '买入价'),
            ('stop_loss_price', '止损价'),
        ):
            raw = holding.get(field)
            if raw in (None, ''):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return {'success': False, 'error': f'第 {idx} 条持仓的{label}不是有效数字'}
            if not math.isfinite(value) or value <= 0:
                return {'success': False, 'error': f'第 {idx} 条持仓的{label}必须为大于0的有限数字'}

        raw_buy_date = holding.get('buy_date')
        if raw_buy_date not in (None, ''):
            try:
                raw_buy_date_text = str(raw_buy_date)
                parsed = datetime.strptime(raw_buy_date_text, '%Y-%m-%d').date()
            except ValueError:
                return {'success': False, 'error': f'第 {idx} 条持仓的买入日期格式应为 YYYY-MM-DD'}
            if parsed.isoformat() != raw_buy_date_text:
                return {'success': False, 'error': f'第 {idx} 条持仓的买入日期格式应为 YYYY-MM-DD'}
            if parsed > date.today():
                return {'success': False, 'error': f'第 {idx} 条持仓的买入日期不能晚于今天'}

    cash_ratio = data.get('cash_ratio', 100)
    if not isinstance(cash_ratio, (int, float)):
        return {'success': False, 'error': 'cash_ratio 必须为数字'}
    if cash_ratio < 0 or cash_ratio > 100:
        return {'success': False, 'error': f'cash_ratio 超出范围 (0-100): {cash_ratio}'}

    # ── 写入 MySQL DB ──
    try:
        from backend.data_access.data_layer import save_holdings as _dl_save
        _db_list = []
        for h in holdings:
            _db_list.append({
                'code': h.get('code', ''),
                'name': h.get('name', ''),
                'direction': h.get('direction', ''),
                'target_ratio': h.get('ratio', 0),
                # buy_price 优先，回退 price（前端旧格式）
                'cost_price': h.get('buy_price') or h.get('price') or None,
                'stop_loss_price': h.get('stop_loss_price') or None,
                'sector': h.get('sector', ''),
                'buy_date': h.get('buy_date') or None,
            })
        _dl_save(1, _db_list)
    except Exception as e:
        log.error('holdings DB save failed: %s', e)
        return {'success': False, 'error': f'DB写入失败: {e}'}

    # 同步方向到自选股（方向管理是权威源，但持仓编辑也需同步）
    try:
        from backend.services.watchlist_service import get_watchlist, save_watchlist
        wl = get_watchlist()
        changed = False
        for h in holdings:
            code = h.get('code', '')
            dir_val = h.get('direction', '')
            if code and dir_val:
                for s in wl.get('stocks', []):
                    if s['code'] == code and s.get('direction') != dir_val:
                        s['direction'] = dir_val
                        changed = True
                        break
        if changed:
            save_watchlist({'stocks': wl['stocks'], 'count': len(wl['stocks'])})
    except Exception:
        log.warning('holdings: silent skip')
        pass

    return {'success': True, 'count': len(holdings)}

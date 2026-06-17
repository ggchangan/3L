"""
持仓/交易服务 — 持仓、交易数据读写
"""
import json, os, requests, tempfile
from backend.core.logger import get_logger
log = get_logger(__name__)
from datetime import datetime
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

# ── 腾讯行情接口格式 ────────────────────────────────────
# 请求: http://qt.gtimg.cn/q=sh603259,sz301200
# 返回: v_pvixnGq="51.200","2.300",... 多行
# 价格在第1个字段，涨跌幅在第2个字段
_TENCENT_URL = 'http://qt.gtimg.cn/q='
# 市场前缀映射（6位代码判断）
_SH_PREFIXES = ('600', '601', '603', '605', '688', '689', '510', '511', '512',
                '513', '515', '516', '517', '518', '560', '561', '562', '563',
                '565', '567', '580', '588')
_SZ_PREFIXES = ('000', '001', '002', '003', '004', '159', '161', '162', '163',
                '164', '165', '166', '168', '180', '200', '201', '202', '203',
                '204', '300', '301')


def _market_prefix(code):
    """根据6位代码返回腾讯行情市场前缀"""
    for p in _SH_PREFIXES:
        if code.startswith(p):
            return 'sh'
    for p in _SZ_PREFIXES:
        if code.startswith(p):
            return 'sz'
    return 'sz'  # 默认


def _build_tencent_codes(codes):
    """构建腾讯接口的代码列表"""
    return ','.join(f'{_market_prefix(c)}{c}' for c in codes)


import re as _re


def _parse_tencent_response(text):
    """解析腾讯行情返回的文本

    实际格式: v_CODE="1~name~code~price~yclose~open~vol~..."
    （~ 分隔，非 "," 分隔）
    price 在第4个字段(index 3)，涨跌幅在 倒数第2个字段
    """
    results = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or '=' not in line:
            continue
        try:
            value_part = line.split('=', 1)[1].strip()
            # 去掉外层引号
            if value_part.startswith('"') and value_part.endswith('"'):
                value_part = value_part[1:-1]
            # 按 ~ 分割
            fields = value_part.split('~')
            if len(fields) < 5:
                continue

            price = float(fields[3]) if fields[3] else 0

            # 涨跌幅在 fields[32]（涨跌额在 fields[31]）
            change = 0.0
            if len(fields) > 32:
                try:
                    change = float(fields[32])
                except (ValueError, IndexError):
                    change = 0.0

            # 代码在 fields[2]
            code = fields[2] if len(fields) > 2 else ''
            results[code] = {'price': price, 'change': change}
        except (ValueError, IndexError, AttributeError):
            continue
    return results


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
            url = _TENCENT_URL + _build_tencent_codes(codes)
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            prices = _parse_tencent_response(resp.text)
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

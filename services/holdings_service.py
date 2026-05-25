"""
持仓/交易服务 — 持仓、交易数据读写
"""
import json, os, requests, tempfile
from datetime import datetime
from config import HOLDINGS_PATH, TRADES_PATH

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

            # 涨跌幅在 fields[31]
            change = 0.0
            if len(fields) > 31:
                try:
                    change = float(fields[31])
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
    """获取持仓数据（原始）"""
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
    for h in holdings:
        item = dict(h)
        code = h.get('code', '')
        price_info = prices.get(code, {})
        item['price'] = price_info.get('price')
        item['change'] = price_info.get('change')

        # 计算止损跌幅
        stop_price = h.get('stop_loss_price')
        current_price = item['price']
        if stop_price is not None and current_price is not None and current_price > 0:
            item['stop_loss_pct'] = round((stop_price - current_price) / current_price * 100, 2)
        else:
            item['stop_loss_pct'] = None

        # 板块（从行业分类映射读取）
        item['sector'] = ''
        try:
            from backend.core.data_layer import get_industry_map
            imap = get_industry_map()
            ind_info = imap.get(code, {})
            if isinstance(ind_info, dict):
                item['sector'] = ind_info.get('ths_industry', '') or ''
        except Exception:
            item['sector'] = ''

        # 结构/阶段（从K线数据分析）
        item['structure'] = '--'
        item['stage'] = '--'
        try:
            from backend.core.data_layer import get_all_stocks, get_stock_klines
            from backend.core.ema_utils import get_structure, get_stage
            stocks = get_all_stocks()
            kls = get_stock_klines(code, stocks=stocks)
            if kls and len(kls) >= 20:
                closes = [k['close'] for k in kls]
                highs_ = [k['high'] for k in kls]
                lows_ = [k['low'] for k in kls]
                vols = [k.get('volume', k.get('vol', 0)) for k in kls]
                item['structure'] = get_structure(closes)
                item['stage'] = get_stage(closes, item['structure'], highs_, lows_, volumes=vols)
        except Exception:
            item['structure'] = '--'
            item['stage'] = '--'

        enriched.append(item)

    return {'holdings': enriched, 'cash_ratio': cash_ratio}


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

    # ── 防误覆盖 ──
    if os.path.isfile(HOLDINGS_PATH):
        try:
            with open(HOLDINGS_PATH, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            existing_count = len(existing.get('holdings', []))
            if existing_count >= 50 and len(holdings) <= 10:
                return {
                    'success': False,
                    'error': f'拒绝写入：已有{existing_count}只但仅写入{len(holdings)}只（防误覆盖）'
                }
        except (json.JSONDecodeError, IOError):
            pass  # 文件损坏，允许写入

    # ── 写入 ──
    today = datetime.now().strftime('%Y-%m-%d')
    output = {
        'update_date': today,
        'holdings': holdings,
        'cash_ratio': cash_ratio
    }

    # 原子写入
    dir_path = os.path.dirname(HOLDINGS_PATH)
    if dir_path and not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path or os.path.dirname(dir_path) or '.',
                                    suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HOLDINGS_PATH)
    except Exception as e:
        if os.path.isfile(tmp_path):
            os.unlink(tmp_path)
        return {'success': False, 'error': f'写入失败: {e}'}

    return {'success': True, 'count': len(holdings)}

"""统一实时行情入口。

历史确认数据仍由 Tushare/MySQL 数据层提供；本模块只负责盘中尚未确认的
实时行情。业务代码不应直接依赖腾讯、mootdx 等供应商接口。
"""

from __future__ import annotations

import os
import re
from typing import Iterable

import requests

from backend.core.logger import get_logger


log = get_logger(__name__)

DEFAULT_PROVIDERS = tuple(
    p.strip().lower()
    for p in os.getenv('REALTIME_QUOTE_PROVIDERS', 'tencent,mootdx').split(',')
    if p.strip()
)
_TENCENT_URL = 'https://qt.gtimg.cn/q='
_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'}


def normalize_symbol(code: str) -> str:
    """转为供应商无关的行情代码，如 ``sh600000``、``sz399006``。"""
    value = str(code or '').strip()
    lower = value.lower()
    if lower.startswith(('sh', 'sz', 'us.')):
        return lower
    local = re.sub(r'\.(sh|sz)$', '', lower)
    if local.startswith(('5', '6', '9')):
        return f'sh{local}'
    return f'sz{local}'


def local_code(symbol: str) -> str:
    value = normalize_symbol(symbol)
    return value[2:] if value.startswith(('sh', 'sz')) else value


def _number(fields, index, default=0.0):
    try:
        return float(fields[index]) if fields[index] else default
    except (IndexError, TypeError, ValueError):
        return default


def _parse_tencent(text: str) -> dict[str, dict]:
    quotes = {}
    for line in re.split(r';\s*|\n+', text.strip()):
        if '="' not in line:
            continue
        key, value = line.split('=', 1)
        fields = value.strip().strip('";').split('~')
        if len(fields) < 6:
            continue
        symbol = key.strip().removeprefix('v_').lower()
        price = _number(fields, 3)
        prev_close = _number(fields, 4, price)
        if not price:
            continue
        amount_yuan = 0.0
        if len(fields) > 35 and '/' in fields[35]:
            amount_parts = fields[35].split('/')
            if len(amount_parts) >= 3:
                try:
                    amount_yuan = float(amount_parts[2])
                except ValueError:
                    pass
        quotes[symbol] = {
            'symbol': symbol,
            'code': fields[2] if len(fields) > 2 and fields[2] else local_code(symbol),
            'name': fields[1] if len(fields) > 1 else '',
            'price': price,
            'close': price,
            'prev_close': prev_close,
            'open': _number(fields, 5),
            'high': _number(fields, 33, _number(fields, 8)),
            'low': _number(fields, 34, _number(fields, 9)),
            'volume': int(_number(fields, 6)),
            'amount': _number(fields, 37),
            'amount_yuan': amount_yuan,
            'turnover_rate': _number(fields, 38),
            'change': round(price - prev_close, 4),
            'change_pct': _number(
                fields, 32,
                round((price / prev_close - 1) * 100, 4) if prev_close else 0,
            ),
            'time': fields[30] if len(fields) > 30 else '',
            'source': 'tencent',
            'realtime': True,
        }
    return quotes


def _fetch_tencent(symbols: list[str], timeout: int = 5) -> dict[str, dict]:
    parsed = {}
    for offset in range(0, len(symbols), 100):
        response = requests.get(
            _TENCENT_URL + ','.join(symbols[offset:offset + 100]),
            headers=_HEADERS,
            timeout=timeout,
        )
        response.encoding = 'gbk'
        parsed.update(_parse_tencent(response.text))
    # 腾讯对海外代码的响应变量名会去掉点号（us.INX -> v_usINX）。
    canonical = {re.sub(r'[^a-z0-9]', '', key): value for key, value in parsed.items()}
    result = {}
    for symbol in symbols:
        quote = parsed.get(symbol) or canonical.get(re.sub(r'[^a-z0-9]', '', symbol))
        if quote:
            quote = dict(quote)
            quote['symbol'] = symbol
            result[symbol] = quote
    return result


def _fetch_mootdx(symbols: list[str]) -> dict[str, dict]:
    """mootdx 降级适配器；只用于当前支持较稳定的 A 股指数。"""
    try:
        from mootdx.quotes import Quotes
    except ImportError:
        return {}

    result = {}
    client = Quotes.factory(method='remote')
    for symbol in symbols:
        code = local_code(symbol)
        if not code.startswith(('000', '399')):
            continue
        try:
            frame = client.bars(symbol=code, frequency=9, start=0, count=2)
            if frame is None or len(frame) < 2:
                continue
            previous, current = frame.iloc[-2], frame.iloc[-1]
            price = float(current['close'])
            prev_close = float(previous['close'])
            if price <= 0:
                continue
            result[symbol] = {
                'symbol': symbol,
                'code': code,
                'name': '',
                'price': price,
                'close': price,
                'prev_close': prev_close,
                'open': float(current.get('open', 0)),
                'high': float(current.get('high', 0)),
                'low': float(current.get('low', 0)),
                'volume': int(float(current.get('vol', 0))),
                'amount': float(current.get('amount', 0)),
                'change': round(price - prev_close, 4),
                'change_pct': round((price / prev_close - 1) * 100, 4) if prev_close else 0,
                'time': str(current.get('datetime', current.get('date', ''))),
                'source': 'mootdx',
                'realtime': True,
            }
        except Exception as exc:
            log.debug('mootdx实时行情失败(%s): %s', symbol, exc)
    return result


def get_realtime_quotes(
    codes: Iterable[str], providers: Iterable[str] | None = None, timeout: int = 5,
) -> dict[str, dict]:
    """批量获取实时行情，返回以原始输入代码为键的标准行情字典。

    按配置的供应商顺序逐级补齐缺失代码。当前 Tushare 的日线接口不是盘中
    实时源，因此不在此处伪装成实时数据；未来若配置可用实时权限，可新增
    Tushare provider 而无需修改业务层。
    """
    originals = [str(code) for code in codes if str(code or '').strip()]
    symbol_map = {original: normalize_symbol(original) for original in originals}
    pending = set(symbol_map.values())
    by_symbol = {}

    for provider in tuple(providers or DEFAULT_PROVIDERS):
        if not pending:
            break
        try:
            if provider == 'tencent':
                fetched = _fetch_tencent(sorted(pending), timeout=timeout)
            elif provider == 'mootdx':
                fetched = _fetch_mootdx(sorted(pending))
            else:
                log.warning('未知实时行情供应商: %s', provider)
                continue
            by_symbol.update(fetched)
            pending.difference_update(fetched)
        except Exception as exc:
            log.warning('%s实时行情批量获取失败: %s', provider, exc)

    return {
        original: by_symbol[symbol]
        for original, symbol in symbol_map.items()
        if symbol in by_symbol
    }


def get_realtime_quote(
    code: str, providers: Iterable[str] | None = None, timeout: int = 5,
) -> dict | None:
    """获取单个标准实时行情；所有业务模块统一使用此入口。"""
    return get_realtime_quotes([code], providers=providers, timeout=timeout).get(str(code))


def get_intraday_minutes(code: str, provider: str = 'tencent', timeout: int = 10) -> list[dict]:
    """获取当日分钟数据的标准列表。

    当前只有腾讯适配器。返回字段为 time、price、volume、amount、source；
    供应商细节仅保留在本数据访问模块内。
    """
    if provider != 'tencent':
        log.warning('供应商%s暂不支持分钟行情', provider)
        return []
    symbol = normalize_symbol(code)
    try:
        response = requests.get(
            f'https://ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}',
            headers=_HEADERS,
            timeout=timeout,
        )
        rows = response.json().get('data', {}).get(symbol, {}).get('data', {}).get('data', [])
        result = []
        for row in rows:
            fields = row.split()
            if len(fields) < 4:
                continue
            raw_time = fields[0]
            result.append({
                'time': f'{raw_time[:2]}:{raw_time[2:]}',
                'price': float(fields[1]),
                'volume': float(fields[2]),
                'amount': float(fields[3]),
                'source': 'tencent',
                'realtime': True,
            })
        return result
    except Exception as exc:
        log.warning('分钟行情获取失败(%s): %s', symbol, exc)
        return []

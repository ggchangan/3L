"""价格复权的纯函数，统一数据库访问层的计算口径。"""
import math


def qfq_ratio(adj_factor, base_adj_factor):
    """返回 Tushare 前复权比例；因子无效时返回 None，禁止混用原价。"""
    try:
        factor = float(adj_factor)
        base = float(base_adj_factor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(factor) or not math.isfinite(base) or factor <= 0 or base <= 0:
        return None
    return factor / base

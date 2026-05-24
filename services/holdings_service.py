"""
持仓/交易服务 — 持仓、交易数据读取
"""
import json, os
from config import HOLDINGS_PATH, TRADES_PATH


def get_holdings():
    """获取持仓数据"""
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

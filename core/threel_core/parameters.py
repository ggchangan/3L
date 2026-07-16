"""3L 交易参数注册表。

修改参数时必须升级 PARAMETER_VERSION，并同步知识来源与回测依据。
"""

PARAMETER_VERSION = '3l-2026.07.1'

TREND_PARAMETERS = {
    'ema5_slope_min': 2.0,
    'ema10_slope_min': 1.5,
    'bias5_buy_max': 2.0,
    'bias5_hold_max': 8.0,
    'bias5_warning_max': 12.0,
    'bias10_buy_max': 3.0,
    'bias10_hold_max': 10.0,
    'bias10_warning_max': 15.0,
    'hard_stop_loss_pct': 5.0,
    'trailing_profit_activation_pct': 5.0,
    'trailing_drawdown_pct': 10.0,
}

PARAMETER_MANIFEST = {
    'version': PARAMETER_VERSION,
    'strategy': '3L 趋势交易参数',
    'provenance_note': '知识库提供趋势、量价和风控原则；具体数值是工程参数，必须通过同口径回测校准，不宣称为原文阈值。',
    'parameters': TREND_PARAMETERS,
    'knowledge_sources': [
        {
            'title': '3L交易体系构建（全文）',
            'path': 'knowledge_base/trading_system/3L交易体系构建_全文.md',
            'url': 'http://43.136.177.133:8080/pub/kb/trading_system/3L交易体系构建_全文.md',
        },
        {
            'title': '量价原理（全文）',
            'path': 'knowledge_base/liangjia_yuanli/量价原理_全文.md',
            'url': 'http://43.136.177.133:8080/pub/kb/liangjia_yuanli/量价原理_全文.md',
        },
    ],
    'backtest_basis': {
        'runner': 'server/backend/services/backtest_service.py::run_backtest',
        'sample_window_days': 60,
        'metrics': [
            'total', 'win_rate', 'avg_win', 'avg_loss', 'cumulative_return',
        ],
        'reproducibility': '参数版本随回测结果返回；比较不同版本时必须保持股票池、日期区间一致。',
        'result_snapshot': None,
        'status': 'runner_bound_snapshot_pending',
    },
}


def get_parameter_manifest():
    """返回副本，防止调用方意外修改全局参数。"""
    import copy
    return copy.deepcopy(PARAMETER_MANIFEST)

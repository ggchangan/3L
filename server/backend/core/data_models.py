"""
数据层数据模型定义 — data_layer 对外合约

所有业务代码通过 data_layer 读取数据，返回以下定义的格式。
如果数据源（data_source）变化，只改 data_source.py，不改 data_models 和 data_layer。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta


# ════════════════════════════════════════════════════════════
# 基础类型
# ════════════════════════════════════════════════════════════


@dataclass
class Kline:
    """单根日K线 — 用于板块K线图和波谷判定"""
    date: str          # YYYYMMDD
    open: float        # 开盘价
    close: float       # 收盘价
    high: float        # 最高价
    low: float         # 最低价
    volume: int        # 成交量（股）


@dataclass
class ThsIndustrySnapshot:
    """行业板块当日涨跌幅快照 — 来自同花顺 stock_board_industry_summary_ths

    业务层使用字段（review_compute_service.get_mainline_data 等）：
    - change_pct (必填): 涨跌幅%
    - up_count / down_count: 上涨/下跌家数
    - leader / leader_chg: 领涨股
    - net_flow: 净流入
    """
    date: str                          # YYYYMMDD，数据日期
    change_pct: float                  # 涨跌幅%
    up_count: Optional[int] = None     # 上涨家数（同花顺特有）
    down_count: Optional[int] = None   # 下跌家数（同花顺特有）
    leader: Optional[str] = None       # 领涨股名称（同花顺特有）
    leader_chg: Optional[float] = None # 领涨股涨跌幅%（同花顺特有）
    net_flow: Optional[float] = None   # 净流入（亿元，同花顺特有）
    volume: Optional[float] = None     # 总成交量（万手，同花顺特有）
    amount: Optional[float] = None     # 总成交额（亿元，同花顺特有）


@dataclass
class Push2TestConceptSnapshot:
    """概念板块当日涨跌幅快照 — 来自 push2test

    概念数据目前只能从 push2test 获取（同花顺无批量概念接口）。
    字段比行业少（无上涨家数/领涨股）。
    """
    date: str          # YYYYMMDD
    change_pct: float  # 涨跌幅%
    close: float       # 收盘价
    open_: float       # 开盘价
    high: float        # 最高价
    low: float         # 最低价
    volume: int        # 成交量
    prev_close: float  # 昨收


# ════════════════════════════════════════════════════════════
# data_layer 对外合约 — 各函数的返回值格式
# ════════════════════════════════════════════════════════════


@dataclass
class SectorKlineData:
    """get_sector_daily() 的返回值格式
    
    Returns: {last_updated, industries: {name: [Kline]}, concepts: {name: [Kline]}}
    """
    last_updated: str                                          # YYYYMMDD
    industries: Dict[str, List[Kline]] = field(default_factory=dict)
    concepts: Dict[str, List[Kline]] = field(default_factory=dict)


@dataclass
class SectorPush2Test:
    """get_sector_push2test() 的返回值格式

    行业数据来自同花顺 THS，概念数据来自 push2test。
    Returns: {industries: {name: ThsIndustrySnapshot}, concepts: {name: Push2TestConceptSnapshot}}
    """
    industries: Dict[str, ThsIndustrySnapshot] = field(default_factory=dict)
    concepts: Dict[str, Push2TestConceptSnapshot] = field(default_factory=dict)

    def get_change_pct(self, name: str, default: Optional[float] = None) -> Optional[float]:
        """获取指定板块的当日涨跌幅"""
        ind = self.industries.get(name)
        if ind is not None and ind.change_pct is not None:
            return float(ind.change_pct)
        con = self.concepts.get(name)
        if con is not None:
            return float(con.change_pct)
        return default


# ════════════════════════════════════════════════════════════
# 数据模型（旧格式兼容 — 已由 ThsIndustrySnapshot 替代）
# ════════════════════════════════════════════════════════════

# ChangePctSnapshot 保留但使用 ThsIndustrySnapshot / Push2TestConceptSnapshot 替代


# ════════════════════════════════════════════════════════════
# 行业主线排行（get_mainline_data 返回的每条 line）
# ════════════════════════════════════════════════════════════

@dataclass
class SectorRankingItem:
    """主线排行单条记录"""
    name: str
    chg_1d: float
    chg_20d: float
    stage: str
    vl_score: float
    volume_ratio: float
    is_mainline: bool = False
    is_secondary: bool = False
    opportunity: str = ''


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def _last_trading_day() -> str:
    """返回最后一个交易日 YYYYMMDD（周末回退到周五，不计节假日）"""
    d = datetime.now()
    for _ in range(7):
        if d.weekday() < 5:
            return d.strftime('%Y%m%d')
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')


def is_trading_day(date_str: str) -> bool:
    '''判断给定日期是否为A股交易日

    支持 YYYYMMDD 或 YYYY-MM-DD 格式。
    含 fallback：先按周末判断，后续可扩展交易日历。
    '''
    if not date_str:
        return False
    try:
        s = date_str.strip().replace('-', '')
        dt = datetime.strptime(s[:8], '%Y%m%d')
        return dt.weekday() < 5
    except (ValueError, IndexError):
        return False


def dict_to_kline(d: dict) -> Kline:
    """dict → Kline"""
    return Kline(
        date=str(d.get('date', '')),
        open=float(d.get('open', 0)),
        close=float(d.get('close', 0)),
        high=float(d.get('high', 0)),
        low=float(d.get('low', 0)),
        volume=int(float(d.get('volume', 0) or 0)),
    )


def ths_dict_to_snapshot(d: dict) -> ThsIndustrySnapshot:
    """THS数据dict → ThsIndustrySnapshot"""
    return ThsIndustrySnapshot(
        date=str(d.get('date', '')),
        change_pct=float(d.get('change_pct', 0)),
        up_count=int(d['up_count']) if d.get('up_count') is not None else None,
        down_count=int(d['down_count']) if d.get('down_count') is not None else None,
        leader=str(d.get('leader', '') or ''),
        leader_chg=round(float(d['leader_chg']), 2) if d.get('leader_chg') is not None else None,
        net_flow=float(d['net_flow']) if d.get('net_flow') is not None else None,
        volume=float(d['volume']) if d.get('volume') is not None else None,
        amount=float(d['amount']) if d.get('amount') is not None else None,
    )


def push2test_dict_to_snapshot(d: dict) -> Push2TestConceptSnapshot:
    """push2test概念dict → Push2TestConceptSnapshot"""
    return Push2TestConceptSnapshot(
        date=str(d.get('date', '')),
        change_pct=float(d.get('change_pct', 0)),
        close=float(d.get('close', 0)),
        open_=float(d.get('open', 0)),
        high=float(d.get('high', 0)),
        low=float(d.get('low', 0)),
        volume=int(float(d.get('volume', 0) or 0)),
        prev_close=float(d.get('prev_close', 0)),
    )


# ════════════════════════════════════════════════════════════
# 个股卡片合约
# ════════════════════════════════════════════════════════════


@dataclass
class StockCardData:
    """个股卡片统一数据合约 — get_stock_card() 输出

    所有个股展示数据唯一来源。外部代码只读取不做推导。
    新增字段必须同步更新 get_stock_card()、_empty_card()、前端 BuySignalItem 类型。
    """
    # ── 基础字段 ──
    code: str                    # 6位股票代码
    name: str                    # 股票名称
    sector: str                  # 所属行业/板块
    direction: str               # 方向（大类.子类）
    price: float                 # 当前价格
    change: float                # 当日涨跌幅%
    date: str                    # 数据日期 YYYYMMDD

    # ── 技术分析 ──
    structure: str               # '上涨趋势'/'区间震荡'/'下降趋势'
    stage: str                   # '上行'/'加速'/'缩量整理'/...
    ema: str                     # EMA排列状态
    ema5: Optional[float]        # EMA5值
    ema10: Optional[float]       # EMA10值
    ema20: Optional[float]       # EMA20值
    ema30: Optional[float]       # EMA30值
    deviation_pct: float         # 偏离率%
    vol_ratio: float             # 量比
    vol_analysis: str            # 量能分析

    # ── 信号和融合判定 ──
    signal: str                  # 原始信号 'buy'/'hold'/'sell'
    signal_text: str             # 信号文字
    buy_point: str               # 买点类型
    profit_model1: bool          # 是否盈利模式1
    trend_stock: bool            # 是否趋势交易股
    trading_system: str          # '3l'/'trend'
    trading_reason: str          # 系统选择理由
    trend_buy_type: str          # 趋势买点类型
    trend_bias: str              # 趋势BIAS偏离率
    mainline_level: str          # 主线定位
    score: int                   # 综合评分
    flags: str                   # 标记
    triggered_signals: list      # 触发的关键信号
    fusion_type: str             # 融合判定类型
    fusion_reason: str           # 融合理由
    wave_position: str           # 波峰波谷位置

    # ── 操作建议（由卡片内部推导，外部不重复计算）──
    action_type: str             # 操作类型 '买入'/'卖出'/'持有'/'加仓'/'减仓'/'换股'
    action_signal: str           # 操作子标签（如 '强势买入·缩量回踩(85)'）
    action_priority: str         # 优先级 '高'/'中'/'低'
    action_reason: str           # 操作理由

    # ── 其他 ──
    stop_loss: Optional[float]   # 止损价
    stop_loss_pct: Optional[float]  # 止损百分比
    sector_chg: Optional[float]  # 板块今日涨幅
    sector_chg_5d: Optional[float]  # 板块5日涨幅
    vs_sector_5d: Optional[float]   # 个股vs板块5日对比
    conclusion: str              # 结论文字
    tags: list                   # 标签列表

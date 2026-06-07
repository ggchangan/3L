"""
数据层数据模型定义 — 所有原始数据文件的结构定义

用途：
  1. 类型安全：读写文件时自动校验字段类型
  2. 文档即代码：字段定义和文档同步
  3. 验证基础：L1 验证直接用模型校验数据正确性
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta


# ════════════════════════════════════════════════════════════
# 基础类型
# ════════════════════════════════════════════════════════════


@dataclass
class Kline:
    """单根日K线"""
    date: str          # YYYYMMDD
    open: float        # 开盘价
    close: float       # 收盘价
    high: float        # 最高价
    low: float         # 最低价
    volume: int        # 成交量


@dataclass
class ChangePctSnapshot:
    """当日涨跌幅快照（来自 push2test f3，不从K线算）"""
    date: str
    change_pct: float
    close: float
    open: float
    high: float
    low: float
    volume: int
    prev_close: float


# ════════════════════════════════════════════════════════════
# 模型1：板块日K线（主力文件）
# ════════════════════════════════════════════════════════════


@dataclass
class SectorDailyPush2Test:
    """_push2test 字段 — push2test 当日快照"""
    industries: Dict[str, ChangePctSnapshot] = field(default_factory=dict)
    concepts: Dict[str, ChangePctSnapshot] = field(default_factory=dict)


@dataclass
class SectorDailyFile:
    """sector_daily.json 主文件结构"""
    last_updated: str                                          # YYYYMMDD
    industries: Dict[str, List[Kline]] = field(default_factory=dict)
    concepts: Dict[str, List[Kline]] = field(default_factory=dict)
    _push2test: Optional[SectorDailyPush2Test] = None
    _push2test_updated: Optional[str] = None                   # YYYYMMDD

    def get_chg_1d(self, name: str) -> Optional[float]:
        """获取最新 chg_1d：优先 _push2test，次选K线计算"""
        if self._push2test:
            ind = self._push2test.industries.get(name)
            if ind and ind.change_pct is not None:
                return float(ind.change_pct)
        klines = self.industries.get(name, [])
        if len(klines) >= 2:
            return (klines[-1].close / klines[-2].close - 1) * 100
        return None

    def get_chg_20d(self, name: str) -> Optional[float]:
        """获取 chg_20d：从K线计算"""
        klines = self.industries.get(name, [])
        if len(klines) >= 20:
            return (klines[-1].close / klines[-20].close - 1) * 100
        return None


# ════════════════════════════════════════════════════════════
# 模型2：EM仓板指快照
# ════════════════════════════════════════════════════════════


@dataclass
class EMSectorFile:
    """sources/em/sector_daily.json — EM仓板指快照"""
    last_updated: str                                          # YYYYMMDD
    industries: Dict[str, ChangePctSnapshot] = field(default_factory=dict)
    concepts: Dict[str, ChangePctSnapshot] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════
# 模型3：THS仓板指历史K线
# ════════════════════════════════════════════════════════════


@dataclass
class THSSectorFile:
    """sources/ths/sector_daily.json — THS仓历史块照"""
    last_updated: str
    industries: Dict[str, List[Kline]] = field(default_factory=dict)
    concepts: Dict[str, List[Kline]] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════
# 模型4：个股→行业映射
# ════════════════════════════════════════════════════════════


@dataclass
class StockIndustry:
    code: str          # 股票代码
    name: str          # 股票名称
    ths_industry: str  # 申万二级行业名


# 存储格式：Dict[str, StockIndustry] keyed by stock code


# ════════════════════════════════════════════════════════════
# 模型5：个股→概念映射
# ════════════════════════════════════════════════════════════


@dataclass
class StockConcept:
    code: str                   # 股票代码
    name: str                   # 股票名称
    concept_codes: List[str]    # 概念板块代码列表
    concept_names: List[str]    # 概念板块名称列表


# 存储格式：Dict[str, StockConcept] keyed by stock code


# ════════════════════════════════════════════════════════════
# 模型6：指数K线
# ════════════════════════════════════════════════════════════


@dataclass
class IndexKlineData:
    """index_sh_data.json — 指数K线"""
    last_updated: str
    indices: Dict[str, List[Kline]] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════
# 模型7：全量A股代码表
# ════════════════════════════════════════════════════════════


# 存储格式：Dict[str, str] — code→name 映射


# ════════════════════════════════════════════════════════════
# 推送数据模型（API 返回给前端）
# ════════════════════════════════════════════════════════════


@dataclass
class SectorRankingItem:
    """get_sector_rankings 返回的单个行业排行"""
    name: str
    chg_1d: float
    chg_20d: float
    stage: str
    vl_score: float
    volume_ratio: float
    is_mainline: bool = False
    is_secondary: bool = False
    opportunity: str = ''


@dataclass
class MainlineResult:
    """get_mainline_data 返回的主线数据"""
    date: str
    lines: List[SectorRankingItem]
    secondary: List[SectorRankingItem]
    industries: dict
    all_ranked: List[SectorRankingItem]
    persistence: dict


# ════════════════════════════════════════════════════════════
# 验证结果模型
# ════════════════════════════════════════════════════════════


@dataclass
class VerifyCheck:
    check: str
    passed: bool
    detail: str
    tier: int = 1  # 1=critical, 2=important, 3=info


@dataclass
class VerifyReport:
    date: str
    last_trade_day: str
    layers: Dict[str, dict]
    checks: List[VerifyCheck]
    status: str  # pass / degraded / fail


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


def dict_to_kline(d: dict) -> Kline:
    """dict → Kline（兼容文件读取）"""
    return Kline(
        date=str(d.get('date', '')),
        open=float(d.get('open', 0)),
        close=float(d.get('close', 0)),
        high=float(d.get('high', 0)),
        low=float(d.get('low', 0)),
        volume=int(float(d.get('volume', 0) or 0)),
    )


def dict_to_chg_snapshot(d: dict) -> ChangePctSnapshot:
    """dict → ChangePctSnapshot"""
    return ChangePctSnapshot(
        date=str(d.get('date', '')),
        change_pct=float(d.get('change_pct', 0)),
        close=float(d.get('close', 0)),
        open=float(d.get('open', 0)),
        high=float(d.get('high', 0)),
        low=float(d.get('low', 0)),
        volume=int(float(d.get('volume', 0) or 0)),
        prev_close=float(d.get('prev_close', 0)),
    )

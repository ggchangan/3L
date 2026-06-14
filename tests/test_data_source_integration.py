"""数据源集成验证测试 — L1~L3 全链路验证

覆盖之前手工跑的所有临时验证脚本：
- L1: THS行业数据源 / push2test概念数据源
- L2: sector_daily.json / get_sector_rankings / data_source.py
- L3: get_mainline_data 主线计算

运行: python3 -m pytest tests/test_data_source_integration.py -v

注意: L1测试需要网络（akshare/requests），无网络时自动跳过
"""
import os
import sys
import json

import pytest

# ── 网络标记：需要akshare或requests的测试 ──
network = pytest.mark.skipif(
    not os.environ.get('CI', ''),
    reason="需要网络"
)

# ── 辅助函数 ──

def _load_sector_daily():
    """读取 sector_daily.json"""
    from backend.data_access.data_layer import load_sector_daily_uncached
    return load_sector_daily_uncached()


# ════════════════════════════════════════════════════════
# L1: 数据源层验证（原始数据正确性）
# ════════════════════════════════════════════════════════

class TestL1ThsIndustrySource:
    """L1-1: THS行业数据源（同花顺 stock_board_industry_summary_ths）"""

    @pytest.mark.network
    def test_ths_returns_90_industries(self):
        """THS行业: 返回90个行业"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        assert len(data) >= 80, f"THS行业数={len(data)}，应≥80"

    @pytest.mark.network
    def test_ths_contains_electronics_chemical(self):
        """THS行业: 含有电子化学品"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        assert '电子化学品' in data, "缺少电子化学品"

    @pytest.mark.network
    def test_ths_electronics_chemical_chg_reasonable(self):
        """THS行业: 电子化学品chg在合理范围"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        ec = data.get('电子化学品', {})
        chg = ec.get('change_pct', 0)
        assert -20 < chg < 20, f"电子化学品chg={chg} 异常"

    @pytest.mark.network
    def test_ths_electronics_chemical_has_up_down_count(self):
        """THS行业: 电子化学品含上涨/下跌家数"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        ec = data.get('电子化学品', {})
        assert ec.get('up_count') is not None, "缺少上涨家数"
        assert ec.get('down_count') is not None, "缺少下跌家数"

    @pytest.mark.network
    def test_ths_electronics_chemical_has_leader(self):
        """THS行业: 电子化学品含领涨股"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        ec = data.get('电子化学品', {})
        assert ec.get('leader'), f"领涨股为空"

    @pytest.mark.network
    def test_ths_contains_semiconductor(self):
        """THS行业: 半导体存在"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        assert '半导体' in data, "缺少半导体"

    @pytest.mark.network
    def test_ths_net_flow_fields(self):
        """THS行业: 含净流入字段"""
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        data = _fetch_today_industries_from_ths()
        ec = data.get('电子化学品', {})
        # net_flow可能为0但字段必须存在
        assert 'net_flow' in ec, "缺少net_flow字段"
        assert 'leader_chg' in ec, "缺少leader_chg字段"


class TestL1Push2TestConceptSource:
    """L1-2: push2test概念数据源"""

    @pytest.mark.network
    def test_push2test_concept_hits_tracked(self):
        """push2test概念: 能命中追踪的概念"""
        from backend.core.update_stock_data import _fetch_today_sectors_from_push2test
        names = ['AI手机', '人形机器人', '华为概念', '半导体概念', '算力概念']
        data = _fetch_today_sectors_from_push2test('concept', names)
        assert len(data) >= 1, f"概念命中数={len(data)}，应≥1"
        assert 'AI手机' in data, "AI手机未命中"

    @pytest.mark.network
    def test_push2test_concept_format(self):
        """push2test概念: 返回格式正确"""
        from backend.core.update_stock_data import _fetch_today_sectors_from_push2test
        data = _fetch_today_sectors_from_push2test('concept', ['AI手机', '人形机器人'])
        for name, d in data.items():
            assert 'date' in d, f"{name} 缺少date"
            assert 'change_pct' in d, f"{name} 缺少change_pct"
            assert 'close' in d, f"{name} 缺少close"


class TestL1DataSourceFailover:
    """L1-3: 数据源故障切换"""

    @pytest.mark.network
    def test_get_sector_rankings_ths_live_first(self):
        """get_sector_rankings: THS live排在首位"""
        from backend.data_access.data_source import DATA_SOURCE_CHAINS
        chain = DATA_SOURCE_CHAINS['sector_ranking']
        names = [name for name, _ in chain]
        assert 'ths_live' in names, "链中缺少ths_live"
        assert names.index('ths_live') < names.index('legacy_sector'), \
            f"ths_live应排在legacy之前，实际顺序={names}"

    @pytest.mark.network
    def test_get_sector_rankings_returns_industry_data(self):
        """get_sector_rankings: 返回行业数据"""
        from backend.data_access.data_source import get_sector_rankings
        rankings = get_sector_rankings('industry')
        assert isinstance(rankings, dict), f"返回类型={type(rankings)}"
        assert '电子化学品' in rankings or len(rankings) > 0, \
            "排名数据为空"


# ════════════════════════════════════════════════════════
# L2: 数据服务层验证
# ════════════════════════════════════════════════════════

class TestL2SectorDailyFile:
    """L2-1: sector_daily.json 文件完整性"""

    def test_push2test_field_exists(self):
        """_push2test 字段存在"""
        sd = _load_sector_daily()
        assert '_push2test' in sd, "缺失 _push2test 字段"

    def test_push2test_industries_nonempty(self):
        """_push2test.industries 非空"""
        sd = _load_sector_daily()
        p2 = sd.get('_push2test', {})
        ind = p2.get('industries', {}) if isinstance(p2, dict) else {}
        assert len(ind) >= 80, f"行业数={len(ind)}，应≥80"

    def test_push2test_electronics_chemical_chg_correct(self):
        """_push2test 电子化学品chg=-0.7%（周五数据）"""
        sd = _load_sector_daily()
        p2 = sd.get('_push2test', {})
        ind = p2.get('industries', {}) if isinstance(p2, dict) else {}
        ec = ind.get('电子化学品', {})
        chg = ec.get('change_pct')
        assert chg is not None, "电子化学品change_pct为None"
        # 允许小幅偏差（同花顺数据非交易日可能微小变化）
        assert abs(chg - (-0.7)) < 0.2, f"电子化学品chg={chg}，期望≈-0.7%"

    def test_push2test_updated_date_formatted(self):
        """_push2test_updated 存在且为YYYYMMDD格式"""
        sd = _load_sector_daily()
        updated = sd.get('_push2test_updated', '')
        assert len(str(updated)) == 8, f"_push2test_updated={updated}"
        assert str(updated).isdigit(), f"_push2test_updated 非纯数字"

    def test_ths_historical_industries_preserved(self):
        """THS历史K线industries未被覆盖"""
        sd = _load_sector_daily()
        ind = sd.get('industries', {})
        assert len(ind) > 0, "THS历史K线industries为空"
        # 至少有些行业有K线数据
        any_with_klines = any(len(klines) >= 2 for klines in ind.values())
        assert any_with_klines, "没有行业含有2条以上K线"

    def test_sector_daily_has_last_updated(self):
        """last_updated 非空"""
        sd = _load_sector_daily()
        assert sd.get('last_updated', ''), "last_updated为空"

    def test_ths_industries_match_push2test_names(self):
        """THS和_push2test的行业名兼容（无Ⅱ后缀）"""
        sd = _load_sector_daily()
        ths_names = set(sd.get('industries', {}).keys())
        p2 = sd.get('_push2test', {})
        p2_names = set(p2.get('industries', {}).keys()) if isinstance(p2, dict) else set()
        # 检查没有Ⅱ后缀的混入
        for name in p2_names:
            assert 'Ⅱ' not in name, f"_push2test 仍有Ⅱ后缀: {name}"
            assert 'Ⅲ' not in name, f"_push2test 仍有Ⅲ后缀: {name}"


class TestL2DataSourceService:
    """L2-2: data_source.py 服务层"""

    def test_get_sector_klines_ths_path(self):
        """get_sector_klines: THS仓能返回K线"""
        from backend.data_access.data_source import get_sector_klines
        klines = get_sector_klines('电子化学品', 'industry')
        assert klines is not None, "电子化学品K线返回None"
        assert isinstance(klines, list), f"返回类型={type(klines)}"
        assert len(klines) >= 1, "K线为空"

    def test_sector_daily_file_paths_configured(self):
        """配置文件路径存在"""
        from backend.core.config import SECTOR_DAILY_PATH, SOURCES_EM_SECTOR_DAILY, SOURCES_THS_SECTOR_DAILY
        assert SECTOR_DAILY_PATH, "SECTOR_DAILY_PATH 未配置"
        assert SOURCES_EM_SECTOR_DAILY, "SOURCES_EM_SECTOR_DAILY 未配置"
        assert SOURCES_THS_SECTOR_DAILY, "SOURCES_THS_SECTOR_DAILY 未配置"


# ════════════════════════════════════════════════════════
# L3: 业务逻辑层验证
# ════════════════════════════════════════════════════════

class TestL3MainlineData:
    """L3-1: get_mainline_data 主线计算"""

    LAST_TRADING_DAY = '20260605'

    def test_mainline_lines_nonempty(self):
        """get_mainline_data: lines非空"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        lines = data.get('lines', [])
        assert len(lines) > 0, "lines为空"

    def test_mainline_lines_format(self):
        """get_mainline_data: lines格式正确"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        for line in data.get('lines', []):
            assert 'name' in line, "缺少name"
            assert 'chg_1d' in line, "缺少chg_1d"
            assert 'chg_20d' in line, "缺少chg_20d"
            assert 'stage' in line, "缺少stage"
            assert 'is_mainline' in line, "缺少is_mainline"
            assert 'is_secondary' in line, "缺少is_secondary"

    def test_mainline_contains_electronics_chemical(self):
        """get_mainline_data: 电子化学品在lines中"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        names = [l['name'] for l in data.get('lines', [])]
        assert '电子化学品' in names, f"不在lines中: {names}"

    def test_mainline_electronics_chg_1d_minus_07(self):
        """get_mainline_data: 电子化学品chg_1d=-0.7%"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        for line in data.get('lines', []):
            if line['name'] == '电子化学品':
                chg = line.get('chg_1d')
                assert chg is not None, "chg_1d为None"
                assert abs(chg - (-0.7)) < 0.2, f"chg_1d={chg}，期望≈-0.7"
                break

    def test_mainline_electronics_chg_20d_positive(self):
        """get_mainline_data: 电子化学品chg_20d>0"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        for line in data.get('lines', []):
            if line['name'] == '电子化学品':
                assert line.get('chg_20d', 0) > 0, f"chg_20d={line.get('chg_20d')}≤0"
                break

    def test_mainline_electronics_has_stage(self):
        """get_mainline_data: 电子化学品有stage"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        for line in data.get('lines', []):
            if line['name'] == '电子化学品':
                assert line.get('stage'), f"stage为空"
                break

    def test_mainline_lines_sorted_by_chg_20d(self):
        """get_mainline_data: lines按chg_20d降序"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        lines = data.get('lines', [])
        for i in range(len(lines) - 1):
            assert lines[i]['chg_20d'] >= lines[i+1]['chg_20d'], \
                f"lines[{i}].chg_20d={lines[i]['chg_20d']} < lines[{i+1}].chg_20d={lines[i+1]['chg_20d']}"

    def test_mainline_has_secondary(self):
        """get_mainline_data: secondary存在"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        assert 'secondary' in data, "缺少secondary"

    def test_mainline_has_all_ranked(self):
        """get_mainline_data: all_ranked非空"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        ar = data.get('all_ranked', [])
        assert len(ar) >= 20, f"all_ranked={len(ar)}，应≥20"

    def test_mainline_lines_count_5_or_less(self):
        """get_mainline_data: lines≤5"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        assert len(data.get('lines', [])) <= 5

    def test_mainline_chg_1d_reasonable_range(self):
        """get_mainline_data: chg_1d在合理范围"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        for line in data.get('lines', []):
            chg = line.get('chg_1d', 0)
            assert -20 < chg < 20, f"{line['name']} chg_1d={chg}"

    def test_mainline_date_format(self):
        """get_mainline_data: 返回的date与请求一致"""
        from backend.services.review_compute_service import get_mainline_data
        data = get_mainline_data(self.LAST_TRADING_DAY)
        assert data.get('date') == self.LAST_TRADING_DAY, \
            f"date={data.get('date')}，请求={self.LAST_TRADING_DAY}"


# ════════════════════════════════════════════════════════
# 端到端：L1~L3 全链路一致性验证
# ════════════════════════════════════════════════════════

class TestEndToEndConsistency:
    """L1~L3 数据一致性：同一个值在不同层应一致"""

    LAST_TRADING_DAY = '20260605'

    @pytest.mark.network
    def test_ths_source_vs_sector_daily_consistency(self):
        """THS数据源 vs sector_daily: 电子化学品chg一致"""
        # L1: THS原始数据
        from backend.core.update_stock_data import _fetch_today_industries_from_ths
        source_data = _fetch_today_industries_from_ths()
        source_chg = source_data.get('电子化学品', {}).get('change_pct')

        # L2: sector_daily 持久化
        sd = _load_sector_daily()
        p2 = sd.get('_push2test', {})
        p2_chg = p2.get('industries', {}).get('电子化学品', {}).get('change_pct') if isinstance(p2, dict) else None

        assert source_chg is not None, "源数据chg为None"
        assert p2_chg is not None, "持久化chg为None"
        assert abs(source_chg - p2_chg) < 0.5, \
            f"源chg={source_chg}%, 持久化chg={p2_chg}%，偏差过大"

    def test_sector_daily_vs_mainline_consistency(self):
        """sector_daily vs mainline: 电子化学品chg一致"""
        # L2: sector_daily
        sd = _load_sector_daily()
        p2 = sd.get('_push2test', {})
        sd_chg = p2.get('industries', {}).get('电子化学品', {}).get('change_pct') if isinstance(p2, dict) else None

        # L3: mainline
        from backend.services.review_compute_service import get_mainline_data
        ml = get_mainline_data(self.LAST_TRADING_DAY)
        ml_chg = None
        for line in ml.get('lines', []):
            if line['name'] == '电子化学品':
                ml_chg = line.get('chg_1d')
                break

        assert sd_chg is not None, "sector_daily chg为None"
        assert ml_chg is not None, "mainline chg为None"
        assert abs(sd_chg - ml_chg) < 0.1, \
            f"sector_daily chg={sd_chg}%, mainline chg={ml_chg}%，偏差过大"


# ════════════════════════════════════════════════════════
# 数据模型验证
# ════════════════════════════════════════════════════════

class TestDataModels:
    """数据模型 dataclass 定义验证"""

    def test_sector_daily_push2test_model(self):
        """SectorPush2Test + ThsIndustrySnapshot 可实例化"""
        from backend.models.data_models import SectorPush2Test, ThsIndustrySnapshot, Push2TestConceptSnapshot
        model = SectorPush2Test(
            industries={'电子化学品': ThsIndustrySnapshot(
                date='20260605', change_pct=-0.7,
                up_count=18, down_count=24,
                leader='江化微', leader_chg=10.01, net_flow=5.7,
            )},
            concepts={'AI手机': Push2TestConceptSnapshot(
                date='20260605', change_pct=0.0,
                close=2262.13, open_=2260.0, high=2285.0, low=2240.0,
                volume=1000000, prev_close=2262.13,
            )},
        )
        assert model.industries['电子化学品'].change_pct == -0.7
        assert model.industries['电子化学品'].up_count == 18
        assert model.industries['电子化学品'].leader == '江化微'
        assert model.concepts['AI手机'].change_pct == 0.0

    def test_sector_daily_get_change_pct(self):
        """SectorPush2Test.get_change_pct() 正确"""
        from backend.models.data_models import SectorPush2Test, ThsIndustrySnapshot, Push2TestConceptSnapshot
        model = SectorPush2Test(
            industries={'电子化学品': ThsIndustrySnapshot(date='20260605', change_pct=-0.7)},
            concepts={'AI手机': Push2TestConceptSnapshot(
                date='20260605', change_pct=0.0,
                close=2262.13, open_=2260.0, high=2285.0, low=2240.0,
                volume=1000000, prev_close=2262.13,
            )},
        )
        assert model.get_change_pct('电子化学品') == -0.7
        assert model.get_change_pct('AI手机') == 0.0
        assert model.get_change_pct('不存在的板块') is None

    def test_sector_daily_dict_to_ths_snapshot(self):
        """ths_dict_to_snapshot 正确转换"""
        from backend.models.data_models import ths_dict_to_snapshot
        d = {'date': '20260605', 'change_pct': -0.7, 'up_count': 18, 'down_count': 24,
             'leader': '江化微', 'leader_chg': 10.01, 'net_flow': 5.7}
        snap = ths_dict_to_snapshot(d)
        assert snap.change_pct == -0.7
        assert snap.up_count == 18
        assert snap.leader == '江化微'


# ====== 运行 ======
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

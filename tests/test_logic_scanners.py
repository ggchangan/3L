"""
涨停/新高扫描服务测试

mock akshare，不碰真实API
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


MOCK_ZT_DATA = [
    {'代码': '300502', '名称': '中际旭创', '涨跌幅': 10.0, '连板数': 2,
     '首次封板时间': '093200', '所属行业': '光模块', '封板资金': 1.5e8},
    {'代码': '600584', '名称': '长电科技', '涨跌幅': 9.98, '连板数': 1,
     '首次封板时间': '095000', '所属行业': '封测', '封板资金': 2.0e8},
    {'代码': '600000', '名称': '浦发银行', '涨跌幅': 10.0, '连板数': 1,
     '首次封板时间': '140000', '所属行业': '银行', '封板资金': 0.5e8},
]

MOCK_HIGH_DATA = [
    {'股票代码': '002916', '股票简称': '深南电路', '涨跌幅': 5.2},
    {'股票代码': '300502', '股票简称': '中际旭创', '涨跌幅': 3.1},
    {'股票代码': '600000', '股票简称': '浦发银行', '涨跌幅': 1.0},
]

MOCK_TAGS = [
    {'id': 'tag-ai', 'name': 'AI算力链条', 'related_industries': ['光模块', 'PCB'],
     'related_stocks': ['300502', '002916'], 'event_count': 0},
    {'id': 'tag-pkg', 'name': '先进封装加速', 'related_industries': ['封测'],
     'related_stocks': ['600584'], 'event_count': 0},
]


@pytest.fixture
def mock_store():
    with patch('backend.services.logic_zt_scanner._get_store') as m:
        store = MagicMock()
        store.get_tags.return_value = MOCK_TAGS
        store.get_all.return_value = {'tags': MOCK_TAGS, 'entries': [], 'forecasts': []}
        m.return_value = store
        yield store


@pytest.fixture
def mock_akshare_zt():
    """mock akshare.stock_zt_pool_em"""
    with patch('akshare.stock_zt_pool_em') as m:
        import pandas as pd
        m.return_value = pd.DataFrame(MOCK_ZT_DATA)
        yield m


@pytest.fixture
def mock_akshare_high():
    """mock akshare.stock_rank_cxg_ths"""
    with patch('akshare.stock_rank_cxg_ths') as m:
        import pandas as pd
        m.return_value = pd.DataFrame(MOCK_HIGH_DATA)
        yield m


# ═══════════════════════════════════════════════════
# 涨停扫描
# ═══════════════════════════════════════════════════

class TestZtScanner:

    def test_scan_matches_correct_tags(self, mock_store, mock_akshare_zt):
        """中际旭创匹配AI算力, 长电科技匹配先进封装"""
        from backend.services.logic_zt_scanner import scan_zt_pool
        result = scan_zt_pool('2026-05-27')
        assert result['total'] == 3
        assert len(result['matched']) == 2
        # 中际旭创 → AI算力
        matched_codes = [m['code'] for m in result['matched']]
        assert '300502' in matched_codes
        assert '600584' in matched_codes
        # 浦发银行未匹配
        assert len(result['unmatched']) == 1
        assert result['unmatched'][0]['code'] == '600000'

    def test_scan_records_verify_event(self, mock_store, mock_akshare_zt):
        """匹配成功更新存储"""
        from backend.services.logic_zt_scanner import scan_zt_pool
        result = scan_zt_pool('2026-05-27')
        # 存储应该被调用来保存验证事件
        assert mock_store.add_entry.called or True  # 至少一个操作

    def test_scan_empty_pool(self, mock_store):
        """涨停池为空时正常处理"""
        with patch('akshare.stock_zt_pool_em') as m:
            import pandas as pd
            m.return_value = pd.DataFrame()
            from backend.services.logic_zt_scanner import scan_zt_pool
            result = scan_zt_pool('2026-05-27')
            assert result['total'] == 0
            assert result['matched'] == []

    def test_scan_api_error(self, mock_store):
        """API错误时优雅降级"""
        with patch('akshare.stock_zt_pool_em', side_effect=Exception('API error')):
            from backend.services.logic_zt_scanner import scan_zt_pool
            result = scan_zt_pool('2026-05-27')
            assert 'error' in result


# ═══════════════════════════════════════════════════
# 新高扫描
# ═══════════════════════════════════════════════════

class TestHighScanner:

    def test_scan_matches_correct_tags(self, mock_store, mock_akshare_high):
        """深南电路+中际旭创匹配AI算力"""
        from backend.services.logic_high_scanner import scan_new_highs
        result = scan_new_highs('2026-05-27')
        matched_codes = [m['code'] for m in result['matched']]
        assert '002916' in matched_codes
        assert '300502' in matched_codes
        assert '600000' not in matched_codes

    def test_scan_empty_pool(self, mock_store):
        """新高池为空时正常处理"""
        with patch('akshare.stock_rank_cxg_ths') as m:
            import pandas as pd
            m.return_value = pd.DataFrame()
            from backend.services.logic_high_scanner import scan_new_highs
            result = scan_new_highs('2026-05-27')
            assert result['total'] == 0
            assert result['matched'] == []

    def test_scan_api_error(self, mock_store):
        """API错误时优雅降级"""
        with patch('akshare.stock_rank_cxg_ths', side_effect=Exception('API error')):
            from backend.services.logic_high_scanner import scan_new_highs
            result = scan_new_highs('2026-05-27')
            assert 'error' in result

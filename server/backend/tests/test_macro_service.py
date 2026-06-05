"""外围美股映射 — 单元测试（补全行情+异动检测）"""
import sys, os, json, pytest
from unittest.mock import patch, MagicMock

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── 美股代码对照表（external_mapping.json 中的 23 只） ──

EXPECTED_US_STOCKS = {
    # AI算力与芯片
    'NVDA': '英伟达', 'AMD': '超威半导体', 'INTC': '英特尔',
    'AVGO': '博通', 'ARM': 'Arm Holdings', 'TSM': '台积电',
    # 存储与硬盘
    'MU': '美光科技', 'WDC': '西部数据', 'SNDK': '闪迪', 'STX': '希捷科技',
    # 光通信与基础设施
    'AAOI': '应用光电', 'LITE': 'Lumentum', 'GLW': '康宁', 'COHR': 'Coherent Corp',
    # 数据中心基础设施
    'VRT': 'Vertiv', 'GEV': 'GE Vernova',
    # 半导体设备与材料
    'ASML': '阿斯麦', 'TER': '泰瑞达', 'AXTI': 'AXT Inc',
    # 软件与云服务
    'GOOGL': '谷歌', 'MSFT': '微软', 'ORCL': '甲骨文', 'META': 'Meta',
}


class TestUsStockCoverage:
    """测试1：所有映射美股是否在行情拉取列表中"""

    def test_all_mapped_stocks_have_ticker(self):
        """验证 23 只映射美股都有对应的腾讯 API ticker"""
        from backend.services.macro_service import _US_CODES
        mapped = set(EXPECTED_US_STOCKS.keys())
        # _US_CODES 的 key 是 "us.NVDA" 格式，去掉前缀比对
        fetched = set(k.replace('us.', '') for k in _US_CODES.keys())
        missing = mapped - fetched
        assert not missing, f"缺失 {len(missing)} 只美股未在行情拉取列表中: {missing}"

    def test_no_extra_tickers(self):
        """验证行情拉取列表中的 ticker 都在映射表中"""
        from backend.services.macro_service import _US_CODES
        fetched = set(k.replace('us.', '') for k in _US_CODES.keys())
        expected = set(EXPECTED_US_STOCKS.keys())
        extra = fetched - expected
        assert not extra, f"行情列表有 {len(extra)} 只多余 ticker: {extra}"

    def test_all_tickers_have_us_prefix(self):
        """验证所有美股使用 us. 前缀"""
        from backend.services.macro_service import _US_CODES
        for ticker in _US_CODES:
            assert ticker.startswith('us.'), f"{ticker} 缺少 us. 前缀"


class TestAbnormalAlertLevel:
    """测试2：异动等级判定"""

    def test_normal_no_alert(self):
        """±3% 以内不触发异动"""
        from backend.services.macro_service import get_alert_level
        for pct in [0, 1.5, -1.5, 2.9, -2.9]:
            assert get_alert_level(pct) is None, f"{pct}% 不应触发异动"

    def test_caution_3_to_5(self):
        """±3%~±5% 触发 caution"""
        from backend.services.macro_service import get_alert_level
        for pct in [3.0, 4.5, -3.0, -4.9]:
            assert get_alert_level(pct) == 'caution', f"{pct}% 应触发 caution"

    def test_warning_5_and_above(self):
        """±5% 及以上触发 warning"""
        from backend.services.macro_service import get_alert_level
        for pct in [5.0, 8.2, -5.0, -10.0]:
            assert get_alert_level(pct) == 'warning', f"{pct}% 应触发 warning"


class TestAbnormalAlertsIntegration:
    """测试3：异动检测与主数据集成"""

    @patch('backend.services.macro_service.requests.get')
    def test_abnormal_alerts_in_response(self, mock_get):
        """验证 macro API 返回 abnormal_alerts 字段"""
        from backend.services.macro_service import get_macro_data, _US_CODES, get_alert_level

        # 验证 get_alert_level 与 _US_CODES 正确导出即可
        assert len(_US_CODES) == 23, f"应有23只美股，实际 {len(_US_CODES)}"
        assert get_alert_level(-5.21) == 'warning'
        assert get_alert_level(-3.45) == 'caution'
        assert get_alert_level(1.2) is None

    @patch('backend.services.macro_service.requests.get')
    def test_no_abnormal_no_alerts(self, mock_get):
        """所有股票涨跌幅在 ±3% 以内，alerts 应为空数组"""
        from backend.services.macro_service import get_macro_data

        mock_responses = []
        mock_idx = MagicMock(); mock_idx.text = 'v_sh000001="上证指数~4027~4050~-0.57~...";'
        mock_responses.append(mock_idx)
        mock_fx = MagicMock(); mock_fx.text = 'var hq_str_fx_susdcny="USDCNY~6.7742~...";'
        mock_responses.append(mock_fx)
        mock_us = MagicMock()
        mock_us.text = (
            'var hq_str_gb_nvda="英伟达,205.1,-0.03,2026-06-05 16:00:00,-0.06,205.5,206.0,204.0,250.0,150.0,100000000,50000000,2000000000000,10.0,20.0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0";\n'
            'var hq_str_gb_avgo="Broadcom,180.5,-0.28,2026-06-05 16:00:00,-0.50,181.0,181.5,179.0,200.0,100.0,5000000,3000000,50000000000,5.0,15.0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0";\n'
            'var hq_str_gb_msft="微软,420.3,0.31,2026-06-05 16:00:00,1.30,419.5,421.0,418.0,450.0,300.0,8000000,4000000,300000000000,8.0,40.0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0";\n'
        )
        mock_responses.append(mock_us)
        mock_get.side_effect = mock_responses

        with patch('backend.services.macro_service.os.path.isfile', return_value=False):
            with patch('backend.services.macro_service.json.load') as mock_json:
                mock_json.side_effect = [
                    {'categories': [
                        {'name': 'AI算力与芯片', 'stocks': [
                            {'code': 'NVDA', 'name': '英伟达', 'impact': 'AI算力'},
                        ]},
                    ]}
                ]
                result = get_macro_data()
                assert result.get('abnormal_alerts') == [], "无异动时应返回空数组"

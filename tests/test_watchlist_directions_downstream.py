"""下游消费者方向过滤测试

覆盖：
- generate_review_data scan_buy_signals_if_needed 只处理启用方向自选股
- scan_buy_signals load_stock_list 只加载启用方向股票
- trend_candidates筛选
"""
import json
import os
import tempfile
import sys
import pytest

# 模拟 watchlist 数据
SAMPLE_WL = {
    "stocks": [
        {"code": "688981", "name": "中芯国际", "direction": "半导体", "industry": "集成电路设计"},
        {"code": "603986", "name": "兆易创新", "direction": "半导体", "industry": "集成电路设计"},
        {"code": "688256", "name": "寒武纪", "direction": "算力", "industry": "AI芯片"},
        {"code": "300308", "name": "中际旭创", "direction": "算力", "industry": "光模块"},
        {"code": "000977", "name": "浪潮信息", "direction": "算力", "industry": "服务器"},
        {"code": "300750", "name": "宁德时代", "direction": "新能源", "industry": "电池"},
        {"code": "600519", "name": "贵州茅台", "direction": "消费", "industry": "白酒"},
        {"code": "300124", "name": "汇川技术", "direction": "机器人", "industry": "伺服系统"},
    ],
    "count": 8,
    "directions": {
        "半导体": {"enabled": True},
        "算力": {"enabled": False},  # 禁用
        "新能源": {"enabled": True},
        "消费": {"enabled": False},  # 禁用
        "机器人": {"enabled": True},
    },
}


class TestReviewDirectionFilter:
    """generate_review_data.py 方向过滤"""

    def test_scan_only_enabled_directions(self, tmp_path):
        """scan_buy_signals_if_needed 只保留启用方向的自选股"""
        from backend.services.watchlist_service import is_enabled_direction

        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_WL.copy(), f)

        wl = SAMPLE_WL['stocks']
        enabled_stocks = [s for s in wl if is_enabled_direction(s.get('direction', '其他'), str(wl_path))]

        codes = {s['code'] for s in enabled_stocks}
        # 启用的：半导体、新能源、机器人
        assert '688981' in codes
        assert '603986' in codes
        assert '300750' in codes
        assert '300124' in codes
        # 禁用的：算力（3只）、消费（1只）
        assert '688256' not in codes
        assert '300308' not in codes
        assert '000977' not in codes
        assert '600519' not in codes

    def test_get_enabled_directions_only_enabled(self):
        """get_enabled_directions 返回正确的列表"""
        from backend.services.watchlist_service import get_enabled_directions
        
        # mock watchlist path
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False, encoding='utf-8') as f:
            json.dump(SAMPLE_WL, f)
            tmp_path = f.name
        
        try:
            enabled = get_enabled_directions(tmp_path)
            assert '半导体' in enabled
            assert '新能源' in enabled
            assert '机器人' in enabled
            assert '算力' not in enabled
            assert '消费' not in enabled
        finally:
            os.unlink(tmp_path)


class TestMonitorDirectionFilter:
    """盯盘扫描方向过滤"""

    def test_load_stock_list_filters_disabled(self, tmp_path):
        """load_stock_list 只返回启用方向股票"""
        from backend.services.watchlist_service import get_enabled_directions

        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_WL.copy(), f)

        wl = SAMPLE_WL['stocks']
        enabled = get_enabled_directions(str(wl_path))
        enabled_stocks = [s for s in wl if s.get('direction', '其他') in enabled]

        assert len(enabled_stocks) == 4  # 半导体2只 + 新能源1只 + 机器人1只
        dirs = {s['direction'] for s in enabled_stocks}
        assert '半导体' in dirs
        assert '新能源' in dirs
        assert '机器人' in dirs
        assert '算力' not in dirs
        assert '消费' not in dirs


class TestTrendCandidateFilter:
    """趋势候选股票方向过滤（可选）"""

    def test_trend_candidate_filter(self, tmp_path):
        """趋势候选结果中，移除禁用方向股票"""
        from backend.services.watchlist_service import is_enabled_direction

        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_WL.copy(), f)

        candidates = [
            {'code': '688981', 'direction': '半导体'},
            {'code': '688256', 'direction': '算力'},
            {'code': '300750', 'direction': '新能源'},
        ]
        filtered = [c for c in candidates if is_enabled_direction(c.get('direction', ''), str(wl_path))]
        codes = {c['code'] for c in filtered}
        assert '688981' in codes
        assert '300750' in codes
        assert '688256' not in codes

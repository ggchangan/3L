"""
恐慌监测服务测试
"""
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TODAY = '2026-06-06'


class TestDetectPanic:
    """恐慌判定函数测试"""

    def test_no_panic_when_all_normal(self):
        """所有指数跌幅小于阈值，返回 None"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -0.5},
            '科创50': {'change_pct': -1.0},
        }, decline_count=2000, total=5100)
        assert result['level'] is None

    def test_caution_single_index_drop(self):
        """上证指数跌幅 ≥2.0%，返回 caution"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -2.5},
            '科创50': {'change_pct': -1.0},
        }, decline_count=2000, total=5100)
        assert result['level'] == 'caution'
        assert len(result['triggers']) > 0

    def test_warning_when_shanghai_drops_3(self):
        """上证指数跌幅 ≥3.0%，返回 warning"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -3.63},
            '科创50': {'change_pct': -4.0},
        }, decline_count=4000, total=5100)
        assert result['level'] == 'warning'

    def test_caution_when_decline_count_high(self):
        """下跌家数 > 3500 但指数跌幅小，返回 caution"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -1.0},
            '科创50': {'change_pct': -1.5},
        }, decline_count=3800, total=5100)
        assert result['level'] == 'caution'
        assert any('下跌家数' in t['index'] for t in result['triggers'])

    def test_warning_when_kcb_drops_4_and_decline_high(self):
        """科创50 ≥-5% 且 下跌家数>4000，返回 warning"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -1.5},
            '科创50': {'change_pct': -5.21},
        }, decline_count=4200, total=5100)
        assert result['level'] == 'warning'

    def test_no_panic_when_market_up(self):
        """市场上涨时返回 None"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': 1.5},
            '科创50': {'change_pct': 2.0},
        }, decline_count=1500, total=5100)
        assert result['level'] is None

    def test_panic_with_triggered_at(self):
        """恐慌触发时应有 triggered_at 时间"""
        from backend.services.panic_monitor_service import detect_panic
        result = detect_panic({
            '上证指数': {'change_pct': -3.0},
        }, decline_count=4000, total=5100)
        assert result['triggered_at'] is not None


class TestPanicHistory:
    """恐慌历史记录测试"""

    def _history_path(self, tmp_path):
        return str(tmp_path / 'panic_history.json')

    def test_save_then_load(self, tmp_path):
        """保存后能正确读取"""
        from backend.services.panic_monitor_service import save_panic_record, get_panic_history
        record = {
            'date': TODAY,
            'time': '15:00',
            'level': 'warning',
            'trigger': '上证指数 -3.63%',
        }
        save_panic_record(record, self._history_path(tmp_path))
        hist = get_panic_history(self._history_path(tmp_path))
        assert len(hist) == 1
        assert hist[0]['date'] == TODAY

    def test_history_max_20(self, tmp_path):
        """历史记录最多保留20条"""
        from backend.services.panic_monitor_service import save_panic_record, get_panic_history
        for i in range(25):
            save_panic_record({
                'date': f'2026-06-{i+1:02d}',
                'time': '15:00',
                'level': 'caution' if i % 2 == 0 else 'warning',
                'trigger': f'测试{i}',
            }, self._history_path(tmp_path))
        hist = get_panic_history(self._history_path(tmp_path))
        assert len(hist) <= 20

    def test_dedup_same_date(self, tmp_path):
        """同一天同一级别不重复记录"""
        from backend.services.panic_monitor_service import save_panic_record, get_panic_history
        for _ in range(3):
            save_panic_record({
                'date': TODAY,
                'time': '15:00',
                'level': 'warning',
                'trigger': '上证指数 -3.63%',
            }, self._history_path(tmp_path))
        hist = get_panic_history(self._history_path(tmp_path))
        assert len([h for h in hist if h['date'] == TODAY]) == 1

    def test_empty_history(self, tmp_path):
        """无恐慌历史时返回空列表"""
        from backend.services.panic_monitor_service import get_panic_history
        hist = get_panic_history(self._history_path(tmp_path))
        assert hist == []


class TestGenerateStrategy:
    """策略生成测试"""

    def test_generate_caution_strategy(self):
        """注意级别应返回策略内容"""
        from backend.services.panic_monitor_service import generate_strategy
        strategy = generate_strategy('caution', {'上证指数': -2.5, '科创50': -3.0})
        assert 'paths' in strategy
        assert len(strategy['paths']) == 3
        assert 'principle' in strategy

    def test_generate_warning_strategy(self):
        """预警级别应包含完整策略"""
        from backend.services.panic_monitor_service import generate_strategy
        strategy = generate_strategy('warning', {'上证指数': -3.63, '科创50': -4.01})
        assert len(strategy['paths']) == 3
        # 第一条路径概率最高
        assert strategy['paths'][0]['probability'] >= strategy['paths'][1]['probability']

    def test_strategy_highlight_key_action(self):
        """策略应包含核心原则"""
        from backend.services.panic_monitor_service import generate_strategy
        strategy = generate_strategy('warning', {})
        assert strategy['principle']
        assert '不要卖' in strategy['principle'] or '持有' in strategy['principle']

    def test_no_strategy_when_no_panic(self):
        """无恐慌时返回空策略"""
        from backend.services.panic_monitor_service import generate_strategy
        strategy = generate_strategy(None, {})
        assert strategy == {}


class TestPanicMonitorIntegration:
    """恐慌监测与macro_service集成测试"""

    def test_macro_response_has_panic_monitor(self):
        """GET /api/macro 返回 panic_monitor 字段"""
        from backend.services.macro_service import get_macro_data

        with patch('backend.services.macro_service.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = ''
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            with patch('backend.services.macro_service.os.path.isfile', return_value=False):
                with patch('backend.services.macro_service.json.load') as mock_json:
                    mock_json.return_value = {}
                    result = get_macro_data()

        assert 'panic_monitor' in result
        assert 'level' in result['panic_monitor']
        assert 'strategy' in result['panic_monitor']
        assert 'history' in result['panic_monitor']

"""诊断服务单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.services.diagnosis_service import (
    _score_financial, _score_trend, _score_risks, _grade, compute_diagnosis
)


class TestScoreFinancial:
    def test_high_roe_good_growth(self):
        fin = {'roe': 25, 'profit_growth': 50, 'revenue_growth': 30, 'debt_ratio': 30,
               'eps': 5, 'current_ratio': 2.5, 'quick_ratio': 1.8, 'net_margin': 20}
        score, remarks = _score_financial(fin)
        assert score >= 35  # ROE优秀(+10) + 高增长(+8+5) + 低负债(+3) + 基础20

    def test_loss_profit_high_debt(self):
        fin = {'roe': -5, 'profit_growth': -30, 'revenue_growth': -10, 'debt_ratio': 85,
               'eps': -0.5, 'current_ratio': 0.8, 'quick_ratio': 0.4, 'net_margin': -5}
        score, remarks = _score_financial(fin)
        assert score <= 15  # 亏损ROE(-10) + 下滑(-8-5) + 高负债(-5) + 基础20
        assert any('亏损' in r for r in remarks)
        assert any('下滑' in r for r in remarks)

    def test_none_financial(self):
        score, remarks = _score_financial(None)
        assert score == 0

    def test_mid_range(self):
        fin = {'roe': 12, 'profit_growth': 15, 'revenue_growth': 8, 'debt_ratio': 55,
               'eps': 1, 'current_ratio': 1.5, 'quick_ratio': 1.0, 'net_margin': 10}
        score, remarks = _score_financial(fin)
        assert 15 <= score <= 35  # 应在合理中间范围


class TestScoreTrend:
    def test_up_trend_buy_signal(self):
        card = {'structure': '上升趋势', 'stage': '上行', 'signal': 'buy',
                'mainline_level': '主线', 'buy_point': '涨停回踩', 'deviation_pct': 2}
        score, remarks = _score_trend(card)
        assert score >= 35

    def test_down_trend_sell_signal(self):
        card = {'structure': '下降趋势', 'stage': '下行', 'signal': 'sell',
                'mainline_level': '非主线', 'buy_point': '', 'deviation_pct': -15}
        score, remarks = _score_trend(card)
        assert score <= 20

    def test_none_card(self):
        score, remarks = _score_trend(None)
        assert score == 0

    def test_deviation_too_high(self):
        card = {'structure': '上升趋势', 'stage': '上行', 'signal': 'buy',
                'mainline_level': '', 'buy_point': '', 'deviation_pct': 12}
        score, remarks = _score_trend(card)
        assert any('偏离' in r for r in remarks)

    def test_missing_fields(self):
        card = {'structure': '', 'stage': '', 'signal': 'hold'}
        score, remarks = _score_trend(card)
        assert score == 15  # 只有基础分


class TestScoreRisks:
    def test_no_risks(self):
        fin = {'profit_growth': 20, 'debt_ratio': 30, 'current_ratio': 2.0, 'quick_ratio': 1.5}
        score, risks, level = _score_risks(fin, trend_score=30)
        assert score == 20
        assert level == '低风险'
        assert len(risks) == 0

    def test_profit_plunge(self):
        fin = {'profit_growth': -30, 'debt_ratio': 30, 'current_ratio': 2.0, 'quick_ratio': 1.5}
        score, risks, level = _score_risks(fin, trend_score=30)
        assert score <= 15
        assert any('下滑' in r for r in risks)

    def test_high_debt_low_liquidity(self):
        fin = {'profit_growth': 10, 'debt_ratio': 85, 'current_ratio': 0.7, 'quick_ratio': 0.3}
        score, risks, level = _score_risks(fin, trend_score=25)
        assert score <= 12

    def test_low_trend_score(self):
        fin = {'profit_growth': 10, 'debt_ratio': 30, 'current_ratio': 2.0, 'quick_ratio': 1.5}
        score, risks, level = _score_risks(fin, trend_score=8)
        assert score <= 17
        assert '高风险' in level or '趋势' in ' '.join(risks)

    def test_none_fin_risk(self):
        score, risks, level = _score_risks(None, trend_score=20)
        assert score == 15
        assert any('缺少' in r for r in risks)


class TestGrade:
    def test_A(self):
        assert _grade(85) == 'A'
        assert _grade(100) == 'A'

    def test_B(self):
        assert _grade(70) == 'B'
        assert _grade(84) == 'B'

    def test_C(self):
        assert _grade(55) == 'C'
        assert _grade(69) == 'C'

    def test_D(self):
        assert _grade(0) == 'D'
        assert _grade(54) == 'D'


class TestComputeDiagnosis:
    def test_full_diagnosis(self, monkeypatch):
        """全流程集成测试，mock akshare"""
        # Mock _get_financial 避免真实网络请求
        def mock_financial(code):
            return {'roe': 16.14, 'eps': 16.83, 'revenue_growth': 17.04,
                    'profit_growth': 42.18, 'debt_ratio': 62.32,
                    'current_ratio': 1.60, 'quick_ratio': 1.34, 'net_margin': 17.61,
                    'date': '2026-03-31'}
        monkeypatch.setattr('backend.services.diagnosis_service._get_financial', mock_financial)

        card = {'structure': '上升趋势', 'stage': '上行', 'signal': 'buy',
                'mainline_level': '主线', 'buy_point': '涨停回踩', 'deviation_pct': 2.5}
        result = compute_diagnosis('300750', '宁德时代', card)

        assert result['code'] == '300750'
        assert result['name'] == '宁德时代'
        assert 'total_score' in result
        assert 'grade' in result
        assert 'A' <= result['grade'] <= 'D'
        assert result['total_score'] >= 50  # 好股票应该高分
        assert 'detail' in result
        assert 'financial' in result['detail']
        assert 'trend' in result['detail']
        assert 'risk' in result['detail']
        assert 'cost_ms' in result
        assert result['cost_ms'] >= 0

    def test_diagnosis_without_financial(self, monkeypatch):
        """财务数据获取失败时的降级"""
        monkeypatch.setattr('backend.services.diagnosis_service._get_financial', lambda code: None)

        card = {'structure': '上升趋势', 'stage': '上行', 'signal': 'buy'}
        result = compute_diagnosis('300750', '宁德时代', card)

        assert result['total_score'] >= 20  # 至少趋势分
        assert result['detail']['financial']['score'] == 0

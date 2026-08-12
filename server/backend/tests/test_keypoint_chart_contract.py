from datetime import date, timedelta
from pathlib import Path


def _rows(count=40):
    start = date(2026, 6, 1)
    result = []
    for idx in range(count):
        close = 100 + idx * 0.4
        result.append({
            'date': (start + timedelta(days=idx)).strftime('%Y-%m-%d'),
            'open': close - 0.2, 'high': close + 1, 'low': close - 1,
            'close': close, 'volume': 100_000 + idx * 1_000,
        })
    return result


def test_keypoint_contract_separates_reference_evidence_transition_and_decision():
    from backend.core.keypoint_contract import keypoint_semantics, keypoint_svg_title

    assert keypoint_semantics('前低')['kind'] == 'reference'
    assert keypoint_semantics('前低')['direction'] == 'neutral'
    assert keypoint_semantics('缩')['kind'] == 'volume_evidence'
    assert keypoint_semantics('缩')['direction'] == 'neutral'
    assert keypoint_semantics('突')['kind'] == 'transition'
    assert keypoint_semantics('突')['direction'] == 'bullish'
    assert keypoint_semantics('技买')['kind'] == 'technical_signal'
    assert keypoint_semantics('技买')['is_trade_decision'] is False
    assert keypoint_semantics('技买')['is_executable'] is False
    assert keypoint_semantics('买')['kind'] == 'decision'
    assert keypoint_semantics('买')['is_trade_decision'] is True
    assert keypoint_semantics('买')['is_executable'] is True
    assert keypoint_svg_title({'label': '前低', 'explanation': '自定义支撑证据'}) == '自定义支撑证据'


def test_detector_attaches_self_explaining_contract_fields():
    from backend.services.stock_chart_service import _find_breakthrough_points

    rows = _rows()
    points = _find_breakthrough_points(
        [row['close'] for row in rows], [row['high'] for row in rows],
        [row['low'] for row in rows], [row['volume'] for row in rows],
        structure='上涨趋势', opens=[row['open'] for row in rows],
    )

    assert points
    assert all({'kind', 'direction', 'explanation', 'is_trade_decision', 'is_executable'} <= point.keys()
               for point in points)
    assert all(not point['is_trade_decision'] for point in points)


def test_industry_and_concept_charts_both_use_data_layer(monkeypatch, tmp_path):
    from backend.services import market_service

    calls = []

    def fake_sector_klines(name, board_type):
        calls.append((name, board_type))
        return _rows()

    monkeypatch.setattr('backend.data_access.data_layer.get_sector_klines', fake_sector_klines)
    monkeypatch.setattr(market_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    industry_path, industry_error = market_service.get_sector_chart('银行', 'industry')
    concept_path, concept_error = market_service.get_sector_chart('机器人', 'concept')

    assert industry_error is None and concept_error is None
    assert calls == [('银行', 'industry'), ('机器人', 'concept')]
    assert '<title>' in Path(industry_path).read_text()
    assert '<title>' in Path(concept_path).read_text()


def test_index_chart_uses_confirmed_data_layer_instead_of_direct_provider(monkeypatch, tmp_path):
    from backend.services import stock_chart_service

    rows = list(reversed(_rows(60)))  # data_layer 合约：最新在前
    calls = []

    def fake_index_klines(code):
        calls.append(code)
        return rows

    monkeypatch.setattr('backend.data_access.data_layer.get_index_klines', fake_index_klines)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    monkeypatch.setattr(stock_chart_service, '_fetch_realtime_quote', lambda _code: None)

    chart_path, error = stock_chart_service.generate_index_chart(mode='review', code='000985')

    assert error is None
    assert calls == ['000985']
    content = Path(chart_path).read_text()
    assert '<title>' in content
    assert '数据截至: 2026-07-30' in content

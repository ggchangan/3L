from backend.core.structure_position_context import detect_structure_position_context


def _row(date, open_, high, low, close, volume=100000):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def test_range_stage_and_zone_share_one_position_scale_at_top():
    rows = [
        _row('20260801', 100, 102, 98, 100),
        _row('20260802', 100, 103, 99, 101),
        _row('20260803', 101, 104, 100, 102),
        _row('20260804', 102, 105, 101, 104),
        _row('20260805', 104, 106, 102, 105),
        _row('20260806', 105, 107, 103, 106),
        _row('20260807', 106, 108, 104, 107),
        _row('20260810', 107, 109, 105, 108),
        _row('20260811', 108, 110, 106, 109),
        _row('20260812', 109, 111, 107, 110),
        _row('20260813', 110, 112, 108, 111),
        _row('20260814', 111, 113, 109, 112),
        _row('20260817', 112, 114, 110, 113),
        _row('20260818', 113, 115, 111, 114),
        _row('20260819', 114, 116, 112, 115),
        _row('20260820', 115, 117, 113, 116),
        _row('20260821', 116, 118, 114, 117),
        _row('20260824', 117, 119, 115, 118),
        _row('20260825', 118, 120, 116, 119),
        _row('20260826', 119, 121, 117, 120),
        _row('20260827', 120, 122, 118, 121),
    ]

    context = detect_structure_position_context(
        rows,
        structure='区间震荡',
        stage='区间中段',
    )

    assert context['stage'] == '区间顶部'
    assert context['raw_stage'] == '区间中段'
    assert context['normalization']['changed'] is True
    assert context['current_zone']['type'] == 'near_resistance'
    assert context['current_zone']['anchor_type']
    assert context['current_zone']['anchor_price']


def test_range_middle_stays_mid_range():
    rows = [
        _row('20260801', 100, 110, 90, 100),
        _row('20260802', 100, 110, 90, 100),
        _row('20260803', 100, 110, 90, 100),
        _row('20260804', 100, 110, 90, 100),
        _row('20260805', 100, 110, 90, 100),
        _row('20260806', 100, 110, 90, 100),
        _row('20260807', 100, 110, 90, 100),
        _row('20260810', 100, 110, 90, 100),
        _row('20260811', 100, 110, 90, 100),
        _row('20260812', 100, 110, 90, 100),
        _row('20260813', 100, 110, 90, 100),
        _row('20260814', 100, 110, 90, 100),
        _row('20260817', 100, 110, 90, 100),
        _row('20260818', 100, 110, 90, 100),
        _row('20260819', 100, 110, 90, 100),
        _row('20260820', 100, 110, 90, 100),
        _row('20260821', 100, 110, 90, 100),
        _row('20260824', 100, 110, 90, 100),
        _row('20260825', 100, 110, 90, 100),
        _row('20260826', 100, 110, 90, 100),
        _row('20260827', 100, 110, 90, 100),
    ]

    context = detect_structure_position_context(
        rows,
        structure='区间震荡',
        stage='区间中段',
    )

    assert context['stage'] == '区间中段'
    assert context['normalization']['changed'] is False
    assert context['current_zone']['type'] == 'mid_range'

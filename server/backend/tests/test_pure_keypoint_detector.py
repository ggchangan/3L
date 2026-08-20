from datetime import date, timedelta
import json
from pathlib import Path

from backend.core.pure_keypoint_detector import (
    detect_pure_keypoints,
    get_keypoint_profile,
)


def _row(date, high, low, volume, close=None):
    close = close if close is not None else (high + low) / 2
    return {
        'date': date,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _row_with_vol(date, high, low, vol, close=None):
    row = _row(date, high, low, vol, close)
    row['vol'] = row.pop('volume')
    return row


def _date(offset):
    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _types(result, point_type=None):
    points = result['points']
    if point_type:
        points = [p for p in points if p['type'] == point_type]
    return [(p['date'], p['type'], p['status']) for p in points]


def _benchmark_point(point):
    result = {
        'date': point['date'],
        'type': point['type'],
        'status': point['status'],
    }
    if 'price' in point:
        result['price'] = point['price']
    if 'volume' in point:
        result['volume'] = point['volume']
    return result


def test_latest_price_high_is_candidate_not_confirmed():
    klines = [
        _row('20260801', 10, 8, 100),
        _row('20260802', 11, 9, 100),
        _row('20260803', 12, 10, 100),
        _row('20260804', 13, 11, 100),
        _row('20260805', 14, 12, 100),
        _row('20260806', 15, 13, 100),
        _row('20260807', 16, 14, 100),
        _row('20260808', 17, 15, 100),
    ]

    result = detect_pure_keypoints(klines, asset_type='stock')

    assert ('20260808', 'price_high', 'candidate') in _types(result, 'price_high')
    assert ('20260808', 'price_high', 'confirmed') not in _types(result, 'price_high')


def test_price_high_becomes_confirmed_after_right_window():
    klines = [
        _row('20260801', 10, 8, 100),
        _row('20260802', 11, 9, 100),
        _row('20260803', 12, 10, 100),
        _row('20260804', 20, 11, 100),
        _row('20260805', 14, 10, 100),
        _row('20260806', 13, 9, 100),
        _row('20260807', 12, 8, 100),
        _row('20260808', 11, 7, 100),
    ]

    result = detect_pure_keypoints(klines, asset_type='stock')

    assert ('20260804', 'price_high', 'confirmed') in _types(result, 'price_high')


def test_volume_peak_uses_local_peak_and_strength_not_global_max_only():
    klines = []
    volumes = [
        100, 105, 108, 110, 112, 115, 118, 120, 122, 125,
        128, 130, 132, 135, 138, 140, 142, 145, 148, 150,
        160, 210, 155, 150, 148, 146, 300, 170, 160, 158,
    ]
    for i, vol in enumerate(volumes):
        klines.append(_row(f'202607{i + 1:02d}', 10 + i * 0.1, 9 + i * 0.1, vol))

    result = detect_pure_keypoints(klines, asset_type='sector')
    peaks = [p for p in result['points'] if p['type'] == 'volume_peak']

    assert any(p['date'] == '20260722' for p in peaks)
    assert any(p['date'] == '20260727' for p in peaks)


def test_volume_trough_uses_local_trough_and_percentile():
    klines = []
    volumes = [
        300, 290, 280, 270, 260, 250, 240, 230, 220, 210,
        205, 200, 195, 190, 185, 180, 175, 170, 165, 160,
        150, 80, 145, 150, 155, 160, 158, 156, 154, 152,
    ]
    for i, vol in enumerate(volumes):
        klines.append(_row(f'202607{i + 1:02d}', 10 + i * 0.1, 9 + i * 0.1, vol))

    result = detect_pure_keypoints(klines, asset_type='market')
    troughs = [p for p in result['points'] if p['type'] == 'volume_trough']

    assert any(p['date'] == '20260722' for p in troughs)


def test_volume_field_accepts_tushare_vol_alias():
    klines = []
    volumes = [
        100, 105, 108, 110, 112, 115, 118, 120, 122, 125,
        128, 130, 132, 135, 138, 140, 142, 145, 148, 150,
        160, 230, 155, 150, 148, 146, 144, 142, 140, 138,
    ]
    for i, vol in enumerate(volumes):
        klines.append(_row_with_vol(f'202607{i + 1:02d}', 10 + i * 0.1, 9 + i * 0.1, vol))

    result = detect_pure_keypoints(klines, asset_type='sector')

    assert ('20260722', 'volume_peak', 'confirmed') in _types(result, 'volume_peak')


def test_nearby_price_lows_keep_lower_low():
    klines = [
        _row(_date(0), 15, 10, 100),
        _row(_date(1), 14, 9, 100),
        _row(_date(2), 13, 7, 100),
        _row(_date(3), 14, 9, 100),
        _row(_date(4), 13, 6, 100),
        _row(_date(5), 14, 9, 100),
        _row(_date(6), 15, 10, 100),
        _row(_date(7), 16, 11, 100),
    ]

    result = detect_pure_keypoints(klines, asset_type='stock')
    lows = [p for p in result['points'] if p['type'] == 'price_low']

    assert any(p['date'] == _date(4) and p['price'] == 6 for p in lows)
    assert all(p['date'] != _date(2) for p in lows)


def test_latest_volume_peak_is_candidate_and_rolls_forward_when_volume_expands():
    base = []
    volumes = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
        120, 122, 124, 126, 128, 130, 132, 134, 136, 138,
        140, 145, 150, 155, 210,
    ]
    for i, vol in enumerate(volumes):
        base.append(_row(_date(i), 10 + i * 0.1, 9 + i * 0.1, vol))

    first = detect_pure_keypoints(base, asset_type='stock')
    assert (_date(24), 'volume_peak', 'candidate') in _types(first, 'volume_peak')
    assert (_date(24), 'volume_peak', 'confirmed') not in _types(first, 'volume_peak')

    rolled = base + [_row(_date(25), 12.6, 11.6, 260)]
    second = detect_pure_keypoints(rolled, asset_type='stock')

    assert (_date(24), 'volume_peak', 'confirmed') not in _types(second, 'volume_peak')
    assert (_date(25), 'volume_peak', 'candidate') in _types(second, 'volume_peak')


def test_latest_volume_trough_is_candidate_and_rolls_forward_when_volume_shrinks():
    base = []
    volumes = [
        300, 295, 290, 285, 280, 275, 270, 265, 260, 255,
        250, 245, 240, 235, 230, 225, 220, 215, 210, 205,
        200, 190, 180, 170, 90,
    ]
    for i, vol in enumerate(volumes):
        base.append(_row(_date(i), 10 + i * 0.1, 9 + i * 0.1, vol))

    first = detect_pure_keypoints(base, asset_type='stock')
    assert (_date(24), 'volume_trough', 'candidate') in _types(first, 'volume_trough')
    assert (_date(24), 'volume_trough', 'confirmed') not in _types(first, 'volume_trough')

    rolled = base + [_row(_date(25), 12.6, 11.6, 70)]
    second = detect_pure_keypoints(rolled, asset_type='stock')

    assert (_date(24), 'volume_trough', 'confirmed') not in _types(second, 'volume_trough')
    assert (_date(25), 'volume_trough', 'candidate') in _types(second, 'volume_trough')


def test_profiles_keep_same_definition_but_different_parameters():
    market = get_keypoint_profile('market')
    sector = get_keypoint_profile('sector')
    stock = get_keypoint_profile('stock')

    assert market.price_left > sector.price_left > stock.price_left
    assert market.volume_peak_ma_ratio < sector.volume_peak_ma_ratio < stock.volume_peak_ma_ratio


def _regression_rows():
    rows = []
    highs = [
        100, 102, 104, 106, 108, 110, 112, 114, 113, 112,
        111, 109, 107, 105, 103, 101, 99, 98, 100, 102,
        104, 108, 112, 116, 120, 118, 116, 114, 112, 110,
        108, 106, 104, 102, 100, 98, 96, 95, 97, 99,
        101, 103, 105, 107, 109, 111, 113, 115, 117, 119,
        121, 123, 125, 127, 129, 131, 133, 134, 135, 136,
    ]
    lows = [
        h - 5 for h in highs
    ]
    lows[17] = 90
    lows[37] = 88
    volumes = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
        120, 122, 124, 126, 128, 130, 132, 134, 136, 138,
        140, 230, 150, 145, 142, 140, 138, 136, 134, 132,
        130, 128, 126, 124, 122, 120, 118, 70, 115, 116,
        118, 120, 122, 124, 126, 128, 130, 132, 134, 136,
        138, 140, 142, 144, 146, 148, 150, 152, 154, 240,
    ]
    for i, (high, low, vol) in enumerate(zip(highs, lows, volumes)):
        rows.append(_row(_date(i), high, low, vol))
    return rows


KEYPOINT_REGRESSION_CASES = [
    {
        'name': 'market-科创50-like',
        'asset_type': 'market',
        'must_include': [
            (_date(7), 'price_high', 'confirmed'),
            (_date(17), 'price_low', 'confirmed'),
            (_date(21), 'volume_peak', 'confirmed'),
            (_date(37), 'volume_trough', 'confirmed'),
            (_date(59), 'price_high', 'candidate'),
        ],
        'must_exclude': [
            (_date(59), 'price_high', 'confirmed'),
        ],
    },
    {
        'name': 'sector-CPO-like',
        'asset_type': 'sector',
        'must_include': [
            (_date(7), 'price_high', 'confirmed'),
            (_date(17), 'price_low', 'confirmed'),
            (_date(21), 'volume_peak', 'confirmed'),
            (_date(59), 'volume_peak', 'candidate'),
        ],
        'must_exclude': [
            (_date(59), 'volume_peak', 'confirmed'),
        ],
    },
    {
        'name': 'stock-普冉股份-like',
        'asset_type': 'stock',
        'must_include': [
            (_date(7), 'price_high', 'confirmed'),
            (_date(17), 'price_low', 'confirmed'),
            (_date(21), 'volume_peak', 'confirmed'),
            (_date(37), 'volume_trough', 'confirmed'),
            (_date(59), 'volume_peak', 'candidate'),
        ],
        'must_exclude': [
            (_date(59), 'volume_peak', 'confirmed'),
        ],
    },
]


def test_keypoint_regression_cases_cover_market_sector_and_stock():
    rows = _regression_rows()

    for case in KEYPOINT_REGRESSION_CASES:
        result = detect_pure_keypoints(rows, asset_type=case['asset_type'])
        detected = set(_types(result))
        for expected in case['must_include']:
            assert expected in detected, f"{case['name']} missing {expected}"
        for unexpected in case['must_exclude']:
            assert unexpected not in detected, f"{case['name']} should exclude {unexpected}"


def test_user_confirmed_pure_keypoint_benchmark_v1():
    fixture_path = Path(__file__).parent / 'fixtures' / 'pure_keypoint_benchmark_v1.json'
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))

    assert fixture['version'] == 'pure-keypoint-benchmark-v1'
    assert fixture['algorithm_version'] == 'pure-keypoint-v1'

    for sample in fixture['samples']:
        result = detect_pure_keypoints(sample['rows'], asset_type=sample['asset_type'])
        actual = [_benchmark_point(point) for point in result['points']]

        assert actual == sample['expected_points'], (
            f"{sample['name']}({sample['slug']}) 关键点基准漂移："
            f"date_range={sample['date_range']}, source={sample['source']}"
        )

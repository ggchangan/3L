import pytest

from backend.services.market_service import _parse_json_output


def test_parse_json_output_ignores_progress_logs():
    output = 'loading...\n50% complete\n{"limit_up": [], "new_highs": []}\n'

    assert _parse_json_output(output) == {'limit_up': [], 'new_highs': []}


def test_parse_json_output_rejects_missing_json():
    with pytest.raises(ValueError, match='没有有效JSON'):
        _parse_json_output('loading...\nfailed\n')

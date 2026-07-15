import json
from concurrent.futures import ThreadPoolExecutor

from backend.services import source_health


def _use_temp_health(monkeypatch, tmp_path):
    path = tmp_path / 'source_health.json'
    monkeypatch.setattr(source_health, 'SOURCE_HEALTH_PATH', str(path))
    return path


def test_corrupt_health_file_does_not_break_reporting(monkeypatch, tmp_path):
    path = _use_temp_health(monkeypatch, tmp_path)
    path.write_text('{"sources": {}} trailing-data', encoding='utf-8')

    source_health.report_success('ths_sector')

    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['sources']['ths_sector']['status'] == 'UP'
    assert saved['sources']['ths_sector']['total_calls'] == 1


def test_concurrent_updates_keep_valid_json(monkeypatch, tmp_path):
    path = _use_temp_health(monkeypatch, tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: source_health.report_success('tushare'), range(40)))

    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['sources']['tushare']['total_calls'] == 40
    assert saved['sources']['tushare']['status'] == 'UP'

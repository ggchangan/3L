"""复盘归档读取 API 的日期校验、缺失语义与契约测试。"""

from backend.api import review


class FakeHandler:
    def __init__(self):
        self.payload = None
        self.status = 200

    def send_json(self, payload, status=200):
        self.payload = payload
        self.status = status


def test_review_archive_returns_normalized_archive(monkeypatch):
    monkeypatch.setattr(review, 'get_archive', lambda date: {'date': date, 'mainline': {'all_ranked': []}})
    handler = FakeHandler()

    review._handle_review_archive(handler, '/api/review/archive?date=2026-07-22')

    assert handler.status == 200
    assert handler.payload['date'] == '2026-07-22'
    assert handler.payload['response_meta']['source'] == 'archive'


def test_review_archive_rejects_non_iso_date_without_reading(monkeypatch):
    called = []
    monkeypatch.setattr(review, 'get_archive', called.append)
    handler = FakeHandler()

    review._handle_review_archive(handler, '/api/review/archive?date=../../private')

    assert handler.status == 400
    assert called == []


def test_review_archive_returns_404_for_missing_date(monkeypatch):
    monkeypatch.setattr(review, 'get_archive', lambda _date: None)
    handler = FakeHandler()

    review._handle_review_archive(handler, '/api/review/archive?date=2026-07-22')

    assert handler.status == 404
    assert handler.payload['date'] == '2026-07-22'

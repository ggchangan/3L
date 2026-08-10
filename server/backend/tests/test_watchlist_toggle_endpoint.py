#!/usr/bin/env python3
"""watchlist add/remove-stock 接口单测（mock 服务层，不触碰生产自选股）。

覆盖 2026-08-10 新增的 remove-stock 接口（复盘页领涨股复选框 toggle 用）：
- remove 移除成功
- remove 不存在幂等
- remove 缺少 code 报错
- add 重复幂等（回归保护）
"""
import sys, os, json, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class _FakeHandler:
    def __init__(self):
        self.data = None
        self.code = 200

    def send_json(self, data, code=200):
        self.data = data
        self.code = code


def _wl(stocks):
    return {'stocks': stocks, 'count': len(stocks), 'directions': []}


class TestRemoveStockEndpoint(unittest.TestCase):
    def setUp(self):
        from backend.api import watchlist as wl_api
        self.wl_api = wl_api

    def _call_remove(self, body):
        h = _FakeHandler()
        self.wl_api._handle_watchlist_remove_stock(h, '', json.dumps(body))
        return h

    def test_remove_success(self):
        """移除存在的股票 → success，保存剩余列表。"""
        stocks = [{'code': '000001', 'name': '平安银行', 'direction': '其他'},
                  {'code': '000002', 'name': '万科A', 'direction': '其他'}]
        saved = {}
        with mock.patch.object(self.wl_api, 'get_watchlist', return_value=_wl(stocks)), \
             mock.patch.object(self.wl_api, 'save_watchlist',
                               side_effect=lambda d: saved.update(d) or {'success': True}):
            h = self._call_remove({'code': '000001'})
        self.assertTrue(h.data['success'])
        self.assertEqual(len(saved['stocks']), 1)
        self.assertEqual(saved['stocks'][0]['code'], '000002')

    def test_remove_not_present_idempotent(self):
        """移除不存在的股票 → success 且不触发保存（幂等）。"""
        stocks = [{'code': '000001', 'name': '平安银行', 'direction': '其他'}]
        with mock.patch.object(self.wl_api, 'get_watchlist', return_value=_wl(stocks)), \
             mock.patch.object(self.wl_api, 'save_watchlist') as save:
            h = self._call_remove({'code': '999999'})
        self.assertTrue(h.data['success'])
        save.assert_not_called()

    def test_remove_missing_code(self):
        """缺少 code → success False。"""
        with mock.patch.object(self.wl_api, 'get_watchlist') as gw:
            h = self._call_remove({'name': 'x'})
        self.assertFalse(h.data['success'])
        gw.assert_not_called()

    def test_add_duplicate_idempotent(self):
        """add 已存在的股票 → success「已在自选股中」且不重复添加（回归保护）。"""
        stocks = [{'code': '000001', 'name': '平安银行', 'direction': '其他'}]
        with mock.patch.object(self.wl_api, 'get_watchlist', return_value=_wl(stocks)), \
             mock.patch.object(self.wl_api, 'save_watchlist') as save:
            h = _FakeHandler()
            self.wl_api._handle_watchlist_add_stock(h, '', json.dumps({'code': '000001', 'name': '平安银行'}))
        self.assertTrue(h.data['success'])
        self.assertIn('已在自选股中', h.data['msg'])
        save.assert_not_called()


if __name__ == '__main__':
    unittest.main()

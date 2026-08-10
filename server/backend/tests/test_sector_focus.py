#!/usr/bin/env python3
"""关注板块/概念 — 单元测试（MySQL watched_sectors 表）。

覆盖: repo CRUD / service toggle / 用户隔离 / sectors 列表 / 复盘匹配。
⚠️ DB 相关测试使用专用随机测试用户 + teardown 清理，绝不触碰 admin 数据。
"""
import sys, os, unittest
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.data_access.tushare_db import TushareDB
from backend.data_access.tushare_db import is_db_available

# 一个真实存在的行业/概念 ts_code（ths_index 表内），仅用于 toggle 校验分支
REAL_INDUSTRY_CODE = '881121.TI'   # 半导体
REAL_CONCEPT_CODE = '886108.TI'    # AI应用


@unittest.skipIf(not is_db_available(), 'MySQL 不可用')
class TestWatchedSectorsRepo(unittest.TestCase):
    def setUp(self):
        from backend.core import auth
        self._uid = 900000 + int(uuid4().hex[:6], 16) % 100000  # 随机 user_id（不建 users 行，仅隔离测试数据）
        self._db = TushareDB()
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])

    def tearDown(self):
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])

    def _assert_table(self):
        rows = self._db.execute_raw("SHOW COLUMNS FROM watched_sectors")
        cols = [r['Field'] for r in rows]
        for required in ('user_id', 'sector_type', 'ts_code', 'name'):
            self.assertIn(required, cols, f'缺少字段: {required}')

    def test_table_structure(self):
        self._assert_table()

    def test_add_and_get(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, get_watched_by_user)
        self.assertTrue(add_watched(self._uid, 'industry', REAL_INDUSTRY_CODE, '半导体'))
        rows = get_watched_by_user(self._uid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ts_code'], REAL_INDUSTRY_CODE)
        self.assertEqual(rows[0]['name'], '半导体')

    def test_add_duplicate_idempotent(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, get_watched_by_user)
        add_watched(self._uid, 'industry', REAL_INDUSTRY_CODE, '半导体')
        # 重复添加不报错、不产生重复行（INSERT IGNORE）
        self.assertFalse(add_watched(self._uid, 'industry', REAL_INDUSTRY_CODE, '半导体'))
        self.assertEqual(len(get_watched_by_user(self._uid)), 1)

    def test_remove(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, remove_watched, get_watched_by_user)
        add_watched(self._uid, 'concept', REAL_CONCEPT_CODE, 'AI应用')
        self.assertTrue(remove_watched(self._uid, REAL_CONCEPT_CODE))
        self.assertEqual(get_watched_by_user(self._uid), [])
        # 重复删除返回 False
        self.assertFalse(remove_watched(self._uid, REAL_CONCEPT_CODE))

    def test_user_isolation(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, get_watched_by_user)
        uid2 = self._uid + 1
        self._db.execute_raw("DELETE FROM watched_sectors WHERE user_id=%s", [uid2])
        try:
            add_watched(self._uid, 'industry', REAL_INDUSTRY_CODE, '半导体')
            add_watched(uid2, 'concept', REAL_CONCEPT_CODE, 'AI应用')
            mine = get_watched_by_user(self._uid)
            other = get_watched_by_user(uid2)
            self.assertEqual([r['ts_code'] for r in mine], [REAL_INDUSTRY_CODE])
            self.assertEqual([r['ts_code'] for r in other], [REAL_CONCEPT_CODE])
        finally:
            self._db.execute_raw("DELETE FROM watched_sectors WHERE user_id=%s", [uid2])


@unittest.skipIf(not is_db_available(), 'MySQL 不可用')
class TestSectorFocusService(unittest.TestCase):
    def setUp(self):
        from backend.core import auth
        self._uid = 900000 + int(uuid4().hex[:6], 16) % 100000
        self._db = TushareDB()
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])

    def tearDown(self):
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])

    def test_toggle_on_off(self):
        from backend.services.sector_focus_service import (
            toggle_watched_sector, get_watched_sectors)
        r1 = toggle_watched_sector(self._uid, 'industry', REAL_INDUSTRY_CODE)
        self.assertTrue(r1['success'])
        self.assertTrue(r1['watched'])
        self.assertEqual(r1['name'], '半导体')
        self.assertEqual(get_watched_sectors(self._uid)['industries'], ['半导体'])

        r2 = toggle_watched_sector(self._uid, 'industry', REAL_INDUSTRY_CODE)
        self.assertTrue(r2['success'])
        self.assertFalse(r2['watched'])
        self.assertEqual(get_watched_sectors(self._uid)['industries'], [])

    def test_toggle_invalid_code(self):
        from backend.services.sector_focus_service import toggle_watched_sector
        r = toggle_watched_sector(self._uid, 'industry', '999999.TI')
        self.assertFalse(r['success'])

    def test_toggle_type_mismatch(self):
        from backend.services.sector_focus_service import toggle_watched_sector
        # 概念 code 用 industry 类型提交 → 拒绝
        r = toggle_watched_sector(self._uid, 'industry', REAL_CONCEPT_CODE)
        self.assertFalse(r['success'])

    def test_get_all_sectors_structure(self):
        from backend.services.sector_focus_service import get_all_sectors
        data = get_all_sectors('industry', self._uid)
        self.assertGreater(data['count'], 100)
        self.assertGreater(data['in_mainline'], 0)
        first = data['sectors'][0]
        for key in ('name', 'ts_code', 'count', 'in_mainline', 'watched'):
            self.assertIn(key, first)
        self.assertFalse(first['watched'])  # 新用户无关注

    def test_build_watched_items_match_and_missing(self):
        from backend.services.sector_focus_service import (
            toggle_watched_sector, build_watched_sector_items)
        toggle_watched_sector(self._uid, 'industry', REAL_INDUSTRY_CODE)
        # 关注一个主线内没有的概念（随便一个真实存在的）
        toggle_watched_sector(self._uid, 'concept', REAL_CONCEPT_CODE)

        m = {'all_ranked': [
            {'name': '半导体', 'chg_20d': 5.5, 'chg_1d': 1.2, 'stage': '上涨',
             'vl_score': 3, 'strength_rank': 1},
        ]}
        cm = {'all_ranked': []}  # AI应用 不在概念榜 → matched=False
        items = build_watched_sector_items(m, cm, self._uid)
        self.assertEqual(len(items['industries']), 1)
        self.assertTrue(items['industries'][0]['matched'])
        self.assertEqual(items['industries'][0]['chg_20d'], 5.5)
        self.assertEqual(len(items['concepts']), 1)
        self.assertFalse(items['concepts'][0]['matched'])
        self.assertEqual(items['concepts'][0]['name'], 'AI应用')


if __name__ == '__main__':
    unittest.main()

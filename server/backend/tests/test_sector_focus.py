#!/usr/bin/env python3
"""关注板块/概念 — 单元测试（MySQL watched_sectors 表）。

覆盖: repo CRUD / service toggle / 用户隔离 / sectors 列表 / 复盘匹配 / 跨类型重名。
⚠️ DB 相关测试使用专用随机测试用户 + teardown 清理，绝不触碰 admin 数据。
"""
import sys, os, unittest
from uuid import uuid4
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.data_access.tushare_db import TushareDB
from backend.data_access.tushare_db import is_db_available


def _find_ths_code(db, sector_type, name_like=None):
    """动态查一个真实存在的 ths_index ts_code（避免硬编码依赖数据快照）。"""
    if name_like:
        rows = db.execute_raw(
            "SELECT ts_code, name FROM ths_index WHERE type=%s AND name LIKE %s LIMIT 1",
            [sector_type, f'%{name_like}%'])
    else:
        rows = db.execute_raw(
            "SELECT ts_code, name FROM ths_index WHERE type=%s LIMIT 1",
            [sector_type])
    if not rows:
        return None, None
    return rows[0]['ts_code'], rows[0]['name']


def _find_dup_name_code(db, name='家用电器'):
    """查跨类型重名板块（I/N 都存在），返回 (industry_code, concept_code) 或 (None, None)。"""
    i = db.execute_raw("SELECT ts_code FROM ths_index WHERE type='I' AND name=%s LIMIT 1", [name])
    n = db.execute_raw("SELECT ts_code FROM ths_index WHERE type='N' AND name=%s LIMIT 1", [name])
    if i and n:
        return i[0]['ts_code'], n[0]['ts_code']
    return None, None


@unittest.skipIf(not is_db_available(), 'MySQL 不可用')
class TestWatchedSectorsRepo(unittest.TestCase):
    def setUp(self):
        self._uid = 900000 + int(uuid4().hex[:6], 16) % 100000  # 随机 user_id（不建 users 行，仅隔离测试数据）
        self._db = TushareDB()
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])
        self._ind_code, self._ind_name = _find_ths_code(self._db, 'I', '半导体')
        self._con_code, self._con_name = _find_ths_code(self._db, 'N', 'AI应用')

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
        self.assertTrue(add_watched(self._uid, 'industry', self._ind_code, self._ind_name))
        rows = get_watched_by_user(self._uid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ts_code'], self._ind_code)
        self.assertEqual(rows[0]['name'], self._ind_name)

    def test_add_duplicate_idempotent(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, get_watched_by_user)
        add_watched(self._uid, 'industry', self._ind_code, self._ind_name)
        # 重复添加不报错、不产生重复行（INSERT IGNORE）
        self.assertFalse(add_watched(self._uid, 'industry', self._ind_code, self._ind_name))
        self.assertEqual(len(get_watched_by_user(self._uid)), 1)

    def test_remove(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, remove_watched, get_watched_by_user)
        add_watched(self._uid, 'concept', self._con_code, self._con_name)
        self.assertTrue(remove_watched(self._uid, self._con_code))
        self.assertEqual(get_watched_by_user(self._uid), [])
        # 重复删除返回 False
        self.assertFalse(remove_watched(self._uid, self._con_code))

    def test_db_error_propagates(self):
        """DB 写入失败必须上抛（防"假成功"），不吞异常。"""
        from backend.data_access.watched_sectors_repo import add_watched
        with mock.patch('backend.data_access.watched_sectors_repo._get_db',
                        side_effect=RuntimeError('MySQL down')):
            with self.assertRaises(RuntimeError):
                add_watched(self._uid, 'industry', self._ind_code, self._ind_name)

    def test_user_isolation(self):
        from backend.data_access.watched_sectors_repo import (
            add_watched, get_watched_by_user)
        uid2 = self._uid + 1
        self._db.execute_raw("DELETE FROM watched_sectors WHERE user_id=%s", [uid2])
        try:
            add_watched(self._uid, 'industry', self._ind_code, self._ind_name)
            add_watched(uid2, 'concept', self._con_code, self._con_name)
            mine = get_watched_by_user(self._uid)
            other = get_watched_by_user(uid2)
            self.assertEqual([r['ts_code'] for r in mine], [self._ind_code])
            self.assertEqual([r['ts_code'] for r in other], [self._con_code])
        finally:
            self._db.execute_raw("DELETE FROM watched_sectors WHERE user_id=%s", [uid2])


@unittest.skipIf(not is_db_available(), 'MySQL 不可用')
class TestSectorFocusService(unittest.TestCase):
    def setUp(self):
        self._uid = 900000 + int(uuid4().hex[:6], 16) % 100000
        self._db = TushareDB()
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])
        self._ind_code, self._ind_name = _find_ths_code(self._db, 'I', '半导体')
        self._con_code, self._con_name = _find_ths_code(self._db, 'N', 'AI应用')

    def tearDown(self):
        self._db.execute_raw(
            "DELETE FROM watched_sectors WHERE user_id=%s", [self._uid])

    def test_toggle_on_off(self):
        from backend.services.sector_focus_service import (
            toggle_watched_sector, get_watched_sectors)
        r1 = toggle_watched_sector(self._uid, 'industry', self._ind_code)
        self.assertTrue(r1['success'])
        self.assertTrue(r1['watched'])
        self.assertEqual(r1['name'], self._ind_name)
        # 响应只含 {success, watched, name, type}
        self.assertEqual(set(r1.keys()), {'success', 'watched', 'name', 'type'})
        self.assertEqual(get_watched_sectors(self._uid)['industries'], [self._ind_name])

        r2 = toggle_watched_sector(self._uid, 'industry', self._ind_code)
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
        r = toggle_watched_sector(self._uid, 'industry', self._con_code)
        self.assertFalse(r['success'])

    def test_toggle_db_error_not_fake_success(self):
        """DB 故障时 toggle 必须抛异常，不得返回假成功。"""
        from backend.services.sector_focus_service import toggle_watched_sector
        with mock.patch('backend.data_access.watched_sectors_repo.add_watched',
                        side_effect=RuntimeError('MySQL down')):
            with self.assertRaises(RuntimeError):
                toggle_watched_sector(self._uid, 'industry', self._ind_code)

    def test_dup_name_sector_isolated_by_type(self):
        """跨类型重名板块（如家用电器 I/N 都有）：关注互不干扰，分别匹配行业/概念榜。"""
        from backend.services.sector_focus_service import (
            toggle_watched_sector, get_watched_sectors, build_watched_sector_items)
        i_code, n_code = _find_dup_name_code(self._db)
        if not i_code:
            self.skipTest('当前 ths_index 无跨类型重名板块（家用电器）')

        toggle_watched_sector(self._uid, 'industry', i_code)
        toggle_watched_sector(self._uid, 'concept', n_code)
        watched = get_watched_sectors(self._uid)
        self.assertEqual(len(watched['industries']), 1)
        self.assertEqual(len(watched['concepts']), 1)
        self.assertEqual(watched['industries'][0], watched['concepts'][0])  # 同名

        # 行业榜含该名 → 命中 all_ranked；概念榜不含 → 走独立强度计算（有K线则 matched=True）
        m = {'all_ranked': [{'name': watched['industries'][0], 'chg_20d': 1.0, 'chg_1d': 0.5, 'stage': '上涨', 'vl_score': 1}]}
        cm = {'all_ranked': []}
        items = build_watched_sector_items(m, cm, self._uid)
        self.assertTrue(items['industries'][0]['matched'])
        self.assertEqual(items['industries'][0]['chg_20d'], 1.0)
        # 概念侧：条目存在且名字正确，不串到行业榜
        self.assertEqual(len(items['concepts']), 1)
        self.assertEqual(items['concepts'][0]['name'], watched['concepts'][0])
        # 若概念在 ths_daily 有K线，应有强度数据
        if items['concepts'][0].get('matched'):
            self.assertIn('data_date', items['concepts'][0])

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
            toggle_watched_sector, build_watched_sector_items, _compute_sector_strength)
        toggle_watched_sector(self._uid, 'industry', self._ind_code)
        toggle_watched_sector(self._uid, 'concept', self._con_code)

        m = {'all_ranked': [
            {'name': self._ind_name, 'chg_20d': 5.5, 'chg_1d': 1.2, 'stage': '上涨',
             'vl_score': 3, 'strength_rank': 1},
        ]}
        cm = {'all_ranked': []}  # 概念不在榜 → 走独立强度计算（AI应用在 ths_daily 有K线）
        items = build_watched_sector_items(m, cm, self._uid)
        self.assertEqual(len(items['industries']), 1)
        self.assertTrue(items['industries'][0]['matched'])
        self.assertEqual(items['industries'][0]['chg_20d'], 5.5)
        self.assertEqual(len(items['concepts']), 1)
        self.assertEqual(items['concepts'][0]['name'], self._con_name)
        self.assertTrue(items['concepts'][0]['matched'])  # 有K线 → 独立算强度
        self.assertIsNotNone(items['concepts'][0]['chg_20d'])
        self.assertIn('data_date', items['concepts'][0])

    def test_compute_strength_no_kline_matched_false(self):
        """ths_daily 完全无K线的关注项 → matched=False（前端显示暂无数据）。"""
        from backend.services.sector_focus_service import _compute_sector_strength
        item = _compute_sector_strength('不存在之板块XYZ', 'concept')
        self.assertFalse(item['matched'])
        self.assertEqual(item['name'], '不存在之板块XYZ')

    def test_watched_items_sorted_by_chg_20d(self):
        """关注列表排序与强度候选一致：chg_20d 降序，无20日数据排最后。"""
        from backend.services.sector_focus_service import (
            toggle_watched_sector, build_watched_sector_items)
        # 关注两个行业：A 在榜(chg_20d 高)，B 在榜(chg_20d 低)，C 不在榜(独立算)
        from backend.data_access.tushare_db import TushareDB
        db = TushareDB()
        rows = db.execute_raw(
            "SELECT ts_code, name FROM ths_index WHERE type='I' LIMIT 3")
        for tc, nm in [(r['ts_code'], r['name']) for r in rows[:3]]:
            toggle_watched_sector(self._uid, 'industry', tc)

        m = {'all_ranked': [
            {'name': rows[0]['name'], 'chg_20d': 10.0, 'chg_1d': 1.0, 'stage': '上涨', 'vl_score': 1},
            {'name': rows[1]['name'], 'chg_20d': -2.0, 'chg_1d': 0.1, 'stage': '下跌', 'vl_score': 0},
        ]}
        items = build_watched_sector_items(m, {'all_ranked': []}, self._uid)
        self.assertEqual(len(items['industries']), 3)
        # 前两个有 chg_20d → 降序；第三个无榜数据 → 独立计算或暂无数据，排在最后
        self.assertEqual(items['industries'][0]['name'], rows[0]['name'])
        self.assertEqual(items['industries'][1]['name'], rows[1]['name'])
        self.assertLessEqual(items['industries'][0]['chg_20d'], 10.0)
        self.assertGreaterEqual(items['industries'][0]['chg_20d'], items['industries'][1]['chg_20d'])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""关注板块每日增量更新保障 — 单元测试。

覆盖（2026-08-10 修复）：
1. update_sectors() 强制纳入用户关注的行业/概念（无论是否满足追踪门槛）
2. _fetch_ths_daily_klines_tushare 正确映射 Tushare 的 pct_change → pct_chg
3. backfill 脚本跳过 close 为 NULL 的脏行（Tushare 新概念早期数据质量）
4. _compute_sector_strength 查询过滤 close IS NOT NULL（防崩溃）

⚠️ 网络测试全部 mock，不触发真实 Tushare 代理调用。
"""
import sys, os, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestUpdateSectorsForcesWatched(unittest.TestCase):
    """update_sectors 必须把用户关注板块纳入 names_to_update。"""

    def _call_update_sectors(self, watched_rows):
        """执行 update_sectors，mock 掉所有外部依赖，捕获 names_to_update。"""
        import backend.core.update_stock_data as usd
        from backend.core import update_stock_data

        captured = {}

        def _fake_fetch(names, today):
            captured['names_to_update'] = list(names)
            # 返回足够覆盖量（行业+概念全部写成功）
            return (len(names), len(names))

        def _fake_coverage(names, target_date, optional_concepts=None):
            captured['optional_concepts'] = set(optional_concepts or [])
            ind_names = {n for n, k in names if k == 'industry'}
            con_names = {n for n, k in names if k == 'concept'}
            gate_concepts = con_names - set(optional_concepts or [])
            return {
                'ready': True,
                'industry': {'expected': len(ind_names), 'covered': len(ind_names),
                             'ratio': 1.0, 'ready': True, 'complete': True, 'missing': []},
                'concept': {'expected': len(gate_concepts), 'covered': len(gate_concepts),
                            'ratio': 1.0, 'ready': True, 'complete': True, 'missing': []},
                'missing': [],
                'optional_missing': [],
                'industry_names': sorted(ind_names),
                'concept_names': sorted(con_names),
                'bootstrap': False,
            }

        patches = [
            mock.patch('backend.data_access.data_source.get_last_completed_trading_day',
                       return_value='20260810'),
            mock.patch.object(update_stock_data, 'get_ths_index_names',
                              return_value=[('半导体', 'I'), ('银行', 'I')]),
            mock.patch.object(update_stock_data, 'get_tracked_concept_universe',
                              return_value={'names': {'AI视频'}, 'excluded': {},
                                            'reference_date': '20260810'}),
            mock.patch('backend.data_access.data_source.get_ths_index_canonical_names',
                       return_value={'886094.TI': {'name': '华为盘古', 'type': 'N'},
                                     '881121.TI': {'name': '半导体', 'type': 'I'},
                                     '886112.TI': {'name': 'MLCC概念', 'type': 'N'}}),
            mock.patch.object(update_stock_data, 'fetch_ths_daily_klines_akshare',
                              side_effect=_fake_fetch),
            mock.patch.object(update_stock_data, 'get_ths_daily_update_coverage',
                              side_effect=_fake_coverage),
            mock.patch.object(update_stock_data, 'retry_missing_ths_concepts',
                              return_value={'covered': 0, 'requested': 0, 'missing': []}),
            mock.patch.object(update_stock_data, 'save_ths_daily_update_confirmation',
                              return_value=None),
            mock.patch('backend.data_access.watched_sectors_repo.get_all_watched',
                       return_value=watched_rows),
        ]
        for p in patches:
            p.start()
        try:
            usd.update_sectors()
        finally:
            for p in patches:
                p.stop()
        captured['names_to_update'] = captured.get('names_to_update', [])
        return captured

    def test_watched_concept_not_in_tracked_is_included(self):
        """关注概念不在追踪集合（如华为盘古停更/新概念关联<6）也必须被拉取。"""
        watched = [
            {'id': 1, 'user_id': 1, 'sector_type': 'concept', 'ts_code': '886094.TI',
             'name': '华为盘古', 'created_at': None},
        ]
        captured = self._call_update_sectors(watched)
        names = captured['names_to_update']
        self.assertIn(('华为盘古', 'concept'), names)
        self.assertIn(('AI视频', 'concept'), names)  # 追踪概念仍在
        # C1: 不在追踪集合的关注概念 → optional（缺失不拉低门禁）
        self.assertIn('华为盘古', captured.get('optional_concepts', set()))
        self.assertNotIn('AI视频', captured.get('optional_concepts', set()))

    def test_watched_industry_is_included(self):
        """关注行业（已在行业全量中）不重复添加。"""
        watched = [
            {'id': 2, 'user_id': 1, 'sector_type': 'industry', 'ts_code': '881121.TI',
             'name': '半导体', 'created_at': None},
        ]
        captured = self._call_update_sectors(watched)
        names = captured['names_to_update']
        # 半导体已在 get_ths_index_names 的行业列表中 → 不重复
        self.assertEqual(names.count(('半导体', 'industry')), 1)

    def test_watched_new_concept_added(self):
        """关注新概念（如 MLCC概念，关联自选股<6 不在追踪）也被纳入。"""
        watched = [
            {'id': 3, 'user_id': 1, 'sector_type': 'concept', 'ts_code': '886112.TI',
             'name': 'MLCC概念', 'created_at': None},
        ]
        captured = self._call_update_sectors(watched)
        names = captured['names_to_update']
        self.assertIn(('MLCC概念', 'concept'), names)
        self.assertIn('MLCC概念', captured.get('optional_concepts', set()))

    def test_watched_uses_canonical_name_not_snapshot(self):
        """C2: watched_sectors.name 是过期快照时，以 ths_index canonical name 为准。"""
        watched = [
            {'id': 4, 'user_id': 1, 'sector_type': 'concept', 'ts_code': '886094.TI',
             'name': '旧名', 'created_at': None},  # 快照过期
        ]
        captured = self._call_update_sectors(watched)
        names = captured['names_to_update']
        # 用 canonical name '华为盘古' 而非快照 '旧名'
        self.assertIn(('华为盘古', 'concept'), names)
        self.assertNotIn(('旧名', 'concept'), names)

    def test_watched_unknown_ts_code_skipped(self):
        """C2: ths_index 无匹配的 ts_code 跳过（不进 names_to_update 也不进门禁）。"""
        watched = [
            {'id': 5, 'user_id': 1, 'sector_type': 'concept', 'ts_code': '999999.TI',
             'name': '幽灵概念', 'created_at': None},
        ]
        captured = self._call_update_sectors(watched)
        names = captured['names_to_update']
        self.assertNotIn(('幽灵概念', 'concept'), names)
        self.assertNotIn('幽灵概念', captured.get('optional_concepts', set()))

    def test_empty_watched_no_change(self):
        """无关注列表时行为不变（不破坏原有更新范围）。"""
        captured = self._call_update_sectors([])
        names = captured['names_to_update']
        self.assertIn(('AI视频', 'concept'), names)
        self.assertIn(('半导体', 'industry'), names)
        self.assertEqual(captured.get('optional_concepts', set()), set())


class TestThsDailyPctChgMapping(unittest.TestCase):
    """_fetch_ths_daily_klines_tushare 必须把 Tushare 的 pct_change 映射到 pct_chg。"""

    def test_pct_change_mapped_to_pct_chg(self):
        from backend.data_access import data_source as ds

        fake_rows = [
            {'ts_code': '886112.TI', 'trade_date': '20260810', 'open': 1, 'high': 2,
             'low': 0.5, 'close': 1.5, 'pre_close': 1.4, 'change': 0.1,
             'pct_change': 7.14, 'vol': 100, 'amount': None},
        ]
        fake_db = mock.Mock()
        fake_db.execute_raw.return_value = [
            {'ts_code': '886112.TI', 'name': 'MLCC概念'},
        ]
        fake_db.upsert_many_from_dicts.return_value = 1

        with mock.patch.object(ds, '_call_ths_proxy', return_value=fake_rows):
            written, requested = ds._fetch_ths_daily_klines_tushare(
                fake_db, [('MLCC概念', 'concept')], '20260810')

        self.assertEqual(written, 1)
        self.assertEqual(requested, 1)
        written_records = fake_db.upsert_many_from_dicts.call_args[0][1]
        self.assertEqual(written_records[0]['pct_chg'], 7.14)

    def test_pct_chg_present_when_pct_change_absent(self):
        """代理返回 pct_chg 而非 pct_change 时兼容（不崩）。"""
        from backend.data_access import data_source as ds

        fake_rows = [
            {'ts_code': '886112.TI', 'trade_date': '20260810', 'open': 1, 'high': 2,
             'low': 0.5, 'close': 1.5, 'pre_close': 1.4, 'change': 0.1,
             'pct_chg': 3.33, 'vol': 100, 'amount': None},
        ]
        fake_db = mock.Mock()
        fake_db.execute_raw.return_value = [
            {'ts_code': '886112.TI', 'name': 'MLCC概念'},
        ]
        fake_db.upsert_many_from_dicts.return_value = 1

        with mock.patch.object(ds, '_call_ths_proxy', return_value=fake_rows):
            written, _ = ds._fetch_ths_daily_klines_tushare(
                fake_db, [('MLCC概念', 'concept')], '20260810')

        written_records = fake_db.upsert_many_from_dicts.call_args[0][1]
        self.assertEqual(written_records[0]['pct_chg'], 3.33)


class TestBackfillSkipsNullClose(unittest.TestCase):
    """backfill 脚本必须跳过 close 为 NULL/<=0 的行 + 校验响应行 ts_code。"""

    def _load_mod(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'backfill_watched_ths_daily',
            os.path.join(os.path.dirname(__file__), '..', '..', 'scripts',
                         'backfill_watched_ths_daily.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_null_close_rows_skipped(self):
        mod = self._load_mod()

        fake_rows = [
            {'ts_code': '886111.TI', 'trade_date': '20260702', 'open': 917.19,
             'high': 947.05, 'low': 887.98, 'close': None, 'pre_close': 973.43,
             'change': None, 'pct_change': -7.47, 'vol': 7184.6},
            {'ts_code': '886111.TI', 'trade_date': '20260703', 'open': 890.8,
             'high': 896.74, 'low': 861.64, 'close': 900.68, 'pre_close': 900.68,
             'change': None, 'pct_change': 0.0, 'vol': 6517.27},
        ]
        fake_db = mock.Mock()

        with mock.patch.object(mod, '_call_ths_proxy', return_value=fake_rows):
            result = mod.backfill_one(fake_db, '886111.TI', '玻璃基板',
                                      '20240101', '20260810')

        # close=NULL 的行被跳过，只写入 1 条
        written_records = fake_db.upsert_many_from_dicts.call_args[0][1]
        self.assertEqual(len(written_records), 1)
        self.assertEqual(written_records[0]['trade_date'], '20260703')
        # pct_change 映射为 pct_chg
        self.assertEqual(written_records[0]['pct_chg'], 0.0)
        self.assertIn('range', result)

    def test_close_zero_rows_skipped(self):
        """W3: close=0 的脏行同样跳过（与直连路径 OHLC<=0 拒绝口径一致）。"""
        mod = self._load_mod()

        fake_rows = [
            {'ts_code': '886111.TI', 'trade_date': '20260702', 'open': 917.19,
             'high': 947.05, 'low': 887.98, 'close': 0, 'pre_close': 973.43,
             'change': None, 'pct_change': -7.47, 'vol': 7184.6},
        ]
        fake_db = mock.Mock()

        with mock.patch.object(mod, '_call_ths_proxy', return_value=fake_rows):
            mod.backfill_one(fake_db, '886111.TI', '玻璃基板', '20240101', '20260810')

        self.assertFalse(fake_db.upsert_many_from_dicts.called,
                         'close=0 的行不应写入')

    def test_wrong_ts_code_rows_skipped(self):
        """W3: 代理返回其他板块的行（忽略 ts_code 过滤）必须拒绝，防全市场误写。"""
        mod = self._load_mod()

        fake_rows = [
            {'ts_code': '885959.TI', 'trade_date': '20260702', 'open': 1,
             'high': 2, 'low': 0.5, 'close': 1.5, 'pre_close': 1.4,
             'change': None, 'pct_change': 7.14, 'vol': 100},
            {'ts_code': '886111.TI', 'trade_date': '20260703', 'open': 890.8,
             'high': 896.74, 'low': 861.64, 'close': 900.68, 'pre_close': 900.68,
             'change': None, 'pct_change': 0.0, 'vol': 6517.27},
        ]
        fake_db = mock.Mock()

        with mock.patch.object(mod, '_call_ths_proxy', return_value=fake_rows):
            mod.backfill_one(fake_db, '886111.TI', '玻璃基板', '20240101', '20260810')

        written_records = fake_db.upsert_many_from_dicts.call_args[0][1]
        self.assertEqual(len(written_records), 1)
        self.assertEqual(written_records[0]['ts_code'], '886111.TI')


class TestCoverageOptionalConcepts(unittest.TestCase):
    """C1: coverage 门禁必须支持 optional_concepts——尽力而为的概念缺失不拉低门禁。"""

    def _call(self, names_to_update, covered_rows, optional=None, confirmation=None):
        from backend.data_access import data_source as ds

        fake_db = mock.Mock()
        fake_db.execute_raw.return_value = covered_rows
        # 非 bootstrap：行业有确认基线（避免 industry['ready']=False 干扰）
        ds.get_ths_daily_update_confirmation = mock.Mock(return_value=confirmation or {
            'industry_names': ['半导体'], 'concept_names': [],
        })
        with mock.patch.object(ds, '_get_tushare_db', return_value=fake_db):
            return ds.get_ths_daily_update_coverage(
                names_to_update, '20260810',
                optional_concepts=optional or set(),
            )

    def test_optional_concept_missing_does_not_fail_gate(self):
        """关注概念缺失（停更无当日数据）不拉低门禁，仅在 optional_missing 记录。"""
        names_to_update = [
            ('半导体', 'industry'),
            ('AI视频', 'concept'),          # 追踪概念（必须覆盖）
            ('华为盘古', 'concept'),        # 关注概念（尽力而为，停更无当日数据）
        ]
        covered_rows = [
            {'name': '半导体', 'type': 'I'},
            {'name': 'AI视频', 'type': 'N'},
        ]
        coverage = self._call(names_to_update, covered_rows,
                              optional={'华为盘古'})

        self.assertTrue(coverage['ready'])
        self.assertEqual(coverage['concept']['missing'], [])
        self.assertEqual(coverage['optional_missing'], ['华为盘古'])
        # 门禁分母不含 optional 概念
        self.assertEqual(coverage['concept']['expected'], 1)

    def test_gate_concept_missing_still_fails(self):
        """追踪概念缺失仍必须卡门禁（保护主线完整性）。"""
        names_to_update = [
            ('半导体', 'industry'),
            ('AI视频', 'concept'),
        ]
        covered_rows = [{'name': '半导体', 'type': 'I'}]  # AI视频 当日无数据
        coverage = self._call(names_to_update, covered_rows,
                              optional=set())

        self.assertFalse(coverage['ready'])
        self.assertIn('AI视频', coverage['concept']['missing'])

    def test_no_optional_keeps_legacy_behavior(self):
        """不传 optional_concepts 时行为与旧版一致（回归保护）。"""
        names_to_update = [
            ('半导体', 'industry'),
            ('AI视频', 'concept'),
        ]
        covered_rows = [
            {'name': '半导体', 'type': 'I'},
            {'name': 'AI视频', 'type': 'N'},
        ]
        coverage = self._call(names_to_update, covered_rows)

        self.assertTrue(coverage['ready'])
        self.assertEqual(coverage.get('optional_missing'), [])
        # 概念门禁按全部 requested 统计（legacy 语义）
        self.assertEqual(coverage['concept']['expected'], 1)


class TestComputeSectorStrengthNullClose(unittest.TestCase):
    """_compute_sector_strength 查询必须过滤 close IS NULL + 补全 OHLCV 结构。"""

    def test_query_filters_null_close(self):
        from backend.services import sector_focus_service as sfs

        class _FakeCursor:
            def __init__(self):
                self.results = [
                    {'ts_code': '886094.TI'},                      # 第一次 fetchone
                    [{'trade_date': '20260809', 'open': 99.0, 'high': 101.0,
                      'low': 98.0, 'close': 100.0, 'vol': 1000},
                     {'trade_date': '20260810', 'open': 100.0, 'high': 102.0,
                      'low': 99.0, 'close': 101.0, 'vol': 2000}],   # 第二次 fetchall
                ]
                self.sqls = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                self.sqls.append(sql)
                return None

            def fetchone(self):
                return self.results[0]

            def fetchall(self):
                return self.results[1]

        fake_cursor = _FakeCursor()
        fake_conn = mock.MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        fake_db = mock.Mock(_get_conn=lambda: fake_conn)

        with mock.patch.object(sfs, '_get_db', return_value=fake_db):
            result = sfs._compute_sector_strength('华为盘古', 'concept')

        self.assertEqual(result['name'], '华为盘古')
        self.assertAlmostEqual(result['chg_1d'], 1.0, places=5)

        # 断言 SQL 包含 close IS NOT NULL 过滤 + OHLCV 字段
        kline_sql = [s for s in fake_cursor.sqls if 'FROM ths_daily' in s]
        self.assertTrue(kline_sql, '应有 ths_daily 查询')
        self.assertIn('close IS NOT NULL', kline_sql[0])
        self.assertIn('vol', kline_sql[0])


if __name__ == '__main__':
    unittest.main()

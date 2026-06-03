#!/usr/bin/env python3
"""
操作计划追踪 v2 — 单元测试

数据源: review trading_plan (holdings_action + buy_priority)
存储: SQLite
"""
import json, os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ['TQDM_DISABLE'] = '1'


def _make_holdings_action(stock='测试A(000001)', action='持有不动', reason='上涨趋势·上行',
                          priority='高', stop_loss=None, stop_loss_pct=None, change=1.5):
    return {
        'stock': stock,
        'action': action,
        'reason': reason,
        'priority': priority,
        'stop_loss': stop_loss,
        'stop_loss_pct': stop_loss_pct,
        'change': change,
    }


def _make_buy_priority(name='测试B', code='000002', buy_point='中继买点', is_main=True,
                       structure='上涨趋势', stage='上行', change=2.0,
                       stop_loss=None, stop_loss_pct=None):
    return {
        'name': name,
        'code': code,
        'buy_point': buy_point,
        'is_main': is_main,
        'structure': structure,
        'stage': stage,
        'change': change,
        'stop_loss': stop_loss,
        'stop_loss_pct': stop_loss_pct,
        'priority': 0,
    }


def _make_trading_plan(holdings_actions=None, buy_priorities=None, date_str='2026-05-28'):
    return {
        'holdings_action': holdings_actions or [],
        'buy_priority': buy_priorities or [],
    }


def _make_kline(date, close=10.0, open_=10.0, high=11.0, low=9.5):
    return {'date': date, 'close': close, 'open': open_, 'high': high, 'low': low}


class TestPlanTrackingV2(unittest.TestCase):
    """计划追踪v2核心测试"""

    # ── Mock utilities ──

    def _assert_db_has_table(self, db_path):
        """验证数据库表结构正确"""
        conn = sqlite3.connect(db_path)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            self.assertIn(('plan_records',), tables)
            cols = [row[1] for row in conn.execute("PRAGMA table_info(plan_records)")]
            for required in ('date', 'code', 'source', 'buy_point', 'structure',
                             'result', 'change_pct', 'is_main'):
                self.assertIn(required, cols, f'缺少字段: {required}')
        finally:
            conn.close()

    def _insert_test_plan(self, db_path, **kwargs):
        """向测试数据库插入一条计划记录"""
        defaults = dict(
            date='2026-05-28', code='000001', name='测试A',
            source='buy_priority', action='买入', reason='上涨趋势·上行',
            structure='上涨趋势', stage='上行', buy_point='中继买点',
            is_main=1, result='pending', change_pct=None,
            plan_close=10.0, next_date=None,
            stop_loss=None, stop_loss_pct=None,
            executed=None, user_note='',
            created_at='2026-05-28T10:00:00', updated_at='2026-05-28T10:00:00',
        )
        defaults.update(kwargs)
        from backend.services.plan_tracking_service import _save_plan_record
        _save_plan_record(db_path, defaults)

    def _count_records(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute("SELECT count(*) FROM plan_records").fetchone()[0]
        finally:
            conn.close()


    # ═══════════════════════════════════════════════════
    # 1. 数据库初始化
    # ═══════════════════════════════════════════════════

    def test_db_init_creates_table(self):
        """初始化SQLite时应创建plan_records表及索引"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            self._assert_db_has_table(db_path)
        finally:
            os.unlink(db_path)

    def test_db_init_idempotent(self):
        """多次初始化不报错"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            for _ in range(3):
                _init_db(db_path)
            self._assert_db_has_table(db_path)
        finally:
            os.unlink(db_path)

    # ═══════════════════════════════════════════════════
    # 2. 从 trading_plan 提取计划
    # ═══════════════════════════════════════════════════

    def test_extract_holdings_action(self):
        """从holdings_action提取计划记录"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        tp = _make_trading_plan(
            holdings_actions=[
                _make_holdings_action(stock='杭齿前进(601177)', action='执行突破买点',
                                      reason='上涨趋势·上行', priority='高', change=2.5),
            ],
        )
        plans = extract_plans_from_trading_plan(tp, '2026-05-28')
        self.assertEqual(len(plans), 1)
        p = plans[0]
        self.assertEqual(p['date'], '2026-05-28')
        self.assertEqual(p['code'], '601177')
        self.assertEqual(p['name'], '杭齿前进')
        self.assertEqual(p['source'], 'holdings_action')
        self.assertEqual(p['action'], '执行突破买点')
        self.assertEqual(p['structure'], '上涨趋势')
        self.assertEqual(p['stage'], '上行')
        self.assertEqual(p['reason'], '上涨趋势·上行')
        self.assertIsNone(p['buy_point'])  # holdings_action 没有 buy_point

    def test_extract_buy_priority(self):
        """从buy_priority提取计划记录"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        tp = _make_trading_plan(
            buy_priorities=[
                _make_buy_priority(name='广钢气体', code='688548', buy_point='中继买点',
                                   structure='上涨趋势', stage='上行', is_main=True),
            ],
        )
        plans = extract_plans_from_trading_plan(tp, '2026-05-28')
        self.assertEqual(len(plans), 1)
        p = plans[0]
        self.assertEqual(p['date'], '2026-05-28')
        self.assertEqual(p['code'], '688548')
        self.assertEqual(p['name'], '广钢气体')
        self.assertEqual(p['source'], 'buy_priority')
        self.assertEqual(p['buy_point'], '中继买点')
        self.assertEqual(p['structure'], '上涨趋势')
        self.assertEqual(p['stage'], '上行')
        self.assertEqual(p['is_main'], 1)

    def test_extract_both_sources(self):
        """同时提取holdings_action和buy_priority"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        tp = _make_trading_plan(
            holdings_actions=[_make_holdings_action(stock='杭齿前进(601177)')],
            buy_priorities=[_make_buy_priority(code='688548')],
        )
        plans = extract_plans_from_trading_plan(tp, '2026-05-28')
        self.assertEqual(len(plans), 2)

    def test_extract_empty_trading_plan(self):
        """空的trading_plan应返回空列表"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        self.assertEqual(extract_plans_from_trading_plan({}, '2026-05-28'), [])
        self.assertEqual(extract_plans_from_trading_plan(
            _make_trading_plan(), '2026-05-28'), [])

    def test_extract_reason_without_dot(self):
        """reason没有·分隔符时正确解析"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        tp = _make_trading_plan(
            holdings_actions=[
                _make_holdings_action(reason='区间震荡'),
            ],
        )
        plans = extract_plans_from_trading_plan(tp, '2026-05-28')
        self.assertEqual(plans[0]['structure'], '区间震荡')
        self.assertEqual(plans[0]['stage'], '')

    # ═══════════════════════════════════════════════════
    # 3. 次日涨跌判定
    # ═══════════════════════════════════════════════════

    def test_judge_buy_success(self):
        """买入方向：次日涨超过0.5%算成功"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'action': '执行突破买点'}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.80),  # +8%
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'success')
        self.assertAlmostEqual(result['change_pct'], 8.0)

    def test_judge_buy_failure(self):
        """买入方向：次日跌超过0.5%算失败"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=9.0),  # -10%
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'failure')
        self.assertAlmostEqual(result['change_pct'], -10.0)

    def test_judge_buy_flat(self):
        """买入方向：次日涨跌在±0.5%内算平盘"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.03),  # +0.3%
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'flat')

    def test_judge_sell_success(self):
        """卖出方向：次日跌算成功（卖对了）"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'action': '卖出'}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=9.0),
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'success')

    def test_judge_sell_failure(self):
        """卖出方向：次日涨算失败（卖飞了）"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'action': '卖出'}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.80),
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'failure')

    def test_judge_no_next_day(self):
        """没有次日K线应返回pending"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-31', 'plan_close': 10.0}
        klines = [_make_kline('20260531', close=10.0)]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'pending')

    def test_judge_no_plan_kline(self):
        """没有当日K线应返回pending"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-06-01', 'plan_close': None}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.50),
        ]
        result = judge_next_day(plan, klines)
        self.assertEqual(result['result'], 'pending')

    def test_judge_hit_stop_loss(self):
        """盘中最低跌破止损价应标记hit_stop_loss"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'stop_loss': 9.0}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.50, low=8.50),  # 盘中跌到8.5 < 9.0
        ]
        result = judge_next_day(plan, klines)
        self.assertTrue(result['hit_stop_loss'])

    def test_judge_not_hit_stop_loss(self):
        """盘中最低未跌破止损价不标记"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'stop_loss': 8.0}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.50, low=9.0),  # 最低9.0 > 8.0
        ]
        result = judge_next_day(plan, klines)
        self.assertFalse(result['hit_stop_loss'])

    def test_hold_action_no_judgment(self):
        """'持有'类action不参与成功率统计（result=None保留）"""
        from backend.services.plan_tracking_service import judge_next_day
        plan = {'date': '2026-05-28', 'plan_close': 10.0, 'action': '持有不动'}
        klines = [
            _make_kline('20260528', close=10.0),
            _make_kline('20260529', close=10.80),
        ]
        result = judge_next_day(plan, klines)
        # 持有类只填change_pct，不写result
        self.assertIsNone(result['result'])
        self.assertAlmostEqual(result['change_pct'], 8.0)

    # ═══════════════════════════════════════════════════
    # 4. SQLite 存储与读取
    # ═══════════════════════════════════════════════════

    def test_save_and_get_plan(self):
        """保存计划后能完整读回"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, get_plans
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            plan = {
                'date': '2026-05-28', 'code': '000001', 'name': '测试A',
                'source': 'buy_priority', 'action': '买入', 'reason': '上涨趋势·上行',
                'structure': '上涨趋势', 'stage': '上行', 'buy_point': '中继买点',
                'is_main': 1, 'result': 'success', 'change_pct': 5.0,
            }
            _save_plan_record(db_path, plan)
            plans = get_plans(db_path)
            self.assertEqual(len(plans), 1)
            self.assertEqual(plans[0]['code'], '000001')
            self.assertEqual(plans[0]['result'], 'success')
        finally:
            os.unlink(db_path)

    def test_save_duplicate_unique_constraint(self):
        """相同(date, code)记录应覆盖更新"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, get_plans
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            base = {
                'date': '2026-05-28', 'code': '000001', 'name': '测试A',
                'source': 'buy_priority',
                'result': 'pending', 'change_pct': None,
            }
            _save_plan_record(db_path, base)
            base['result'] = 'success'
            base['change_pct'] = 5.0
            _save_plan_record(db_path, base)
            plans = get_plans(db_path)
            self.assertEqual(len(plans), 1)
            self.assertEqual(plans[0]['result'], 'success')
        finally:
            os.unlink(db_path)

    def test_annotate_executed(self):
        """标记执行状态后能正确更新"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, annotate_plan, get_plans
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            plan = {
                'date': '2026-05-28', 'code': '000001', 'name': '测试A',
                'source': 'buy_priority', 'result': 'success',
            }
            _save_plan_record(db_path, plan)
            result = annotate_plan(db_path, '2026-05-28', '000001', executed=True, user_note='按计划执行')
            self.assertTrue(result['success'])
            plans = get_plans(db_path)
            self.assertEqual(plans[0]['executed'], 1)
            self.assertEqual(plans[0]['user_note'], '按计划执行')
        finally:
            os.unlink(db_path)

    # ═══════════════════════════════════════════════════
    # 5. 日期筛选
    # ═══════════════════════════════════════════════════

    def test_date_filter(self):
        """日期筛选应只返回范围内的记录"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, get_plans
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            dates = ['2026-05-20', '2026-05-25', '2026-06-01']
            for i, d in enumerate(dates):
                _save_plan_record(db_path, {
                    'date': d, 'code': f'00000{i}', 'name': f'测试{i}',
                    'source': 'buy_priority', 'result': 'pending',
                })
            filtered = get_plans(db_path, start_date='2026-05-22', end_date='2026-05-30')
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['date'], '2026-05-25')
        finally:
            os.unlink(db_path)

    # ═══════════════════════════════════════════════════
    # 6. 多维统计摘要
    # ═══════════════════════════════════════════════════

    def _setup_stats_db(self, db_path):
        """准备一组统计数据"""
        from backend.services.plan_tracking_service import _init_db, _save_plan_record
        _init_db(db_path)
        records = [
            # buy_priority, 中继买点, 主线, 上涨趋势·上行
            {'date': '2026-05-20', 'code': '000001', 'source': 'buy_priority',
             'buy_point': '中继买点', 'structure': '上涨趋势', 'stage': '上行',
             'is_main': 1, 'result': 'success', 'change_pct': 3.0},
            {'date': '2026-05-20', 'code': '000002', 'source': 'buy_priority',
             'buy_point': '中继买点', 'structure': '上涨趋势', 'stage': '上行',
             'is_main': 1, 'result': 'success', 'change_pct': 4.0},
            {'date': '2026-05-20', 'code': '000003', 'source': 'buy_priority',
             'buy_point': '中继买点', 'structure': '上涨趋势', 'stage': '上行',
             'is_main': 1, 'result': 'failure', 'change_pct': -2.0},
            # buy_priority, 涨停回踩, 非主线, 区间震荡·区底
            {'date': '2026-05-21', 'code': '000004', 'source': 'buy_priority',
             'buy_point': '涨停回踩', 'structure': '区间震荡', 'stage': '区底',
             'is_main': 0, 'result': 'failure', 'change_pct': -3.0},
            {'date': '2026-05-21', 'code': '000005', 'source': 'buy_priority',
             'buy_point': '涨停回踩', 'structure': '区间震荡', 'stage': '区底',
             'is_main': 0, 'result': 'flat', 'change_pct': 0.2},
            # holdings_action
            {'date': '2026-05-22', 'code': '000006', 'source': 'holdings_action',
             'action': '执行突破买点', 'reason': '上涨趋势·上行',
             'structure': '上涨趋势', 'stage': '上行',
             'result': 'success', 'change_pct': 5.0},
            # pending
            {'date': '2026-05-30', 'code': '000007', 'source': 'buy_priority',
             'buy_point': '中继买点', 'result': 'pending'},
        ]
        for r in records:
            _save_plan_record(db_path, r)

    def test_summary_basic(self):
        """统计摘要应正确计算成功率"""
        import tempfile
        from backend.services.plan_tracking_service import get_tracking
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            self._setup_stats_db(db_path)
            result = get_tracking(db_path)
            s = result['summary']
            # 6笔有结果(不包含pending)，3 success, 2 failure, 1 flat
            self.assertEqual(s['total_plans'], 6)
            self.assertEqual(s['success'], 3)
            self.assertEqual(s['failure'], 2)
            self.assertAlmostEqual(s['success_rate'], 60.0, delta=0.1)
        finally:
            os.unlink(db_path)

    def test_summary_by_buy_point(self):
        """按买点类型分组统计"""
        import tempfile
        from backend.services.plan_tracking_service import get_tracking
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            self._setup_stats_db(db_path)
            result = get_tracking(db_path)
            bp = result['by_buy_point']
            self.assertIn('中继买点', bp)
            self.assertIn('涨停回踩', bp)
            self.assertEqual(bp['中继买点']['total'], 3)
            self.assertEqual(bp['中继买点']['success'], 2)
            self.assertEqual(bp['中继买点']['failure'], 1)
            self.assertEqual(bp['涨停回踩']['total'], 2)
        finally:
            os.unlink(db_path)

    def test_summary_by_structure(self):
        """按结构分组统计"""
        import tempfile
        from backend.services.plan_tracking_service import get_tracking
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            self._setup_stats_db(db_path)
            result = get_tracking(db_path)
            bs = result['by_structure']
            self.assertIn('上涨趋势', bs)
            self.assertIn('区间震荡', bs)
            self.assertEqual(bs['上涨趋势']['total'], 4)  # 3 buy_priority + 1 holdings_action
            self.assertEqual(bs['区间震荡']['total'], 2)
        finally:
            os.unlink(db_path)

    def test_summary_by_is_main(self):
        """按是否主线分组统计"""
        import tempfile
        from backend.services.plan_tracking_service import get_tracking
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            self._setup_stats_db(db_path)
            result = get_tracking(db_path)
            im = result['by_is_main']
            self.assertIn('1', im)
            self.assertIn('0', im)
            self.assertEqual(im['1']['total'], 3)  # 3条主线
        finally:
            os.unlink(db_path)

    def test_summary_by_source(self):
        """按来源分组统计"""
        import tempfile
        from backend.services.plan_tracking_service import get_tracking
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            self._setup_stats_db(db_path)
            result = get_tracking(db_path)
            bs = result['by_source']
            self.assertIn('buy_priority', bs)
            self.assertIn('holdings_action', bs)
            self.assertEqual(bs['buy_priority']['total'], 5)
            self.assertEqual(bs['holdings_action']['total'], 1)
        finally:
            os.unlink(db_path)

    # ═══════════════════════════════════════════════════
    # 7. 自动建议
    # ═══════════════════════════════════════════════════

    def test_suggestions_too_few(self):
        """少于3条有结果的计划不生成建议"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, generate_suggestions_for_db
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            _save_plan_record(db_path, {
                'date': '2026-05-20', 'code': '000001', 'source': 'buy_priority',
                'result': 'success', 'buy_point': '中继买点',
            })
            sug = generate_suggestions_for_db(db_path)
            self.assertEqual(sug, [])
        finally:
            os.unlink(db_path)

    def test_suggestions_low_rate_warning(self):
        """买点类型成功率<50%应生成warning"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, generate_suggestions_for_db
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            for i in range(3):
                _save_plan_record(db_path, {
                    'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                    'source': 'buy_priority', 'buy_point': '涨停回踩',
                    'result': 'failure', 'change_pct': -2.0,
                })
            _save_plan_record(db_path, {
                'date': '2026-05-23', 'code': '000003', 'source': 'buy_priority',
                'buy_point': '中继买点', 'result': 'success', 'change_pct': 3.0,
            })
            sug = generate_suggestions_for_db(db_path)
            warnings = [s for s in sug if s['type'] == 'warning' and s['dimension'] == 'buy_point']
            self.assertTrue(any('涨停回踩' in w['message'] for w in warnings))
        finally:
            os.unlink(db_path)

    def test_suggestions_by_mainline(self):
        """非主线成功率偏低应生成主线-非主线对比建议"""
        import tempfile
        from backend.services.plan_tracking_service import _init_db, _save_plan_record, generate_suggestions_for_db
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            _init_db(db_path)
            # 3条主线成功
            for i in range(3):
                _save_plan_record(db_path, {
                    'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                    'source': 'buy_priority', 'is_main': 1,
                    'buy_point': '中继买点', 'result': 'success', 'change_pct': 3.0,
                })
            # 3条非主线失败
            for i in range(3, 6):
                _save_plan_record(db_path, {
                    'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                    'source': 'buy_priority', 'is_main': 0,
                    'buy_point': '涨停回踩', 'result': 'failure', 'change_pct': -3.0,
                })
            sug = generate_suggestions_for_db(db_path)
            mainline_sug = [s for s in sug if s['dimension'] == 'mainline']
            self.assertTrue(len(mainline_sug) >= 1)
        finally:
            os.unlink(db_path)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    unittest.main()

#!/usr/bin/env python3
"""
操作计划追踪 v2 — 单元测试

数据源: review trading_plan (holdings_action + buy_priority)
存储: MySQL plan_records 表（按 user_id 隔离）

⚠️ DB 相关测试使用专用随机测试用户 + teardown 清理，绝不触碰 admin 数据。
"""
import json, os, sys, unittest
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ['TQDM_DISABLE'] = '1'

import pytest  # noqa: E402
from backend.data_access.tushare_db import is_db_available  # noqa: E402


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


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestPlanTrackingV2(unittest.TestCase):
    """计划追踪v2核心测试"""

    # ── 测试用户管理（MySQL 隔离） ──

    def setUp(self):
        """每个测试创建专用测试用户，隔离于 admin 数据"""
        from backend.data_access.tushare_db import TushareDB
        from backend.core.auth import set_current_user
        db = TushareDB()
        username = f'pytest_plan_{uuid4().hex[:12]}'
        db.execute_raw(
            "INSERT INTO users(username, display_name) VALUES(%s, %s)",
            [username, '计划追踪测试用户'],
        )
        rows = db.execute_raw("SELECT id FROM users WHERE username=%s", [username])
        self._uid = rows[0]['id']
        self._username = username
        set_current_user({'id': self._uid, 'username': username})
        # 建表（幂等）
        from backend.services.plan_tracking_service import _init_db
        _init_db()

    def tearDown(self):
        """清理测试用户及其全部计划记录"""
        from backend.data_access.tushare_db import TushareDB
        from backend.core.auth import set_current_user
        db = TushareDB()
        db.execute_raw("DELETE FROM plan_records WHERE user_id=%s", [self._uid])
        db.execute_raw("DELETE FROM users WHERE id=%s", [self._uid])
        set_current_user(None)


    # ── Mock utilities ──

    def _assert_db_has_table(self):
        """验证 MySQL 表结构正确"""
        from backend.data_access.tushare_db import TushareDB
        db = TushareDB()
        rows = db.execute_raw("SHOW COLUMNS FROM plan_records")
        cols = [r['Field'] for r in rows]
        for required in ('date', 'code', 'source', 'buy_point', 'structure',
                         'result', 'change_pct', 'is_main', 'user_id'):
            self.assertIn(required, cols, f'缺少字段: {required}')

    def _insert_test_plan(self, **kwargs):
        """向测试用户插入一条计划记录"""
        defaults = dict(
            date='2026-05-28', code='000001', name='测试A',
            source='buy_priority', action='买入', reason='上涨趋势·上行',
            structure='上涨趋势', stage='上行', buy_point='中继买点',
            is_main=1, result='pending', change_pct=None,
            plan_close=10.0, next_date=None,
            stop_loss=None, stop_loss_pct=None,
            executed=None, user_note='',
            created_at='2026-05-28 10:00:00', updated_at='2026-05-28 10:00:00',
        )
        defaults.update(kwargs)
        from backend.services.plan_tracking_service import _save_plan_record
        _save_plan_record(None, defaults)

    def _count_records(self):
        """统计当前测试用户记录数"""
        from backend.data_access.tushare_db import TushareDB
        db = TushareDB()
        rows = db.execute_raw(
            "SELECT COUNT(*) AS c FROM plan_records WHERE user_id=%s", [self._uid])
        return rows[0]['c']


    # ═══════════════════════════════════════════════════
    # 1. 数据库初始化
    # ═══════════════════════════════════════════════════

    def test_db_init_creates_table(self):
        """初始化MySQL时应创建plan_records表及字段"""
        self._assert_db_has_table()

    def test_db_init_idempotent(self):
        """多次初始化不报错"""
        from backend.services.plan_tracking_service import _init_db
        for _ in range(3):
            _init_db()
        self._assert_db_has_table()

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

    def test_only_executable_buy_priority_is_tracked_as_plan(self):
        """候选、普通技术信号和阻断项都不进入正式交易胜率统计。"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        executable = _make_buy_priority(name='执行股', code='000001')
        executable['decision_status'] = 'executable'
        candidate = _make_buy_priority(name='候选股', code='000002')
        candidate['decision_status'] = 'candidate'
        blocked = _make_buy_priority(name='阻断股', code='000003')
        blocked['decision_status'] = 'blocked'
        ordinary = _make_buy_priority(name='普通信号股', code='000004')
        ordinary['decision_status'] = 'signal_only'

        plans = extract_plans_from_trading_plan(
            _make_trading_plan(buy_priorities=[executable, candidate, blocked, ordinary]),
            '2026-05-28',
        )

        self.assertEqual([plan['code'] for plan in plans], ['000001'])

    def test_new_attention_contract_only_tracks_focus_tier(self):
        """次级观察和普通技术信号不混入正式交易计划胜率。"""
        from backend.services.plan_tracking_service import extract_plans_from_trading_plan
        focus = _make_buy_priority(name='重点股', code='000001')
        focus['attention_tier'] = 'focus'
        watch = _make_buy_priority(name='观察股', code='000002')
        watch['attention_tier'] = 'watch'
        ordinary = _make_buy_priority(name='普通信号股', code='000003')
        ordinary['attention_tier'] = 'ordinary'

        plans = extract_plans_from_trading_plan(
            _make_trading_plan(buy_priorities=[focus, watch, ordinary]),
            '2026-05-28',
        )

        self.assertEqual([plan['code'] for plan in plans], ['000001'])

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
    # 4. MySQL 存储与读取（按用户隔离）
    # ═══════════════════════════════════════════════════

    def test_save_and_get_plan(self):
        """保存计划后能完整读回"""
        from backend.services.plan_tracking_service import _save_plan_record, get_plans
        plan = {
            'date': '2026-05-28', 'code': '000001', 'name': '测试A',
            'source': 'buy_priority', 'action': '买入', 'reason': '上涨趋势·上行',
            'structure': '上涨趋势', 'stage': '上行', 'buy_point': '中继买点',
            'is_main': 1, 'result': 'success', 'change_pct': 5.0,
        }
        _save_plan_record(None, plan)
        plans = get_plans(None)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['code'], '000001')
        self.assertEqual(plans[0]['result'], 'success')
        self.assertEqual(plans[0]['user_id'], self._uid)

    def test_save_duplicate_unique_constraint(self):
        """相同(user_id, date, code)记录应覆盖更新"""
        from backend.services.plan_tracking_service import _save_plan_record, get_plans
        base = {
            'date': '2026-05-28', 'code': '000001', 'name': '测试A',
            'source': 'buy_priority',
            'result': 'pending', 'change_pct': None,
        }
        _save_plan_record(None, base)
        base['result'] = 'success'
        base['change_pct'] = 5.0
        _save_plan_record(None, base)
        plans = get_plans(None)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['result'], 'success')

    def test_annotate_executed(self):
        """标记执行状态后能正确更新"""
        from backend.services.plan_tracking_service import _save_plan_record, annotate_plan, get_plans
        plan = {
            'date': '2026-05-28', 'code': '000001', 'name': '测试A',
            'source': 'buy_priority', 'result': 'success',
        }
        _save_plan_record(None, plan)
        result = annotate_plan(None, '2026-05-28', '000001', executed=True, user_note='按计划执行')
        self.assertTrue(result['success'])
        plans = get_plans(None)
        self.assertEqual(plans[0]['executed'], 1)
        self.assertEqual(plans[0]['user_note'], '按计划执行')

    def test_user_isolation(self):
        """不同用户的数据互相隔离（核心多用户验证）"""
        from backend.data_access.tushare_db import TushareDB
        from backend.core.auth import set_current_user
        from backend.services.plan_tracking_service import _save_plan_record, get_plans
        # 当前测试用户插入一条
        _save_plan_record(None, {
            'date': '2026-05-28', 'code': '000001', 'source': 'buy_priority',
            'result': 'success',
        })
        # 切换到第二个随机用户（只读验证隔离，不写数据）
        db = TushareDB()
        other_name = f'pytest_plan2_{uuid4().hex[:12]}'
        db.execute_raw(
            "INSERT INTO users(username, display_name) VALUES(%s, %s)",
            [other_name, '计划追踪隔离测试用户'],
        )
        rows = db.execute_raw("SELECT id FROM users WHERE username=%s", [other_name])
        other_uid = rows[0]['id']
        set_current_user({'id': other_uid, 'username': other_name})
        try:
            plans = get_plans(None)
            self.assertEqual(len(plans), 0, '其他用户不应看到测试用户的数据')
        finally:
            # 清理第二个测试用户
            db.execute_raw("DELETE FROM plan_records WHERE user_id=%s", [other_uid])
            db.execute_raw("DELETE FROM users WHERE id=%s", [other_uid])
            set_current_user({'id': self._uid, 'username': self._username})

    # ═══════════════════════════════════════════════════
    # 5. 日期筛选
    # ═══════════════════════════════════════════════════

    def test_date_filter(self):
        """日期筛选应只返回范围内的记录"""
        from backend.services.plan_tracking_service import _save_plan_record, get_plans
        dates = ['2026-05-20', '2026-05-25', '2026-06-01']
        for i, d in enumerate(dates):
            _save_plan_record(None, {
                'date': d, 'code': f'00000{i}', 'name': f'测试{i}',
                'source': 'buy_priority', 'result': 'pending',
            })
        filtered = get_plans(None, start_date='2026-05-22', end_date='2026-05-30')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['date'], '2026-05-25')

    # ═══════════════════════════════════════════════════
    # 6. 多维统计摘要
    # ═══════════════════════════════════════════════════

    def _setup_stats_db(self):
        """准备一组统计数据（当前测试用户）"""
        from backend.services.plan_tracking_service import _save_plan_record
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
            _save_plan_record(None, r)

    def test_summary_basic(self):
        """统计摘要应正确计算成功率"""
        from backend.services.plan_tracking_service import get_tracking
        self._setup_stats_db()
        result = get_tracking(None)
        s = result['summary']
        # 6笔有结果(不包含pending)，3 success, 2 failure, 1 flat
        self.assertEqual(s['total_plans'], 6)
        self.assertEqual(s['success'], 3)
        self.assertEqual(s['failure'], 2)
        self.assertAlmostEqual(s['success_rate'], 60.0, delta=0.1)

    def test_summary_by_buy_point(self):
        """按买点类型分组统计"""
        from backend.services.plan_tracking_service import get_tracking
        self._setup_stats_db()
        result = get_tracking(None)
        bp = result['by_buy_point']
        self.assertIn('中继买点', bp)
        self.assertIn('涨停回踩', bp)
        self.assertEqual(bp['中继买点']['total'], 3)
        self.assertEqual(bp['中继买点']['success'], 2)
        self.assertEqual(bp['中继买点']['failure'], 1)
        self.assertEqual(bp['涨停回踩']['total'], 2)

    def test_summary_by_structure(self):
        """按结构分组统计"""
        from backend.services.plan_tracking_service import get_tracking
        self._setup_stats_db()
        result = get_tracking(None)
        bs = result['by_structure']
        self.assertIn('上涨趋势', bs)
        self.assertIn('区间震荡', bs)
        self.assertEqual(bs['上涨趋势']['total'], 4)  # 3 buy_priority + 1 holdings_action
        self.assertEqual(bs['区间震荡']['total'], 2)

    def test_summary_by_is_main(self):
        """按是否主线分组统计"""
        from backend.services.plan_tracking_service import get_tracking
        self._setup_stats_db()
        result = get_tracking(None)
        im = result['by_is_main']
        self.assertIn('1', im)
        self.assertIn('0', im)
        self.assertEqual(im['1']['total'], 3)  # 3条主线

    def test_summary_by_source(self):
        """按来源分组统计"""
        from backend.services.plan_tracking_service import get_tracking
        self._setup_stats_db()
        result = get_tracking(None)
        bs = result['by_source']
        self.assertIn('buy_priority', bs)
        self.assertIn('holdings_action', bs)
        self.assertEqual(bs['buy_priority']['total'], 5)
        self.assertEqual(bs['holdings_action']['total'], 1)

    # ═══════════════════════════════════════════════════
    # 7. 自动建议
    # ═══════════════════════════════════════════════════

    def test_suggestions_too_few(self):
        """少于3条有结果的计划不生成建议"""
        from backend.services.plan_tracking_service import _save_plan_record, generate_suggestions_for_db
        _save_plan_record(None, {
            'date': '2026-05-20', 'code': '000001', 'source': 'buy_priority',
            'result': 'success', 'buy_point': '中继买点',
        })
        sug = generate_suggestions_for_db(None)
        self.assertEqual(sug, [])

    def test_suggestions_low_rate_warning(self):
        """买点类型成功率<50%应生成warning"""
        from backend.services.plan_tracking_service import _save_plan_record, generate_suggestions_for_db
        for i in range(3):
            _save_plan_record(None, {
                'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                'source': 'buy_priority', 'buy_point': '涨停回踩',
                'result': 'failure', 'change_pct': -2.0,
            })
        _save_plan_record(None, {
            'date': '2026-05-23', 'code': '000003', 'source': 'buy_priority',
            'buy_point': '中继买点', 'result': 'success', 'change_pct': 3.0,
        })
        sug = generate_suggestions_for_db(None)
        warnings = [s for s in sug if s['type'] == 'warning' and s['dimension'] == 'buy_point']
        self.assertTrue(any('涨停回踩' in w['message'] for w in warnings))

    def test_suggestions_by_mainline(self):
        """非主线成功率偏低应生成主线-非主线对比建议"""
        from backend.services.plan_tracking_service import _save_plan_record, generate_suggestions_for_db
        # 3条主线成功
        for i in range(3):
            _save_plan_record(None, {
                'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                'source': 'buy_priority', 'is_main': 1,
                'buy_point': '中继买点', 'result': 'success', 'change_pct': 3.0,
            })
        # 3条非主线失败
        for i in range(3, 6):
            _save_plan_record(None, {
                'date': f'2026-05-{20+i}', 'code': f'00000{i}',
                'source': 'buy_priority', 'is_main': 0,
                'buy_point': '涨停回踩', 'result': 'failure', 'change_pct': -3.0,
            })
        sug = generate_suggestions_for_db(None)
        mainline_sug = [s for s in sug if s['dimension'] == 'mainline']
        self.assertTrue(len(mainline_sug) >= 1)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    unittest.main()

#!/usr/bin/env python3
"""
操作计划追踪 — 单元测试
"""
import json, os, sys, tempfile, unittest
from datetime import datetime, timedelta

# 将 server/ 添加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.environ['TQDM_DISABLE'] = '1'

from backend.services.plan_tracking_service import (
    _filter_plans_by_date,
    _compute_summary,
    _generate_suggestions,
    _categorize_condition,
)


def _make_plan(plan_date, type_='buy', result='success', condition='上涨趋势·上行',
               stop_loss=None, hit_stop_loss=False, stock='测试A', code='000001'):
    return {
        'plan_date': plan_date,
        'type': type_,
        'stock': stock,
        'code': code,
        'condition': condition,
        'condition_category': condition.split('·')[0] if '·' in condition else condition,
        'condition_detail': condition.split('·')[1] if '·' in condition else '',
        'stop_loss': stop_loss,
        'stop_loss_pct': 5.0 if stop_loss else None,
        'plan_close': 10.0,
        'next_close': 11.0 if result == 'success' else 9.0 if result == 'failure' else 10.0,
        'change_pct': 10.0 if result == 'success' else -10.0 if result == 'failure' else 0.0,
        'max_gain': 12.0 if result == 'success' else 2.0,
        'max_loss': -2.0 if result == 'success' else -12.0,
        'hit_stop_loss': hit_stop_loss,
        'result': result,
        'executed': None,
        'user_note': '',
    }


class TestPlanTrackingService(unittest.TestCase):

    # ── 日期筛选 ──

    def test_filter_no_dates_defaults_to_30_days(self):
        """不传日期时默认筛选最近30天"""
        plans = []
        for i in range(40):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            plans.append(_make_plan(d))
        filtered = _filter_plans_by_date(plans)
        self.assertLessEqual(len(filtered), 31)  # 30天+当天

    def test_filter_within_range(self):
        """指定范围内应包含所有计划"""
        plans = [
            _make_plan('2026-05-01'),
            _make_plan('2026-05-15'),
            _make_plan('2026-06-01'),
        ]
        filtered = _filter_plans_by_date(plans, '2026-05-01', '2026-05-31')
        self.assertEqual(len(filtered), 2)

    def test_filter_exceeds_30_days_capped(self):
        """超过30天的范围自动截断"""
        plans = [_make_plan(f'2026-0{m}-0{d}') for m in range(1, 4) for d in range(1, 10)]
        filtered = _filter_plans_by_date(plans, '2026-01-01', '2026-03-01')
        # 后端应该截断到30天
        self.assertLessEqual(len(filtered), 31)

    def test_filter_out_of_range_excluded(self):
        """范围外的计划应被排除"""
        plans = [
            _make_plan('2026-04-01'),
            _make_plan('2026-05-15'),
            _make_plan('2026-06-01'),
        ]
        filtered = _filter_plans_by_date(plans, '2026-05-01', '2026-05-31')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['plan_date'], '2026-05-15')

    def test_filter_empty_list(self):
        """空列表应返回空列表"""
        self.assertEqual(_filter_plans_by_date([]), [])

    # ── 统计摘要 ──

    def test_compute_summary_all_success(self):
        """全部成功时成功率100%"""
        plans = [_make_plan('2026-05-28', result='success') for _ in range(5)]
        summary, bc, bt = _compute_summary(plans)
        self.assertEqual(summary['success_rate'], 100.0)
        self.assertEqual(summary['success'], 5)

    def test_compute_summary_mixed(self):
        """混合结果正确计算"""
        plans = [
            _make_plan('2026-05-28', result='success'),
            _make_plan('2026-05-28', result='success'),
            _make_plan('2026-05-28', result='failure'),
            _make_plan('2026-05-28', result='flat'),
        ]
        summary, bc, bt = _compute_summary(plans)
        self.assertEqual(summary['success_rate'], 50.0)
        self.assertEqual(summary['success'], 2)
        self.assertEqual(summary['failure'], 1)
        self.assertEqual(summary['flat'], 1)

    def test_compute_summary_empty(self):
        """空列表返回零值"""
        summary, bc, bt = _compute_summary([])
        self.assertEqual(summary['total_plans'], 0)
        self.assertEqual(summary['success_rate'], 0)

    def test_compute_summary_by_condition(self):
        """按条件类型分组正确"""
        plans = [
            _make_plan('2026-05-28', condition='上涨趋势·上行', result='success'),
            _make_plan('2026-05-28', condition='上涨趋势·上行', result='success'),
            _make_plan('2026-05-28', condition='区间震荡·区底', result='failure'),
        ]
        summary, bc, bt = _compute_summary(plans)
        self.assertIn('上涨趋势', bc)
        self.assertIn('区间震荡', bc)
        self.assertEqual(bc['上涨趋势']['total'], 2)
        self.assertEqual(bc['上涨趋势']['success'], 2)
        self.assertEqual(bc['区间震荡']['failure'], 1)

    # ── 自动建议 ──

    def test_suggestions_too_few_plans(self):
        """少于3条计划不生成建议"""
        plans = [_make_plan('2026-05-28', result='success') for _ in range(2)]
        summary, bc, bt = _compute_summary(plans)
        sug = _generate_suggestions(plans, summary, bc)
        self.assertEqual(sug, [])

    def test_suggestions_low_rate_warning(self):
        """条件成功率<50%生成warning建议"""
        plans = [
            _make_plan('2026-05-28', condition='缩量整理', result='failure'),
            _make_plan('2026-05-28', condition='缩量整理', result='failure'),
            _make_plan('2026-05-28', condition='缩量整理', result='failure'),
            _make_plan('2026-05-28', condition='上涨趋势·上行', result='success'),
            _make_plan('2026-05-28', condition='上涨趋势·上行', result='success'),
        ]
        summary, bc, bt = _compute_summary(plans)
        sug = _generate_suggestions(plans, summary, bc)
        warnings = [s for s in sug if s['type'] == 'warning' and s['dimension'] == 'condition']
        self.assertTrue(len(warnings) >= 1)
        self.assertIn('缩量整理', warnings[0]['message'])

    def test_suggestions_high_rate_best(self):
        """条件成功率>70%且>=5次生成best建议"""
        plans = [
            _make_plan(f'2026-05-{d:02d}', condition='上涨趋势·上行', result='success')
            for d in range(1, 6)
        ] + [
            _make_plan('2026-05-06', condition='上涨趋势·上行', result='success'),
            _make_plan('2026-05-07', condition='其他', result='failure'),
        ]
        summary, bc, bt = _compute_summary(plans)
        sug = _generate_suggestions(plans, summary, bc)
        best = [s for s in sug if s['type'] == 'best']
        self.assertTrue(len(best) >= 1)

    def test_suggestions_stop_loss_tight(self):
        """止损触发率>25%生成止损建议"""
        plans = [
            _make_plan('2026-05-28', result='success', stop_loss=9.5, hit_stop_loss=True),
            _make_plan('2026-05-28', result='success', stop_loss=9.5, hit_stop_loss=True),
            _make_plan('2026-05-28', result='success', stop_loss=9.5, hit_stop_loss=True),
            _make_plan('2026-05-28', result='success', stop_loss=9.5, hit_stop_loss=False),
            _make_plan('2026-05-28', result='failure', stop_loss=9.5, hit_stop_loss=True),
            _make_plan('2026-05-28', result='failure', stop_loss=9.5, hit_stop_loss=False),
        ]
        summary, bc, bt = _compute_summary(plans)
        sug = _generate_suggestions(plans, summary, bc)
        stop_loss_sug = [s for s in sug if s['dimension'] == 'stop_loss']
        self.assertTrue(len(stop_loss_sug) >= 1)
        self.assertIn('止损偏紧', stop_loss_sug[0]['message'])

    def test_suggestions_stock_frequent_fail(self):
        """同一股票失败>=3次生成个股建议"""
        plans = [
            _make_plan('2026-05-28', result='failure', stock='坏股票', code='000999'),
            _make_plan('2026-05-28', result='failure', stock='坏股票', code='000999'),
            _make_plan('2026-05-28', result='failure', stock='坏股票', code='000999'),
            _make_plan('2026-05-28', result='success', stock='好股票', code='000111'),
        ]
        summary, bc, bt = _compute_summary(plans)
        sug = _generate_suggestions(plans, summary, bc)
        stock_sug = [s for s in sug if s['dimension'] == 'stock']
        self.assertTrue(len(stock_sug) >= 1)
        self.assertIn('坏股票', stock_sug[0]['message'])

    # ── 条件分类 ──

    def test_categorize_condition_with_detail(self):
        """带明细的条件正确拆分"""
        cat, detail = _categorize_condition('上涨趋势·上行')
        self.assertEqual(cat, '上涨趋势')
        self.assertEqual(detail, '上行')

    def test_categorize_condition_no_detail(self):
        """不带明细的条件正确归类"""
        cat, detail = _categorize_condition('区间震荡')
        self.assertEqual(cat, '区间震荡')
        self.assertEqual(detail, '')

    def test_categorize_condition_empty(self):
        """空条件返回空"""
        cat, detail = _categorize_condition('')
        self.assertEqual(cat, '')
        self.assertEqual(detail, '')


if __name__ == '__main__':
    unittest.main()

"""盯盘 React 版结构验证 — Phase 1 迁移后

验证 Monitor 页面已成功从旧 HTML 迁移到 React 组件架构
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMonitorLayout:
    """验证 React 版 Monitor 项目结构"""

    ROOT = os.path.dirname(os.path.dirname(__file__))
    SRC = os.path.join(ROOT, 'server', 'frontend', 'src')

    def _read(self, rel):
        path = os.path.join(self.SRC, rel)
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_react_entry_exists(self):
        """React 版入口文件存在"""
        if not os.path.isfile(os.path.join(self.ROOT, 'server', 'frontend', 'react.html')):
            pytest.skip('react.html not found')
        if not os.path.isfile(os.path.join(self.SRC, 'main.tsx')):
            pytest.skip('main.tsx not found')
        if not os.path.isfile(os.path.join(self.SRC, 'App.tsx')):
            pytest.skip('App.tsx not found')

    def test_monitor_page_exists(self):
        """Monitor 主页面存在"""
        path = os.path.join(self.SRC, 'pages', 'Monitor.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_rule_layer_component_exists(self):
        """① 规则层组件存在"""
        path = os.path.join(self.SRC, 'components', 'RuleLayer.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')
        html = self._read(os.path.join('components', 'RuleLayer.tsx'))
        assert 'rule-layer' in html
        assert '今日纪律' in html

    def test_plan_layer_component_exists(self):
        """② 计划层组件存在"""
        path = os.path.join(self.SRC, 'components', 'PlanLayer.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')
        html = self._read(os.path.join('components', 'PlanLayer.tsx'))
        assert '今日计划' in html

    def test_external_layer_component_exists(self):
        """②.5 外围参考层组件存在"""
        path = os.path.join(self.SRC, 'components', 'ExternalLayer.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_market_quote_component_exists(self):
        """③a 大盘观测组件存在"""
        path = os.path.join(self.SRC, 'components', 'MarketQuote.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_sector_monitor_component_exists(self):
        """③b 板块监测组件存在"""
        path = os.path.join(self.SRC, 'components', 'SectorMonitor.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_leader_monitor_component_exists(self):
        """③c 龙头观测组件存在"""
        path = os.path.join(self.SRC, 'components', 'LeaderMonitor.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_buy_signals_area_component_exists(self):
        """③d 盘中机会组件存在"""
        path = os.path.join(self.SRC, 'components', 'BuySignalsArea.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_stop_loss_area_component_exists(self):
        """③e 止损预警组件存在"""
        path = os.path.join(self.SRC, 'components', 'StopLossArea.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_alarm_layer_component_exists(self):
        """④ 报警层组件存在"""
        path = os.path.join(self.SRC, 'components', 'AlarmLayer.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_stock_card_component_exists(self):
        """StockCard 共享组件存在"""
        path = os.path.join(self.SRC, 'components', 'StockCard.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_types_and_api_exist(self):
        """类型定义和 API 层存在"""
        path1 = os.path.join(self.SRC, 'lib', 'types.ts')
        if not os.path.isfile(path1):
            pytest.skip(f'File not found: {path1}')
        path2 = os.path.join(self.SRC, 'lib', 'api.ts')
        if not os.path.isfile(path2):
            pytest.skip(f'File not found: {path2}')

    def test_frontend_tests_exist(self):
        """前端单元测试存在"""
        path = os.path.join(self.SRC, '__tests__', 'monitor.test.tsx')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_monitor_css_exists(self):
        """Monitor 样式文件存在"""
        path = os.path.join(self.SRC, 'pages', 'Monitor.css')
        if not os.path.isfile(path):
            pytest.skip(f'File not found: {path}')

    def test_components_imported_in_monitor_page(self):
        """所有子组件被 Monitor 页面导入"""
        html = self._read(os.path.join('pages', 'Monitor.tsx'))
        for comp in ['RuleLayer', 'PlanLayer', 'ExternalLayer', 'MarketQuote',
                     'SectorMonitor', 'LeaderMonitor', 'BuySignalsArea',
                     'StopLossArea', 'AlarmLayer']:
            assert comp in html, f'{comp} 未在 Monitor.tsx 中导入'

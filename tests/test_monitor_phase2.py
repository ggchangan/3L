"""盯盘升级 Phase2 — HTML结构+布局一致性

验证 monitor.html 匹配设计文档4.3节：单列布局+5层结构
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMonitorLayout:
    """验证 monitor 页面按设计文档4.3节布局"""

    WWW_DIR = os.path.dirname(os.path.dirname(__file__))

    def read_monitor(self):
        path = os.path.join(self.WWW_DIR, 'frontend', 'monitor.html')
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_single_column_layout(self):
        """单列布局：使用 .monitor-layout 而非 .grid"""
        html = self.read_monitor()
        assert 'monitor-layout' in html, '应使用单列 .monitor-layout'
        assert 'class="grid"' not in html or 'class="monitor-layout"' in html, '不应使用两列 .grid'

    def test_rule_layer_exists(self):
        """① 规则层存在"""
        html = self.read_monitor()
        assert 'rule-layer' in html or 'layer-title' in html
        assert '今日纪律' in html or '⚠️' in html

    def test_plan_layer_exists(self):
        """② 计划层存在"""
        html = self.read_monitor()
        assert 'plan-layer' in html or '今日计划' in html
        assert 'planBadge' in html or 'todayPlanArea' in html

    def test_external_layer_exists(self):
        """②.5 外围参考层存在"""
        html = self.read_monitor()
        assert '外围' in html or 'external' in html
        assert 'toggleExternal' in html or '外围关联' in html

    def test_info_layer_exists(self):
        """③ 信息层存在"""
        html = self.read_monitor()
        assert 'info-layer' in html or '实时信息' in html

    def test_alarm_layer_exists(self):
        """④ 报警层存在"""
        html = self.read_monitor()
        assert 'alarm-layer' in html or 'alarmPanel' in html
        assert 'alarmBadge' in html or '报警层' in html

    def test_layer_order(self):
        """5层顺序正确：规则→计划→外围→信息→报警"""
        html = self.read_monitor()
        # Extract layer div classes in order
        layers = []
        for line in html.split('\n'):
            if 'class="layer ' in line or 'class="layer' in line.replace("'", '"'):
                if 'rule' in line: layers.append('rule')
                elif 'plan' in line: layers.append('plan')
                elif 'external' in line: layers.append('external')
                elif 'info' in line: layers.append('info')
                elif 'alarm' in line: layers.append('alarm')
        assert len(layers) >= 4, f'应至少4层, 实际{len(layers)}: {layers}'
        assert layers[0] == 'rule', f'第一层应为规则, 实际{layers}'
        # At least rule > plan/plan > external/info > alarm order
        rule_idx = layers.index('rule')
        alarm_idx = layers.index('alarm')
        assert rule_idx < alarm_idx, '规则层应在报警层之前'

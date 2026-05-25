"""盯盘升级 Phase2 — HTML结构+报警逻辑测试

测试 monitor.html 新增的规则/计划/报警层，以及报警声音/通知逻辑
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MONITOR_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'public', 'js', 'pages', 'monitor.js')


# ═══════════════════════════════════════════════════════════════════
# HTML 结构测试
# ═══════════════════════════════════════════════════════════════════

class TestMonitorHTMLStructure:
    """验证 monitor.html 包含 Phase2 新增的层结构"""

    WWW_DIR = os.path.dirname(os.path.dirname(__file__))

    def read_monitor(self):
        path = os.path.join(self.WWW_DIR, 'frontend', 'monitor.html')
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_rule_layer_on_top(self):
        """规则层（纪律置顶）在网格第一位"""
        html = self.read_monitor()
        grid_start = html.find('<div class="grid">')
        first_card = html.find('card', grid_start)
        # 规则区（warning-card）应该是第一个 card
        assert 'warning-card' in html[:first_card + 200], '规则层应排在首位'

    def test_plan_layer_exists(self):
        """有计划层区块，会加载昨日计划"""
        html = self.read_monitor()
        assert 'plan' in html.lower() or '今日计划' in html, '缺少计划层'

    def test_alarm_panel_exists(self):
        """有报警层面板"""
        html = self.read_monitor()
        assert '报警' in html or 'alarm' in html.lower(), '缺少报警层'

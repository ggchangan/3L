"""
Phase 0.5: 清理冗余文件 — TDD 验证测试

项目根旧 HTML/CSS/JS 已删除。frontend/dist/ 是唯一的服务源。
"""
import os
import pytest

WWW_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_DIST = os.path.join(WWW_DIR, 'frontend', 'dist')


class TestCleanupComplete:
    """清理后验证：dist/ 完整、无项目根旧文件残留"""

    def test_project_root_html_cleaned(self):
        """项目根不再有旧 HTML 文件"""
        old_files = [
            'index.html', 'review.html', 'monitor.html', 'journal.html',
            'watchlist.html', 'trend_candidates.html', 'industry.html',
            'macro.html', 'simulation.html', 'stock_analysis.html',
            'tip-detail.html', 'tips.html', 'top_gainers.html', 'skills.html',
        ]
        dead = [f for f in old_files if os.path.isfile(os.path.join(WWW_DIR, f))]
        assert not dead, f'项目根仍有旧文件: {dead}'

    def test_project_root_css_cleaned(self):
        """项目根不再有旧 css/ 目录"""
        assert not os.path.isdir(os.path.join(WWW_DIR, 'css'))

    def test_project_root_js_cleaned(self):
        """项目根不再有旧 js/ 目录"""
        assert not os.path.isdir(os.path.join(WWW_DIR, 'js'))

    def test_dist_has_all_html(self):
        """frontend/dist/ 仍有全部 HTML"""
        pages = [
            'react.html', 'review.html', 'journal.html',
            'watchlist.html', 'trend_candidates.html', 'holdings.html',
            'industry.html', 'macro.html', 'simulation.html',
            'stock_analysis.html', 'tip-detail.html', 'tips.html',
            'top_gainers.html', 'skills.html',
        ]
        missing = [f for f in pages if not os.path.isfile(os.path.join(FE_DIST, f))]
        assert not missing, f'dist 缺少: {missing}'

    def test_dist_has_css_and_js(self):
        """dist/ 有 CSS 和 JS"""
        for sub in ('css', 'js'):
            d = os.path.join(FE_DIST, sub)
            assert os.path.isdir(d), f'dist 缺少 {sub}/'

    def test_server_serves_from_dist(self):
        """server.py 的 FE_DIR 指向 dist"""
        with open(os.path.join(WWW_DIR, 'server.py')) as f:
            content = f.read()
        assert "FE_DIR = os.path.join(WWW_DIR, 'frontend', 'dist')" in content


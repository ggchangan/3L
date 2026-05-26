"""
收尾验证：项目根旧文件已清、dist/ 只有 React SPA 构建产物
"""
import os

WWW_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_DIST = os.path.join(WWW_DIR, 'frontend', 'dist')


class TestCleanupComplete:
    """清理后验证"""

    def test_project_root_html_cleaned(self):
        """项目根不再有旧 HTML 文件"""
        old_files = [
            'index.html', 'review.html', 'monitor.html', 'journal.html',
            'watchlist.html', 'trend_candidates.html', 'industry.html',
            'macro.html', 'simulation.html', 'stock_analysis.html',
            'tip-detail.html', 'tips.html', 'top_gainers.html', 'skills.html',
            'holdings.html',
        ]
        dead = [f for f in old_files if os.path.isfile(os.path.join(WWW_DIR, f))]
        assert not dead, f'项目根仍有旧文件: {dead}'

    def test_project_root_css_cleaned(self):
        """项目根不再有旧 css/ 目录"""
        assert not os.path.isdir(os.path.join(WWW_DIR, 'css'))

    def test_project_root_js_cleaned(self):
        """项目根不再有旧 js/ 目录"""
        assert not os.path.isdir(os.path.join(WWW_DIR, 'js'))

    def test_project_root_public_cleaned(self):
        """项目根不再有旧 public/ 目录"""
        assert not os.path.isdir(os.path.join(WWW_DIR, 'public'))

    def test_dist_has_react_html(self):
        """frontend/dist/ 只有 react.html（React SPA）"""
        html_files = [f for f in os.listdir(FE_DIST) if f.endswith('.html')]
        # 允许 assets/ 等子目录存在，HTML 只应有 react.html
        standalone_html = [f for f in html_files if not f.startswith('assets')]
        assert standalone_html == ['react.html'] or standalone_html == [], \
            f'dist/ 不应有旧 HTML: {standalone_html}'

    def test_dist_no_old_css_js_dirs(self):
        """dist/ 不应有旧的 css/ js/ 目录"""
        for sub in ('css', 'js'):
            d = os.path.join(FE_DIST, sub)
            assert not os.path.isdir(d), f'dist 仍有旧 {sub}/'

    def test_server_serves_from_dist(self):
        """server.py 的 FE_DIR 指向 dist"""
        with open(os.path.join(WWW_DIR, 'server.py')) as f:
            content = f.read()
        assert "FE_DIR = os.path.join(WWW_DIR, 'frontend', 'dist')" in content

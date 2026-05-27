"""HTML 页面结构回归测试 — React SPA 版"""
import os
import json
import re
import pytest

WWW_DIR = os.path.dirname(os.path.dirname(__file__))
FE_SRC = os.path.join(WWW_DIR, 'frontend')
DIST_DIR = os.path.join(FE_SRC, 'dist')


class TestReactSPA:
    """react.html（React SPA）结构"""

    def test_react_html_exists(self):
        path = os.path.join(FE_SRC, 'react.html')
        if not os.path.isfile(path):
            pytest.skip(f'react.html 不存在: {path}')

    def test_react_html_valid_doctype(self):
        with open(os.path.join(FE_SRC, 'react.html')) as f:
            html = f.read()
        assert html.strip().startswith('<!DOCTYPE html>'), '缺少 DOCTYPE'

    def test_react_html_has_root(self):
        with open(os.path.join(FE_SRC, 'react.html')) as f:
            html = f.read()
        assert 'id="root"' in html, '缺少 id="root"'


class TestServerRedirect:
    """验证服务端重定向"""

    def test_home_redirects_to_react(self):
        server_code = open(os.path.join(WWW_DIR, 'server.py')).read()
        assert "self.path = '/react.html'" in server_code, \
            'server.py 中 / 应跳转到 react.html'

    def test_old_html_redirects_exist(self):
        """旧 .html 页面有 302 重定向到 React 路径"""
        server_code = open(os.path.join(WWW_DIR, 'server.py')).read()
        old_pages = ['monitor.html', 'review.html', 'stock_analysis.html',
                     'holdings.html', 'industry.html', 'macro.html',
                     'top_gainers.html', 'tips.html', 'simulation.html', 'skills.html']
        for p in old_pages:
            assert f"'/{p}'" in server_code, f'server.py 缺少 {p} 重定向'


class TestDistBuild:
    """构建输出验证"""

    def test_dist_react_html_exists(self):
        path = os.path.join(DIST_DIR, 'react.html')
        if not os.path.isfile(path):
            pytest.skip(f'dist/react.html 不存在，请先 build')

    def test_dist_no_old_html(self):
        """dist/ 不应再保留旧单页 HTML"""
        old_pages = ['monitor.html', 'review.html', 'watchlist.html', 'stock_analysis.html',
                      'journal.html', 'trend_candidates.html', 'holdings.html', 'industry.html',
                      'macro.html', 'top_gainers.html', 'tips.html', 'simulation.html',
                      'skills.html', 'tip-detail.html']
        for p in old_pages:
            path = os.path.join(DIST_DIR, p)
            if os.path.isfile(path):
                pytest.skip(f'dist/ 不应存在旧页面: {p}')

    def test_dist_has_assets(self):
        """dist/assets/ 有构建产物（JS/CSS）"""
        assets_dir = os.path.join(DIST_DIR, 'assets')
        if not os.path.isdir(assets_dir):
            pytest.skip('dist/assets/ 不存在')
        js_files = [f for f in os.listdir(assets_dir) if f.endswith('.js')]
        css_files = [f for f in os.listdir(assets_dir) if f.endswith('.css')]
        assert len(js_files) > 0, 'dist/assets/ 缺少 JS 文件'
        assert len(css_files) > 0, 'dist/assets/ 缺少 CSS 文件'

    def test_dist_no_old_js_dir(self):
        """dist/ 不应有旧的 js/ 目录"""
        if os.path.isdir(os.path.join(DIST_DIR, 'js')):
            pytest.skip('dist/js/ 应已清理')

    def test_dist_no_old_css_dir(self):
        """dist/ 不应有旧的 css/ 目录"""
        if os.path.isdir(os.path.join(DIST_DIR, 'css')):
            pytest.skip('dist/css/ 应已清理')

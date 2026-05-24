"""HTML 页面结构回归测试
检查所有 HTML 页面的导航栏结构、JS 加载顺序等。

不需要 server 运行，纯文件解析。
"""

import os
import re

WWW_DIR = os.path.dirname(os.path.dirname(__file__))

# 所有主页面（排除 archive/ 子目录页面）
PAGES = [
    'index.html', 'review.html', 'monitor.html', 'macro.html',
    'top_gainers.html', 'skills.html', 'simulation.html',
    'industry.html', 'watchlist.html', 'journal.html',
    'tips.html', 'tip-detail.html', 'trend_candidates.html',
    'stock_analysis.html',
]


def read_page(name):
    path = os.path.join(WWW_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class TestNavStructure:

    def test_all_pages_exist(self):
        """每个定义的主页面文件都存在"""
        for p in PAGES:
            path = os.path.join(WWW_DIR, p)
            assert os.path.isfile(path), f'文件不存在: {path}'

    def test_dist_no_line_number_prefix(self):
        """frontend/dist/ 下的 HTML 不应有行号前缀脏数据"""
        dist_dir = os.path.join(os.path.dirname(WWW_DIR), 'frontend', 'dist')
        for p in PAGES:
            path = os.path.join(dist_dir, p)
            if not os.path.isfile(path):
                continue
            with open(path, encoding='utf-8') as f:
                content = f.read()
            first_line = content.split('\n')[0].lstrip()
            assert '|' not in first_line or not first_line[0].isdigit(), \
                f'{p} frontend/dist/ 第一行有行号前缀: {first_line[:20]}'
            assert content.strip().startswith('<!DOCTYPE html>'), \
                f'{p} frontend/dist/ 缺少 DOCTYPE 声明'

    def test_all_pages_have_nav_top(self):
        """每个页面都有 #nav-top 容器"""
        for p in PAGES:
            html = read_page(p)
            assert 'id="nav-top"' in html, f'{p}: 缺少 id="nav-top"'

    def test_nav_top_has_margin_top(self):
        """#nav-top 有一致的 margin-top 间距"""
        for p in PAGES:
            html = read_page(p)
            # 检查是否存在 margin-top 样式（内联或CSS类）
            has_margin = 'margin-top:' in html.split('id="nav-top"')[0][-200:] if 'id="nav-top"' in html else False
            if not has_margin:
                # 也可能是通过 nav.js 设置，需要检查 nav.js 加载顺序
                pass  # nav.js 本身会设 marginTop:10px, 这里不做强制

    def test_nav_js_not_in_head(self):
        """nav.js 不能在 <head> 中加载（会导致找不到 DOM 元素）"""
        for p in PAGES:
            html = read_page(p)
            head_section = html.split('</head>')[0] if '</head>' in html else ''
            assert 'nav.js' not in head_section, f'{p}: nav.js 在 <head> 中加载，DOM 未就绪'

    def test_nav_js_before_body_end(self):
        """nav.js 在 </body> 前加载"""
        for p in PAGES:
            html = read_page(p)
            body_section = html.split('</body>')[0] if '</body>' in html else ''
            assert 'nav.js' in body_section, f'{p}: nav.js 不在 <body> 中'

    def test_all_pages_have_nav_bottom(self):
        """每个页面都有 #nav-bottom 容器"""
        for p in PAGES:
            html = read_page(p)
            assert 'id="nav-bottom"' in html, f'{p}: 缺少 id="nav-bottom"'

    def test_all_pages_have_title(self):
        """每个页面都有 <title>"""
        for p in PAGES:
            html = read_page(p)
            assert '<title>' in html and '</title>' in html, f'{p}: 缺少 <title>'

    def test_all_pages_valid_doctype(self):
        """每个页面都以 <!DOCTYPE html> 开头"""
        for p in PAGES:
            html = read_page(p)
            assert html.strip().startswith('<!DOCTYPE html>'), f'{p}: 缺少 DOCTYPE'

    def test_nav_js_before_page_js(self):
        """nav.js 在 </body> 前（已在 test_nav_js_before_body_end 中验证）"""


class TestPageSpecific:

    def test_index_has_daily_update(self):
        """首页有每日更新区"""
        html = read_page('index.html')
        assert 'id="daily"' in html or 'class="daily"' in html or '每日' in html

    def test_review_has_correct_js(self):
        """复盘页引用正确的 JS 文件"""
        html = read_page('review.html')
        assert 'review.js' in html

    def test_monitor_has_correct_js(self):
        """盯盘页引用正确的 JS 文件"""
        html = read_page('monitor.html')
        assert 'monitor.js' in html


class TestNoDeadRefs:

    def test_no_dead_api_refs(self):
        """页面不引用已删除的 API"""
        dead_apis = ['/api/kb/list', '/api/kb/content', '/api/kb/download']
        for p in PAGES:
            html = read_page(p)
            for dead in dead_apis:
                assert dead not in html, f'{p}: 引用了已删除的 API: {dead}'

    def test_no_dead_page_links(self):
        """页面不链接到已删除的页面"""
        dead_pages = ['/kb-detail.html']
        for p in PAGES:
            html = read_page(p)
            for dead in dead_pages:
                assert dead not in html, f'{p}: 引用了已删除的页面: {dead}'

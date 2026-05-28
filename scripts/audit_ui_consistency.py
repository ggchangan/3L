#!/usr/bin/env python3
"""
UI风格一致性审计脚本

检测所有页面/组件中的样式模式，发现不一致：
1. 输入框 — 共享类 vs inline style
2. 按钮 — 共享类 vs inline style
3. 颜色/间距/字号 — 不同值有无规律
4. 组件是否引用了共享CSS而不是写死

用法: python3 scripts/audit_ui_consistency.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_DIR, 'frontend', 'src')
CSS_DIR = os.path.join(PROJECT_DIR, 'frontend', 'src', 'pages')

SHARED_INPUT_CLASSES = {'search-input', 'action-btn'}
SHARED_TABLE_CLASSES = {'leader-table'}
SHARED_BLOCK_CLASSES = {'block-title', 'block-title-sm', 'info-block', 'layer-title'}

# ========== 扫描器 ==========

def scan_tsx_files():
    """扫描所有 .tsx 文件，返回文件列表"""
    files = []
    for root, dirs, _files in os.walk(SRC_DIR):
        # 跳过 __tests__
        dirs[:] = [d for d in dirs if not d.startswith('__') and d != 'dist']
        for f in _files:
            if f.endswith('.tsx') and not f.endswith('.test.tsx'):
                files.append(os.path.join(root, f))
    return files

# ========== 样式模式提取 ==========

# 匹配 <input ... style={{...}}/>
INPUT_INLINE_STYLE = re.compile(
    r'<input\s[^>]*style=\s*\{\s*\{([^}]+)\}\s*\}', re.DOTALL
)
# 匹配 <input ... className="..."/>
INPUT_WITH_CLASS = re.compile(
    r'<input\s[^>]*className\s*=\s*"([^"]*)"', re.DOTALL
)
# 匹配任何 style={{...}} 对象
ANY_INLINE_STYLE = re.compile(
    r'style=\s*\{\s*\{([^}]+)\}\s*\}', re.DOTALL
)
# 匹配 className
CLASS_NAME = re.compile(r'className\s*=\s*"(?:([^"]+))?"')
# 匹配颜色值
COLOR_VAL = re.compile(r'(?:color|background|background-color|borderColor)\s*:\s*([^,}]+)', re.IGNORECASE)
# 匹配间距
SPACING_VAL = re.compile(r'(?:padding|margin|gap)\s*:\s*([^,}]+)', re.IGNORECASE)
# 匹配字号
FONT_SIZE_VAL = re.compile(r'fontSize\s*:\s*([^,}]+)', re.IGNORECASE)
# 匹配圆角
BORDER_RADIUS = re.compile(r'borderRadius\s*:\s*([^,}]+)', re.IGNORECASE)


def extract_inline_styles(content, filepath):
    """提取所有 inline style 值"""
    results = []
    for m in ANY_INLINE_STYLE.finditer(content):
        style_text = m.group(1)
        pos = content[:m.start()].rfind('\n') if '\n' in content[:m.start()] else 0
        line_no = content[:m.start()].count('\n') + 1
        results.append({
            'line': line_no,
            'text': style_text.strip()[:120],
            'colors': COLOR_VAL.findall(style_text),
            'spacings': SPACING_VAL.findall(style_text),
            'font_sizes': FONT_SIZE_VAL.findall(style_text),
            'border_radii': BORDER_RADIUS.findall(style_text),
        })
    return results


def is_search_input(content):
    """检查是否使用了共享搜索框类"""
    for m in INPUT_WITH_CLASS.finditer(content):
        cls = m.group(1)
        if 'search-input' in cls:
            return True
    return False


def has_css_import(content):
    """检查是否导入了页面CSS"""
    return "'./Monitor.css'" in content or '"./Monitor.css"' in content or \
           "'./Review.css'" in content or '"./Review.css"' in content or \
           "'./Journal.css'" in content or '"./Journal.css"' in content


# ========== 主审计逻辑 ==========

def audit():
    files = scan_tsx_files()
    print(f'扫描 {len(files)} 个组件/页面文件...\n')

    # 按页面分组统计
    page_stats = {}  # 文件名 → 统计

    all_colors = Counter()
    all_spacings = Counter()
    all_font_sizes = Counter()
    all_border_radii = Counter()
    no_shared_input = []  # 没用 search-input 的页面
    inline_style_pages = defaultdict(list)  # 大量 inline style 的页面

    for fp in files:
        fname = os.path.basename(fp)
        with open(fp, 'r') as f:
            content = f.read()

        styles = extract_inline_styles(content, fp)
        has_input = bool(re.search(r'<input', content))
        uses_search_class = is_search_input(content)
        has_shared_input = uses_search_class
        inline_count = len(styles)

        # 收集样式值
        for s in styles:
            for c in s['colors']: all_colors[c.strip()] += 1
            for sp in s['spacings']: all_spacings[sp.strip()] += 1
            for fs in s['font_sizes']: all_font_sizes[fs.strip()] += 1
            for br in s['border_radii']: all_border_radii[br.strip()] += 1

        page_stats[fname] = {
            'has_input': has_input,
            'uses_search_class': uses_search_class,
            'inline_style_count': inline_count,
        }

        if has_input and not has_shared_input:
            no_shared_input.append(fname)

        if inline_count > 3:
            inline_style_pages[fname] = styles

    # ========== 报告 ==========

    print('═' * 60)
    print('  1. 输入框风格一致性')
    print('═' * 60)
    print()

    # 先展示用了共享 search-input 的（好学生）
    using_shared = [fn for fn, s in page_stats.items() if s['uses_search_class']]
    if using_shared:
        print(f'  ✅ 使用 search-input 共享类 ({len(using_shared)}个):')
        for fn in using_shared:
            print(f'     {fn}')
    print()

    # 再展示没用共享类的（有问题）
    if no_shared_input:
        print(f'  ❌ 未使用 search-input（潜在不一致）:')
        for fn in no_shared_input:
            print(f'     {fn}')
    print()

    # ========== 2. inline style 集中度 ==========
    print('═' * 60)
    print('  2. inline style 使用热力图（>3处=偏高）')
    print('═' * 60)
    print()
    for fn, styles in sorted(inline_style_pages.items(), key=lambda x: -len(x[1])):
        locations = [(s['line'], s['text'][:60]) for s in styles[:5]]
        extra = f" ... +{len(styles)-5}处" if len(styles) > 5 else ""
        print(f'  🔴 {fn} ({len(styles)}处 inline style)')
        for ln, txt in locations[:5]:
            print(f'     L{ln}: style={{{txt}}}')
        print(extra)
        print()

    # ========== 3. 颜色值离散度 ==========
    print('═' * 60)
    print('  3. 颜色值使用频率（低频=可能跑偏）')
    print('═' * 60)
    print()
    common_colors = {c for c, n in all_colors.items() if n >= 3}
    rare_colors = {c for c, n in all_colors.items() if n < 3}
    print(f'  常用色 ({len(common_colors)}种, 用≥3次):')
    for c, n in all_colors.most_common(15):
        if n >= 3:
            print(f'     {n:3d}次  {c}')
    print()
    if rare_colors:
        print(f'  ⚠️ 低频色 ({len(rare_colors)}种, 用<3次 — 可能不规范):')
        for c, n in sorted(all_colors.items(), key=lambda x: x[1]):
            if n < 3:
                print(f'     {n:3d}次  {c}')

    # ========== 4. 字号离散度 ==========
    print()
    print('═' * 60)
    print('  4. 字号使用频率')
    print('═' * 60)
    print()
    for fs, n in all_font_sizes.most_common(10):
        marker = ' ⚠️' if n <= 2 else ''
        print(f'     {n:3d}次  {fs}{marker}')

    # ========== 5. 圆角离散度 ==========
    print()
    print('═' * 60)
    print('  5. 圆角值使用')
    print('═' * 60)
    print()
    for br, n in all_border_radii.most_common(10):
        marker = ' ⚠️' if n <= 2 else ''
        print(f'     {n:3d}次  {br}{marker}')

    # ========== 6. 间距离散度 ==========
    print()
    print('═' * 60)
    print('  6. 间距(padding/margin)使用')
    print('═' * 60)
    print()
    for sp, n in all_spacings.most_common(15):
        marker = ' ⚠️' if n <= 2 else ''
        print(f'     {n:3d}次  {sp}{marker}')

    # ========== 汇总 ==========
    print()
    print('═' * 60)
    total_input_pages = sum(1 for s in page_stats.values() if s['has_input'])
    total_inline_heavy = len(inline_style_pages)
    total_rare_colors = len(rare_colors)
    total_no_shared = len(no_shared_input)
    print(f'  汇总: 共扫描{len(files)}个文件, {total_input_pages}个含input')
    print(f'    输入框风格不一致: {total_no_shared}个页面没用search-input共享类')
    print(f'    inline style集中: {total_inline_heavy}个页面有3+处inline style')
    print(f'    低频颜色: {total_rare_colors}种')
    print(f'    建议: 先统一 search-input → 再逐步迁移inline style到CSS类')
    print('═' * 60)

    return len(no_shared_input) + total_inline_heavy


if __name__ == '__main__':
    sys.exit(audit())

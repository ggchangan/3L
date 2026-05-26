"""部署构建脚本：npm build + 复制静态文件 + 验证"""
import os
import subprocess
import sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_DIR = os.path.join(ROOT, 'frontend')
DIST_DIR = os.path.join(FE_DIR, 'dist')


def run_npm_build():
    """Step 1: 运行 Vite 构建"""
    print('🧱 npm run build...')
    r = subprocess.run(['npm', 'run', 'build'], cwd=FE_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'❌ Vite build 失败:\n{r.stderr}')
        return False
    print(f'✅ Vite build 成功 ({len(r.stdout.splitlines())} lines)')
    return True


def inject_stock_card_css():
    """补丁：Vite 不自动引入 stock_card.css，手动注入到 monitor.html"""
    path = os.path.join(DIST_DIR, 'monitor.html')
    if not os.path.isfile(path):
        return True
    with open(path) as f:
        html = f.read()
    if '/css/stock_card.css' in html:
        return True
    html = html.replace(
        '<link rel="stylesheet" crossorigin href="/assets/monitor-',
        '<link rel="stylesheet" href="/css/stock_card.css?v=1">\n  <link rel="stylesheet" crossorigin href="/assets/monitor-',
        1
    )
    with open(path, 'w') as f:
        f.write(html)
    print('  ✅ stock_card.css -> 注入 dist/monitor.html')
    return True


def copy_static_files():
    """Step 2: 复制 css/ js/ 到 dist（Vite 只处理 JS import 的 CSS，不处理 <link> 引用的独立 CSS）"""
    print('📦 复制静态文件...')
    for sub in ('css', 'js'):
        src = os.path.join(FE_DIR, sub)
        dst = os.path.join(DIST_DIR, sub)
        if not os.path.isdir(src):
            continue
        for root, dirs, files in os.walk(src):
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, FE_DIR)
                dst_fp = os.path.join(DIST_DIR, rel)
                os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
                with open(fp, 'rb') as fin:
                    with open(dst_fp, 'wb') as fout:
                        fout.write(fin.read())
        print(f'  ✅ {sub}/ → dist/{sub}/')
    return True


def ensure_charts_symlink():
    """创建 dist/charts -> project_root/charts 软链"""
    link_path = os.path.join(DIST_DIR, 'charts')
    target = os.path.join(ROOT, 'charts')
    if os.path.islink(link_path):
        cur = os.readlink(link_path)
        if cur == target:
            return True
        os.unlink(link_path)
    elif os.path.exists(link_path):
        return True
    os.symlink(target, link_path)
    print('  ✅ charts/ symlink -> dist/charts/')
    return True


def validate_dist():
    """Step 3: 验证所有 HTML 引用的 css/js 文件在 dist 中存在"""
    print('🔍 验证 dist 完整性...')
    errors = []
    for f in os.listdir(DIST_DIR):
        if not f.endswith('.html'):
            continue
        fp = os.path.join(DIST_DIR, f)
        with open(fp) as fh:
            html = fh.read()
        # 找所有 <link href="..."> 和 <script src="...">
        for m in re.finditer(r'(?:href|src)="(/(?:css|js)/[^?"]+)(?:\?[^"]*)?"', html):
            url_path = m.group(1).lstrip('/')
            target = os.path.join(DIST_DIR, url_path)
            if not os.path.isfile(target):
                errors.append(f'  ❌ {f}: 引用 {m.group(1)} 但 dist 中不存在')

    if errors:
        print('\n'.join(errors))
        return False
    html_count = len([f for f in os.listdir(DIST_DIR) if f.endswith('.html')])
    print(f'  ✅ 所有 {html_count} 个 HTML 引用的文件均存在')
    return True


def main():
    print('═══════════════════════════════════')
    print('    3L 前端构建+部署')
    print('═══════════════════════════════════')
    if not run_npm_build():
        sys.exit(1)
    if not copy_static_files():
        sys.exit(1)
    if not inject_stock_card_css():
        sys.exit(1)
    if not ensure_charts_symlink():
        sys.exit(1)
    if not validate_dist():
        sys.exit(1)
    print('\n✅ 构建完整，dist 就绪')
    sys.exit(0)


if __name__ == '__main__':
    main()

"""部署构建脚本：npm build + 注入模块预加载"""
import os
import subprocess
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_DIR = os.path.join(ROOT, 'frontend')
DIST_DIR = os.path.join(FE_DIR, 'dist')


def run_npm_build():
    """运行 Vite 构建"""
    print('🧱 npm run build...')
    r = subprocess.run(['npm', 'run', 'build'], cwd=FE_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'❌ Vite build 失败:\n{r.stderr}')
        return False
    print(f'✅ Vite build 成功 ({len(r.stdout.splitlines())} lines)')
    return True


def inject_preload():
    """给 react.html 注入 modulepreload 链接
    只预加载入口块和 StockCard。"""
    html_path = os.path.join(DIST_DIR, 'react.html')
    if not os.path.isfile(html_path):
        print('⚠️  react.html 未找到，跳过预加载注入')
        return

    with open(html_path, 'r') as f:
        html = f.read()

    js_files = sorted(glob.glob(os.path.join(DIST_DIR, 'assets', '*.js')))

    # 只预加载：入口块（react-）+ StockCard（共享组件）
    KEEP = ('react-', 'StockCard-')

    preload_links = ''
    for js in js_files:
        fname = os.path.basename(js)
        if not fname.startswith(KEEP):
            continue
        preload_links += f'  <link rel="modulepreload" href="/assets/{fname}">\n'

    if not preload_links:
        return

    html = html.replace('</head>', preload_links + '</head>')

    with open(html_path, 'w') as f:
        f.write(html)

    print(f'✅ 注入 {preload_links.count("modulepreload")} 个 modulepreload 链接')


def main():
    print('═══════════════════════════════════')
    print('    3L 前端构建+部署')
    print('═══════════════════════════════════')
    if not run_npm_build():
        sys.exit(1)
    inject_preload()
    print('\n✅ 构建完整，dist 就绪')
    sys.exit(0)


if __name__ == '__main__':
    main()

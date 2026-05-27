"""部署构建脚本：npm build + 注入模块预加载"""
import os
import subprocess
import sys
import glob
import re

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
    SSR 已提供即时内容，只预加载入口块和 StockCard。"""
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


def build_ssr():
    """构建 SSR 服务端渲染包"""
    ssr_dir = os.path.join(DIST_DIR, 'ssr')
    if os.path.isdir(ssr_dir):
        import shutil
        shutil.rmtree(ssr_dir)

    print('🔧 SSR build...')
    r = subprocess.run(
        ['npx', 'vite', 'build', '--ssr', 'src/ssr-entry.tsx', '--outDir', 'dist/ssr'],
        cwd=FE_DIR, capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        print(f'❌ SSR build 失败:\n{r.stderr}')
        return False

    # 重命名为 .mjs（SSR server 用 ESM import）
    src = os.path.join(ssr_dir, 'ssr-entry.js')
    dst = os.path.join(ssr_dir, 'render.mjs')
    if os.path.isfile(src):
        os.rename(src, dst)

    out_files = sorted(glob.glob(os.path.join(ssr_dir, '*')))
    for f in out_files:
        print(f'  → {os.path.basename(f)} ({os.path.getsize(f) / 1024:.0f} KB)')

    print(f'✅ SSR build 成功')
    return True


def main():
    print('═══════════════════════════════════')
    print('    3L 前端构建+部署')
    print('═══════════════════════════════════')
    if not run_npm_build():
        sys.exit(1)
    inject_preload()
    if not build_ssr():
        sys.exit(1)
    print('\n✅ 构建完整，dist 就绪')
    sys.exit(0)


if __name__ == '__main__':
    main()

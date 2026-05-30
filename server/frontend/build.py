"""
3L 部署构建脚本：全回归 → npm build → 注入模块预加载

流程：
  1. 运行全回归测试（CRITICAL必须通过）
  2. npm run build
  3. 注入 modulepreload 链接
"""
import os
import subprocess
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_DIR = os.path.join(ROOT, 'frontend')
DIST_DIR = os.path.join(FE_DIR, 'dist')


def run_regression():
    """运行全回归测试（CRITICAL等级）"""
    print('🧪 运行全回归测试...')
    r = subprocess.run(
        [sys.executable, 'scripts/run_full_regression.py', '--ci'],
        cwd=ROOT, capture_output=True, text=True
    )
    # 输出结果
    for line in (r.stdout + r.stderr).split('\n'):
        if line.strip():
            print(f'  {line}')
    if r.returncode != 0:
        print('❌ 回归测试失败，构建终止')
        print(r.stderr[-500:])
        return False
    print('✅ 回归测试通过')
    return True


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


def copy_assets():
    """将静态资源（WAV 音效等）复制到 dist 目录"""
    src = os.path.join(FE_DIR, 'src', 'assets', 'sounds')
    dst = os.path.join(DIST_DIR, 'assets', 'sounds')
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if f.endswith('.wav') or f.endswith('.mp3'):
                import shutil
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
        print(f'✅ 复制 {len(os.listdir(src))} 个音效文件到 dist')


def main():
    print('═══════════════════════════════════')
    print('    3L 前端构建+部署')
    print('═══════════════════════════════════')
    if not run_regression():
        sys.exit(1)
    if not run_npm_build():
        sys.exit(1)
    inject_preload()
    copy_assets()
    print('\n✅ 构建完整，dist 就绪')
    sys.exit(0)


if __name__ == '__main__':
    main()

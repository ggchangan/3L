"""部署构建脚本：npm build 后部署到 dist"""
import os
import subprocess
import sys

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


def main():
    print('═══════════════════════════════════')
    print('    3L 前端构建+部署')
    print('═══════════════════════════════════')
    if not run_npm_build():
        sys.exit(1)
    print('\n✅ 构建完整，dist 就绪')
    sys.exit(0)


if __name__ == '__main__':
    main()

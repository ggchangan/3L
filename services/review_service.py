"""
复盘存档服务 — 复盘数据的读取/写入/存档管理
"""
import json, os, sys
from datetime import datetime
from config import REVIEW_ARCHIVE_DIR, REVIEW_DATA_PATH
from config import WWW_DIR, PRIVATE_DIR, SCRIPTS_DIR, MOMENTUM_CACHE_PREFIX


def load_review_data():
    """加载复盘内存缓存数据"""
    if os.path.isfile(REVIEW_DATA_PATH):
        with open(REVIEW_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'date': '', 'market': {}, 'mainline': {}, 'timing_signals': {},
            'trading_plan': {}, 'holdings': [], 'buy_signals': []}


def save_review_data(data):
    """保存复盘数据到文件"""
    os.makedirs(os.path.dirname(REVIEW_DATA_PATH), exist_ok=True)
    config.atomic_json_dump(data, REVIEW_DATA_PATH, indent=2)


def get_archive_dates():
    """获取所有复盘存档日期（倒序）"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return []
    files = sorted([f.replace('.json', '') for f in os.listdir(REVIEW_ARCHIVE_DIR)
                    if f.endswith('.json')], reverse=True)
    return files


def get_archive(date_str):
    """获取指定日期的复盘存档"""
    path = os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_latest_archive():
    """获取最新一份复盘存档"""
    dates = get_archive_dates()
    if dates:
        return get_archive(dates[0])
    return None


def save_review(data):
    """
    保存复盘数据到两个位置：
      1) data/review_archive/{date}.json（新格式目录）
      2) private/review_archive/{date}.json（兼容旧版）
    """
    date = data.get('date', '')
    if not date:
        return {'status': 'error', 'msg': 'missing date'}
    adir = os.path.join(os.path.dirname(REVIEW_ARCHIVE_DIR), 'data', 'review_archive')
    os.makedirs(adir, exist_ok=True)
    fp = os.path.join(adir, f'{date}.json')
    config.atomic_json_dump(data, fp, indent=2)
    pdir = REVIEW_ARCHIVE_DIR
    os.makedirs(pdir, exist_ok=True)
    pf = os.path.join(pdir, f'{date}.json')
    config.atomic_json_dump(data, pf, indent=2)
    return {'status': 'ok'}


def run_daily_review():
    """运行每日复盘完整流水线（cron调用），返回日志列表"""
    import subprocess, shutil
    DATE = datetime.now().strftime('%Y-%m-%d')
    logs = []
    def run_script(desc, cmd, cwd=None):
        logs.append(f'[{datetime.now().strftime("%H:%M:%S")}] {desc}...')
        try:
            env = os.environ.copy()
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=cwd, env=env)
            if r.returncode == 0:
                logs.append(f'  ✅成功 ({len(r.stdout)}B)')
            else:
                logs.append(f'  ⚠️失败(code={r.returncode}): {r.stderr[-200:]}')
        except Exception as e:
            logs.append(f'  ❌异常: {str(e)}')
    SCRIPTS = SCRIPTS_DIR
    for f in ['review_data.json', f'review_archive/{DATE}.json']:
        fp = os.path.join(PRIVATE_DIR, f)
        if os.path.isfile(fp): os.remove(fp)
    run_script('Step1 更新数据+扫买点',
        [sys.executable, f'{SCRIPTS}/update_stock_data.py'], cwd=WWW_DIR)
    run_script('Step3a 中证全指图',
        [sys.executable, os.path.join(WWW_DIR, 'gen_index_chart.py')])
    try:
        shutil.copy2(os.path.join(config.CHARTS_DIR, 'sz000985.svg'),
                     os.path.join(config.CHARTS_DIR, 'zzqz_v2.svg'))
        logs.append(f'  ✅SVG已复制')
    except Exception as e:
        logs.append(f'  ⚠️SVG复制失败: {e}')
    run_script('Step3b 批量个股图',
        [sys.executable, f'{SCRIPTS}/batch_gen_charts.py'])
    mom_cache = f'{MOMENTUM_CACHE_PREFIX}{DATE}.json'
    if os.path.isfile(mom_cache): os.remove(mom_cache)
    run_script('Step4a 拉取动量数据',
        [sys.executable, os.path.join(WWW_DIR, 'fetch_momentum.py')])
    run_script('Step4b 生成复盘',
        [sys.executable, os.path.join(WWW_DIR, 'generate_review_data.py'), DATE])
    return {'status': 'ok', 'date': DATE, 'logs': logs}


def generate_review(date_arg=None):
    """单独生成复盘数据（通过 /api/review/generate 调用）"""
    import subprocess
    cmd = [sys.executable, os.path.join(WWW_DIR, 'generate_review_data.py')]
    if date_arg:
        cmd.append(date_arg)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        return {'status': 'ok', 'output': result.stdout[-500:]}
    else:
        return {'status': 'error', 'output': result.stderr[-500:]}


def get_mainline_archive():
    """获取主线数据（包括次级主线）"""
    archive = get_latest_archive()
    if archive and 'mainline' in archive:
        return archive['mainline']
    return {}

"""
3L 交易系统 — 集中配置文件
所有路径/常量集中在此，其他模块通过 config.XXX 引用

环境变量覆盖（通过 .env 文件或 export）:
  WWW_DIR, DATA_DIR, PORT, LOG_LEVEL, LOG_DIR
"""

import os, json, tempfile
from threading import Lock

# ── 从 .env 文件加载（如果存在）──────────────────
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
if os.path.isfile(_env_path):
    with open(_env_path, 'r') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#'):
                continue
            if '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── 工具函数 ────────────────────────────────────
def _env(key, default):
    return os.environ.get(key, default)

# =====================================================
# 项目根路径
# =====================================================
WWW_DIR = _env('WWW_DIR', '/home/ubuntu/3l-server')
DATA_DIR = _env('DATA_DIR', '/home/ubuntu/data/3l')
CONFIG_DIR = os.path.join(DATA_DIR, 'config')
COMPUTED_DIR = os.path.join(DATA_DIR, 'computed')

# =====================================================
# 数据文件路径
# =====================================================
ALL_CODES_PATH = os.path.join(DATA_DIR, 'all_stock_codes.json')

# 用户配置（config/）
WATCHLIST_PATH = os.path.join(CONFIG_DIR, 'watchlist.json')
WATCHED_INDUSTRIES_PATH = os.path.join(CONFIG_DIR, 'watched_industries.json')
HOLDINGS_PATH = os.path.join(CONFIG_DIR, 'holdings.json')
TRADES_PATH = os.path.join(CONFIG_DIR, 'trades.json')
MANUAL_TREND_PATH = os.path.join(CONFIG_DIR, 'manual_trend.json')
MAINLINES_CACHE_PATH = os.path.join(CONFIG_DIR, 'mainlines_cache.json')
REVIEW_DATA_PATH = os.path.join(CONFIG_DIR, 'review_data.json')

# 计算结果（computed/）
INDUSTRY_MAP_PATH = os.path.join(COMPUTED_DIR, 'stock_industry_map.json')
SUB_SECTOR_CLUSTERS_PATH = os.path.join(COMPUTED_DIR, 'sub_sector_clusters.json')
FINANCIAL_CACHE_PATH = os.path.join(COMPUTED_DIR, 'financial_data_cache.json')
PROFIT_QUALITY_PATH = os.path.join(COMPUTED_DIR, 'profit_quality.json')
INDUSTRY_LEADERS_PATH = os.path.join(COMPUTED_DIR, 'industry_leaders.json')
LATEST_SCAN_PATH = os.path.join(COMPUTED_DIR, 'scan_result.json')
LOGIC_TRACKING_PATH = os.path.join(COMPUTED_DIR, 'logic_tracking.json')
SOURCE_HEALTH_PATH = os.path.join(COMPUTED_DIR, 'source_health.json')
KEY_POINTS_DIR = os.path.join(COMPUTED_DIR, 'key_points')

# 概念映射
CONCEPT_LIST_PATH = os.path.join(DATA_DIR, 'map', 'concept_list.json')
STOCK_CONCEPT_MAP_PATH = os.path.join(DATA_DIR, 'map', 'stock_concept.json')

# 运行时缓存（cache/）

# 前端公开数据
SCRIPTS_DIR = os.path.join(WWW_DIR, 'scripts')

# =====================================================
# 缓存目录/文件
# =====================================================
CACHE_DIR = os.path.join(DATA_DIR, 'cache')
ANALYSIS_CACHE_PATH = os.path.join(CACHE_DIR, 'watchlist_analysis_cache.json')
ON_DEMAND_CACHE_PATH = os.path.join(CACHE_DIR, 'stock_on_demand_cache.json')

# =====================================================
# 知识库
# =====================================================
KB_BASE = os.path.join(DATA_DIR, 'knowledge_base')
TRADING_TIPS_DIR = os.path.join(KB_BASE, 'trading_tips')

# =====================================================
# 私人数据（持仓、交易、复盘存档）
# =====================================================
PRIVATE_DIR = os.path.join(DATA_DIR, 'private')
REVIEW_ARCHIVE_DIR = os.path.join(PRIVATE_DIR, 'review_archive')
BT_RESULTS_PATH = os.path.join(WWW_DIR, 'files', 'buy_signal_backtest_results.json')

# =====================================================
# 公开访问的后端生成文件（统一由 /pub/ 路由服务）
# =====================================================
PUBLIC_DIR = os.path.join(WWW_DIR, 'data', 'public')
CHARTS_DIR = os.path.join(PUBLIC_DIR, 'charts')
FILES_DIR = os.path.join(PUBLIC_DIR, 'files')
PINYIN_PATH = os.path.join(PUBLIC_DIR, 'pinyin.json')

# =====================================================
# 复盘图表
# =====================================================
REVIEW_CHARTS_DIR = CHARTS_DIR

# =====================================================
# Tushare Pro 配置（2026-06-14 新增）
# 从 .env 读取，不硬编码
# =====================================================
TUSHARE_TOKEN = _env('TUSHARE_TOKEN', '')
TUSHARE_TOKEN_HIGH = _env('TUSHARE_TOKEN_HIGH', '') or TUSHARE_TOKEN
TUSHARE_PROXY_URL = _env('TUSHARE_PROXY_URL', '')

# MySQL 数据库配置
MYSQL_HOST = _env('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(_env('MYSQL_PORT', '3306'))
MYSQL_USER = _env('MYSQL_USER', 'tushare')
MYSQL_PASSWORD = _env('MYSQL_PASSWORD', 'tushare_pass')
MYSQL_DATABASE = _env('MYSQL_DATABASE', 'tushare')

# =====================================================
# 服务器配置
# =====================================================
SERVER_PORT = int(_env('PORT', '8080'))
SERVER_HOST = _env('SERVER_HOST', '127.0.0.1')
AUTH_USER = _env('AUTH_USER', '')
AUTH_PASS = _env('AUTH_PASS', '')
MOMENTUM_CACHE_PREFIX = os.path.join(WWW_DIR, 'data', 'cache', 'momentum_')

# =====================================================
# 数据库/存档历史路径
# =====================================================
SIMULATION_DIR = os.path.join(DATA_DIR, 'simulation')
SIMULATION_V3_DIR = os.path.join(SIMULATION_DIR, 'v3')

# =====================================================
# 日志
# =====================================================
LOG_LEVEL = _env('LOG_LEVEL', 'INFO')
LOG_DIR = _env('LOG_DIR', os.path.join(WWW_DIR, 'logs'))

# =====================================================
# SVG 图表路径模板
# =====================================================
# ── 文件写入锁（防止多线程并发覆盖）──────────────
_FILE_WRITE_LOCK = Lock()

def atomic_json_dump(data, path, indent=None):
    """原子写入JSON：先写临时文件，再rename替换，避免崩溃导致文件损坏。线程安全。"""
    with _FILE_WRITE_LOCK:
        dirname = os.path.dirname(path)
        os.makedirs(dirname, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', dir=dirname, delete=False, suffix='.tmp') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            tmp = f.name
        os.replace(tmp, path)

def review_chart_svg(code):
    return os.path.join(REVIEW_CHARTS_DIR, f'{code}.svg')

def trend_chart_svg(code):
    return os.path.join(REVIEW_CHARTS_DIR, f'trend_{code}.svg')

def backtest_chart_svg(code):
    return os.path.join(REVIEW_CHARTS_DIR, f'bt_{code}.svg')

def cleanup_cache():
    """清理过期缓存文件（超过 CACHE_MAX_AGE_DAYS 的文件自动删除）"""
    import re, time, logging
    logger = logging.getLogger('config.cleanup')
    now = time.time()
    max_age = 30 * 86400  # 默认保留30天
    total_removed = 0

    for cache_path in [CACHE_DIR, os.path.join(WWW_DIR, 'data', 'cache')]:
        if not os.path.isdir(cache_path):
            continue
        for fname in os.listdir(cache_path):
            fpath = os.path.join(cache_path, fname)
            if not os.path.isfile(fpath):
                continue
            # 从文件名提取日期判断（格式：name_YYYY-MM-DD.json 或 name_YYYYMMDD.json）
            m = re.search(r'(20\d{2}[_-]\d{2}[_-]\d{2}|20\d{6})', fname)
            if m:
                try:
                    date_str = m.group(1).replace('_', '').replace('-', '')
                    ftime = time.mktime(time.strptime(date_str[:8], '%Y%m%d'))
                except (ValueError, OverflowError):
                    ftime = os.path.getmtime(fpath)
            else:
                ftime = os.path.getmtime(fpath)

            if now - ftime > max_age:
                try:
                    os.remove(fpath)
                    total_removed += 1
                    logger.info(f'清理过期缓存: {fname}')
                except OSError:
                    logger.warning(f'清理缓存失败: {fname}')
    if total_removed:
        logger.info(f'缓存清理完成，共删除 {total_removed} 个文件')
    return total_removed

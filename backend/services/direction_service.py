"""方向管理服务 — 独立于 watchlist 的 standalone 模块

数据存储: {DATA_DIR}/directions.json
格式:
{
  "all": ["半导体", "算力"],
  "active": ["半导体"],
  "suggestions": {
    "industry": ["元件", "光模块"],
    "concept": ["AI", "低空经济"],
    "custom": ["北交所", "科创板"]
  }
}
"""
import json
import os
from backend.config import DATA_DIR

DIRECTIONS_FILE = os.environ.get('DIRECTIONS_PATH',
    os.path.join(DATA_DIR, 'directions.json'))


def _load():
    if os.path.isfile(DIRECTIONS_FILE):
        with open(DIRECTIONS_FILE, 'r') as f:
            return json.load(f)
    return {'all': [], 'active': []}


def _save(data):
    with open(DIRECTIONS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── CRUD ──

def get_all():
    """返回所有方向 {name: active: bool}"""
    data = _load()
    active_set = set(data.get('active', []))
    return {name: name in active_set for name in data.get('all', [])}


def get_active():
    """返回已启用方向名称列表"""
    data = _load()
    return data.get('active', [])


def add(name):
    """添加方向（默认启用）"""
    name = name.strip()
    if not name:
        return {'success': False, 'error': '方向名称不能为空'}
    if name in ('全部', '其他'):
        return {'success': False, 'error': '不能添加系统保留方向'}
    data = _load()
    if name in data['all']:
        return {'success': False, 'error': f'方向 "{name}" 已存在'}
    data['all'].append(name)
    if name not in data['active']:
        data['active'].append(name)
    _save(data)
    return {'success': True, 'name': name}


def remove(name):
    """删除方向（该方向股票归其他）"""
    if name == '其他':
        return {'success': False, 'error': '不能删除"其他"方向'}
    data = _load()
    if name not in data['all']:
        return {'success': False, 'error': f'方向 "{name}" 不存在'}
    data['all'].remove(name)
    data['active'] = [d for d in data['active'] if d != name]
    _save(data)
    return {'success': True}


def set_active(name, active):
    """启用/禁用方向"""
    data = _load()
    if name not in data['all']:
        return {'success': False, 'error': f'方向 "{name}" 不存在'}
    if active and name not in data['active']:
        data['active'].append(name)
    elif not active and name in data['active']:
        data['active'].remove(name)
    _save(data)
    return {'success': True}


# ── 排序 ──

def get_all_ordered():
    """返回有序的所有方向名称列表"""
    data = _load()
    return data.get('all', [])


def reorder(names):
    """重新排序方向"""
    data = _load()
    existing = set(data['all'])
    if set(names) != existing:
        missing = existing - set(names)
        extra = set(names) - existing
        msg = []
        if missing: msg.append(f'缺少: {missing}')
        if extra: msg.append(f'多余: {extra}')
        return {'success': False, 'error': '; '.join(msg) or '方向集合不匹配'}
    data['all'] = names
    active_set = set(data['active'])
    data['active'] = [n for n in names if n in active_set]
    _save(data)
    return {'success': True}


# ── 建议来源 ──

def get_suggestions():
    """返回建议方向（综合来源）"""
    data = _load()
    existing = data.get('suggestions', {})
    if existing:
        return existing

    # 首次调用时自动生成
    suggestions = {'industry': [], 'concept': [], 'custom': []}

    # 从 industry map 提取行业
    imp = os.path.join(DATA_DIR, 'stock_industry_map.json')
    if os.path.isfile(imp):
        with open(imp) as f:
            im = json.load(f)
        industries = set()
        for info in im.values():
            ind = info.get('ths_industry', '')
            if ind and len(ind) <= 6:
                industries.add(ind)
        suggestions['industry'] = sorted(industries)[:30]

    # 自定义推荐
    suggestions['custom'] = [
        '北交所', '科创板', '高股息', '军工', '国企改革',
        '并购重组', '大金融', '周期股',
    ]

    data['suggestions'] = suggestions
    _save(data)
    return suggestions


# ── 数据迁移（从旧 watchlist.json 导入） ──

def migrate_from_watchlist(wl_path=None):
    """从 watchlist.json 的 directions 字段迁移到独立文件"""
    if wl_path is None:
        wl_path = os.path.join(DATA_DIR, 'watchlist.json')
    if not os.path.isfile(wl_path):
        return {'success': False, 'error': 'watchlist.json 不存在'}

    with open(wl_path) as f:
        wl = json.load(f)

    # 从股票 direction 字段提取
    stocks = wl.get('stocks', [])
    dirs_set = set()
    for s in stocks:
        d = s.get('direction', '')
        if d and d not in ('全部',):
            dirs_set.add(d)

    all_dirs = sorted(dirs_set)
    active_dirs = list(all_dirs)  # 默认全部启用

    data = {'all': all_dirs, 'active': active_dirs}
    _save(data)
    return {'success': True, 'migrated': len(all_dirs), 'active': len(active_dirs)}

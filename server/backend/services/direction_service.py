"""方向管理服务 — 方向分层 + 概念绑定（V2）

数据格式 (directions.json):
{
  "version": 2,
  "categories": {
    "科技": {"order": 0, "enabled": true},
    "医药": {"order": 1, "enabled": true}
  },
  "sub_directions": {
    "科技.半导体": {
      "category": "科技", "enabled": true, "order": 0,
      "concept_codes": ["301085", "307940"],
      "concept_names": ["芯片概念", "存储芯片"]
    }
  },
  "suggestions": {"industry": [...], "concept": [...], "custom": [...]},
  "core": {"002371": {"name": "北方华创", "deviation": 6}}
}
"""
import json
import os
import logging

from backend.config import DATA_DIR as _DATA_DIR

logger = logging.getLogger(__name__)

DATA_DIR = _DATA_DIR  # 暴露给测试
DIRECTIONS_FILE = os.environ.get('DIRECTIONS_PATH',
                                 os.path.join(DATA_DIR, 'directions.json'))

# ── 概念数据路径 ──
CONCEPT_LIST_PATH = os.path.join(DATA_DIR, 'map', 'concept_list.json')

# ── 默认结构 ──
_DEFAULT_V2 = {
    "version": 2,
    "categories": {},
    "sub_directions": {},
    "suggestions": {"industry": [], "concept": [], "custom": []},
    "core": {},
}


def _default_v2():
    """返回默认 V2 结构的深拷贝"""
    return {
        "version": 2,
        "categories": {},
        "sub_directions": {},
        "suggestions": {"industry": [], "concept": [], "custom": []},
        "core": {},
    }


# ═══════════════════════════════════════════════════════════
# 内部 IO
# ═══════════════════════════════════════════════════════════

def _load():
    """加载数据，自动兼容 V1 → V2 升级"""
    if os.path.isfile(DIRECTIONS_FILE):
        try:
            with open(DIRECTIONS_FILE, 'r') as f:
                content = f.read().strip()
            if not content:
                return _default_v2()
            data = json.loads(content)
        except (json.JSONDecodeError, OSError):
            logger.warning('directions.json 损坏，返回默认结构')
            return _default_v2()
    else:
        return _default_v2()

    # V1 → V2 自动升级
    if data.get('version') != 2:
        data = _migrate_v1_to_v2_inplace(data)
    else:
        # 确保 V2 所有字段存在
        data.setdefault('categories', {})
        data.setdefault('sub_directions', {})
        data.setdefault('suggestions', {"industry": [], "concept": [], "custom": []})
        data.setdefault('core', {})

    return data


def _save(data):
    """原子写入 JSON"""
    dirname = os.path.dirname(DIRECTIONS_FILE)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(DIRECTIONS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _migrate_v1_to_v2_inplace(data):
    """V1 → V2 原位升级。V1 格式: {all: [...], active: [...], suggestions: {...}, core: {...}}"""
    v2 = _default_v2()
    v2['suggestions'] = data.get('suggestions', {"industry": [], "concept": [], "custom": []})
    v2['core'] = data.get('core', {})

    # 保留 category="" 作为"未分类"
    old_all = data.get('all', [])
    old_active_set = set(data.get('active', []))

    v2['categories']["未分类"] = {"order": 0, "enabled": True}
    for idx, name in enumerate(old_all):
        key = name  # 没有分类前缀，直接使用原名
        v2['sub_directions'][key] = {
            "category": "未分类",
            "enabled": name in old_active_set or name not in ('其他',),
            "order": idx,
            "concept_codes": [],
            "concept_names": [],
        }

    return v2


# ═══════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════

def parse_direction(full_name: str) -> tuple:
    """解析 "科技.半导体" → ("科技", "半导体")。没有点号时 category="" """
    if '.' in full_name:
        cat, _, sub = full_name.partition('.')
        return cat, sub
    return "", full_name


def format_direction(category: str, sub_direction: str) -> str:
    """("科技", "半导体") → "科技.半导体"。category 为空时返回 sub_direction"""
    if category:
        return f"{category}.{sub_direction}"
    return sub_direction


# ═══════════════════════════════════════════════════════════
# CATEGORY 操作
# ═══════════════════════════════════════════════════════════

def add_category(name: str) -> dict:
    """添加分类"""
    name = name.strip()
    if not name:
        return {'success': False, 'error': '分类名称不能为空'}
    data = _load()
    if name in data['categories']:
        return {'success': False, 'error': f'分类 "{name}" 已存在'}
    max_order = max((c['order'] for c in data['categories'].values()), default=-1)
    data['categories'][name] = {"order": max_order + 1, "enabled": True}
    _save(data)
    return {'success': True, 'name': name}


def remove_category(name: str) -> dict:
    """删除分类及其下所有细分方向"""
    data = _load()
    if name not in data['categories']:
        return {'success': False, 'error': f'分类 "{name}" 不存在'}
    del data['categories'][name]
    # 删除该分类下的所有细分方向
    keys_to_delete = [
        k for k, v in data['sub_directions'].items()
        if v.get('category') == name
    ]
    for k in keys_to_delete:
        del data['sub_directions'][k]
    _save(data)
    return {'success': True, 'removed_sub_directions': len(keys_to_delete)}


def get_categories() -> dict:
    """返回 {分类名: {order, enabled}}"""
    data = _load()
    return dict(data.get('categories', {}))


def set_category_enabled(name: str, enabled: bool) -> dict:
    """启用/禁用分类"""
    data = _load()
    if name not in data['categories']:
        return {'success': False, 'error': f'分类 "{name}" 不存在'}
    data['categories'][name]['enabled'] = enabled
    _save(data)
    return {'success': True}


def rename_category(old_name: str, new_name: str) -> dict:
    """重命名分类，同时更新 sub_directions 中的 category 引用"""
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not new_name:
        return {'success': False, 'error': '新名称不能为空'}
    data = _load()
    if old_name not in data['categories']:
        return {'success': False, 'error': f'分类 "{old_name}" 不存在'}
    if new_name in data['categories']:
        return {'success': False, 'error': f'分类 "{new_name}" 已存在'}

    # 重命名分类键
    data['categories'][new_name] = data['categories'].pop(old_name)

    # 更新所有细分方向的 category 字段和 key
    new_subs = {}
    for key, sub in data['sub_directions'].items():
        if sub.get('category') == old_name:
            sub['category'] = new_name
            new_key = format_direction(new_name, sub['sub_name'] if 'sub_name' in sub else _extract_sub_name(key, old_name))
            # 重建 key
            old_sub_name = _extract_sub_name(key, old_name)
            new_key = format_direction(new_name, old_sub_name)
            new_subs[new_key] = sub
        else:
            new_subs[key] = sub
    data['sub_directions'] = new_subs
    _save(data)
    return {'success': True}


def _extract_sub_name(full_key: str, category: str) -> str:
    """从 "科技.半导体" 中提取 "半导体"（假设 category 已知）"""
    if full_key.startswith(category + '.'):
        return full_key[len(category) + 1:]
    return full_key


def reorder_categories(names: list) -> dict:
    """按 names 顺序重新排列分类"""
    data = _load()
    existing = set(data['categories'].keys())
    if set(names) != existing:
        missing = existing - set(names)
        extra = set(names) - existing
        msg = []
        if missing: msg.append(f'缺少: {missing}')
        if extra: msg.append(f'多余: {extra}')
        return {'success': False, 'error': '; '.join(msg) or '分类集合不匹配'}
    for idx, name in enumerate(names):
        data['categories'][name]['order'] = idx
    _save(data)
    return {'success': True}


# ═══════════════════════════════════════════════════════════
# SUB_DIRECTION 操作
# ═══════════════════════════════════════════════════════════

def add_sub_direction(category: str, name: str, *, auto_create_category: bool = True, enabled: bool = True) -> dict:
    """添加细分方向

    Args:
        category: 分类名称
        name: 细分方向名称
        auto_create_category: 分类不存在时自动创建
        enabled: 是否启用
    """
    name = name.strip()
    if not name:
        return {'success': False, 'error': '细分方向名称不能为空'}
    data = _load()

    if category not in data['categories']:
        if auto_create_category:
            max_order = max((c['order'] for c in data['categories'].values()), default=-1)
            data['categories'][category] = {"order": max_order + 1, "enabled": True}
        else:
            return {'success': False, 'error': f'分类 "{category}" 不存在，请先添加分类'}

    key = format_direction(category, name)
    if key in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{key}" 已存在'}

    # 计算 order
    same_cat_subs = [v for v in data['sub_directions'].values() if v.get('category') == category]
    max_order = max((s['order'] for s in same_cat_subs), default=-1)

    data['sub_directions'][key] = {
        "category": category,
        "enabled": enabled,
        "order": max_order + 1,
        "concept_codes": [],
        "concept_names": [],
    }
    _save(data)
    return {'success': True, 'name': name, 'key': key}


def remove_sub_direction(category: str, name: str) -> dict:
    """删除细分方向"""
    key = format_direction(category, name)
    data = _load()
    if key not in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{key}" 不存在'}
    del data['sub_directions'][key]
    _save(data)
    return {'success': True}


def get_sub_directions(category: str = None) -> dict:
    """获取细分方向

    Args:
        category: 可选，按分类筛选

    Returns:
        {full_key: {category, enabled, order, concept_codes, concept_names}}
    """
    data = _load()
    subs = data.get('sub_directions', {})
    if category is not None:
        return {k: v for k, v in subs.items() if v.get('category') == category}
    return dict(subs)


def set_sub_direction_enabled(category: str, name: str, enabled: bool) -> dict:
    """启用/禁用细分方向"""
    key = format_direction(category, name)
    data = _load()
    if key not in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{key}" 不存在'}
    data['sub_directions'][key]['enabled'] = enabled
    _save(data)
    return {'success': True}


def rename_sub_direction(category: str, old_name: str, new_name: str) -> dict:
    """重命名细分方向"""
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not new_name:
        return {'success': False, 'error': '新名称不能为空'}

    old_key = format_direction(category, old_name)
    new_key = format_direction(category, new_name)

    data = _load()
    if old_key not in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{old_key}" 不存在'}
    if new_key in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{new_key}" 已存在'}

    data['sub_directions'][new_key] = data['sub_directions'].pop(old_key)
    _save(data)
    return {'success': True}


def move_sub_direction(category: str, sub_name: str, new_category: str, *, auto_create_category: bool = True) -> dict:
    """将细分方向移动到另一个大类

    Args:
        category: 当前所属分类
        sub_name: 细分方向名称
        new_category: 目标分类
        auto_create_category: 目标分类不存在时自动创建
    """
    sub_name = sub_name.strip()
    new_category = new_category.strip()
    if not sub_name:
        return {'success': False, 'error': '细分方向名称不能为空'}
    if not new_category:
        return {'success': False, 'error': '目标分类名称不能为空'}
    if new_category == category:
        return {'success': False, 'error': '已经在当前分类中'}

    old_key = format_direction(category, sub_name)
    data = _load()

    # V1 迁移兼容：如果 format_direction 的 key 找不到，尝试直接用 sub_name（V1 格式无前缀）
    if old_key not in data['sub_directions']:
        if sub_name in data['sub_directions']:
            old_key = sub_name
        else:
            return {'success': False, 'error': f'细分方向 "{old_key}" 或 "{sub_name}" 不存在'}

    # 确保目标分类存在
    if new_category not in data['categories']:
        if auto_create_category:
            max_order = max((c['order'] for c in data['categories'].values()), default=-1)
            data['categories'][new_category] = {"order": max_order + 1, "enabled": True}
        else:
            return {'success': False, 'error': f'分类 "{new_category}" 不存在，请先添加分类'}

    new_key = format_direction(new_category, sub_name)
    if new_key in data['sub_directions']:
        return {'success': False, 'error': f'目标细分方向 "{new_key}" 已存在'}

    # 复制并更新 category 字段
    sub_info = data['sub_directions'].pop(old_key)
    sub_info['category'] = new_category
    # 计算新分类下的 order
    same_cat_subs = [v for v in data['sub_directions'].values() if v.get('category') == new_category]
    sub_info['order'] = max((s['order'] for s in same_cat_subs), default=-1) + 1
    data['sub_directions'][new_key] = sub_info

    # 同步更新 watchlist 中股票的 directions 字段
    wl_path = os.path.join(DATA_DIR, 'watchlist.json')
    if os.path.isfile(wl_path):
        try:
            with open(wl_path, 'r') as f:
                wl = json.load(f)
            changed = 0
            for s in wl.get('stocks', []):
                dirs = s.get('directions', [])
                # 新格式 directions 数组
                if isinstance(dirs, list) and old_key in dirs:
                    dirs.remove(old_key)
                    if new_key not in dirs:
                        dirs.append(new_key)
                    changed += 1
                # 旧格式 direction 字符串（也包括 directions=[] 但 direction 有值的情况）
                d = s.get('direction', '')
                if d and d == old_key:
                    s['direction'] = new_key
                    changed += 1
            if changed > 0:
                with open(wl_path, 'w') as f:
                    json.dump(wl, f, ensure_ascii=False, indent=2)
                # 强制刷新缓存
                try:
                    from scripts.cache_layer import cache as _cl
                    _cl.invalidate('watchlist')
                except ImportError:
                    pass
        except (OSError, json.JSONDecodeError):
            pass

    _save(data)
    return {'success': True, 'old_key': old_key, 'new_key': new_key}


def reorder_sub_directions(category: str, names: list) -> dict:
    """按 names 顺序重新排列某分类下的细分方向

    names: 完整 key 列表 ["科技.AI", "科技.算力", ...] 或子名称列表 ["AI", "算力", ...]
    """
    data = _load()
    subs = data['sub_directions']

    # 判断 names 是完整 key 还是子名称
    if names and '.' in names[0]:
        keys = names
    else:
        keys = [format_direction(category, n) for n in names]

    same_cat_keys = {k for k, v in subs.items() if v.get('category') == category}
    if set(keys) != same_cat_keys:
        missing = same_cat_keys - set(keys)
        extra = set(keys) - same_cat_keys
        msg = []
        if missing: msg.append(f'缺少: {missing}')
        if extra: msg.append(f'多余: {extra}')
        return {'success': False, 'error': '; '.join(msg) or '细分方向集合不匹配'}

    for idx, key in enumerate(keys):
        subs[key]['order'] = idx

    _save(data)
    return {'success': True}


# ═══════════════════════════════════════════════════════════
# 概念绑定
# ═══════════════════════════════════════════════════════════

def bind_concept(category: str, sub_name: str, concept_code: str, concept_name: str = "") -> dict:
    """绑定概念到一个细分方向"""
    key = format_direction(category, sub_name)
    data = _load()
    if key not in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{key}" 不存在'}
    sub = data['sub_directions'][key]
    codes = sub.setdefault('concept_codes', [])
    names = sub.setdefault('concept_names', [])
    if concept_code not in codes:
        codes.append(concept_code)
        names.append(concept_name or _lookup_concept_name(concept_code) or concept_code)
    _save(data)
    return {'success': True}


def unbind_concept(category: str, sub_name: str, concept_code: str) -> dict:
    """解绑概念"""
    key = format_direction(category, sub_name)
    data = _load()
    if key not in data['sub_directions']:
        return {'success': False, 'error': f'细分方向 "{key}" 不存在'}
    sub = data['sub_directions'][key]
    codes = sub.get('concept_codes', [])
    names = sub.get('concept_names', [])
    if concept_code not in codes:
        return {'success': False, 'error': f'概念代码 "{concept_code}" 未绑定'}
    idx = codes.index(concept_code)
    codes.pop(idx)
    if idx < len(names):
        names.pop(idx)
    _save(data)
    return {'success': True}


def get_bound_concepts(category: str, sub_name: str) -> dict:
    """获取已绑定的概念 {code: name}"""
    key = format_direction(category, sub_name)
    data = _load()
    if key not in data['sub_directions']:
        return {}
    sub = data['sub_directions'][key]
    codes = sub.get('concept_codes', [])
    names = sub.get('concept_names', [])
    return dict(zip(codes, names)) if codes else {}


def _lookup_concept_name(code: str) -> str:
    """在概念列表中查询概念名称"""
    try:
        if os.path.isfile(CONCEPT_LIST_PATH):
            with open(CONCEPT_LIST_PATH, 'r') as f:
                concepts = json.load(f)
            info = concepts.get(code)
            if info:
                return info.get('name', '')
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def search_concepts(q: str) -> dict:
    """搜索概念 {code: name}，模糊匹配"""
    if not q:
        return {}
    results = {}
    try:
        if os.path.isfile(CONCEPT_LIST_PATH):
            with open(CONCEPT_LIST_PATH, 'r') as f:
                concepts = json.load(f)
        else:
            return {}
    except (OSError, json.JSONDecodeError):
        return {}

    q_lower = q.lower()
    for code, info in concepts.items():
        name = info.get('name', '')
        if q_lower in name.lower():
            results[code] = name
    return results


# ═══════════════════════════════════════════════════════════
# 兼容接口（保持 V1 签名不变）
# ═══════════════════════════════════════════════════════════

def get_active():
    """返回已启用的细分方向完整名称列表"""
    data = _load()
    subs = data.get('sub_directions', {})
    return [k for k, v in subs.items() if v.get('enabled', True)]


def get_all():
    """返回 {完整名称: enabled} 字典"""
    data = _load()
    subs = data.get('sub_directions', {})
    return {k: v.get('enabled', True) for k, v in subs.items()}


def get_all_ordered():
    """返回有序的细分方向完整名称列表（按 order 排序）"""
    data = _load()
    subs = data.get('sub_directions', {})
    sorted_subs = sorted(subs.items(), key=lambda x: (x[1].get('order', 0)))
    return [k for k, v in sorted_subs]


def reorder(names: list) -> dict:
    """重新排序所有细分方向（兼容旧接口）

    names: 完整名称列表 ["科技.半导体", "科技.算力", ...]
    """
    data = _load()
    existing = set(data['sub_directions'].keys())
    if set(names) != existing:
        missing = existing - set(names)
        extra = set(names) - existing
        msg = []
        if missing: msg.append(f'缺少: {missing}')
        if extra: msg.append(f'多余: {extra}')
        return {'success': False, 'error': '; '.join(msg) or '细分方向集合不匹配'}
    for idx, name in enumerate(names):
        if name in data['sub_directions']:
            data['sub_directions'][name]['order'] = idx
    _save(data)
    return {'success': True}


# ── 建议来源 ──

def get_suggestions():
    """返回建议方向（兼容旧接口）"""
    data = _load()
    existing = data.get('suggestions', {})
    if existing and (existing.get('industry') or existing.get('concept') or existing.get('custom')):
        return existing

    suggestions = {'industry': [], 'concept': [], 'custom': []}

    # 从 industry map 提取行业
    imp = os.path.join(DATA_DIR, 'stock_industry_map.json')
    if os.path.isfile(imp):
        try:
            with open(imp) as f:
                im = json.load(f)
            industries = set()
            for info in im.values():
                ind = info.get('ths_industry', '')
                if ind and len(ind) <= 6:
                    industries.add(ind)
            suggestions['industry'] = sorted(industries)[:30]
        except (OSError, json.JSONDecodeError):
            pass

    # 自定义推荐
    suggestions['custom'] = [
        '北交所', '科创板', '高股息', '军工', '国企改革',
        '并购重组', '大金融', '周期股',
    ]

    data['suggestions'] = suggestions
    _save(data)
    return suggestions


# ── V1 兼容接口（add / remove / set_active） ──

def add(name: str) -> dict:
    """添加方向（V1 兼容），归入\"未分类\""""
    return add_sub_direction("未分类", name, auto_create_category=True)


def remove(name: str) -> dict:
    """删除方向（V1 兼容）"""
    cat, sub = parse_direction(name)
    if not cat:
        cat = "未分类"
    return remove_sub_direction(cat, sub)


def set_active(name: str, active: bool) -> dict:
    """启用/禁用方向（V1 兼容）"""
    cat, sub = parse_direction(name)
    if not cat:
        cat = "未分类"
    return set_sub_direction_enabled(cat, sub, active)


# ── 个股方向读取工具（兼容旧格式 direction → 新格式 directions） ──

def get_stock_directions(stock: dict) -> list:
    """从 stock 对象读取方向列表，兼容旧格式 direction (str) 和新格式 directions (list)

    旧格式: {"direction": "半导体"} → ["未分类.半导体"]
    新格式: {"directions": ["科技.半导体"]} → ["科技.半导体"]
    无方向: → ["其他.未分类"]
    """
    dirs = stock.get('directions')
    if isinstance(dirs, list):
        return dirs
    d = stock.get('direction', '')
    if isinstance(d, str) and d.strip():
        # 旧格式没有大类前缀，尝试解析
        cat, sub = parse_direction(d.strip())
        if not cat:
            return ['其他.未分类']
        return [d.strip()]
    return ['其他.未分类']


def normalize_stock_directions(stock: dict) -> dict:
    """将 stock 中的旧 direction 字段转为新 directions 数组（用于保存前标准化）"""
    s = dict(stock)
    dirs = get_stock_directions(s)
    s['directions'] = dirs
    s.pop('direction', None)
    return s


# ── 核心股 ──

def get_core_stocks() -> dict:
    """返回核心股列表（兼容旧接口）"""
    data = _load()
    core = data.get('core', {})
    result = {}
    for code, info in core.items():
        if isinstance(info, str):
            result[code] = {'name': info, 'deviation': 6}
        else:
            result[code] = {
                'name': info.get('name', ''),
                'deviation': info.get('deviation', 6),
            }
    return result


# ── 迁移 ──

def migrate_v1_to_v2() -> dict:
    """显式触发 V1 → V2 迁移"""
    if not os.path.isfile(DIRECTIONS_FILE):
        return {'success': False, 'error': 'directions.json 不存在'}

    # 直接读原始文件，绕过 _load 的自动升级
    try:
        with open(DIRECTIONS_FILE, 'r') as f:
            content = f.read().strip()
        if not content:
            return {'success': False, 'error': 'directions.json 为空'}
        raw_data = json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        return {'success': False, 'error': f'directions.json 读取失败: {e}'}

    # 检查是否已经是 V2
    if raw_data.get('version') == 2:
        return {'success': False, 'error': '已是最新版本，无需迁移'}

    v2 = _migrate_v1_to_v2_inplace(raw_data)
    _save(v2)
    return {'success': True, 'migrated': len(v2['sub_directions'])}


def migrate_from_watchlist(wl_path=None):
    """从 watchlist.json 的 direction 字段迁移到独立文件（兼容旧接口）

    迁移后自动升级为 V2 格式。
    """
    if wl_path is None:
        wl_path = os.path.join(DATA_DIR, 'watchlist.json')
    if not os.path.isfile(wl_path):
        return {'success': False, 'error': 'watchlist.json 不存在'}

    try:
        with open(wl_path) as f:
            wl = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {'success': False, 'error': 'watchlist.json 读取失败'}

    stocks = wl.get('stocks', [])
    dirs_set = set()
    for s in stocks:
        d = s.get('direction', '')
        if d and d not in ('全部',):
            dirs_set.add(d)

    all_dirs = sorted(dirs_set)

    # 构建 V2 格式
    v2 = _default_v2()
    if all_dirs:
        v2['categories']["未分类"] = {"order": 0, "enabled": True}
        for idx, name in enumerate(all_dirs):
            v2['sub_directions'][name] = {
                "category": "未分类",
                "enabled": True,
                "order": idx,
                "concept_codes": [],
                "concept_names": [],
            }
    _save(v2)
    return {'success': True, 'migrated': len(all_dirs), 'active': len(all_dirs)}

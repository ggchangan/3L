"""
方向管理服务 — 方向 CRUD + 启用状态管理
"""
import json
import os
from services.logger import get_logger

log = get_logger(__name__)

DIR_PATH = os.path.join(
    os.environ.get('DATA_DIR', '/home/ubuntu/data/3l'),
    'directions.json'
)


def _ensure_dir(path):
    """确保文件存在，不存在时创建默认空文件"""
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"all": [], "active": []}, f, ensure_ascii=False, indent=2)


def load_directions(path=None):
    """加载方向数据"""
    path = path or DIR_PATH
    _ensure_dir(path)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write(path, data):
    """写入方向数据"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def save_directions(path=None, data=None, add=None, remove=None, set_active=None, rename=None):
    """
    修改方向并保存
    
    参数:
        add: list[str] — 新增的方向
        remove: list[str] — 删除的方向
        set_active: list[str] — 设为启用的方向
        rename: dict {旧名: 新名} — 重命名
    返回: 更新后的方向数据
    """
    path = path or DIR_PATH
    if data is None:
        data = load_directions(path)
    
    if add:
        for name in add:
            if name and name not in data["all"]:
                data["all"].append(name)
            if name and name not in data["active"]:
                data["active"].append(name)
    
    if rename:
        for old, new in rename.items():
            if old in data["all"]:
                idx = data["all"].index(old)
                data["all"][idx] = new
            if old in data["active"]:
                idx = data["active"].index(old)
                data["active"][idx] = new
    
    if remove:
        for name in remove:
            if name in data["all"]:
                data["all"].remove(name)
            if name in data["active"]:
                data["active"].remove(name)
    
    if set_active is not None:
        # 只保留在 all 中存在的方向
        data["active"] = [d for d in set_active if d in data["all"]]
    
    return _write(path, data)


def get_active_directions(path=None):
    """获取启用的方向列表"""
    data = load_directions(path)
    return data.get("active", [])


def is_direction_active(name, path=None):
    """判断某方向是否启用"""
    return name in get_active_directions(path)


def reassign_stocks_on_remove(stocks, removed_dir, fallback="其他"):
    """
    删除方向后，将该方向的股票重新分配
    
    参数:
        stocks: list[dict] — 股票列表，每项有 'direction' 字段
        removed_dir: str — 被删除的方向名
        fallback: str — 默认分配方向
    返回: 更新后的股票列表
    """
    updated = []
    for s in stocks:
        if s.get("direction") == removed_dir:
            s = dict(s)
            s["direction"] = fallback
        updated.append(s)
    return updated

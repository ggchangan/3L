"""
逻辑追踪系统 — 数据存储层

读写 data/logic_tracking.json，原子写入。
提供 tags/entries/forecasts 的 CRUD 操作。
"""
import json
import os
import shutil
from datetime import datetime, date, timedelta


class LogicTrackingStore:
    """逻辑追踪数据存储"""

    def __init__(self, data_path=None):
        if data_path is None:
            from backend.core import config
            data_path = config.LOGIC_TRACKING_PATH
        self._path = data_path
        self._data = self._load()

    # ── 内部方法 ─────────────────────────────────────

    def _load(self):
        """加载JSON文件，不存在则返回空模板"""
        if os.path.isfile(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                pass
        return {'tags': [], 'entries': [], 'forecasts': [], 'updated_at': ''}

    def _save(self):
        """原子写入JSON文件（tmp+rename）"""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        tmp = self._path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, self._path)

    def get_all(self):
        """获取完整数据"""
        return self._data

    # ── 标签 CRUD ───────────────────────────────────

    def get_tags(self, tier=None):
        """获取所有标签，可选按层级过滤"""
        tags = self._data.get('tags', [])
        if tier:
            return [t for t in tags if t.get('tier') == tier]
        return tags

    def get_tag(self, tag_id):
        """按ID获取单个标签"""
        for t in self._data.get('tags', []):
            if t.get('id') == tag_id:
                return t
        return None

    def add_tag(self, tag):
        """添加标签，检查重复ID和聚焦上限"""
        tags = self._data.setdefault('tags', [])
        # 检查重复ID
        if any(t.get('id') == tag.get('id') for t in tags):
            raise ValueError(f'标签 {tag["id"]} 已存在')
        # 检查聚焦上限（最多3个）
        if tag.get('tier') == 'focused':
            focused_count = sum(1 for t in tags if t.get('tier') == 'focused')
            if focused_count >= 3:
                raise ValueError('聚焦层级最多3个')
        tags.append(tag)
        self._save()

    def update_tag(self, tag_id, updated):
        """更新标签"""
        tags = self._data.setdefault('tags', [])
        for i, t in enumerate(tags):
            if t.get('id') == tag_id:
                tags[i] = updated
                self._save()
                return
        raise ValueError(f'标签 {tag_id} 不存在')

    def delete_tag(self, tag_id):
        """删除标签"""
        tags = self._data.setdefault('tags', [])
        for i, t in enumerate(tags):
            if t.get('id') == tag_id:
                tags.pop(i)
                self._save()
                return
        raise ValueError(f'标签 {tag_id} 不存在')

    # ── 条目 CRUD ───────────────────────────────────

    def get_entries(self, tag_id=None):
        """获取所有条目，可选按标签过滤"""
        entries = self._data.get('entries', [])
        if tag_id:
            return [e for e in entries if tag_id in e.get('logic_tags', [])]
        return entries

    def add_entry(self, entry):
        """添加条目，并更新关联标签的事件计数"""
        self._data.setdefault('entries', []).append(entry)
        # 更新关联标签的 event_count
        for tag_id in entry.get('logic_tags', []):
            for t in self._data.get('tags', []):
                if t.get('id') == tag_id:
                    t['event_count'] = t.get('event_count', 0) + 1
                    break
        self._save()

    def delete_entry(self, entry_id):
        """删除条目"""
        entries = self._data.setdefault('entries', [])
        for i, e in enumerate(entries):
            if e.get('id') == entry_id:
                entries.pop(i)
                self._save()
                return
        raise ValueError(f'条目 {entry_id} 不存在')

    # ── 预判 CRUD ───────────────────────────────────

    def get_forecasts(self, upcoming_days=None):
        """获取预判，可选按未来N天过滤"""
        forecasts = self._data.get('forecasts', [])
        if upcoming_days is not None:
            today = date.today()
            cutoff = today + timedelta(days=upcoming_days)
            result = []
            for f in forecasts:
                try:
                    fd = datetime.strptime(f.get('event_date', ''), '%Y-%m-%d').date()
                    if today <= fd <= cutoff:
                        result.append(f)
                except (ValueError, TypeError):
                    continue
            return result
        return forecasts

    def add_forecast(self, forecast):
        """添加预判"""
        self._data.setdefault('forecasts', []).append(forecast)
        self._save()

    def delete_forecast(self, forecast_id):
        """删除预判"""
        forecasts = self._data.setdefault('forecasts', [])
        for i, f in enumerate(forecasts):
            if f.get('id') == forecast_id:
                forecasts.pop(i)
                self._save()
                return
        raise ValueError(f'预判 {forecast_id} 不存在')

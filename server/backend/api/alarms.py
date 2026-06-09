"""报警管理 API 路由"""
import json, os, base64
from urllib.parse import urlparse, parse_qs
from datetime import date, timedelta

from backend.services.alarm_service import (
    get_active_alarms,
    get_alarms,
    remove_alarm,
    mark_alarm_triggered,
    dismiss_alarm,
    reenable_alarm,
)
from backend.config import DATA_DIR
from backend.core.exceptions import APIError


# 用户上传的报警音乐存到 public/（Vite 开发时直接服务）和 dist/（构建后）
# 不要存到 src/ — src/ 下的文件会被 git 跟踪
SOUNDS_PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                 'frontend', 'public', 'assets', 'sounds')
SOUNDS_DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                               'frontend', 'dist', 'assets', 'sounds')


def _get_sounds_config_path():
    return os.path.join(DATA_DIR, 'public', 'sounds', 'alarm_sounds.json')


def _load_sounds_config():
    p = _get_sounds_config_path()
    if os.path.isfile(p):
        with open(p) as f:
            return json.load(f)
    return {}


def _save_sounds_config(config):
    p = _get_sounds_config_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _handle_alarm_sounds(h, path):
    """GET /api/alarm-sounds — 返回报警音乐配置"""
    config = _load_sounds_config()
    h.send_json({'alarms': config})


def _handle_upload(h, path, body):
    """POST /api/alarm-sounds/upload — 上传报警音乐文件

    Body (JSON): {
        "type": "stop|stock|market|market_critical",
        "name": "用户可见的文件名",
        "data": "<base64 encoded file content>"
    }
    """
    import logging
    log = logging.getLogger('server')

    try:
        data = json.loads(body)
        alarm_type = data.get('type', '')
        file_name = data.get('name', 'upload.mp3')
        log.info('upload: type=%s name=%s size=%d chars', alarm_type, file_name, len(data.get('data','')))

        raw = base64.b64decode(data.get('data', ''))
        log.info('upload: decoded %d bytes', len(raw))

        valid_types = {'stop', 'stock', 'market', 'market_critical'}
        if alarm_type not in valid_types:
            h.send_json({'success': False, 'error': '无效的报警类型: ' + alarm_type})
            return

        # 保存到 public/ + dist/（不再存 src/，避免 git 跟踪）
        for d in [SOUNDS_PUBLIC_DIR, SOUNDS_DIST_DIR]:
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, file_name)
            with open(fp, 'wb') as f:
                f.write(raw)
            log.info('upload: saved to %s', fp)

        # 更新配置
        config = _load_sounds_config()
        config[alarm_type] = {
            'url': '/assets/sounds/' + file_name,
            'name': file_name,
            'duration': 30,
        }
        _save_sounds_config(config)

        h.send_json({'success': True, 'config': config[alarm_type]})
    except Exception as e:
        raise APIError(f"报警模块异常: {e}") from e


def _handle_list(h, path):
    """GET /api/alarms/list — 返回当前生效的报警"""
    alarms = get_active_alarms()
    h.send_json({'alarms': alarms, 'count': len(alarms)})


def _handle_list_all(h, path):
    """GET /api/alarms/list-all — 返回全部报警（含已触发/过期）
    
    只返回：
    - 已触发的报警（有 triggered_at）
    - 已处理的报警（status=handled）
    不返回从未触发过的active报警（它们只是配置，不是待处理事项）
    """
    alarms = get_alarms()
    # 过滤掉从未触发过的active报警
    filtered = [a for a in alarms if a.get('triggered_at') or a.get('status') == 'handled']
    h.send_json({'alarms': filtered, 'count': len(filtered)})


def _handle_remove(h, path, body):
    """POST /api/alarms/remove — 删除报警

    Body: {"id": "alarm_002371_xxx"}
    """
    try:
        data = json.loads(body)
        alarm_id = data.get('id', '')
        if not alarm_id:
            h.send_json({'success': False, 'error': '缺少 id'})
            return
        result = remove_alarm(alarm_id)
        h.send_json(result)
    except Exception as e:
        raise APIError(f"报警模块异常: {e}") from e


def _handle_dismiss(h, path, body):
    """POST /api/alarms/dismiss — 标记报警为已处理

    Body: {"id": "alarm_002371_xxx"}
    处理后此报警不再触发通知，直到手动重新启用。
    """
    try:
        data = json.loads(body)
        alarm_id = data.get('id', '')
        if not alarm_id:
            h.send_json({'success': False, 'error': '缺少 id'})
            return
        result = dismiss_alarm(alarm_id)
        h.send_json(result)
    except Exception as e:
        raise APIError(f"报警模块异常: {e}") from e


def _handle_reenable(h, path, body):
    """POST /api/alarms/reenable — 重新启用已处理的报警

    Body: {"id": "alarm_002371_xxx"}
    """
    try:
        data = json.loads(body)
        alarm_id = data.get('id', '')
        if not alarm_id:
            h.send_json({'success': False, 'error': '缺少 id'})
            return
        result = reenable_alarm(alarm_id)
        h.send_json(result)
    except Exception as e:
        raise APIError(f"报警模块异常: {e}") from e


def register_routes(routes):
    routes.exact('/api/alarms/list', func=_handle_list)
    routes.exact('/api/alarms/list-all', func=_handle_list_all)
    routes.exact('/api/alarms/remove', func=_handle_remove)
    routes.exact('/api/alarm-sounds', func=_handle_alarm_sounds)
    routes.exact('/api/alarm-sounds/upload', func=_handle_upload)
    return routes

"""WxPusher 微信推送配置 API 路由"""
import json
from backend.core.logger import get_logger
log = get_logger(__name__)


from backend.core.exceptions import APIError
from backend.services.wxpush_sender import is_configured, update_config


def _handle_status(h, path):
    """GET /api/wxpush/status — 返回 WxPusher 配置状态"""
    h.send_json({'success': True, **is_configured()})


def _handle_config(h, path, body):
    """POST /api/wxpush/config — 更新 WxPusher 配置

    Body: {"token": "AT_xxx", "uid": "UID_xxx"}
    """
    try:
        data = json.loads(body)
        token = data.get('token', '').strip()
        uid = data.get('uid', '').strip()

        if not token and not uid:
            h.send_json({'success': False, 'error': '至少提供 token 或 uid 之一'})
            return

        ok = update_config(token=token or None, uid=uid or None)
        if ok:
            h.send_json({'success': True, **is_configured()})
        else:
            h.send_json({'success': False, 'error': '更新 .env 失败'})
    except Exception as e:
        log.error("wxpush error: %s", e, exc_info=True)
        raise APIError(f"推送模块异常: {e}") from e


def _handle_test(h, path):
    """GET /api/wxpush/test — 发送测试消息"""
    from backend.services.wxpush_sender import send_alert

    ok = send_alert(
        '🔔 3L 报警测试',
        '如果收到这条消息，说明 WxPusher 配置成功！\n\n'
        '报警会实时推送到你的微信，不再依赖 Hermes。',
        alarm_type='test',
    )
    if ok:
        h.send_json({'success': True, 'message': '测试消息已发送，请检查微信'})
    else:
        h.send_json({'success': False, 'error': '发送失败，请检查配置'})


def register_routes(routes):
    routes.exact('/api/wxpush/status', func=_handle_status)
    routes.exact('/api/wxpush/config', func=_handle_config)
    routes.exact('/api/wxpush/test', func=_handle_test)
    return routes

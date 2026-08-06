"""用户认证路由 — 登录 / 注册 / 改密码 / 登出 / 当前用户。

POST 路由在 server.py do_POST 的 post_routes 中注册；
GET /api/auth/me 通过 RouteRegistry 注册。
"""
import json
import re

from backend.core import auth
from backend.core.logger import get_logger
from backend.data_access import users_repo

log = get_logger(__name__)

USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,20}$')


def _parse_body(body):
    try:
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _public_user(user):
    return {
        'id': user['id'],
        'username': user['username'],
        'display_name': user.get('display_name') or user['username'],
    }


def _handle_login(h, path, body):
    """登录：{username, password} → {token, user}"""
    data = _parse_body(body)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        h.send_json({'success': False, 'error': '用户名和密码不能为空'}, 400)
        return
    user = users_repo.get_user_by_username(username)
    if not user or not user.get('is_active'):
        h.send_json({'success': False, 'error': '用户名或密码错误'}, 401)
        return
    if not auth.verify_password(password, user.get('password_salt'), user.get('password_hash')):
        h.send_json({'success': False, 'error': '用户名或密码错误'}, 401)
        return
    token = auth.create_token(user)
    h.send_json({'success': True, 'token': token, 'user': _public_user(user)})


def _handle_register(h, path, body):
    """注册：{username, password, display_name?} → 自动登录"""
    data = _parse_body(body)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    display_name = (data.get('display_name') or '').strip()
    if not USERNAME_RE.match(username):
        h.send_json({'success': False, 'error': '用户名需为3-20位字母/数字/下划线'}, 400)
        return
    if len(password) < 6:
        h.send_json({'success': False, 'error': '密码至少6位'}, 400)
        return
    pwd_hash, salt = auth.hash_password(password)
    try:
        user = users_repo.create_user(username, pwd_hash, salt, display_name)
    except Exception as e:
        # 并发注册竞态：UNIQUE(username) 冲突 → 友好 409，而不是 500
        if 'Duplicate' in str(e) or '1062' in str(e):
            h.send_json({'success': False, 'error': '用户名已存在'}, 409)
            return
        log.warning('注册失败: %s', e)
        h.send_json({'success': False, 'error': '注册失败，请重试'}, 500)
        return
    token = auth.create_token(user)
    h.send_json({'success': True, 'token': token, 'user': user})


def _handle_change_password(h, path, body):
    """修改密码：{old_password, new_password}（需登录态）

    改密成功后撤销该用户除当前会话外的所有 token，
    防止旧 token（如已泄露/其他设备）继续有效。
    """
    cur = auth.get_current_user()
    if not cur:
        h.send_json({'success': False, 'error': '未登录'}, 401)
        return
    data = _parse_body(body)
    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    if len(new_password) < 6:
        h.send_json({'success': False, 'error': '新密码至少6位'}, 400)
        return
    user = users_repo.get_user_by_id(cur['id'])
    if not user:
        h.send_json({'success': False, 'error': '用户不存在'}, 404)
        return
    if not auth.verify_password(old_password, user.get('password_salt'), user.get('password_hash')):
        h.send_json({'success': False, 'error': '原密码错误'}, 401)
        return
    if old_password == new_password:
        h.send_json({'success': False, 'error': '新密码不能与原密码相同'}, 400)
        return
    pwd_hash, salt = auth.hash_password(new_password)
    if users_repo.update_password(cur['id'], pwd_hash, salt):
        # 撤销该用户其他会话的 token（保留当前请求的 token）
        token = h.headers.get('Authorization', '') or ''
        token = token.replace('Bearer ', '') if token.startswith('Bearer ') else token
        auth.revoke_user_tokens(cur['id'], except_token=token or None)
        h.send_json({'success': True, 'message': '密码修改成功'})
    else:
        h.send_json({'success': False, 'error': '密码修改失败，请重试'}, 500)


def _handle_logout(h, path, body):
    """登出：使当前 token 失效"""
    token = h.headers.get('Authorization', '') or ''
    token = token.replace('Bearer ', '') if token.startswith('Bearer ') else token
    auth.revoke_token(token)
    h.send_json({'success': True})


def _handle_me(h, path):
    """当前登录用户信息"""
    cur = auth.get_current_user()
    if not cur:
        h.send_json({'success': False, 'error': '未登录'}, 401)
        return
    h.send_json({'success': True, 'user': cur})


def register_routes(routes):
    routes.exact('/api/auth/me', func=_handle_me)
    return routes

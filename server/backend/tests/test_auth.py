"""认证模块测试 — auth 核心 / users_repo / API handler

⚠️ DB 相关测试使用专用随机测试用户 + teardown 清理，绝不触碰 admin 数据。
CI 只跑本目录：cd server && python -m pytest backend/tests/
"""
import os
import sys
import time
from uuid import uuid4

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402
from backend.core import auth  # noqa: E402
from backend.data_access.tushare_db import is_db_available  # noqa: E402
from backend.data_access import users_repo  # noqa: E402


@pytest.fixture(autouse=True)
def _cleanup_after():
    """每个测试后清理内存 token 与 thread-local，防跨测试泄漏"""
    yield
    auth._tokens.clear()
    auth.set_current_user(None)


# ═══════════════════════════════════════════════════════════
# 1. auth 核心纯函数（无需 DB）
# ═══════════════════════════════════════════════════════════

class TestAuthCore:

    def test_hash_password_generates_salt(self):
        digest, salt = auth.hash_password('mypassword')
        assert salt and len(salt) == 32  # hex(16) → 32 chars
        assert digest and len(digest) == 64  # sha256 hex

    def test_hash_password_deterministic_with_same_salt(self):
        d1, s1 = auth.hash_password('pw', salt='a' * 32)
        d2, s2 = auth.hash_password('pw', salt='a' * 32)
        assert d1 == d2 and s1 == s2

    def test_hash_password_random_salt_differs(self):
        d1, _ = auth.hash_password('pw')
        d2, _ = auth.hash_password('pw')
        assert d1 != d2

    def test_verify_password_correct(self):
        digest, salt = auth.hash_password('secret123')
        assert auth.verify_password('secret123', salt, digest) is True

    def test_verify_password_wrong(self):
        digest, salt = auth.hash_password('secret123')
        assert auth.verify_password('wrong', salt, digest) is False

    def test_verify_password_missing_fields(self):
        assert auth.verify_password('x', None, None) is False
        assert auth.verify_password('x', '', '') is False

    def test_token_create_and_get(self):
        user = {'id': 7, 'username': 'tester', 'display_name': '测试'}
        token = auth.create_token(user)
        got = auth.get_token_user(token)
        assert got['id'] == 7
        assert got['username'] == 'tester'

    def test_token_invalid_returns_none(self):
        assert auth.get_token_user('') is None
        assert auth.get_token_user('not-a-real-token') is None

    def test_token_expiry(self, monkeypatch):
        user = {'id': 8, 'username': 'expiry'}
        token = auth.create_token(user)
        # 把时间拨到过期之后（必须在 patch 前保存原始 time.time 防递归）
        import time as _time
        real_time = _time.time
        monkeypatch.setattr(auth.time, 'time', lambda: real_time() + auth.TOKEN_TTL_SECONDS + 10)
        assert auth.get_token_user(token) is None

    def test_revoke_token(self):
        token = auth.create_token({'id': 9, 'username': 'revoke'})
        auth.revoke_token(token)
        assert auth.get_token_user(token) is None

    def test_revoke_user_tokens_except_current(self):
        t1 = auth.create_token({'id': 10, 'username': 'multi'})
        t2 = auth.create_token({'id': 10, 'username': 'multi'})
        t_other = auth.create_token({'id': 11, 'username': 'other'})
        auth.revoke_user_tokens(10, except_token=t1)
        assert auth.get_token_user(t1) is not None   # 保留当前
        assert auth.get_token_user(t2) is None        # 其他会话被撤销
        assert auth.get_token_user(t_other) is not None  # 其他用户不受影响

    def test_token_expiry_boundary(self, monkeypatch):
        """边界：未到期仍有效，超过 expires_at 即失效"""
        import time as _time
        real_time = _time.time
        user = {'id': 13, 'username': 'boundary'}
        token = auth.create_token(user)
        # 未到期（TTL-5s）：仍有效
        monkeypatch.setattr(auth.time, 'time', lambda: real_time() + auth.TOKEN_TTL_SECONDS - 5)
        assert auth.get_token_user(token) is not None
        # 超过 1 秒：失效
        monkeypatch.setattr(auth.time, 'time', lambda: real_time() + auth.TOKEN_TTL_SECONDS + 1)
        assert auth.get_token_user(token) is None

    def test_revoke_user_tokens_all_without_exception(self):
        """except_token=None 时撤销该用户全部 token"""
        t1 = auth.create_token({'id': 14, 'username': 'revall'})
        t2 = auth.create_token({'id': 14, 'username': 'revall'})
        auth.revoke_user_tokens(14)
        assert auth.get_token_user(t1) is None
        assert auth.get_token_user(t2) is None

    def test_sweep_expired_tokens(self, monkeypatch):
        token = auth.create_token({'id': 12, 'username': 'sweep'})
        import time as _time
        real_time = _time.time
        monkeypatch.setattr(auth.time, 'time', lambda: real_time() + auth.TOKEN_TTL_SECONDS + 10)
        auth.sweep_expired_tokens()
        # 直接断言 token 从内存字典移除（而非依赖 get_token_user 的惰性清理）
        assert token not in auth._tokens


# ═══════════════════════════════════════════════════════════
# 2. users_repo（MySQL CRUD，专用随机用户）
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def tmp_user():
    """创建专用测试用户，teardown 彻底清理（含关联数据）"""
    from backend.data_access.tushare_db import TushareDB
    db = TushareDB()
    username = f'pytest_auth_{uuid4().hex[:12]}'
    digest, salt = auth.hash_password('testpass123')
    db.execute_raw(
        "INSERT INTO users (username, display_name, password_hash, password_salt) "
        "VALUES (%s, %s, %s, %s)",
        [username, '认证测试用户', digest, salt],
    )
    rows = db.execute_raw("SELECT id FROM users WHERE username=%s", [username])
    uid = rows[0]['id']
    yield uid
    db.execute_raw("DELETE FROM users WHERE id=%s", [uid])


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestUsersRepo:

    def test_create_and_get_user(self):
        username = f'pytest_auth_{uuid4().hex[:12]}'
        digest, salt = auth.hash_password('pw123456')
        user = users_repo.create_user(username, digest, salt, display_name='张三')
        assert user['id'] > 0
        try:
            got = users_repo.get_user_by_username(username)
            assert got['username'] == username
            assert got['display_name'] == '张三'
            assert got['password_hash'] == digest
            assert got['is_active'] is True
        finally:
            from backend.data_access.tushare_db import TushareDB
            TushareDB().execute_raw("DELETE FROM users WHERE id=%s", [user['id']])

    def test_get_user_by_id(self, tmp_user):
        got = users_repo.get_user_by_id(tmp_user)
        assert got is not None and got['id'] == tmp_user

    def test_get_user_not_found(self):
        assert users_repo.get_user_by_username('no_such_user_xyz') is None
        assert users_repo.get_user_by_id(999999999) is None

    def test_username_exists(self, tmp_user):
        rows = users_repo.get_user_by_id(tmp_user)
        assert users_repo.username_exists(rows['username']) is True
        assert users_repo.username_exists('no_such_user_xyz') is False

    def test_update_password(self, tmp_user):
        new_digest, new_salt = auth.hash_password('newpass456')
        assert users_repo.update_password(tmp_user, new_digest, new_salt) is True
        got = users_repo.get_user_by_id(tmp_user)
        assert got['password_hash'] == new_digest
        assert got['password_salt'] == new_salt

    def test_list_users_contains_admin(self):
        users = users_repo.list_users()
        assert any(u['username'] == 'admin' for u in users)
        # 不含密码字段
        assert all('password_hash' not in u for u in users)

    def test_create_duplicate_username_raises(self):
        username = f'pytest_dup_{uuid4().hex[:10]}'
        digest, salt = auth.hash_password('pw123456')
        users_repo.create_user(username, digest, salt)
        try:
            with pytest.raises(Exception):
                users_repo.create_user(username, digest, salt)
        finally:
            from backend.data_access.tushare_db import TushareDB
            TushareDB().execute_raw("DELETE FROM users WHERE username=%s", [username])


# ═══════════════════════════════════════════════════════════
# 3. API handler（登录/注册/改密/登出/me）
# ═══════════════════════════════════════════════════════════

class FakeHandler:
    """模拟 server.py 的 handler：捕获 send_json 调用"""

    def __init__(self, headers=None, body='{}'):
        self.headers = headers or {}
        self.body = body
        self.responses = []

    def send_json(self, data, status=200):
        self.responses.append((status, data))
        return data


@pytest.fixture
def auth_user():
    """创建带密码的测试用户，返回 (uid, username, password)"""
    from backend.data_access.tushare_db import TushareDB
    db = TushareDB()
    username = f'pytest_api_{uuid4().hex[:8]}'  # 10+8=18 ≤ 20 字符上限
    password = 'origpass123'
    digest, salt = auth.hash_password(password)
    db.execute_raw(
        "INSERT INTO users (username, display_name, password_hash, password_salt) "
        "VALUES (%s, %s, %s, %s)",
        [username, 'API测试用户', digest, salt],
    )
    rows = db.execute_raw("SELECT id FROM users WHERE username=%s", [username])
    uid = rows[0]['id']
    yield (uid, username, password)
    db.execute_raw("DELETE FROM users WHERE id=%s", [uid])


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestAuthAPI:

    def test_login_success(self, auth_user):
        from backend.api.auth import _handle_login
        _, username, password = auth_user
        h = FakeHandler(body='{}')
        _handle_login(h, '/api/auth/login',
                      f'{{"username": "{username}", "password": "{password}"}}')
        status, data = h.responses[-1]
        assert status == 200
        assert data['success'] is True
        assert data['token']
        assert data['user']['username'] == username

    def test_login_wrong_password(self, auth_user):
        from backend.api.auth import _handle_login
        _, username, _ = auth_user
        h = FakeHandler(body='{}')
        _handle_login(h, '/api/auth/login',
                      f'{{"username": "{username}", "password": "wrongpass"}}')
        status, data = h.responses[-1]
        assert status == 401
        assert data['success'] is False
        # 统一错误信息，不泄露用户是否存在
        assert data['error'] == '用户名或密码错误'

    def test_login_nonexistent_user(self):
        from backend.api.auth import _handle_login
        h = FakeHandler(body='{}')
        _handle_login(h, '/api/auth/login',
                      '{"username": "no_such_user_xyz", "password": "whatever"}')
        status, data = h.responses[-1]
        assert status == 401
        assert data['error'] == '用户名或密码错误'

    def test_login_empty_fields(self):
        from backend.api.auth import _handle_login
        h = FakeHandler(body='{}')
        _handle_login(h, '/api/auth/login', '{"username": "", "password": ""}')
        status, data = h.responses[-1]
        assert status == 400

    def test_register_success(self):
        from backend.api.auth import _handle_register
        from backend.data_access.tushare_db import TushareDB
        username = f'pytest_reg_{uuid4().hex[:8]}'  # 11+8=19 ≤ 20 字符上限
        h = FakeHandler(body='{}')
        _handle_register(h, '/api/auth/register',
                         f'{{"username": "{username}", "password": "regpass123"}}')
        status, data = h.responses[-1]
        assert status == 200
        assert data['success'] is True
        assert data['token']
        # 清理
        TushareDB().execute_raw("DELETE FROM users WHERE username=%s", [username])

    def test_register_with_display_name(self):
        """注册时带昵称应保存并返回"""
        from backend.api.auth import _handle_register
        from backend.data_access.tushare_db import TushareDB
        username = f'pytest_reg_{uuid4().hex[:8]}'
        h = FakeHandler(body='{}')
        _handle_register(h, '/api/auth/register',
                         f'{{"username": "{username}", "password": "regpass123", "display_name": "测试昵称"}}')
        status, data = h.responses[-1]
        assert status == 200
        assert data['user']['display_name'] == '测试昵称'
        # DB 中也保存了昵称
        got = users_repo.get_user_by_username(username)
        assert got['display_name'] == '测试昵称'
        TushareDB().execute_raw("DELETE FROM users WHERE username=%s", [username])

    def test_login_deactivated_user(self, auth_user):
        """停用用户（is_active=0）不能登录"""
        from backend.api.auth import _handle_login
        from backend.data_access.tushare_db import TushareDB
        uid, username, password = auth_user
        TushareDB().execute_raw("UPDATE users SET is_active=0 WHERE id=%s", [uid])
        h = FakeHandler(body='{}')
        _handle_login(h, '/api/auth/login',
                      f'{{"username": "{username}", "password": "{password}"}}')
        status, data = h.responses[-1]
        assert status == 401
        assert data['error'] == '用户名或密码错误'

    def test_register_duplicate_username(self, auth_user):
        from backend.api.auth import _handle_register
        _, username, _ = auth_user
        h = FakeHandler(body='{}')
        _handle_register(h, '/api/auth/register',
                         f'{{"username": "{username}", "password": "regpass123"}}')
        status, data = h.responses[-1]
        assert status == 409
        assert data['error'] == '用户名已存在'

    def test_register_invalid_username(self):
        from backend.api.auth import _handle_register
        h = FakeHandler(body='{}')
        _handle_register(h, '/api/auth/register',
                         '{"username": "ab", "password": "regpass123"}')  # 太短
        status, data = h.responses[-1]
        assert status == 400

    def test_register_short_password(self):
        from backend.api.auth import _handle_register
        h = FakeHandler(body='{}')
        _handle_register(h, '/api/auth/register',
                         '{"username": "validuser123", "password": "123"}')
        status, data = h.responses[-1]
        assert status == 400

    def test_change_password_success_and_revokes_other_tokens(self, auth_user):
        from backend.api.auth import _handle_change_password
        uid, username, password = auth_user
        # 签发两个 token，并模拟当前登录态（真实 server 由 _resolve_user 设置）
        user = {'id': uid, 'username': username}
        t1 = auth.create_token(user)
        t2 = auth.create_token(user)
        auth.set_current_user(auth.get_token_user(t1))
        try:
            h = FakeHandler(headers={'Authorization': f'Bearer {t1}'}, body='{}')
            _handle_change_password(h, '/api/auth/change-password',
                                    f'{{"old_password": "{password}", "new_password": "newpass456"}}')
            status, data = h.responses[-1]
            assert status == 200
            assert data['success'] is True
            # t1 保留（当前会话），t2 被撤销
            assert auth.get_token_user(t1) is not None
            assert auth.get_token_user(t2) is None
            # 新密码可登录
            got = users_repo.get_user_by_id(uid)
            assert auth.verify_password('newpass456', got['password_salt'], got['password_hash'])
        finally:
            auth.set_current_user(None)

    def test_change_password_wrong_old(self, auth_user):
        from backend.api.auth import _handle_change_password
        uid, username, _ = auth_user
        token = auth.create_token({'id': uid, 'username': username})
        auth.set_current_user(auth.get_token_user(token))
        try:
            h = FakeHandler(headers={'Authorization': f'Bearer {token}'}, body='{}')
            _handle_change_password(h, '/api/auth/change-password',
                                    '{"old_password": "wrong", "new_password": "newpass456"}')
            status, data = h.responses[-1]
            assert status == 401
            assert data['error'] == '原密码错误'
        finally:
            auth.set_current_user(None)

    def test_change_password_same_as_old(self, auth_user):
        from backend.api.auth import _handle_change_password
        uid, username, password = auth_user
        token = auth.create_token({'id': uid, 'username': username})
        auth.set_current_user(auth.get_token_user(token))
        try:
            h = FakeHandler(headers={'Authorization': f'Bearer {token}'}, body='{}')
            _handle_change_password(h, '/api/auth/change-password',
                                    f'{{"old_password": "{password}", "new_password": "{password}"}}')
            status, data = h.responses[-1]
            assert status == 400
            assert '不能与原密码相同' in data['error']
        finally:
            auth.set_current_user(None)

    def test_change_password_not_logged_in(self):
        from backend.api.auth import _handle_change_password
        h = FakeHandler(headers={}, body='{}')
        _handle_change_password(h, '/api/auth/change-password',
                                '{"old_password": "x", "new_password": "y"}')
        status, data = h.responses[-1]
        assert status == 401

    def test_logout_revokes_token(self):
        from backend.api.auth import _handle_logout
        token = auth.create_token({'id': 5, 'username': 'logout'})
        h = FakeHandler(headers={'Authorization': f'Bearer {token}'}, body='{}')
        _handle_logout(h, '/api/auth/logout', '{}')
        status, data = h.responses[-1]
        assert status == 200
        assert auth.get_token_user(token) is None

    def test_me_returns_current_user(self):
        from backend.api.auth import _handle_me
        token = auth.create_token({'id': 5, 'username': 'meuser', 'display_name': '我'})
        auth.set_current_user(auth.get_token_user(token))
        try:
            h = FakeHandler(body='{}')
            _handle_me(h, '/api/auth/me')
            status, data = h.responses[-1]
            assert status == 200
            assert data['user']['username'] == 'meuser'
        finally:
            auth.set_current_user(None)

    def test_me_not_logged_in(self):
        from backend.api.auth import _handle_me
        auth.set_current_user(None)
        h = FakeHandler(body='{}')
        _handle_me(h, '/api/auth/me')
        status, data = h.responses[-1]
        assert status == 401


class TestChartEndpointsAuthWhitelist:
    """图表端点必须免登录（前端 <img>/<object> 原生标签无法携带 Authorization header）。

    2026-08-06 回归：多用户改造后所有 /api/* 强制登录，图表端点返回 401，
    导致复盘/盯盘页面大盘与个股关键点图全部加载失败。修复后白名单包含
    index-chart / stock-chart / sector-chart，此处锁定行为防止再次回归。
    """

    @pytest.mark.parametrize('path', [
        '/api/index-chart',
        '/api/stock-chart',
        '/api/sector-chart',
    ])
    def test_chart_endpoints_anonymous_ok(self, path):
        from server.server import Handler
        assert path in Handler.AUTH_WHITELIST

    def test_private_api_still_requires_auth(self):
        """非白名单 /api/* 仍必须登录（数据隔离不放松）。"""
        from server.server import Handler
        assert '/api/watchlist' not in Handler.AUTH_WHITELIST
        assert '/api/review' not in Handler.AUTH_WHITELIST
        assert '/api/holdings' not in Handler.AUTH_WHITELIST

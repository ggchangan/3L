"""认证核心 — 密码哈希、token 管理、请求级用户上下文。

设计要点：
- 密码：sha256(salt + password)，salt 每用户随机（标准库，零新依赖）
- token：secrets.token_hex(32)，服务端内存维护，7 天过期（重启需重新登录）
- 请求上下文：thread-local。http.server 的 ThreadingHTTPServer 每请求一线程，
  do_GET/do_POST 开头解析 Authorization 头后 set_current_user()。
- 无上下文的调用方（cron 批处理、脚本）默认视为 admin(id=1)：
  与「批处理只扫主用户」的决策一致，天然向后兼容。
"""
import hashlib
import secrets
import threading
import time

TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 天

# token -> {user_id, username, display_name, expires_at}
_tokens = {}
_tokens_lock = threading.Lock()

# 请求级用户上下文（thread-local）
_local = threading.local()


# ── 密码哈希 ──────────────────────────────────────────────

def hash_password(password: str, salt: str = None):
    """返回 (password_hash, salt)。salt 为空时自动生成。"""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return digest, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    if not salt or not expected_hash:
        return False
    digest, _ = hash_password(password, salt)
    return secrets.compare_digest(digest, expected_hash)


# ── token 管理 ────────────────────────────────────────────

def create_token(user: dict) -> str:
    """为用户签发 token。user 需含 id/username/display_name。"""
    token = secrets.token_hex(32)
    with _tokens_lock:
        _tokens[token] = {
            'user_id': user['id'],
            'username': user['username'],
            'display_name': user.get('display_name') or user['username'],
            'expires_at': time.time() + TOKEN_TTL_SECONDS,
        }
    return token


def get_token_user(token: str):
    """按 token 取用户信息；无效/过期返回 None。"""
    if not token:
        return None
    with _tokens_lock:
        info = _tokens.get(token)
        if not info:
            return None
        if time.time() > info['expires_at']:
            _tokens.pop(token, None)
            return None
        return {'id': info['user_id'], 'username': info['username'],
                'display_name': info['display_name']}


def revoke_token(token: str):
    with _tokens_lock:
        _tokens.pop(token, None)


def revoke_user_tokens(user_id: int, except_token: str = None):
    """撤销某用户签发的全部 token（改密/封号用）。

    Args:
        user_id: 目标用户 id
        except_token: 保留的 token（可选，如当前会话）
    """
    with _tokens_lock:
        for token, info in list(_tokens.items()):
            if info['user_id'] == user_id and token != except_token:
                _tokens.pop(token, None)


def sweep_expired_tokens():
    """清理过期 token，防止内存无限增长。"""
    now = time.time()
    with _tokens_lock:
        for token, info in list(_tokens.items()):
            if now > info['expires_at']:
                _tokens.pop(token, None)


# ── 请求上下文 ────────────────────────────────────────────

def set_current_user(user: dict):
    """设置当前请求的用户（token 解析结果）。"""
    _local.user = user


def get_current_user():
    """当前请求的用户；无上下文（cron/脚本）返回 None。"""
    return getattr(_local, 'user', None)


def get_current_user_id() -> int:
    """当前用户 id；无登录上下文时默认 admin(id=1)。

    这是数据隔离的关键：cron 批处理、复盘生成、扫描脚本没有 HTTP 请求
    上下文，全部默认作用于主用户 admin，与「只扫主用户买卖点」一致。
    """
    u = get_current_user()
    if u and u.get('id'):
        return u['id']
    return 1


def get_current_username() -> str:
    u = get_current_user()
    return u['username'] if u else 'admin'

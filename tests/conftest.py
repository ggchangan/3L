import sys, pytest, json, os
sys.path.insert(0, '/home/ubuntu/3l-server/server')


def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "network: 需要网络访问的测试（akshare/requests）")


@pytest.fixture(scope='session')
def stocks():
    from backend.core.data_layer import get_all_stocks
    return get_all_stocks()


@pytest.fixture(scope='session')
def watchlist():
    from backend.core.data_layer import get_watchlist
    return get_watchlist()


@pytest.fixture(scope='session')
def wl_codes(watchlist):
    return set(s['code'] for s in watchlist)

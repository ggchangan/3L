import sys, pytest, json, os
sys.path.insert(0, '/home/ubuntu/3l-server')


@pytest.fixture(scope='session')
def stocks():
    from scripts.data_layer import get_all_stocks
    return get_all_stocks()


@pytest.fixture(scope='session')
def watchlist():
    from scripts.data_layer import get_watchlist
    return get_watchlist()


@pytest.fixture(scope='session')
def wl_codes(watchlist):
    return set(s['code'] for s in watchlist)

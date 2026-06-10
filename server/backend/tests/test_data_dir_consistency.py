"""
DATA_DIR 统一性测试

A类（module-level DATA_DIR — 用 fallback 而非 config）：
  移除 DATA_DIR env → patch config.DATA_DIR 为哨兵值 → 重载模块
  RED: 模块用自己的 fallback(/home/ubuntu/data/3l)，不取 config → 不等于哨兵值
  GREEN: 从 config 导入 → 等于哨兵值

B类（module-level 派生路径 check_alerts.INDEX_DATA_PATH）：
  设 DATA_DIR env → 重载模块 → 断言路径正确

C类（函数内联用法 — 导入正常即可）

D类（scripts/ 源码检查 — = 改为 setdefault）
"""
import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib
import pytest


SENTINEL = '/tmp/_SENTINEL_3L_DATA_DIR'


def _clean_reimport(mod_name: str):
    mods_to_del = [k for k in list(sys.modules)
                   if k.startswith('backend.') and k != 'backend.config']
    if mod_name in sys.modules:
        mods_to_del.append(mod_name)
    for k in mods_to_del:
        del sys.modules[k]
    return importlib.import_module(mod_name)


# ── A类：module-level DATA_DIR ──────────────────────────

def test_a_concept_wave_uses_config():
    """concept_wave_service 应从 config 导入 DATA_DIR"""
    import backend.config as cfg
    old_env = os.environ.pop('DATA_DIR', None)
    old_cfg = cfg.DATA_DIR
    cfg.DATA_DIR = SENTINEL
    try:
        svc = _clean_reimport('backend.services.concept_wave_service')
        assert svc.DATA_DIR == SENTINEL, (
            f'concept_wave_service.DATA_DIR={svc.DATA_DIR!r} != {SENTINEL!r}\n'
            '仍用自己的 fallback，未取 backend.config.DATA_DIR'
        )
    finally:
        cfg.DATA_DIR = old_cfg
        if old_env is not None:
            os.environ['DATA_DIR'] = old_env


def test_a_strong_trend_uses_config():
    """strong_trend_service 应从 config 导入 DATA_DIR"""
    import backend.config as cfg
    old_env = os.environ.pop('DATA_DIR', None)
    old_cfg = cfg.DATA_DIR
    cfg.DATA_DIR = SENTINEL
    try:
        svc = _clean_reimport('backend.services.strong_trend_service')
        assert svc.DATA_DIR == SENTINEL, (
            f'strong_trend_service.DATA_DIR={svc.DATA_DIR!r} != {SENTINEL!r}'
        )
    finally:
        cfg.DATA_DIR = old_cfg
        if old_env is not None:
            os.environ['DATA_DIR'] = old_env


def test_a_backtest_reads_env():
    """backtest 应读 DATA_DIR 环境变量（当前硬编码）"""
    test_val = '/tmp/_test_backtest'
    os.environ['DATA_DIR'] = test_val
    try:
        mod = _clean_reimport('backend.core.signal_detector.backtest')
        assert mod.DATA_DIR == test_val, (
            f'backtest.DATA_DIR={mod.DATA_DIR!r} != {test_val!r}\n'
            '仍硬编码不读 env'
        )
    finally:
        os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'


# ── B类：module-level 派生路径 ──────────────────────────

def test_b_check_alerts_index_data_path():
    """check_alerts.INDEX_DATA_PATH 应与 config.DATA_DIR 一致"""
    import backend.config as cfg
    old = cfg.DATA_DIR
    test_val = '/tmp/_test_alerts'
    cfg.DATA_DIR = test_val
    try:
        mod = _clean_reimport('backend.services.check_alerts')
        expected = os.path.join(test_val, 'index_sh_data.json')
        assert mod.INDEX_DATA_PATH == expected, (
            f'INDEX_DATA_PATH={mod.INDEX_DATA_PATH!r} != {expected!r}'
        )
    finally:
        cfg.DATA_DIR = old


# ── C类：函数内联用法 — 导入正常即可 ──────────────────

def test_c_macro_service_imports():
    mod = _clean_reimport('backend.services.macro_service')
    assert hasattr(mod, 'get_macro_data')


def test_c_macro_analysis_imports():
    mod = _clean_reimport('backend.services.macro_analysis_service')
    assert hasattr(mod, '_find_related_a_shares')


def test_c_check_alerts_imports():
    mod = _clean_reimport('backend.services.check_alerts')
    assert hasattr(mod, '_is_index_dismissed')


# ── D类：scripts/ 源码检查 ─────────────────────────────

SCRIPTS_WITH_HARD_OVERRIDE = [
    'backtest_downtrend_v2', 'panic_backtest',
    'backtest_structure_compare', 'debug_stagnation_deep',
    'backtest_structure_deep', 'backtest_structure_fine',
    'backtest_downtrend_confirmation', 'backtest_downtrend_v3',
    'debug_stagnation_conditions', 'backtest_structure_final',
    'debug_stagnation_examples', 'backtest_stage_predict',
    'backtest_structure_optimize',
]


@pytest.mark.parametrize('script_name', SCRIPTS_WITH_HARD_OVERRIDE)
def test_d_script_uses_setdefault(script_name):
    script_path = os.path.abspath(
        os.path.join(_server_root, '..', 'scripts', f'{script_name}.py')
    )
    assert os.path.isfile(script_path), f'脚本不存在: {script_path}'
    with open(script_path) as f:
        content = f.read()
    for line in content.splitlines():
        stripped = line.strip()
        if 'DATA_DIR' in stripped and '/home/ubuntu/data/3l' in stripped:
            assert 'setdefault' in stripped, (
                f'{script_name}.py 用 = 而非 setdefault:\n  {stripped}'
            )

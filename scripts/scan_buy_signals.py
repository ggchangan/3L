"""Shim: 向后兼容 — 已迁移到 backend.core.scan_buy_signals"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import backend.core.scan_buy_signals as _mod
sys.modules[__name__] = _mod
# 作为__main__运行时需调用main()
if __name__ == '__main__':
    _mod.main()

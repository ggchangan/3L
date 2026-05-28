#!/usr/bin/env python3
"""Shim: 向后兼容 — 已迁移到 backend.core.scan_buy_signals"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import backend.core.scan_buy_signals as _mod
sys.modules[__name__] = _mod
if __name__ == '__main__':
    _mod.main()

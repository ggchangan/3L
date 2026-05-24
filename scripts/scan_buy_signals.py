"""Shim: 向后兼容 — 已迁移到 backend.core.scan_buy_signals"""
import sys
import backend.core.scan_buy_signals as _mod
sys.modules[__name__] = _mod

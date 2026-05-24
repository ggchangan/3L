"""Shim: 向后兼容 — 已迁移到 backend.core.buy_point_detection"""
import sys
import backend.core.buy_point_detection as _mod
sys.modules[__name__] = _mod

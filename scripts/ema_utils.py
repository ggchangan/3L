"""Shim: 向后兼容 — 已迁移到 backend.core.ema_utils"""
import sys
import backend.core.ema_utils as _mod
sys.modules[__name__] = _mod

"""Shim: 向后兼容 — 已迁移到 backend.core.monitor_data"""
import sys
import backend.core.monitor_data as _mod
sys.modules[__name__] = _mod

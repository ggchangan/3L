"""Shim: 向后兼容 — 已迁移到 backend.core.gen_trend_chart"""
import sys
import backend.core.gen_trend_chart as _mod
sys.modules[__name__] = _mod

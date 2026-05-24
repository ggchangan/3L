"""Shim: 向后兼容 — 已迁移到 backend.core.trend_candidates"""
import sys
import backend.core.trend_candidates as _mod
sys.modules[__name__] = _mod

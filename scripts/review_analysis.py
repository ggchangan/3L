"""Shim: 向后兼容 — 已迁移到 backend.core.review_analysis"""
import sys
import backend.core.review_analysis as _mod
sys.modules[__name__] = _mod

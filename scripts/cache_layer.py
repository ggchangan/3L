"""Shim: 向后兼容 — 已迁移到 backend.core.cache_layer"""
import sys
import backend.core.cache_layer as _mod
sys.modules[__name__] = _mod

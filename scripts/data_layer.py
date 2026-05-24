"""Shim: 向后兼容 — 已迁移到 backend.core.data_layer"""
import sys
import backend.core.data_layer as _mod
sys.modules[__name__] = _mod

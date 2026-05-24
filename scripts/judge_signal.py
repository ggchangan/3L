"""Shim: 向后兼容 — 已迁移到 backend.core.judge_signal"""
import sys
import backend.core.judge_signal as _mod
sys.modules[__name__] = _mod

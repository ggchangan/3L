#!/usr/bin/env python3
"""幂等增加持仓建仓信号与止损生命周期字段。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'server'))

from backend.migrations.holdings_entry_metadata import main  # noqa: E402


if __name__ == '__main__':
    main()

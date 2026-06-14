#!/usr/bin/env python3
"""Tushare 数据回填入口（项目根目录快捷方式）"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
from backend.services.fill_history import main
main()

#!/usr/bin/env python3
"""
3L 每日复盘数据生成器 — CLI 入口

计算逻辑已迁移至 services/review_compute_service.py，
编排逻辑已迁移至 services/review_service.py，
此处仅保留 __main__ 入口供命令行调用。
"""
import sys
from services.review_service import generate_daily_review, update_historical_archives

if __name__ == '__main__':
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    update_historical_archives()
    generate_daily_review(date_arg)

#!/usr/bin/env python3
"""生成中证全指资金流向图（全市场主力净流入+中证全指涨跌幅）
用法: python3 gen_fund_flow_chart.py [date]
      date: YYYY-MM-DD 格式，默认当天
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PUBLIC_DIR
os.environ['TQDM_DISABLE'] = '1'
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

OUTPUT = os.path.join(PUBLIC_DIR, 'charts', 'fund_flow_chart.png')

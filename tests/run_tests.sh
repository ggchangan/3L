#!/bin/bash
# 运行所有测试
cd /home/ubuntu/3l-server && python -m pytest tests/ -v "$@"

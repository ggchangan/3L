#!/bin/bash
# 运行所有测试
cd /home/ubuntu/www && python -m pytest tests/ -v "$@"

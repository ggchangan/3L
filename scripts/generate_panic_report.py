#!/usr/bin/env python3
"""
恐慌报告生成脚本 — 调用 panic_report_service 生成PDF

用法:
  python3 scripts/generate_panic_report.py                  # 生成PDF到 files/
  python3 scripts/generate_panic_report.py --pdf output.pdf # 指定输出路径
  
数据源: 统一从 get_panic_monitor() 获取（同花顺THS）
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

def main():
    from backend.services.panic_report_service import generate_panic_report_pdf
    result = generate_panic_report_pdf()
    
    if 'error' in result:
        print(f"❌ 生成失败: {result['error']}")
        sys.exit(1)
    
    print(f"✅ PDF已生成: {result['filename']}")
    print(f"   大小: {result['size_kb']} KB")
    print(f"   下载: http://localhost:8080{result['download_url']}")


if __name__ == '__main__':
    main()

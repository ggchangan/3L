"""
恐慌报告PDF生成服务 — 从静态模板生成彩色白底PDF

使用 docs/panic-analysis-corrected.md 作为模板，
通过 wechat-pdf-template.html 渲染。
"""
import os, subprocess, tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')
MD_SOURCE = os.path.join(PROJECT_DIR, 'docs', 'panic-analysis-corrected.md')


def generate_panic_report_pdf():
    if not os.path.isfile(MD_SOURCE):
        return {'error': f'模板文件不存在: {MD_SOURCE}'}
    with open(MD_SOURCE, 'r') as f:
        md = f.read()

    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_name = f'panic_report_{date_str}.pdf'
    pdf_path = os.path.join(WWW_DIR, pdf_name)
    os.makedirs(WWW_DIR, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        try:
            p = subprocess.run(
                ['pandoc', '-f', 'markdown', '-t', 'html5',
                 '--template', TEMPLATE, '--metadata', 'title=恐慌应对策略报告'],
                input=md, capture_output=True, text=True, timeout=15)
            if p.returncode != 0:
                return {'error': f'pandoc: {p.stderr}'}
            tmp.write(p.stdout); tmp.flush()
            r = subprocess.run(
                ['wkhtmltopdf', '--encoding', 'utf-8', '--enable-local-file-access',
                 '--page-size', 'A4',
                 '--margin-top', '12mm', '--margin-bottom', '12mm',
                 '--margin-left', '10mm', '--margin-right', '10mm',
                 tmp.name, pdf_path],
                capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return {'error': f'wkhtmltopdf: {r.stderr}'}
            if not os.path.isfile(pdf_path):
                return {'error': 'PDF not created'}
            return {'filename': pdf_name, 'download_url': f'/download/{pdf_name}',
                    'size_kb': round(os.path.getsize(pdf_path)/1024, 1)}
        finally:
            try: os.unlink(tmp.name)
            except: pass

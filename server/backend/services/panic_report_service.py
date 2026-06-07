"""
恐慌报告PDF生成服务 — 从 get_panic_monitor() 数据生成彩色白底PDF

供 POST /api/panic-report-pdf 调用。
"""
import os
import json
import subprocess
import tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')


def generate_panic_report_pdf(indices_dict=None, decline_count=0, total=5100):
    """生成恐慌报告PDF，返回下载信息"""
    from backend.services.panic_monitor_service import get_panic_monitor
    from backend.core.data_layer import get_sector_daily

    # 1. 调用统一入口
    data = get_panic_monitor(indices_dict or {}, decline_count, total)

    # 2. 补充概念今日涨跌数据
    concepts_extra = {}
    try:
        sd = get_sector_daily()
        p2t = sd.get('_push2test', {})
        if p2t:
            con_pool = p2t.get('concepts', {})
            ind_pool = p2t.get('industries', {})
    except Exception:
        con_pool = {}
        ind_pool = {}

    # 3. 生成 Markdown
    md = _format_markdown(data, con_pool, ind_pool)

    # 4. 生成 PDF
    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_name = f'panic_report_{date_str}.pdf'
    pdf_path = os.path.join(WWW_DIR, pdf_name)
    os.makedirs(WWW_DIR, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        try:
            title = "恐慌应对策略报告"
            p = subprocess.run(
                ['pandoc', '-f', 'markdown', '-t', 'html5',
                 '--template', TEMPLATE,
                 '--metadata', f'title={title}'],
                input=md, capture_output=True, text=True, timeout=15
            )
            if p.returncode != 0:
                return {'error': f'pandoc failed: {p.stderr}'}

            tmp.write(p.stdout)
            tmp.flush()
            tmp_path = tmp.name

            r = subprocess.run(
                ['wkhtmltopdf', '--encoding', 'utf-8', '--enable-local-file-access',
                 '--page-size', 'A4', '--margin-top', '12mm', '--margin-bottom', '12mm',
                 '--margin-left', '10mm', '--margin-right', '10mm',
                 tmp_path, pdf_path],
                capture_output=True, text=True, timeout=20
            )
            if r.returncode != 0:
                return {'error': f'wkhtmltopdf failed: {r.stderr}'}
            if not os.path.isfile(pdf_path):
                return {'error': 'PDF file not created'}

            return {
                'filename': pdf_name,
                'download_url': f'/download/{pdf_name}',
                'size_kb': round(os.path.getsize(pdf_path) / 1024, 1),
            }
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def _format_markdown(data, con_pool, ind_pool):
    """从 get_panic_monitor() + 概念数据 生成 Markdown"""
    level = data.get('level')
    triggers = data.get('triggers', [])
    strategy = data.get('strategy', {})
    lines = []

    lines.append("# 🛡️ 恐慌应对策略报告")
    lines.append("")
    lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append("---")
    lines.append("")

    # ── 恐慌等级 ──
    if level:
        lines.append("## 🔴 恐慌状态")
        lines.append("")
        level_icon = '🔴 预警' if level == 'warning' else '⚠️ 注意'
        lines.append(f"**当前等级：{level_icon}**")
        lines.append("")
        for t in triggers:
            icon = '🔴' if t.get('level') == 'warning' else '⚠️'
            if t.get('is_decline_count'):
                lines.append(f"- {icon} {t['index']}")
            else:
                lines.append(f"- {icon} {t['index']} {t['change_pct']:.2f}%（阈值 {t['threshold']}）")
        lines.append("")

    # ── 市场环境 ──
    overview = strategy.get('market_overview', {})
    if overview:
        lines.append("## 📊 市场环境")
        lines.append("")
        lines.append(f"- 结构：**{overview.get('structure', '—')}**")
        lines.append(f"- 阶段：**{overview.get('stage', '—')}**")
        lines.append(f"- 仓位建议：**{overview.get('position_advice', '—')}**")
        lines.append(f"- BIAS20：**{overview.get('bias20', 0):.1f}%**")
        lines.append("")

    # ── 主线方向 ──
    mainline = strategy.get('mainline_sectors', [])
    if mainline:
        lines.append("### 🟢 主线抗跌方向")
        lines.append("")
        tags = '  '.join([f'<span class="tag tag-green">{s}</span>' for s in mainline[:8]])
        lines.append(tags)
        lines.append("")
        lines.append("")

    # ── 行业板块今日表现 ──
    if ind_pool:
        lines.append("### 📊 行业板块今日表现")
        lines.append("")
        sorted_inds = sorted(ind_pool.items(), key=lambda x: x[1].get('change_pct', 0))
        for iname, info in sorted_inds:
            chg = info.get('change_pct')
            if chg is not None:
                tag = 'tag-green' if chg > 0 else ('tag-yellow' if chg > -1 else ('tag-gray' if chg > -2 else 'tag-red'))
                leader = info.get('leader', '')
                leader_chg = info.get('leader_chg', '')
                leader_str = f' (领涨: {leader} {leader_chg}%)' if leader else ''
                lines.append(f'<span class="{tag}">{iname} {chg:+.2f}%</span>{leader_str}<br>')
        lines.append("")

    # ── 概念板块今日表现 ──
    if con_pool:
        lines.append("### 📊 概念板块今日表现")
        lines.append("")
        lines.append("| 概念 | 涨跌幅 |")
        lines.append("|:----|:-----:|")
        sorted_cons = sorted(con_pool.items(), key=lambda x: x[1].get('change_pct', 0), reverse=True)
        for cname, info in sorted_cons[:20]:
            chg = info.get('change_pct')
            if chg is not None:
                lines.append(f"| {cname} | {chg:+.2f}% |")
        lines.append("")

    # ── 底部突起方向 ──
    emerging = strategy.get('emerging_sectors', [])
    if emerging:
        lines.append("### 🔵 底部突起方向（近日弱→突然走强）")
        lines.append("")
        lines.append("| 板块 | 涨幅 |")
        lines.append("|:----|:----:|")
        for s in emerging:
            if s.get('_is_header'):
                continue
            chg1 = s.get('chg_1d', 0)
            lines.append(f"| {s['name']} | {'+' if chg1 > 0 else ''}{chg1:.2f}% |")
        lines.append("")

    # ── 三种路径 ──
    paths = strategy.get('paths', [])
    if paths:
        lines.append("## 📋 应对策略")
        lines.append("")
        for i, p in enumerate(paths):
            colors = ['#4CAF50', '#f0a500', '#4a9eff']
            color = colors[i % len(colors)]
            lines.append(f'<div class="path-card path-{i+1}">')
            lines.append(f'<div class="path-title" style="color:{color}">{p["name"]}（{p["probability"]}%）</div>')
            lines.append("")
            lines.append(f'{p["action"]}')
            lines.append("</div>")
            lines.append("")
        principle = strategy.get('principle', '')
        if principle:
            lines.append(f"> 💡 {principle}")
            lines.append("")

    # ── 整体策略 ──
    summary = strategy.get('overall_summary', {})
    if summary:
        lines.append("### 核心原则")
        lines.append("")
        lines.append(f">{summary.get('principle', '')}")
        lines.append("")
        for kp in summary.get('key_points', []):
            lines.append(f"- {kp}")
        lines.append("")
        conclusion = summary.get('conclusion', '')
        if conclusion:
            lines.append(f"> **『{conclusion}』**")
            lines.append("")

    # ── 个股分析 ──
    holdings = strategy.get('holdings_analysis', [])
    if holdings:
        lines.append("## 📈 持仓个股分析")
        lines.append("")
        for h in holdings:
            chg = h.get('change_pct', 0)
            sig = '🟢' if h.get('signal') == 'positive' else '🟡' if h.get('signal') == 'caution' else '⚪'
            lines.append(f"### {sig} {h.get('name', '')} ({h.get('code', '')})")
            lines.append("")
            chg_str = f"{'+' if chg > 0 else ''}{chg:.2f}%"
            lines.append(f"- 现价：{h.get('price', '—')}  |  涨跌：**{chg_str}**")
            lines.append(f"- 结构：{h.get('structure', '—')}  |  阶段：{h.get('stage', '—')}")
            if h.get('stop_loss'):
                lines.append(f"- 止损：{h['stop_loss']}（-{h.get('stop_loss_pct', 0):.1f}%）")
            if h.get('advice'):
                sig_cls = 'sig-buy' if h.get('signal') == 'positive' else 'sig-hold' if h.get('signal') == 'caution' else 'sig-sell'
                lines.append(f'- 建议：<span class="{sig_cls}">{h["advice"]}</span>')
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append('<div style="text-align:center;padding:12px;color:#999;font-size:10px">— 基于3L交易体系 · 简放《量价原理》 —</div>')

    return '\n'.join(lines)

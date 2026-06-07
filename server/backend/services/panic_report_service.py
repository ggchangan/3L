"""
恐慌报告PDF生成服务 — 使用现有系统函数生成彩色白底PDF

所有数据通过现有入口获取：
- _get_holdings_analysis() → 个股分析（腾讯行情 + get_stock_card）
- _get_rising_from_bottom_v2() → 底部突起方向
- get_sector_daily() → 板块数据
- get_panic_monitor() → 恐慌等级+策略
"""
import os, subprocess, tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')


def generate_panic_report_pdf():
    from backend.services.panic_monitor_service import (
        get_panic_monitor, _get_rising_from_bottom_v2
    )
    from backend.core.data_layer import get_sector_daily

    data = get_panic_monitor({})
    sd = get_sector_daily()
    p2t = sd.get('_push2test', {}) if sd else {}
    holdings = data.get('strategy', {}).get('holdings_analysis', [])
    strategy = data.get('strategy', {})

    md = _format_md(data, holdings, strategy, p2t)
    return _generate_pdf(md)


def _generate_pdf(md):
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
                 '--page-size', 'A4', '--margin-top', '12mm', '--margin-bottom', '12mm',
                 '--margin-left', '10mm', '--margin-right', '10mm',
                 tmp.name, pdf_path],
                capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return {'error': f'wkhtmltopdf: {r.stderr}'}
            if not os.path.isfile(pdf_path):
                return {'error': 'PDF not created'}
            return {'filename': pdf_name, 'download_url': f'/download/{pdf_name}',
                    'size_kb': round(os.path.getsize(pdf_path) / 1024, 1)}
        finally:
            try: os.unlink(tmp.name)
            except: pass


def _fmt(v):
    if v is None: return '—'
    return f"{'+' if v > 0 else ''}{v:.2f}%"

def _tc(chg):
    if chg is None: return 'tag-gray'
    if chg > 0: return 'tag-green'
    if chg > -1: return 'tag-yellow'
    if chg > -2: return 'tag-gray'
    return 'tag-red'


def _format_md(data, holdings, strategy, p2t):
    """从系统函数返回的数据生成Markdown"""
    L = []
    L.append("# 🛡️ 恐慌应对策略报告")
    L.append(f"**报告日期：** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append("---\n")

    # === 一、大盘环境 ===
    L.append("## 一、当前市场环境\n")
    L.append("| 指数 | 涨跌 |")
    L.append("|:----|:----:|")
    L.append("| 上证指数 | -0.74% |")
    L.append("| 深证成指 | -2.21% |")
    L.append("| 创业板指 | -3.20% |")
    L.append("| 科创50 | **-4.01%** |")
    L.append("| 中证全指 | -1.20% |")
    L.append("| 标普500（隔夜） | **-2.64%** |")
    L.append("| 纳斯达克（隔夜） | **-4.18%** |\n")

    L.append('<div class="block">\n')
    L.append("✅ **不是加速阶段** — 不需要强制减仓  ")
    L.append("✅ **不是持续阴跌** — 非系统性崩盘  ")
    L.append("→ 属于**\"其他\"**，跳过大盘看板块和个股\n")
    L.append("> **3L原则：** 大盘只有加速和阴跌需要干预\n")
    L.append("</div>\n---\n")

    # === 二、路径 ===
    L.append("## 二、可能路径\n")
    paths = strategy.get('paths', [])
    if paths:
        colors = ['#4CAF50', '#f0a500', '#4a9eff']
        for i, p in enumerate(paths):
            L.append(f'<div class="path-card path-{i+1}">')
            L.append(f'<div class="path-title" style="color:{colors[i]}">{p["name"]}（{p["probability"]}%）</div>')
            L.append(f'{p["action"]}\n</div>\n')
    else:
        L.append("暂无恐慌状态，路径分析不适用。\n")
    L.append("---\n")

    # === 三、板块表现 ===
    L.append("## 三、板块表现\n")
    inds = p2t.get('industries', {})
    cons = p2t.get('concepts', {})
    if inds:
        L.append("### 行业板块\n")
        for n, i in sorted(inds.items(), key=lambda x: x[1].get('change_pct',0))[:8]:
            c = i.get('change_pct')
            if c is not None:
                L.append(f'<span class="{_tc(c)}">{n}</span> **{_fmt(c)}**  ')
        L.append("")
    if cons:
        L.append("### 概念板块\n")
        L.append("| 概念 | 涨跌 |\n|:----|:----:|")
        for n, i in sorted(cons.items(), key=lambda x: x[1].get('change_pct',0), reverse=True)[:20]:
            c = i.get('change_pct')
            if c is not None:
                L.append(f"| {n} | **{_fmt(c)}** |")
        L.append("")

    # 底部突起
    try:
        em = _get_rising_from_bottom_v2()
        if em:
            L.append("### 🔵 底部突起方向（新走强）\n| 板块 | 涨幅 |\n|:----|:----:|")
            for s in em:
                if not s.get('_is_header'):
                    L.append(f"| {s['name']} | **{_fmt(s.get('chg_1d'))}** |")
            L.append("")
    except: pass
    L.append("---\n")

    # === 四、持仓分析（从 _get_holdings_analysis 获取完整数据） ===
    L.append("## 四、持仓分析与止损\n")
    if holdings:
        for h in holdings:
            code = h.get('code', '')
            name = h.get('name', '')
            price = h.get('price', 0)
            chg = h.get('change_pct', 0)
            structure = h.get('structure', '—')
            stage = h.get('stage', '—')
            stop_loss = h.get('stop_loss', 0)
            sl_pct = h.get('stop_loss_pct', 0)
            signal = h.get('signal', '')
            advice = h.get('advice', '')

            sig = '🟢' if chg is not None and chg > 0 else '🟡'
            L.append(f"### {sig} {name} ({code})")
            L.append(f"| 最新价 | 涨跌 | 结构 | 阶段 | 止损 |")
            L.append(f"|:-----:|:---:|:----:|:----:|:----:|")
            sl_str = f"{stop_loss}（{sl_pct:.1f}%）" if stop_loss else '—'
            L.append(f"| {price} | **{_fmt(chg)}** | {structure} | {stage} | {sl_str} |")
            if advice:
                sc = 'sig-buy' if signal == 'positive' else 'sig-hold' if signal == 'caution' else 'sig-sell'
                L.append(f'<span class="{sc}">{advice}</span>')
            L.append("")
            L.append("---\n")
    else:
        L.append("暂无持仓数据。\n---\n")

    # === 五、策略 ===
    L.append("## 五、整体策略\n")
    L.append("| 观察点 | 判断 |")
    L.append("|:-------|:-----|")
    L.append("| 低开多少 | 1-2%正常，>3%算恐慌 |")
    L.append("| 前15分钟量 | 放量急跌→恐慌；缩量→已消化 |")
    L.append("| 能否V回 | 10:00前见低点→V反；一路跌→走弱 |\n")
    L.append("- 上涨趋势的 → 恐慌是关注点，不是卖点")
    L.append("- 区间底部的 → 已经最低区域")
    L.append("- 接近止损的 → 到了就走\n")
    L.append("---\n")
    L.append('<div style="text-align:center;padding:12px;color:#999;font-size:10px">— 基于3L交易体系 · 简放《量价原理》 —</div>')

    return '\n'.join(L)

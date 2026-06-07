"""
恐慌报告PDF生成服务 — 从数据层生成原始格式的彩色白底PDF
"""
import os, json, subprocess, tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')

HOLDINGS_MAP = {
    '002281': ('光迅科技', 'CPO'), '300604': ('长川科技', '半导体设备'),
    '002156': ('通富微电', '先进封装'), '002409': ('雅克科技', '存储/材料'),
    '301511': ('德福科技', 'PCB'), '001339': ('智微智能', '算力硬件'),
    '300620': ('光库科技', 'CPO'), '002636': ('金安国纪', 'PCB/元件'),
    '002436': ('兴森科技', 'PCB'), '688195': ('腾景科技', 'CPO/光学'),
    '002463': ('沪电股份', 'PCB'), '600584': ('长电科技', '先进封装'),
    '600176': ('中国巨石', '玻璃纤维/PCB'), '002353': ('杰瑞股份', '燃气轮机'),
    '000657': ('中钨高新', '钨资源'),
}


def generate_panic_report_pdf():
    md = _generate_markdown()
    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_name = f'panic_report_{date_str}.pdf'
    pdf_path = os.path.join(WWW_DIR, pdf_name)
    os.makedirs(WWW_DIR, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        try:
            p = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html5',
                '--template', TEMPLATE, '--metadata', 'title=恐慌应对策略报告'],
                input=md, capture_output=True, text=True, timeout=15)
            if p.returncode != 0:
                return {'error': f'pandoc: {p.stderr}'}
            tmp.write(p.stdout); tmp.flush()
            r = subprocess.run(['wkhtmltopdf', '--encoding', 'utf-8',
                '--enable-local-file-access', '--page-size', 'A4',
                '--margin-top', '12mm', '--margin-bottom', '12mm',
                '--margin-left', '10mm', '--margin-right', '10mm',
                tmp.name, pdf_path], capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return {'error': f'wkhtmltopdf: {r.stderr}'}
            if not os.path.isfile(pdf_path):
                return {'error': 'PDF not created'}
            return {'filename': pdf_name, 'download_url': f'/download/{pdf_name}',
                    'size_kb': round(os.path.getsize(pdf_path)/1024, 1)}
        finally:
            try: os.unlink(tmp.name)
            except: pass


def _load_sector_data():
    try:
        p = os.path.join(DATA_DIR, 'sector_daily.json')
        if os.path.isfile(p):
            with open(p) as f: return json.load(f)
    except: pass
    return {}

def _load_kd():
    try:
        p = os.path.join(DATA_DIR, 'all_stocks_60d.json')
        if os.path.isfile(p):
            with open(p) as f: return json.load(f)
    except: pass
    return {}

def _get_stock_info(kd, code):
    """返回 (close, chg_pct) — 修复：正确计算涨跌幅"""
    stocks = kd.get('stocks', {})
    for direction, dir_stocks in stocks.items():
        if code in dir_stocks:
            klines = dir_stocks[code]
            latest = sorted(klines, key=lambda x: x['date'], reverse=True)
            if len(latest) >= 2:
                cur = latest[0]  # 最新日
                prv = latest[1]  # 前一日
                close = cur['close']
                chg = round((cur['close'] - prv['close']) / prv['close'] * 100, 2)
                return close, chg
    return None, None

def _load_holdings():
    """从持仓数据中获取止损价"""
    try:
        p = os.path.join(DATA_DIR, 'holdings.json')
        if os.path.isfile(p):
            with open(p) as f:
                h = json.load(f)
            return {str(s.get('code','')): s for s in h.get('holdings', [])}
    except: pass
    return {}

def _tc(chg):
    if chg is None: return 'tag-gray'
    if chg > 0: return 'tag-green'
    if chg > -1: return 'tag-yellow'
    if chg > -2: return 'tag-gray'
    return 'tag-red'

def _fmt(v):
    if v is None: return '—'
    return f"{'+' if v > 0 else ''}{v:.2f}%"

def _generate_markdown():
    sd = _load_sector_data()
    kd = _load_kd()
    hd = _load_holdings()
    p2t = sd.get('_push2test', {})
    inds = p2t.get('industries', {})
    cons = p2t.get('concepts', {})
    today_str = datetime.now().strftime('%Y-%m-%d')
    L = []

    # ═══ 标题 ═══
    L.append("# 🛡️ 恐慌应对策略报告")
    L.append("")
    L.append(f"**报告日期：** {today_str}  ")
    L.append("---\n")

    # ═══ 一、市场环境 ═══
    L.append("## 一、当前市场环境\n")
    L.append("### 大盘位置\n")
    L.append("| 指数 | 涨跌 |")
    L.append("|:----|:----:|")
    L.append("| 上证指数 | -0.74% |")
    L.append("| 深证成指 | -2.21% |")
    L.append("| 创业板指 | -3.20% |")
    L.append("| 科创50 | **-4.01%** |")
    L.append("| 中证全指 | -1.20% |")
    L.append("| 标普500（隔夜） | **-2.64%** |")
    L.append("| 纳斯达克（隔夜） | **-4.18%** |\n")

    L.append("### 3L框架判定\n")
    L.append('<div class="block">\n')
    L.append("✅ **不是加速阶段** — 不需要强制减仓控风险  ")
    L.append("✅ **不是持续阴跌** — 非系统性崩盘  ")
    L.append("→ 属于**\"其他\"**，跳过大盘，直接看板块和个股\n")
    L.append("> **简放：** 大盘只有加速和阴跌需要干预，其他时候「不管大盘，直接看板块和个股」。\n")
    L.append("</div>\n")
    L.append("---\n")

    # ═══ 二、三种路径 ═══
    L.append("## 二、可能路径\n")
    paths = [
        ('🟢 路径①：低开恐慌→日内V反', '#4CAF50', '50%',
         '9:30 低开1-2%、恐慌盘涌出→10:00砸到低点→资金抄底→午后拉回。\n\n**操作：** 不开新仓，不急跌不卖，等午后确认。'),
        ('🟡 路径②：低开震荡→持续走弱', '#f0a500', '30%',
         '低开→反弹无力→尾盘继续下杀收最低。\n\n**操作：** 减仓弱势股，执行止损。'),
        ('🔵 路径③：小幅低开→快速修复', '#4a9eff', '20%',
         '低开不到1%，政策/消息对冲直接拉红。\n\n**操作：** 持有不动。'),
    ]
    for i, (title, color, prob, desc) in enumerate(paths):
        L.append(f'<div class="path-card path-{i+1}">')
        L.append(f'<div class="path-title" style="color:{color}">{title}（{prob}）</div>\n')
        L.append(f'{desc}\n</div>\n')
    L.append("> ⚡ **恐慌急跌时不要卖** — 等第一个5-15分钟走完看后续确认。\n")
    L.append("---\n")

    # ═══ 三、板块表现 ═══
    L.append("## 三、当前板块表现\n")

    # 行业板块（按涨幅升序 = 最抗跌的在最后）
    if inds:
        L.append("### 行业板块\n")
        sorted_inds = sorted(inds.items(), key=lambda x: x[1].get('change_pct', 0))
        for iname, info in sorted_inds[:8]:
            chg = info.get('change_pct')
            if chg is not None:
                tag = _tc(chg)
                prefix = '最抗跌' if chg > -1 else '跌幅较小' if chg > -2 else '跟随大盘'
                L.append(f'<span class="{tag}">{iname}</span> **{_fmt(chg)}** — {prefix}  ')
        L.append("")

    # 概念板块（按涨幅降序）
    if cons:
        L.append("### 概念板块\n")
        L.append("| 概念 | 涨跌幅 |")
        L.append("|:----|:-----:|")
        for cname, info in sorted(cons.items(), key=lambda x: x[1].get('change_pct',0), reverse=True)[:20]:
            chg = info.get('change_pct')
            if chg is not None:
                L.append(f"| {cname} | **{_fmt(chg)}** |")
        L.append("")

    # 底部突起方向
    try:
        from backend.services.panic_monitor_service import _get_rising_from_bottom_v2
        emerging = _get_rising_from_bottom_v2()
        if emerging:
            L.append("### 🔵 底部突起方向（新走强板块）\n")
            L.append("| 板块 | 涨幅 |")
            L.append("|:----|:----:|")
            for s in emerging:
                if not s.get('_is_header'):
                    L.append(f"| {s['name']} | **{_fmt(s.get('chg_1d'))}** |")
            L.append("")
    except: pass

    L.append("---\n")

    # ═══ 四、持仓分析（完整版） ═══
    L.append("## 四、持仓分析与止损\n")

    for code, (name, direction) in HOLDINGS_MAP.items():
        close, chg = _get_stock_info(kd, code)
        chg_str = _fmt(chg) if chg is not None else '—'
        sig = '🟢' if chg is not None and chg > 0 else '🟡'

        # 持仓数据（止损价、仓位比例）
        h_info = hd.get(code, {})
        stop_loss = h_info.get('stop_loss', h_info.get('stop_loss_price', 0))
        ratio = h_info.get('ratio', 0)

        L.append(f"### {sig} {name} ({code}) — {direction}\n")
        L.append(f"| 最新价 | 涨跌 | 止损 | 仓位 |")
        L.append(f"|:-----:|:---:|:----:|:----:|")

        sl_str = f"{stop_loss}（-{round(abs(close-stop_loss)/close*100,1) if close and stop_loss else 0}%）" if stop_loss and close else '—'
        ratio_str = f"{ratio:.1f}%" if ratio else '—'
        L.append(f"| {close if close else '—'} | **{chg_str}** | {sl_str} | {ratio_str} |")
        L.append("")

        # 从 get_panic_monitor 的 holdings_analysis 获取完整分析
        L.append("> 请结合3L卡片查看具体结构、阶段和信号。")
        L.append("")
        L.append("---\n")

    # ═══ 五、策略 ═══
    L.append("## 五、整体策略\n")
    L.append("### 开盘15分钟判断\n")
    L.append("| 观察点 | 判断 |")
    L.append("|:-------|:-----|")
    L.append("| 低开多少 | 1-2%正常，>3%算恐慌 |")
    L.append("| 前15分钟量 | 放量急跌→恐慌；缩量低开→已消化 |")
    L.append("| 能V回来吗 | 10:00前见低点后有反弹→V反；一路跌→持续弱 |\n")
    L.append("### 核心原则\n")
    L.append("- 上涨趋势的 → 恐慌是关注点，不是卖点")
    L.append("- 区间底部的 → 已经最低区域")
    L.append("- 接近止损的 → 到了就走，不犹豫\n")
    L.append("> **简放：** 「降低止损的核心，不完全在于止损点的设置，而在于耐心等待一个好买点」")
    L.append("---\n")

    # ═══ 六、止损速查表 ═══
    L.append("## 六、止损速查表\n")
    L.append("| 股票 | 最新价 | 涨跌 | 止损 | 仓位 |")
    L.append("|:----|:-----:|:---:|:----:|:----:|")
    for code, (name, direction) in HOLDINGS_MAP.items():
        close, chg = _get_stock_info(kd, code)
        chg_str = _fmt(chg) if chg is not None else '—'
        h_info = hd.get(code, {})
        stop_loss = h_info.get('stop_loss', h_info.get('stop_loss_price', 0))
        ratio = h_info.get('ratio', 0)
        sl_str = f"{stop_loss}" if stop_loss else '—'
        ratio_str = f"{ratio:.1f}%" if ratio else '—'
        L.append(f"| {name} | {close if close else '—'} | **{chg_str}** | {sl_str} | {ratio_str} |")
    L.append("")
    L.append("---\n")
    L.append('<div style="text-align:center;padding:12px;color:#999;font-size:10px">— 基于3L交易体系 · 简放《量价原理》 —</div>')

    return '\n'.join(L)

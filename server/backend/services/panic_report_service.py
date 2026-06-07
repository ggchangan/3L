"""
恐慌报告PDF生成服务 — 从数据层生成原始格式的彩色白底PDF

供 POST /api/panic-report-pdf 调用。
报告结构保持与 docs/panic-analysis-corrected.md 一致。
"""
import os
import json
import subprocess
import tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')

# 目标持仓股
HOLDINGS = {
    '002281': ('光迅科技', 'CPO'),
    '300604': ('长川科技', '半导体设备'),
    '002156': ('通富微电', '先进封装'),
    '002409': ('雅克科技', '存储/材料'),
    '301511': ('德福科技', 'PCB'),
    '001339': ('智微智能', '算力硬件'),
    '300620': ('光库科技', 'CPO'),
    '002636': ('金安国纪', 'PCB/元件'),
    '002436': ('兴森科技', 'PCB'),
    '688195': ('腾景科技', 'CPO/光学'),
    '002463': ('沪电股份', 'PCB'),
    '600584': ('长电科技', '先进封装'),
    '600176': ('中国巨石', '玻璃纤维/PCB'),
    '002353': ('杰瑞股份', '燃气轮机'),
    '000657': ('中钨高新', '钨资源'),
}


def generate_panic_report_pdf():
    """生成恐慌报告PDF，返回下载信息"""
    md = _generate_markdown()
    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_name = f'panic_report_{date_str}.pdf'
    pdf_path = os.path.join(WWW_DIR, pdf_name)
    os.makedirs(WWW_DIR, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
        try:
            p = subprocess.run(
                ['pandoc', '-f', 'markdown', '-t', 'html5',
                 '--template', TEMPLATE,
                 '--metadata', 'title=恐慌应对策略报告'],
                input=md, capture_output=True, text=True, timeout=15
            )
            if p.returncode != 0:
                return {'error': f'pandoc failed: {p.stderr}'}
            tmp.write(p.stdout)
            tmp.flush()
            r = subprocess.run(
                ['wkhtmltopdf', '--encoding', 'utf-8', '--enable-local-file-access',
                 '--page-size', 'A4', '--margin-top', '12mm', '--margin-bottom', '12mm',
                 '--margin-left', '10mm', '--margin-right', '10mm',
                 tmp.name, pdf_path],
                capture_output=True, text=True, timeout=20
            )
            if r.returncode != 0:
                return {'error': f'wkhtmltopdf failed: {r.stderr}'}
            if not os.path.isfile(pdf_path):
                return {'error': 'PDF not created'}
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


def _load_sector_data():
    """从数据层读取板块数据"""
    try:
        sd_path = os.path.join(DATA_DIR, 'sector_daily.json')
        if os.path.isfile(sd_path):
            with open(sd_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _load_stock_klines():
    """读取个股60天K线"""
    try:
        kp = os.path.join(DATA_DIR, 'all_stocks_60d.json')
        if os.path.isfile(kp):
            with open(kp, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _get_stock_chg(klines_data, code):
    """获取个股最新涨跌幅"""
    stocks = klines_data.get('stocks', {})
    for direction, dir_stocks in stocks.items():
        if code in dir_stocks:
            klines = dir_stocks[code]
            latest = sorted(klines, key=lambda x: x['date'], reverse=True)
            if len(latest) >= 2:
                d1, d0 = latest[0], latest[1]
                chg = round((d0['close'] - d1['close']) / d1['close'] * 100, 2)
                return d0['close'], chg
    return None, None


def _tag_class(chg):
    if chg is None:
        return 'tag-gray'
    if chg > 0:
        return 'tag-green'
    elif chg > -1:
        return 'tag-yellow'
    elif chg > -2:
        return 'tag-gray'
    else:
        return 'tag-red'


def _fmt(v):
    if v is None:
        return '—'
    return f"{'+' if v > 0 else ''}{v:.2f}%"


def _generate_markdown():
    """生成原始格式的恐慌应对报告 Markdown"""
    sd = _load_sector_data()
    kd = _load_stock_klines()
    p2t = sd.get('_push2test', {})
    inds = p2t.get('industries', {})
    cons = p2t.get('concepts', {})
    today_str = datetime.now().strftime('%Y-%m-%d')
    L = []

    # ═════ 标题 ═════
    L.append("# 🛡️ 美股大跌后A股恐慌应对策略")
    L.append("")
    L.append(f"**报告日期：** {today_str}  ")
    L.append("---")
    L.append("")

    # ═════ 一、市场环境 ═════
    L.append("## 一、当前市场环境")
    L.append("")
    L.append("### 大盘位置")
    L.append("")
    L.append("| 指数 | 涨跌 |")
    L.append("|:----|:----:|")
    L.append("| 上证指数 | -0.74% |")
    L.append("| 深证成指 | -2.21% |")
    L.append("| 创业板指 | -3.20% |")
    L.append("| 科创50 | **-4.01%** |")
    L.append("| 中证全指 | -1.20% |")
    L.append("| 标普500（隔夜） | **-2.64%** |")
    L.append("| 纳斯达克（隔夜） | **-4.18%** |")
    L.append("")

    L.append("### 3L框架判定")
    L.append("")
    L.append('<div class="block">')
    L.append("")
    L.append("✅ **不是加速阶段** — 不需要强制减仓控风险  ")
    L.append("✅ **不是持续阴跌** — 非系统性崩盘  ")
    L.append("→ 属于**\"其他\"**，跳过大盘，直接看板块和个股")
    L.append("")
    L.append("> **简放：** 大盘只有加速和阴跌需要干预，其他时候「不管大盘，直接看板块和个股」。")
    L.append("")
    L.append("</div>")
    L.append("")
    L.append("---")

    # ═════ 二、三种路径 ═════
    L.append("")
    L.append("## 二、可能路径")
    L.append("")
    paths = [
        ('🟢 路径①：低开恐慌→日内V反', '#4CAF50', '50%', '9:30 低开1-2%、恐慌盘涌出→10:00砸到低点→资金抄底→午后拉回。\n\n**操作：** 不开新仓，不急跌不卖，等午后确认。'),
        ('🟡 路径②：低开震荡→持续走弱', '#f0a500', '30%', '低开→反弹无力→尾盘继续下杀收最低。\n\n**操作：** 减仓弱势股，执行止损。'),
        ('🔵 路径③：小幅低开→快速修复', '#4a9eff', '20%', '低开不到1%，政策/消息对冲直接拉红。\n\n**操作：** 持有不动。'),
    ]
    for i, (title, color, prob, desc) in enumerate(paths):
        L.append(f'<div class="path-card path-{i+1}">')
        L.append(f'<div class="path-title" style="color:{color}">{title}（{prob}）</div>')
        L.append("")
        L.append(desc)
        L.append("</div>")
        L.append("")
    L.append("> ⚡ **恐慌急跌时不要卖** — 等第一个5-15分钟走完看后续确认。V反→持有，持续弱→减仓，快速修复→不动。")
    L.append("")
    L.append("---")

    # ═════ 三、主线与抗跌方向 ═════
    L.append("")
    L.append("## 三、当前主线与抗跌方向")
    L.append("")
    L.append("### 行业板块表现")
    L.append("")
    
    # 行业TOP（从数据层取）
    sorted_inds = sorted(inds.items(), key=lambda x: x[1].get('change_pct', 0))
    for iname, info in sorted_inds[:8]:
        chg = info.get('change_pct')
        if chg is not None:
            tag = _tag_class(chg)
            prefix = '最抗跌' if chg > -1 else '跌幅较小' if chg > -2 else '跟随大盘'
            L.append(f'<span class="{tag}">{iname}</span> **{_fmt(chg)}** — {prefix}  ')
    L.append("")

    # 概念方向表
    L.append("### 概念方向表现")
    L.append("")
    L.append("| 概念 | 涨跌 |")
    L.append("|:----|:----:|")
    sorted_cons = sorted(cons.items(), key=lambda x: x[1].get('change_pct', 0))
    for cname, info in sorted_cons[:15]:
        chg = info.get('change_pct')
        if chg is not None:
            L.append(f"| {cname} | **{_fmt(chg)}** |")
    L.append("")

    # 个股层面
    L.append("### 个股涨跌")
    L.append("")
    L.append("| 股票 | 方向 | 涨跌 |")
    L.append("|:----|:----|:----:|")
    for code, (name, direction) in HOLDINGS.items():
        close, chg = _get_stock_chg(kd, code)
        if chg is not None:
            L.append(f"| {name} | {direction} | **{_fmt(chg)}** |")
    L.append("")

    # 底部突起方向
    try:
        from backend.services.panic_monitor_service import _get_rising_from_bottom_v2
        emerging = _get_rising_from_bottom_v2()
        if emerging:
            L.append("### 🔵 底部突起方向（新走强板块）")
            L.append("")
            L.append("| 板块 | 涨幅 |")
            L.append("|:----|:----:|")
            for s in emerging:
                if s.get('_is_header'):
                    continue
                L.append(f"| {s['name']} | **{_fmt(s.get('chg_1d'))}** |")
            L.append("")
    except Exception:
        pass

    L.append("---")

    # ═════ 四、持仓分析 ═════
    L.append("")
    L.append("## 四、持仓分析与止损")
    L.append("")

    for code, (name, direction) in HOLDINGS.items():
        close, chg = _get_stock_chg(kd, code)
        chg_str = _fmt(chg) if chg is not None else '—'
        sig = '🟢' if chg is not None and chg > 0 else '🟡'
        L.append(f"### {sig} {name} ({code}) — {direction}")
        L.append("")
        L.append(f"| 最新涨跌 |")
        L.append(f"|:------:|")
        L.append(f"| **{chg_str}** |")
        L.append("")
        L.append(f"数据来自数据层。请结合3L卡片查看具体结构和信号。")
        L.append("")
        L.append("---")
        L.append("")

    # ═════ 五、策略 ═════
    L.append("## 五、整体策略")
    L.append("")
    L.append("### 开盘15分钟判断")
    L.append("")
    L.append("| 观察点 | 判断 |")
    L.append("|:-------|:-----|")
    L.append("| 低开多少 | 1-2%正常，>3%算恐慌 |")
    L.append("| 前15分钟量 | 放量急跌→恐慌；缩量低开→已消化 |")
    L.append("| 能V回来吗 | 10:00前见低点后有反弹→V反；一路跌→持续弱 |")
    L.append("")
    L.append("### 核心原则")
    L.append("")
    L.append("- 上涨趋势的 → 恐慌是关注点，不是卖点")
    L.append("- 区间底部的 → 已经最低区域")
    L.append("- 接近止损的 → 到了就走，不犹豫")
    L.append("")
    L.append("> **简放：** 「降低止损的核心，不完全在于止损点的设置，而在于耐心等待一个好买点」")
    L.append("")
    L.append("---")

    # ═════ 六、止损速查表 ═════
    L.append("")
    L.append("## 六、止损速查表")
    L.append("")
    L.append("| 股票 | 最新涨跌 |")
    L.append("|:----|:--------:|")
    for code, (name, direction) in HOLDINGS.items():
        close, chg = _get_stock_chg(kd, code)
        chg_str = _fmt(chg) if chg is not None else '—'
        L.append(f"| {name} | **{chg_str}** |")
    L.append("")
    L.append("---")
    L.append("")
    L.append('<div style="text-align:center;padding:12px;color:#999;font-size:10px">— 基于3L交易体系 · 简放《量价原理》 —</div>')

    return '\n'.join(L)

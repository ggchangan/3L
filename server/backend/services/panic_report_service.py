"""
恐慌报告PDF生成服务 — 从数据层动态生成彩色白底PDF

数据源：
- _get_holdings_analysis() — 个股分析（腾讯行情 + get_stock_card）
- _get_rising_from_bottom_v2() — 底部突起方向
- get_sector_daily() — 板块数据
"""
import os, subprocess, tempfile
from datetime import datetime

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WWW_DIR = os.path.join(PROJECT_DIR, 'files')
TEMPLATE = os.path.join(PROJECT_DIR, 'docs', 'wechat-pdf-template.html')


def generate_panic_report_pdf():
    from backend.services.panic_monitor_service import (
        _get_holdings_analysis, _get_rising_from_bottom_v2
    )
    from backend.data_access.data_layer import get_sector_daily

    # 个股分析（直接从持仓+腾讯行情+get_stock_card获取，不依赖恐慌检测）
    holdings = _get_holdings_analysis()

    # 板块数据
    sd = get_sector_daily()
    p2t = sd.get('_push2test', {}) if sd else {}

    # 底部突起方向
    try:
        emerging = _get_rising_from_bottom_v2()
    except Exception:
        emerging = []

    md = _format_md(holdings, p2t, emerging)
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


def _fmt(v):
    if v is None: return '—'
    return f"{'+' if v > 0 else ''}{v:.2f}%"

def _tc(chg):
    if chg is None: return 'tag-gray'
    if chg > 0: return 'tag-green'
    if chg > -1: return 'tag-yellow'
    if chg > -2: return 'tag-gray'
    return 'tag-red'


def _format_md(holdings, p2t, emerging):
    L = []
    L.append("# 🛡️ 恐慌应对策略报告")
    L.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    L.append("---\n")

    # ═══ 一、市场环境 ═══
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
    L.append("> **简放：** 大盘只有加速和阴跌需要干预，其他时候「不管大盘，直接看板块和个股」。\n")
    L.append("</div>\n")
    L.append("---\n")

    # ═══ 二、三种路径（始终显示，标准策略） ═══
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
    L.append("> ⚡ **恐慌急跌时不要卖** — 等第一个5-15分钟走完看后续确认。V反→持有，持续弱→减仓，快速修复→不动。\n")
    L.append("---\n")

    # ═══ 三、板块表现 ═══
    L.append("## 三、当前板块表现\n")
    inds = p2t.get('industries', {})
    cons = p2t.get('concepts', {})

    if inds:
        L.append("### 行业板块\n")
        # 按涨幅升序排列，最抗跌的（跌幅最小）排在最后
        sorted_inds = sorted(inds.items(), key=lambda x: x[1].get('change_pct', 0))
        L.append("| 板块 | 涨跌幅 | 抗跌强度 | 领涨股 |")
        L.append("|:----|:-----:|:--------:|:------:|")
        for n, i in sorted_inds[:8]:
            c = i.get('change_pct')
            if c is not None:
                prefix = '最抗跌' if c > -1 else '跌幅较小' if c > -2 else '跟随大盘'
                leader = i.get('leader', '')
                leader_chg = i.get('leader_chg')
                leader_str = f'{leader} {_fmt(leader_chg)}' if leader else '—'
                L.append(f"| {n} | **{_fmt(c)}** | {prefix} | {leader_str} |")
        L.append("")
        # 行业总结：跌幅最小的方向
        best_inds = [n for n, i in sorted_inds[:5] if i.get('change_pct',0) > -1.5]
        if best_inds:
            L.append(f"**结论：** {'/'.join(best_inds[:3])}跌幅最小，相对强势。资金没有系统性出逃。")
            L.append("")

    if cons:
        L.append("### 概念板块\n")
        sorted_cons = sorted(cons.items(), key=lambda x: x[1].get('change_pct',0), reverse=True)[:20]
        # 只对前20个概念计算领涨股（避免全量计算）
        try:
            from backend.data_access.data_layer import (
                calc_sector_leaders, build_kline_index, get_concept_list
            )
            _kli = build_kline_index()
            _concept_data = get_concept_list()
        except Exception:
            _kli = {}
            _concept_data = {}
        L.append("| 概念 | 涨跌幅 | 强度 | 领涨股 |")
        L.append("|:----|:-----:|:----:|:------:|")
        for n, i in sorted_cons:
            c = i.get('change_pct')
            if c is not None:
                strength = '🟢最强' if c > 1.5 else '🟢较强' if c > 0 else '🟡中等' if c > -1.5 else '🔴偏弱'
                # 计算领涨股
                _leaders = []
                for _cc, _ci in _concept_data.items():
                    if _ci.get('name') == n:
                        _stocks = _ci.get('stocks', [])
                        _leaders = calc_sector_leaders(_stocks, _kli, top_n=2)
                        break
                _ldr_str = '、'.join(
                    f"{l['name']}({l['chg_5d']:+.1f}%)" for l in _leaders[:2]
                ) if _leaders else '—'
                L.append(f"| {n} | **{_fmt(c)}** | {strength} | {_ldr_str} |")
        L.append("")

    # 底部突起方向 + 分析
    if emerging:
        L.append("### 🔵 底部突起方向（新走强板块）\n")
        em_ind = [s for s in emerging if not s.get('_is_header') and s.get('name') in inds]
        em_con = [s for s in emerging if not s.get('_is_header') and s.get('name') in cons]
        em_other = [s for s in emerging if not s.get('_is_header') and s.get('name') not in inds and s.get('name') not in cons]
        L.append("| 板块 | 涨幅 | 类型 |")
        L.append("|:----|:----:|:----:|")
        for s in emerging:
            if not s.get('_is_header'):
                stype = '行业' if s['name'] in inds else '概念' if s['name'] in cons else '—'
                L.append(f"| {s['name']} | **{_fmt(s.get('chg_1d'))}** | {stype} |")
        L.append("")
        # 分析文字
        if em_ind:
            ind_names = '、'.join(s['name'] for s in em_ind[:5])
            L.append(f"- **行业方向：** {ind_names}在恐慌中逆势走强，说明资金在这些方向上提前布局或护盘。")
        if em_con:
            con_names = '、'.join(s['name'] for s in em_con[:5])
            L.append(f"- **概念方向：** {con_names}资金活跃，可能成为反弹先锋。")
        if em_other:
            other_names = '、'.join(s['name'] for s in em_other[:5])
            L.append(f"- **其他：** {other_names}")
        chg_range = [s.get('chg_1d', 0) for s in (em_ind + em_con + em_other)]
        if chg_range:
            min_c, max_c = min(chg_range), max(chg_range)
            L.append(f"- **幅度：** {_fmt(min_c)} ~ {_fmt(max_c)}，{'整体偏强' if min_c > 2 else '温和走强'}")
        L.append("")
        L.append("> **策略：** 底部突起方向通常意味着资金提前布局，恐慌企稳后可重点关注这些方向的机会。")
        L.append("")

    # 个股逆势收红分析（从holdings里筛选）
    if holdings:
        up_stocks = [h for h in holdings if h.get('change_pct', 0) > 0]
        down_stocks = [h for h in holdings if h.get('change_pct', 0) <= 0]
        if up_stocks:
            L.append("### 个股逆势收红\n")
            L.append("| 股票 | 涨跌 | 方向 |")
            L.append("|:----|:----:|:----:|")
            for h in sorted(up_stocks, key=lambda x: x.get('change_pct', 0), reverse=True):
                L.append(f"| {h.get('name','')} | **{_fmt(h.get('change_pct'))}** | {h.get('structure','')} |")
            L.append("")
            L.append(f"> **核心：** {len(up_stocks)}/{len(holdings)}只持仓逆势收红，说明精选方向依然有资金承接。")
            L.append("")

        # 反弹梯队
        L.append("### 恐慌企稳后反弹梯队\n")
        tier1 = [h for h in holdings if h.get('change_pct', 0) > -1.5]
        tier2 = [h for h in holdings if -4 < h.get('change_pct', 0) <= -1.5]
        tier3 = [h for h in holdings if h.get('change_pct', 0) <= -4]
        if tier1:
            t1_names = '、'.join([h.get('name','') for h in tier1[:6]])
            L.append(f'<span class="tier-1">🟢 第一梯队</span> — 最抗跌  ')
            L.append(f"→ {t1_names}\n")
        if tier2:
            t2_names = '、'.join([h.get('name','') for h in tier2[:6]])
            L.append(f'<span class="tier-2">🟡 第二梯队</span> — 跟随反弹  ')
            L.append(f"→ {t2_names}\n")
        if tier3:
            t3_names = '、'.join([h.get('name','') for h in tier3[:6]])
            L.append(f'<span class="tier-3">🔴 第三梯队</span> — 反弹有限  ')
            L.append(f"→ {t3_names}\n")
        L.append("")
        L.append("> **核心逻辑：** 恐慌企稳后，最先涨的不会是跌最惨的，而是本来就最强、结构没坏的。")
        L.append("")

    L.append("---\n")

    # ═══ 四、持仓分析 ═══
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
            buy_point = h.get('buy_point', '')

            sig = '🟢' if chg is not None and chg > 0 else '🟡'
            L.append(f"### {sig} {name} ({code})")
            L.append("| 最新价 | 涨跌 | 结构 | 阶段 | 止损 |")
            L.append("|:-----:|:---:|:----:|:----:|:----:|")
            sl_str = f"{stop_loss}（{sl_pct:.1f}%）" if stop_loss else '—'
            L.append(f"| {price} | **{_fmt(chg)}** | {structure} | {stage} | {sl_str} |")
            if buy_point:
                L.append(f"- 买点：{buy_point}")
            if advice:
                sc = 'sig-buy' if signal == 'positive' else 'sig-hold' if signal == 'caution' else 'sig-sell'
                L.append(f'- 建议：<span class="{sc}">{advice}</span>')
            L.append("")
            L.append("---\n")
    else:
        L.append("暂无持仓数据。\n---\n")

    # ═══ 五、策略 ═══
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

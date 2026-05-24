const API = '/api/macro';

function toggleChart(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

async function loadMacro() {
    try {
        const res = await fetch(API);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        render(data);
    } catch (e) {
        document.getElementById('loading').innerHTML =
            `<div class="error-card">❌ 加载失败: ${e.message}</div>`;
    }
}

function render(data) {
    const updateEl = document.getElementById('updateTime');
    updateEl.textContent = '更新于 ' + (data.updated || '—');

    const indices = data.indices || {};
    const fx = data.fx || {};
    const cpi = data.cpi || [];

    const app = document.getElementById('loading');

    // ────── 1. A股大盘 ──────
    const aShares = ['上证指数', '深证成指', '创业板指', '沪深300', '中证全指', '科创50'];
    let aHtml = '';
    for (const name of aShares) {
        const idx = indices[name];
        if (!idx) continue;
        const cls = idx.change_pct >= 0 ? 'up' : 'down';
        const arrow = idx.change_pct >= 0 ? '▲' : '▼';
        aHtml += `<div class="index-card">
            <div class="name">${name}</div>
            <div class="price">${idx.price.toFixed(2)}</div>
            <div class="change ${cls}">${arrow} ${idx.change_pct >= 0 ? '+' : ''}${idx.change_pct.toFixed(2)}%</div>
            <div class="highlow">
                <span>高 <span class="hl-up">${idx.high ? idx.high.toFixed(2) : '-'}</span></span>
                <span>低 <span class="hl-down">${idx.low ? idx.low.toFixed(2) : '-'}</span></span>
            </div>
            <div class="time">${idx.time || ''}</div>
        </div>`;
    }

    // ────── 2. 全球市场 ──────
    const globals = ['标普500', '纳斯达克', '道琼斯'];
    let gHtml = '';
    for (const name of globals) {
        const idx = indices[name];
        if (!idx) continue;
        const cls = idx.change_pct >= 0 ? 'up' : 'down';
        const arrow = idx.change_pct >= 0 ? '▲' : '▼';
        gHtml += `<div class="index-card">
            <div class="name">${name}</div>
            <div class="price">${idx.price.toFixed(2)}</div>
            <div class="change ${cls}">${arrow} ${idx.change_pct >= 0 ? '+' : ''}${idx.change_pct.toFixed(2)}%</div>
            <div class="range">前收 ${idx.prev_close.toFixed(2)}</div>
            <div class="time">${idx.time || ''}</div>
        </div>`;
    }
    // 如果美股数据不在收盘时段可能为空
    if (!gHtml) gHtml = '<div class="error-card">美股非交易时段或无数据</div>';

    // ────── 3. CPI ──────
    let cpiHtml = '';
    if (cpi.length > 0) {
        const lastCpi = cpi[cpi.length - 1];
        const cpiVal = lastCpi.value;
        const cpiCls = cpiVal !== null && cpiVal !== undefined ? (cpiVal >= 0 ? 'cpi-positive' : 'cpi-negative') : '';
        const cpiSign = cpiVal !== null && cpiVal !== undefined ? (cpiVal >= 0 ? '▲' : '▼') : '—';

        cpiHtml = `<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
            <div class="risk-item">
                <div class="label">最新CPI</div>
                <div class="value ${cpiCls}">${cpiVal !== null && cpiVal !== undefined ? cpiVal.toFixed(1) + '%' : '—'}</div>
                <div class="sub">${lastCpi.date || ''}</div>
            </div>
            <div class="risk-item" style="flex:2;">
                <div class="label">近12个月走势</div>
                <div class="cpi-bars" style="display:flex;align-items:flex-end;gap:4px;height:60px;padding:8px 4px 0;">
                    ${cpi.map(d => {
                        const v = d.value;
                        if (v === null || v === undefined) return '<div style="flex:1;height:8px;background:#2a2a4e;border-radius:2px;" title="无数据"></div>';
                        const barH = Math.max(4, Math.abs(v) * 12);
                        const barBg = v >= 0 ? '#e94560' : '#4CAF50';
                        return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;">
                            <span style="font-size:9px;color:#888;margin-bottom:2px;">${v.toFixed(1)}</span>
                            <div style="width:100%;height:${barH}px;background:${barBg};border-radius:2px 2px 0 0;opacity:0.7;"></div>
                        </div>`;
                    }).join('')}
                </div>
                <div class="sub" style="display:flex;justify-content:space-between;font-size:9px;color:#555;padding:2px 4px 0;">
                    ${cpi.map(d => `<span>${(d.date || '').slice(-2)}</span>`).join('')}
                </div>
            </div>
        </div>`;

        cpiHtml += `<table class="cpi-table">
            <thead><tr><th>日期</th><th>今值(%)</th><th>预测值(%)</th><th>前值(%)</th></tr></thead>
            <tbody>
            ${cpi.slice().reverse().map(d => {
                const v = d.value;
                const f = d.forecast;
                const p = d.previous;
                const vCls = v !== null && v !== undefined ? (v >= 0 ? 'cpi-positive' : 'cpi-negative') : '';
                return `<tr>
                    <td>${d.date || '—'}</td>
                    <td class="${vCls}">${v !== null && v !== undefined ? v.toFixed(1) : '—'}</td>
                    <td>${f !== null && f !== undefined ? f.toFixed(1) : '—'}</td>
                    <td>${p !== null && p !== undefined ? p.toFixed(1) : '—'}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    } else {
        cpiHtml = '<div class="error-card">暂无CPI数据</div>';
    }

    // ────── 4. 汇率 ──────
    const fxPairs = [
        { key: '在岸人民币', cn: '美元/人民币', symbol: 'USDCNY' },
        { key: '欧元', cn: '欧元/人民币', symbol: 'EURCNY' },
        { key: '英镑', cn: '英镑/人民币', symbol: 'GBPCNY' },
        { key: '日元', cn: '100日元/人民币', symbol: 'JPYCNY' },
    ];
    let fxHtml = '';
    for (const pair of fxPairs) {
        let d = fx[pair.key];
        if (!d) {
            // 遍历找包含 key 的
            for (const [k, v] of Object.entries(fx)) {
                if (k.includes(pair.key)) { d = v; break; }
            }
        }
        if (!d) {
            fxHtml += `<div class="fx-card">
                <div class="left">
                    <div class="name">${pair.cn}</div>
                    <div class="pair">${pair.symbol}</div>
                </div>
                <div class="right">
                    <div class="price">—</div>
                    <div class="change" style="color:#666;">暂无数据</div>
                </div>
            </div>`;
            continue;
        }
        const cls = d.change_pct >= 0 ? 'up' : 'down';
        const arrow = d.change_pct >= 0 ? '▲' : '▼';
        fxHtml += `<div class="fx-card">
            <div class="left">
                <div class="name">${pair.cn}</div>
                <div class="pair">${pair.symbol}  ·  ${d.time || ''}</div>
            </div>
            <div class="right">
                <div class="price">${d.price.toFixed(4)}</div>
                <div class="change ${cls}">${arrow} ${d.change_pct >= 0 ? '+' : ''}${d.change_pct.toFixed(4)}%</div>
            </div>
        </div>`;
    }

    app.innerHTML = `
        <div class="section">
            <div class="section-title">📈 A股大盘 <span class="badge">${aShares.filter(n => indices[n]).length}/6</span></div>
            <div class="grid-4">${aHtml}</div>
        </div>

        <div class="section">
            <div class="section-title">🌎 全球市场 <span class="badge">美股</span></div>
            <div class="grid-3">${gHtml}</div>
        </div>

        <div class="section">
            <div class="section-title">📊 宏观数据 <span class="badge">CPI</span></div>
            ${cpiHtml}
        </div>`;

    // PPI
    const ppi = data.ppi || [];
    let ppiHtml = '';
    if (ppi.length > 0) {
        const lastPpi = ppi[0]; // newest first
        const ppiVal = lastPpi.value;
        const ppiCls = ppiVal !== null && ppiVal !== undefined ? (ppiVal >= 0 ? 'cpi-positive' : 'cpi-negative') : '';
        ppiHtml += `<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
            <div class="risk-item">
                <div class="label">最新PPI同比</div>
                <div class="value ${ppiCls}">${ppiVal !== null && ppiVal !== undefined ? ppiVal.toFixed(1) + '%' : '—'}</div>
                <div class="sub">${lastPpi.date || ''}</div>
            </div>
            <div class="risk-item" style="flex:2;">
                <div class="label">近12个月走势</div>
                <div class="cpi-bars" style="display:flex;align-items:flex-end;gap:4px;height:60px;padding:8px 4px 0;">
                    ${ppi.slice().reverse().map(d => {
                        const v = d.value;
                        if (v === null || v === undefined) return '<div style="flex:1;height:8px;background:#2a2a4e;border-radius:2px;" title="无数据"></div>';
                        const barH = Math.max(4, Math.abs(v) * 8);
                        const barBg = v >= 0 ? '#e94560' : '#4CAF50';
                        return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;">
                            <span style="font-size:9px;color:#888;margin-bottom:2px;">${v.toFixed(1)}</span>
                            <div style="width:100%;height:${barH}px;background:${barBg};border-radius:2px 2px 0 0;opacity:0.7;"></div>
                        </div>`;
                    }).join('')}
                </div>
                <div class="sub" style="display:flex;justify-content:space-between;font-size:9px;color:#555;padding:2px 4px 0;">
                    ${ppi.slice().reverse().map(d => `<span>${(d.date || '').slice(5, 7)}月</span>`).join('')}
                </div>
            </div>
        </div>`;
        ppiHtml += `<table class="cpi-table">
            <thead><tr><th>月份</th><th>同比增长(%)</th></tr></thead>
            <tbody>
            ${ppi.map(d => {
                const v = d.value;
                const vCls = v !== null && v !== undefined ? (v >= 0 ? 'cpi-positive' : 'cpi-negative') : '';
                return `<tr>
                    <td>${d.date || '—'}</td>
                    <td class="${vCls}">${v !== null && v !== undefined ? v.toFixed(1) : '—'}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    } else {
        ppiHtml = '<div class="error-card">暂无PPI数据</div>';
    }

    app.innerHTML += `
        <div class="section">
            <div class="section-title">📊 宏观数据 <span class="badge">PPI</span></div>
            ${ppiHtml}
        </div>

        <div class="section">
            <div class="section-title">💱 汇率 <span class="badge">人民币中间价</span></div>
            <div class="grid-2">${fxHtml}</div>
        </div>

        <div style="text-align:center;padding:20px;color:#333;font-size:12px;">
            数据来源: 腾讯财经 · 新浪财经 · akshare | 自动刷新
        </div>
    `;

    // 自动刷新
    setTimeout(loadMacro, 30000);
}

loadMacro();
/* 3L 个股分析 + 回测 JS */
const API_BASE = 'http://43.136.177.133:8080';
let lastCode = '';

function getEl(id) { return document.getElementById(id); }

/* ===== 个股分析 ===== */
function search() {
    const q = getEl('stockInput').value.trim();
    if (!q) return;
    const btn = getEl('searchBtn');
    btn.disabled = true; btn.textContent = '分析中...';
    getEl('resultArea').innerHTML = '<div class="loading"><div class="spinner"></div><p>分析中...</p></div>';

    fetch(`${API_BASE}/api/stock-analysis?q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(d => {
            btn.disabled = false; btn.textContent = '分析';
            if (d.error) {
                getEl('resultArea').innerHTML = `<div class="error-box">${d.error}</div>`;
                return;
            }
            lastCode = d.code;
            renderAnalysis(d);
        })
        .catch(e => {
            btn.disabled = false; btn.textContent = '分析';
            getEl('resultArea').innerHTML = `<div class="error-box">请求失败: ${e.message}</div>`;
        });
}

function renderAnalysis(d) {
    const signalClass = d.signal === 'buy' ? 'buy' : d.signal === 'hold' ? 'hold' : d.signal === 'warn' ? 'warn' : 'none';
    const signalText = d.signal === 'buy' ? '🟢 买点信号' : d.signal === 'hold' ? '🟡 持有观察' : d.signal === 'warn' ? '🔴 不宜操作' : '⚪ 无信号';
    const changeClass = d.change >= 0 ? 'up' : 'down';
    const sysLabel = d.trading_system === 'trend' ? '📈 趋势交易' : '📊 3L系统';

    let html = `<div class="result-card">
        <div class="result-header">
            <div>
                <span class="stock-name">${d.name}</span>
                <span class="stock-code">${d.code}</span>
                <span class="stock-direction">${d.direction || ''}</span>
            </div>
            <div style="text-align:right">
                <div class="stock-price ${changeClass}">${d.price} <span style="font-size:14px">${d.change >= 0 ? '+' : ''}${d.change}%</span></div>
                <div style="color:#666;font-size:11px;margin-top:2px">${d.date}</div>
            </div>
        </div>
        <div class="signal-bar ${signalClass}">${signalText}</div>
        <div class="tags">
            <span class="tag ${sysLabel.includes('趋势') ? 'orange' : 'blue'}">${sysLabel}</span>
            <span class="tag ${d.structure === '上涨趋势' ? 'green' : d.structure === '下跌趋势' ? 'red' : 'yellow'}">${d.structure || '--'}</span>
            <span class="tag gray">阶段${d.stage || '?'}</span>
            ${d.is_watchlist ? '<span class="tag purple">自选</span>' : ''}
            ${d.trend_stock ? '<span class="tag orange">趋势股</span>' : ''}
            ${d.buy_point ? `<span class="tag green">${d.buy_point}</span>` : ''}
            ${d.mainline_level ? `<span class="tag ${d.mainline_level === '主线' ? 'red' : d.mainline_level === '次级主线' ? 'yellow' : 'gray'}">${d.mainline_level}</span>` : ''}
        </div>
        <div class="info-grid">
            <div class="info-item"><div class="l">EMA5</div><div class="v normal">${d.ema5 ?? '--'}</div></div>
            <div class="info-item"><div class="l">EMA10</div><div class="v normal">${d.ema10 ?? '--'}</div></div>
            <div class="info-item"><div class="l">EMA20</div><div class="v normal">${d.ema20 ?? '--'}</div></div>
            <div class="info-item"><div class="l">乖离率(EMA5)</div><div class="v ${Math.abs(d.deviation_pct) < 3 ? 'good' : 'warn'}">${d.deviation_pct}%</div></div>
            <div class="info-item"><div class="l">量比</div><div class="v ${d.vol_ratio > 1.1 ? 'good' : 'normal'}">${d.vol_ratio}</div></div>
            <div class="info-item"><div class="l">止损位</div><div class="v bad">${d.stop_loss ?? '--'} ${d.stop_loss_pct ? '(' + d.stop_loss_pct + '%)' : ''}</div></div>
            <div class="info-item"><div class="l">盈亏比</div><div class="v ${d.risk_reward_ratio && d.risk_reward_ratio > 2 ? 'good' : 'warn'}">${d.risk_reward_ratio ?? '--'}</div></div>
            <div class="info-item"><div class="l">历史胜率</div><div class="v ${d.success_rate && d.success_rate > 50 ? 'good' : 'warn'}">${d.success_rate ?? '--'}${d.success_rate ? '%' : ''}</div></div>
        </div>`;

    if (d.buy_detail) {
        html += `<div class="detail-section"><h3>📋 买点详情</h3><table class="detail-table">`;
        for (const [k, v] of Object.entries(d.buy_detail)) {
            html += `<tr><td>${k}</td><td>${JSON.stringify(v)}</td></tr>`;
        }
        html += `</table></div>`;
    }

    if (d.trading_reason) {
        html += `<div class="detail-section"><h3>💡 系统判定</h3><div style="color:#888;font-size:13px;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">${d.trading_reason}</div></div>`;
    }

    if (d.has_chart) {
        html += `<div class="chart-section"><details><summary>📈 查看K线图</summary><object type="image/svg+xml" data="/review_charts/${d.code}.svg">K线图</object></details></div>`;
    }

    html += `</div>`;
    getEl('resultArea').innerHTML = html;
}

/* ===== 回测 ===== */
function runBacktest() {
    const code = lastCode || getEl('stockInput').value.trim();
    if (!code) { alert('请先输入股票代码或名称'); return; }

    const btn = getEl('btBtn');
    btn.disabled = true; btn.textContent = '回测中...';
    const area = getEl('btResultArea');
    area.innerHTML = '<div class="loading"><div class="spinner"></div><p>回测中（60天数据模拟）...</p></div>';

    fetch(`${API_BASE}/api/stock-backtest?code=${encodeURIComponent(code)}&days=60`)
        .then(r => r.json())
        .then(d => {
            btn.disabled = false; btn.textContent = '📊 回测';
            if (d.error) {
                area.innerHTML = `<div class="error-box">${d.error}</div>`;
                return;
            }
            renderBacktest(d, area);
        })
        .catch(e => {
            btn.disabled = false; btn.textContent = '📊 回测';
            area.innerHTML = `<div class="error-box">请求失败: ${e.message}</div>`;
        });
}

function renderBacktest(d, area) {
    const stats = `<div class="bt-summary">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-size:16px;font-weight:700;color:#4ecdc4;">${d.name} (${d.code})</div>
            <div style="font-size:12px;color:#888;">${d.direction} · 回测60天</div>
        </div>
        <div class="bt-stats">
            <div class="bt-stat"><div class="l">累计收益</div><div class="v ${d.cumulative_return >= 0 ? 'good' : 'bad'}">${d.cumulative_return >= 0 ? '+' : ''}${d.cumulative_return}%</div></div>
            <div class="bt-stat"><div class="l">信号数</div><div class="v normal">${d.total}</div></div>
            <div class="bt-stat"><div class="l">胜率</div><div class="v ${d.win_rate >= 50 ? 'good' : 'bad'}">${d.win_rate}%</div></div>
            <div class="bt-stat"><div class="l">平均盈利</div><div class="v good">${d.avg_win ? '+' + d.avg_win + '%' : '--'}</div></div>
            <div class="bt-stat"><div class="l">平均亏损</div><div class="v bad">${d.avg_loss ? d.avg_loss + '%' : '--'}</div></div>
        </div>`;

    let table = '';
    if (d.signals && d.signals.length > 0) {
        table = `<table class="bt-table">
            <thead><tr><th>#</th><th>日期</th><th>系统</th><th>类型</th><th>入场</th><th>出场</th><th>收益</th><th>持有</th><th>退出原因</th></tr></thead><tbody>`;
        d.signals.forEach(s => {
            const gainClass = s.gain >= 0 ? 'good' : 'bad';
            const sysTag = s.trading_system === 'trend' ? '趋势' : '3L';
            table += `<tr>
                <td>${s.n}</td>
                <td>${s.date ? s.date.slice(5) : '--'}</td>
                <td><span style="color:${sysTag === '趋势' ? '#ff9800' : '#2196f3'}">${sysTag}</span></td>
                <td>${s.type || '--'}</td>
                <td>${s.entry || '--'}</td>
                <td>${s.exit || '--'}</td>
                <td class="${gainClass}">${s.gain >= 0 ? '+' : ''}${s.gain}%</td>
                <td>${s.days || 0}d</td>
                <td style="color:#888;font-size:11px;">${s.exit_reason || '--'}</td>
            </tr>`;
        });
        table += '</tbody></table>';
    }

    let chart = '';
    if (d.has_chart && d.chart_svg) {
        chart = `<div class="bt-chart"><object type="image/svg+xml" data="${d.chart_svg}" style="width:100%;border-radius:8px;">回测图表</object></div>`;
    }

    area.innerHTML = stats + table + chart;
}

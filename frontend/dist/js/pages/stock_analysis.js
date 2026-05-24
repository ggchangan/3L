// 图表切换（signalStockCard调用）— toggleChart已移至stock_card.js

async function search() {
    const q = document.getElementById('stockInput').value.trim();
    if (!q) return;
    
    const area = document.getElementById('resultArea');
    const btn = document.getElementById('searchBtn');
    btn.disabled = true;
    area.innerHTML = '<div class="loading"><div class="spinner"></div>正在分析...</div>';
    
    try {
        const res = await fetch(`/api/stock-analysis?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        
        if (data.error) {
            area.innerHTML = `<div class="error-box">❌ ${data.error}</div>`;
            return;
        }
        
        area.innerHTML = renderResult(data);
    } catch (e) {
        area.innerHTML = `<div class="error-box">❌ 请求失败: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
    }
}

function renderResult(d) {
    // 统一卡片（用公共signalStockCard）
    const card = function(){ 
        const d2 = Object.assign({}, d, {
            sector: d.direction,
            change: d.change||0,
            signal: d.signal || 'hold',
            // 扁平化trend_buy嵌套对象 → signalStockCard期望的字段名
            trend_buy_type: d.trend_buy?.buy_type,
            trend_bias: d.trend_buy?.bias5,
        }); 
        return signalStockCard(d2, 0); 
    }();
    
    return `${card}`;
}

async function runBacktest() {
    const q = document.getElementById('stockInput').value.trim();
    if (!q) return;
    const area = document.getElementById('btResultArea');
    area.innerHTML = '<div class="loading"><div class="spinner"></div>正在跑回测...</div>';
    try {
        const res = await fetch(`/api/stock-backtest?code=${encodeURIComponent(q)}&days=60`);
        const d = await res.json();
        if (d.error) { area.innerHTML = `<div class="error-box">❌ ${d.error}</div>`; return; }
        let tableRows = '';
        for (const s of d.signals) {
            const clr = s.gain > 0 ? '#4ecdc4' : '#e94560';
            const sysLabel = s.trading_system === 'trend' ? '<span class="tag" style="background:#4ecdc4;color:#000;">趋势</span>' : '<span class="tag" style="background:#e94560;color:#fff;">3L</span>';
            tableRows += `<tr>
                <td>${s.n}</td><td>${sysLabel}</td><td>${s.date ? s.date.substring(5,10) : '--'}</td>
                <td><span class="tag ${s.type.includes('突破') ? 'red' : s.type.includes('BIAS') ? 'green' : 'yellow'}">${s.type}</span></td>
                <td>${s.entry?.toFixed(2) || '--'}</td>
                <td>${s.exit_date ? s.exit_date.substring(5,10) : '--'}</td>
                <td>${s.exit?.toFixed(2) || '--'}</td>
                <td>${s.days || '--'}天</td>
                <td style="color:${clr};font-weight:600">${s.gain > 0 ? '✅' : '❌'} ${s.gain >= 0 ? '+' : ''}${s.gain}%</td>
            </tr>`;
        }
        area.innerHTML = `
        <div class="bt-summary">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div><span style="font-size:18px;font-weight:700;color:#4ecdc4">${d.name}</span>
                <span style="color:#888;font-size:13px;margin-left:8px">${d.code}</span></div>
                <span style="color:#666;font-size:12px">60天回测</span>
            </div>
            <div class="bt-stats">
                <div class="bt-stat"><div class="l">信号</div><div class="v">${d.total}笔</div></div>
                <div class="bt-stat"><div class="l">盈利</div><div class="v" style="color:#4ecdc4">${d.wins}</div></div>
                <div class="bt-stat"><div class="l">亏损</div><div class="v" style="color:#e94560">${d.losses}</div></div>
                <div class="bt-stat"><div class="l">胜率</div><div class="v">${d.win_rate}%</div></div>
                <div class="bt-stat"><div class="l">累计收益</div><div class="v" style="color:${d.cumulative_return > 0 ? '#4ecdc4' : '#e94560'}">${d.cumulative_return > 0 ? '+' : ''}${d.cumulative_return}%</div></div>
                <div class="bt-stat"><div class="l">均盈/亏</div><div class="v" style="font-size:14px"><span style="color:#4ecdc4">+${d.avg_win}%</span> / <span style="color:#e94560">${d.avg_loss}%</span></div></div>
            </div>
            ${d.has_chart ? `<details class="bt-chart" open><summary style="cursor:pointer;color:#4ecdc4;font-size:14px;margin-bottom:8px">📊 K线图（含买卖标注）</summary>
            <object data="${d.chart_svg}?t=${Date.now()}" type="image/svg+xml" style="width:100%;border-radius:8px"></object></details>` : ''}
            <h3 style="color:#4ecdc4;font-size:14px;margin:16px 0 8px">📋 交易明细</h3>
            <table class="bt-table"><tr><th>#</th><th>系统</th><th>入场日</th><th>类型</th><th>入场价</th><th>出场日</th><th>出场价</th><th>持有</th><th>盈亏</th></tr>
            ${tableRows}
            </table>
        </div>`;
    } catch(e) {
        area.innerHTML = `<div class="error-box">❌ 回测失败: ${e.message}</div>`;
    }
}

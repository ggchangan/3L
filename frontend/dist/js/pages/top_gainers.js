const API = '/api/top-gainers';

// 初始化日期（最新交易日）
const today = new Date();
const defaultDate = today.toISOString().split('T')[0];
document.getElementById('datePicker').value = defaultDate;

// Chart toggle (required by signalStockCard)
const PIE_COLORS = [
    '#e94560', '#2196f3', '#4CAF50', '#ff9800', '#a855f7',
    '#00bcd4', '#ff5722', '#8bc34a', '#e91e63', '#3f51b5',
    '#009688', '#ffeb3b', '#9c27b0', '#795548', '#607d8b',
    '#cddc39', '#03a9f4', '#f44336', '#4caf50', '#ffc107',
];

function renderPie(pie) {
    if (!pie || pie.length === 0) {
        document.getElementById('pieSection').style.display = 'none';
        return;
    }
    document.getElementById('pieSection').style.display = 'block';
    const total = pie.reduce((s, d) => s + d.count, 0);
    const svgW = 280, svgH = 280, cx = 140, cy = 140, r = 110;

    // SVG饼图
    let startAngle = -90;
    let paths = '';
    let legendHtml = '';

    pie.forEach((d, i) => {
        const angle = (d.count / total) * 360;
        const endAngle = startAngle + angle;
        const color = PIE_COLORS[i % PIE_COLORS.length];

        // 饼图扇形
        const sRad = startAngle * Math.PI / 180;
        const eRad = endAngle * Math.PI / 180;
        const x1 = cx + r * Math.cos(sRad);
        const y1 = cy + r * Math.sin(sRad);
        const x2 = cx + r * Math.cos(eRad);
        const y2 = cy + r * Math.sin(eRad);
        const largeArc = angle > 180 ? 1 : 0;
        const path = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
        paths += `<path d="${path}" fill="${color}" stroke="#1a1a2e" stroke-width="1.5" opacity="0.9"/>`;

        // 标签线 + 百分比文字
        const labelAngle = (startAngle + endAngle) / 2;
        const lRad = labelAngle * Math.PI / 180;
        const textR = r * 0.65;
        const tx = cx + textR * Math.cos(lRad);
        const ty = cy + textR * Math.sin(lRad);
        if (d.pct >= 5) {
            paths += `<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central" font-size="11" fill="#fff" font-weight="600">${d.pct.toFixed(0)}%</text>`;
        }

        // 图例
        legendHtml += `<div class="legend-item">
            <div class="legend-dot" style="background:${color}"></div>
            <span class="legend-name">${d.name}</span>
            <span class="legend-count">${d.count}只</span>
            <span class="legend-pct">${d.pct}%</span>
        </div>`;

        startAngle = endAngle;
    });

    // 中间空心圆（中心文字）
    paths += `<circle cx="${cx}" cy="${cy}" r="45" fill="#0f0f1a" stroke="#2a2a4e" stroke-width="1"/>
        <text x="${cx}" y="${cy - 5}" text-anchor="middle" font-size="22" font-weight="700" fill="#e94560">${total}</text>
        <text x="${cx}" y="${cy + 14}" text-anchor="middle" font-size="11" fill="#888">只个股</text>`;

    document.getElementById('pieContainer').innerHTML = `<svg width="100%" height="100%" viewBox="0 0 ${svgW} ${svgH}" style="max-width:280px;max-height:280px;">${paths}</svg>`;
    document.getElementById('pieLegend').innerHTML = legendHtml;
}

async function loadData() {
    const date = document.getElementById('datePicker').value;
    const limit = document.getElementById('limitSelect').value;
    const btn = document.getElementById('queryBtn');
    const hint = document.getElementById('loadingHint');

    btn.disabled = true;
    hint.textContent = '加载中...';

    try {
        const res = await fetch(`${API}?date=${date}&limit=${limit}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        // 摘要
        const summaryArea = document.getElementById('summaryArea');
        summaryArea.style.display = 'flex';
        const avgGain = data.stocks.length > 0
            ? (data.stocks.reduce((s, st) => s + st.gain_30d, 0) / data.stocks.length).toFixed(1)
            : 0;
        const maxGain = data.stocks.length > 0 ? data.stocks[0].gain_30d.toFixed(1) : 0;
        summaryArea.innerHTML = `
            <div class="summary-item"><div class="label">截止日期</div><div class="value" style="font-size:16px;color:#e0e0e0;">${date}</div></div>
            <div class="summary-item"><div class="label">展示个股</div><div class="value" style="color:#e94560;">${data.stocks.length}/${data.total}</div><div class="sub">总符合条件的个股</div></div>
            <div class="summary-item"><div class="label">平均涨幅</div><div class="value" style="color:${avgGain >= 0 ? '#e94560' : '#4CAF50'};">${avgGain}%</div><div class="sub">30日</div></div>
            <div class="summary-item"><div class="label">最高涨幅</div><div class="value" style="color:#e94560;">${maxGain}%</div><div class="sub">${data.stocks[0]?.name || ''}</div></div>
        `;

        // 饼图
        renderPie(data.pie);

        // 股票列表
        const list = document.getElementById('stockList');
        if (data.stocks.length === 0) {
            list.innerHTML = '<div class="error-card">该日期无数据</div>';
            btn.disabled = false;
            hint.textContent = '';
            return;
        }

        // 按涨幅排序（API已排好）
        let html = '<div class="stock-grid">';
        data.stocks.forEach((s, i) => {
            const rankClass = i === 0 ? 'top1' : i < 5 ? 'top5' : i < 10 ? 'top10' : 'normal';
            const rankLabel = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`;

            // 映射字段给signalStockCard
            const cardData = Object.assign({}, s, {
                signal: 'hold',  // 涨幅榜默认持有状态，不显示"--"
                change: s.change || 0,
                flags: '',
                mainline_level: '',
                stop_loss: null,
                stop_loss_pct: null,
            });

            let card = signalStockCard(cardData, i);
            // 在名称后加排名标签
            const nameMatch = card.match(/(<div class="name">)([^<]*)(<\/div>)/);
            if (nameMatch) {
                const rankTag = `<span class="gain-rank ${rankClass}">${rankLabel} ${s.gain_30d.toFixed(1)}%</span>`;
                const newName = nameMatch[1] + nameMatch[2] + rankTag + nameMatch[3];
                card = card.replace(nameMatch[0], newName);
            }

            // 在第一个.row之前插入"30日涨幅"字段
            const gainArrow = s.gain_30d >= 0 ? '▲' : '▼';
            const gainField = `<div class="field"><span class="l">30日涨幅:</span><span class="v" style="color:${s.gain_30d >= 0 ? '#e94560' : '#4CAF50'};font-size:14px;font-weight:700;">${gainArrow} ${s.gain_30d >= 0 ? '+' : ''}${s.gain_30d.toFixed(2)}%</span></div>`;
            card = card.replace('<div class="row" style="margin-top:6px;">', gainField + '<div class="row" style="margin-top:6px;">');

            html += card;
        });
        html += '</div>';
        list.innerHTML = html;

        hint.textContent = `共 ${data.stocks.length} 只`;
    } catch (e) {
        document.getElementById('stockList').innerHTML = `<div class="error-card">❌ 加载失败: ${e.message}</div>`;
    }

    btn.disabled = false;
}

// 自动加载
loadData();
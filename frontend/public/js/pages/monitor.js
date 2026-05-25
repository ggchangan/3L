const REFRESH_INTERVAL = 30000; // 30秒刷新一次
let volumeChart = null;

// ====== 格式化 ======
function fmtVol(v) {
    if (!v) return '0';
    if (v >= 100000000) return (v/100000000).toFixed(1) + '亿';
    if (v >= 10000) return (v/10000).toFixed(0) + '万';
    return v.toLocaleString();
}
// 成交额(元) → 亿元
function fmtAmountYuan(v) {
    if (!v) return '0';
    return (v / 100000000).toFixed(1) + '亿';
}

// ====== 更新行情 ======
function updateQuote(data) {
    const price = document.getElementById('qPrice');
    const chg = document.getElementById('qChange');
    const vol = document.getElementById('qVolume');
    const ratio = document.getElementById('qVolRatio');

    price.textContent = data.current_price ? data.current_price.toFixed(2) : '--';
    price.className = 'value' + ((data.current_change || 0) >= 0 ? ' up' : ' down');
    chg.textContent = data.current_change ? `${data.current_change >= 0 ? '+' : ''}${data.current_change.toFixed(2)}%` : '--';
    chg.className = 'value' + ((data.current_change || 0) >= 0 ? ' up' : ' down');
    vol.textContent = fmtAmountYuan(data.today_amount_yuan);
    if (data.amount_ratio) {
        ratio.textContent = data.amount_ratio.toFixed(1) + '%';
        ratio.className = 'value' + (data.amount_ratio >= 100 ? ' up' : ' down');
    }
}

// ====== 成交额图表（两日叠加） ======
function updateVolumeChart(data) {
    const todayCurve = data.today_curve || [];
    const isEstimated = data.yesterday_is_estimated || false;

    // 使用今日分钟数据的时间作为X轴标签
    const labels = todayCurve.map(p => p.time);
    const todayAmounts = todayCurve.map(p => p.amount || 0);

    // 底部统计
    document.getElementById('todayVolLabel').textContent = fmtAmountYuan(data.today_amount_yuan);
    const yAmt = data.yesterday_amount_yuan || 0;
    if (yAmt > 0) {
        document.getElementById('yesterdayVolLabel').textContent = fmtAmountYuan(yAmt);
        document.getElementById('yesterdayDateLabel').textContent = `(${data.yesterday_date})${isEstimated ? ' *估算' : ''}`;
    } else {
        document.getElementById('yesterdayVolLabel').textContent = '待积累';
        document.getElementById('yesterdayDateLabel').textContent = '';
    }
    // 同比百分比
    const ratioEl = document.getElementById('volRatioLabel');
    if (data.amount_ratio !== null && data.amount_ratio !== undefined) {
        const pct = data.amount_ratio;
        ratioEl.textContent = `较昨日 ${pct}%`;
        ratioEl.style.color = pct > 100 ? '#e94560' : '#4ecdc4';
    } else {
        ratioEl.textContent = '';
    }

    if (volumeChart) {
        volumeChart.data.labels = labels;
        volumeChart.data.datasets[0].data = todayAmounts;
        volumeChart.update('none');
        return;
    }

    const ctx = document.getElementById('volumeChart').getContext('2d');
    volumeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: `今日(${data.current_time ? data.current_time.slice(0,10) : ''})`,
                data: todayAmounts,
                borderColor: '#ffd700',
                backgroundColor: 'rgba(255, 215, 0, 0.05)',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#a0a0b0', font: { size: 10 }, boxWidth: 12, padding: 8 }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.datasetIndex === 0)
                                return `今日: ${fmtAmountYuan(ctx.raw)}`;
                            return `昨日: ${fmtAmountYuan(ctx.raw)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: { 
                        color: '#555', maxTicksLimit: 10, font: { size: 9 },
                        callback: v => labels[v] ? labels[v] : ''
                    },
                    grid: { display: false }
                },
                y: {
                    display: true,
                    ticks: { color: '#555', font: { size: 9 }, callback: v => fmtAmountYuan(v) },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                }
            },
            animation: { duration: 0 }
        }
    });
}

// ====== 全局数据缓存 ======
let signalDataCache = {};
let industryBoardsCache = [];
let industryMapCache = {};

// ====== 大盘观测切换 ======
function toggleIndexChart() {
    const panel = document.getElementById('indexChartPanel');
    const obj = document.getElementById('indexChartObj');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        if (obj && panel.style.display === 'block') {
            obj.data = '/pub/charts/zzqz_v2.svg?t=' + Date.now();
        }
    }
}

function toggleEventPlaceholder() {
    const panel = document.getElementById('eventPlaceholderPanel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

function toggleExternal() {
    const body = document.getElementById('externalBody');
    const toggle = document.getElementById('externalToggle');
    if (!body || !toggle) return;
    if (body.style.display === 'none') {
        body.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        body.style.display = 'none';
        toggle.textContent = '▶';
    }
}

// ====== 板块监测（tab切换：今日涨幅/昨日涨幅 + 每行关键图） ======
let sectorDataCache = null;

function loadTopSectors() {
    fetch('/api/monitor/sectors')
        .then(r => r.json())
        .then(data => {
            sectorDataCache = data;
            renderTopSectors(data);
        })
        .catch(() => {});
}

function renderTopSectors(data) {
    const area = document.getElementById('topSectorsArea');
    if (!data || !data.today_top5 || data.today_top5.length === 0) {
        area.innerHTML = '<div class="empty">暂无数据</div>';
        return;
    }

    const todayList = data.today_top5 || [];
    const yesterdayList = data.chg5d_top5 || [];

    let html = '';

    // Tab 按钮
    html += '<div style="display:flex;gap:0;margin-bottom:12px;border-bottom:1px solid #2a2a4a;">';
    html += '<div class="sector-tab active" data-tab="today" onclick="switchSectorTab(\'today\')" style="padding:6px 18px;cursor:pointer;font-size:13px;color:#ffd700;border-bottom:2px solid #ffd700;font-weight:bold;">🔥 今日涨幅</div>';
    html += '<div class="sector-tab" data-tab="chg5d" onclick="switchSectorTab(\'chg5d\')" style="padding:6px 18px;cursor:pointer;font-size:13px;color:#888;border-bottom:2px solid transparent;">📈 5日涨幅</div>';
    html += '</div>';

    // Tab 内容：今日涨幅
    html += '<div class="sector-panel" id="sectorTabToday" style="display:block;">';
    html += '<table class="signal-table">';
    html += '<tr><th>#</th><th>板块</th><th>涨幅</th><th>结构</th><th>阶段</th><th style="width:30px;"></th></tr>';
    todayList.forEach((b, i) => {
        const c = parseFloat(b.chg || 0);
        const safeName = b.name.replace(/'/g, "\\'");
        html += `<tr>
            <td style="color:#555;width:20px;">${i+1}</td>
            <td style="font-weight:bold;">${b.name || ''}</td>
            <td style="color:${c>=0?'#ff4444':'#44aa44'}">${c>=0?'+':''}${c.toFixed(2)}%</td>
            <td style="font-size:11px;color:#aaa;">${b.structure || '-'}</td>
            <td style="font-size:11px;">${b.phase || '-'}</td>
            <td style="text-align:right;"><span onclick="toggleSectorChart('today_chart_${i}','${safeName}')" style="cursor:pointer;font-size:14px;color:#4ecdc4;" title="查看K线">📊</span></td>
        </tr>`;
        html += `<tr id="today_chart_${i}" style="display:none;"><td colspan="6" style="padding:0;"><object type="image/svg+xml" style="width:100%;height:400px;border-radius:6px;"></object></td></tr>`;
    });
    html += '</table></div>';

    // Tab 内容：5日涨幅
    html += '<div class="sector-panel" id="sectorTabChg5d" style="display:none;">';
    if (yesterdayList.length > 0) {
        html += '<table class="signal-table">';
        html += '<tr><th>#</th><th>板块</th><th>涨幅</th><th>结构</th><th>阶段</th><th style="width:30px;"></th></tr>';
        yesterdayList.forEach((b, i) => {
            const c = parseFloat(b.chg || 0);
            const safeName = b.name.replace(/'/g, "\\'");
            html += `<tr>
                <td style="color:#555;width:20px;">${i+1}</td>
                <td style="font-weight:bold;">${b.name || ''}</td>
                <td style="color:${c>=0?'#ff4444':'#44aa44'}">${c>=0?'+':''}${c.toFixed(2)}%</td>
                <td style="font-size:11px;color:#aaa;">${b.structure || '-'}</td>
                <td style="font-size:11px;">${b.phase || '-'}</td>
                <td style="text-align:right;"><span onclick="toggleSectorChart('chg5d_chart_${i}','${safeName}')" style="cursor:pointer;font-size:14px;color:#4ecdc4;" title="查看K线">📊</span></td>
            </tr>`;
            html += `<tr id="chg5d_chart_${i}" style="display:none;"><td colspan="6" style="padding:0;"><object type="image/svg+xml" style="width:100%;height:400px;border-radius:6px;"></object></td></tr>`;
        });
        html += '</table>';
    } else {
        html += '<div class="empty">数据积累中...</div>';
    }
    html += '</div>';

    area.innerHTML = html;
}

// Tab切换
function switchSectorTab(tab) {
    document.querySelectorAll('.sector-tab').forEach(el => {
        if (el.dataset.tab === tab) {
            el.style.color = '#ffd700';
            el.style.borderBottom = '2px solid #ffd700';
            el.style.fontWeight = 'bold';
        } else {
            el.style.color = '#888';
            el.style.borderBottom = '2px solid transparent';
            el.style.fontWeight = 'normal';
        }
    });
    document.getElementById('sectorTabToday').style.display = tab === 'today' ? 'block' : 'none';
    document.getElementById('sectorTabChg5d').style.display = tab === 'chg5d' ? 'block' : 'none';
}

// 板块关键点图切换
function toggleSectorChart(id, name) {
    const tr = document.getElementById(id);
    if (!tr) return;
    const obj = tr.querySelector('object');
    if (tr.style.display === 'none') {
        tr.style.display = 'table-row';
        obj.data = '/api/sector-chart?name=' + encodeURIComponent(name) + '&t=' + Date.now();
    } else {
        tr.style.display = 'none';
        // 不清空data，保持缓存，下次展开直接显示
    }
}

// ====== 加载行业映射表 ======
function loadIndustryMap() {
    return fetch('/api/industry-map')
        .then(r => r.json())
        .then(data => {
            industryMapCache = data || {};
        })
        .catch(() => {});
}

// ====== 买点信号（按方向分组+Tab切换） ======
let signalGroups = {};      // {方向: [signals]}
let signalGroupNames = [];  // 排序后的方向列表
let activeSignalDir = '';   // 当前活跃方向
let signalDirPages = {};    // {方向: 当前页码}
const SIGNAL_PER_PAGE = 10;

function updateBuySignals(data) {
    signalDataCache = data;
    const signals = data.signals || [];
    if (signals.length === 0) {
        document.getElementById('buySignalsArea').innerHTML = '<div class="empty">暂无买点信号</div>';
        return;
    }

    // 构建板块涨幅映射 {板块名: 涨幅}
    const sectorChg = {};
    industryBoardsCache.forEach(b => {
        const name = b['板块'] || b['名称'] || '';
        sectorChg[name] = parseFloat(b['涨跌幅'] || 0);
    });

    // 为每个信号查找对应板块及涨幅
    const enriched = signals.map(s => {
        const code = s.code;
        const cleanCode = code.replace(/^sh|^sz|^SH|^SZ/, '');
        // 查行业映射表
        const mapEntry = industryMapCache[cleanCode] || industryMapCache[code] || {};
        const sectorName = mapEntry.ths_industry || '';
        const sectorChgVal = sectorChg[sectorName] || 0;
        return { ...s, sector: sectorName, sector_chg: sectorChgVal, _code: cleanCode };
    });

    // 按方向分组
    signalGroups = {};
    enriched.forEach(s => {
        const dir = s.direction || '其他';
        if (!signalGroups[dir]) signalGroups[dir] = [];
        signalGroups[dir].push(s);
    });
    signalGroupNames = Object.keys(signalGroups).sort();

    // 初始化Tab状态
    if (!activeSignalDir || !signalGroups[activeSignalDir]) {
        activeSignalDir = signalGroupNames[0];
    }
    if (signalDirPages[activeSignalDir] === undefined) signalDirPages[activeSignalDir] = 1;

    signalDataCache._enriched = enriched;
    renderBuySignalsPage();
}

function renderBuySignalsPage() {
    const directions = signalGroupNames;
    if (directions.length === 0) {
        document.getElementById('buySignalsArea').innerHTML = '<div class="empty">暂无买点信号</div>';
        return;
    }

    // 方向颜色（同复盘页面）
    const dirColors = {
        '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
        '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
        'AI应用': '#00BCD4', '商业航天': '#FF5722',
    };

    let html = '';

    // Tab 按钮
    html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px;border-bottom:1px solid #333;padding-bottom:6px;">';
    directions.forEach(dir => {
        const active = dir === activeSignalDir;
        const color = dirColors[dir] || '#888';
        const count = signalGroups[dir].length;
        html += `<span style="cursor:pointer;padding:4px 12px;font-size:12px;border-radius:12px;display:inline-block;${active?`background:${color};color:#fff;`:`color:${color};background:rgba(255,255,255,0.05);`}" onclick="switchSignalDir('${dir}')">${dir} (${count})</span>`;
    });
    html += '</div>';

    // 当前Tab数据
    const activeData = signalGroups[activeSignalDir] || [];
    if (signalDirPages[activeSignalDir] === undefined) signalDirPages[activeSignalDir] = 1;
    const page = signalDirPages[activeSignalDir];
    const totalPages = Math.ceil(activeData.length / SIGNAL_PER_PAGE);
    const start = (page - 1) * SIGNAL_PER_PAGE;
    const pageItems = activeData.slice(start, start + SIGNAL_PER_PAGE);

    // 每只股票用公共 signalStockCard
    pageItems.forEach((s, idx) => {
        const card = signalStockCard(s, start + idx + 1);
        html += card.replace(/id="hchart_/g, `id="mchart_${activeSignalDir}_`)
                    .replace(/toggleChart\('hchart_/g, `toggleMChart('mchart_${activeSignalDir}_`)
                    .replace(/toggleChart\('/g, `toggleMChart('`);
    });

    // 分页
    if (totalPages > 1) {
        html += `<div style="text-align:center;margin-top:8px;font-size:12px;">`;
        html += `<span onclick="goSignalDirPage(${page-1})" style="cursor:pointer;color:${page>1?'#4ecdc4':'#333'};margin:0 8px;">◀</span>`;
        html += `<span style="color:#888;">第${page}/${totalPages}页</span>`;
        html += `<span onclick="goSignalDirPage(${page+1})" style="cursor:pointer;color:${page<totalPages?'#4ecdc4':'#333'};margin:0 8px;">▶</span>`;
        html += `</div>`;
    }

    html += `<div style="text-align:right;font-size:10px;color:#555;margin-top:4px;">扫描: ${signalDataCache.scan_time || ''} | ${signalDataCache.stocks_scanned || 0}只扫描 | ${activeData.length}个信号</div>`;
    document.getElementById('buySignalsArea').innerHTML = html;
}

function switchSignalDir(dir) {
    activeSignalDir = dir;
    if (signalDirPages[dir] === undefined) signalDirPages[dir] = 1;
    renderBuySignalsPage();
}

function goSignalDirPage(page) {
    const activeData = signalGroups[activeSignalDir] || [];
    const totalPages = Math.ceil(activeData.length / SIGNAL_PER_PAGE);
    if (page < 1 || page > totalPages) return;
    signalDirPages[activeSignalDir] = page;
    renderBuySignalsPage();
}

// 买点信号图表切换（点击📊展开/收起K线图）
function toggleMChart(id, code) {
    const div = document.getElementById(id);
    if (!div) return;
    const obj = div.querySelector('object');
    if (div.style.display === 'none') {
        div.style.display = 'block';
        obj.data = '/pub/charts/' + code + '.svg?t=' + Date.now();
    } else {
        div.style.display = 'none';
        // 不清空data，保持缓存
    }
}

// ====== 龙头观测 ======
let leaderTab = 'industry';
let leaderData = [];
let leaderPage = 1;
let leaderSort = {col: 'chg', asc: false};
const LEADER_PAGE_SIZE = 10;

function switchLeaderTab(tab) {
    leaderTab = tab;
    document.getElementById('tabIndustryLeaders').className = tab === 'industry' ? 'tab-btn active' : 'tab-btn';
    document.getElementById('tabMarketLeaders').className = tab === 'market' ? 'tab-btn active' : 'tab-btn';
    if (tab === 'industry') loadIndustryLeaders();
    else loadMarketLeaders();
}

function leaderSortBy(col) {
    if (leaderSort.col === col) leaderSort.asc = !leaderSort.asc;
    else { leaderSort.col = col; leaderSort.asc = true; }
    renderIndustryLeaders();
}

function loadIndustryLeaders() {
    const area = document.getElementById('leaderArea');
    area.innerHTML = '<div class="empty">加载中...</div>';
    fetch('/api/monitor/leaders')
        .then(r => r.json())
        .then(data => {
            const industries = data.by_industry || {};
            const keys = Object.keys(industries);
            if (keys.length === 0) {
                area.innerHTML = '<div class="empty">暂无行业龙头数据</div>';
                return;
            }
            // 展平为数组
            leaderData = keys.map(ind => {
                const top = industries[ind][0] || {};
                return {
                    industry: ind,
                    name: top.name || '',
                    chg: parseFloat(top.chg) || 0,
                    price: top.price || '',
                    mcap: top.mcap ? parseFloat(top.mcap) / 100000000 : 0,
                };
            });
            leaderPage = 1;
            renderIndustryLeaders();
        })
        .catch(() => { area.innerHTML = '<div class="empty">加载失败</div>'; });
}

function renderIndustryLeaders() {
    const area = document.getElementById('leaderArea');
    let items = [...leaderData];

    // 排序
    const col = leaderSort.col;
    items.sort((a, b) => {
        if (col === 'industry') return leaderSort.asc ? a.industry.localeCompare(b.industry) : b.industry.localeCompare(a.industry);
        if (col === 'chg') return leaderSort.asc ? a.chg - b.chg : b.chg - a.chg;
        if (col === 'mcap') return leaderSort.asc ? a.mcap - b.mcap : b.mcap - a.mcap;
        return 0;
    });

    const totalPages = Math.ceil(items.length / LEADER_PAGE_SIZE);
    if (leaderPage > totalPages) leaderPage = totalPages;
    const start = (leaderPage - 1) * LEADER_PAGE_SIZE;
    const pageItems = items.slice(start, start + LEADER_PAGE_SIZE);

    function sortArrow(colName, label) {
        const active = leaderSort.col === colName;
        const dir = active ? (leaderSort.asc ? '▲' : '▼') : '';
        return `<span onclick="leaderSortBy('${colName}')" style="cursor:pointer;user-select:none;">${label} ${dir}</span>`;
    }

    let html = `<table class="leader-table"><tr>
        <th>${sortArrow('industry', '细分行业')}</th>
        <th>龙头股</th>
        <th>${sortArrow('chg', '涨跌幅')}</th>
        <th>现价</th>
        <th>${sortArrow('mcap', '总市值')}</th>
    </tr>`;

    pageItems.forEach(item => {
        const mcapStr = item.mcap > 0 ? item.mcap.toFixed(1) + '亿' : '-';
        html += `<tr>
            <td style="color:#aaa;">${item.industry}</td>
            <td><b>${item.name}</b></td>
            <td class="${item.chg >= 0 ? 'up' : 'down'}">${item.chg >= 0 ? '+' : ''}${item.chg}%</td>
            <td>${item.price}</td>
            <td style="color:#888;font-size:10px;">${mcapStr}</td>
        </tr>`;
    });
    html += '</table>';

    // 分页
    if (totalPages > 1) {
        html += `<div style="text-align:center;margin-top:8px;font-size:12px;">`;
        html += `<span onclick="leaderPageChange(${leaderPage-1})" style="cursor:pointer;color:${leaderPage>1?'#4ecdc4':'#333'};margin:0 8px;">◀</span>`;
        html += `<span style="color:#888;">第${leaderPage}/${totalPages}页</span>`;
        html += `<span onclick="leaderPageChange(${leaderPage+1})" style="cursor:pointer;color:${leaderPage<totalPages?'#4ecdc4':'#333'};margin:0 8px;">▶</span>`;
        html += `</div>`;
    }

    html += `<div style="text-align:right;font-size:10px;color:#555;margin-top:4px;">共${leaderData.length}个细分行业 | 按${leaderSort.col==='industry'?'行业名称':leaderSort.col==='chg'?'涨跌幅':'总市值'}${leaderSort.asc?'升序':'降序'}排列</div>`;
    area.innerHTML = html;
}

function leaderPageChange(page) {
    const totalPages = Math.ceil(leaderData.length / LEADER_PAGE_SIZE);
    if (page < 1 || page > totalPages) return;
    leaderPage = page;
    renderIndustryLeaders();
}

function loadMarketLeaders() {
    const area = document.getElementById('leaderArea');
    area.innerHTML = '<div class="empty">扫描中...</div>';
    fetch('/api/monitor/market-leaders')
        .then(r => r.json())
        .then(data => {
            const list = data.leaders || [];
            if (list.length === 0) {
                area.innerHTML = '<div class="empty">暂无符合条件的市场龙头<br><span style="font-size:10px;color:#666;">条件：近5日行业涨幅第一 + 成交额第一 + MA10向上 + 换手率>3%</span></div>';
                return;
            }
            let html = `<div style="font-size:11px;color:#888;margin-bottom:6px;">扫描时间: ${data.scan_time || '-'} | 共${data.total_industries||'-'}行业, 筛选出${list.length}只龙头</div>`;
            html += `<table class="leader-table"><tr>
                <th>行业</th>
                <th>股票</th>
                <th>5日涨幅</th>
                <th>今日涨跌</th>
                <th>换手率</th>
                <th>MA10方向</th>
                <th>现价</th>
            </tr>`;
            list.forEach(item => {
                const gainClass = item.gain_5d >= 0 ? 'up' : 'down';
                const chgClass = item.change_pct >= 0 ? 'up' : 'down';
                const ma10Icon = item.ma10_up ? '📈' : '📉';
                html += `<tr>
                    <td style="color:#aaa;font-size:10px;">${item.industry}</td>
                    <td><b>${item.name}</b></td>
                    <td class="${gainClass}">${item.gain_5d >= 0 ? '+' : ''}${item.gain_5d}%</td>
                    <td class="${chgClass}">${item.change_pct >= 0 ? '+' : ''}${item.change_pct}%</td>
                    <td style="color:#888;">${item.turnover_rate}%</td>
                    <td>${ma10Icon}</td>
                    <td style="color:#ccc;">${item.price.toFixed(2)}</td>
                </tr>`;
            });
            html += '</table>';
            html += `<div style="text-align:right;font-size:10px;color:#444;margin-top:4px;">每10分钟刷新 · 数据缓存至收盘</div>`;
            area.innerHTML = html;
        })
        .catch(() => {
            area.innerHTML = '<div class="empty">加载失败</div>';
        });
}

// ====== 止损预警 ======
function updateStopLoss(data) {
    const area = document.getElementById('stopLossArea');
    const list = data.triggered || [];
    document.getElementById('stopLossBadge').textContent = list.length;

    if (list.length === 0) {
        area.innerHTML = '<div class="empty">✅ 暂无触发止损</div>';
        return;
    }
    let html = '';
    list.forEach(s => {
        html += `<div class="stop-loss-item">
            <div class="code">${s.name} (${s.code})</div>
            <div class="detail">
                <span>现价: <b style="color:#e94560;">${s.current_price.toFixed(2)}</b></span>
                <span>止损: ${s.stop_loss.toFixed(2)}</span>
                <span>亏损: <b style="color:#e94560;">${s.loss_pct}%</b></span>
                <span>理由: ${s.reason || '-'}</span>
            </div>
        </div>`;
    });
    area.innerHTML = html;
}

// ====== Phase2: 计划层 — 加载昨日日志的计划 ======
function loadTodayPlan() {
    const area = document.getElementById('todayPlanArea');
    const badge = document.getElementById('planBadge');
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yStr = yesterday.toISOString().slice(0, 10);

    fetch('/api/workbench/get?date=' + yStr)
        .then(r => r.json())
        .then(data => {
            const plan = data.plan || {};
            const buy = plan.buy || [];
            const sell = plan.sell || [];
            const watch = plan.watch || [];
            const total = buy.length + sell.length + watch.length;

            if (total === 0) {
                area.innerHTML = '<div class="empty">昨日无计划</div>';
                badge.textContent = '0项';
                badge.style.background = '#555';
                return;
            }

            badge.textContent = total + '项';
            badge.style.background = '#e94560';

            let html = '<div style="font-size:11px;color:#555;margin-bottom:6px;">📅 ' + yStr + ' 计划</div>';
            if (buy.length) {
                html += '<div style="font-size:11px;margin-bottom:4px;">🟢 买入：</div>';
                html += renderPlanItems(buy, 'buy');
            }
            if (sell.length) {
                html += '<div style="font-size:11px;margin:6px 0 4px;">🔴 卖出：</div>';
                html += renderPlanItems(sell, 'sell');
            }
            if (watch.length) {
                html += '<div style="font-size:11px;margin:6px 0 4px;">👁️ 观察：</div>';
                html += renderPlanItems(watch, 'watch');
            }
            area.innerHTML = html;
        })
        .catch(() => {
            area.innerHTML = '<div class="empty">加载失败</div>';
            badge.textContent = '失败';
        });
}

function renderPlanItems(items, type) {
    if (type === 'watch') {
        return items.map(p =>
            '<div style="display:flex;gap:8px;align-items:center;padding:3px 8px;border-radius:4px;background:rgba(255,255,255,0.02);margin-bottom:2px;font-size:12px;">' +
                '<span style="color:#e0e0e0;">' + (p.stock || p.sector || '--') + '</span>' +
                '<span style="color:#888;">→</span>' +
                '<span style="color:#aaa;">' + (p.focus || '') + '</span>' +
                '<span style="margin-left:auto;">' + statusLabel(p.status) + '</span>' +
            '</div>'
        ).join('');
    }
    return items.map(p =>
        '<div style="display:flex;gap:8px;align-items:center;padding:3px 8px;border-radius:4px;background:rgba(255,255,255,0.02);margin-bottom:2px;font-size:12px;">' +
            '<span style="color:#e0e0e0;">' + (p.stock || '--') + '</span>' +
            '<span style="color:#888;font-size:10px;">' + (p.condition || '') + '</span>' +
            '<span style="color:#555;font-size:10px;">' + (p.qty || '') + '</span>' +
            '<span style="margin-left:auto;">' + statusLabel(p.status) + '</span>' +
        '</div>'
    ).join('');
}

function statusLabel(s) {
    switch(s) {
        case 'executed': return '<span style="color:#22c55e;">✅ 已执行</span>';
        case 'triggered': return '<span style="color:#ffd700;">⚡ 已触发</span>';
        case 'not_triggered': return '<span style="color:#e94560;">❌ 未触发</span>';
        default: return '<span style="color:#888;">⏳ 待触发</span>';
    }
}

// ====== Phase2: 报警层 + 声音 ======
let audioCtx = null;

function getAudioCtx() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtx;
}

function playAlarmSound(type) {
    try {
        const ctx = getAudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        switch(type) {
            case 'buy':  // 一声叮
                osc.frequency.value = 880;
                osc.type = 'sine';
                gain.gain.value = 0.3;
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.15);
                break;
            case 'stop':  // 急促叮叮叮
                osc.frequency.value = 660;
                osc.type = 'square';
                gain.gain.value = 0.4;
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.08);
                // Chain 3 beeps
                setTimeout(() => playAlarmSound('stop'), 200);
                setTimeout(() => playAlarmSound('stop'), 400);
                break;
            case 'warn':  // 一声咚
                osc.frequency.value = 330;
                osc.type = 'triangle';
                gain.gain.value = 0.3;
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.2);
                break;
            case 'abnormal':  // 嘟嘟
                osc.frequency.value = 440;
                osc.type = 'sawtooth';
                gain.gain.value = 0.2;
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.1);
                setTimeout(() => playAlarmSound('abnormal'), 150);
                break;
            default:  // 轻叮
                osc.frequency.value = 660;
                osc.type = 'sine';
                gain.gain.value = 0.2;
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.1);
        }
    } catch(e) { /* audio not supported */ }
}

function sendBrowserNotification(title, body) {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'granted') {
        new Notification(title, { body: body, icon: '/favicon.ico' });
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => {
            if (p === 'granted') {
                new Notification(title, { body: body, icon: '/favicon.ico' });
            }
        });
    }
}

function pushAlarm(msg, type) {
    const panel = document.getElementById('alarmPanel');
    const badge = document.getElementById('alarmBadge');
    if (!panel) return;

    // Remove empty state
    const emptyEl = panel.querySelector('.empty');
    if (emptyEl) panel.innerHTML = '';

    const colors = { buy: '#22c55e', stop: '#e94560', warn: '#ffd700', abnormal: '#ff9800', info: '#2196f3' };
    const icons = { buy: '🟢', stop: '🔴', warn: '🟡', abnormal: '🔔', info: 'ℹ️' };
    const c = colors[type] || '#888';
    const ic = icons[type] || 'ℹ️';

    const el = document.createElement('div');
    el.style.cssText = 'display:flex;gap:8px;align-items:flex-start;padding:6px 10px;margin-bottom:4px;border-radius:6px;background:rgba(255,255,255,0.02);border-left:3px solid ' + c + ';font-size:12px;';
    el.innerHTML = '<span>' + ic + '</span><span style="color:#e0e0e0;">' + msg + '</span>';

    // Prepend so newest is first
    panel.insertBefore(el, panel.firstChild);

    // Update badge count
    const count = panel.children.length;
    badge.textContent = count;
    badge.style.background = count > 0 ? '#e94560' : '#555';

    // Play sound and notify
    playAlarmSound(type);
    sendBrowserNotification('3L 盯盘报警', msg);

    // Keep max 20 alarms
    while (panel.children.length > 20) {
        panel.removeChild(panel.lastChild);
    }
}

// ====== Phase2: 报警检测 ======
function checkPlanAlarms(data) {
    // Load plan from workbench and compare with current market data
    // Placeholder: for now, basic price checks against plan conditions
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yStr = yesterday.toISOString().slice(0, 10);

    fetch('/api/workbench/get?date=' + yStr)
        .then(r => r.json())
        .then(log => {
            const plan = log.plan || {};
            const buy = plan.buy || [];
            const sell = plan.sell || [];

            // Check buy conditions: if stock price is near EMA5 (simplified)
            // This is a placeholder — real condition detection needs K-line data
            buy.forEach(p => {
                if (!p.stock || p.status === 'executed') return;
                // Check if stock has buy signal
                fetch('/api/stock-summary?code=' + p.stock)
                    .then(r => r.json())
                    .then(s => {
                        if (s.bias5 !== undefined && Math.abs(s.bias5) < 2) {
                            pushAlarm(p.stock + ' 接近回踩到位 (BIAS5=' + s.bias5.toFixed(1) + '%)', 'buy');
                        }
                    })
                    .catch(() => {});
            });

            // Check sell conditions
            sell.forEach(p => {
                if (!p.stock || p.status === 'executed') return;
                fetch('/api/stock-summary?code=' + p.stock)
                    .then(r => r.json())
                    .then(s => {
                        if (s.bias5 !== undefined && s.bias5 < -3) {
                            pushAlarm(p.stock + ' 跌破均线 (BIAS5=' + s.bias5.toFixed(1) + '%)', 'stop');
                        }
                    })
                    .catch(() => {});
            });
        })
        .catch(() => {});
}

// 收盘前15分钟提醒
function checkClosingAlarm() {
    const now = new Date();
    const h = now.getHours();
    const m = now.getMinutes();
    // A-share close at 15:00
    if (h === 14 && m >= 45) {
        pushAlarm('收盘前' + (60 - m) + '分钟，检查有无未执行计划', 'info');
    }
}

// ====== Phase2: 外围参考 ======
function loadExternalMapping() {
    const body = document.getElementById('externalBody');
    const badge = document.getElementById('externalUpdateBadge');
    if (!body) return;

    fetch('/api/external-mapping')
        .then(r => r.json())
        .then(data => {
            badge.textContent = data.updated || '已加载';

            let html = '<div style="font-size:10px;color:#555;margin-bottom:6px;">实时行情待接入 · 影响板块按文章映射</div>';

            (data.categories || []).forEach(cat => {
                html += '<div class="ext-section">';
                html += '<div class="ext-section-title">🔥 ' + cat.name + '</div>';

                (cat.stocks || []).forEach(s => {
                    const isUp = Math.random() > 0.5;
                    const change = (Math.random() * 5).toFixed(1);
                    const changeStr = (isUp ? '+' : '-') + change + '%';
                    const arrow = isUp ? '↑' : '↓';
                    const hot = parseFloat(change) > 3;
                    html += '<div class="ext-row" onclick="toggleExtDetail(\'' + s.code + '\')">';
                    html += '  <span class="ext-code">' + s.code + '</span>';
                    html += '  <span class="ext-change ' + (isUp ? 'up' : 'down') + '">' + changeStr + '</span>';
                    html += '  <span class="ext-arrow">' + arrow + '</span>';
                    html += '  <span class="ext-impact">→ ' + (s.impact || s.sectors || '') + '</span>';
                    if (hot) html += '<span class="ext-hot">🔥</span>';
                    html += '</div>';
                    html += '<div class="ext-detail" id="extDetail_' + s.code + '">';
                    html += '  <div><span class="dl">美股：</span><span class="dv">' + s.name + ' (' + s.code + ')</span></div>';
                    html += '  <div><span class="dl">影响板块：</span><span class="dv">' + (s.sectors || '') + '</span></div>';
                    html += '  <div style="margin-top:4px;"><span class="dl">核心供应商：</span></div>';
                    html += '  <div class="dv">' + (s.suppliers || '暂无') + '</div>';
                    if (s.potential) {
                        html += '  <div style="margin-top:4px;"><span class="dl">潜在受益：</span></div>';
                        html += '  <div class="dv">' + s.potential + '</div>';
                    }
                    if (s.counterparts) {
                        html += '  <div style="margin-top:4px;"><span class="dl">A股对标：</span><span class="dv">' + s.counterparts + '</span></div>';
                    }
                    html += '</div>';
                });
                html += '</div>';
            });

            if (data.source_url) {
                html += '<div class="ext-source">📎 <a href="' + data.source_url + '" target="_blank">' + (data.source || '原文') + '</a></div>';
            }
            body.innerHTML = html;
        })
        .catch(() => {
            body.innerHTML = '<div class="empty">加载失败</div>';
            badge.textContent = '失败';
        });
}

function toggleExtDetail(code) {
    const el = document.getElementById('extDetail_' + code);
    if (el) {
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }
}

function refreshAll() {
    const badge = document.getElementById('updateBadge');
    const now = new Date();
    badge.textContent = `更新中 ${now.toLocaleTimeString('zh-CN', {hour12:false})}`;

    // 成交量
    fetch('/api/monitor/volume')
        .then(r => r.json())
        .then(data => {
            updateQuote(data);
            updateVolumeChart(data);
        })
        .catch(() => {});

    // 板块排行（供买点信号排序用）
    fetch('/api/industry-boards')
        .then(r => r.json())
        .then(data => { industryBoardsCache = data.data || []; })
        .catch(() => {});

    // 买点信号
    fetch('/api/monitor/buy-signals')
        .then(r => r.json())
        .then(data => updateBuySignals(data))
        .catch(() => {});

    // 止损预警
    fetch('/api/monitor/stop-loss')
        .then(r => r.json())
        .then(data => updateStopLoss(data))
        .catch(() => {});

    // 检查报警（每60秒一次）
    const nowMs = Date.now();
    if (!window._lastAlarmCheck || nowMs - window._lastAlarmCheck > 60000) {
        window._lastAlarmCheck = nowMs;
        checkPlanAlarms(data);
        checkClosingAlarm();
    }

    // 龙头观测（10分钟刷新）
    const nowMs2 = Date.now();
    if (!window._lastLeaderRefresh || nowMs2 - window._lastLeaderRefresh > 600000) {
        window._lastLeaderRefresh = nowMs2;
        if (leaderTab === 'industry') loadIndustryLeaders();
        else loadMarketLeaders();
    }

    const t = new Date();
    badge.textContent = `最后更新 ${t.toLocaleTimeString('zh-CN', {hour12:false})}`;
}


// ====== 初始化 ======
// 先加载板块和行业映射（仅首次），再加载所有数据
loadTopSectors();
loadIndustryLeaders();
loadIndustryMap().then(() => {
    refreshAll();
    loadTodayPlan();
    loadExternalMapping();
});
setInterval(refreshAll, REFRESH_INTERVAL);

// 请求浏览器通知权限
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}